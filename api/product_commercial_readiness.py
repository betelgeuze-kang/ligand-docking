from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from api.product_accounting import (
    commercial_delta_force_closure_fields as _commercial_delta_force_closure_fields,
    commercial_engine_refinement_claim_fields as _commercial_engine_refinement_claim_fields,
    commercial_first_parallelizable_source_modality_fields as _commercial_first_parallelizable_source_modality_fields,
    commercial_first_worker_runtime_receipt_fields as _commercial_first_worker_runtime_receipt_fields,
    commercial_full_scope_operator_handoff_fields as _commercial_full_scope_operator_handoff_fields,
    commercial_handoff_closure_acceptance_fields as _commercial_handoff_closure_acceptance_fields,
    commercial_production_ai_registry_promotion_fields as _commercial_production_ai_registry_promotion_fields,
    commercial_production_ai_return_fields as _commercial_production_ai_return_fields,
    commercial_scope_breadth_evidence_receipt_fields as _commercial_scope_breadth_evidence_receipt_fields,
    commercial_scope_closure_fields as _commercial_scope_closure_fields,
)

router = APIRouter(prefix="/product", tags=["product"])

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_COMMERCIAL_READINESS_OPERATOR_PACKET_ARTIFACT = (
    ROOT / "runs" / "product_commercial_readiness_operator_packet_current.json"
)
PRODUCT_COMMERCIAL_READINESS_OPERATOR_PACKET_FRESHNESS_ARTIFACT = (
    ROOT / "runs" / "product_commercial_readiness_operator_packet_freshness_current.json"
)
PRODUCT_COMMERCIAL_READINESS_EXECUTION_LADDER_ARTIFACT = (
    ROOT / "runs" / "product_commercial_readiness_execution_ladder_current.json"
)
PRODUCT_COMMERCIAL_READINESS_HANDOFF_BUNDLE_ARTIFACT = (
    ROOT / "runs" / "product_commercial_readiness_handoff_bundle_current.json"
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


@router.get("/commercial-readiness-operator-packet")
async def get_product_commercial_readiness_operator_packet() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_COMMERCIAL_READINESS_OPERATOR_PACKET_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    operator_packets = (
        packet.get("operator_completion_packets")
        if isinstance(packet.get("operator_completion_packets"), list)
        else []
    )
    if not summary:
        return {
            "status": "missing_product_commercial_readiness_operator_packet",
            "artifact_path": str(PRODUCT_COMMERCIAL_READINESS_OPERATOR_PACKET_ARTIFACT),
            "packet_ready": False,
            "goal_audit_artifact": "",
            "goal_audit_sha256": "",
            "commercial_readiness_matrix_sha256": "",
            "source_fingerprint_ready": False,
            "goal_complete": False,
            "open_gap_ids": [],
            "action_count": 0,
            "blocked_action_count": 0,
            "ready_action_count": 0,
            "parallelizable_action_count": 0,
            "parallelizable_action_ids": [],
            "first_parallelizable_action_id": "",
            "first_parallelizable_action_artifact": "",
            "first_parallelizable_action_next_action": "",
            "first_parallelizable_action_validation_command": "",
            "first_parallelizable_action_required_operator_inputs": "",
            "first_parallelizable_action_required_exact_evidence_fields": "",
            "first_parallelizable_action_required_claim_guardrails": "",
            "first_parallelizable_action_expected_evidence_type": "",
            "first_parallelizable_action_required_missing_fields": "",
            "first_parallelizable_action_operator_review_artifact": "",
            "first_parallelizable_action_post_intake_synchronization_targets": "",
            "first_parallelizable_action_acceptance_gate_commands": "",
            **_commercial_first_parallelizable_source_modality_fields(summary),
            "first_parallelizable_action_lane_id": "",
            "first_parallelizable_action_precondition": "",
            "first_action_id": "",
            "first_artifact": "",
            "first_execution_command": "",
            "first_validation_command": "",
            **_commercial_first_worker_runtime_receipt_fields(summary),
            **_commercial_production_ai_registry_promotion_fields(summary),
            **_commercial_production_ai_return_fields(summary),
            **_commercial_delta_force_closure_fields(summary),
            **_commercial_scope_closure_fields(summary),
            **_commercial_engine_refinement_claim_fields(summary),
            **_commercial_scope_breadth_evidence_receipt_fields(summary),
            **_commercial_full_scope_operator_handoff_fields(summary),
            "operator_input_total_count": 0,
            "operator_completion_packet_ready_count": 0,
            "release_blocker_action_ids": [],
            "actions": [],
            "operator_completion_packets": [],
            "next_required_step": "",
            "execution_enabled": False,
            "external_state_mutated": False,
            "docking_results_emitted": False,
            "scope_widened": False,
            "checkpoint_promoted": False,
            "claim_boundary": (
                "Product commercial-readiness operator-packet endpoint only; the local handoff packet artifact is "
                "missing or invalid. It does not run docking, run GPU jobs, fill evidence, promote checkpoints, "
                "widen claims, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_COMMERCIAL_READINESS_OPERATOR_PACKET_ARTIFACT),
        "packet_ready": bool(summary.get("packet_ready") is True),
        "goal_audit_artifact": summary.get("goal_audit_artifact", ""),
        "goal_audit_sha256": summary.get("goal_audit_sha256", ""),
        "commercial_readiness_matrix_sha256": summary.get("commercial_readiness_matrix_sha256", ""),
        "source_fingerprint_ready": bool(summary.get("source_fingerprint_ready") is True),
        "goal_complete": bool(summary.get("goal_complete") is True),
        "open_gap_ids": list(summary.get("open_gap_ids") or []),
        "action_count": int(summary.get("action_count") or 0),
        "blocked_action_count": int(summary.get("blocked_action_count") or 0),
        "ready_action_count": int(summary.get("ready_action_count") or 0),
        "parallelizable_action_count": int(summary.get("parallelizable_action_count") or 0),
        "parallelizable_action_ids": list(summary.get("parallelizable_action_ids") or []),
        "first_parallelizable_action_id": summary.get("first_parallelizable_action_id", ""),
        "first_parallelizable_action_artifact": summary.get("first_parallelizable_action_artifact", ""),
        "first_parallelizable_action_next_action": summary.get(
            "first_parallelizable_action_next_action", ""
        ),
        "first_parallelizable_action_validation_command": summary.get(
            "first_parallelizable_action_validation_command", ""
        ),
        "first_parallelizable_action_required_operator_inputs": summary.get(
            "first_parallelizable_action_required_operator_inputs", ""
        ),
        "first_parallelizable_action_required_exact_evidence_fields": summary.get(
            "first_parallelizable_action_required_exact_evidence_fields", ""
        ),
        "first_parallelizable_action_required_claim_guardrails": summary.get(
            "first_parallelizable_action_required_claim_guardrails", ""
        ),
        "first_parallelizable_action_expected_evidence_type": summary.get(
            "first_parallelizable_action_expected_evidence_type", ""
        ),
        "first_parallelizable_action_required_missing_fields": summary.get(
            "first_parallelizable_action_required_missing_fields", ""
        ),
        "first_parallelizable_action_operator_review_artifact": summary.get(
            "first_parallelizable_action_operator_review_artifact", ""
        ),
        "first_parallelizable_action_post_intake_synchronization_targets": summary.get(
            "first_parallelizable_action_post_intake_synchronization_targets", ""
        ),
        "first_parallelizable_action_acceptance_gate_commands": summary.get(
            "first_parallelizable_action_acceptance_gate_commands", ""
        ),
        **_commercial_first_parallelizable_source_modality_fields(summary),
        "first_parallelizable_action_lane_id": summary.get("first_parallelizable_action_lane_id", ""),
        "first_parallelizable_action_precondition": summary.get(
            "first_parallelizable_action_precondition", ""
        ),
        "first_action_id": summary.get("first_action_id", ""),
        "first_artifact": summary.get("first_artifact", ""),
        "first_execution_command": summary.get("first_execution_command", ""),
        "first_validation_command": summary.get("first_validation_command", ""),
        **_commercial_first_worker_runtime_receipt_fields(summary),
        **_commercial_production_ai_registry_promotion_fields(summary),
        **_commercial_production_ai_return_fields(summary),
        **_commercial_delta_force_closure_fields(summary),
        **_commercial_scope_closure_fields(summary),
        **_commercial_engine_refinement_claim_fields(summary),
        **_commercial_scope_breadth_evidence_receipt_fields(summary),
        **_commercial_full_scope_operator_handoff_fields(summary),
        "operator_input_total_count": int(summary.get("operator_input_total_count") or 0),
        "operator_completion_packet_ready_count": int(
            summary.get("operator_completion_packet_ready_count") or 0
        ),
        "release_blocker_action_ids": list(summary.get("release_blocker_action_ids") or []),
        "actions": list(rows),
        "operator_completion_packets": list(operator_packets),
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "external_state_mutated": False,
        "docking_results_emitted": False,
        "scope_widened": False,
        "checkpoint_promoted": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/commercial-readiness-operator-packet-freshness")
async def get_product_commercial_readiness_operator_packet_freshness() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_COMMERCIAL_READINESS_OPERATOR_PACKET_FRESHNESS_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_product_commercial_readiness_operator_packet_freshness",
            "artifact_path": str(PRODUCT_COMMERCIAL_READINESS_OPERATOR_PACKET_FRESHNESS_ARTIFACT),
            "freshness_ready": False,
            "goal_complete": False,
            "goal_audit_artifact": "",
            "operator_packet_artifact": "",
            "current_goal_audit_sha256": "",
            "operator_goal_audit_sha256": "",
            "current_commercial_readiness_matrix_sha256": "",
            "operator_commercial_readiness_matrix_sha256": "",
            "current_action_count": 0,
            "operator_action_count": 0,
            "current_blocked_action_count": 0,
            "operator_blocked_action_count": 0,
            "current_first_action_id": "",
            "operator_first_action_id": "",
            "command_references_ready": False,
            "operator_python_tool_reference_count": 0,
            "operator_missing_python_tool_reference_count": 0,
            "operator_python_tool_references": [],
            "operator_missing_python_tool_references": [],
            "check_count": 0,
            "pass_count": 0,
            "fail_count": 1,
            "failed_check_ids": ["missing_product_commercial_readiness_operator_packet_freshness"],
            "checks": [],
            "blockers": [],
            "next_required_step": "",
            "execution_enabled": False,
            "external_state_mutated": False,
            "docking_results_emitted": False,
            "scope_widened": False,
            "checkpoint_promoted": False,
            "claim_boundary": (
                "Product commercial-readiness operator-packet freshness endpoint only; the local freshness artifact "
                "is missing or invalid. It does not run docking, run GPU jobs, fill evidence, promote checkpoints, "
                "widen claims, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_COMMERCIAL_READINESS_OPERATOR_PACKET_FRESHNESS_ARTIFACT),
        "freshness_ready": bool(summary.get("freshness_ready") is True),
        "goal_complete": bool(summary.get("goal_complete") is True),
        "goal_audit_artifact": summary.get("goal_audit_artifact", ""),
        "operator_packet_artifact": summary.get("operator_packet_artifact", ""),
        "current_goal_audit_sha256": summary.get("current_goal_audit_sha256", ""),
        "operator_goal_audit_sha256": summary.get("operator_goal_audit_sha256", ""),
        "current_commercial_readiness_matrix_sha256": summary.get(
            "current_commercial_readiness_matrix_sha256", ""
        ),
        "operator_commercial_readiness_matrix_sha256": summary.get(
            "operator_commercial_readiness_matrix_sha256", ""
        ),
        "current_action_count": int(summary.get("current_action_count") or 0),
        "operator_action_count": int(summary.get("operator_action_count") or 0),
        "current_blocked_action_count": int(summary.get("current_blocked_action_count") or 0),
        "operator_blocked_action_count": int(summary.get("operator_blocked_action_count") or 0),
        "current_first_action_id": summary.get("current_first_action_id", ""),
        "operator_first_action_id": summary.get("operator_first_action_id", ""),
        "command_references_ready": bool(summary.get("command_references_ready") is True),
        "operator_python_tool_reference_count": int(
            summary.get("operator_python_tool_reference_count") or 0
        ),
        "operator_missing_python_tool_reference_count": int(
            summary.get("operator_missing_python_tool_reference_count") or 0
        ),
        "operator_python_tool_references": list(summary.get("operator_python_tool_references") or []),
        "operator_missing_python_tool_references": list(
            summary.get("operator_missing_python_tool_references") or []
        ),
        "check_count": int(summary.get("check_count") or 0),
        "pass_count": int(summary.get("pass_count") or 0),
        "fail_count": int(summary.get("fail_count") or 0),
        "failed_check_ids": list(summary.get("failed_check_ids") or []),
        "checks": list(rows),
        "blockers": list(blockers),
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "external_state_mutated": False,
        "docking_results_emitted": False,
        "scope_widened": False,
        "checkpoint_promoted": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/commercial-readiness-execution-ladder")
async def get_product_commercial_readiness_execution_ladder() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_COMMERCIAL_READINESS_EXECUTION_LADDER_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_product_commercial_readiness_execution_ladder",
            "artifact_path": str(PRODUCT_COMMERCIAL_READINESS_EXECUTION_LADDER_ARTIFACT),
            "ladder_ready": False,
            "operator_packet_artifact": "",
            "freshness_artifact": "",
            "operator_packet_ready": False,
            "freshness_ready": False,
            "goal_complete": False,
            "action_count": 0,
            "blocked_action_count": 0,
            "parallelizable_action_count": 0,
            "parallelizable_action_ids": [],
            "first_parallelizable_action_id": "",
            "first_parallelizable_action_order": 0,
            "first_parallelizable_action_artifact": "",
            "first_parallelizable_action_next_action": "",
            "first_parallelizable_action_validation_command": "",
            "first_parallelizable_action_required_operator_inputs": "",
            "first_parallelizable_action_required_exact_evidence_fields": "",
            "first_parallelizable_action_required_claim_guardrails": "",
            "first_parallelizable_action_expected_evidence_type": "",
            "first_parallelizable_action_required_missing_fields": "",
            "first_parallelizable_action_operator_review_artifact": "",
            "first_parallelizable_action_post_intake_synchronization_targets": "",
            "first_parallelizable_action_acceptance_gate_commands": "",
            **_commercial_first_parallelizable_source_modality_fields(summary),
            "first_parallelizable_action_lane_id": "",
            "first_parallelizable_action_precondition": "",
            "first_execution_order": 0,
            "first_action_id": "",
            "first_operator_input_artifact": "",
            "first_execution_command": "",
            "first_validation_command": "",
            **_commercial_first_worker_runtime_receipt_fields(summary),
            **_commercial_production_ai_registry_promotion_fields(summary),
            **_commercial_production_ai_return_fields(summary),
            "all_preconditions_satisfied": False,
            "ladder": [],
            "blockers": [],
            "next_required_step": "",
            "execution_enabled": False,
            "external_state_mutated": False,
            "docking_results_emitted": False,
            "scope_widened": False,
            "checkpoint_promoted": False,
            "claim_boundary": (
                "Product commercial-readiness execution-ladder endpoint only; the local ladder artifact is missing "
                "or invalid. It does not run commands, run docking, run GPU jobs, fill evidence, promote checkpoints, "
                "widen claims, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_COMMERCIAL_READINESS_EXECUTION_LADDER_ARTIFACT),
        "ladder_ready": bool(summary.get("ladder_ready") is True),
        "operator_packet_artifact": summary.get("operator_packet_artifact", ""),
        "freshness_artifact": summary.get("freshness_artifact", ""),
        "operator_packet_ready": bool(summary.get("operator_packet_ready") is True),
        "freshness_ready": bool(summary.get("freshness_ready") is True),
        "goal_complete": bool(summary.get("goal_complete") is True),
        "action_count": int(summary.get("action_count") or 0),
        "blocked_action_count": int(summary.get("blocked_action_count") or 0),
        "parallelizable_action_count": int(summary.get("parallelizable_action_count") or 0),
        "parallelizable_action_ids": list(summary.get("parallelizable_action_ids") or []),
        "first_parallelizable_action_id": summary.get("first_parallelizable_action_id", ""),
        "first_parallelizable_action_order": int(
            summary.get("first_parallelizable_action_order") or 0
        ),
        "first_parallelizable_action_artifact": summary.get("first_parallelizable_action_artifact", ""),
        "first_parallelizable_action_next_action": summary.get(
            "first_parallelizable_action_next_action", ""
        ),
        "first_parallelizable_action_validation_command": summary.get(
            "first_parallelizable_action_validation_command", ""
        ),
        "first_parallelizable_action_required_operator_inputs": summary.get(
            "first_parallelizable_action_required_operator_inputs", ""
        ),
        "first_parallelizable_action_required_exact_evidence_fields": summary.get(
            "first_parallelizable_action_required_exact_evidence_fields", ""
        ),
        "first_parallelizable_action_required_claim_guardrails": summary.get(
            "first_parallelizable_action_required_claim_guardrails", ""
        ),
        "first_parallelizable_action_expected_evidence_type": summary.get(
            "first_parallelizable_action_expected_evidence_type", ""
        ),
        "first_parallelizable_action_required_missing_fields": summary.get(
            "first_parallelizable_action_required_missing_fields", ""
        ),
        "first_parallelizable_action_operator_review_artifact": summary.get(
            "first_parallelizable_action_operator_review_artifact", ""
        ),
        "first_parallelizable_action_post_intake_synchronization_targets": summary.get(
            "first_parallelizable_action_post_intake_synchronization_targets", ""
        ),
        "first_parallelizable_action_acceptance_gate_commands": summary.get(
            "first_parallelizable_action_acceptance_gate_commands", ""
        ),
        **_commercial_first_parallelizable_source_modality_fields(summary),
        "first_parallelizable_action_lane_id": summary.get("first_parallelizable_action_lane_id", ""),
        "first_parallelizable_action_precondition": summary.get(
            "first_parallelizable_action_precondition", ""
        ),
        "first_execution_order": int(summary.get("first_execution_order") or 0),
        "first_action_id": summary.get("first_action_id", ""),
        "first_operator_input_artifact": summary.get("first_operator_input_artifact", ""),
        "first_execution_command": summary.get("first_execution_command", ""),
        "first_validation_command": summary.get("first_validation_command", ""),
        **_commercial_first_worker_runtime_receipt_fields(summary),
        **_commercial_production_ai_registry_promotion_fields(summary),
        **_commercial_production_ai_return_fields(summary),
        "all_preconditions_satisfied": bool(summary.get("all_preconditions_satisfied") is True),
        "ladder": list(rows),
        "blockers": list(blockers),
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "external_state_mutated": False,
        "docking_results_emitted": False,
        "scope_widened": False,
        "checkpoint_promoted": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/commercial-readiness-handoff-bundle")
async def get_product_commercial_readiness_handoff_bundle() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_COMMERCIAL_READINESS_HANDOFF_BUNDLE_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_product_commercial_readiness_handoff_bundle",
            "artifact_path": str(PRODUCT_COMMERCIAL_READINESS_HANDOFF_BUNDLE_ARTIFACT),
            "handoff_bundle_ready": False,
            "goal_complete": False,
            "artifact_count": 0,
            "ready_artifact_count": 0,
            "blocked_artifact_count": 1,
            "blocked_artifact_ids": ["missing_product_commercial_readiness_handoff_bundle"],
            "operator_packet_ready": False,
            "source_fingerprint_ready": False,
            "freshness_ready": False,
            "execution_ladder_ready": False,
            "operator_action_count": 0,
            "operator_blocked_action_count": 0,
            "ladder_action_count": 0,
            "operator_parallelizable_action_count": 0,
            "operator_parallelizable_action_ids": [],
            "ladder_parallelizable_action_count": 0,
            "ladder_parallelizable_action_ids": [],
            "first_parallelizable_action_id": "",
            "first_parallelizable_action_artifact": "",
            "first_parallelizable_action_next_action": "",
            "first_parallelizable_action_validation_command": "",
            "first_parallelizable_action_required_operator_inputs": "",
            "first_parallelizable_action_required_exact_evidence_fields": "",
            "first_parallelizable_action_required_claim_guardrails": "",
            "first_parallelizable_action_expected_evidence_type": "",
            "first_parallelizable_action_required_missing_fields": "",
            "first_parallelizable_action_operator_review_artifact": "",
            "first_parallelizable_action_post_intake_synchronization_targets": "",
            "first_parallelizable_action_acceptance_gate_commands": "",
            **_commercial_first_parallelizable_source_modality_fields(summary),
            "first_parallelizable_action_lane_id": "",
            "first_parallelizable_action_precondition": "",
            "first_action_id": "",
            "first_operator_input_artifact": "",
            "first_execution_command": "",
            "first_validation_command": "",
            **_commercial_first_worker_runtime_receipt_fields(summary),
            **_commercial_production_ai_registry_promotion_fields(summary),
            **_commercial_production_ai_return_fields(summary),
            **_commercial_handoff_closure_acceptance_fields(summary),
            **_commercial_engine_refinement_claim_fields(summary),
            **_commercial_scope_breadth_evidence_receipt_fields(summary),
            **_commercial_full_scope_operator_handoff_fields(summary),
            "artifact_reference_contract_ready": False,
            "artifact_reference_count": 0,
            "artifact_reference_manifest": [],
            "local_required_artifact_reference_count": 0,
            "local_missing_artifact_reference_count": 1,
            "local_missing_artifact_references": [
                "missing_product_commercial_readiness_handoff_bundle"
            ],
            "operator_return_artifact_reference_count": 0,
            "operator_return_pending_artifact_reference_count": 0,
            "abstract_artifact_reference_count": 0,
            "artifacts": [],
            "blockers": [],
            "next_required_step": "",
            "execution_enabled": False,
            "external_state_mutated": False,
            "docking_results_emitted": False,
            "scope_widened": False,
            "checkpoint_promoted": False,
            "claim_boundary": (
                "Product commercial-readiness handoff-bundle endpoint only; the local bundle artifact is missing "
                "or invalid. It does not run commands, run docking, run GPU jobs, fill evidence, promote checkpoints, "
                "widen claims, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_COMMERCIAL_READINESS_HANDOFF_BUNDLE_ARTIFACT),
        "handoff_bundle_ready": bool(summary.get("handoff_bundle_ready") is True),
        "goal_complete": bool(summary.get("goal_complete") is True),
        "artifact_count": int(summary.get("artifact_count") or 0),
        "ready_artifact_count": int(summary.get("ready_artifact_count") or 0),
        "blocked_artifact_count": int(summary.get("blocked_artifact_count") or 0),
        "blocked_artifact_ids": list(summary.get("blocked_artifact_ids") or []),
        "operator_packet_ready": bool(summary.get("operator_packet_ready") is True),
        "source_fingerprint_ready": bool(summary.get("source_fingerprint_ready") is True),
        "freshness_ready": bool(summary.get("freshness_ready") is True),
        "execution_ladder_ready": bool(summary.get("execution_ladder_ready") is True),
        "operator_action_count": int(summary.get("operator_action_count") or 0),
        "operator_blocked_action_count": int(summary.get("operator_blocked_action_count") or 0),
        "ladder_action_count": int(summary.get("ladder_action_count") or 0),
        "operator_parallelizable_action_count": int(
            summary.get("operator_parallelizable_action_count") or 0
        ),
        "operator_parallelizable_action_ids": list(
            summary.get("operator_parallelizable_action_ids") or []
        ),
        "ladder_parallelizable_action_count": int(
            summary.get("ladder_parallelizable_action_count") or 0
        ),
        "ladder_parallelizable_action_ids": list(
            summary.get("ladder_parallelizable_action_ids") or []
        ),
        "first_parallelizable_action_id": summary.get("first_parallelizable_action_id", ""),
        "first_parallelizable_action_artifact": summary.get("first_parallelizable_action_artifact", ""),
        "first_parallelizable_action_next_action": summary.get(
            "first_parallelizable_action_next_action", ""
        ),
        "first_parallelizable_action_validation_command": summary.get(
            "first_parallelizable_action_validation_command", ""
        ),
        "first_parallelizable_action_required_operator_inputs": summary.get(
            "first_parallelizable_action_required_operator_inputs", ""
        ),
        "first_parallelizable_action_required_exact_evidence_fields": summary.get(
            "first_parallelizable_action_required_exact_evidence_fields", ""
        ),
        "first_parallelizable_action_required_claim_guardrails": summary.get(
            "first_parallelizable_action_required_claim_guardrails", ""
        ),
        "first_parallelizable_action_expected_evidence_type": summary.get(
            "first_parallelizable_action_expected_evidence_type", ""
        ),
        "first_parallelizable_action_required_missing_fields": summary.get(
            "first_parallelizable_action_required_missing_fields", ""
        ),
        "first_parallelizable_action_operator_review_artifact": summary.get(
            "first_parallelizable_action_operator_review_artifact", ""
        ),
        "first_parallelizable_action_post_intake_synchronization_targets": summary.get(
            "first_parallelizable_action_post_intake_synchronization_targets", ""
        ),
        "first_parallelizable_action_acceptance_gate_commands": summary.get(
            "first_parallelizable_action_acceptance_gate_commands", ""
        ),
        **_commercial_first_parallelizable_source_modality_fields(summary),
        "first_parallelizable_action_lane_id": summary.get("first_parallelizable_action_lane_id", ""),
        "first_parallelizable_action_precondition": summary.get(
            "first_parallelizable_action_precondition", ""
        ),
        "first_action_id": summary.get("first_action_id", ""),
        "first_operator_input_artifact": summary.get("first_operator_input_artifact", ""),
        "first_execution_command": summary.get("first_execution_command", ""),
        "first_validation_command": summary.get("first_validation_command", ""),
        **_commercial_first_worker_runtime_receipt_fields(summary),
        **_commercial_production_ai_registry_promotion_fields(summary),
        **_commercial_production_ai_return_fields(summary),
        **_commercial_handoff_closure_acceptance_fields(summary),
        **_commercial_engine_refinement_claim_fields(summary),
        **_commercial_scope_breadth_evidence_receipt_fields(summary),
        **_commercial_full_scope_operator_handoff_fields(summary),
        "artifact_reference_contract_ready": bool(
            summary.get("artifact_reference_contract_ready") is True
        ),
        "artifact_reference_count": int(summary.get("artifact_reference_count") or 0),
        "artifact_reference_manifest": list(summary.get("artifact_reference_manifest") or []),
        "local_required_artifact_reference_count": int(
            summary.get("local_required_artifact_reference_count") or 0
        ),
        "local_missing_artifact_reference_count": int(
            summary.get("local_missing_artifact_reference_count") or 0
        ),
        "local_missing_artifact_references": list(
            summary.get("local_missing_artifact_references") or []
        ),
        "operator_return_artifact_reference_count": int(
            summary.get("operator_return_artifact_reference_count") or 0
        ),
        "operator_return_pending_artifact_reference_count": int(
            summary.get("operator_return_pending_artifact_reference_count") or 0
        ),
        "abstract_artifact_reference_count": int(
            summary.get("abstract_artifact_reference_count") or 0
        ),
        "artifacts": list(rows),
        "blockers": list(blockers),
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "external_state_mutated": False,
        "docking_results_emitted": False,
        "scope_widened": False,
        "checkpoint_promoted": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }
