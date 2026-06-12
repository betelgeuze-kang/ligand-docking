from __future__ import annotations

import json
from pathlib import Path

from tools import build_goal_release_decision_gate as mod


def _blocked_product() -> dict:
    return {
        "summary": {
            "status": "product_pilot_packet_preflight_ready",
            "pilot_delivery_ready": False,
            "delivery_ready_claim_allowed": False,
            "bundle_validation_passed": False,
        }
    }


def _ready_product() -> dict:
    return {
        "summary": {
            "status": "product_pilot_packet_ready",
            "pilot_delivery_ready": True,
            "delivery_ready_claim_allowed": True,
            "bundle_validation_passed": True,
        }
    }


def _ready_product_architecture() -> dict:
    return {
        "summary": {
            "status": "product_architecture_contract_ready",
            "local_architecture_surface_ready": True,
            "architecture_release_ready": True,
            "blocked_lane_count": 0,
            "approval_required_lane_count": 0,
            "public_benchmark_validation_ready": True,
            "public_benchmark_status": "product_public_benchmark_contract_ready",
            "public_benchmark_required_suite_count": 5,
            "public_benchmark_ready_required_suite_count": 5,
            "public_benchmark_blocked_suite_count": 0,
            "public_benchmark_suite_materialization_manifest_count": 5,
            "public_benchmark_suite_scorecard_row_csv_count": 5,
            "public_benchmark_suite_threshold_count": 5,
            "public_benchmark_suite_blocker_count": 5,
            "public_benchmark_suite_run_command_count": 5,
            "public_benchmark_suite_materialization_run_command_count": 5,
            "public_benchmark_suite_no_external_dependency_count": 5,
            "public_benchmark_requires_24h_server": False,
            "public_benchmark_requires_competition_season": False,
            "public_benchmark_requires_paid_vps": False,
            "cameo_official_validation_evidence_ready": True,
            "cameo_receiver_smoke_status": "cameo_receiver_smoke_ready",
            "cameo_api_dependency_status": "cameo_api_dependency_ready",
            "cameo_public_registration_blocker_count": 0,
            "cameo_registration_approval_token_count": 0,
            "cameo_registration_approval_tokens_required": [],
        }
    }


def _blocked_product_architecture() -> dict:
    return {
        "summary": {
            "status": "blocked_product_architecture_contract",
            "local_architecture_surface_ready": True,
            "architecture_release_ready": False,
            "blocked_lane_count": 1,
            "approval_required_lane_count": 2,
            "public_benchmark_validation_ready": False,
            "public_benchmark_status": "blocked_product_public_benchmark_contract",
            "public_benchmark_required_suite_count": 5,
            "public_benchmark_ready_required_suite_count": 0,
            "public_benchmark_blocked_suite_count": 5,
            "public_benchmark_suite_materialization_manifest_count": 5,
            "public_benchmark_suite_scorecard_row_csv_count": 5,
            "public_benchmark_suite_threshold_count": 5,
            "public_benchmark_suite_blocker_count": 5,
            "public_benchmark_suite_run_command_count": 5,
            "public_benchmark_suite_materialization_run_command_count": 5,
            "public_benchmark_suite_no_external_dependency_count": 5,
            "public_benchmark_requires_24h_server": False,
            "public_benchmark_requires_competition_season": False,
            "public_benchmark_requires_paid_vps": False,
            "cameo_official_validation_evidence_ready": False,
            "cameo_receiver_smoke_status": "blocked_cameo_receiver_smoke",
            "cameo_api_dependency_status": "blocked_cameo_api_dependency_readiness",
            "cameo_public_registration_blocker_count": 4,
            "cameo_registration_approval_token_count": 2,
            "cameo_registration_approval_tokens_required": [
                "APPROVE_CAMEO_SERVER_REGISTRATION",
                "APPROVE_CAMEO_OUTBOUND_EMAIL",
            ],
        }
    }


def _ready_product_independence() -> dict:
    return {
        "summary": {
            "status": "product_commercial_independence_gate_ready",
            "commercial_independent_product_claim_allowed": True,
        }
    }


def _blocked_product_independence() -> dict:
    return {
        "summary": {
            "status": "blocked_product_commercial_independence_gate",
            "commercial_independent_product_claim_allowed": False,
            "blocker_count": 3,
        }
    }


def _blocked_cameo_validation() -> dict:
    return {
        "summary": {
            "status": "blocked_cameo_validation_readiness",
            "official_cameo_results_used": False,
        }
    }


def _ready_cameo_validation() -> dict:
    return {
        "summary": {
            "status": "cameo_validation_evidence_ready",
            "official_cameo_results_used": True,
        }
    }


def _blocked_cameo_capability() -> dict:
    return {
        "summary": {
            "status": "blocked_cameo_capability_preflight",
            "public_registration_allowed": False,
        }
    }


def _ready_cameo_capability() -> dict:
    return {
        "summary": {
            "status": "cameo_public_registration_preflight_ready",
            "public_registration_allowed": True,
        }
    }


def _ready_cameo_registration_gate() -> dict:
    return {
        "summary": {
            "status": "cameo_public_registration_approval_gate_ready",
            "authorized_for_registration_review": True,
        }
    }


def _blocked_rollup() -> dict:
    return {"summary": {"status": "blocked_goal_readiness"}}


def _ready_rollup() -> dict:
    return {"summary": {"status": "goal_readiness_ready"}}


def _pending_nonblocking_rollup() -> dict:
    return {
        "summary": {
            "status": "goal_readiness_pending_operator_or_external_results",
            "blocked_lane_count": 0,
            "operator_approval_pending_count": 3,
            "external_results_pending_count": 1,
        }
    }


def _release_complete_operator_pending_rollup() -> dict:
    return {
        "summary": {
            "status": "goal_readiness_release_complete_operator_pending",
            "blocked_lane_count": 0,
            "operator_approval_pending_count": 3,
            "external_results_pending_count": 1,
        }
    }


def _blocked_action_board() -> dict:
    return {
        "summary": {
            "status": "operator_actions_required",
            "action_count": 17,
            "approval_required_count": 7,
            "review_required_count": 2,
            "approval_reclaim_size_gb": 49.216,
            "product_cli_status_set_status": "blocked_product_cli_status_set",
            "product_cli_approval_token_count": 2,
            "product_cli_operations_blocked_stage_count": 4,
            "product_cli_operations_approval_required_stage_count": 2,
            "product_cli_capability_surface_ready": True,
            "product_cli_operational_quality_ready": True,
            "product_release_operations_operational_quality_ready": True,
            "product_release_operations_operational_quality_blocker_count": 0,
            "product_release_operations_source_operational_quality_status": "product_operational_quality_contract_ready",
            "product_release_operations_operational_quality_artifact": "runs/product_operational_quality_contract_current.json",
            "product_cli_architecture_release_ready": False,
            "product_cli_commercial_independence_ready": False,
            "product_cli_authorized_for_execution": False,
            "product_cli_bundle_validation_passed": False,
            "product_cli_delivery_ready_claim_allowed": False,
            "cameo_cli_status_set_status": "blocked_cameo_cli_status_set",
            "cameo_cli_approval_token_count": 3,
            "cameo_cli_official_result_required": True,
            "cameo_cli_official_results_accepted_count": 0,
            "cameo_cli_evidence_integrity_ready": True,
            "cameo_cli_official_results_pending_honest": True,
            "cameo_cli_no_local_native_accuracy_substitution": True,
            "cameo_validation_operations_evidence_integrity_status": "cameo_evidence_integrity_contract_ready",
            "cameo_validation_operations_evidence_integrity_ready": True,
            "cameo_validation_operations_evidence_integrity_blocker_count": 0,
            "cameo_validation_operations_official_results_pending_honest": True,
            "cameo_validation_operations_no_local_native_accuracy_substitution": True,
            "cameo_validation_operations_evidence_integrity_artifact": "runs/cameo_evidence_integrity_contract_current.json",
            "cameo_cli_api_install_approval_required": True,
            "cameo_cli_receiver_smoke_status": "blocked_cameo_receiver_smoke",
            "cameo_cli_public_registration_authorized": False,
            "cleanup_cli_status_set_status": "blocked_cleanup_cli_status_set",
            "cleanup_cli_approval_token_count": 4,
            "cleanup_cli_approval_reclaim_size_gb": 49.216,
            "cleanup_cli_postcheck_contract_ready": True,
            "cleanup_cli_postcheck_blocked_row_count": 0,
            "cleanup_cli_protected_payload_size_gb": 396.794,
            "cleanup_cli_protected_policy_change_required_count": 2,
            "cleanup_cli_protected_policy_resolved": False,
        }
    }


def _clear_action_board() -> dict:
    return {
        "summary": {
            "status": "goal_operator_actions_clear",
            "action_count": 0,
            "approval_required_count": 0,
            "review_required_count": 0,
            "approval_reclaim_size_gb": 0,
        }
    }


def _transition_cleanup(status: str) -> dict:
    return {"summary": {"status": status, "external_state_mutated": status.endswith("_complete")}}


def _ligand_cleanup(status: str) -> dict:
    return {"summary": {"status": status, "delete_executed": status.endswith("_complete")}}


def _protected_cleanup(policy_change_required_count: int) -> dict:
    return {
        "summary": {
            "status": "protected_cleanup_payload_review_ready",
            "protected_payload_size_gb": 396.794,
            "policy_change_required_count": policy_change_required_count,
        }
    }


def _protected_policy_gate_ready() -> dict:
    return {
        "summary": {
            "status": "protected_cleanup_policy_decision_gate_ready",
            "policy_resolved": True,
            "policy_change_requested_row_count": 0,
            "awaiting_policy_decision_row_count": 0,
            "blocked_row_count": 0,
            "known_payload_child_count": 2,
            "known_payload_child_size_gb": 396.794,
            "preservation_sibling_count": 2,
            "policy_change_required_for_deletion_count": 2,
        }
    }


def _ready_cleanup_postcheck() -> dict:
    return {
        "summary": {
            "status": "cleanup_postcheck_contract_ready",
            "postcheck_contract_ready": True,
            "row_count": 7,
            "blocked_row_count": 0,
            "global_refresh_command_count": 9,
        }
    }


def _blocked_cleanup_postcheck() -> dict:
    return {
        "summary": {
            "status": "blocked_cleanup_postcheck_contract",
            "postcheck_contract_ready": False,
            "row_count": 7,
            "blocked_row_count": 1,
            "global_refresh_command_count": 9,
        }
    }


def _cleanup_completion_ready() -> dict:
    return {
        "summary": {
            "status": "cleanup_completion_gate_ready",
            "cleanup_complete": True,
            "transition_cleanup_complete": True,
            "ligand_heavy_cleanup_complete": True,
            "protected_policy_resolved": True,
        }
    }


def _blocked_cleanup_completion_gate() -> dict:
    return {
        "summary": {
            "status": "blocked_cleanup_completion_gate",
            "cleanup_complete": False,
            "blocked_stage_count": 4,
            "total_reclaim_size_gb": 49.216,
            "authorized_reclaim_size_gb": 0.0,
            "approval_awaiting_operator_approval_row_count": 5,
            "approval_blocked_row_count": 5,
            "transition_approval_gated_reclaim_size_gb": 43.206,
            "ligand_heavy_candidate_size_gb": 6.011,
        }
    }


def _ready_goal_api_surface_contract() -> dict:
    return {
        "summary": {
            "status": "goal_api_surface_contract_ready",
            "surface_ready": True,
            "check_count": 7,
            "blocker_count": 0,
            "missing_endpoint_count": 0,
            "missing_status_key_count": 0,
        }
    }


def _blocked_goal_api_surface_contract() -> dict:
    return {
        "summary": {
            "status": "blocked_goal_api_surface_contract",
            "surface_ready": False,
            "check_count": 7,
            "blocker_count": 1,
            "missing_endpoint_count": 1,
            "missing_status_key_count": 0,
        }
    }


def _ready_product_ai_gap() -> dict:
    return {
        "summary": {
            "status": "product_ai_architecture_gap_closure_complete",
            "all_gaps_closed": True,
            "open_gap_count": 0,
            "current_primary_open_gap": "none",
        }
    }


def _blocked_product_ai_gap() -> dict:
    return {
        "summary": {
            "status": "blocked_product_ai_architecture_gap_closure",
            "all_gaps_closed": False,
            "open_gap_count": 1,
            "current_primary_open_gap": "scope_breadth_expansion",
        }
    }


def _ready_product_ai_backlog() -> dict:
    return {
        "summary": {
            "status": "product_ai_architecture_execution_backlog_clear",
            "backlog_clear": True,
            "work_item_count": 0,
            "primary_work_item_id": "none",
        }
    }


def _blocked_product_ai_backlog() -> dict:
    return {
        "summary": {
            "status": "product_ai_architecture_execution_backlog_ready",
            "backlog_clear": False,
            "work_item_count": 21,
            "primary_work_item_id": "training_data.production_delta_force_label_evidence",
            "scope_closure_detail": (
                "scope_closure_blocker_classes=direct_binding_evidence_missing=4,exact_negative_quantitative_value_missing=6;"
                "scope_closure_first_scientific_blocker=AQP1.core_binder_01;"
                "scope_closure_pxr_reconciled_blocked_row_count=6;"
                "scope_closure_general_claim_blocker_count=4;"
                "scope_closure_authoritative_apply_allowed=False"
            ),
        },
        "rows": [
            {
                "work_item_id": "training_data.production_delta_force_label_evidence",
                "observed": (
                    "gpu_worker_return_expected_queue_rows=768;"
                    "gpu_worker_return_manifest_operator_verified=False;"
                    "gpu_worker_return_operator_verified_true_count=0;"
                    "gpu_worker_return_queue_fingerprints=768"
                ),
                "next_action": "Run the full GPU regeneration command and return the current summary JSON.",
            }
        ],
    }


def _blocked_source_of_truth() -> dict:
    return {
        "summary": {
            "status": "blocked_product_release_source_of_truth_gate",
            "release_source_of_truth_ready": False,
            "blocker_count": 2,
            "stale_artifact_count": 1,
            "readme_drift_count": 1,
            "missing_artifact_count": 0,
        }
    }


def _ready_source_of_truth() -> dict:
    return {
        "summary": {
            "status": "product_release_source_of_truth_gate_ready",
            "release_source_of_truth_ready": True,
            "blocker_count": 0,
            "stale_artifact_count": 0,
            "readme_drift_count": 0,
            "missing_artifact_count": 0,
        }
    }


def _blocked_full_commercial_matrix() -> dict:
    return {
        "summary": {
            "status": "blocked_product_full_commercial_blocker_evidence_matrix",
            "full_commercial_blocker_evidence_matrix_ready": False,
            "release_blocker_visibility_ready": True,
            "expected_release_blocker_ids": [
                "R8_full_scope_claim_closure",
                "R9_engine_refinement_claim_promotion",
            ],
            "matrix_row_count": 12,
            "blocked_matrix_row_count": 12,
            "approval_token_count": 2,
            "first_blocked_release_blocker_id": "R8_full_scope_claim_closure",
            "first_blocked_evidence_row_id": "direct_binding_evidence_missing",
            "first_blocked_evidence_artifact": "OPERATOR_FILL_LOCAL_EVIDENCE_JSON",
            "first_blocked_expected_evidence_status": (
                "product_scope_transporter_direct_binding_evidence_ready"
            ),
            "first_blocked_observed_evidence_status": "missing",
            "first_blocked_row_blockers": "operator_placeholders_unfilled",
            "scope_receipt_most_common_row_blocker": "operator_placeholders_unfilled",
            "engine_receipt_most_common_row_blocker": "operator_placeholders_unfilled",
            "next_required_step": (
                "Fill the R8/R9 receipt CSVs with reviewed local evidence artifacts and approval tokens."
            ),
            "execution_enabled": False,
            "external_state_mutated": False,
        }
    }


def _blocked_rollout_smoke_receipt() -> dict:
    return {
        "summary": {
            "status": "blocked_product_rollout_execution_smoke_receipt",
            "rollout_execution_smoke_receipt_ready": False,
            "source_authorized_for_separate_operator_execution": True,
            "receipt_csv_present": False,
            "receipt_row_count": 0,
            "blocker_count": 2,
            "rollout_executed": False,
            "external_state_mutated": False,
            "pager_provider_contacted": False,
            "ingress_certificate_verified_live": False,
        }
    }


def _blocked_master_gap_rollup() -> dict:
    return {
        "summary": {
            "status": "blocked_master_gap_closure_rollup",
            "all_gaps_closed": False,
            "gap_count": 9,
            "open_gap_count": 2,
            "open_gap_ids": ["SCI-CLAIM", "DEPLOY-OPS"],
            "current_primary_open_gap_id": "SCI-CLAIM",
            "execution_enabled": False,
            "external_state_mutated": False,
        }
    }


def _blocked_api_customer_flow() -> dict:
    return {
        "summary": {
            "status": "blocked_api_customer_flow_release_evidence",
            "formal_release_evidence_ready": False,
            "clean_install_flow_ready": False,
            "result_manifest_signature_verified": False,
            "bundle_validation_ready": True,
            "restricted_unattended_runtime_ready": True,
            "blocker_count": 1,
        }
    }


def _ready_api_customer_flow() -> dict:
    return {
        "summary": {
            "status": "api_customer_flow_release_evidence_ready",
            "formal_release_evidence_ready": True,
            "clean_install_flow_ready": True,
            "result_manifest_signature_verified": True,
            "bundle_validation_ready": True,
            "restricted_unattended_runtime_ready": True,
            "blocker_count": 0,
        }
    }


def test_goal_release_decision_gate_blocks_current_incomplete_goal() -> None:
    payload = mod.build_goal_release_decision_gate(
        product_pilot_packet=_blocked_product(),
        product_architecture_packet=_blocked_product_architecture(),
        product_commercial_independence_packet=_blocked_product_independence(),
        cameo_validation_packet=_blocked_cameo_validation(),
        cameo_capability_packet=_blocked_cameo_capability(),
        goal_rollup_packet=_blocked_rollup(),
        operator_action_board_packet=_blocked_action_board(),
        transition_cleanup_preflight_packet=_transition_cleanup("transition_cleanup_execution_preflight_ready"),
        ligand_cleanup_preflight_packet=_ligand_cleanup("ligand_heavy_cleanup_execution_preflight_ready"),
        protected_cleanup_review_packet=_protected_cleanup(2),
        cleanup_postcheck_contract_packet=_ready_cleanup_postcheck(),
        cleanup_completion_gate_packet=_blocked_cleanup_completion_gate(),
        goal_api_surface_contract_packet=_ready_goal_api_surface_contract(),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_goal_release_decision"
    assert summary["release_allowed"] is False
    assert summary["commercial_independent_product_ready"] is False
    assert summary["cameo_architecture_validation_ready"] is False
    assert summary["cleanup_objective_ready"] is False
    assert summary["operator_action_count"] == 17
    assert summary["operator_approval_required_count"] == 7
    assert summary["product_cli_status_set_status"] == "blocked_product_cli_status_set"
    assert summary["product_cli_approval_token_count"] == 2
    assert summary["product_cli_operations_blocked_stage_count"] == 4
    assert summary["product_cli_capability_surface_ready"] is True
    assert summary["product_cli_operational_quality_ready"] is True
    assert summary["product_operational_quality_ready"] is True
    assert summary["product_operational_quality_status"] == "product_operational_quality_contract_ready"
    assert summary["product_operational_quality_blocker_count"] == 0
    assert summary["product_cli_architecture_release_ready"] is False
    assert summary["product_cli_authorized_for_execution"] is False
    assert summary["product_cli_delivery_ready_claim_allowed"] is False
    assert summary["cameo_cli_status_set_status"] == "blocked_cameo_cli_status_set"
    assert summary["cameo_cli_approval_token_count"] == 3
    assert summary["cameo_cli_official_result_required"] is True
    assert summary["cameo_cli_evidence_integrity_ready"] is True
    assert summary["cameo_evidence_integrity_ready"] is True
    assert summary["cameo_evidence_integrity_status"] == "cameo_evidence_integrity_contract_ready"
    assert summary["cameo_evidence_integrity_blocker_count"] == 0
    assert summary["cameo_official_results_pending_honest"] is True
    assert summary["cameo_no_local_native_accuracy_substitution"] is True
    assert summary["cameo_cli_receiver_smoke_status"] == "blocked_cameo_receiver_smoke"
    assert summary["cleanup_cli_status_set_status"] == "blocked_cleanup_cli_status_set"
    assert summary["cleanup_cli_approval_token_count"] == 4
    assert summary["cleanup_cli_approval_reclaim_size_gb"] == 49.216
    assert summary["cleanup_cli_postcheck_contract_ready"] is True
    assert summary["cleanup_cli_protected_payload_size_gb"] == 396.794
    assert summary["cleanup_cli_protected_policy_change_required_count"] == 2
    assert summary["product_architecture_local_surface_ready"] is True
    assert summary["product_architecture_release_ready"] is False
    assert summary["product_architecture_public_benchmark_validation_ready"] is False
    assert summary["product_architecture_public_benchmark_status"] == "blocked_product_public_benchmark_contract"
    assert summary["product_architecture_public_benchmark_blocked_suite_count"] == 5
    assert summary["product_architecture_public_benchmark_suite_materialization_manifest_count"] == 5
    assert summary["product_architecture_public_benchmark_suite_scorecard_row_csv_count"] == 5
    assert summary["product_architecture_public_benchmark_suite_threshold_count"] == 5
    assert summary["product_architecture_public_benchmark_suite_blocker_count"] == 5
    assert summary["product_architecture_public_benchmark_suite_run_command_count"] == 5
    assert summary["product_architecture_public_benchmark_suite_materialization_run_command_count"] == 5
    assert summary["product_architecture_public_benchmark_suite_no_external_dependency_count"] == 5
    assert summary["product_architecture_public_benchmark_requires_24h_server"] is False
    assert summary["public_benchmark_required_for_product_release"] is True
    assert summary["release_blocked_by_public_benchmark"] is True
    assert summary["cameo_live_validation_channel"] is True
    assert summary["cameo_live_validation_required_for_product_release"] is False
    assert summary["cameo_registration_required_for_product_release"] is False
    assert summary["cameo_official_results_required_for_product_release"] is False
    assert summary["release_blocked_by_cameo_live_validation"] is False
    assert summary["product_architecture_cameo_official_validation_evidence_ready"] is False
    assert summary["product_architecture_cameo_receiver_smoke_status"] == "blocked_cameo_receiver_smoke"
    assert summary["product_architecture_cameo_api_dependency_status"] == "blocked_cameo_api_dependency_readiness"
    assert summary["product_architecture_cameo_public_registration_blocker_count"] == 4
    assert summary["product_architecture_cameo_registration_approval_token_count"] == 2
    assert summary["product_architecture_cameo_registration_approval_tokens_required"] == [
        "APPROVE_CAMEO_SERVER_REGISTRATION",
        "APPROVE_CAMEO_OUTBOUND_EMAIL",
    ]
    assert summary["protected_cleanup_policy_change_required_count"] == 2
    assert summary["cleanup_postcheck_contract_status"] == "cleanup_postcheck_contract_ready"
    assert summary["cleanup_postcheck_contract_ready"] is True
    assert summary["cleanup_postcheck_row_count"] == 7
    assert summary["cleanup_postcheck_blocked_row_count"] == 0
    assert summary["source_goal_api_surface_contract_status"] == "goal_api_surface_contract_ready"
    assert summary["goal_api_surface_ready"] is True
    assert summary["goal_api_surface_blocker_count"] == 0
    assert summary["protected_cleanup_policy_decision_gate_status"] == ""
    assert summary["protected_cleanup_policy_resolved"] is False
    assert summary["cleanup_completion_gate_status"] == "blocked_cleanup_completion_gate"
    assert summary["cleanup_completion_complete"] is False
    assert summary["cleanup_completion_blocked_stage_count"] == 4
    assert summary["cleanup_completion_total_reclaim_size_gb"] == 49.216
    assert summary["cleanup_completion_authorized_reclaim_size_gb"] == 0
    assert summary["cleanup_completion_awaiting_approval_count"] == 5
    assert summary["cleanup_completion_blocked_approval_count"] == 5
    assert summary["cleanup_completion_transition_approval_gated_reclaim_size_gb"] == 43.206
    assert summary["cleanup_completion_ligand_heavy_candidate_size_gb"] == 6.011
    assert summary["product_commercial_independence_ready"] is False
    assert summary["execution_enabled"] is False
    assert summary["delete_executed"] is False
    assert summary["external_state_mutated"] is False
    assert any(row["check"] == "public_benchmark_validation_ready" and row["status"] == "fail" for row in payload["rows"])
    architecture_row = next(row for row in payload["rows"] if row["check"] == "product_architecture_release_ready")
    assert architecture_row["status"] == "fail"
    assert "public_benchmark_suite_scorecard_row_csv_count=5" in architecture_row["observed"]
    assert "public_benchmark_suite_run_command_count=5" in architecture_row["observed"]
    assert "cameo_official_evidence_ready=false" in architecture_row["observed"]
    assert "cameo_receiver_smoke_status=blocked_cameo_receiver_smoke" in architecture_row["observed"]
    assert "cameo_api_dependency_status=blocked_cameo_api_dependency_readiness" in architecture_row["observed"]
    assert "cameo_public_registration_blocker_count=4" in architecture_row["observed"]
    assert "cameo_registration_tokens=APPROVE_CAMEO_SERVER_REGISTRATION;APPROVE_CAMEO_OUTBOUND_EMAIL" in architecture_row["observed"]
    assert any(row["check"] == "commercial_independence_gate_ready" and row["status"] == "fail" for row in payload["rows"])
    benchmark_row = next(row for row in payload["rows"] if row["check"] == "public_benchmark_validation_ready")
    assert "suite_materialization_manifest_count=5" in benchmark_row["observed"]
    assert "suite_scorecard_row_csv_count=5" in benchmark_row["observed"]
    assert "suite_run_command_count=5" in benchmark_row["observed"]
    assert any(row["check"] == "protected_cleanup_policy_resolved" and row["status"] == "fail" for row in payload["rows"])
    transition_row = next(row for row in payload["rows"] if row["check"] == "transition_cleanup_complete")
    ligand_row = next(row for row in payload["rows"] if row["check"] == "ligand_heavy_cleanup_complete")
    assert transition_row["status"] == "fail"
    assert "transition_approval_gated_reclaim_size_gb=43.206" in transition_row["observed"]
    assert "approval_awaiting=5" in transition_row["observed"]
    assert "approval_blocked=5" in transition_row["observed"]
    assert ligand_row["status"] == "fail"
    assert "ligand_heavy_candidate_size_gb=6.011" in ligand_row["observed"]
    assert "total_reclaim_size_gb=49.216" in ligand_row["observed"]


def test_goal_release_decision_gate_allows_only_when_all_lanes_are_complete() -> None:
    payload = mod.build_goal_release_decision_gate(
        product_pilot_packet=_ready_product(),
        product_architecture_packet=_ready_product_architecture(),
        product_commercial_independence_packet=_ready_product_independence(),
        cameo_validation_packet=_ready_cameo_validation(),
        cameo_capability_packet=_ready_cameo_capability(),
        goal_rollup_packet=_ready_rollup(),
        operator_action_board_packet=_clear_action_board(),
        transition_cleanup_preflight_packet=_transition_cleanup("transition_cleanup_execution_complete"),
        ligand_cleanup_preflight_packet=_ligand_cleanup("ligand_heavy_cleanup_execution_complete"),
        protected_cleanup_review_packet=_protected_cleanup(0),
        cleanup_postcheck_contract_packet=_ready_cleanup_postcheck(),
        goal_api_surface_contract_packet=_ready_goal_api_surface_contract(),
    )

    summary = payload["summary"]
    assert summary["status"] == "goal_release_ready"
    assert summary["release_allowed"] is True
    assert summary["restricted_release_allowed"] is True
    assert summary["full_commercial_release_allowed"] is True
    assert summary["full_commercial_release_blocker_count"] == 0
    assert summary["full_commercial_release_blocker_ids"] == []
    assert summary["blocker_count"] == 0
    assert all(row["status"] == "pass" for row in payload["rows"])


def test_goal_release_decision_gate_blocks_stale_current_source_of_truth() -> None:
    payload = mod.build_goal_release_decision_gate(
        product_pilot_packet=_ready_product(),
        product_architecture_packet=_ready_product_architecture(),
        product_commercial_independence_packet=_ready_product_independence(),
        cameo_validation_packet=_ready_cameo_validation(),
        cameo_capability_packet=_ready_cameo_capability(),
        goal_rollup_packet=_ready_rollup(),
        operator_action_board_packet=_clear_action_board(),
        transition_cleanup_preflight_packet=_transition_cleanup("transition_cleanup_execution_complete"),
        ligand_cleanup_preflight_packet=_ligand_cleanup("ligand_heavy_cleanup_execution_complete"),
        protected_cleanup_review_packet=_protected_cleanup(0),
        cleanup_postcheck_contract_packet=_ready_cleanup_postcheck(),
        goal_api_surface_contract_packet=_ready_goal_api_surface_contract(),
        product_release_source_of_truth_packet=_blocked_source_of_truth(),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_goal_release_decision"
    assert summary["release_allowed"] is False
    assert summary["product_release_source_of_truth_gate_present"] is True
    assert summary["product_release_source_of_truth_ready"] is False
    assert summary["product_release_source_of_truth_stale_artifact_count"] == 1
    assert summary["product_release_source_of_truth_readme_drift_count"] == 1
    row = next(row for row in payload["rows"] if row["check"] == "product_release_source_of_truth_ready")
    assert row["status"] == "fail"
    assert row["release_blocker"] is True


def test_goal_release_decision_gate_passes_ready_current_source_of_truth() -> None:
    payload = mod.build_goal_release_decision_gate(
        product_pilot_packet=_ready_product(),
        product_architecture_packet=_ready_product_architecture(),
        product_commercial_independence_packet=_ready_product_independence(),
        cameo_validation_packet=_ready_cameo_validation(),
        cameo_capability_packet=_ready_cameo_capability(),
        goal_rollup_packet=_ready_rollup(),
        operator_action_board_packet=_clear_action_board(),
        transition_cleanup_preflight_packet=_transition_cleanup("transition_cleanup_execution_complete"),
        ligand_cleanup_preflight_packet=_ligand_cleanup("ligand_heavy_cleanup_execution_complete"),
        protected_cleanup_review_packet=_protected_cleanup(0),
        cleanup_postcheck_contract_packet=_ready_cleanup_postcheck(),
        goal_api_surface_contract_packet=_ready_goal_api_surface_contract(),
        product_release_source_of_truth_packet=_ready_source_of_truth(),
    )

    summary = payload["summary"]
    assert summary["status"] == "goal_release_ready"
    assert summary["release_allowed"] is True
    assert summary["product_release_source_of_truth_ready"] is True
    assert next(row for row in payload["rows"] if row["check"] == "product_release_source_of_truth_ready")[
        "status"
    ] == "pass"


def test_goal_release_decision_gate_surfaces_full_commercial_matrix_without_blocking_restricted_release() -> None:
    payload = mod.build_goal_release_decision_gate(
        product_pilot_packet=_ready_product(),
        product_architecture_packet=_ready_product_architecture(),
        product_commercial_independence_packet=_ready_product_independence(),
        cameo_validation_packet=_ready_cameo_validation(),
        cameo_capability_packet=_ready_cameo_capability(),
        goal_rollup_packet=_ready_rollup(),
        operator_action_board_packet=_clear_action_board(),
        transition_cleanup_preflight_packet=_transition_cleanup("transition_cleanup_execution_complete"),
        ligand_cleanup_preflight_packet=_ligand_cleanup("ligand_heavy_cleanup_execution_complete"),
        protected_cleanup_review_packet=_protected_cleanup(0),
        cleanup_postcheck_contract_packet=_ready_cleanup_postcheck(),
        goal_api_surface_contract_packet=_ready_goal_api_surface_contract(),
        product_release_source_of_truth_packet=_ready_source_of_truth(),
        product_full_commercial_blocker_evidence_matrix_packet=_blocked_full_commercial_matrix(),
    )

    summary = payload["summary"]
    assert summary["status"] == "goal_release_ready"
    assert summary["release_allowed"] is True
    assert summary["restricted_release_allowed"] is True
    assert summary["full_commercial_release_allowed"] is False
    assert summary["full_commercial_release_blocker_count"] == 2
    assert summary["full_commercial_release_blocker_ids"] == [
        "R8_full_scope_claim_closure",
        "R9_engine_refinement_claim_promotion",
    ]
    assert summary["primary_full_commercial_release_blocker_id"] == "R8_full_scope_claim_closure"
    assert summary["primary_full_commercial_release_blocker"] == "direct_binding_evidence_missing"
    assert summary["full_commercial_release_next_required_step"].startswith("Fill the R8/R9 receipt CSVs")
    assert summary["product_full_commercial_blocker_evidence_matrix_gate_present"] is True
    assert summary["product_full_commercial_blocker_evidence_matrix_status"] == (
        "blocked_product_full_commercial_blocker_evidence_matrix"
    )
    assert summary["product_full_commercial_blocker_evidence_matrix_ready"] is False
    assert summary[
        "product_full_commercial_blocker_evidence_matrix_release_blocker_visibility_ready"
    ] is True
    assert summary["product_full_commercial_blocker_evidence_matrix_row_count"] == 12
    assert summary["product_full_commercial_blocker_evidence_matrix_blocked_row_count"] == 12
    assert summary["product_full_commercial_blocker_evidence_matrix_approval_token_count"] == 2
    assert summary["product_full_commercial_blocker_evidence_matrix_first_blocked_release_blocker_id"] == (
        "R8_full_scope_claim_closure"
    )
    assert summary["product_full_commercial_blocker_evidence_matrix_first_blocked_evidence_row_id"] == (
        "direct_binding_evidence_missing"
    )
    assert summary["product_full_commercial_blocker_evidence_matrix_first_blocked_evidence_artifact"] == (
        "OPERATOR_FILL_LOCAL_EVIDENCE_JSON"
    )
    assert summary[
        "product_full_commercial_blocker_evidence_matrix_first_blocked_expected_evidence_status"
    ] == "product_scope_transporter_direct_binding_evidence_ready"
    assert summary[
        "product_full_commercial_blocker_evidence_matrix_first_blocked_observed_evidence_status"
    ] == "missing"
    assert summary["product_full_commercial_blocker_evidence_matrix_first_blocked_row_blockers"] == (
        "operator_placeholders_unfilled"
    )
    assert summary["product_full_commercial_blocker_evidence_matrix_scope_receipt_most_common_row_blocker"] == (
        "operator_placeholders_unfilled"
    )
    assert summary["product_full_commercial_blocker_evidence_matrix_engine_receipt_most_common_row_blocker"] == (
        "operator_placeholders_unfilled"
    )
    matrix_row = next(
        row
        for row in payload["rows"]
        if row["check"] == "product_full_commercial_blocker_evidence_matrix_recorded"
    )
    assert matrix_row["status"] == "pass"
    assert matrix_row["release_blocker"] is False
    assert "first_blocked_evidence_row_id=direct_binding_evidence_missing" in matrix_row["observed"]
    assert "first_blocked_evidence_artifact=OPERATOR_FILL_LOCAL_EVIDENCE_JSON" in matrix_row["observed"]
    assert "scope_receipt_most_common_row_blocker=operator_placeholders_unfilled" in matrix_row["observed"]


def test_goal_release_decision_gate_surfaces_r4_smoke_and_master_rollup_without_blocking_restricted_release() -> None:
    payload = mod.build_goal_release_decision_gate(
        product_pilot_packet=_ready_product(),
        product_architecture_packet=_ready_product_architecture(),
        product_commercial_independence_packet=_ready_product_independence(),
        cameo_validation_packet=_ready_cameo_validation(),
        cameo_capability_packet=_ready_cameo_capability(),
        goal_rollup_packet=_ready_rollup(),
        operator_action_board_packet=_clear_action_board(),
        transition_cleanup_preflight_packet=_transition_cleanup("transition_cleanup_execution_complete"),
        ligand_cleanup_preflight_packet=_ligand_cleanup("ligand_heavy_cleanup_execution_complete"),
        protected_cleanup_review_packet=_protected_cleanup(0),
        cleanup_postcheck_contract_packet=_ready_cleanup_postcheck(),
        goal_api_surface_contract_packet=_ready_goal_api_surface_contract(),
        product_release_source_of_truth_packet=_ready_source_of_truth(),
        product_rollout_execution_smoke_receipt_packet=_blocked_rollout_smoke_receipt(),
        master_gap_closure_rollup_packet=_blocked_master_gap_rollup(),
    )

    summary = payload["summary"]
    assert summary["status"] == "goal_release_ready"
    assert summary["release_allowed"] is True
    assert summary["product_rollout_execution_smoke_receipt_gate_present"] is True
    assert summary["product_rollout_execution_smoke_receipt_status"] == (
        "blocked_product_rollout_execution_smoke_receipt"
    )
    assert summary["product_rollout_execution_smoke_receipt_ready"] is False
    assert summary["product_rollout_execution_smoke_receipt_csv_present"] is False
    assert summary["product_rollout_execution_smoke_receipt_rollout_executed"] is False
    assert summary["master_gap_closure_rollup_gate_present"] is True
    assert summary["master_gap_closure_rollup_status"] == "blocked_master_gap_closure_rollup"
    assert summary["master_gap_closure_rollup_open_gap_ids"] == ["SCI-CLAIM", "DEPLOY-OPS"]
    smoke_row = next(
        row
        for row in payload["rows"]
        if row["check"] == "product_rollout_execution_smoke_receipt_recorded"
    )
    master_row = next(
        row for row in payload["rows"] if row["check"] == "master_gap_closure_rollup_recorded"
    )
    assert smoke_row["status"] == "pass"
    assert smoke_row["release_blocker"] is False
    assert "rollout_executed=false" in smoke_row["observed"]
    assert master_row["status"] == "pass"
    assert master_row["release_blocker"] is False
    assert "open_gap_ids=SCI-CLAIM;DEPLOY-OPS" in master_row["observed"]


def test_goal_release_decision_gate_blocks_missing_api_customer_flow_release_evidence() -> None:
    payload = mod.build_goal_release_decision_gate(
        product_pilot_packet=_ready_product(),
        product_architecture_packet=_ready_product_architecture(),
        product_commercial_independence_packet=_ready_product_independence(),
        cameo_validation_packet=_ready_cameo_validation(),
        cameo_capability_packet=_ready_cameo_capability(),
        goal_rollup_packet=_ready_rollup(),
        operator_action_board_packet=_clear_action_board(),
        transition_cleanup_preflight_packet=_transition_cleanup("transition_cleanup_execution_complete"),
        ligand_cleanup_preflight_packet=_ligand_cleanup("ligand_heavy_cleanup_execution_complete"),
        protected_cleanup_review_packet=_protected_cleanup(0),
        cleanup_postcheck_contract_packet=_ready_cleanup_postcheck(),
        goal_api_surface_contract_packet=_ready_goal_api_surface_contract(),
        api_customer_flow_release_evidence_packet=_blocked_api_customer_flow(),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_goal_release_decision"
    assert summary["release_allowed"] is False
    assert summary["api_customer_flow_release_evidence_gate_present"] is True
    assert summary["api_customer_flow_release_evidence_ready"] is False
    row = next(row for row in payload["rows"] if row["check"] == "api_customer_flow_release_evidence_ready")
    assert row["status"] == "fail"
    assert row["release_blocker"] is True


def test_goal_release_decision_gate_passes_ready_api_customer_flow_release_evidence() -> None:
    payload = mod.build_goal_release_decision_gate(
        product_pilot_packet=_ready_product(),
        product_architecture_packet=_ready_product_architecture(),
        product_commercial_independence_packet=_ready_product_independence(),
        cameo_validation_packet=_ready_cameo_validation(),
        cameo_capability_packet=_ready_cameo_capability(),
        goal_rollup_packet=_ready_rollup(),
        operator_action_board_packet=_clear_action_board(),
        transition_cleanup_preflight_packet=_transition_cleanup("transition_cleanup_execution_complete"),
        ligand_cleanup_preflight_packet=_ligand_cleanup("ligand_heavy_cleanup_execution_complete"),
        protected_cleanup_review_packet=_protected_cleanup(0),
        cleanup_postcheck_contract_packet=_ready_cleanup_postcheck(),
        goal_api_surface_contract_packet=_ready_goal_api_surface_contract(),
        api_customer_flow_release_evidence_packet=_ready_api_customer_flow(),
    )

    summary = payload["summary"]
    assert summary["status"] == "goal_release_ready"
    assert summary["release_allowed"] is True
    assert summary["api_customer_flow_release_evidence_ready"] is True
    assert next(row for row in payload["rows"] if row["check"] == "api_customer_flow_release_evidence_ready")[
        "status"
    ] == "pass"


def test_goal_release_decision_gate_does_not_block_on_optional_cameo_live_validation() -> None:
    payload = mod.build_goal_release_decision_gate(
        product_pilot_packet=_ready_product(),
        product_architecture_packet=_ready_product_architecture(),
        product_commercial_independence_packet=_ready_product_independence(),
        cameo_validation_packet=_blocked_cameo_validation(),
        cameo_capability_packet=_blocked_cameo_capability(),
        goal_rollup_packet=_ready_rollup(),
        operator_action_board_packet=_clear_action_board(),
        transition_cleanup_preflight_packet=_transition_cleanup("transition_cleanup_execution_complete"),
        ligand_cleanup_preflight_packet=_ligand_cleanup("ligand_heavy_cleanup_execution_complete"),
        protected_cleanup_review_packet=_protected_cleanup(0),
        cleanup_postcheck_contract_packet=_ready_cleanup_postcheck(),
        goal_api_surface_contract_packet=_ready_goal_api_surface_contract(),
    )

    summary = payload["summary"]
    assert summary["status"] == "goal_release_ready"
    assert summary["release_allowed"] is True
    assert summary["cameo_architecture_validation_ready"] is False
    assert summary["cameo_live_validation_channel"] is True
    assert summary["cameo_live_validation_required_for_product_release"] is False
    assert summary["cameo_registration_required_for_product_release"] is False
    assert summary["cameo_official_results_required_for_product_release"] is False
    assert summary["release_blocked_by_cameo_live_validation"] is False
    assert not any("cameo" in row["check"] for row in payload["rows"])


def test_goal_release_decision_gate_accepts_nonblocking_pending_rollup_lanes() -> None:
    payload = mod.build_goal_release_decision_gate(
        product_pilot_packet=_ready_product(),
        product_architecture_packet=_ready_product_architecture(),
        product_commercial_independence_packet=_ready_product_independence(),
        cameo_validation_packet=_blocked_cameo_validation(),
        cameo_capability_packet=_blocked_cameo_capability(),
        goal_rollup_packet=_pending_nonblocking_rollup(),
        operator_action_board_packet=_clear_action_board(),
        transition_cleanup_preflight_packet=_transition_cleanup("transition_cleanup_execution_complete"),
        ligand_cleanup_preflight_packet=_ligand_cleanup("ligand_heavy_cleanup_execution_complete"),
        protected_cleanup_review_packet=_protected_cleanup(0),
        cleanup_postcheck_contract_packet=_ready_cleanup_postcheck(),
        goal_api_surface_contract_packet=_ready_goal_api_surface_contract(),
    )

    summary = payload["summary"]
    assert summary["status"] == "goal_release_ready"
    assert summary["release_allowed"] is True
    row = next(row for row in payload["rows"] if row["check"] == "product_release_evidence_ready")
    assert row["status"] == "pass"
    assert "operator_approval_pending_count=3" in row["observed"]
    assert "external_results_pending_count=1" in row["observed"]


def test_goal_release_decision_gate_accepts_release_complete_operator_pending_split() -> None:
    payload = mod.build_goal_release_decision_gate(
        product_pilot_packet=_ready_product(),
        product_architecture_packet=_ready_product_architecture(),
        product_commercial_independence_packet=_ready_product_independence(),
        cameo_validation_packet=_blocked_cameo_validation(),
        cameo_capability_packet=_blocked_cameo_capability(),
        goal_rollup_packet=_release_complete_operator_pending_rollup(),
        operator_action_board_packet=_clear_action_board(),
        transition_cleanup_preflight_packet=_transition_cleanup("transition_cleanup_execution_complete"),
        ligand_cleanup_preflight_packet=_ligand_cleanup("ligand_heavy_cleanup_execution_complete"),
        protected_cleanup_review_packet=_protected_cleanup(0),
        cleanup_postcheck_contract_packet=_ready_cleanup_postcheck(),
        goal_api_surface_contract_packet=_ready_goal_api_surface_contract(),
    )

    summary = payload["summary"]
    assert summary["status"] == "goal_release_ready"
    assert summary["release_allowed"] is True
    row = next(row for row in payload["rows"] if row["check"] == "product_release_evidence_ready")
    assert row["status"] == "pass"
    assert "goal_readiness_release_complete_operator_pending" in row["observed"]


def test_goal_release_decision_gate_accepts_explicit_keep_policy_gate() -> None:
    payload = mod.build_goal_release_decision_gate(
        product_pilot_packet=_ready_product(),
        product_architecture_packet=_ready_product_architecture(),
        product_commercial_independence_packet=_ready_product_independence(),
        cameo_validation_packet=_ready_cameo_validation(),
        cameo_capability_packet=_ready_cameo_capability(),
        goal_rollup_packet=_ready_rollup(),
        operator_action_board_packet=_clear_action_board(),
        transition_cleanup_preflight_packet=_transition_cleanup("transition_cleanup_execution_complete"),
        ligand_cleanup_preflight_packet=_ligand_cleanup("ligand_heavy_cleanup_execution_complete"),
        protected_cleanup_review_packet=_protected_cleanup(2),
        protected_cleanup_policy_decision_gate_packet=_protected_policy_gate_ready(),
        cleanup_postcheck_contract_packet=_ready_cleanup_postcheck(),
        goal_api_surface_contract_packet=_ready_goal_api_surface_contract(),
    )

    summary = payload["summary"]
    assert summary["status"] == "goal_release_ready"
    assert summary["protected_cleanup_policy_change_required_count"] == 2
    assert summary["protected_cleanup_policy_decision_gate_status"] == "protected_cleanup_policy_decision_gate_ready"
    assert summary["protected_cleanup_known_payload_child_count"] == 2
    assert summary["protected_cleanup_known_payload_child_size_gb"] == 396.794
    assert summary["protected_cleanup_preservation_sibling_count"] == 2
    assert summary["protected_cleanup_policy_change_required_for_deletion_count"] == 2
    assert summary["protected_cleanup_policy_resolved"] is True
    row = next(row for row in payload["rows"] if row["check"] == "protected_cleanup_policy_resolved")
    assert row["status"] == "pass"
    assert "known_payload_child_size_gb=396.794" in row["observed"]


def test_goal_release_decision_gate_accepts_cleanup_completion_gate() -> None:
    payload = mod.build_goal_release_decision_gate(
        product_pilot_packet=_ready_product(),
        product_architecture_packet=_ready_product_architecture(),
        product_commercial_independence_packet=_ready_product_independence(),
        cameo_validation_packet=_ready_cameo_validation(),
        cameo_capability_packet=_ready_cameo_capability(),
        goal_rollup_packet=_ready_rollup(),
        operator_action_board_packet=_clear_action_board(),
        transition_cleanup_preflight_packet=_transition_cleanup("transition_cleanup_execution_preflight_ready"),
        ligand_cleanup_preflight_packet=_ligand_cleanup("ligand_heavy_cleanup_execution_preflight_ready"),
        protected_cleanup_review_packet=_protected_cleanup(2),
        protected_cleanup_policy_decision_gate_packet={},
        cleanup_postcheck_contract_packet=_ready_cleanup_postcheck(),
        cleanup_completion_gate_packet=_cleanup_completion_ready(),
        goal_api_surface_contract_packet=_ready_goal_api_surface_contract(),
    )

    assert payload["summary"]["status"] == "goal_release_ready"
    assert payload["summary"]["cleanup_completion_gate_status"] == "cleanup_completion_gate_ready"
    assert payload["summary"]["cleanup_completion_complete"] is True
    assert next(row for row in payload["rows"] if row["check"] == "transition_cleanup_complete")["status"] == "pass"
    assert next(row for row in payload["rows"] if row["check"] == "ligand_heavy_cleanup_complete")["status"] == "pass"
    assert next(row for row in payload["rows"] if row["check"] == "protected_cleanup_policy_resolved")["status"] == "pass"


def test_goal_release_decision_gate_next_step_omits_cleanup_when_completion_gate_ready() -> None:
    payload = mod.build_goal_release_decision_gate(
        product_pilot_packet=_blocked_product(),
        product_architecture_packet=_blocked_product_architecture(),
        product_commercial_independence_packet=_blocked_product_independence(),
        cameo_validation_packet=_blocked_cameo_validation(),
        cameo_capability_packet=_ready_cameo_capability(),
        goal_rollup_packet=_blocked_rollup(),
        operator_action_board_packet=_blocked_action_board(),
        transition_cleanup_preflight_packet=_transition_cleanup("transition_cleanup_execution_preflight_ready"),
        ligand_cleanup_preflight_packet=_ligand_cleanup("ligand_heavy_cleanup_execution_preflight_ready"),
        protected_cleanup_review_packet=_protected_cleanup(2),
        protected_cleanup_policy_decision_gate_packet={},
        cleanup_postcheck_contract_packet=_ready_cleanup_postcheck(),
        cleanup_completion_gate_packet=_cleanup_completion_ready(),
        goal_api_surface_contract_packet=_ready_goal_api_surface_contract(),
    )

    next_step = payload["summary"]["next_required_step"]
    assert payload["summary"]["status"] == "blocked_goal_release_decision"
    assert payload["summary"]["cleanup_objective_ready"] is True
    assert "cleanup" not in next_step
    assert "product bundle validation" in next_step
    assert "public benchmark scorecards" in next_step


def test_goal_release_decision_gate_accepts_cameo_registration_approval_gate() -> None:
    blocked_capability_without_allowed_flag = {"summary": {"status": "blocked_cameo_capability_preflight", "public_registration_allowed": False}}
    payload = mod.build_goal_release_decision_gate(
        product_pilot_packet=_ready_product(),
        product_architecture_packet=_ready_product_architecture(),
        product_commercial_independence_packet=_ready_product_independence(),
        cameo_validation_packet=_ready_cameo_validation(),
        cameo_capability_packet=blocked_capability_without_allowed_flag,
        cameo_public_registration_approval_gate_packet=_ready_cameo_registration_gate(),
        goal_rollup_packet=_ready_rollup(),
        operator_action_board_packet=_clear_action_board(),
        transition_cleanup_preflight_packet=_transition_cleanup("transition_cleanup_execution_complete"),
        ligand_cleanup_preflight_packet=_ligand_cleanup("ligand_heavy_cleanup_execution_complete"),
        protected_cleanup_review_packet=_protected_cleanup(0),
        cleanup_postcheck_contract_packet=_ready_cleanup_postcheck(),
        goal_api_surface_contract_packet=_ready_goal_api_surface_contract(),
    )

    assert payload["summary"]["status"] == "goal_release_ready"
    assert payload["summary"]["source_cameo_public_registration_approval_gate_status"] == "cameo_public_registration_approval_gate_ready"
    assert payload["summary"]["cameo_public_registration_authorized_for_registration_review"] is True
    assert not any(row["check"] == "cameo_public_registration_allowed" for row in payload["rows"])


def test_goal_release_decision_gate_requires_product_commercial_independence_gate() -> None:
    payload = mod.build_goal_release_decision_gate(
        product_pilot_packet=_ready_product(),
        product_architecture_packet=_ready_product_architecture(),
        product_commercial_independence_packet=_blocked_product_independence(),
        cameo_validation_packet=_ready_cameo_validation(),
        cameo_capability_packet=_ready_cameo_capability(),
        goal_rollup_packet=_ready_rollup(),
        operator_action_board_packet=_clear_action_board(),
        transition_cleanup_preflight_packet=_transition_cleanup("transition_cleanup_execution_complete"),
        ligand_cleanup_preflight_packet=_ligand_cleanup("ligand_heavy_cleanup_execution_complete"),
        protected_cleanup_review_packet=_protected_cleanup(0),
        cleanup_postcheck_contract_packet=_ready_cleanup_postcheck(),
        goal_api_surface_contract_packet=_ready_goal_api_surface_contract(),
    )

    assert payload["summary"]["status"] == "blocked_goal_release_decision"
    assert payload["summary"]["commercial_independent_product_ready"] is False
    assert payload["summary"]["product_commercial_independence_ready"] is False
    assert next(row for row in payload["rows"] if row["check"] == "commercial_independence_gate_ready")["status"] == "fail"


def test_goal_release_decision_gate_requires_product_architecture_contract() -> None:
    payload = mod.build_goal_release_decision_gate(
        product_pilot_packet=_ready_product(),
        product_architecture_packet=_blocked_product_architecture(),
        product_commercial_independence_packet=_ready_product_independence(),
        cameo_validation_packet=_ready_cameo_validation(),
        cameo_capability_packet=_ready_cameo_capability(),
        goal_rollup_packet=_ready_rollup(),
        operator_action_board_packet=_clear_action_board(),
        transition_cleanup_preflight_packet=_transition_cleanup("transition_cleanup_execution_complete"),
        ligand_cleanup_preflight_packet=_ligand_cleanup("ligand_heavy_cleanup_execution_complete"),
        protected_cleanup_review_packet=_protected_cleanup(0),
        cleanup_postcheck_contract_packet=_ready_cleanup_postcheck(),
        goal_api_surface_contract_packet=_ready_goal_api_surface_contract(),
    )

    assert payload["summary"]["status"] == "blocked_goal_release_decision"
    assert payload["summary"]["commercial_independent_product_ready"] is False
    assert payload["summary"]["product_architecture_release_ready"] is False
    assert next(row for row in payload["rows"] if row["check"] == "product_architecture_release_ready")["status"] == "fail"


def test_goal_release_decision_gate_requires_cleanup_postcheck_contract() -> None:
    payload = mod.build_goal_release_decision_gate(
        product_pilot_packet=_ready_product(),
        product_architecture_packet=_ready_product_architecture(),
        product_commercial_independence_packet=_ready_product_independence(),
        cameo_validation_packet=_ready_cameo_validation(),
        cameo_capability_packet=_ready_cameo_capability(),
        goal_rollup_packet=_ready_rollup(),
        operator_action_board_packet=_clear_action_board(),
        transition_cleanup_preflight_packet=_transition_cleanup("transition_cleanup_execution_complete"),
        ligand_cleanup_preflight_packet=_ligand_cleanup("ligand_heavy_cleanup_execution_complete"),
        protected_cleanup_review_packet=_protected_cleanup(0),
        cleanup_postcheck_contract_packet=_blocked_cleanup_postcheck(),
        goal_api_surface_contract_packet=_ready_goal_api_surface_contract(),
    )

    assert payload["summary"]["status"] == "blocked_goal_release_decision"
    assert payload["summary"]["cleanup_objective_ready"] is False
    assert payload["summary"]["cleanup_postcheck_contract_ready"] is False
    row = next(row for row in payload["rows"] if row["check"] == "cleanup_postcheck_contract_ready")
    assert row["status"] == "fail"
    assert "blocked_rows=1" in row["observed"]


def test_goal_release_decision_gate_requires_goal_api_surface_contract() -> None:
    payload = mod.build_goal_release_decision_gate(
        product_pilot_packet=_ready_product(),
        product_architecture_packet=_ready_product_architecture(),
        product_commercial_independence_packet=_ready_product_independence(),
        cameo_validation_packet=_ready_cameo_validation(),
        cameo_capability_packet=_ready_cameo_capability(),
        goal_rollup_packet=_ready_rollup(),
        operator_action_board_packet=_clear_action_board(),
        transition_cleanup_preflight_packet=_transition_cleanup("transition_cleanup_execution_complete"),
        ligand_cleanup_preflight_packet=_ligand_cleanup("ligand_heavy_cleanup_execution_complete"),
        protected_cleanup_review_packet=_protected_cleanup(0),
        cleanup_postcheck_contract_packet=_ready_cleanup_postcheck(),
        goal_api_surface_contract_packet=_blocked_goal_api_surface_contract(),
    )

    assert payload["summary"]["status"] == "blocked_goal_release_decision"
    assert payload["summary"]["goal_api_surface_ready"] is False
    assert payload["summary"]["goal_api_surface_blocker_count"] == 1
    row = next(row for row in payload["rows"] if row["check"] == "goal_api_surface_contract_ready")
    assert row["status"] == "fail"
    assert "missing_endpoint_count=1" in row["observed"]


def test_goal_release_decision_gate_requires_product_ai_architecture_closure_when_supplied() -> None:
    payload = mod.build_goal_release_decision_gate(
        product_pilot_packet=_ready_product(),
        product_architecture_packet=_ready_product_architecture(),
        product_commercial_independence_packet=_ready_product_independence(),
        cameo_validation_packet=_ready_cameo_validation(),
        cameo_capability_packet=_ready_cameo_capability(),
        goal_rollup_packet=_ready_rollup(),
        operator_action_board_packet=_clear_action_board(),
        transition_cleanup_preflight_packet=_transition_cleanup("transition_cleanup_execution_complete"),
        ligand_cleanup_preflight_packet=_ligand_cleanup("ligand_heavy_cleanup_execution_complete"),
        protected_cleanup_review_packet=_protected_cleanup(0),
        cleanup_postcheck_contract_packet=_ready_cleanup_postcheck(),
        goal_api_surface_contract_packet=_ready_goal_api_surface_contract(),
        product_ai_architecture_gap_packet=_blocked_product_ai_gap(),
        product_ai_execution_backlog_packet=_blocked_product_ai_backlog(),
    )

    summary = payload["summary"]
    row = next(row for row in payload["rows"] if row["check"] == "product_ai_architecture_gap_closure_ready")
    assert summary["status"] == "blocked_goal_release_decision"
    assert summary["release_allowed"] is False
    assert summary["product_ai_architecture_gate_present"] is True
    assert summary["product_ai_architecture_ready"] is False
    assert summary["product_ai_architecture_open_gap_count"] == 1
    assert summary["product_ai_execution_backlog_work_item_count"] == 21
    assert summary["product_ai_execution_backlog_primary_work_item_id"] == "training_data.production_delta_force_label_evidence"
    assert "gpu_worker_return_expected_queue_rows=768" in summary["product_ai_execution_backlog_primary_detail"]
    assert "gpu_worker_return_manifest_operator_verified=False" in summary["product_ai_execution_backlog_primary_detail"]
    assert "scope_closure_first_scientific_blocker=AQP1.core_binder_01" in summary[
        "product_ai_execution_backlog_scope_closure_detail"
    ]
    assert row["status"] == "fail"
    assert "scope_breadth_expansion" in row["observed"]
    assert "primary_backlog_work_item_id=training_data.production_delta_force_label_evidence" in row["observed"]
    assert "gpu_worker_return_operator_verified_true_count=0" in row["observed"]
    assert "scope_closure_pxr_reconciled_blocked_row_count=6" in row["observed"]
    assert "gpu_worker_return_queue_fingerprints=768" in row["reason"]
    assert "scope_closure_authoritative_apply_allowed=False" in row["reason"]
    assert "product AI architecture gap closure" in summary["next_required_step"]


def test_goal_release_decision_gate_accepts_product_ai_architecture_closure_when_supplied() -> None:
    payload = mod.build_goal_release_decision_gate(
        product_pilot_packet=_ready_product(),
        product_architecture_packet=_ready_product_architecture(),
        product_commercial_independence_packet=_ready_product_independence(),
        cameo_validation_packet=_ready_cameo_validation(),
        cameo_capability_packet=_ready_cameo_capability(),
        goal_rollup_packet=_ready_rollup(),
        operator_action_board_packet=_clear_action_board(),
        transition_cleanup_preflight_packet=_transition_cleanup("transition_cleanup_execution_complete"),
        ligand_cleanup_preflight_packet=_ligand_cleanup("ligand_heavy_cleanup_execution_complete"),
        protected_cleanup_review_packet=_protected_cleanup(0),
        cleanup_postcheck_contract_packet=_ready_cleanup_postcheck(),
        goal_api_surface_contract_packet=_ready_goal_api_surface_contract(),
        product_ai_architecture_gap_packet=_ready_product_ai_gap(),
        product_ai_execution_backlog_packet=_ready_product_ai_backlog(),
    )

    assert payload["summary"]["status"] == "goal_release_ready"
    assert payload["summary"]["product_ai_architecture_ready"] is True
    assert next(row for row in payload["rows"] if row["check"] == "product_ai_architecture_gap_closure_ready")["status"] == "pass"


def test_goal_release_decision_gate_tool_writes_outputs(tmp_path: Path) -> None:
    paths = {
        "product": tmp_path / "product.json",
        "product_architecture": tmp_path / "product_architecture.json",
        "product_independence": tmp_path / "product_independence.json",
        "cameo_validation": tmp_path / "cameo_validation.json",
        "cameo_capability": tmp_path / "cameo_capability.json",
        "rollup": tmp_path / "rollup.json",
        "actions": tmp_path / "actions.json",
        "transition_cleanup": tmp_path / "transition_cleanup.json",
        "ligand_cleanup": tmp_path / "ligand_cleanup.json",
        "protected_cleanup": tmp_path / "protected_cleanup.json",
        "cleanup_postcheck": tmp_path / "cleanup_postcheck.json",
        "goal_api_surface": tmp_path / "goal_api_surface.json",
        "product_ai_gap": tmp_path / "product_ai_gap.json",
        "product_ai_backlog": tmp_path / "product_ai_backlog.json",
        "source_of_truth": tmp_path / "source_of_truth.json",
        "api_customer_flow": tmp_path / "api_customer_flow.json",
        "full_commercial_matrix": tmp_path / "full_commercial_matrix.json",
        "rollout_smoke_receipt": tmp_path / "rollout_smoke_receipt.json",
        "master_gap_rollup": tmp_path / "master_gap_rollup.json",
    }
    paths["product"].write_text(json.dumps(_blocked_product()) + "\n", encoding="utf-8")
    paths["product_architecture"].write_text(json.dumps(_blocked_product_architecture()) + "\n", encoding="utf-8")
    paths["product_independence"].write_text(json.dumps(_blocked_product_independence()) + "\n", encoding="utf-8")
    paths["cameo_validation"].write_text(json.dumps(_blocked_cameo_validation()) + "\n", encoding="utf-8")
    paths["cameo_capability"].write_text(json.dumps(_blocked_cameo_capability()) + "\n", encoding="utf-8")
    paths["rollup"].write_text(json.dumps(_blocked_rollup()) + "\n", encoding="utf-8")
    paths["actions"].write_text(json.dumps(_blocked_action_board()) + "\n", encoding="utf-8")
    paths["transition_cleanup"].write_text(json.dumps(_transition_cleanup("transition_cleanup_execution_preflight_ready")) + "\n", encoding="utf-8")
    paths["ligand_cleanup"].write_text(json.dumps(_ligand_cleanup("ligand_heavy_cleanup_execution_preflight_ready")) + "\n", encoding="utf-8")
    paths["protected_cleanup"].write_text(json.dumps(_protected_cleanup(2)) + "\n", encoding="utf-8")
    paths["cleanup_postcheck"].write_text(json.dumps(_ready_cleanup_postcheck()) + "\n", encoding="utf-8")
    paths["goal_api_surface"].write_text(json.dumps(_ready_goal_api_surface_contract()) + "\n", encoding="utf-8")
    paths["product_ai_gap"].write_text(json.dumps(_ready_product_ai_gap()) + "\n", encoding="utf-8")
    paths["product_ai_backlog"].write_text(json.dumps(_ready_product_ai_backlog()) + "\n", encoding="utf-8")
    paths["source_of_truth"].write_text(json.dumps(_ready_source_of_truth()) + "\n", encoding="utf-8")
    paths["api_customer_flow"].write_text(json.dumps(_ready_api_customer_flow()) + "\n", encoding="utf-8")
    paths["full_commercial_matrix"].write_text(
        json.dumps(_blocked_full_commercial_matrix()) + "\n",
        encoding="utf-8",
    )
    paths["rollout_smoke_receipt"].write_text(
        json.dumps(_blocked_rollout_smoke_receipt()) + "\n",
        encoding="utf-8",
    )
    paths["master_gap_rollup"].write_text(
        json.dumps(_blocked_master_gap_rollup()) + "\n",
        encoding="utf-8",
    )
    out_json = tmp_path / "release_gate.json"
    out_csv = tmp_path / "release_gate.csv"
    out_md = tmp_path / "release_gate.md"

    mod.main(
        [
            "--product-pilot-json",
            str(paths["product"]),
            "--product-architecture-json",
            str(paths["product_architecture"]),
            "--product-commercial-independence-json",
            str(paths["product_independence"]),
            "--cameo-validation-json",
            str(paths["cameo_validation"]),
            "--cameo-capability-json",
            str(paths["cameo_capability"]),
            "--goal-rollup-json",
            str(paths["rollup"]),
            "--operator-action-board-json",
            str(paths["actions"]),
            "--transition-cleanup-preflight-json",
            str(paths["transition_cleanup"]),
            "--ligand-cleanup-preflight-json",
            str(paths["ligand_cleanup"]),
            "--protected-cleanup-review-json",
            str(paths["protected_cleanup"]),
            "--cleanup-postcheck-contract-json",
            str(paths["cleanup_postcheck"]),
            "--goal-api-surface-contract-json",
            str(paths["goal_api_surface"]),
            "--product-ai-architecture-gap-json",
            str(paths["product_ai_gap"]),
            "--product-ai-execution-backlog-json",
            str(paths["product_ai_backlog"]),
            "--product-release-source-of-truth-json",
            str(paths["source_of_truth"]),
            "--api-customer-flow-release-evidence-json",
            str(paths["api_customer_flow"]),
            "--product-full-commercial-blocker-evidence-matrix-json",
            str(paths["full_commercial_matrix"]),
            "--product-rollout-execution-smoke-receipt-json",
            str(paths["rollout_smoke_receipt"]),
            "--master-gap-closure-rollup-json",
            str(paths["master_gap_rollup"]),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    summary = json.loads(out_json.read_text(encoding="utf-8"))["summary"]
    assert summary["status"] == "blocked_goal_release_decision"
    assert summary["product_full_commercial_blocker_evidence_matrix_status"] == (
        "blocked_product_full_commercial_blocker_evidence_matrix"
    )
    assert summary["product_rollout_execution_smoke_receipt_status"] == (
        "blocked_product_rollout_execution_smoke_receipt"
    )
    assert summary["master_gap_closure_rollup_status"] == "blocked_master_gap_closure_rollup"
    assert summary["release_blocked_by_public_benchmark"] is True
    assert summary["cameo_live_validation_required_for_product_release"] is False
    assert out_csv.read_text(encoding="utf-8").startswith("lane_id,check,")
    md_text = out_md.read_text(encoding="utf-8")
    assert "Goal Release Decision Gate" in md_text
    assert "cameo_live_validation_required_for_product_release" in md_text
    assert "product_full_commercial_blocker_evidence_matrix_status" in md_text
    assert "product_rollout_execution_smoke_receipt_status" in md_text
    assert "master_gap_closure_rollup_status" in md_text
