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
DEFAULT_PRODUCT_AI_ARCHITECTURE_GAP_JSON = "runs/product_ai_architecture_gap_closure_current.json"
DEFAULT_PRODUCT_AI_EXECUTION_BACKLOG_JSON = "runs/product_ai_architecture_execution_backlog_current.json"
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


def _text(value: Any) -> str:
    return str(value or "").strip()


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
    product_ai_architecture_gap_packet: dict[str, Any] | None = None,
    product_ai_execution_backlog_packet: dict[str, Any] | None = None,
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
    product_ai_architecture_gap_path: str = DEFAULT_PRODUCT_AI_ARCHITECTURE_GAP_JSON,
    product_ai_execution_backlog_path: str = DEFAULT_PRODUCT_AI_EXECUTION_BACKLOG_JSON,
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
            bool(product_ai_backlog.get("backlog_clear") is True),
            _int(product_ai_backlog.get("work_item_count")) == 0,
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
    ) or (cleanup_completion_ready and bool(cleanup_completion.get("transition_cleanup_complete") is True))
    ligand_cleanup_done = (
        _text(ligand_cleanup.get("status")) == "ligand_heavy_cleanup_execution_complete"
        and bool(ligand_cleanup.get("delete_executed") is True)
    ) or (cleanup_completion_ready and bool(cleanup_completion.get("ligand_heavy_cleanup_complete") is True))
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
                required="all_gaps_closed=true;open_gap_count=0;backlog_clear=true;work_item_count=0",
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
    parser.add_argument("--product-ai-architecture-gap-json", default=DEFAULT_PRODUCT_AI_ARCHITECTURE_GAP_JSON)
    parser.add_argument("--product-ai-execution-backlog-json", default=DEFAULT_PRODUCT_AI_EXECUTION_BACKLOG_JSON)
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
        product_ai_architecture_gap_packet=_read_json_if_present(args.product_ai_architecture_gap_json),
        product_ai_execution_backlog_packet=_read_json_if_present(args.product_ai_execution_backlog_json),
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
        product_ai_architecture_gap_path=args.product_ai_architecture_gap_json,
        product_ai_execution_backlog_path=args.product_ai_execution_backlog_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
