"""Scope and engine priority projection assertions for the product goal suite."""

from __future__ import annotations


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
