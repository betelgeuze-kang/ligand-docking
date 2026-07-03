from __future__ import annotations

import asyncio
import json
from pathlib import Path

from api import goal as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_goal_readiness_returns_dashboard_safe_rows(tmp_path: Path, monkeypatch) -> None:
    artifact = tmp_path / "runs/goal_readiness_rollup_current.json"
    monkeypatch.setattr(mod, "GOAL_READINESS_ROLLUP_ARTIFACT", artifact)
    _write_json(
        artifact,
        {
            "summary": {
                "status": "blocked_goal_readiness",
                "lane_count": 2,
                "blocked_lane_count": 1,
                "operator_approval_pending_count": 1,
                "external_results_pending_count": 0,
                "release_allowed": False,
                "claim_boundary": "goal readiness fixture boundary",
            },
            "rows": [
                {
                    "lane_id": "commercial_product_execution",
                    "lane_status": "operator_approval_pending",
                    "artifact_path": "runs/product_pilot_packet_current.json",
                    "artifact_present": True,
                    "observed_status": "product_pilot_packet_ready",
                    "next_required_step": "Review restricted customer handoff.",
                    "blocker_count": 0,
                    "approval_token_required": "APPROVE_PRODUCT_DOCKING_EXECUTION",
                    "reclaim_size_gb": 1.5,
                    "execution_enabled": True,
                    "action_executed": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                },
                {
                    "lane_id": "public_benchmark",
                    "lane_status": "blocked",
                    "artifact_path": "runs/public_benchmark_external_receipts_audit_current.json",
                    "artifact_present": True,
                    "observed_status": "missing_external_receipts",
                    "next_required_step": "Attach benchmark receipts.",
                    "blocker_count": 2,
                    "approval_token_required": "",
                    "reclaim_size_gb": 0,
                    "blockers": "pose_rmsd_missing;posebusters_missing",
                    "execution_enabled": True,
                    "external_state_mutated": True,
                },
            ],
            "blockers": [{"blocker_id": "public_benchmark_receipts_missing"}],
        },
    )

    response = asyncio.run(mod.get_goal_readiness())

    assert response["status"] == "blocked_goal_readiness"
    assert response["readiness_row_count"] == 2
    assert response["readiness_action_required_row_count"] == 2
    assert len(response["rows"]) == 2
    assert response["blockers"] == [{"blocker_id": "public_benchmark_receipts_missing"}]
    assert response["readiness_rows"] == [
        {
            "lane_id": "commercial_product_execution",
            "lane_status": "operator_approval_pending",
            "artifact_path": "runs/product_pilot_packet_current.json",
            "artifact_present": True,
            "observed_status": "product_pilot_packet_ready",
            "next_required_step": "Review restricted customer handoff.",
            "blocker_count": 0,
            "approval_token_required": "APPROVE_PRODUCT_DOCKING_EXECUTION",
            "operator_action_required": True,
            "reclaim_size_gb": 1.5,
            "blockers": [],
            "execution_enabled": False,
            "action_executed": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        },
        {
            "lane_id": "public_benchmark",
            "lane_status": "blocked",
            "artifact_path": "runs/public_benchmark_external_receipts_audit_current.json",
            "artifact_present": True,
            "observed_status": "missing_external_receipts",
            "next_required_step": "Attach benchmark receipts.",
            "blocker_count": 2,
            "approval_token_required": "",
            "operator_action_required": True,
            "reclaim_size_gb": 0.0,
            "blockers": ["pose_rmsd_missing", "posebusters_missing"],
            "execution_enabled": False,
            "action_executed": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        },
    ]
    assert response["execution_enabled"] is False
    assert response["action_executed"] is False
    assert response["external_state_mutated"] is False


def test_goal_readiness_missing_artifact_keeps_dashboard_shape(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        mod,
        "GOAL_READINESS_ROLLUP_ARTIFACT",
        tmp_path / "runs/missing_goal_readiness_rollup_current.json",
    )

    response = asyncio.run(mod.get_goal_readiness())

    assert response["status"] == "missing_goal_readiness_rollup"
    assert response["readiness_row_count"] == 0
    assert response["readiness_action_required_row_count"] == 0
    assert response["readiness_rows"] == []
    assert response["rows"] == []
    assert response["blockers"] == []
    assert response["execution_enabled"] is False
    assert response["action_executed"] is False
    assert response["external_state_mutated"] is False


def test_goal_developer_preview_exposes_requirement_rows_fail_closed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact = tmp_path / "runs/developer_preview_final_gate_audit_current.json"
    clean_checkout_receipt = (
        tmp_path / ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
    )
    monkeypatch.setattr(mod, "DEVELOPER_PREVIEW_FINAL_GATE_AUDIT_ARTIFACT", artifact)
    monkeypatch.setattr(
        mod,
        "DEVELOPER_PREVIEW_CLEAN_CHECKOUT_RECEIPT_ARTIFACT",
        clean_checkout_receipt,
    )
    _write_json(
        artifact,
        {
            "summary": {
                "status": "blocked_developer_preview_final_gate_audit",
                "developer_preview_clean_baseline_ready": True,
                "gate_count": 2,
                "ready_gate_count": 1,
                "blocked_gate_count": 1,
                "receipt_work_order_row_count": 1,
                "claim_boundary": "developer preview fixture boundary",
            },
            "rows": [
                {
                    "gate_id": "benchmark_results_clean_checkout_regenerated",
                    "priority": "A",
                    "status": "blocked_developer_preview_gate",
                    "ready": False,
                    "blocker": "clean_checkout_receipt_not_ready",
                    "blockers": "clean_checkout_receipt_not_ready;review_missing",
                    "receipt_artifacts": (
                        ".betelgeuze/"
                        "developer_preview_clean_checkout_benchmark_receipt.json"
                    ),
                    "present_receipt_count": 1,
                    "required_receipt_count": 1,
                    "present_blocked_receipt_count": 1,
                    "receipt_blocker_count": 2,
                    "receipt_blockers": "review_missing;blocker_count_nonzero",
                    "primary_metric": "required_ready=false",
                    "secondary_metric": "present_receipts=1; required_receipts=1",
                    "next_required_step": "Attach reviewed clean-checkout receipt.",
                },
                {
                    "gate_id": "silent_import_loss_zero",
                    "priority": "B",
                    "status": "developer_preview_gate_ready",
                    "ready": True,
                    "receipt_artifacts": (
                        ".betelgeuze/developer_preview_silent_import_loss_receipt.json"
                    ),
                    "present_receipt_count": 1,
                    "required_receipt_count": 1,
                    "present_blocked_receipt_count": 0,
                    "receipt_blocker_count": 0,
                    "next_required_step": "Keep import-loss receipt current.",
                },
            ],
            "receipt_work_order_rows": [
                {
                    "gate_id": "benchmark_results_clean_checkout_regenerated",
                    "priority": "A",
                    "receipt_artifact": (
                        ".betelgeuze/"
                        "developer_preview_clean_checkout_benchmark_receipt.json"
                    ),
                    "receipt_kind": "required",
                    "blocker_scope": "receipt_contract",
                    "blocker_detail": "review_missing",
                    "required_action": "Attach reviewed clean-checkout receipt.",
                    "required_receipt_status": (
                        "developer_preview_clean_checkout_benchmark_receipt_ready"
                    ),
                    "required_true_fields": (
                        "clean_checkout_benchmark_regenerated,"
                        "reviewed_receipt_attached"
                    ),
                    "required_zero_fields": "blocker_count,failed_count",
                    "next_required_step": "Attach reviewed clean-checkout receipt.",
                }
            ],
        },
    )

    response = asyncio.run(mod.get_goal_developer_preview())

    assert response["status"] == "blocked_developer_preview_final_gate_audit"
    assert response["developer_preview_requirement_row_count"] == 6
    assert response["developer_preview_requirement_ready_row_count"] == 1
    assert response["developer_preview_requirement_blocked_row_count"] == 5
    assert response["developer_preview_requirement_all_ready"] is False
    assert response["developer_demo_wording_allowed"] is False
    assert response["paid_pilot_wording_allowed"] is False
    rows = {
        row["requirement_id"]: row
        for row in response["developer_preview_requirement_rows"]
    }
    assert rows["benchmark_results_clean_checkout_regenerated"]["blocker"] == (
        "clean_checkout_receipt_not_ready"
    )
    assert rows["benchmark_results_clean_checkout_regenerated"][
        "operator_action_required"
    ] is True
    assert rows["silent_import_loss_zero"]["ready"] is True
    assert rows["silent_import_loss_zero"]["operator_action_required"] is False
    assert rows["large_models_crash_oom_free"]["status"] == (
        "missing_developer_preview_gate"
    )
    assert rows["large_models_crash_oom_free"]["blocker"] == (
        "developer_preview_gate_missing"
    )
    assert response["developer_demo_wording_blocker_gate_ids"] == [
        "benchmark_results_clean_checkout_regenerated",
        "selected_medium_models_pass_or_approved_review",
        "large_models_crash_oom_free",
        "linux_windows_reproducibility_confirmed",
        "new_user_core_workflow_observation_passed",
    ]
    assert all(
        row["developer_demo_wording_allowed"] is False
        and row["paid_pilot_wording_allowed"] is False
        and row["claim_promotion_allowed"] is False
        and row["execution_enabled"] is False
        and row["external_state_mutated"] is False
        for row in response["developer_preview_requirement_rows"]
    )
    assert response["receipt_work_order_blocked_row_count"] == 1
    assert response["execution_enabled"] is False
    assert response["external_state_mutated"] is False
    assert response["claim_boundary"] == "developer preview fixture boundary"


def test_goal_developer_preview_missing_artifact_keeps_requirements_fail_closed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        mod,
        "DEVELOPER_PREVIEW_FINAL_GATE_AUDIT_ARTIFACT",
        tmp_path / "runs/missing_developer_preview_final_gate_audit_current.json",
    )
    monkeypatch.setattr(
        mod,
        "DEVELOPER_PREVIEW_CLEAN_CHECKOUT_RECEIPT_ARTIFACT",
        tmp_path / ".betelgeuze/missing_developer_preview_clean_checkout_receipt.json",
    )

    response = asyncio.run(mod.get_goal_developer_preview())

    assert response["status"] == "missing_developer_preview_final_gate_audit"
    assert response["developer_preview_requirement_row_count"] == 6
    assert response["developer_preview_requirement_ready_row_count"] == 0
    assert response["developer_preview_requirement_blocked_row_count"] == 6
    assert response["developer_preview_requirement_all_ready"] is False
    assert response["developer_preview_requirement_blocked_rows"] == response[
        "developer_preview_requirement_rows"
    ]
    assert response["developer_demo_wording_allowed"] is False
    assert response["paid_pilot_wording_allowed"] is False
    assert all(
        row["blocker"] == "developer_preview_gate_missing"
        for row in response["developer_preview_requirement_rows"]
    )
    assert response["execution_enabled"] is False
    assert response["external_state_mutated"] is False


def test_goal_api_customer_flow_exposes_release_evidence_rows(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact = tmp_path / "runs/api_customer_flow_release_evidence_current.json"
    monkeypatch.setattr(mod, "API_CUSTOMER_FLOW_RELEASE_EVIDENCE_ARTIFACT", artifact)
    check_ids = [
        "api_dispatch_live_job_ready",
        "tier_alpha_smoke_live_job_ready",
        "worker_lease_and_runner_profile_ready",
        "signed_result_manifest_ready",
        "bundle_validation_ready",
        "restricted_unattended_runtime_ready",
    ]
    _write_json(
        artifact,
        {
            "summary": {
                "status": "api_customer_flow_release_evidence_ready",
                "formal_release_evidence_ready": True,
                "clean_install_flow_ready": True,
                "tier_alpha_runner_execution_ok": True,
                "tier_alpha_worker_dispatch_enqueued": True,
                "result_manifest_signature_verified": True,
                "bundle_validation_ready": True,
                "restricted_unattended_runtime_ready": True,
                "general_platform_claim_allowed": False,
                "check_count": 6,
                "pass_count": 6,
                "blocker_count": 0,
                "blocked_check_ids": [],
                "tier_alpha_smoke_status": "tier_alpha_adrb2_dispatch_smoke_pass",
                "tier_alpha_evidence_mode": "live_job_recovered_from_completed_artifacts",
                "e2e_evidence_mode": "live_job",
                "result_manifest": "runs/tier_alpha/result_manifest.json",
                "result_manifest_sha256": "abc123",
                "allowed_scope_families": ["gpcr", "ion_channel", "kinase"],
                "claim_boundary": "api customer flow fixture boundary",
            },
            "rows": [
                {
                    "check_id": check_id,
                    "status": "pass",
                    "release_blocker": False,
                    "artifact_path": f"runs/{check_id}.json",
                    "required": f"{check_id}:required",
                    "observed": f"{check_id}:observed",
                    "reason": f"{check_id}:reason",
                    "execution_enabled": True,
                    "external_state_mutated": True,
                }
                for check_id in check_ids
            ],
        },
    )

    response = asyncio.run(mod.get_goal_api_customer_flow())

    assert response["status"] == "api_customer_flow_release_evidence_ready"
    assert response["api_customer_flow_release_evidence_ready"] is True
    assert response["api_customer_local_workflow_claim_allowed"] is True
    assert response["restricted_scope_customer_flow_claim_allowed"] is True
    assert response["paid_pilot_wording_allowed"] is False
    assert response["tier_alpha_smoke_status"] == "tier_alpha_adrb2_dispatch_smoke_pass"
    assert response["result_manifest_signature_verified"] is True
    assert response["bundle_validation_ready"] is True
    assert response["restricted_unattended_runtime_ready"] is True
    assert response["general_platform_claim_allowed"] is False
    assert response["requirement_row_count"] == 6
    assert response["requirement_ready_row_count"] == 6
    assert response["requirement_blocked_row_count"] == 0
    assert response["requirement_blocked_rows"] == []
    assert [row["check_id"] for row in response["requirement_rows"]] == check_ids
    assert all(
        row["ready"] is True
        and row["execution_enabled"] is False
        and row["external_state_mutated"] is False
        and row["claim_promotion_allowed"] is False
        and row["paid_pilot_wording_allowed"] is False
        for row in response["requirement_rows"]
    )
    assert response["execution_enabled"] is False
    assert response["external_state_mutated"] is False
    assert response["claim_boundary"] == "api customer flow fixture boundary"


def test_goal_api_customer_flow_missing_artifact_fails_closed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        mod,
        "API_CUSTOMER_FLOW_RELEASE_EVIDENCE_ARTIFACT",
        tmp_path / "runs/missing_api_customer_flow_release_evidence_current.json",
    )

    response = asyncio.run(mod.get_goal_api_customer_flow())

    assert response["status"] == "missing_api_customer_flow_release_evidence"
    assert response["api_customer_flow_release_evidence_ready"] is False
    assert response["api_customer_local_workflow_claim_allowed"] is False
    assert response["restricted_scope_customer_flow_claim_allowed"] is False
    assert response["paid_pilot_wording_allowed"] is False
    assert response["blocker_count"] == 1
    assert response["blocked_check_ids"] == ["api_customer_flow_release_evidence_missing"]
    assert response["requirement_row_count"] == 0
    assert response["requirement_rows"] == []
    assert response["execution_enabled"] is False
    assert response["external_state_mutated"] is False


def test_goal_customer_shadow_exposes_paid_pilot_requirement_rows(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact = tmp_path / "runs/customer_shadow_evidence_status_current.json"
    monkeypatch.setattr(mod, "CUSTOMER_SHADOW_EVIDENCE_STATUS_ARTIFACT", artifact)
    _write_json(
        artifact,
        {
            "summary": {
                "status": "blocked_customer_shadow_evidence_status",
                "customer_shadow_intake_schema_ready": True,
                "customer_shadow_minimum_met": False,
                "row_count": 2,
                "real_customer_shadow_row_count": 2,
                "completed_customer_shadow_case_count": 1,
                "required_completed_customer_shadow_case_count": 3,
                "missing_completed_customer_shadow_case_count": 2,
                "mock_fixture_row_count": 0,
                "invalid_row_count": 0,
                "customer_retained_raw_data_count": 3,
                "redistribution_allowed_false_count": 1,
                "anonymized_result_summary_count": 2,
                "reviewer_signoff_count": 0,
                "customer_raw_data_stored_in_repo": False,
                "redistribution_allowed_required_value": False,
                "required_column_count": 12,
                "missing_required_columns": [],
                "blocker_count": 1,
                "customer_shadow_work_order_ready": False,
                "customer_shadow_work_order_row_count": 2,
                "customer_shadow_work_order_missing_case_count": 2,
                "customer_shadow_work_order_primary_required_anonymized_result_summary": (
                    "At least 24 characters."
                ),
                "customer_shadow_work_order_primary_required_reviewer_id": (
                    "non-empty reviewer id"
                ),
                "customer_shadow_work_order_primary_required_reviewed_at_utc": (
                    "timezone-aware ISO timestamp"
                ),
                "paid_pilot_evidence_ready": False,
                "paid_pilot_claim_allowed": False,
                "commercial_readiness_promotion_allowed": False,
                "readiness_promotion_allowed": False,
                "next_required_step": "Collect reviewed customer-shadow evidence.",
                "claim_boundary": "customer shadow fixture boundary",
            },
            "rows": [
                {
                    "case_id": "customer_shadow_case_0",
                    "row_kind": "customer_shadow",
                    "status": "pass",
                    "counts_toward_minimum": True,
                    "completed_schema_valid": True,
                    "is_mock_fixture": False,
                    "blocker_count": 0,
                    "blockers": "",
                    "raw_data_custody": "customer_retained",
                    "customer_retained_raw_data": "true",
                    "redistribution_allowed": "false",
                    "raw_data_stored_in_repo": "false",
                    "reviewer_signoff_status": "approved",
                }
            ],
            "blockers": [
                {
                    "case_id": "minimum_completed_cases",
                    "row_kind": "minimum",
                    "status": "fail",
                    "counts_toward_minimum": False,
                    "blocker_count": 1,
                    "blockers": "missing_completed_customer_shadow_case_count:2",
                    "next_action": "Add two reviewed real customer-shadow rows.",
                }
            ],
            "customer_shadow_work_order_rows": [
                {
                    "work_order_id": "customer_shadow_case_slot_2",
                    "case_slot_id": "customer_shadow_case_2",
                    "status": "missing_customer_shadow_evidence",
                    "required_row_kind": "customer_shadow",
                    "operator_csv": "config/customer_shadow_evidence_intake_template.csv",
                    "required_action": "Add one reviewed real customer-shadow metadata row.",
                    "required_raw_data_custody": "customer_retained",
                    "required_customer_retained_raw_data": True,
                    "required_redistribution_allowed": False,
                    "required_raw_data_stored_in_repo": False,
                    "required_derived_metadata_fields": ["artifact_fingerprint"],
                    "required_anonymized_result_summary": "At least 24 characters.",
                    "required_reviewer_signoff_status": "approved",
                    "required_reviewer_id": "non-empty reviewer id",
                    "required_reviewed_at_utc": "timezone-aware ISO timestamp",
                    "required_source_artifact_fingerprint": "sha256",
                    "execution_enabled": True,
                    "external_state_mutated": True,
                }
            ],
        },
    )

    response = asyncio.run(mod.get_goal_customer_shadow())

    assert response["status"] == "blocked_customer_shadow_evidence_status"
    assert response["paid_pilot_wording_allowed"] is False
    assert response["paid_pilot_requirement_row_count"] == 14
    assert response["paid_pilot_requirement_ready_row_count"] == 5
    assert response["paid_pilot_requirement_blocked_row_count"] == 9
    rows = {
        row["requirement_id"]: row
        for row in response["paid_pilot_requirement_rows"]
    }
    assert rows["completed_customer_shadow_cases"]["blocker"] == (
        "completed_customer_shadow_cases_below_required:1/3"
    )
    assert rows["customer_retained_raw_data"]["ready"] is True
    assert rows["redistribution_allowed_false"]["blocker"] == (
        "redistribution_false_rows_below_required:1/3"
    )
    assert rows["reviewer_signoff"]["operator_action"] == (
        "Add reviewer signoff for each counted customer-shadow row."
    )
    assert rows["customer_shadow_work_order_closed"]["blocker"] == (
        "customer_shadow_work_order_rows_open:2"
    )
    assert response["customer_shadow_work_order_primary_required_anonymized_result_summary"] == (
        "At least 24 characters."
    )
    assert response["customer_shadow_work_order_primary_required_reviewer_id"] == (
        "non-empty reviewer id"
    )
    assert response["customer_shadow_work_order_primary_required_reviewed_at_utc"] == (
        "timezone-aware ISO timestamp"
    )
    assert all(
        row["paid_pilot_wording_allowed"] is False
        and row["claim_promotion_allowed"] is False
        and row["execution_enabled"] is False
        and row["external_state_mutated"] is False
        for row in response["paid_pilot_requirement_rows"]
    )
    assert response["customer_shadow_work_order_blocked_rows"][0]["execution_enabled"] is False
    assert response["customer_shadow_work_order_blocked_rows"][0]["external_state_mutated"] is False
    assert response["customer_shadow_work_order_blocked_rows"][0][
        "required_anonymized_result_summary"
    ] == "At least 24 characters."
    assert response["customer_shadow_work_order_blocked_rows"][0]["required_reviewer_id"] == (
        "non-empty reviewer id"
    )
    assert response["customer_shadow_work_order_blocked_rows"][0]["required_reviewed_at_utc"] == (
        "timezone-aware ISO timestamp"
    )
    assert response["execution_enabled"] is False
    assert response["external_state_mutated"] is False
    assert response["claim_boundary"] == "customer shadow fixture boundary"


def test_goal_customer_shadow_missing_artifact_keeps_paid_pilot_rows_fail_closed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        mod,
        "CUSTOMER_SHADOW_EVIDENCE_STATUS_ARTIFACT",
        tmp_path / "runs/missing_customer_shadow_evidence_status_current.json",
    )

    response = asyncio.run(mod.get_goal_customer_shadow())

    assert response["status"] == "missing_customer_shadow_evidence_status"
    assert response["paid_pilot_wording_allowed"] is False
    assert response["paid_pilot_requirement_row_count"] == 14
    assert response["paid_pilot_requirement_ready_row_count"] == 0
    assert response["paid_pilot_requirement_blocked_row_count"] == 14
    assert all(not row["ready"] for row in response["paid_pilot_requirement_rows"])
    assert response["paid_pilot_requirement_blocked_rows"] == response[
        "paid_pilot_requirement_rows"
    ]
    assert response["execution_enabled"] is False
    assert response["external_state_mutated"] is False
