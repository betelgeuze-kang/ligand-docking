"""Benchmark, launch, and deployment projection assertions for the product goal suite."""

from __future__ import annotations


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
    write_guard_missing_reasons = []
    if artifact.get("refine_tier_public_benchmark_work_order_apply_recorded") is not True:
        write_guard_missing_reasons.append("apply_gate_not_recorded")
    if artifact.get("refine_tier_public_benchmark_work_order_apply_work_order_csv_present") is not True:
        write_guard_missing_reasons.append("work_order_csv_missing")
    if not artifact.get("refine_tier_public_benchmark_work_order_apply_target_intake_csv"):
        write_guard_missing_reasons.append("target_intake_csv_missing")
    for field, reason in [
        ("refine_tier_public_benchmark_work_order_apply_candidate_intake_written", "candidate_intake_written"),
        (
            "refine_tier_public_benchmark_work_order_apply_candidate_readiness_checked",
            "candidate_readiness_checked",
        ),
        ("refine_tier_public_benchmark_work_order_apply_intake_written", "intake_written"),
        ("refine_tier_public_benchmark_work_order_apply_write_intake_requested", "write_intake_requested"),
        ("refine_tier_public_benchmark_work_order_apply_approval_token_present", "approval_token_present"),
        ("refine_tier_public_benchmark_work_order_apply_approval_token_accepted", "approval_token_accepted"),
        ("refine_tier_public_benchmark_work_order_apply_external_state_mutated", "external_state_mutated"),
    ]:
        if artifact.get(field) is True:
            write_guard_missing_reasons.append(reason)
    assert observed["refine_tier_public_benchmark_work_order_apply_write_guard_ready"] is (
        not write_guard_missing_reasons
    )
    assert (
        observed["refine_tier_public_benchmark_work_order_apply_write_guard_missing_reasons"]
        == write_guard_missing_reasons
    )


def _assert_product_launch_r4_preflight_fields(*, observed: dict, artifact: dict) -> None:
    prefix = "product_launch_r4_preflight"
    bool_fields = [
        "authorized_for_r4_confirmation",
        "authorized_for_external_mutation",
        "launch_executed",
        "external_state_mutated",
        "engine_refinement_claim_evidence_receipt_ready",
    ]
    int_fields = [
        "check_count",
        "pass_count",
        "blocker_count",
        "engine_refinement_claim_evidence_receipt_blocked_row_count",
        "engine_refinement_claim_promotion_action_row_count",
    ]
    text_fields = [
        "status",
        "source_api_customer_flow_status",
        "source_rollout_execution_status",
        "source_release_bundle_status",
        "source_commercial_independence_status",
        "source_license_decision_status",
        "source_third_party_license_status",
        "source_engine_refinement_status",
        "engine_refinement_claim_evidence_receipt_status",
        "engine_refinement_claim_evidence_receipt_csv",
        "next_required_step",
    ]
    list_fields = [
        "blocked_check_ids",
        "required_r4_fields",
        "required_rollout_tokens",
    ]
    assert observed[f"{prefix}_ready"] is (
        artifact.get("status") == "product_launch_r4_preflight_ready"
    )
    assert observed[f"{prefix}_artifact_path"].endswith(
        "runs/product_launch_r4_preflight_current.json"
    )
    for field in bool_fields:
        assert observed[f"{prefix}_{field}"] is (artifact.get(field) is True)
    for field in int_fields:
        assert observed[f"{prefix}_{field}"] == int(artifact.get(field) or 0)
    for field in text_fields:
        assert observed[f"{prefix}_{field}"] == artifact.get(field, "")
    for field in list_fields:
        assert observed[f"{prefix}_{field}"] == (artifact.get(field) or [])

    guard_missing_reasons = []
    if artifact.get("status") != "product_launch_r4_preflight_ready":
        guard_missing_reasons.append("preflight_not_ready")
    if artifact.get("authorized_for_r4_confirmation") is not True:
        guard_missing_reasons.append("r4_confirmation_not_authorized")
    if artifact.get("authorized_for_external_mutation") is True:
        guard_missing_reasons.append("external_mutation_authorized")
    if artifact.get("launch_executed") is True:
        guard_missing_reasons.append("launch_executed")
    if artifact.get("external_state_mutated") is True:
        guard_missing_reasons.append("external_state_mutated")
    if int(artifact.get("blocker_count") or 0) != 0:
        guard_missing_reasons.append("blockers_present")
    if int(artifact.get("check_count") or 0) == 0 or int(
        artifact.get("pass_count") or 0
    ) != int(artifact.get("check_count") or 0):
        guard_missing_reasons.append("checks_not_all_passed")
    for field in ("target", "action", "impact", "risk", "rollback", "verification"):
        if field not in (artifact.get("required_r4_fields") or []):
            guard_missing_reasons.append("required_r4_fields_missing")
            break
    for token in ("APPROVE_PRODUCT_ROLLOUT", "APPROVE_HOSTED_PRODUCT_API_EXPOSURE"):
        if token not in (artifact.get("required_rollout_tokens") or []):
            guard_missing_reasons.append("required_rollout_tokens_missing")
            break
    assert observed[f"{prefix}_fail_closed_guard_ready"] is (
        not guard_missing_reasons
    )
    assert observed[f"{prefix}_fail_closed_guard_missing_reasons"] == guard_missing_reasons


def _assert_deploy_ops_legal_gap_closure_fields(*, observed: dict, artifact: dict) -> None:
    prefix = "deploy_ops_legal_gap_closure"
    bool_fields = [
        "all_gaps_closed",
        "rollout_execution_readiness_ready",
        "rollout_smoke_receipt_ready",
        "rollout_executed",
        "rollout_smoke_external_state_mutated",
        "rollout_smoke_pager_provider_contacted",
        "rollout_smoke_ingress_certificate_verified_live",
        "pager_provider_contacted",
        "ingress_certificate_verified_live",
        "legal_advice_provided",
        "external_state_mutated",
    ]
    int_fields = ["gap_count", "closed_gap_count", "open_gap_count"]
    text_fields = [
        "status",
        "current_primary_open_gap_id",
        "current_next_action",
        "rollout_smoke_receipt_status",
    ]
    list_fields = ["closed_gap_ids", "open_gap_ids"]
    assert observed[f"{prefix}_complete"] is (
        artifact.get("status") == "deploy_ops_legal_gap_closure_complete"
        and artifact.get("all_gaps_closed") is True
    )
    assert observed[f"{prefix}_artifact_path"].endswith(
        "runs/deploy_ops_legal_gap_closure_current.json"
    )
    for field in bool_fields:
        assert observed[f"{prefix}_{field}"] is (artifact.get(field) is True)
    for field in int_fields:
        assert observed[f"{prefix}_{field}"] == int(artifact.get(field) or 0)
    for field in text_fields:
        assert observed[f"{prefix}_{field}"] == artifact.get(field, "")
    for field in list_fields:
        assert observed[f"{prefix}_{field}"] == (artifact.get(field) or [])

    guard_missing_reasons = []
    if artifact.get("status") != "deploy_ops_legal_gap_closure_complete":
        guard_missing_reasons.append("gap_closure_not_complete")
    if artifact.get("all_gaps_closed") is not True:
        guard_missing_reasons.append("gaps_open")
    if int(artifact.get("open_gap_count") or 0) != 0:
        guard_missing_reasons.append("open_gap_count_nonzero")
    if artifact.get("rollout_execution_readiness_ready") is not True:
        guard_missing_reasons.append("rollout_readiness_not_ready")
    if artifact.get("rollout_smoke_receipt_ready") is not True:
        guard_missing_reasons.append("rollout_smoke_receipt_not_ready")
    if artifact.get("rollout_executed") is not True:
        guard_missing_reasons.append("rollout_execution_not_recorded")
    if artifact.get("rollout_smoke_external_state_mutated") is not True:
        guard_missing_reasons.append("rollout_smoke_external_mutation_not_recorded")
    if artifact.get("rollout_smoke_pager_provider_contacted") is not True:
        guard_missing_reasons.append("rollout_smoke_pager_contact_not_recorded")
    if artifact.get("rollout_smoke_ingress_certificate_verified_live") is not True:
        guard_missing_reasons.append("rollout_smoke_ingress_certificate_not_verified")
    if artifact.get("external_state_mutated") is True:
        guard_missing_reasons.append("gap_closure_builder_mutated_external_state")
    if artifact.get("legal_advice_provided") is True:
        guard_missing_reasons.append("legal_advice_claimed")
    assert observed[f"{prefix}_boundary_guard_ready"] is (not guard_missing_reasons)
    assert observed[f"{prefix}_boundary_guard_missing_reasons"] == guard_missing_reasons
