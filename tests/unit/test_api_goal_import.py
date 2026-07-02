from __future__ import annotations

import asyncio
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _artifact_summary(name: str) -> dict:
    path = ROOT / "runs" / name
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _artifact_payload(name: str) -> dict:
    path = ROOT / "runs" / name
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


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
    assert status[f"{status_prefix}_receipt_status"] == artifact.get(
        "product_scope_breadth_evidence_priority_receipt_status"
    )
    assert status[f"{status_prefix}_receipt_ready"] is (
        artifact.get("product_scope_breadth_evidence_priority_receipt_ready") is True
    )
    assert status[f"{status_prefix}_receipt_csv"] == artifact.get(
        "product_scope_breadth_evidence_priority_receipt_csv"
    )
    assert status[f"{status_prefix}_receipt_operator_review_surface_ready_count"] == int(
        artifact.get("product_scope_breadth_evidence_priority_receipt_operator_review_surface_ready_count") or 0
    )
    assert status[f"{status_prefix}_receipt_operator_review_surface_blocked_count"] == int(
        artifact.get("product_scope_breadth_evidence_priority_receipt_operator_review_surface_blocked_count") or 0
    )
    assert status[f"{status_prefix}_receipt_manual_field_pending_count"] == int(
        artifact.get("product_scope_breadth_evidence_priority_receipt_manual_field_pending_count") or 0
    )
    assert status[f"{status_prefix}_receipt_first_blocked_scope_blocker_id"] == artifact.get(
        "product_scope_breadth_evidence_priority_receipt_first_blocked_scope_blocker_id"
    )
    assert status[f"{status_prefix}_receipt_first_blocked_evidence_artifact"] == artifact.get(
        "product_scope_breadth_evidence_priority_receipt_first_blocked_evidence_artifact"
    )
    assert status[f"{status_prefix}_receipt_first_blocked_missing_true_fields"] == (
        artifact.get("product_scope_breadth_evidence_priority_receipt_first_blocked_missing_true_fields") or []
    )
    assert status[f"{status_prefix}_receipt_first_blocked_row_blockers"] == (
        artifact.get("product_scope_breadth_evidence_priority_receipt_first_blocked_row_blockers") or []
    )
    assert status[f"{status_prefix}_receipt_approval_token_required"] == artifact.get(
        "product_scope_breadth_evidence_priority_receipt_approval_token_required"
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


def _split_delimited(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [
            part.strip()
            for part in value.replace(";", ",").split(",")
            if part.strip()
        ]
    return []


def _assert_license_legal_boundary_fields(*, observed: dict, artifact: dict) -> None:
    audit_bool_fields = [
        "gate_present",
        "recorded",
        "product_license_hash_matches_approved_source",
        "third_party_license_review_gate_ready",
        "legal_advice_provided",
        "external_state_mutated",
    ]
    audit_int_fields = [
        "hard_blocker_count",
        "operator_review_item_count",
        "third_party_license_review_gate_blocker_count",
    ]
    audit_text_fields = [
        "status",
        "product_license_path",
        "approved_license_text_source",
        "spdx_license_id",
        "copyright_holder",
        "third_party_license_review_gate_status",
        "viewer_third_party_notice_path",
    ]
    for field in audit_bool_fields:
        key = f"self_hosted_license_distribution_audit_{field}"
        assert observed[key] is (artifact.get(key) is True)
    for field in audit_int_fields:
        key = f"self_hosted_license_distribution_audit_{field}"
        assert observed[key] == int(artifact.get(key) or 0)
    for field in audit_text_fields:
        key = f"self_hosted_license_distribution_audit_{field}"
        assert observed[key] == artifact.get(key, "")
    assert observed[
        "self_hosted_license_distribution_audit_third_party_dual_license_assets"
    ] == _split_delimited(
        artifact.get("self_hosted_license_distribution_audit_third_party_dual_license_assets")
    )

    audit_guard_missing_reasons = []
    if artifact.get("self_hosted_license_distribution_audit_gate_present") is not True:
        audit_guard_missing_reasons.append("audit_gate_not_present")
    if artifact.get("self_hosted_license_distribution_audit_recorded") is not True:
        audit_guard_missing_reasons.append("audit_not_recorded")
    if artifact.get("self_hosted_license_distribution_audit_status") != (
        "self_hosted_license_distribution_audit_recorded"
    ):
        audit_guard_missing_reasons.append("audit_status_not_recorded")
    if artifact.get(
        "self_hosted_license_distribution_audit_product_license_hash_matches_approved_source"
    ) is not True:
        audit_guard_missing_reasons.append("product_license_hash_mismatch")
    if int(artifact.get("self_hosted_license_distribution_audit_hard_blocker_count") or 0) != 0:
        audit_guard_missing_reasons.append("hard_blockers_present")
    if int(artifact.get("self_hosted_license_distribution_audit_operator_review_item_count") or 0) < 1:
        audit_guard_missing_reasons.append("operator_review_boundary_missing")
    if artifact.get(
        "self_hosted_license_distribution_audit_third_party_license_review_gate_ready"
    ) is not True:
        audit_guard_missing_reasons.append("third_party_review_gate_not_ready")
    if int(
        artifact.get(
            "self_hosted_license_distribution_audit_third_party_license_review_gate_blocker_count"
        )
        or 0
    ) != 0:
        audit_guard_missing_reasons.append("third_party_review_blockers_present")
    if artifact.get("self_hosted_license_distribution_audit_legal_advice_provided") is True:
        audit_guard_missing_reasons.append("legal_advice_claimed")
    if artifact.get("self_hosted_license_distribution_audit_external_state_mutated") is True:
        audit_guard_missing_reasons.append("audit_mutated_external_state")
    assert observed["self_hosted_license_distribution_audit_boundary_guard_ready"] is (
        not audit_guard_missing_reasons
    )
    assert (
        observed["self_hosted_license_distribution_audit_boundary_guard_missing_reasons"]
        == audit_guard_missing_reasons
    )

    review_bool_fields = [
        "present",
        "recorded",
        "ready",
        "review_csv_present",
        "asset_modified",
        "legal_advice_provided",
        "external_state_mutated",
    ]
    review_int_fields = [
        "review_row_count",
        "expected_review_asset_count",
        "approved_review_asset_count",
        "missing_review_asset_count",
        "deferred_review_asset_count",
        "blocker_count",
        "source_hard_blocker_count",
        "source_operator_review_item_count",
    ]
    review_text_fields = [
        "status",
        "review_csv",
        "operator_template_csv",
        "approval_token_required",
        "source_license_audit_status",
    ]
    for field in review_bool_fields:
        key = f"third_party_license_review_gate_{field}"
        assert observed[key] is (artifact.get(key) is True)
    for field in review_int_fields:
        key = f"third_party_license_review_gate_{field}"
        assert observed[key] == int(artifact.get(key) or 0)
    for field in review_text_fields:
        key = f"third_party_license_review_gate_{field}"
        assert observed[key] == artifact.get(key, "")
    assert observed["third_party_license_review_gate_approved_assets"] == _split_delimited(
        artifact.get("third_party_license_review_gate_approved_assets")
    )
    assert observed["third_party_license_review_gate_allowed_license_paths"] == _split_delimited(
        artifact.get("third_party_license_review_gate_allowed_license_paths")
    )

    review_guard_missing_reasons = []
    if artifact.get("third_party_license_review_gate_present") is not True:
        review_guard_missing_reasons.append("review_gate_not_present")
    if artifact.get("third_party_license_review_gate_recorded") is not True:
        review_guard_missing_reasons.append("review_gate_not_recorded")
    if artifact.get("third_party_license_review_gate_ready") is not True:
        review_guard_missing_reasons.append("review_gate_not_ready")
    if artifact.get("third_party_license_review_gate_status") != "third_party_license_review_gate_ready":
        review_guard_missing_reasons.append("review_gate_status_not_ready")
    if artifact.get("third_party_license_review_gate_review_csv_present") is not True:
        review_guard_missing_reasons.append("review_csv_missing")
    if not artifact.get("third_party_license_review_gate_review_csv"):
        review_guard_missing_reasons.append("review_csv_path_missing")
    if not artifact.get("third_party_license_review_gate_operator_template_csv"):
        review_guard_missing_reasons.append("operator_template_missing")
    if not artifact.get("third_party_license_review_gate_approval_token_required"):
        review_guard_missing_reasons.append("approval_token_missing")
    if int(artifact.get("third_party_license_review_gate_review_row_count") or 0) < 1:
        review_guard_missing_reasons.append("review_row_missing")
    if int(artifact.get("third_party_license_review_gate_blocker_count") or 0) != 0:
        review_guard_missing_reasons.append("review_blockers_present")
    if int(artifact.get("third_party_license_review_gate_missing_review_asset_count") or 0) != 0:
        review_guard_missing_reasons.append("missing_review_assets_present")
    if int(artifact.get("third_party_license_review_gate_deferred_review_asset_count") or 0) != 0:
        review_guard_missing_reasons.append("deferred_review_assets_present")
    if artifact.get("third_party_license_review_gate_asset_modified") is True:
        review_guard_missing_reasons.append("asset_modified")
    if artifact.get("third_party_license_review_gate_legal_advice_provided") is True:
        review_guard_missing_reasons.append("legal_advice_claimed")
    if artifact.get("third_party_license_review_gate_external_state_mutated") is True:
        review_guard_missing_reasons.append("review_mutated_external_state")
    assert observed["third_party_license_review_gate_boundary_guard_ready"] is (
        not review_guard_missing_reasons
    )
    assert (
        observed["third_party_license_review_gate_boundary_guard_missing_reasons"]
        == review_guard_missing_reasons
    )


def _assert_product_release_bundle_fields(*, observed: dict, artifact: dict) -> None:
    policy = artifact.get("operator_promotion_policy")
    policy = policy if isinstance(policy, dict) else {}
    checks = artifact.get("checks")
    checks = [row for row in checks if isinstance(row, dict)] if isinstance(checks, list) else []
    failed_check_ids = [
        str(row.get("check") or "").strip()
        for row in checks
        if row.get("passed") is not True and str(row.get("check") or "").strip()
    ]
    approval_tokens = policy.get("approval_tokens_required") or []
    must_review_fields = policy.get("must_review_fields") or []
    required_before_execution = policy.get("required_before_execution") or []

    assert observed["product_release_bundle_status"] == artifact.get("status", "")
    assert observed["product_release_bundle_ready"] is (
        artifact.get("release_bundle_ready") is True
    )
    assert observed["product_release_bundle_artifact_path"].endswith(
        "runs/product_release_bundle_current.json"
    )
    assert observed["product_release_bundle_release_id"] == artifact.get("release_id", "")
    assert observed["product_release_bundle_bundle_version"] == artifact.get(
        "bundle_version", ""
    )
    assert observed["product_release_bundle_artifact_count"] == int(
        artifact.get("artifact_count") or 0
    )
    assert observed["product_release_bundle_check_count"] == int(
        artifact.get("check_count") or 0
    )
    assert observed["product_release_bundle_pass_count"] == int(
        artifact.get("pass_count") or 0
    )
    assert observed["product_release_bundle_blocker_count"] == int(
        artifact.get("blocker_count") or 0
    )
    assert observed["product_release_bundle_failed_check_ids"] == failed_check_ids
    assert observed["product_release_bundle_operator_policy_status"] == policy.get(
        "status", ""
    )
    assert observed[
        "product_release_bundle_operator_policy_approval_tokens_required"
    ] == approval_tokens
    assert observed["product_release_bundle_operator_policy_must_review_fields"] == (
        must_review_fields
    )
    assert observed[
        "product_release_bundle_operator_policy_required_before_execution"
    ] == required_before_execution
    assert observed[
        "product_release_bundle_operator_policy_external_state_mutation_allowed"
    ] is (policy.get("external_state_mutation_allowed") is True)

    guard_missing_reasons = []
    if artifact.get("status") != "release_bundle_ready_for_operator_review":
        guard_missing_reasons.append("bundle_status_not_ready")
    if artifact.get("release_bundle_ready") is not True:
        guard_missing_reasons.append("bundle_ready_flag_not_true")
    if int(artifact.get("blocker_count") or 0) != 0:
        guard_missing_reasons.append("blockers_present")
    if int(artifact.get("check_count") or 0) == 0 or int(
        artifact.get("pass_count") or 0
    ) != int(artifact.get("check_count") or 0):
        guard_missing_reasons.append("checks_not_all_passed")
    if failed_check_ids:
        guard_missing_reasons.append("failed_checks_present")
    if int(artifact.get("artifact_count") or 0) < 1:
        guard_missing_reasons.append("artifacts_missing")
    if policy.get("status") != "operator_approval_required":
        guard_missing_reasons.append("operator_policy_not_approval_required")
    if policy.get("external_state_mutation_allowed") is True:
        guard_missing_reasons.append("external_state_mutation_allowed")
    for token in (
        "APPROVE_PRODUCT_ROLLOUT",
        "APPROVE_HOSTED_PRODUCT_API_EXPOSURE",
        "MODEL_REGISTRY_SIGNING_KEY",
        "API_RESULT_MANIFEST_SIGNING_KEY",
    ):
        if token not in approval_tokens:
            guard_missing_reasons.append("approval_tokens_missing")
            break
    for field in ("target", "action", "impact", "risk", "rollback", "verification"):
        if field not in must_review_fields:
            guard_missing_reasons.append("must_review_fields_missing")
            break
    if len(required_before_execution) < 1:
        guard_missing_reasons.append("required_before_execution_missing")
    assert observed["product_release_bundle_operator_review_guard_ready"] is (
        not guard_missing_reasons
    )
    assert (
        observed["product_release_bundle_operator_review_guard_missing_reasons"]
        == guard_missing_reasons
    )


def _assert_product_scope_priority_fields(*, observed: dict, artifact: dict) -> None:
    guard_missing_reasons = []
    if artifact.get("status") != "product_scope_breadth_evidence_priority_packet_ready":
        guard_missing_reasons.append("priority_status_not_ready")
    if artifact.get("priority_packet_ready") is not True:
        guard_missing_reasons.append("priority_packet_ready_flag_not_true")
    if not artifact.get("top_item_id"):
        guard_missing_reasons.append("top_item_missing")
    if not artifact.get("top_required_evidence_type"):
        guard_missing_reasons.append("top_required_evidence_type_missing")
    if not artifact.get("top_review_template_artifact"):
        guard_missing_reasons.append("top_review_template_missing")
    if not artifact.get("top_apply_gate_artifact"):
        guard_missing_reasons.append("top_apply_gate_missing")
    if artifact.get("scope_promotion_allowed") is True:
        guard_missing_reasons.append("scope_promotion_allowed")
    if artifact.get("authoritative_apply_allowed") is True:
        guard_missing_reasons.append("authoritative_apply_allowed")
    if artifact.get("external_state_mutated") is True:
        guard_missing_reasons.append("external_state_mutated")

    assert observed["product_scope_breadth_evidence_priority_status"] == artifact.get(
        "status", ""
    )
    assert observed["product_scope_breadth_evidence_priority_packet_ready"] is (
        artifact.get("priority_packet_ready") is True
    )
    assert observed["product_scope_breadth_evidence_priority_artifact_path"].endswith(
        "runs/product_scope_breadth_evidence_priority_packet_current.json"
    )
    assert observed["product_scope_breadth_evidence_priority_queue_item_count"] == int(
        artifact.get("queue_item_count") or 0
    )
    assert observed["product_scope_breadth_evidence_priority_open_item_count"] == int(
        artifact.get("open_item_count") or 0
    )
    assert observed[
        "product_scope_breadth_evidence_priority_local_crosscheck_candidate_count"
    ] == int(artifact.get("local_crosscheck_candidate_count") or 0)
    assert observed[
        "product_scope_breadth_evidence_priority_scientific_evidence_request_count"
    ] == int(artifact.get("scientific_evidence_request_count") or 0)
    assert observed[
        "product_scope_breadth_evidence_priority_review_only_keep_blocked_count"
    ] == int(artifact.get("review_only_keep_blocked_count") or 0)
    assert observed["product_scope_breadth_evidence_priority_top_item_id"] == artifact.get(
        "top_item_id", ""
    )
    assert observed["product_scope_breadth_evidence_priority_top_domain"] == artifact.get(
        "top_domain", ""
    )
    assert observed["product_scope_breadth_evidence_priority_top_bucket"] == artifact.get(
        "top_bucket", ""
    )
    assert observed["product_scope_breadth_evidence_priority_top_target_id"] == artifact.get(
        "top_target_id", ""
    )
    assert observed[
        "product_scope_breadth_evidence_priority_top_target_promotion_status"
    ] == artifact.get("top_target_promotion_status", "")
    assert observed[
        "product_scope_breadth_evidence_priority_top_required_evidence_type"
    ] == artifact.get("top_required_evidence_type", "")
    assert observed[
        "product_scope_breadth_evidence_priority_top_review_template_artifact"
    ] == artifact.get("top_review_template_artifact", "")
    assert observed[
        "product_scope_breadth_evidence_priority_top_apply_gate_artifact"
    ] == artifact.get("top_apply_gate_artifact", "")
    assert observed["product_scope_breadth_evidence_priority_top_next_step"] == artifact.get(
        "top_next_step", ""
    )
    assert observed["product_scope_breadth_evidence_priority_receipt_status"] == artifact.get(
        "receipt_status", ""
    )
    assert observed["product_scope_breadth_evidence_priority_receipt_ready"] is (
        artifact.get("receipt_ready") is True
    )
    assert observed["product_scope_breadth_evidence_priority_receipt_csv"] == artifact.get(
        "receipt_csv", ""
    )
    assert observed["product_scope_breadth_evidence_priority_receipt_row_count"] == int(
        artifact.get("receipt_row_count") or 0
    )
    assert observed["product_scope_breadth_evidence_priority_receipt_blocked_row_count"] == int(
        artifact.get("receipt_blocked_row_count") or 0
    )
    assert observed[
        "product_scope_breadth_evidence_priority_receipt_operator_review_surface_ready_count"
    ] == int(artifact.get("receipt_operator_review_surface_ready_count") or 0)
    assert observed[
        "product_scope_breadth_evidence_priority_receipt_operator_review_surface_blocked_count"
    ] == int(artifact.get("receipt_operator_review_surface_blocked_count") or 0)
    assert observed[
        "product_scope_breadth_evidence_priority_receipt_manual_field_pending_count"
    ] == int(artifact.get("receipt_manual_field_pending_count") or 0)
    assert observed[
        "product_scope_breadth_evidence_priority_receipt_evidence_artifact_pending_count"
    ] == int(artifact.get("receipt_evidence_artifact_pending_count") or 0)
    assert observed[
        "product_scope_breadth_evidence_priority_receipt_claim_ready_pending_count"
    ] == int(artifact.get("receipt_claim_ready_pending_count") or 0)
    assert observed[
        "product_scope_breadth_evidence_priority_receipt_reviewer_pending_count"
    ] == int(artifact.get("receipt_reviewer_pending_count") or 0)
    assert observed[
        "product_scope_breadth_evidence_priority_receipt_reviewed_at_utc_pending_count"
    ] == int(artifact.get("receipt_reviewed_at_utc_pending_count") or 0)
    assert observed[
        "product_scope_breadth_evidence_priority_receipt_license_ok_pending_count"
    ] == int(artifact.get("receipt_license_ok_pending_count") or 0)
    assert observed[
        "product_scope_breadth_evidence_priority_receipt_approval_token_pending_count"
    ] == int(artifact.get("receipt_approval_token_pending_count") or 0)
    assert observed[
        "product_scope_breadth_evidence_priority_receipt_first_blocked_scope_blocker_id"
    ] == artifact.get("receipt_first_blocked_scope_blocker_id", "")
    assert observed[
        "product_scope_breadth_evidence_priority_receipt_first_blocked_evidence_artifact"
    ] == artifact.get("receipt_first_blocked_evidence_artifact", "")
    assert observed[
        "product_scope_breadth_evidence_priority_receipt_first_blocked_expected_evidence_status"
    ] == artifact.get("receipt_first_blocked_expected_evidence_status", "")
    assert observed[
        "product_scope_breadth_evidence_priority_receipt_first_blocked_observed_evidence_status"
    ] == artifact.get("receipt_first_blocked_observed_evidence_status", "")
    assert observed[
        "product_scope_breadth_evidence_priority_receipt_first_blocked_missing_true_fields"
    ] == (artifact.get("receipt_first_blocked_missing_true_fields") or [])
    assert observed[
        "product_scope_breadth_evidence_priority_receipt_first_blocked_row_blockers"
    ] == (artifact.get("receipt_first_blocked_row_blockers") or [])
    assert observed[
        "product_scope_breadth_evidence_priority_receipt_most_common_row_blocker"
    ] == artifact.get("receipt_most_common_row_blocker", "")
    assert observed[
        "product_scope_breadth_evidence_priority_receipt_approval_token_required"
    ] == artifact.get("receipt_approval_token_required", "")
    assert observed[
        "product_scope_breadth_evidence_priority_transporter_target_ready_for_promotion_count"
    ] == int(artifact.get("transporter_target_ready_for_promotion_count") or 0)
    assert observed[
        "product_scope_breadth_evidence_priority_transporter_target_ready_for_promotion_ids"
    ] == (artifact.get("transporter_target_ready_for_promotion_ids") or [])
    assert observed[
        "product_scope_breadth_evidence_priority_transporter_target_blocked_for_promotion_count"
    ] == int(artifact.get("transporter_target_blocked_for_promotion_count") or 0)
    assert observed[
        "product_scope_breadth_evidence_priority_transporter_target_blocked_for_promotion_ids"
    ] == (artifact.get("transporter_target_blocked_for_promotion_ids") or [])
    assert observed[
        "product_scope_breadth_evidence_priority_scope_promotion_allowed"
    ] is (artifact.get("scope_promotion_allowed") is True)
    assert observed[
        "product_scope_breadth_evidence_priority_authoritative_apply_allowed"
    ] is (artifact.get("authoritative_apply_allowed") is True)
    assert observed[
        "product_scope_breadth_evidence_priority_external_state_mutated"
    ] is (artifact.get("external_state_mutated") is True)
    assert observed["product_scope_breadth_evidence_priority_source_artifacts"] == (
        artifact.get("source_artifacts") or []
    )
    assert observed[
        "product_scope_breadth_evidence_priority_operator_review_guard_ready"
    ] is (not guard_missing_reasons)
    assert observed[
        "product_scope_breadth_evidence_priority_operator_review_guard_missing_reasons"
    ] == guard_missing_reasons


def _assert_engine_priority_fields(*, observed: dict, artifact: dict) -> None:
    approval_token_required = artifact.get("approval_token_required") or ""
    guard_missing_reasons = []
    if artifact.get("priority_packet_ready") is not True:
        guard_missing_reasons.append("priority_packet_ready_flag_not_true")
    if not str(artifact.get("status") or "").strip():
        guard_missing_reasons.append("priority_status_missing")
    if int(artifact.get("operator_input_required_count") or 0) < 1:
        guard_missing_reasons.append("operator_input_required_count_missing")
    if not artifact.get("top_blocker_id"):
        guard_missing_reasons.append("top_blocker_missing")
    if not artifact.get("top_required_input"):
        guard_missing_reasons.append("top_required_input_missing")
    if not artifact.get("top_acceptance_artifact"):
        guard_missing_reasons.append("top_acceptance_artifact_missing")
    if not artifact.get("top_verification_command"):
        guard_missing_reasons.append("top_verification_command_missing")
    if approval_token_required != "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT":
        guard_missing_reasons.append("approval_token_required_mismatch")
    if artifact.get("claim_promotion_allowed") is True:
        guard_missing_reasons.append("claim_promotion_allowed")
    if artifact.get("external_state_mutated") is True:
        guard_missing_reasons.append("external_state_mutated")

    assert observed["engine_refinement_claim_evidence_priority_status"] == artifact.get(
        "status", ""
    )
    assert observed["engine_refinement_claim_evidence_priority_packet_ready"] is (
        artifact.get("priority_packet_ready") is True
    )
    assert observed["engine_refinement_claim_evidence_priority_artifact_path"].endswith(
        "runs/engine_refinement_claim_evidence_priority_packet_current.json"
    )
    assert observed["engine_refinement_claim_evidence_priority_priority_item_count"] == int(
        artifact.get("priority_item_count") or 0
    )
    assert observed[
        "engine_refinement_claim_evidence_priority_blocked_priority_item_count"
    ] == int(artifact.get("blocked_priority_item_count") or 0)
    assert observed[
        "engine_refinement_claim_evidence_priority_operator_input_required_count"
    ] == int(artifact.get("operator_input_required_count") or 0)
    assert observed[
        "engine_refinement_claim_evidence_priority_required_blocker_count"
    ] == int(artifact.get("required_blocker_count") or 0)
    assert observed[
        "engine_refinement_claim_evidence_priority_missing_required_blocker_count"
    ] == int(artifact.get("missing_required_blocker_count") or 0)
    assert observed[
        "engine_refinement_claim_evidence_priority_missing_required_blockers"
    ] == (artifact.get("missing_required_blockers") or [])
    assert observed["engine_refinement_claim_evidence_priority_blocker_count"] == int(
        artifact.get("blocker_count") or 0
    )
    assert observed["engine_refinement_claim_evidence_priority_blockers"] == (
        artifact.get("blockers") or []
    )
    assert observed["engine_refinement_claim_evidence_priority_top_blocker_id"] == artifact.get(
        "top_blocker_id", ""
    )
    assert observed[
        "engine_refinement_claim_evidence_priority_top_priority_bucket"
    ] == artifact.get("top_priority_bucket", "")
    assert observed[
        "engine_refinement_claim_evidence_priority_top_required_input"
    ] == artifact.get("top_required_input", "")
    assert observed[
        "engine_refinement_claim_evidence_priority_top_acceptance_artifact"
    ] == artifact.get("top_acceptance_artifact", "")
    assert observed[
        "engine_refinement_claim_evidence_priority_top_next_operator_step"
    ] == artifact.get("top_next_operator_step", "")
    assert observed[
        "engine_refinement_claim_evidence_priority_top_verification_command"
    ] == artifact.get("top_verification_command", "")
    assert observed[
        "engine_refinement_claim_evidence_priority_public_benchmark_status"
    ] == artifact.get("public_benchmark_status", "")
    assert observed[
        "engine_refinement_claim_evidence_priority_public_benchmark_gate_ready"
    ] is (artifact.get("public_benchmark_gate_ready") is True)
    assert observed[
        "engine_refinement_claim_evidence_priority_public_benchmark_work_order_present"
    ] is (artifact.get("public_benchmark_work_order_present") is True)
    assert observed[
        "engine_refinement_claim_evidence_priority_public_benchmark_work_order_row_count"
    ] == int(artifact.get("public_benchmark_work_order_row_count") or 0)
    assert observed[
        "engine_refinement_claim_evidence_priority_public_benchmark_work_order_apply_status"
    ] == artifact.get("public_benchmark_work_order_apply_status", "")
    assert observed[
        "engine_refinement_claim_evidence_priority_public_benchmark_work_order_apply_ready"
    ] is (artifact.get("public_benchmark_work_order_apply_ready") is True)
    assert observed[
        "engine_refinement_claim_evidence_priority_public_benchmark_work_order_apply_blocked_row_count"
    ] == int(artifact.get("public_benchmark_work_order_apply_blocked_row_count") or 0)
    assert observed[
        "engine_refinement_claim_evidence_priority_claim_evidence_receipt_status"
    ] == artifact.get("claim_evidence_receipt_status", "")
    assert observed[
        "engine_refinement_claim_evidence_priority_claim_evidence_receipt_ready"
    ] is (artifact.get("claim_evidence_receipt_ready") is True)
    assert observed[
        "engine_refinement_claim_evidence_priority_claim_promotion_allowed"
    ] is (artifact.get("claim_promotion_allowed") is True)
    assert observed[
        "engine_refinement_claim_evidence_priority_approval_token_required"
    ] == approval_token_required
    assert observed["engine_refinement_claim_evidence_priority_approval_token_count"] == int(
        artifact.get("approval_token_count") or 0
    )
    assert observed[
        "engine_refinement_claim_evidence_priority_external_state_mutated"
    ] is (artifact.get("external_state_mutated") is True)
    assert observed["engine_refinement_claim_evidence_priority_source_artifacts"] == (
        artifact.get("source_artifacts") or []
    )
    assert observed[
        "engine_refinement_claim_evidence_priority_operator_review_guard_ready"
    ] is (not guard_missing_reasons)
    assert observed[
        "engine_refinement_claim_evidence_priority_operator_review_guard_missing_reasons"
    ] == guard_missing_reasons


def test_goal_priority_queue_endpoint_reads_fail_closed_pm_queue(monkeypatch, tmp_path: Path) -> None:
    from api import goal as goal_api

    artifact = tmp_path / ".betelgeuze/pm_priority_queue_status_current.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "blocked_pm_priority_queue",
                    "ready_item_count": 3,
                    "blocked_item_count": 5,
                    "first_blocked_item_id": "2",
                    "next_required_step": "Restore F2/G1 implementation tree.",
                    "claim_boundary": "pm boundary",
                },
                "rows": [
                    {
                        "item_id": "2",
                        "status": "blocked_f2g_f2h_surface_preflight",
                        "ready": False,
                        "blocker": "f2g_authoritative_surfaces_missing",
                        "next_action": "Restore F2/G1 implementation tree.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(goal_api, "PM_PRIORITY_QUEUE_ARTIFACT", artifact)

    response = asyncio.run(goal_api.get_goal_priority_queue())

    assert response["status"] == "blocked_pm_priority_queue"
    assert response["ready_item_count"] == 3
    assert response["blocked_item_count"] == 5
    assert response["first_blocked_item_id"] == "2"
    assert response["first_blocked_blocker"] == "f2g_authoritative_surfaces_missing"
    assert response["first_blocked_next_action"] == "Restore F2/G1 implementation tree."
    assert response["first_blocked_item"]["item_id"] == "2"
    assert response["rows"][0]["status"] == "blocked_f2g_f2h_surface_preflight"
    assert response["execution_enabled"] is False
    assert response["external_state_mutated"] is False
    assert response["claim_boundary"] == "pm boundary"

    monkeypatch.setattr(goal_api, "PM_PRIORITY_QUEUE_ARTIFACT", tmp_path / "missing.json")
    missing = asyncio.run(goal_api.get_goal_priority_queue())
    assert missing["status"] == "missing_pm_priority_queue_status"
    assert missing["ready_item_count"] == 0
    assert missing["blocked_item_count"] == 0
    assert missing["first_blocked_item"] == {}
    assert missing["rows"] == []
    assert missing["execution_enabled"] is False
    assert missing["external_state_mutated"] is False


def test_goal_developer_preview_endpoint_reads_fail_closed_audit(monkeypatch, tmp_path: Path) -> None:
    from api import goal as goal_api

    artifact = tmp_path / "runs/developer_preview_final_gate_audit_current.json"
    clean_checkout_receipt = (
        tmp_path / ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
    )
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "blocked_developer_preview_final_gate_audit",
                    "developer_preview_clean_baseline_ready": False,
                    "gate_count": 6,
                    "ready_gate_count": 3,
                    "blocked_gate_count": 3,
                    "receipt_work_order_row_count": 29,
                    "receipt_work_order_source_blocker_count": 5,
                    "receipt_work_order_primary_source_blocker_gate_id": (
                        "benchmark_results_clean_checkout_regenerated"
                    ),
                    "receipt_work_order_primary_source_blocker_receipt_artifact": (
                        ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
                    ),
                    "receipt_work_order_primary_source_blocker": (
                        ".betelgeuze/developer_preview_clean_checkout_ai_verify.log:missing"
                    ),
                    "receipt_work_order_primary_source_blocker_required_action": (
                        "Attach the missing source evidence required by the receipt."
                    ),
                    "primary_blocker_id": "benchmark_results_clean_checkout_regenerated",
                    "next_required_step": "Attach clean-checkout receipt.",
                    "claim_boundary": "developer preview boundary",
                },
                "rows": [
                    {
                        "gate_id": "benchmark_results_clean_checkout_regenerated",
                        "status": "blocked_developer_preview_gate",
                        "ready": False,
                    }
                ],
                "receipt_work_order_rows": [
                    {
                        "gate_id": "benchmark_results_clean_checkout_regenerated",
                        "receipt_artifact": ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json",
                        "blocker_detail": "status=blocked_developer_preview_clean_checkout_benchmark_receipt",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    clean_checkout_receipt.parent.mkdir(parents=True)
    clean_checkout_receipt.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "blocked_developer_preview_clean_checkout_benchmark_receipt",
                    "clean_checkout_benchmark_regenerated": False,
                    "ai_verify_passed": True,
                    "reviewed_receipt_attached": False,
                    "reviewer_id_present": False,
                    "reviewed_at_utc_present": False,
                    "blocker_count": 3,
                    "failed_count": 2,
                    "baseline_summary_present": True,
                    "baseline_task_count": 0,
                    "baseline_score_row_count": 0,
                    "baseline_score_leaderboard_count": 0,
                    "baseline_score_leaderboard_csv_count": 0,
                    "baseline_ranking_summary_missing_count": 0,
                },
                "rows": [
                    {
                        "check": "clean_checkout_ai_verify",
                        "status": "pass",
                        "artifact_path": ".betelgeuze/developer_preview_clean_checkout_ai_verify.log",
                        "blockers": [],
                    },
                    {
                        "check": "baseline_summary",
                        "status": "blocked",
                        "artifact_path": (
                            ".betelgeuze/developer_preview_external_baselines/"
                            "biorxiv_baseline_comparison_developer_preview_clean_checkout/summary.json"
                        ),
                        "blockers": [
                            "baseline_task_count_zero",
                            "baseline_score_leaderboard_empty",
                        ],
                    },
                    {
                        "check": "operator_review",
                        "status": "blocked",
                        "blockers": [
                            "reviewed_receipt_attached_not_true",
                            "reviewer_id_missing",
                            "reviewed_at_utc_missing",
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(goal_api, "DEVELOPER_PREVIEW_FINAL_GATE_AUDIT_ARTIFACT", artifact)
    monkeypatch.setattr(
        goal_api,
        "DEVELOPER_PREVIEW_CLEAN_CHECKOUT_RECEIPT_ARTIFACT",
        clean_checkout_receipt,
    )

    response = asyncio.run(goal_api.get_goal_developer_preview())

    assert response["status"] == "blocked_developer_preview_final_gate_audit"
    assert response["developer_preview_clean_baseline_ready"] is False
    assert response["gate_count"] == 6
    assert response["ready_gate_count"] == 3
    assert response["blocked_gate_count"] == 3
    assert response["receipt_work_order_row_count"] == 29
    assert response["receipt_work_order_source_blocker_count"] == 5
    assert response["receipt_work_order_primary_source_blocker_gate_id"] == (
        "benchmark_results_clean_checkout_regenerated"
    )
    assert response["receipt_work_order_primary_source_blocker_receipt_artifact"] == (
        ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
    )
    assert response["receipt_work_order_primary_source_blocker"] == (
        ".betelgeuze/developer_preview_clean_checkout_ai_verify.log:missing"
    )
    assert response["receipt_work_order_primary_source_blocker_required_action"] == (
        "Attach the missing source evidence required by the receipt."
    )
    assert response["rows"][0]["gate_id"] == "benchmark_results_clean_checkout_regenerated"
    assert response["receipt_work_order_rows"][0]["blocker_detail"] == (
        "status=blocked_developer_preview_clean_checkout_benchmark_receipt"
    )
    assert response["clean_checkout_receipt_status"] == (
        "blocked_developer_preview_clean_checkout_benchmark_receipt"
    )
    assert response["clean_checkout_receipt_ready"] is False
    assert response["clean_checkout_ai_verify_passed"] is True
    assert response["clean_checkout_benchmark_regenerated"] is False
    assert response["clean_checkout_reviewed_receipt_attached"] is False
    assert response["clean_checkout_blocker_count"] == 3
    assert response["clean_checkout_failed_count"] == 2
    assert response["clean_checkout_baseline_summary_present"] is True
    assert response["clean_checkout_baseline_task_count"] == 0
    assert response["clean_checkout_source_evidence_ready"] is False
    assert response["clean_checkout_source_evidence"][0]["check"] == "clean_checkout_ai_verify"
    assert response["clean_checkout_source_evidence"][1]["check"] == "baseline_summary"
    assert "baseline_task_count_zero" in response["clean_checkout_source_blockers"]
    assert "reviewer_id_missing" in response["clean_checkout_source_blockers"]
    assert response["developer_demo_wording_allowed"] is False
    assert response["paid_pilot_wording_allowed"] is False
    assert response["execution_enabled"] is False
    assert response["external_state_mutated"] is False
    assert response["claim_boundary"] == "developer preview boundary"

    monkeypatch.setattr(goal_api, "DEVELOPER_PREVIEW_FINAL_GATE_AUDIT_ARTIFACT", tmp_path / "missing.json")
    missing = asyncio.run(goal_api.get_goal_developer_preview())
    assert missing["status"] == "missing_developer_preview_final_gate_audit"
    assert missing["developer_preview_clean_baseline_ready"] is False
    assert missing["gate_count"] == 0
    assert missing["receipt_work_order_rows"] == []
    assert missing["receipt_work_order_source_blocker_count"] == 0
    assert missing["receipt_work_order_primary_source_blocker"] == ""
    assert missing["clean_checkout_receipt_ready"] is False
    assert missing["developer_demo_wording_allowed"] is False
    assert missing["paid_pilot_wording_allowed"] is False
    assert missing["execution_enabled"] is False
    assert missing["external_state_mutated"] is False


def test_goal_public_benchmark_endpoint_reads_fail_closed_receipts(monkeypatch, tmp_path: Path) -> None:
    from api import goal as goal_api

    audit_artifact = tmp_path / "runs/public_benchmark_external_receipts_audit_current.json"
    attach_artifact = tmp_path / "runs/public_benchmark_receipt_attach_packet_current.json"
    audit_artifact.parent.mkdir(parents=True)
    audit_artifact.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "blocked_public_benchmark_external_receipts_audit",
                    "external_benchmark_receipts_ready": False,
                    "blocker_count": 2,
                    "ready_step_count": 5,
                    "blocked_step_count": 2,
                    "receipt_blocked_row_count": 51,
                    "next_required_step": "Fill public benchmark receipts.",
                    "claim_boundary": "benchmark audit boundary",
                },
                "rows": [
                    {
                        "step_id": "vina_gnina_same_input_comparison",
                        "status": "blocked",
                        "ready": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    attach_artifact.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "blocked_public_benchmark_receipt_attach_packet",
                    "receipt_attach_packet_ready": False,
                    "external_benchmark_receipts_ready": False,
                    "blocker_count": 2,
                    "field_work_order_row_count": 22,
                    "field_work_order_primary_lane_id": "vina_gnina_same_input_scores",
                    "field_work_order_primary_field_name": "approval_token",
                    "field_work_order_primary_pending_row_count": 16,
                    "field_work_order_primary_required_value": (
                        "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES for approval_token"
                    ),
                    "field_work_order_primary_required_action": (
                        "Fill approval_token with APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES "
                        "after operator review."
                    ),
                    "field_work_order_primary_approval_token_required": (
                        "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES"
                    ),
                    "field_work_order_primary_operator_csv": (
                        "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
                    ),
                    "field_work_order_primary_source_artifact": (
                        "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
                    ),
                    "vina_gnina_score_value_pending_count": 32,
                    "vina_gnina_operator_metadata_pending_count": 128,
                    "vina_gnina_approval_token_pending_count": 16,
                    "metric_source_receipt_blocked_row_count": 51,
                    "metric_source_receipt_manual_field_pending_count": 510,
                    "next_required_step": "Fill score-template rows.",
                    "claim_boundary": "receipt attach boundary",
                },
                "rows": [
                    {
                        "lane_id": "vina_gnina_same_input_scores",
                        "status": "blocked",
                        "ready": False,
                    }
                ],
                "field_work_order_rows": [
                    {
                        "lane_id": "vina_gnina_same_input_scores",
                        "field_name": "approval_token",
                        "pending_row_count": 16,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(goal_api, "PUBLIC_BENCHMARK_EXTERNAL_RECEIPTS_AUDIT_ARTIFACT", audit_artifact)
    monkeypatch.setattr(goal_api, "PUBLIC_BENCHMARK_RECEIPT_ATTACH_PACKET_ARTIFACT", attach_artifact)

    response = asyncio.run(goal_api.get_goal_public_benchmark())

    assert response["status"] == "blocked_public_benchmark_receipt_attach_packet"
    assert response["audit_status"] == "blocked_public_benchmark_external_receipts_audit"
    assert response["receipt_attach_packet_status"] == "blocked_public_benchmark_receipt_attach_packet"
    assert response["external_benchmark_receipts_ready"] is False
    assert response["receipt_attach_packet_ready"] is False
    assert response["blocker_count"] == 2
    assert response["ready_step_count"] == 5
    assert response["blocked_step_count"] == 2
    assert response["receipt_blocked_row_count"] == 51
    assert response["field_work_order_row_count"] == 22
    assert response["field_work_order_primary_lane_id"] == "vina_gnina_same_input_scores"
    assert response["field_work_order_primary_field_name"] == "approval_token"
    assert response["field_work_order_primary_pending_row_count"] == 16
    assert response["field_work_order_primary_required_value"] == (
        "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES for approval_token"
    )
    assert response["field_work_order_primary_required_action"] == (
        "Fill approval_token with APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES "
        "after operator review."
    )
    assert response["field_work_order_primary_approval_token_required"] == (
        "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES"
    )
    assert response["field_work_order_primary_operator_csv"] == (
        "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
    )
    assert response["field_work_order_primary_source_artifact"] == (
        "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
    )
    assert response["vina_gnina_score_value_pending_count"] == 32
    assert response["metric_source_receipt_manual_field_pending_count"] == 510
    assert response["rows"][0]["step_id"] == "vina_gnina_same_input_comparison"
    assert response["receipt_attach_rows"][0]["lane_id"] == "vina_gnina_same_input_scores"
    assert response["field_work_order_rows"][0]["field_name"] == "approval_token"
    assert response["next_required_step"] == "Fill score-template rows."
    assert response["execution_enabled"] is False
    assert response["external_state_mutated"] is False
    assert response["claim_boundary"] == "receipt attach boundary"

    monkeypatch.setattr(goal_api, "PUBLIC_BENCHMARK_EXTERNAL_RECEIPTS_AUDIT_ARTIFACT", tmp_path / "missing-audit.json")
    monkeypatch.setattr(
        goal_api,
        "PUBLIC_BENCHMARK_RECEIPT_ATTACH_PACKET_ARTIFACT",
        tmp_path / "missing-attach.json",
    )
    missing = asyncio.run(goal_api.get_goal_public_benchmark())
    assert missing["status"] == "missing_public_benchmark_receipts"
    assert missing["external_benchmark_receipts_ready"] is False
    assert missing["receipt_attach_packet_ready"] is False
    assert missing["field_work_order_primary_required_action"] == ""
    assert missing["field_work_order_rows"] == []
    assert missing["execution_enabled"] is False
    assert missing["external_state_mutated"] is False


def test_goal_customer_shadow_endpoint_reads_fail_closed_evidence(monkeypatch, tmp_path: Path) -> None:
    from api import goal as goal_api

    artifact = tmp_path / "runs/customer_shadow_evidence_status_current.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "blocked_customer_shadow_evidence_status",
                    "customer_shadow_intake_schema_ready": True,
                    "customer_shadow_minimum_met": False,
                    "completed_customer_shadow_case_count": 0,
                    "required_completed_customer_shadow_case_count": 3,
                    "missing_completed_customer_shadow_case_count": 3,
                    "customer_shadow_work_order_ready": False,
                    "customer_shadow_work_order_row_count": 3,
                    "customer_shadow_work_order_primary_case_slot_id": "customer_shadow_case_1",
                    "customer_shadow_work_order_primary_required_action": (
                        "Add one reviewed real customer-shadow metadata row."
                    ),
                    "customer_shadow_work_order_primary_operator_csv": (
                        "config/customer_shadow_evidence_intake_template.csv"
                    ),
                    "customer_shadow_work_order_primary_required_row_kind": "customer_shadow",
                    "customer_shadow_work_order_primary_required_raw_data_custody": "customer_retained",
                    "customer_shadow_work_order_primary_required_customer_retained_raw_data": True,
                    "customer_shadow_work_order_primary_required_redistribution_allowed": False,
                    "customer_shadow_work_order_primary_required_raw_data_stored_in_repo": False,
                    "customer_shadow_work_order_primary_required_derived_metadata_fields": [
                        "artifact_fingerprint",
                        "case_domain",
                        "input_size_class",
                        "result_metric_summary",
                        "runner_profile",
                    ],
                    "customer_shadow_work_order_primary_required_reviewer_signoff_status": "approved",
                    "customer_shadow_work_order_primary_required_source_artifact_fingerprint": "sha256",
                    "paid_pilot_claim_allowed": False,
                    "commercial_readiness_promotion_allowed": False,
                    "next_required_step": "Collect three reviewed customer-shadow rows.",
                    "claim_boundary": "customer shadow boundary",
                },
                "rows": [],
                "customer_shadow_work_order_rows": [
                    {
                        "case_slot_id": "customer_shadow_case_1",
                        "required_customer_retained_raw_data": True,
                        "required_raw_data_stored_in_repo": False,
                        "required_redistribution_allowed": False,
                        "required_reviewer_signoff_status": "approved",
                        "paid_pilot_claim_allowed": False,
                        "commercial_readiness_promotion_allowed": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(goal_api, "CUSTOMER_SHADOW_EVIDENCE_STATUS_ARTIFACT", artifact)

    response = asyncio.run(goal_api.get_goal_customer_shadow())

    assert response["status"] == "blocked_customer_shadow_evidence_status"
    assert response["customer_shadow_intake_schema_ready"] is True
    assert response["customer_shadow_minimum_met"] is False
    assert response["completed_customer_shadow_case_count"] == 0
    assert response["required_completed_customer_shadow_case_count"] == 3
    assert response["missing_completed_customer_shadow_case_count"] == 3
    assert response["customer_shadow_work_order_ready"] is False
    assert response["customer_shadow_work_order_row_count"] == 3
    assert response["customer_shadow_work_order_primary_case_slot_id"] == "customer_shadow_case_1"
    assert response["customer_shadow_work_order_primary_required_action"] == (
        "Add one reviewed real customer-shadow metadata row."
    )
    assert response["customer_shadow_work_order_primary_operator_csv"] == (
        "config/customer_shadow_evidence_intake_template.csv"
    )
    assert response["customer_shadow_work_order_primary_required_row_kind"] == "customer_shadow"
    assert response["customer_shadow_work_order_primary_required_raw_data_custody"] == "customer_retained"
    assert response["customer_shadow_work_order_primary_required_customer_retained_raw_data"] is True
    assert response["customer_shadow_work_order_primary_required_redistribution_allowed"] is False
    assert response["customer_shadow_work_order_primary_required_raw_data_stored_in_repo"] is False
    assert response["customer_shadow_work_order_primary_required_derived_metadata_fields"] == [
        "artifact_fingerprint",
        "case_domain",
        "input_size_class",
        "result_metric_summary",
        "runner_profile",
    ]
    assert response["customer_shadow_work_order_primary_required_reviewer_signoff_status"] == "approved"
    assert response["customer_shadow_work_order_primary_required_source_artifact_fingerprint"] == "sha256"
    assert response["paid_pilot_claim_allowed"] is False
    assert response["commercial_readiness_promotion_allowed"] is False
    assert response["rows"] == []
    assert response["customer_shadow_work_order_rows"][0]["case_slot_id"] == "customer_shadow_case_1"
    assert response["customer_shadow_work_order_rows"][0]["required_raw_data_stored_in_repo"] is False
    assert response["execution_enabled"] is False
    assert response["external_state_mutated"] is False
    assert response["claim_boundary"] == "customer shadow boundary"

    monkeypatch.setattr(goal_api, "CUSTOMER_SHADOW_EVIDENCE_STATUS_ARTIFACT", tmp_path / "missing.json")
    missing = asyncio.run(goal_api.get_goal_customer_shadow())
    assert missing["status"] == "missing_customer_shadow_evidence_status"
    assert missing["customer_shadow_intake_schema_ready"] is False
    assert missing["customer_shadow_minimum_met"] is False
    assert missing["completed_customer_shadow_case_count"] == 0
    assert missing["required_completed_customer_shadow_case_count"] == 3
    assert missing["missing_completed_customer_shadow_case_count"] == 3
    assert missing["customer_shadow_work_order_ready"] is False
    assert missing["customer_shadow_work_order_row_count"] == 0
    assert missing["customer_shadow_work_order_primary_required_derived_metadata_fields"] == []
    assert missing["paid_pilot_claim_allowed"] is False
    assert missing["commercial_readiness_promotion_allowed"] is False
    assert missing["customer_shadow_work_order_rows"] == []
    assert missing["execution_enabled"] is False
    assert missing["external_state_mutated"] is False


def test_api_app_imports_with_goal_router() -> None:
    from api.main import app
    from api.goal import (
        get_goal_actions,
        get_goal_api_contract,
        get_goal_bottlenecks,
        get_goal_burndown,
        get_goal_customer_shadow,
        get_goal_developer_preview,
        get_goal_operator_intake_kit,
        get_goal_priority_queue,
        get_goal_public_benchmark,
        get_goal_readiness,
        get_goal_release_decision,
        get_goal_status,
    )

    paths = {route.path for route in app.routes}
    assert "/goal/status" in paths
    assert "/goal/readiness" in paths
    assert "/goal/priority-queue" in paths
    assert "/goal/developer-preview" in paths
    assert "/goal/public-benchmark" in paths
    assert "/goal/customer-shadow" in paths
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
    product_release_bundle_artifact = _artifact_payload("product_release_bundle_current.json")
    scope_priority_artifact = _artifact_summary(
        "product_scope_breadth_evidence_priority_packet_current.json"
    )
    engine_priority_artifact = _artifact_summary(
        "engine_refinement_claim_evidence_priority_packet_current.json"
    )
    cameo_fetch_artifact = _artifact_summary("cameo_official_result_fetch_preflight_current.json")
    rollout_smoke_receipt_artifact = _artifact_summary(
        "product_rollout_execution_smoke_receipt_current.json"
    )
    launch_r4_preflight_artifact = _artifact_summary("product_launch_r4_preflight_current.json")
    deploy_ops_legal_artifact = _artifact_summary(
        "deploy_ops_legal_gap_closure_current.json"
    )
    scope_receipt_artifact = _artifact_summary("product_scope_breadth_evidence_receipt_current.json")
    engine_receipt_artifact = _artifact_summary(
        "engine_refinement_claim_evidence_receipt_current.json"
    )
    full_matrix_artifact = _artifact_summary(
        "product_full_commercial_blocker_evidence_matrix_current.json"
    )

    status = asyncio.run(get_goal_status())
    readiness = asyncio.run(get_goal_readiness())
    priority_queue = asyncio.run(get_goal_priority_queue())
    actions = asyncio.run(get_goal_actions())
    intake_kit = asyncio.run(get_goal_operator_intake_kit())
    release = asyncio.run(get_goal_release_decision())
    burndown = asyncio.run(get_goal_burndown())
    bottlenecks = asyncio.run(get_goal_bottlenecks())
    api_contract = asyncio.run(get_goal_api_contract())

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
    assert status["operator_action_board_full_commercial_release_blocker_ids"] == actions_artifact.get(
        "full_commercial_release_blocker_ids"
    )
    assert status["operator_action_board_full_commercial_release_blocker_count"] == int(
        actions_artifact.get("full_commercial_release_blocker_count") or 0
    )
    assert status["operator_intake_kit_full_commercial_release_blocker_ids"] == intake_artifact.get(
        "full_commercial_release_blocker_ids"
    )
    assert status["operator_intake_kit_full_commercial_release_blocker_count"] == int(
        intake_artifact.get("full_commercial_release_blocker_count") or 0
    )
    assert status["bottleneck_briefing_full_commercial_release_blocker_ids"] == (
        bottlenecks_artifact.get("full_commercial_release_blocker_ids")
    )
    assert status["bottleneck_briefing_full_commercial_release_blocker_count"] == int(
        bottlenecks_artifact.get("full_commercial_release_blocker_count") or 0
    )
    assert status["full_commercial_release_blocker_downstream_visibility_ready"] is True
    assert status["full_commercial_release_blocker_downstream_missing_surfaces"] == []
    assert status["primary_full_commercial_release_blocker_id"] == release_artifact.get(
        "primary_full_commercial_release_blocker_id"
    )
    assert status["primary_full_commercial_release_blocker_requirement_id"] == release_artifact.get(
        "primary_full_commercial_release_blocker_requirement_id"
    )
    assert status["primary_full_commercial_release_blocker_tier"] == release_artifact.get(
        "primary_full_commercial_release_blocker_tier"
    )
    assert status["primary_full_commercial_release_blocker"] == release_artifact.get(
        "primary_full_commercial_release_blocker"
    )
    assert status["primary_full_commercial_release_blocker_blocked_row_count"] == int(
        release_artifact.get("primary_full_commercial_release_blocker_blocked_row_count") or 0
    )
    assert status["primary_full_commercial_release_blocker_first_blocked_evidence_row_id"] == (
        release_artifact.get("primary_full_commercial_release_blocker_first_blocked_evidence_row_id")
    )
    assert status["primary_full_commercial_release_blocker_receipt_csv"] == release_artifact.get(
        "primary_full_commercial_release_blocker_receipt_csv"
    )
    assert status["primary_full_commercial_release_blocker_approval_token_required"] == (
        release_artifact.get("primary_full_commercial_release_blocker_approval_token_required")
    )
    assert status["primary_full_commercial_release_blocker_next_required_step"] == (
        release_artifact.get("primary_full_commercial_release_blocker_next_required_step")
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
    api_runner_guard_missing_reasons = []
    if release_artifact.get("api_runner_profile_promotion_operator_receipt_gate_present") is not True:
        api_runner_guard_missing_reasons.append("gate_not_present")
    if release_artifact.get("api_runner_profile_promotion_operator_receipt_recorded") is not True:
        api_runner_guard_missing_reasons.append("receipt_not_recorded")
    if not release_artifact.get("api_runner_profile_promotion_operator_receipt_operator_template_csv"):
        api_runner_guard_missing_reasons.append("operator_template_missing")
    if not release_artifact.get("api_runner_profile_promotion_operator_receipt_approval_token_required"):
        api_runner_guard_missing_reasons.append("approval_token_required_missing")
    for field, reason in [
        (
            "api_runner_profile_promotion_operator_receipt_profile_enabled_by_this_tool",
            "profile_enabled_by_this_tool",
        ),
        ("api_runner_profile_promotion_operator_receipt_runner_executed", "runner_executed"),
        (
            "api_runner_profile_promotion_operator_receipt_external_state_mutated",
            "external_state_mutated",
        ),
    ]:
        if release_artifact.get(field) is True:
            api_runner_guard_missing_reasons.append(reason)
    assert status["api_runner_profile_promotion_operator_receipt_fail_closed_guard_ready"] is (
        not api_runner_guard_missing_reasons
    )
    assert (
        status["api_runner_profile_promotion_operator_receipt_fail_closed_guard_missing_reasons"]
        == api_runner_guard_missing_reasons
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
        "product_accuracy_parity:close_ligand_ranking_claim_scope"
    )
    assert status["product_accuracy_parity_ligand_ranking_action_present"] is (
        actions_artifact.get("product_accuracy_parity_ligand_ranking_action_present") is True
    )
    assert status["product_accuracy_parity_ligand_ranking_required_input"] == (
        actions_artifact.get("product_accuracy_parity_ligand_ranking_required_input")
    )
    assert status["product_accuracy_parity_ligand_ranking_artifact_path"] == (
        actions_artifact.get("product_accuracy_parity_ligand_ranking_artifact_path")
    )
    assert status["product_accuracy_parity_ligand_ranking_recommended_action"] == (
        actions_artifact.get("product_accuracy_parity_ligand_ranking_recommended_action")
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
    assert status["commercial_readiness_handoff_bundle_artifact_reference_count"] == int(
        handoff_artifact.get("artifact_reference_count") or 0
    )
    assert status["commercial_readiness_handoff_bundle_local_missing_artifact_reference_count"] == int(
        handoff_artifact.get("local_missing_artifact_reference_count") or 0
    )
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
    for source_key, status_key in [
        (
            "product_goal_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id",
            "operator_intake_kit_product_goal_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id",
        ),
        (
            "product_goal_scope_breadth_evidence_receipt_first_blocked_evidence_artifact",
            "operator_intake_kit_product_goal_scope_breadth_evidence_receipt_first_blocked_evidence_artifact",
        ),
        (
            "product_goal_scope_breadth_evidence_receipt_first_blocked_expected_evidence_status",
            "operator_intake_kit_product_goal_scope_breadth_evidence_receipt_first_blocked_expected_evidence_status",
        ),
        (
            "product_goal_scope_breadth_evidence_receipt_first_blocked_observed_evidence_status",
            "operator_intake_kit_product_goal_scope_breadth_evidence_receipt_first_blocked_observed_evidence_status",
        ),
        (
            "product_goal_scope_breadth_evidence_receipt_first_blocked_missing_true_fields",
            "operator_intake_kit_product_goal_scope_breadth_evidence_receipt_first_blocked_missing_true_fields",
        ),
        (
            "product_goal_scope_breadth_evidence_receipt_first_blocked_row_blockers",
            "operator_intake_kit_product_goal_scope_breadth_evidence_receipt_first_blocked_row_blockers",
        ),
        (
            "product_goal_scope_breadth_evidence_receipt_most_common_row_blocker",
            "operator_intake_kit_product_goal_scope_breadth_evidence_receipt_most_common_row_blocker",
        ),
        (
            "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_blocker_id",
            "operator_intake_kit_product_goal_engine_refinement_claim_evidence_receipt_first_blocked_blocker_id",
        ),
        (
            "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_evidence_artifact",
            "operator_intake_kit_product_goal_engine_refinement_claim_evidence_receipt_first_blocked_evidence_artifact",
        ),
        (
            "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_expected_evidence_status",
            "operator_intake_kit_product_goal_engine_refinement_claim_evidence_receipt_first_blocked_expected_evidence_status",
        ),
        (
            "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_observed_evidence_status",
            "operator_intake_kit_product_goal_engine_refinement_claim_evidence_receipt_first_blocked_observed_evidence_status",
        ),
        (
            "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_missing_true_fields",
            "operator_intake_kit_product_goal_engine_refinement_claim_evidence_receipt_first_blocked_missing_true_fields",
        ),
        (
            "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_row_blockers",
            "operator_intake_kit_product_goal_engine_refinement_claim_evidence_receipt_first_blocked_row_blockers",
        ),
        (
            "product_goal_engine_refinement_claim_evidence_receipt_most_common_row_blocker",
            "operator_intake_kit_product_goal_engine_refinement_claim_evidence_receipt_most_common_row_blocker",
        ),
    ]:
        assert status[status_key] == intake_artifact.get(source_key)
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
    for source_key, status_key in [
        (
            "product_goal_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id",
            "bottleneck_briefing_product_goal_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id",
        ),
        (
            "product_goal_scope_breadth_evidence_receipt_first_blocked_evidence_artifact",
            "bottleneck_briefing_product_goal_scope_breadth_evidence_receipt_first_blocked_evidence_artifact",
        ),
        (
            "product_goal_scope_breadth_evidence_receipt_first_blocked_expected_evidence_status",
            "bottleneck_briefing_product_goal_scope_breadth_evidence_receipt_first_blocked_expected_evidence_status",
        ),
        (
            "product_goal_scope_breadth_evidence_receipt_first_blocked_observed_evidence_status",
            "bottleneck_briefing_product_goal_scope_breadth_evidence_receipt_first_blocked_observed_evidence_status",
        ),
        (
            "product_goal_scope_breadth_evidence_receipt_first_blocked_missing_true_fields",
            "bottleneck_briefing_product_goal_scope_breadth_evidence_receipt_first_blocked_missing_true_fields",
        ),
        (
            "product_goal_scope_breadth_evidence_receipt_first_blocked_row_blockers",
            "bottleneck_briefing_product_goal_scope_breadth_evidence_receipt_first_blocked_row_blockers",
        ),
        (
            "product_goal_scope_breadth_evidence_receipt_most_common_row_blocker",
            "bottleneck_briefing_product_goal_scope_breadth_evidence_receipt_most_common_row_blocker",
        ),
        (
            "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_blocker_id",
            "bottleneck_briefing_product_goal_engine_refinement_claim_evidence_receipt_first_blocked_blocker_id",
        ),
        (
            "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_evidence_artifact",
            "bottleneck_briefing_product_goal_engine_refinement_claim_evidence_receipt_first_blocked_evidence_artifact",
        ),
        (
            "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_expected_evidence_status",
            "bottleneck_briefing_product_goal_engine_refinement_claim_evidence_receipt_first_blocked_expected_evidence_status",
        ),
        (
            "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_observed_evidence_status",
            "bottleneck_briefing_product_goal_engine_refinement_claim_evidence_receipt_first_blocked_observed_evidence_status",
        ),
        (
            "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_missing_true_fields",
            "bottleneck_briefing_product_goal_engine_refinement_claim_evidence_receipt_first_blocked_missing_true_fields",
        ),
        (
            "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_row_blockers",
            "bottleneck_briefing_product_goal_engine_refinement_claim_evidence_receipt_first_blocked_row_blockers",
        ),
        (
            "product_goal_engine_refinement_claim_evidence_receipt_most_common_row_blocker",
            "bottleneck_briefing_product_goal_engine_refinement_claim_evidence_receipt_most_common_row_blocker",
        ),
    ]:
        assert status[status_key] == bottlenecks_artifact.get(source_key)
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
    assert status[
        "operator_intake_kit_production_ai_registry_promotion_priority_top_gate_id"
    ] == intake_artifact.get("production_ai_registry_promotion_priority_top_gate_id")
    assert status[
        "operator_intake_kit_production_ai_registry_promotion_priority_top_priority_bucket"
    ] == intake_artifact.get("production_ai_registry_promotion_priority_top_priority_bucket")
    assert status[
        "operator_intake_kit_production_ai_registry_promotion_priority_missing_gate_count"
    ] == int(intake_artifact.get("production_ai_registry_promotion_priority_missing_gate_count") or 0)
    assert status[
        "bottleneck_briefing_production_ai_registry_promotion_priority_top_gate_id"
    ] == bottlenecks_artifact.get("production_ai_registry_promotion_priority_top_gate_id")
    assert status[
        "bottleneck_briefing_production_ai_registry_promotion_priority_top_priority_bucket"
    ] == bottlenecks_artifact.get("production_ai_registry_promotion_priority_top_priority_bucket")
    assert status[
        "bottleneck_briefing_production_ai_registry_promotion_priority_missing_gate_count"
    ] == int(
        bottlenecks_artifact.get("production_ai_registry_promotion_priority_missing_gate_count")
        or 0
    )
    assert status[
        "commercial_readiness_handoff_bundle_production_ai_registry_promotion_priority_top_gate_id"
    ] == handoff_artifact.get("production_ai_registry_promotion_priority_top_gate_id")
    assert status[
        "commercial_readiness_handoff_bundle_production_ai_registry_promotion_priority_top_priority_bucket"
    ] == handoff_artifact.get("production_ai_registry_promotion_priority_top_priority_bucket")
    assert status[
        "commercial_readiness_handoff_bundle_production_ai_registry_promotion_priority_missing_gate_count"
    ] == int(handoff_artifact.get("production_ai_registry_promotion_priority_missing_gate_count") or 0)
    assert status["production_ai_registry_promotion_priority_downstream_visibility_ready"] is True
    assert status["production_ai_registry_promotion_priority_downstream_missing_surfaces"] == []
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
    cameo_fetch_intake_entry = next(
        row
        for row in intake_kit["entries"]
        if row.get("kit_entry_id") == "cameo_official_result_fetch_preflight"
    )
    assert status["cameo_official_result_fetch_preflight_intake_link_ready"] is True
    assert status["cameo_official_result_fetch_preflight_intake_link_missing_reasons"] == []
    assert status["cameo_official_result_fetch_preflight_intake_source_gate_status"] == (
        cameo_fetch_intake_entry.get("source_gate_status")
    )
    assert status["cameo_official_result_fetch_preflight_operator_template_csv"] == (
        cameo_fetch_intake_entry.get("template_path")
    )
    assert status["cameo_official_result_fetch_preflight_operator_intake_csv"] == (
        cameo_fetch_intake_entry.get("intake_path")
    )
    assert status["cameo_official_result_fetch_preflight_approval_token_required"] == (
        cameo_fetch_intake_entry.get("approval_token_required")
    )
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
    assert status["product_rollout_execution_smoke_receipt_status"] == (
        rollout_smoke_receipt_artifact.get("status")
    )
    assert status["product_rollout_execution_smoke_receipt_ready"] is (
        rollout_smoke_receipt_artifact.get("rollout_execution_smoke_receipt_ready") is True
    )
    assert status["product_rollout_execution_smoke_receipt_artifact_path"].endswith(
        "runs/product_rollout_execution_smoke_receipt_current.json"
    )
    assert status["product_rollout_execution_smoke_receipt_receipt_csv"] == (
        rollout_smoke_receipt_artifact.get("receipt_csv")
    )
    assert status["product_rollout_execution_smoke_receipt_receipt_csv_present"] is (
        rollout_smoke_receipt_artifact.get("receipt_csv_present") is True
    )
    assert status["product_rollout_execution_smoke_receipt_receipt_row_count"] == int(
        rollout_smoke_receipt_artifact.get("receipt_row_count") or 0
    )
    assert status["product_rollout_execution_smoke_receipt_ready_receipt_row_count"] == int(
        rollout_smoke_receipt_artifact.get("ready_receipt_row_count") or 0
    )
    assert status["product_rollout_execution_smoke_receipt_target_environment"] == (
        rollout_smoke_receipt_artifact.get("target_environment")
    )
    assert status[
        "product_rollout_execution_smoke_receipt_source_rollout_execution_readiness_status"
    ] == rollout_smoke_receipt_artifact.get("source_rollout_execution_readiness_status")
    assert status[
        "product_rollout_execution_smoke_receipt_source_authorized_for_separate_operator_execution"
    ] is (
        rollout_smoke_receipt_artifact.get(
            "source_authorized_for_separate_operator_execution"
        )
        is True
    )
    assert status["product_rollout_execution_smoke_receipt_source_rollout_executed"] is (
        rollout_smoke_receipt_artifact.get("source_rollout_executed") is True
    )
    assert status["product_rollout_execution_smoke_receipt_rollout_executed"] is (
        rollout_smoke_receipt_artifact.get("rollout_executed") is True
    )
    assert status["product_rollout_execution_smoke_receipt_external_state_mutated"] is (
        rollout_smoke_receipt_artifact.get("external_state_mutated") is True
    )
    assert status["product_rollout_execution_smoke_receipt_image_pushed"] is (
        rollout_smoke_receipt_artifact.get("image_pushed") is True
    )
    assert status["product_rollout_execution_smoke_receipt_service_restarted"] is (
        rollout_smoke_receipt_artifact.get("service_restarted") is True
    )
    assert status["product_rollout_execution_smoke_receipt_pager_provider_contacted"] is (
        rollout_smoke_receipt_artifact.get("pager_provider_contacted") is True
    )
    assert status[
        "product_rollout_execution_smoke_receipt_ingress_certificate_verified_live"
    ] is (
        rollout_smoke_receipt_artifact.get("ingress_certificate_verified_live") is True
    )
    assert status["product_rollout_execution_smoke_receipt_blocker_count"] == int(
        rollout_smoke_receipt_artifact.get("blocker_count") or 0
    )
    assert status["product_rollout_execution_smoke_receipt_blockers"] == (
        rollout_smoke_receipt_artifact.get("blockers") or []
    )
    assert status["product_rollout_execution_smoke_receipt_next_required_step"] == (
        rollout_smoke_receipt_artifact.get("next_required_step")
    )
    rollout_guard_missing_reasons = []
    if rollout_smoke_receipt_artifact.get("status") != "product_rollout_execution_smoke_receipt_ready":
        rollout_guard_missing_reasons.append("receipt_not_ready")
    if rollout_smoke_receipt_artifact.get("rollout_execution_smoke_receipt_ready") is not True:
        rollout_guard_missing_reasons.append("ready_flag_not_true")
    if rollout_smoke_receipt_artifact.get("receipt_csv_present") is not True:
        rollout_guard_missing_reasons.append("receipt_csv_missing")
    if int(rollout_smoke_receipt_artifact.get("receipt_row_count") or 0) < 1:
        rollout_guard_missing_reasons.append("receipt_row_missing")
    if (
        rollout_smoke_receipt_artifact.get(
            "source_authorized_for_separate_operator_execution"
        )
        is not True
    ):
        rollout_guard_missing_reasons.append("source_preflight_not_authorized")
    if rollout_smoke_receipt_artifact.get("source_rollout_executed") is True:
        rollout_guard_missing_reasons.append("source_preflight_executed_rollout")
    if rollout_smoke_receipt_artifact.get("rollout_executed") is not True:
        rollout_guard_missing_reasons.append("rollout_execution_not_recorded")
    if rollout_smoke_receipt_artifact.get("external_state_mutated") is not True:
        rollout_guard_missing_reasons.append("external_mutation_not_recorded")
    if rollout_smoke_receipt_artifact.get("image_pushed") is not True:
        rollout_guard_missing_reasons.append("image_push_not_recorded")
    if rollout_smoke_receipt_artifact.get("service_restarted") is not True:
        rollout_guard_missing_reasons.append("service_restart_not_recorded")
    if rollout_smoke_receipt_artifact.get("pager_provider_contacted") is not True:
        rollout_guard_missing_reasons.append("pager_contact_not_recorded")
    if rollout_smoke_receipt_artifact.get("ingress_certificate_verified_live") is not True:
        rollout_guard_missing_reasons.append("ingress_certificate_not_verified")
    if int(rollout_smoke_receipt_artifact.get("blocker_count") or 0) != 0:
        rollout_guard_missing_reasons.append("blockers_present")
    assert status["product_rollout_execution_smoke_receipt_operator_receipt_guard_ready"] is (
        not rollout_guard_missing_reasons
    )
    assert (
        status[
            "product_rollout_execution_smoke_receipt_operator_receipt_guard_missing_reasons"
        ]
        == rollout_guard_missing_reasons
    )
    _assert_product_launch_r4_preflight_fields(
        observed=status,
        artifact=launch_r4_preflight_artifact,
    )
    _assert_deploy_ops_legal_gap_closure_fields(
        observed=status,
        artifact=deploy_ops_legal_artifact,
    )
    _assert_license_legal_boundary_fields(
        observed=status,
        artifact=release_artifact,
    )
    _assert_product_release_bundle_fields(
        observed=status,
        artifact=product_release_bundle_artifact,
    )
    _assert_product_scope_priority_fields(
        observed=status,
        artifact=scope_priority_artifact,
    )
    _assert_engine_priority_fields(
        observed=status,
        artifact=engine_priority_artifact,
    )
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
    assert status["full_commercial_blocker_evidence_matrix_r8_blocked_row_count"] == int(
        (full_matrix_artifact.get("release_blocker_blocked_row_counts") or {}).get(
            "R8_full_scope_claim_closure"
        )
        or 0
    )
    assert status["full_commercial_blocker_evidence_matrix_r8_first_blocked_evidence_row_id"] == (
        (full_matrix_artifact.get("release_blocker_first_blocked_evidence_row_ids") or {}).get(
            "R8_full_scope_claim_closure"
        )
    )
    assert status["full_commercial_blocker_evidence_matrix_r8_receipt_csv"] == (
        (full_matrix_artifact.get("release_blocker_receipt_csvs") or {}).get(
            "R8_full_scope_claim_closure"
        )
    )
    assert status["full_commercial_blocker_evidence_matrix_r8_approval_token_required"] == (
        (full_matrix_artifact.get("release_blocker_approval_tokens_required") or {}).get(
            "R8_full_scope_claim_closure"
        )
    )
    assert status["full_commercial_blocker_evidence_matrix_r9_blocked_row_count"] == int(
        (full_matrix_artifact.get("release_blocker_blocked_row_counts") or {}).get(
            "R9_engine_refinement_claim_promotion"
        )
        or 0
    )
    assert status["full_commercial_blocker_evidence_matrix_r9_first_blocked_evidence_row_id"] == (
        (full_matrix_artifact.get("release_blocker_first_blocked_evidence_row_ids") or {}).get(
            "R9_engine_refinement_claim_promotion"
        )
    )
    assert status["full_commercial_blocker_evidence_matrix_r9_receipt_csv"] == (
        (full_matrix_artifact.get("release_blocker_receipt_csvs") or {}).get(
            "R9_engine_refinement_claim_promotion"
        )
    )
    assert status["full_commercial_blocker_evidence_matrix_r9_approval_token_required"] == (
        (full_matrix_artifact.get("release_blocker_approval_tokens_required") or {}).get(
            "R9_engine_refinement_claim_promotion"
        )
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
    assert release["primary_full_commercial_release_blocker_requirement_id"] == (
        release_artifact.get("primary_full_commercial_release_blocker_requirement_id")
    )
    assert release["primary_full_commercial_release_blocker_receipt_csv"] == release_artifact.get(
        "primary_full_commercial_release_blocker_receipt_csv"
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

    for payload in (
        status,
        readiness,
        priority_queue,
        actions,
        intake_kit,
        release,
        burndown,
        bottlenecks,
        api_contract,
    ):
        assert payload["execution_enabled"] is False
        assert payload["delete_executed"] is False
        assert payload["external_state_mutated"] is False
