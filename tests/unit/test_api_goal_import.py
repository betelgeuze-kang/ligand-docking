from __future__ import annotations

import json
from pathlib import Path

import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient

ROOT = Path(__file__).resolve().parents[2]


def _artifact_summary(name: str) -> dict:
    path = ROOT / "runs" / name
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _assert_receipt_fields(
    *,
    status: dict,
    prefix: str,
    artifact: dict,
    path_suffix: str,
    ready_key: str,
    first_blocked_id_source_key: str,
    first_blocked_id_status_key: str,
    required_blocker_count_key: str,
    required_blockers_key: str,
) -> None:
    assert status[f"{prefix}_status"] == artifact.get("status")
    assert status[f"{prefix}_ready"] is (artifact.get(ready_key) is True)
    assert status[f"{prefix}_artifact_path"].endswith(path_suffix)
    assert status[f"{prefix}_csv"] == artifact.get("receipt_csv")
    assert status[f"{prefix}_csv_present"] is (artifact.get("receipt_csv_present") is True)
    assert status[f"{prefix}_approval_token_required"] == artifact.get(
        "approval_token_required"
    )
    assert status[f"{prefix}_receipt_row_count"] == int(
        artifact.get("receipt_row_count") or 0
    )
    assert status[f"{prefix}_pass_row_count"] == int(artifact.get("pass_row_count") or 0)
    assert status[f"{prefix}_blocked_row_count"] == int(
        artifact.get("blocked_row_count") or 0
    )
    assert status[f"{prefix}_blocker_count"] == int(artifact.get("blocker_count") or 0)
    assert status[f"{prefix}_evidence_artifact_present_count"] == int(
        artifact.get("evidence_artifact_present_count") or 0
    )
    assert status[f"{prefix}_evidence_status_verified_count"] == int(
        artifact.get("evidence_status_verified_count") or 0
    )
    assert status[f"{prefix}_{first_blocked_id_status_key}"] == artifact.get(
        first_blocked_id_source_key
    )
    assert status[f"{prefix}_first_blocked_evidence_artifact"] == artifact.get(
        "first_blocked_evidence_artifact"
    )
    assert status[f"{prefix}_first_blocked_expected_evidence_status"] == artifact.get(
        "first_blocked_expected_evidence_status"
    )
    assert status[f"{prefix}_first_blocked_observed_evidence_status"] == artifact.get(
        "first_blocked_observed_evidence_status"
    )
    assert status[f"{prefix}_first_blocked_missing_true_fields"] == artifact.get(
        "first_blocked_missing_true_fields"
    )
    assert status[f"{prefix}_first_blocked_row_blockers"] == artifact.get(
        "first_blocked_row_blockers"
    )
    assert status[f"{prefix}_most_common_row_blocker"] == artifact.get(
        "most_common_row_blocker"
    )
    assert status[f"{prefix}_required_blocker_count"] == int(
        artifact.get(required_blocker_count_key) or 0
    )
    assert status[f"{prefix}_required_blockers"] == artifact.get(required_blockers_key)
    assert status[f"{prefix}_next_required_step"] == artifact.get("next_required_step")
    assert status[f"{prefix}_external_state_mutated"] is (
        artifact.get("external_state_mutated") is True
    )


def _assert_scope_priority_fields(*, status: dict, prefix: str, artifact: dict) -> None:
    status_prefix = f"{prefix}_product_scope_breadth_evidence_priority"

    assert status[f"{status_prefix}_status"] == artifact.get(
        "product_scope_breadth_evidence_priority_status"
    )
    assert status[f"{status_prefix}_packet_ready"] is (
        artifact.get("product_scope_breadth_evidence_priority_packet_ready") is True
    )
    assert status[f"{status_prefix}_open_item_count"] == int(
        artifact.get("product_scope_breadth_evidence_priority_open_item_count") or 0
    )
    assert status[f"{status_prefix}_scientific_evidence_request_count"] == int(
        artifact.get(
            "product_scope_breadth_evidence_priority_scientific_evidence_request_count"
        )
        or 0
    )
    assert status[f"{status_prefix}_top_item_id"] == artifact.get(
        "product_scope_breadth_evidence_priority_top_item_id"
    )
    assert status[f"{status_prefix}_top_domain"] == artifact.get(
        "product_scope_breadth_evidence_priority_top_domain"
    )
    assert status[f"{status_prefix}_top_bucket"] == artifact.get(
        "product_scope_breadth_evidence_priority_top_bucket"
    )
    assert status[f"{status_prefix}_top_required_evidence_type"] == artifact.get(
        "product_scope_breadth_evidence_priority_top_required_evidence_type"
    )
    assert status[f"{status_prefix}_top_review_template_artifact"] == artifact.get(
        "product_scope_breadth_evidence_priority_top_review_template_artifact"
    )
    assert status[f"{status_prefix}_top_apply_gate_artifact"] == artifact.get(
        "product_scope_breadth_evidence_priority_top_apply_gate_artifact"
    )
    assert status[f"{status_prefix}_top_next_step"] == artifact.get(
        "product_scope_breadth_evidence_priority_top_next_step"
    )
    assert status[f"{status_prefix}_scope_promotion_allowed"] is (
        artifact.get("product_scope_breadth_evidence_priority_scope_promotion_allowed")
        is True
    )
    assert status[f"{status_prefix}_authoritative_apply_allowed"] is (
        artifact.get(
            "product_scope_breadth_evidence_priority_authoritative_apply_allowed"
        )
        is True
    )
    assert status[f"{status_prefix}_external_state_mutated"] is (
        artifact.get("product_scope_breadth_evidence_priority_external_state_mutated")
        is True
    )


def _assert_refine_tier_public_benchmark_fields(
    *, observed: dict, artifact: dict
) -> None:
    bool_fields = [
        "refine_tier_public_benchmark_gate_present",
        "refine_tier_public_benchmark_recorded",
        "refine_tier_public_benchmark_input_csv_present",
        "refine_tier_public_benchmark_claim_grade_public_benchmark_ready",
        "refine_tier_public_benchmark_benchmark_metric_surface_ready",
        "refine_tier_public_benchmark_operator_work_order_ready",
        "refine_tier_public_benchmark_external_state_mutated",
        "refine_tier_public_benchmark_work_order_apply_gate_present",
        "refine_tier_public_benchmark_work_order_apply_recorded",
        "refine_tier_public_benchmark_work_order_apply_aggregate_readiness_required",
        "refine_tier_public_benchmark_work_order_apply_apply_ready",
        "refine_tier_public_benchmark_work_order_apply_work_order_csv_present",
        "refine_tier_public_benchmark_work_order_apply_candidate_intake_written",
        "refine_tier_public_benchmark_work_order_apply_candidate_readiness_checked",
        "refine_tier_public_benchmark_work_order_apply_candidate_claim_grade_public_benchmark_ready",
        "refine_tier_public_benchmark_work_order_apply_intake_written",
        "refine_tier_public_benchmark_work_order_apply_write_intake_requested",
        "refine_tier_public_benchmark_work_order_apply_approval_token_present",
        "refine_tier_public_benchmark_work_order_apply_approval_token_accepted",
        "refine_tier_public_benchmark_work_order_apply_external_state_mutated",
    ]
    int_fields = [
        "refine_tier_public_benchmark_row_count",
        "refine_tier_public_benchmark_valid_row_count",
        "refine_tier_public_benchmark_pose_metric_row_count",
        "refine_tier_public_benchmark_pose_metric_pass_count",
        "refine_tier_public_benchmark_free_energy_pair_count",
        "refine_tier_public_benchmark_blocker_count",
        "refine_tier_public_benchmark_min_total_rows_required",
        "refine_tier_public_benchmark_min_pose_rows_required",
        "refine_tier_public_benchmark_min_free_energy_pairs_required",
        "refine_tier_public_benchmark_work_order_row_count",
        "refine_tier_public_benchmark_work_order_apply_work_order_row_count",
        "refine_tier_public_benchmark_work_order_apply_blocked_row_count",
        "refine_tier_public_benchmark_work_order_apply_valid_intake_row_count",
        "refine_tier_public_benchmark_work_order_apply_blocker_count",
        "refine_tier_public_benchmark_work_order_apply_duplicate_benchmark_id_count",
    ]
    text_fields = [
        "refine_tier_public_benchmark_status",
        "refine_tier_public_benchmark_input_csv",
        "refine_tier_public_benchmark_work_order_csv",
        "refine_tier_public_benchmark_write_intake_approval_token_required",
        "refine_tier_public_benchmark_next_required_step",
        "refine_tier_public_benchmark_work_order_apply_status",
        "refine_tier_public_benchmark_work_order_apply_work_order_csv",
        "refine_tier_public_benchmark_work_order_apply_target_intake_csv",
        "refine_tier_public_benchmark_work_order_apply_next_required_step",
    ]
    for field in bool_fields:
        assert observed[field] is (artifact.get(field) is True)
    for field in int_fields:
        assert observed[field] == int(artifact.get(field) or 0)
    for field in text_fields:
        assert observed[field] == artifact.get(field, "")


def test_api_app_imports_with_goal_router() -> None:
    from api.main import app

    paths = {route.path for route in app.routes}
    assert "/goal/status" in paths
    assert "/goal/readiness" in paths
    assert "/goal/actions" in paths
    assert "/goal/operator-intake-kit" in paths
    assert "/goal/release-decision" in paths
    assert "/goal/burndown" in paths
    assert "/goal/bottlenecks" in paths
    assert "/goal/api-contract" in paths

    release_artifact = _artifact_summary("goal_release_decision_gate_current.json")
    readiness_artifact = _artifact_summary("goal_readiness_rollup_current.json")
    burndown_artifact = _artifact_summary("goal_release_burndown_work_order_current.json")
    bottlenecks_artifact = _artifact_summary("goal_bottleneck_briefing_current.json")
    actions_artifact = _artifact_summary("goal_operator_action_board_current.json")
    intake_artifact = _artifact_summary("goal_operator_intake_kit_current/manifest.json")
    api_contract_artifact = _artifact_summary("goal_api_surface_contract_current.json")
    product_goal_completion_artifact = _artifact_summary("product_goal_completion_audit_current.json")
    handoff_artifact = _artifact_summary("product_commercial_readiness_handoff_bundle_current.json")
    cameo_fetch_artifact = _artifact_summary("cameo_official_result_fetch_preflight_current.json")
    scope_receipt_artifact = _artifact_summary("product_scope_breadth_evidence_receipt_current.json")
    engine_receipt_artifact = _artifact_summary(
        "engine_refinement_claim_evidence_receipt_current.json"
    )
    full_matrix_artifact = _artifact_summary(
        "product_full_commercial_blocker_evidence_matrix_current.json"
    )

    client = TestClient(app)
    status = client.get("/goal/status").json()
    readiness = client.get("/goal/readiness").json()
    actions = client.get("/goal/actions").json()
    intake_kit = client.get("/goal/operator-intake-kit").json()
    release = client.get("/goal/release-decision").json()
    burndown = client.get("/goal/burndown").json()
    bottlenecks = client.get("/goal/bottlenecks").json()
    api_contract = client.get("/goal/api-contract").json()

    assert status["status"] == release_artifact.get("status")
    assert status["release_allowed"] is (release_artifact.get("release_allowed") is True)
    assert status["restricted_release_allowed"] is (
        release_artifact.get("restricted_release_allowed") is True
    )
    assert status["full_commercial_release_allowed"] is (
        release_artifact.get("full_commercial_release_allowed") is True
    )
    assert status["release_blocker_count"] == int(release_artifact.get("blocker_count") or 0)
    assert status["release_decision_status"] == release_artifact.get("status")
    assert status["readiness_status"] == readiness_artifact.get("status")
    assert status["release_burndown_status"] == burndown_artifact.get("status")
    assert status["commercial_independent_product_ready"] is True
    assert status["cleanup_objective_ready"] is True
    assert status["goal_api_surface_ready"] is True
    assert status["bottleneck_count"] == int(bottlenecks_artifact.get("bottleneck_count") or 0)
    primary_source = (
        bottlenecks_artifact
        if int(bottlenecks_artifact.get("current_bottleneck_count") or bottlenecks_artifact.get("bottleneck_count") or 0)
        and bottlenecks_artifact.get("primary_action_id")
        else intake_artifact
    )
    assert status["primary_action_id"] == primary_source.get("primary_action_id")
    assert status["primary_action_status"] == primary_source.get("primary_action_status")
    assert status["primary_action_required_input"] == primary_source.get("primary_action_required_input")
    assert status["primary_action_command"] == primary_source.get("primary_action_command")
    assert status["release_complete_vs_operator_pending_lane"] == readiness_artifact.get(
        "release_complete_vs_operator_pending_lane"
    )
    expected_full_commercial_blockers = [
        "R8_full_scope_claim_closure",
        "R9_engine_refinement_claim_promotion",
        "MASTER:SCI-CLAIM",
        "ACCURACY:ligand_ranking",
    ]
    assert status["expected_full_commercial_release_blocker_ids"] == expected_full_commercial_blockers
    assert status["full_commercial_release_blocker_ids"] == release_artifact.get(
        "full_commercial_release_blocker_ids"
    )
    assert status["full_commercial_release_blocker_count"] == int(
        release_artifact.get("full_commercial_release_blocker_count") or 0
    )
    assert status["missing_full_commercial_release_blocker_ids"] == []
    assert status["full_commercial_release_blocker_visibility_ready"] is True
    assert status["primary_full_commercial_release_blocker_id"] == release_artifact.get(
        "primary_full_commercial_release_blocker_id"
    )
    assert status["primary_full_commercial_release_blocker"] == release_artifact.get(
        "primary_full_commercial_release_blocker"
    )
    assert status["full_commercial_release_next_required_step"] == release_artifact.get(
        "full_commercial_release_next_required_step"
    )
    assert status["master_gap_closure_rollup_status"] == release_artifact.get(
        "master_gap_closure_rollup_status"
    )
    assert status["master_gap_closure_rollup_recorded"] is (
        release_artifact.get("master_gap_closure_rollup_recorded") is True
    )
    assert status["master_gap_closure_rollup_open_gap_count"] == int(
        release_artifact.get("master_gap_closure_rollup_open_gap_count") or 0
    )
    assert status["master_gap_closure_rollup_open_gap_ids"] == release_artifact.get(
        "master_gap_closure_rollup_open_gap_ids"
    )
    assert status["master_gap_closure_rollup_closed_gap_count"] == int(
        release_artifact.get("master_gap_closure_rollup_closed_gap_count") or 0
    )
    assert status["master_gap_closure_rollup_closed_gap_ids"] == release_artifact.get(
        "master_gap_closure_rollup_closed_gap_ids"
    )
    assert status["master_gap_closure_rollup_release_blocker_row_count"] == int(
        release_artifact.get("master_gap_closure_rollup_release_blocker_row_count") or 0
    )
    assert status["master_gap_closure_rollup_science_claim_rollup_status"] == release_artifact.get(
        "master_gap_closure_rollup_science_claim_rollup_status"
    )
    assert status["master_gap_closure_rollup_science_claim_release_blocker"] is (
        release_artifact.get("master_gap_closure_rollup_science_claim_release_blocker") is True
    )
    assert status["science_claim_promotion_gap_closure_status"] == release_artifact.get(
        "science_claim_promotion_gap_closure_status"
    )
    assert status["science_claim_promotion_gap_closure_recorded"] is (
        release_artifact.get("science_claim_promotion_gap_closure_recorded") is True
    )
    assert status["science_claim_promotion_gap_closure_open_gap_count"] == int(
        release_artifact.get("science_claim_promotion_gap_closure_open_gap_count") or 0
    )
    assert status["science_claim_promotion_gap_closure_open_gap_ids"] == release_artifact.get(
        "science_claim_promotion_gap_closure_open_gap_ids"
    )
    assert status["science_claim_promotion_gap_closure_closed_gap_count"] == int(
        release_artifact.get("science_claim_promotion_gap_closure_closed_gap_count") or 0
    )
    assert status["science_claim_promotion_gap_closure_closed_gap_ids"] == release_artifact.get(
        "science_claim_promotion_gap_closure_closed_gap_ids"
    )
    assert status["science_claim_promotion_gap_closure_release_blocker_row_count"] == int(
        release_artifact.get("science_claim_promotion_gap_closure_release_blocker_row_count") or 0
    )
    assert status["science_claim_promotion_gap_closure_current_primary_open_gap_id"] == (
        release_artifact.get("science_claim_promotion_gap_closure_current_primary_open_gap_id")
    )
    assert status[
        "science_claim_promotion_gap_closure_primary_open_gap_claim_promotion_status"
    ] == release_artifact.get(
        "science_claim_promotion_gap_closure_primary_open_gap_claim_promotion_status"
    )
    assert status["science_claim_promotion_gap_closure_gpcr_claim_promotion_status"] == (
        release_artifact.get("science_claim_promotion_gap_closure_gpcr_claim_promotion_status")
    )
    assert status["science_claim_promotion_gap_closure_gpcr_release_blocker"] is (
        release_artifact.get("science_claim_promotion_gap_closure_gpcr_release_blocker") is True
    )
    assert status["science_claim_promotion_gap_closure_openmm_claim_promotion_status"] == (
        release_artifact.get("science_claim_promotion_gap_closure_openmm_claim_promotion_status")
    )
    assert status["science_claim_promotion_gap_closure_openmm_release_blocker"] is (
        release_artifact.get("science_claim_promotion_gap_closure_openmm_release_blocker") is True
    )
    assert status["accuracy_parity_scorecard_status"] == release_artifact.get(
        "accuracy_parity_scorecard_status", ""
    )
    assert status["accuracy_parity_scorecard_recorded"] is (
        release_artifact.get("accuracy_parity_scorecard_recorded") is True
    )
    assert status["accuracy_parity_scorecard_top_blocker_count"] == int(
        release_artifact.get("accuracy_parity_scorecard_top_blocker_count") or 0
    )
    assert status["accuracy_parity_scorecard_top_blockers"] == release_artifact.get(
        "accuracy_parity_scorecard_top_blockers", []
    )
    assert status["accuracy_parity_ligand_ranking_status"] == release_artifact.get(
        "accuracy_parity_ligand_ranking_status", ""
    )
    assert status["accuracy_parity_ligand_ranking_blocker_count"] == int(
        release_artifact.get("accuracy_parity_ligand_ranking_blocker_count") or 0
    )
    assert status["accuracy_parity_ligand_ranking_blockers"] == release_artifact.get(
        "accuracy_parity_ligand_ranking_blockers", []
    )
    assert status["accuracy_parity_ligand_ranking_score_col_used"] == release_artifact.get(
        "accuracy_parity_ligand_ranking_score_col_used", ""
    )
    assert status["api_runner_profile_promotion_operator_receipt_status"] == release_artifact.get(
        "api_runner_profile_promotion_operator_receipt_status", ""
    )
    assert status["product_quality_gate_verification_status"] == release_artifact.get(
        "product_quality_gate_verification_status", ""
    )
    assert status["product_quality_gate_verification_recorded"] is (
        release_artifact.get("product_quality_gate_verification_recorded") is True
    )
    assert status["product_quality_gate_verification_ready"] is (
        release_artifact.get("product_quality_gate_verification_ready") is True
    )
    assert status["product_quality_gate_verification_source_contract_status"] == release_artifact.get(
        "product_quality_gate_verification_source_contract_status", ""
    )
    assert status["product_quality_gate_verification_check_count"] == int(
        release_artifact.get("product_quality_gate_verification_check_count") or 0
    )
    assert status["product_quality_gate_verification_pass_count"] == int(
        release_artifact.get("product_quality_gate_verification_pass_count") or 0
    )
    assert status["product_quality_gate_verification_blocker_count"] == int(
        release_artifact.get("product_quality_gate_verification_blocker_count") or 0
    )
    assert status["product_quality_gate_verification_execution_enabled"] is (
        release_artifact.get("product_quality_gate_verification_execution_enabled") is True
    )
    assert status["product_quality_gate_verification_external_state_mutated"] is (
        release_artifact.get("product_quality_gate_verification_external_state_mutated") is True
    )
    assert status["product_pose_sampling_readiness_status"] == release_artifact.get(
        "product_pose_sampling_readiness_status", ""
    )
    assert status["product_pose_sampling_readiness_recorded"] is (
        release_artifact.get("product_pose_sampling_readiness_recorded") is True
    )
    assert status["product_pose_sampling_readiness_ready"] is (
        release_artifact.get("product_pose_sampling_readiness_ready") is True
    )
    assert status["product_pose_sampling_readiness_pose_generation_contract_ready"] is (
        release_artifact.get("product_pose_sampling_readiness_pose_generation_contract_ready") is True
    )
    assert status["product_pose_sampling_readiness_pose_count"] == int(
        release_artifact.get("product_pose_sampling_readiness_pose_count") or 0
    )
    assert status["product_pose_sampling_readiness_cluster_count"] == int(
        release_artifact.get("product_pose_sampling_readiness_cluster_count") or 0
    )
    assert status["product_pose_sampling_readiness_cross_docking_pose_count"] == int(
        release_artifact.get("product_pose_sampling_readiness_cross_docking_pose_count") or 0
    )
    assert status["product_pose_sampling_readiness_claim_grade_pose_accuracy_ready"] is (
        release_artifact.get("product_pose_sampling_readiness_claim_grade_pose_accuracy_ready")
        is True
    )
    assert status["product_pose_sampling_readiness_docking_results_emitted"] is (
        release_artifact.get("product_pose_sampling_readiness_docking_results_emitted") is True
    )
    assert status["product_pose_sampling_readiness_execution_enabled"] is (
        release_artifact.get("product_pose_sampling_readiness_execution_enabled") is True
    )
    assert status["product_pose_sampling_readiness_external_state_mutated"] is (
        release_artifact.get("product_pose_sampling_readiness_external_state_mutated") is True
    )
    assert status["product_ledger_privacy_scan_status"] == release_artifact.get(
        "product_ledger_privacy_scan_status", ""
    )
    assert status["product_ledger_privacy_scan_recorded"] is (
        release_artifact.get("product_ledger_privacy_scan_recorded") is True
    )
    assert status["product_ledger_privacy_scan_ready"] is (
        release_artifact.get("product_ledger_privacy_scan_ready") is True
    )
    assert status["product_ledger_privacy_scan_scan_file_count"] == int(
        release_artifact.get("product_ledger_privacy_scan_scan_file_count") or 0
    )
    assert status["product_ledger_privacy_scan_scan_glob_count"] == int(
        release_artifact.get("product_ledger_privacy_scan_scan_glob_count") or 0
    )
    assert status["product_ledger_privacy_scan_pass_count"] == int(
        release_artifact.get("product_ledger_privacy_scan_pass_count") or 0
    )
    assert status["product_ledger_privacy_scan_leak_count"] == int(
        release_artifact.get("product_ledger_privacy_scan_leak_count") or 0
    )
    assert status["product_ledger_privacy_scan_invalid_json_count"] == int(
        release_artifact.get("product_ledger_privacy_scan_invalid_json_count") or 0
    )
    assert status["product_ledger_privacy_scan_execution_enabled"] is (
        release_artifact.get("product_ledger_privacy_scan_execution_enabled") is True
    )
    assert status["product_ledger_privacy_scan_external_state_mutated"] is (
        release_artifact.get("product_ledger_privacy_scan_external_state_mutated") is True
    )
    _assert_refine_tier_public_benchmark_fields(
        observed=status,
        artifact=release_artifact,
    )
    assert status["api_runner_profile_promotion_operator_receipt_recorded"] is (
        release_artifact.get("api_runner_profile_promotion_operator_receipt_recorded") is True
    )
    assert status["api_runner_profile_promotion_operator_receipt_profile_count"] == int(
        release_artifact.get("api_runner_profile_promotion_operator_receipt_profile_count") or 0
    )
    assert status["api_runner_profile_promotion_operator_receipt_blocked_row_count"] == int(
        release_artifact.get("api_runner_profile_promotion_operator_receipt_blocked_row_count") or 0
    )
    assert status["api_runner_profile_promotion_operator_receipt_first_blocked_profile_id"] == (
        release_artifact.get(
            "api_runner_profile_promotion_operator_receipt_first_blocked_profile_id", ""
        )
    )
    assert status["api_runner_profile_promotion_operator_receipt_first_blocked_row_blocker"] == (
        release_artifact.get(
            "api_runner_profile_promotion_operator_receipt_first_blocked_row_blocker", ""
        )
    )
    assert status["api_runner_profile_promotion_operator_receipt_runner_executed"] is (
        release_artifact.get("api_runner_profile_promotion_operator_receipt_runner_executed") is True
    )
    assert status["product_goal_release_blocker_fail_count"] == int(
        actions_artifact.get("product_goal_release_blocker_fail_count") or 0
    )
    assert status["product_goal_release_blocker_requirement_ids"] == actions_artifact.get(
        "product_goal_release_blocker_requirement_ids"
    )
    assert status["product_goal_primary_release_blocker_requirement_id"] == actions_artifact.get(
        "product_goal_primary_release_blocker_requirement_id"
    )
    assert status["product_goal_primary_release_blocker_tier"] == actions_artifact.get(
        "product_goal_primary_release_blocker_tier"
    )
    assert status["product_goal_primary_release_blocker"] == actions_artifact.get(
        "product_goal_primary_release_blocker"
    )
    assert status["product_goal_primary_release_blocker_next_command"] == actions_artifact.get(
        "product_goal_primary_release_blocker_next_command"
    )
    assert status["primary_release_blocker_action_id"] == actions_artifact.get(
        "primary_release_blocker_action_id"
    )
    assert status["primary_release_blocker_action_status"] == actions_artifact.get(
        "primary_release_blocker_action_status"
    )
    assert status["primary_release_blocker_action_required_input"] == actions_artifact.get(
        "primary_release_blocker_action_required_input"
    )
    assert status["primary_release_blocker_action_artifact_path"] == actions_artifact.get(
        "primary_release_blocker_action_artifact_path"
    )
    assert status["primary_release_blocker_action_recommended_action"] == actions_artifact.get(
        "primary_release_blocker_action_recommended_action"
    )
    assert status["product_accuracy_parity_action_count"] == int(
        actions_artifact.get("product_accuracy_parity_action_count") or 0
    )
    assert status["product_accuracy_parity_ligand_ranking_action_id"] == (
        "product_accuracy_parity:repair_ligand_ranking_parity"
    )
    assert status["product_accuracy_parity_ligand_ranking_action_present"] is (
        actions_artifact.get("product_accuracy_parity_ligand_ranking_action_present") is True
    )
    assert status["product_accuracy_parity_scorecard_status"] == actions_artifact.get(
        "product_accuracy_parity_scorecard_status"
    )
    assert status["product_accuracy_parity_ligand_ranking_action_status"] == actions_artifact.get(
        "product_accuracy_parity_ligand_ranking_status"
    )
    assert status["product_accuracy_parity_ligand_ranking_blocker_count"] == int(
        actions_artifact.get("product_accuracy_parity_ligand_ranking_blocker_count") or 0
    )
    assert status["product_accuracy_parity_ligand_ranking_blockers"] == actions_artifact.get(
        "product_accuracy_parity_ligand_ranking_blockers"
    )
    assert status["product_accuracy_parity_ligand_ranking_pr_auc"] == float(
        actions_artifact.get("product_accuracy_parity_ligand_ranking_pr_auc") or 0.0
    )
    assert status["product_accuracy_parity_ligand_ranking_pr_auc_ci_low"] == float(
        actions_artifact.get("product_accuracy_parity_ligand_ranking_pr_auc_ci_low") or 0.0
    )
    assert status["product_accuracy_parity_ligand_ranking_topk_hit_rate"] == float(
        actions_artifact.get("product_accuracy_parity_ligand_ranking_topk_hit_rate") or 0.0
    )
    assert status["product_accuracy_parity_ligand_ranking_next_required_step"] == actions_artifact.get(
        "product_accuracy_parity_ligand_ranking_next_required_step"
    )
    assert status["product_accuracy_parity_scorecard_json"] == actions_artifact.get(
        "product_accuracy_parity_scorecard_json"
    )
    assert status["production_ai_checkpoint_registry_promotion_required_gate_ids"] == (
        product_goal_completion_artifact.get(
            "production_ai_checkpoint_registry_promotion_required_gate_ids"
        )
    )
    assert status["production_ai_checkpoint_registry_promotion_missing_gate_ids"] == (
        product_goal_completion_artifact.get(
            "production_ai_checkpoint_registry_promotion_missing_gate_ids"
        )
    )
    assert status["production_ai_checkpoint_registry_promotion_missing_gate_count"] == int(
        product_goal_completion_artifact.get(
            "production_ai_checkpoint_registry_promotion_missing_gate_count"
        )
        or 0
    )
    assert status["production_ai_checkpoint_registry_promotion_upstream_acceptance_ready"] is (
        product_goal_completion_artifact.get(
            "production_ai_checkpoint_registry_promotion_upstream_acceptance_ready"
        )
        is True
    )
    assert status["production_ai_checkpoint_registry_promotion_currently_satisfied"] is (
        product_goal_completion_artifact.get(
            "production_ai_checkpoint_registry_promotion_currently_satisfied"
        )
        is True
    )
    assert status["production_ai_checkpoint_actionable_operator_completion_packet_ready"] is (
        product_goal_completion_artifact.get(
            "production_ai_checkpoint_actionable_operator_completion_packet_ready"
        )
        is True
    )
    assert status["production_ai_checkpoint_actionable_operator_completion_artifact_id"] == (
        product_goal_completion_artifact.get(
            "production_ai_checkpoint_actionable_operator_completion_artifact_id"
        )
    )
    assert status[
        "production_ai_checkpoint_actionable_operator_completion_required_fields_or_columns"
    ] == product_goal_completion_artifact.get(
        "production_ai_checkpoint_actionable_operator_completion_required_fields_or_columns"
    )
    assert status[
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_commands"
    ] == product_goal_completion_artifact.get(
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_commands"
    )
    assert status[
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_command_count"
    ] == int(
        product_goal_completion_artifact.get(
            "production_ai_checkpoint_actionable_operator_completion_diagnostic_command_count"
        )
        or 0
    )
    assert status["production_ai_checkpoint_actionable_operator_completion_completion_rule"] == (
        product_goal_completion_artifact.get(
            "production_ai_checkpoint_actionable_operator_completion_completion_rule"
        )
    )
    assert status["production_ai_checkpoint_actionable_operator_completion_next_action"] == (
        product_goal_completion_artifact.get(
            "production_ai_checkpoint_actionable_operator_completion_next_action"
        )
    )
    assert status["completion_audit_release_blocker_bottleneck_count"] == int(
        bottlenecks_artifact.get("completion_audit_release_blocker_bottleneck_count") or 0
    )
    assert status["irreducible_external_return_bottleneck_count"] == int(
        bottlenecks_artifact.get("irreducible_external_return_bottleneck_count") or 0
    )
    assert status["primary_bottleneck_post_return_acceptance_artifact"] == bottlenecks_artifact.get(
        "primary_bottleneck_post_return_acceptance_artifact"
    )
    assert status["commercial_readiness_handoff_bundle_status"] == (
        "product_commercial_readiness_handoff_bundle_ready"
    )
    assert status["commercial_readiness_handoff_bundle_ready"] is True
    assert status["commercial_readiness_handoff_bundle_artifact_reference_count"] == 29
    assert status["commercial_readiness_handoff_bundle_local_missing_artifact_reference_count"] == 0
    assert status["operator_intake_kit_full_commercial_evidence_receipt_entry_count"] == int(
        intake_artifact.get("full_commercial_evidence_receipt_entry_count") or 0
    )
    assert status[
        "operator_intake_kit_full_commercial_evidence_receipt_operator_input_required_count"
    ] == int(
        intake_artifact.get(
            "full_commercial_evidence_receipt_operator_input_required_count"
        )
        or 0
    )
    assert status[
        "operator_intake_kit_full_commercial_evidence_receipt_current_action_required_count"
    ] == int(
        intake_artifact.get("full_commercial_evidence_receipt_current_action_required_count")
        or 0
    )
    assert status[
        "operator_intake_kit_full_commercial_evidence_receipt_template_required_count"
    ] == int(
        intake_artifact.get("full_commercial_evidence_receipt_template_required_count")
        or 0
    )
    assert status[
        "operator_intake_kit_full_commercial_evidence_receipt_template_present_count"
    ] == int(
        intake_artifact.get("full_commercial_evidence_receipt_template_present_count")
        or 0
    )
    assert status[
        "operator_intake_kit_full_commercial_evidence_receipt_approval_token_count"
    ] == int(
        intake_artifact.get("full_commercial_evidence_receipt_approval_token_count")
        or 0
    )
    assert status["operator_intake_kit_full_commercial_evidence_receipt_entry_ids"] == (
        intake_artifact.get("full_commercial_evidence_receipt_entry_ids")
    )
    assert status[
        "operator_intake_kit_full_commercial_evidence_receipt_source_gate_statuses"
    ] == intake_artifact.get("full_commercial_evidence_receipt_source_gate_statuses")
    assert status[
        "operator_intake_kit_full_commercial_evidence_receipt_required_inputs"
    ] == intake_artifact.get("full_commercial_evidence_receipt_required_inputs")
    assert status[
        "operator_intake_kit_full_commercial_evidence_receipt_approval_tokens"
    ] == intake_artifact.get("full_commercial_evidence_receipt_approval_tokens")
    assert status["bottleneck_briefing_full_commercial_evidence_receipt_entry_count"] == int(
        bottlenecks_artifact.get("full_commercial_evidence_receipt_entry_count") or 0
    )
    assert status[
        "bottleneck_briefing_full_commercial_evidence_receipt_operator_input_required_count"
    ] == int(
        bottlenecks_artifact.get(
            "full_commercial_evidence_receipt_operator_input_required_count"
        )
        or 0
    )
    assert status[
        "bottleneck_briefing_full_commercial_evidence_receipt_current_action_required_count"
    ] == int(
        bottlenecks_artifact.get("full_commercial_evidence_receipt_current_action_required_count")
        or 0
    )
    assert status[
        "bottleneck_briefing_full_commercial_evidence_receipt_template_required_count"
    ] == int(
        bottlenecks_artifact.get("full_commercial_evidence_receipt_template_required_count")
        or 0
    )
    assert status[
        "bottleneck_briefing_full_commercial_evidence_receipt_template_present_count"
    ] == int(
        bottlenecks_artifact.get("full_commercial_evidence_receipt_template_present_count")
        or 0
    )
    assert status[
        "bottleneck_briefing_full_commercial_evidence_receipt_approval_token_count"
    ] == int(
        bottlenecks_artifact.get("full_commercial_evidence_receipt_approval_token_count")
        or 0
    )
    assert status["bottleneck_briefing_full_commercial_evidence_receipt_entry_ids"] == (
        bottlenecks_artifact.get("full_commercial_evidence_receipt_entry_ids")
    )
    assert status[
        "bottleneck_briefing_full_commercial_evidence_receipt_source_gate_statuses"
    ] == bottlenecks_artifact.get("full_commercial_evidence_receipt_source_gate_statuses")
    assert status[
        "bottleneck_briefing_full_commercial_evidence_receipt_required_inputs"
    ] == bottlenecks_artifact.get("full_commercial_evidence_receipt_required_inputs")
    assert status[
        "bottleneck_briefing_full_commercial_evidence_receipt_approval_tokens"
    ] == bottlenecks_artifact.get("full_commercial_evidence_receipt_approval_tokens")
    assert status["bottleneck_briefing_full_commercial_evidence_receipt_entry_count"] == 2
    assert status["operator_intake_kit_full_commercial_evidence_receipt_entry_count"] == 2
    assert (
        "blocked_product_scope_breadth_evidence_receipt"
        in status[
            "operator_intake_kit_full_commercial_evidence_receipt_source_gate_statuses"
        ]
    )
    assert (
        "blocked_engine_refinement_claim_evidence_receipt"
        in status[
            "operator_intake_kit_full_commercial_evidence_receipt_source_gate_statuses"
        ]
    )
    _assert_scope_priority_fields(
        status=status,
        prefix="operator_intake_kit",
        artifact=intake_artifact,
    )
    _assert_scope_priority_fields(
        status=status,
        prefix="bottleneck_briefing",
        artifact=bottlenecks_artifact,
    )
    assert status[
        "operator_intake_kit_product_scope_breadth_evidence_priority_status"
    ] == "product_scope_breadth_evidence_priority_packet_ready"
    assert status[
        "operator_intake_kit_product_scope_breadth_evidence_priority_packet_ready"
    ] is True
    assert status[
        "operator_intake_kit_product_scope_breadth_evidence_priority_top_item_id"
    ] == "AQP1.core_binder_01"
    assert status[
        "operator_intake_kit_product_scope_breadth_evidence_priority_top_domain"
    ] == "transporter"
    assert status[
        "operator_intake_kit_product_scope_breadth_evidence_priority_top_bucket"
    ] == "local_crosscheck_review_present_but_exact_quant_required"
    assert status[
        "operator_intake_kit_product_scope_breadth_evidence_priority_top_required_evidence_type"
    ] == "exact_transporter_target_pair_quantitative_binder_kcal"
    assert status[
        "operator_intake_kit_product_scope_breadth_evidence_priority_scope_promotion_allowed"
    ] is False
    assert status[
        "operator_intake_kit_product_scope_breadth_evidence_priority_authoritative_apply_allowed"
    ] is False
    assert status[
        "bottleneck_briefing_product_scope_breadth_evidence_priority_top_item_id"
    ] == "AQP1.core_binder_01"
    assert status[
        "bottleneck_briefing_product_scope_breadth_evidence_priority_top_domain"
    ] == "transporter"
    assert status[
        "bottleneck_briefing_product_scope_breadth_evidence_priority_top_bucket"
    ] == "local_crosscheck_review_present_but_exact_quant_required"
    assert status[
        "bottleneck_briefing_product_scope_breadth_evidence_priority_top_required_evidence_type"
    ] == "exact_transporter_target_pair_quantitative_binder_kcal"
    assert status[
        "bottleneck_briefing_product_scope_breadth_evidence_priority_scope_promotion_allowed"
    ] is False
    assert status[
        "bottleneck_briefing_product_scope_breadth_evidence_priority_authoritative_apply_allowed"
    ] is False
    assert status["production_ai_registry_promotion_operator_receipt_status"] == (
        handoff_artifact.get("production_ai_registry_promotion_operator_receipt_status")
    )
    assert status["production_ai_registry_promotion_operator_receipt_status"] == (
        "blocked_production_ai_registry_promotion_operator_receipt"
    )
    assert status["production_ai_registry_promotion_operator_receipt_ready"] is False
    assert status["production_ai_registry_promotion_operator_receipt_artifact"] == (
        "runs/production_ai_registry_promotion_operator_receipt_current.json"
    )
    assert status["production_ai_registry_promotion_operator_receipt_csv"] == (
        "config/production_ai_registry_promotion_operator_receipt_current.csv"
    )
    assert status["production_ai_registry_promotion_operator_receipt_approval_token_required"] == (
        "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION"
    )
    assert status["production_ai_registry_promotion_operator_receipt_first_blocked_row_blocker"] == (
        "operator_placeholders_unfilled"
    )
    assert status[
        "production_ai_registry_promotion_operator_receipt_observed_registry_default_residual_mode"
    ] == "shadow"
    assert status[
        "production_ai_registry_promotion_operator_receipt_observed_registry_trained_model_checkpoint_count"
    ] == 1
    assert (
        status[
            "production_ai_registry_promotion_operator_receipt_observed_checkpoint_registry_promotion_currently_satisfied"
        ]
        is False
    )
    assert "default_residual_mode_guarded" in status[
        "production_ai_registry_promotion_operator_receipt_observed_checkpoint_registry_promotion_missing_gate_ids"
    ]
    assert status["production_ai_registry_promotion_priority_status"] == (
        handoff_artifact.get("production_ai_registry_promotion_priority_status")
    )
    assert status["production_ai_registry_promotion_priority_status"] == (
        "blocked_production_ai_registry_promotion_priority_packet"
    )
    assert status["production_ai_registry_promotion_priority_packet_ready"] is True
    assert status["production_ai_registry_promotion_priority_registry_promotion_ready"] is False
    assert status["production_ai_registry_promotion_priority_operator_input_required_count"] == 3
    assert status["production_ai_registry_promotion_priority_blocked_priority_item_count"] == 3
    assert status["production_ai_registry_promotion_priority_missing_gate_count"] == 3
    assert "default_residual_mode_guarded" in status[
        "production_ai_registry_promotion_priority_missing_gate_ids"
    ]
    assert status["production_ai_registry_promotion_priority_top_gate_id"] == (
        "default_residual_mode_guarded"
    )
    assert status["production_ai_registry_promotion_priority_top_priority_bucket"] == (
        "guarded_residual_mode_selection_required"
    )
    assert status["production_ai_registry_promotion_priority_top_acceptance_artifact"] == (
        "runs/residual_model_registry_current.json"
    )
    assert status["production_ai_registry_promotion_priority_model_promoted"] is False
    assert status[
        "production_ai_registry_promotion_priority_customer_facing_mutation_enabled"
    ] is False
    assert status["production_ai_registry_promotion_priority_external_state_mutated"] is False
    assert status["cameo_official_result_fetch_preflight_status"] == cameo_fetch_artifact.get(
        "status"
    )
    assert status["cameo_official_result_fetch_preflight_status"] == (
        "blocked_cameo_official_result_fetch_preflight"
    )
    assert status["cameo_official_result_fetch_preflight_ready"] is False
    assert status["cameo_official_result_fetch_preflight_artifact_path"].endswith(
        "runs/cameo_official_result_fetch_preflight_current.json"
    )
    assert status["cameo_official_result_fetch_preflight_operator_template_csv"] == (
        cameo_fetch_artifact.get("operator_template_csv")
    )
    assert status["cameo_official_result_fetch_preflight_operator_intake_csv"] == (
        cameo_fetch_artifact.get("operator_fetch_csv")
    )
    assert status["cameo_official_result_fetch_preflight_kit_template_path"] == (
        "runs/goal_operator_intake_kit_current/templates/"
        "cameo_official_result_fetch_operator_approval_template_current.csv"
    )
    assert status["cameo_official_result_fetch_preflight_approval_token_required"] == (
        "APPROVE_CAMEO_OFFICIAL_RESULT_FETCH"
    )
    assert status["cameo_official_result_fetch_preflight_kit_status"] == "approval_required"
    assert status["cameo_official_result_fetch_preflight_operator_fetch_csv_present"] is False
    assert (
        status[
            "cameo_official_result_fetch_preflight_authorized_for_separate_operator_fetch"
        ]
        is False
    )
    assert status["cameo_official_result_fetch_preflight_network_request_opened"] is False
    assert status["cameo_official_result_fetch_preflight_official_results_fetched"] is False
    assert status["cameo_official_result_fetch_preflight_native_local_accuracy_used"] is False
    assert status["cameo_official_result_fetch_preflight_external_state_mutated"] is False
    assert status["cameo_official_result_fetch_preflight_blocker_count"] == int(
        cameo_fetch_artifact.get("blocker_count") or 0
    )
    assert "operator_fetch_csv_missing" in status[
        "cameo_official_result_fetch_preflight_blockers"
    ]
    _assert_receipt_fields(
        status=status,
        prefix="product_scope_breadth_evidence_receipt",
        artifact=scope_receipt_artifact,
        path_suffix="runs/product_scope_breadth_evidence_receipt_current.json",
        ready_key="full_scope_evidence_receipt_ready",
        first_blocked_id_source_key="first_blocked_scope_blocker_id",
        first_blocked_id_status_key="first_blocked_scope_blocker_id",
        required_blocker_count_key="required_scope_blocker_count",
        required_blockers_key="required_scope_blockers",
    )
    assert status["product_scope_breadth_evidence_receipt_status"] == (
        "blocked_product_scope_breadth_evidence_receipt"
    )
    assert status["product_scope_breadth_evidence_receipt_blocked_row_count"] == 6
    assert status["product_scope_breadth_evidence_receipt_pass_row_count"] == 0
    assert status["product_scope_breadth_evidence_receipt_approval_token_required"] == (
        "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT"
    )
    assert status["product_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id"] == (
        "direct_binding_evidence_missing"
    )
    assert "operator_placeholders_unfilled" in status[
        "product_scope_breadth_evidence_receipt_first_blocked_row_blockers"
    ]
    _assert_receipt_fields(
        status=status,
        prefix="engine_refinement_claim_evidence_receipt",
        artifact=engine_receipt_artifact,
        path_suffix="runs/engine_refinement_claim_evidence_receipt_current.json",
        ready_key="claim_promotion_evidence_receipt_ready",
        first_blocked_id_source_key="first_blocked_blocker_id",
        first_blocked_id_status_key="first_blocked_blocker_id",
        required_blocker_count_key="required_blocker_count",
        required_blockers_key="required_blockers",
    )
    assert status["engine_refinement_claim_evidence_receipt_status"] == (
        "blocked_engine_refinement_claim_evidence_receipt"
    )
    assert status["engine_refinement_claim_evidence_receipt_blocked_row_count"] == 6
    assert status["engine_refinement_claim_evidence_receipt_pass_row_count"] == 0
    assert status["engine_refinement_claim_evidence_receipt_approval_token_required"] == (
        "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT"
    )
    assert status["engine_refinement_claim_evidence_receipt_first_blocked_blocker_id"] == (
        "public_benchmark_gate_not_ready"
    )
    assert "operator_placeholders_unfilled" in status[
        "engine_refinement_claim_evidence_receipt_first_blocked_row_blockers"
    ]
    assert status["full_commercial_blocker_evidence_matrix_status"] == full_matrix_artifact.get(
        "status"
    )
    assert status["full_commercial_blocker_evidence_matrix_ready"] is (
        full_matrix_artifact.get("full_commercial_blocker_evidence_matrix_ready") is True
    )
    assert status["full_commercial_blocker_evidence_matrix_release_blocker_visibility_ready"] is (
        full_matrix_artifact.get("release_blocker_visibility_ready") is True
    )
    assert status["full_commercial_blocker_evidence_matrix_row_count"] == int(
        full_matrix_artifact.get("matrix_row_count") or 0
    )
    assert status["full_commercial_blocker_evidence_matrix_blocked_row_count"] == int(
        full_matrix_artifact.get("blocked_matrix_row_count") or 0
    )
    assert status["full_commercial_blocker_evidence_matrix_approval_token_count"] == int(
        full_matrix_artifact.get("approval_token_count") or 0
    )
    assert status["full_commercial_blocker_evidence_matrix_first_blocked_release_blocker_id"] == (
        full_matrix_artifact.get("first_blocked_release_blocker_id")
    )
    assert status["full_commercial_blocker_evidence_matrix_first_blocked_evidence_row_id"] == (
        full_matrix_artifact.get("first_blocked_evidence_row_id")
    )
    assert status["full_commercial_blocker_evidence_matrix_first_blocked_evidence_artifact"] == (
        full_matrix_artifact.get("first_blocked_evidence_artifact")
    )
    assert status["full_commercial_blocker_evidence_matrix_first_blocked_expected_evidence_status"] == (
        full_matrix_artifact.get("first_blocked_expected_evidence_status")
    )
    assert status["full_commercial_blocker_evidence_matrix_first_blocked_observed_evidence_status"] == (
        full_matrix_artifact.get("first_blocked_observed_evidence_status")
    )
    assert status["full_commercial_blocker_evidence_matrix_first_blocked_row_blockers"] == (
        full_matrix_artifact.get("first_blocked_row_blockers")
    )
    assert status["full_commercial_blocker_evidence_matrix_first_blocked_acceptance_artifact"] == (
        full_matrix_artifact.get("first_blocked_acceptance_artifact")
    )
    assert status["full_commercial_blocker_evidence_matrix_scope_receipt_most_common_row_blocker"] == (
        full_matrix_artifact.get("scope_receipt_most_common_row_blocker")
    )
    assert status["full_commercial_blocker_evidence_matrix_engine_receipt_most_common_row_blocker"] == (
        full_matrix_artifact.get("engine_receipt_most_common_row_blocker")
    )
    assert status["goal_completion_audit_goal_complete"] == readiness_artifact.get(
        "goal_completion_audit_goal_complete"
    )
    assert status["release_complete_lane_ready"] == readiness_artifact.get("release_complete_lane_ready")
    assert status["operator_pending_lane_ready"] == readiness_artifact.get("operator_pending_lane_ready")

    assert readiness["status"] == readiness_artifact.get("status")
    assert readiness["blocked_lane_count"] == int(readiness_artifact.get("blocked_lane_count") or 0)
    assert readiness["operator_approval_pending_count"] == int(
        readiness_artifact.get("operator_approval_pending_count") or 0
    )
    assert readiness["external_results_pending_count"] == int(
        readiness_artifact.get("external_results_pending_count") or 0
    )
    assert readiness["release_complete_vs_operator_pending_lane"] == readiness_artifact.get(
        "release_complete_vs_operator_pending_lane"
    )
    assert readiness["goal_completion_audit_goal_complete"] is readiness_artifact.get(
        "goal_completion_audit_goal_complete"
    )
    assert readiness["release_complete_lane_ready"] is readiness_artifact.get("release_complete_lane_ready")
    assert readiness["operator_pending_lane_ready"] is False
    assert len(readiness["rows"]) == int(readiness_artifact.get("lane_count") or 0)

    assert actions["status"] == actions_artifact.get("status")
    assert actions["action_count"] == int(actions_artifact.get("action_count") or 0)
    assert len(actions["actions"]) == int(actions_artifact.get("action_count") or 0)

    assert intake_kit["status"] == intake_artifact.get("status")
    assert intake_kit["entry_count"] == int(intake_artifact.get("entry_count") or 0)
    assert len(intake_kit["entries"]) == int(intake_artifact.get("entry_count") or 0)

    assert release["status"] == release_artifact.get("status")
    assert release["release_allowed"] is (release_artifact.get("release_allowed") is True)
    assert release["restricted_release_allowed"] is (
        release_artifact.get("restricted_release_allowed") is True
    )
    assert release["full_commercial_release_allowed"] is (
        release_artifact.get("full_commercial_release_allowed") is True
    )
    assert release["full_commercial_release_blocker_count"] == int(
        release_artifact.get("full_commercial_release_blocker_count") or 0
    )
    assert release["full_commercial_release_blocker_ids"] == release_artifact.get(
        "full_commercial_release_blocker_ids"
    )
    assert release["primary_full_commercial_release_blocker_id"] == release_artifact.get(
        "primary_full_commercial_release_blocker_id"
    )
    assert release["master_gap_closure_rollup_open_gap_ids"] == release_artifact.get(
        "master_gap_closure_rollup_open_gap_ids"
    )
    assert release["master_gap_closure_rollup_science_claim_rollup_status"] == (
        release_artifact.get("master_gap_closure_rollup_science_claim_rollup_status")
    )
    assert release["science_claim_promotion_gap_closure_open_gap_ids"] == release_artifact.get(
        "science_claim_promotion_gap_closure_open_gap_ids"
    )
    assert release["science_claim_promotion_gap_closure_closed_gap_ids"] == release_artifact.get(
        "science_claim_promotion_gap_closure_closed_gap_ids"
    )
    assert release["science_claim_promotion_gap_closure_current_primary_open_gap_id"] == (
        release_artifact.get("science_claim_promotion_gap_closure_current_primary_open_gap_id")
    )
    assert release["science_claim_promotion_gap_closure_openmm_claim_promotion_status"] == (
        release_artifact.get("science_claim_promotion_gap_closure_openmm_claim_promotion_status")
    )
    assert release["accuracy_parity_scorecard_status"] == release_artifact.get(
        "accuracy_parity_scorecard_status", ""
    )
    assert release["accuracy_parity_ligand_ranking_status"] == release_artifact.get(
        "accuracy_parity_ligand_ranking_status", ""
    )
    assert release["api_runner_profile_promotion_operator_receipt_status"] == (
        release_artifact.get("api_runner_profile_promotion_operator_receipt_status", "")
    )
    assert release["api_runner_profile_promotion_operator_receipt_first_blocked_profile_id"] == (
        release_artifact.get(
            "api_runner_profile_promotion_operator_receipt_first_blocked_profile_id", ""
        )
    )
    assert release["product_ledger_privacy_scan_status"] == release_artifact.get(
        "product_ledger_privacy_scan_status", ""
    )
    assert release["product_ledger_privacy_scan_recorded"] is (
        release_artifact.get("product_ledger_privacy_scan_recorded") is True
    )
    assert release["product_ledger_privacy_scan_leak_count"] == int(
        release_artifact.get("product_ledger_privacy_scan_leak_count") or 0
    )
    _assert_refine_tier_public_benchmark_fields(
        observed=release,
        artifact=release_artifact,
    )
    assert release["blocker_count"] == int(release_artifact.get("blocker_count") or 0)
    assert len(release["checks"]) == int(release_artifact.get("check_count") or 0)

    assert burndown["status"] == burndown_artifact.get("status")
    assert burndown["work_item_count"] == int(burndown_artifact.get("work_item_count") or 0)
    assert len(burndown["work_items"]) == int(burndown_artifact.get("work_item_count") or 0)

    assert bottlenecks["status"] == bottlenecks_artifact.get("status")
    assert bottlenecks["bottleneck_count"] == int(bottlenecks_artifact.get("bottleneck_count") or 0)
    assert len(bottlenecks["bottlenecks"]) == int(bottlenecks_artifact.get("bottleneck_count") or 0)

    assert api_contract["status"] == api_contract_artifact.get("status")
    assert api_contract["surface_ready"] is True
    assert api_contract["blocker_count"] == 0

    for payload in (status, readiness, actions, intake_kit, release, burndown, bottlenecks, api_contract):
        assert payload["execution_enabled"] is False
        assert payload["delete_executed"] is False
        assert payload["external_state_mutated"] is False
