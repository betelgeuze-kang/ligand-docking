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
PRODUCT_GOAL_COMPLETION_AUDIT_ARTIFACT = ROOT / "runs" / "product_goal_completion_audit_current.json"
PRODUCT_COMMERCIAL_READINESS_HANDOFF_BUNDLE_ARTIFACT = (
    ROOT / "runs" / "product_commercial_readiness_handoff_bundle_current.json"
)
PRODUCT_FULL_COMMERCIAL_BLOCKER_EVIDENCE_MATRIX_ARTIFACT = (
    ROOT / "runs" / "product_full_commercial_blocker_evidence_matrix_current.json"
)

FULL_COMMERCIAL_RELEASE_BLOCKER_IDS = (
    "R8_full_scope_claim_closure",
    "R9_engine_refinement_claim_promotion",
)

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


def _bottleneck_id(row: dict[str, Any]) -> str:
    return str(row.get("bottleneck_id") or row.get("requirement_id") or row.get("phase") or "").strip()


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
    product_goal_completion_packet = _read_json_object(PRODUCT_GOAL_COMPLETION_AUDIT_ARTIFACT)
    handoff_packet = _read_json_object(PRODUCT_COMMERCIAL_READINESS_HANDOFF_BUNDLE_ARTIFACT)
    full_commercial_matrix_packet = _read_json_object(
        PRODUCT_FULL_COMMERCIAL_BLOCKER_EVIDENCE_MATRIX_ARTIFACT
    )

    readiness = _summary(readiness_packet)
    actions = _summary(action_packet)
    intake = _summary(intake_packet)
    release = _summary(release_packet)
    burndown = _summary(burndown_packet)
    bottlenecks = _summary(bottleneck_packet)
    api_contract = _summary(api_contract_packet)
    product_goal_completion = _summary(product_goal_completion_packet)
    handoff = _summary(handoff_packet)
    full_commercial_matrix = _summary(full_commercial_matrix_packet)
    bottleneck_rows = _rows(bottleneck_packet)
    full_commercial_release_blocker_ids = [
        bottleneck_id
        for row in bottleneck_rows
        for bottleneck_id in [_bottleneck_id(row)]
        if bottleneck_id in FULL_COMMERCIAL_RELEASE_BLOCKER_IDS
    ]
    release_full_commercial_blocker_ids = _string_list(
        release.get("full_commercial_release_blocker_ids")
    ) or list(full_commercial_release_blocker_ids)
    missing_full_commercial_release_blocker_ids = [
        blocker_id
        for blocker_id in FULL_COMMERCIAL_RELEASE_BLOCKER_IDS
        if blocker_id not in full_commercial_release_blocker_ids
    ]
    full_commercial_release_blocker_visibility_ready = (
        not missing_full_commercial_release_blocker_ids
        and len(full_commercial_release_blocker_ids) >= len(FULL_COMMERCIAL_RELEASE_BLOCKER_IDS)
    )
    active_bottleneck_primary = (
        _int(bottlenecks.get("current_bottleneck_count") or bottlenecks.get("bottleneck_count")) > 0
        and bool(bottlenecks.get("primary_action_id"))
    )
    primary_action_source = bottlenecks if active_bottleneck_primary else intake
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
            "primary_bottleneck_post_return_acceptance_artifact": "",
            "completion_audit_release_blocker_bottleneck_count": 0,
            "irreducible_external_return_bottleneck_count": 0,
            "expected_full_commercial_release_blocker_ids": list(FULL_COMMERCIAL_RELEASE_BLOCKER_IDS),
            "full_commercial_release_blocker_ids": [],
            "full_commercial_release_blocker_count": 0,
            "missing_full_commercial_release_blocker_ids": list(FULL_COMMERCIAL_RELEASE_BLOCKER_IDS),
            "full_commercial_release_blocker_visibility_ready": False,
            "restricted_release_allowed": False,
            "full_commercial_release_allowed": False,
            "primary_full_commercial_release_blocker_id": "",
            "primary_full_commercial_release_blocker": "",
            "full_commercial_release_next_required_step": "",
            "product_goal_release_blocker_fail_count": 0,
            "product_goal_release_blocker_requirement_ids": [],
            "product_goal_primary_release_blocker_requirement_id": "",
            "product_goal_primary_release_blocker_tier": "",
            "product_goal_primary_release_blocker": "",
            "product_goal_primary_release_blocker_next_command": "",
            "primary_release_blocker_action_id": "",
            "primary_release_blocker_action_status": "",
            "primary_release_blocker_action_required_input": "",
            "primary_release_blocker_action_artifact_path": "",
            "primary_release_blocker_action_recommended_action": "",
            "product_goal_completion_audit_artifact_path": str(PRODUCT_GOAL_COMPLETION_AUDIT_ARTIFACT),
            "production_ai_checkpoint_registry_promotion_required_gate_ids": [],
            "production_ai_checkpoint_registry_promotion_missing_gate_ids": [],
            "production_ai_checkpoint_registry_promotion_missing_gate_count": 0,
            "production_ai_checkpoint_registry_promotion_upstream_acceptance_ready": False,
            "production_ai_checkpoint_registry_promotion_currently_satisfied": False,
            "production_ai_checkpoint_actionable_operator_completion_packet_ready": False,
            "production_ai_checkpoint_actionable_operator_completion_artifact_id": "",
            "production_ai_checkpoint_actionable_operator_completion_required_fields_or_columns": [],
            "production_ai_checkpoint_actionable_operator_completion_diagnostic_commands": [],
            "production_ai_checkpoint_actionable_operator_completion_diagnostic_command_count": 0,
            "production_ai_checkpoint_actionable_operator_completion_completion_rule": "",
            "production_ai_checkpoint_actionable_operator_completion_next_action": "",
            "commercial_readiness_handoff_bundle_status": "",
            "commercial_readiness_handoff_bundle_ready": False,
            "commercial_readiness_handoff_bundle_artifact_path": str(
                PRODUCT_COMMERCIAL_READINESS_HANDOFF_BUNDLE_ARTIFACT
            ),
            "commercial_readiness_handoff_bundle_artifact_reference_count": 0,
            "commercial_readiness_handoff_bundle_local_missing_artifact_reference_count": 0,
            "full_commercial_blocker_evidence_matrix_status": "",
            "full_commercial_blocker_evidence_matrix_ready": False,
            "full_commercial_blocker_evidence_matrix_artifact_path": str(
                PRODUCT_FULL_COMMERCIAL_BLOCKER_EVIDENCE_MATRIX_ARTIFACT
            ),
            "full_commercial_blocker_evidence_matrix_release_blocker_visibility_ready": False,
            "full_commercial_blocker_evidence_matrix_row_count": 0,
            "full_commercial_blocker_evidence_matrix_blocked_row_count": 0,
            "full_commercial_blocker_evidence_matrix_approval_token_count": 0,
            "full_commercial_blocker_evidence_matrix_first_blocked_release_blocker_id": "",
            "full_commercial_blocker_evidence_matrix_first_blocked_evidence_row_id": "",
            "full_commercial_blocker_evidence_matrix_first_blocked_evidence_artifact": "",
            "full_commercial_blocker_evidence_matrix_first_blocked_expected_evidence_status": "",
            "full_commercial_blocker_evidence_matrix_first_blocked_observed_evidence_status": "",
            "full_commercial_blocker_evidence_matrix_first_blocked_row_blockers": "",
            "full_commercial_blocker_evidence_matrix_first_blocked_acceptance_artifact": "",
            "full_commercial_blocker_evidence_matrix_scope_receipt_most_common_row_blocker": "",
            "full_commercial_blocker_evidence_matrix_engine_receipt_most_common_row_blocker": "",
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
        "restricted_release_allowed": bool(
            release.get("restricted_release_allowed") is True
            or release.get("release_allowed") is True
        ),
        "full_commercial_release_allowed": bool(
            release.get("full_commercial_release_allowed") is True
        ),
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
        "primary_bottleneck_post_return_acceptance_artifact": bottlenecks.get(
            "primary_bottleneck_post_return_acceptance_artifact", ""
        ),
        "completion_audit_release_blocker_bottleneck_count": _int(
            bottlenecks.get("completion_audit_release_blocker_bottleneck_count")
        ),
        "irreducible_external_return_bottleneck_count": _int(
            bottlenecks.get("irreducible_external_return_bottleneck_count")
        ),
        "expected_full_commercial_release_blocker_ids": list(FULL_COMMERCIAL_RELEASE_BLOCKER_IDS),
        "full_commercial_release_blocker_ids": release_full_commercial_blocker_ids,
        "full_commercial_release_blocker_count": len(release_full_commercial_blocker_ids),
        "missing_full_commercial_release_blocker_ids": missing_full_commercial_release_blocker_ids,
        "full_commercial_release_blocker_visibility_ready": full_commercial_release_blocker_visibility_ready,
        "primary_full_commercial_release_blocker_id": release.get(
            "primary_full_commercial_release_blocker_id", ""
        ),
        "primary_full_commercial_release_blocker": release.get(
            "primary_full_commercial_release_blocker", ""
        ),
        "full_commercial_release_next_required_step": release.get(
            "full_commercial_release_next_required_step", ""
        ),
        "product_goal_release_blocker_fail_count": _int(
            actions.get("product_goal_release_blocker_fail_count")
            or intake.get("product_goal_release_blocker_fail_count")
        ),
        "product_goal_release_blocker_requirement_ids": _string_list(
            actions.get("product_goal_release_blocker_requirement_ids")
            or intake.get("product_goal_release_blocker_requirement_ids")
        ),
        "product_goal_primary_release_blocker_requirement_id": actions.get(
            "product_goal_primary_release_blocker_requirement_id"
        )
        or intake.get("product_goal_primary_release_blocker_requirement_id", ""),
        "product_goal_primary_release_blocker_tier": actions.get("product_goal_primary_release_blocker_tier")
        or intake.get("product_goal_primary_release_blocker_tier", ""),
        "product_goal_primary_release_blocker": actions.get("product_goal_primary_release_blocker")
        or intake.get("product_goal_primary_release_blocker", ""),
        "product_goal_primary_release_blocker_next_command": actions.get(
            "product_goal_primary_release_blocker_next_command", ""
        ),
        "primary_release_blocker_action_id": actions.get("primary_release_blocker_action_id")
        or intake.get("primary_release_blocker_action_id", ""),
        "primary_release_blocker_action_status": actions.get("primary_release_blocker_action_status")
        or intake.get("primary_release_blocker_action_status", ""),
        "primary_release_blocker_action_required_input": actions.get(
            "primary_release_blocker_action_required_input"
        )
        or intake.get("primary_release_blocker_action_required_input", ""),
        "primary_release_blocker_action_artifact_path": actions.get(
            "primary_release_blocker_action_artifact_path"
        )
        or intake.get("primary_release_blocker_action_artifact_path", ""),
        "primary_release_blocker_action_recommended_action": actions.get(
            "primary_release_blocker_action_recommended_action"
        )
        or intake.get("primary_release_blocker_action_recommended_action", ""),
        "product_goal_completion_audit_artifact_path": str(PRODUCT_GOAL_COMPLETION_AUDIT_ARTIFACT),
        "production_ai_checkpoint_registry_promotion_required_gate_ids": _string_list(
            product_goal_completion.get("production_ai_checkpoint_registry_promotion_required_gate_ids")
        ),
        "production_ai_checkpoint_registry_promotion_missing_gate_ids": _string_list(
            product_goal_completion.get("production_ai_checkpoint_registry_promotion_missing_gate_ids")
        ),
        "production_ai_checkpoint_registry_promotion_missing_gate_count": _int(
            product_goal_completion.get("production_ai_checkpoint_registry_promotion_missing_gate_count")
        ),
        "production_ai_checkpoint_registry_promotion_upstream_acceptance_ready": bool(
            product_goal_completion.get(
                "production_ai_checkpoint_registry_promotion_upstream_acceptance_ready"
            )
            is True
        ),
        "production_ai_checkpoint_registry_promotion_currently_satisfied": bool(
            product_goal_completion.get(
                "production_ai_checkpoint_registry_promotion_currently_satisfied"
            )
            is True
        ),
        "production_ai_checkpoint_actionable_operator_completion_packet_ready": bool(
            product_goal_completion.get(
                "production_ai_checkpoint_actionable_operator_completion_packet_ready"
            )
            is True
        ),
        "production_ai_checkpoint_actionable_operator_completion_artifact_id": product_goal_completion.get(
            "production_ai_checkpoint_actionable_operator_completion_artifact_id", ""
        ),
        "production_ai_checkpoint_actionable_operator_completion_required_fields_or_columns": _string_list(
            product_goal_completion.get(
                "production_ai_checkpoint_actionable_operator_completion_required_fields_or_columns"
            )
        ),
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_commands": _string_list(
            product_goal_completion.get(
                "production_ai_checkpoint_actionable_operator_completion_diagnostic_commands"
            )
        ),
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_command_count": _int(
            product_goal_completion.get(
                "production_ai_checkpoint_actionable_operator_completion_diagnostic_command_count"
            )
        ),
        "production_ai_checkpoint_actionable_operator_completion_completion_rule": product_goal_completion.get(
            "production_ai_checkpoint_actionable_operator_completion_completion_rule", ""
        ),
        "production_ai_checkpoint_actionable_operator_completion_next_action": product_goal_completion.get(
            "production_ai_checkpoint_actionable_operator_completion_next_action", ""
        ),
        "commercial_readiness_handoff_bundle_status": handoff.get("status", ""),
        "commercial_readiness_handoff_bundle_ready": bool(handoff.get("handoff_bundle_ready") is True),
        "commercial_readiness_handoff_bundle_artifact_path": str(
            PRODUCT_COMMERCIAL_READINESS_HANDOFF_BUNDLE_ARTIFACT
        ),
        "commercial_readiness_handoff_bundle_artifact_reference_count": _int(
            handoff.get("artifact_reference_count")
        ),
        "commercial_readiness_handoff_bundle_local_missing_artifact_reference_count": _int(
            handoff.get("local_missing_artifact_reference_count")
        ),
        "full_commercial_blocker_evidence_matrix_status": full_commercial_matrix.get("status", ""),
        "full_commercial_blocker_evidence_matrix_ready": bool(
            full_commercial_matrix.get("full_commercial_blocker_evidence_matrix_ready") is True
        ),
        "full_commercial_blocker_evidence_matrix_artifact_path": str(
            PRODUCT_FULL_COMMERCIAL_BLOCKER_EVIDENCE_MATRIX_ARTIFACT
        ),
        "full_commercial_blocker_evidence_matrix_release_blocker_visibility_ready": bool(
            full_commercial_matrix.get("release_blocker_visibility_ready") is True
        ),
        "full_commercial_blocker_evidence_matrix_row_count": _int(
            full_commercial_matrix.get("matrix_row_count")
        ),
        "full_commercial_blocker_evidence_matrix_blocked_row_count": _int(
            full_commercial_matrix.get("blocked_matrix_row_count")
        ),
        "full_commercial_blocker_evidence_matrix_approval_token_count": _int(
            full_commercial_matrix.get("approval_token_count")
        ),
        "full_commercial_blocker_evidence_matrix_first_blocked_release_blocker_id": full_commercial_matrix.get(
            "first_blocked_release_blocker_id", ""
        ),
        "full_commercial_blocker_evidence_matrix_first_blocked_evidence_row_id": full_commercial_matrix.get(
            "first_blocked_evidence_row_id", ""
        ),
        "full_commercial_blocker_evidence_matrix_first_blocked_evidence_artifact": full_commercial_matrix.get(
            "first_blocked_evidence_artifact", ""
        ),
        "full_commercial_blocker_evidence_matrix_first_blocked_expected_evidence_status": (
            full_commercial_matrix.get("first_blocked_expected_evidence_status", "")
        ),
        "full_commercial_blocker_evidence_matrix_first_blocked_observed_evidence_status": (
            full_commercial_matrix.get("first_blocked_observed_evidence_status", "")
        ),
        "full_commercial_blocker_evidence_matrix_first_blocked_row_blockers": full_commercial_matrix.get(
            "first_blocked_row_blockers", ""
        ),
        "full_commercial_blocker_evidence_matrix_first_blocked_acceptance_artifact": full_commercial_matrix.get(
            "first_blocked_acceptance_artifact", ""
        ),
        "full_commercial_blocker_evidence_matrix_scope_receipt_most_common_row_blocker": (
            full_commercial_matrix.get("scope_receipt_most_common_row_blocker", "")
        ),
        "full_commercial_blocker_evidence_matrix_engine_receipt_most_common_row_blocker": (
            full_commercial_matrix.get("engine_receipt_most_common_row_blocker", "")
        ),
        "official_results_required_bottleneck_count": _int(
            bottlenecks.get("official_results_required_bottleneck_count")
        ),
        "work_item_count": _int(burndown.get("work_item_count")),
        "operator_action_count": _int(actions.get("action_count") or release.get("operator_action_count")),
        "operator_approval_required_count": _int(actions.get("approval_required_count") or release.get("operator_approval_required_count")),
        "operator_input_required_count": _int(intake.get("operator_input_required_count")),
        "primary_action_id": primary_action_source.get("primary_action_id") or actions.get("primary_action_id", ""),
        "primary_action_status": primary_action_source.get("primary_action_status") or actions.get("primary_action_status", ""),
        "primary_action_required_input": primary_action_source.get("primary_action_required_input")
        or actions.get("primary_action_required_input", ""),
        "primary_action_command": primary_action_source.get("primary_action_command") or actions.get("primary_action_command", ""),
        "primary_action_recommended_action": primary_action_source.get("primary_action_recommended_action")
        or actions.get("primary_action_recommended_action", ""),
        "primary_action_artifact_path": primary_action_source.get("primary_action_artifact_path")
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
