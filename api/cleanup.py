from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/cleanup", tags=["cleanup"])
ROOT = Path(__file__).resolve().parents[1]

CLEANUP_SNAPSHOT_PREFLIGHT_ARTIFACT = ROOT / "runs" / "cleanup_snapshot_preflight_current.json"
CLEANUP_SNAPSHOT_ARTIFACTS_ARTIFACT = ROOT / "runs" / "cleanup_snapshot_artifacts_current.json"
CLEANUP_EXECUTION_DOSSIER_ARTIFACT = ROOT / "runs" / "cleanup_execution_approval_dossier_current.json"
CLEANUP_PAYLOAD_LOCK_ARTIFACT = ROOT / "runs" / "cleanup_payload_manifest_lock_current.json"
CLEANUP_APPROVAL_GATE_ARTIFACT = ROOT / "runs" / "cleanup_execution_approval_gate_current.json"
CLEANUP_POSTCHECK_CONTRACT_ARTIFACT = ROOT / "runs" / "cleanup_postcheck_contract_current.json"
CLEANUP_APPROVAL_TEMPLATE_CSV = ROOT / "runs" / "cleanup_execution_operator_approval_template_current.csv"
CLEANUP_APPROVAL_INTAKE_CSV = ROOT / "runs" / "cleanup_execution_operator_approval_intake.csv"
CLEANUP_COMPLETION_GATE_ARTIFACT = ROOT / "runs" / "cleanup_completion_gate_current.json"
LARGE_CLEANUP_DRILLDOWN_ARTIFACT = ROOT / "runs" / "large_cleanup_surface_drilldown_current.json"
PROTECTED_CLEANUP_REVIEW_ARTIFACT = ROOT / "runs" / "protected_cleanup_payload_review_current.json"
PROTECTED_LIGAND_HEAVY_DEEP_REVIEW_ARTIFACT = ROOT / "runs" / "protected_ligand_heavy_payload_deep_review_current.json"
PROTECTED_CLEANUP_POLICY_GATE_ARTIFACT = ROOT / "runs" / "protected_cleanup_policy_decision_gate_current.json"
GOAL_RELEASE_DECISION_ARTIFACT = ROOT / "runs" / "goal_release_decision_gate_current.json"
CLEANUP_APPROVAL_REQUIRED_COLUMNS = [
    "lane",
    "recommended_action",
    "path",
    "payload_fingerprint_sha256",
    "approval_status",
    "approval_token_required",
    "operator_decision",
    "operator_approval_token",
    "operator_note",
]
CLEANUP_APPROVAL_VALID_DECISIONS = ["approve", "skip"]


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


def _approval_tokens(rows: list[dict[str, Any]]) -> list[str]:
    return sorted({str(row.get("approval_token_required") or "").strip() for row in rows if str(row.get("approval_token_required") or "").strip()})


@router.get("/operations")
async def get_cleanup_operations() -> dict[str, Any]:
    snapshot_preflight_packet = _read_json_object(CLEANUP_SNAPSHOT_PREFLIGHT_ARTIFACT)
    snapshot_artifacts_packet = _read_json_object(CLEANUP_SNAPSHOT_ARTIFACTS_ARTIFACT)
    dossier_packet = _read_json_object(CLEANUP_EXECUTION_DOSSIER_ARTIFACT)
    payload_lock_packet = _read_json_object(CLEANUP_PAYLOAD_LOCK_ARTIFACT)
    approval_packet = _read_json_object(CLEANUP_APPROVAL_GATE_ARTIFACT)
    postcheck_packet = _read_json_object(CLEANUP_POSTCHECK_CONTRACT_ARTIFACT)
    completion_packet = _read_json_object(CLEANUP_COMPLETION_GATE_ARTIFACT)
    protected_policy_packet = _read_json_object(PROTECTED_CLEANUP_POLICY_GATE_ARTIFACT)
    goal_packet = _read_json_object(GOAL_RELEASE_DECISION_ARTIFACT)

    approval = _summary(approval_packet)
    completion = _summary(completion_packet)
    if not approval and not completion:
        return {
            "status": "missing_cleanup_operations_artifacts",
            "approval_gate_artifact_path": str(CLEANUP_APPROVAL_GATE_ARTIFACT),
            "completion_gate_artifact_path": str(CLEANUP_COMPLETION_GATE_ARTIFACT),
            "execution_enabled": False,
            "delete_executed": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Cleanup operations endpoint only; local cleanup operation artifacts are missing or invalid. "
                "It does not approve cleanup, delete, move, archive, externalize, upload, or mutate external state."
            ),
        }

    snapshot_preflight = _summary(snapshot_preflight_packet)
    snapshot_artifacts = _summary(snapshot_artifacts_packet)
    dossier = _summary(dossier_packet)
    payload_lock = _summary(payload_lock_packet)
    postcheck = _summary(postcheck_packet)
    protected_policy = _summary(protected_policy_packet)
    goal = _summary(goal_packet)
    return {
        "status": completion.get("status") or approval.get("status"),
        "approval_gate_artifact_path": str(CLEANUP_APPROVAL_GATE_ARTIFACT),
        "completion_gate_artifact_path": str(CLEANUP_COMPLETION_GATE_ARTIFACT),
        "snapshot_preflight_status": snapshot_preflight.get("status", ""),
        "snapshot_artifacts_status": snapshot_artifacts.get("status", ""),
        "approval_dossier_status": dossier.get("status", ""),
        "payload_lock_status": payload_lock.get("status", ""),
        "postcheck_contract_status": postcheck.get("status", ""),
        "postcheck_contract_ready": bool(postcheck.get("postcheck_contract_ready") is True),
        "postcheck_row_count": int(postcheck.get("row_count") or 0),
        "completion_postcheck_contract_ready": bool(completion.get("postcheck_contract_ready") is True),
        "completion_postcheck_row_count": int(completion.get("postcheck_row_count") or 0),
        "completion_postcheck_blocked_row_count": int(completion.get("postcheck_blocked_row_count") or 0),
        "completion_postcheck_global_refresh_command_count": int(completion.get("postcheck_global_refresh_command_count") or 0),
        "approval_gate_status": approval.get("status", ""),
        "completion_gate_status": completion.get("status", ""),
        "protected_policy_gate_status": protected_policy.get("status", ""),
        "cleanup_complete": bool(completion.get("cleanup_complete") is True),
        "approval_ready": bool(completion.get("approval_ready") is True),
        "transition_cleanup_complete": bool(completion.get("transition_cleanup_complete") is True),
        "ligand_heavy_cleanup_complete": bool(completion.get("ligand_heavy_cleanup_complete") is True),
        "protected_policy_resolved": bool(completion.get("protected_policy_resolved") is True),
        "authorized_row_count": int(approval.get("authorized_row_count") or 0),
        "awaiting_operator_approval_row_count": int(approval.get("awaiting_operator_approval_row_count") or 0),
        "blocked_row_count": int(approval.get("blocked_row_count") or 0),
        "authorized_reclaim_size_gb": float(approval.get("authorized_reclaim_size_gb") or 0.0),
        "total_reclaim_size_gb": float(approval.get("total_reclaim_size_gb") or completion.get("total_reclaim_size_gb") or 0.0),
        "protected_payload_size_gb": float(protected_policy.get("protected_payload_size_gb") or completion.get("protected_payload_size_gb") or 0.0),
        "payload_manifest_fingerprint_sha256": payload_lock.get("payload_manifest_fingerprint_sha256", ""),
        "postcheck_global_refresh_command_count": int(postcheck.get("global_refresh_command_count") or 0),
        "operator_approval_csv_present": bool(approval.get("operator_approval_csv_present") is True),
        "operator_template_csv": approval.get("operator_template_csv", str(CLEANUP_APPROVAL_TEMPLATE_CSV)),
        "operator_approval_csv": approval.get("operator_approval_csv", str(CLEANUP_APPROVAL_INTAKE_CSV)),
        "operator_approval_required_columns": CLEANUP_APPROVAL_REQUIRED_COLUMNS,
        "operator_approval_valid_decisions": CLEANUP_APPROVAL_VALID_DECISIONS,
        "goal_release_status": goal.get("status", ""),
        "cleanup_objective_ready": bool(goal.get("cleanup_objective_ready") is True),
        "release_allowed": bool(goal.get("release_allowed") is True),
        "execution_enabled": False,
        "delete_executed": False,
        "external_state_mutated": False,
        "claim_boundary": (
            "Cleanup operations endpoint only; it reports local cleanup approval, payload-lock, completion, protected-policy, "
            "and release-gate summaries. It does not approve cleanup, delete, move, archive, externalize, upload, or mutate external state."
        ),
    }


@router.get("/completion")
async def get_cleanup_completion() -> dict[str, Any]:
    packet = _read_json_object(CLEANUP_COMPLETION_GATE_ARTIFACT)
    summary = _summary(packet)
    rows = _rows(packet)
    if not summary:
        return {
            "status": "missing_cleanup_completion_gate",
            "artifact_path": str(CLEANUP_COMPLETION_GATE_ARTIFACT),
            "cleanup_complete": False,
            "stage_count": 0,
            "blocked_stage_count": 1,
            "approval_ready": False,
            "postcheck_contract_ready": False,
            "postcheck_row_count": 0,
            "postcheck_blocked_row_count": 1,
            "postcheck_global_refresh_command_count": 0,
            "transition_cleanup_complete": False,
            "ligand_heavy_cleanup_complete": False,
            "protected_policy_resolved": False,
            "execution_enabled": False,
            "delete_executed": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Cleanup completion endpoint only; the local cleanup completion artifact is missing or invalid. "
                "It does not approve cleanup, delete, move, archive, externalize, upload, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(CLEANUP_COMPLETION_GATE_ARTIFACT),
        "cleanup_complete": bool(summary.get("cleanup_complete") is True),
        "stage_count": int(summary.get("stage_count") or 0),
        "blocked_stage_count": int(summary.get("blocked_stage_count") or 0),
        "approval_ready": bool(summary.get("approval_ready") is True),
        "postcheck_contract_ready": bool(summary.get("postcheck_contract_ready") is True),
        "postcheck_row_count": int(summary.get("postcheck_row_count") or 0),
        "postcheck_blocked_row_count": int(summary.get("postcheck_blocked_row_count") or 0),
        "postcheck_global_refresh_command_count": int(summary.get("postcheck_global_refresh_command_count") or 0),
        "transition_cleanup_complete": bool(summary.get("transition_cleanup_complete") is True),
        "ligand_heavy_cleanup_complete": bool(summary.get("ligand_heavy_cleanup_complete") is True),
        "protected_policy_resolved": bool(summary.get("protected_policy_resolved") is True),
        "authorized_reclaim_size_gb": float(summary.get("authorized_reclaim_size_gb") or 0.0),
        "total_reclaim_size_gb": float(summary.get("total_reclaim_size_gb") or 0.0),
        "protected_payload_size_gb": float(summary.get("protected_payload_size_gb") or 0.0),
        "stages": rows,
        "execution_enabled": False,
        "delete_executed": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/postcheck")
async def get_cleanup_postcheck() -> dict[str, Any]:
    packet = _read_json_object(CLEANUP_POSTCHECK_CONTRACT_ARTIFACT)
    summary = _summary(packet)
    rows = _rows(packet)
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_cleanup_postcheck_contract",
            "artifact_path": str(CLEANUP_POSTCHECK_CONTRACT_ARTIFACT),
            "postcheck_contract_ready": False,
            "row_count": 0,
            "blocker_count": 1,
            "execution_enabled": False,
            "delete_executed": False,
            "archive_executed": False,
            "externalize_executed": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Cleanup postcheck endpoint only; the local postcheck contract artifact is missing or invalid. "
                "It does not approve cleanup, delete, move, archive, externalize, upload, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(CLEANUP_POSTCHECK_CONTRACT_ARTIFACT),
        "postcheck_contract_ready": bool(summary.get("postcheck_contract_ready") is True),
        "row_count": int(summary.get("row_count") or 0),
        "approval_row_count": int(summary.get("approval_row_count") or 0),
        "protected_policy_row_count": int(summary.get("protected_policy_row_count") or 0),
        "blocked_row_count": int(summary.get("blocked_row_count") or 0),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "approval_reclaim_size_gb": float(summary.get("approval_reclaim_size_gb") or 0.0),
        "protected_payload_size_gb": float(summary.get("protected_payload_size_gb") or 0.0),
        "payload_manifest_fingerprint_sha256": summary.get("payload_manifest_fingerprint_sha256", ""),
        "global_refresh_command_count": int(summary.get("global_refresh_command_count") or 0),
        "global_refresh_commands": summary.get("global_refresh_commands", []),
        "rows": rows,
        "blockers": blockers,
        "execution_enabled": False,
        "delete_executed": False,
        "archive_executed": False,
        "externalize_executed": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/approval-gate")
async def get_cleanup_approval_gate() -> dict[str, Any]:
    approval_packet = _read_json_object(CLEANUP_APPROVAL_GATE_ARTIFACT)
    summary = _summary(approval_packet)
    rows = _rows(approval_packet)
    if not summary:
        return {
            "status": "missing_cleanup_execution_operator_approval_gate",
            "artifact_path": str(CLEANUP_APPROVAL_GATE_ARTIFACT),
            "operator_template_csv": str(CLEANUP_APPROVAL_TEMPLATE_CSV),
            "operator_approval_csv": str(CLEANUP_APPROVAL_INTAKE_CSV),
            "required_columns": CLEANUP_APPROVAL_REQUIRED_COLUMNS,
            "valid_decisions": CLEANUP_APPROVAL_VALID_DECISIONS,
            "authorized_row_count": 0,
            "awaiting_operator_approval_row_count": 0,
            "blocked_row_count": 1,
            "authorized_reclaim_size_gb": 0.0,
            "total_reclaim_size_gb": 0.0,
            "execution_enabled": False,
            "delete_executed": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Cleanup approval-gate endpoint only; the local cleanup approval artifact is missing or invalid. "
                "It does not approve cleanup, delete, move, archive, externalize, upload, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(CLEANUP_APPROVAL_GATE_ARTIFACT),
        "operator_template_csv": summary.get("operator_template_csv") or str(CLEANUP_APPROVAL_TEMPLATE_CSV),
        "operator_approval_csv": summary.get("operator_approval_csv") or str(CLEANUP_APPROVAL_INTAKE_CSV),
        "required_columns": CLEANUP_APPROVAL_REQUIRED_COLUMNS,
        "valid_decisions": CLEANUP_APPROVAL_VALID_DECISIONS,
        "payload_lock_required": bool(summary.get("payload_lock_required") is True),
        "payload_manifest_fingerprint_sha256": summary.get("payload_manifest_fingerprint_sha256", ""),
        "operator_approval_csv_present": bool(summary.get("operator_approval_csv_present") is True),
        "approval_row_count": int(summary.get("approval_row_count") or 0),
        "authorized_row_count": int(summary.get("authorized_row_count") or 0),
        "skipped_row_count": int(summary.get("skipped_row_count") or 0),
        "awaiting_operator_approval_row_count": int(summary.get("awaiting_operator_approval_row_count") or 0),
        "blocked_row_count": int(summary.get("blocked_row_count") or 0),
        "protected_not_promoted_row_count": int(summary.get("protected_not_promoted_row_count") or 0),
        "approval_tokens_required": _approval_tokens(rows),
        "authorized_reclaim_size_gb": float(summary.get("authorized_reclaim_size_gb") or 0.0),
        "total_reclaim_size_gb": float(summary.get("total_reclaim_size_gb") or 0.0),
        "protected_payload_size_gb": float(summary.get("protected_payload_size_gb") or 0.0),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "blockers": summary.get("blockers", []),
        "rows": rows,
        "execution_enabled": False,
        "delete_executed": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/payloads")
async def get_cleanup_payloads() -> dict[str, Any]:
    drilldown_packet = _read_json_object(LARGE_CLEANUP_DRILLDOWN_ARTIFACT)
    protected_packet = _read_json_object(PROTECTED_CLEANUP_REVIEW_ARTIFACT)
    deep_review_packet = _read_json_object(PROTECTED_LIGAND_HEAVY_DEEP_REVIEW_ARTIFACT)
    dossier_packet = _read_json_object(CLEANUP_EXECUTION_DOSSIER_ARTIFACT)
    payload_lock_packet = _read_json_object(CLEANUP_PAYLOAD_LOCK_ARTIFACT)
    drilldown = _summary(drilldown_packet)
    protected = _summary(protected_packet)
    deep_review = _summary(deep_review_packet)
    dossier = _summary(dossier_packet)
    payload_lock = _summary(payload_lock_packet)
    if not drilldown:
        return {
            "status": "missing_large_cleanup_surface_drilldown",
            "artifact_path": str(LARGE_CLEANUP_DRILLDOWN_ARTIFACT),
            "delete_enabled": False,
            "delete_executed": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Cleanup payload endpoint only; the local large-cleanup drilldown artifact is missing or invalid. "
                "It does not delete, move, archive, externalize, upload, or mutate external state."
            ),
        }
    return {
        "status": drilldown.get("status"),
        "artifact_path": str(LARGE_CLEANUP_DRILLDOWN_ARTIFACT),
        "known_payload_row_count": int(drilldown.get("known_payload_row_count") or 0),
        "known_payload_total_size_gb": float(drilldown.get("known_payload_total_size_gb") or 0.0),
        "dry_run_delete_payload_row_count": int(drilldown.get("dry_run_delete_payload_row_count") or 0),
        "dry_run_delete_payload_size_gb": float(drilldown.get("dry_run_delete_payload_size_gb") or 0.0),
        "dry_run_protected_payload_row_count": int(drilldown.get("dry_run_protected_payload_row_count") or 0),
        "dry_run_protected_payload_size_gb": float(drilldown.get("dry_run_protected_payload_size_gb") or 0.0),
        "protected_payload_row_count": int(protected.get("protected_payload_row_count") or 0),
        "protected_payload_size_gb": float(protected.get("protected_payload_size_gb") or 0.0),
        "protected_ligand_heavy_deep_review_status": deep_review.get("status", ""),
        "protected_ligand_heavy_known_payload_child_count": int(deep_review.get("known_payload_child_count") or 0),
        "protected_ligand_heavy_known_payload_child_size_gb": float(deep_review.get("known_payload_child_size_gb") or 0.0),
        "protected_ligand_heavy_preservation_sibling_count": int(deep_review.get("preservation_sibling_count") or 0),
        "protected_ligand_heavy_preservation_sibling_size_gb": float(deep_review.get("preservation_sibling_size_gb") or 0.0),
        "approval_row_count": int(dossier.get("approval_row_count") or 0),
        "approval_reclaim_size_gb": float(dossier.get("approval_reclaim_size_gb") or 0.0),
        "payload_manifest_fingerprint_sha256": payload_lock.get("payload_manifest_fingerprint_sha256", ""),
        "approval_rows": _rows(dossier_packet),
        "protected_rows": _rows(protected_packet),
        "protected_ligand_heavy_deep_review_rows": _rows(deep_review_packet),
        "delete_enabled": False,
        "delete_executed": False,
        "external_state_mutated": False,
        "claim_boundary": drilldown.get("claim_boundary", ""),
    }


@router.get("/protected-ligand-heavy-review")
async def get_cleanup_protected_ligand_heavy_review() -> dict[str, Any]:
    deep_review_packet = _read_json_object(PROTECTED_LIGAND_HEAVY_DEEP_REVIEW_ARTIFACT)
    summary = _summary(deep_review_packet)
    rows = _rows(deep_review_packet)
    if not summary:
        return {
            "status": "missing_protected_ligand_heavy_payload_deep_review",
            "artifact_path": str(PROTECTED_LIGAND_HEAVY_DEEP_REVIEW_ARTIFACT),
            "known_payload_child_count": 0,
            "known_payload_child_size_gb": 0.0,
            "preservation_sibling_count": 0,
            "preservation_sibling_size_gb": 0.0,
            "approval_promoted_count": 0,
            "delete_enabled": False,
            "delete_executed": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Protected ligand-heavy review endpoint only; the local deep-review artifact is missing or invalid. "
                "It does not promote protected rows, delete, move, archive, externalize, upload, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PROTECTED_LIGAND_HEAVY_DEEP_REVIEW_ARTIFACT),
        "source_protected_review_status": summary.get("source_protected_review_status", ""),
        "known_payload_child_count": int(summary.get("known_payload_child_count") or 0),
        "known_payload_child_size_gb": float(summary.get("known_payload_child_size_gb") or 0.0),
        "preservation_sibling_count": int(summary.get("preservation_sibling_count") or 0),
        "preservation_sibling_size_gb": float(summary.get("preservation_sibling_size_gb") or 0.0),
        "largest_known_payload_child_size_gb": float(summary.get("largest_known_payload_child_size_gb") or 0.0),
        "policy_change_required_for_deletion_count": int(summary.get("policy_change_required_for_deletion_count") or 0),
        "approval_promoted_count": int(summary.get("approval_promoted_count") or 0),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "rows": rows,
        "delete_enabled": False,
        "delete_executed": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/protected-policy")
async def get_cleanup_protected_policy() -> dict[str, Any]:
    protected_packet = _read_json_object(PROTECTED_CLEANUP_REVIEW_ARTIFACT)
    deep_review_packet = _read_json_object(PROTECTED_LIGAND_HEAVY_DEEP_REVIEW_ARTIFACT)
    gate_packet = _read_json_object(PROTECTED_CLEANUP_POLICY_GATE_ARTIFACT)
    protected = _summary(protected_packet)
    deep_review = _summary(deep_review_packet)
    gate = _summary(gate_packet)
    if not gate:
        return {
            "status": "missing_protected_cleanup_policy_decision_gate",
            "artifact_path": str(PROTECTED_CLEANUP_POLICY_GATE_ARTIFACT),
            "policy_resolved": False,
            "delete_enabled": False,
            "delete_executed": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Protected cleanup policy endpoint only; the local protected-policy artifact is missing or invalid. "
                "It does not promote protected rows, delete, move, archive, externalize, upload, or mutate external state."
            ),
        }
    return {
        "status": gate.get("status"),
        "artifact_path": str(PROTECTED_CLEANUP_POLICY_GATE_ARTIFACT),
        "source_protected_review_status": protected.get("status", ""),
        "protected_ligand_heavy_deep_review_status": gate.get("protected_ligand_heavy_deep_review_status") or deep_review.get("status", ""),
        "policy_resolved": bool(gate.get("policy_resolved") is True),
        "approval_promoted": bool(gate.get("approval_promoted") is True),
        "protected_payload_row_count": int(gate.get("protected_payload_row_count") or protected.get("protected_payload_row_count") or 0),
        "protected_payload_size_gb": float(gate.get("protected_payload_size_gb") or protected.get("protected_payload_size_gb") or 0.0),
        "known_payload_child_count": int(gate.get("known_payload_child_count") or deep_review.get("known_payload_child_count") or 0),
        "known_payload_child_size_gb": float(gate.get("known_payload_child_size_gb") or deep_review.get("known_payload_child_size_gb") or 0.0),
        "preservation_sibling_count": int(gate.get("preservation_sibling_count") or deep_review.get("preservation_sibling_count") or 0),
        "policy_change_required_for_deletion_count": int(
            gate.get("policy_change_required_for_deletion_count") or deep_review.get("policy_change_required_for_deletion_count") or 0
        ),
        "awaiting_policy_decision_row_count": int(gate.get("awaiting_policy_decision_row_count") or 0),
        "blocked_row_count": int(gate.get("blocked_row_count") or 0),
        "operator_policy_csv_present": bool(gate.get("operator_policy_csv_present") is True),
        "operator_template_csv": gate.get("operator_template_csv", ""),
        "operator_policy_csv": gate.get("operator_policy_csv", ""),
        "protected_rows": _rows(protected_packet),
        "protected_policy_rows": _rows(gate_packet),
        "delete_enabled": False,
        "delete_executed": False,
        "external_state_mutated": False,
        "claim_boundary": gate.get("claim_boundary", ""),
    }
