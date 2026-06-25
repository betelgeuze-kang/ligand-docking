from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/product", tags=["product-cameo-runner"])

ROOT = Path(__file__).resolve().parents[1]
API_RUNNER_PROFILE_PROMOTION_OPERATOR_RECEIPT_ARTIFACT = (
    ROOT / "runs" / "api_runner_profile_promotion_operator_receipt_current.json"
)
API_RUNNER_PROFILE_PROMOTION_OPERATOR_STAGING_APPLY_ARTIFACT = (
    ROOT / "runs" / "api_runner_profile_promotion_operator_staging_apply_current.json"
)
CAMEO_VALIDATION_OPERATIONS_ARTIFACT = ROOT / "runs" / "cameo_validation_operations_dossier_current.json"
CAMEO_OFFICIAL_RESULTS_ARTIFACT = ROOT / "runs" / "cameo_official_results_intake_gate_current.json"
CAMEO_OFFICIAL_RESULTS_TEMPLATE = ROOT / "runs" / "cameo_official_results_operator_template_current.csv"
CAMEO_OFFICIAL_RESULTS_INTAKE = ROOT / "runs" / "cameo_official_results_operator_intake.csv"
CAMEO_OFFICIAL_RESULT_FETCH_PREFLIGHT_ARTIFACT = (
    ROOT / "runs" / "cameo_official_result_fetch_preflight_current.json"
)
CAMEO_OFFICIAL_RESULT_FETCH_TEMPLATE = (
    ROOT / "runs" / "cameo_official_result_fetch_operator_approval_template_current.csv"
)
CAMEO_OFFICIAL_RESULT_FETCH_INTAKE = (
    ROOT / "runs" / "cameo_official_result_fetch_operator_approval_intake.csv"
)
CAMEO_PUBLIC_REGISTRATION_ARTIFACT = ROOT / "runs" / "cameo_public_registration_approval_gate_current.json"
CAMEO_PUBLIC_REGISTRATION_TEMPLATE = ROOT / "runs" / "cameo_public_registration_operator_approval_template_current.csv"
CAMEO_PUBLIC_REGISTRATION_INTAKE = ROOT / "runs" / "cameo_public_registration_operator_approval_intake.csv"


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


@router.get("/cameo-live-validation")
async def get_product_cameo_live_validation() -> dict[str, Any]:
    packet = _read_json_object(CAMEO_VALIDATION_OPERATIONS_ARTIFACT)
    official_packet = _read_json_object(CAMEO_OFFICIAL_RESULTS_ARTIFACT)
    registration_packet = _read_json_object(CAMEO_PUBLIC_REGISTRATION_ARTIFACT)
    summary = _summary(packet)
    official = _summary(official_packet)
    registration = _summary(registration_packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_cameo_validation_operations_dossier",
            "artifact_path": str(CAMEO_VALIDATION_OPERATIONS_ARTIFACT),
            "validation_ready": False,
            "official_result_required": True,
            "official_results_intake_ready": False,
            "official_results_intake_status": "",
            "official_results_operator_template_csv": str(CAMEO_OFFICIAL_RESULTS_TEMPLATE),
            "official_results_operator_intake_csv": str(CAMEO_OFFICIAL_RESULTS_INTAKE),
            "official_results_blocker_codes": [],
            "public_registration_allowed": False,
            "registration_gate_status": "",
            "registration_operator_template_csv": str(CAMEO_PUBLIC_REGISTRATION_TEMPLATE),
            "registration_operator_approval_csv": str(CAMEO_PUBLIC_REGISTRATION_INTAKE),
            "approval_tokens_required": [],
            "next_required_step": "",
            "server_started": False,
            "outbound_email_enabled": False,
            "server_registration_mutated": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product CAMEO live-validation endpoint only; the local CAMEO validation operations dossier is missing "
                "or invalid. It does not start a server, register a CAMEO server, send email, fetch official results, "
                "submit predictions, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(CAMEO_VALIDATION_OPERATIONS_ARTIFACT),
        "validation_ready": bool(summary.get("validation_ready") is True),
        "validation_readiness_status": summary.get("validation_readiness_status", ""),
        "official_result_required": bool(summary.get("official_result_required") is True),
        "official_results_intake_ready": bool(summary.get("official_results_intake_ready") is True),
        "official_results_intake_status": summary.get("official_results_intake_status", ""),
        "official_results_intake_blocker_count": int(summary.get("official_results_intake_blocker_count") or 0),
        "official_results_gate_status": official.get("status", ""),
        "official_results_result_row_count": int(official.get("result_row_count") or 0),
        "official_results_accepted_count": int(official.get("accepted_official_result_count") or 0),
        "official_results_rejected_count": int(official.get("rejected_official_result_count") or 0),
        "official_results_blocker_codes": list(official.get("blocker_codes") or []),
        "official_results_operator_template_csv": official.get("operator_template_csv") or str(CAMEO_OFFICIAL_RESULTS_TEMPLATE),
        "official_results_operator_intake_csv": official.get("operator_intake_csv") or str(CAMEO_OFFICIAL_RESULTS_INTAKE),
        "official_results_required_columns": list(official.get("required_columns") or []),
        "official_results_missing_required_columns": list(official.get("missing_required_columns") or []),
        "official_results_metric_columns": list(official.get("official_metric_columns") or []),
        "official_model1_result_ready": bool(summary.get("official_model1_result_ready") is True),
        "official_cameo_results_used": bool(summary.get("official_cameo_results_used") is True),
        "official_results_pending_honest": bool(summary.get("official_results_pending_honest") is True),
        "receiver_smoke_status": summary.get("receiver_smoke_status", ""),
        "api_dependency_status": summary.get("api_dependency_status", ""),
        "evidence_integrity_ready": bool(summary.get("evidence_integrity_ready") is True),
        "evidence_integrity_status": summary.get("evidence_integrity_status", ""),
        "public_registration_allowed": bool(summary.get("public_registration_allowed") is True),
        "registration_gate_status": registration.get("status", ""),
        "registration_authorized_for_review": bool(registration.get("authorized_for_registration_review") is True),
        "registration_operator_template_csv": registration.get("operator_template_csv")
        or str(CAMEO_PUBLIC_REGISTRATION_TEMPLATE),
        "registration_operator_approval_csv": registration.get("operator_approval_csv")
        or str(CAMEO_PUBLIC_REGISTRATION_INTAKE),
        "registration_blocker_count": int(registration.get("blocker_count") or 0),
        "registration_blockers": list(registration.get("blockers") or []),
        "registration_approval_token_required": summary.get("registration_approval_token_required", ""),
        "outbound_email_approval_token_required": summary.get("outbound_email_approval_token_required", ""),
        "approval_token_count": int(summary.get("approval_token_count") or 0),
        "approval_tokens_required": list(summary.get("approval_tokens_required") or []),
        "next_required_step": summary.get("next_required_step", ""),
        "stages": rows,
        "server_started": bool(summary.get("server_started") is True),
        "outbound_email_enabled": bool(summary.get("outbound_email_enabled") is True),
        "server_registration_mutated": bool(summary.get("server_registration_mutated") is True),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": bool(summary.get("external_state_mutated") is True),
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/cameo-official-result-fetch-preflight")
async def get_product_cameo_official_result_fetch_preflight() -> dict[str, Any]:
    packet = _read_json_object(CAMEO_OFFICIAL_RESULT_FETCH_PREFLIGHT_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_cameo_official_result_fetch_preflight",
            "artifact_path": str(CAMEO_OFFICIAL_RESULT_FETCH_PREFLIGHT_ARTIFACT),
            "official_result_fetch_preflight_ready": False,
            "operations_surface_ready": False,
            "receiver_smoke_ready": False,
            "source_operations_dossier_status": "",
            "operator_template_csv": str(CAMEO_OFFICIAL_RESULT_FETCH_TEMPLATE),
            "operator_fetch_csv": str(CAMEO_OFFICIAL_RESULT_FETCH_INTAKE),
            "operator_fetch_csv_present": False,
            "fetch_approval_token_required": "APPROVE_CAMEO_OFFICIAL_RESULT_FETCH",
            "authorized_for_separate_operator_fetch": False,
            "authorized_row_count": 0,
            "awaiting_operator_fetch_approval_row_count": 0,
            "blocked_row_count": 0,
            "skipped_row_count": 0,
            "target_id": "",
            "blocker_count": 1,
            "blockers": [],
            "fetch_rows": [],
            "next_required_step": "",
            "network_request_opened": False,
            "official_results_fetched": False,
            "native_local_accuracy_used": False,
            "outbound_email_enabled": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product CAMEO official result fetch preflight endpoint only; the local preflight artifact is "
                "missing or invalid. It does not open network connections, fetch official CAMEO pages, parse "
                "remote content, use local native accuracy, send email, upload, delete, commit, push, or mutate "
                "external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(CAMEO_OFFICIAL_RESULT_FETCH_PREFLIGHT_ARTIFACT),
        "official_result_fetch_preflight_ready": (
            summary.get("status") == "cameo_official_result_fetch_preflight_ready"
        ),
        "operations_surface_ready": bool(summary.get("operations_surface_ready") is True),
        "receiver_smoke_ready": bool(summary.get("receiver_smoke_ready") is True),
        "source_operations_dossier_status": summary.get("source_operations_dossier_status", ""),
        "operator_template_csv": summary.get("operator_template_csv")
        or str(CAMEO_OFFICIAL_RESULT_FETCH_TEMPLATE),
        "operator_fetch_csv": summary.get("operator_fetch_csv")
        or str(CAMEO_OFFICIAL_RESULT_FETCH_INTAKE),
        "operator_fetch_csv_present": bool(summary.get("operator_fetch_csv_present") is True),
        "fetch_approval_token_required": summary.get(
            "fetch_approval_token_required", "APPROVE_CAMEO_OFFICIAL_RESULT_FETCH"
        ),
        "authorized_for_separate_operator_fetch": bool(
            summary.get("authorized_for_separate_operator_fetch") is True
        ),
        "authorized_row_count": int(summary.get("authorized_row_count") or 0),
        "awaiting_operator_fetch_approval_row_count": int(
            summary.get("awaiting_operator_fetch_approval_row_count") or 0
        ),
        "blocked_row_count": int(summary.get("blocked_row_count") or 0),
        "skipped_row_count": int(summary.get("skipped_row_count") or 0),
        "target_id": summary.get("target_id", ""),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "blockers": list(summary.get("blockers") or []),
        "fetch_rows": rows,
        "next_required_step": summary.get("next_required_step", ""),
        "network_request_opened": bool(summary.get("network_request_opened") is True),
        "official_results_fetched": bool(summary.get("official_results_fetched") is True),
        "native_local_accuracy_used": bool(summary.get("native_local_accuracy_used") is True),
        "outbound_email_enabled": bool(summary.get("outbound_email_enabled") is True),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": bool(summary.get("external_state_mutated") is True),
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/api-runner-profile-promotion-operator-receipt")
async def get_product_api_runner_profile_promotion_operator_receipt() -> dict[str, Any]:
    packet = _read_json_object(API_RUNNER_PROFILE_PROMOTION_OPERATOR_RECEIPT_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_api_runner_profile_promotion_operator_receipt",
            "artifact_path": str(API_RUNNER_PROFILE_PROMOTION_OPERATOR_RECEIPT_ARTIFACT),
            "operator_receipt_ready": False,
            "readiness_artifact": "",
            "readiness_status": "",
            "operator_template_csv": "",
            "profile_count": 0,
            "receipt_row_count": 0,
            "pass_row_count": 0,
            "blocked_row_count": 0,
            "first_blocked_profile_id": "",
            "first_blocked_row_blocker": "",
            "first_blocked_row_blockers": [],
            "most_common_row_blocker": "",
            "approved_profile_count": 0,
            "held_profile_count": 0,
            "missing_profile_count": 0,
            "duplicate_profile_count": 0,
            "missing_columns": [],
            "approval_token_required": "APPROVE_API_RUNNER_PROFILE_PROMOTION",
            "profile_enabled_by_this_tool": False,
            "runner_executed": False,
            "profile_promoted": False,
            "blocker_count": 1,
            "blockers": [],
            "receipt_rows": [],
            "next_required_step": "",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "API runner profile promotion operator receipt endpoint only; the local receipt artifact is "
                "missing or invalid. It does not edit profile JSON, enable profiles, run scientific runners, "
                "submit jobs, emit fake results, upload, delete, commit, push, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(API_RUNNER_PROFILE_PROMOTION_OPERATOR_RECEIPT_ARTIFACT),
        "operator_receipt_ready": bool(summary.get("operator_receipt_ready") is True),
        "readiness_artifact": summary.get("readiness_artifact", ""),
        "readiness_status": summary.get("readiness_status", ""),
        "operator_template_csv": summary.get("operator_template_csv", ""),
        "profile_count": int(summary.get("profile_count") or 0),
        "receipt_row_count": int(summary.get("receipt_row_count") or 0),
        "pass_row_count": int(summary.get("pass_row_count") or 0),
        "blocked_row_count": int(summary.get("blocked_row_count") or 0),
        "first_blocked_profile_id": summary.get("first_blocked_profile_id", ""),
        "first_blocked_row_blocker": summary.get("first_blocked_row_blocker", ""),
        "first_blocked_row_blockers": list(summary.get("first_blocked_row_blockers") or []),
        "most_common_row_blocker": summary.get("most_common_row_blocker", ""),
        "approved_profile_count": int(summary.get("approved_profile_count") or 0),
        "held_profile_count": int(summary.get("held_profile_count") or 0),
        "missing_profile_count": int(summary.get("missing_profile_count") or 0),
        "duplicate_profile_count": int(summary.get("duplicate_profile_count") or 0),
        "missing_columns": list(summary.get("missing_columns") or []),
        "approval_token_required": summary.get(
            "approval_token_required", "APPROVE_API_RUNNER_PROFILE_PROMOTION"
        ),
        "profile_enabled_by_this_tool": bool(summary.get("profile_enabled_by_this_tool") is True),
        "runner_executed": bool(summary.get("runner_executed") is True),
        "profile_promoted": False,
        "blocker_count": int(summary.get("blocker_count") or 0),
        "blockers": list(summary.get("blockers") or []),
        "receipt_rows": rows,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": bool(summary.get("external_state_mutated") is True),
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/api-runner-profile-promotion-operator-staging-apply")
async def get_product_api_runner_profile_promotion_operator_staging_apply() -> dict[str, Any]:
    packet = _read_json_object(API_RUNNER_PROFILE_PROMOTION_OPERATOR_STAGING_APPLY_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_api_runner_profile_promotion_operator_staging_apply",
            "artifact_path": str(API_RUNNER_PROFILE_PROMOTION_OPERATOR_STAGING_APPLY_ARTIFACT),
            "mode": "preview",
            "staging_operator_template_csv": "",
            "staging_operator_template_csv_present": False,
            "staging_row_count": 0,
            "staging_missing_required_column_count": 0,
            "live_operator_template_csv": "",
            "live_operator_template_csv_present": False,
            "live_operator_template_row_count": 0,
            "candidate_operator_template_csv": "",
            "candidate_operator_template_written": False,
            "candidate_operator_receipt_ready": False,
            "candidate_operator_receipt_status": "",
            "candidate_profile_count": 0,
            "candidate_pass_row_count": 0,
            "candidate_blocked_row_count": 0,
            "candidate_first_blocked_profile_id": "",
            "candidate_first_blocked_row_blocker": "",
            "candidate_most_common_row_blocker": "",
            "candidate_approved_profile_count": 0,
            "candidate_promote_decision_count": 0,
            "candidate_keep_enabled_decision_count": 0,
            "accuracy_parity_status": "",
            "accuracy_parity_gate_ready": False,
            "overall_commercial_tool_accuracy_parity_allowed": False,
            "schrodinger_class_claim_allowed": False,
            "science_claim_status": "",
            "science_claim_gate_ready": False,
            "science_claim_promotion_allowed": False,
            "science_claim_open_gap_count": 0,
            "science_claim_open_gap_ids": [],
            "broad_promotion_gate_required": False,
            "broad_promotion_gate_ready": False,
            "broad_commercial_profile_promotion_allowed": False,
            "approval_token_required": "",
            "approval_token_present": False,
            "approval_token_accepted": False,
            "live_copy_allowed": False,
            "write_canonical_operator_template_requested": False,
            "canonical_operator_template_written": False,
            "profile_json_edited_by_this_tool": False,
            "profile_enabled_by_this_tool": False,
            "runner_executed": False,
            "docking_results_emitted": False,
            "blocker_count": 1,
            "blockers": ["api_runner_profile_promotion_operator_staging_apply_missing"],
            "staging_rows": [],
            "next_required_step": "",
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "API runner profile promotion operator staging apply endpoint only; the local staging artifact is "
                "missing or invalid. It does not edit profile JSON, enable profiles, run scientific runners, "
                "emit results, upload, delete, commit, push, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(API_RUNNER_PROFILE_PROMOTION_OPERATOR_STAGING_APPLY_ARTIFACT),
        "mode": summary.get("mode", "preview"),
        "staging_operator_template_csv": summary.get("staging_operator_template_csv", ""),
        "staging_operator_template_csv_present": bool(
            summary.get("staging_operator_template_csv_present") is True
        ),
        "staging_row_count": int(summary.get("staging_row_count") or 0),
        "staging_missing_required_column_count": int(
            summary.get("staging_missing_required_column_count") or 0
        ),
        "live_operator_template_csv": summary.get("live_operator_template_csv", ""),
        "live_operator_template_csv_present": bool(
            summary.get("live_operator_template_csv_present") is True
        ),
        "live_operator_template_row_count": int(
            summary.get("live_operator_template_row_count") or 0
        ),
        "candidate_operator_template_csv": summary.get("candidate_operator_template_csv", ""),
        "candidate_operator_template_written": bool(
            summary.get("candidate_operator_template_written") is True
        ),
        "candidate_operator_receipt_ready": bool(
            summary.get("candidate_operator_receipt_ready") is True
        ),
        "candidate_operator_receipt_status": summary.get("candidate_operator_receipt_status", ""),
        "candidate_profile_count": int(summary.get("candidate_profile_count") or 0),
        "candidate_pass_row_count": int(summary.get("candidate_pass_row_count") or 0),
        "candidate_blocked_row_count": int(summary.get("candidate_blocked_row_count") or 0),
        "candidate_first_blocked_profile_id": summary.get(
            "candidate_first_blocked_profile_id", ""
        ),
        "candidate_first_blocked_row_blocker": summary.get(
            "candidate_first_blocked_row_blocker", ""
        ),
        "candidate_most_common_row_blocker": summary.get(
            "candidate_most_common_row_blocker", ""
        ),
        "candidate_approved_profile_count": int(
            summary.get("candidate_approved_profile_count") or 0
        ),
        "candidate_promote_decision_count": int(
            summary.get("candidate_promote_decision_count") or 0
        ),
        "candidate_keep_enabled_decision_count": int(
            summary.get("candidate_keep_enabled_decision_count") or 0
        ),
        "accuracy_parity_status": summary.get("accuracy_parity_status", ""),
        "accuracy_parity_gate_ready": bool(summary.get("accuracy_parity_gate_ready") is True),
        "overall_commercial_tool_accuracy_parity_allowed": bool(
            summary.get("overall_commercial_tool_accuracy_parity_allowed") is True
        ),
        "schrodinger_class_claim_allowed": bool(
            summary.get("schrodinger_class_claim_allowed") is True
        ),
        "science_claim_status": summary.get("science_claim_status", ""),
        "science_claim_gate_ready": bool(summary.get("science_claim_gate_ready") is True),
        "science_claim_promotion_allowed": bool(
            summary.get("science_claim_promotion_allowed") is True
        ),
        "science_claim_open_gap_count": int(summary.get("science_claim_open_gap_count") or 0),
        "science_claim_open_gap_ids": list(summary.get("science_claim_open_gap_ids") or []),
        "broad_promotion_gate_required": bool(
            summary.get("broad_promotion_gate_required") is True
        ),
        "broad_promotion_gate_ready": bool(summary.get("broad_promotion_gate_ready") is True),
        "broad_commercial_profile_promotion_allowed": bool(
            summary.get("broad_commercial_profile_promotion_allowed") is True
        ),
        "approval_token_required": summary.get("approval_token_required", ""),
        "approval_token_present": bool(summary.get("approval_token_present") is True),
        "approval_token_accepted": bool(summary.get("approval_token_accepted") is True),
        "live_copy_allowed": bool(summary.get("live_copy_allowed") is True),
        "write_canonical_operator_template_requested": bool(
            summary.get("write_canonical_operator_template_requested") is True
        ),
        "canonical_operator_template_written": bool(
            summary.get("canonical_operator_template_written") is True
        ),
        "profile_json_edited_by_this_tool": bool(
            summary.get("profile_json_edited_by_this_tool") is True
        ),
        "profile_enabled_by_this_tool": bool(
            summary.get("profile_enabled_by_this_tool") is True
        ),
        "runner_executed": bool(summary.get("runner_executed") is True),
        "docking_results_emitted": bool(summary.get("docking_results_emitted") is True),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "blockers": list(summary.get("blockers") or []),
        "staging_rows": rows,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "external_state_mutated": bool(summary.get("external_state_mutated") is True),
        "claim_boundary": summary.get("claim_boundary", ""),
    }
