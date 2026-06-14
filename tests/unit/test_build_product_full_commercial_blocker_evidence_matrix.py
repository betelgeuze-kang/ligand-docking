from __future__ import annotations

from tools.product import build_product_full_commercial_blocker_evidence_matrix as mod


def _goal_audit() -> dict:
    return {
        "summary": {
            "status": "blocked_product_goal_completion_audit",
            "goal_complete": False,
        },
        "rows": [
            {
                "requirement_id": "R8_full_scope_claim_closure",
                "release_blocker": True,
                "status": "fail",
            },
            {
                "requirement_id": "R9_engine_refinement_claim_promotion",
                "release_blocker": True,
                "status": "fail",
            },
        ],
    }


def _bottleneck_briefing() -> dict:
    return {
        "summary": {"status": "goal_bottleneck_briefing_ready"},
        "rows": [
            {"bottleneck_id": "R8_full_scope_claim_closure"},
            {"bottleneck_id": "R9_engine_refinement_claim_promotion"},
        ],
    }


def test_full_commercial_blocker_evidence_matrix_surfaces_r8_r9_blocked_receipts() -> None:
    scope_receipt = {
        "summary": {
            "status": "blocked_product_scope_breadth_evidence_receipt",
            "full_scope_evidence_receipt_ready": False,
            "blocked_row_count": 1,
            "operator_review_surface_ready_count": 1,
            "operator_review_surface_blocked_count": 0,
            "receipt_manual_field_pending_count": 6,
            "evidence_status_contract_present_count": 1,
            "expected_true_fields_present_count": 1,
            "provenance_kind_accepted_count": 1,
            "first_blocked_scope_blocker_id": "direct_binding_evidence_missing",
            "most_common_row_blocker": "operator_placeholders_unfilled",
            "receipt_csv": "config/product_scope_breadth_evidence_receipt_current.csv",
            "approval_token_required": "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT",
            "next_required_step": "Fill scope receipt rows.",
        },
        "rows": [
            {
                "scope_blocker_id": "direct_binding_evidence_missing",
                "row_status": "blocked",
                "blockers": "operator_placeholders_unfilled",
                "evidence_artifact": "OPERATOR_FILL_LOCAL_EVIDENCE_JSON",
                "expected_evidence_status": "product_scope_transporter_direct_binding_evidence_ready",
                "observed_evidence_status": "missing",
                "operator_review_surface_ready": True,
                "operator_manual_pending_field_count": 6,
                "operator_manual_pending_fields": (
                    "evidence_artifact;claim_ready;reviewer;reviewed_at_utc;license_ok;approval_token"
                ),
            }
        ],
    }
    engine_receipt = {
        "summary": {
            "status": "blocked_engine_refinement_claim_evidence_receipt",
            "claim_promotion_evidence_receipt_ready": False,
            "blocked_row_count": 1,
            "first_blocked_blocker_id": "public_benchmark_gate_not_ready",
            "most_common_row_blocker": "operator_placeholders_unfilled",
            "receipt_csv": "config/engine_refinement_claim_promotion_evidence_receipt_current.csv",
            "approval_token_required": "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT",
            "next_required_step": "Fill engine receipt rows.",
        },
        "rows": [
            {
                "blocker_id": "public_benchmark_gate_not_ready",
                "row_status": "blocked",
                "blockers": "operator_placeholders_unfilled",
                "evidence_artifact": "OPERATOR_FILL_LOCAL_EVIDENCE_JSON",
                "expected_evidence_status": "refine_tier_public_benchmark_ready",
                "observed_evidence_status": "missing",
            }
        ],
    }

    payload = mod.build_product_full_commercial_blocker_evidence_matrix_from_packets(
        scope_packet=scope_receipt,
        scope_present=True,
        engine_packet=engine_receipt,
        engine_present=True,
        goal_packet=_goal_audit(),
        goal_present=True,
        bottleneck_packet=_bottleneck_briefing(),
        bottleneck_present=True,
        scope_receipt_json="runs/scope.json",
        engine_receipt_json="runs/engine.json",
        goal_audit_json="runs/goal.json",
        bottleneck_briefing_json="runs/bottleneck.json",
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_full_commercial_blocker_evidence_matrix"
    assert summary["release_blocker_visibility_ready"] is True
    assert summary["expected_release_blocker_ids"] == [
        "R8_full_scope_claim_closure",
        "R9_engine_refinement_claim_promotion",
    ]
    assert summary["matrix_row_count"] == 2
    assert summary["blocked_matrix_row_count"] == 2
    assert summary["release_blocker_row_counts"] == {
        "R8_full_scope_claim_closure": 1,
        "R9_engine_refinement_claim_promotion": 1,
    }
    assert summary["release_blocker_blocked_row_counts"] == {
        "R8_full_scope_claim_closure": 1,
        "R9_engine_refinement_claim_promotion": 1,
    }
    assert summary["release_blocker_first_blocked_evidence_row_ids"] == {
        "R8_full_scope_claim_closure": "direct_binding_evidence_missing",
        "R9_engine_refinement_claim_promotion": "public_benchmark_gate_not_ready",
    }
    assert summary["release_blocker_receipt_csvs"] == {
        "R8_full_scope_claim_closure": "config/product_scope_breadth_evidence_receipt_current.csv",
        "R9_engine_refinement_claim_promotion": (
            "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
        ),
    }
    assert summary["release_blocker_approval_tokens_required"] == {
        "R8_full_scope_claim_closure": "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT",
        "R9_engine_refinement_claim_promotion": "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT",
    }
    assert summary["first_blocked_release_blocker_id"] == "R8_full_scope_claim_closure"
    assert summary["first_blocked_evidence_row_id"] == "direct_binding_evidence_missing"
    assert summary["first_blocked_evidence_artifact"] == "OPERATOR_FILL_LOCAL_EVIDENCE_JSON"
    assert summary["first_blocked_expected_evidence_status"] == (
        "product_scope_transporter_direct_binding_evidence_ready"
    )
    assert summary["first_blocked_observed_evidence_status"] == "missing"
    assert summary["first_blocked_row_blockers"] == "operator_placeholders_unfilled"
    assert summary["scope_receipt_first_blocked_scope_blocker_id"] == "direct_binding_evidence_missing"
    assert summary["scope_receipt_most_common_row_blocker"] == "operator_placeholders_unfilled"
    assert summary["scope_receipt_operator_review_surface_ready_count"] == 1
    assert summary["scope_receipt_operator_review_surface_blocked_count"] == 0
    assert summary["scope_receipt_manual_field_pending_count"] == 6
    assert summary["scope_receipt_evidence_status_contract_present_count"] == 1
    assert summary["scope_receipt_expected_true_fields_present_count"] == 1
    assert summary["scope_receipt_provenance_kind_accepted_count"] == 1
    assert summary["engine_receipt_first_blocked_blocker_id"] == "public_benchmark_gate_not_ready"
    assert summary["engine_receipt_most_common_row_blocker"] == "operator_placeholders_unfilled"
    assert "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT" in summary["approval_tokens_required"]
    assert "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT" in summary["approval_tokens_required"]
    assert "blocked_evidence_matrix_rows_present" in summary["blockers"]
    assert "full_commercial_receipts_not_ready" in summary["blockers"]
    assert payload["rows"][1]["release_blocker_id"] == "R9_engine_refinement_claim_promotion"
    assert payload["rows"][0]["operator_review_surface_ready"] is True
    assert payload["rows"][0]["operator_manual_pending_field_count"] == 6
    assert payload["summary"]["external_state_mutated"] is False


def test_full_commercial_blocker_evidence_matrix_passes_when_both_receipts_are_ready() -> None:
    scope_receipt = {
        "summary": {
            "status": "product_scope_breadth_evidence_receipt_ready",
            "full_scope_evidence_receipt_ready": True,
            "blocked_row_count": 0,
            "operator_review_surface_ready_count": 1,
            "operator_review_surface_blocked_count": 0,
            "receipt_manual_field_pending_count": 0,
            "evidence_status_contract_present_count": 1,
            "expected_true_fields_present_count": 1,
            "provenance_kind_accepted_count": 1,
            "receipt_csv": "config/product_scope_breadth_evidence_receipt_current.csv",
            "approval_token_required": "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT",
        },
        "rows": [
            {
                "scope_blocker_id": "direct_binding_evidence_missing",
                "row_status": "pass",
                "evidence_artifact": "runs/scope_evidence.json",
                "evidence_artifact_present": True,
                "expected_evidence_status": "product_scope_transporter_direct_binding_evidence_ready",
                "observed_evidence_status": "product_scope_transporter_direct_binding_evidence_ready",
                "claim_ready": True,
                "operator_review_surface_ready": True,
                "operator_manual_pending_field_count": 0,
            }
        ],
    }
    engine_receipt = {
        "summary": {
            "status": "engine_refinement_claim_evidence_receipt_ready",
            "claim_promotion_evidence_receipt_ready": True,
            "blocked_row_count": 0,
            "receipt_csv": "config/engine_refinement_claim_promotion_evidence_receipt_current.csv",
            "approval_token_required": "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT",
        },
        "rows": [
            {
                "blocker_id": "public_benchmark_gate_not_ready",
                "row_status": "pass",
                "evidence_artifact": "runs/engine_evidence.json",
                "evidence_artifact_present": True,
                "expected_evidence_status": "refine_tier_public_benchmark_ready",
                "observed_evidence_status": "refine_tier_public_benchmark_ready",
                "claim_ready": True,
            }
        ],
    }

    payload = mod.build_product_full_commercial_blocker_evidence_matrix_from_packets(
        scope_packet=scope_receipt,
        scope_present=True,
        engine_packet=engine_receipt,
        engine_present=True,
        goal_packet=_goal_audit(),
        goal_present=True,
        bottleneck_packet=_bottleneck_briefing(),
        bottleneck_present=True,
        scope_receipt_json="runs/scope.json",
        engine_receipt_json="runs/engine.json",
        goal_audit_json="runs/goal.json",
        bottleneck_briefing_json="runs/bottleneck.json",
    )

    summary = payload["summary"]
    assert summary["status"] == "product_full_commercial_blocker_evidence_matrix_ready"
    assert summary["full_commercial_blocker_evidence_matrix_ready"] is True
    assert summary["full_commercial_evidence_receipts_ready"] is True
    assert summary["blocked_matrix_row_count"] == 0
    assert summary["release_blocker_pass_row_counts"] == {
        "R8_full_scope_claim_closure": 1,
        "R9_engine_refinement_claim_promotion": 1,
    }
    assert summary["release_blocker_blocked_row_counts"] == {
        "R8_full_scope_claim_closure": 0,
        "R9_engine_refinement_claim_promotion": 0,
    }
    assert summary["release_blocker_first_blocked_evidence_row_ids"] == {
        "R8_full_scope_claim_closure": "",
        "R9_engine_refinement_claim_promotion": "",
    }
    assert summary["first_blocked_release_blocker_id"] == ""
    assert summary["first_blocked_row_blockers"] == ""
    assert summary["blocker_count"] == 0
