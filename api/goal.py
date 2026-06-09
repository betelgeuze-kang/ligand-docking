from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/goal", tags=["goal"])
ROOT = Path(__file__).resolve().parents[1]

GOAL_READINESS_ROLLUP_ARTIFACT = ROOT / "runs" / "goal_readiness_rollup_current.json"
GOAL_OPERATOR_ACTION_BOARD_ARTIFACT = ROOT / "runs" / "goal_operator_action_board_current.json"
GOAL_OPERATOR_INTAKE_KIT_MANIFEST = ROOT / "runs" / "goal_operator_intake_kit_current" / "manifest.json"
GOAL_RELEASE_DECISION_ARTIFACT = ROOT / "runs" / "goal_release_decision_gate_current.json"
GOAL_RELEASE_BURNDOWN_ARTIFACT = ROOT / "runs" / "goal_release_burndown_work_order_current.json"
GOAL_BOTTLENECK_BRIEFING_ARTIFACT = ROOT / "runs" / "goal_bottleneck_briefing_current.json"
GOAL_API_SURFACE_CONTRACT_ARTIFACT = ROOT / "runs" / "goal_api_surface_contract_current.json"

CLAIM_BOUNDARY = (
    "Goal endpoints are read-only local status surfaces for the commercial product, CAMEO validation, "
    "CASP17 transition, and cleanup objective. They do not run docking, assemble bundles, install packages, "
    "submit predictions, register servers, send email, delete, archive, externalize, upload, or mutate external state."
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
    return summary if isinstance(summary, dict) else packet if isinstance(packet, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _blockers(packet: dict[str, Any]) -> list[dict[str, Any]]:
    blockers = packet.get("blockers")
    return [row for row in blockers if isinstance(row, dict)] if isinstance(blockers, list) else []


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


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _mutation_flags() -> dict[str, bool]:
    return {
        "execution_enabled": False,
        "action_executed": False,
        "delete_executed": False,
        "archive_executed": False,
        "externalize_executed": False,
        "upload_executed": False,
        "docking_results_emitted": False,
        "prediction_generation_enabled": False,
        "server_registration_mutated": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
    }


@router.get("/status")
async def get_goal_status() -> dict[str, Any]:
    readiness_packet = _read_json_object(GOAL_READINESS_ROLLUP_ARTIFACT)
    action_packet = _read_json_object(GOAL_OPERATOR_ACTION_BOARD_ARTIFACT)
    intake_packet = _read_json_object(GOAL_OPERATOR_INTAKE_KIT_MANIFEST)
    release_packet = _read_json_object(GOAL_RELEASE_DECISION_ARTIFACT)
    burndown_packet = _read_json_object(GOAL_RELEASE_BURNDOWN_ARTIFACT)
    bottleneck_packet = _read_json_object(GOAL_BOTTLENECK_BRIEFING_ARTIFACT)
    api_contract_packet = _read_json_object(GOAL_API_SURFACE_CONTRACT_ARTIFACT)

    readiness = _summary(readiness_packet)
    actions = _summary(action_packet)
    intake = _summary(intake_packet)
    release = _summary(release_packet)
    burndown = _summary(burndown_packet)
    bottlenecks = _summary(bottleneck_packet)
    api_contract = _summary(api_contract_packet)
    if not any([readiness, actions, release, burndown]):
        return {
            "status": "missing_goal_status_artifacts",
            "readiness_artifact_path": str(GOAL_READINESS_ROLLUP_ARTIFACT),
            "action_board_artifact_path": str(GOAL_OPERATOR_ACTION_BOARD_ARTIFACT),
            "release_decision_artifact_path": str(GOAL_RELEASE_DECISION_ARTIFACT),
            "burndown_artifact_path": str(GOAL_RELEASE_BURNDOWN_ARTIFACT),
            "primary_action_id": "",
            "primary_action_status": "",
            "primary_action_required_input": "",
            "primary_action_command": "",
            "primary_action_recommended_action": "",
            "primary_action_artifact_path": "",
            "primary_bottleneck_root_cause_category": "",
            "primary_bottleneck_locally_closable_without_operator_return": False,
            "primary_bottleneck_required_external_return": "",
            **_mutation_flags(),
            "claim_boundary": CLAIM_BOUNDARY,
        }

    return {
        "status": release.get("status") or readiness.get("status") or actions.get("status") or burndown.get("status"),
        "readiness_status": readiness.get("status", ""),
        "release_complete_vs_operator_pending_lane": readiness.get(
            "release_complete_vs_operator_pending_lane", ""
        ),
        "goal_completion_audit_goal_complete": readiness.get("goal_completion_audit_goal_complete"),
        "release_complete_lane_ready": readiness.get("release_complete_lane_ready"),
        "operator_pending_lane_ready": readiness.get("operator_pending_lane_ready"),
        "operator_action_board_status": actions.get("status", ""),
        "operator_intake_kit_status": intake.get("status", ""),
        "release_decision_status": release.get("status", ""),
        "release_burndown_status": burndown.get("status", ""),
        "bottleneck_briefing_status": bottlenecks.get("status", ""),
        "goal_api_surface_contract_status": api_contract.get("status", ""),
        "goal_api_surface_ready": bool(api_contract.get("surface_ready") is True),
        "release_allowed": bool(release.get("release_allowed") is True),
        "commercial_independent_product_ready": bool(release.get("commercial_independent_product_ready") is True),
        "cameo_architecture_validation_ready": bool(release.get("cameo_architecture_validation_ready") is True),
        "cleanup_objective_ready": bool(release.get("cleanup_objective_ready") is True),
        "release_blocker_count": _int(release.get("blocker_count")),
        "release_check_count": _int(release.get("check_count")),
        "bottleneck_count": _int(bottlenecks.get("bottleneck_count")),
        "primary_bottleneck_kind": bottlenecks.get("primary_bottleneck_kind", ""),
        "primary_bottleneck_phase": bottlenecks.get("primary_bottleneck_phase", ""),
        "primary_bottleneck_root_cause_category": bottlenecks.get(
            "primary_bottleneck_root_cause_category", ""
        ),
        "primary_bottleneck_locally_closable_without_operator_return": bool(
            bottlenecks.get("primary_bottleneck_locally_closable_without_operator_return") is True
        ),
        "primary_bottleneck_required_external_return": bottlenecks.get(
            "primary_bottleneck_required_external_return", ""
        ),
        "official_results_required_bottleneck_count": _int(
            bottlenecks.get("official_results_required_bottleneck_count")
        ),
        "work_item_count": _int(burndown.get("work_item_count")),
        "operator_action_count": _int(actions.get("action_count") or release.get("operator_action_count")),
        "operator_approval_required_count": _int(actions.get("approval_required_count") or release.get("operator_approval_required_count")),
        "operator_input_required_count": _int(intake.get("operator_input_required_count")),
        "primary_action_id": intake.get("primary_action_id") or actions.get("primary_action_id", ""),
        "primary_action_status": intake.get("primary_action_status") or actions.get("primary_action_status", ""),
        "primary_action_required_input": intake.get("primary_action_required_input")
        or actions.get("primary_action_required_input", ""),
        "primary_action_command": intake.get("primary_action_command") or actions.get("primary_action_command", ""),
        "primary_action_recommended_action": intake.get("primary_action_recommended_action")
        or actions.get("primary_action_recommended_action", ""),
        "primary_action_artifact_path": intake.get("primary_action_artifact_path")
        or actions.get("primary_action_artifact_path", ""),
        "operator_intake_kit_release_burndown_linked_entry_count": _int(
            intake.get("release_burndown_linked_entry_count")
        ),
        "operator_template_missing_count": _int(intake.get("template_missing_count")),
        "all_required_templates_present": bool(intake.get("all_required_templates_present") is True),
        "official_results_required_count": _int(intake.get("official_results_required_count") or burndown.get("official_results_required_item_count")),
        "policy_decision_required_count": _int(intake.get("policy_decision_required_count") or burndown.get("policy_decision_required_item_count")),
        "approval_token_count": _int(
            bottlenecks.get("approval_token_count")
            or intake.get("approval_token_count")
            or burndown.get("approval_token_count")
        ),
        "approval_tokens": _string_list(
            bottlenecks.get("approval_tokens_required")
            or intake.get("approval_tokens")
            or burndown.get("approval_tokens_required")
        ),
        "approval_reclaim_size_gb": _float(actions.get("approval_reclaim_size_gb") or release.get("approval_reclaim_size_gb")),
        "protected_cleanup_payload_size_gb": _float(
            release.get("protected_cleanup_payload_size_gb")
            or actions.get("protected_cleanup_payload_size_gb")
            or readiness.get("cleanup_cli_protected_payload_size_gb")
        ),
        "product_cli_status_set_status": release.get("product_cli_status_set_status") or readiness.get("product_cli_status_set_status", ""),
        "product_cli_approval_token_count": _int(release.get("product_cli_approval_token_count") or readiness.get("product_cli_approval_token_count")),
        "product_cli_operations_blocked_stage_count": _int(
            release.get("product_cli_operations_blocked_stage_count")
            or readiness.get("product_cli_operations_blocked_stage_count")
        ),
        "product_operational_quality_ready": bool(
            release.get("product_operational_quality_ready") is True
            or release.get("product_cli_operational_quality_ready") is True
            or readiness.get("product_operational_quality_ready") is True
            or readiness.get("product_cli_operational_quality_ready") is True
            or actions.get("product_cli_operational_quality_ready") is True
        ),
        "product_operational_quality_status": release.get("product_operational_quality_status")
        or release.get("product_release_operations_source_operational_quality_status")
        or readiness.get("product_operational_quality_status")
        or actions.get("product_release_operations_source_operational_quality_status", ""),
        "product_operational_quality_blocker_count": _int(
            release.get("product_operational_quality_blocker_count")
            or readiness.get("product_operational_quality_blocker_count")
            or actions.get("product_release_operations_operational_quality_blocker_count")
        ),
        "product_operational_quality_artifact": release.get("product_operational_quality_artifact")
        or readiness.get("product_operational_quality_artifact")
        or actions.get("product_release_operations_operational_quality_artifact", ""),
        "product_cli_authorized_for_execution": bool(
            release.get("product_cli_authorized_for_execution") is True
            or readiness.get("product_cli_authorized_for_execution") is True
        ),
        "product_cli_delivery_ready_claim_allowed": bool(
            release.get("product_cli_delivery_ready_claim_allowed") is True
            or readiness.get("product_cli_delivery_ready_claim_allowed") is True
        ),
        "cameo_cli_status_set_status": release.get("cameo_cli_status_set_status") or readiness.get("cameo_cli_status_set_status", ""),
        "cameo_cli_approval_token_count": _int(release.get("cameo_cli_approval_token_count") or readiness.get("cameo_cli_approval_token_count")),
        "cameo_cli_official_result_required": bool(
            release.get("cameo_cli_official_result_required") is True
            or readiness.get("cameo_cli_official_result_required") is True
        ),
        "cameo_cli_receiver_smoke_status": release.get("cameo_cli_receiver_smoke_status") or readiness.get("cameo_cli_receiver_smoke_status", ""),
        "cameo_evidence_integrity_ready": bool(
            release.get("cameo_evidence_integrity_ready") is True
            or release.get("cameo_cli_evidence_integrity_ready") is True
            or readiness.get("cameo_evidence_integrity_ready") is True
            or readiness.get("cameo_cli_evidence_integrity_ready") is True
            or actions.get("cameo_cli_evidence_integrity_ready") is True
        ),
        "cameo_evidence_integrity_status": release.get("cameo_evidence_integrity_status")
        or release.get("cameo_validation_operations_evidence_integrity_status")
        or readiness.get("cameo_evidence_integrity_status")
        or actions.get("cameo_validation_operations_evidence_integrity_status", ""),
        "cameo_evidence_integrity_blocker_count": _int(
            release.get("cameo_evidence_integrity_blocker_count")
            or readiness.get("cameo_evidence_integrity_blocker_count")
            or actions.get("cameo_validation_operations_evidence_integrity_blocker_count")
        ),
        "cameo_evidence_integrity_artifact": release.get("cameo_evidence_integrity_artifact")
        or readiness.get("cameo_evidence_integrity_artifact")
        or actions.get("cameo_validation_operations_evidence_integrity_artifact", ""),
        "cameo_official_results_pending_honest": bool(
            release.get("cameo_official_results_pending_honest") is True
            or release.get("cameo_cli_official_results_pending_honest") is True
            or readiness.get("cameo_official_results_pending_honest") is True
            or readiness.get("cameo_cli_official_results_pending_honest") is True
            or actions.get("cameo_cli_official_results_pending_honest") is True
        ),
        "cameo_no_local_native_accuracy_substitution": bool(
            release.get("cameo_no_local_native_accuracy_substitution") is True
            or release.get("cameo_cli_no_local_native_accuracy_substitution") is True
            or readiness.get("cameo_no_local_native_accuracy_substitution") is True
            or readiness.get("cameo_cli_no_local_native_accuracy_substitution") is True
            or actions.get("cameo_cli_no_local_native_accuracy_substitution") is True
        ),
        "cleanup_cli_status_set_status": release.get("cleanup_cli_status_set_status") or readiness.get("cleanup_cli_status_set_status", ""),
        "cleanup_cli_approval_token_count": _int(release.get("cleanup_cli_approval_token_count") or readiness.get("cleanup_cli_approval_token_count")),
        "cleanup_cli_approval_reclaim_size_gb": _float(
            release.get("cleanup_cli_approval_reclaim_size_gb")
            or readiness.get("cleanup_cli_approval_reclaim_size_gb")
        ),
        "cleanup_cli_postcheck_contract_ready": bool(
            release.get("cleanup_cli_postcheck_contract_ready") is True
            or readiness.get("cleanup_cli_postcheck_contract_ready") is True
        ),
        "cleanup_cli_protected_payload_size_gb": _float(
            release.get("cleanup_cli_protected_payload_size_gb")
            or readiness.get("cleanup_cli_protected_payload_size_gb")
        ),
        "cleanup_cli_protected_policy_change_required_count": _int(
            release.get("cleanup_cli_protected_policy_change_required_count")
            or readiness.get("cleanup_cli_protected_policy_change_required_count")
        ),
        **_mutation_flags(),
        "claim_boundary": CLAIM_BOUNDARY,
    }


@router.get("/readiness")
async def get_goal_readiness() -> dict[str, Any]:
    packet = _read_json_object(GOAL_READINESS_ROLLUP_ARTIFACT)
    summary = _summary(packet)
    if not summary:
        return {
            "status": "missing_goal_readiness_rollup",
            "artifact_path": str(GOAL_READINESS_ROLLUP_ARTIFACT),
            "release_allowed": False,
            **_mutation_flags(),
            "claim_boundary": CLAIM_BOUNDARY,
        }
    return {
        **summary,
        "artifact_path": str(GOAL_READINESS_ROLLUP_ARTIFACT),
        "rows": _rows(packet),
        "blockers": _blockers(packet),
        **_mutation_flags(),
    }


@router.get("/actions")
async def get_goal_actions() -> dict[str, Any]:
    packet = _read_json_object(GOAL_OPERATOR_ACTION_BOARD_ARTIFACT)
    intake_packet = _read_json_object(GOAL_OPERATOR_INTAKE_KIT_MANIFEST)
    summary = _summary(packet)
    intake = _summary(intake_packet)
    if not summary:
        return {
            "status": "missing_goal_operator_action_board",
            "artifact_path": str(GOAL_OPERATOR_ACTION_BOARD_ARTIFACT),
            "intake_kit_manifest_path": str(GOAL_OPERATOR_INTAKE_KIT_MANIFEST),
            **_mutation_flags(),
            "claim_boundary": CLAIM_BOUNDARY,
        }
    return {
        **summary,
        "artifact_path": str(GOAL_OPERATOR_ACTION_BOARD_ARTIFACT),
        "intake_kit_manifest_path": str(GOAL_OPERATOR_INTAKE_KIT_MANIFEST),
        "operator_intake_kit_status": intake.get("status", ""),
        "operator_intake_kit_template_missing_count": _int(intake.get("template_missing_count")),
        "operator_intake_kit_approval_token_count": _int(intake.get("approval_token_count")),
        "operator_intake_kit_approval_tokens": _string_list(intake.get("approval_tokens")),
        "actions": _rows(packet),
        "blockers": _blockers(packet),
        **_mutation_flags(),
    }


@router.get("/operator-intake-kit")
async def get_goal_operator_intake_kit() -> dict[str, Any]:
    packet = _read_json_object(GOAL_OPERATOR_INTAKE_KIT_MANIFEST)
    summary = _summary(packet)
    if not summary:
        return {
            "status": "missing_goal_operator_intake_kit",
            "artifact_path": str(GOAL_OPERATOR_INTAKE_KIT_MANIFEST),
            "operator_input_required_count": 0,
            "release_burndown_linked_entry_count": 0,
            **_mutation_flags(),
            "claim_boundary": CLAIM_BOUNDARY,
        }
    return {
        **summary,
        "artifact_path": str(GOAL_OPERATOR_INTAKE_KIT_MANIFEST),
        "entries": _rows(packet),
        "blockers": _blockers(packet),
        **_mutation_flags(),
    }


@router.get("/release-decision")
async def get_goal_release_decision() -> dict[str, Any]:
    packet = _read_json_object(GOAL_RELEASE_DECISION_ARTIFACT)
    summary = _summary(packet)
    if not summary:
        return {
            "status": "missing_goal_release_decision_gate",
            "artifact_path": str(GOAL_RELEASE_DECISION_ARTIFACT),
            "release_allowed": False,
            **_mutation_flags(),
            "claim_boundary": CLAIM_BOUNDARY,
        }
    return {
        **summary,
        "artifact_path": str(GOAL_RELEASE_DECISION_ARTIFACT),
        "checks": _rows(packet),
        "blockers": _blockers(packet),
        **_mutation_flags(),
    }


@router.get("/burndown")
async def get_goal_burndown() -> dict[str, Any]:
    packet = _read_json_object(GOAL_RELEASE_BURNDOWN_ARTIFACT)
    summary = _summary(packet)
    if not summary:
        return {
            "status": "missing_goal_release_burndown_work_order",
            "artifact_path": str(GOAL_RELEASE_BURNDOWN_ARTIFACT),
            "release_allowed": False,
            **_mutation_flags(),
            "claim_boundary": CLAIM_BOUNDARY,
        }
    return {
        **summary,
        "artifact_path": str(GOAL_RELEASE_BURNDOWN_ARTIFACT),
        "work_items": _rows(packet),
        "blockers": _blockers(packet),
        **_mutation_flags(),
    }


@router.get("/bottlenecks")
async def get_goal_bottlenecks() -> dict[str, Any]:
    packet = _read_json_object(GOAL_BOTTLENECK_BRIEFING_ARTIFACT)
    summary = _summary(packet)
    if not summary:
        return {
            "status": "missing_goal_bottleneck_briefing",
            "artifact_path": str(GOAL_BOTTLENECK_BRIEFING_ARTIFACT),
            "bottleneck_count": 0,
            "release_allowed": False,
            **_mutation_flags(),
            "claim_boundary": CLAIM_BOUNDARY,
        }
    return {
        **summary,
        "artifact_path": str(GOAL_BOTTLENECK_BRIEFING_ARTIFACT),
        "bottlenecks": _rows(packet),
        "blockers": _blockers(packet),
        **_mutation_flags(),
    }


@router.get("/api-contract")
async def get_goal_api_contract() -> dict[str, Any]:
    packet = _read_json_object(GOAL_API_SURFACE_CONTRACT_ARTIFACT)
    summary = _summary(packet)
    if not summary:
        return {
            "status": "missing_goal_api_surface_contract",
            "artifact_path": str(GOAL_API_SURFACE_CONTRACT_ARTIFACT),
            "surface_ready": False,
            "check_count": 0,
            "blocker_count": 1,
            **_mutation_flags(),
            "claim_boundary": CLAIM_BOUNDARY,
        }
    return {
        **summary,
        "artifact_path": str(GOAL_API_SURFACE_CONTRACT_ARTIFACT),
        "checks": _rows(packet),
        "blockers": _blockers(packet),
        **_mutation_flags(),
    }
