from __future__ import annotations

import json
from pathlib import Path

from tools import build_goal_operator_action_board as mod


def _rollup() -> dict:
    return {"summary": {"status": "blocked_goal_readiness"}}


def _rollup_with_blocked_receiver_smoke() -> dict:
    return {
        "summary": {"status": "blocked_goal_readiness"},
        "rows": [
            {
                "lane_id": "cameo_validation",
                "artifact_path": "runs/cameo_capability_preflight_current.json",
                "receiver_smoke_status": "blocked_cameo_receiver_smoke",
                "api_dependency_status": "blocked_cameo_api_dependency_readiness",
                "api_dependency_ready": False,
                "api_dependency_blocker_count": 4,
                "receiver_smoke_post_200_ok": False,
                "receiver_smoke_blocker_count": 1,
            }
        ],
    }


def _product_preflight() -> dict:
    return {
        "summary": {
            "status": "product_execution_preflight_ready",
            "approval_token_required": "APPROVE_PRODUCT_DOCKING_EXECUTION",
            "execution_enabled": False,
        }
    }


def _bundle_contract() -> dict:
    return {"summary": {"status": "product_bundle_contract_ready", "bundle_assembled": False}}


def _delivery_evidence() -> dict:
    return {"summary": {"status": "product_delivery_evidence_contract_ready", "delivery_ready_claim_allowed": False}}


def _product_pilot_packet() -> dict:
    return {
        "summary": {
            "status": "product_pilot_packet_preflight_ready",
            "pilot_delivery_ready": False,
        }
    }


def _product_execution_approval_gate() -> dict:
    return {
        "summary": {
            "status": "blocked_product_execution_operator_approval_gate",
            "authorized_for_execution": False,
            "authorized_row_count": 0,
            "awaiting_operator_approval_row_count": 1,
            "blocked_row_count": 1,
            "operator_approval_csv_present": False,
        }
    }


def _product_license_decision_gate() -> dict:
    return {
        "summary": {
            "status": "blocked_product_license_decision_gate",
            "authorized_for_license_file_creation_review": False,
            "operator_intake_csv_present": False,
            "blocker_count": 4,
            "approval_token_required": "APPROVE_PRODUCT_LICENSE_FILE_CREATION",
        }
    }


def _product_license_decision_packet() -> dict:
    return {
        "summary": {
            "status": "product_license_decision_packet_ready",
            "option_count": 5,
            "commercial_gate_only_license_blocked": True,
            "approval_token_required": "APPROVE_PRODUCT_LICENSE_FILE_CREATION",
            "operator_intake_fill_command_template": (
                "python3 tools/fill_product_license_decision_operator_intake.py "
                "--approval-token APPROVE_PRODUCT_LICENSE_FILE_CREATION "
                "--spdx-license-id OPERATOR_FILL_SPDX "
                "--license-text-source OPERATOR_APPROVED_LICENSE_TEXT_FILE "
                "--copyright-holder OPERATOR_FILL_HOLDER "
                "--effective-year OPERATOR_FILL_YEAR "
                "--out-csv runs/product_license_decision_operator_intake.csv"
            ),
            "legal_advice_provided": False,
            "license_file_written": False,
            "external_state_mutated": False,
        }
    }


def _product_license_decision_gate_ready() -> dict:
    return {
        "summary": {
            "status": "product_license_decision_gate_ready",
            "authorized_for_license_file_creation_review": True,
            "operator_intake_csv_present": True,
            "blocker_count": 0,
            "approval_token_required": "APPROVE_PRODUCT_LICENSE_FILE_CREATION",
            "spdx_license_id": "ProprietaryRef-Betelgeuze",
            "license_text_source": "internal counsel approved text",
            "copyright_holder": "Betelgeuze",
            "effective_year": "2026",
        }
    }


def _product_license_file_creation_work_order_ready() -> dict:
    return {
        "summary": {
            "status": "product_license_file_creation_work_order_ready",
            "license_file_creation_review_ready": True,
            "approval_token_required": "APPROVE_PRODUCT_LICENSE_FILE_CREATION",
            "target_license_path": "LICENSE",
            "spdx_license_id": "ProprietaryRef-Betelgeuze",
            "license_text_source": "internal counsel approved text",
            "license_review_manifest_ready": True,
            "license_review_manifest_fingerprint_sha256": "a" * 64,
            "license_file_written": False,
            "external_state_mutated": False,
        }
    }


def _product_release_operations_dossier() -> dict:
    return {
        "summary": {
            "status": "blocked_product_release_operations_dossier",
            "blocked_stage_count": 4,
            "approval_required_stage_count": 2,
            "capability_surface_ready": True,
            "architecture_contract_ready": False,
            "architecture_release_ready": False,
            "architecture_blocked_lane_count": 1,
            "architecture_approval_required_lane_count": 2,
            "cameo_architecture_validation_ready": False,
            "cameo_official_validation_evidence_ready": False,
            "cameo_receiver_smoke_ready": False,
            "cameo_receiver_smoke_status": "blocked_cameo_receiver_smoke",
            "cameo_api_dependency_ready": False,
            "cameo_api_dependency_status": "blocked_cameo_api_dependency_readiness",
            "cameo_public_registration_allowed": False,
            "cameo_public_registration_blocker_count": 4,
            "cameo_registration_approval_token_count": 2,
            "cameo_registration_approval_tokens_required": [
                "APPROVE_CAMEO_SERVER_REGISTRATION",
                "APPROVE_CAMEO_OUTBOUND_EMAIL",
            ],
            "cleanup_postcheck_contract_ready": True,
            "structure_analysis_capability_ready": True,
            "ligand_docking_capability_ready": True,
            "product_api_surface_ready": True,
            "commercial_independence_ready": False,
            "license_present": False,
            "license_decision_packet_ready": True,
            "license_decision_option_count": 5,
            "license_authorized_for_file_creation_review": False,
            "authorized_for_execution": False,
            "bundle_assembled": False,
            "bundle_validation_passed": False,
            "delivery_ready_claim_allowed": False,
            "pilot_delivery_ready": False,
        }
    }


def _product_cli_status() -> dict:
    return {
        "status": "blocked_product_cli_status_set",
        "command_count": 9,
        "blocked_or_missing_command_count": 5,
        "approval_token_count": 2,
        "approval_tokens_required": [
            "APPROVE_PRODUCT_DOCKING_EXECUTION",
            "APPROVE_PRODUCT_LICENSE_FILE_CREATION",
        ],
        "operations_stage_count": 9,
        "operations_blocked_stage_count": 4,
        "operations_approval_required_stage_count": 2,
        "capability_surface_ready": True,
        "operational_quality_ready": True,
        "structure_analysis_capability_ready": True,
        "ligand_docking_capability_ready": True,
        "product_api_surface_ready": True,
        "architecture_release_ready": False,
        "commercial_independence_ready": False,
        "license_present": False,
        "license_authorized_for_file_creation_review": False,
        "authorized_for_execution": False,
        "bundle_assembled": False,
        "bundle_validation_passed": False,
        "delivery_ready_claim_allowed": False,
        "pilot_delivery_ready": False,
    }


def _cameo_input_kit(tmp_path: Path) -> dict:
    return {
        "summary": {"status": "cameo_operator_input_kit_ready", "template_count": 2},
        "rows": [
            {
                "template": "candidates_template.csv",
                "path": str(tmp_path / "candidates_template.csv"),
                "repair_command_arg": "--candidates-csv",
                "required_now": True,
                "purpose": "Internal candidate rows.",
            },
            {
                "template": "models_template.csv",
                "path": str(tmp_path / "models_template.csv"),
                "repair_command_arg": "--models-csv",
                "required_now": True,
                "purpose": "Selected model rows.",
            },
        ],
    }


def _cameo_input_validation() -> dict:
    return {
        "summary": {"status": "blocked_cameo_operator_input_validation", "blocker_count": 2},
        "rows": [
            {"input_name": "candidates_csv", "blockers": "operator_placeholder_present", "ready": False},
            {"input_name": "models_csv", "blockers": "model_path_missing_on_disk", "ready": False},
        ],
    }


def _cameo_repair_preflight() -> dict:
    return {
        "summary": {"status": "blocked_cameo_repair_execution_preflight", "blocker_count": 2},
        "rows": [
            {
                "step": "selection",
                "preflight_status": "fail",
                "input_required": "candidates_csv",
                "command": "python3 tools/build_cameo_model1_selection_packet.py --candidates-csv OPERATOR_FILL",
                "blockers": "operator_placeholder_present",
            },
            {
                "step": "handoff",
                "preflight_status": "pass",
                "input_required": "",
                "command": "python3 tools/build_cameo_dry_run_handoff_packet.py",
                "blockers": "",
            },
        ],
    }


def _transition_preflight() -> dict:
    return {
        "summary": {"status": "transition_cleanup_execution_preflight_ready"},
        "rows": [
            {
                "path": "casp17/massivefold_external_pool_intake",
                "lane": "casp17_external_pool",
                "work_order_status": "approval_gated",
                "recommended_action": "externalize",
                "approval_token": "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS",
                "size_gb": 32.36,
            },
            {
                "path": "/mnt/heavy/ligand_heavy_runs",
                "lane": "ligand_heavy_runs_config_root",
                "work_order_status": "review_only",
                "recommended_action": "review_for_ligand_heavy_payload_cleanup",
                "approval_token": "",
                "size_gb": 402.806,
            },
        ],
    }


def _ligand_preflight() -> dict:
    return {
        "summary": {
            "status": "ligand_heavy_cleanup_execution_preflight_ready",
            "approval_token_required": "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS",
            "candidate_size_gb": 6.011,
            "existing_candidate_count": 40,
        }
    }


def _large_cleanup_drilldown() -> dict:
    return {
        "summary": {
            "status": "large_cleanup_surface_drilldown_ready",
            "known_payload_total_size_gb": 406.131,
            "dry_run_delete_payload_size_gb": 6.012,
            "dry_run_protected_payload_size_gb": 396.794,
        },
        "rows": [
            {
                "surface_path": "/mnt/heavy/ligand_heavy_runs",
                "status": "known_payloads_found",
                "known_payload_size_gb": 6.012,
            }
        ],
    }


def _protected_cleanup_review() -> dict:
    return {
        "summary": {
            "status": "protected_cleanup_payload_review_ready",
            "protected_payload_size_gb": 396.794,
            "policy_change_required_count": 1,
            "approval_promoted_count": 0,
        }
    }


def _protected_ligand_heavy_deep_review() -> dict:
    return {
        "summary": {
            "status": "protected_ligand_heavy_payload_deep_review_ready",
            "known_payload_child_count": 2,
            "known_payload_child_size_gb": 396.794,
            "preservation_sibling_count": 2,
            "policy_change_required_for_deletion_count": 2,
            "approval_promoted_count": 0,
            "delete_executed": False,
            "external_state_mutated": False,
        }
    }


def _protected_cleanup_policy_decision_gate() -> dict:
    return {
        "summary": {
            "status": "blocked_protected_cleanup_policy_decision_gate",
            "policy_resolved": False,
            "awaiting_policy_decision_row_count": 2,
            "policy_change_requested_row_count": 0,
            "blocked_row_count": 2,
        }
    }


def _cleanup_cli_status() -> dict:
    return {
        "status": "blocked_cleanup_cli_status_set",
        "command_count": 16,
        "blocked_or_missing_command_count": 3,
        "approval_required_command_count": 2,
        "approval_token_count": 4,
        "approval_tokens_required": [
            "APPROVE_ARCHIVE_LEGACY_RUNS",
            "APPROVE_DELETE_REGENERABLE_LOCAL_ARTIFACTS",
            "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS",
            "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS",
        ],
        "approval_reclaim_size_gb": 49.216,
        "authorized_reclaim_size_gb": 0.0,
        "awaiting_operator_approval_row_count": 5,
        "postcheck_contract_ready": True,
        "postcheck_row_count": 7,
        "postcheck_blocked_row_count": 0,
        "protected_payload_size_gb": 396.794,
        "protected_policy_change_required_count": 2,
        "protected_policy_resolved": False,
    }


def _cleanup_snapshot_preflight() -> dict:
    return {
        "summary": {
            "status": "blocked_cleanup_snapshot_preflight",
            "blocked_row_count": 2,
            "snapshot_missing_count": 2,
            "snapshot_required_count": 2,
            "approval_gated_size_gb": 49.216,
        }
    }


def _cleanup_payload_manifest_lock() -> dict:
    return {
        "summary": {
            "status": "cleanup_payload_manifest_lock_ready",
            "row_count": 7,
            "blocked_row_count": 0,
            "payload_manifest_fingerprint_sha256": "b" * 64,
        }
    }


def _cleanup_postcheck_contract() -> dict:
    return {
        "summary": {
            "status": "cleanup_postcheck_contract_ready",
            "postcheck_contract_ready": True,
            "row_count": 7,
            "approval_row_count": 5,
            "protected_policy_row_count": 2,
            "blocked_row_count": 0,
            "global_refresh_command_count": 9,
        }
    }


def _cleanup_execution_approval_dossier() -> dict:
    return {
        "summary": {
            "status": "cleanup_execution_approval_dossier_ready",
            "approval_row_count": 5,
            "snapshot_backed_approval_row_count": 2,
            "snapshot_artifact_count": 2,
            "snapshot_ready_count": 2,
            "snapshot_listing_truncated_count": 1,
            "snapshot_total_entry_count": 201224,
            "snapshot_set_fingerprint_sha256": "c" * 64,
        }
    }


def _cleanup_execution_approval_gate() -> dict:
    return {
        "summary": {
            "status": "blocked_cleanup_execution_operator_approval_gate",
            "authorized_row_count": 0,
            "awaiting_operator_approval_row_count": 5,
            "blocked_row_count": 5,
            "authorized_reclaim_size_gb": 0,
            "total_reclaim_size_gb": 49.216,
            "operator_approval_csv_present": False,
        }
    }


def _cleanup_completion_gate() -> dict:
    return {
        "summary": {
            "status": "blocked_cleanup_completion_gate",
            "cleanup_complete": False,
            "blocked_stage_count": 4,
            "approval_ready": False,
            "transition_cleanup_complete": False,
            "ligand_heavy_cleanup_complete": False,
            "protected_policy_resolved": False,
        }
    }


def _cleanup_completion_gate_ready() -> dict:
    return {
        "summary": {
            "status": "cleanup_completion_gate_ready",
            "cleanup_complete": True,
            "blocked_stage_count": 0,
            "approval_ready": True,
            "transition_cleanup_complete": True,
            "ligand_heavy_cleanup_complete": True,
            "protected_policy_resolved": True,
        }
    }


def _cameo_runtime_repair_work_order() -> dict:
    return {
        "summary": {
            "status": "cameo_runtime_repair_work_order_ready",
            "install_approval_required": True,
            "approval_token_required": "APPROVE_API_DEPENDENCY_INSTALL",
            "command_count": 5,
        }
    }


def _cameo_validation_operations_dossier() -> dict:
    return {
        "summary": {
            "status": "blocked_cameo_validation_operations_dossier",
            "blocked_stage_count": 5,
            "approval_required_stage_count": 1,
            "operator_input_required_count": 3,
            "approval_token_count": 3,
            "official_result_required": True,
            "official_results_intake_status": "blocked_cameo_official_results_intake",
            "official_results_intake_ready": False,
            "official_results_intake_blocker_count": 2,
            "public_registration_allowed": False,
        }
    }


def _cameo_validation_operations_dossier_runtime_ready() -> dict:
    packet = _cameo_validation_operations_dossier()
    packet["summary"] = {
        **packet["summary"],
        "api_dependency_status": "cameo_api_dependency_ready",
        "receiver_smoke_status": "cameo_receiver_smoke_ready",
        "approval_required_stage_count": 0,
        "approval_token_count": 2,
    }
    return packet


def _cameo_cli_status() -> dict:
    return {
        "status": "blocked_cameo_cli_status_set",
        "command_count": 11,
        "blocked_or_missing_command_count": 7,
        "approval_required_command_count": 2,
        "approval_token_count": 3,
        "approval_tokens_required": [
            "APPROVE_API_DEPENDENCY_INSTALL",
            "APPROVE_CAMEO_OUTBOUND_EMAIL",
            "APPROVE_CAMEO_SERVER_REGISTRATION",
        ],
        "official_result_required": True,
        "official_results_result_row_count": 0,
        "official_results_accepted_count": 0,
        "official_model1_result_ready": False,
        "evidence_integrity_ready": True,
        "official_results_pending_honest": True,
        "no_local_native_accuracy_substitution": True,
        "api_install_approval_required": True,
        "api_dependency_status": "blocked_cameo_api_dependency_readiness",
        "receiver_smoke_status": "blocked_cameo_receiver_smoke",
        "public_registration_authorized": False,
        "registration_awaiting_operator_approval_row_count": 1,
    }


def _cameo_official_results_intake_gate() -> dict:
    return {
        "summary": {
            "status": "blocked_cameo_official_results_intake",
            "result_row_count": 0,
            "accepted_official_result_count": 0,
            "rejected_official_result_count": 0,
            "model1_official_result_ready": False,
            "blocker_count": 2,
            "blocker_codes": ["official_result_required_columns_missing", "official_result_rows_missing"],
            "missing_required_columns": ["target_id", "candidate_id", "cameo_model_rank"],
            "operator_intake_csv": "runs/cameo_official_results_operator_intake.csv",
        }
    }


def _cameo_public_registration_approval_gate() -> dict:
    return {
        "summary": {
            "status": "blocked_cameo_public_registration_approval_gate",
            "authorized_for_registration_review": False,
            "operator_approval_csv_present": False,
            "blocked_row_count": 1,
        }
    }


def _goal_release_decision_gate() -> dict:
    return {
        "summary": {
            "status": "blocked_goal_release_decision",
            "release_allowed": False,
            "commercial_independent_product_ready": False,
            "cameo_architecture_validation_ready": False,
            "cleanup_objective_ready": False,
            "blocker_count": 12,
            "check_count": 15,
            "source_goal_api_surface_contract_status": "goal_api_surface_contract_ready",
            "goal_api_surface_ready": True,
            "goal_api_surface_check_count": 7,
            "goal_api_surface_blocker_count": 0,
            "goal_api_surface_missing_endpoint_count": 0,
            "goal_api_surface_missing_status_key_count": 0,
            "full_commercial_release_allowed": False,
            "full_commercial_release_blocker_count": 3,
            "full_commercial_release_blocker_ids": [
                "R8_full_scope_claim_closure",
                "R9_engine_refinement_claim_promotion",
                "ACCURACY:ligand_ranking",
            ],
            "full_commercial_release_next_required_step": "Fill the R8/R9 receipt CSVs.",
            "science_claim_promotion_gap_closure_open_gap_ids": [],
            "science_claim_promotion_gap_closure_current_next_action": (
                "All science claim promotion boundary gaps are closed."
            ),
            "accuracy_parity_ligand_ranking_status": "restricted_pass",
            "accuracy_parity_ligand_ranking_pr_auc": 0.871853,
            "accuracy_parity_ligand_ranking_pr_auc_ci_low": 0.761168,
            "accuracy_parity_ligand_ranking_topk_hit_rate": 1.0,
            "accuracy_parity_ligand_ranking_next_required_step": (
                "Keep broad GPCR/Schrodinger-class promotion locked until target-held-out "
                "broad-scope review and scorer/router promotion gates are approved."
            ),
            "primary_full_commercial_release_blocker_id": "R8_full_scope_claim_closure",
            "primary_full_commercial_release_blocker_requirement_id": "R8_full_scope_claim_closure",
            "primary_full_commercial_release_blocker_tier": "full_commercial_scope",
            "primary_full_commercial_release_blocker_blocked_row_count": 6,
            "primary_full_commercial_release_blocker_first_blocked_evidence_row_id": (
                "direct_binding_evidence_missing"
            ),
            "primary_full_commercial_release_blocker_receipt_csv": (
                "config/product_scope_breadth_evidence_receipt_current.csv"
            ),
            "primary_full_commercial_release_blocker_approval_token_required": (
                "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT"
            ),
            "primary_full_commercial_release_blocker_next_required_step": (
                "Replace placeholder receipt rows with reviewed local evidence."
            ),
            "product_full_commercial_blocker_evidence_matrix_r8_blocked_row_count": 6,
            "product_full_commercial_blocker_evidence_matrix_r8_first_blocked_evidence_row_id": (
                "direct_binding_evidence_missing"
            ),
            "product_full_commercial_blocker_evidence_matrix_r8_receipt_csv": (
                "config/product_scope_breadth_evidence_receipt_current.csv"
            ),
            "product_full_commercial_blocker_evidence_matrix_r8_approval_token_required": (
                "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT"
            ),
            "product_full_commercial_blocker_evidence_matrix_r9_blocked_row_count": 6,
            "product_full_commercial_blocker_evidence_matrix_r9_first_blocked_evidence_row_id": (
                "public_benchmark_gate_not_ready"
            ),
            "product_full_commercial_blocker_evidence_matrix_r9_receipt_csv": (
                "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
            ),
            "product_full_commercial_blocker_evidence_matrix_r9_approval_token_required": (
                "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT"
            ),
        }
    }


def _goal_release_burndown_work_order() -> dict:
    return {
        "summary": {
            "status": "goal_release_burndown_work_order_ready",
            "release_blocker_check_count": 12,
            "work_item_count": 12,
            "approval_required_item_count": 7,
            "operator_input_required_item_count": 5,
            "burndown_operator_input_required_work_item_count": 0,
            "official_results_required_item_count": 2,
            "policy_decision_required_item_count": 1,
            "postcheck_required_item_count": 0,
            "approval_token_count": 5,
        }
    }


def _goal_operator_intake_kit() -> dict:
    return {
        "summary": {
            "status": "goal_operator_intake_kit_ready",
            "entry_count": 7,
            "release_burndown_linked_entry_count": 6,
            "operator_input_required_count": 7,
            "current_action_required_count": 5,
            "deferred_operator_input_count": 2,
            "template_copied_count": 6,
            "template_missing_count": 0,
            "approval_token_count": 9,
            "current_action_approval_token_count": 5,
            "current_action_approval_tokens": [
                "APPROVE_API_DEPENDENCY_INSTALL",
                "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS",
                "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS",
                "APPROVE_PRODUCT_DOCKING_EXECUTION",
                "APPROVE_PRODUCT_LICENSE_FILE_CREATION",
            ],
            "product_commercial_independence_status": "blocked_product_commercial_independence_gate",
            "product_commercial_independent_claim_allowed": False,
            "product_commercial_independence_blocker_count": 1,
            "product_commercial_independence_license_present": False,
            "goal_api_surface_contract_status": "goal_api_surface_contract_ready",
            "goal_api_surface_ready": True,
            "goal_api_surface_check_count": 7,
            "goal_api_surface_blocker_count": 0,
            "goal_api_status_endpoint": "/goal/status",
            "goal_api_contract_endpoint": "/goal/api-contract",
        }
    }


def _engine_refinement_claim_action_rows() -> list[dict[str, str]]:
    return [
        {
            "blocker_id": "public_benchmark_gate_not_ready",
            "current_status": "blocked_refine_tier_public_benchmark_readiness",
            "required_evidence": "Curated public benchmark intake rows.",
            "owner_action": "Fill public benchmark work-order rows.",
            "gate_or_artifact": "runs/refine_tier_public_benchmark_readiness_current.json",
            "external_dependency": "Operator curated public benchmark rows.",
            "claim_boundary": "Public benchmark claim stays blocked.",
            "blocking_signals": "insufficient_total_rows;fit_and_holdout_splits_required",
            "next_required_step": "Fill and apply work-order rows.",
        },
        {
            "blocker_id": "external_structure_quality_parity_not_ready",
            "current_status": "blocked_structure_quality_claim",
            "required_evidence": "External MolProbity/OpenStructure parity.",
            "owner_action": "Ingest external structure-quality parity result packet.",
            "gate_or_artifact": "refine_tier_structure_quality_interface_claim_guard",
            "external_dependency": "External parity result packet.",
            "claim_boundary": "Internal proxy is not external parity.",
            "blocking_signals": "external_molprobity_not_available;external_openstructure_not_available",
            "next_required_step": "Add external structure-quality parity intake.",
        },
    ]


def _blocked_accuracy_parity_scorecard() -> dict:
    return {
        "summary": {
            "status": "blocked_accuracy_parity",
            "top_blockers": ["ligand_ranking:broad_gpcr_claim_not_allowed"],
        },
        "rows": [
            {
                "axis": "ligand_ranking",
                "comparator": "Schrodinger Glide/FEP+ class ranking",
                "status": "restricted_pass",
                "claim_scope": "broad GPCR ligand ranking/docking parity",
                "commercial_parity_claim_allowed": False,
                "claim_promotion_allowed": False,
                "source_artifacts": [
                    "runs/gpcr_ranking_summary.json",
                    "runs/gpcr_core_rank_diagnostics_current.json",
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
                    "core_primary_blocker_task": "gpcr_smoke",
                },
                "thresholds": {
                    "ranking_pr_auc_min": 0.55,
                    "ranking_pr_auc_ci_low_min": 0.45,
                    "ranking_topk_hit_rate_min": 0.5,
                    "requires_pose_supported_decoy_resistance": True,
                },
                "blockers": [
                    "broad_gpcr_claim_not_allowed",
                ],
                "next_required_step": (
                    "Keep broad GPCR/Schrodinger-class promotion locked until target-held-out "
                    "broad-scope review and scorer/router promotion gates are approved."
                ),
            }
        ],
    }


def _product_goal_completion_audit() -> dict:
    return {
        "summary": {
            "status": "blocked_product_goal_completion_audit",
            "goal_complete": False,
            "primary_bottleneck_kind": "production_ai_checkpoint_evidence_required",
            "release_blocker_fail_count": 2,
            "release_blocker_requirement_ids": [
                "R8_full_scope_claim_closure",
                "R9_engine_refinement_claim_promotion",
            ],
            "primary_release_blocker_requirement_id": "R8_full_scope_claim_closure",
            "primary_release_blocker_tier": "full_commercial_scope",
            "primary_release_blocker": "full_scope_claim_closure_not_ready",
            "primary_release_blocker_next_command": "python3 tools/build_product_scope_breadth_closure_checklist.py",
            "engine_refinement_claim_promotion_ready": False,
            "engine_refinement_claim_promotion_blocker_count": 6,
            "engine_refinement_claim_promotion_action_row_count": 6,
            "engine_refinement_claim_promotion_blockers": [
                "public_benchmark_gate_not_ready",
                "parameter_calibration_claim_not_ready",
                "metal_cofactor_parameterization_not_ready",
                "charged_residue_protonation_and_charge_calibration_not_ready",
                "solvent_fep_public_pair_calibration_not_ready",
                "external_structure_quality_parity_not_ready",
            ],
            "engine_refinement_claim_promotion_action_board_csv": (
                "runs/engine_refinement_claim_promotion_action_board_current.csv"
            ),
            "engine_refinement_claim_evidence_receipt_ready": False,
            "engine_refinement_claim_evidence_receipt_blocked_row_count": 6,
            "engine_refinement_claim_evidence_receipt_artifact": (
                "runs/engine_refinement_claim_evidence_receipt_current.json"
            ),
            "engine_refinement_claim_evidence_receipt_csv": (
                "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
            ),
            "engine_refinement_claim_promotion_next_required_step": (
                "Fill and apply curated public benchmark rows, then calibrate claim-grade parameterization gates."
            ),
            "production_ai_checkpoint_ready": False,
            "production_ai_checkpoint_failed_check_ids": [
                "production_training_data_ready",
                "force_gpu_worker_return_receipt_ready",
            ],
            "production_ai_gpu_return_intake_status": "blocked_product_production_ai_gpu_return_intake",
            "production_ai_gpu_return_intake_artifact_path": (
                "runs/product_production_ai_gpu_return_intake_current.json"
            ),
            "production_ai_gpu_return_intake_ready": True,
            "production_ai_gpu_return_artifacts_ready": False,
            "production_ai_gpu_return_failed_check_ids": [
                "actual_summary_returned_complete",
                "actual_manifest_operator_verified",
            ],
            "production_ai_gpu_return_actual_summary_return_path": (
                "runs/residual_force_trajectory_regeneration_current_summary.json"
            ),
            "production_ai_gpu_return_actual_manifest_return_path": (
                "runs/residual_force_trajectory_regeneration_current_manifest.csv"
            ),
            "production_ai_gpu_return_manifest_template_csv": (
                "runs/residual_force_gpu_worker_return_manifest_template_current.csv"
            ),
            "production_ai_gpu_return_summary_template_csv": (
                "runs/residual_force_gpu_worker_return_summary_template_current.csv"
            ),
            "production_ai_gpu_return_summary_template_payload_json": (
                "runs/residual_force_trajectory_regeneration_current_summary_template.json"
            ),
            "production_ai_gpu_return_manifest_operator_verification_placeholder_count": 768,
            "production_ai_force_gpu_worker_handoff_ready": True,
            "production_ai_force_gpu_worker_operator_action_required": True,
            "production_ai_force_gpu_full_regeneration_command": (
                "python3 tools/generate_ligand_trajectory_engine.py --prod-mode"
            ),
            "production_ai_force_gpu_post_return_validation_command": (
                "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
            ),
            "production_ai_force_gpu_post_run_validation_commands": [
                "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
                "python3 tools/build_product_goal_completion_audit.py",
            ],
            "production_ai_force_gpu_post_return_required_production_output_fields": [
                "delta_score",
                "corrected_score",
                "delta_energy",
                "delta_force",
                "uncertainty",
                "abstention_reason",
                "stage2_route_decision",
            ],
            "production_ai_force_gpu_post_return_unlock_output_fields": [
                "delta_force",
                "uncertainty",
                "abstention_reason",
                "stage2_route_decision",
            ],
            "production_ai_force_gpu_post_return_min_expected_label_rows": 768,
            "production_ai_force_gpu_post_return_promotion_ladder_stage_count": 10,
            "production_ai_force_gpu_post_return_promotion_ladder_stage_ids": [
                "gpu_return_receipt",
                "product_goal_completion_audit",
            ],
            "production_ai_force_gpu_receipt_manifest_identity_row_count": 0,
            "production_ai_force_gpu_receipt_matched_queue_id_count": 0,
            "production_ai_force_gpu_receipt_matched_expected_npz_count": 0,
            "production_ai_force_gpu_receipt_matched_queue_fingerprint_count": 0,
            "product_scope_general_platform_claim_allowed": False,
            "product_scope_breadth_evidence_receipt_status": "blocked_product_scope_breadth_evidence_receipt",
            "product_scope_breadth_evidence_receipt_ready": False,
            "product_scope_breadth_evidence_receipt_blocker_count": 1,
            "product_scope_breadth_evidence_receipt_blocked_row_count": 6,
            "product_scope_breadth_evidence_receipt_required_scope_blocker_count": 6,
            "product_scope_breadth_evidence_receipt_artifact": (
                "runs/product_scope_breadth_evidence_receipt_current.json"
            ),
            "product_scope_breadth_evidence_receipt_csv": (
                "config/product_scope_breadth_evidence_receipt_current.csv"
            ),
            "product_scope_evidence_priority_ready": True,
            "product_scope_evidence_priority_queue_item_count": 21,
            "product_scope_evidence_priority_open_item_count": 21,
            "product_scope_evidence_priority_local_crosscheck_candidate_count": 11,
            "product_scope_evidence_priority_external_primary_exact_required_count": 6,
            "product_scope_evidence_priority_top_item_id": "AQP1.core_binder_01",
            "product_scope_evidence_priority_top_domain": "transporter",
            "product_scope_evidence_priority_top_bucket": "local_crosscheck_review_present_but_exact_quant_required",
            "product_scope_evidence_priority_top_required_evidence_type": (
                "exact_transporter_target_pair_quantitative_binder_kcal"
            ),
            "product_scope_evidence_priority_top_review_template_artifact": (
                "runs/transporter_manual_review_intake_template_current.json"
            ),
            "product_scope_evidence_priority_top_apply_gate_artifact": (
                "runs/transporter_binder_promotion_gate_current.json"
            ),
            "product_scope_evidence_priority_top_next_step": (
                "Review local crosscheck files, capture exact evidence if present."
            ),
            "product_scope_evidence_intake_ready": True,
            "product_scope_local_crosscheck_intake_ready_count": 10,
            "product_scope_transporter_manual_review_direct_binding_evidence_required_count": 4,
            "product_scope_transporter_manual_review_negative_quantitative_value_required_count": 6,
            "product_scope_transporter_manual_review_decision_placeholder_count": 11,
            "product_scope_transporter_candidate_ready_for_apply_count": 0,
            "product_scope_transporter_top_claim_safe_blocker": (
                "direct_pool_exists_but_named_candidate_identity_not_operator_confirmed"
            ),
            "product_scope_transporter_top_operator_next_verdict": (
                "manual_match_candidate_to_exact_source_then_sync_reference_split_meta"
            ),
            "product_scope_next_operator_completion_item_id": "AQP1.core_binder_01",
            "product_scope_next_operator_completion_intake_mode": "local_crosscheck_triage",
            "product_scope_next_operator_completion_required_evidence_type": (
                "exact_transporter_target_pair_quantitative_binder_kcal"
            ),
            "product_scope_next_operator_completion_transporter_claim_safe_blocker": (
                "direct_pool_exists_but_named_candidate_identity_not_operator_confirmed"
            ),
            "product_scope_next_operator_completion_transporter_operator_next_verdict": (
                "manual_match_candidate_to_exact_source_then_sync_reference_split_meta"
            ),
            "product_scope_next_operator_completion_transporter_best_evidence_source_file": (
                "runs/life_science_skill_crosscheck/chembl_activity_aqp1_target_current_recheck.json"
            ),
            "product_scope_next_operator_completion_transporter_best_evidence_activity_type": "KD",
            "product_scope_next_operator_completion_transporter_best_evidence_value": "174000.0",
            "product_scope_next_operator_completion_transporter_best_evidence_units": "nM",
            "product_scope_next_operator_completion_transporter_best_evidence_document_id": "CHEMBL6182835",
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count": 5,
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_blocker_count": 5,
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id": (
                "operator_review_row"
            ),
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_path": (
                "runs/transporter_manual_review_intake_template_current.csv"
            ),
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_failed_check_ids": [
                "next_slot_required_missing_fields",
                "operator_review_row_not_operator_verified",
            ],
            "product_scope_transporter_p0_operator_validation_candidate_ready": True,
            "product_scope_transporter_p0_operator_validation_candidate_status": "operator_validation_required",
            "product_scope_transporter_p0_operator_validation_candidate_id": (
                "aqp1_chembl20_direct_like_kd_operator_validation"
            ),
            "product_scope_transporter_p0_operator_validation_candidate_target_id": "AQP1",
            "product_scope_transporter_p0_operator_validation_candidate_ligand_external_identifier": "CHEMBL20",
            "product_scope_transporter_p0_operator_validation_candidate_ligand_name": "acetazolamide",
            "product_scope_transporter_p0_operator_validation_candidate_reference_binding_kcal_mol": "-5.13",
            "product_scope_transporter_p0_operator_validation_candidate_source_locator": (
                "https://www.ebi.ac.uk/chembl/api/data/activity.json?"
                "target_chembl_id=CHEMBL4523210&molecule_chembl_id=CHEMBL20"
            ),
            "product_scope_transporter_p0_operator_validation_candidate_blocker": (
                "data_validity_outside_typical_range_and_assay_origin_unknown"
            ),
            "product_scope_transporter_p0_operator_validation_candidate_required_decision_fields": [
                "operator_target_match_confirmed",
                "operator_assay_origin_confirmed",
                "operator_data_validity_accepted",
                "operator_endpoint_is_direct_binding",
                "operator_source_locator_verified",
                "operator_claim_safe_decision",
            ],
            "product_scope_transporter_p0_operator_validation_candidate_required_decision_field_count": 6,
            "product_scope_transporter_p0_operator_validation_candidate_placeholder_count": 6,
            "product_scope_transporter_p0_operator_validation_candidate_validation_blockers": [
                "assay_origin_unknown",
                "data_validity_outside_typical_range",
                "source_locator_requires_operator_verification",
                "direct_binding_claim_requires_exact_target_pair_source",
            ],
            "product_scope_pxr_exact_review_intake_ready": True,
            "product_scope_pxr_exact_review_template_row_count": 6,
            "product_scope_pxr_exact_review_kcal_placeholder_count": 6,
            "product_scope_pxr_exact_review_conflict_resolution_required_count": 3,
        }
    }


def _product_goal_completion_audit_registry_action() -> dict:
    payload = json.loads(json.dumps(_product_goal_completion_audit()))
    summary = payload["summary"]
    packet = {
        "artifact_id": "residual_model_registry_guarded_promotion",
        "artifact_path": "runs/residual_model_registry_current.json",
        "packet_ready": True,
        "required_fields_or_columns": [
            "production_promotion_allowed",
            "customer_facing_auto_correction_allowed",
            "customer_facing_score_mutation_allowed",
            "customer_facing_ranking_mutation_allowed",
            "default_residual_mode",
            "trained_model_checkpoint_count",
        ],
        "diagnostic_commands": [
            "python3 tools/build_residual_model_registry.py",
            "python3 tools/build_product_production_ai_checkpoint_readiness.py",
            "python3 tools/build_product_production_ai_promotion_workbench.py",
        ],
        "diagnostic_command_count": 3,
        "diagnostic_required_fields": [
            "production_promotion_allowed",
            "customer_facing_auto_correction_allowed",
            "customer_facing_score_mutation_allowed",
            "customer_facing_ranking_mutation_allowed",
            "default_residual_mode",
            "trained_model_checkpoint_count",
        ],
        "diagnostic_required_field_count": 6,
        "diagnostic_completion_rule": (
            "production_promotion_allowed=true; all customer-facing mutation flags true; "
            "default_residual_mode in assist/production/production_guarded; "
            "trained_model_checkpoint_count>0"
        ),
        "diagnostic_return_artifacts": [
            "runs/residual_model_registry_current.json",
            "runs/product_production_ai_checkpoint_readiness_current.json",
            "runs/product_production_ai_promotion_workbench_current.json",
        ],
        "failed_check_ids": [
            "production_promotion_allowed",
            "customer_facing_mutation_flags",
            "default_residual_mode_guarded",
            "trained_model_checkpoint_count_positive",
        ],
        "validation_command": (
            "python3 tools/build_residual_model_registry.py && "
            "python3 tools/build_product_production_ai_checkpoint_readiness.py && "
            "python3 tools/build_product_production_ai_promotion_workbench.py"
        ),
        "full_regeneration_command": "python3 tools/generate_ligand_trajectory_engine.py --prod-mode",
        "completion_rule": "registry_promotion_missing_gate_count=0 and registry_promotion_currently_satisfied=true",
        "next_action": "Register or promote a trained preflight-ready production checkpoint in residual_model_registry.",
    }
    summary.update(
        {
            "production_ai_checkpoint_failed_check_ids": [
                "registry_customer_facing_promotion_allowed"
            ],
            "production_ai_gpu_return_artifacts_ready": True,
            "production_ai_gpu_return_failed_check_ids": [],
            "production_ai_force_gpu_receipt_manifest_identity_row_count": 768,
            "production_ai_force_gpu_receipt_matched_queue_id_count": 768,
            "production_ai_force_gpu_receipt_matched_expected_npz_count": 768,
            "production_ai_force_gpu_receipt_matched_queue_fingerprint_count": 768,
            "production_ai_checkpoint_actionable_blocker_stage_id": "registry_guarded_promotion_acceptance",
            "production_ai_checkpoint_actionable_blocker_check_id": "registry_customer_facing_promotion_allowed",
            "production_ai_checkpoint_actionable_operator_completion_packet_ready": True,
            "production_ai_checkpoint_actionable_operator_completion_artifact_id": (
                "residual_model_registry_guarded_promotion"
            ),
            "production_ai_checkpoint_actionable_operator_completion_artifact_path": (
                "runs/residual_model_registry_current.json"
            ),
            "production_ai_checkpoint_actionable_operator_completion_required_fields_or_columns": packet[
                "required_fields_or_columns"
            ],
            "production_ai_checkpoint_actionable_operator_completion_diagnostic_commands": packet[
                "diagnostic_commands"
            ],
            "production_ai_checkpoint_actionable_operator_completion_diagnostic_command_count": 3,
            "production_ai_checkpoint_actionable_operator_completion_validation_command": packet[
                "validation_command"
            ],
            "production_ai_checkpoint_actionable_operator_completion_completion_rule": packet[
                "completion_rule"
            ],
            "production_ai_checkpoint_actionable_operator_completion_next_action": packet["next_action"],
            "production_ai_checkpoint_actionable_operator_completion_packet": packet,
        }
    )
    return payload


def _scope_breadth_evidence_receipt() -> dict:
    return {
        "summary": {
            "first_blocked_scope_blocker_id": "direct_binding_evidence_missing",
            "first_blocked_evidence_artifact": "OPERATOR_FILL_LOCAL_EVIDENCE_JSON",
            "first_blocked_expected_evidence_status": (
                "product_scope_transporter_direct_binding_evidence_ready"
            ),
            "first_blocked_observed_evidence_status": "missing",
            "first_blocked_missing_true_fields": [
                "transporter_direct_binding_evidence_ready",
            ],
            "first_blocked_row_blockers": [
                "operator_placeholders_unfilled",
                "evidence_artifact_not_found",
                "approval_token_missing_or_invalid",
            ],
            "most_common_row_blocker": "operator_placeholders_unfilled",
        }
    }


def _engine_refinement_claim_evidence_receipt() -> dict:
    return {
        "summary": {
            "status": "blocked_engine_refinement_claim_evidence_receipt",
            "receipt_csv": "config/engine_refinement_claim_promotion_evidence_receipt_current.csv",
            "approval_token_required": "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT",
            "blocked_row_count": 6,
            "first_blocked_blocker_id": "public_benchmark_gate_not_ready",
            "first_blocked_evidence_artifact": "OPERATOR_FILL_LOCAL_EVIDENCE_JSON",
            "first_blocked_expected_evidence_status": "refine_tier_public_benchmark_ready",
            "first_blocked_observed_evidence_status": "missing",
            "first_blocked_missing_true_fields": [
                "claim_grade_public_benchmark_ready",
            ],
            "first_blocked_row_blockers": [
                "operator_placeholders_unfilled",
                "evidence_artifact_not_found",
                "approval_token_missing_or_invalid",
            ],
            "most_common_row_blocker": "operator_placeholders_unfilled",
        }
    }


def _engine_refinement_claim_evidence_priority_packet() -> dict:
    return {
        "summary": {
            "status": "blocked_engine_refinement_claim_evidence_priority_packet",
            "priority_packet_ready": True,
            "claim_promotion_allowed": False,
            "claim_evidence_receipt_status": "blocked_engine_refinement_claim_evidence_receipt",
            "top_blocker_id": "public_benchmark_gate_not_ready",
            "top_priority_bucket": "public_benchmark_work_order_apply_required",
            "top_required_input": (
                "config/refine_tier_public_benchmark_statistical_support_"
                "metric_source_payload_operator_receipt_current.csv"
            ),
            "top_acceptance_artifact": "runs/refine_tier_public_benchmark_readiness_current.json",
            "top_verification_command": (
                "python3 tools/product/build_refine_tier_public_benchmark_"
                "statistical_support_metric_source_payload_operator_receipt.py; "
                "python3 tools/product/materialize_refine_tier_public_benchmark_"
                "statistical_support_metric_candidates.py; "
                "python3 tools/product/build_engine_refinement_claim_evidence_priority_packet.py"
            ),
            "top_next_operator_step": (
                "Fill and review the 51 DockQ/lDDT-PLI/internal DeltaG metric source payloads."
            ),
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_csv": (
                "config/refine_tier_public_benchmark_statistical_support_"
                "metric_source_payload_operator_receipt_current.csv"
            ),
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_approval_token_required": (
                "APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS"
            ),
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_status": (
                "blocked_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt"
            ),
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready": False,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_row_count": 51,
        }
    }


def test_goal_operator_action_board_surfaces_product_ai_goal_completion_actions() -> None:
    actions = mod._product_goal_completion_actions(
        goal_completion_audit=_product_goal_completion_audit(),
        goal_completion_audit_path="runs/product_goal_completion_audit_current.json",
        scope_breadth_evidence_receipt=_scope_breadth_evidence_receipt(),
    )

    by_type = {row["action_type"]: row for row in actions}
    gpu = by_type["return_gpu_force_regeneration_receipt"]
    assert gpu["priority"] == 0
    assert gpu["lane_id"] == "product_ai_production"
    assert gpu["status"] == "required"
    assert "product_production_ai_gpu_return_intake_current.json" in gpu["artifact_path"]
    assert "generate_ligand_trajectory_engine.py" in gpu["command"]
    assert gpu["gpu_return_intake_status"] == "blocked_product_production_ai_gpu_return_intake"
    assert gpu["gpu_return_intake_ready"] is True
    assert gpu["gpu_return_artifacts_ready"] is False
    assert gpu["gpu_return_failed_check_ids"] == (
        "actual_summary_returned_complete;actual_manifest_operator_verified"
    )
    assert gpu["gpu_return_actual_summary_return_path"] == (
        "runs/residual_force_trajectory_regeneration_current_summary.json"
    )
    assert gpu["gpu_return_actual_manifest_return_path"] == (
        "runs/residual_force_trajectory_regeneration_current_manifest.csv"
    )
    assert gpu["gpu_return_manifest_operator_verification_placeholder_count"] == 768
    assert gpu["gpu_return_summary_template_csv"] == (
        "runs/residual_force_gpu_worker_return_summary_template_current.csv"
    )
    assert gpu["gpu_return_summary_template_payload_json"] == (
        "runs/residual_force_trajectory_regeneration_current_summary_template.json"
    )
    assert "delta_force;uncertainty;abstention_reason;stage2_route_decision" == gpu[
        "post_return_unlock_output_fields"
    ]
    assert gpu["post_return_min_expected_label_rows"] == 768
    assert gpu["post_return_promotion_ladder_stage_count"] == 10
    assert gpu["post_return_promotion_ladder_stage_ids"] == "gpu_return_receipt;product_goal_completion_audit"
    assert gpu["post_return_required_production_output_fields"] == (
        "delta_score;corrected_score;delta_energy;delta_force;uncertainty;abstention_reason;stage2_route_decision"
    )
    assert gpu["post_run_validation_command_count"] == 2
    assert gpu["parallelizable_with_primary_action"] is False
    assert gpu["receipt_manifest_identity_row_count"] == 0
    assert gpu["receipt_matched_queue_id_count"] == 0
    assert gpu["receipt_matched_expected_npz_count"] == 0
    assert gpu["receipt_matched_queue_fingerprint_count"] == 0
    assert "gpu_return_failed_checks=actual_summary_returned_complete;actual_manifest_operator_verified" in gpu["reason"]
    assert "receipt_manifest_identity_rows=0" in gpu["reason"]

    registry_payload = mod._product_goal_completion_actions(
        goal_completion_audit=_product_goal_completion_audit_registry_action(),
        goal_completion_audit_path="runs/product_goal_completion_audit_current.json",
    )
    registry_by_type = {row["action_type"]: row for row in registry_payload}
    registry = registry_by_type["complete_residual_registry_guarded_promotion"]
    assert "return_gpu_force_regeneration_receipt" not in registry_by_type
    assert registry["priority"] == 0
    assert registry["lane_id"] == "product_ai_production"
    assert registry["approval_token"] == mod.PRODUCTION_AI_REGISTRY_PROMOTION_APPROVAL_TOKEN
    assert registry["operator_completion_packet_ready"] is True
    assert registry["operator_completion_artifact_id"] == "residual_model_registry_guarded_promotion"
    assert registry["required_input"] == (
        "production_promotion_allowed;customer_facing_auto_correction_allowed;"
        "customer_facing_score_mutation_allowed;customer_facing_ranking_mutation_allowed;"
        "default_residual_mode;trained_model_checkpoint_count"
    )
    assert "build_residual_model_registry.py" in registry["command"]
    assert "registry_promotion_missing_gate_count=0" in registry[
        "operator_completion_completion_rule"
    ]
    assert "failed_checks=production_promotion_allowed" in registry["reason"]
    assert "registry promotion operator receipt" in mod._next_required_step([registry])

    scope = by_type["curate_scope_evidence_priority_item"]
    assert scope["priority"] == 2
    assert scope["lane_id"] == "product_scope_expansion"
    assert scope["status"] == "review_required"
    assert scope["parallelizable_with_primary_action"] is True
    assert scope["parallel_primary_action_id"] == (
        "product_ai_production:return_gpu_force_regeneration_receipt"
    )
    assert "does not require production GPU execution" in scope["parallel_lane_precondition"]
    assert scope["required_input"] == "AQP1.core_binder_01"
    assert scope["scope_priority_top_domain"] == "transporter"
    assert scope["scope_transporter_top_claim_safe_blocker"] == (
        "direct_pool_exists_but_named_candidate_identity_not_operator_confirmed"
    )
    assert scope["scope_transporter_top_operator_next_verdict"] == (
        "manual_match_candidate_to_exact_source_then_sync_reference_split_meta"
    )
    assert scope["scope_next_operator_completion_item_id"] == "AQP1.core_binder_01"
    assert scope["scope_next_operator_completion_intake_mode"] == "local_crosscheck_triage"
    assert scope["scope_next_operator_completion_required_evidence_type"] == (
        "exact_transporter_target_pair_quantitative_binder_kcal"
    )
    assert scope["scope_next_operator_completion_transporter_claim_safe_blocker"] == (
        "direct_pool_exists_but_named_candidate_identity_not_operator_confirmed"
    )
    assert scope["scope_next_operator_completion_transporter_operator_next_verdict"] == (
        "manual_match_candidate_to_exact_source_then_sync_reference_split_meta"
    )
    assert scope["scope_next_operator_completion_transporter_best_evidence_source_file"] == (
        "runs/life_science_skill_crosscheck/chembl_activity_aqp1_target_current_recheck.json"
    )
    assert scope["scope_next_operator_completion_transporter_best_evidence_activity_type"] == "KD"
    assert scope["scope_next_operator_completion_transporter_best_evidence_value"] == "174000.0"
    assert scope["scope_next_operator_completion_transporter_best_evidence_units"] == "nM"
    assert scope["scope_next_operator_completion_transporter_best_evidence_document_id"] == (
        "CHEMBL6182835"
    )
    assert scope["scope_transporter_p0_return_bundle_required_artifact_count"] == 5
    assert scope["scope_transporter_p0_return_bundle_blocker_count"] == 5
    assert scope["scope_transporter_p0_return_bundle_next_artifact_id"] == "operator_review_row"
    assert scope["scope_transporter_p0_return_bundle_next_artifact_path"] == (
        "runs/transporter_manual_review_intake_template_current.csv"
    )
    assert scope["scope_transporter_p0_return_bundle_next_artifact_failed_check_ids"] == (
        "next_slot_required_missing_fields;operator_review_row_not_operator_verified"
    )
    assert scope["scope_transporter_p0_operator_validation_candidate_ready"] is True
    assert scope["scope_transporter_p0_operator_validation_candidate_status"] == (
        "operator_validation_required"
    )
    assert scope["scope_transporter_p0_operator_validation_candidate_id"] == (
        "aqp1_chembl20_direct_like_kd_operator_validation"
    )
    assert scope["scope_transporter_p0_operator_validation_candidate_target_id"] == "AQP1"
    assert scope[
        "scope_transporter_p0_operator_validation_candidate_ligand_external_identifier"
    ] == "CHEMBL20"
    assert scope["scope_transporter_p0_operator_validation_candidate_ligand_name"] == (
        "acetazolamide"
    )
    assert scope[
        "scope_transporter_p0_operator_validation_candidate_reference_binding_kcal_mol"
    ] == "-5.13"
    assert "molecule_chembl_id=CHEMBL20" in scope[
        "scope_transporter_p0_operator_validation_candidate_source_locator"
    ]
    assert scope["scope_transporter_p0_operator_validation_candidate_blocker"] == (
        "data_validity_outside_typical_range_and_assay_origin_unknown"
    )
    assert "operator_claim_safe_decision" in scope[
        "scope_transporter_p0_operator_validation_candidate_required_decision_fields"
    ]
    assert scope["scope_transporter_p0_operator_validation_candidate_required_decision_field_count"] == 6
    assert scope["scope_transporter_p0_operator_validation_candidate_placeholder_count"] == 6
    assert "source_locator_requires_operator_verification" in scope[
        "scope_transporter_p0_operator_validation_candidate_validation_blockers"
    ]
    assert scope["scope_evidence_intake_ready"] is True
    assert scope["scope_local_crosscheck_intake_ready_count"] == 10
    assert scope["scope_transporter_manual_review_direct_binding_required_count"] == 4
    assert scope["scope_transporter_manual_review_negative_quantitative_required_count"] == 6
    assert scope["scope_transporter_manual_review_decision_placeholder_count"] == 11
    assert scope["scope_transporter_candidate_ready_for_apply_count"] == 0
    assert scope["scope_pxr_exact_review_intake_ready"] is True
    assert scope["scope_pxr_exact_review_template_row_count"] == 6
    assert scope["scope_pxr_exact_review_kcal_placeholder_count"] == 6
    assert scope["scope_pxr_exact_review_conflict_resolution_required_count"] == 3
    assert "pxr_exact_review_kcal_placeholder_count=6" in scope["reason"]
    assert "transporter_top_claim_safe_blocker=direct_pool_exists_but_named_candidate_identity_not_operator_confirmed" in scope[
        "reason"
    ]
    assert "next_operator_best_evidence=KD:174000.0nM:CHEMBL6182835" in scope["reason"]
    assert "return_bundle_next_artifact=operator_review_row:runs/transporter_manual_review_intake_template_current.csv" in scope[
        "reason"
    ]
    assert "operator_validation_candidate=CHEMBL20:-5.13:operator_validation_required" in scope[
        "reason"
    ]
    assert "operator_validation_placeholder_count=6" in scope["reason"]

    receipt = by_type["resolve_full_scope_breadth_evidence_receipt"]
    assert receipt["priority"] == 2
    assert receipt["lane_id"] == "product_scope_expansion"
    assert receipt["status"] == "required"
    assert receipt["approval_token"] == mod.PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT_APPROVAL_TOKEN
    assert receipt["required_input"] == "config/product_scope_breadth_evidence_receipt_current.csv"
    assert receipt["scope_breadth_evidence_receipt_status"] == (
        "blocked_product_scope_breadth_evidence_receipt"
    )
    assert receipt["scope_breadth_evidence_receipt_blocked_row_count"] == 6
    assert receipt["scope_breadth_evidence_receipt_required_scope_blocker_count"] == 6
    assert receipt["scope_breadth_evidence_receipt_first_blocked_scope_blocker_id"] == (
        "direct_binding_evidence_missing"
    )
    assert receipt["scope_breadth_evidence_receipt_first_blocked_evidence_artifact"] == (
        "OPERATOR_FILL_LOCAL_EVIDENCE_JSON"
    )
    assert receipt["scope_breadth_evidence_receipt_first_blocked_expected_evidence_status"] == (
        "product_scope_transporter_direct_binding_evidence_ready"
    )
    assert receipt["scope_breadth_evidence_receipt_first_blocked_observed_evidence_status"] == (
        "missing"
    )
    assert receipt["scope_breadth_evidence_receipt_first_blocked_missing_true_fields"] == (
        "transporter_direct_binding_evidence_ready"
    )
    assert "operator_placeholders_unfilled" in receipt[
        "scope_breadth_evidence_receipt_first_blocked_row_blockers"
    ]
    assert receipt["scope_breadth_evidence_receipt_most_common_row_blocker"] == (
        "operator_placeholders_unfilled"
    )
    assert "blocked_row_count=6" in receipt["reason"]


def test_goal_operator_action_board_surfaces_engine_refinement_claim_actions() -> None:
    payload = mod.build_action_board(
        rollup_packet={},
        product_preflight_packet={},
        product_bundle_contract_packet={},
        product_delivery_evidence_packet={},
        cameo_input_kit_packet={},
        cameo_input_validation_packet={},
        cameo_repair_preflight_packet={},
        transition_cleanup_preflight_packet={},
        ligand_cleanup_preflight_packet={},
        cleanup_completion_gate_packet=_cleanup_completion_gate_ready(),
        engine_refinement_claim_action_board_rows=_engine_refinement_claim_action_rows(),
        engine_refinement_claim_evidence_receipt_packet=_engine_refinement_claim_evidence_receipt(),
        engine_refinement_claim_evidence_priority_packet=(
            _engine_refinement_claim_evidence_priority_packet()
        ),
        engine_refinement_claim_action_board_path=(
            "runs/engine_refinement_claim_promotion_action_board_current.csv"
        ),
    )

    summary = payload["summary"]
    assert summary["product_engine_refinement_action_count"] == 2
    assert summary["product_engine_refinement_claim_blocker_count"] == 2
    assert (
        summary["product_engine_refinement_action_board_csv"]
        == "runs/engine_refinement_claim_promotion_action_board_current.csv"
    )
    assert summary["engine_refinement_priority_action_id"] == (
        "product_engine_refinement:resolve_refine_tier_claim_promotion_blocker"
    )
    assert summary["engine_refinement_priority_top_item_id"] == "public_benchmark_gate_not_ready"
    assert summary["engine_refinement_priority_top_blocker_id"] == "public_benchmark_gate_not_ready"
    assert summary["engine_refinement_priority_top_bucket"] == (
        "public_benchmark_work_order_apply_required"
    )
    assert summary["engine_refinement_priority_top_required_input"] == (
        "config/refine_tier_public_benchmark_statistical_support_"
        "metric_source_payload_operator_receipt_current.csv"
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
    assert summary["engine_refinement_priority_metric_source_payload_receipt_csv"] == (
        "config/refine_tier_public_benchmark_statistical_support_"
        "metric_source_payload_operator_receipt_current.csv"
    )
    assert summary[
        "engine_refinement_priority_metric_source_payload_receipt_approval_token_required"
    ] == "APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS"
    assert summary[
        "engine_refinement_priority_metric_source_payload_receipt_status"
    ] == "blocked_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt"
    assert summary["engine_refinement_priority_metric_source_payload_receipt_ready"] is False
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
    rows = {row["claim_blocker_id"]: row for row in payload["rows"]}
    public = rows["public_benchmark_gate_not_ready"]
    assert public["lane_id"] == "product_engine_refinement"
    assert public["action_type"] == "resolve_refine_tier_claim_promotion_blocker"
    assert public["status"] == "required"
    assert public["required_input"] == "public_benchmark_gate_not_ready"
    assert public["claim_blocker_gate_or_artifact"] == "runs/refine_tier_public_benchmark_readiness_current.json"
    assert "insufficient_total_rows" in public["claim_blocker_blocking_signals"]
    assert public["claim_evidence_receipt_first_blocked_match"] is True
    assert public["claim_evidence_receipt_first_blocked_blocker_id"] == (
        "public_benchmark_gate_not_ready"
    )
    assert public["claim_evidence_receipt_first_blocked_evidence_artifact"] == (
        "OPERATOR_FILL_LOCAL_EVIDENCE_JSON"
    )
    assert public["claim_evidence_receipt_first_blocked_expected_evidence_status"] == (
        "refine_tier_public_benchmark_ready"
    )
    assert public["claim_evidence_receipt_first_blocked_missing_true_fields"] == (
        "claim_grade_public_benchmark_ready"
    )
    assert "operator_placeholders_unfilled" in public[
        "claim_evidence_receipt_first_blocked_row_blockers"
    ]
    assert public["claim_evidence_receipt_most_common_row_blocker"] == (
        "operator_placeholders_unfilled"
    )


def test_goal_operator_action_board_surfaces_accuracy_ligand_ranking_action() -> None:
    payload = mod.build_action_board(
        rollup_packet={},
        product_preflight_packet={},
        product_bundle_contract_packet={},
        product_delivery_evidence_packet={},
        cameo_input_kit_packet={},
        cameo_input_validation_packet={},
        cameo_repair_preflight_packet={},
        transition_cleanup_preflight_packet={},
        ligand_cleanup_preflight_packet={},
        cleanup_completion_gate_packet=_cleanup_completion_gate_ready(),
        accuracy_parity_scorecard_packet=_blocked_accuracy_parity_scorecard(),
        accuracy_parity_scorecard_path="runs/accuracy_parity_scorecard_current.json",
    )

    summary = payload["summary"]
    assert summary["product_accuracy_parity_action_count"] == 1
    assert summary["product_accuracy_parity_ligand_ranking_action_id"] == (
        "product_accuracy_parity:close_ligand_ranking_claim_scope"
    )
    assert summary["product_accuracy_parity_ligand_ranking_action_present"] is True
    assert summary["product_accuracy_parity_ligand_ranking_required_input"] == (
        "ACCURACY:ligand_ranking"
    )
    assert summary["product_accuracy_parity_ligand_ranking_artifact_path"] == (
        "runs/accuracy_parity_scorecard_current.json"
    )
    assert "target-held-out broad-scope review" in summary[
        "product_accuracy_parity_ligand_ranking_recommended_action"
    ]
    assert summary["product_accuracy_parity_scorecard_status"] == "blocked_accuracy_parity"
    assert summary["product_accuracy_parity_ligand_ranking_status"] == "restricted_pass"
    assert summary["product_accuracy_parity_ligand_ranking_blocker_count"] == 1
    assert summary["product_accuracy_parity_ligand_ranking_metric_thresholds_pass"] is True
    assert summary["product_accuracy_parity_ligand_ranking_metric_blocker_count"] == 0
    assert summary["product_accuracy_parity_ligand_ranking_metric_blockers"] == []
    assert summary["product_accuracy_parity_ligand_ranking_claim_scope_lock_only"] is True
    assert summary["product_accuracy_parity_ligand_ranking_pr_auc"] == 0.871853
    assert summary["product_accuracy_parity_ligand_ranking_pr_auc_ci_low"] == 0.761168
    assert summary["product_accuracy_parity_ligand_ranking_topk_hit_rate"] == 1.0
    assert summary["parallel_product_action_ids"] == [
        "product_accuracy_parity:close_ligand_ranking_claim_scope"
    ]

    action = payload["rows"][0]
    assert action["lane_id"] == "product_accuracy_parity"
    assert action["action_type"] == "close_ligand_ranking_claim_scope"
    assert action["status"] == "required"
    assert action["required_input"] == "ACCURACY:ligand_ranking"
    assert action["artifact_path"] == "runs/accuracy_parity_scorecard_current.json"
    assert action["accuracy_parity_ligand_ranking_blocker_count"] == 1
    assert action["accuracy_parity_ligand_ranking_metric_thresholds_pass"] is True
    assert action["accuracy_parity_ligand_ranking_metric_blocker_count"] == 0
    assert action["accuracy_parity_ligand_ranking_metric_blockers"] == ""
    assert action["accuracy_parity_ligand_ranking_claim_scope_lock_only"] is True
    assert action["accuracy_parity_ligand_ranking_pr_auc_threshold"] == 0.55
    assert action["accuracy_parity_ligand_ranking_pr_auc_ci_low_threshold"] == 0.45
    assert action["accuracy_parity_ligand_ranking_topk_hit_rate_threshold"] == 0.5
    assert action["accuracy_parity_ligand_ranking_positive_count"] == 34
    assert action["accuracy_parity_ligand_ranking_core_claim_safe"] is False
    assert "ranking_pr_auc=0.871853" in action["reason"]
    assert "broad_gpcr_claim_not_allowed" in action["reason"]
    assert "metric_thresholds_pass=True" in action["reason"]
    assert "claim_scope_lock_only=True" in action["reason"]
    assert "target-held-out broad-scope review" in action["recommended_action"]


def test_goal_operator_action_board_summary_points_to_primary_product_ai_action() -> None:
    payload = mod.build_action_board(
        rollup_packet={},
        product_preflight_packet={},
        product_bundle_contract_packet={},
        product_delivery_evidence_packet={},
        product_goal_completion_audit_packet=_product_goal_completion_audit_registry_action(),
        product_scope_breadth_evidence_receipt_packet=_scope_breadth_evidence_receipt(),
        engine_refinement_claim_evidence_receipt_packet=_engine_refinement_claim_evidence_receipt(),
        engine_refinement_claim_evidence_priority_packet=(
            _engine_refinement_claim_evidence_priority_packet()
        ),
        cameo_input_kit_packet={},
        cameo_input_validation_packet={},
        cameo_repair_preflight_packet={},
        transition_cleanup_preflight_packet={},
        ligand_cleanup_preflight_packet={},
        cleanup_completion_gate_packet=_cleanup_completion_gate_ready(),
        goal_release_decision_gate_packet=_goal_release_decision_gate(),
    )

    summary = payload["summary"]
    assert summary["primary_action_id"] == "product_ai_production:complete_residual_registry_guarded_promotion"
    assert summary["top_action_id"] == summary["primary_action_id"]
    assert summary["primary_action_priority"] == 0
    assert summary["primary_action_lane_id"] == "product_ai_production"
    assert summary["primary_action_type"] == "complete_residual_registry_guarded_promotion"
    assert summary["primary_action_status"] == "required"
    assert summary["primary_action_required_input"] == (
        "production_promotion_allowed;customer_facing_auto_correction_allowed;"
        "customer_facing_score_mutation_allowed;customer_facing_ranking_mutation_allowed;"
        "default_residual_mode;trained_model_checkpoint_count"
    )
    assert "build_residual_model_registry.py" in summary["primary_action_command"]
    assert "Register or promote a trained preflight-ready production checkpoint" in summary[
        "primary_action_recommended_action"
    ]
    assert summary["product_goal_engine_refinement_claim_promotion_ready"] is False
    assert summary["product_goal_release_blocker_fail_count"] == 2
    assert summary["product_goal_release_blocker_requirement_ids"] == [
        "R8_full_scope_claim_closure",
        "R9_engine_refinement_claim_promotion",
    ]
    assert summary["product_goal_primary_release_blocker_requirement_id"] == "R8_full_scope_claim_closure"
    assert summary["product_goal_primary_release_blocker_tier"] == "full_commercial_scope"
    assert summary["product_goal_primary_release_blocker"] == "full_scope_claim_closure_not_ready"
    assert summary["primary_release_blocker_action_id"] == (
        "product_scope_expansion:resolve_full_scope_breadth_evidence_receipt"
    )
    assert summary["primary_release_blocker_action_required_input"] == (
        "config/product_scope_breadth_evidence_receipt_current.csv"
    )
    assert "full-scope evidence receipt rows" in summary[
        "primary_release_blocker_action_recommended_action"
    ]
    assert summary["product_scope_breadth_evidence_priority_action_id"] == (
        "product_scope_expansion:curate_scope_evidence_priority_item"
    )
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
    assert summary["product_scope_breadth_evidence_priority_receipt_action_id"] == (
        "product_scope_expansion:resolve_full_scope_breadth_evidence_receipt"
    )
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
    assert summary["engine_refinement_priority_action_id"] == ""
    assert summary["engine_refinement_priority_top_item_id"] == "public_benchmark_gate_not_ready"
    assert summary["engine_refinement_priority_top_required_input"] == (
        "config/refine_tier_public_benchmark_statistical_support_"
        "metric_source_payload_operator_receipt_current.csv"
    )
    assert summary["engine_refinement_priority_metric_source_payload_receipt_csv"] == (
        "config/refine_tier_public_benchmark_statistical_support_"
        "metric_source_payload_operator_receipt_current.csv"
    )
    assert summary[
        "engine_refinement_priority_metric_source_payload_receipt_approval_token_required"
    ] == "APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS"
    assert summary["engine_refinement_priority_metric_source_payload_receipt_blocked_row_count"] == 51
    assert summary["engine_refinement_priority_claim_evidence_receipt_csv"] == (
        "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
    )
    assert summary["full_commercial_release_allowed"] is False
    assert summary["full_commercial_release_blocker_count"] == 3
    assert summary["full_commercial_release_blocker_ids"] == [
        "R8_full_scope_claim_closure",
        "R9_engine_refinement_claim_promotion",
        "ACCURACY:ligand_ranking",
    ]
    assert "R8/R9 receipt CSVs" in summary["full_commercial_release_next_required_step"]
    assert summary["science_claim_promotion_gap_closure_open_gap_ids"] == []
    assert "All science claim promotion boundary gaps are closed" in summary[
        "science_claim_promotion_gap_closure_current_next_action"
    ]
    assert summary["accuracy_parity_ligand_ranking_status"] == "restricted_pass"
    assert summary["accuracy_parity_ligand_ranking_pr_auc"] == 0.871853
    assert summary["accuracy_parity_ligand_ranking_pr_auc_ci_low"] == 0.761168
    assert summary["accuracy_parity_ligand_ranking_topk_hit_rate"] == 1.0
    assert "target-held-out broad-scope review" in summary[
        "accuracy_parity_ligand_ranking_next_required_step"
    ]
    assert summary["primary_full_commercial_release_blocker_id"] == "R8_full_scope_claim_closure"
    assert summary["primary_full_commercial_release_blocker_requirement_id"] == (
        "R8_full_scope_claim_closure"
    )
    assert summary["primary_full_commercial_release_blocker_tier"] == "full_commercial_scope"
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
    assert "placeholder receipt rows" in summary[
        "primary_full_commercial_release_blocker_next_required_step"
    ]
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
    assert summary["product_goal_engine_refinement_claim_promotion_blocker_count"] == 6
    assert summary["product_goal_engine_refinement_claim_promotion_action_row_count"] == 6
    assert (
        "public_benchmark_gate_not_ready"
        in summary["product_goal_engine_refinement_claim_promotion_blockers"]
    )
    assert (
        summary["product_goal_engine_refinement_claim_promotion_action_board_csv"]
        == "runs/engine_refinement_claim_promotion_action_board_current.csv"
    )
    assert summary["product_goal_engine_refinement_claim_evidence_receipt_ready"] is False
    assert summary["product_goal_engine_refinement_claim_evidence_receipt_blocked_row_count"] == 6
    assert (
        summary["product_goal_engine_refinement_claim_evidence_receipt_artifact"]
        == "runs/engine_refinement_claim_evidence_receipt_current.json"
    )
    assert summary[
        "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_blocker_id"
    ] == "public_benchmark_gate_not_ready"
    assert summary[
        "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_evidence_artifact"
    ] == "OPERATOR_FILL_LOCAL_EVIDENCE_JSON"
    assert summary[
        "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_expected_evidence_status"
    ] == "refine_tier_public_benchmark_ready"
    assert summary[
        "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_missing_true_fields"
    ] == ["claim_grade_public_benchmark_ready"]
    assert "operator_placeholders_unfilled" in summary[
        "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_row_blockers"
    ]
    assert summary[
        "product_goal_engine_refinement_claim_evidence_receipt_most_common_row_blocker"
    ] == "operator_placeholders_unfilled"
    assert summary["product_goal_scope_breadth_evidence_receipt_ready"] is False
    assert summary["product_goal_scope_breadth_evidence_receipt_blocked_row_count"] == 6
    assert (
        summary["product_goal_scope_breadth_evidence_receipt_artifact"]
        == "runs/product_scope_breadth_evidence_receipt_current.json"
    )
    assert summary["product_goal_scope_transporter_top_claim_safe_blocker"] == (
        "direct_pool_exists_but_named_candidate_identity_not_operator_confirmed"
    )
    assert summary["product_goal_scope_transporter_top_operator_next_verdict"] == (
        "manual_match_candidate_to_exact_source_then_sync_reference_split_meta"
    )
    assert summary["product_goal_scope_next_operator_completion_item_id"] == "AQP1.core_binder_01"
    assert summary["product_goal_scope_next_operator_completion_intake_mode"] == "local_crosscheck_triage"
    assert summary["product_goal_scope_next_operator_completion_required_evidence_type"] == (
        "exact_transporter_target_pair_quantitative_binder_kcal"
    )
    assert summary["product_goal_scope_next_operator_completion_transporter_claim_safe_blocker"] == (
        "direct_pool_exists_but_named_candidate_identity_not_operator_confirmed"
    )
    assert summary[
        "product_goal_scope_next_operator_completion_transporter_operator_next_verdict"
    ] == "manual_match_candidate_to_exact_source_then_sync_reference_split_meta"
    assert summary[
        "product_goal_scope_next_operator_completion_transporter_best_evidence_source_file"
    ] == "runs/life_science_skill_crosscheck/chembl_activity_aqp1_target_current_recheck.json"
    assert summary[
        "product_goal_scope_next_operator_completion_transporter_best_evidence_activity_type"
    ] == "KD"
    assert summary[
        "product_goal_scope_next_operator_completion_transporter_best_evidence_value"
    ] == "174000.0"
    assert summary["product_goal_scope_next_operator_completion_transporter_best_evidence_units"] == "nM"
    assert summary[
        "product_goal_scope_next_operator_completion_transporter_best_evidence_document_id"
    ] == "CHEMBL6182835"
    assert summary["product_goal_scope_transporter_p0_return_bundle_required_artifact_count"] == 5
    assert summary["product_goal_scope_transporter_p0_return_bundle_blocker_count"] == 5
    assert summary["product_goal_scope_transporter_p0_return_bundle_next_artifact_id"] == (
        "operator_review_row"
    )
    assert summary["product_goal_scope_transporter_p0_return_bundle_next_artifact_path"] == (
        "runs/transporter_manual_review_intake_template_current.csv"
    )
    assert summary["product_goal_scope_transporter_p0_operator_validation_candidate_ready"] is True
    assert summary["product_goal_scope_transporter_p0_operator_validation_candidate_status"] == (
        "operator_validation_required"
    )
    assert summary[
        "product_goal_scope_transporter_p0_operator_validation_candidate_ligand_external_identifier"
    ] == "CHEMBL20"
    assert summary[
        "product_goal_scope_transporter_p0_operator_validation_candidate_reference_binding_kcal_mol"
    ] == "-5.13"
    assert summary["product_goal_scope_transporter_p0_operator_validation_candidate_blocker"] == (
        "data_validity_outside_typical_range_and_assay_origin_unknown"
    )
    assert summary[
        "product_goal_scope_transporter_p0_operator_validation_candidate_required_decision_field_count"
    ] == 6
    assert summary[
        "product_goal_scope_transporter_p0_operator_validation_candidate_placeholder_count"
    ] == 6
    assert summary[
        "product_goal_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id"
    ] == "direct_binding_evidence_missing"
    assert summary[
        "product_goal_scope_breadth_evidence_receipt_first_blocked_evidence_artifact"
    ] == "OPERATOR_FILL_LOCAL_EVIDENCE_JSON"
    assert summary[
        "product_goal_scope_breadth_evidence_receipt_first_blocked_expected_evidence_status"
    ] == "product_scope_transporter_direct_binding_evidence_ready"
    assert summary[
        "product_goal_scope_breadth_evidence_receipt_first_blocked_missing_true_fields"
    ] == ["transporter_direct_binding_evidence_ready"]
    assert "operator_placeholders_unfilled" in summary[
        "product_goal_scope_breadth_evidence_receipt_first_blocked_row_blockers"
    ]
    assert summary[
        "product_goal_scope_breadth_evidence_receipt_most_common_row_blocker"
    ] == "operator_placeholders_unfilled"
    assert "curated public benchmark rows" in summary[
        "product_goal_engine_refinement_claim_promotion_next_required_step"
    ]
    assert summary["operator_input_required_count"] == 3
    assert summary["blocked_or_required_action_count"] == 2
    assert summary["review_required_count"] == 1
    assert summary["parallel_product_action_count"] == 2
    assert summary["parallel_product_action_ids"] == [
        "product_scope_expansion:curate_scope_evidence_priority_item",
        "product_scope_expansion:resolve_full_scope_breadth_evidence_receipt",
    ]
    assert summary["first_parallel_product_action_id"] == (
        "product_scope_expansion:curate_scope_evidence_priority_item"
    )
    assert summary["first_parallel_product_action_required_input"] == "AQP1.core_binder_01"
    assert summary["first_parallel_product_action_primary_action_id"] == summary["primary_action_id"]
    assert "does not require production GPU execution" in summary[
        "first_parallel_product_action_precondition"
    ]
    priority_action = next(
        row for row in payload["rows"] if row["action_type"] == "curate_scope_evidence_priority_item"
    )
    assert priority_action["scope_priority_top_required_evidence_type"] == (
        "exact_transporter_target_pair_quantitative_binder_kcal"
    )
    assert priority_action["scope_priority_top_review_template_artifact"] == (
        "runs/transporter_manual_review_intake_template_current.json"
    )
    assert priority_action["scope_priority_top_apply_gate_artifact"] == (
        "runs/transporter_binder_promotion_gate_current.json"
    )


def test_goal_operator_action_board_collects_blockers_approvals_and_review_rows(tmp_path: Path) -> None:
    payload = mod.build_action_board(
        rollup_packet=_rollup(),
        product_preflight_packet=_product_preflight(),
        product_bundle_contract_packet=_bundle_contract(),
        product_delivery_evidence_packet=_delivery_evidence(),
        product_pilot_packet=_product_pilot_packet(),
        product_execution_approval_gate_packet=_product_execution_approval_gate(),
        product_license_decision_gate_packet=_product_license_decision_gate(),
        product_license_decision_packet=_product_license_decision_packet(),
        product_release_operations_dossier_packet=_product_release_operations_dossier(),
        product_cli_status_packet=_product_cli_status(),
        goal_release_decision_gate_packet=_goal_release_decision_gate(),
        goal_release_burndown_work_order_packet=_goal_release_burndown_work_order(),
        goal_operator_intake_kit_packet=_goal_operator_intake_kit(),
        cameo_validation_operations_dossier_packet=_cameo_validation_operations_dossier(),
        cameo_cli_status_packet=_cameo_cli_status(),
        cameo_official_results_intake_gate_packet=_cameo_official_results_intake_gate(),
        cameo_public_registration_approval_gate_packet=_cameo_public_registration_approval_gate(),
        cameo_input_kit_packet=_cameo_input_kit(tmp_path),
        cameo_input_validation_packet=_cameo_input_validation(),
        cameo_repair_preflight_packet=_cameo_repair_preflight(),
        transition_cleanup_preflight_packet=_transition_preflight(),
        ligand_cleanup_preflight_packet=_ligand_preflight(),
        large_cleanup_drilldown_packet=_large_cleanup_drilldown(),
        protected_cleanup_review_packet=_protected_cleanup_review(),
        protected_ligand_heavy_deep_review_packet=_protected_ligand_heavy_deep_review(),
        protected_cleanup_policy_decision_gate_packet=_protected_cleanup_policy_decision_gate(),
        cleanup_cli_status_packet=_cleanup_cli_status(),
        cleanup_snapshot_preflight_packet=_cleanup_snapshot_preflight(),
        cleanup_payload_manifest_lock_packet=_cleanup_payload_manifest_lock(),
        cleanup_postcheck_contract_packet=_cleanup_postcheck_contract(),
        cleanup_execution_approval_dossier_packet=_cleanup_execution_approval_dossier(),
        cleanup_execution_approval_gate_packet=_cleanup_execution_approval_gate(),
        cleanup_completion_gate_packet=_cleanup_completion_gate(),
    )

    rows = payload["rows"]
    assert payload["summary"]["status"] == "operator_actions_required"
    assert payload["summary"]["source_rollup_status"] == "blocked_goal_readiness"
    assert payload["summary"]["approval_required_count"] == 3
    assert payload["summary"]["review_required_count"] == 0
    assert payload["summary"]["approval_reclaim_size_gb"] == 38.371
    assert payload["summary"]["large_review_size_gb"] == 0
    assert payload["summary"]["large_cleanup_review_resolved_by_drilldown_count"] == 1
    assert payload["summary"]["large_cleanup_drilldown_status"] == "large_cleanup_surface_drilldown_ready"
    assert payload["summary"]["large_cleanup_known_payload_size_gb"] == 406.131
    assert payload["summary"]["large_cleanup_dry_run_delete_payload_size_gb"] == 6.012
    assert payload["summary"]["large_cleanup_dry_run_protected_payload_size_gb"] == 396.794
    assert payload["summary"]["protected_cleanup_review_status"] == "protected_cleanup_payload_review_ready"
    assert payload["summary"]["protected_cleanup_payload_size_gb"] == 396.794
    assert payload["summary"]["protected_cleanup_policy_change_required_count"] == 1
    assert payload["summary"]["protected_cleanup_approval_promoted_count"] == 0
    assert payload["summary"]["protected_ligand_heavy_deep_review_status"] == "protected_ligand_heavy_payload_deep_review_ready"
    assert payload["summary"]["protected_ligand_heavy_known_payload_child_count"] == 2
    assert payload["summary"]["protected_ligand_heavy_known_payload_child_size_gb"] == 396.794
    assert payload["summary"]["protected_ligand_heavy_preservation_sibling_count"] == 2
    assert payload["summary"]["protected_ligand_heavy_policy_change_required_for_deletion_count"] == 2
    assert payload["summary"]["protected_cleanup_policy_decision_gate_status"] == "blocked_protected_cleanup_policy_decision_gate"
    assert payload["summary"]["protected_cleanup_policy_resolved"] is False
    assert payload["summary"]["protected_cleanup_policy_awaiting_decision_row_count"] == 2
    assert payload["summary"]["protected_cleanup_policy_change_requested_row_count"] == 0
    assert payload["summary"]["protected_cleanup_policy_decision_blocked_row_count"] == 2
    assert payload["summary"]["cleanup_cli_status_set_status"] == "blocked_cleanup_cli_status_set"
    assert payload["summary"]["cleanup_cli_command_count"] == 16
    assert payload["summary"]["cleanup_cli_blocked_or_missing_command_count"] == 3
    assert payload["summary"]["cleanup_cli_approval_required_command_count"] == 2
    assert payload["summary"]["cleanup_cli_approval_token_count"] == 4
    assert payload["summary"]["cleanup_cli_approval_tokens_required"] == [
        "APPROVE_ARCHIVE_LEGACY_RUNS",
        "APPROVE_DELETE_REGENERABLE_LOCAL_ARTIFACTS",
        "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS",
        "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS",
    ]
    assert payload["summary"]["cleanup_cli_approval_reclaim_size_gb"] == 49.216
    assert payload["summary"]["cleanup_cli_authorized_reclaim_size_gb"] == 0
    assert payload["summary"]["cleanup_cli_awaiting_operator_approval_row_count"] == 5
    assert payload["summary"]["cleanup_cli_postcheck_contract_ready"] is True
    assert payload["summary"]["cleanup_cli_postcheck_row_count"] == 7
    assert payload["summary"]["cleanup_cli_postcheck_blocked_row_count"] == 0
    assert payload["summary"]["cleanup_cli_protected_payload_size_gb"] == 396.794
    assert payload["summary"]["cleanup_cli_protected_policy_change_required_count"] == 2
    assert payload["summary"]["cleanup_cli_protected_policy_resolved"] is False
    assert payload["summary"]["cleanup_snapshot_preflight_status"] == "blocked_cleanup_snapshot_preflight"
    assert payload["summary"]["cleanup_snapshot_blocked_row_count"] == 2
    assert payload["summary"]["cleanup_snapshot_missing_count"] == 2
    assert payload["summary"]["cleanup_snapshot_required_count"] == 2
    assert payload["summary"]["cleanup_snapshot_approval_gated_size_gb"] == 49.216
    assert payload["summary"]["cleanup_payload_manifest_lock_status"] == "cleanup_payload_manifest_lock_ready"
    assert payload["summary"]["cleanup_payload_manifest_lock_row_count"] == 7
    assert payload["summary"]["cleanup_payload_manifest_lock_blocked_row_count"] == 0
    assert payload["summary"]["cleanup_payload_manifest_fingerprint_sha256"] == "b" * 64
    assert payload["summary"]["cleanup_postcheck_contract_status"] == "cleanup_postcheck_contract_ready"
    assert payload["summary"]["cleanup_postcheck_contract_ready"] is True
    assert payload["summary"]["cleanup_postcheck_row_count"] == 7
    assert payload["summary"]["cleanup_postcheck_approval_row_count"] == 5
    assert payload["summary"]["cleanup_postcheck_protected_policy_row_count"] == 2
    assert payload["summary"]["cleanup_postcheck_blocked_row_count"] == 0
    assert payload["summary"]["cleanup_postcheck_global_refresh_command_count"] == 9
    assert payload["summary"]["cleanup_execution_approval_dossier_status"] == "cleanup_execution_approval_dossier_ready"
    assert payload["summary"]["cleanup_execution_approval_dossier_approval_row_count"] == 5
    assert payload["summary"]["cleanup_execution_approval_dossier_snapshot_backed_approval_row_count"] == 2
    assert payload["summary"]["cleanup_execution_approval_dossier_snapshot_artifact_count"] == 2
    assert payload["summary"]["cleanup_execution_approval_dossier_snapshot_ready_count"] == 2
    assert payload["summary"]["cleanup_execution_approval_dossier_snapshot_listing_truncated_count"] == 1
    assert payload["summary"]["cleanup_execution_approval_dossier_snapshot_total_entry_count"] == 201224
    assert payload["summary"]["cleanup_execution_approval_dossier_snapshot_set_fingerprint_sha256"] == "c" * 64
    assert payload["summary"]["cleanup_execution_approval_gate_status"] == "blocked_cleanup_execution_operator_approval_gate"
    assert payload["summary"]["cleanup_execution_authorized_row_count"] == 0
    assert payload["summary"]["cleanup_execution_awaiting_operator_approval_row_count"] == 5
    assert payload["summary"]["cleanup_execution_blocked_row_count"] == 5
    assert payload["summary"]["cleanup_execution_authorized_reclaim_size_gb"] == 0
    assert payload["summary"]["cleanup_execution_total_reclaim_size_gb"] == 49.216
    assert payload["summary"]["cleanup_execution_operator_approval_csv_present"] is False
    assert payload["summary"]["cleanup_completion_gate_status"] == "blocked_cleanup_completion_gate"
    assert payload["summary"]["cleanup_completion_complete"] is False
    assert payload["summary"]["cleanup_completion_blocked_stage_count"] == 4
    assert payload["summary"]["cleanup_completion_approval_ready"] is False
    assert payload["summary"]["cleanup_completion_transition_cleanup_complete"] is False
    assert payload["summary"]["cleanup_completion_ligand_heavy_cleanup_complete"] is False
    assert payload["summary"]["cleanup_completion_protected_policy_resolved"] is False
    assert payload["summary"]["goal_release_decision_gate_status"] == "blocked_goal_release_decision"
    assert payload["summary"]["goal_release_allowed"] is False
    assert payload["summary"]["goal_release_blocker_count"] == 12
    assert payload["summary"]["goal_release_check_count"] == 15
    assert payload["summary"]["commercial_independent_product_ready"] is False
    assert payload["summary"]["cameo_architecture_validation_ready"] is False
    assert payload["summary"]["cleanup_objective_ready"] is False
    assert payload["summary"]["source_goal_api_surface_contract_status"] == "goal_api_surface_contract_ready"
    assert payload["summary"]["goal_api_surface_ready"] is True
    assert payload["summary"]["goal_api_surface_check_count"] == 7
    assert payload["summary"]["goal_api_surface_blocker_count"] == 0
    assert payload["summary"]["goal_api_surface_missing_endpoint_count"] == 0
    assert payload["summary"]["goal_api_surface_missing_status_key_count"] == 0
    assert payload["summary"]["goal_release_burndown_work_order_status"] == "goal_release_burndown_work_order_ready"
    assert payload["summary"]["goal_release_burndown_release_blocker_check_count"] == 12
    assert payload["summary"]["goal_release_burndown_work_item_count"] == 12
    assert payload["summary"]["goal_release_burndown_approval_required_item_count"] == 7
    assert payload["summary"]["goal_release_burndown_operator_input_required_item_count"] == 5
    assert payload["summary"]["goal_release_burndown_operator_input_required_work_item_count"] == 0
    assert payload["summary"]["goal_release_burndown_official_results_required_item_count"] == 2
    assert payload["summary"]["goal_release_burndown_policy_decision_required_item_count"] == 1
    assert payload["summary"]["goal_release_burndown_postcheck_required_item_count"] == 0
    assert payload["summary"]["goal_release_burndown_approval_token_count"] == 5
    assert payload["summary"]["goal_operator_intake_kit_status"] == "goal_operator_intake_kit_ready"
    assert payload["summary"]["goal_operator_intake_kit_entry_count"] == 7
    assert payload["summary"]["goal_operator_intake_kit_release_burndown_linked_entry_count"] == 6
    assert payload["summary"]["goal_operator_intake_kit_operator_input_required_count"] == 7
    assert payload["summary"]["goal_operator_intake_kit_current_action_required_count"] == 5
    assert payload["summary"]["goal_operator_intake_kit_deferred_operator_input_count"] == 2
    assert payload["summary"]["goal_operator_intake_kit_template_copied_count"] == 6
    assert payload["summary"]["goal_operator_intake_kit_template_missing_count"] == 0
    assert payload["summary"]["goal_operator_intake_kit_approval_token_count"] == 9
    assert payload["summary"]["goal_operator_intake_kit_current_action_approval_token_count"] == 5
    assert payload["summary"]["goal_operator_intake_kit_current_action_approval_tokens"] == [
        "APPROVE_API_DEPENDENCY_INSTALL",
        "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS",
        "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS",
        "APPROVE_PRODUCT_DOCKING_EXECUTION",
        "APPROVE_PRODUCT_LICENSE_FILE_CREATION",
    ]
    assert (
        payload["summary"]["goal_operator_intake_kit_product_commercial_independence_status"]
        == "blocked_product_commercial_independence_gate"
    )
    assert payload["summary"]["goal_operator_intake_kit_product_commercial_independent_claim_allowed"] is False
    assert payload["summary"]["goal_operator_intake_kit_product_commercial_independence_blocker_count"] == 1
    assert payload["summary"]["goal_operator_intake_kit_product_commercial_independence_license_present"] is False
    assert payload["summary"]["goal_operator_intake_kit_goal_api_surface_contract_status"] == "goal_api_surface_contract_ready"
    assert payload["summary"]["goal_operator_intake_kit_goal_api_surface_ready"] is True
    assert payload["summary"]["goal_operator_intake_kit_goal_api_surface_check_count"] == 7
    assert payload["summary"]["goal_operator_intake_kit_goal_api_surface_blocker_count"] == 0
    assert payload["summary"]["goal_operator_intake_kit_goal_api_status_endpoint"] == "/goal/status"
    assert payload["summary"]["goal_operator_intake_kit_goal_api_contract_endpoint"] == "/goal/api-contract"
    assert payload["summary"]["cameo_validation_operations_dossier_status"] == "blocked_cameo_validation_operations_dossier"
    assert payload["summary"]["cameo_validation_operations_blocked_stage_count"] == 5
    assert payload["summary"]["cameo_validation_operations_approval_required_stage_count"] == 1
    assert payload["summary"]["cameo_validation_operations_operator_input_required_count"] == 3
    assert payload["summary"]["cameo_validation_operations_approval_token_count"] == 3
    assert payload["summary"]["cameo_validation_operations_official_result_required"] is True
    assert payload["summary"]["cameo_validation_operations_official_results_intake_status"] == "blocked_cameo_official_results_intake"
    assert payload["summary"]["cameo_validation_operations_official_results_intake_ready"] is False
    assert payload["summary"]["cameo_validation_operations_official_results_intake_blocker_count"] == 2
    assert payload["summary"]["cameo_validation_operations_public_registration_allowed"] is False
    assert payload["summary"]["cameo_cli_status_set_status"] == "blocked_cameo_cli_status_set"
    assert payload["summary"]["cameo_cli_command_count"] == 11
    assert payload["summary"]["cameo_cli_blocked_or_missing_command_count"] == 7
    assert payload["summary"]["cameo_cli_approval_required_command_count"] == 2
    assert payload["summary"]["cameo_cli_approval_token_count"] == 3
    assert payload["summary"]["cameo_cli_approval_tokens_required"] == [
        "APPROVE_API_DEPENDENCY_INSTALL",
        "APPROVE_CAMEO_OUTBOUND_EMAIL",
        "APPROVE_CAMEO_SERVER_REGISTRATION",
    ]
    assert payload["summary"]["cameo_cli_official_result_required"] is True
    assert payload["summary"]["cameo_cli_official_results_result_row_count"] == 0
    assert payload["summary"]["cameo_cli_official_results_accepted_count"] == 0
    assert payload["summary"]["cameo_cli_official_model1_result_ready"] is False
    assert payload["summary"]["cameo_cli_evidence_integrity_ready"] is True
    assert payload["summary"]["cameo_cli_official_results_pending_honest"] is True
    assert payload["summary"]["cameo_cli_no_local_native_accuracy_substitution"] is True
    assert payload["summary"]["cameo_cli_api_install_approval_required"] is True
    assert payload["summary"]["cameo_cli_api_dependency_status"] == "blocked_cameo_api_dependency_readiness"
    assert payload["summary"]["cameo_cli_receiver_smoke_status"] == "blocked_cameo_receiver_smoke"
    assert payload["summary"]["cameo_cli_public_registration_authorized"] is False
    assert payload["summary"]["cameo_cli_registration_awaiting_operator_approval_row_count"] == 1
    assert payload["summary"]["cameo_official_results_intake_gate_status"] == "blocked_cameo_official_results_intake"
    assert payload["summary"]["cameo_official_results_intake_result_row_count"] == 0
    assert payload["summary"]["cameo_official_results_intake_accepted_count"] == 0
    assert payload["summary"]["cameo_official_results_intake_rejected_count"] == 0
    assert payload["summary"]["cameo_official_results_intake_model1_ready"] is False
    assert payload["summary"]["cameo_official_results_intake_blocker_count"] == 2
    assert payload["summary"]["cameo_official_results_intake_blocker_codes"] == [
        "official_result_required_columns_missing",
        "official_result_rows_missing",
    ]
    assert payload["summary"]["cameo_official_results_intake_missing_required_columns"] == [
        "target_id",
        "candidate_id",
        "cameo_model_rank",
    ]
    assert payload["summary"]["cameo_official_results_operator_intake_csv"] == "runs/cameo_official_results_operator_intake.csv"
    assert payload["summary"]["cameo_public_registration_approval_gate_status"] == "blocked_cameo_public_registration_approval_gate"
    assert payload["summary"]["cameo_public_registration_authorized_for_registration_review"] is False
    assert payload["summary"]["cameo_public_registration_operator_approval_csv_present"] is False
    assert payload["summary"]["cameo_public_registration_blocked_row_count"] == 1
    assert payload["summary"]["product_pilot_packet_status"] == "product_pilot_packet_preflight_ready"
    assert payload["summary"]["product_pilot_delivery_ready"] is False
    assert payload["summary"]["product_execution_approval_gate_status"] == "blocked_product_execution_operator_approval_gate"
    assert payload["summary"]["product_execution_authorized_for_execution"] is False
    assert payload["summary"]["product_execution_authorized_row_count"] == 0
    assert payload["summary"]["product_execution_awaiting_operator_approval_row_count"] == 1
    assert payload["summary"]["product_execution_blocked_row_count"] == 1
    assert payload["summary"]["product_execution_operator_approval_csv_present"] is False
    assert payload["summary"]["product_license_decision_gate_status"] == "blocked_product_license_decision_gate"
    assert payload["summary"]["product_license_decision_packet_status"] == "product_license_decision_packet_ready"
    assert payload["summary"]["product_license_decision_option_count"] == 5
    assert payload["summary"]["product_license_decision_packet_ready"] is True
    assert payload["summary"]["product_license_authorized_for_file_creation_review"] is False
    assert payload["summary"]["product_license_operator_intake_csv_present"] is False
    assert payload["summary"]["product_license_blocker_count"] == 4
    assert payload["summary"]["product_cli_status_set_status"] == "blocked_product_cli_status_set"
    assert payload["summary"]["product_cli_command_count"] == 9
    assert payload["summary"]["product_cli_blocked_or_missing_command_count"] == 5
    assert payload["summary"]["product_cli_approval_token_count"] == 2
    assert payload["summary"]["product_cli_approval_tokens_required"] == [
        "APPROVE_PRODUCT_DOCKING_EXECUTION",
        "APPROVE_PRODUCT_LICENSE_FILE_CREATION",
    ]
    assert payload["summary"]["product_cli_operations_stage_count"] == 9
    assert payload["summary"]["product_cli_operations_blocked_stage_count"] == 4
    assert payload["summary"]["product_cli_operations_approval_required_stage_count"] == 2
    assert payload["summary"]["product_cli_capability_surface_ready"] is True
    assert payload["summary"]["product_cli_operational_quality_ready"] is True
    assert payload["summary"]["product_cli_structure_analysis_capability_ready"] is True
    assert payload["summary"]["product_cli_ligand_docking_capability_ready"] is True
    assert payload["summary"]["product_cli_product_api_surface_ready"] is True
    assert payload["summary"]["product_cli_architecture_release_ready"] is False
    assert payload["summary"]["product_cli_commercial_independence_ready"] is False
    assert payload["summary"]["product_cli_license_present"] is False
    assert payload["summary"]["product_cli_license_authorized_for_file_creation_review"] is False
    assert payload["summary"]["product_cli_authorized_for_execution"] is False
    assert payload["summary"]["product_cli_bundle_assembled"] is False
    assert payload["summary"]["product_cli_bundle_validation_passed"] is False
    assert payload["summary"]["product_cli_delivery_ready_claim_allowed"] is False
    assert payload["summary"]["product_cli_pilot_delivery_ready"] is False
    assert payload["summary"]["product_release_operations_dossier_status"] == "blocked_product_release_operations_dossier"
    assert payload["summary"]["product_release_operations_blocked_stage_count"] == 4
    assert payload["summary"]["product_release_operations_approval_required_stage_count"] == 2
    assert payload["summary"]["product_release_operations_capability_surface_ready"] is True
    assert payload["summary"]["product_release_operations_architecture_contract_ready"] is False
    assert payload["summary"]["product_release_operations_architecture_release_ready"] is False
    assert payload["summary"]["product_release_operations_architecture_blocked_lane_count"] == 1
    assert payload["summary"]["product_release_operations_architecture_approval_required_lane_count"] == 2
    assert payload["summary"]["product_release_operations_cameo_architecture_validation_ready"] is False
    assert payload["summary"]["product_release_operations_cameo_official_validation_evidence_ready"] is False
    assert payload["summary"]["product_release_operations_cameo_receiver_smoke_ready"] is False
    assert payload["summary"]["product_release_operations_cameo_receiver_smoke_status"] == "blocked_cameo_receiver_smoke"
    assert payload["summary"]["product_release_operations_cameo_api_dependency_ready"] is False
    assert payload["summary"]["product_release_operations_cameo_api_dependency_status"] == "blocked_cameo_api_dependency_readiness"
    assert payload["summary"]["product_release_operations_cameo_public_registration_allowed"] is False
    assert payload["summary"]["product_release_operations_cameo_public_registration_blocker_count"] == 4
    assert payload["summary"]["product_release_operations_cameo_registration_approval_token_count"] == 2
    assert payload["summary"]["product_release_operations_cameo_registration_approval_tokens_required"] == [
        "APPROVE_CAMEO_SERVER_REGISTRATION",
        "APPROVE_CAMEO_OUTBOUND_EMAIL",
    ]
    assert payload["summary"]["product_release_operations_cleanup_postcheck_contract_ready"] is True
    assert payload["summary"]["product_release_operations_structure_analysis_capability_ready"] is True
    assert payload["summary"]["product_release_operations_ligand_docking_capability_ready"] is True
    assert payload["summary"]["product_release_operations_api_surface_ready"] is True
    assert payload["summary"]["product_release_operations_commercial_independence_ready"] is False
    assert payload["summary"]["product_release_operations_license_present"] is False
    assert payload["summary"]["product_release_operations_license_decision_packet_ready"] is True
    assert payload["summary"]["product_release_operations_license_decision_option_count"] == 5
    assert payload["summary"]["product_release_operations_license_authorized_for_file_creation_review"] is False
    assert payload["summary"]["product_release_operations_authorized_for_execution"] is False
    assert payload["summary"]["product_release_operations_bundle_assembled"] is False
    assert payload["summary"]["product_release_operations_bundle_validation_passed"] is False
    assert payload["summary"]["product_release_operations_delivery_ready_claim_allowed"] is False
    assert payload["summary"]["product_release_operations_pilot_delivery_ready"] is False
    assert payload["summary"]["action_executed"] is False
    assert payload["summary"]["delete_executed"] is False
    assert payload["summary"]["external_state_mutated"] is False
    assert any(row["action_type"] == "fill_or_repair_cameo_operator_input" for row in rows)
    assert any(row["action_type"] == "fill_cameo_official_results_intake" for row in rows)
    official_action = next(row for row in rows if row["action_type"] == "fill_cameo_official_results_intake")
    assert official_action["official_results_operator_intake_csv"] == "runs/cameo_official_results_operator_intake.csv"
    assert official_action["official_results_missing_required_columns"] == "target_id;candidate_id;cameo_model_rank"
    assert official_action["official_results_blocker_codes"] == "official_result_required_columns_missing;official_result_rows_missing"
    assert "missing_required_columns=target_id;candidate_id;cameo_model_rank" in official_action["reason"]
    assert any(row["action_type"] == "repair_cameo_rebuild_command" for row in rows)
    assert any(row["approval_token"] == "APPROVE_PRODUCT_DOCKING_EXECUTION" for row in rows)
    assert any("delivery evidence contract" in row["reason"] for row in rows)
    assert any("Pilot packet status=product_pilot_packet_preflight_ready" in row["reason"] for row in rows)
    assert any(row["action_type"] == "fill_product_license_decision" for row in rows)
    assert any(row["action_type"] == "review_product_license_options" for row in rows)
    assert any(row["approval_token"] == "APPROVE_PRODUCT_LICENSE_FILE_CREATION" for row in rows)
    license_action = next(row for row in rows if row["action_type"] == "fill_product_license_decision")
    assert "fill_product_license_decision_operator_intake.py" in license_action["command"]
    assert "--license-text-source OPERATOR_APPROVED_LICENSE_TEXT_FILE" in license_action["command"]
    assert any(row["approval_token"] == "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS" for row in rows)
    assert not any(row["action_type"] == "review_large_cleanup_surface" for row in rows)
    assert any(row["action_type"] == "review_protected_ligand_heavy_policy" for row in rows)
    protected_action = next(row for row in rows if row["action_type"] == "review_protected_ligand_heavy_policy")
    assert protected_action["status"] == "policy_decision_required"
    assert protected_action["size_gb"] == 396.794


def test_goal_operator_action_board_suppresses_cleanup_actions_when_completion_ready() -> None:
    payload = mod.build_action_board(
        rollup_packet={},
        product_preflight_packet={},
        product_bundle_contract_packet={},
        product_delivery_evidence_packet={},
        cameo_input_kit_packet={},
        cameo_input_validation_packet={},
        cameo_repair_preflight_packet={},
        transition_cleanup_preflight_packet=_transition_preflight(),
        ligand_cleanup_preflight_packet=_ligand_preflight(),
        large_cleanup_drilldown_packet={},
        protected_ligand_heavy_deep_review_packet=_protected_ligand_heavy_deep_review(),
        protected_cleanup_policy_decision_gate_packet=_protected_cleanup_policy_decision_gate(),
        cleanup_completion_gate_packet=_cleanup_completion_gate_ready(),
    )

    assert payload["summary"]["status"] == "goal_operator_actions_clear"
    assert payload["summary"]["action_count"] == 0
    assert payload["summary"]["operator_input_required_count"] == 0
    assert payload["summary"]["primary_action_id"] == ""
    assert payload["summary"]["top_action_id"] == ""
    assert payload["summary"]["primary_action_priority"] == 0
    assert payload["summary"]["cleanup_completion_gate_status"] == "cleanup_completion_gate_ready"
    assert payload["summary"]["cleanup_completion_complete"] is True
    assert not any(row["lane_id"] in {"transition_cleanup", "ligand_heavy_cleanup"} for row in payload["rows"])


def test_goal_operator_action_board_surfaces_cameo_receiver_smoke_repair(tmp_path: Path) -> None:
    payload = mod.build_action_board(
        rollup_packet=_rollup_with_blocked_receiver_smoke(),
        product_preflight_packet={},
        product_bundle_contract_packet={},
        product_delivery_evidence_packet={},
        cameo_input_kit_packet=_cameo_input_kit(tmp_path),
        cameo_input_validation_packet={},
        cameo_repair_preflight_packet={},
        transition_cleanup_preflight_packet={},
        ligand_cleanup_preflight_packet={},
        large_cleanup_drilldown_packet={},
    )

    assert any(row["action_type"] == "repair_cameo_receiver_runtime_smoke" for row in payload["rows"])
    action = next(row for row in payload["rows"] if row["action_type"] == "repair_cameo_receiver_runtime_smoke")
    assert action["status"] == "required"
    assert "requirements-api.txt" in action["required_input"]
    assert "api_dependency_status=blocked_cameo_api_dependency_readiness" in action["reason"]


def test_goal_operator_action_board_promotes_cameo_runtime_repair_to_approval_required(tmp_path: Path) -> None:
    payload = mod.build_action_board(
        rollup_packet=_rollup_with_blocked_receiver_smoke(),
        product_preflight_packet={},
        product_bundle_contract_packet={},
        product_delivery_evidence_packet={},
        cameo_runtime_repair_work_order_packet=_cameo_runtime_repair_work_order(),
        cameo_input_kit_packet=_cameo_input_kit(tmp_path),
        cameo_input_validation_packet={},
        cameo_repair_preflight_packet={},
        transition_cleanup_preflight_packet={},
        ligand_cleanup_preflight_packet={},
        large_cleanup_drilldown_packet={},
        cameo_runtime_repair_work_order_path="runs/cameo_runtime_repair_work_order_current.json",
    )

    action = next(row for row in payload["rows"] if row["action_type"] == "repair_cameo_receiver_runtime_smoke")
    assert action["status"] == "approval_required"
    assert action["approval_token"] == "APPROVE_API_DEPENDENCY_INSTALL"
    assert action["artifact_path"] == "runs/cameo_runtime_repair_work_order_current.json"
    assert "runtime_repair_work_order_status=cameo_runtime_repair_work_order_ready" in action["reason"]
    assert payload["summary"]["cameo_runtime_repair_work_order_status"] == "cameo_runtime_repair_work_order_ready"
    assert payload["summary"]["cameo_runtime_install_approval_required"] is True
    assert payload["summary"]["cameo_runtime_approval_token_required"] == "APPROVE_API_DEPENDENCY_INSTALL"
    assert payload["summary"]["cameo_runtime_repair_command_count"] == 5


def test_goal_operator_action_board_suppresses_stale_runtime_repair_summary_when_runtime_ready(tmp_path: Path) -> None:
    payload = mod.build_action_board(
        rollup_packet=_rollup(),
        product_preflight_packet={},
        product_bundle_contract_packet={},
        product_delivery_evidence_packet={},
        cameo_runtime_repair_work_order_packet=_cameo_runtime_repair_work_order(),
        cameo_validation_operations_dossier_packet=_cameo_validation_operations_dossier_runtime_ready(),
        cameo_input_kit_packet=_cameo_input_kit(tmp_path),
        cameo_input_validation_packet={},
        cameo_repair_preflight_packet={},
        transition_cleanup_preflight_packet={},
        ligand_cleanup_preflight_packet={},
        large_cleanup_drilldown_packet={},
    )

    assert payload["summary"]["cameo_runtime_repair_work_order_status"] == "cameo_runtime_repair_work_order_ready"
    assert payload["summary"]["cameo_runtime_install_approval_required"] is False
    assert payload["summary"]["cameo_runtime_approval_token_required"] == ""
    assert payload["summary"]["cameo_runtime_repair_command_count"] == 0


def test_goal_operator_action_board_prioritizes_product_p1_when_runtime_and_cleanup_are_ready(tmp_path: Path) -> None:
    payload = mod.build_action_board(
        rollup_packet=_rollup(),
        product_preflight_packet=_product_preflight(),
        product_bundle_contract_packet=_bundle_contract(),
        product_delivery_evidence_packet=_delivery_evidence(),
        product_pilot_packet=_product_pilot_packet(),
        product_execution_approval_gate_packet=_product_execution_approval_gate(),
        product_license_decision_gate_packet=_product_license_decision_gate(),
        product_license_decision_packet=_product_license_decision_packet(),
        product_release_operations_dossier_packet=_product_release_operations_dossier(),
        cameo_validation_operations_dossier_packet=_cameo_validation_operations_dossier_runtime_ready(),
        cameo_official_results_intake_gate_packet=_cameo_official_results_intake_gate(),
        cameo_input_kit_packet=_cameo_input_kit(tmp_path),
        cameo_input_validation_packet={},
        cameo_repair_preflight_packet={},
        transition_cleanup_preflight_packet=_transition_preflight(),
        ligand_cleanup_preflight_packet=_ligand_preflight(),
        large_cleanup_drilldown_packet={},
        cleanup_completion_gate_packet=_cleanup_completion_gate_ready(),
    )

    rows = payload["rows"]
    assert [row["lane_id"] for row in rows[:3]] == [
        "commercial_product_execution",
        "commercial_product_license",
        "commercial_product_license",
    ]
    assert rows[0]["action_type"] == "review_product_execution_approval"
    assert rows[0]["priority"] == 1
    assert "fill the exact execution approval intake" in rows[0]["recommended_action"]
    assert rows[1]["priority"] == 1
    assert "Complete P1 product execution and license intake actions first" in payload["summary"]["next_required_step"]
    assert any(row["action_type"] == "fill_cameo_official_results_intake" and row["priority"] == 2 for row in rows)
    assert not any(row["lane_id"] in {"transition_cleanup", "ligand_heavy_cleanup"} for row in rows)
    assert payload["summary"]["cameo_runtime_install_approval_required"] is False


def test_goal_operator_action_board_surfaces_license_file_creation_work_order_when_decision_is_ready() -> None:
    payload = mod.build_action_board(
        rollup_packet=_rollup(),
        product_preflight_packet={},
        product_bundle_contract_packet={},
        product_delivery_evidence_packet={},
        product_license_decision_gate_packet=_product_license_decision_gate_ready(),
        product_license_decision_packet=_product_license_decision_packet(),
        product_license_file_creation_work_order_packet=_product_license_file_creation_work_order_ready(),
        cameo_input_kit_packet={},
        cameo_input_validation_packet={},
        cameo_repair_preflight_packet={},
        transition_cleanup_preflight_packet={},
        ligand_cleanup_preflight_packet={},
        large_cleanup_drilldown_packet={},
        cleanup_completion_gate_packet=_cleanup_completion_gate_ready(),
    )

    rows = payload["rows"]
    assert not any(row["action_type"] == "fill_product_license_decision" for row in rows)
    action = next(row for row in rows if row["action_type"] == "create_product_license_file_from_approved_metadata")
    assert action["priority"] == 1
    assert action["lane_id"] == "commercial_product_license"
    assert action["status"] == "required"
    assert action["approval_token"] == "APPROVE_PRODUCT_LICENSE_FILE_CREATION"
    assert action["required_input"] == "internal counsel approved text"
    assert action["artifact_path"] == "runs/product_license_file_creation_work_order_current.json"
    assert action["license_review_manifest_fingerprint_sha256"] == "a" * 64
    assert "license_review_manifest_fingerprint_sha256=" + ("a" * 64) in action["reason"]
    assert "Create/review the LICENSE file" in action["recommended_action"]
    assert payload["summary"]["product_license_decision_gate_status"] == "product_license_decision_gate_ready"
    assert payload["summary"]["product_license_file_creation_work_order_status"] == "product_license_file_creation_work_order_ready"
    assert payload["summary"]["product_license_file_creation_review_ready"] is True
    assert payload["summary"]["product_license_review_manifest_ready"] is True
    assert payload["summary"]["product_license_review_manifest_fingerprint_sha256"] == "a" * 64
    assert "Complete P1 product execution and license intake actions first" in payload["summary"]["next_required_step"]


def test_goal_operator_action_board_tool_writes_outputs(tmp_path: Path) -> None:
    paths = {
        "rollup": tmp_path / "rollup.json",
        "product_preflight": tmp_path / "product_preflight.json",
        "bundle_contract": tmp_path / "bundle_contract.json",
        "delivery_evidence": tmp_path / "delivery_evidence.json",
        "product_pilot_packet": tmp_path / "product_pilot_packet.json",
        "product_execution_approval_gate": tmp_path / "product_execution_approval_gate.json",
        "product_license_decision_gate": tmp_path / "product_license_decision_gate.json",
        "product_license_decision_packet": tmp_path / "product_license_decision_packet.json",
        "product_license_file_creation_work_order": tmp_path / "product_license_file_creation_work_order.json",
        "product_release_operations_dossier": tmp_path / "product_release_operations_dossier.json",
        "goal_release_decision_gate": tmp_path / "goal_release_decision_gate.json",
        "goal_release_burndown_work_order": tmp_path / "goal_release_burndown_work_order.json",
        "goal_operator_intake_kit": tmp_path / "goal_operator_intake_kit.json",
        "cameo_runtime_repair_work_order": tmp_path / "cameo_runtime_repair_work_order.json",
        "cameo_validation_operations_dossier": tmp_path / "cameo_validation_operations_dossier.json",
        "cameo_official_results_intake_gate": tmp_path / "cameo_official_results_intake_gate.json",
        "cameo_public_registration_approval_gate": tmp_path / "cameo_public_registration_approval_gate.json",
        "cameo_input_kit": tmp_path / "cameo_input_kit.json",
        "cameo_input_validation": tmp_path / "cameo_input_validation.json",
        "cameo_repair_preflight": tmp_path / "cameo_repair_preflight.json",
        "transition_preflight": tmp_path / "transition_preflight.json",
        "ligand_preflight": tmp_path / "ligand_preflight.json",
        "large_cleanup_drilldown": tmp_path / "large_cleanup_drilldown.json",
        "protected_cleanup_review": tmp_path / "protected_cleanup_review.json",
        "protected_ligand_heavy_deep_review": tmp_path / "protected_ligand_heavy_deep_review.json",
        "protected_cleanup_policy_decision_gate": tmp_path / "protected_cleanup_policy_decision_gate.json",
        "cleanup_snapshot_preflight": tmp_path / "cleanup_snapshot_preflight.json",
        "cleanup_payload_manifest_lock": tmp_path / "cleanup_payload_manifest_lock.json",
        "cleanup_postcheck_contract": tmp_path / "cleanup_postcheck_contract.json",
        "cleanup_execution_approval_dossier": tmp_path / "cleanup_execution_approval_dossier.json",
        "cleanup_execution_approval_gate": tmp_path / "cleanup_execution_approval_gate.json",
        "cleanup_completion_gate": tmp_path / "cleanup_completion_gate.json",
    }
    paths["rollup"].write_text(json.dumps(_rollup()) + "\n", encoding="utf-8")
    paths["product_preflight"].write_text(json.dumps(_product_preflight()) + "\n", encoding="utf-8")
    paths["bundle_contract"].write_text(json.dumps(_bundle_contract()) + "\n", encoding="utf-8")
    paths["delivery_evidence"].write_text(json.dumps(_delivery_evidence()) + "\n", encoding="utf-8")
    paths["product_pilot_packet"].write_text(json.dumps(_product_pilot_packet()) + "\n", encoding="utf-8")
    paths["product_execution_approval_gate"].write_text(json.dumps(_product_execution_approval_gate()) + "\n", encoding="utf-8")
    paths["product_license_decision_gate"].write_text(json.dumps(_product_license_decision_gate()) + "\n", encoding="utf-8")
    paths["product_license_decision_packet"].write_text(json.dumps(_product_license_decision_packet()) + "\n", encoding="utf-8")
    paths["product_license_file_creation_work_order"].write_text(
        json.dumps(_product_license_file_creation_work_order_ready()) + "\n", encoding="utf-8"
    )
    paths["product_release_operations_dossier"].write_text(json.dumps(_product_release_operations_dossier()) + "\n", encoding="utf-8")
    paths["goal_release_decision_gate"].write_text(json.dumps(_goal_release_decision_gate()) + "\n", encoding="utf-8")
    paths["goal_release_burndown_work_order"].write_text(json.dumps(_goal_release_burndown_work_order()) + "\n", encoding="utf-8")
    paths["goal_operator_intake_kit"].write_text(json.dumps(_goal_operator_intake_kit()) + "\n", encoding="utf-8")
    paths["cameo_runtime_repair_work_order"].write_text(json.dumps(_cameo_runtime_repair_work_order()) + "\n", encoding="utf-8")
    paths["cameo_validation_operations_dossier"].write_text(json.dumps(_cameo_validation_operations_dossier()) + "\n", encoding="utf-8")
    paths["cameo_official_results_intake_gate"].write_text(json.dumps(_cameo_official_results_intake_gate()) + "\n", encoding="utf-8")
    paths["cameo_public_registration_approval_gate"].write_text(json.dumps(_cameo_public_registration_approval_gate()) + "\n", encoding="utf-8")
    paths["cameo_input_kit"].write_text(json.dumps(_cameo_input_kit(tmp_path)) + "\n", encoding="utf-8")
    paths["cameo_input_validation"].write_text(json.dumps(_cameo_input_validation()) + "\n", encoding="utf-8")
    paths["cameo_repair_preflight"].write_text(json.dumps(_cameo_repair_preflight()) + "\n", encoding="utf-8")
    paths["transition_preflight"].write_text(json.dumps(_transition_preflight()) + "\n", encoding="utf-8")
    paths["ligand_preflight"].write_text(json.dumps(_ligand_preflight()) + "\n", encoding="utf-8")
    paths["large_cleanup_drilldown"].write_text(json.dumps(_large_cleanup_drilldown()) + "\n", encoding="utf-8")
    paths["protected_cleanup_review"].write_text(json.dumps(_protected_cleanup_review()) + "\n", encoding="utf-8")
    paths["protected_ligand_heavy_deep_review"].write_text(json.dumps(_protected_ligand_heavy_deep_review()) + "\n", encoding="utf-8")
    paths["protected_cleanup_policy_decision_gate"].write_text(json.dumps(_protected_cleanup_policy_decision_gate()) + "\n", encoding="utf-8")
    paths["cleanup_snapshot_preflight"].write_text(json.dumps(_cleanup_snapshot_preflight()) + "\n", encoding="utf-8")
    paths["cleanup_payload_manifest_lock"].write_text(json.dumps(_cleanup_payload_manifest_lock()) + "\n", encoding="utf-8")
    paths["cleanup_postcheck_contract"].write_text(json.dumps(_cleanup_postcheck_contract()) + "\n", encoding="utf-8")
    paths["cleanup_execution_approval_dossier"].write_text(
        json.dumps(_cleanup_execution_approval_dossier()) + "\n", encoding="utf-8"
    )
    paths["cleanup_execution_approval_gate"].write_text(json.dumps(_cleanup_execution_approval_gate()) + "\n", encoding="utf-8")
    paths["cleanup_completion_gate"].write_text(json.dumps(_cleanup_completion_gate()) + "\n", encoding="utf-8")
    out_json = tmp_path / "board.json"
    out_csv = tmp_path / "board.csv"
    out_md = tmp_path / "board.md"

    mod.main(
        [
            "--rollup-json",
            str(paths["rollup"]),
            "--product-preflight-json",
            str(paths["product_preflight"]),
            "--product-bundle-contract-json",
            str(paths["bundle_contract"]),
            "--product-delivery-evidence-json",
            str(paths["delivery_evidence"]),
            "--product-pilot-packet-json",
            str(paths["product_pilot_packet"]),
            "--product-execution-approval-gate-json",
            str(paths["product_execution_approval_gate"]),
            "--product-license-decision-gate-json",
            str(paths["product_license_decision_gate"]),
            "--product-license-decision-packet-json",
            str(paths["product_license_decision_packet"]),
            "--product-license-file-creation-work-order-json",
            str(paths["product_license_file_creation_work_order"]),
            "--product-release-operations-dossier-json",
            str(paths["product_release_operations_dossier"]),
            "--goal-release-decision-gate-json",
            str(paths["goal_release_decision_gate"]),
            "--goal-release-burndown-work-order-json",
            str(paths["goal_release_burndown_work_order"]),
            "--goal-operator-intake-kit-json",
            str(paths["goal_operator_intake_kit"]),
            "--cameo-runtime-repair-work-order-json",
            str(paths["cameo_runtime_repair_work_order"]),
            "--cameo-validation-operations-dossier-json",
            str(paths["cameo_validation_operations_dossier"]),
            "--cameo-official-results-intake-gate-json",
            str(paths["cameo_official_results_intake_gate"]),
            "--cameo-public-registration-approval-gate-json",
            str(paths["cameo_public_registration_approval_gate"]),
            "--cameo-input-kit-json",
            str(paths["cameo_input_kit"]),
            "--cameo-input-validation-json",
            str(paths["cameo_input_validation"]),
            "--cameo-repair-preflight-json",
            str(paths["cameo_repair_preflight"]),
            "--transition-cleanup-preflight-json",
            str(paths["transition_preflight"]),
            "--ligand-cleanup-preflight-json",
            str(paths["ligand_preflight"]),
            "--large-cleanup-drilldown-json",
            str(paths["large_cleanup_drilldown"]),
            "--protected-cleanup-review-json",
            str(paths["protected_cleanup_review"]),
            "--protected-ligand-heavy-deep-review-json",
            str(paths["protected_ligand_heavy_deep_review"]),
            "--protected-cleanup-policy-decision-gate-json",
            str(paths["protected_cleanup_policy_decision_gate"]),
            "--cleanup-snapshot-preflight-json",
            str(paths["cleanup_snapshot_preflight"]),
            "--cleanup-payload-manifest-lock-json",
            str(paths["cleanup_payload_manifest_lock"]),
            "--cleanup-postcheck-contract-json",
            str(paths["cleanup_postcheck_contract"]),
            "--cleanup-execution-approval-dossier-json",
            str(paths["cleanup_execution_approval_dossier"]),
            "--cleanup-execution-approval-gate-json",
            str(paths["cleanup_execution_approval_gate"]),
            "--cleanup-completion-gate-json",
            str(paths["cleanup_completion_gate"]),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "operator_actions_required"
    assert out_csv.read_text(encoding="utf-8").startswith("priority,lane_id,")
    assert "Goal Operator Action Board" in out_md.read_text(encoding="utf-8")
