from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from api.config import settings
from betelgeuze_cameo.intake import build_intake_record, persist_intake_record
from betelgeuze_cameo.official_results import DISALLOWED_LOCAL_ACCURACY_COLUMNS, METRIC_COLUMNS, REQUIRED_COLUMNS

router = APIRouter(prefix="/cameo", tags=["cameo"])
ROOT = Path(__file__).resolve().parents[1]
CAMEO_VALIDATION_OPERATIONS_ARTIFACT = ROOT / "runs" / "cameo_validation_operations_dossier_current.json"
CAMEO_ARCHITECTURE_VALIDATION_ARTIFACT = ROOT / "runs" / "cameo_architecture_validation_contract_current.json"
CAMEO_API_CONTRACT_ARTIFACT = ROOT / "runs" / "cameo_api_contract_current.json"
CAMEO_SERVICE_BOUNDARY_ARTIFACT = ROOT / "runs" / "cameo_service_boundary_contract_current.json"
CAMEO_EVIDENCE_INTEGRITY_ARTIFACT = ROOT / "runs" / "cameo_evidence_integrity_contract_current.json"
CAMEO_OFFICIAL_RESULTS_ARTIFACT = ROOT / "runs" / "cameo_official_results_intake_gate_current.json"
CAMEO_OFFICIAL_RESULTS_TEMPLATE = ROOT / "runs" / "cameo_official_results_operator_template_current.csv"
CAMEO_OFFICIAL_RESULTS_INTAKE = ROOT / "runs" / "cameo_official_results_operator_intake.csv"
CAMEO_PUBLIC_REGISTRATION_ARTIFACT = ROOT / "runs" / "cameo_public_registration_approval_gate_current.json"
CAMEO_PUBLIC_REGISTRATION_TEMPLATE = ROOT / "runs" / "cameo_public_registration_operator_approval_template_current.csv"
CAMEO_PUBLIC_REGISTRATION_INTAKE = ROOT / "runs" / "cameo_public_registration_operator_approval_intake.csv"
CAMEO_CAPABILITY_PREFLIGHT_ARTIFACT = ROOT / "runs" / "cameo_capability_preflight_current.json"
CAMEO_REGISTRATION_REQUIRED_COLUMNS = [
    "target_id",
    "operator_decision",
    "registration_approval_token",
    "outbound_email_approval_token",
    "public_endpoint_url",
    "results_email",
    "contact_email",
    "operator_note",
]
CAMEO_REGISTRATION_VALID_DECISIONS = ["approve", "skip"]
CAMEO_REGISTRATION_APPROVAL_TOKEN = "APPROVE_CAMEO_SERVER_REGISTRATION"
CAMEO_OUTBOUND_EMAIL_APPROVAL_TOKEN = "APPROVE_CAMEO_OUTBOUND_EMAIL"


class CameoIntakeResponse(BaseModel):
    job_id: str
    status: str
    message: str
    parsed_sequence_count: int
    capability_lane: str


def _jobs_dir() -> Path:
    return Path(settings.results_storage_path) / "cameo_jobs"


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


async def _payload_from_request(request: Request) -> tuple[dict[str, Any], bytes]:
    body = await request.body()
    if body:
        try:
            decoded = json.loads(body.decode("utf-8"))
            if isinstance(decoded, dict):
                return decoded, body
        except Exception:
            pass
        return {"raw_body": body.decode("utf-8", errors="replace")}, body
    return dict(request.query_params), json.dumps(dict(request.query_params), sort_keys=True).encode("utf-8")


async def persist_cameo_intake(request: Request, capability_lane: str) -> dict[str, Any]:
    payload, raw = await _payload_from_request(request)
    record = build_intake_record(
        payload=payload,
        raw_request=raw,
        request_method=request.method,
        source_host=request.client.host if request.client else "",
        capability_lane=capability_lane,
    )
    persist_intake_record(record, _jobs_dir())
    return record


@router.post("/targets", response_model=CameoIntakeResponse)
async def receive_cameo_target_post(
    request: Request,
    capability_lane: str = Query(default="polymer_complex_receiver_dry_run"),
) -> CameoIntakeResponse:
    record = await persist_cameo_intake(request, capability_lane)
    return CameoIntakeResponse(
        job_id=record["job_id"],
        status=record["status"],
        message="CAMEO target received; prediction generation and outbound email are disabled.",
        parsed_sequence_count=record["parsed_sequence_count"],
        capability_lane=record["capability_lane"],
    )


@router.get("/operations")
async def get_cameo_operations() -> dict[str, Any]:
    operations_packet = _read_json_object(CAMEO_VALIDATION_OPERATIONS_ARTIFACT)
    official_packet = _read_json_object(CAMEO_OFFICIAL_RESULTS_ARTIFACT)
    evidence_packet = _read_json_object(CAMEO_EVIDENCE_INTEGRITY_ARTIFACT)
    registration_packet = _read_json_object(CAMEO_PUBLIC_REGISTRATION_ARTIFACT)
    capability_packet = _read_json_object(CAMEO_CAPABILITY_PREFLIGHT_ARTIFACT)
    operations = _summary(operations_packet)
    official = _summary(official_packet)
    evidence = _summary(evidence_packet)
    registration = _summary(registration_packet)
    capability = _summary(capability_packet)
    if not operations:
        return {
            "status": "missing_cameo_validation_operations_dossier",
            "artifact_path": str(CAMEO_VALIDATION_OPERATIONS_ARTIFACT),
            "prediction_generation_enabled": False,
            "outbound_email_enabled": False,
            "server_registration_mutated": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "CAMEO operations endpoint only; the local operations artifact is missing or invalid. "
                "It does not generate predictions, submit CAMEO results, register a server, send email, or mutate external state."
            ),
        }
    return {
        "status": operations.get("status"),
        "artifact_path": str(CAMEO_VALIDATION_OPERATIONS_ARTIFACT),
        "stage_count": int(operations.get("stage_count") or 0),
        "blocked_stage_count": int(operations.get("blocked_stage_count") or 0),
        "approval_required_stage_count": int(operations.get("approval_required_stage_count") or 0),
        "first_blocked_stage_id": operations.get("first_blocked_stage_id", ""),
        "first_blocked_stage_source_status": operations.get("first_blocked_stage_source_status", ""),
        "first_blocked_stage_artifact": operations.get("first_blocked_stage_artifact", ""),
        "first_blocked_stage_blocker_count": int(operations.get("first_blocked_stage_blocker_count") or 0),
        "first_blocked_stage_recommended_action": operations.get("first_blocked_stage_recommended_action", ""),
        "first_approval_required_stage_id": operations.get("first_approval_required_stage_id", ""),
        "first_approval_required_stage_source_status": operations.get("first_approval_required_stage_source_status", ""),
        "first_approval_required_stage_artifact": operations.get("first_approval_required_stage_artifact", ""),
        "first_approval_required_stage_token_required": operations.get(
            "first_approval_required_stage_token_required", ""
        ),
        "first_approval_required_stage_recommended_action": operations.get(
            "first_approval_required_stage_recommended_action", ""
        ),
        "validation_ready": bool(operations.get("validation_ready") is True),
        "official_result_required": bool(operations.get("official_result_required") is True),
        "official_results_intake_status": operations.get("official_results_intake_status", ""),
        "official_results_intake_ready": bool(operations.get("official_results_intake_ready") is True),
        "official_model1_result_ready": bool(operations.get("official_model1_result_ready") is True),
        "official_cameo_results_used": bool(operations.get("official_cameo_results_used") is True),
        "public_registration_allowed": bool(operations.get("public_registration_allowed") is True),
        "receiver_smoke_status": operations.get("receiver_smoke_status", ""),
        "api_dependency_status": operations.get("api_dependency_status", ""),
        "official_results_gate_status": official.get("status", ""),
        "official_results_result_row_count": int(official.get("result_row_count") or 0),
        "official_results_accepted_count": int(official.get("accepted_official_result_count") or 0),
        "official_results_rejected_count": int(official.get("rejected_official_result_count") or 0),
        "official_results_blocker_count": int(official.get("blocker_count") or 0),
        "official_results_blocker_codes": list(official.get("blocker_codes") or []),
        "official_results_operator_template_csv": official.get("operator_template_csv") or str(CAMEO_OFFICIAL_RESULTS_TEMPLATE),
        "official_results_operator_intake_csv": official.get("operator_intake_csv") or str(CAMEO_OFFICIAL_RESULTS_INTAKE),
        "official_results_required_columns": list(official.get("required_columns") or REQUIRED_COLUMNS),
        "official_results_missing_required_columns": list(official.get("missing_required_columns") or []),
        "official_results_metric_columns": list(official.get("official_metric_columns") or METRIC_COLUMNS),
        "official_results_disallowed_local_accuracy_columns": list(
            official.get("disallowed_local_accuracy_columns") or DISALLOWED_LOCAL_ACCURACY_COLUMNS
        ),
        "evidence_integrity_status": operations.get("evidence_integrity_status") or evidence.get("status", ""),
        "evidence_integrity_ready": bool(
            operations.get("evidence_integrity_ready") is True
            or evidence.get("evidence_integrity_ready") is True
        ),
        "evidence_integrity_blocker_count": int(
            operations.get("evidence_integrity_blocker_count")
            if operations.get("evidence_integrity_blocker_count") is not None
            else evidence.get("blocker_count") or 0
        ),
        "official_results_pending_honest": bool(
            operations.get("official_results_pending_honest") is True
            or evidence.get("official_results_pending_honest") is True
        ),
        "no_local_native_accuracy_substitution": bool(
            operations.get("no_local_native_accuracy_substitution") is True
            or evidence.get("no_local_native_accuracy_substitution") is True
        ),
        "external_mutation_flags_clear": bool(
            operations.get("external_mutation_flags_clear") is True
            or evidence.get("external_mutation_flags_clear") is True
        ),
        "registration_gate_status": registration.get("status", ""),
        "registration_authorized_for_review": bool(registration.get("authorized_for_registration_review") is True),
        "registration_operator_template_csv": str(CAMEO_PUBLIC_REGISTRATION_TEMPLATE),
        "registration_operator_approval_csv": str(CAMEO_PUBLIC_REGISTRATION_INTAKE),
        "registration_required_columns": CAMEO_REGISTRATION_REQUIRED_COLUMNS,
        "registration_valid_decisions": CAMEO_REGISTRATION_VALID_DECISIONS,
        "registration_approval_token_required": CAMEO_REGISTRATION_APPROVAL_TOKEN,
        "outbound_email_approval_token_required": CAMEO_OUTBOUND_EMAIL_APPROVAL_TOKEN,
        "capability_preflight_status": capability.get("status", ""),
        "capability_api_route_registered": bool(capability.get("api_route_registered") is True),
        "capability_operations_route_registered": bool(capability.get("api_operations_route_registered") is True),
        "prediction_generation_enabled": False,
        "outbound_email_enabled": False,
        "server_registration_mutated": False,
        "external_state_mutated": False,
        "native_local_accuracy_used": False,
        "claim_boundary": operations.get("claim_boundary", ""),
    }


@router.get("/service-boundary")
async def get_cameo_service_boundary() -> dict[str, Any]:
    packet = _read_json_object(CAMEO_SERVICE_BOUNDARY_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_cameo_service_boundary_contract",
            "artifact_path": str(CAMEO_SERVICE_BOUNDARY_ARTIFACT),
            "service_boundary_ready": False,
            "check_count": 0,
            "blocker_count": 1,
            "server_started": False,
            "server_registration_mutated": False,
            "prediction_generation_enabled": False,
            "outbound_email_enabled": False,
            "official_results_fetched": False,
            "native_local_accuracy_used": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "CAMEO service-boundary endpoint only; the local service-boundary artifact is missing or invalid. "
                "It does not start a server, register CAMEO, submit predictions, send email, fetch official results, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(CAMEO_SERVICE_BOUNDARY_ARTIFACT),
        "service_boundary_ready": bool(summary.get("service_boundary_ready") is True),
        "check_count": int(summary.get("check_count") or 0),
        "pass_count": int(summary.get("pass_count") or 0),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "api_route_count": int(summary.get("api_route_count") or 0),
        "expected_api_route_count": int(summary.get("expected_api_route_count") or 0),
        "missing_api_route_count": int(summary.get("missing_api_route_count") or 0),
        "cli_command_count": int(summary.get("cli_command_count") or 0),
        "expected_cli_command_count": int(summary.get("expected_cli_command_count") or 0),
        "missing_cli_command_count": int(summary.get("missing_cli_command_count") or 0),
        "artifact_registry_mismatch_count": int(summary.get("artifact_registry_mismatch_count") or 0),
        "console_script_ready": bool(summary.get("console_script_ready") is True),
        "checks": rows,
        "blockers": blockers,
        "server_started": False,
        "server_registration_mutated": False,
        "prediction_generation_enabled": False,
        "outbound_email_enabled": False,
        "official_results_fetched": False,
        "native_local_accuracy_used": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/api-contract")
async def get_cameo_api_contract() -> dict[str, Any]:
    packet = _read_json_object(CAMEO_API_CONTRACT_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_cameo_api_contract",
            "artifact_path": str(CAMEO_API_CONTRACT_ARTIFACT),
            "api_contract_ready": False,
            "check_count": 0,
            "blocker_count": 1,
            "server_started": False,
            "server_registration_mutated": False,
            "prediction_generation_enabled": False,
            "outbound_email_enabled": False,
            "official_results_fetched": False,
            "native_local_accuracy_used": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "CAMEO API contract endpoint only; the local API contract artifact is missing or invalid. "
                "It does not start a server, register CAMEO, submit predictions, send email, fetch official results, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(CAMEO_API_CONTRACT_ARTIFACT),
        "api_contract_ready": bool(summary.get("api_contract_ready") is True),
        "check_count": int(summary.get("check_count") or 0),
        "pass_count": int(summary.get("pass_count") or 0),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "expected_route_count": int(summary.get("expected_route_count") or 0),
        "missing_route_count": int(summary.get("missing_route_count") or 0),
        "response_model_count": int(summary.get("response_model_count") or 0),
        "missing_response_model_field_count": int(summary.get("missing_response_model_field_count") or 0),
        "status_response_missing_key_count": int(summary.get("status_response_missing_key_count") or 0),
        "status_response_domain_missing_key_count": int(summary.get("status_response_domain_missing_key_count") or 0),
        "checks": rows,
        "blockers": blockers,
        "server_started": False,
        "server_registration_mutated": False,
        "prediction_generation_enabled": False,
        "outbound_email_enabled": False,
        "official_results_fetched": False,
        "native_local_accuracy_used": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/evidence-integrity")
async def get_cameo_evidence_integrity() -> dict[str, Any]:
    packet = _read_json_object(CAMEO_EVIDENCE_INTEGRITY_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_cameo_evidence_integrity_contract",
            "artifact_path": str(CAMEO_EVIDENCE_INTEGRITY_ARTIFACT),
            "evidence_integrity_ready": False,
            "blocker_count": 1,
            "checks": [],
            "blockers": [],
            "server_started": False,
            "server_registration_mutated": False,
            "prediction_generation_enabled": False,
            "outbound_email_enabled": False,
            "official_results_fetched": False,
            "native_local_accuracy_used": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "CAMEO evidence-integrity endpoint only; the local integrity artifact is missing or invalid. "
                "It does not fetch official results, register CAMEO, submit predictions, send email, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(CAMEO_EVIDENCE_INTEGRITY_ARTIFACT),
        "evidence_integrity_ready": bool(summary.get("evidence_integrity_ready") is True),
        "check_count": int(summary.get("check_count") or 0),
        "pass_count": int(summary.get("pass_count") or 0),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "official_result_provenance_honest": bool(summary.get("official_result_provenance_honest") is True),
        "official_result_schema_visible": bool(summary.get("official_result_schema_visible") is True),
        "official_results_ready": bool(summary.get("official_results_ready") is True),
        "official_results_pending_honest": bool(summary.get("official_results_pending_honest") is True),
        "no_local_native_accuracy_substitution": bool(summary.get("no_local_native_accuracy_substitution") is True),
        "external_mutation_flags_clear": bool(summary.get("external_mutation_flags_clear") is True),
        "registration_and_email_gated": bool(summary.get("registration_and_email_gated") is True),
        "local_protocol_connected": bool(summary.get("local_protocol_connected") is True),
        "operator_intake_csv": summary.get("operator_intake_csv", ""),
        "missing_required_columns": list(summary.get("missing_required_columns") or []),
        "checks": rows,
        "blockers": blockers,
        "server_started": False,
        "server_registration_mutated": False,
        "prediction_generation_enabled": False,
        "outbound_email_enabled": False,
        "official_results_fetched": False,
        "native_local_accuracy_used": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/architecture-validation")
async def get_cameo_architecture_validation() -> dict[str, Any]:
    packet = _read_json_object(CAMEO_ARCHITECTURE_VALIDATION_ARTIFACT)
    official_packet = _read_json_object(CAMEO_OFFICIAL_RESULTS_ARTIFACT)
    summary = _summary(packet)
    official = _summary(official_packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_cameo_architecture_validation_contract",
            "artifact_path": str(CAMEO_ARCHITECTURE_VALIDATION_ARTIFACT),
            "local_validation_protocol_ready": False,
            "cameo_architecture_validation_ready": False,
            "official_results_gate_status": official.get("status", ""),
            "official_results_result_row_count": int(official.get("result_row_count") or 0),
            "official_results_accepted_count": int(official.get("accepted_official_result_count") or 0),
            "official_model1_result_ready": bool(official.get("model1_official_result_ready") is True),
            "official_results_rejected_count": int(official.get("rejected_official_result_count") or 0),
            "official_results_blocker_count": int(official.get("blocker_count") or 0),
            "official_results_blocker_codes": list(official.get("blocker_codes") or []),
            "official_results_operator_template_csv": official.get("operator_template_csv") or str(CAMEO_OFFICIAL_RESULTS_TEMPLATE),
            "official_results_operator_intake_csv": official.get("operator_intake_csv") or str(CAMEO_OFFICIAL_RESULTS_INTAKE),
            "official_results_required_columns": list(official.get("required_columns") or REQUIRED_COLUMNS),
            "official_results_missing_required_columns": list(official.get("missing_required_columns") or []),
            "official_results_metric_columns": list(official.get("official_metric_columns") or METRIC_COLUMNS),
            "official_results_disallowed_local_accuracy_columns": list(
                official.get("disallowed_local_accuracy_columns") or DISALLOWED_LOCAL_ACCURACY_COLUMNS
            ),
            "official_cameo_results_used": False,
            "public_registration_authorized": False,
            "server_registration_mutated": False,
            "prediction_generation_enabled": False,
            "outbound_email_enabled": False,
            "native_local_accuracy_used": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "CAMEO architecture-validation endpoint only; the local architecture validation artifact is missing or invalid. "
                "It does not register a server, submit predictions, send email, use local native accuracy, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(CAMEO_ARCHITECTURE_VALIDATION_ARTIFACT),
        "lane_count": int(summary.get("lane_count") or 0),
        "ready_lane_count": int(summary.get("ready_lane_count") or 0),
        "blocked_lane_count": int(summary.get("blocked_lane_count") or 0),
        "approval_required_lane_count": int(summary.get("approval_required_lane_count") or 0),
        "local_validation_protocol_ready": bool(summary.get("local_validation_protocol_ready") is True),
        "cameo_architecture_validation_ready": bool(summary.get("cameo_architecture_validation_ready") is True),
        "product_architecture_local_surface_ready": bool(summary.get("product_architecture_local_surface_ready") is True),
        "validation_operations_surface_ready": bool(summary.get("validation_operations_surface_ready") is True),
        "validation_evidence_ready": bool(summary.get("validation_evidence_ready") is True),
        "performance_scorecard_evidence_ready": bool(summary.get("performance_scorecard_evidence_ready") is True),
        "official_results_ready": bool(summary.get("official_results_ready") is True),
        "official_results_gate_status": official.get("status", ""),
        "official_results_result_row_count": int(official.get("result_row_count") or 0),
        "official_results_accepted_count": int(official.get("accepted_official_result_count") or 0),
        "official_model1_result_ready": bool(official.get("model1_official_result_ready") is True),
        "official_results_rejected_count": int(official.get("rejected_official_result_count") or 0),
        "official_results_blocker_count": int(official.get("blocker_count") or 0),
        "official_results_blocker_codes": list(official.get("blocker_codes") or []),
        "official_results_operator_template_csv": official.get("operator_template_csv") or str(CAMEO_OFFICIAL_RESULTS_TEMPLATE),
        "official_results_operator_intake_csv": official.get("operator_intake_csv") or str(CAMEO_OFFICIAL_RESULTS_INTAKE),
        "official_results_required_columns": list(official.get("required_columns") or REQUIRED_COLUMNS),
        "official_results_missing_required_columns": list(official.get("missing_required_columns") or []),
        "official_results_metric_columns": list(official.get("official_metric_columns") or METRIC_COLUMNS),
        "official_results_disallowed_local_accuracy_columns": list(
            official.get("disallowed_local_accuracy_columns") or DISALLOWED_LOCAL_ACCURACY_COLUMNS
        ),
        "official_cameo_results_used": bool(summary.get("official_cameo_results_used") is True),
        "public_registration_authorized": bool(summary.get("public_registration_authorized") is True),
        "server_registration_mutated": False,
        "prediction_generation_enabled": False,
        "outbound_email_enabled": False,
        "native_local_accuracy_used": False,
        "external_state_mutated": False,
        "rows": rows,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/registration-approval")
async def get_cameo_registration_approval() -> dict[str, Any]:
    packet = _read_json_object(CAMEO_PUBLIC_REGISTRATION_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_cameo_public_registration_approval_gate",
            "artifact_path": str(CAMEO_PUBLIC_REGISTRATION_ARTIFACT),
            "operator_template_csv": str(CAMEO_PUBLIC_REGISTRATION_TEMPLATE),
            "operator_approval_csv": str(CAMEO_PUBLIC_REGISTRATION_INTAKE),
            "required_columns": CAMEO_REGISTRATION_REQUIRED_COLUMNS,
            "valid_decisions": CAMEO_REGISTRATION_VALID_DECISIONS,
            "registration_approval_token_required": CAMEO_REGISTRATION_APPROVAL_TOKEN,
            "outbound_email_approval_token_required": CAMEO_OUTBOUND_EMAIL_APPROVAL_TOKEN,
            "authorized_for_registration_review": False,
            "server_registration_mutated": False,
            "outbound_email_enabled": False,
            "prediction_generation_enabled": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "CAMEO registration-approval endpoint only; the local registration approval artifact is missing or invalid. "
                "It does not register a CAMEO server, submit predictions, send email, start a server, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(CAMEO_PUBLIC_REGISTRATION_ARTIFACT),
        "operator_template_csv": summary.get("operator_template_csv") or str(CAMEO_PUBLIC_REGISTRATION_TEMPLATE),
        "operator_approval_csv": summary.get("operator_approval_csv") or str(CAMEO_PUBLIC_REGISTRATION_INTAKE),
        "required_columns": CAMEO_REGISTRATION_REQUIRED_COLUMNS,
        "valid_decisions": CAMEO_REGISTRATION_VALID_DECISIONS,
        "target_id": summary.get("target_id", ""),
        "capability_public_registration_ready": bool(summary.get("capability_public_registration_ready") is True),
        "official_cameo_validation_evidence_ready": bool(summary.get("official_cameo_validation_evidence_ready") is True),
        "receiver_smoke_ready": bool(summary.get("receiver_smoke_ready") is True),
        "operator_approval_csv_present": bool(summary.get("operator_approval_csv_present") is True),
        "authorized_for_registration_review": bool(summary.get("authorized_for_registration_review") is True),
        "authorized_row_count": int(summary.get("authorized_row_count") or 0),
        "awaiting_operator_approval_row_count": int(summary.get("awaiting_operator_approval_row_count") or 0),
        "skipped_row_count": int(summary.get("skipped_row_count") or 0),
        "blocked_row_count": int(summary.get("blocked_row_count") or 0),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "blockers": summary.get("blockers", []),
        "registration_approval_token_required": summary.get("registration_approval_token_required") or CAMEO_REGISTRATION_APPROVAL_TOKEN,
        "outbound_email_approval_token_required": summary.get("outbound_email_approval_token_required")
        or CAMEO_OUTBOUND_EMAIL_APPROVAL_TOKEN,
        "rows": rows,
        "server_registration_mutated": False,
        "outbound_email_enabled": False,
        "prediction_generation_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/official-results")
async def get_cameo_official_results_status() -> dict[str, Any]:
    packet = _read_json_object(CAMEO_OFFICIAL_RESULTS_ARTIFACT)
    summary = _summary(packet)
    if not summary:
        return {
            "status": "missing_cameo_official_results_intake_gate",
            "artifact_path": str(CAMEO_OFFICIAL_RESULTS_ARTIFACT),
            "result_row_count": 0,
            "accepted_official_result_count": 0,
            "model1_official_result_ready": False,
            "operator_template_csv": str(CAMEO_OFFICIAL_RESULTS_TEMPLATE),
            "operator_intake_csv": str(CAMEO_OFFICIAL_RESULTS_INTAKE),
            "required_columns": list(REQUIRED_COLUMNS),
            "missing_required_columns": list(REQUIRED_COLUMNS),
            "official_metric_columns": list(METRIC_COLUMNS),
            "disallowed_local_accuracy_columns": list(DISALLOWED_LOCAL_ACCURACY_COLUMNS),
            "rejected_official_result_count": 0,
            "blocker_count": 1,
            "blocker_codes": ["missing_cameo_official_results_intake_gate"],
            "official_cameo_results_used": False,
            "native_local_accuracy_used": False,
            "prediction_generation_enabled": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "CAMEO official-results endpoint only; the local official-results intake artifact is missing or invalid. "
                "It does not fetch web pages, submit predictions, use local native accuracy, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(CAMEO_OFFICIAL_RESULTS_ARTIFACT),
        "result_row_count": int(summary.get("result_row_count") or 0),
        "accepted_official_result_count": int(summary.get("accepted_official_result_count") or 0),
        "rejected_official_result_count": int(summary.get("rejected_official_result_count") or 0),
        "model1_official_result_ready": bool(summary.get("model1_official_result_ready") is True),
        "operator_template_csv": summary.get("operator_template_csv") or str(CAMEO_OFFICIAL_RESULTS_TEMPLATE),
        "operator_intake_csv": summary.get("operator_intake_csv") or str(CAMEO_OFFICIAL_RESULTS_INTAKE),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "blocker_codes": list(summary.get("blocker_codes") or []),
        "required_columns": list(summary.get("required_columns") or REQUIRED_COLUMNS),
        "missing_required_columns": list(summary.get("missing_required_columns") or []),
        "official_metric_columns": list(summary.get("official_metric_columns") or METRIC_COLUMNS),
        "disallowed_local_accuracy_columns": list(summary.get("disallowed_local_accuracy_columns") or DISALLOWED_LOCAL_ACCURACY_COLUMNS),
        "official_cameo_results_used": bool(summary.get("official_cameo_results_used") is True),
        "native_local_accuracy_used": False,
        "prediction_generation_enabled": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/targets", response_model=CameoIntakeResponse)
async def receive_cameo_target_get(
    request: Request,
    capability_lane: str = Query(default="polymer_complex_receiver_dry_run"),
) -> CameoIntakeResponse:
    record = await persist_cameo_intake(request, capability_lane)
    return CameoIntakeResponse(
        job_id=record["job_id"],
        status=record["status"],
        message="CAMEO target received; prediction generation and outbound email are disabled.",
        parsed_sequence_count=record["parsed_sequence_count"],
        capability_lane=record["capability_lane"],
    )
