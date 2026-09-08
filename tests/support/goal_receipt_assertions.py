"""Receipt and scope-priority projection assertions for the product goal suite."""

from __future__ import annotations


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
