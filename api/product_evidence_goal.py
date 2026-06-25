from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/product", tags=["product"])

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_GOAL_COMPLETION_AUDIT_ARTIFACT = ROOT / "runs" / "product_goal_completion_audit_current.json"
GOAL_READINESS_ROLLUP_ARTIFACT = ROOT / "runs" / "goal_readiness_rollup_current.json"
PRODUCT_FULL_COMMERCIAL_BLOCKER_EVIDENCE_MATRIX_ARTIFACT = (
    ROOT / "runs" / "product_full_commercial_blocker_evidence_matrix_current.json"
)
ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT_ARTIFACT = (
    ROOT / "runs" / "engine_refinement_claim_evidence_receipt_current.json"
)
ENGINE_REFINEMENT_CLAIM_EVIDENCE_PRIORITY_ARTIFACT = (
    ROOT / "runs" / "engine_refinement_claim_evidence_priority_packet_current.json"
)
PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT_ARTIFACT = (
    ROOT / "runs" / "product_scope_breadth_evidence_receipt_current.json"
)
RESIDUAL_MODEL_REGISTRY_ARTIFACT = ROOT / "runs" / "residual_model_registry_current.json"


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


def _goal_readiness_rollup_lane_surface(readiness: dict[str, Any]) -> dict[str, Any]:
    readiness = readiness or {}
    return {
        "release_complete_vs_operator_pending_lane": readiness.get(
            "release_complete_vs_operator_pending_lane", ""
        ),
        "goal_completion_audit_goal_complete": readiness.get("goal_completion_audit_goal_complete"),
        "release_complete_lane_ready": readiness.get("release_complete_lane_ready"),
        "operator_pending_lane_ready": readiness.get("operator_pending_lane_ready"),
        "operator_or_external_pending_lane_count": int(
            readiness.get("operator_or_external_pending_lane_count") or 0
        ),
        "release_complete_vs_operator_pending_matrix": list(
            readiness.get("release_complete_vs_operator_pending_matrix") or []
        ),
    }






@router.get("/scope-breadth-evidence-receipt")
async def get_product_scope_breadth_evidence_receipt() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    required_columns = packet.get("required_columns") if isinstance(packet.get("required_columns"), list) else []
    if not summary:
        return {
            "status": "missing_product_scope_breadth_evidence_receipt",
            "artifact_path": str(PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT_ARTIFACT),
            "full_scope_evidence_receipt_ready": False,
            "receipt_csv": "",
            "receipt_csv_present": False,
            "receipt_row_count": 0,
            "required_scope_blocker_count": 0,
            "required_scope_blockers": [],
            "current_scope_blocker_count": 0,
            "current_scope_blockers": [],
            "missing_required_scope_blocker_count": 0,
            "missing_required_scope_blockers": [],
            "duplicate_scope_blocker_id_count": 0,
            "duplicate_scope_blocker_ids": [],
            "pass_row_count": 0,
            "blocked_row_count": 0,
            "first_blocked_scope_blocker_id": "",
            "first_blocked_row_blockers": [],
            "first_blocked_evidence_artifact": "",
            "first_blocked_expected_evidence_status": "",
            "first_blocked_observed_evidence_status": "",
            "first_blocked_missing_true_fields": [],
            "most_common_row_blocker": "",
            "evidence_artifact_present_count": 0,
            "evidence_status_verified_count": 0,
            "scope_checklist_json": "",
            "scope_checklist_present": False,
            "scope_checklist_scope_breadth_ready": False,
            "scope_checklist_status": "",
            "approval_token_required": "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT",
            "blocker_count": 1,
            "blockers": [],
            "receipt_rows": [],
            "required_columns": [],
            "next_required_step": "",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "scope_widened": False,
            "claim_promoted": False,
            "claim_boundary": (
                "Product scope-breadth evidence receipt endpoint only; the local receipt artifact is missing "
                "or invalid. It does not acquire evidence, widen scope, approve tokens, run docking, promote "
                "claims, upload, email, delete, commit, push, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT_ARTIFACT),
        "full_scope_evidence_receipt_ready": bool(
            summary.get("full_scope_evidence_receipt_ready") is True
        ),
        "receipt_csv": summary.get("receipt_csv", ""),
        "receipt_csv_present": bool(summary.get("receipt_csv_present") is True),
        "receipt_row_count": int(summary.get("receipt_row_count") or 0),
        "required_scope_blocker_count": int(summary.get("required_scope_blocker_count") or 0),
        "required_scope_blockers": list(summary.get("required_scope_blockers") or []),
        "current_scope_blocker_count": int(summary.get("current_scope_blocker_count") or 0),
        "current_scope_blockers": list(summary.get("current_scope_blockers") or []),
        "missing_required_scope_blocker_count": int(
            summary.get("missing_required_scope_blocker_count") or 0
        ),
        "missing_required_scope_blockers": list(
            summary.get("missing_required_scope_blockers") or []
        ),
        "duplicate_scope_blocker_id_count": int(summary.get("duplicate_scope_blocker_id_count") or 0),
        "duplicate_scope_blocker_ids": list(summary.get("duplicate_scope_blocker_ids") or []),
        "pass_row_count": int(summary.get("pass_row_count") or 0),
        "blocked_row_count": int(summary.get("blocked_row_count") or 0),
        "first_blocked_scope_blocker_id": summary.get("first_blocked_scope_blocker_id", ""),
        "first_blocked_row_blockers": list(summary.get("first_blocked_row_blockers") or []),
        "first_blocked_evidence_artifact": summary.get("first_blocked_evidence_artifact", ""),
        "first_blocked_expected_evidence_status": summary.get(
            "first_blocked_expected_evidence_status", ""
        ),
        "first_blocked_observed_evidence_status": summary.get(
            "first_blocked_observed_evidence_status", ""
        ),
        "first_blocked_missing_true_fields": list(
            summary.get("first_blocked_missing_true_fields") or []
        ),
        "most_common_row_blocker": summary.get("most_common_row_blocker", ""),
        "evidence_artifact_present_count": int(summary.get("evidence_artifact_present_count") or 0),
        "evidence_status_verified_count": int(summary.get("evidence_status_verified_count") or 0),
        "scope_checklist_json": summary.get("scope_checklist_json", ""),
        "scope_checklist_present": bool(summary.get("scope_checklist_present") is True),
        "scope_checklist_scope_breadth_ready": bool(
            summary.get("scope_checklist_scope_breadth_ready") is True
        ),
        "scope_checklist_status": summary.get("scope_checklist_status", ""),
        "approval_token_required": summary.get(
            "approval_token_required", "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT"
        ),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "blockers": list(summary.get("blockers") or []),
        "receipt_rows": rows,
        "required_columns": required_columns,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "scope_widened": False,
        "claim_promoted": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/full-commercial-blocker-evidence-matrix")
async def get_product_full_commercial_blocker_evidence_matrix() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_FULL_COMMERCIAL_BLOCKER_EVIDENCE_MATRIX_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_product_full_commercial_blocker_evidence_matrix",
            "artifact_path": str(PRODUCT_FULL_COMMERCIAL_BLOCKER_EVIDENCE_MATRIX_ARTIFACT),
            "full_commercial_blocker_evidence_matrix_ready": False,
            "full_commercial_evidence_receipts_ready": False,
            "release_blocker_visibility_ready": False,
            "expected_release_blocker_ids": [],
            "expected_release_blocker_count": 0,
            "goal_audit_release_blocker_ids": [],
            "missing_goal_audit_release_blocker_ids": [],
            "bottleneck_release_blocker_ids": [],
            "missing_bottleneck_release_blocker_ids": [],
            "scope_receipt_json": "",
            "scope_receipt_status": "",
            "scope_receipt_ready": False,
            "scope_receipt_blocked_row_count": 0,
            "engine_receipt_json": "",
            "engine_receipt_status": "",
            "engine_receipt_ready": False,
            "engine_receipt_blocked_row_count": 0,
            "matrix_row_count": 0,
            "pass_matrix_row_count": 0,
            "blocked_matrix_row_count": 0,
            "ready_receipt_count": 0,
            "blocked_receipt_count": 0,
            "approval_token_count": 0,
            "approval_tokens_required": [],
            "first_blocked_release_blocker_id": "",
            "first_blocked_evidence_row_id": "",
            "first_blocked_evidence_artifact": "",
            "first_blocked_expected_evidence_status": "",
            "first_blocked_observed_evidence_status": "",
            "first_blocked_row_blockers": "",
            "first_blocked_receipt_json": "",
            "first_blocked_acceptance_artifact": "",
            "first_blocked_next_required_step": "",
            "scope_receipt_most_common_row_blocker": "",
            "engine_receipt_most_common_row_blocker": "",
            "evidence_matrix": [],
            "blockers": [],
            "next_required_step": "",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product full-commercial blocker evidence-matrix endpoint only; the local matrix artifact is "
                "missing or invalid. It does not fill evidence, approve tokens, run docking, promote claims, "
                "upload, email, delete, commit, push, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_FULL_COMMERCIAL_BLOCKER_EVIDENCE_MATRIX_ARTIFACT),
        "full_commercial_blocker_evidence_matrix_ready": bool(
            summary.get("full_commercial_blocker_evidence_matrix_ready") is True
        ),
        "full_commercial_evidence_receipts_ready": bool(
            summary.get("full_commercial_evidence_receipts_ready") is True
        ),
        "release_blocker_visibility_ready": bool(
            summary.get("release_blocker_visibility_ready") is True
        ),
        "expected_release_blocker_ids": list(summary.get("expected_release_blocker_ids") or []),
        "expected_release_blocker_count": int(summary.get("expected_release_blocker_count") or 0),
        "goal_audit_release_blocker_ids": list(summary.get("goal_audit_release_blocker_ids") or []),
        "missing_goal_audit_release_blocker_ids": list(
            summary.get("missing_goal_audit_release_blocker_ids") or []
        ),
        "bottleneck_release_blocker_ids": list(summary.get("bottleneck_release_blocker_ids") or []),
        "missing_bottleneck_release_blocker_ids": list(
            summary.get("missing_bottleneck_release_blocker_ids") or []
        ),
        "scope_receipt_json": summary.get("scope_receipt_json", ""),
        "scope_receipt_status": summary.get("scope_receipt_status", ""),
        "scope_receipt_ready": bool(summary.get("scope_receipt_ready") is True),
        "scope_receipt_blocked_row_count": int(summary.get("scope_receipt_blocked_row_count") or 0),
        "engine_receipt_json": summary.get("engine_receipt_json", ""),
        "engine_receipt_status": summary.get("engine_receipt_status", ""),
        "engine_receipt_ready": bool(summary.get("engine_receipt_ready") is True),
        "engine_receipt_blocked_row_count": int(
            summary.get("engine_receipt_blocked_row_count") or 0
        ),
        "matrix_row_count": int(summary.get("matrix_row_count") or 0),
        "pass_matrix_row_count": int(summary.get("pass_matrix_row_count") or 0),
        "blocked_matrix_row_count": int(summary.get("blocked_matrix_row_count") or 0),
        "ready_receipt_count": int(summary.get("ready_receipt_count") or 0),
        "blocked_receipt_count": int(summary.get("blocked_receipt_count") or 0),
        "approval_token_count": int(summary.get("approval_token_count") or 0),
        "approval_tokens_required": list(summary.get("approval_tokens_required") or []),
        "first_blocked_release_blocker_id": summary.get("first_blocked_release_blocker_id", ""),
        "first_blocked_evidence_row_id": summary.get("first_blocked_evidence_row_id", ""),
        "first_blocked_evidence_artifact": summary.get("first_blocked_evidence_artifact", ""),
        "first_blocked_expected_evidence_status": summary.get(
            "first_blocked_expected_evidence_status", ""
        ),
        "first_blocked_observed_evidence_status": summary.get(
            "first_blocked_observed_evidence_status", ""
        ),
        "first_blocked_row_blockers": summary.get("first_blocked_row_blockers", ""),
        "first_blocked_receipt_json": summary.get("first_blocked_receipt_json", ""),
        "first_blocked_acceptance_artifact": summary.get("first_blocked_acceptance_artifact", ""),
        "first_blocked_next_required_step": summary.get("first_blocked_next_required_step", ""),
        "scope_receipt_most_common_row_blocker": summary.get(
            "scope_receipt_most_common_row_blocker", ""
        ),
        "engine_receipt_most_common_row_blocker": summary.get(
            "engine_receipt_most_common_row_blocker", ""
        ),
        "evidence_matrix": list(rows),
        "blockers": list(blockers),
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/engine-refinement-claim-evidence-receipt")
async def get_product_engine_refinement_claim_evidence_receipt() -> dict[str, Any]:
    packet = _read_json_object(ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    required_columns = packet.get("required_columns") if isinstance(packet.get("required_columns"), list) else []
    if not summary:
        return {
            "status": "missing_engine_refinement_claim_evidence_receipt",
            "artifact_path": str(ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT_ARTIFACT),
            "claim_promotion_evidence_receipt_ready": False,
            "receipt_csv": "",
            "receipt_csv_present": False,
            "receipt_row_count": 0,
            "required_blocker_count": 0,
            "required_blockers": [],
            "missing_required_blocker_count": 0,
            "missing_required_blockers": [],
            "duplicate_blocker_id_count": 0,
            "duplicate_blocker_ids": [],
            "pass_row_count": 0,
            "blocked_row_count": 0,
            "first_blocked_blocker_id": "",
            "first_blocked_row_blockers": [],
            "first_blocked_evidence_artifact": "",
            "first_blocked_expected_evidence_status": "",
            "first_blocked_observed_evidence_status": "",
            "first_blocked_missing_true_fields": [],
            "most_common_row_blocker": "",
            "evidence_artifact_present_count": 0,
            "evidence_status_verified_count": 0,
            "action_board_csv": "",
            "action_board_blocker_count": 0,
            "approval_token_required": "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT",
            "blocker_count": 1,
            "blockers": [],
            "receipt_rows": [],
            "required_columns": [],
            "next_required_step": "",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_promoted": False,
            "claim_boundary": (
                "Engine refinement claim evidence receipt endpoint only; the local receipt artifact is "
                "missing or invalid. It does not fill evidence, approve tokens, run docking or MD, promote "
                "claims, upload, email, delete, commit, push, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT_ARTIFACT),
        "claim_promotion_evidence_receipt_ready": bool(
            summary.get("claim_promotion_evidence_receipt_ready") is True
        ),
        "receipt_csv": summary.get("receipt_csv", ""),
        "receipt_csv_present": bool(summary.get("receipt_csv_present") is True),
        "receipt_row_count": int(summary.get("receipt_row_count") or 0),
        "required_blocker_count": int(summary.get("required_blocker_count") or 0),
        "required_blockers": list(summary.get("required_blockers") or []),
        "missing_required_blocker_count": int(summary.get("missing_required_blocker_count") or 0),
        "missing_required_blockers": list(summary.get("missing_required_blockers") or []),
        "duplicate_blocker_id_count": int(summary.get("duplicate_blocker_id_count") or 0),
        "duplicate_blocker_ids": list(summary.get("duplicate_blocker_ids") or []),
        "pass_row_count": int(summary.get("pass_row_count") or 0),
        "blocked_row_count": int(summary.get("blocked_row_count") or 0),
        "first_blocked_blocker_id": summary.get("first_blocked_blocker_id", ""),
        "first_blocked_row_blockers": list(summary.get("first_blocked_row_blockers") or []),
        "first_blocked_evidence_artifact": summary.get("first_blocked_evidence_artifact", ""),
        "first_blocked_expected_evidence_status": summary.get(
            "first_blocked_expected_evidence_status", ""
        ),
        "first_blocked_observed_evidence_status": summary.get(
            "first_blocked_observed_evidence_status", ""
        ),
        "first_blocked_missing_true_fields": list(
            summary.get("first_blocked_missing_true_fields") or []
        ),
        "most_common_row_blocker": summary.get("most_common_row_blocker", ""),
        "evidence_artifact_present_count": int(summary.get("evidence_artifact_present_count") or 0),
        "evidence_status_verified_count": int(summary.get("evidence_status_verified_count") or 0),
        "action_board_csv": summary.get("action_board_csv", ""),
        "action_board_blocker_count": int(summary.get("action_board_blocker_count") or 0),
        "approval_token_required": summary.get(
            "approval_token_required", "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT"
        ),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "blockers": list(summary.get("blockers") or []),
        "receipt_rows": rows,
        "required_columns": required_columns,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_promoted": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/engine-refinement-claim-evidence-priority")
async def get_product_engine_refinement_claim_evidence_priority() -> dict[str, Any]:
    packet = _read_json_object(ENGINE_REFINEMENT_CLAIM_EVIDENCE_PRIORITY_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_engine_refinement_claim_evidence_priority_packet",
            "artifact_path": str(ENGINE_REFINEMENT_CLAIM_EVIDENCE_PRIORITY_ARTIFACT),
            "priority_packet_ready": False,
            "claim_promotion_allowed": False,
            "claim_evidence_receipt_ready": False,
            "claim_evidence_receipt_status": "",
            "priority_item_count": 0,
            "operator_input_required_count": 0,
            "blocked_priority_item_count": 0,
            "required_blocker_count": 0,
            "missing_required_blocker_count": 0,
            "missing_required_blockers": [],
            "public_benchmark_gate_ready": False,
            "public_benchmark_status": "",
            "public_benchmark_work_order_present": False,
            "public_benchmark_work_order_row_count": 0,
            "public_benchmark_work_order_apply_status": "",
            "public_benchmark_work_order_apply_ready": False,
            "public_benchmark_work_order_apply_blocked_row_count": 0,
            "top_blocker_id": "",
            "top_priority_bucket": "",
            "top_required_input": "",
            "top_acceptance_artifact": "",
            "top_verification_command": "",
            "top_next_operator_step": "",
            "approval_token_required": "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT",
            "approval_token_count": 0,
            "blocker_count": 1,
            "blockers": ["engine_refinement_claim_evidence_priority_packet_missing"],
            "source_artifacts": [],
            "top_priority_items": [],
            "priority_items": [],
            "next_required_step": (
                "Run python3 tools/product/build_engine_refinement_claim_evidence_priority_packet.py."
            ),
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_promoted": False,
            "claim_boundary": (
                "Engine refinement claim evidence priority endpoint only; the local priority packet is missing. "
                "It does not download data, run docking or MD, approve tokens, promote claims, or mutate external state."
            ),
        }
    sorted_rows = sorted(
        [row for row in rows if isinstance(row, dict)],
        key=lambda row: int(row.get("priority") or 999999),
    )
    return {
        "status": summary.get("status"),
        "artifact_path": str(ENGINE_REFINEMENT_CLAIM_EVIDENCE_PRIORITY_ARTIFACT),
        "priority_packet_ready": bool(summary.get("priority_packet_ready") is True),
        "claim_promotion_allowed": bool(summary.get("claim_promotion_allowed") is True),
        "claim_evidence_receipt_ready": bool(summary.get("claim_evidence_receipt_ready") is True),
        "claim_evidence_receipt_status": summary.get("claim_evidence_receipt_status", ""),
        "priority_item_count": int(summary.get("priority_item_count") or 0),
        "operator_input_required_count": int(summary.get("operator_input_required_count") or 0),
        "blocked_priority_item_count": int(summary.get("blocked_priority_item_count") or 0),
        "required_blocker_count": int(summary.get("required_blocker_count") or 0),
        "missing_required_blocker_count": int(summary.get("missing_required_blocker_count") or 0),
        "missing_required_blockers": list(summary.get("missing_required_blockers") or []),
        "public_benchmark_gate_ready": bool(summary.get("public_benchmark_gate_ready") is True),
        "public_benchmark_status": summary.get("public_benchmark_status", ""),
        "public_benchmark_work_order_present": bool(
            summary.get("public_benchmark_work_order_present") is True
        ),
        "public_benchmark_work_order_row_count": int(
            summary.get("public_benchmark_work_order_row_count") or 0
        ),
        "public_benchmark_work_order_apply_status": summary.get(
            "public_benchmark_work_order_apply_status", ""
        ),
        "public_benchmark_work_order_apply_ready": bool(
            summary.get("public_benchmark_work_order_apply_ready") is True
        ),
        "public_benchmark_work_order_apply_blocked_row_count": int(
            summary.get("public_benchmark_work_order_apply_blocked_row_count") or 0
        ),
        "top_blocker_id": summary.get("top_blocker_id", ""),
        "top_priority_bucket": summary.get("top_priority_bucket", ""),
        "top_required_input": summary.get("top_required_input", ""),
        "top_acceptance_artifact": summary.get("top_acceptance_artifact", ""),
        "top_verification_command": summary.get("top_verification_command", ""),
        "top_next_operator_step": summary.get("top_next_operator_step", ""),
        "approval_token_required": summary.get(
            "approval_token_required", "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT"
        ),
        "approval_token_count": int(summary.get("approval_token_count") or 0),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "blockers": list(summary.get("blockers") or []),
        "source_artifacts": list(summary.get("source_artifacts") or []),
        "top_priority_items": sorted_rows[:3],
        "priority_items": sorted_rows,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_promoted": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/goal-completion-audit")
async def get_product_goal_completion_audit() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_GOAL_COMPLETION_AUDIT_ARTIFACT)
    readiness = _summary(_read_json_object(GOAL_READINESS_ROLLUP_ARTIFACT))
    lane_surface = _goal_readiness_rollup_lane_surface(readiness)
    registry_packet = _read_json_object(RESIDUAL_MODEL_REGISTRY_ARTIFACT)
    summary = _summary(packet)
    registry = _summary(registry_packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_product_goal_completion_audit",
            "artifact_path": str(PRODUCT_GOAL_COMPLETION_AUDIT_ARTIFACT),
            "goal_complete": False,
            "requirement_count": 0,
            "pass_count": 0,
            "fail_count": 1,
            "primary_bottleneck_phase": "",
            "primary_bottleneck_kind": "",
            "approval_tokens_required": [],
            "next_command": "",
            "next_command_candidate_count": 0,
            "next_command_candidates": [],
            "product_ai_architecture_ready": False,
            "product_ai_architecture_gap_status": "",
            "product_ai_architecture_all_gaps_closed": False,
            "product_ai_architecture_gap_count": 0,
            "product_ai_architecture_closed_gap_count": 0,
            "product_ai_architecture_open_gap_count": 0,
            "product_ai_architecture_open_gap_ids": [],
            "product_ai_architecture_closed_gap_ids": [],
            "product_ai_architecture_gap_blocker_matrix_ready": False,
            "product_ai_architecture_gap_blocker_matrix_count": 0,
            "product_ai_architecture_gap_blocker_matrix": [],
            "product_ai_architecture_current_primary_blocker_gap_id": "",
            "product_ai_architecture_current_primary_blocker_id": "",
            "product_ai_architecture_current_primary_blocker_artifact": "",
            "product_ai_architecture_current_primary_blocker_validation_command": "",
            "product_ai_architecture_current_primary_blocker_next_action": "",
            "product_ai_architecture_current_primary_blocker_operator_input_fields": [],
            "product_ai_architecture_current_primary_blocker_unlock_claim": "",
            "product_ai_architecture_current_primary_blocker_next_after_stage_id": "",
            "product_ai_architecture_current_primary_blocker_next_after_artifact": "",
            "product_ai_architecture_current_primary_blocker_next_after_validation_command": "",
            "product_ai_architecture_current_primary_blocker_next_after_next_action": "",
            "product_ai_architecture_current_primary_blocker_next_after_required_checks": [],
            "product_ai_architecture_current_primary_blocker_next_after_unlock_fields": [],
            "product_ai_architecture_parallelizable_gap_blocker_count": 0,
            "product_ai_architecture_parallelizable_gap_blocker_ids": [],
            "product_ai_architecture_first_parallelizable_gap_id": "",
            "product_ai_architecture_first_parallelizable_blocker_id": "",
            "product_ai_architecture_first_parallelizable_blocker_artifact": "",
            "product_ai_architecture_first_parallelizable_blocker_next_action": "",
            "product_ai_architecture_first_parallelizable_blocker_validation_command": "",
            "product_ai_architecture_first_parallelizable_blocker_operator_input_fields": [],
            "product_ai_architecture_first_parallelizable_blocker_required_exact_evidence_fields": [],
            "product_ai_architecture_first_parallelizable_blocker_required_claim_guardrails": [],
            "product_ai_architecture_first_parallelizable_blocker_claim_safe_completion_rule": "",
            "product_ai_architecture_first_parallelizable_blocker_unlock_claim": "",
            "product_ai_architecture_first_parallelizable_blocker_source_modality_triage_artifact": "",
            "product_ai_architecture_first_parallelizable_blocker_source_modality_triage_decision": "",
            "product_ai_architecture_first_parallelizable_blocker_source_modality_direct_experimental_binding_row_count": 0,
            "product_ai_architecture_first_parallelizable_blocker_source_modality_claim_safe_binding_kcal_ready_count": 0,
            "product_ai_architecture_first_parallelizable_blocker_source_modality_computational_binding_energy_row_count": 0,
            "product_ai_architecture_first_parallelizable_blocker_source_modality_best_computational_binding_energy_kcal_mol": "",
            "commercial_readiness_next_action_matrix_ready": False,
            "commercial_readiness_next_action_matrix": [],
            "commercial_readiness_next_action_matrix_count": 0,
            "commercial_readiness_next_action_blocker_matrix": [],
            "commercial_readiness_next_action_blocker_count": 0,
            "commercial_readiness_first_next_action_id": "",
            "commercial_readiness_first_next_action_artifact": "",
            "commercial_readiness_first_next_action_validation_command": "",
            "commercial_readiness_handoff_bundle_status": "",
            "commercial_readiness_handoff_bundle_artifact_path": "",
            "commercial_readiness_handoff_bundle_ready": False,
            "commercial_readiness_handoff_bundle_artifact_count": 0,
            "commercial_readiness_handoff_bundle_blocked_artifact_count": 0,
            "commercial_readiness_handoff_bundle_blocked_artifact_ids": [],
            "commercial_readiness_handoff_bundle_artifact_reference_contract_ready": False,
            "commercial_readiness_handoff_bundle_artifact_reference_count": 0,
            "commercial_readiness_handoff_bundle_local_missing_artifact_reference_count": 0,
            "commercial_readiness_handoff_bundle_operator_return_pending_artifact_reference_count": 0,
            "commercial_readiness_handoff_bundle_first_action_id": "",
            "commercial_readiness_handoff_bundle_first_operator_input_artifact": "",
            "commercial_readiness_handoff_bundle_next_required_step": "",
            "product_ai_production_checkpoint_gap_ready": False,
            "product_ai_production_checkpoint_gap_observed": "",
            "product_ai_closed_loop_decision_graph_ready": False,
            "product_ai_closed_loop_decision_graph_observed": "",
            "product_ai_durable_job_orchestration_ready": False,
            "product_ai_durable_job_orchestration_observed": "",
            "product_ai_trajectory_sla_ready": False,
            "product_ai_trajectory_sla_observed": "",
            "product_ai_trajectory_sla_claim_tier": "",
            "product_ai_trajectory_sla_restricted_family_allowed": False,
            "product_ai_trajectory_sla_broad_platform_allowed": False,
            "product_ai_trajectory_sla_current_rocm_baseline_claim_scope": "",
            "product_ai_trajectory_sla_current_rocm_baseline_production_profile_enabled": False,
            "product_ai_trajectory_sla_rocm_baseline_profile_gap_acknowledged": False,
            "product_ai_scope_breadth_ready": False,
            "product_ai_scope_breadth_observed": "",
            "product_scope_evidence_queue_next_operator_completion_packet_ready": False,
            "product_scope_evidence_queue_next_operator_completion_slot_id": "",
            "product_scope_evidence_queue_next_operator_completion_expected_evidence_type": "",
            "product_scope_evidence_queue_next_operator_completion_required_exact_evidence_field_count": 0,
            "product_scope_evidence_queue_next_operator_completion_required_exact_evidence_fields": "",
            "product_scope_evidence_queue_next_operator_completion_required_operator_intake_columns": "",
            "product_scope_evidence_queue_next_operator_completion_required_claim_guardrails": "",
            "product_scope_evidence_queue_next_operator_completion_operator_review_artifact": "",
            "product_scope_evidence_queue_next_operator_completion_post_intake_synchronization_targets": "",
            "product_scope_evidence_queue_next_operator_completion_acceptance_gate_commands": "",
            "product_scope_evidence_queue_next_operator_completion_contract_artifact": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_sidecar_ready": False,
            "product_scope_evidence_queue_next_operator_completion_aqp1_functional_surrogate_artifact": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_candidate_ledger_artifact": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_candidate_name": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_source_anchor": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_source_url": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_target_uniprot": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_functional_measure": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_assay_type_honesty": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_direct_binding_claim_allowed": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_binding_kcal_claim_allowed": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_claim_safe_functional_kcal_ready": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_ledger_review_bucket": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_ledger_promotion_policy": "",
            "product_scope_evidence_queue_pxr_exact_review_sidecar_row_count": 0,
            "product_scope_evidence_queue_next_pxr_exact_review_sidecar_ready": False,
            "product_scope_evidence_queue_next_pxr_exact_review_row_id": "",
            "product_scope_evidence_queue_next_pxr_exact_review_candidate_name": "",
            "product_scope_evidence_queue_next_pxr_exact_review_required_evidence_mode": "",
            "product_scope_evidence_queue_next_pxr_exact_review_target_match_confirmed": "",
            "product_scope_evidence_queue_next_pxr_exact_review_replacement_reference_binding_kcal_mol": "",
            "product_scope_evidence_queue_next_pxr_exact_review_replacement_source_url_or_doi": "",
            "product_scope_evidence_queue_next_pxr_exact_review_authoritative_apply_allowed": False,
            "product_scope_evidence_queue_next_pxr_exact_review_scope_promotion_allowed": False,
            "product_ai_report_ux_ready": False,
            "product_ai_report_ux_observed": "",
            "product_ai_report_ux_customer_report_delivery_contract_ready": False,
            "product_ai_report_ux_customer_report_evidence_binding_ready": False,
            "product_ai_report_ux_customer_report_viewer_binding_ready": False,
            "product_ai_report_ux_viewer_customer_report_binding_ready": False,
            "product_ai_report_ux_customer_report_ready_block_count": 0,
            "product_ai_report_ux_customer_report_required_block_count": 0,
            "product_ai_report_ux_customer_report_blocked_block_count": 0,
            "product_ai_security_deployment_ready": False,
            "product_ai_security_deployment_observed": "",
            "product_ai_security_hosted_deployment_contract_ready": False,
            "product_ai_security_hosted_deployment_currently_satisfied": False,
            "product_ai_security_hosted_deployment_next_stage_id": "",
            "product_ai_security_hosted_external_exposure_allowed": False,
            "product_ai_security_hosted_secret_injection_ready": False,
            "product_ai_security_tls_termination_operator_verified": False,
            "production_ai_inference_subject_active": False,
            "production_ai_default_residual_mode": "",
            "production_ai_promotion_allowed": False,
            "production_ai_customer_facing_auto_correction_allowed": False,
            "production_ai_customer_facing_score_mutation_allowed": False,
            "production_ai_customer_facing_ranking_mutation_allowed": False,
            "production_ai_trained_checkpoint_count": 0,
            "production_ai_selected_sidecar_ready": False,
            "production_ai_selected_sidecar_missing_output_fields": [],
            "production_ai_blocked_reason": "missing_product_goal_completion_audit",
            "production_ai_residual_model_registry_status": "",
            "production_ai_residual_model_registry_artifact_path": "",
            "production_ai_residual_model_registry_ready": False,
            "production_ai_product_model_layer_ready": False,
            "production_ai_registry_checkpoint_preflight_ready": False,
            "production_ai_registry_production_checkpoint_blocked": False,
            "production_ai_registry_checkpoint_primary_blocker": "",
            "production_ai_registry_checkpoint_missing_output_fields": [],
            "production_ai_registry_checkpoint_missing_adapter_output_policy_fields": [],
            "product_ai_primary_backlog_detail": "",
            "product_ai_primary_backlog_work_item_id": "",
            "product_ai_primary_backlog_acceptance_criteria": "",
            "product_ai_primary_backlog_next_action": "",
            "product_ai_primary_backlog_source_artifact": "",
            "product_ai_primary_backlog_verification_command": "",
            "production_ai_gpu_worker_return_receipt_ready": False,
            "production_ai_gpu_worker_return_receipt_blockers": [],
            "production_ai_gpu_expected_queue_rows": 0,
            "production_ai_gpu_manifest_ok_row_count": 0,
            "production_ai_gpu_manifest_status_placeholder_count": 0,
            "production_ai_gpu_manifest_status_invalid_count": 0,
            "production_ai_gpu_manifest_npz_paths_complete": False,
            "production_ai_gpu_manifest_npz_files_exist": False,
            "production_ai_gpu_manifest_npz_files_valid": False,
            "production_ai_gpu_manifest_npz_schema_valid": False,
            "production_ai_gpu_manifest_npz_identity_valid": False,
            "production_ai_gpu_manifest_npz_path_present_count": 0,
            "production_ai_gpu_manifest_npz_path_missing_count": 0,
            "production_ai_gpu_manifest_ok_row_missing_npz_path_count": 0,
            "production_ai_gpu_manifest_operator_verified_missing_npz_path_count": 0,
            "production_ai_gpu_manifest_npz_file_existing_count": 0,
            "production_ai_gpu_manifest_npz_file_missing_count": 0,
            "production_ai_gpu_manifest_ok_row_missing_npz_file_count": 0,
            "production_ai_gpu_manifest_operator_verified_missing_npz_file_count": 0,
            "production_ai_gpu_manifest_npz_file_valid_count": 0,
            "production_ai_gpu_manifest_npz_file_invalid_count": 0,
            "production_ai_gpu_manifest_ok_row_invalid_npz_file_count": 0,
            "production_ai_gpu_manifest_operator_verified_invalid_npz_file_count": 0,
            "production_ai_gpu_manifest_npz_schema_valid_count": 0,
            "production_ai_gpu_manifest_npz_schema_invalid_count": 0,
            "production_ai_gpu_manifest_ok_row_invalid_npz_schema_count": 0,
            "production_ai_gpu_manifest_operator_verified_invalid_npz_schema_count": 0,
            "production_ai_gpu_manifest_npz_identity_valid_count": 0,
            "production_ai_gpu_manifest_npz_identity_invalid_count": 0,
            "production_ai_gpu_manifest_ok_row_invalid_npz_identity_count": 0,
            "production_ai_gpu_manifest_operator_verified_invalid_npz_identity_count": 0,
            "production_ai_gpu_manifest_operator_verified": False,
            "production_ai_gpu_operator_verified_true_count": 0,
            "production_ai_gpu_operator_verification_column_present": False,
            "production_ai_gpu_identity_coverage_ready": False,
            "production_ai_gpu_matched_queue_fingerprints": 0,
            "production_ai_gpu_queue_fingerprints": 0,
            "production_ai_force_derivation_input_ready": False,
            "production_ai_delta_force_derivation_validation_ready": False,
            "production_ai_missing_output_labels": [],
            "production_ai_checkpoint_output_head_gap_contract_ready": False,
            "production_ai_checkpoint_output_heads_complete": False,
            "production_ai_checkpoint_output_head_required_field_count": 0,
            "production_ai_checkpoint_output_head_ready_field_count": 0,
            "production_ai_checkpoint_output_head_blocked_field_count": 0,
            "production_ai_checkpoint_output_head_blocked_fields": [],
            "production_ai_checkpoint_output_head_first_blocked_field": "",
            "production_ai_checkpoint_output_head_first_blocked_field_blockers": [],
            "production_ai_checkpoint_output_head_gap_contract_artifact_path": "",
            "production_ai_delta_force_closure_acceptance_artifact_path": "",
            "production_ai_delta_force_closure_acceptance_packet_ready": False,
            "production_ai_delta_force_closure_ready": False,
            "production_ai_delta_force_closure_first_blocked_output_field": "",
            "production_ai_delta_force_closure_failed_stage_count": 0,
            "production_ai_delta_force_closure_failed_stage_ids": [],
            "production_ai_delta_force_closure_next_stage_id": "",
            "production_ai_delta_force_closure_next_stage_artifact": "",
            "production_ai_delta_force_closure_next_stage_validation_command": "",
            "production_ai_delta_force_closure_next_required_step": "",
            "production_ai_checkpoint_readiness_status": "",
            "production_ai_checkpoint_ready": False,
            "production_ai_checkpoint_failed_check_ids": [],
            "production_ai_checkpoint_first_failed_check_id": "",
            "production_ai_checkpoint_first_failed_source_artifact": "",
            "production_ai_checkpoint_first_failed_observed": "",
            "production_ai_checkpoint_first_failed_required": "",
            "production_ai_checkpoint_first_failed_next_action": "",
            "production_ai_checkpoint_registry_promotion_required_gate_ids": [],
            "production_ai_checkpoint_registry_promotion_missing_gate_ids": [],
            "production_ai_checkpoint_registry_promotion_missing_gate_count": 0,
            "production_ai_checkpoint_registry_promotion_upstream_acceptance_ready": False,
            "production_ai_checkpoint_registry_promotion_currently_satisfied": False,
            "production_ai_checkpoint_actionable_blocker_stage_id": "",
            "production_ai_checkpoint_actionable_blocker_check_id": "",
            "production_ai_checkpoint_actionable_blocker_artifact": "",
            "production_ai_checkpoint_actionable_blocker_observed": "",
            "production_ai_checkpoint_actionable_blocker_required": "",
            "production_ai_checkpoint_actionable_blocker_next_action": "",
            "production_ai_checkpoint_actionable_blocker_validation_command": "",
            "production_ai_checkpoint_actionable_blocker_unlock_fields": [],
            "production_ai_checkpoint_actionable_blocker_downstream_blocked_stage_count": 0,
            "production_ai_checkpoint_next_after_actionable_blocker_stage_id": "",
            "production_ai_checkpoint_next_after_actionable_blocker_artifact": "",
            "production_ai_checkpoint_next_after_actionable_blocker_validation_command": "",
            "production_ai_checkpoint_next_after_actionable_blocker_required_checks": [],
            "production_ai_checkpoint_next_after_actionable_blocker_unlock_fields": [],
            "production_ai_checkpoint_next_after_actionable_blocker_next_action": "",
            "production_ai_checkpoint_actionable_blocker_blocks_registry_promotion": False,
            "production_ai_checkpoint_actionable_operator_completion_packet_ready": False,
            "production_ai_checkpoint_actionable_operator_completion_packet_artifact": "",
            "production_ai_checkpoint_actionable_operator_completion_artifact_id": "",
            "production_ai_checkpoint_actionable_operator_completion_artifact_path": "",
            "production_ai_checkpoint_actionable_operator_completion_expected_queue_rows": 0,
            "production_ai_checkpoint_actionable_operator_completion_required_fields_or_columns": [],
            "production_ai_checkpoint_actionable_operator_completion_diagnostic_commands": [],
            "production_ai_checkpoint_actionable_operator_completion_diagnostic_command_count": 0,
            "production_ai_checkpoint_actionable_operator_completion_diagnostic_required_fields": [],
            "production_ai_checkpoint_actionable_operator_completion_diagnostic_required_field_count": 0,
            "production_ai_checkpoint_actionable_operator_completion_diagnostic_completion_rule": "",
            "production_ai_checkpoint_actionable_operator_completion_diagnostic_return_artifacts": [],
            "production_ai_checkpoint_actionable_operator_completion_torch_visibility_probe_command": "",
            "production_ai_checkpoint_actionable_operator_completion_failed_check_ids": [],
            "production_ai_checkpoint_actionable_operator_completion_template_payload_json": "",
            "production_ai_checkpoint_actionable_operator_completion_validation_command": "",
            "production_ai_checkpoint_actionable_operator_completion_full_regeneration_command": "",
            "production_ai_checkpoint_actionable_operator_completion_completion_rule": "",
            "production_ai_checkpoint_actionable_operator_completion_backend_provenance_completion_rule": "",
            "production_ai_checkpoint_actionable_operator_completion_next_action": "",
            "production_ai_checkpoint_actionable_operator_completion_packet": {},
            "production_ai_checkpoint_worker_runtime_receipt_contract_ready": False,
            "production_ai_checkpoint_worker_runtime_receipt_contract": {},
            "production_ai_checkpoint_worker_runtime_receipt_required_fields_or_columns": [],
            "production_ai_checkpoint_worker_runtime_receipt_required_field_count": 0,
            "production_ai_checkpoint_worker_runtime_receipt_completion_rule": "",
            "production_ai_checkpoint_worker_runtime_receipt_post_environment_next_stage_id": "",
            "production_ai_checkpoint_worker_runtime_receipt_post_environment_next_artifact": "",
            "production_ai_checkpoint_worker_runtime_receipt_post_environment_validation_command": "",
            "production_ai_checkpoint_worker_runtime_receipt_full_regeneration_command": "",
            "production_ai_checkpoint_worker_runtime_receipt_guardrails": [],
            "production_ai_checkpoint_acceptance_matrix_ready": False,
            "production_ai_checkpoint_acceptance_stage_count": 0,
            "production_ai_checkpoint_acceptance_ready_stage_count": 0,
            "production_ai_checkpoint_acceptance_blocked_stage_count": 0,
            "production_ai_checkpoint_acceptance_stage_ids": [],
            "production_ai_checkpoint_acceptance_ready_stage_ids": [],
            "production_ai_checkpoint_acceptance_blocked_stage_ids": [],
            "production_ai_checkpoint_acceptance_matrix": [],
            "production_ai_checkpoint_acceptance_current_blocked_stage_matrix": [],
            "production_ai_checkpoint_acceptance_release_blocker_stage_count": 0,
            "production_ai_checkpoint_acceptance_release_blocker_stage_ids": [],
            "production_ai_checkpoint_acceptance_next_stage_id": "",
            "production_ai_checkpoint_acceptance_next_stage_artifact": "",
            "production_ai_checkpoint_acceptance_next_stage_validation_command": "",
            "production_ai_checkpoint_acceptance_next_stage_release_effect": "",
            "production_ai_checkpoint_acceptance_next_stage_unlock_fields": [],
            "production_ai_checkpoint_acceptance_next_stage_required_checks": [],
            "production_ai_checkpoint_acceptance_next_stage_next_action": "",
            "production_ai_gpu_return_intake_status": "",
            "production_ai_gpu_return_intake_artifact_path": "",
            "production_ai_gpu_return_intake_ready": False,
            "production_ai_gpu_return_artifacts_ready": False,
            "production_ai_gpu_return_check_count": 0,
            "production_ai_gpu_return_fail_check_count": 0,
            "production_ai_gpu_return_failed_check_ids": [],
            "production_ai_gpu_return_blocker_matrix": [],
            "production_ai_gpu_return_blocker_matrix_count": 0,
            "production_ai_gpu_return_first_failed_check_id": "",
            "production_ai_gpu_return_first_failed_source_artifact": "",
            "production_ai_gpu_return_first_failed_observed": "",
            "production_ai_gpu_return_first_failed_required": "",
            "production_ai_gpu_return_first_failed_next_action": "",
            "production_ai_gpu_return_operator_return_artifact_completion_matrix": [],
            "production_ai_gpu_return_operator_return_artifact_completion_matrix_count": 0,
            "production_ai_gpu_return_operator_return_artifact_completion_blocker_matrix": [],
            "production_ai_gpu_return_operator_return_artifact_completion_blocker_count": 0,
            "production_ai_gpu_return_operator_return_next_artifact_completion_packet_ready": False,
            "production_ai_gpu_return_operator_return_next_artifact_completion_packet": {},
            "production_ai_gpu_return_operator_return_next_artifact_id": "",
            "production_ai_gpu_return_operator_return_next_artifact_path": "",
            "production_ai_gpu_return_operator_return_next_artifact_failed_check_ids": [],
            "production_ai_gpu_return_expected_queue_rows": 0,
            "production_ai_gpu_return_handoff_binding_ready": False,
            "production_ai_gpu_return_handoff_queue_csv": "",
            "production_ai_gpu_return_handoff_queue_csv_sha256": "",
            "production_ai_gpu_return_handoff_full_regeneration_command": "",
            "production_ai_gpu_return_handoff_return_manifest_schema_contract_ready": False,
            "production_ai_gpu_return_handoff_return_manifest_required_identity_rule": "",
            "production_ai_gpu_return_handoff_return_manifest_fingerprint_columns": [],
            "production_ai_gpu_return_handoff_return_manifest_queue_id_columns": [],
            "production_ai_gpu_return_handoff_return_manifest_npz_columns": [],
            "production_ai_gpu_return_manifest_template_csv": "",
            "production_ai_gpu_return_summary_template_csv": "",
            "production_ai_gpu_return_summary_template_payload_json": "",
            "production_ai_gpu_return_summary_template_required_fields": [],
            "production_ai_gpu_return_summary_template_completion_rule": "",
            "production_ai_gpu_return_summary_template_backend_provenance_contract_ready": False,
            "production_ai_gpu_return_summary_template_required_backend_provenance_fields": [],
            "production_ai_gpu_return_summary_template_backend_provenance_completion_rule": "",
            "production_ai_gpu_return_manifest_template_row_count": 0,
            "production_ai_gpu_return_manifest_operator_verification_placeholder_count": 0,
            "production_ai_gpu_return_operator_acceptance_matrix_ready": False,
            "production_ai_gpu_return_operator_acceptance_matrix": [],
            "production_ai_gpu_return_operator_acceptance_current_blocked_stage_matrix": [],
            "production_ai_gpu_return_operator_acceptance_stage_check_matrix": [],
            "production_ai_gpu_return_operator_acceptance_stage_check_matrix_count": 0,
            "production_ai_gpu_return_operator_acceptance_current_blocked_stage_check_matrix": [],
            "production_ai_gpu_return_operator_acceptance_current_blocked_stage_check_matrix_count": 0,
            "production_ai_gpu_return_operator_acceptance_stage_count": 0,
            "production_ai_gpu_return_operator_acceptance_ready_stage_count": 0,
            "production_ai_gpu_return_operator_acceptance_blocked_stage_count": 0,
            "production_ai_gpu_return_operator_acceptance_stage_ids": [],
            "production_ai_gpu_return_operator_acceptance_ready_stage_ids": [],
            "production_ai_gpu_return_operator_acceptance_blocked_stage_ids": [],
            "production_ai_gpu_return_operator_acceptance_next_stage_id": "",
            "production_ai_gpu_return_operator_acceptance_next_stage_artifact": "",
            "production_ai_gpu_return_operator_acceptance_next_stage_validation_command": "",
            "production_ai_gpu_return_operator_acceptance_next_stage_release_effect": "",
            "production_ai_gpu_return_operator_acceptance_next_stage_unlock_fields": [],
            "production_ai_gpu_return_operator_acceptance_next_stage_required_checks": [],
            "production_ai_gpu_return_operator_acceptance_next_stage_next_action": "",
            "production_ai_gpu_return_actual_summary_return_path": "",
            "production_ai_gpu_return_actual_manifest_return_path": "",
            "production_ai_gpu_summary_manifest_bound": False,
            "production_ai_gpu_summary_manifest_csv": "",
            "production_ai_gpu_summary_out_manifest_csv_present": False,
            "production_ai_gpu_summary_out_manifest_csv": "",
            "production_ai_gpu_summary_out_manifest_csv_bound": False,
            "production_ai_gpu_summary_out_summary_json_bound": False,
            "production_ai_gpu_summary_out_summary_json": "",
            "production_ai_gpu_summary_manifest_row_counts_consistent": False,
            "production_ai_gpu_backend_provenance_ready": False,
            "production_ai_gpu_backend_rows": 0,
            "production_ai_gpu_backend_non_production_rows": 0,
            "production_ai_gpu_backend_prod_mode": False,
            "production_ai_gpu_backend_require_rust_hip": False,
            "production_ai_gpu_worker_rocm_manifest_artifact": "",
            "production_ai_gpu_worker_rocm_manifest_ready": False,
            "production_ai_gpu_worker_rocm_manifest_generation_command": "",
            "production_ai_gpu_worker_rocm_manifest_completion_rule": "",
            "production_ai_gpu_worker_rocm_stack_detected": False,
            "production_ai_gpu_worker_rocm_torch_ready": False,
            "production_ai_gpu_worker_rocm_amd_gpu_detected": False,
            "production_ai_gpu_worker_rocm_visible_device_count": 0,
            "production_ai_gpu_worker_rocm_device_names": [],
            "production_ai_gpu_worker_rocm_next_required_step": "",
            "production_ai_checkpoint_gpu_backend_provenance_ready": False,
            "production_ai_checkpoint_gpu_backend_rows": 0,
            "production_ai_checkpoint_gpu_backend_non_production_rows": 0,
            "production_ai_gpu_return_post_return_validation_command": "",
            "production_ai_gpu_return_next_required_step": "",
            "production_ai_promotion_workbench_status": "",
            "production_ai_promotion_workbench_ready": False,
            "production_ai_promotion_ready": False,
            "production_ai_promotion_first_blocked_stage_id": "",
            "production_ai_promotion_first_blocked_stage_artifact": "",
            "production_ai_promotion_first_blocked_stage_ready_key": "",
            "production_ai_promotion_blocked_stage_count": 0,
            "production_ai_promotion_blocked_stage_ids": [],
            "production_ai_force_gpu_worker_handoff_ready": False,
            "production_ai_force_gpu_worker_operator_action_required": False,
            "production_ai_force_gpu_operator_transfer_manifest_ready": False,
            "production_ai_force_gpu_operator_transfer_outbound_artifact_count": 0,
            "production_ai_force_gpu_operator_transfer_outbound_artifacts": [],
            "production_ai_force_gpu_operator_transfer_inbound_artifact_count": 0,
            "production_ai_force_gpu_operator_transfer_inbound_artifacts": [],
            "production_ai_force_gpu_operator_transfer_first_return_artifact": "",
            "production_ai_force_gpu_operator_transfer_return_manifest_artifact": "",
            "production_ai_force_gpu_operator_transfer_acceptance_artifact": "",
            "production_ai_force_gpu_operator_transfer_acceptance_ready_key": "",
            "production_ai_force_gpu_operator_transfer_post_return_validation_command": "",
            "production_ai_force_gpu_full_regeneration_command": "",
            "production_ai_force_gpu_post_return_validation_command": "",
            "production_ai_force_gpu_post_run_validation_commands": [],
            "production_ai_force_gpu_post_return_required_production_output_fields": [],
            "production_ai_force_gpu_post_return_gpu_unlock_artifacts": [],
            "production_ai_force_gpu_post_return_unlock_output_fields": [],
            "production_ai_force_gpu_post_return_min_expected_label_rows": 0,
            "production_ai_force_gpu_post_return_promotion_ladder_stage_count": 0,
            "production_ai_force_gpu_post_return_promotion_ladder_contract_ready": False,
            "production_ai_force_gpu_post_return_promotion_ladder_currently_satisfied": False,
            "production_ai_force_gpu_post_return_promotion_ladder_current_blocked_stage_count": 0,
            "production_ai_force_gpu_post_return_promotion_ladder_current_blocked_stage_ids": [],
            "production_ai_force_gpu_post_return_promotion_ladder_current_next_stage_id": "",
            "production_ai_force_gpu_post_return_promotion_ladder_current_next_stage_artifact": "",
            "production_ai_force_gpu_post_return_promotion_ladder_current_next_stage_validation_command": "",
            "production_ai_force_gpu_post_return_promotion_ladder_stage_ids": [],
            "production_ai_force_gpu_post_return_promotion_ladder_missing_ready_keys": [],
            "production_ai_force_gpu_receipt_manifest_identity_row_count": 0,
            "production_ai_force_gpu_receipt_matched_queue_id_count": 0,
            "production_ai_force_gpu_receipt_matched_expected_npz_count": 0,
            "production_ai_force_gpu_receipt_matched_queue_fingerprint_count": 0,
            "product_scope_closure_acceptance_artifact_path": "",
            "product_scope_closure_acceptance_packet_ready": False,
            "product_scope_closure_acceptance_ready": False,
            "product_scope_closure_acceptance_stage_count": 0,
            "product_scope_closure_acceptance_blocked_stage_count": 0,
            "product_scope_closure_acceptance_blocked_stage_ids": [],
            "product_scope_closure_acceptance_next_stage_id": "",
            "product_scope_closure_acceptance_first_blocked_evidence_row_id": "",
            "product_scope_closure_acceptance_first_blocked_target_id": "",
            "product_scope_closure_acceptance_first_blocked_required_missing_fields": "",
            "product_scope_closure_acceptance_transporter_unresolved_slot_count": 0,
            "product_scope_closure_acceptance_pxr_direct_or_claim_safe_quantitative_ready_count": 0,
            "product_scope_closure_acceptance_general_platform_claim_allowed": False,
            "product_scope_closure_acceptance_next_required_step": "",
            "product_ai_scope_backlog_detail": "",
            "product_scope_closure_blocker_class_counts": {},
            "product_scope_first_scientific_blocker": "",
            "product_scope_manual_review_subcheck_count": 0,
            "product_scope_transporter_manual_review_subcheck_count": 0,
            "product_scope_transporter_identity_scaffold_confirmation_required_count": 0,
            "product_scope_transporter_direct_binding_or_kcal_confirmation_required_count": 0,
            "product_scope_transporter_negative_quantitative_confirmation_required_count": 0,
            "product_scope_transporter_direct_binding_missing_count": 0,
            "product_scope_transporter_negative_quantitative_missing_count": 0,
            "product_scope_transporter_operator_review_evidence_matrix_ready": False,
            "product_scope_transporter_claim_safe_local_evidence_ready_count": 0,
            "product_scope_transporter_claim_safe_local_evidence_blocked_count": 0,
            "product_scope_transporter_direct_binding_claim_blocked_count": 0,
            "product_scope_transporter_negative_value_claim_blocked_count": 0,
            "product_scope_transporter_top_claim_safe_blocker": "",
            "product_scope_transporter_top_operator_next_verdict": "",
            "product_scope_transporter_target_ready_for_promotion_count": 0,
            "product_scope_transporter_target_blocked_for_promotion_count": 0,
            "product_scope_transporter_target_ready_for_promotion_ids": [],
            "product_scope_transporter_target_blocked_for_promotion_ids": [],
            "product_scope_transporter_primary_blocker_target_id": "",
            "product_scope_transporter_primary_blocker_packet_step": "",
            "product_scope_transporter_primary_blocker_candidate_name": "",
            "product_scope_pxr_reconciled_blocked_row_count": 0,
            "product_scope_pxr_conflict_resolution_count": 0,
            "product_scope_pxr_quantitative_missing_count": 0,
            "product_scope_breadth_contract_status": "",
            "product_scope_breadth_contract_artifact_path": "",
            "product_scope_operator_transfer_manifest_ready": False,
            "product_scope_operator_transfer_outbound_artifact_count": 0,
            "product_scope_operator_transfer_outbound_artifacts": [],
            "product_scope_operator_transfer_inbound_artifact_count": 0,
            "product_scope_operator_transfer_inbound_artifacts": [],
            "product_scope_operator_transfer_first_return_artifact": "",
            "product_scope_operator_transfer_acceptance_artifact": "",
            "product_scope_operator_transfer_acceptance_ready_key": "",
            "product_scope_operator_transfer_next_acceptance_stage": "",
            "product_scope_operator_transfer_post_return_validation_command": "",
            "product_scope_acceptance_matrix_ready": False,
            "product_scope_claim_expansion_contract_ready": False,
            "product_scope_claim_expansion_currently_satisfied": False,
            "product_scope_claim_expansion_current_blocked_stage_count": 0,
            "product_scope_claim_expansion_current_blocked_stage_ids": [],
            "product_scope_claim_expansion_current_next_stage_id": "",
            "product_scope_claim_expansion_current_next_stage_artifact": "",
            "product_scope_claim_expansion_current_next_stage_validation_command": "",
            "product_scope_claim_expansion_current_next_stage_unlock_claim_scopes": [],
            "product_scope_acceptance_stage_count": 0,
            "product_scope_acceptance_ready_stage_count": 0,
            "product_scope_acceptance_blocked_stage_count": 0,
            "product_scope_acceptance_stage_ids": [],
            "product_scope_acceptance_ready_stage_ids": [],
            "product_scope_acceptance_blocked_stage_ids": [],
            "product_scope_acceptance_matrix": [],
            "product_scope_acceptance_current_blocked_stage_matrix": [],
            "product_scope_acceptance_stage_evidence_matrix": [],
            "product_scope_acceptance_stage_evidence_matrix_count": 0,
            "product_scope_acceptance_current_blocked_stage_evidence_matrix": [],
            "product_scope_acceptance_current_blocked_stage_evidence_matrix_count": 0,
            "product_scope_acceptance_release_blocker_stage_count": 0,
            "product_scope_acceptance_release_blocker_stage_ids": [],
            "product_scope_acceptance_next_stage_id": "",
            "product_scope_acceptance_next_stage_artifact": "",
            "product_scope_acceptance_next_stage_validation_command": "",
            "product_scope_acceptance_next_stage_release_effect": "",
            "product_scope_acceptance_next_stage_unlock_claim_scopes": [],
            "product_scope_acceptance_next_stage_required_checks": [],
            "product_scope_acceptance_next_stage_next_action": "",
            "product_scope_general_claim_blocker_count": 0,
            "product_scope_ready_for_apply_count": 0,
            "product_scope_authoritative_apply_allowed": False,
            "product_scope_domain_count": 0,
            "product_scope_ready_domain_count": 0,
            "product_scope_missing_domain_count": 0,
            "product_scope_ready_domains": [],
            "product_scope_missing_domains": [],
            "product_scope_first_blocked_domain": "",
            "product_scope_first_blocked_domain_artifact": "",
            "product_scope_first_blocked_domain_observed": "",
            "product_scope_first_blocked_domain_requirement": "",
            "product_scope_first_blocked_domain_next_action": "",
            "product_scope_transporter_p0_readiness_matrix_ready": False,
            "product_scope_transporter_p0_readiness_matrix_artifact": "",
            "product_scope_transporter_p0_auto_close_ready_artifact_count": 0,
            "product_scope_transporter_p0_manual_or_external_required_artifact_count": 0,
            "product_scope_transporter_p0_unresolved_slot_count": 0,
            "product_scope_transporter_p0_auto_close_ready_slot_count": 0,
            "product_scope_transporter_p0_external_exact_evidence_required_slot_count": 0,
            "product_scope_transporter_p0_first_manual_or_external_required_step_id": "",
            "product_scope_transporter_p0_first_manual_or_external_required_slot_step": "",
            "product_scope_transporter_p0_first_manual_or_external_required_action": "",
            "product_scope_transporter_p0_evidence_acquisition_packet_ready": False,
            "product_scope_transporter_p0_evidence_acquisition_artifact": "",
            "product_scope_transporter_p0_evidence_acquisition_exact_request_slot_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_unresolved_slot_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_first_target_id": "",
            "product_scope_transporter_p0_evidence_acquisition_first_packet_step": "",
            "product_scope_transporter_p0_evidence_acquisition_first_replacement_ligand_id": "",
            "product_scope_transporter_p0_evidence_acquisition_first_request_mode": "",
            "product_scope_transporter_p0_evidence_acquisition_first_source_signal": "",
            "product_scope_transporter_p0_evidence_acquisition_first_required_missing_fields": "",
            "product_scope_transporter_p0_evidence_acquisition_first_next_required_action": "",
            "product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet_ready": False,
            "product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet": {},
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifacts": [],
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix": [],
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_blocker_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id": "",
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_path": "",
            "product_scope_transporter_p0_evidence_acquisition_next_slot_id": "",
            "product_scope_transporter_p0_evidence_acquisition_next_slot_operator_review_artifact": "",
            "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_guard_ready": False,
            "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality": "",
            "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_claim_safe": False,
            "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_direct_binding_claim_allowed": False,
            "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_decision": "",
            "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_guardrails": [],
            "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_observed_signal": "",
            "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_required_upgrade": "",
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_source_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_result": "",
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_database_recheck_row_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_ligand_identity_mismatch_row_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_like_binding_candidate_row_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_like_binding_candidate_claim_safe_ready_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_chembl_id": "",
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_delta_g_kcal_mol": "",
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_blocker": "",
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bindingdb_aqp1_expanded_cutoff_affinity_row_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bindingdb_aqp1_expanded_cutoff_direct_like_affinity_row_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_pubchem_cid": "",
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_id": "",
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_chembl_target_id": "",
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_bindingdb_uniprot_affinity_row_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_aqp1_activity_row_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_functional_ic50_identity_mismatch_detail": "",
            "product_scope_general_platform_domain_floor_ready": False,
            "product_scope_general_platform_domain_floor_missing_domain_count": 0,
            "product_scope_general_platform_domain_floor_missing_domains": [],
            "product_scope_allowed_families": [],
            "product_scope_blocked_claim_scopes": [],
            "product_scope_claim_blocked_domains": [],
            "product_scope_general_platform_claim_allowed": False,
            "product_scope_evidence_priority_ready": False,
            "product_scope_evidence_priority_queue_item_count": 0,
            "product_scope_evidence_priority_open_item_count": 0,
            "product_scope_evidence_priority_local_crosscheck_candidate_count": 0,
            "product_scope_evidence_priority_external_primary_exact_required_count": 0,
            "product_scope_evidence_priority_top_item_id": "",
            "product_scope_evidence_priority_top_domain": "",
            "product_scope_evidence_priority_top_bucket": "",
            "product_scope_evidence_priority_top_next_step": "",
            "product_scope_evidence_priority_next_required_step": "",
            "product_scope_evidence_intake_ready": False,
            "product_scope_evidence_intake_row_count": 0,
            "product_scope_local_crosscheck_triage_item_count": 0,
            "product_scope_local_crosscheck_intake_ready_count": 0,
            "product_scope_external_exact_evidence_required_count": 0,
            "product_scope_guardrail_item_count": 0,
            "product_scope_transporter_triage_packet_ready": False,
            "product_scope_transporter_candidate_assignment_required_count": 0,
            "product_scope_transporter_functional_quantitative_only_direct_gap_open_count": 0,
            "product_scope_transporter_review_only_direct_binding_gap_count": 0,
            "product_scope_transporter_candidate_ready_for_manual_review_count": 0,
            "product_scope_transporter_candidate_ready_for_apply_count": 0,
            "product_scope_transporter_manual_review_intake_ready": False,
            "product_scope_transporter_manual_review_template_row_count": 0,
            "product_scope_transporter_manual_review_direct_binding_evidence_required_count": 0,
            "product_scope_transporter_manual_review_negative_quantitative_value_required_count": 0,
            "product_scope_transporter_manual_review_decision_placeholder_count": 0,
            "product_scope_transporter_manual_review_p0_slot_overlay_row_count": 0,
            "product_scope_transporter_manual_review_p0_slot_overlay_candidate_changed_count": 0,
            "product_scope_transporter_manual_review_p0_slot_overlay_first_item_id": "",
            "product_scope_transporter_manual_review_p0_slot_overlay_first_candidate_ligand_id": "",
            "product_scope_transporter_manual_review_p0_slot_overlay_first_source": "",
            "product_scope_transporter_manual_review_first_review_row_id": "",
            "product_scope_transporter_manual_review_first_review_item_id": "",
            "product_scope_transporter_manual_review_first_review_target_id": "",
            "product_scope_transporter_manual_review_first_review_candidate_ligand_id": "",
            "product_scope_transporter_manual_review_first_review_replacement_source": "",
            "product_scope_transporter_manual_review_first_review_replacement_reference_binding_kcal_mol": "",
            "product_scope_transporter_manual_review_first_review_direct_binding_evidence_required": False,
            "product_scope_transporter_manual_review_first_review_direct_binding_source_url_or_doi": "",
            "product_scope_transporter_manual_review_first_review_negative_quantitative_value_required": False,
            "product_scope_transporter_manual_review_first_review_negative_reference_binding_kcal_mol": "",
            "product_scope_transporter_manual_review_first_review_review_decision": "",
            "product_scope_transporter_manual_review_first_review_authoritative_apply_requested": "",
            "product_scope_transporter_manual_review_first_review_manual_review_blockers": "",
            "product_scope_transporter_manual_review_first_review_review_requirements": "",
            "product_scope_transporter_manual_review_first_review_p0_slot_overlay_required_missing_fields": "",
            "product_scope_transporter_manual_review_first_review_p0_slot_overlay_claim_safe_step_ready": False,
            "product_scope_transporter_manual_review_first_review_p0_slot_overlay_authoritative_apply_allowed": False,
            "product_scope_transporter_manual_review_first_review_p0_slot_overlay_scope_promotion_allowed": False,
            "product_scope_evidence_intake_next_required_step": "",
            "product_scope_pxr_exact_review_intake_ready": False,
            "product_scope_pxr_exact_review_template_row_count": 0,
            "product_scope_pxr_exact_review_expected_blocked_row_count": 0,
            "product_scope_pxr_exact_review_conflict_resolution_required_count": 0,
            "product_scope_pxr_exact_review_kcal_placeholder_count": 0,
            "product_scope_pxr_exact_review_source_placeholder_count": 0,
            "product_scope_pxr_exact_review_target_match_placeholder_count": 0,
            "product_scope_pxr_exact_review_decision_placeholder_count": 0,
            "product_scope_pxr_exact_review_next_review_completion_packet_ready": False,
            "product_scope_pxr_exact_review_next_review_completion_packet": {},
            "product_scope_pxr_exact_review_next_review_return_bundle_required_artifacts": [],
            "product_scope_pxr_exact_review_next_review_return_bundle_required_artifact_count": 0,
            "product_scope_pxr_exact_review_next_review_return_bundle_completion_matrix": [],
            "product_scope_pxr_exact_review_next_review_return_bundle_completion_matrix_count": 0,
            "product_scope_pxr_exact_review_next_review_return_bundle_blocker_count": 0,
            "product_scope_pxr_exact_review_next_review_return_bundle_next_artifact_id": "",
            "product_scope_pxr_exact_review_next_review_return_bundle_next_artifact_path": "",
            "product_scope_pxr_exact_review_next_review_return_bundle_next_artifact_failed_check_ids": [],
            "product_scope_pxr_exact_review_next_review_row_id": "",
            "product_scope_pxr_exact_review_next_review_candidate_name": "",
            "product_scope_pxr_exact_review_next_review_operator_review_artifact": "",
            "product_scope_pxr_exact_review_next_required_step": "",
            "product_scope_pxr_source_modality_triage_ready": False,
            "product_scope_pxr_source_modality_triage_status": "",
            "product_scope_pxr_source_modality_triage_artifact": "",
            "product_scope_pxr_source_modality_triage_decision": "",
            "product_scope_pxr_source_modality_public_evidence_recheck_ready": False,
            "product_scope_pxr_source_modality_public_recheck_artifact": "",
            "product_scope_pxr_source_modality_public_recheck_candidate_count": 0,
            "product_scope_pxr_source_modality_public_recheck_chembl_direct_binding_total_record_count": 0,
            "product_scope_pxr_source_modality_public_recheck_chembl_functional_activity_total_record_count": 0,
            "product_scope_pxr_source_modality_public_recheck_bindingdb_pxr_like_total_record_count": 0,
            "product_scope_pxr_source_modality_public_recheck_direct_or_claim_safe_binding_kcal_ready_count": 0,
            "product_scope_pxr_source_modality_public_recheck_all_candidates_remain_blocked": False,
            "product_scope_pxr_source_modality_public_recheck_first_blocked_candidate_name": "",
            "product_scope_pxr_source_modality_public_recheck_first_blocked_reason": "",
            "product_scope_pxr_source_modality_direct_replacement_candidate_packet_ready": False,
            "product_scope_pxr_source_modality_direct_replacement_artifact": "",
            "product_scope_pxr_source_modality_direct_replacement_candidate_count": 0,
            "product_scope_pxr_source_modality_direct_replacement_selected_candidate_count": 0,
            "product_scope_pxr_source_modality_direct_replacement_selected_claim_safe_candidate_count": 0,
            "product_scope_pxr_source_modality_direct_replacement_first_ligand_id": "",
            "product_scope_pxr_source_modality_direct_replacement_first_molecule_chembl_id": "",
            "product_scope_pxr_source_modality_direct_replacement_first_reference_binding_kcal_mol": "",
            "product_scope_pxr_source_modality_direct_replacement_first_source": "",
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_ready": False,
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_status": "",
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_artifact": "",
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_workbook_row_count": 0,
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_before_draft": 0,
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_overlay_row_count": 0,
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_ready_for_apply_row_count_after_draft": 0,
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_after_draft": 0,
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_first_overlay_ligand_id": "",
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_authoritative_fields_touched": False,
            "product_scope_pxr_source_modality_activity_proxy_or_conflict_surrogate_row_count": 0,
            "product_scope_pxr_source_modality_direct_or_claim_safe_quantitative_ready_count": 0,
            "product_scope_pxr_source_modality_accepted_for_scope_promotion_count": 0,
            "product_scope_pxr_source_modality_next_review_row_id": "",
            "product_scope_pxr_source_modality_next_review_candidate_name": "",
            "product_scope_pxr_source_modality_next_review_source_modality": "",
            "product_scope_pxr_source_modality_next_review_rejection_reason": "",
            "requirements": [],
            "execution_enabled": False,
            "docking_results_emitted": False,
            "license_file_written": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product goal-completion-audit endpoint only; the local completion audit artifact is missing or invalid. "
                "It does not choose a license, run docking, create files, submit predictions, or mutate external state."
            ),
            "release_complete_vs_operator_pending_lane": lane_surface["release_complete_vs_operator_pending_lane"],
            "goal_completion_audit_goal_complete": lane_surface["goal_completion_audit_goal_complete"],
            "release_complete_lane_ready": lane_surface["release_complete_lane_ready"],
            "operator_pending_lane_ready": lane_surface["operator_pending_lane_ready"],
            "operator_or_external_pending_lane_count": lane_surface["operator_or_external_pending_lane_count"],
            "release_complete_vs_operator_pending_matrix": lane_surface["release_complete_vs_operator_pending_matrix"],
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_GOAL_COMPLETION_AUDIT_ARTIFACT),
        "goal_complete": bool(summary.get("goal_complete") is True),
        "requirement_count": int(summary.get("requirement_count") or 0),
        "pass_count": int(summary.get("pass_count") or 0),
        "fail_count": int(summary.get("fail_count") or 0),
        "primary_bottleneck_phase": summary.get("primary_bottleneck_phase", ""),
        "primary_bottleneck_kind": summary.get("primary_bottleneck_kind", ""),
        "approval_tokens_required": list(summary.get("approval_tokens_required") or []),
        "next_command": summary.get("next_command", ""),
        "next_command_candidate_count": int(summary.get("next_command_candidate_count") or 0),
        "next_command_candidates": list(summary.get("next_command_candidates") or []),
        "release_allowed": bool(summary.get("release_allowed") is True),
        "commercial_independence_ready": bool(summary.get("commercial_independence_ready") is True),
        "public_benchmark_validation_ready": bool(summary.get("public_benchmark_validation_ready") is True),
        "local_self_hosted_product_ready": bool(summary.get("local_self_hosted_product_ready") is True),
        "cameo_optional_live_validation_ready": bool(summary.get("cameo_optional_live_validation_ready") is True),
        "release_artifact_ready": bool(summary.get("release_artifact_ready") is True),
        "product_ai_architecture_ready": bool(summary.get("product_ai_architecture_ready") is True),
        "product_ai_architecture_gap_status": summary.get("product_ai_architecture_gap_status", ""),
        "product_ai_architecture_all_gaps_closed": bool(
            summary.get("product_ai_architecture_all_gaps_closed") is True
        ),
        "product_ai_architecture_gap_count": int(summary.get("product_ai_architecture_gap_count") or 0),
        "product_ai_architecture_closed_gap_count": int(
            summary.get("product_ai_architecture_closed_gap_count") or 0
        ),
        "product_ai_architecture_open_gap_count": int(summary.get("product_ai_architecture_open_gap_count") or 0),
        "product_ai_architecture_open_gap_ids": list(summary.get("product_ai_architecture_open_gap_ids") or []),
        "product_ai_architecture_closed_gap_ids": list(summary.get("product_ai_architecture_closed_gap_ids") or []),
        "product_ai_architecture_gap_blocker_matrix_ready": bool(
            summary.get("product_ai_architecture_gap_blocker_matrix_ready") is True
        ),
        "product_ai_architecture_gap_blocker_matrix_count": int(
            summary.get("product_ai_architecture_gap_blocker_matrix_count") or 0
        ),
        "product_ai_architecture_gap_blocker_matrix": list(
            summary.get("product_ai_architecture_gap_blocker_matrix") or []
        ),
        "product_ai_architecture_current_primary_blocker_gap_id": summary.get(
            "product_ai_architecture_current_primary_blocker_gap_id", ""
        ),
        "product_ai_architecture_current_primary_blocker_id": summary.get(
            "product_ai_architecture_current_primary_blocker_id", ""
        ),
        "product_ai_architecture_current_primary_blocker_artifact": summary.get(
            "product_ai_architecture_current_primary_blocker_artifact", ""
        ),
        "product_ai_architecture_current_primary_blocker_validation_command": summary.get(
            "product_ai_architecture_current_primary_blocker_validation_command", ""
        ),
        "product_ai_architecture_current_primary_blocker_next_action": summary.get(
            "product_ai_architecture_current_primary_blocker_next_action", ""
        ),
        "product_ai_architecture_current_primary_blocker_operator_input_fields": list(
            summary.get("product_ai_architecture_current_primary_blocker_operator_input_fields") or []
        ),
        "product_ai_architecture_current_primary_blocker_unlock_claim": summary.get(
            "product_ai_architecture_current_primary_blocker_unlock_claim", ""
        ),
        "product_ai_architecture_current_primary_blocker_next_after_stage_id": summary.get(
            "product_ai_architecture_current_primary_blocker_next_after_stage_id", ""
        ),
        "product_ai_architecture_current_primary_blocker_next_after_artifact": summary.get(
            "product_ai_architecture_current_primary_blocker_next_after_artifact", ""
        ),
        "product_ai_architecture_current_primary_blocker_next_after_validation_command": summary.get(
            "product_ai_architecture_current_primary_blocker_next_after_validation_command", ""
        ),
        "product_ai_architecture_current_primary_blocker_next_after_next_action": summary.get(
            "product_ai_architecture_current_primary_blocker_next_after_next_action", ""
        ),
        "product_ai_architecture_current_primary_blocker_next_after_required_checks": list(
            summary.get("product_ai_architecture_current_primary_blocker_next_after_required_checks")
            or []
        ),
        "product_ai_architecture_current_primary_blocker_next_after_unlock_fields": list(
            summary.get("product_ai_architecture_current_primary_blocker_next_after_unlock_fields")
            or []
        ),
        "product_ai_architecture_parallelizable_gap_blocker_count": int(
            summary.get("product_ai_architecture_parallelizable_gap_blocker_count") or 0
        ),
        "product_ai_architecture_parallelizable_gap_blocker_ids": list(
            summary.get("product_ai_architecture_parallelizable_gap_blocker_ids") or []
        ),
        "product_ai_architecture_first_parallelizable_gap_id": summary.get(
            "product_ai_architecture_first_parallelizable_gap_id", ""
        ),
        "product_ai_architecture_first_parallelizable_blocker_id": summary.get(
            "product_ai_architecture_first_parallelizable_blocker_id", ""
        ),
        "product_ai_architecture_first_parallelizable_blocker_artifact": summary.get(
            "product_ai_architecture_first_parallelizable_blocker_artifact", ""
        ),
        "product_ai_architecture_first_parallelizable_blocker_next_action": summary.get(
            "product_ai_architecture_first_parallelizable_blocker_next_action", ""
        ),
        "product_ai_architecture_first_parallelizable_blocker_validation_command": summary.get(
            "product_ai_architecture_first_parallelizable_blocker_validation_command", ""
        ),
        "product_ai_architecture_first_parallelizable_blocker_operator_input_fields": list(
            summary.get("product_ai_architecture_first_parallelizable_blocker_operator_input_fields")
            or []
        ),
        "product_ai_architecture_first_parallelizable_blocker_required_exact_evidence_fields": list(
            summary.get(
                "product_ai_architecture_first_parallelizable_blocker_required_exact_evidence_fields"
            )
            or []
        ),
        "product_ai_architecture_first_parallelizable_blocker_required_claim_guardrails": list(
            summary.get("product_ai_architecture_first_parallelizable_blocker_required_claim_guardrails")
            or []
        ),
        "product_ai_architecture_first_parallelizable_blocker_claim_safe_completion_rule": summary.get(
            "product_ai_architecture_first_parallelizable_blocker_claim_safe_completion_rule", ""
        ),
        "product_ai_architecture_first_parallelizable_blocker_unlock_claim": summary.get(
            "product_ai_architecture_first_parallelizable_blocker_unlock_claim", ""
        ),
        "product_ai_architecture_first_parallelizable_blocker_source_modality_triage_artifact": summary.get(
            "product_ai_architecture_first_parallelizable_blocker_source_modality_triage_artifact", ""
        ),
        "product_ai_architecture_first_parallelizable_blocker_source_modality_triage_decision": summary.get(
            "product_ai_architecture_first_parallelizable_blocker_source_modality_triage_decision", ""
        ),
        "product_ai_architecture_first_parallelizable_blocker_source_modality_direct_experimental_binding_row_count": int(
            summary.get(
                "product_ai_architecture_first_parallelizable_blocker_source_modality_direct_experimental_binding_row_count"
            )
            or 0
        ),
        "product_ai_architecture_first_parallelizable_blocker_source_modality_claim_safe_binding_kcal_ready_count": int(
            summary.get(
                "product_ai_architecture_first_parallelizable_blocker_source_modality_claim_safe_binding_kcal_ready_count"
            )
            or 0
        ),
        "product_ai_architecture_first_parallelizable_blocker_source_modality_computational_binding_energy_row_count": int(
            summary.get(
                "product_ai_architecture_first_parallelizable_blocker_source_modality_computational_binding_energy_row_count"
            )
            or 0
        ),
        "product_ai_architecture_first_parallelizable_blocker_source_modality_best_computational_binding_energy_kcal_mol": summary.get(
            "product_ai_architecture_first_parallelizable_blocker_source_modality_best_computational_binding_energy_kcal_mol",
            "",
        ),
        "commercial_readiness_next_action_matrix_ready": bool(
            summary.get("commercial_readiness_next_action_matrix_ready") is True
        ),
        "commercial_readiness_next_action_matrix": list(
            summary.get("commercial_readiness_next_action_matrix") or []
        ),
        "commercial_readiness_next_action_matrix_count": int(
            summary.get("commercial_readiness_next_action_matrix_count") or 0
        ),
        "commercial_readiness_next_action_blocker_matrix": list(
            summary.get("commercial_readiness_next_action_blocker_matrix") or []
        ),
        "commercial_readiness_next_action_blocker_count": int(
            summary.get("commercial_readiness_next_action_blocker_count") or 0
        ),
        "commercial_readiness_first_next_action_id": summary.get(
            "commercial_readiness_first_next_action_id", ""
        ),
        "commercial_readiness_first_next_action_artifact": summary.get(
            "commercial_readiness_first_next_action_artifact", ""
        ),
        "commercial_readiness_first_next_action_validation_command": summary.get(
            "commercial_readiness_first_next_action_validation_command", ""
        ),
        "commercial_readiness_handoff_bundle_status": summary.get(
            "commercial_readiness_handoff_bundle_status", ""
        ),
        "commercial_readiness_handoff_bundle_artifact_path": summary.get(
            "commercial_readiness_handoff_bundle_artifact_path", ""
        ),
        "commercial_readiness_handoff_bundle_ready": bool(
            summary.get("commercial_readiness_handoff_bundle_ready") is True
        ),
        "commercial_readiness_handoff_bundle_artifact_count": int(
            summary.get("commercial_readiness_handoff_bundle_artifact_count") or 0
        ),
        "commercial_readiness_handoff_bundle_blocked_artifact_count": int(
            summary.get("commercial_readiness_handoff_bundle_blocked_artifact_count") or 0
        ),
        "commercial_readiness_handoff_bundle_blocked_artifact_ids": list(
            summary.get("commercial_readiness_handoff_bundle_blocked_artifact_ids") or []
        ),
        "commercial_readiness_handoff_bundle_artifact_reference_contract_ready": bool(
            summary.get("commercial_readiness_handoff_bundle_artifact_reference_contract_ready")
            is True
        ),
        "commercial_readiness_handoff_bundle_artifact_reference_count": int(
            summary.get("commercial_readiness_handoff_bundle_artifact_reference_count") or 0
        ),
        "commercial_readiness_handoff_bundle_local_missing_artifact_reference_count": int(
            summary.get("commercial_readiness_handoff_bundle_local_missing_artifact_reference_count")
            or 0
        ),
        "commercial_readiness_handoff_bundle_operator_return_pending_artifact_reference_count": int(
            summary.get(
                "commercial_readiness_handoff_bundle_operator_return_pending_artifact_reference_count"
            )
            or 0
        ),
        "commercial_readiness_handoff_bundle_first_action_id": summary.get(
            "commercial_readiness_handoff_bundle_first_action_id", ""
        ),
        "commercial_readiness_handoff_bundle_first_operator_input_artifact": summary.get(
            "commercial_readiness_handoff_bundle_first_operator_input_artifact", ""
        ),
        "commercial_readiness_handoff_bundle_next_required_step": summary.get(
            "commercial_readiness_handoff_bundle_next_required_step", ""
        ),
        "product_ai_production_checkpoint_gap_ready": bool(
            summary.get("product_ai_production_checkpoint_gap_ready") is True
        ),
        "product_ai_production_checkpoint_gap_observed": summary.get(
            "product_ai_production_checkpoint_gap_observed", ""
        ),
        "product_ai_closed_loop_decision_graph_ready": bool(
            summary.get("product_ai_closed_loop_decision_graph_ready") is True
        ),
        "product_ai_closed_loop_decision_graph_observed": summary.get(
            "product_ai_closed_loop_decision_graph_observed", ""
        ),
        "product_ai_durable_job_orchestration_ready": bool(
            summary.get("product_ai_durable_job_orchestration_ready") is True
        ),
        "product_ai_durable_job_orchestration_observed": summary.get(
            "product_ai_durable_job_orchestration_observed", ""
        ),
        "product_ai_trajectory_sla_ready": bool(summary.get("product_ai_trajectory_sla_ready") is True),
        "product_ai_trajectory_sla_observed": summary.get("product_ai_trajectory_sla_observed", ""),
        "product_ai_trajectory_sla_claim_tier": summary.get("product_ai_trajectory_sla_claim_tier", ""),
        "product_ai_trajectory_sla_restricted_family_allowed": bool(
            summary.get("product_ai_trajectory_sla_restricted_family_allowed") is True
        ),
        "product_ai_trajectory_sla_broad_platform_allowed": bool(
            summary.get("product_ai_trajectory_sla_broad_platform_allowed") is True
        ),
        "product_ai_trajectory_sla_current_rocm_baseline_claim_scope": summary.get(
            "product_ai_trajectory_sla_current_rocm_baseline_claim_scope", ""
        ),
        "product_ai_trajectory_sla_current_rocm_baseline_production_profile_enabled": bool(
            summary.get("product_ai_trajectory_sla_current_rocm_baseline_production_profile_enabled") is True
        ),
        "product_ai_trajectory_sla_rocm_baseline_profile_gap_acknowledged": bool(
            summary.get("product_ai_trajectory_sla_rocm_baseline_profile_gap_acknowledged") is True
        ),
        "product_ai_scope_breadth_ready": bool(summary.get("product_ai_scope_breadth_ready") is True),
        "product_ai_scope_breadth_observed": summary.get("product_ai_scope_breadth_observed", ""),
        "product_scope_evidence_queue_next_operator_completion_packet_ready": bool(
            summary.get("product_scope_evidence_queue_next_operator_completion_packet_ready") is True
        ),
        "product_scope_evidence_queue_next_operator_completion_slot_id": summary.get(
            "product_scope_evidence_queue_next_operator_completion_slot_id", ""
        ),
        "product_scope_evidence_queue_next_operator_completion_expected_evidence_type": summary.get(
            "product_scope_evidence_queue_next_operator_completion_expected_evidence_type", ""
        ),
        "product_scope_evidence_queue_next_operator_completion_required_exact_evidence_field_count": int(
            summary.get(
                "product_scope_evidence_queue_next_operator_completion_required_exact_evidence_field_count",
                0,
            )
            or 0
        ),
        "product_scope_evidence_queue_next_operator_completion_required_exact_evidence_fields": summary.get(
            "product_scope_evidence_queue_next_operator_completion_required_exact_evidence_fields", ""
        ),
        "product_scope_evidence_queue_next_operator_completion_required_operator_intake_columns": summary.get(
            "product_scope_evidence_queue_next_operator_completion_required_operator_intake_columns", ""
        ),
        "product_scope_evidence_queue_next_operator_completion_required_claim_guardrails": summary.get(
            "product_scope_evidence_queue_next_operator_completion_required_claim_guardrails", ""
        ),
        "product_scope_evidence_queue_next_operator_completion_operator_review_artifact": summary.get(
            "product_scope_evidence_queue_next_operator_completion_operator_review_artifact", ""
        ),
        "product_scope_evidence_queue_next_operator_completion_post_intake_synchronization_targets": summary.get(
            "product_scope_evidence_queue_next_operator_completion_post_intake_synchronization_targets", ""
        ),
        "product_scope_evidence_queue_next_operator_completion_acceptance_gate_commands": summary.get(
            "product_scope_evidence_queue_next_operator_completion_acceptance_gate_commands", ""
        ),
        "product_scope_evidence_queue_next_operator_completion_contract_artifact": summary.get(
            "product_scope_evidence_queue_next_operator_completion_contract_artifact", ""
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_sidecar_ready": bool(
            summary.get(
                "product_scope_evidence_queue_next_operator_completion_aqp1_review_sidecar_ready"
            )
            is True
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_functional_surrogate_artifact": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_functional_surrogate_artifact",
            "",
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_candidate_ledger_artifact": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_candidate_ledger_artifact",
            "",
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_candidate_name": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_candidate_name", ""
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_source_anchor": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_source_anchor", ""
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_source_url": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_source_url", ""
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_target_uniprot": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_target_uniprot", ""
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_functional_measure": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_functional_measure",
            "",
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol",
            "",
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_assay_type_honesty": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_assay_type_honesty",
            "",
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_direct_binding_claim_allowed": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_direct_binding_claim_allowed",
            "",
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_binding_kcal_claim_allowed": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_binding_kcal_claim_allowed",
            "",
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank",
            "",
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_claim_safe_functional_kcal_ready": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_claim_safe_functional_kcal_ready",
            "",
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_ledger_review_bucket": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_ledger_review_bucket",
            "",
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_ledger_promotion_policy": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_ledger_promotion_policy",
            "",
        ),
        "product_scope_evidence_queue_pxr_exact_review_sidecar_row_count": int(
            summary.get("product_scope_evidence_queue_pxr_exact_review_sidecar_row_count") or 0
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_sidecar_ready": bool(
            summary.get("product_scope_evidence_queue_next_pxr_exact_review_sidecar_ready") is True
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_row_id": summary.get(
            "product_scope_evidence_queue_next_pxr_exact_review_row_id", ""
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_candidate_name": summary.get(
            "product_scope_evidence_queue_next_pxr_exact_review_candidate_name", ""
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_required_evidence_mode": summary.get(
            "product_scope_evidence_queue_next_pxr_exact_review_required_evidence_mode", ""
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_target_match_confirmed": summary.get(
            "product_scope_evidence_queue_next_pxr_exact_review_target_match_confirmed", ""
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_replacement_reference_binding_kcal_mol": summary.get(
            "product_scope_evidence_queue_next_pxr_exact_review_replacement_reference_binding_kcal_mol",
            "",
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_replacement_source_url_or_doi": summary.get(
            "product_scope_evidence_queue_next_pxr_exact_review_replacement_source_url_or_doi",
            "",
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_authoritative_apply_allowed": bool(
            summary.get("product_scope_evidence_queue_next_pxr_exact_review_authoritative_apply_allowed") is True
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_scope_promotion_allowed": bool(
            summary.get("product_scope_evidence_queue_next_pxr_exact_review_scope_promotion_allowed") is True
        ),
        "product_ai_report_ux_ready": bool(summary.get("product_ai_report_ux_ready") is True),
        "product_ai_report_ux_observed": summary.get("product_ai_report_ux_observed", ""),
        "product_ai_report_ux_customer_report_delivery_contract_ready": bool(
            summary.get("product_ai_report_ux_customer_report_delivery_contract_ready") is True
        ),
        "product_ai_report_ux_customer_report_evidence_binding_ready": bool(
            summary.get("product_ai_report_ux_customer_report_evidence_binding_ready") is True
        ),
        "product_ai_report_ux_customer_report_viewer_binding_ready": bool(
            summary.get("product_ai_report_ux_customer_report_viewer_binding_ready") is True
        ),
        "product_ai_report_ux_viewer_customer_report_binding_ready": bool(
            summary.get("product_ai_report_ux_viewer_customer_report_binding_ready") is True
        ),
        "product_ai_report_ux_customer_report_ready_block_count": int(
            summary.get("product_ai_report_ux_customer_report_ready_block_count") or 0
        ),
        "product_ai_report_ux_customer_report_required_block_count": int(
            summary.get("product_ai_report_ux_customer_report_required_block_count") or 0
        ),
        "product_ai_report_ux_customer_report_blocked_block_count": int(
            summary.get("product_ai_report_ux_customer_report_blocked_block_count") or 0
        ),
        "product_ai_security_deployment_ready": bool(
            summary.get("product_ai_security_deployment_ready") is True
        ),
        "product_ai_security_deployment_observed": summary.get("product_ai_security_deployment_observed", ""),
        "product_ai_security_hosted_deployment_contract_ready": bool(
            summary.get("product_ai_security_hosted_deployment_contract_ready") is True
        ),
        "product_ai_security_hosted_deployment_currently_satisfied": bool(
            summary.get("product_ai_security_hosted_deployment_currently_satisfied") is True
        ),
        "product_ai_security_hosted_deployment_next_stage_id": summary.get(
            "product_ai_security_hosted_deployment_next_stage_id", ""
        ),
        "product_ai_security_hosted_external_exposure_allowed": bool(
            summary.get("product_ai_security_hosted_external_exposure_allowed") is True
        ),
        "product_ai_security_hosted_secret_injection_ready": bool(
            summary.get("product_ai_security_hosted_secret_injection_ready") is True
        ),
        "product_ai_security_tls_termination_operator_verified": bool(
            summary.get("product_ai_security_tls_termination_operator_verified") is True
        ),
        "production_ai_inference_subject_active": bool(
            registry.get("production_promotion_allowed") is True
            and registry.get("customer_facing_auto_correction_allowed") is True
            and registry.get("customer_facing_score_mutation_allowed") is True
            and registry.get("customer_facing_ranking_mutation_allowed") is True
            and registry.get("trained_model_checkpoint_count")
            and str(registry.get("default_residual_mode") or "") in {"assist", "production", "production_guarded"}
        ),
        "production_ai_default_residual_mode": registry.get("default_residual_mode", ""),
        "production_ai_promotion_allowed": bool(registry.get("production_promotion_allowed") is True),
        "production_ai_customer_facing_auto_correction_allowed": bool(
            registry.get("customer_facing_auto_correction_allowed") is True
        ),
        "production_ai_customer_facing_score_mutation_allowed": bool(
            registry.get("customer_facing_score_mutation_allowed") is True
        ),
        "production_ai_customer_facing_ranking_mutation_allowed": bool(
            registry.get("customer_facing_ranking_mutation_allowed") is True
        ),
        "production_ai_trained_checkpoint_count": int(registry.get("trained_model_checkpoint_count") or 0),
        "production_ai_selected_sidecar_ready": bool(registry.get("selected_sidecar_ready") is True),
        "production_ai_selected_sidecar_missing_output_fields": list(
            registry.get("selected_sidecar_missing_output_fields") or []
        ),
        "production_ai_blocked_reason": registry.get("production_promotion_blocked_reason", ""),
        "production_ai_residual_model_registry_status": summary.get(
            "production_ai_residual_model_registry_status", registry.get("status", "")
        ),
        "production_ai_residual_model_registry_artifact_path": summary.get(
            "production_ai_residual_model_registry_artifact_path", str(RESIDUAL_MODEL_REGISTRY_ARTIFACT)
        ),
        "production_ai_residual_model_registry_ready": bool(
            summary.get("production_ai_residual_model_registry_ready") is True
            or registry.get("registry_ready") is True
        ),
        "production_ai_product_model_layer_ready": bool(
            summary.get("production_ai_product_model_layer_ready") is True
            or registry.get("product_model_layer_ready") is True
        ),
        "production_ai_registry_checkpoint_preflight_ready": bool(
            summary.get("production_ai_registry_checkpoint_preflight_ready") is True
            or registry.get("checkpoint_preflight_ready") is True
        ),
        "production_ai_registry_production_checkpoint_blocked": bool(
            summary.get("production_ai_registry_production_checkpoint_blocked") is True
            or registry.get("production_checkpoint_blocked") is True
        ),
        "production_ai_registry_checkpoint_primary_blocker": summary.get(
            "production_ai_registry_checkpoint_primary_blocker", registry.get("checkpoint_primary_blocker", "")
        ),
        "production_ai_registry_checkpoint_missing_output_fields": list(
            summary.get("production_ai_registry_checkpoint_missing_output_fields")
            or registry.get("checkpoint_missing_output_fields")
            or []
        ),
        "production_ai_registry_checkpoint_missing_adapter_output_policy_fields": list(
            summary.get("production_ai_registry_checkpoint_missing_adapter_output_policy_fields")
            or registry.get("checkpoint_missing_adapter_output_policy_fields")
            or []
        ),
        "product_ai_primary_backlog_detail": summary.get("product_ai_primary_backlog_detail", ""),
        "product_ai_primary_backlog_work_item_id": summary.get("product_ai_primary_backlog_work_item_id", ""),
        "product_ai_primary_backlog_acceptance_criteria": summary.get(
            "product_ai_primary_backlog_acceptance_criteria", ""
        ),
        "product_ai_primary_backlog_next_action": summary.get("product_ai_primary_backlog_next_action", ""),
        "product_ai_primary_backlog_source_artifact": summary.get("product_ai_primary_backlog_source_artifact", ""),
        "product_ai_primary_backlog_verification_command": summary.get(
            "product_ai_primary_backlog_verification_command", ""
        ),
        "production_ai_gpu_worker_return_receipt_ready": bool(
            summary.get("production_ai_gpu_worker_return_receipt_ready") is True
        ),
        "production_ai_gpu_worker_return_receipt_blockers": list(
            summary.get("production_ai_gpu_worker_return_receipt_blockers") or []
        ),
        "production_ai_gpu_expected_queue_rows": int(summary.get("production_ai_gpu_expected_queue_rows") or 0),
        "production_ai_gpu_manifest_ok_row_count": int(
            summary.get("production_ai_gpu_manifest_ok_row_count") or 0
        ),
        "production_ai_gpu_manifest_status_placeholder_count": int(
            summary.get("production_ai_gpu_manifest_status_placeholder_count") or 0
        ),
        "production_ai_gpu_manifest_status_invalid_count": int(
            summary.get("production_ai_gpu_manifest_status_invalid_count") or 0
        ),
        "production_ai_gpu_manifest_npz_paths_complete": bool(
            summary.get("production_ai_gpu_manifest_npz_paths_complete") is True
        ),
        "production_ai_gpu_manifest_npz_files_exist": bool(
            summary.get("production_ai_gpu_manifest_npz_files_exist") is True
        ),
        "production_ai_gpu_manifest_npz_files_valid": bool(
            summary.get("production_ai_gpu_manifest_npz_files_valid") is True
        ),
        "production_ai_gpu_manifest_npz_schema_valid": bool(
            summary.get("production_ai_gpu_manifest_npz_schema_valid") is True
        ),
        "production_ai_gpu_manifest_npz_identity_valid": bool(
            summary.get("production_ai_gpu_manifest_npz_identity_valid") is True
        ),
        "production_ai_gpu_manifest_npz_path_present_count": int(
            summary.get("production_ai_gpu_manifest_npz_path_present_count") or 0
        ),
        "production_ai_gpu_manifest_npz_path_missing_count": int(
            summary.get("production_ai_gpu_manifest_npz_path_missing_count") or 0
        ),
        "production_ai_gpu_manifest_ok_row_missing_npz_path_count": int(
            summary.get("production_ai_gpu_manifest_ok_row_missing_npz_path_count") or 0
        ),
        "production_ai_gpu_manifest_operator_verified_missing_npz_path_count": int(
            summary.get("production_ai_gpu_manifest_operator_verified_missing_npz_path_count") or 0
        ),
        "production_ai_gpu_manifest_npz_file_existing_count": int(
            summary.get("production_ai_gpu_manifest_npz_file_existing_count") or 0
        ),
        "production_ai_gpu_manifest_npz_file_missing_count": int(
            summary.get("production_ai_gpu_manifest_npz_file_missing_count") or 0
        ),
        "production_ai_gpu_manifest_ok_row_missing_npz_file_count": int(
            summary.get("production_ai_gpu_manifest_ok_row_missing_npz_file_count") or 0
        ),
        "production_ai_gpu_manifest_operator_verified_missing_npz_file_count": int(
            summary.get("production_ai_gpu_manifest_operator_verified_missing_npz_file_count") or 0
        ),
        "production_ai_gpu_manifest_npz_file_valid_count": int(
            summary.get("production_ai_gpu_manifest_npz_file_valid_count") or 0
        ),
        "production_ai_gpu_manifest_npz_file_invalid_count": int(
            summary.get("production_ai_gpu_manifest_npz_file_invalid_count") or 0
        ),
        "production_ai_gpu_manifest_ok_row_invalid_npz_file_count": int(
            summary.get("production_ai_gpu_manifest_ok_row_invalid_npz_file_count") or 0
        ),
        "production_ai_gpu_manifest_operator_verified_invalid_npz_file_count": int(
            summary.get("production_ai_gpu_manifest_operator_verified_invalid_npz_file_count") or 0
        ),
        "production_ai_gpu_manifest_npz_schema_valid_count": int(
            summary.get("production_ai_gpu_manifest_npz_schema_valid_count") or 0
        ),
        "production_ai_gpu_manifest_npz_schema_invalid_count": int(
            summary.get("production_ai_gpu_manifest_npz_schema_invalid_count") or 0
        ),
        "production_ai_gpu_manifest_ok_row_invalid_npz_schema_count": int(
            summary.get("production_ai_gpu_manifest_ok_row_invalid_npz_schema_count") or 0
        ),
        "production_ai_gpu_manifest_operator_verified_invalid_npz_schema_count": int(
            summary.get("production_ai_gpu_manifest_operator_verified_invalid_npz_schema_count") or 0
        ),
        "production_ai_gpu_manifest_npz_identity_valid_count": int(
            summary.get("production_ai_gpu_manifest_npz_identity_valid_count") or 0
        ),
        "production_ai_gpu_manifest_npz_identity_invalid_count": int(
            summary.get("production_ai_gpu_manifest_npz_identity_invalid_count") or 0
        ),
        "production_ai_gpu_manifest_ok_row_invalid_npz_identity_count": int(
            summary.get("production_ai_gpu_manifest_ok_row_invalid_npz_identity_count") or 0
        ),
        "production_ai_gpu_manifest_operator_verified_invalid_npz_identity_count": int(
            summary.get("production_ai_gpu_manifest_operator_verified_invalid_npz_identity_count") or 0
        ),
        "production_ai_gpu_manifest_operator_verified": bool(
            summary.get("production_ai_gpu_manifest_operator_verified") is True
        ),
        "production_ai_gpu_operator_verified_true_count": int(
            summary.get("production_ai_gpu_operator_verified_true_count") or 0
        ),
        "production_ai_gpu_operator_verification_column_present": bool(
            summary.get("production_ai_gpu_operator_verification_column_present") is True
        ),
        "production_ai_gpu_identity_coverage_ready": bool(
            summary.get("production_ai_gpu_identity_coverage_ready") is True
        ),
        "production_ai_gpu_matched_queue_fingerprints": int(
            summary.get("production_ai_gpu_matched_queue_fingerprints") or 0
        ),
        "production_ai_gpu_queue_fingerprints": int(summary.get("production_ai_gpu_queue_fingerprints") or 0),
        "production_ai_force_derivation_input_ready": bool(
            summary.get("production_ai_force_derivation_input_ready") is True
        ),
        "production_ai_delta_force_derivation_validation_ready": bool(
            summary.get("production_ai_delta_force_derivation_validation_ready") is True
        ),
        "production_ai_missing_output_labels": list(summary.get("production_ai_missing_output_labels") or []),
        "production_ai_checkpoint_readiness_status": summary.get("production_ai_checkpoint_readiness_status", ""),
        "production_ai_checkpoint_ready": bool(summary.get("production_ai_checkpoint_ready") is True),
        "production_ai_checkpoint_output_head_gap_contract_ready": bool(
            summary.get("production_ai_checkpoint_output_head_gap_contract_ready") is True
        ),
        "production_ai_checkpoint_output_heads_complete": bool(
            summary.get("production_ai_checkpoint_output_heads_complete") is True
        ),
        "production_ai_checkpoint_output_head_required_field_count": int(
            summary.get("production_ai_checkpoint_output_head_required_field_count") or 0
        ),
        "production_ai_checkpoint_output_head_ready_field_count": int(
            summary.get("production_ai_checkpoint_output_head_ready_field_count") or 0
        ),
        "production_ai_checkpoint_output_head_blocked_field_count": int(
            summary.get("production_ai_checkpoint_output_head_blocked_field_count") or 0
        ),
        "production_ai_checkpoint_output_head_blocked_fields": list(
            summary.get("production_ai_checkpoint_output_head_blocked_fields") or []
        ),
        "production_ai_checkpoint_output_head_first_blocked_field": summary.get(
            "production_ai_checkpoint_output_head_first_blocked_field", ""
        ),
        "production_ai_checkpoint_output_head_first_blocked_field_blockers": list(
            summary.get("production_ai_checkpoint_output_head_first_blocked_field_blockers") or []
        ),
        "production_ai_checkpoint_output_head_gap_contract_artifact_path": summary.get(
            "production_ai_checkpoint_output_head_gap_contract_artifact_path", ""
        ),
        "production_ai_delta_force_closure_acceptance_artifact_path": summary.get(
            "production_ai_delta_force_closure_acceptance_artifact_path", ""
        ),
        "production_ai_delta_force_closure_acceptance_packet_ready": bool(
            summary.get("production_ai_delta_force_closure_acceptance_packet_ready") is True
        ),
        "production_ai_delta_force_closure_ready": bool(
            summary.get("production_ai_delta_force_closure_ready") is True
        ),
        "production_ai_delta_force_closure_first_blocked_output_field": summary.get(
            "production_ai_delta_force_closure_first_blocked_output_field", ""
        ),
        "production_ai_delta_force_closure_failed_stage_count": int(
            summary.get("production_ai_delta_force_closure_failed_stage_count") or 0
        ),
        "production_ai_delta_force_closure_failed_stage_ids": list(
            summary.get("production_ai_delta_force_closure_failed_stage_ids") or []
        ),
        "production_ai_delta_force_closure_next_stage_id": summary.get(
            "production_ai_delta_force_closure_next_stage_id", ""
        ),
        "production_ai_delta_force_closure_next_stage_artifact": summary.get(
            "production_ai_delta_force_closure_next_stage_artifact", ""
        ),
        "production_ai_delta_force_closure_next_stage_validation_command": summary.get(
            "production_ai_delta_force_closure_next_stage_validation_command", ""
        ),
        "production_ai_delta_force_closure_next_required_step": summary.get(
            "production_ai_delta_force_closure_next_required_step", ""
        ),
        "production_ai_checkpoint_failed_check_ids": list(
            summary.get("production_ai_checkpoint_failed_check_ids") or []
        ),
        "production_ai_checkpoint_first_failed_check_id": summary.get(
            "production_ai_checkpoint_first_failed_check_id", ""
        ),
        "production_ai_checkpoint_first_failed_source_artifact": summary.get(
            "production_ai_checkpoint_first_failed_source_artifact", ""
        ),
        "production_ai_checkpoint_first_failed_observed": summary.get(
            "production_ai_checkpoint_first_failed_observed", ""
        ),
        "production_ai_checkpoint_first_failed_required": summary.get(
            "production_ai_checkpoint_first_failed_required", ""
        ),
        "production_ai_checkpoint_first_failed_next_action": summary.get(
            "production_ai_checkpoint_first_failed_next_action", ""
        ),
        "production_ai_checkpoint_registry_promotion_required_gate_ids": list(
            summary.get("production_ai_checkpoint_registry_promotion_required_gate_ids") or []
        ),
        "production_ai_checkpoint_registry_promotion_missing_gate_ids": list(
            summary.get("production_ai_checkpoint_registry_promotion_missing_gate_ids") or []
        ),
        "production_ai_checkpoint_registry_promotion_missing_gate_count": int(
            summary.get("production_ai_checkpoint_registry_promotion_missing_gate_count") or 0
        ),
        "production_ai_checkpoint_registry_promotion_upstream_acceptance_ready": bool(
            summary.get("production_ai_checkpoint_registry_promotion_upstream_acceptance_ready") is True
        ),
        "production_ai_checkpoint_registry_promotion_currently_satisfied": bool(
            summary.get("production_ai_checkpoint_registry_promotion_currently_satisfied") is True
        ),
        "production_ai_checkpoint_actionable_blocker_stage_id": summary.get(
            "production_ai_checkpoint_actionable_blocker_stage_id", ""
        ),
        "production_ai_checkpoint_actionable_blocker_check_id": summary.get(
            "production_ai_checkpoint_actionable_blocker_check_id", ""
        ),
        "production_ai_checkpoint_actionable_blocker_artifact": summary.get(
            "production_ai_checkpoint_actionable_blocker_artifact", ""
        ),
        "production_ai_checkpoint_actionable_blocker_observed": summary.get(
            "production_ai_checkpoint_actionable_blocker_observed", ""
        ),
        "production_ai_checkpoint_actionable_blocker_required": summary.get(
            "production_ai_checkpoint_actionable_blocker_required", ""
        ),
        "production_ai_checkpoint_actionable_blocker_next_action": summary.get(
            "production_ai_checkpoint_actionable_blocker_next_action", ""
        ),
        "production_ai_checkpoint_actionable_blocker_validation_command": summary.get(
            "production_ai_checkpoint_actionable_blocker_validation_command", ""
        ),
        "production_ai_checkpoint_actionable_blocker_unlock_fields": list(
            summary.get("production_ai_checkpoint_actionable_blocker_unlock_fields") or []
        ),
        "production_ai_checkpoint_actionable_blocker_downstream_blocked_stage_count": int(
            summary.get("production_ai_checkpoint_actionable_blocker_downstream_blocked_stage_count") or 0
        ),
        "production_ai_checkpoint_next_after_actionable_blocker_stage_id": summary.get(
            "production_ai_checkpoint_next_after_actionable_blocker_stage_id", ""
        ),
        "production_ai_checkpoint_next_after_actionable_blocker_artifact": summary.get(
            "production_ai_checkpoint_next_after_actionable_blocker_artifact", ""
        ),
        "production_ai_checkpoint_next_after_actionable_blocker_validation_command": summary.get(
            "production_ai_checkpoint_next_after_actionable_blocker_validation_command", ""
        ),
        "production_ai_checkpoint_next_after_actionable_blocker_required_checks": list(
            summary.get("production_ai_checkpoint_next_after_actionable_blocker_required_checks") or []
        ),
        "production_ai_checkpoint_next_after_actionable_blocker_unlock_fields": list(
            summary.get("production_ai_checkpoint_next_after_actionable_blocker_unlock_fields") or []
        ),
        "production_ai_checkpoint_next_after_actionable_blocker_next_action": summary.get(
            "production_ai_checkpoint_next_after_actionable_blocker_next_action", ""
        ),
        "production_ai_checkpoint_actionable_blocker_blocks_registry_promotion": bool(
            summary.get("production_ai_checkpoint_actionable_blocker_blocks_registry_promotion") is True
        ),
        "production_ai_checkpoint_actionable_operator_completion_packet_ready": bool(
            summary.get("production_ai_checkpoint_actionable_operator_completion_packet_ready") is True
        ),
        "production_ai_checkpoint_actionable_operator_completion_packet_artifact": summary.get(
            "production_ai_checkpoint_actionable_operator_completion_packet_artifact", ""
        ),
        "production_ai_checkpoint_actionable_operator_completion_artifact_id": summary.get(
            "production_ai_checkpoint_actionable_operator_completion_artifact_id", ""
        ),
        "production_ai_checkpoint_actionable_operator_completion_artifact_path": summary.get(
            "production_ai_checkpoint_actionable_operator_completion_artifact_path", ""
        ),
        "production_ai_checkpoint_actionable_operator_completion_expected_queue_rows": int(
            summary.get("production_ai_checkpoint_actionable_operator_completion_expected_queue_rows") or 0
        ),
        "production_ai_checkpoint_actionable_operator_completion_required_fields_or_columns": list(
            summary.get("production_ai_checkpoint_actionable_operator_completion_required_fields_or_columns") or []
        ),
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_commands": list(
            summary.get("production_ai_checkpoint_actionable_operator_completion_diagnostic_commands") or []
        ),
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_command_count": int(
            summary.get("production_ai_checkpoint_actionable_operator_completion_diagnostic_command_count") or 0
        ),
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_required_fields": list(
            summary.get("production_ai_checkpoint_actionable_operator_completion_diagnostic_required_fields") or []
        ),
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_required_field_count": int(
            summary.get("production_ai_checkpoint_actionable_operator_completion_diagnostic_required_field_count")
            or 0
        ),
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_completion_rule": summary.get(
            "production_ai_checkpoint_actionable_operator_completion_diagnostic_completion_rule", ""
        ),
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_return_artifacts": list(
            summary.get("production_ai_checkpoint_actionable_operator_completion_diagnostic_return_artifacts") or []
        ),
        "production_ai_checkpoint_actionable_operator_completion_torch_visibility_probe_command": summary.get(
            "production_ai_checkpoint_actionable_operator_completion_torch_visibility_probe_command", ""
        ),
        "production_ai_checkpoint_actionable_operator_completion_failed_check_ids": list(
            summary.get("production_ai_checkpoint_actionable_operator_completion_failed_check_ids") or []
        ),
        "production_ai_checkpoint_actionable_operator_completion_template_payload_json": summary.get(
            "production_ai_checkpoint_actionable_operator_completion_template_payload_json", ""
        ),
        "production_ai_checkpoint_actionable_operator_completion_validation_command": summary.get(
            "production_ai_checkpoint_actionable_operator_completion_validation_command", ""
        ),
        "production_ai_checkpoint_actionable_operator_completion_full_regeneration_command": summary.get(
            "production_ai_checkpoint_actionable_operator_completion_full_regeneration_command", ""
        ),
        "production_ai_checkpoint_actionable_operator_completion_completion_rule": summary.get(
            "production_ai_checkpoint_actionable_operator_completion_completion_rule", ""
        ),
        "production_ai_checkpoint_actionable_operator_completion_backend_provenance_completion_rule": summary.get(
            "production_ai_checkpoint_actionable_operator_completion_backend_provenance_completion_rule", ""
        ),
        "production_ai_checkpoint_actionable_operator_completion_next_action": summary.get(
            "production_ai_checkpoint_actionable_operator_completion_next_action", ""
        ),
        "production_ai_checkpoint_actionable_operator_completion_packet": dict(
            summary.get("production_ai_checkpoint_actionable_operator_completion_packet") or {}
        ),
        "production_ai_checkpoint_worker_runtime_receipt_contract_ready": bool(
            summary.get("production_ai_checkpoint_worker_runtime_receipt_contract_ready") is True
        ),
        "production_ai_checkpoint_worker_runtime_receipt_contract": dict(
            summary.get("production_ai_checkpoint_worker_runtime_receipt_contract") or {}
        ),
        "production_ai_checkpoint_worker_runtime_receipt_required_fields_or_columns": list(
            summary.get("production_ai_checkpoint_worker_runtime_receipt_required_fields_or_columns") or []
        ),
        "production_ai_checkpoint_worker_runtime_receipt_required_field_count": int(
            summary.get("production_ai_checkpoint_worker_runtime_receipt_required_field_count") or 0
        ),
        "production_ai_checkpoint_worker_runtime_receipt_completion_rule": summary.get(
            "production_ai_checkpoint_worker_runtime_receipt_completion_rule", ""
        ),
        "production_ai_checkpoint_worker_runtime_receipt_post_environment_next_stage_id": summary.get(
            "production_ai_checkpoint_worker_runtime_receipt_post_environment_next_stage_id", ""
        ),
        "production_ai_checkpoint_worker_runtime_receipt_post_environment_next_artifact": summary.get(
            "production_ai_checkpoint_worker_runtime_receipt_post_environment_next_artifact", ""
        ),
        "production_ai_checkpoint_worker_runtime_receipt_post_environment_validation_command": summary.get(
            "production_ai_checkpoint_worker_runtime_receipt_post_environment_validation_command", ""
        ),
        "production_ai_checkpoint_worker_runtime_receipt_full_regeneration_command": summary.get(
            "production_ai_checkpoint_worker_runtime_receipt_full_regeneration_command", ""
        ),
        "production_ai_checkpoint_worker_runtime_receipt_guardrails": list(
            summary.get("production_ai_checkpoint_worker_runtime_receipt_guardrails") or []
        ),
        "production_ai_checkpoint_acceptance_matrix_ready": bool(
            summary.get("production_ai_checkpoint_acceptance_matrix_ready") is True
        ),
        "production_ai_checkpoint_acceptance_stage_count": int(
            summary.get("production_ai_checkpoint_acceptance_stage_count") or 0
        ),
        "production_ai_checkpoint_acceptance_ready_stage_count": int(
            summary.get("production_ai_checkpoint_acceptance_ready_stage_count") or 0
        ),
        "production_ai_checkpoint_acceptance_blocked_stage_count": int(
            summary.get("production_ai_checkpoint_acceptance_blocked_stage_count") or 0
        ),
        "production_ai_checkpoint_acceptance_stage_ids": list(
            summary.get("production_ai_checkpoint_acceptance_stage_ids") or []
        ),
        "production_ai_checkpoint_acceptance_ready_stage_ids": list(
            summary.get("production_ai_checkpoint_acceptance_ready_stage_ids") or []
        ),
        "production_ai_checkpoint_acceptance_blocked_stage_ids": list(
            summary.get("production_ai_checkpoint_acceptance_blocked_stage_ids") or []
        ),
        "production_ai_checkpoint_acceptance_matrix": list(
            summary.get("production_ai_checkpoint_acceptance_matrix") or []
        ),
        "production_ai_checkpoint_acceptance_current_blocked_stage_matrix": list(
            summary.get("production_ai_checkpoint_acceptance_current_blocked_stage_matrix") or []
        ),
        "production_ai_checkpoint_acceptance_release_blocker_stage_count": int(
            summary.get("production_ai_checkpoint_acceptance_release_blocker_stage_count") or 0
        ),
        "production_ai_checkpoint_acceptance_release_blocker_stage_ids": list(
            summary.get("production_ai_checkpoint_acceptance_release_blocker_stage_ids") or []
        ),
        "production_ai_checkpoint_acceptance_next_stage_id": summary.get(
            "production_ai_checkpoint_acceptance_next_stage_id", ""
        ),
        "production_ai_checkpoint_acceptance_next_stage_artifact": summary.get(
            "production_ai_checkpoint_acceptance_next_stage_artifact", ""
        ),
        "production_ai_checkpoint_acceptance_next_stage_validation_command": summary.get(
            "production_ai_checkpoint_acceptance_next_stage_validation_command", ""
        ),
        "production_ai_checkpoint_acceptance_next_stage_release_effect": summary.get(
            "production_ai_checkpoint_acceptance_next_stage_release_effect", ""
        ),
        "production_ai_checkpoint_acceptance_next_stage_unlock_fields": list(
            summary.get("production_ai_checkpoint_acceptance_next_stage_unlock_fields") or []
        ),
        "production_ai_checkpoint_acceptance_next_stage_required_checks": list(
            summary.get("production_ai_checkpoint_acceptance_next_stage_required_checks") or []
        ),
        "production_ai_checkpoint_acceptance_next_stage_next_action": summary.get(
            "production_ai_checkpoint_acceptance_next_stage_next_action", ""
        ),
        "production_ai_gpu_return_intake_status": summary.get("production_ai_gpu_return_intake_status", ""),
        "production_ai_gpu_return_intake_artifact_path": summary.get(
            "production_ai_gpu_return_intake_artifact_path", ""
        ),
        "production_ai_gpu_return_intake_ready": bool(
            summary.get("production_ai_gpu_return_intake_ready") is True
        ),
        "production_ai_gpu_return_artifacts_ready": bool(
            summary.get("production_ai_gpu_return_artifacts_ready") is True
        ),
        "production_ai_gpu_return_check_count": int(summary.get("production_ai_gpu_return_check_count") or 0),
        "production_ai_gpu_return_fail_check_count": int(
            summary.get("production_ai_gpu_return_fail_check_count") or 0
        ),
        "production_ai_gpu_return_failed_check_ids": list(
            summary.get("production_ai_gpu_return_failed_check_ids") or []
        ),
        "production_ai_gpu_return_blocker_matrix": list(
            summary.get("production_ai_gpu_return_blocker_matrix") or []
        ),
        "production_ai_gpu_return_blocker_matrix_count": int(
            summary.get("production_ai_gpu_return_blocker_matrix_count") or 0
        ),
        "production_ai_gpu_return_first_failed_check_id": summary.get(
            "production_ai_gpu_return_first_failed_check_id", ""
        ),
        "production_ai_gpu_return_first_failed_source_artifact": summary.get(
            "production_ai_gpu_return_first_failed_source_artifact", ""
        ),
        "production_ai_gpu_return_first_failed_observed": summary.get(
            "production_ai_gpu_return_first_failed_observed", ""
        ),
        "production_ai_gpu_return_first_failed_required": summary.get(
            "production_ai_gpu_return_first_failed_required", ""
        ),
        "production_ai_gpu_return_first_failed_next_action": summary.get(
            "production_ai_gpu_return_first_failed_next_action", ""
        ),
        "production_ai_gpu_return_operator_return_artifact_completion_matrix": list(
            summary.get("production_ai_gpu_return_operator_return_artifact_completion_matrix") or []
        ),
        "production_ai_gpu_return_operator_return_artifact_completion_matrix_count": int(
            summary.get("production_ai_gpu_return_operator_return_artifact_completion_matrix_count") or 0
        ),
        "production_ai_gpu_return_operator_return_artifact_completion_blocker_matrix": list(
            summary.get("production_ai_gpu_return_operator_return_artifact_completion_blocker_matrix") or []
        ),
        "production_ai_gpu_return_operator_return_artifact_completion_blocker_count": int(
            summary.get("production_ai_gpu_return_operator_return_artifact_completion_blocker_count") or 0
        ),
        "production_ai_gpu_return_operator_return_next_artifact_completion_packet_ready": bool(
            summary.get("production_ai_gpu_return_operator_return_next_artifact_completion_packet_ready") is True
        ),
        "production_ai_gpu_return_operator_return_next_artifact_completion_packet": dict(
            summary.get("production_ai_gpu_return_operator_return_next_artifact_completion_packet") or {}
        ),
        "production_ai_gpu_return_operator_return_next_artifact_id": summary.get(
            "production_ai_gpu_return_operator_return_next_artifact_id", ""
        ),
        "production_ai_gpu_return_operator_return_next_artifact_path": summary.get(
            "production_ai_gpu_return_operator_return_next_artifact_path", ""
        ),
        "production_ai_gpu_return_operator_return_next_artifact_failed_check_ids": list(
            summary.get("production_ai_gpu_return_operator_return_next_artifact_failed_check_ids") or []
        ),
        "production_ai_gpu_return_handoff_binding_ready": bool(
            summary.get("production_ai_gpu_return_handoff_binding_ready") is True
        ),
        "production_ai_gpu_return_handoff_queue_csv": summary.get(
            "production_ai_gpu_return_handoff_queue_csv", ""
        ),
        "production_ai_gpu_return_handoff_queue_csv_sha256": summary.get(
            "production_ai_gpu_return_handoff_queue_csv_sha256", ""
        ),
        "production_ai_gpu_return_handoff_full_regeneration_command": summary.get(
            "production_ai_gpu_return_handoff_full_regeneration_command", ""
        ),
        "production_ai_gpu_return_handoff_return_manifest_schema_contract_ready": bool(
            summary.get("production_ai_gpu_return_handoff_return_manifest_schema_contract_ready") is True
        ),
        "production_ai_gpu_return_handoff_return_manifest_required_identity_rule": summary.get(
            "production_ai_gpu_return_handoff_return_manifest_required_identity_rule", ""
        ),
        "production_ai_gpu_return_handoff_return_manifest_fingerprint_columns": list(
            summary.get("production_ai_gpu_return_handoff_return_manifest_fingerprint_columns") or []
        ),
        "production_ai_gpu_return_handoff_return_manifest_queue_id_columns": list(
            summary.get("production_ai_gpu_return_handoff_return_manifest_queue_id_columns") or []
        ),
        "production_ai_gpu_return_handoff_return_manifest_npz_columns": list(
            summary.get("production_ai_gpu_return_handoff_return_manifest_npz_columns") or []
        ),
        "production_ai_gpu_return_operator_acceptance_matrix_ready": bool(
            summary.get("production_ai_gpu_return_operator_acceptance_matrix_ready") is True
        ),
        "production_ai_gpu_return_operator_acceptance_matrix": list(
            summary.get("production_ai_gpu_return_operator_acceptance_matrix") or []
        ),
        "production_ai_gpu_return_operator_acceptance_current_blocked_stage_matrix": list(
            summary.get("production_ai_gpu_return_operator_acceptance_current_blocked_stage_matrix") or []
        ),
        "production_ai_gpu_return_operator_acceptance_stage_check_matrix": list(
            summary.get("production_ai_gpu_return_operator_acceptance_stage_check_matrix") or []
        ),
        "production_ai_gpu_return_operator_acceptance_stage_check_matrix_count": int(
            summary.get("production_ai_gpu_return_operator_acceptance_stage_check_matrix_count") or 0
        ),
        "production_ai_gpu_return_operator_acceptance_current_blocked_stage_check_matrix": list(
            summary.get("production_ai_gpu_return_operator_acceptance_current_blocked_stage_check_matrix") or []
        ),
        "production_ai_gpu_return_operator_acceptance_current_blocked_stage_check_matrix_count": int(
            summary.get("production_ai_gpu_return_operator_acceptance_current_blocked_stage_check_matrix_count")
            or 0
        ),
        "production_ai_gpu_return_operator_acceptance_stage_count": int(
            summary.get("production_ai_gpu_return_operator_acceptance_stage_count") or 0
        ),
        "production_ai_gpu_return_operator_acceptance_ready_stage_count": int(
            summary.get("production_ai_gpu_return_operator_acceptance_ready_stage_count") or 0
        ),
        "production_ai_gpu_return_operator_acceptance_blocked_stage_count": int(
            summary.get("production_ai_gpu_return_operator_acceptance_blocked_stage_count") or 0
        ),
        "production_ai_gpu_return_operator_acceptance_stage_ids": list(
            summary.get("production_ai_gpu_return_operator_acceptance_stage_ids") or []
        ),
        "production_ai_gpu_return_operator_acceptance_ready_stage_ids": list(
            summary.get("production_ai_gpu_return_operator_acceptance_ready_stage_ids") or []
        ),
        "production_ai_gpu_return_operator_acceptance_blocked_stage_ids": list(
            summary.get("production_ai_gpu_return_operator_acceptance_blocked_stage_ids") or []
        ),
        "production_ai_gpu_return_operator_acceptance_next_stage_id": summary.get(
            "production_ai_gpu_return_operator_acceptance_next_stage_id", ""
        ),
        "production_ai_gpu_return_operator_acceptance_next_stage_artifact": summary.get(
            "production_ai_gpu_return_operator_acceptance_next_stage_artifact", ""
        ),
        "production_ai_gpu_return_operator_acceptance_next_stage_validation_command": summary.get(
            "production_ai_gpu_return_operator_acceptance_next_stage_validation_command", ""
        ),
        "production_ai_gpu_return_operator_acceptance_next_stage_release_effect": summary.get(
            "production_ai_gpu_return_operator_acceptance_next_stage_release_effect", ""
        ),
        "production_ai_gpu_return_operator_acceptance_next_stage_unlock_fields": list(
            summary.get("production_ai_gpu_return_operator_acceptance_next_stage_unlock_fields") or []
        ),
        "production_ai_gpu_return_operator_acceptance_next_stage_required_checks": list(
            summary.get("production_ai_gpu_return_operator_acceptance_next_stage_required_checks") or []
        ),
        "production_ai_gpu_return_operator_acceptance_next_stage_next_action": summary.get(
            "production_ai_gpu_return_operator_acceptance_next_stage_next_action", ""
        ),
        "production_ai_gpu_return_expected_queue_rows": int(
            summary.get("production_ai_gpu_return_expected_queue_rows") or 0
        ),
        "production_ai_gpu_return_manifest_template_csv": summary.get(
            "production_ai_gpu_return_manifest_template_csv", ""
        ),
        "production_ai_gpu_return_summary_template_csv": summary.get(
            "production_ai_gpu_return_summary_template_csv", ""
        ),
        "production_ai_gpu_return_summary_template_payload_json": summary.get(
            "production_ai_gpu_return_summary_template_payload_json", ""
        ),
        "production_ai_gpu_return_summary_template_required_fields": list(
            summary.get("production_ai_gpu_return_summary_template_required_fields") or []
        ),
        "production_ai_gpu_return_summary_template_completion_rule": summary.get(
            "production_ai_gpu_return_summary_template_completion_rule", ""
        ),
        "production_ai_gpu_return_summary_template_backend_provenance_contract_ready": bool(
            summary.get("production_ai_gpu_return_summary_template_backend_provenance_contract_ready") is True
        ),
        "production_ai_gpu_return_summary_template_required_backend_provenance_fields": list(
            summary.get("production_ai_gpu_return_summary_template_required_backend_provenance_fields") or []
        ),
        "production_ai_gpu_return_summary_template_backend_provenance_completion_rule": summary.get(
            "production_ai_gpu_return_summary_template_backend_provenance_completion_rule", ""
        ),
        "production_ai_gpu_return_manifest_template_row_count": int(
            summary.get("production_ai_gpu_return_manifest_template_row_count") or 0
        ),
        "production_ai_gpu_return_manifest_operator_verification_placeholder_count": int(
            summary.get("production_ai_gpu_return_manifest_operator_verification_placeholder_count") or 0
        ),
        "production_ai_gpu_return_actual_summary_return_path": summary.get(
            "production_ai_gpu_return_actual_summary_return_path", ""
        ),
        "production_ai_gpu_return_actual_manifest_return_path": summary.get(
            "production_ai_gpu_return_actual_manifest_return_path", ""
        ),
        "production_ai_gpu_summary_manifest_bound": bool(
            summary.get("production_ai_gpu_summary_manifest_bound") is True
        ),
        "production_ai_gpu_summary_manifest_csv": summary.get(
            "production_ai_gpu_summary_manifest_csv", ""
        ),
        "production_ai_gpu_summary_out_manifest_csv_present": bool(
            summary.get("production_ai_gpu_summary_out_manifest_csv_present") is True
        ),
        "production_ai_gpu_summary_out_manifest_csv": summary.get(
            "production_ai_gpu_summary_out_manifest_csv", ""
        ),
        "production_ai_gpu_summary_out_manifest_csv_bound": bool(
            summary.get("production_ai_gpu_summary_out_manifest_csv_bound") is True
        ),
        "production_ai_gpu_summary_out_summary_json_bound": bool(
            summary.get("production_ai_gpu_summary_out_summary_json_bound") is True
        ),
        "production_ai_gpu_summary_out_summary_json": summary.get(
            "production_ai_gpu_summary_out_summary_json", ""
        ),
        "production_ai_gpu_summary_manifest_row_counts_consistent": bool(
            summary.get("production_ai_gpu_summary_manifest_row_counts_consistent") is True
        ),
        "production_ai_gpu_backend_provenance_ready": bool(
            summary.get("production_ai_gpu_backend_provenance_ready") is True
        ),
        "production_ai_gpu_backend_rows": int(summary.get("production_ai_gpu_backend_rows") or 0),
        "production_ai_gpu_backend_non_production_rows": int(
            summary.get("production_ai_gpu_backend_non_production_rows") or 0
        ),
        "production_ai_gpu_backend_prod_mode": bool(
            summary.get("production_ai_gpu_backend_prod_mode") is True
        ),
        "production_ai_gpu_backend_require_rust_hip": bool(
            summary.get("production_ai_gpu_backend_require_rust_hip") is True
        ),
        "production_ai_gpu_worker_rocm_manifest_artifact": summary.get(
            "production_ai_gpu_worker_rocm_manifest_artifact", ""
        ),
        "production_ai_gpu_worker_rocm_manifest_ready": bool(
            summary.get("production_ai_gpu_worker_rocm_manifest_ready") is True
        ),
        "production_ai_gpu_worker_rocm_manifest_generation_command": summary.get(
            "production_ai_gpu_worker_rocm_manifest_generation_command", ""
        ),
        "production_ai_gpu_worker_rocm_manifest_completion_rule": summary.get(
            "production_ai_gpu_worker_rocm_manifest_completion_rule", ""
        ),
        "production_ai_gpu_worker_rocm_stack_detected": bool(
            summary.get("production_ai_gpu_worker_rocm_stack_detected") is True
        ),
        "production_ai_gpu_worker_rocm_torch_ready": bool(
            summary.get("production_ai_gpu_worker_rocm_torch_ready") is True
        ),
        "production_ai_gpu_worker_rocm_amd_gpu_detected": bool(
            summary.get("production_ai_gpu_worker_rocm_amd_gpu_detected") is True
        ),
        "production_ai_gpu_worker_rocm_visible_device_count": int(
            summary.get("production_ai_gpu_worker_rocm_visible_device_count") or 0
        ),
        "production_ai_gpu_worker_rocm_device_names": list(
            summary.get("production_ai_gpu_worker_rocm_device_names") or []
        ),
        "production_ai_gpu_worker_rocm_next_required_step": summary.get(
            "production_ai_gpu_worker_rocm_next_required_step", ""
        ),
        "production_ai_checkpoint_gpu_backend_provenance_ready": bool(
            summary.get("production_ai_checkpoint_gpu_backend_provenance_ready") is True
        ),
        "production_ai_checkpoint_gpu_backend_rows": int(
            summary.get("production_ai_checkpoint_gpu_backend_rows") or 0
        ),
        "production_ai_checkpoint_gpu_backend_non_production_rows": int(
            summary.get("production_ai_checkpoint_gpu_backend_non_production_rows") or 0
        ),
        "production_ai_gpu_return_post_return_validation_command": summary.get(
            "production_ai_gpu_return_post_return_validation_command", ""
        ),
        "production_ai_gpu_return_next_required_step": summary.get(
            "production_ai_gpu_return_next_required_step", ""
        ),
        "production_ai_promotion_workbench_status": summary.get("production_ai_promotion_workbench_status", ""),
        "production_ai_promotion_workbench_ready": bool(
            summary.get("production_ai_promotion_workbench_ready") is True
        ),
        "production_ai_promotion_ready": bool(summary.get("production_ai_promotion_ready") is True),
        "production_ai_promotion_first_blocked_stage_id": summary.get(
            "production_ai_promotion_first_blocked_stage_id", ""
        ),
        "production_ai_promotion_first_blocked_stage_artifact": summary.get(
            "production_ai_promotion_first_blocked_stage_artifact", ""
        ),
        "production_ai_promotion_first_blocked_stage_ready_key": summary.get(
            "production_ai_promotion_first_blocked_stage_ready_key", ""
        ),
        "production_ai_promotion_blocked_stage_count": int(
            summary.get("production_ai_promotion_blocked_stage_count") or 0
        ),
        "production_ai_promotion_blocked_stage_ids": list(
            summary.get("production_ai_promotion_blocked_stage_ids") or []
        ),
        "production_ai_force_gpu_worker_handoff_ready": bool(
            summary.get("production_ai_force_gpu_worker_handoff_ready") is True
        ),
        "production_ai_force_gpu_worker_operator_action_required": bool(
            summary.get("production_ai_force_gpu_worker_operator_action_required") is True
        ),
        "production_ai_force_gpu_operator_transfer_manifest_ready": bool(
            summary.get("production_ai_force_gpu_operator_transfer_manifest_ready") is True
        ),
        "production_ai_force_gpu_operator_transfer_outbound_artifact_count": int(
            summary.get("production_ai_force_gpu_operator_transfer_outbound_artifact_count") or 0
        ),
        "production_ai_force_gpu_operator_transfer_outbound_artifacts": list(
            summary.get("production_ai_force_gpu_operator_transfer_outbound_artifacts") or []
        ),
        "production_ai_force_gpu_operator_transfer_inbound_artifact_count": int(
            summary.get("production_ai_force_gpu_operator_transfer_inbound_artifact_count") or 0
        ),
        "production_ai_force_gpu_operator_transfer_inbound_artifacts": list(
            summary.get("production_ai_force_gpu_operator_transfer_inbound_artifacts") or []
        ),
        "production_ai_force_gpu_operator_transfer_first_return_artifact": summary.get(
            "production_ai_force_gpu_operator_transfer_first_return_artifact", ""
        ),
        "production_ai_force_gpu_operator_transfer_return_manifest_artifact": summary.get(
            "production_ai_force_gpu_operator_transfer_return_manifest_artifact", ""
        ),
        "production_ai_force_gpu_operator_transfer_acceptance_artifact": summary.get(
            "production_ai_force_gpu_operator_transfer_acceptance_artifact", ""
        ),
        "production_ai_force_gpu_operator_transfer_acceptance_ready_key": summary.get(
            "production_ai_force_gpu_operator_transfer_acceptance_ready_key", ""
        ),
        "production_ai_force_gpu_operator_transfer_post_return_validation_command": summary.get(
            "production_ai_force_gpu_operator_transfer_post_return_validation_command", ""
        ),
        "production_ai_force_gpu_full_regeneration_command": summary.get(
            "production_ai_force_gpu_full_regeneration_command", ""
        ),
        "production_ai_force_gpu_post_return_validation_command": summary.get(
            "production_ai_force_gpu_post_return_validation_command", ""
        ),
        "production_ai_force_gpu_post_run_validation_commands": list(
            summary.get("production_ai_force_gpu_post_run_validation_commands") or []
        ),
        "production_ai_force_gpu_post_return_required_production_output_fields": list(
            summary.get("production_ai_force_gpu_post_return_required_production_output_fields") or []
        ),
        "production_ai_force_gpu_post_return_gpu_unlock_artifacts": list(
            summary.get("production_ai_force_gpu_post_return_gpu_unlock_artifacts") or []
        ),
        "production_ai_force_gpu_post_return_unlock_output_fields": list(
            summary.get("production_ai_force_gpu_post_return_unlock_output_fields") or []
        ),
        "production_ai_force_gpu_post_return_min_expected_label_rows": int(
            summary.get("production_ai_force_gpu_post_return_min_expected_label_rows") or 0
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_stage_count": int(
            summary.get("production_ai_force_gpu_post_return_promotion_ladder_stage_count") or 0
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_contract_ready": bool(
            summary.get("production_ai_force_gpu_post_return_promotion_ladder_contract_ready") is True
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_currently_satisfied": bool(
            summary.get("production_ai_force_gpu_post_return_promotion_ladder_currently_satisfied") is True
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_current_blocked_stage_count": int(
            summary.get("production_ai_force_gpu_post_return_promotion_ladder_current_blocked_stage_count") or 0
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_current_blocked_stage_ids": list(
            summary.get("production_ai_force_gpu_post_return_promotion_ladder_current_blocked_stage_ids") or []
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_current_next_stage_id": summary.get(
            "production_ai_force_gpu_post_return_promotion_ladder_current_next_stage_id", ""
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_current_next_stage_artifact": summary.get(
            "production_ai_force_gpu_post_return_promotion_ladder_current_next_stage_artifact", ""
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_current_next_stage_validation_command": summary.get(
            "production_ai_force_gpu_post_return_promotion_ladder_current_next_stage_validation_command", ""
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_stage_ids": list(
            summary.get("production_ai_force_gpu_post_return_promotion_ladder_stage_ids") or []
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_missing_ready_keys": list(
            summary.get("production_ai_force_gpu_post_return_promotion_ladder_missing_ready_keys") or []
        ),
        "production_ai_force_gpu_receipt_manifest_identity_row_count": int(
            summary.get("production_ai_force_gpu_receipt_manifest_identity_row_count") or 0
        ),
        "production_ai_force_gpu_receipt_matched_queue_id_count": int(
            summary.get("production_ai_force_gpu_receipt_matched_queue_id_count") or 0
        ),
        "production_ai_force_gpu_receipt_matched_expected_npz_count": int(
            summary.get("production_ai_force_gpu_receipt_matched_expected_npz_count") or 0
        ),
        "production_ai_force_gpu_receipt_matched_queue_fingerprint_count": int(
            summary.get("production_ai_force_gpu_receipt_matched_queue_fingerprint_count") or 0
        ),
        "product_scope_closure_acceptance_artifact_path": summary.get(
            "product_scope_closure_acceptance_artifact_path", ""
        ),
        "product_scope_closure_acceptance_packet_ready": bool(
            summary.get("product_scope_closure_acceptance_packet_ready") is True
        ),
        "product_scope_closure_acceptance_ready": bool(
            summary.get("product_scope_closure_acceptance_ready") is True
        ),
        "product_scope_closure_acceptance_stage_count": int(
            summary.get("product_scope_closure_acceptance_stage_count") or 0
        ),
        "product_scope_closure_acceptance_blocked_stage_count": int(
            summary.get("product_scope_closure_acceptance_blocked_stage_count") or 0
        ),
        "product_scope_closure_acceptance_blocked_stage_ids": list(
            summary.get("product_scope_closure_acceptance_blocked_stage_ids") or []
        ),
        "product_scope_closure_acceptance_next_stage_id": summary.get(
            "product_scope_closure_acceptance_next_stage_id", ""
        ),
        "product_scope_closure_acceptance_first_blocked_evidence_row_id": summary.get(
            "product_scope_closure_acceptance_first_blocked_evidence_row_id", ""
        ),
        "product_scope_closure_acceptance_first_blocked_target_id": summary.get(
            "product_scope_closure_acceptance_first_blocked_target_id", ""
        ),
        "product_scope_closure_acceptance_first_blocked_required_missing_fields": summary.get(
            "product_scope_closure_acceptance_first_blocked_required_missing_fields", ""
        ),
        "product_scope_closure_acceptance_transporter_unresolved_slot_count": int(
            summary.get("product_scope_closure_acceptance_transporter_unresolved_slot_count") or 0
        ),
        "product_scope_closure_acceptance_pxr_direct_or_claim_safe_quantitative_ready_count": int(
            summary.get("product_scope_closure_acceptance_pxr_direct_or_claim_safe_quantitative_ready_count") or 0
        ),
        "product_scope_closure_acceptance_general_platform_claim_allowed": bool(
            summary.get("product_scope_closure_acceptance_general_platform_claim_allowed") is True
        ),
        "product_scope_closure_acceptance_next_required_step": summary.get(
            "product_scope_closure_acceptance_next_required_step", ""
        ),
        "product_ai_scope_backlog_detail": summary.get("product_ai_scope_backlog_detail", ""),
        "product_scope_closure_blocker_class_counts": (
            summary.get("product_scope_closure_blocker_class_counts")
            if isinstance(summary.get("product_scope_closure_blocker_class_counts"), dict)
            else {}
        ),
        "product_scope_first_scientific_blocker": summary.get("product_scope_first_scientific_blocker", ""),
        "product_scope_manual_review_subcheck_count": int(
            summary.get("product_scope_manual_review_subcheck_count") or 0
        ),
        "product_scope_transporter_manual_review_subcheck_count": int(
            summary.get("product_scope_transporter_manual_review_subcheck_count") or 0
        ),
        "product_scope_transporter_identity_scaffold_confirmation_required_count": int(
            summary.get("product_scope_transporter_identity_scaffold_confirmation_required_count") or 0
        ),
        "product_scope_transporter_direct_binding_or_kcal_confirmation_required_count": int(
            summary.get("product_scope_transporter_direct_binding_or_kcal_confirmation_required_count") or 0
        ),
        "product_scope_transporter_negative_quantitative_confirmation_required_count": int(
            summary.get("product_scope_transporter_negative_quantitative_confirmation_required_count") or 0
        ),
        "product_scope_transporter_direct_binding_missing_count": int(
            summary.get("product_scope_transporter_direct_binding_missing_count") or 0
        ),
        "product_scope_transporter_negative_quantitative_missing_count": int(
            summary.get("product_scope_transporter_negative_quantitative_missing_count") or 0
        ),
        "product_scope_pxr_reconciled_blocked_row_count": int(
            summary.get("product_scope_pxr_reconciled_blocked_row_count") or 0
        ),
        "product_scope_pxr_conflict_resolution_count": int(
            summary.get("product_scope_pxr_conflict_resolution_count") or 0
        ),
        "product_scope_pxr_quantitative_missing_count": int(
            summary.get("product_scope_pxr_quantitative_missing_count") or 0
        ),
        "product_scope_breadth_contract_status": summary.get("product_scope_breadth_contract_status", ""),
        "product_scope_breadth_contract_artifact_path": summary.get(
            "product_scope_breadth_contract_artifact_path", ""
        ),
        "product_scope_operator_transfer_manifest_ready": bool(
            summary.get("product_scope_operator_transfer_manifest_ready") is True
        ),
        "product_scope_operator_transfer_outbound_artifact_count": int(
            summary.get("product_scope_operator_transfer_outbound_artifact_count") or 0
        ),
        "product_scope_operator_transfer_outbound_artifacts": list(
            summary.get("product_scope_operator_transfer_outbound_artifacts") or []
        ),
        "product_scope_operator_transfer_inbound_artifact_count": int(
            summary.get("product_scope_operator_transfer_inbound_artifact_count") or 0
        ),
        "product_scope_operator_transfer_inbound_artifacts": list(
            summary.get("product_scope_operator_transfer_inbound_artifacts") or []
        ),
        "product_scope_operator_transfer_first_return_artifact": summary.get(
            "product_scope_operator_transfer_first_return_artifact", ""
        ),
        "product_scope_operator_transfer_acceptance_artifact": summary.get(
            "product_scope_operator_transfer_acceptance_artifact", ""
        ),
        "product_scope_operator_transfer_acceptance_ready_key": summary.get(
            "product_scope_operator_transfer_acceptance_ready_key", ""
        ),
        "product_scope_operator_transfer_next_acceptance_stage": summary.get(
            "product_scope_operator_transfer_next_acceptance_stage", ""
        ),
        "product_scope_operator_transfer_post_return_validation_command": summary.get(
            "product_scope_operator_transfer_post_return_validation_command", ""
        ),
        "product_scope_acceptance_matrix_ready": bool(
            summary.get("product_scope_acceptance_matrix_ready") is True
        ),
        "product_scope_claim_expansion_contract_ready": bool(
            summary.get("product_scope_claim_expansion_contract_ready") is True
        ),
        "product_scope_claim_expansion_currently_satisfied": bool(
            summary.get("product_scope_claim_expansion_currently_satisfied") is True
        ),
        "product_scope_claim_expansion_current_blocked_stage_count": int(
            summary.get("product_scope_claim_expansion_current_blocked_stage_count") or 0
        ),
        "product_scope_claim_expansion_current_blocked_stage_ids": list(
            summary.get("product_scope_claim_expansion_current_blocked_stage_ids") or []
        ),
        "product_scope_claim_expansion_current_next_stage_id": summary.get(
            "product_scope_claim_expansion_current_next_stage_id", ""
        ),
        "product_scope_claim_expansion_current_next_stage_artifact": summary.get(
            "product_scope_claim_expansion_current_next_stage_artifact", ""
        ),
        "product_scope_claim_expansion_current_next_stage_validation_command": summary.get(
            "product_scope_claim_expansion_current_next_stage_validation_command", ""
        ),
        "product_scope_claim_expansion_current_next_stage_unlock_claim_scopes": list(
            summary.get("product_scope_claim_expansion_current_next_stage_unlock_claim_scopes") or []
        ),
        "product_scope_acceptance_stage_count": int(summary.get("product_scope_acceptance_stage_count") or 0),
        "product_scope_acceptance_ready_stage_count": int(
            summary.get("product_scope_acceptance_ready_stage_count") or 0
        ),
        "product_scope_acceptance_blocked_stage_count": int(
            summary.get("product_scope_acceptance_blocked_stage_count") or 0
        ),
        "product_scope_acceptance_stage_ids": list(summary.get("product_scope_acceptance_stage_ids") or []),
        "product_scope_acceptance_ready_stage_ids": list(
            summary.get("product_scope_acceptance_ready_stage_ids") or []
        ),
        "product_scope_acceptance_blocked_stage_ids": list(
            summary.get("product_scope_acceptance_blocked_stage_ids") or []
        ),
        "product_scope_acceptance_matrix": list(summary.get("product_scope_acceptance_matrix") or []),
        "product_scope_acceptance_current_blocked_stage_matrix": list(
            summary.get("product_scope_acceptance_current_blocked_stage_matrix") or []
        ),
        "product_scope_acceptance_stage_evidence_matrix": list(
            summary.get("product_scope_acceptance_stage_evidence_matrix") or []
        ),
        "product_scope_acceptance_stage_evidence_matrix_count": int(
            summary.get("product_scope_acceptance_stage_evidence_matrix_count") or 0
        ),
        "product_scope_acceptance_current_blocked_stage_evidence_matrix": list(
            summary.get("product_scope_acceptance_current_blocked_stage_evidence_matrix") or []
        ),
        "product_scope_acceptance_current_blocked_stage_evidence_matrix_count": int(
            summary.get("product_scope_acceptance_current_blocked_stage_evidence_matrix_count") or 0
        ),
        "product_scope_acceptance_release_blocker_stage_count": int(
            summary.get("product_scope_acceptance_release_blocker_stage_count") or 0
        ),
        "product_scope_acceptance_release_blocker_stage_ids": list(
            summary.get("product_scope_acceptance_release_blocker_stage_ids") or []
        ),
        "product_scope_acceptance_next_stage_id": summary.get(
            "product_scope_acceptance_next_stage_id", ""
        ),
        "product_scope_acceptance_next_stage_artifact": summary.get(
            "product_scope_acceptance_next_stage_artifact", ""
        ),
        "product_scope_acceptance_next_stage_validation_command": summary.get(
            "product_scope_acceptance_next_stage_validation_command", ""
        ),
        "product_scope_acceptance_next_stage_release_effect": summary.get(
            "product_scope_acceptance_next_stage_release_effect", ""
        ),
        "product_scope_acceptance_next_stage_unlock_claim_scopes": list(
            summary.get("product_scope_acceptance_next_stage_unlock_claim_scopes") or []
        ),
        "product_scope_acceptance_next_stage_required_checks": list(
            summary.get("product_scope_acceptance_next_stage_required_checks") or []
        ),
        "product_scope_acceptance_next_stage_next_action": summary.get(
            "product_scope_acceptance_next_stage_next_action", ""
        ),
        "product_scope_general_claim_blocker_count": int(
            summary.get("product_scope_general_claim_blocker_count") or 0
        ),
        "product_scope_ready_for_apply_count": int(summary.get("product_scope_ready_for_apply_count") or 0),
        "product_scope_authoritative_apply_allowed": bool(
            summary.get("product_scope_authoritative_apply_allowed") is True
        ),
        "product_scope_domain_count": int(summary.get("product_scope_domain_count") or 0),
        "product_scope_ready_domain_count": int(summary.get("product_scope_ready_domain_count") or 0),
        "product_scope_missing_domain_count": int(summary.get("product_scope_missing_domain_count") or 0),
        "product_scope_ready_domains": list(summary.get("product_scope_ready_domains") or []),
        "product_scope_missing_domains": list(summary.get("product_scope_missing_domains") or []),
        "product_scope_first_blocked_domain": summary.get("product_scope_first_blocked_domain", ""),
        "product_scope_first_blocked_domain_artifact": summary.get(
            "product_scope_first_blocked_domain_artifact", ""
        ),
        "product_scope_first_blocked_domain_observed": summary.get(
            "product_scope_first_blocked_domain_observed", ""
        ),
        "product_scope_first_blocked_domain_requirement": summary.get(
            "product_scope_first_blocked_domain_requirement", ""
        ),
        "product_scope_first_blocked_domain_next_action": summary.get(
            "product_scope_first_blocked_domain_next_action", ""
        ),
        "product_scope_transporter_p0_readiness_matrix_ready": bool(
            summary.get("product_scope_transporter_p0_readiness_matrix_ready") is True
        ),
        "product_scope_transporter_p0_readiness_matrix_artifact": summary.get(
            "product_scope_transporter_p0_readiness_matrix_artifact", ""
        ),
        "product_scope_transporter_p0_auto_close_ready_artifact_count": int(
            summary.get("product_scope_transporter_p0_auto_close_ready_artifact_count") or 0
        ),
        "product_scope_transporter_p0_manual_or_external_required_artifact_count": int(
            summary.get("product_scope_transporter_p0_manual_or_external_required_artifact_count") or 0
        ),
        "product_scope_transporter_p0_unresolved_slot_count": int(
            summary.get("product_scope_transporter_p0_unresolved_slot_count") or 0
        ),
        "product_scope_transporter_p0_auto_close_ready_slot_count": int(
            summary.get("product_scope_transporter_p0_auto_close_ready_slot_count") or 0
        ),
        "product_scope_transporter_p0_external_exact_evidence_required_slot_count": int(
            summary.get("product_scope_transporter_p0_external_exact_evidence_required_slot_count") or 0
        ),
        "product_scope_transporter_p0_first_manual_or_external_required_step_id": summary.get(
            "product_scope_transporter_p0_first_manual_or_external_required_step_id", ""
        ),
        "product_scope_transporter_p0_first_manual_or_external_required_slot_step": summary.get(
            "product_scope_transporter_p0_first_manual_or_external_required_slot_step", ""
        ),
        "product_scope_transporter_p0_first_manual_or_external_required_action": summary.get(
            "product_scope_transporter_p0_first_manual_or_external_required_action", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_packet_ready": bool(
            summary.get("product_scope_transporter_p0_evidence_acquisition_packet_ready") is True
        ),
        "product_scope_transporter_p0_evidence_acquisition_artifact": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_artifact", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_exact_request_slot_count": int(
            summary.get("product_scope_transporter_p0_evidence_acquisition_exact_request_slot_count") or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_unresolved_slot_count": int(
            summary.get("product_scope_transporter_p0_evidence_acquisition_unresolved_slot_count") or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_first_target_id": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_first_target_id", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_first_packet_step": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_first_packet_step", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_first_replacement_ligand_id": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_first_replacement_ligand_id", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_first_request_mode": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_first_request_mode", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_first_source_signal": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_first_source_signal", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_first_required_missing_fields": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_first_required_missing_fields", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_first_next_required_action": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_first_next_required_action", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet_ready": bool(
            summary.get("product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet_ready")
            is True
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet": dict(
            summary.get("product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet") or {}
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifacts": list(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifacts"
            )
            or []
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count": int(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix": list(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix"
            )
            or []
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix_count": int(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_blocker_count": int(
            summary.get("product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_blocker_count")
            or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_path": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_path", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_id": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_next_slot_id", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_operator_review_artifact": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_next_slot_operator_review_artifact", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_guard_ready": bool(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_guard_ready"
            )
            is True
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_claim_safe": bool(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_claim_safe"
            )
            is True
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_direct_binding_claim_allowed": bool(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_direct_binding_claim_allowed"
            )
            is True
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_decision": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_decision", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_guardrails": list(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_guardrails"
            )
            or []
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_observed_signal": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_observed_signal", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_required_upgrade": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_required_upgrade", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_source_count": int(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_source_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_result": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_result",
            "",
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_database_recheck_row_count": int(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_database_recheck_row_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_ligand_identity_mismatch_row_count": int(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_ligand_identity_mismatch_row_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_like_binding_candidate_row_count": int(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_like_binding_candidate_row_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_like_binding_candidate_claim_safe_ready_count": int(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_like_binding_candidate_claim_safe_ready_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_chembl_id": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_chembl_id",
            "",
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_delta_g_kcal_mol": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_delta_g_kcal_mol",
            "",
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_blocker": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_blocker",
            "",
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bindingdb_aqp1_expanded_cutoff_affinity_row_count": int(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bindingdb_aqp1_expanded_cutoff_affinity_row_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bindingdb_aqp1_expanded_cutoff_direct_like_affinity_row_count": int(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bindingdb_aqp1_expanded_cutoff_direct_like_affinity_row_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_pubchem_cid": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_pubchem_cid",
            "",
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_id": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_id",
            "",
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_chembl_target_id": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_chembl_target_id",
            "",
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_bindingdb_uniprot_affinity_row_count": int(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_bindingdb_uniprot_affinity_row_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_aqp1_activity_row_count": int(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_aqp1_activity_row_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_functional_ic50_identity_mismatch_detail": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_functional_ic50_identity_mismatch_detail",
            "",
        ),
        "product_scope_general_platform_domain_floor_ready": bool(
            summary.get("product_scope_general_platform_domain_floor_ready") is True
        ),
        "product_scope_general_platform_domain_floor_missing_domain_count": int(
            summary.get("product_scope_general_platform_domain_floor_missing_domain_count") or 0
        ),
        "product_scope_general_platform_domain_floor_missing_domains": list(
            summary.get("product_scope_general_platform_domain_floor_missing_domains") or []
        ),
        "product_scope_allowed_families": list(summary.get("product_scope_allowed_families") or []),
        "product_scope_blocked_claim_scopes": list(summary.get("product_scope_blocked_claim_scopes") or []),
        "product_scope_claim_blocked_domains": list(summary.get("product_scope_claim_blocked_domains") or []),
        "product_scope_general_platform_claim_allowed": bool(
            summary.get("product_scope_general_platform_claim_allowed") is True
        ),
        "product_scope_evidence_priority_ready": bool(
            summary.get("product_scope_evidence_priority_ready") is True
        ),
        "product_scope_evidence_priority_queue_item_count": int(
            summary.get("product_scope_evidence_priority_queue_item_count") or 0
        ),
        "product_scope_evidence_priority_open_item_count": int(
            summary.get("product_scope_evidence_priority_open_item_count") or 0
        ),
        "product_scope_evidence_priority_local_crosscheck_candidate_count": int(
            summary.get("product_scope_evidence_priority_local_crosscheck_candidate_count") or 0
        ),
        "product_scope_evidence_priority_external_primary_exact_required_count": int(
            summary.get("product_scope_evidence_priority_external_primary_exact_required_count") or 0
        ),
        "product_scope_evidence_priority_top_item_id": summary.get(
            "product_scope_evidence_priority_top_item_id", ""
        ),
        "product_scope_evidence_priority_top_domain": summary.get(
            "product_scope_evidence_priority_top_domain", ""
        ),
        "product_scope_evidence_priority_top_bucket": summary.get(
            "product_scope_evidence_priority_top_bucket", ""
        ),
        "product_scope_evidence_priority_top_next_step": summary.get(
            "product_scope_evidence_priority_top_next_step", ""
        ),
        "product_scope_evidence_priority_next_required_step": summary.get(
            "product_scope_evidence_priority_next_required_step", ""
        ),
        "product_scope_evidence_intake_ready": bool(
            summary.get("product_scope_evidence_intake_ready") is True
        ),
        "product_scope_evidence_intake_row_count": int(summary.get("product_scope_evidence_intake_row_count") or 0),
        "product_scope_local_crosscheck_triage_item_count": int(
            summary.get("product_scope_local_crosscheck_triage_item_count") or 0
        ),
        "product_scope_local_crosscheck_intake_ready_count": int(
            summary.get("product_scope_local_crosscheck_intake_ready_count") or 0
        ),
        "product_scope_external_exact_evidence_required_count": int(
            summary.get("product_scope_external_exact_evidence_required_count") or 0
        ),
        "product_scope_guardrail_item_count": int(summary.get("product_scope_guardrail_item_count") or 0),
        "product_scope_transporter_triage_packet_ready": bool(
            summary.get("product_scope_transporter_triage_packet_ready") is True
        ),
        "product_scope_transporter_operator_review_evidence_matrix_ready": bool(
            summary.get("product_scope_transporter_operator_review_evidence_matrix_ready") is True
        ),
        "product_scope_transporter_claim_safe_local_evidence_ready_count": int(
            summary.get("product_scope_transporter_claim_safe_local_evidence_ready_count") or 0
        ),
        "product_scope_transporter_claim_safe_local_evidence_blocked_count": int(
            summary.get("product_scope_transporter_claim_safe_local_evidence_blocked_count") or 0
        ),
        "product_scope_transporter_direct_binding_claim_blocked_count": int(
            summary.get("product_scope_transporter_direct_binding_claim_blocked_count") or 0
        ),
        "product_scope_transporter_negative_value_claim_blocked_count": int(
            summary.get("product_scope_transporter_negative_value_claim_blocked_count") or 0
        ),
        "product_scope_transporter_top_claim_safe_blocker": summary.get(
            "product_scope_transporter_top_claim_safe_blocker", ""
        ),
        "product_scope_transporter_top_operator_next_verdict": summary.get(
            "product_scope_transporter_top_operator_next_verdict", ""
        ),
        "product_scope_transporter_target_ready_for_promotion_count": int(
            summary.get("product_scope_transporter_target_ready_for_promotion_count") or 0
        ),
        "product_scope_transporter_target_blocked_for_promotion_count": int(
            summary.get("product_scope_transporter_target_blocked_for_promotion_count") or 0
        ),
        "product_scope_transporter_target_ready_for_promotion_ids": list(
            summary.get("product_scope_transporter_target_ready_for_promotion_ids") or []
        ),
        "product_scope_transporter_target_blocked_for_promotion_ids": list(
            summary.get("product_scope_transporter_target_blocked_for_promotion_ids") or []
        ),
        "product_scope_transporter_primary_blocker_target_id": summary.get(
            "product_scope_transporter_primary_blocker_target_id", ""
        ),
        "product_scope_transporter_primary_blocker_packet_step": summary.get(
            "product_scope_transporter_primary_blocker_packet_step", ""
        ),
        "product_scope_transporter_primary_blocker_candidate_name": summary.get(
            "product_scope_transporter_primary_blocker_candidate_name", ""
        ),
        "product_scope_transporter_candidate_assignment_required_count": int(
            summary.get("product_scope_transporter_candidate_assignment_required_count") or 0
        ),
        "product_scope_transporter_functional_quantitative_only_direct_gap_open_count": int(
            summary.get("product_scope_transporter_functional_quantitative_only_direct_gap_open_count") or 0
        ),
        "product_scope_transporter_review_only_direct_binding_gap_count": int(
            summary.get("product_scope_transporter_review_only_direct_binding_gap_count") or 0
        ),
        "product_scope_transporter_candidate_ready_for_manual_review_count": int(
            summary.get("product_scope_transporter_candidate_ready_for_manual_review_count") or 0
        ),
        "product_scope_transporter_candidate_ready_for_apply_count": int(
            summary.get("product_scope_transporter_candidate_ready_for_apply_count") or 0
        ),
        "product_scope_transporter_manual_review_intake_ready": bool(
            summary.get("product_scope_transporter_manual_review_intake_ready") is True
        ),
        "product_scope_transporter_manual_review_template_row_count": int(
            summary.get("product_scope_transporter_manual_review_template_row_count") or 0
        ),
        "product_scope_transporter_manual_review_direct_binding_evidence_required_count": int(
            summary.get("product_scope_transporter_manual_review_direct_binding_evidence_required_count") or 0
        ),
        "product_scope_transporter_manual_review_negative_quantitative_value_required_count": int(
            summary.get("product_scope_transporter_manual_review_negative_quantitative_value_required_count") or 0
        ),
        "product_scope_transporter_manual_review_decision_placeholder_count": int(
            summary.get("product_scope_transporter_manual_review_decision_placeholder_count") or 0
        ),
        "product_scope_transporter_manual_review_p0_slot_overlay_row_count": int(
            summary.get("product_scope_transporter_manual_review_p0_slot_overlay_row_count") or 0
        ),
        "product_scope_transporter_manual_review_p0_slot_overlay_candidate_changed_count": int(
            summary.get("product_scope_transporter_manual_review_p0_slot_overlay_candidate_changed_count") or 0
        ),
        "product_scope_transporter_manual_review_p0_slot_overlay_first_item_id": summary.get(
            "product_scope_transporter_manual_review_p0_slot_overlay_first_item_id",
            "",
        ),
        "product_scope_transporter_manual_review_p0_slot_overlay_first_candidate_ligand_id": summary.get(
            "product_scope_transporter_manual_review_p0_slot_overlay_first_candidate_ligand_id",
            "",
        ),
        "product_scope_transporter_manual_review_p0_slot_overlay_first_source": summary.get(
            "product_scope_transporter_manual_review_p0_slot_overlay_first_source",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_row_id": summary.get(
            "product_scope_transporter_manual_review_first_review_row_id",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_item_id": summary.get(
            "product_scope_transporter_manual_review_first_review_item_id",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_target_id": summary.get(
            "product_scope_transporter_manual_review_first_review_target_id",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_candidate_ligand_id": summary.get(
            "product_scope_transporter_manual_review_first_review_candidate_ligand_id",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_replacement_source": summary.get(
            "product_scope_transporter_manual_review_first_review_replacement_source",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_replacement_reference_binding_kcal_mol": summary.get(
            "product_scope_transporter_manual_review_first_review_replacement_reference_binding_kcal_mol",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_direct_binding_evidence_required": bool(
            summary.get("product_scope_transporter_manual_review_first_review_direct_binding_evidence_required")
            is True
        ),
        "product_scope_transporter_manual_review_first_review_direct_binding_source_url_or_doi": summary.get(
            "product_scope_transporter_manual_review_first_review_direct_binding_source_url_or_doi",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_negative_quantitative_value_required": bool(
            summary.get(
                "product_scope_transporter_manual_review_first_review_negative_quantitative_value_required"
            )
            is True
        ),
        "product_scope_transporter_manual_review_first_review_negative_reference_binding_kcal_mol": summary.get(
            "product_scope_transporter_manual_review_first_review_negative_reference_binding_kcal_mol",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_review_decision": summary.get(
            "product_scope_transporter_manual_review_first_review_review_decision",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_authoritative_apply_requested": summary.get(
            "product_scope_transporter_manual_review_first_review_authoritative_apply_requested",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_manual_review_blockers": summary.get(
            "product_scope_transporter_manual_review_first_review_manual_review_blockers",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_review_requirements": summary.get(
            "product_scope_transporter_manual_review_first_review_review_requirements",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_p0_slot_overlay_required_missing_fields": summary.get(
            "product_scope_transporter_manual_review_first_review_p0_slot_overlay_required_missing_fields",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_p0_slot_overlay_claim_safe_step_ready": bool(
            summary.get(
                "product_scope_transporter_manual_review_first_review_p0_slot_overlay_claim_safe_step_ready"
            )
            is True
        ),
        "product_scope_transporter_manual_review_first_review_p0_slot_overlay_authoritative_apply_allowed": bool(
            summary.get(
                "product_scope_transporter_manual_review_first_review_p0_slot_overlay_authoritative_apply_allowed"
            )
            is True
        ),
        "product_scope_transporter_manual_review_first_review_p0_slot_overlay_scope_promotion_allowed": bool(
            summary.get(
                "product_scope_transporter_manual_review_first_review_p0_slot_overlay_scope_promotion_allowed"
            )
            is True
        ),
        "product_scope_evidence_intake_next_required_step": summary.get(
            "product_scope_evidence_intake_next_required_step", ""
        ),
        "product_scope_pxr_exact_review_intake_ready": bool(
            summary.get("product_scope_pxr_exact_review_intake_ready") is True
        ),
        "product_scope_pxr_exact_review_template_row_count": int(
            summary.get("product_scope_pxr_exact_review_template_row_count") or 0
        ),
        "product_scope_pxr_exact_review_expected_blocked_row_count": int(
            summary.get("product_scope_pxr_exact_review_expected_blocked_row_count") or 0
        ),
        "product_scope_pxr_exact_review_conflict_resolution_required_count": int(
            summary.get("product_scope_pxr_exact_review_conflict_resolution_required_count") or 0
        ),
        "product_scope_pxr_exact_review_kcal_placeholder_count": int(
            summary.get("product_scope_pxr_exact_review_kcal_placeholder_count") or 0
        ),
        "product_scope_pxr_exact_review_source_placeholder_count": int(
            summary.get("product_scope_pxr_exact_review_source_placeholder_count") or 0
        ),
        "product_scope_pxr_exact_review_target_match_placeholder_count": int(
            summary.get("product_scope_pxr_exact_review_target_match_placeholder_count") or 0
        ),
        "product_scope_pxr_exact_review_decision_placeholder_count": int(
            summary.get("product_scope_pxr_exact_review_decision_placeholder_count") or 0
        ),
        "product_scope_pxr_exact_review_next_review_completion_packet_ready": bool(
            summary.get("product_scope_pxr_exact_review_next_review_completion_packet_ready") is True
        ),
        "product_scope_pxr_exact_review_next_review_completion_packet": dict(
            summary.get("product_scope_pxr_exact_review_next_review_completion_packet") or {}
        ),
        "product_scope_pxr_exact_review_next_review_return_bundle_required_artifacts": list(
            summary.get("product_scope_pxr_exact_review_next_review_return_bundle_required_artifacts") or []
        ),
        "product_scope_pxr_exact_review_next_review_return_bundle_required_artifact_count": int(
            summary.get("product_scope_pxr_exact_review_next_review_return_bundle_required_artifact_count") or 0
        ),
        "product_scope_pxr_exact_review_next_review_return_bundle_completion_matrix": list(
            summary.get("product_scope_pxr_exact_review_next_review_return_bundle_completion_matrix") or []
        ),
        "product_scope_pxr_exact_review_next_review_return_bundle_completion_matrix_count": int(
            summary.get("product_scope_pxr_exact_review_next_review_return_bundle_completion_matrix_count") or 0
        ),
        "product_scope_pxr_exact_review_next_review_return_bundle_blocker_count": int(
            summary.get("product_scope_pxr_exact_review_next_review_return_bundle_blocker_count") or 0
        ),
        "product_scope_pxr_exact_review_next_review_return_bundle_next_artifact_id": summary.get(
            "product_scope_pxr_exact_review_next_review_return_bundle_next_artifact_id", ""
        ),
        "product_scope_pxr_exact_review_next_review_return_bundle_next_artifact_path": summary.get(
            "product_scope_pxr_exact_review_next_review_return_bundle_next_artifact_path", ""
        ),
        "product_scope_pxr_exact_review_next_review_return_bundle_next_artifact_failed_check_ids": list(
            summary.get(
                "product_scope_pxr_exact_review_next_review_return_bundle_next_artifact_failed_check_ids"
            )
            or []
        ),
        "product_scope_pxr_exact_review_next_review_row_id": summary.get(
            "product_scope_pxr_exact_review_next_review_row_id", ""
        ),
        "product_scope_pxr_exact_review_next_review_candidate_name": summary.get(
            "product_scope_pxr_exact_review_next_review_candidate_name", ""
        ),
        "product_scope_pxr_exact_review_next_review_operator_review_artifact": summary.get(
            "product_scope_pxr_exact_review_next_review_operator_review_artifact", ""
        ),
        "product_scope_pxr_exact_review_next_required_step": summary.get(
            "product_scope_pxr_exact_review_next_required_step", ""
        ),
        "product_scope_pxr_source_modality_triage_ready": bool(
            summary.get("product_scope_pxr_source_modality_triage_ready") is True
        ),
        "product_scope_pxr_source_modality_triage_status": summary.get(
            "product_scope_pxr_source_modality_triage_status", ""
        ),
        "product_scope_pxr_source_modality_triage_artifact": summary.get(
            "product_scope_pxr_source_modality_triage_artifact", ""
        ),
        "product_scope_pxr_source_modality_triage_decision": summary.get(
            "product_scope_pxr_source_modality_triage_decision", ""
        ),
        "product_scope_pxr_source_modality_public_evidence_recheck_ready": bool(
            summary.get("product_scope_pxr_source_modality_public_evidence_recheck_ready") is True
        ),
        "product_scope_pxr_source_modality_public_recheck_artifact": summary.get(
            "product_scope_pxr_source_modality_public_recheck_artifact", ""
        ),
        "product_scope_pxr_source_modality_public_recheck_candidate_count": int(
            summary.get("product_scope_pxr_source_modality_public_recheck_candidate_count") or 0
        ),
        "product_scope_pxr_source_modality_public_recheck_chembl_direct_binding_total_record_count": int(
            summary.get(
                "product_scope_pxr_source_modality_public_recheck_chembl_direct_binding_total_record_count"
            )
            or 0
        ),
        "product_scope_pxr_source_modality_public_recheck_chembl_functional_activity_total_record_count": int(
            summary.get(
                "product_scope_pxr_source_modality_public_recheck_chembl_functional_activity_total_record_count"
            )
            or 0
        ),
        "product_scope_pxr_source_modality_public_recheck_bindingdb_pxr_like_total_record_count": int(
            summary.get(
                "product_scope_pxr_source_modality_public_recheck_bindingdb_pxr_like_total_record_count"
            )
            or 0
        ),
        "product_scope_pxr_source_modality_public_recheck_direct_or_claim_safe_binding_kcal_ready_count": int(
            summary.get(
                "product_scope_pxr_source_modality_public_recheck_direct_or_claim_safe_binding_kcal_ready_count"
            )
            or 0
        ),
        "product_scope_pxr_source_modality_public_recheck_all_candidates_remain_blocked": bool(
            summary.get("product_scope_pxr_source_modality_public_recheck_all_candidates_remain_blocked")
            is True
        ),
        "product_scope_pxr_source_modality_public_recheck_first_blocked_candidate_name": summary.get(
            "product_scope_pxr_source_modality_public_recheck_first_blocked_candidate_name", ""
        ),
        "product_scope_pxr_source_modality_public_recheck_first_blocked_reason": summary.get(
            "product_scope_pxr_source_modality_public_recheck_first_blocked_reason", ""
        ),
        "product_scope_pxr_source_modality_direct_replacement_candidate_packet_ready": bool(
            summary.get("product_scope_pxr_source_modality_direct_replacement_candidate_packet_ready") is True
        ),
        "product_scope_pxr_source_modality_direct_replacement_artifact": summary.get(
            "product_scope_pxr_source_modality_direct_replacement_artifact", ""
        ),
        "product_scope_pxr_source_modality_direct_replacement_candidate_count": int(
            summary.get("product_scope_pxr_source_modality_direct_replacement_candidate_count") or 0
        ),
        "product_scope_pxr_source_modality_direct_replacement_selected_candidate_count": int(
            summary.get("product_scope_pxr_source_modality_direct_replacement_selected_candidate_count") or 0
        ),
        "product_scope_pxr_source_modality_direct_replacement_selected_claim_safe_candidate_count": int(
            summary.get(
                "product_scope_pxr_source_modality_direct_replacement_selected_claim_safe_candidate_count"
            )
            or 0
        ),
        "product_scope_pxr_source_modality_direct_replacement_first_ligand_id": summary.get(
            "product_scope_pxr_source_modality_direct_replacement_first_ligand_id", ""
        ),
        "product_scope_pxr_source_modality_direct_replacement_first_molecule_chembl_id": summary.get(
            "product_scope_pxr_source_modality_direct_replacement_first_molecule_chembl_id", ""
        ),
        "product_scope_pxr_source_modality_direct_replacement_first_reference_binding_kcal_mol": summary.get(
            "product_scope_pxr_source_modality_direct_replacement_first_reference_binding_kcal_mol", ""
        ),
        "product_scope_pxr_source_modality_direct_replacement_first_source": summary.get(
            "product_scope_pxr_source_modality_direct_replacement_first_source", ""
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_ready": bool(
            summary.get("product_scope_pxr_source_modality_direct_replacement_apply_draft_ready") is True
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_status": summary.get(
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_status", ""
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_artifact": summary.get(
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_artifact", ""
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_workbook_row_count": int(
            summary.get("product_scope_pxr_source_modality_direct_replacement_apply_draft_workbook_row_count")
            or 0
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_before_draft": int(
            summary.get(
                "product_scope_pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_before_draft"
            )
            or 0
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_overlay_row_count": int(
            summary.get("product_scope_pxr_source_modality_direct_replacement_apply_draft_overlay_row_count")
            or 0
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_ready_for_apply_row_count_after_draft": int(
            summary.get(
                "product_scope_pxr_source_modality_direct_replacement_apply_draft_ready_for_apply_row_count_after_draft"
            )
            or 0
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_after_draft": int(
            summary.get(
                "product_scope_pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_after_draft"
            )
            or 0
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_first_overlay_ligand_id": summary.get(
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_first_overlay_ligand_id", ""
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_authoritative_fields_touched": bool(
            summary.get(
                "product_scope_pxr_source_modality_direct_replacement_apply_draft_authoritative_fields_touched"
            )
            is True
        ),
        "product_scope_pxr_source_modality_activity_proxy_or_conflict_surrogate_row_count": int(
            summary.get("product_scope_pxr_source_modality_activity_proxy_or_conflict_surrogate_row_count") or 0
        ),
        "product_scope_pxr_source_modality_direct_or_claim_safe_quantitative_ready_count": int(
            summary.get("product_scope_pxr_source_modality_direct_or_claim_safe_quantitative_ready_count") or 0
        ),
        "product_scope_pxr_source_modality_accepted_for_scope_promotion_count": int(
            summary.get("product_scope_pxr_source_modality_accepted_for_scope_promotion_count") or 0
        ),
        "product_scope_pxr_source_modality_next_review_row_id": summary.get(
            "product_scope_pxr_source_modality_next_review_row_id", ""
        ),
        "product_scope_pxr_source_modality_next_review_candidate_name": summary.get(
            "product_scope_pxr_source_modality_next_review_candidate_name", ""
        ),
        "product_scope_pxr_source_modality_next_review_source_modality": summary.get(
            "product_scope_pxr_source_modality_next_review_source_modality", ""
        ),
        "product_scope_pxr_source_modality_next_review_rejection_reason": summary.get(
            "product_scope_pxr_source_modality_next_review_rejection_reason", ""
        ),
        "release_complete_vs_operator_pending_lane": lane_surface["release_complete_vs_operator_pending_lane"],
        "goal_completion_audit_goal_complete": lane_surface["goal_completion_audit_goal_complete"],
        "release_complete_lane_ready": lane_surface["release_complete_lane_ready"],
        "operator_pending_lane_ready": lane_surface["operator_pending_lane_ready"],
        "operator_or_external_pending_lane_count": lane_surface["operator_or_external_pending_lane_count"],
        "release_complete_vs_operator_pending_matrix": lane_surface["release_complete_vs_operator_pending_matrix"],
        "requirements": rows,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "license_file_written": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }
