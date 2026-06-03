from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/casp17", tags=["casp17"])
ROOT = Path(__file__).resolve().parents[1]

CASP17_WORKBENCH_ARTIFACT = ROOT / "casp17" / "casp17_workbench_index_current.json"
CASP17_UPLOAD_DECISION_RULE_ARTIFACT = ROOT / "casp17" / "casp17_current_upload_decision_rule_gate_current.json"
CASP17_UPLOAD_ACTION_RUNWAY_ARTIFACT = ROOT / "casp17" / "casp17_current_upload_operator_action_runway_current.json"
CASP17_ACTIVE_MANIFEST_LOCK_ARTIFACT = ROOT / "casp17" / "casp17_current_upload_active_manifest_lock_current.json"
LARGE_CLEANUP_DRILLDOWN_ARTIFACT = ROOT / "runs" / "large_cleanup_surface_drilldown_current.json"
PROTECTED_CLEANUP_REVIEW_ARTIFACT = ROOT / "runs" / "protected_cleanup_payload_review_current.json"
CENTRAL_CLEANUP_APPROVAL_GATE_ARTIFACT = ROOT / "runs" / "cleanup_execution_approval_gate_current.json"
CENTRAL_CLEANUP_POSTCHECK_ARTIFACT = ROOT / "runs" / "cleanup_postcheck_contract_current.json"
CENTRAL_CLEANUP_COMPLETION_ARTIFACT = ROOT / "runs" / "cleanup_completion_gate_current.json"
GOAL_RELEASE_DECISION_ARTIFACT = ROOT / "runs" / "goal_release_decision_gate_current.json"

CLAIM_BOUNDARY = (
    "CASP17 transition endpoints are read-only local status surfaces. They do not enter operator decisions, "
    "serialize a CASP author code, create final upload files, submit to CASP, compute native accuracy, delete, "
    "move, archive, externalize, upload, send email, or mutate external state."
)


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


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


@router.get("/upload")
async def get_casp17_upload_status() -> dict[str, Any]:
    decision_packet = _read_json_object(CASP17_UPLOAD_DECISION_RULE_ARTIFACT)
    runway_packet = _read_json_object(CASP17_UPLOAD_ACTION_RUNWAY_ARTIFACT)
    lock_packet = _read_json_object(CASP17_ACTIVE_MANIFEST_LOCK_ARTIFACT)
    decision = _summary(decision_packet)
    runway = _summary(runway_packet)
    lock = _summary(lock_packet)
    if not decision and not runway:
        return {
            "status": "missing_casp17_current_upload_artifacts",
            "decision_rule_artifact_path": str(CASP17_UPLOAD_DECISION_RULE_ARTIFACT),
            "operator_action_runway_artifact_path": str(CASP17_UPLOAD_ACTION_RUNWAY_ARTIFACT),
            "active_manifest_lock_artifact_path": str(CASP17_ACTIVE_MANIFEST_LOCK_ARTIFACT),
            "operator_decision_required_count": 0,
            "ready_for_runtime_upload_count": 0,
            "upload_executed": False,
            "external_state_mutated": False,
            "claim_boundary": CLAIM_BOUNDARY,
        }
    return {
        "status": runway.get("operator_action_runway_status") or decision.get("upload_decision_rule_gate_status", ""),
        "decision_rule_artifact_path": str(CASP17_UPLOAD_DECISION_RULE_ARTIFACT),
        "operator_action_runway_artifact_path": str(CASP17_UPLOAD_ACTION_RUNWAY_ARTIFACT),
        "active_manifest_lock_artifact_path": str(CASP17_ACTIVE_MANIFEST_LOCK_ARTIFACT),
        "decision_rule_gate_status": decision.get("upload_decision_rule_gate_status", ""),
        "operator_action_runway_status": runway.get("operator_action_runway_status", ""),
        "active_manifest_lock_status": lock.get("active_manifest_lock_status", ""),
        "active_target_count": _int(runway.get("active_target_count") or decision.get("active_target_count")),
        "technical_upload_candidate_count": _int(
            runway.get("technical_upload_candidate_count") or decision.get("technical_upload_candidate_count")
        ),
        "operator_decision_required_count": _int(runway.get("operator_decision_required_count")),
        "author_serialization_required_count": _int(runway.get("author_serialization_required_count")),
        "ready_for_runtime_upload_count": _int(runway.get("ready_for_runtime_upload_count")),
        "conditional_approve_after_operator_count": _int(decision.get("conditional_approve_after_operator_count")),
        "operator_decision_missing_count": _int(decision.get("operator_decision_missing_count")),
        "author_serialization_missing_count": _int(decision.get("author_serialization_missing_count")),
        "first_target_id": runway.get("first_target_id") or decision.get("first_target_id", ""),
        "first_action_status": runway.get("first_action_status", ""),
        "first_required_operator_fields": runway.get("first_required_operator_fields", ""),
        "first_fill_surface": runway.get("first_fill_surface", ""),
        "first_decision_md": runway.get("first_decision_md", ""),
        "first_blockers": runway.get("first_blockers") or decision.get("first_blockers", ""),
        "stale_folder_count": _int(lock.get("stale_folder_count")),
        "stale_readonly_count": _int(lock.get("stale_readonly_count")),
        "stale_operator_value_folder_count": _int(lock.get("stale_operator_value_folder_count")),
        "rows": _rows(runway_packet),
        "operator_decision_written": False,
        "author_serialized": False,
        "final_upload_file_created": False,
        "upload_executed": False,
        "native_accuracy_computed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }


@router.get("/transition")
async def get_casp17_transition_status() -> dict[str, Any]:
    workbench_packet = _read_json_object(CASP17_WORKBENCH_ARTIFACT)
    runway_packet = _read_json_object(CASP17_UPLOAD_ACTION_RUNWAY_ARTIFACT)
    lock_packet = _read_json_object(CASP17_ACTIVE_MANIFEST_LOCK_ARTIFACT)
    drilldown_packet = _read_json_object(LARGE_CLEANUP_DRILLDOWN_ARTIFACT)
    protected_packet = _read_json_object(PROTECTED_CLEANUP_REVIEW_ARTIFACT)
    cleanup_approval_packet = _read_json_object(CENTRAL_CLEANUP_APPROVAL_GATE_ARTIFACT)
    cleanup_postcheck_packet = _read_json_object(CENTRAL_CLEANUP_POSTCHECK_ARTIFACT)
    cleanup_completion_packet = _read_json_object(CENTRAL_CLEANUP_COMPLETION_ARTIFACT)
    goal_packet = _read_json_object(GOAL_RELEASE_DECISION_ARTIFACT)
    workbench = _summary(workbench_packet)
    runway = _summary(runway_packet)
    lock = _summary(lock_packet)
    drilldown = _summary(drilldown_packet)
    protected = _summary(protected_packet)
    cleanup_approval = _summary(cleanup_approval_packet)
    cleanup_postcheck = _summary(cleanup_postcheck_packet)
    cleanup_completion = _summary(cleanup_completion_packet)
    goal = _summary(goal_packet)
    if not workbench:
        return {
            "status": "missing_casp17_workbench_index",
            "workbench_artifact_path": str(CASP17_WORKBENCH_ARTIFACT),
            "release_allowed": False,
            "cleanup_execution_approval_gate_status": cleanup_approval.get("status", ""),
            "cleanup_postcheck_contract_ready": bool(cleanup_postcheck.get("postcheck_contract_ready") is True),
            "cleanup_completion_gate_status": cleanup_completion.get("status", ""),
            "cleanup_completion_complete": False,
            "delete_executed": False,
            "upload_executed": False,
            "external_state_mutated": False,
            "claim_boundary": CLAIM_BOUNDARY,
        }
    return {
        "status": workbench.get("workbench_status"),
        "workbench_artifact_path": str(CASP17_WORKBENCH_ARTIFACT),
        "upload_action_runway_status": runway.get("operator_action_runway_status", ""),
        "active_scope_decision_status": workbench.get("active_scope_decision_status", ""),
        "active_competition_scope": workbench.get("active_competition_scope", ""),
        "active_scope_casp17_continuation_status": workbench.get("active_scope_casp17_continuation_status", ""),
        "active_scope_next_action": workbench.get("active_scope_next_action", ""),
        "benchmark_rows_total": _int(workbench.get("benchmark_rows_total")),
        "benchmark_operator_blocked_count": _int(workbench.get("benchmark_operator_blocked_count")),
        "win_tier_critical_path_status": workbench.get("win_tier_critical_path_status", ""),
        "win_tier_critical_path_stage_ready_count": _int(workbench.get("win_tier_critical_path_stage_ready_count")),
        "win_tier_critical_path_stage_blocked_count": _int(workbench.get("win_tier_critical_path_stage_blocked_count")),
        "strict_blind_source_request_operator_value_missing_count": _int(
            workbench.get("strict_blind_source_request_operator_fill_batch_kit_operator_value_missing_count")
        ),
        "current_upload_operator_decision_required_count": _int(runway.get("operator_decision_required_count")),
        "current_upload_ready_for_runtime_upload_count": _int(runway.get("ready_for_runtime_upload_count")),
        "stale_generated_folder_count": _int(lock.get("stale_folder_count")),
        "stale_generated_readonly_count": _int(lock.get("stale_readonly_count")),
        "large_cleanup_known_payload_size_gb": _float(drilldown.get("known_payload_total_size_gb")),
        "large_cleanup_dry_run_delete_payload_size_gb": _float(drilldown.get("dry_run_delete_payload_size_gb")),
        "large_cleanup_dry_run_protected_payload_size_gb": _float(drilldown.get("dry_run_protected_payload_size_gb")),
        "protected_cleanup_payload_size_gb": _float(protected.get("protected_payload_size_gb")),
        "cleanup_execution_approval_gate_status": cleanup_approval.get("status", ""),
        "cleanup_execution_authorized_row_count": _int(cleanup_approval.get("authorized_row_count")),
        "cleanup_execution_awaiting_operator_approval_row_count": _int(cleanup_approval.get("awaiting_operator_approval_row_count")),
        "cleanup_execution_blocked_row_count": _int(cleanup_approval.get("blocked_row_count")),
        "cleanup_execution_authorized_reclaim_size_gb": _float(cleanup_approval.get("authorized_reclaim_size_gb")),
        "cleanup_execution_total_reclaim_size_gb": _float(cleanup_approval.get("total_reclaim_size_gb")),
        "cleanup_execution_operator_approval_csv_present": bool(cleanup_approval.get("operator_approval_csv_present") is True),
        "cleanup_postcheck_contract_status": cleanup_postcheck.get("status", ""),
        "cleanup_postcheck_contract_ready": bool(cleanup_postcheck.get("postcheck_contract_ready") is True),
        "cleanup_postcheck_row_count": _int(cleanup_postcheck.get("row_count")),
        "cleanup_postcheck_blocked_row_count": _int(cleanup_postcheck.get("blocked_row_count")),
        "cleanup_postcheck_global_refresh_command_count": _int(cleanup_postcheck.get("global_refresh_command_count")),
        "cleanup_completion_gate_status": cleanup_completion.get("status", ""),
        "cleanup_completion_complete": bool(cleanup_completion.get("cleanup_complete") is True),
        "cleanup_completion_blocked_stage_count": _int(cleanup_completion.get("blocked_stage_count")),
        "cleanup_completion_approval_ready": bool(cleanup_completion.get("approval_ready") is True),
        "cleanup_completion_transition_cleanup_complete": bool(cleanup_completion.get("transition_cleanup_complete") is True),
        "cleanup_completion_ligand_heavy_cleanup_complete": bool(cleanup_completion.get("ligand_heavy_cleanup_complete") is True),
        "cleanup_completion_protected_policy_resolved": bool(cleanup_completion.get("protected_policy_resolved") is True),
        "goal_release_status": goal.get("status", ""),
        "release_allowed": bool(goal.get("release_allowed") is True),
        "cleanup_objective_ready": bool(goal.get("cleanup_objective_ready") is True),
        "delete_executed": False,
        "upload_executed": False,
        "author_serialized": False,
        "native_accuracy_computed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
