#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PRODUCT_PILOT_JSON = "runs/product_pilot_packet_contract_current.json"
DEFAULT_PRODUCT_ARCHITECTURE_JSON = "runs/product_architecture_contract_current.json"
DEFAULT_PRODUCT_COMMERCIAL_INDEPENDENCE_JSON = "runs/product_commercial_independence_gate_current.json"
DEFAULT_CAMEO_VALIDATION_JSON = "runs/cameo_validation_readiness_gate_current.json"
DEFAULT_CAMEO_CAPABILITY_JSON = "runs/cameo_capability_preflight_current.json"
DEFAULT_CAMEO_PUBLIC_REGISTRATION_APPROVAL_GATE_JSON = "runs/cameo_public_registration_approval_gate_current.json"
DEFAULT_GOAL_ROLLUP_JSON = "runs/goal_readiness_rollup_current.json"
DEFAULT_OPERATOR_ACTION_BOARD_JSON = "runs/goal_operator_action_board_current.json"
DEFAULT_TRANSITION_CLEANUP_PREFLIGHT_JSON = "runs/transition_cleanup_execution_preflight_current.json"
DEFAULT_LIGAND_CLEANUP_PREFLIGHT_JSON = "runs/ligand_heavy_cleanup_execution_preflight_current.json"
DEFAULT_PROTECTED_CLEANUP_REVIEW_JSON = "runs/protected_cleanup_payload_review_current.json"
DEFAULT_PROTECTED_CLEANUP_POLICY_DECISION_GATE_JSON = "runs/protected_cleanup_policy_decision_gate_current.json"
DEFAULT_CLEANUP_POSTCHECK_CONTRACT_JSON = "runs/cleanup_postcheck_contract_current.json"
DEFAULT_CLEANUP_COMPLETION_GATE_JSON = "runs/cleanup_completion_gate_current.json"
DEFAULT_GOAL_API_SURFACE_CONTRACT_JSON = "runs/goal_api_surface_contract_current.json"
DEFAULT_GOAL_BOTTLENECK_BRIEFING_JSON = "runs/goal_bottleneck_briefing_current.json"
DEFAULT_PRODUCT_AI_ARCHITECTURE_GAP_JSON = "runs/product_ai_architecture_gap_closure_current.json"
DEFAULT_PRODUCT_AI_EXECUTION_BACKLOG_JSON = "runs/product_ai_architecture_execution_backlog_current.json"
DEFAULT_PRODUCT_RELEASE_SOURCE_OF_TRUTH_JSON = "runs/product_release_source_of_truth_gate_current.json"
DEFAULT_API_CUSTOMER_FLOW_RELEASE_EVIDENCE_JSON = "runs/api_customer_flow_release_evidence_current.json"
DEFAULT_PRODUCT_FULL_COMMERCIAL_BLOCKER_EVIDENCE_MATRIX_JSON = (
    "runs/product_full_commercial_blocker_evidence_matrix_current.json"
)
DEFAULT_PRODUCT_ROLLOUT_EXECUTION_SMOKE_RECEIPT_JSON = (
    "runs/product_rollout_execution_smoke_receipt_current.json"
)
DEFAULT_ACCURACY_PARITY_SCORECARD_JSON = "runs/accuracy_parity_scorecard_current.json"
DEFAULT_SCIENCE_CLAIM_PROMOTION_GAP_CLOSURE_JSON = "runs/science_claim_promotion_gap_closure_current.json"
DEFAULT_MASTER_GAP_CLOSURE_ROLLUP_JSON = "runs/master_gap_closure_rollup_current.json"
DEFAULT_OUT_JSON = "runs/goal_release_decision_gate_current.json"
DEFAULT_OUT_CSV = "runs/goal_release_decision_gate_current.csv"
DEFAULT_OUT_MD = "runs/goal_release_decision_gate_current.md"

CLAIM_BOUNDARY = (
    "Goal release decision gate only; it audits whether the commercial product, CAMEO validation, and cleanup lanes "
    "are release-ready from existing local artifacts. It does not run docking, assemble bundles, submit CAMEO "
    "predictions, register a server, send email, delete, archive, externalize, upload, commit, push, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _primary_backlog_row(backlog_packet: dict[str, Any]) -> dict[str, Any]:
    summary = _summary(backlog_packet)
    primary_id = _text(summary.get("primary_work_item_id"))
    rows = _rows(backlog_packet)
    for row in rows:
        if primary_id and _text(row.get("work_item_id")) == primary_id:
            return row
    return rows[0] if rows else {}


def _primary_backlog_detail(backlog_packet: dict[str, Any]) -> str:
    summary = _summary(backlog_packet)
    primary = _primary_backlog_row(backlog_packet)
    if not summary and not primary:
        return ""
    return (
        f"primary_backlog_work_item_id={_text(summary.get('primary_work_item_id'))};"
        f"primary_backlog_observed={_text(primary.get('observed'))};"
        f"primary_backlog_next_action={_text(primary.get('next_action'))}"
    )


def _row_by_id(rows: list[dict[str, Any]], key: str, row_id: str) -> dict[str, Any]:
    for row in rows:
        if _text(row.get(key)) == row_id:
            return row
    return {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    if isinstance(value, tuple):
        return [_text(item) for item in value if _text(item)]
    text = _text(value)
    return [text] if text else []


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


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _row(
    *,
    lane_id: str,
    check: str,
    artifact_path: str,
    observed: str,
    required: str,
    passed: bool,
    reason: str,
) -> dict[str, Any]:
    return {
        "lane_id": lane_id,
        "check": check,
        "status": "pass" if passed else "fail",
        "observed": observed,
        "required": required,
        "artifact_path": artifact_path,
        "reason": reason,
        "release_blocker": not passed,
        "execution_enabled": False,
        "action_executed": False,
        "delete_executed": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
    }


def build_goal_release_decision_gate(
    *,
    product_pilot_packet: dict[str, Any],
    product_architecture_packet: dict[str, Any] | None = None,
    product_commercial_independence_packet: dict[str, Any] | None = None,
    cameo_validation_packet: dict[str, Any],
    cameo_capability_packet: dict[str, Any],
    cameo_public_registration_approval_gate_packet: dict[str, Any] | None = None,
    goal_rollup_packet: dict[str, Any],
    operator_action_board_packet: dict[str, Any],
    transition_cleanup_preflight_packet: dict[str, Any],
    ligand_cleanup_preflight_packet: dict[str, Any],
    protected_cleanup_review_packet: dict[str, Any],
    protected_cleanup_policy_decision_gate_packet: dict[str, Any] | None = None,
    cleanup_postcheck_contract_packet: dict[str, Any] | None = None,
    cleanup_completion_gate_packet: dict[str, Any] | None = None,
    goal_api_surface_contract_packet: dict[str, Any] | None = None,
    goal_bottleneck_briefing_packet: dict[str, Any] | None = None,
    product_ai_architecture_gap_packet: dict[str, Any] | None = None,
    product_ai_execution_backlog_packet: dict[str, Any] | None = None,
    product_release_source_of_truth_packet: dict[str, Any] | None = None,
    api_customer_flow_release_evidence_packet: dict[str, Any] | None = None,
    product_full_commercial_blocker_evidence_matrix_packet: dict[str, Any] | None = None,
    product_rollout_execution_smoke_receipt_packet: dict[str, Any] | None = None,
    accuracy_parity_scorecard_packet: dict[str, Any] | None = None,
    science_claim_promotion_gap_packet: dict[str, Any] | None = None,
    master_gap_closure_rollup_packet: dict[str, Any] | None = None,
    product_pilot_path: str = DEFAULT_PRODUCT_PILOT_JSON,
    product_architecture_path: str = DEFAULT_PRODUCT_ARCHITECTURE_JSON,
    product_commercial_independence_path: str = DEFAULT_PRODUCT_COMMERCIAL_INDEPENDENCE_JSON,
    cameo_validation_path: str = DEFAULT_CAMEO_VALIDATION_JSON,
    cameo_capability_path: str = DEFAULT_CAMEO_CAPABILITY_JSON,
    cameo_public_registration_approval_gate_path: str = DEFAULT_CAMEO_PUBLIC_REGISTRATION_APPROVAL_GATE_JSON,
    goal_rollup_path: str = DEFAULT_GOAL_ROLLUP_JSON,
    operator_action_board_path: str = DEFAULT_OPERATOR_ACTION_BOARD_JSON,
    transition_cleanup_preflight_path: str = DEFAULT_TRANSITION_CLEANUP_PREFLIGHT_JSON,
    ligand_cleanup_preflight_path: str = DEFAULT_LIGAND_CLEANUP_PREFLIGHT_JSON,
    protected_cleanup_review_path: str = DEFAULT_PROTECTED_CLEANUP_REVIEW_JSON,
    protected_cleanup_policy_decision_gate_path: str = DEFAULT_PROTECTED_CLEANUP_POLICY_DECISION_GATE_JSON,
    cleanup_postcheck_contract_path: str = DEFAULT_CLEANUP_POSTCHECK_CONTRACT_JSON,
    cleanup_completion_gate_path: str = DEFAULT_CLEANUP_COMPLETION_GATE_JSON,
    goal_api_surface_contract_path: str = DEFAULT_GOAL_API_SURFACE_CONTRACT_JSON,
    goal_bottleneck_briefing_path: str = DEFAULT_GOAL_BOTTLENECK_BRIEFING_JSON,
    product_ai_architecture_gap_path: str = DEFAULT_PRODUCT_AI_ARCHITECTURE_GAP_JSON,
    product_ai_execution_backlog_path: str = DEFAULT_PRODUCT_AI_EXECUTION_BACKLOG_JSON,
    product_release_source_of_truth_path: str = DEFAULT_PRODUCT_RELEASE_SOURCE_OF_TRUTH_JSON,
    api_customer_flow_release_evidence_path: str = DEFAULT_API_CUSTOMER_FLOW_RELEASE_EVIDENCE_JSON,
    product_full_commercial_blocker_evidence_matrix_path: str = (
        DEFAULT_PRODUCT_FULL_COMMERCIAL_BLOCKER_EVIDENCE_MATRIX_JSON
    ),
    product_rollout_execution_smoke_receipt_path: str = (
        DEFAULT_PRODUCT_ROLLOUT_EXECUTION_SMOKE_RECEIPT_JSON
    ),
    accuracy_parity_scorecard_path: str = DEFAULT_ACCURACY_PARITY_SCORECARD_JSON,
    science_claim_promotion_gap_path: str = DEFAULT_SCIENCE_CLAIM_PROMOTION_GAP_CLOSURE_JSON,
    master_gap_closure_rollup_path: str = DEFAULT_MASTER_GAP_CLOSURE_ROLLUP_JSON,
) -> dict[str, Any]:
    product = _summary(product_pilot_packet)
    product_architecture = _summary(product_architecture_packet or {})
    product_independence = _summary(product_commercial_independence_packet or {})
    cameo_validation = _summary(cameo_validation_packet)
    cameo_capability = _summary(cameo_capability_packet)
    cameo_registration_gate = _summary(cameo_public_registration_approval_gate_packet or {})
    rollup = _summary(goal_rollup_packet)
    actions = _summary(operator_action_board_packet)
    transition_cleanup = _summary(transition_cleanup_preflight_packet)
    ligand_cleanup = _summary(ligand_cleanup_preflight_packet)
    protected_cleanup = _summary(protected_cleanup_review_packet)
    protected_policy_gate = _summary(protected_cleanup_policy_decision_gate_packet or {})
    cleanup_postcheck = _summary(cleanup_postcheck_contract_packet or {})
    cleanup_completion = _summary(cleanup_completion_gate_packet or {})
    goal_api_surface = _summary(goal_api_surface_contract_packet or {})
    goal_bottleneck_briefing = _summary(goal_bottleneck_briefing_packet or {})
    goal_bottleneck_briefing_gate_present = goal_bottleneck_briefing_packet is not None
    goal_bottleneck_full_commercial_receipts_recorded = (
        _text(goal_bottleneck_briefing.get("status")) == "goal_bottleneck_briefing_ready"
        and _int(goal_bottleneck_briefing.get("completion_audit_release_blocker_bottleneck_count")) == 2
        and _int(goal_bottleneck_briefing.get("full_commercial_evidence_receipt_entry_count")) == 2
        and _int(goal_bottleneck_briefing.get("full_commercial_evidence_receipt_operator_input_required_count")) == 2
        and _int(goal_bottleneck_briefing.get("full_commercial_evidence_receipt_current_action_required_count")) == 2
        and _int(goal_bottleneck_briefing.get("full_commercial_evidence_receipt_template_required_count")) == 2
        and _int(goal_bottleneck_briefing.get("full_commercial_evidence_receipt_template_present_count")) == 2
        and _int(goal_bottleneck_briefing.get("full_commercial_evidence_receipt_approval_token_count")) == 2
        and _text(goal_bottleneck_briefing.get("full_commercial_evidence_receipt_source_gate_statuses"))
        == (
            "product_scope_breadth_evidence_receipt=blocked_product_scope_breadth_evidence_receipt;"
            "engine_refinement_claim_evidence_receipt=blocked_engine_refinement_claim_evidence_receipt"
        )
        and _text(goal_bottleneck_briefing.get("full_commercial_evidence_receipt_required_inputs"))
        == (
            "config/product_scope_breadth_evidence_receipt_current.csv;"
            "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
        )
        and _text(goal_bottleneck_briefing.get("full_commercial_evidence_receipt_approval_tokens"))
        == (
            "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT;"
            "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT"
        )
        and bool(goal_bottleneck_briefing.get("execution_enabled") is False)
        and bool(goal_bottleneck_briefing.get("external_state_mutated") is False)
    )
    goal_bottleneck_production_ai_registry_promotion_priority_missing_gate_ids = _text_list(
        goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_missing_gate_ids")
    )
    expected_production_ai_registry_promotion_missing_gate_ids = [
        "trained_model_checkpoint_count_positive",
        "default_residual_mode_guarded",
        "production_promotion_allowed",
        "customer_facing_mutation_flags",
    ]
    goal_bottleneck_production_ai_registry_promotion_priority_recorded = (
        _text(goal_bottleneck_briefing.get("status")) == "goal_bottleneck_briefing_ready"
        and _text(goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_source_json"))
        == "runs/production_ai_registry_promotion_priority_packet_current.json"
        and _text(goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_status"))
        == "blocked_production_ai_registry_promotion_priority_packet"
        and bool(goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_packet_ready") is True)
        and bool(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_registry_promotion_ready")
            is False
        )
        and _int(goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_operator_input_required_count"))
        == 4
        and _int(goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_blocked_priority_item_count"))
        == 4
        and _int(goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_missing_gate_count")) == 4
        and goal_bottleneck_production_ai_registry_promotion_priority_missing_gate_ids
        == expected_production_ai_registry_promotion_missing_gate_ids
        and _text(goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_top_gate_id"))
        == "trained_model_checkpoint_count_positive"
        and _text(goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_top_priority_bucket"))
        == "trained_checkpoint_registration_required"
        and _text(goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_top_acceptance_artifact"))
        == "runs/residual_model_registry_current.json"
        and bool(goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_model_promoted") is False)
        and bool(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_customer_facing_mutation_enabled")
            is False
        )
        and bool(goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_external_state_mutated") is False)
    )
    release_source_of_truth = _summary(product_release_source_of_truth_packet or {})
    release_source_of_truth_gate_present = product_release_source_of_truth_packet is not None
    release_source_of_truth_ready = (
        _text(release_source_of_truth.get("status")) == "product_release_source_of_truth_gate_ready"
        and bool(release_source_of_truth.get("release_source_of_truth_ready") is True)
        and _int(release_source_of_truth.get("blocker_count")) == 0
    )
    api_customer_flow = _summary(api_customer_flow_release_evidence_packet or {})
    api_customer_flow_gate_present = api_customer_flow_release_evidence_packet is not None
    api_customer_flow_ready = (
        _text(api_customer_flow.get("status")) == "api_customer_flow_release_evidence_ready"
        and bool(api_customer_flow.get("formal_release_evidence_ready") is True)
        and bool(api_customer_flow.get("clean_install_flow_ready") is True)
        and bool(api_customer_flow.get("result_manifest_signature_verified") is True)
        and bool(api_customer_flow.get("bundle_validation_ready") is True)
        and bool(api_customer_flow.get("restricted_unattended_runtime_ready") is True)
        and _int(api_customer_flow.get("blocker_count")) == 0
    )
    full_commercial_matrix = _summary(product_full_commercial_blocker_evidence_matrix_packet or {})
    full_commercial_matrix_gate_present = (
        product_full_commercial_blocker_evidence_matrix_packet is not None
    )
    full_commercial_matrix_recorded = (
        _text(full_commercial_matrix.get("status"))
        in {
            "blocked_product_full_commercial_blocker_evidence_matrix",
            "product_full_commercial_blocker_evidence_matrix_ready",
        }
        and full_commercial_matrix.get("expected_release_blocker_ids")
        == ["R8_full_scope_claim_closure", "R9_engine_refinement_claim_promotion"]
        and bool(full_commercial_matrix.get("release_blocker_visibility_ready") is True)
        and _int(full_commercial_matrix.get("matrix_row_count")) >= 2
        and bool(full_commercial_matrix.get("execution_enabled") is False)
        and bool(full_commercial_matrix.get("external_state_mutated") is False)
    )
    rollout_smoke = _summary(product_rollout_execution_smoke_receipt_packet or {})
    rollout_smoke_gate_present = product_rollout_execution_smoke_receipt_packet is not None
    rollout_smoke_recorded = (
        _text(rollout_smoke.get("status"))
        in {
            "blocked_product_rollout_execution_smoke_receipt",
            "product_rollout_execution_smoke_receipt_ready",
        }
        and bool(rollout_smoke.get("source_authorized_for_separate_operator_execution") is True)
        and bool(rollout_smoke.get("rollout_executed") is False)
        and bool(rollout_smoke.get("external_state_mutated") is False)
    ) or (
        _text(rollout_smoke.get("status")) == "product_rollout_execution_smoke_receipt_ready"
        and bool(rollout_smoke.get("rollout_executed") is True)
        and bool(rollout_smoke.get("external_state_mutated") is True)
    )
    science_claim_gap = _summary(science_claim_promotion_gap_packet or {})
    science_claim_gap_rows = _rows(science_claim_promotion_gap_packet or {})
    science_claim_gap_gate_present = science_claim_promotion_gap_packet is not None
    science_claim_open_gap_ids = _text_list(science_claim_gap.get("open_gap_ids"))
    science_claim_primary_open_gap_id = _text(science_claim_gap.get("current_primary_open_gap_id"))
    science_claim_primary_open_gap = _row_by_id(
        science_claim_gap_rows,
        "gap_id",
        science_claim_primary_open_gap_id,
    )
    science_claim_gap_recorded = (
        _text(science_claim_gap.get("status"))
        in {
            "blocked_science_claim_promotion_gap_closure",
            "science_claim_promotion_gap_closure_complete",
        }
        and _int(science_claim_gap.get("gap_count")) >= 1
        and bool(science_claim_gap.get("execution_enabled") is False)
        and bool(science_claim_gap.get("external_state_mutated") is False)
    )
    accuracy_parity = _summary(accuracy_parity_scorecard_packet or {})
    accuracy_parity_rows = _rows(accuracy_parity_scorecard_packet or {})
    accuracy_parity_claim_boundary = (
        accuracy_parity_scorecard_packet.get("claim_boundary")
        if isinstance(accuracy_parity_scorecard_packet, dict)
        else {}
    )
    if not isinstance(accuracy_parity_claim_boundary, dict):
        accuracy_parity_claim_boundary = {}
    accuracy_parity_gate_present = accuracy_parity_scorecard_packet is not None
    accuracy_parity_top_blockers = _text_list(accuracy_parity.get("top_blockers"))
    accuracy_ligand_ranking = _row_by_id(accuracy_parity_rows, "axis", "ligand_ranking")
    accuracy_ligand_metrics = accuracy_ligand_ranking.get("metrics")
    if not isinstance(accuracy_ligand_metrics, dict):
        accuracy_ligand_metrics = {}
    accuracy_ligand_thresholds = accuracy_ligand_ranking.get("thresholds")
    if not isinstance(accuracy_ligand_thresholds, dict):
        accuracy_ligand_thresholds = {}
    accuracy_ligand_blockers = _text_list(accuracy_ligand_ranking.get("blockers"))
    accuracy_parity_rows_accounted = (
        _int(accuracy_parity.get("pass_row_count"))
        + _int(accuracy_parity.get("restricted_pass_row_count"))
        + _int(accuracy_parity.get("blocked_row_count"))
        + _int(accuracy_parity.get("missing_row_count"))
    )
    accuracy_parity_scorecard_recorded = (
        _text(accuracy_parity.get("status")) in {"blocked_accuracy_parity", "green"}
        and _int(accuracy_parity.get("row_count")) >= 1
        and accuracy_parity_rows_accounted == _int(accuracy_parity.get("row_count"))
        and bool(accuracy_parity_claim_boundary.get("fake_pass_allowed") is False)
        and bool(accuracy_parity_claim_boundary.get("threshold_relaxation_allowed") is False)
        and bool(accuracy_parity_claim_boundary.get("scorecard_rows_must_map_to_frozen_artifacts") is True)
        and bool(accuracy_ligand_ranking)
    )
    accuracy_parity_full_commercial_blocked = (
        accuracy_parity_gate_present
        and not bool(accuracy_parity.get("overall_commercial_tool_accuracy_parity_allowed") is True)
    )
    master_gap_rollup = _summary(master_gap_closure_rollup_packet or {})
    master_gap_rollup_gate_present = master_gap_closure_rollup_packet is not None
    master_gap_open_ids = [
        _text(item)
        for item in (master_gap_rollup.get("open_gap_ids") or [])
        if _text(item)
    ]
    master_gap_rollup_recorded = (
        _text(master_gap_rollup.get("status"))
        in {"blocked_master_gap_closure_rollup", "master_gap_closure_rollup_complete"}
        and _int(master_gap_rollup.get("gap_count")) >= 1
        and bool(master_gap_rollup.get("execution_enabled") is False)
        and bool(master_gap_rollup.get("external_state_mutated") is False)
    )
    product_ai_architecture_gate_present = (
        product_ai_architecture_gap_packet is not None or product_ai_execution_backlog_packet is not None
    )
    product_ai_architecture = _summary(product_ai_architecture_gap_packet or {})
    product_ai_backlog = _summary(product_ai_execution_backlog_packet or {})
    product_ai_backlog_detail = _primary_backlog_detail(product_ai_execution_backlog_packet or {})
    product_ai_scope_detail = _text(product_ai_backlog.get("scope_closure_detail"))

    product_ready = bool(product.get("pilot_delivery_ready") is True)
    product_claim_allowed = bool(product.get("delivery_ready_claim_allowed") is True)
    product_bundle_validated = bool(product.get("bundle_validation_passed") is True)
    product_architecture_ready = bool(product_architecture.get("architecture_release_ready") is True)
    product_local_architecture_surface_ready = bool(product_architecture.get("local_architecture_surface_ready") is True)
    product_architecture_public_benchmark_ready = bool(product_architecture.get("public_benchmark_validation_ready") is True)
    product_architecture_public_benchmark_status = _text(product_architecture.get("public_benchmark_status"))
    product_architecture_public_benchmark_blocked_suite_count = _int(
        product_architecture.get("public_benchmark_blocked_suite_count")
    )
    product_architecture_public_benchmark_ready_required_suite_count = _int(
        product_architecture.get("public_benchmark_ready_required_suite_count")
    )
    product_architecture_public_benchmark_required_suite_count = _int(
        product_architecture.get("public_benchmark_required_suite_count")
    )
    product_architecture_public_benchmark_suite_materialization_manifest_count = _int(
        product_architecture.get("public_benchmark_suite_materialization_manifest_count")
    )
    product_architecture_public_benchmark_suite_scorecard_row_csv_count = _int(
        product_architecture.get("public_benchmark_suite_scorecard_row_csv_count")
    )
    product_architecture_public_benchmark_suite_threshold_count = _int(
        product_architecture.get("public_benchmark_suite_threshold_count")
    )
    product_architecture_public_benchmark_suite_blocker_count = _int(
        product_architecture.get("public_benchmark_suite_blocker_count")
    )
    product_architecture_public_benchmark_suite_run_command_count = _int(
        product_architecture.get("public_benchmark_suite_run_command_count")
    )
    product_architecture_public_benchmark_suite_materialization_run_command_count = _int(
        product_architecture.get("public_benchmark_suite_materialization_run_command_count")
    )
    product_architecture_public_benchmark_suite_no_external_dependency_count = _int(
        product_architecture.get("public_benchmark_suite_no_external_dependency_count")
    )
    product_architecture_cameo_official_evidence_ready = bool(
        product_architecture.get("cameo_official_validation_evidence_ready") is True
    )
    product_architecture_cameo_receiver_smoke_status = _text(product_architecture.get("cameo_receiver_smoke_status"))
    product_architecture_cameo_api_dependency_status = _text(product_architecture.get("cameo_api_dependency_status"))
    product_architecture_cameo_public_registration_blocker_count = _int(
        product_architecture.get("cameo_public_registration_blocker_count")
    )
    product_architecture_cameo_registration_tokens = list(
        product_architecture.get("cameo_registration_approval_tokens_required") or []
    )
    public_benchmark_required_for_product_release = True
    cameo_live_validation_channel = True
    cameo_live_validation_required_for_product_release = False
    cameo_registration_required_for_product_release = False
    cameo_official_results_required_for_product_release = False
    release_blocked_by_public_benchmark = not product_architecture_public_benchmark_ready
    release_blocked_by_cameo_live_validation = False
    product_commercial_independence_ready = (
        _text(product_independence.get("status")) == "product_commercial_independence_gate_ready"
        and bool(product_independence.get("commercial_independent_product_claim_allowed") is True)
    )

    cameo_evidence_ready = _text(cameo_validation.get("status")) == "cameo_validation_evidence_ready"
    cameo_official_used = bool(cameo_validation.get("official_cameo_results_used") is True)
    cameo_public_registration_allowed = bool(cameo_capability.get("public_registration_allowed") is True)
    cameo_capability_ready = _text(cameo_capability.get("status")) in {
        "cameo_development_capability_preflight_ready",
        "cameo_public_registration_preflight_ready",
    }
    cameo_registration_gate_ready = (
        _text(cameo_registration_gate.get("status")) == "cameo_public_registration_approval_gate_ready"
        and bool(cameo_registration_gate.get("authorized_for_registration_review") is True)
    )

    no_operator_actions = _text(actions.get("status")) == "goal_operator_actions_clear" and _int(actions.get("action_count")) == 0
    rollup_status = _text(rollup.get("status"))
    no_goal_blockers = rollup_status in {
        "goal_readiness_ready",
        "goal_readiness_evidence_ready",
        "goal_readiness_pending_operator_or_external_results",
        "goal_readiness_release_complete_operator_pending",
    } and _int(rollup.get("blocked_lane_count")) == 0
    goal_api_surface_ready = (
        _text(goal_api_surface.get("status")) == "goal_api_surface_contract_ready"
        and bool(goal_api_surface.get("surface_ready") is True)
        and _int(goal_api_surface.get("blocker_count")) == 0
    )
    product_ai_architecture_ready = all(
        [
            bool(product_ai_architecture.get("all_gaps_closed") is True),
            _int(product_ai_architecture.get("open_gap_count")) == 0,
            _int(
                product_ai_backlog.get(
                    "release_blocking_work_item_count",
                    product_ai_backlog.get("work_item_count"),
                )
            )
            == 0,
            bool(product_ai_backlog.get("backlog_clear") is True),
        ]
    )
    cleanup_postcheck_ready = (
        _text(cleanup_postcheck.get("status")) == "cleanup_postcheck_contract_ready"
        and bool(cleanup_postcheck.get("postcheck_contract_ready") is True)
        and _int(cleanup_postcheck.get("row_count")) > 0
        and _int(cleanup_postcheck.get("blocked_row_count")) == 0
    )
    cleanup_completion_ready = (
        _text(cleanup_completion.get("status")) == "cleanup_completion_gate_ready"
        and bool(cleanup_completion.get("cleanup_complete") is True)
    )
    cleanup_completion_blocked_stage_count = _int(cleanup_completion.get("blocked_stage_count"))
    cleanup_completion_total_reclaim_size_gb = round(_float(cleanup_completion.get("total_reclaim_size_gb")), 3)
    cleanup_completion_authorized_reclaim_size_gb = round(_float(cleanup_completion.get("authorized_reclaim_size_gb")), 3)
    cleanup_completion_awaiting_approval_count = _int(
        cleanup_completion.get("approval_awaiting_operator_approval_row_count")
    )
    cleanup_completion_blocked_approval_count = _int(cleanup_completion.get("approval_blocked_row_count"))
    cleanup_completion_ligand_candidate_size_gb = round(_float(cleanup_completion.get("ligand_heavy_candidate_size_gb")), 3)
    cleanup_completion_transition_reclaim_size_gb = round(
        _float(cleanup_completion.get("transition_approval_gated_reclaim_size_gb")), 3
    )
    transition_cleanup_done = (
        _text(transition_cleanup.get("status")) == "transition_cleanup_execution_complete"
        and bool(transition_cleanup.get("external_state_mutated") is True)
    ) or (
        cleanup_completion_ready
        and bool(
            cleanup_completion.get("transition_cleanup_complete") is True
            or cleanup_completion.get("cleanup_complete") is True
        )
    )
    ligand_cleanup_done = (
        _text(ligand_cleanup.get("status")) == "ligand_heavy_cleanup_execution_complete"
        and bool(ligand_cleanup.get("delete_executed") is True)
    ) or (
        cleanup_completion_ready
        and bool(
            cleanup_completion.get("ligand_heavy_cleanup_complete") is True
            or cleanup_completion.get("cleanup_complete") is True
        )
    )
    protected_policy_resolved_by_review = _int(protected_cleanup.get("policy_change_required_count")) == 0
    protected_policy_resolved_by_gate = (
        _text(protected_policy_gate.get("status")) == "protected_cleanup_policy_decision_gate_ready"
        and bool(protected_policy_gate.get("policy_resolved") is True)
        and _int(protected_policy_gate.get("policy_change_requested_row_count")) == 0
        and _int(protected_policy_gate.get("awaiting_policy_decision_row_count")) == 0
        and _int(protected_policy_gate.get("blocked_row_count")) == 0
    )
    protected_policy_resolved = protected_policy_resolved_by_review or protected_policy_resolved_by_gate or (
        cleanup_completion_ready and bool(cleanup_completion.get("protected_policy_resolved") is True)
    )

    rows = [
        _row(
            lane_id="commercial_product_release",
            check="product_architecture_release_ready",
            artifact_path=product_architecture_path,
            observed=(
                f"{_text(product_architecture.get('status')) or 'missing'};"
                f"local_surface={_bool_text(product_local_architecture_surface_ready)};"
                f"architecture_release_ready={_bool_text(product_architecture_ready)};"
                f"public_benchmark_ready={_bool_text(product_architecture_public_benchmark_ready)};"
                f"public_benchmark_status={product_architecture_public_benchmark_status or 'missing'};"
                f"public_benchmark_ready_required_suites={product_architecture_public_benchmark_ready_required_suite_count};"
                f"public_benchmark_required_suites={product_architecture_public_benchmark_required_suite_count};"
                f"public_benchmark_blocked_suites={product_architecture_public_benchmark_blocked_suite_count};"
                f"public_benchmark_suite_materialization_manifest_count={product_architecture_public_benchmark_suite_materialization_manifest_count};"
                f"public_benchmark_suite_scorecard_row_csv_count={product_architecture_public_benchmark_suite_scorecard_row_csv_count};"
                f"public_benchmark_suite_threshold_count={product_architecture_public_benchmark_suite_threshold_count};"
                f"public_benchmark_suite_blocker_count={product_architecture_public_benchmark_suite_blocker_count};"
                f"public_benchmark_suite_run_command_count={product_architecture_public_benchmark_suite_run_command_count};"
                f"public_benchmark_suite_materialization_run_command_count={product_architecture_public_benchmark_suite_materialization_run_command_count};"
                f"public_benchmark_suite_no_external_dependency_count={product_architecture_public_benchmark_suite_no_external_dependency_count};"
                f"cameo_official_evidence_ready={_bool_text(product_architecture_cameo_official_evidence_ready)};"
                f"cameo_receiver_smoke_status={product_architecture_cameo_receiver_smoke_status or 'missing'};"
                f"cameo_api_dependency_status={product_architecture_cameo_api_dependency_status or 'missing'};"
                f"cameo_public_registration_blocker_count={product_architecture_cameo_public_registration_blocker_count};"
                f"cameo_registration_tokens={';'.join(product_architecture_cameo_registration_tokens)}"
            ),
            required="product_architecture_contract_current.json with architecture_release_ready=true",
            passed=product_architecture_ready,
            reason="Full release requires the molecular-structure, ligand-docking, public benchmark, optional CAMEO surface, CASP17, and cleanup architecture contract to be release-ready.",
        ),
        _row(
            lane_id="commercial_product_release",
            check="pilot_delivery_ready",
            artifact_path=product_pilot_path,
            observed=_bool_text(product_ready),
            required="true",
            passed=product_ready,
            reason="Pilot packet must be delivery-ready after approved execution, bundle assembly, and final validation.",
        ),
        _row(
            lane_id="commercial_product_release",
            check="bundle_validation_passed",
            artifact_path=product_pilot_path,
            observed=_bool_text(product_bundle_validated),
            required="true",
            passed=product_bundle_validated,
            reason="Commercial independent-product release requires the final product bundle validator to pass.",
        ),
        _row(
            lane_id="commercial_product_release",
            check="delivery_ready_claim_allowed",
            artifact_path=product_pilot_path,
            observed=_bool_text(product_claim_allowed),
            required="true",
            passed=product_claim_allowed,
            reason="Customer-facing delivery-ready wording must stay blocked until the product bundle is validated.",
        ),
        _row(
            lane_id="commercial_product_release",
            check="commercial_independence_gate_ready",
            artifact_path=product_commercial_independence_path,
            observed=(
                f"{_text(product_independence.get('status')) or 'missing'};"
                f"claim_allowed={_bool_text(product_commercial_independence_ready)}"
            ),
            required="product_commercial_independence_gate_ready",
            passed=product_commercial_independence_ready,
            reason="Commercial independent-product release requires license, reproducible core runtime dependencies, optional-profile separation, deployment evidence, and product API/package surfaces.",
        ),
        _row(
            lane_id="performance_validation",
            check="public_benchmark_validation_ready",
            artifact_path=product_architecture_path,
            observed=(
                f"public_benchmark_status={product_architecture_public_benchmark_status or 'missing'};"
                f"ready_required_suites={product_architecture_public_benchmark_ready_required_suite_count};"
                f"required_suites={product_architecture_public_benchmark_required_suite_count};"
                f"blocked_suites={product_architecture_public_benchmark_blocked_suite_count};"
                f"suite_materialization_manifest_count={product_architecture_public_benchmark_suite_materialization_manifest_count};"
                f"suite_scorecard_row_csv_count={product_architecture_public_benchmark_suite_scorecard_row_csv_count};"
                f"suite_threshold_count={product_architecture_public_benchmark_suite_threshold_count};"
                f"suite_blocker_count={product_architecture_public_benchmark_suite_blocker_count};"
                f"suite_run_command_count={product_architecture_public_benchmark_suite_run_command_count};"
                f"suite_materialization_run_command_count={product_architecture_public_benchmark_suite_materialization_run_command_count};"
                f"suite_no_external_dependency_count={product_architecture_public_benchmark_suite_no_external_dependency_count};"
                f"requires_24h_server={_bool_text(product_architecture.get('public_benchmark_requires_24h_server'))};"
                f"requires_competition_season={_bool_text(product_architecture.get('public_benchmark_requires_competition_season'))};"
                f"requires_paid_vps={_bool_text(product_architecture.get('public_benchmark_requires_paid_vps'))}"
            ),
            required="product_public_benchmark_contract_ready with all required suites passing",
            passed=product_architecture_public_benchmark_ready,
            reason="Architecture performance validation is now based on reproducible public benchmark scorecards rather than CAMEO server registration.",
        ),
        _row(
            lane_id="cleanup_release",
            check="cleanup_operator_actions_resolved",
            artifact_path=cleanup_completion_gate_path if cleanup_completion_gate_packet else operator_action_board_path,
            observed=(
                f"operator_board={_text(actions.get('status')) or 'missing'};"
                f"action_count={_int(actions.get('action_count'))};"
                f"cleanup_completion={_text(cleanup_completion.get('status')) or 'missing'};"
                f"cleanup_complete={_bool_text(cleanup_completion_ready)}"
            ),
            required="cleanup_completion_gate_ready;cleanup_complete=true OR cleanup execution rows complete and action board clear",
            passed=cleanup_completion_ready or (no_operator_actions and transition_cleanup_done and ligand_cleanup_done and protected_policy_resolved),
            reason="Cleanup release cannot be claimed until cleanup-specific approvals, execution, postchecks, and policy resolution are complete.",
        ),
        _row(
            lane_id="cleanup_release",
            check="cleanup_postcheck_contract_ready",
            artifact_path=cleanup_postcheck_contract_path,
            observed=(
                f"{_text(cleanup_postcheck.get('status')) or 'missing'};"
                f"ready={_bool_text(cleanup_postcheck_ready)};"
                f"rows={_int(cleanup_postcheck.get('row_count'))};"
                f"blocked_rows={_int(cleanup_postcheck.get('blocked_row_count'))};"
                f"global_refresh_commands={_int(cleanup_postcheck.get('global_refresh_command_count'))}"
            ),
            required="cleanup_postcheck_contract_ready;postcheck_contract_ready=true;blocked_row_count=0",
            passed=cleanup_postcheck_ready,
            reason="Cleanup release needs row-specific postcheck evidence and refresh commands before cleanup completion can be claimed.",
        ),
        _row(
            lane_id="cleanup_release",
            check="transition_cleanup_complete",
            artifact_path=cleanup_completion_gate_path if cleanup_completion_gate_packet else transition_cleanup_preflight_path,
            observed=(
                f"{_text(transition_cleanup.get('status')) or 'missing'};"
                f"completion_gate={_text(cleanup_completion.get('status')) or 'missing'};"
                f"transition_approval_gated_reclaim_size_gb={cleanup_completion_transition_reclaim_size_gb};"
                f"approval_awaiting={cleanup_completion_awaiting_approval_count};"
                f"approval_blocked={cleanup_completion_blocked_approval_count}"
            ),
            required="transition_cleanup_execution_complete OR cleanup_completion_gate_ready",
            passed=transition_cleanup_done,
            reason="CASP17-heavy transition cleanup must be explicitly executed or resolved before release.",
        ),
        _row(
            lane_id="cleanup_release",
            check="ligand_heavy_cleanup_complete",
            artifact_path=cleanup_completion_gate_path if cleanup_completion_gate_packet else ligand_cleanup_preflight_path,
            observed=(
                f"{_text(ligand_cleanup.get('status')) or 'missing'};"
                f"completion_gate={_text(cleanup_completion.get('status')) or 'missing'};"
                f"ligand_heavy_candidate_size_gb={cleanup_completion_ligand_candidate_size_gb};"
                f"total_reclaim_size_gb={cleanup_completion_total_reclaim_size_gb}"
            ),
            required="ligand_heavy_cleanup_execution_complete OR cleanup_completion_gate_ready",
            passed=ligand_cleanup_done,
            reason="Stale ligand-heavy trajectory payload cleanup must be explicitly executed or resolved before release.",
        ),
        _row(
            lane_id="cleanup_release",
            check="protected_cleanup_policy_resolved",
            artifact_path=cleanup_completion_gate_path if cleanup_completion_gate_packet else (protected_cleanup_policy_decision_gate_path if protected_cleanup_policy_decision_gate_packet else protected_cleanup_review_path),
            observed=(
                f"policy_change_required_count={_int(protected_cleanup.get('policy_change_required_count'))};"
                f"policy_gate_status={_text(protected_policy_gate.get('status')) or 'missing'};"
                f"policy_resolved={bool(protected_policy_gate.get('policy_resolved') is True)};"
                f"known_payload_child_count={_int(protected_policy_gate.get('known_payload_child_count'))};"
                f"known_payload_child_size_gb={round(_float(protected_policy_gate.get('known_payload_child_size_gb')), 3)};"
                f"completion_gate={_text(cleanup_completion.get('status')) or 'missing'}"
            ),
            required="policy_change_required_count=0 OR protected_cleanup_policy_decision_gate_ready OR cleanup_completion_gate_ready",
            passed=protected_policy_resolved,
            reason="Protected heavy payload rows must be kept by explicit policy or promoted by an explicit cleanup-policy change.",
        ),
        _row(
            lane_id="goal_release",
            check="product_release_evidence_ready",
            artifact_path=goal_rollup_path,
            observed=(
                f"{rollup_status or 'missing'};"
                f"blocked_lane_count={_int(rollup.get('blocked_lane_count'))};"
                f"operator_approval_pending_count={_int(rollup.get('operator_approval_pending_count'))};"
                f"external_results_pending_count={_int(rollup.get('external_results_pending_count'))}"
            ),
            required="no blocked rollup lanes; optional/operator/external lanes may remain pending after product release evidence is ready",
            passed=no_goal_blockers,
            reason="Product release evidence may pass while optional CAMEO, cleanup, or execution-operation lanes remain tracked separately for approval or external results.",
        ),
        _row(
            lane_id="goal_release",
            check="goal_api_surface_contract_ready",
            artifact_path=goal_api_surface_contract_path,
            observed=(
                f"{_text(goal_api_surface.get('status')) or 'missing'};"
                f"surface_ready={_bool_text(goal_api_surface_ready)};"
                f"check_count={_int(goal_api_surface.get('check_count'))};"
                f"blocker_count={_int(goal_api_surface.get('blocker_count'))};"
                f"missing_endpoint_count={_int(goal_api_surface.get('missing_endpoint_count'))};"
                f"missing_status_key_count={_int(goal_api_surface.get('missing_status_key_count'))}"
            ),
            required="goal_api_surface_contract_ready;surface_ready=true;blocker_count=0",
            passed=goal_api_surface_ready,
            reason="The top-level local API must expose a verified read-only goal status surface before release can be claimed.",
        ),
    ]
    if goal_bottleneck_briefing_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="goal_bottleneck_briefing_full_commercial_receipts_recorded",
                artifact_path=goal_bottleneck_briefing_path,
                observed=(
                    f"{_text(goal_bottleneck_briefing.get('status')) or 'missing'};"
                    f"completion_audit_release_blocker_bottleneck_count={_int(goal_bottleneck_briefing.get('completion_audit_release_blocker_bottleneck_count'))};"
                    f"full_commercial_evidence_receipt_entry_count={_int(goal_bottleneck_briefing.get('full_commercial_evidence_receipt_entry_count'))};"
                    f"full_commercial_evidence_receipt_operator_input_required_count={_int(goal_bottleneck_briefing.get('full_commercial_evidence_receipt_operator_input_required_count'))};"
                    f"full_commercial_evidence_receipt_current_action_required_count={_int(goal_bottleneck_briefing.get('full_commercial_evidence_receipt_current_action_required_count'))};"
                    f"full_commercial_evidence_receipt_template_required_count={_int(goal_bottleneck_briefing.get('full_commercial_evidence_receipt_template_required_count'))};"
                    f"full_commercial_evidence_receipt_template_present_count={_int(goal_bottleneck_briefing.get('full_commercial_evidence_receipt_template_present_count'))};"
                    f"full_commercial_evidence_receipt_approval_token_count={_int(goal_bottleneck_briefing.get('full_commercial_evidence_receipt_approval_token_count'))};"
                    f"full_commercial_evidence_receipt_source_gate_statuses={_text(goal_bottleneck_briefing.get('full_commercial_evidence_receipt_source_gate_statuses'))};"
                    f"full_commercial_evidence_receipt_required_inputs={_text(goal_bottleneck_briefing.get('full_commercial_evidence_receipt_required_inputs'))};"
                    f"full_commercial_evidence_receipt_approval_tokens={_text(goal_bottleneck_briefing.get('full_commercial_evidence_receipt_approval_tokens'))}"
                ),
                required=(
                    "goal_bottleneck_briefing_ready with R8/R9 completion blockers and full-commercial receipt "
                    "operator handoff summary recorded"
                ),
                passed=goal_bottleneck_full_commercial_receipts_recorded,
                reason=(
                    "The final release decision must preserve the bottleneck briefing's R8/R9 receipt "
                    "handoff summary, not only the downstream matrix diagnostics."
                ),
            )
        )
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="goal_bottleneck_briefing_production_ai_registry_promotion_priority_recorded",
                artifact_path=goal_bottleneck_briefing_path,
                observed=(
                    f"{_text(goal_bottleneck_briefing.get('status')) or 'missing'};"
                    f"production_ai_registry_promotion_priority_status={_text(goal_bottleneck_briefing.get('production_ai_registry_promotion_priority_status'))};"
                    f"production_ai_registry_promotion_priority_packet_ready={_bool_text(bool(goal_bottleneck_briefing.get('production_ai_registry_promotion_priority_packet_ready') is True))};"
                    f"production_ai_registry_promotion_priority_registry_promotion_ready={_bool_text(bool(goal_bottleneck_briefing.get('production_ai_registry_promotion_priority_registry_promotion_ready') is True))};"
                    f"production_ai_registry_promotion_priority_operator_input_required_count={_int(goal_bottleneck_briefing.get('production_ai_registry_promotion_priority_operator_input_required_count'))};"
                    f"production_ai_registry_promotion_priority_blocked_priority_item_count={_int(goal_bottleneck_briefing.get('production_ai_registry_promotion_priority_blocked_priority_item_count'))};"
                    f"production_ai_registry_promotion_priority_missing_gate_count={_int(goal_bottleneck_briefing.get('production_ai_registry_promotion_priority_missing_gate_count'))};"
                    f"production_ai_registry_promotion_priority_missing_gate_ids={';'.join(goal_bottleneck_production_ai_registry_promotion_priority_missing_gate_ids)};"
                    f"production_ai_registry_promotion_priority_top_gate_id={_text(goal_bottleneck_briefing.get('production_ai_registry_promotion_priority_top_gate_id'))};"
                    f"production_ai_registry_promotion_priority_top_priority_bucket={_text(goal_bottleneck_briefing.get('production_ai_registry_promotion_priority_top_priority_bucket'))};"
                    f"production_ai_registry_promotion_priority_model_promoted={_bool_text(bool(goal_bottleneck_briefing.get('production_ai_registry_promotion_priority_model_promoted') is True))};"
                    f"production_ai_registry_promotion_priority_customer_facing_mutation_enabled={_bool_text(bool(goal_bottleneck_briefing.get('production_ai_registry_promotion_priority_customer_facing_mutation_enabled') is True))};"
                    f"production_ai_registry_promotion_priority_external_state_mutated={_bool_text(bool(goal_bottleneck_briefing.get('production_ai_registry_promotion_priority_external_state_mutated') is True))}"
                ),
                required=(
                    "goal_bottleneck_briefing_ready with Production AI registry promotion priority packet "
                    "recorded and top gate trained_model_checkpoint_count_positive preserved"
                ),
                passed=goal_bottleneck_production_ai_registry_promotion_priority_recorded,
                reason=(
                    "The final release decision must preserve the bottleneck briefing's Production AI registry "
                    "promotion top gate so model-promotion work cannot disappear behind restricted-release readiness."
                ),
            )
        )
    if release_source_of_truth_gate_present:
        rows.append(
            _row(
                lane_id="goal_release",
                check="product_release_source_of_truth_ready",
                artifact_path=product_release_source_of_truth_path,
                observed=(
                    f"{_text(release_source_of_truth.get('status')) or 'missing'};"
                    f"ready={_bool_text(release_source_of_truth_ready)};"
                    f"blocker_count={_int(release_source_of_truth.get('blocker_count'))};"
                    f"stale_artifact_count={_int(release_source_of_truth.get('stale_artifact_count'))};"
                    f"readme_drift_count={_int(release_source_of_truth.get('readme_drift_count'))};"
                    f"missing_artifact_count={_int(release_source_of_truth.get('missing_artifact_count'))}"
                ),
                required="product_release_source_of_truth_gate_ready;release_source_of_truth_ready=true;blocker_count=0",
                passed=release_source_of_truth_ready,
                reason="Release must fail when any current artifact is stale against its source dependencies or README metrics drift from current JSON evidence.",
            )
        )
    if full_commercial_matrix_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="product_full_commercial_blocker_evidence_matrix_recorded",
                artifact_path=product_full_commercial_blocker_evidence_matrix_path,
                observed=(
                    f"{_text(full_commercial_matrix.get('status')) or 'missing'};"
                    f"matrix_ready={_bool_text(bool(full_commercial_matrix.get('full_commercial_blocker_evidence_matrix_ready') is True))};"
                    f"release_blocker_visibility_ready={_bool_text(bool(full_commercial_matrix.get('release_blocker_visibility_ready') is True))};"
                    f"matrix_row_count={_int(full_commercial_matrix.get('matrix_row_count'))};"
                    f"blocked_matrix_row_count={_int(full_commercial_matrix.get('blocked_matrix_row_count'))};"
                    f"approval_token_count={_int(full_commercial_matrix.get('approval_token_count'))};"
                    f"first_blocked_release_blocker_id={_text(full_commercial_matrix.get('first_blocked_release_blocker_id'))};"
                    f"first_blocked_evidence_row_id={_text(full_commercial_matrix.get('first_blocked_evidence_row_id'))};"
                    f"first_blocked_evidence_artifact={_text(full_commercial_matrix.get('first_blocked_evidence_artifact'))};"
                    f"first_blocked_expected_evidence_status={_text(full_commercial_matrix.get('first_blocked_expected_evidence_status'))};"
                    f"first_blocked_observed_evidence_status={_text(full_commercial_matrix.get('first_blocked_observed_evidence_status'))};"
                    f"first_blocked_row_blockers={_text(full_commercial_matrix.get('first_blocked_row_blockers'))};"
                    f"scope_receipt_most_common_row_blocker={_text(full_commercial_matrix.get('scope_receipt_most_common_row_blocker'))};"
                    f"engine_receipt_most_common_row_blocker={_text(full_commercial_matrix.get('engine_receipt_most_common_row_blocker'))}"
                ),
                required="R8/R9 full-commercial blocker matrix recorded with release blocker visibility and read-only flags",
                passed=full_commercial_matrix_recorded,
                reason="The final release decision must not hide R8/R9 full-commercial evidence receipt blockers even when restricted release source-of-truth is green.",
            )
        )
    if rollout_smoke_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="product_rollout_execution_smoke_receipt_recorded",
                artifact_path=product_rollout_execution_smoke_receipt_path,
                observed=(
                    f"{_text(rollout_smoke.get('status')) or 'missing'};"
                    f"receipt_ready={_bool_text(bool(rollout_smoke.get('rollout_execution_smoke_receipt_ready') is True))};"
                    f"receipt_csv_present={_bool_text(bool(rollout_smoke.get('receipt_csv_present') is True))};"
                    f"receipt_row_count={_int(rollout_smoke.get('receipt_row_count'))};"
                    f"blocker_count={_int(rollout_smoke.get('blocker_count'))};"
                    f"rollout_executed={_bool_text(bool(rollout_smoke.get('rollout_executed') is True))};"
                    f"external_state_mutated={_bool_text(bool(rollout_smoke.get('external_state_mutated') is True))};"
                    f"pager_provider_contacted={_bool_text(bool(rollout_smoke.get('pager_provider_contacted') is True))};"
                    f"ingress_certificate_verified_live={_bool_text(bool(rollout_smoke.get('ingress_certificate_verified_live') is True))}"
                ),
                required="R4 rollout execution smoke receipt status recorded without this decision gate executing rollout",
                passed=rollout_smoke_recorded,
                reason="The final release decision must not hide whether the separate R4/operator-approved rollout smoke has actually been executed.",
            )
        )
    if master_gap_rollup_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="master_gap_closure_rollup_recorded",
                artifact_path=master_gap_closure_rollup_path,
                observed=(
                    f"{_text(master_gap_rollup.get('status')) or 'missing'};"
                    f"all_gaps_closed={_bool_text(bool(master_gap_rollup.get('all_gaps_closed') is True))};"
                    f"open_gap_count={_int(master_gap_rollup.get('open_gap_count'))};"
                    f"open_gap_ids={';'.join(master_gap_open_ids)};"
                    f"current_primary_open_gap_id={_text(master_gap_rollup.get('current_primary_open_gap_id'))}"
                ),
                required="master gap closure rollup recorded with full-commercial open gap visibility",
                passed=master_gap_rollup_recorded,
                reason="The final release decision must not hide full-commercial SCI-CLAIM or DEPLOY-OPS rollup gaps while restricted release evidence is green.",
            )
        )
    if accuracy_parity_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="accuracy_parity_scorecard_recorded",
                artifact_path=accuracy_parity_scorecard_path,
                observed=(
                    f"{_text(accuracy_parity.get('status')) or 'missing'};"
                    f"overall_commercial_tool_accuracy_parity_allowed="
                    f"{_bool_text(bool(accuracy_parity.get('overall_commercial_tool_accuracy_parity_allowed') is True))};"
                    f"schrodinger_class_claim_allowed="
                    f"{_bool_text(bool(accuracy_parity.get('schrodinger_class_claim_allowed') is True))};"
                    f"row_count={_int(accuracy_parity.get('row_count'))};"
                    f"pass_row_count={_int(accuracy_parity.get('pass_row_count'))};"
                    f"blocked_row_count={_int(accuracy_parity.get('blocked_row_count'))};"
                    f"top_blockers={';'.join(accuracy_parity_top_blockers)};"
                    f"ligand_ranking_status={_text(accuracy_ligand_ranking.get('status'))};"
                    f"ligand_ranking_pr_auc={_float(accuracy_ligand_metrics.get('ranking_pr_auc'))};"
                    f"ligand_ranking_pr_auc_ci_low={_float(accuracy_ligand_metrics.get('ranking_pr_auc_ci_low'))};"
                    f"ligand_ranking_topk_hit_rate={_float(accuracy_ligand_metrics.get('ranking_topk_hit_rate'))};"
                    f"ligand_ranking_blockers={';'.join(accuracy_ligand_blockers)}"
                ),
                required=(
                    "accuracy parity scorecard recorded with frozen-row claim boundary and "
                    "ligand_ranking Schrodinger-class blocker visibility"
                ),
                passed=accuracy_parity_scorecard_recorded,
                reason=(
                    "The final release decision must preserve the broad GPCR ligand-ranking/Schrodinger-class "
                    "parity blocker instead of allowing it to disappear behind restricted local delivery readiness."
                ),
            )
        )
    if science_claim_gap_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="science_claim_promotion_gap_closure_recorded",
                artifact_path=science_claim_promotion_gap_path,
                observed=(
                    f"{_text(science_claim_gap.get('status')) or 'missing'};"
                    f"all_gaps_closed={_bool_text(bool(science_claim_gap.get('all_gaps_closed') is True))};"
                    f"claim_promotion_allowed={_bool_text(bool(science_claim_gap.get('claim_promotion_allowed') is True))};"
                    f"open_gap_count={_int(science_claim_gap.get('open_gap_count'))};"
                    f"open_gap_ids={';'.join(science_claim_open_gap_ids)};"
                    f"current_primary_open_gap_id={science_claim_primary_open_gap_id};"
                    f"primary_open_gap_area={_text(science_claim_primary_open_gap.get('area'))};"
                    f"primary_open_gap_claim_promotion_status={_text(science_claim_primary_open_gap.get('claim_promotion_status'))};"
                    f"primary_open_gap_evidence={_text(science_claim_primary_open_gap.get('evidence'))}"
                ),
                required="science claim promotion gap closure recorded with SCI-GPCR/SCI-OPENMM open-gap visibility",
                passed=science_claim_gap_recorded,
                reason=(
                    "The final release decision must preserve the science-claim sub-gaps underneath "
                    "MASTER:SCI-CLAIM, not only the collapsed master rollup id."
                ),
            )
        )
    if api_customer_flow_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="api_customer_flow_release_evidence_ready",
                artifact_path=api_customer_flow_release_evidence_path,
                observed=(
                    f"{_text(api_customer_flow.get('status')) or 'missing'};"
                    f"formal_release_evidence_ready={_bool_text(api_customer_flow_ready)};"
                    f"clean_install_flow_ready={_bool_text(bool(api_customer_flow.get('clean_install_flow_ready') is True))};"
                    f"result_manifest_signature_verified={_bool_text(bool(api_customer_flow.get('result_manifest_signature_verified') is True))};"
                    f"bundle_validation_ready={_bool_text(bool(api_customer_flow.get('bundle_validation_ready') is True))};"
                    f"restricted_runtime={_bool_text(bool(api_customer_flow.get('restricted_unattended_runtime_ready') is True))};"
                    f"blocker_count={_int(api_customer_flow.get('blocker_count'))}"
                ),
                required="api_customer_flow_release_evidence_ready with live job, signed result manifest, bundle validation, and restricted runtime readiness",
                passed=api_customer_flow_ready,
                reason="Customer-facing API release claims require live end-to-end evidence, not only static wiring or synthetic ledger sync.",
            )
        )
    if product_ai_architecture_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="product_ai_architecture_gap_closure_ready",
                artifact_path=f"{product_ai_architecture_gap_path};{product_ai_execution_backlog_path}",
                observed=(
                    f"ai_gap_status={_text(product_ai_architecture.get('status')) or 'missing'};"
                    f"all_gaps_closed={_bool_text(bool(product_ai_architecture.get('all_gaps_closed') is True))};"
                    f"open_gap_count={_int(product_ai_architecture.get('open_gap_count'))};"
                    f"current_primary_open_gap={_text(product_ai_architecture.get('current_primary_open_gap')) or 'missing'};"
                    f"backlog_clear={_bool_text(bool(product_ai_backlog.get('backlog_clear') is True))};"
                    f"work_item_count={_int(product_ai_backlog.get('work_item_count'))};"
                    f"primary_work_item_id={_text(product_ai_backlog.get('primary_work_item_id')) or 'missing'};"
                    f"{product_ai_backlog_detail}"
                    + (f";{product_ai_scope_detail}" if product_ai_scope_detail else "")
                ),
                required="all_gaps_closed=true;open_gap_count=0;release_blocking_work_item_count=0;optional scope backlog may remain deferred",
                passed=product_ai_architecture_ready,
                reason=(
                    "Commercial release cannot be allowed while the protein-structure plus ligand-docking AI "
                    f"architecture has open gaps or execution backlog items. {product_ai_backlog_detail}"
                    + (f";{product_ai_scope_detail}" if product_ai_scope_detail else "")
                ).strip(),
            )
        )

    blocker_count = sum(1 for row in rows if row["release_blocker"])
    product_release_ready = (
        product_architecture_ready
        and product_ready
        and product_claim_allowed
        and product_bundle_validated
        and product_commercial_independence_ready
    )
    cameo_architecture_validation_ready = cameo_evidence_ready and cameo_official_used and (
        (cameo_public_registration_allowed and cameo_capability_ready) or cameo_registration_gate_ready
    )
    cleanup_objective_ready = (
        cleanup_postcheck_ready
        and transition_cleanup_done
        and ligand_cleanup_done
        and protected_policy_resolved
    )
    release_allowed = blocker_count == 0
    full_commercial_release_blocker_ids = (
        list(full_commercial_matrix.get("expected_release_blocker_ids") or [])
        if full_commercial_matrix_gate_present
        and _int(full_commercial_matrix.get("blocked_matrix_row_count")) > 0
        else []
    )
    if master_gap_rollup_gate_present and master_gap_open_ids:
        full_commercial_release_blocker_ids.extend(
            f"MASTER:{gap_id}" for gap_id in master_gap_open_ids if f"MASTER:{gap_id}" not in full_commercial_release_blocker_ids
        )
    if accuracy_parity_full_commercial_blocked:
        full_commercial_release_blocker_ids.append("ACCURACY:ligand_ranking")
    full_commercial_release_blocker_ids = list(dict.fromkeys(full_commercial_release_blocker_ids))
    primary_full_commercial_release_blocker_id = (
        _text(full_commercial_matrix.get("first_blocked_release_blocker_id"))
        or (f"MASTER:{master_gap_open_ids[0]}" if master_gap_open_ids else "")
    )
    full_commercial_release_allowed = (
        release_allowed
        and (
            not full_commercial_matrix_gate_present
            or bool(full_commercial_matrix.get("full_commercial_blocker_evidence_matrix_ready") is True)
        )
        and (not master_gap_rollup_gate_present or bool(master_gap_rollup.get("all_gaps_closed") is True))
        and (
            not accuracy_parity_gate_present
            or bool(accuracy_parity.get("overall_commercial_tool_accuracy_parity_allowed") is True)
        )
    )
    next_required_items: list[str] = []
    if not product_bundle_validated or not product_ready or not product_claim_allowed:
        next_required_items.append("product bundle validation")
    if not product_commercial_independence_ready:
        next_required_items.append("commercial-independence packaging")
    if not product_architecture_public_benchmark_ready:
        next_required_items.append("public benchmark scorecards")
    if not cleanup_objective_ready:
        next_required_items.append("cleanup completion/postchecks")
    if not no_goal_blockers:
        next_required_items.append("product release evidence rollup")
    if not goal_api_surface_ready:
        next_required_items.append("goal API surface contract")
    if goal_bottleneck_briefing_gate_present and not goal_bottleneck_full_commercial_receipts_recorded:
        next_required_items.append("goal bottleneck full-commercial receipt briefing")
    if (
        goal_bottleneck_briefing_gate_present
        and not goal_bottleneck_production_ai_registry_promotion_priority_recorded
    ):
        next_required_items.append("goal bottleneck Production AI registry promotion priority briefing")
    if release_source_of_truth_gate_present and not release_source_of_truth_ready:
        next_required_items.append("product release source-of-truth gate")
    if full_commercial_matrix_gate_present and not full_commercial_matrix_recorded:
        next_required_items.append("full-commercial blocker evidence matrix")
    if rollout_smoke_gate_present and not rollout_smoke_recorded:
        next_required_items.append("R4 rollout execution smoke receipt")
    if master_gap_rollup_gate_present and not master_gap_rollup_recorded:
        next_required_items.append("master gap closure rollup")
    if accuracy_parity_gate_present and not accuracy_parity_scorecard_recorded:
        next_required_items.append("accuracy parity scorecard")
    if science_claim_gap_gate_present and not science_claim_gap_recorded:
        next_required_items.append("science claim promotion gap closure")
    if api_customer_flow_gate_present and not api_customer_flow_ready:
        next_required_items.append("API customer-flow release evidence")
    if product_ai_architecture_gate_present and not product_ai_architecture_ready:
        next_required_items.append("product AI architecture gap closure")
    next_required_step = (
        "Release gate is clear; archive the evidence packet before customer-facing or public benchmark claims."
        if release_allowed
        else f"Clear {', '.join(next_required_items)} before release."
    )

    summary = {
        "packet_type": "goal_release_decision_gate",
        "status": "goal_release_ready" if release_allowed else "blocked_goal_release_decision",
        "release_allowed": release_allowed,
        "restricted_release_allowed": release_allowed,
        "full_commercial_release_allowed": full_commercial_release_allowed,
        "full_commercial_release_blocker_count": len(full_commercial_release_blocker_ids),
        "full_commercial_release_blocker_ids": full_commercial_release_blocker_ids,
        "primary_full_commercial_release_blocker_id": primary_full_commercial_release_blocker_id,
        "primary_full_commercial_release_blocker": _text(
            full_commercial_matrix.get("first_blocked_evidence_row_id")
        )
        or _text(master_gap_rollup.get("current_primary_open_gap_id")),
        "full_commercial_release_next_required_step": (
            "Full-commercial release is clear."
            if full_commercial_release_allowed
            else (
                _text(full_commercial_matrix.get("next_required_step"))
                or _text(master_gap_rollup.get("current_next_action"))
                or "Close full-commercial release blockers before claiming full-commercial release."
            )
        ),
        "commercial_independent_product_ready": product_release_ready,
        "cameo_architecture_validation_ready": cameo_architecture_validation_ready,
        "cleanup_objective_ready": cleanup_objective_ready,
        "blocker_count": blocker_count,
        "check_count": len(rows),
        "source_product_pilot_status": _text(product.get("status")),
        "source_product_architecture_status": _text(product_architecture.get("status")),
        "product_architecture_local_surface_ready": product_local_architecture_surface_ready,
        "product_architecture_release_ready": product_architecture_ready,
        "product_architecture_public_benchmark_validation_ready": product_architecture_public_benchmark_ready,
        "product_architecture_public_benchmark_status": product_architecture_public_benchmark_status,
        "product_architecture_public_benchmark_required_suite_count": product_architecture_public_benchmark_required_suite_count,
        "product_architecture_public_benchmark_ready_required_suite_count": product_architecture_public_benchmark_ready_required_suite_count,
        "product_architecture_public_benchmark_blocked_suite_count": product_architecture_public_benchmark_blocked_suite_count,
        "product_architecture_public_benchmark_suite_materialization_manifest_count": product_architecture_public_benchmark_suite_materialization_manifest_count,
        "product_architecture_public_benchmark_suite_scorecard_row_csv_count": product_architecture_public_benchmark_suite_scorecard_row_csv_count,
        "product_architecture_public_benchmark_suite_threshold_count": product_architecture_public_benchmark_suite_threshold_count,
        "product_architecture_public_benchmark_suite_blocker_count": product_architecture_public_benchmark_suite_blocker_count,
        "product_architecture_public_benchmark_suite_run_command_count": product_architecture_public_benchmark_suite_run_command_count,
        "product_architecture_public_benchmark_suite_materialization_run_command_count": product_architecture_public_benchmark_suite_materialization_run_command_count,
        "product_architecture_public_benchmark_suite_no_external_dependency_count": product_architecture_public_benchmark_suite_no_external_dependency_count,
        "product_architecture_public_benchmark_requires_24h_server": bool(
            product_architecture.get("public_benchmark_requires_24h_server") is True
        ),
        "product_architecture_public_benchmark_requires_competition_season": bool(
            product_architecture.get("public_benchmark_requires_competition_season") is True
        ),
        "product_architecture_public_benchmark_requires_paid_vps": bool(
            product_architecture.get("public_benchmark_requires_paid_vps") is True
        ),
        "public_benchmark_required_for_product_release": public_benchmark_required_for_product_release,
        "release_blocked_by_public_benchmark": release_blocked_by_public_benchmark,
        "cameo_live_validation_channel": cameo_live_validation_channel,
        "cameo_live_validation_required_for_product_release": cameo_live_validation_required_for_product_release,
        "cameo_registration_required_for_product_release": cameo_registration_required_for_product_release,
        "cameo_official_results_required_for_product_release": cameo_official_results_required_for_product_release,
        "release_blocked_by_cameo_live_validation": release_blocked_by_cameo_live_validation,
        "product_architecture_cameo_official_validation_evidence_ready": product_architecture_cameo_official_evidence_ready,
        "product_architecture_cameo_receiver_smoke_status": product_architecture_cameo_receiver_smoke_status,
        "product_architecture_cameo_api_dependency_status": product_architecture_cameo_api_dependency_status,
        "product_architecture_cameo_public_registration_blocker_count": product_architecture_cameo_public_registration_blocker_count,
        "product_architecture_cameo_registration_approval_token_count": _int(
            product_architecture.get("cameo_registration_approval_token_count")
        ),
        "product_architecture_cameo_registration_approval_tokens_required": product_architecture_cameo_registration_tokens,
        "source_product_commercial_independence_status": _text(product_independence.get("status")),
        "product_commercial_independence_ready": product_commercial_independence_ready,
        "source_cameo_validation_status": _text(cameo_validation.get("status")),
        "source_cameo_capability_status": _text(cameo_capability.get("status")),
        "source_cameo_public_registration_approval_gate_status": _text(cameo_registration_gate.get("status")),
        "cameo_public_registration_authorized_for_registration_review": bool(cameo_registration_gate.get("authorized_for_registration_review") is True),
        "source_goal_rollup_status": _text(rollup.get("status")),
        "source_goal_api_surface_contract_status": _text(goal_api_surface.get("status")),
        "goal_api_surface_ready": goal_api_surface_ready,
        "goal_bottleneck_briefing_gate_present": goal_bottleneck_briefing_gate_present,
        "source_goal_bottleneck_briefing_status": _text(goal_bottleneck_briefing.get("status")),
        "goal_bottleneck_briefing_full_commercial_receipts_recorded": (
            goal_bottleneck_full_commercial_receipts_recorded
            if goal_bottleneck_briefing_gate_present
            else None
        ),
        "goal_bottleneck_briefing_completion_audit_release_blocker_bottleneck_count": _int(
            goal_bottleneck_briefing.get("completion_audit_release_blocker_bottleneck_count")
        ),
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_entry_count": _int(
            goal_bottleneck_briefing.get("full_commercial_evidence_receipt_entry_count")
        ),
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_operator_input_required_count": _int(
            goal_bottleneck_briefing.get("full_commercial_evidence_receipt_operator_input_required_count")
        ),
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_current_action_required_count": _int(
            goal_bottleneck_briefing.get("full_commercial_evidence_receipt_current_action_required_count")
        ),
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_template_required_count": _int(
            goal_bottleneck_briefing.get("full_commercial_evidence_receipt_template_required_count")
        ),
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_template_present_count": _int(
            goal_bottleneck_briefing.get("full_commercial_evidence_receipt_template_present_count")
        ),
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_approval_token_count": _int(
            goal_bottleneck_briefing.get("full_commercial_evidence_receipt_approval_token_count")
        ),
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_source_gate_statuses": _text(
            goal_bottleneck_briefing.get("full_commercial_evidence_receipt_source_gate_statuses")
        ),
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_required_inputs": _text(
            goal_bottleneck_briefing.get("full_commercial_evidence_receipt_required_inputs")
        ),
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_approval_tokens": _text(
            goal_bottleneck_briefing.get("full_commercial_evidence_receipt_approval_tokens")
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_recorded": (
            goal_bottleneck_production_ai_registry_promotion_priority_recorded
            if goal_bottleneck_briefing_gate_present
            else None
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_source_json": _text(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_source_json")
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_status": _text(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_status")
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_packet_ready": bool(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_packet_ready") is True
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_registry_promotion_ready": bool(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_registry_promotion_ready") is True
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_operator_input_required_count": _int(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_operator_input_required_count")
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_blocked_priority_item_count": _int(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_blocked_priority_item_count")
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_missing_gate_count": _int(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_missing_gate_count")
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_missing_gate_ids": (
            goal_bottleneck_production_ai_registry_promotion_priority_missing_gate_ids
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_top_gate_id": _text(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_top_gate_id")
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_top_priority_bucket": _text(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_top_priority_bucket")
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_top_required_input": _text(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_top_required_input")
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_top_acceptance_artifact": _text(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_top_acceptance_artifact")
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_top_verification_command": _text(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_top_verification_command")
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_top_next_operator_step": _text(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_top_next_operator_step")
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_model_promoted": bool(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_model_promoted") is True
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_customer_facing_mutation_enabled": bool(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_customer_facing_mutation_enabled")
            is True
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_external_state_mutated": bool(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_external_state_mutated") is True
        ),
        "product_release_source_of_truth_gate_present": release_source_of_truth_gate_present,
        "product_release_source_of_truth_status": _text(release_source_of_truth.get("status")),
        "product_release_source_of_truth_ready": release_source_of_truth_ready if release_source_of_truth_gate_present else None,
        "product_release_source_of_truth_blocker_count": _int(release_source_of_truth.get("blocker_count")),
        "product_release_source_of_truth_stale_artifact_count": _int(
            release_source_of_truth.get("stale_artifact_count")
        ),
        "product_release_source_of_truth_readme_drift_count": _int(
            release_source_of_truth.get("readme_drift_count")
        ),
        "product_full_commercial_blocker_evidence_matrix_gate_present": full_commercial_matrix_gate_present,
        "product_full_commercial_blocker_evidence_matrix_status": _text(
            full_commercial_matrix.get("status")
        ),
        "product_full_commercial_blocker_evidence_matrix_ready": (
            bool(full_commercial_matrix.get("full_commercial_blocker_evidence_matrix_ready") is True)
            if full_commercial_matrix_gate_present
            else None
        ),
        "product_full_commercial_blocker_evidence_matrix_release_blocker_visibility_ready": bool(
            full_commercial_matrix.get("release_blocker_visibility_ready") is True
        ),
        "product_full_commercial_blocker_evidence_matrix_row_count": _int(
            full_commercial_matrix.get("matrix_row_count")
        ),
        "product_full_commercial_blocker_evidence_matrix_blocked_row_count": _int(
            full_commercial_matrix.get("blocked_matrix_row_count")
        ),
        "product_full_commercial_blocker_evidence_matrix_approval_token_count": _int(
            full_commercial_matrix.get("approval_token_count")
        ),
        "product_full_commercial_blocker_evidence_matrix_first_blocked_release_blocker_id": _text(
            full_commercial_matrix.get("first_blocked_release_blocker_id")
        ),
        "product_full_commercial_blocker_evidence_matrix_first_blocked_evidence_row_id": _text(
            full_commercial_matrix.get("first_blocked_evidence_row_id")
        ),
        "product_full_commercial_blocker_evidence_matrix_first_blocked_evidence_artifact": _text(
            full_commercial_matrix.get("first_blocked_evidence_artifact")
        ),
        "product_full_commercial_blocker_evidence_matrix_first_blocked_expected_evidence_status": _text(
            full_commercial_matrix.get("first_blocked_expected_evidence_status")
        ),
        "product_full_commercial_blocker_evidence_matrix_first_blocked_observed_evidence_status": _text(
            full_commercial_matrix.get("first_blocked_observed_evidence_status")
        ),
        "product_full_commercial_blocker_evidence_matrix_first_blocked_row_blockers": _text(
            full_commercial_matrix.get("first_blocked_row_blockers")
        ),
        "product_full_commercial_blocker_evidence_matrix_scope_receipt_most_common_row_blocker": _text(
            full_commercial_matrix.get("scope_receipt_most_common_row_blocker")
        ),
        "product_full_commercial_blocker_evidence_matrix_engine_receipt_most_common_row_blocker": _text(
            full_commercial_matrix.get("engine_receipt_most_common_row_blocker")
        ),
        "product_rollout_execution_smoke_receipt_gate_present": rollout_smoke_gate_present,
        "product_rollout_execution_smoke_receipt_status": _text(rollout_smoke.get("status")),
        "product_rollout_execution_smoke_receipt_ready": (
            bool(rollout_smoke.get("rollout_execution_smoke_receipt_ready") is True)
            if rollout_smoke_gate_present
            else None
        ),
        "product_rollout_execution_smoke_receipt_csv_present": bool(
            rollout_smoke.get("receipt_csv_present") is True
        ),
        "product_rollout_execution_smoke_receipt_row_count": _int(
            rollout_smoke.get("receipt_row_count")
        ),
        "product_rollout_execution_smoke_receipt_blocker_count": _int(
            rollout_smoke.get("blocker_count")
        ),
        "product_rollout_execution_smoke_receipt_rollout_executed": bool(
            rollout_smoke.get("rollout_executed") is True
        ),
        "product_rollout_execution_smoke_receipt_external_state_mutated": bool(
            rollout_smoke.get("external_state_mutated") is True
        ),
        "product_rollout_execution_smoke_receipt_pager_provider_contacted": bool(
            rollout_smoke.get("pager_provider_contacted") is True
        ),
        "product_rollout_execution_smoke_receipt_ingress_certificate_verified_live": bool(
            rollout_smoke.get("ingress_certificate_verified_live") is True
        ),
        "master_gap_closure_rollup_gate_present": master_gap_rollup_gate_present,
        "master_gap_closure_rollup_status": _text(master_gap_rollup.get("status")),
        "master_gap_closure_rollup_all_gaps_closed": (
            bool(master_gap_rollup.get("all_gaps_closed") is True)
            if master_gap_rollup_gate_present
            else None
        ),
        "master_gap_closure_rollup_open_gap_count": _int(master_gap_rollup.get("open_gap_count")),
        "master_gap_closure_rollup_open_gap_ids": master_gap_open_ids,
        "master_gap_closure_rollup_current_primary_open_gap_id": _text(
            master_gap_rollup.get("current_primary_open_gap_id")
        ),
        "accuracy_parity_scorecard_gate_present": accuracy_parity_gate_present,
        "accuracy_parity_scorecard_status": _text(accuracy_parity.get("status")),
        "accuracy_parity_scorecard_recorded": (
            accuracy_parity_scorecard_recorded if accuracy_parity_gate_present else None
        ),
        "accuracy_parity_scorecard_row_count": _int(accuracy_parity.get("row_count")),
        "accuracy_parity_scorecard_pass_row_count": _int(accuracy_parity.get("pass_row_count")),
        "accuracy_parity_scorecard_restricted_pass_row_count": _int(
            accuracy_parity.get("restricted_pass_row_count")
        ),
        "accuracy_parity_scorecard_blocked_row_count": _int(accuracy_parity.get("blocked_row_count")),
        "accuracy_parity_scorecard_missing_row_count": _int(accuracy_parity.get("missing_row_count")),
        "accuracy_parity_scorecard_top_blocker_count": len(accuracy_parity_top_blockers),
        "accuracy_parity_scorecard_top_blockers": accuracy_parity_top_blockers,
        "accuracy_parity_scorecard_overall_commercial_tool_accuracy_parity_allowed": bool(
            accuracy_parity.get("overall_commercial_tool_accuracy_parity_allowed") is True
        ),
        "accuracy_parity_scorecard_schrodinger_class_claim_allowed": bool(
            accuracy_parity.get("schrodinger_class_claim_allowed") is True
        ),
        "accuracy_parity_scorecard_openmm_class_claim_allowed": bool(
            accuracy_parity.get("openmm_class_claim_allowed") is True
        ),
        "accuracy_parity_scorecard_current_broad_accuracy_parity_estimate_pct": _text(
            accuracy_parity.get("current_broad_accuracy_parity_estimate_pct")
        ),
        "accuracy_parity_scorecard_current_broad_commercial_platform_estimate_pct": _text(
            accuracy_parity.get("current_broad_commercial_platform_estimate_pct")
        ),
        "accuracy_parity_ligand_ranking_status": _text(accuracy_ligand_ranking.get("status")),
        "accuracy_parity_ligand_ranking_claim_promotion_allowed": bool(
            accuracy_ligand_ranking.get("claim_promotion_allowed") is True
        ),
        "accuracy_parity_ligand_ranking_commercial_parity_claim_allowed": bool(
            accuracy_ligand_ranking.get("commercial_parity_claim_allowed") is True
        ),
        "accuracy_parity_ligand_ranking_blocker_count": len(accuracy_ligand_blockers),
        "accuracy_parity_ligand_ranking_blockers": accuracy_ligand_blockers,
        "accuracy_parity_ligand_ranking_pr_auc": _float(
            accuracy_ligand_metrics.get("ranking_pr_auc")
        ),
        "accuracy_parity_ligand_ranking_pr_auc_ci_low": _float(
            accuracy_ligand_metrics.get("ranking_pr_auc_ci_low")
        ),
        "accuracy_parity_ligand_ranking_topk_hit_rate": _float(
            accuracy_ligand_metrics.get("ranking_topk_hit_rate")
        ),
        "accuracy_parity_ligand_ranking_positive_count": _int(
            accuracy_ligand_metrics.get("positive_count")
        ),
        "accuracy_parity_ligand_ranking_score_col_used": _text(
            accuracy_ligand_metrics.get("ranking_score_col_used")
        ),
        "accuracy_parity_ligand_ranking_pr_auc_threshold": _float(
            accuracy_ligand_thresholds.get("ranking_pr_auc_min")
        ),
        "accuracy_parity_ligand_ranking_pr_auc_ci_low_threshold": _float(
            accuracy_ligand_thresholds.get("ranking_pr_auc_ci_low_min")
        ),
        "accuracy_parity_ligand_ranking_topk_hit_rate_threshold": _float(
            accuracy_ligand_thresholds.get("ranking_topk_hit_rate_min")
        ),
        "accuracy_parity_ligand_ranking_next_required_step": _text(
            accuracy_ligand_ranking.get("next_required_step")
        ),
        "science_claim_promotion_gap_closure_gate_present": science_claim_gap_gate_present,
        "science_claim_promotion_gap_closure_status": _text(science_claim_gap.get("status")),
        "science_claim_promotion_gap_closure_recorded": (
            science_claim_gap_recorded if science_claim_gap_gate_present else None
        ),
        "science_claim_promotion_gap_closure_all_gaps_closed": (
            bool(science_claim_gap.get("all_gaps_closed") is True)
            if science_claim_gap_gate_present
            else None
        ),
        "science_claim_promotion_gap_closure_claim_promotion_allowed": bool(
            science_claim_gap.get("claim_promotion_allowed") is True
        ),
        "science_claim_promotion_gap_closure_open_gap_count": _int(
            science_claim_gap.get("open_gap_count")
        ),
        "science_claim_promotion_gap_closure_open_gap_ids": science_claim_open_gap_ids,
        "science_claim_promotion_gap_closure_current_primary_open_gap_id": science_claim_primary_open_gap_id,
        "science_claim_promotion_gap_closure_current_next_action": _text(
            science_claim_gap.get("current_next_action")
        ),
        "science_claim_promotion_gap_closure_primary_open_gap_area": _text(
            science_claim_primary_open_gap.get("area")
        ),
        "science_claim_promotion_gap_closure_primary_open_gap_claim_promotion_status": _text(
            science_claim_primary_open_gap.get("claim_promotion_status")
        ),
        "science_claim_promotion_gap_closure_primary_open_gap_evidence": _text(
            science_claim_primary_open_gap.get("evidence")
        ),
        "science_claim_promotion_gap_closure_primary_open_gap_next_action": _text(
            science_claim_primary_open_gap.get("next_action")
        ),
        "science_claim_promotion_gap_closure_primary_open_gap_release_blocker": bool(
            science_claim_primary_open_gap.get("release_blocker") is True
        ),
        "api_customer_flow_release_evidence_gate_present": api_customer_flow_gate_present,
        "api_customer_flow_release_evidence_status": _text(api_customer_flow.get("status")),
        "api_customer_flow_release_evidence_ready": api_customer_flow_ready if api_customer_flow_gate_present else None,
        "api_customer_flow_result_manifest_signature_verified": bool(
            api_customer_flow.get("result_manifest_signature_verified") is True
        ),
        "api_customer_flow_bundle_validation_ready": bool(api_customer_flow.get("bundle_validation_ready") is True),
        "api_customer_flow_restricted_runtime_ready": bool(
            api_customer_flow.get("restricted_unattended_runtime_ready") is True
        ),
        "api_customer_flow_blocker_count": _int(api_customer_flow.get("blocker_count")),
        "product_ai_architecture_gate_present": product_ai_architecture_gate_present,
        "product_ai_architecture_ready": product_ai_architecture_ready if product_ai_architecture_gate_present else None,
        "product_ai_architecture_open_gap_count": _int(product_ai_architecture.get("open_gap_count")),
        "product_ai_execution_backlog_work_item_count": _int(product_ai_backlog.get("work_item_count")),
        "product_ai_execution_backlog_primary_work_item_id": _text(product_ai_backlog.get("primary_work_item_id")),
        "product_ai_execution_backlog_primary_detail": product_ai_backlog_detail,
        "product_ai_execution_backlog_scope_closure_detail": product_ai_scope_detail,
        "goal_api_surface_check_count": _int(goal_api_surface.get("check_count")),
        "goal_api_surface_blocker_count": _int(goal_api_surface.get("blocker_count")),
        "goal_api_surface_missing_endpoint_count": _int(goal_api_surface.get("missing_endpoint_count")),
        "goal_api_surface_missing_status_key_count": _int(goal_api_surface.get("missing_status_key_count")),
        "source_operator_action_board_status": _text(actions.get("status")),
        "operator_action_count": _int(actions.get("action_count")),
        "operator_approval_required_count": _int(actions.get("approval_required_count")),
        "operator_review_required_count": _int(actions.get("review_required_count")),
        "approval_reclaim_size_gb": round(_float(actions.get("approval_reclaim_size_gb")), 3),
        "product_cli_status_set_status": _text(actions.get("product_cli_status_set_status")),
        "product_cli_approval_token_count": _int(actions.get("product_cli_approval_token_count")),
        "product_cli_operations_blocked_stage_count": _int(actions.get("product_cli_operations_blocked_stage_count")),
        "product_cli_operations_approval_required_stage_count": _int(
            actions.get("product_cli_operations_approval_required_stage_count")
        ),
        "product_cli_capability_surface_ready": bool(actions.get("product_cli_capability_surface_ready") is True),
        "product_cli_operational_quality_ready": bool(actions.get("product_cli_operational_quality_ready") is True),
        "product_operational_quality_ready": bool(
            actions.get("product_cli_operational_quality_ready") is True
            or actions.get("product_release_operations_operational_quality_ready") is True
        ),
        "product_operational_quality_status": _text(
            actions.get("product_release_operations_source_operational_quality_status")
        ),
        "product_operational_quality_blocker_count": _int(
            actions.get("product_release_operations_operational_quality_blocker_count")
        ),
        "product_operational_quality_artifact": _text(
            actions.get("product_release_operations_operational_quality_artifact")
        ),
        "product_cli_architecture_release_ready": bool(actions.get("product_cli_architecture_release_ready") is True),
        "product_cli_commercial_independence_ready": bool(actions.get("product_cli_commercial_independence_ready") is True),
        "product_cli_authorized_for_execution": bool(actions.get("product_cli_authorized_for_execution") is True),
        "product_cli_bundle_validation_passed": bool(actions.get("product_cli_bundle_validation_passed") is True),
        "product_cli_delivery_ready_claim_allowed": bool(actions.get("product_cli_delivery_ready_claim_allowed") is True),
        "cameo_cli_status_set_status": _text(actions.get("cameo_cli_status_set_status")),
        "cameo_cli_approval_token_count": _int(actions.get("cameo_cli_approval_token_count")),
        "cameo_cli_official_result_required": bool(actions.get("cameo_cli_official_result_required") is True),
        "cameo_cli_official_results_accepted_count": _int(actions.get("cameo_cli_official_results_accepted_count")),
        "cameo_cli_evidence_integrity_ready": bool(actions.get("cameo_cli_evidence_integrity_ready") is True),
        "cameo_cli_official_results_pending_honest": bool(
            actions.get("cameo_cli_official_results_pending_honest") is True
        ),
        "cameo_cli_no_local_native_accuracy_substitution": bool(
            actions.get("cameo_cli_no_local_native_accuracy_substitution") is True
        ),
        "cameo_evidence_integrity_ready": bool(
            actions.get("cameo_cli_evidence_integrity_ready") is True
            or actions.get("cameo_validation_operations_evidence_integrity_ready") is True
        ),
        "cameo_evidence_integrity_status": _text(
            actions.get("cameo_validation_operations_evidence_integrity_status")
        ),
        "cameo_evidence_integrity_blocker_count": _int(
            actions.get("cameo_validation_operations_evidence_integrity_blocker_count")
        ),
        "cameo_evidence_integrity_artifact": _text(
            actions.get("cameo_validation_operations_evidence_integrity_artifact")
        ),
        "cameo_official_results_pending_honest": bool(
            actions.get("cameo_cli_official_results_pending_honest") is True
            or actions.get("cameo_validation_operations_official_results_pending_honest") is True
        ),
        "cameo_no_local_native_accuracy_substitution": bool(
            actions.get("cameo_cli_no_local_native_accuracy_substitution") is True
            or actions.get("cameo_validation_operations_no_local_native_accuracy_substitution") is True
        ),
        "cameo_cli_api_install_approval_required": bool(actions.get("cameo_cli_api_install_approval_required") is True),
        "cameo_cli_receiver_smoke_status": _text(actions.get("cameo_cli_receiver_smoke_status")),
        "cameo_cli_public_registration_authorized": bool(actions.get("cameo_cli_public_registration_authorized") is True),
        "cleanup_cli_status_set_status": _text(actions.get("cleanup_cli_status_set_status")),
        "cleanup_cli_approval_token_count": _int(actions.get("cleanup_cli_approval_token_count")),
        "cleanup_cli_approval_reclaim_size_gb": round(_float(actions.get("cleanup_cli_approval_reclaim_size_gb")), 3),
        "cleanup_cli_postcheck_contract_ready": bool(actions.get("cleanup_cli_postcheck_contract_ready") is True),
        "cleanup_cli_postcheck_blocked_row_count": _int(actions.get("cleanup_cli_postcheck_blocked_row_count")),
        "cleanup_cli_protected_payload_size_gb": round(_float(actions.get("cleanup_cli_protected_payload_size_gb")), 3),
        "cleanup_cli_protected_policy_change_required_count": _int(
            actions.get("cleanup_cli_protected_policy_change_required_count")
        ),
        "cleanup_cli_protected_policy_resolved": bool(actions.get("cleanup_cli_protected_policy_resolved") is True),
        "protected_cleanup_payload_size_gb": round(_float(protected_cleanup.get("protected_payload_size_gb")), 3),
        "protected_cleanup_policy_change_required_count": _int(protected_cleanup.get("policy_change_required_count")),
        "protected_cleanup_policy_decision_gate_status": _text(protected_policy_gate.get("status")),
        "protected_cleanup_known_payload_child_count": _int(protected_policy_gate.get("known_payload_child_count")),
        "protected_cleanup_known_payload_child_size_gb": round(_float(protected_policy_gate.get("known_payload_child_size_gb")), 3),
        "protected_cleanup_preservation_sibling_count": _int(protected_policy_gate.get("preservation_sibling_count")),
        "protected_cleanup_policy_change_required_for_deletion_count": _int(
            protected_policy_gate.get("policy_change_required_for_deletion_count")
        ),
        "protected_cleanup_policy_resolved": protected_policy_resolved,
        "cleanup_postcheck_contract_status": _text(cleanup_postcheck.get("status")),
        "cleanup_postcheck_contract_ready": cleanup_postcheck_ready,
        "cleanup_postcheck_row_count": _int(cleanup_postcheck.get("row_count")),
        "cleanup_postcheck_blocked_row_count": _int(cleanup_postcheck.get("blocked_row_count")),
        "cleanup_postcheck_global_refresh_command_count": _int(cleanup_postcheck.get("global_refresh_command_count")),
        "cleanup_completion_gate_status": _text(cleanup_completion.get("status")),
        "cleanup_completion_complete": cleanup_completion_ready,
        "cleanup_completion_blocked_stage_count": cleanup_completion_blocked_stage_count,
        "cleanup_completion_total_reclaim_size_gb": cleanup_completion_total_reclaim_size_gb,
        "cleanup_completion_authorized_reclaim_size_gb": cleanup_completion_authorized_reclaim_size_gb,
        "cleanup_completion_awaiting_approval_count": cleanup_completion_awaiting_approval_count,
        "cleanup_completion_blocked_approval_count": cleanup_completion_blocked_approval_count,
        "cleanup_completion_transition_approval_gated_reclaim_size_gb": cleanup_completion_transition_reclaim_size_gb,
        "cleanup_completion_ligand_heavy_candidate_size_gb": cleanup_completion_ligand_candidate_size_gb,
        "execution_enabled": False,
        "action_executed": False,
        "delete_executed": False,
        "outbound_email_enabled": False,
        "server_registration_mutated": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": next_required_step,
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Goal Release Decision Gate",
        "",
        f"- status: `{s['status']}`",
        f"- release_allowed: `{s['release_allowed']}`",
        f"- restricted_release_allowed: `{s['restricted_release_allowed']}`",
        f"- full_commercial_release_allowed: `{s['full_commercial_release_allowed']}`",
        f"- full_commercial_release_blocker_count: `{s['full_commercial_release_blocker_count']}`",
        f"- full_commercial_release_blocker_ids: `{';'.join(s['full_commercial_release_blocker_ids'])}`",
        f"- primary_full_commercial_release_blocker_id: `{s['primary_full_commercial_release_blocker_id']}`",
        f"- primary_full_commercial_release_blocker: `{s['primary_full_commercial_release_blocker']}`",
        f"- commercial_independent_product_ready: `{s['commercial_independent_product_ready']}`",
        f"- product_architecture_local_surface_ready: `{s['product_architecture_local_surface_ready']}`",
        f"- product_architecture_release_ready: `{s['product_architecture_release_ready']}`",
        f"- product_architecture_public_benchmark_validation_ready: `{s['product_architecture_public_benchmark_validation_ready']}`",
        f"- product_architecture_public_benchmark_status: `{s['product_architecture_public_benchmark_status']}`",
        f"- product_architecture_public_benchmark_required_suite_count: `{s['product_architecture_public_benchmark_required_suite_count']}`",
        f"- product_architecture_public_benchmark_ready_required_suite_count: `{s['product_architecture_public_benchmark_ready_required_suite_count']}`",
        f"- product_architecture_public_benchmark_blocked_suite_count: `{s['product_architecture_public_benchmark_blocked_suite_count']}`",
        f"- product_architecture_public_benchmark_suite_materialization_manifest_count: `{s['product_architecture_public_benchmark_suite_materialization_manifest_count']}`",
        f"- product_architecture_public_benchmark_suite_scorecard_row_csv_count: `{s['product_architecture_public_benchmark_suite_scorecard_row_csv_count']}`",
        f"- product_architecture_public_benchmark_suite_threshold_count: `{s['product_architecture_public_benchmark_suite_threshold_count']}`",
        f"- product_architecture_public_benchmark_suite_blocker_count: `{s['product_architecture_public_benchmark_suite_blocker_count']}`",
        f"- product_architecture_public_benchmark_suite_run_command_count: `{s['product_architecture_public_benchmark_suite_run_command_count']}`",
        f"- product_architecture_public_benchmark_suite_materialization_run_command_count: `{s['product_architecture_public_benchmark_suite_materialization_run_command_count']}`",
        f"- product_architecture_public_benchmark_suite_no_external_dependency_count: `{s['product_architecture_public_benchmark_suite_no_external_dependency_count']}`",
        f"- product_architecture_public_benchmark_requires_24h_server: `{s['product_architecture_public_benchmark_requires_24h_server']}`",
        f"- product_architecture_public_benchmark_requires_competition_season: `{s['product_architecture_public_benchmark_requires_competition_season']}`",
        f"- product_architecture_public_benchmark_requires_paid_vps: `{s['product_architecture_public_benchmark_requires_paid_vps']}`",
        f"- public_benchmark_required_for_product_release: `{s['public_benchmark_required_for_product_release']}`",
        f"- release_blocked_by_public_benchmark: `{s['release_blocked_by_public_benchmark']}`",
        f"- cameo_live_validation_channel: `{s['cameo_live_validation_channel']}`",
        f"- cameo_live_validation_required_for_product_release: `{s['cameo_live_validation_required_for_product_release']}`",
        f"- cameo_registration_required_for_product_release: `{s['cameo_registration_required_for_product_release']}`",
        f"- cameo_official_results_required_for_product_release: `{s['cameo_official_results_required_for_product_release']}`",
        f"- release_blocked_by_cameo_live_validation: `{s['release_blocked_by_cameo_live_validation']}`",
        f"- product_architecture_cameo_official_validation_evidence_ready: `{s['product_architecture_cameo_official_validation_evidence_ready']}`",
        f"- product_architecture_cameo_receiver_smoke_status: `{s['product_architecture_cameo_receiver_smoke_status']}`",
        f"- product_architecture_cameo_api_dependency_status: `{s['product_architecture_cameo_api_dependency_status']}`",
        f"- product_architecture_cameo_public_registration_blocker_count: `{s['product_architecture_cameo_public_registration_blocker_count']}`",
        f"- product_architecture_cameo_registration_approval_token_count: `{s['product_architecture_cameo_registration_approval_token_count']}`",
        f"- product_architecture_cameo_registration_approval_tokens_required: `{';'.join(s['product_architecture_cameo_registration_approval_tokens_required'])}`",
        f"- product_commercial_independence_ready: `{s['product_commercial_independence_ready']}`",
        f"- cameo_architecture_validation_ready: `{s['cameo_architecture_validation_ready']}`",
        f"- cleanup_objective_ready: `{s['cleanup_objective_ready']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- source_goal_api_surface_contract_status: `{s['source_goal_api_surface_contract_status']}`",
        f"- goal_api_surface_ready: `{s['goal_api_surface_ready']}`",
        f"- goal_bottleneck_briefing_gate_present: `{s['goal_bottleneck_briefing_gate_present']}`",
        f"- source_goal_bottleneck_briefing_status: `{s['source_goal_bottleneck_briefing_status']}`",
        f"- goal_bottleneck_briefing_full_commercial_receipts_recorded: `{s['goal_bottleneck_briefing_full_commercial_receipts_recorded']}`",
        f"- goal_bottleneck_briefing_full_commercial_evidence_receipt_entry_count: `{s['goal_bottleneck_briefing_full_commercial_evidence_receipt_entry_count']}`",
        f"- goal_bottleneck_briefing_full_commercial_evidence_receipt_template_present_count: `{s['goal_bottleneck_briefing_full_commercial_evidence_receipt_template_present_count']}`",
        f"- goal_bottleneck_briefing_full_commercial_evidence_receipt_approval_token_count: `{s['goal_bottleneck_briefing_full_commercial_evidence_receipt_approval_token_count']}`",
        f"- goal_bottleneck_briefing_full_commercial_evidence_receipt_required_inputs: `{s['goal_bottleneck_briefing_full_commercial_evidence_receipt_required_inputs']}`",
        f"- goal_bottleneck_briefing_production_ai_registry_promotion_priority_recorded: `{s['goal_bottleneck_briefing_production_ai_registry_promotion_priority_recorded']}`",
        f"- goal_bottleneck_briefing_production_ai_registry_promotion_priority_status: `{s['goal_bottleneck_briefing_production_ai_registry_promotion_priority_status']}`",
        f"- goal_bottleneck_briefing_production_ai_registry_promotion_priority_top_gate_id: `{s['goal_bottleneck_briefing_production_ai_registry_promotion_priority_top_gate_id']}`",
        f"- goal_bottleneck_briefing_production_ai_registry_promotion_priority_missing_gate_count: `{s['goal_bottleneck_briefing_production_ai_registry_promotion_priority_missing_gate_count']}`",
        f"- product_release_source_of_truth_gate_present: `{s['product_release_source_of_truth_gate_present']}`",
        f"- product_release_source_of_truth_status: `{s['product_release_source_of_truth_status']}`",
        f"- product_release_source_of_truth_ready: `{s['product_release_source_of_truth_ready']}`",
        f"- product_release_source_of_truth_blocker_count: `{s['product_release_source_of_truth_blocker_count']}`",
        f"- product_release_source_of_truth_stale_artifact_count: `{s['product_release_source_of_truth_stale_artifact_count']}`",
        f"- product_release_source_of_truth_readme_drift_count: `{s['product_release_source_of_truth_readme_drift_count']}`",
        f"- product_full_commercial_blocker_evidence_matrix_gate_present: `{s['product_full_commercial_blocker_evidence_matrix_gate_present']}`",
        f"- product_full_commercial_blocker_evidence_matrix_status: `{s['product_full_commercial_blocker_evidence_matrix_status']}`",
        f"- product_full_commercial_blocker_evidence_matrix_ready: `{s['product_full_commercial_blocker_evidence_matrix_ready']}`",
        f"- product_full_commercial_blocker_evidence_matrix_release_blocker_visibility_ready: `{s['product_full_commercial_blocker_evidence_matrix_release_blocker_visibility_ready']}`",
        f"- product_full_commercial_blocker_evidence_matrix_row_count: `{s['product_full_commercial_blocker_evidence_matrix_row_count']}`",
        f"- product_full_commercial_blocker_evidence_matrix_blocked_row_count: `{s['product_full_commercial_blocker_evidence_matrix_blocked_row_count']}`",
        f"- product_full_commercial_blocker_evidence_matrix_approval_token_count: `{s['product_full_commercial_blocker_evidence_matrix_approval_token_count']}`",
        f"- product_full_commercial_blocker_evidence_matrix_first_blocked_release_blocker_id: `{s['product_full_commercial_blocker_evidence_matrix_first_blocked_release_blocker_id']}`",
        f"- product_full_commercial_blocker_evidence_matrix_first_blocked_evidence_row_id: `{s['product_full_commercial_blocker_evidence_matrix_first_blocked_evidence_row_id']}`",
        f"- product_full_commercial_blocker_evidence_matrix_first_blocked_evidence_artifact: `{s['product_full_commercial_blocker_evidence_matrix_first_blocked_evidence_artifact']}`",
        f"- product_full_commercial_blocker_evidence_matrix_first_blocked_expected_evidence_status: `{s['product_full_commercial_blocker_evidence_matrix_first_blocked_expected_evidence_status']}`",
        f"- product_full_commercial_blocker_evidence_matrix_first_blocked_observed_evidence_status: `{s['product_full_commercial_blocker_evidence_matrix_first_blocked_observed_evidence_status']}`",
        f"- product_full_commercial_blocker_evidence_matrix_first_blocked_row_blockers: `{s['product_full_commercial_blocker_evidence_matrix_first_blocked_row_blockers']}`",
        f"- product_full_commercial_blocker_evidence_matrix_scope_receipt_most_common_row_blocker: `{s['product_full_commercial_blocker_evidence_matrix_scope_receipt_most_common_row_blocker']}`",
        f"- product_full_commercial_blocker_evidence_matrix_engine_receipt_most_common_row_blocker: `{s['product_full_commercial_blocker_evidence_matrix_engine_receipt_most_common_row_blocker']}`",
        f"- product_rollout_execution_smoke_receipt_gate_present: `{s['product_rollout_execution_smoke_receipt_gate_present']}`",
        f"- product_rollout_execution_smoke_receipt_status: `{s['product_rollout_execution_smoke_receipt_status']}`",
        f"- product_rollout_execution_smoke_receipt_ready: `{s['product_rollout_execution_smoke_receipt_ready']}`",
        f"- product_rollout_execution_smoke_receipt_csv_present: `{s['product_rollout_execution_smoke_receipt_csv_present']}`",
        f"- product_rollout_execution_smoke_receipt_row_count: `{s['product_rollout_execution_smoke_receipt_row_count']}`",
        f"- product_rollout_execution_smoke_receipt_blocker_count: `{s['product_rollout_execution_smoke_receipt_blocker_count']}`",
        f"- product_rollout_execution_smoke_receipt_rollout_executed: `{s['product_rollout_execution_smoke_receipt_rollout_executed']}`",
        f"- product_rollout_execution_smoke_receipt_external_state_mutated: `{s['product_rollout_execution_smoke_receipt_external_state_mutated']}`",
        f"- product_rollout_execution_smoke_receipt_pager_provider_contacted: `{s['product_rollout_execution_smoke_receipt_pager_provider_contacted']}`",
        f"- product_rollout_execution_smoke_receipt_ingress_certificate_verified_live: `{s['product_rollout_execution_smoke_receipt_ingress_certificate_verified_live']}`",
        f"- master_gap_closure_rollup_gate_present: `{s['master_gap_closure_rollup_gate_present']}`",
        f"- master_gap_closure_rollup_status: `{s['master_gap_closure_rollup_status']}`",
        f"- master_gap_closure_rollup_all_gaps_closed: `{s['master_gap_closure_rollup_all_gaps_closed']}`",
        f"- master_gap_closure_rollup_open_gap_count: `{s['master_gap_closure_rollup_open_gap_count']}`",
        f"- master_gap_closure_rollup_open_gap_ids: `{';'.join(s['master_gap_closure_rollup_open_gap_ids'])}`",
        f"- master_gap_closure_rollup_current_primary_open_gap_id: `{s['master_gap_closure_rollup_current_primary_open_gap_id']}`",
        f"- accuracy_parity_scorecard_gate_present: `{s['accuracy_parity_scorecard_gate_present']}`",
        f"- accuracy_parity_scorecard_status: `{s['accuracy_parity_scorecard_status']}`",
        f"- accuracy_parity_scorecard_recorded: `{s['accuracy_parity_scorecard_recorded']}`",
        f"- accuracy_parity_scorecard_row_count: `{s['accuracy_parity_scorecard_row_count']}`",
        f"- accuracy_parity_scorecard_pass_row_count: `{s['accuracy_parity_scorecard_pass_row_count']}`",
        f"- accuracy_parity_scorecard_blocked_row_count: `{s['accuracy_parity_scorecard_blocked_row_count']}`",
        f"- accuracy_parity_scorecard_top_blocker_count: `{s['accuracy_parity_scorecard_top_blocker_count']}`",
        f"- accuracy_parity_scorecard_top_blockers: `{';'.join(s['accuracy_parity_scorecard_top_blockers'])}`",
        f"- accuracy_parity_scorecard_schrodinger_class_claim_allowed: `{s['accuracy_parity_scorecard_schrodinger_class_claim_allowed']}`",
        f"- accuracy_parity_ligand_ranking_status: `{s['accuracy_parity_ligand_ranking_status']}`",
        f"- accuracy_parity_ligand_ranking_pr_auc: `{s['accuracy_parity_ligand_ranking_pr_auc']}`",
        f"- accuracy_parity_ligand_ranking_pr_auc_ci_low: `{s['accuracy_parity_ligand_ranking_pr_auc_ci_low']}`",
        f"- accuracy_parity_ligand_ranking_topk_hit_rate: `{s['accuracy_parity_ligand_ranking_topk_hit_rate']}`",
        f"- accuracy_parity_ligand_ranking_blocker_count: `{s['accuracy_parity_ligand_ranking_blocker_count']}`",
        f"- accuracy_parity_ligand_ranking_blockers: `{';'.join(s['accuracy_parity_ligand_ranking_blockers'])}`",
        f"- science_claim_promotion_gap_closure_gate_present: `{s['science_claim_promotion_gap_closure_gate_present']}`",
        f"- science_claim_promotion_gap_closure_status: `{s['science_claim_promotion_gap_closure_status']}`",
        f"- science_claim_promotion_gap_closure_recorded: `{s['science_claim_promotion_gap_closure_recorded']}`",
        f"- science_claim_promotion_gap_closure_open_gap_count: `{s['science_claim_promotion_gap_closure_open_gap_count']}`",
        f"- science_claim_promotion_gap_closure_open_gap_ids: `{';'.join(s['science_claim_promotion_gap_closure_open_gap_ids'])}`",
        f"- science_claim_promotion_gap_closure_current_primary_open_gap_id: `{s['science_claim_promotion_gap_closure_current_primary_open_gap_id']}`",
        f"- science_claim_promotion_gap_closure_primary_open_gap_claim_promotion_status: `{s['science_claim_promotion_gap_closure_primary_open_gap_claim_promotion_status']}`",
        f"- api_customer_flow_release_evidence_gate_present: `{s['api_customer_flow_release_evidence_gate_present']}`",
        f"- api_customer_flow_release_evidence_status: `{s['api_customer_flow_release_evidence_status']}`",
        f"- api_customer_flow_release_evidence_ready: `{s['api_customer_flow_release_evidence_ready']}`",
        f"- api_customer_flow_result_manifest_signature_verified: `{s['api_customer_flow_result_manifest_signature_verified']}`",
        f"- api_customer_flow_bundle_validation_ready: `{s['api_customer_flow_bundle_validation_ready']}`",
        f"- api_customer_flow_restricted_runtime_ready: `{s['api_customer_flow_restricted_runtime_ready']}`",
        f"- api_customer_flow_blocker_count: `{s['api_customer_flow_blocker_count']}`",
        f"- product_ai_architecture_gate_present: `{s['product_ai_architecture_gate_present']}`",
        f"- product_ai_architecture_ready: `{s['product_ai_architecture_ready']}`",
        f"- product_ai_architecture_open_gap_count: `{s['product_ai_architecture_open_gap_count']}`",
        f"- product_ai_execution_backlog_work_item_count: `{s['product_ai_execution_backlog_work_item_count']}`",
        f"- product_ai_execution_backlog_primary_work_item_id: `{s['product_ai_execution_backlog_primary_work_item_id']}`",
        f"- product_ai_execution_backlog_primary_detail: `{s['product_ai_execution_backlog_primary_detail']}`",
        f"- product_ai_execution_backlog_scope_closure_detail: `{s['product_ai_execution_backlog_scope_closure_detail']}`",
        f"- goal_api_surface_check_count: `{s['goal_api_surface_check_count']}`",
        f"- goal_api_surface_blocker_count: `{s['goal_api_surface_blocker_count']}`",
        f"- operator_action_count: `{s['operator_action_count']}`",
        f"- operator_approval_required_count: `{s['operator_approval_required_count']}`",
        f"- product_cli_status_set_status: `{s['product_cli_status_set_status']}`",
        f"- product_cli_approval_token_count: `{s['product_cli_approval_token_count']}`",
        f"- product_cli_operations_blocked_stage_count: `{s['product_cli_operations_blocked_stage_count']}`",
        f"- product_operational_quality_status: `{s['product_operational_quality_status']}`",
        f"- product_operational_quality_ready: `{s['product_operational_quality_ready']}`",
        f"- product_operational_quality_blocker_count: `{s['product_operational_quality_blocker_count']}`",
        f"- product_cli_architecture_release_ready: `{s['product_cli_architecture_release_ready']}`",
        f"- product_cli_authorized_for_execution: `{s['product_cli_authorized_for_execution']}`",
        f"- product_cli_delivery_ready_claim_allowed: `{s['product_cli_delivery_ready_claim_allowed']}`",
        f"- cameo_cli_status_set_status: `{s['cameo_cli_status_set_status']}`",
        f"- cameo_cli_approval_token_count: `{s['cameo_cli_approval_token_count']}`",
        f"- cameo_cli_official_result_required: `{s['cameo_cli_official_result_required']}`",
        f"- cameo_evidence_integrity_status: `{s['cameo_evidence_integrity_status']}`",
        f"- cameo_evidence_integrity_ready: `{s['cameo_evidence_integrity_ready']}`",
        f"- cameo_evidence_integrity_blocker_count: `{s['cameo_evidence_integrity_blocker_count']}`",
        f"- cameo_official_results_pending_honest: `{s['cameo_official_results_pending_honest']}`",
        f"- cameo_no_local_native_accuracy_substitution: `{s['cameo_no_local_native_accuracy_substitution']}`",
        f"- cameo_cli_receiver_smoke_status: `{s['cameo_cli_receiver_smoke_status']}`",
        f"- cleanup_cli_status_set_status: `{s['cleanup_cli_status_set_status']}`",
        f"- cleanup_cli_approval_token_count: `{s['cleanup_cli_approval_token_count']}`",
        f"- cleanup_cli_approval_reclaim_size_gb: `{s['cleanup_cli_approval_reclaim_size_gb']}`",
        f"- cleanup_cli_postcheck_contract_ready: `{s['cleanup_cli_postcheck_contract_ready']}`",
        f"- cleanup_cli_protected_payload_size_gb: `{s['cleanup_cli_protected_payload_size_gb']}`",
        f"- protected_cleanup_payload_size_gb: `{s['protected_cleanup_payload_size_gb']}`",
        f"- protected_cleanup_known_payload_child_count: `{s['protected_cleanup_known_payload_child_count']}`",
        f"- protected_cleanup_known_payload_child_size_gb: `{s['protected_cleanup_known_payload_child_size_gb']}`",
        f"- protected_cleanup_preservation_sibling_count: `{s['protected_cleanup_preservation_sibling_count']}`",
        f"- cleanup_postcheck_contract_status: `{s['cleanup_postcheck_contract_status']}`",
        f"- cleanup_postcheck_contract_ready: `{s['cleanup_postcheck_contract_ready']}`",
        f"- cleanup_postcheck_row_count: `{s['cleanup_postcheck_row_count']}`",
        f"- cleanup_postcheck_blocked_row_count: `{s['cleanup_postcheck_blocked_row_count']}`",
        f"- cleanup_postcheck_global_refresh_command_count: `{s['cleanup_postcheck_global_refresh_command_count']}`",
        f"- cleanup_completion_gate_status: `{s['cleanup_completion_gate_status']}`",
        f"- cleanup_completion_complete: `{s['cleanup_completion_complete']}`",
        f"- cleanup_completion_blocked_stage_count: `{s['cleanup_completion_blocked_stage_count']}`",
        f"- cleanup_completion_total_reclaim_size_gb: `{s['cleanup_completion_total_reclaim_size_gb']}`",
        f"- cleanup_completion_authorized_reclaim_size_gb: `{s['cleanup_completion_authorized_reclaim_size_gb']}`",
        f"- cleanup_completion_awaiting_approval_count: `{s['cleanup_completion_awaiting_approval_count']}`",
        f"- cleanup_completion_blocked_approval_count: `{s['cleanup_completion_blocked_approval_count']}`",
        f"- cleanup_completion_transition_approval_gated_reclaim_size_gb: `{s['cleanup_completion_transition_approval_gated_reclaim_size_gb']}`",
        f"- cleanup_completion_ligand_heavy_candidate_size_gb: `{s['cleanup_completion_ligand_heavy_candidate_size_gb']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- action_executed: `{s['action_executed']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Checks",
        "",
        "| lane | check | status | observed | required | artifact | reason |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['lane_id']}` | `{row['check']}` | `{row['status']}` | "
            f"`{row['observed']}` | `{row['required']}` | `{row['artifact_path']}` | {row['reason']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a full-goal release decision gate from current local artifacts.")
    parser.add_argument("--product-pilot-json", default=DEFAULT_PRODUCT_PILOT_JSON)
    parser.add_argument("--product-architecture-json", default=DEFAULT_PRODUCT_ARCHITECTURE_JSON)
    parser.add_argument("--product-commercial-independence-json", default=DEFAULT_PRODUCT_COMMERCIAL_INDEPENDENCE_JSON)
    parser.add_argument("--cameo-validation-json", default=DEFAULT_CAMEO_VALIDATION_JSON)
    parser.add_argument("--cameo-capability-json", default=DEFAULT_CAMEO_CAPABILITY_JSON)
    parser.add_argument("--cameo-public-registration-approval-gate-json", default=DEFAULT_CAMEO_PUBLIC_REGISTRATION_APPROVAL_GATE_JSON)
    parser.add_argument("--goal-rollup-json", default=DEFAULT_GOAL_ROLLUP_JSON)
    parser.add_argument("--operator-action-board-json", default=DEFAULT_OPERATOR_ACTION_BOARD_JSON)
    parser.add_argument("--transition-cleanup-preflight-json", default=DEFAULT_TRANSITION_CLEANUP_PREFLIGHT_JSON)
    parser.add_argument("--ligand-cleanup-preflight-json", default=DEFAULT_LIGAND_CLEANUP_PREFLIGHT_JSON)
    parser.add_argument("--protected-cleanup-review-json", default=DEFAULT_PROTECTED_CLEANUP_REVIEW_JSON)
    parser.add_argument("--protected-cleanup-policy-decision-gate-json", default=DEFAULT_PROTECTED_CLEANUP_POLICY_DECISION_GATE_JSON)
    parser.add_argument("--cleanup-postcheck-contract-json", default=DEFAULT_CLEANUP_POSTCHECK_CONTRACT_JSON)
    parser.add_argument("--cleanup-completion-gate-json", default=DEFAULT_CLEANUP_COMPLETION_GATE_JSON)
    parser.add_argument("--goal-api-surface-contract-json", default=DEFAULT_GOAL_API_SURFACE_CONTRACT_JSON)
    parser.add_argument("--goal-bottleneck-briefing-json", default=DEFAULT_GOAL_BOTTLENECK_BRIEFING_JSON)
    parser.add_argument("--product-ai-architecture-gap-json", default=DEFAULT_PRODUCT_AI_ARCHITECTURE_GAP_JSON)
    parser.add_argument("--product-ai-execution-backlog-json", default=DEFAULT_PRODUCT_AI_EXECUTION_BACKLOG_JSON)
    parser.add_argument("--product-release-source-of-truth-json", default=DEFAULT_PRODUCT_RELEASE_SOURCE_OF_TRUTH_JSON)
    parser.add_argument("--api-customer-flow-release-evidence-json", default=DEFAULT_API_CUSTOMER_FLOW_RELEASE_EVIDENCE_JSON)
    parser.add_argument(
        "--product-full-commercial-blocker-evidence-matrix-json",
        default=DEFAULT_PRODUCT_FULL_COMMERCIAL_BLOCKER_EVIDENCE_MATRIX_JSON,
    )
    parser.add_argument(
        "--product-rollout-execution-smoke-receipt-json",
        default=DEFAULT_PRODUCT_ROLLOUT_EXECUTION_SMOKE_RECEIPT_JSON,
    )
    parser.add_argument(
        "--accuracy-parity-scorecard-json",
        default=DEFAULT_ACCURACY_PARITY_SCORECARD_JSON,
    )
    parser.add_argument(
        "--science-claim-promotion-gap-json",
        default=DEFAULT_SCIENCE_CLAIM_PROMOTION_GAP_CLOSURE_JSON,
    )
    parser.add_argument(
        "--master-gap-closure-rollup-json",
        default=DEFAULT_MASTER_GAP_CLOSURE_ROLLUP_JSON,
    )
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_goal_release_decision_gate(
        product_pilot_packet=_read_json_if_present(args.product_pilot_json),
        product_architecture_packet=_read_json_if_present(args.product_architecture_json),
        product_commercial_independence_packet=_read_json_if_present(args.product_commercial_independence_json),
        cameo_validation_packet=_read_json_if_present(args.cameo_validation_json),
        cameo_capability_packet=_read_json_if_present(args.cameo_capability_json),
        cameo_public_registration_approval_gate_packet=_read_json_if_present(args.cameo_public_registration_approval_gate_json),
        goal_rollup_packet=_read_json_if_present(args.goal_rollup_json),
        operator_action_board_packet=_read_json_if_present(args.operator_action_board_json),
        transition_cleanup_preflight_packet=_read_json_if_present(args.transition_cleanup_preflight_json),
        ligand_cleanup_preflight_packet=_read_json_if_present(args.ligand_cleanup_preflight_json),
        protected_cleanup_review_packet=_read_json_if_present(args.protected_cleanup_review_json),
        protected_cleanup_policy_decision_gate_packet=_read_json_if_present(args.protected_cleanup_policy_decision_gate_json),
        cleanup_postcheck_contract_packet=_read_json_if_present(args.cleanup_postcheck_contract_json),
        cleanup_completion_gate_packet=_read_json_if_present(args.cleanup_completion_gate_json),
        goal_api_surface_contract_packet=_read_json_if_present(args.goal_api_surface_contract_json),
        goal_bottleneck_briefing_packet=_read_json_if_present(args.goal_bottleneck_briefing_json),
        product_ai_architecture_gap_packet=_read_json_if_present(args.product_ai_architecture_gap_json),
        product_ai_execution_backlog_packet=_read_json_if_present(args.product_ai_execution_backlog_json),
        product_release_source_of_truth_packet=_read_json_if_present(args.product_release_source_of_truth_json),
        api_customer_flow_release_evidence_packet=_read_json_if_present(
            args.api_customer_flow_release_evidence_json
        ),
        product_full_commercial_blocker_evidence_matrix_packet=_read_json_if_present(
            args.product_full_commercial_blocker_evidence_matrix_json
        ),
        product_rollout_execution_smoke_receipt_packet=_read_json_if_present(
            args.product_rollout_execution_smoke_receipt_json
        ),
        accuracy_parity_scorecard_packet=_read_json_if_present(
            args.accuracy_parity_scorecard_json
        ),
        science_claim_promotion_gap_packet=_read_json_if_present(
            args.science_claim_promotion_gap_json
        ),
        master_gap_closure_rollup_packet=_read_json_if_present(
            args.master_gap_closure_rollup_json
        ),
        product_pilot_path=args.product_pilot_json,
        product_architecture_path=args.product_architecture_json,
        product_commercial_independence_path=args.product_commercial_independence_json,
        cameo_validation_path=args.cameo_validation_json,
        cameo_capability_path=args.cameo_capability_json,
        cameo_public_registration_approval_gate_path=args.cameo_public_registration_approval_gate_json,
        goal_rollup_path=args.goal_rollup_json,
        operator_action_board_path=args.operator_action_board_json,
        transition_cleanup_preflight_path=args.transition_cleanup_preflight_json,
        ligand_cleanup_preflight_path=args.ligand_cleanup_preflight_json,
        protected_cleanup_review_path=args.protected_cleanup_review_json,
        protected_cleanup_policy_decision_gate_path=args.protected_cleanup_policy_decision_gate_json,
        cleanup_postcheck_contract_path=args.cleanup_postcheck_contract_json,
        cleanup_completion_gate_path=args.cleanup_completion_gate_json,
        goal_api_surface_contract_path=args.goal_api_surface_contract_json,
        goal_bottleneck_briefing_path=args.goal_bottleneck_briefing_json,
        product_ai_architecture_gap_path=args.product_ai_architecture_gap_json,
        product_ai_execution_backlog_path=args.product_ai_execution_backlog_json,
        product_release_source_of_truth_path=args.product_release_source_of_truth_json,
        api_customer_flow_release_evidence_path=args.api_customer_flow_release_evidence_json,
        product_full_commercial_blocker_evidence_matrix_path=(
            args.product_full_commercial_blocker_evidence_matrix_json
        ),
        product_rollout_execution_smoke_receipt_path=(
            args.product_rollout_execution_smoke_receipt_json
        ),
        accuracy_parity_scorecard_path=args.accuracy_parity_scorecard_json,
        science_claim_promotion_gap_path=args.science_claim_promotion_gap_json,
        master_gap_closure_rollup_path=args.master_gap_closure_rollup_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
