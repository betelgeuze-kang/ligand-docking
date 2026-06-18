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


def _blocked_cameo_official_result_fetch_preflight() -> dict:
    return {
        "summary": {
            "status": "blocked_cameo_official_result_fetch_preflight",
            "authorized_for_separate_operator_fetch": False,
            "operator_fetch_csv": "runs/cameo_official_result_fetch_operator_approval_intake.csv",
            "operator_fetch_csv_present": False,
            "operator_template_csv": (
                "runs/cameo_official_result_fetch_operator_approval_template_current.csv"
            ),
            "blocked_row_count": 1,
            "blocker_count": 2,
            "awaiting_operator_fetch_approval_row_count": 1,
            "fetch_approval_token_required": "APPROVE_CAMEO_OFFICIAL_RESULT_FETCH",
            "network_request_opened": False,
            "official_results_fetched": False,
            "native_local_accuracy_used": False,
            "outbound_email_enabled": False,
            "external_state_mutated": False,
        }
    }


def _self_hosted_license_distribution_audit() -> dict:
    return {
        "summary": {
            "status": "self_hosted_license_distribution_audit_recorded",
            "product_license_path": "LICENSE",
            "product_license_sha256": "license-hash",
            "approved_license_text_source": "LICENSE",
            "approved_license_text_source_sha256": "license-hash",
            "spdx_license_id": "ProprietaryRef-Betelgeuze",
            "copyright_holder": "JIHOON KANG",
            "hard_blocker_count": 0,
            "operator_review_item_count": 1,
            "legal_advice_provided": False,
            "third_party_license_review_gate_status": "third_party_license_review_gate_ready",
            "third_party_license_review_gate_ready": True,
            "third_party_license_review_gate_blocker_count": 0,
            "third_party_dual_license_assets": ["jszip"],
            "viewer_third_party_notice_path": "viewer/vendor/THIRD_PARTY_NOTICES.md",
            "external_state_mutated": False,
        }
    }


def _third_party_license_review_gate() -> dict:
    return {
        "summary": {
            "status": "third_party_license_review_gate_ready",
            "allowed_license_paths": [
                "GPL-3.0-or-later",
                "MIT",
                "remove_or_replace_asset",
            ],
            "approval_token_required": "APPROVE_THIRD_PARTY_LICENSE_REVIEW",
            "approved_assets": ["jszip"],
            "approved_review_asset_count": 1,
            "asset_modified": False,
            "blocker_count": 0,
            "deferred_review_asset_count": 0,
            "expected_review_asset_count": 1,
            "external_state_mutated": False,
            "legal_advice_provided": False,
            "missing_review_asset_count": 0,
            "operator_template_csv": "runs/third_party_license_review_operator_template_current.csv",
            "review_csv": "runs/third_party_license_review_operator_intake.csv",
            "review_csv_present": True,
            "review_row_count": 1,
            "source_hard_blocker_count": 0,
            "source_license_audit_status": "self_hosted_license_distribution_audit_recorded",
            "source_operator_review_item_count": 1,
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


def _optional_product_ai_backlog() -> dict:
    return {
        "summary": {
            "status": "product_ai_architecture_execution_backlog_ready",
            "backlog_clear": False,
            "work_item_count": 12,
            "release_blocking_work_item_count": 0,
            "primary_work_item_id": "scope_breadth.transporter.AQP1.core_non_binder_01",
            "scope_closure_detail": (
                "scope_closure_blocker_classes=exact_negative_quantitative_value_missing=6;"
                "scope_closure_authoritative_apply_allowed=False"
            ),
        },
        "rows": [
            {
                "work_item_id": "scope_breadth.transporter.AQP1.core_non_binder_01",
                "observed": "candidate_reference_binding_kcal_mol=none",
                "next_action": "Keep optional AI scope and promotion backlog deferred.",
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


def _blocked_product_quality_gate_verification() -> dict:
    return {
        "summary": {
            "status": "blocked_product_quality_gate_verification",
            "quality_gate_ready": False,
            "source_contract_status": "blocked_product_operational_quality_contract",
            "check_count": 4,
            "pass_count": 3,
            "source_contract_check_count": 6,
            "source_contract_pass_count": 5,
            "blocker_count": 1,
            "execution_enabled": False,
            "external_state_mutated": False,
        }
    }


def _ready_product_quality_gate_verification() -> dict:
    return {
        "summary": {
            "status": "product_quality_gate_verified",
            "quality_gate_ready": True,
            "source_contract_status": "product_operational_quality_contract_ready",
            "check_count": 4,
            "pass_count": 4,
            "source_contract_check_count": 6,
            "source_contract_pass_count": 6,
            "blocker_count": 0,
            "execution_enabled": False,
            "external_state_mutated": False,
        }
    }


def _ready_product_pose_sampling_readiness() -> dict:
    return {
        "summary": {
            "status": "product_pose_sampling_readiness_ready",
            "pose_sampling_readiness_ready": True,
            "pose_generation_contract_ready": True,
            "pocket_detection_ready": True,
            "multi_start_pose_ensemble_ready": True,
            "pose_centroid_pocket_bound_ready": True,
            "pose_rmsd_diversity_surface_ready": True,
            "bounded_cross_docking_induced_fit_guard_ready": True,
            "pose_claim_boundary_guard_ready": True,
            "check_count": 6,
            "pass_count": 6,
            "blocker_count": 0,
            "requested_pose_start_count": 6,
            "pose_count": 6,
            "cluster_count": 6,
            "cross_docking_pose_count": 4,
            "pocket_method": "ligand_guided",
            "claim_grade_pose_accuracy_ready": False,
            "claim_grade_induced_fit_ready": False,
            "claim_grade_cross_docking_ready": False,
            "docking_results_emitted": False,
            "execution_enabled": False,
            "external_state_mutated": False,
            "next_required_step": (
                "Keep pose accuracy, induced-fit, and cross-target claims blocked until public pose benchmarks clear."
            ),
        }
    }


def _blocked_product_pose_sampling_readiness() -> dict:
    packet = _ready_product_pose_sampling_readiness()
    packet["summary"].update(
        {
            "status": "blocked_product_pose_sampling_readiness",
            "pose_sampling_readiness_ready": False,
            "pose_count": 4,
            "cluster_count": 1,
            "pass_count": 4,
            "blocker_count": 2,
        }
    )
    return packet


def _ready_product_ledger_privacy_scan() -> dict:
    return {
        "summary": {
            "status": "product_ledger_privacy_scan_ready",
            "ledger_privacy_scan_ready": True,
            "scan_file_count": 285,
            "pass_count": 285,
            "scan_globs": [f"runs/privacy-scan-target-{index}.json" for index in range(24)],
            "blocker_count": 0,
            "leak_count": 0,
            "invalid_json_count": 0,
            "blocked_artifact_paths": [],
            "invalid_json_paths": [],
            "execution_enabled": False,
            "external_state_mutated": False,
            "next_required_step": (
                "Ledger privacy scan is ready; keep this artifact in the release source-of-truth gate."
            ),
        }
    }


def _blocked_product_ledger_privacy_scan() -> dict:
    packet = _ready_product_ledger_privacy_scan()
    packet["summary"].update(
        {
            "status": "blocked_product_ledger_privacy_scan",
            "ledger_privacy_scan_ready": False,
            "pass_count": 284,
            "blocker_count": 1,
            "leak_count": 1,
            "blocked_artifact_paths": ["runs/goal_operator_action_board_current.json"],
        }
    )
    return packet


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
            "release_blocker_blocked_row_counts": {
                "R8_full_scope_claim_closure": 6,
                "R9_engine_refinement_claim_promotion": 6,
            },
            "release_blocker_first_blocked_evidence_row_ids": {
                "R8_full_scope_claim_closure": "direct_binding_evidence_missing",
                "R9_engine_refinement_claim_promotion": "public_benchmark_gate_not_ready",
            },
            "release_blocker_receipt_csvs": {
                "R8_full_scope_claim_closure": "config/product_scope_breadth_evidence_receipt_current.csv",
                "R9_engine_refinement_claim_promotion": (
                    "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
                ),
            },
            "release_blocker_approval_tokens_required": {
                "R8_full_scope_claim_closure": "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT",
                "R9_engine_refinement_claim_promotion": (
                    "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT"
                ),
            },
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


def _blocked_product_scope_receipt() -> dict:
    return {
        "summary": {
            "status": "blocked_product_scope_breadth_evidence_receipt",
            "full_scope_evidence_receipt_ready": False,
            "receipt_row_count": 6,
            "pass_row_count": 0,
            "blocked_row_count": 6,
            "blocker_count": 1,
            "evidence_status_contract_present_count": 6,
            "expected_true_fields_present_count": 6,
            "expected_quality_true_field_count": 4,
            "expected_int_min_field_count": 4,
            "expected_false_field_count": 4,
            "provenance_kind_accepted_count": 6,
            "external_state_mutated_false_count": 6,
            "operator_attestation_accepted_count": 6,
            "operator_review_surface_ready_count": 6,
            "operator_review_surface_blocked_count": 0,
            "receipt_manual_field_pending_count": 36,
            "receipt_evidence_artifact_pending_count": 6,
            "receipt_claim_ready_pending_count": 6,
            "receipt_reviewer_pending_count": 6,
            "receipt_reviewed_at_utc_pending_count": 6,
            "receipt_license_ok_pending_count": 6,
            "receipt_approval_token_pending_count": 6,
            "required_scope_blocker_count": 6,
            "first_blocked_scope_blocker_id": "direct_binding_evidence_missing",
            "first_blocked_evidence_artifact": "OPERATOR_FILL_LOCAL_EVIDENCE_JSON",
            "first_blocked_expected_evidence_status": (
                "product_scope_transporter_direct_binding_evidence_ready"
            ),
            "first_blocked_observed_evidence_status": "missing",
            "first_blocked_row_blockers": [
                "operator_placeholders_unfilled",
                "evidence_artifact_not_found",
                "claim_ready_not_true",
            ],
            "most_common_row_blocker": "operator_placeholders_unfilled",
            "approval_token_required": "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT",
            "receipt_csv": "config/product_scope_breadth_evidence_receipt_current.csv",
            "external_state_mutated": False,
        }
    }


def _blocked_engine_refinement_receipt() -> dict:
    return {
        "summary": {
            "status": "blocked_engine_refinement_claim_evidence_receipt",
            "claim_promotion_evidence_receipt_ready": False,
            "receipt_row_count": 6,
            "pass_row_count": 0,
            "blocked_row_count": 6,
            "blocker_count": 1,
            "required_blocker_count": 6,
            "first_blocked_blocker_id": "public_benchmark_gate_not_ready",
            "first_blocked_evidence_artifact": "OPERATOR_FILL_LOCAL_EVIDENCE_JSON",
            "first_blocked_expected_evidence_status": "refine_tier_public_benchmark_ready",
            "first_blocked_observed_evidence_status": "missing",
            "first_blocked_row_blockers": [
                "operator_placeholders_unfilled",
                "evidence_artifact_not_found",
                "claim_ready_not_true",
            ],
            "most_common_row_blocker": "operator_placeholders_unfilled",
            "approval_token_required": "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT",
            "receipt_csv": "config/engine_refinement_claim_promotion_evidence_receipt_current.csv",
            "external_state_mutated": False,
        }
    }


def _blocked_engine_refinement_priority_packet() -> dict:
    return {
        "summary": {
            "status": "blocked_engine_refinement_claim_evidence_priority_packet",
            "priority_packet_ready": True,
            "priority_item_count": 6,
            "operator_input_required_count": 6,
            "blocked_priority_item_count": 6,
            "required_blocker_count": 6,
            "missing_required_blocker_count": 0,
            "blocker_count": 1,
            "claim_evidence_receipt_status": "blocked_engine_refinement_claim_evidence_receipt",
            "claim_evidence_receipt_ready": False,
            "claim_promotion_allowed": False,
            "public_benchmark_status": "blocked_refine_tier_public_benchmark_readiness",
            "public_benchmark_gate_ready": False,
            "public_benchmark_work_order_present": True,
            "public_benchmark_work_order_row_count": 8,
            "public_benchmark_work_order_apply_status": (
                "blocked_refine_tier_public_benchmark_work_order_apply"
            ),
            "public_benchmark_work_order_apply_ready": False,
            "public_benchmark_work_order_apply_blocked_row_count": 8,
            "top_blocker_id": "public_benchmark_gate_not_ready",
            "top_priority_bucket": "public_benchmark_work_order_apply_required",
            "top_required_input": (
                "config/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.csv"
            ),
            "top_acceptance_artifact": "runs/refine_tier_public_benchmark_readiness_current.json",
            "top_verification_command": (
                "python3 tools/product/build_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt.py; "
                "python3 tools/product/materialize_refine_tier_public_benchmark_statistical_support_metric_candidates.py; "
                "python3 tools/product/build_refine_tier_public_benchmark_claim_grade_gap_audit.py; "
                "python3 tools/product/build_engine_refinement_claim_evidence_priority_packet.py"
            ),
            "top_next_operator_step": (
                "Fill and validate 8 public benchmark work-order rows; current apply blocked rows=8."
            ),
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_csv": (
                "config/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.csv"
            ),
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_approval_token_required": (
                "APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS"
            ),
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_status": (
                "blocked_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt"
            ),
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready": False,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_row_count": 51,
            "approval_token_required": "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT",
            "approval_token_count": 1,
            "external_state_mutated": False,
        }
    }


def _refine_tier_public_benchmark_fail_closed() -> dict:
    return {
        "summary": {
            "status": "blocked_refine_tier_public_benchmark_readiness",
            "input_csv": "config/refine_tier_public_benchmark_intake_current.csv",
            "input_csv_present": True,
            "claim_grade_public_benchmark_ready": False,
            "benchmark_metric_surface_ready": False,
            "row_count": 0,
            "valid_row_count": 0,
            "pose_metric_row_count": 0,
            "pose_metric_pass_count": 0,
            "free_energy_pair_count": 0,
            "blocker_count": 6,
            "min_total_rows_required": 8,
            "min_pose_rows_required": 5,
            "min_free_energy_pairs_required": 5,
            "operator_work_order_ready": True,
            "work_order_csv": "runs/refine_tier_public_benchmark_work_order_current.csv",
            "work_order_row_count": 8,
            "write_intake_approval_token_required": (
                "APPROVE_REFINE_TIER_PUBLIC_BENCHMARK_INTAKE"
            ),
            "external_state_mutated": False,
            "next_required_step": "Fill the work-order CSV from reviewed public provenance.",
        }
    }


def _refine_tier_public_benchmark_work_order_apply_fail_closed() -> dict:
    return {
        "summary": {
            "status": "blocked_refine_tier_public_benchmark_work_order_apply",
            "aggregate_readiness_required": True,
            "apply_ready": False,
            "work_order_csv": "runs/refine_tier_public_benchmark_work_order_current.csv",
            "work_order_csv_present": True,
            "work_order_row_count": 8,
            "blocked_row_count": 8,
            "valid_intake_row_count": 0,
            "blocker_count": 1,
            "duplicate_benchmark_id_count": 0,
            "receptor_coordinate_validation_required": True,
            "receptor_coordinate_validation_csv_present": True,
            "receptor_coordinate_validation_pass_row_count": 8,
            "receptor_coordinate_validation_blocked_row_count": 0,
            "receptor_coordinate_validation_missing_row_count": 0,
            "metric_evidence_required": True,
            "metric_evidence_csv_present": True,
            "metric_evidence_pass_row_count": 0,
            "metric_evidence_blocked_row_count": 8,
            "metric_evidence_missing_row_count": 0,
            "candidate_intake_written": False,
            "candidate_readiness_checked": False,
            "candidate_claim_grade_public_benchmark_ready": False,
            "intake_written": False,
            "write_intake_requested": False,
            "approval_token_present": False,
            "approval_token_accepted": False,
            "target_intake_csv": "config/refine_tier_public_benchmark_intake_current.csv",
            "external_state_mutated": False,
            "next_required_step": "Fill or repair blocked work-order rows.",
        }
    }


def _full_commercial_bottleneck_briefing() -> dict:
    return {
        "summary": {
            "status": "goal_bottleneck_briefing_ready",
            "completion_audit_release_blocker_bottleneck_count": 2,
            "full_commercial_evidence_receipt_entry_count": 2,
            "full_commercial_evidence_receipt_operator_input_required_count": 2,
            "full_commercial_evidence_receipt_current_action_required_count": 2,
            "full_commercial_evidence_receipt_template_required_count": 2,
            "full_commercial_evidence_receipt_template_present_count": 2,
            "full_commercial_evidence_receipt_approval_token_count": 2,
            "full_commercial_evidence_receipt_source_gate_statuses": (
                "product_scope_breadth_evidence_receipt=blocked_product_scope_breadth_evidence_receipt;"
                "engine_refinement_claim_evidence_receipt=blocked_engine_refinement_claim_evidence_receipt"
            ),
            "full_commercial_evidence_receipt_required_inputs": (
                "config/product_scope_breadth_evidence_receipt_current.csv;"
                "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
            ),
            "full_commercial_evidence_receipt_approval_tokens": (
                "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT;"
                "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT"
            ),
            "product_scope_breadth_evidence_priority_top_item_id": "AQP1.core_binder_01",
            "product_scope_breadth_evidence_priority_top_domain": "transporter",
            "product_scope_breadth_evidence_priority_top_bucket": (
                "local_crosscheck_review_present_but_exact_quant_required"
            ),
            "product_scope_breadth_evidence_priority_top_required_evidence_type": (
                "exact_transporter_target_pair_quantitative_binder_kcal"
            ),
            "product_scope_breadth_evidence_priority_top_review_template_artifact": (
                "runs/transporter_manual_review_intake_template_current.json"
            ),
            "product_scope_breadth_evidence_priority_top_apply_gate_artifact": (
                "runs/transporter_binder_promotion_gate_current.json"
            ),
            "product_scope_breadth_evidence_priority_top_next_step": (
                "Review local crosscheck files, capture exact evidence if present."
            ),
            "product_scope_breadth_evidence_priority_receipt_csv": (
                "config/product_scope_breadth_evidence_receipt_current.csv"
            ),
            "product_scope_breadth_evidence_priority_receipt_approval_token_required": (
                "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT"
            ),
            "product_scope_breadth_evidence_priority_receipt_status": (
                "blocked_product_scope_breadth_evidence_receipt"
            ),
            "product_scope_breadth_evidence_priority_receipt_blocked_row_count": 6,
            "engine_refinement_priority_action_id": (
                "product_engine_refinement:resolve_refine_tier_claim_promotion_blocker"
            ),
            "engine_refinement_priority_top_item_id": "public_benchmark_gate_not_ready",
            "engine_refinement_priority_top_blocker_id": "public_benchmark_gate_not_ready",
            "engine_refinement_priority_top_bucket": "public_benchmark_work_order_apply_required",
            "engine_refinement_priority_top_required_input": (
                "config/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.csv"
            ),
            "engine_refinement_priority_top_acceptance_artifact": (
                "runs/refine_tier_public_benchmark_readiness_current.json"
            ),
            "engine_refinement_priority_top_verification_command": (
                "python3 tools/product/build_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt.py; "
                "python3 tools/product/materialize_refine_tier_public_benchmark_statistical_support_metric_candidates.py; "
                "python3 tools/product/build_engine_refinement_claim_evidence_priority_packet.py"
            ),
            "engine_refinement_priority_top_next_operator_step": (
                "Fill and review the 51 DockQ/lDDT-PLI/internal DeltaG metric source payloads."
            ),
            "engine_refinement_priority_metric_source_payload_receipt_csv": (
                "config/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.csv"
            ),
            "engine_refinement_priority_metric_source_payload_receipt_approval_token_required": (
                "APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS"
            ),
            "engine_refinement_priority_metric_source_payload_receipt_status": (
                "blocked_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt"
            ),
            "engine_refinement_priority_metric_source_payload_receipt_blocked_row_count": 51,
            "engine_refinement_priority_claim_evidence_receipt_csv": (
                "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
            ),
            "engine_refinement_priority_claim_evidence_receipt_approval_token_required": (
                "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT"
            ),
            "engine_refinement_priority_claim_evidence_receipt_status": (
                "blocked_engine_refinement_claim_evidence_receipt"
            ),
            "engine_refinement_priority_claim_evidence_receipt_blocked_row_count": 6,
            "production_ai_registry_promotion_priority_source_json": (
                "runs/production_ai_registry_promotion_priority_packet_current.json"
            ),
            "production_ai_registry_promotion_priority_status": (
                "blocked_production_ai_registry_promotion_priority_packet"
            ),
            "production_ai_registry_promotion_priority_packet_ready": True,
            "production_ai_registry_promotion_priority_registry_promotion_ready": False,
            "production_ai_registry_promotion_priority_operator_input_required_count": 3,
            "production_ai_registry_promotion_priority_blocked_priority_item_count": 3,
            "production_ai_registry_promotion_priority_missing_gate_count": 3,
            "production_ai_registry_promotion_priority_missing_gate_ids": [
                "default_residual_mode_guarded",
                "production_promotion_allowed",
                "customer_facing_mutation_flags",
            ],
            "production_ai_registry_promotion_priority_top_gate_id": (
                "default_residual_mode_guarded"
            ),
            "production_ai_registry_promotion_priority_top_priority_bucket": (
                "guarded_residual_mode_selection_required"
            ),
            "production_ai_registry_promotion_priority_top_required_input": (
                "Set the guarded default residual mode in the production AI registry promotion "
                "operator receipt after confirming the preflight-ready checkpoint count."
            ),
            "production_ai_registry_promotion_priority_top_acceptance_artifact": (
                "runs/residual_model_registry_current.json"
            ),
            "production_ai_registry_promotion_priority_top_verification_command": (
                "python3 tools/build_residual_model_registry.py; "
                "python3 tools/build_product_production_ai_checkpoint_readiness.py"
            ),
            "production_ai_registry_promotion_priority_top_next_operator_step": (
                "Fill the guarded promotion operator receipt with a reviewed default residual mode, "
                "approval token, reviewer, and validation-chain review, then rerun registry readiness."
            ),
            "production_ai_registry_promotion_priority_model_promoted": False,
            "production_ai_registry_promotion_priority_customer_facing_mutation_enabled": False,
            "production_ai_registry_promotion_priority_external_state_mutated": False,
            "execution_enabled": False,
            "external_state_mutated": False,
        }
    }


def _production_ai_registry_promotion_priority_packet() -> dict:
    missing_gate_ids = [
        "default_residual_mode_guarded",
        "production_promotion_allowed",
        "customer_facing_mutation_flags",
    ]
    return {
        "summary": {
            "status": "blocked_production_ai_registry_promotion_priority_packet",
            "priority_packet_ready": True,
            "registry_promotion_ready": False,
            "required_gate_count": 4,
            "priority_item_count": 4,
            "operator_input_required_count": 3,
            "blocked_priority_item_count": 3,
            "registry_promotion_missing_gate_count": 3,
            "registry_promotion_missing_gate_ids": missing_gate_ids,
            "observed_checkpoint_registry_promotion_missing_gate_ids": [
                "production_promotion_allowed",
                "customer_facing_mutation_flags",
                "default_residual_mode_guarded",
            ],
            "top_gate_id": "default_residual_mode_guarded",
            "top_priority_bucket": "guarded_residual_mode_selection_required",
            "top_required_input": (
                "Set the guarded default residual mode in the production AI registry promotion "
                "operator receipt after confirming the preflight-ready checkpoint count."
            ),
            "top_acceptance_artifact": "runs/residual_model_registry_current.json",
            "top_verification_command": (
                "python3 tools/build_residual_model_registry.py; "
                "python3 tools/build_product_production_ai_checkpoint_readiness.py"
            ),
            "top_next_operator_step": (
                "Fill the guarded promotion operator receipt with a reviewed default residual mode, "
                "approval token, reviewer, and validation-chain review, then rerun registry readiness."
            ),
            "approval_token_required": "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION",
            "approval_token_count": 1,
            "operator_receipt_artifact": "runs/production_ai_registry_promotion_operator_receipt_current.json",
            "operator_receipt_artifact_present": True,
            "operator_receipt_csv": "config/production_ai_registry_promotion_operator_receipt_current.csv",
            "operator_receipt_csv_present": True,
            "operator_receipt_status": "blocked_production_ai_registry_promotion_operator_receipt",
            "operator_receipt_ready": False,
            "residual_registry_artifact": "runs/residual_model_registry_current.json",
            "residual_registry_artifact_present": True,
            "checkpoint_readiness_artifact": "runs/product_production_ai_checkpoint_readiness_current.json",
            "checkpoint_readiness_artifact_present": True,
            "promotion_workbench_artifact": "runs/product_production_ai_promotion_workbench_current.json",
            "promotion_workbench_artifact_present": True,
            "observed_registry_trained_model_checkpoint_count": 1,
            "observed_registry_default_residual_mode": "shadow",
            "observed_registry_production_promotion_allowed": False,
            "observed_registry_customer_facing_mutation_flags_ready": False,
            "observed_checkpoint_registry_promotion_currently_satisfied": False,
            "model_promoted": False,
            "customer_facing_mutation_enabled": False,
            "registry_edited_by_this_tool": False,
            "checkpoint_created_by_this_tool": False,
            "execution_enabled": False,
            "external_state_mutated": False,
        }
    }


def _production_ai_checkpoint_readiness() -> dict:
    missing_gate_ids = [
        "production_promotion_allowed",
        "customer_facing_mutation_flags",
        "default_residual_mode_guarded",
    ]
    return {
        "summary": {
            "status": "blocked_product_production_ai_checkpoint_readiness",
            "product_model_layer_ready": True,
            "production_gpu_execution_environment_ready": True,
            "force_gpu_worker_return_receipt_ready": True,
            "delta_force_derivation_validation_ready": True,
            "selected_sidecar_ready": True,
            "checkpoint_preflight_ready": True,
            "production_training_data_ready": True,
            "production_output_heads_complete": True,
            "production_inference_acceptance_matrix_ready": True,
            "check_count": 8,
            "pass_check_count": 7,
            "fail_check_count": 1,
            "production_inference_acceptance_stage_count": 8,
            "production_inference_acceptance_ready_stage_count": 7,
            "production_inference_acceptance_blocked_stage_count": 1,
            "production_inference_acceptance_blocked_stage_ids": [
                "registry_guarded_promotion_acceptance"
            ],
            "first_failed_check_id": "registry_customer_facing_promotion_allowed",
            "first_failed_source_artifact": "runs/residual_model_registry_current.json",
            "production_inference_actionable_blocker_stage_id": (
                "registry_guarded_promotion_acceptance"
            ),
            "production_inference_actionable_blocker_check_id": (
                "registry_customer_facing_promotion_allowed"
            ),
            "production_inference_actionable_blocker_artifact": (
                "runs/residual_model_registry_current.json"
            ),
            "registry_promotion_upstream_acceptance_ready": True,
            "registry_promotion_currently_satisfied": False,
            "registry_promotion_missing_gate_count": 3,
            "registry_promotion_missing_gate_ids": missing_gate_ids,
            "candidate_checkpoint_count": 1,
            "ready_checkpoint_count": 1,
            "trained_model_checkpoint_count": 1,
            "default_residual_mode": "shadow",
            "production_ai_checkpoint_ready": False,
            "production_ai_inference_subject_active": False,
            "production_promotion_allowed": False,
            "customer_facing_auto_correction_allowed": False,
            "customer_facing_score_mutation_allowed": False,
            "customer_facing_ranking_mutation_allowed": False,
            "model_promoted": False,
            "docking_results_emitted": False,
            "execution_enabled": False,
            "external_state_mutated": False,
        }
    }


def _production_ai_promotion_workbench() -> dict:
    missing_gate_ids = [
        "production_promotion_allowed",
        "customer_facing_mutation_flags",
        "default_residual_mode_guarded",
    ]
    return {
        "summary": {
            "status": "blocked_product_production_ai_promotion_workbench",
            "promotion_workbench_ready": True,
            "checkpoint_readiness_artifact_path": (
                "runs/product_production_ai_checkpoint_readiness_current.json"
            ),
            "post_return_promotion_ladder_stage_count": 10,
            "post_return_promotion_ladder_ready_stage_count": 7,
            "post_return_promotion_ladder_blocked_stage_count": 3,
            "blocked_stage_ids": [
                "residual_model_registry",
                "product_ai_architecture_gap_closure",
                "product_goal_completion_audit",
            ],
            "first_blocked_stage_id": "residual_model_registry",
            "first_blocked_stage_artifact": "runs/residual_model_registry_current.json",
            "first_blocked_stage_ready_key": "production_promotion_allowed",
            "registry_promotion_upstream_acceptance_ready": True,
            "registry_promotion_currently_satisfied": False,
            "registry_promotion_missing_gate_count": 3,
            "registry_promotion_missing_gate_ids": missing_gate_ids,
            "candidate_checkpoint_count": 1,
            "ready_checkpoint_count": 1,
            "trained_model_checkpoint_count": 1,
            "default_residual_mode": "shadow",
            "production_ai_promotion_ready": False,
            "production_ai_checkpoint_ready": False,
            "production_ai_inference_subject_active": False,
            "production_promotion_allowed": False,
            "model_promoted": False,
            "docking_results_emitted": False,
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


def _complete_master_gap_rollup() -> dict:
    return {
        "rows": [
            {
                "gap_id": "COMMERCIAL",
                "status": "closed",
                "rollup_status": "commercial_gap_closure_complete",
                "evidence": "runs/commercial_gap_closure_status_current.json",
                "release_blocker": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            },
            {
                "gap_id": "PRODUCT-AI",
                "status": "closed",
                "rollup_status": "product_ai_architecture_gap_closure_complete",
                "evidence": "runs/product_ai_architecture_gap_closure_current.json",
                "release_blocker": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            },
            {
                "gap_id": "DATA-SCIENCE",
                "status": "closed",
                "rollup_status": "data_science_expansion_gap_closure_complete",
                "evidence": "runs/data_science_expansion_gap_closure_current.json",
                "release_blocker": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            },
            {
                "gap_id": "INFRA",
                "status": "closed",
                "rollup_status": "product_infrastructure_gap_closure_complete",
                "evidence": "runs/product_infrastructure_gap_closure_current.json",
                "release_blocker": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            },
            {
                "gap_id": "SCI-CLAIM",
                "status": "closed",
                "rollup_status": "science_claim_promotion_gap_closure_complete",
                "evidence": "runs/science_claim_promotion_gap_closure_current.json",
                "release_blocker": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            },
            {
                "gap_id": "DEPLOY-OPS",
                "status": "closed",
                "rollup_status": "deploy_ops_legal_gap_closure_complete",
                "evidence": "runs/deploy_ops_legal_gap_closure_current.json",
                "release_blocker": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            },
            {
                "gap_id": "STORAGE",
                "status": "closed",
                "rollup_status": "storage_cleanup_gap_closure_complete",
                "evidence": "runs/storage_cleanup_gap_closure_current.json",
                "release_blocker": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            },
            {
                "gap_id": "TOOLS",
                "status": "closed",
                "rollup_status": "tools_refactor_gap_closure_complete",
                "evidence": "runs/tools_refactor_gap_closure_current.json",
                "release_blocker": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            },
            {
                "gap_id": "API-RUNNER",
                "status": "closed",
                "rollup_status": "api_runner_profile_promotion_ready",
                "evidence": "runs/api_runner_profile_promotion_readiness_current.json",
                "release_blocker": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            },
        ],
        "summary": {
            "status": "master_gap_closure_rollup_complete",
            "all_gaps_closed": True,
            "claim_promotion_allowed": False,
            "gap_count": 9,
            "closed_gap_count": 9,
            "closed_gap_ids": [
                "COMMERCIAL",
                "PRODUCT-AI",
                "DATA-SCIENCE",
                "INFRA",
                "SCI-CLAIM",
                "DEPLOY-OPS",
                "STORAGE",
                "TOOLS",
                "API-RUNNER",
            ],
            "open_gap_count": 0,
            "open_gap_ids": [],
            "current_primary_open_gap_id": "none",
            "execution_enabled": False,
            "external_state_mutated": False,
        }
    }


def _complete_science_claim_gap() -> dict:
    return {
        "rows": [
            {
                "gap_id": "SCI-GPCR",
                "area": "GPCR broad family",
                "status": "closed",
                "claim_promotion_status": "boundary_ready_comparison_only",
                "claim_promotion_allowed": False,
                "evidence": "runs/gpcr_conditional_prior_promotion_gate_current.json",
                "next_action": (
                    "Keep broad-family claim promotion locked until target-held-out broad-scope "
                    "review and scorer/router promotion gates are approved."
                ),
                "release_blocker": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            },
            {
                "gap_id": "SCI-OPENMM",
                "area": "OpenMM restricted vs full physics",
                "status": "closed",
                "claim_promotion_status": "restricted_2bead_only",
                "claim_promotion_allowed": False,
                "evidence": (
                    "runs/wetlab_openmm_claim_promotion_boundary_current.json; "
                    "runs/accuracy_parity_scorecard_current.json"
                ),
                "next_action": (
                    "Maintain restricted 2-bead OpenMM lane; full all-atom/MM-GBSA/FEP+ "
                    "remain unimplemented."
                ),
                "release_blocker": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            },
            {
                "gap_id": "SCI-TRANS",
                "area": "Transporter AQP1/GLUT1",
                "status": "closed",
                "claim_promotion_status": "functional_surrogate_only",
                "claim_promotion_allowed": False,
                "evidence": "runs/transporter_claim_promotion_boundary_current.json",
                "release_blocker": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            },
            {
                "gap_id": "SCI-CA2-PXR",
                "area": "CA2/PXR packet replacement",
                "status": "closed",
                "claim_promotion_status": "review_only_until_workbook_applied",
                "claim_promotion_allowed": False,
                "evidence": (
                    "runs/ca2_packet_replacement_readiness_current.json; "
                    "runs/pxr_packet_replacement_readiness_current.json"
                ),
                "release_blocker": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            },
            {
                "gap_id": "SCI-WETLAB",
                "area": "Wetlab prospective translation",
                "status": "closed",
                "claim_promotion_status": "simulation_packet_only",
                "claim_promotion_allowed": False,
                "evidence": "runs/wetlab_openmm_claim_promotion_boundary_current.json",
                "release_blocker": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            },
        ],
        "summary": {
            "status": "science_claim_promotion_gap_closure_complete",
            "all_gaps_closed": True,
            "claim_promotion_allowed": False,
            "gap_count": 5,
            "closed_gap_count": 5,
            "closed_gap_ids": [
                "SCI-GPCR",
                "SCI-TRANS",
                "SCI-CA2-PXR",
                "SCI-WETLAB",
                "SCI-OPENMM",
            ],
            "open_gap_count": 0,
            "open_gap_ids": [],
            "current_primary_open_gap_id": "none",
            "current_next_action": "All science claim promotion boundary gaps are closed.",
            "execution_enabled": False,
            "external_state_mutated": False,
        },
    }


def _restricted_accuracy_parity_scorecard() -> dict:
    return {
        "claim_boundary": {
            "commercial_tool_accuracy_parity_allowed": False,
            "fake_pass_allowed": False,
            "scorecard_rows_must_map_to_frozen_artifacts": True,
            "threshold_relaxation_allowed": False,
        },
        "rows": [
            {
                "axis": "ligand_ranking",
                "status": "restricted_pass",
                "claim_scope": "broad GPCR ligand ranking/docking parity",
                "comparator": "Schrodinger Glide/FEP+ class ranking",
                "claim_promotion_allowed": False,
                "commercial_parity_claim_allowed": False,
                "blockers": [
                    "broad_gpcr_claim_not_allowed",
                ],
                "metrics": {
                    "ranking_pr_auc": 0.871853,
                    "ranking_pr_auc_ci_low": 0.761168,
                    "ranking_topk_hit_rate": 1.0,
                    "positive_count": 34,
                    "ranking_score_col_used": (
                        "binding_score_composite_v7_coverage_v2_crossfit_rank_rescue_shadow"
                    ),
                    "core_claim_safe": False,
                },
                "thresholds": {
                    "ranking_pr_auc_min": 0.55,
                    "ranking_pr_auc_ci_low_min": 0.45,
                    "ranking_topk_hit_rate_min": 0.5,
                    "requires_pose_supported_decoy_resistance": True,
                },
                "next_required_step": (
                    "Rank-rescue metrics and the GPCR conditional-prior/OPRM1 boundary are green "
                    "under claim lock; keep broad GPCR/Schrodinger-class promotion locked until "
                    "target-held-out broad-scope review and scorer/router promotion gates are approved."
                ),
            }
        ],
        "summary": {
            "status": "blocked_accuracy_parity",
            "row_count": 5,
            "pass_row_count": 4,
            "restricted_pass_row_count": 1,
            "blocked_row_count": 0,
            "missing_row_count": 0,
            "overall_commercial_tool_accuracy_parity_allowed": False,
            "schrodinger_class_claim_allowed": False,
            "openmm_class_claim_allowed": True,
            "current_broad_accuracy_parity_estimate_pct": "65-75",
            "current_broad_commercial_platform_estimate_pct": "45-55",
            "top_blockers": [
                "ligand_ranking:broad_gpcr_claim_not_allowed",
            ],
        },
    }


def _blocked_api_runner_profile_operator_receipt() -> dict:
    return {
        "summary": {
            "status": "blocked_api_runner_profile_promotion_operator_receipt",
            "readiness_status": "api_runner_profile_promotion_ready",
            "operator_receipt_ready": False,
            "profile_count": 4,
            "receipt_row_count": 4,
            "pass_row_count": 0,
            "blocked_row_count": 4,
            "blocker_count": 1,
            "blockers": ["blocked_receipt_rows_present"],
            "first_blocked_profile_id": "backmapping_scoring.example",
            "first_blocked_row_blocker": "operator_decision_missing",
            "first_blocked_row_blockers": [
                "operator_decision_missing",
                "approval_token_invalid",
                "input_contract_reviewed_not_true",
                "output_contract_reviewed_not_true",
            ],
            "most_common_row_blocker": "operator_decision_missing",
            "approval_token_required": "APPROVE_API_RUNNER_PROFILE_PROMOTION",
            "operator_template_csv": "runs/api_runner_profile_promotion_operator_template_current.csv",
            "next_required_step": (
                "Fill the operator receipt with approve/hold decisions and "
                "APPROVE_API_RUNNER_PROFILE_PROMOTION."
            ),
            "profile_enabled_by_this_tool": False,
            "runner_executed": False,
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


def _product_image_smoke_preflight(*, ready: bool = True) -> dict:
    return {
        "summary": {
            "status": "product_image_smoke_preflight_ready"
            if ready
            else "blocked_product_image_smoke_preflight",
            "clean_container_smoke_ready": ready,
            "receipt_status": "product_image_smoke_ready" if ready else "blocked_product_image_smoke",
            "receipt_mode": "rocm-runtime" if ready else "build",
            "container_runtime_receipt_ready": ready,
            "container_runtime_proof_schema_version": "rocm_container_runtime_proof_v1" if ready else "",
            "container_runtime_in_container": ready,
            "container_runtime_device_nodes_ready": ready,
            "container_runtime_torch_rocm_ready": ready,
            "container_runtime_torch_cuda_available": ready,
            "container_runtime_visible_device_count": 1 if ready else 0,
            "container_runtime_rust_hip_backend_enabled": ready,
            "product_runner_smoke_ready": ready,
            "receipt_simulate_missing_profile_http": 422 if ready else 0,
        }
    }


def test_goal_release_decision_gate_blocks_current_incomplete_goal() -> None:
    payload = mod.build_goal_release_decision_gate(
        product_pilot_packet=_blocked_product(),
        product_architecture_packet=_blocked_product_architecture(),
        product_commercial_independence_packet=_blocked_product_independence(),
        self_hosted_license_distribution_audit_packet=_self_hosted_license_distribution_audit(),
        third_party_license_review_gate_packet=_third_party_license_review_gate(),
        cameo_validation_packet=_blocked_cameo_validation(),
        cameo_capability_packet=_blocked_cameo_capability(),
        cameo_official_result_fetch_preflight_packet=(
            _blocked_cameo_official_result_fetch_preflight()
        ),
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
    assert summary["cameo_official_result_fetch_preflight_recorded"] is True
    assert summary["cameo_official_result_fetch_preflight_status"] == (
        "blocked_cameo_official_result_fetch_preflight"
    )
    assert summary["cameo_official_result_fetch_preflight_blocked_row_count"] == 1
    assert summary["cameo_official_result_fetch_preflight_blocker_count"] == 2
    assert summary["cameo_official_result_fetch_preflight_fetch_approval_token_required"] == (
        "APPROVE_CAMEO_OFFICIAL_RESULT_FETCH"
    )
    assert summary["cameo_official_result_fetch_preflight_network_request_opened"] is False
    assert summary["cameo_official_result_fetch_preflight_official_results_fetched"] is False
    fetch_row = next(
        row
        for row in payload["rows"]
        if row["check"] == "cameo_official_result_fetch_preflight_recorded"
    )
    assert fetch_row["status"] == "pass"
    assert fetch_row["release_blocker"] is False
    assert "fetch_approval_token_required=APPROVE_CAMEO_OFFICIAL_RESULT_FETCH" in fetch_row["observed"]
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
    assert summary["self_hosted_license_distribution_audit_recorded"] is True
    assert summary["self_hosted_license_distribution_audit_status"] == (
        "self_hosted_license_distribution_audit_recorded"
    )
    assert summary["self_hosted_license_distribution_audit_product_license_path"] == "LICENSE"
    assert (
        summary["self_hosted_license_distribution_audit_product_license_hash_matches_approved_source"]
        is True
    )
    assert summary["self_hosted_license_distribution_audit_spdx_license_id"] == (
        "ProprietaryRef-Betelgeuze"
    )
    assert summary["self_hosted_license_distribution_audit_hard_blocker_count"] == 0
    assert summary["self_hosted_license_distribution_audit_operator_review_item_count"] == 1
    assert summary["self_hosted_license_distribution_audit_legal_advice_provided"] is False
    assert summary["self_hosted_license_distribution_audit_third_party_dual_license_assets"] == "jszip"
    assert summary["third_party_license_review_gate_recorded"] is True
    assert summary["third_party_license_review_gate_status"] == "third_party_license_review_gate_ready"
    assert summary["third_party_license_review_gate_approved_assets"] == "jszip"
    assert summary["third_party_license_review_gate_expected_review_asset_count"] == 1
    assert summary["third_party_license_review_gate_blocker_count"] == 0
    assert summary["third_party_license_review_gate_legal_advice_provided"] is False
    assert summary["third_party_license_review_gate_asset_modified"] is False
    assert summary["third_party_license_review_gate_approval_token_required"] == (
        "APPROVE_THIRD_PARTY_LICENSE_REVIEW"
    )
    license_audit_row = next(
        row
        for row in payload["rows"]
        if row["check"] == "self_hosted_license_distribution_audit_recorded"
    )
    third_party_license_row = next(
        row for row in payload["rows"] if row["check"] == "third_party_license_review_gate_recorded"
    )
    assert license_audit_row["status"] == "pass"
    assert license_audit_row["release_blocker"] is False
    assert "third_party_dual_license_assets=jszip" in license_audit_row["observed"]
    assert third_party_license_row["status"] == "pass"
    assert third_party_license_row["release_blocker"] is False
    assert "approved_assets=jszip" in third_party_license_row["observed"]
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
        product_quality_gate_verification_packet=_ready_product_quality_gate_verification(),
    )

    summary = payload["summary"]
    assert summary["status"] == "goal_release_ready"
    assert summary["release_allowed"] is True
    assert summary["product_release_source_of_truth_ready"] is True
    assert summary["product_quality_gate_verification_gate_present"] is True
    assert summary["product_quality_gate_verification_status"] == "product_quality_gate_verified"
    assert summary["product_quality_gate_verification_recorded"] is True
    assert summary["product_quality_gate_verification_ready"] is True
    assert summary["product_quality_gate_verification_source_contract_status"] == (
        "product_operational_quality_contract_ready"
    )
    assert summary["product_quality_gate_verification_check_count"] == 4
    assert summary["product_quality_gate_verification_pass_count"] == 4
    assert summary["product_quality_gate_verification_blocker_count"] == 0
    assert summary["product_quality_gate_verification_execution_enabled"] is False
    assert summary["product_quality_gate_verification_external_state_mutated"] is False
    assert next(row for row in payload["rows"] if row["check"] == "product_release_source_of_truth_ready")[
        "status"
    ] == "pass"
    quality_row = next(
        row for row in payload["rows"] if row["check"] == "product_quality_gate_verification_recorded"
    )
    assert quality_row["status"] == "pass"
    assert quality_row["release_blocker"] is False
    assert "source_contract_status=product_operational_quality_contract_ready" in quality_row["observed"]


def test_goal_release_decision_gate_blocks_failed_quality_gate_verification() -> None:
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
        product_quality_gate_verification_packet=_blocked_product_quality_gate_verification(),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_goal_release_decision"
    assert summary["release_allowed"] is False
    assert summary["product_quality_gate_verification_recorded"] is False
    assert summary["product_quality_gate_verification_blocker_count"] == 1
    assert "product quality gate verification receipt" in summary["next_required_step"]
    quality_row = next(
        row for row in payload["rows"] if row["check"] == "product_quality_gate_verification_recorded"
    )
    assert quality_row["status"] == "fail"
    assert quality_row["release_blocker"] is True
    assert "pass_count=3" in quality_row["observed"]


def test_goal_release_decision_gate_passes_ready_pose_sampling_readiness() -> None:
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
        product_quality_gate_verification_packet=_ready_product_quality_gate_verification(),
        product_pose_sampling_readiness_packet=_ready_product_pose_sampling_readiness(),
    )

    summary = payload["summary"]
    assert summary["status"] == "goal_release_ready"
    assert summary["product_pose_sampling_readiness_gate_present"] is True
    assert summary["product_pose_sampling_readiness_recorded"] is True
    assert summary["product_pose_sampling_readiness_ready"] is True
    assert summary["product_pose_sampling_readiness_pose_generation_contract_ready"] is True
    assert summary["product_pose_sampling_readiness_pose_count"] == 6
    assert summary["product_pose_sampling_readiness_cluster_count"] == 6
    assert summary["product_pose_sampling_readiness_cross_docking_pose_count"] == 4
    assert summary["product_pose_sampling_readiness_claim_grade_pose_accuracy_ready"] is False
    assert summary["product_pose_sampling_readiness_docking_results_emitted"] is False
    assert summary["product_pose_sampling_readiness_execution_enabled"] is False
    assert summary["product_pose_sampling_readiness_external_state_mutated"] is False
    pose_row = next(
        row for row in payload["rows"] if row["check"] == "product_pose_sampling_readiness_recorded"
    )
    assert pose_row["status"] == "pass"
    assert pose_row["release_blocker"] is False
    assert "pose_count=6" in pose_row["observed"]
    assert "claim_grade_pose_accuracy_ready=false" in pose_row["observed"]


def test_goal_release_decision_gate_blocks_failed_pose_sampling_readiness() -> None:
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
        product_quality_gate_verification_packet=_ready_product_quality_gate_verification(),
        product_pose_sampling_readiness_packet=_blocked_product_pose_sampling_readiness(),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_goal_release_decision"
    assert summary["release_allowed"] is False
    assert summary["product_pose_sampling_readiness_recorded"] is False
    assert summary["product_pose_sampling_readiness_pose_count"] == 4
    assert summary["product_pose_sampling_readiness_cluster_count"] == 1
    assert "product pose sampling readiness receipt" in summary["next_required_step"]
    pose_row = next(
        row for row in payload["rows"] if row["check"] == "product_pose_sampling_readiness_recorded"
    )
    assert pose_row["status"] == "fail"
    assert pose_row["release_blocker"] is True
    assert "pose_count=4" in pose_row["observed"]


def test_goal_release_decision_gate_passes_ready_ledger_privacy_scan() -> None:
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
        product_quality_gate_verification_packet=_ready_product_quality_gate_verification(),
        product_pose_sampling_readiness_packet=_ready_product_pose_sampling_readiness(),
        product_ledger_privacy_scan_packet=_ready_product_ledger_privacy_scan(),
    )

    summary = payload["summary"]
    assert summary["status"] == "goal_release_ready"
    assert summary["product_ledger_privacy_scan_gate_present"] is True
    assert summary["product_ledger_privacy_scan_recorded"] is True
    assert summary["product_ledger_privacy_scan_ready"] is True
    assert summary["product_ledger_privacy_scan_scan_file_count"] == 285
    assert summary["product_ledger_privacy_scan_scan_glob_count"] == 24
    assert summary["product_ledger_privacy_scan_pass_count"] == 285
    assert summary["product_ledger_privacy_scan_leak_count"] == 0
    assert summary["product_ledger_privacy_scan_invalid_json_count"] == 0
    assert summary["product_ledger_privacy_scan_execution_enabled"] is False
    assert summary["product_ledger_privacy_scan_external_state_mutated"] is False
    privacy_row = next(
        row for row in payload["rows"] if row["check"] == "product_ledger_privacy_scan_recorded"
    )
    assert privacy_row["status"] == "pass"
    assert privacy_row["release_blocker"] is False
    assert "scan_file_count=285" in privacy_row["observed"]
    assert "leak_count=0" in privacy_row["observed"]


def test_goal_release_decision_gate_blocks_failed_ledger_privacy_scan() -> None:
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
        product_quality_gate_verification_packet=_ready_product_quality_gate_verification(),
        product_pose_sampling_readiness_packet=_ready_product_pose_sampling_readiness(),
        product_ledger_privacy_scan_packet=_blocked_product_ledger_privacy_scan(),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_goal_release_decision"
    assert summary["release_allowed"] is False
    assert summary["product_ledger_privacy_scan_recorded"] is False
    assert summary["product_ledger_privacy_scan_pass_count"] == 284
    assert summary["product_ledger_privacy_scan_leak_count"] == 1
    assert summary["product_ledger_privacy_scan_blocked_artifact_path_count"] == 1
    assert "product ledger privacy scan receipt" in summary["next_required_step"]
    privacy_row = next(
        row for row in payload["rows"] if row["check"] == "product_ledger_privacy_scan_recorded"
    )
    assert privacy_row["status"] == "fail"
    assert privacy_row["release_blocker"] is True
    assert "leak_count=1" in privacy_row["observed"]


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
        goal_bottleneck_briefing_packet=_full_commercial_bottleneck_briefing(),
        production_ai_registry_promotion_priority_packet=(
            _production_ai_registry_promotion_priority_packet()
        ),
        product_production_ai_checkpoint_readiness_packet=_production_ai_checkpoint_readiness(),
        product_production_ai_promotion_workbench_packet=_production_ai_promotion_workbench(),
        product_release_source_of_truth_packet=_ready_source_of_truth(),
        product_scope_breadth_evidence_receipt_packet=_blocked_product_scope_receipt(),
        engine_refinement_claim_evidence_receipt_packet=_blocked_engine_refinement_receipt(),
        engine_refinement_claim_evidence_priority_packet=_blocked_engine_refinement_priority_packet(),
        refine_tier_public_benchmark_readiness_packet=(
            _refine_tier_public_benchmark_fail_closed()
        ),
        refine_tier_public_benchmark_work_order_apply_packet=(
            _refine_tier_public_benchmark_work_order_apply_fail_closed()
        ),
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
    assert summary["primary_full_commercial_release_blocker_requirement_id"] == (
        "R8_full_scope_claim_closure"
    )
    assert summary["primary_full_commercial_release_blocker_tier"] == "full_commercial_scope"
    assert summary["primary_full_commercial_release_blocker"] == "direct_binding_evidence_missing"
    assert summary["primary_full_commercial_release_blocker_blocked_row_count"] == 6
    assert summary["primary_full_commercial_release_blocker_first_blocked_evidence_row_id"] == (
        "direct_binding_evidence_missing"
    )
    assert summary["primary_full_commercial_release_blocker_receipt_csv"] == (
        "config/product_scope_breadth_evidence_receipt_current.csv"
    )
    assert summary["primary_full_commercial_release_blocker_approval_token_required"] == (
        "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT"
    )
    assert summary["primary_full_commercial_release_blocker_next_required_step"].startswith(
        "Fill the R8/R9 receipt CSVs"
    )
    assert summary["full_commercial_release_next_required_step"].startswith("Fill the R8/R9 receipt CSVs")
    assert summary["product_scope_breadth_evidence_priority_top_item_id"] == "AQP1.core_binder_01"
    assert summary["product_scope_breadth_evidence_priority_top_domain"] == "transporter"
    assert summary["product_scope_breadth_evidence_priority_top_bucket"] == (
        "local_crosscheck_review_present_but_exact_quant_required"
    )
    assert summary["product_scope_breadth_evidence_priority_top_required_evidence_type"] == (
        "exact_transporter_target_pair_quantitative_binder_kcal"
    )
    assert summary["product_scope_breadth_evidence_priority_top_review_template_artifact"] == (
        "runs/transporter_manual_review_intake_template_current.json"
    )
    assert summary["product_scope_breadth_evidence_priority_top_apply_gate_artifact"] == (
        "runs/transporter_binder_promotion_gate_current.json"
    )
    assert "Review local crosscheck files" in summary[
        "product_scope_breadth_evidence_priority_top_next_step"
    ]
    assert summary["product_scope_breadth_evidence_priority_receipt_csv"] == (
        "config/product_scope_breadth_evidence_receipt_current.csv"
    )
    assert summary["product_scope_breadth_evidence_priority_receipt_approval_token_required"] == (
        "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT"
    )
    assert summary["product_scope_breadth_evidence_priority_receipt_status"] == (
        "blocked_product_scope_breadth_evidence_receipt"
    )
    assert summary["product_scope_breadth_evidence_priority_receipt_blocked_row_count"] == 6
    assert summary["engine_refinement_priority_action_id"] == (
        "product_engine_refinement:resolve_refine_tier_claim_promotion_blocker"
    )
    assert summary["engine_refinement_priority_top_item_id"] == "public_benchmark_gate_not_ready"
    assert summary["engine_refinement_priority_top_blocker_id"] == "public_benchmark_gate_not_ready"
    assert summary["engine_refinement_priority_top_bucket"] == (
        "public_benchmark_work_order_apply_required"
    )
    assert summary["engine_refinement_priority_top_required_input"] == (
        "config/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.csv"
    )
    assert summary["engine_refinement_priority_top_acceptance_artifact"] == (
        "runs/refine_tier_public_benchmark_readiness_current.json"
    )
    assert "materialize_refine_tier_public_benchmark" in summary[
        "engine_refinement_priority_top_verification_command"
    ]
    assert "51 DockQ/lDDT-PLI/internal DeltaG" in summary[
        "engine_refinement_priority_top_next_operator_step"
    ]
    assert summary["engine_refinement_priority_receipt_action_id"] == (
        "product_engine_refinement:resolve_refine_tier_claim_promotion_blocker"
    )
    assert summary["engine_refinement_priority_metric_source_payload_receipt_csv"] == (
        "config/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.csv"
    )
    assert summary[
        "engine_refinement_priority_metric_source_payload_receipt_approval_token_required"
    ] == "APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS"
    assert summary[
        "engine_refinement_priority_metric_source_payload_receipt_status"
    ] == "blocked_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt"
    assert summary["engine_refinement_priority_metric_source_payload_receipt_blocked_row_count"] == 51
    assert summary["engine_refinement_priority_claim_evidence_receipt_csv"] == (
        "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
    )
    assert summary["engine_refinement_priority_claim_evidence_receipt_approval_token_required"] == (
        "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT"
    )
    assert summary["engine_refinement_priority_claim_evidence_receipt_status"] == (
        "blocked_engine_refinement_claim_evidence_receipt"
    )
    assert summary["engine_refinement_priority_claim_evidence_receipt_blocked_row_count"] == 6
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
    assert summary["product_full_commercial_blocker_evidence_matrix_r8_blocked_row_count"] == 6
    assert summary[
        "product_full_commercial_blocker_evidence_matrix_r8_first_blocked_evidence_row_id"
    ] == "direct_binding_evidence_missing"
    assert summary["product_full_commercial_blocker_evidence_matrix_r8_receipt_csv"] == (
        "config/product_scope_breadth_evidence_receipt_current.csv"
    )
    assert summary["product_full_commercial_blocker_evidence_matrix_r8_approval_token_required"] == (
        "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT"
    )
    assert summary["product_full_commercial_blocker_evidence_matrix_r9_blocked_row_count"] == 6
    assert summary[
        "product_full_commercial_blocker_evidence_matrix_r9_first_blocked_evidence_row_id"
    ] == "public_benchmark_gate_not_ready"
    assert summary["product_full_commercial_blocker_evidence_matrix_r9_receipt_csv"] == (
        "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
    )
    assert summary["product_full_commercial_blocker_evidence_matrix_r9_approval_token_required"] == (
        "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT"
    )
    assert summary["goal_bottleneck_briefing_gate_present"] is True
    assert summary["source_goal_bottleneck_briefing_status"] == "goal_bottleneck_briefing_ready"
    assert summary["goal_bottleneck_briefing_full_commercial_receipts_recorded"] is True
    assert summary["goal_bottleneck_briefing_completion_audit_release_blocker_bottleneck_count"] == 2
    assert summary["goal_bottleneck_briefing_full_commercial_evidence_receipt_entry_count"] == 2
    assert summary[
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_operator_input_required_count"
    ] == 2
    assert summary[
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_current_action_required_count"
    ] == 2
    assert summary[
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_template_present_count"
    ] == 2
    assert summary[
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_approval_token_count"
    ] == 2
    assert "blocked_product_scope_breadth_evidence_receipt" in summary[
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_source_gate_statuses"
    ]
    assert "config/engine_refinement_claim_promotion_evidence_receipt_current.csv" in summary[
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_required_inputs"
    ]
    assert "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT" in summary[
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_approval_tokens"
    ]
    assert summary["goal_bottleneck_briefing_production_ai_registry_promotion_priority_recorded"] is True
    assert summary[
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_source_json"
    ] == "runs/production_ai_registry_promotion_priority_packet_current.json"
    assert summary[
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_status"
    ] == "blocked_production_ai_registry_promotion_priority_packet"
    assert summary[
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_packet_ready"
    ] is True
    assert summary[
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_registry_promotion_ready"
    ] is False
    assert summary[
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_operator_input_required_count"
    ] == 3
    assert summary[
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_blocked_priority_item_count"
    ] == 3
    assert summary[
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_missing_gate_count"
    ] == 3
    assert summary[
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_missing_gate_ids"
    ] == [
        "default_residual_mode_guarded",
        "production_promotion_allowed",
        "customer_facing_mutation_flags",
    ]
    assert summary[
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_top_gate_id"
    ] == "default_residual_mode_guarded"
    assert summary[
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_top_priority_bucket"
    ] == "guarded_residual_mode_selection_required"
    assert summary[
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_top_acceptance_artifact"
    ] == "runs/residual_model_registry_current.json"
    assert summary[
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_model_promoted"
    ] is False
    assert summary[
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_customer_facing_mutation_enabled"
    ] is False
    assert summary[
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_external_state_mutated"
    ] is False
    assert summary["production_ai_registry_promotion_priority_packet_recorded"] is True
    assert summary["production_ai_registry_promotion_priority_packet_status"] == (
        "blocked_production_ai_registry_promotion_priority_packet"
    )
    assert summary["production_ai_registry_promotion_priority_packet_ready"] is True
    assert summary["production_ai_registry_promotion_priority_registry_promotion_ready"] is False
    assert summary["production_ai_registry_promotion_priority_missing_gate_count"] == 3
    assert summary["production_ai_registry_promotion_priority_missing_gate_ids"] == [
        "default_residual_mode_guarded",
        "production_promotion_allowed",
        "customer_facing_mutation_flags",
    ]
    assert summary["production_ai_registry_promotion_priority_top_gate_id"] == (
        "default_residual_mode_guarded"
    )
    assert summary["production_ai_registry_promotion_priority_operator_receipt_status"] == (
        "blocked_production_ai_registry_promotion_operator_receipt"
    )
    assert summary["production_ai_registry_promotion_priority_observed_registry_default_residual_mode"] == (
        "shadow"
    )
    assert summary[
        "production_ai_registry_promotion_priority_observed_registry_trained_model_checkpoint_count"
    ] == 1
    assert summary["production_ai_registry_promotion_priority_approval_token_required"] == (
        "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION"
    )
    assert summary["production_ai_checkpoint_readiness_recorded"] is True
    assert summary["production_ai_checkpoint_readiness_status"] == (
        "blocked_product_production_ai_checkpoint_readiness"
    )
    assert summary["production_ai_checkpoint_readiness_production_gpu_execution_environment_ready"] is True
    assert summary["production_ai_checkpoint_readiness_checkpoint_preflight_ready"] is True
    assert summary["production_ai_checkpoint_readiness_production_inference_acceptance_blocked_stage_count"] == 1
    assert summary["production_ai_checkpoint_readiness_actionable_blocker_stage_id"] == (
        "registry_guarded_promotion_acceptance"
    )
    assert summary["production_ai_checkpoint_readiness_registry_promotion_missing_gate_ids"] == (
        "production_promotion_allowed;customer_facing_mutation_flags;"
        "default_residual_mode_guarded"
    )
    assert summary["production_ai_checkpoint_readiness_trained_model_checkpoint_count"] == 1
    assert summary["production_ai_checkpoint_readiness_default_residual_mode"] == "shadow"
    assert summary["production_ai_checkpoint_readiness_production_promotion_allowed"] is False
    assert summary["production_ai_promotion_workbench_recorded"] is True
    assert summary["production_ai_promotion_workbench_status"] == (
        "blocked_product_production_ai_promotion_workbench"
    )
    assert summary["production_ai_promotion_workbench_post_return_ladder_blocked_stage_count"] == 3
    assert summary["production_ai_promotion_workbench_blocked_stage_ids"] == (
        "residual_model_registry;product_ai_architecture_gap_closure;product_goal_completion_audit"
    )
    assert summary["production_ai_promotion_workbench_first_blocked_stage_id"] == (
        "residual_model_registry"
    )
    assert summary["production_ai_promotion_workbench_registry_promotion_missing_gate_count"] == 3
    checkpoint_row = next(
        row for row in payload["rows"] if row["check"] == "production_ai_checkpoint_readiness_recorded"
    )
    workbench_row = next(
        row for row in payload["rows"] if row["check"] == "production_ai_promotion_workbench_recorded"
    )
    assert checkpoint_row["status"] == "pass"
    assert "actionable_blocker_stage_id=registry_guarded_promotion_acceptance" in checkpoint_row["observed"]
    assert workbench_row["status"] == "pass"
    assert "blocked_stage_ids=residual_model_registry;product_ai_architecture_gap_closure" in workbench_row["observed"]
    assert summary["product_scope_breadth_evidence_receipt_recorded"] is True
    assert summary["product_scope_breadth_evidence_receipt_status"] == (
        "blocked_product_scope_breadth_evidence_receipt"
    )
    assert summary["product_scope_breadth_evidence_receipt_ready"] is False
    assert summary["product_scope_breadth_evidence_receipt_blocked_row_count"] == 6
    assert summary["product_scope_breadth_evidence_receipt_evidence_status_contract_present_count"] == 6
    assert summary["product_scope_breadth_evidence_receipt_expected_true_fields_present_count"] == 6
    assert summary["product_scope_breadth_evidence_receipt_expected_quality_true_field_count"] == 4
    assert summary["product_scope_breadth_evidence_receipt_expected_int_min_field_count"] == 4
    assert summary["product_scope_breadth_evidence_receipt_expected_false_field_count"] == 4
    assert summary["product_scope_breadth_evidence_receipt_provenance_kind_accepted_count"] == 6
    assert summary["product_scope_breadth_evidence_receipt_external_state_mutated_false_count"] == 6
    assert summary["product_scope_breadth_evidence_receipt_operator_attestation_accepted_count"] == 6
    assert summary["product_scope_breadth_evidence_receipt_operator_review_surface_ready_count"] == 6
    assert summary["product_scope_breadth_evidence_receipt_operator_review_surface_blocked_count"] == 0
    assert summary["product_scope_breadth_evidence_receipt_receipt_manual_field_pending_count"] == 36
    assert summary["product_scope_breadth_evidence_receipt_receipt_evidence_artifact_pending_count"] == 6
    assert summary["product_scope_breadth_evidence_receipt_receipt_claim_ready_pending_count"] == 6
    assert summary["product_scope_breadth_evidence_receipt_receipt_reviewer_pending_count"] == 6
    assert summary["product_scope_breadth_evidence_receipt_receipt_reviewed_at_utc_pending_count"] == 6
    assert summary["product_scope_breadth_evidence_receipt_receipt_license_ok_pending_count"] == 6
    assert summary["product_scope_breadth_evidence_receipt_receipt_approval_token_pending_count"] == 6
    assert summary["product_scope_breadth_evidence_receipt_required_scope_blocker_count"] == 6
    assert summary["product_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id"] == (
        "direct_binding_evidence_missing"
    )
    assert summary["product_scope_breadth_evidence_receipt_most_common_row_blocker"] == (
        "operator_placeholders_unfilled"
    )
    assert summary["product_scope_breadth_evidence_receipt_approval_token_required"] == (
        "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT"
    )
    assert summary["engine_refinement_claim_evidence_receipt_recorded"] is True
    assert summary["engine_refinement_claim_evidence_receipt_status"] == (
        "blocked_engine_refinement_claim_evidence_receipt"
    )
    assert summary["engine_refinement_claim_evidence_receipt_ready"] is False
    assert summary["engine_refinement_claim_evidence_receipt_blocked_row_count"] == 6
    assert summary["engine_refinement_claim_evidence_receipt_required_blocker_count"] == 6
    assert summary["engine_refinement_claim_evidence_receipt_first_blocked_blocker_id"] == (
        "public_benchmark_gate_not_ready"
    )
    assert summary["engine_refinement_claim_evidence_receipt_most_common_row_blocker"] == (
        "operator_placeholders_unfilled"
    )
    assert summary["engine_refinement_claim_evidence_receipt_approval_token_required"] == (
        "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT"
    )
    assert summary["engine_refinement_claim_evidence_priority_packet_recorded"] is True
    assert summary["engine_refinement_claim_evidence_priority_packet_status"] == (
        "blocked_engine_refinement_claim_evidence_priority_packet"
    )
    assert summary["engine_refinement_claim_evidence_priority_packet_priority_item_count"] == 6
    assert summary["engine_refinement_claim_evidence_priority_packet_operator_input_required_count"] == 6
    assert summary["engine_refinement_claim_evidence_priority_packet_top_blocker_id"] == (
        "public_benchmark_gate_not_ready"
    )
    assert summary["engine_refinement_claim_evidence_priority_packet_top_priority_bucket"] == (
        "public_benchmark_work_order_apply_required"
    )
    assert summary["engine_refinement_claim_evidence_priority_packet_top_required_input"] == (
        "config/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.csv"
    )
    assert summary[
        "engine_refinement_claim_evidence_priority_packet_public_benchmark_work_order_apply_blocked_row_count"
    ] == 8
    assert summary["engine_refinement_claim_evidence_priority_packet_approval_token_required"] == (
        "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT"
    )
    assert summary["refine_tier_public_benchmark_recorded"] is True
    assert summary["refine_tier_public_benchmark_status"] == (
        "blocked_refine_tier_public_benchmark_readiness"
    )
    assert summary["refine_tier_public_benchmark_claim_grade_public_benchmark_ready"] is False
    assert summary["refine_tier_public_benchmark_row_count"] == 0
    assert summary["refine_tier_public_benchmark_valid_row_count"] == 0
    assert summary["refine_tier_public_benchmark_blocker_count"] == 6
    assert summary["refine_tier_public_benchmark_operator_work_order_ready"] is True
    assert summary["refine_tier_public_benchmark_work_order_row_count"] == 8
    assert summary["refine_tier_public_benchmark_write_intake_approval_token_required"] == (
        "APPROVE_REFINE_TIER_PUBLIC_BENCHMARK_INTAKE"
    )
    assert summary["refine_tier_public_benchmark_work_order_apply_recorded"] is True
    assert summary["refine_tier_public_benchmark_work_order_apply_status"] == (
        "blocked_refine_tier_public_benchmark_work_order_apply"
    )
    assert summary["refine_tier_public_benchmark_work_order_apply_blocked_row_count"] == 8
    assert (
        summary[
            "refine_tier_public_benchmark_work_order_apply_receptor_coordinate_validation_required"
        ]
        is True
    )
    assert (
        summary[
            "refine_tier_public_benchmark_work_order_apply_receptor_coordinate_validation_pass_row_count"
        ]
        == 8
    )
    assert (
        summary[
            "refine_tier_public_benchmark_work_order_apply_receptor_coordinate_validation_blocked_row_count"
        ]
        == 0
    )
    assert (
        summary["refine_tier_public_benchmark_work_order_apply_metric_evidence_required"]
        is True
    )
    assert (
        summary["refine_tier_public_benchmark_work_order_apply_metric_evidence_pass_row_count"]
        == 0
    )
    assert (
        summary["refine_tier_public_benchmark_work_order_apply_metric_evidence_blocked_row_count"]
        == 8
    )
    assert summary["refine_tier_public_benchmark_work_order_apply_intake_written"] is False
    assert summary["refine_tier_public_benchmark_work_order_apply_external_state_mutated"] is False
    matrix_row = next(
        row
        for row in payload["rows"]
        if row["check"] == "product_full_commercial_blocker_evidence_matrix_recorded"
    )
    bottleneck_row = next(
        row
        for row in payload["rows"]
        if row["check"] == "goal_bottleneck_briefing_full_commercial_receipts_recorded"
    )
    production_ai_priority_row = next(
        row
        for row in payload["rows"]
        if row["check"] == "goal_bottleneck_briefing_production_ai_registry_promotion_priority_recorded"
    )
    production_ai_priority_packet_row = next(
        row
        for row in payload["rows"]
        if row["check"] == "production_ai_registry_promotion_priority_packet_recorded"
    )
    scope_receipt_row = next(
        row
        for row in payload["rows"]
        if row["check"] == "product_scope_breadth_evidence_receipt_recorded"
    )
    engine_receipt_row = next(
        row
        for row in payload["rows"]
        if row["check"] == "engine_refinement_claim_evidence_receipt_recorded"
    )
    engine_priority_row = next(
        row
        for row in payload["rows"]
        if row["check"] == "engine_refinement_claim_evidence_priority_packet_recorded"
    )
    benchmark_row = next(
        row
        for row in payload["rows"]
        if row["check"] == "refine_tier_public_benchmark_fail_closed_recorded"
    )
    benchmark_apply_row = next(
        row
        for row in payload["rows"]
        if row["check"] == "refine_tier_public_benchmark_work_order_apply_fail_closed_recorded"
    )
    assert bottleneck_row["status"] == "pass"
    assert bottleneck_row["release_blocker"] is False
    assert "full_commercial_evidence_receipt_entry_count=2" in bottleneck_row["observed"]
    assert "full_commercial_evidence_receipt_approval_token_count=2" in bottleneck_row["observed"]
    assert production_ai_priority_row["status"] == "pass"
    assert production_ai_priority_row["release_blocker"] is False
    assert "production_ai_registry_promotion_priority_missing_gate_count=3" in production_ai_priority_row["observed"]
    assert (
        "production_ai_registry_promotion_priority_top_gate_id=default_residual_mode_guarded"
        in production_ai_priority_row["observed"]
    )
    assert (
        "production_ai_registry_promotion_priority_model_promoted=false"
        in production_ai_priority_row["observed"]
    )
    assert "receptor_coordinate_validation_pass_row_count=8" in benchmark_apply_row["observed"]
    assert "receptor_coordinate_validation_blocked_row_count=0" in benchmark_apply_row["observed"]
    assert "metric_evidence_pass_row_count=0" in benchmark_apply_row["observed"]
    assert "metric_evidence_blocked_row_count=8" in benchmark_apply_row["observed"]
    assert production_ai_priority_packet_row["status"] == "pass"
    assert production_ai_priority_packet_row["release_blocker"] is False
    assert "top_gate_id=default_residual_mode_guarded" in production_ai_priority_packet_row["observed"]
    assert "observed_registry_default_residual_mode=shadow" in production_ai_priority_packet_row["observed"]
    assert (
        "operator_receipt_status=blocked_production_ai_registry_promotion_operator_receipt"
        in production_ai_priority_packet_row["observed"]
    )
    assert matrix_row["status"] == "pass"
    assert matrix_row["release_blocker"] is False
    assert "first_blocked_evidence_row_id=direct_binding_evidence_missing" in matrix_row["observed"]
    assert "first_blocked_evidence_artifact=OPERATOR_FILL_LOCAL_EVIDENCE_JSON" in matrix_row["observed"]
    assert "scope_receipt_most_common_row_blocker=operator_placeholders_unfilled" in matrix_row["observed"]
    assert scope_receipt_row["status"] == "pass"
    assert scope_receipt_row["release_blocker"] is False
    assert "first_blocked_scope_blocker_id=direct_binding_evidence_missing" in scope_receipt_row["observed"]
    assert "most_common_row_blocker=operator_placeholders_unfilled" in scope_receipt_row["observed"]
    assert engine_receipt_row["status"] == "pass"
    assert engine_receipt_row["release_blocker"] is False
    assert "first_blocked_blocker_id=public_benchmark_gate_not_ready" in engine_receipt_row["observed"]
    assert "approval_token_required=APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT" in engine_receipt_row["observed"]
    assert engine_priority_row["status"] == "pass"
    assert engine_priority_row["release_blocker"] is False
    assert "top_blocker_id=public_benchmark_gate_not_ready" in engine_priority_row["observed"]
    assert "public_benchmark_work_order_apply_blocked_row_count=8" in engine_priority_row["observed"]
    assert benchmark_row["status"] == "pass"
    assert benchmark_row["release_blocker"] is False
    assert "claim_grade_public_benchmark_ready=false" in benchmark_row["observed"]
    assert "write_intake_approval_token_required=APPROVE_REFINE_TIER_PUBLIC_BENCHMARK_INTAKE" in benchmark_row["observed"]
    assert benchmark_apply_row["status"] == "pass"
    assert benchmark_apply_row["release_blocker"] is False
    assert "blocked_row_count=8" in benchmark_apply_row["observed"]
    assert "intake_written=false" in benchmark_apply_row["observed"]


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
        api_runner_profile_promotion_operator_receipt_packet=(
            _blocked_api_runner_profile_operator_receipt()
        ),
        product_rollout_execution_smoke_receipt_packet=_blocked_rollout_smoke_receipt(),
        accuracy_parity_scorecard_packet=_restricted_accuracy_parity_scorecard(),
        science_claim_promotion_gap_packet=_complete_science_claim_gap(),
        master_gap_closure_rollup_packet=_complete_master_gap_rollup(),
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
    assert summary["master_gap_closure_rollup_status"] == "master_gap_closure_rollup_complete"
    assert summary["master_gap_closure_rollup_recorded"] is True
    assert summary["master_gap_closure_rollup_open_gap_count"] == 0
    assert summary["master_gap_closure_rollup_open_gap_ids"] == []
    assert summary["master_gap_closure_rollup_open_gap_ids_joined"] == ""
    assert summary["master_gap_closure_rollup_closed_gap_count"] == 9
    assert summary["master_gap_closure_rollup_closed_gap_ids_joined"] == (
        "COMMERCIAL;PRODUCT-AI;DATA-SCIENCE;INFRA;SCI-CLAIM;DEPLOY-OPS;STORAGE;TOOLS;API-RUNNER"
    )
    assert summary["master_gap_closure_rollup_release_blocker_row_count"] == 0
    assert summary["master_gap_closure_rollup_science_claim_rollup_status"] == (
        "science_claim_promotion_gap_closure_complete"
    )
    assert summary["master_gap_closure_rollup_science_claim_evidence"] == (
        "runs/science_claim_promotion_gap_closure_current.json"
    )
    assert summary["master_gap_closure_rollup_science_claim_release_blocker"] is False
    assert summary["science_claim_promotion_gap_closure_gate_present"] is True
    assert summary[
        "science_claim_promotion_gap_closure_status"
    ] == "science_claim_promotion_gap_closure_complete"
    assert summary["science_claim_promotion_gap_closure_recorded"] is True
    assert summary["science_claim_promotion_gap_closure_open_gap_ids"] == []
    assert summary["science_claim_promotion_gap_closure_open_gap_ids_joined"] == ""
    assert summary["science_claim_promotion_gap_closure_closed_gap_count"] == 5
    assert summary["science_claim_promotion_gap_closure_closed_gap_ids_joined"] == (
        "SCI-GPCR;SCI-TRANS;SCI-CA2-PXR;SCI-WETLAB;SCI-OPENMM"
    )
    assert summary["science_claim_promotion_gap_closure_release_blocker_row_count"] == 0
    assert summary["science_claim_promotion_gap_closure_current_primary_open_gap_id"] == "none"
    assert summary[
        "science_claim_promotion_gap_closure_primary_open_gap_claim_promotion_status"
    ] == ""
    assert summary["science_claim_promotion_gap_closure_gpcr_claim_promotion_status"] == (
        "boundary_ready_comparison_only"
    )
    assert summary["science_claim_promotion_gap_closure_gpcr_evidence"] == (
        "runs/gpcr_conditional_prior_promotion_gate_current.json"
    )
    assert summary["science_claim_promotion_gap_closure_gpcr_release_blocker"] is False
    assert summary["science_claim_promotion_gap_closure_openmm_claim_promotion_status"] == (
        "restricted_2bead_only"
    )
    assert summary["science_claim_promotion_gap_closure_openmm_evidence"] == (
        "runs/wetlab_openmm_claim_promotion_boundary_current.json; "
        "runs/accuracy_parity_scorecard_current.json"
    )
    assert summary["science_claim_promotion_gap_closure_openmm_release_blocker"] is False
    assert summary["accuracy_parity_scorecard_gate_present"] is True
    assert summary["accuracy_parity_scorecard_status"] == "blocked_accuracy_parity"
    assert summary["accuracy_parity_scorecard_recorded"] is True
    assert summary["accuracy_parity_scorecard_row_count"] == 5
    assert summary["accuracy_parity_scorecard_restricted_pass_row_count"] == 1
    assert summary["accuracy_parity_scorecard_blocked_row_count"] == 0
    assert summary["accuracy_parity_scorecard_top_blocker_count"] == 1
    assert summary["accuracy_parity_scorecard_schrodinger_class_claim_allowed"] is False
    assert summary["accuracy_parity_ligand_ranking_status"] == "restricted_pass"
    assert summary["accuracy_parity_ligand_ranking_blocker_count"] == 1
    assert summary["accuracy_parity_ligand_ranking_metric_thresholds_pass"] is True
    assert summary["accuracy_parity_ligand_ranking_metric_blocker_count"] == 0
    assert summary["accuracy_parity_ligand_ranking_metric_blockers"] == []
    assert summary["accuracy_parity_ligand_ranking_claim_scope_lock_only"] is True
    assert summary["accuracy_parity_ligand_ranking_pr_auc"] == 0.871853
    assert summary["accuracy_parity_ligand_ranking_pr_auc_ci_low"] == 0.761168
    assert summary["accuracy_parity_ligand_ranking_topk_hit_rate"] == 1.0
    assert summary["accuracy_parity_ligand_ranking_score_col_used"] == (
        "binding_score_composite_v7_coverage_v2_crossfit_rank_rescue_shadow"
    )
    assert summary["api_runner_profile_promotion_operator_receipt_gate_present"] is True
    assert summary["api_runner_profile_promotion_operator_receipt_recorded"] is True
    assert summary["api_runner_profile_promotion_operator_receipt_status"] == (
        "blocked_api_runner_profile_promotion_operator_receipt"
    )
    assert summary["api_runner_profile_promotion_operator_receipt_ready"] is False
    assert summary["api_runner_profile_promotion_operator_receipt_profile_count"] == 4
    assert summary["api_runner_profile_promotion_operator_receipt_blocked_row_count"] == 4
    assert summary["api_runner_profile_promotion_operator_receipt_first_blocked_profile_id"] == (
        "backmapping_scoring.example"
    )
    assert summary["api_runner_profile_promotion_operator_receipt_first_blocked_row_blocker"] == (
        "operator_decision_missing"
    )
    assert summary["api_runner_profile_promotion_operator_receipt_runner_executed"] is False
    assert "ACCURACY:ligand_ranking" in summary["full_commercial_release_blocker_ids"]
    smoke_row = next(
        row
        for row in payload["rows"]
        if row["check"] == "product_rollout_execution_smoke_receipt_recorded"
    )
    master_row = next(
        row for row in payload["rows"] if row["check"] == "master_gap_closure_rollup_recorded"
    )
    science_claim_row = next(
        row
        for row in payload["rows"]
        if row["check"] == "science_claim_promotion_gap_closure_recorded"
    )
    accuracy_row = next(
        row for row in payload["rows"] if row["check"] == "accuracy_parity_scorecard_recorded"
    )
    api_runner_receipt_row = next(
        row
        for row in payload["rows"]
        if row["check"] == "api_runner_profile_promotion_operator_receipt_recorded"
    )
    assert smoke_row["status"] == "pass"
    assert smoke_row["release_blocker"] is False
    assert "rollout_executed=false" in smoke_row["observed"]
    assert master_row["status"] == "pass"
    assert master_row["release_blocker"] is False
    assert "open_gap_ids=;" in master_row["observed"]
    assert "closed_gap_count=9" in master_row["observed"]
    assert "release_blocker_row_count=0" in master_row["observed"]
    assert "science_claim_rollup_status=science_claim_promotion_gap_closure_complete" in master_row["observed"]
    assert "science_claim_release_blocker=false" in master_row["observed"]
    assert science_claim_row["status"] == "pass"
    assert science_claim_row["release_blocker"] is False
    assert "open_gap_ids=;" in science_claim_row["observed"]
    assert "closed_gap_count=5" in science_claim_row["observed"]
    assert "release_blocker_row_count=0" in science_claim_row["observed"]
    assert "current_primary_open_gap_id=none" in science_claim_row["observed"]
    assert "gpcr_claim_promotion_status=boundary_ready_comparison_only" in science_claim_row["observed"]
    assert "gpcr_release_blocker=false" in science_claim_row["observed"]
    assert "openmm_claim_promotion_status=restricted_2bead_only" in science_claim_row["observed"]
    assert "openmm_release_blocker=false" in science_claim_row["observed"]
    assert accuracy_row["status"] == "pass"
    assert accuracy_row["release_blocker"] is False
    assert "restricted_pass_row_count=1" in accuracy_row["observed"]
    assert "ligand_ranking_status=restricted_pass" in accuracy_row["observed"]
    assert "ligand_ranking_pr_auc=0.871853" in accuracy_row["observed"]
    assert "ligand_ranking_pr_auc_ci_low=0.761168" in accuracy_row["observed"]
    assert "ligand_ranking_topk_hit_rate=1.0" in accuracy_row["observed"]
    assert "ligand_ranking_metric_thresholds_pass=true" in accuracy_row["observed"]
    assert "ligand_ranking_metric_blocker_count=0" in accuracy_row["observed"]
    assert "ligand_ranking_claim_scope_lock_only=true" in accuracy_row["observed"]
    assert "broad_gpcr_claim_not_allowed" in accuracy_row["observed"]
    assert api_runner_receipt_row["status"] == "pass"
    assert api_runner_receipt_row["release_blocker"] is False
    assert "first_blocked_profile_id=backmapping_scoring.example" in api_runner_receipt_row["observed"]
    assert "first_blocked_row_blocker=operator_decision_missing" in api_runner_receipt_row["observed"]
    assert "runner_executed=false" in api_runner_receipt_row["observed"]


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


def test_goal_release_decision_gate_blocks_without_clean_container_rocm_runtime_smoke() -> None:
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
        product_image_smoke_preflight_packet=_product_image_smoke_preflight(ready=False),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_goal_release_decision"
    assert summary["release_allowed"] is False
    assert summary["product_image_smoke_preflight_gate_present"] is True
    assert summary["clean_container_smoke_ready"] is False
    row = next(row for row in payload["rows"] if row["check"] == "clean_container_rocm_runtime_smoke_ready")
    assert row["status"] == "fail"
    assert row["release_blocker"] is True


def test_goal_release_decision_gate_passes_ready_clean_container_rocm_runtime_smoke() -> None:
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
        product_image_smoke_preflight_packet=_product_image_smoke_preflight(),
    )

    summary = payload["summary"]
    assert summary["status"] == "goal_release_ready"
    assert summary["release_allowed"] is True
    assert summary["clean_container_smoke_ready"] is True
    assert summary["product_image_smoke_container_runtime_receipt_ready"] is True
    assert summary["product_image_smoke_container_runtime_rust_hip_backend_enabled"] is True
    row = next(row for row in payload["rows"] if row["check"] == "clean_container_rocm_runtime_smoke_ready")
    assert row["status"] == "pass"


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


def test_goal_release_decision_gate_accepts_optional_product_ai_backlog_when_nonblocking() -> None:
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
        product_ai_execution_backlog_packet=_optional_product_ai_backlog(),
    )

    summary = payload["summary"]
    row = next(row for row in payload["rows"] if row["check"] == "product_ai_architecture_gap_closure_ready")
    assert summary["status"] == "goal_release_ready"
    assert summary["release_allowed"] is True
    assert summary["product_ai_architecture_ready"] is True
    assert summary["product_ai_architecture_open_gap_count"] == 1
    assert summary["product_ai_execution_backlog_work_item_count"] == 12
    assert summary["product_ai_execution_backlog_release_blocking_work_item_count"] == 0
    assert summary["product_ai_execution_backlog_optional_work_item_count"] == 12
    assert row["status"] == "pass"
    assert "release_blocking_work_item_count=0" in row["observed"]
    assert "optional_work_item_count=12" in row["observed"]
    assert "optional/non-release-blocking" in row["reason"]
    assert "product AI architecture gap closure" not in summary["next_required_step"]


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
        "self_hosted_license_audit": tmp_path / "self_hosted_license_audit.json",
        "third_party_license_review": tmp_path / "third_party_license_review.json",
        "cameo_validation": tmp_path / "cameo_validation.json",
        "cameo_capability": tmp_path / "cameo_capability.json",
        "cameo_fetch_preflight": tmp_path / "cameo_fetch_preflight.json",
        "rollup": tmp_path / "rollup.json",
        "actions": tmp_path / "actions.json",
        "transition_cleanup": tmp_path / "transition_cleanup.json",
        "ligand_cleanup": tmp_path / "ligand_cleanup.json",
        "protected_cleanup": tmp_path / "protected_cleanup.json",
        "cleanup_postcheck": tmp_path / "cleanup_postcheck.json",
        "goal_api_surface": tmp_path / "goal_api_surface.json",
        "goal_bottleneck_briefing": tmp_path / "goal_bottleneck_briefing.json",
        "production_ai_priority": tmp_path / "production_ai_priority.json",
        "production_ai_checkpoint": tmp_path / "production_ai_checkpoint.json",
        "production_ai_workbench": tmp_path / "production_ai_workbench.json",
        "product_ai_gap": tmp_path / "product_ai_gap.json",
        "product_ai_backlog": tmp_path / "product_ai_backlog.json",
        "source_of_truth": tmp_path / "source_of_truth.json",
        "api_customer_flow": tmp_path / "api_customer_flow.json",
        "api_runner_profile_receipt": tmp_path / "api_runner_profile_receipt.json",
        "product_scope_receipt": tmp_path / "product_scope_receipt.json",
        "engine_refinement_receipt": tmp_path / "engine_refinement_receipt.json",
        "engine_refinement_priority": tmp_path / "engine_refinement_priority.json",
        "full_commercial_matrix": tmp_path / "full_commercial_matrix.json",
        "rollout_smoke_receipt": tmp_path / "rollout_smoke_receipt.json",
        "accuracy_parity": tmp_path / "accuracy_parity.json",
        "science_claim_gap": tmp_path / "science_claim_gap.json",
        "master_gap_rollup": tmp_path / "master_gap_rollup.json",
    }
    paths["product"].write_text(json.dumps(_blocked_product()) + "\n", encoding="utf-8")
    paths["product_architecture"].write_text(json.dumps(_blocked_product_architecture()) + "\n", encoding="utf-8")
    paths["product_independence"].write_text(json.dumps(_blocked_product_independence()) + "\n", encoding="utf-8")
    paths["self_hosted_license_audit"].write_text(
        json.dumps(_self_hosted_license_distribution_audit()) + "\n",
        encoding="utf-8",
    )
    paths["third_party_license_review"].write_text(
        json.dumps(_third_party_license_review_gate()) + "\n",
        encoding="utf-8",
    )
    paths["cameo_validation"].write_text(json.dumps(_blocked_cameo_validation()) + "\n", encoding="utf-8")
    paths["cameo_capability"].write_text(json.dumps(_blocked_cameo_capability()) + "\n", encoding="utf-8")
    paths["cameo_fetch_preflight"].write_text(
        json.dumps(_blocked_cameo_official_result_fetch_preflight()) + "\n",
        encoding="utf-8",
    )
    paths["rollup"].write_text(json.dumps(_blocked_rollup()) + "\n", encoding="utf-8")
    paths["actions"].write_text(json.dumps(_blocked_action_board()) + "\n", encoding="utf-8")
    paths["transition_cleanup"].write_text(json.dumps(_transition_cleanup("transition_cleanup_execution_preflight_ready")) + "\n", encoding="utf-8")
    paths["ligand_cleanup"].write_text(json.dumps(_ligand_cleanup("ligand_heavy_cleanup_execution_preflight_ready")) + "\n", encoding="utf-8")
    paths["protected_cleanup"].write_text(json.dumps(_protected_cleanup(2)) + "\n", encoding="utf-8")
    paths["cleanup_postcheck"].write_text(json.dumps(_ready_cleanup_postcheck()) + "\n", encoding="utf-8")
    paths["goal_api_surface"].write_text(json.dumps(_ready_goal_api_surface_contract()) + "\n", encoding="utf-8")
    paths["goal_bottleneck_briefing"].write_text(
        json.dumps(_full_commercial_bottleneck_briefing()) + "\n",
        encoding="utf-8",
    )
    paths["production_ai_priority"].write_text(
        json.dumps(_production_ai_registry_promotion_priority_packet()) + "\n",
        encoding="utf-8",
    )
    paths["production_ai_checkpoint"].write_text(
        json.dumps(_production_ai_checkpoint_readiness()) + "\n",
        encoding="utf-8",
    )
    paths["production_ai_workbench"].write_text(
        json.dumps(_production_ai_promotion_workbench()) + "\n",
        encoding="utf-8",
    )
    paths["product_ai_gap"].write_text(json.dumps(_ready_product_ai_gap()) + "\n", encoding="utf-8")
    paths["product_ai_backlog"].write_text(json.dumps(_ready_product_ai_backlog()) + "\n", encoding="utf-8")
    paths["source_of_truth"].write_text(json.dumps(_ready_source_of_truth()) + "\n", encoding="utf-8")
    paths["api_customer_flow"].write_text(json.dumps(_ready_api_customer_flow()) + "\n", encoding="utf-8")
    paths["api_runner_profile_receipt"].write_text(
        json.dumps(_blocked_api_runner_profile_operator_receipt()) + "\n",
        encoding="utf-8",
    )
    paths["product_scope_receipt"].write_text(
        json.dumps(_blocked_product_scope_receipt()) + "\n",
        encoding="utf-8",
    )
    paths["engine_refinement_receipt"].write_text(
        json.dumps(_blocked_engine_refinement_receipt()) + "\n",
        encoding="utf-8",
    )
    paths["engine_refinement_priority"].write_text(
        json.dumps(_blocked_engine_refinement_priority_packet()) + "\n",
        encoding="utf-8",
    )
    paths["full_commercial_matrix"].write_text(
        json.dumps(_blocked_full_commercial_matrix()) + "\n",
        encoding="utf-8",
    )
    paths["rollout_smoke_receipt"].write_text(
        json.dumps(_blocked_rollout_smoke_receipt()) + "\n",
        encoding="utf-8",
    )
    paths["accuracy_parity"].write_text(
        json.dumps(_restricted_accuracy_parity_scorecard()) + "\n",
        encoding="utf-8",
    )
    paths["science_claim_gap"].write_text(
        json.dumps(_complete_science_claim_gap()) + "\n",
        encoding="utf-8",
    )
    paths["master_gap_rollup"].write_text(
        json.dumps(_complete_master_gap_rollup()) + "\n",
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
            "--self-hosted-license-distribution-audit-json",
            str(paths["self_hosted_license_audit"]),
            "--third-party-license-review-gate-json",
            str(paths["third_party_license_review"]),
            "--cameo-validation-json",
            str(paths["cameo_validation"]),
            "--cameo-capability-json",
            str(paths["cameo_capability"]),
            "--cameo-official-result-fetch-preflight-json",
            str(paths["cameo_fetch_preflight"]),
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
            "--goal-bottleneck-briefing-json",
            str(paths["goal_bottleneck_briefing"]),
            "--production-ai-registry-promotion-priority-packet-json",
            str(paths["production_ai_priority"]),
            "--product-production-ai-checkpoint-readiness-json",
            str(paths["production_ai_checkpoint"]),
            "--product-production-ai-promotion-workbench-json",
            str(paths["production_ai_workbench"]),
            "--product-ai-architecture-gap-json",
            str(paths["product_ai_gap"]),
            "--product-ai-execution-backlog-json",
            str(paths["product_ai_backlog"]),
            "--product-release-source-of-truth-json",
            str(paths["source_of_truth"]),
            "--api-customer-flow-release-evidence-json",
            str(paths["api_customer_flow"]),
            "--api-runner-profile-promotion-operator-receipt-json",
            str(paths["api_runner_profile_receipt"]),
            "--product-scope-breadth-evidence-receipt-json",
            str(paths["product_scope_receipt"]),
            "--engine-refinement-claim-evidence-receipt-json",
            str(paths["engine_refinement_receipt"]),
            "--engine-refinement-claim-evidence-priority-packet-json",
            str(paths["engine_refinement_priority"]),
            "--product-full-commercial-blocker-evidence-matrix-json",
            str(paths["full_commercial_matrix"]),
            "--product-rollout-execution-smoke-receipt-json",
            str(paths["rollout_smoke_receipt"]),
            "--accuracy-parity-scorecard-json",
            str(paths["accuracy_parity"]),
            "--science-claim-promotion-gap-json",
            str(paths["science_claim_gap"]),
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
    assert summary["cameo_official_result_fetch_preflight_status"] == (
        "blocked_cameo_official_result_fetch_preflight"
    )
    assert summary["cameo_official_result_fetch_preflight_fetch_approval_token_required"] == (
        "APPROVE_CAMEO_OFFICIAL_RESULT_FETCH"
    )
    assert summary["self_hosted_license_distribution_audit_recorded"] is True
    assert summary["self_hosted_license_distribution_audit_product_license_path"] == "LICENSE"
    assert summary["self_hosted_license_distribution_audit_third_party_dual_license_assets"] == "jszip"
    assert summary["third_party_license_review_gate_recorded"] is True
    assert summary["third_party_license_review_gate_approved_assets"] == "jszip"
    assert summary["third_party_license_review_gate_approval_token_required"] == (
        "APPROVE_THIRD_PARTY_LICENSE_REVIEW"
    )
    assert summary["product_full_commercial_blocker_evidence_matrix_status"] == (
        "blocked_product_full_commercial_blocker_evidence_matrix"
    )
    assert summary["source_goal_bottleneck_briefing_status"] == "goal_bottleneck_briefing_ready"
    assert summary["goal_bottleneck_briefing_full_commercial_receipts_recorded"] is True
    assert summary["goal_bottleneck_briefing_production_ai_registry_promotion_priority_recorded"] is True
    assert summary[
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_top_gate_id"
    ] == "default_residual_mode_guarded"
    assert summary["production_ai_registry_promotion_priority_packet_recorded"] is True
    assert summary["production_ai_registry_promotion_priority_operator_receipt_status"] == (
        "blocked_production_ai_registry_promotion_operator_receipt"
    )
    assert summary[
        "production_ai_registry_promotion_priority_observed_registry_default_residual_mode"
    ] == "shadow"
    assert summary["production_ai_checkpoint_readiness_recorded"] is True
    assert summary["production_ai_checkpoint_readiness_actionable_blocker_check_id"] == (
        "registry_customer_facing_promotion_allowed"
    )
    assert summary["production_ai_checkpoint_readiness_trained_model_checkpoint_count"] == 1
    assert summary["production_ai_promotion_workbench_recorded"] is True
    assert summary["production_ai_promotion_workbench_first_blocked_stage_ready_key"] == (
        "production_promotion_allowed"
    )
    assert summary["production_ai_promotion_workbench_post_return_ladder_blocked_stage_count"] == 3
    assert summary["product_rollout_execution_smoke_receipt_status"] == (
        "blocked_product_rollout_execution_smoke_receipt"
    )
    assert summary["accuracy_parity_scorecard_status"] == "blocked_accuracy_parity"
    assert summary["accuracy_parity_scorecard_recorded"] is True
    assert summary["accuracy_parity_ligand_ranking_metric_thresholds_pass"] is True
    assert summary["accuracy_parity_ligand_ranking_metric_blocker_count"] == 0
    assert summary["accuracy_parity_ligand_ranking_claim_scope_lock_only"] is True
    assert summary["accuracy_parity_ligand_ranking_score_col_used"] == (
        "binding_score_composite_v7_coverage_v2_crossfit_rank_rescue_shadow"
    )
    assert summary["api_runner_profile_promotion_operator_receipt_status"] == (
        "blocked_api_runner_profile_promotion_operator_receipt"
    )
    assert summary["api_runner_profile_promotion_operator_receipt_recorded"] is True
    assert summary["api_runner_profile_promotion_operator_receipt_first_blocked_profile_id"] == (
        "backmapping_scoring.example"
    )
    assert summary["product_scope_breadth_evidence_receipt_status"] == (
        "blocked_product_scope_breadth_evidence_receipt"
    )
    assert summary["product_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id"] == (
        "direct_binding_evidence_missing"
    )
    assert summary["engine_refinement_claim_evidence_receipt_status"] == (
        "blocked_engine_refinement_claim_evidence_receipt"
    )
    assert summary["engine_refinement_claim_evidence_receipt_first_blocked_blocker_id"] == (
        "public_benchmark_gate_not_ready"
    )
    assert summary["engine_refinement_claim_evidence_priority_packet_status"] == (
        "blocked_engine_refinement_claim_evidence_priority_packet"
    )
    assert summary["engine_refinement_claim_evidence_priority_packet_top_blocker_id"] == (
        "public_benchmark_gate_not_ready"
    )
    assert summary[
        "engine_refinement_claim_evidence_priority_packet_public_benchmark_work_order_apply_blocked_row_count"
    ] == 8
    assert summary["master_gap_closure_rollup_status"] == "master_gap_closure_rollup_complete"
    assert summary["master_gap_closure_rollup_recorded"] is True
    assert summary["master_gap_closure_rollup_open_gap_ids"] == []
    assert summary["master_gap_closure_rollup_closed_gap_count"] == 9
    assert summary["master_gap_closure_rollup_release_blocker_row_count"] == 0
    assert summary["master_gap_closure_rollup_science_claim_rollup_status"] == (
        "science_claim_promotion_gap_closure_complete"
    )
    assert summary[
        "science_claim_promotion_gap_closure_status"
    ] == "science_claim_promotion_gap_closure_complete"
    assert summary["science_claim_promotion_gap_closure_recorded"] is True
    assert summary["science_claim_promotion_gap_closure_open_gap_ids"] == []
    assert summary["science_claim_promotion_gap_closure_closed_gap_count"] == 5
    assert summary["science_claim_promotion_gap_closure_release_blocker_row_count"] == 0
    assert summary["science_claim_promotion_gap_closure_gpcr_claim_promotion_status"] == (
        "boundary_ready_comparison_only"
    )
    assert summary["science_claim_promotion_gap_closure_openmm_claim_promotion_status"] == (
        "restricted_2bead_only"
    )
    assert summary["release_blocked_by_public_benchmark"] is True
    assert summary["cameo_live_validation_required_for_product_release"] is False
    assert out_csv.read_text(encoding="utf-8").startswith("lane_id,check,")
    md_text = out_md.read_text(encoding="utf-8")
    assert "Goal Release Decision Gate" in md_text
    assert "cameo_live_validation_required_for_product_release" in md_text
    assert "cameo_official_result_fetch_preflight_status" in md_text
    assert "APPROVE_CAMEO_OFFICIAL_RESULT_FETCH" in md_text
    assert "self_hosted_license_distribution_audit_recorded" in md_text
    assert "third_party_license_review_gate_recorded" in md_text
    assert "APPROVE_THIRD_PARTY_LICENSE_REVIEW" in md_text
    assert "goal_bottleneck_briefing_full_commercial_receipts_recorded" in md_text
    assert "goal_bottleneck_briefing_production_ai_registry_promotion_priority_recorded" in md_text
    assert "default_residual_mode_guarded" in md_text
    assert "production_ai_registry_promotion_priority_packet_recorded" in md_text
    assert "blocked_production_ai_registry_promotion_operator_receipt" in md_text
    assert "production_ai_checkpoint_readiness_recorded" in md_text
    assert "production_ai_promotion_workbench_recorded" in md_text
    assert "registry_guarded_promotion_acceptance" in md_text
    assert "product_full_commercial_blocker_evidence_matrix_status" in md_text
    assert "product_rollout_execution_smoke_receipt_status" in md_text
    assert "accuracy_parity_scorecard_status" in md_text
    assert "broad_gpcr_claim_not_allowed" in md_text
    assert "api_runner_profile_promotion_operator_receipt_status" in md_text
    assert "backmapping_scoring.example" in md_text
    assert "product_scope_breadth_evidence_receipt_status" in md_text
    assert "engine_refinement_claim_evidence_receipt_status" in md_text
    assert "public_benchmark_gate_not_ready" in md_text
    assert "engine_refinement_claim_evidence_priority_packet_status" in md_text
    assert "public_benchmark_work_order_apply_required" in md_text
    assert "master_gap_closure_rollup_status" in md_text
    assert "master_gap_closure_rollup_science_claim_rollup_status" in md_text
    assert "science_claim_promotion_gap_closure_status" in md_text
    assert "science_claim_promotion_gap_closure_gpcr_claim_promotion_status" in md_text
    assert "science_claim_promotion_gap_closure_openmm_claim_promotion_status" in md_text
    assert "SCI-OPENMM" in md_text
