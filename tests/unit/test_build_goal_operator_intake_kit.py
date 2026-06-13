from __future__ import annotations

import json
from pathlib import Path

from tools import build_goal_operator_intake_kit as mod


def _action_board() -> dict:
    return {
        "summary": {
            "status": "operator_actions_required",
            "action_count": 7,
            "operator_input_required_count": 4,
            "primary_action_id": "product_ai_production:return_gpu_force_regeneration_receipt",
            "top_action_id": "product_ai_production:return_gpu_force_regeneration_receipt",
            "primary_action_priority": 0,
            "primary_action_lane_id": "product_ai_production",
            "primary_action_type": "return_gpu_force_regeneration_receipt",
            "primary_action_status": "required",
            "primary_action_required_input": "GPU full-regeneration summary and manifest with operator verification",
            "primary_action_command": "python3 tools/generate_ligand_trajectory_engine.py --prod-mode",
            "primary_action_recommended_action": (
                "Run the full regeneration command on a GPU worker, return the identity-locked manifest and summary."
            ),
            "product_goal_release_blocker_fail_count": 2,
            "product_goal_release_blocker_requirement_ids": [
                "R8_full_scope_claim_closure",
                "R9_engine_refinement_claim_promotion",
            ],
            "product_goal_primary_release_blocker_requirement_id": "R8_full_scope_claim_closure",
            "product_goal_primary_release_blocker_tier": "full_commercial_scope",
            "product_goal_primary_release_blocker": "full_scope_claim_closure_not_ready",
            "primary_release_blocker_action_id": (
                "product_scope_expansion:resolve_full_scope_breadth_evidence_receipt"
            ),
            "primary_release_blocker_action_status": "required",
            "primary_release_blocker_action_required_input": (
                "config/product_scope_breadth_evidence_receipt_current.csv"
            ),
            "primary_release_blocker_action_artifact_path": (
                "runs/product_goal_completion_audit_current.json;"
                "runs/product_scope_breadth_evidence_receipt_current.json;"
                "config/product_scope_breadth_evidence_receipt_current.csv"
            ),
            "primary_release_blocker_action_recommended_action": (
                "Fill the full-scope evidence receipt rows with local evidence artifacts."
            ),
            "full_commercial_release_allowed": False,
            "full_commercial_release_blocker_count": 4,
            "full_commercial_release_blocker_ids": [
                "R8_full_scope_claim_closure",
                "R9_engine_refinement_claim_promotion",
                "MASTER:SCI-CLAIM",
                "ACCURACY:ligand_ranking",
            ],
            "full_commercial_release_next_required_step": "Fill the R8/R9 receipt CSVs.",
            "product_accuracy_parity_ligand_ranking_action_id": (
                "product_accuracy_parity:repair_ligand_ranking_parity"
            ),
            "product_accuracy_parity_ligand_ranking_action_present": True,
            "product_accuracy_parity_ligand_ranking_required_input": "ACCURACY:ligand_ranking",
            "product_accuracy_parity_ligand_ranking_artifact_path": (
                "runs/accuracy_parity_scorecard_current.json"
            ),
            "product_accuracy_parity_ligand_ranking_recommended_action": (
                "Repair DRD2/HTR2A/OPRM1 pose-supported ranking."
            ),
            "science_claim_promotion_gap_closure_open_gap_ids": [
                "SCI-GPCR",
                "SCI-OPENMM",
            ],
            "science_claim_promotion_gap_closure_current_next_action": (
                "Maintain conditional prior gate and keep broad-family claim promotion blocked."
            ),
            "accuracy_parity_ligand_ranking_status": "blocked",
            "accuracy_parity_ligand_ranking_pr_auc": 0.15749,
            "accuracy_parity_ligand_ranking_pr_auc_ci_low": 0.001347,
            "accuracy_parity_ligand_ranking_topk_hit_rate": 0.1,
            "accuracy_parity_ligand_ranking_next_required_step": (
                "Repair DRD2/HTR2A/OPRM1 pose-supported ranking."
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
        },
        "rows": [
            {
                "lane_id": "product_ai_production",
                "action_type": "return_gpu_force_regeneration_receipt",
                "status": "required",
                "artifact_path": (
                    "runs/product_goal_completion_audit_current.json;"
                    "runs/product_production_ai_gpu_return_intake_current.json"
                ),
                "approval_token": "",
            },
            {
                "lane_id": "cameo_validation",
                "action_type": "fill_cameo_official_results_intake",
                "status": "required",
                "artifact_path": "runs/cameo_official_results_intake_gate_current.json",
                "approval_token": "",
            },
            {
                "lane_id": "cameo_validation",
                "action_type": "repair_cameo_receiver_runtime_smoke",
                "status": "approval_required",
                "artifact_path": "runs/cameo_runtime_repair_work_order_current.json",
                "approval_token": "APPROVE_API_DEPENDENCY_INSTALL",
            },
            {
                "lane_id": "commercial_product_execution",
                "action_type": "review_product_execution_approval",
                "status": "approval_required",
                "artifact_path": "runs/product_execution_preflight_current.json",
                "approval_token": "APPROVE_PRODUCT_DOCKING_EXECUTION",
            },
            {
                "lane_id": "commercial_product_license",
                "action_type": "fill_product_license_decision",
                "status": "required",
                "artifact_path": "runs/product_license_decision_gate_current.json",
                "approval_token": "APPROVE_PRODUCT_LICENSE_FILE_CREATION",
            },
            {
                "lane_id": "product_scope_expansion",
                "action_type": "curate_scope_evidence_priority_item",
                "status": "review_required",
                "artifact_path": "runs/product_goal_completion_audit_current.json",
                "approval_token": "",
            },
            {
                "lane_id": "product_scope_expansion",
                "action_type": "resolve_full_scope_breadth_evidence_receipt",
                "status": "required",
                "artifact_path": (
                    "runs/product_goal_completion_audit_current.json;"
                    "runs/product_scope_breadth_evidence_receipt_current.json;"
                    "config/product_scope_breadth_evidence_receipt_current.csv"
                ),
                "approval_token": mod.PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT_APPROVAL_TOKEN,
            },
            {
                "lane_id": "product_engine_refinement",
                "action_type": "resolve_refine_tier_claim_promotion_blocker",
                "status": "required",
                "artifact_path": "runs/engine_refinement_claim_promotion_action_board_current.csv",
                "approval_token": "",
            },
            {
                "lane_id": "ligand_heavy_cleanup",
                "action_type": "review_protected_ligand_heavy_policy",
                "status": "policy_decision_required",
                "artifact_path": "runs/protected_cleanup_policy_decision_gate_current.json",
                "approval_token": "",
            },
        ],
    }


def _source_packets() -> dict[str, dict]:
    return {
        mod.DEFAULT_CAMEO_OFFICIAL_RESULTS_GATE_JSON: {"summary": {"status": "blocked_cameo_official_results_intake"}},
        mod.DEFAULT_CAMEO_OFFICIAL_RESULT_FETCH_PREFLIGHT_JSON: {
            "summary": {
                "status": "blocked_cameo_official_result_fetch_preflight",
                "operator_fetch_csv_present": False,
                "fetch_approval_token_required": mod.CAMEO_OFFICIAL_RESULT_FETCH_APPROVAL_TOKEN,
                "external_state_mutated": False,
            }
        },
        mod.DEFAULT_CAMEO_REGISTRATION_GATE_JSON: {"summary": {"status": "blocked_cameo_public_registration_approval_gate"}},
        mod.DEFAULT_PRODUCT_EXECUTION_GATE_JSON: {"summary": {"status": "blocked_product_execution_operator_approval_gate"}},
        mod.DEFAULT_API_RUNNER_PROFILE_PROMOTION_RECEIPT_JSON: {
            "summary": {
                "status": "blocked_api_runner_profile_promotion_operator_receipt",
                "operator_receipt_ready": False,
                "blocked_row_count": 4,
                "external_state_mutated": False,
            }
        },
        mod.DEFAULT_PRODUCTION_AI_REGISTRY_PROMOTION_RECEIPT_JSON: {
            "summary": {
                "status": "blocked_production_ai_registry_promotion_operator_receipt",
                "operator_receipt_ready": False,
                "blocked_row_count": 1,
                "approval_token_required": mod.PRODUCTION_AI_REGISTRY_PROMOTION_APPROVAL_TOKEN,
                "external_state_mutated": False,
            }
        },
        mod.DEFAULT_PRODUCTION_AI_REGISTRY_PROMOTION_PRIORITY_JSON: {
            "status": "blocked_production_ai_registry_promotion_priority_packet",
            "priority_packet_ready": True,
            "registry_promotion_ready": False,
            "operator_input_required_count": 3,
            "blocked_priority_item_count": 3,
            "registry_promotion_missing_gate_count": 3,
            "registry_promotion_missing_gate_ids": [
                "default_residual_mode_guarded",
                "production_promotion_allowed",
                "customer_facing_mutation_flags",
            ],
            "observed_registry_trained_model_checkpoint_count": 1,
            "top_gate_id": "default_residual_mode_guarded",
            "top_priority_bucket": "guarded_residual_mode_selection_required",
            "top_required_input": (
                "Set the guarded default residual mode in the production AI registry promotion operator receipt."
            ),
            "top_acceptance_artifact": "runs/residual_model_registry_current.json",
            "top_verification_command": "python3 tools/build_residual_model_registry.py",
            "top_next_operator_step": "Fill the guarded promotion operator receipt.",
            "model_promoted": False,
            "customer_facing_mutation_enabled": False,
            "external_state_mutated": False,
        },
        mod.DEFAULT_PRODUCT_COMMERCIAL_INDEPENDENCE_JSON: {
            "summary": {
                "status": "blocked_product_commercial_independence_gate",
                "commercial_independent_product_claim_allowed": False,
                "blocker_count": 1,
                "license_present": False,
                "check_count": 10,
            }
        },
        mod.DEFAULT_PRODUCT_LICENSE_GATE_JSON: {"summary": {"status": "blocked_product_license_decision_gate"}},
        mod.DEFAULT_PRODUCTION_AI_GPU_RETURN_INTAKE_JSON: {
            "summary": {"status": "blocked_product_production_ai_gpu_return_intake"}
        },
        mod.DEFAULT_PRODUCT_SCOPE_EVIDENCE_INTAKE_READINESS_JSON: {
            "summary": {
                "packet_type": "product_scope_breadth_evidence_intake_readiness",
                "intake_readiness_ready": True,
            }
        },
        mod.DEFAULT_PRODUCT_SCOPE_EVIDENCE_PRIORITY_JSON: {
            "summary": {
                "status": "product_scope_breadth_evidence_priority_packet_ready",
                "packet_type": "product_scope_breadth_evidence_priority_packet",
                "priority_packet_ready": True,
                "scope_promotion_allowed": False,
                "authoritative_apply_allowed": False,
                "queue_item_count": 15,
                "open_item_count": 15,
                "scientific_evidence_request_count": 11,
                "local_crosscheck_candidate_count": 11,
                "external_primary_exact_evidence_required_count": 0,
                "review_only_keep_blocked_count": 1,
                "top_item_id": "AQP1.core_binder_01",
                "top_domain": "transporter",
                "top_bucket": "local_crosscheck_review_present_but_exact_quant_required",
                "top_required_evidence_type": "exact_transporter_target_pair_quantitative_binder_kcal",
                "top_review_template_artifact": "runs/transporter_manual_review_intake_template_current.json",
                "top_apply_gate_artifact": "runs/transporter_binder_promotion_gate_current.json",
                "top_next_step": "Review local crosscheck files, capture exact evidence if present.",
                "external_state_mutated": False,
            }
        },
        mod.DEFAULT_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT_JSON: {
            "summary": {
                "status": "blocked_product_scope_breadth_evidence_receipt",
                "full_scope_evidence_receipt_ready": False,
                "blocked_row_count": 6,
                "external_state_mutated": False,
            }
        },
        mod.DEFAULT_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT_JSON: {
            "summary": {
                "status": "blocked_engine_refinement_claim_evidence_receipt",
                "claim_promotion_evidence_receipt_ready": False,
                "blocked_row_count": 6,
                "external_state_mutated": False,
            }
        },
        mod.DEFAULT_CLEANUP_APPROVAL_GATE_JSON: {"summary": {"status": "blocked_cleanup_execution_approval_gate"}},
        mod.DEFAULT_PROTECTED_POLICY_GATE_JSON: {"summary": {"status": "blocked_protected_cleanup_policy_decision_gate"}},
        mod.DEFAULT_GOAL_API_SURFACE_CONTRACT_JSON: {
            "summary": {
                "status": "goal_api_surface_contract_ready",
                "surface_ready": True,
                "check_count": 7,
                "blocker_count": 0,
                "missing_endpoint_count": 0,
                "missing_status_key_count": 0,
            }
        },
    }


def _release_burndown() -> dict:
    return {
        "summary": {"status": "goal_release_burndown_work_order_ready", "work_item_count": 8},
        "rows": [
            {
                "sequence": "0",
                "phase": "P0_product_ai_architecture_production_inference_closure",
                "burndown_status": "operator_input_required",
                "release_checks": "product_ai_architecture_gap_closure_ready",
                "source_artifact": "runs/product_production_ai_gpu_return_intake_current.json",
                "recommended_action": "Return GPU regeneration manifest and summary.",
            },
            {
                "sequence": 1,
                "phase": "P1_product_execution_and_bundle_validation",
                "burndown_status": "approval_required",
                "release_checks": "product_architecture_release_ready;pilot_delivery_ready;bundle_validation_passed;delivery_ready_claim_allowed",
                "source_artifact": "runs/product_execution_work_order_current.json;runs/product_pilot_packet_contract_current.json",
                "recommended_action": "Review product execution and bundle validation.",
            },
            {
                "sequence": 2,
                "phase": "P1_product_commercial_independence",
                "burndown_status": "approval_required",
                "release_checks": "commercial_independence_gate_ready",
                "source_artifact": "runs/product_commercial_independence_gate_current.json",
                "recommended_action": "Fill the product license decision intake.",
            },
            {
                "sequence": 3,
                "phase": "P2_cameo_official_validation_and_registration",
                "burndown_status": "official_results_required",
                "release_checks": "official_cameo_validation_evidence_ready;official_cameo_results_used",
                "source_artifact": "runs/cameo_official_results_intake_gate_current.json",
                "recommended_action": "Attach official CAMEO result rows.",
            },
            {
                "sequence": 4,
                "phase": "P2_cameo_official_validation_and_registration",
                "burndown_status": "approval_required",
                "release_checks": "cameo_public_registration_allowed",
                "source_artifact": "runs/cameo_runtime_repair_work_order_current.json",
                "recommended_action": "Repair API dependency and receiver smoke.",
            },
            {
                "sequence": 6,
                "phase": "P3_cleanup_execution_or_policy_resolution",
                "burndown_status": "approval_required",
                "release_checks": "transition_cleanup_complete",
                "source_artifact": "runs/transition_cleanup_work_order_current.json",
                "recommended_action": "Review transition cleanup approvals.",
            },
            {
                "sequence": 7,
                "phase": "P3_cleanup_execution_or_policy_resolution",
                "burndown_status": "approval_required",
                "release_checks": "ligand_heavy_cleanup_complete",
                "source_artifact": "runs/ligand_heavy_cleanup_work_order_current.json",
                "recommended_action": "Review ligand-heavy cleanup approvals.",
            },
            {
                "sequence": 8,
                "phase": "P3_cleanup_execution_or_policy_resolution",
                "burndown_status": "policy_decision_required",
                "release_checks": "protected_cleanup_policy_resolved",
                "source_artifact": "runs/protected_cleanup_payload_review_current.json",
                "recommended_action": "Review protected cleanup policy.",
            },
        ],
    }


def _release_burndown_runtime_ready_registration_only() -> dict:
    payload = _release_burndown()
    for row in payload["rows"]:
        if row.get("release_checks") == "cameo_public_registration_allowed":
            row["approval_token_required"] = "APPROVE_CAMEO_SERVER_REGISTRATION;APPROVE_CAMEO_OUTBOUND_EMAIL"
            row["source_artifact"] = "runs/cameo_capability_preflight_current.json"
            row["recommended_action"] = "Review CAMEO registration and outbound-email approval only after official validation evidence is ready."
    return payload


def test_goal_operator_intake_kit_summarizes_actions_tokens_and_requirements(tmp_path: Path) -> None:
    payload = mod.build_goal_operator_intake_kit(
        action_board_packet=_action_board(),
        release_burndown_packet=_release_burndown(),
        source_packets=_source_packets(),
        out_dir=tmp_path / "kit",
    )

    summary = payload["summary"]
    by_id = {row["kit_entry_id"]: row for row in payload["rows"]}
    assert summary["status"] == "goal_operator_intake_kit_ready"
    assert summary["entry_count"] == 19
    assert summary["source_action_count"] == 9
    assert summary["release_burndown_source_row_count"] == 8
    assert summary["release_burndown_linked_entry_count"] == 12
    assert summary["operator_input_required_count"] == 17
    assert summary["current_action_required_count"] == 12
    assert summary["deferred_operator_input_count"] == 5
    assert summary["full_commercial_evidence_receipt_entry_count"] == 2
    assert summary["full_commercial_evidence_receipt_operator_input_required_count"] == 2
    assert summary["full_commercial_evidence_receipt_current_action_required_count"] == 2
    assert summary["full_commercial_evidence_receipt_template_required_count"] == 2
    assert summary["full_commercial_evidence_receipt_template_present_count"] == 2
    assert summary["full_commercial_evidence_receipt_approval_token_count"] == 2
    assert summary["full_commercial_evidence_receipt_entry_ids"] == [
        "product_scope_breadth_evidence_receipt",
        "engine_refinement_claim_evidence_receipt",
    ]
    assert summary["full_commercial_evidence_receipt_source_gate_statuses"] == (
        "product_scope_breadth_evidence_receipt=blocked_product_scope_breadth_evidence_receipt;"
        "engine_refinement_claim_evidence_receipt=blocked_engine_refinement_claim_evidence_receipt"
    )
    assert summary["full_commercial_evidence_receipt_required_inputs"] == (
        "config/product_scope_breadth_evidence_receipt_current.csv;"
        "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
    )
    assert summary["full_commercial_evidence_receipt_approval_tokens"] == (
        "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT;"
        "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT"
    )
    assert summary["product_scope_breadth_evidence_priority_source_json"] == (
        mod.DEFAULT_PRODUCT_SCOPE_EVIDENCE_PRIORITY_JSON
    )
    assert summary["product_scope_breadth_evidence_priority_status"] == (
        "product_scope_breadth_evidence_priority_packet_ready"
    )
    assert summary["product_scope_breadth_evidence_priority_packet_ready"] is True
    assert summary["product_scope_breadth_evidence_priority_open_item_count"] == 15
    assert summary["product_scope_breadth_evidence_priority_scientific_evidence_request_count"] == 11
    assert summary["product_scope_breadth_evidence_priority_top_item_id"] == "AQP1.core_binder_01"
    assert summary["product_scope_breadth_evidence_priority_top_domain"] == "transporter"
    assert summary["product_scope_breadth_evidence_priority_top_bucket"] == (
        "local_crosscheck_review_present_but_exact_quant_required"
    )
    assert summary["product_scope_breadth_evidence_priority_top_required_evidence_type"] == (
        "exact_transporter_target_pair_quantitative_binder_kcal"
    )
    assert summary["product_scope_breadth_evidence_priority_scope_promotion_allowed"] is False
    assert summary["product_scope_breadth_evidence_priority_authoritative_apply_allowed"] is False
    assert by_id["production_ai_registry_promotion"]["kit_status"] == "approval_required"
    assert by_id["production_ai_registry_promotion"]["template_required"] is True
    assert by_id["production_ai_registry_promotion"]["template_path"] == (
        "config/production_ai_registry_promotion_operator_receipt_current.csv"
    )
    assert by_id["production_ai_registry_promotion"]["intake_path"] == (
        "config/production_ai_registry_promotion_operator_receipt_current.csv"
    )
    assert by_id["production_ai_registry_promotion"]["approval_token_required"] == (
        mod.PRODUCTION_AI_REGISTRY_PROMOTION_APPROVAL_TOKEN
    )
    assert by_id["production_ai_registry_promotion"]["operator_input_required_now"] is False
    assert by_id["production_ai_registry_promotion"]["priority_source_json"] == (
        mod.DEFAULT_PRODUCTION_AI_REGISTRY_PROMOTION_PRIORITY_JSON
    )
    assert by_id["production_ai_registry_promotion"]["priority_status"] == (
        "blocked_production_ai_registry_promotion_priority_packet"
    )
    assert by_id["production_ai_registry_promotion"]["priority_packet_ready"] is True
    assert by_id["production_ai_registry_promotion"]["priority_registry_promotion_ready"] is False
    assert by_id["production_ai_registry_promotion"]["priority_operator_input_required_count"] == 3
    assert by_id["production_ai_registry_promotion"]["priority_blocked_item_count"] == 3
    assert by_id["production_ai_registry_promotion"]["priority_missing_gate_count"] == 3
    assert "default_residual_mode_guarded" in by_id[
        "production_ai_registry_promotion"
    ]["priority_missing_gate_ids"]
    assert by_id["production_ai_registry_promotion"][
        "priority_observed_registry_trained_model_checkpoint_count"
    ] == 1
    assert by_id["production_ai_registry_promotion"]["priority_top_gate_id"] == (
        "default_residual_mode_guarded"
    )
    assert by_id["production_ai_registry_promotion"]["priority_top_priority_bucket"] == (
        "guarded_residual_mode_selection_required"
    )
    assert by_id["production_ai_registry_promotion"]["priority_model_promoted"] is False
    assert by_id["production_ai_registry_promotion"]["priority_external_state_mutated"] is False
    assert summary["production_ai_registry_promotion_priority_status"] == (
        "blocked_production_ai_registry_promotion_priority_packet"
    )
    assert summary["production_ai_registry_promotion_priority_packet_ready"] is True
    assert summary["production_ai_registry_promotion_priority_registry_promotion_ready"] is False
    assert summary["production_ai_registry_promotion_priority_operator_input_required_count"] == 3
    assert summary["production_ai_registry_promotion_priority_blocked_priority_item_count"] == 3
    assert summary["production_ai_registry_promotion_priority_missing_gate_count"] == 3
    assert summary["production_ai_registry_promotion_priority_missing_gate_ids"] == [
        "default_residual_mode_guarded",
        "production_promotion_allowed",
        "customer_facing_mutation_flags",
    ]
    assert summary[
        "production_ai_registry_promotion_priority_observed_registry_trained_model_checkpoint_count"
    ] == 1
    assert summary["production_ai_registry_promotion_priority_top_gate_id"] == (
        "default_residual_mode_guarded"
    )
    assert summary["production_ai_registry_promotion_priority_top_priority_bucket"] == (
        "guarded_residual_mode_selection_required"
    )
    assert summary["production_ai_registry_promotion_priority_model_promoted"] is False
    assert summary["production_ai_registry_promotion_priority_external_state_mutated"] is False
    assert summary["primary_action_id"] == "product_ai_production:return_gpu_force_regeneration_receipt"
    assert summary["top_action_id"] == summary["primary_action_id"]
    assert summary["primary_action_priority"] == 0
    assert summary["primary_action_lane_id"] == "product_ai_production"
    assert summary["primary_action_type"] == "return_gpu_force_regeneration_receipt"
    assert summary["primary_action_status"] == "required"
    assert summary["primary_action_required_input"] == (
        "GPU full-regeneration summary and manifest with operator verification"
    )
    assert "generate_ligand_trajectory_engine.py" in summary["primary_action_command"]
    assert "Run the full regeneration command on a GPU worker" in summary[
        "primary_action_recommended_action"
    ]
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
    assert summary["primary_release_blocker_action_status"] == "required"
    assert summary["primary_release_blocker_action_required_input"] == (
        "config/product_scope_breadth_evidence_receipt_current.csv"
    )
    assert "product_scope_breadth_evidence_receipt_current.json" in summary[
        "primary_release_blocker_action_artifact_path"
    ]
    assert "full-scope evidence receipt rows" in summary[
        "primary_release_blocker_action_recommended_action"
    ]
    assert summary["full_commercial_release_allowed"] is False
    assert summary["full_commercial_release_blocker_count"] == 4
    assert summary["full_commercial_release_blocker_ids"] == [
        "R8_full_scope_claim_closure",
        "R9_engine_refinement_claim_promotion",
        "MASTER:SCI-CLAIM",
        "ACCURACY:ligand_ranking",
    ]
    assert "R8/R9 receipt CSVs" in summary["full_commercial_release_next_required_step"]
    assert summary["science_claim_promotion_gap_closure_open_gap_ids"] == [
        "SCI-GPCR",
        "SCI-OPENMM",
    ]
    assert "broad-family claim promotion" in summary[
        "science_claim_promotion_gap_closure_current_next_action"
    ]
    assert summary["accuracy_parity_ligand_ranking_status"] == "blocked"
    assert summary["product_accuracy_parity_ligand_ranking_action_id"] == (
        "product_accuracy_parity:repair_ligand_ranking_parity"
    )
    assert summary["product_accuracy_parity_ligand_ranking_action_present"] is True
    assert summary["product_accuracy_parity_ligand_ranking_required_input"] == (
        "ACCURACY:ligand_ranking"
    )
    assert summary["product_accuracy_parity_ligand_ranking_artifact_path"] == (
        "runs/accuracy_parity_scorecard_current.json"
    )
    assert summary["accuracy_parity_ligand_ranking_pr_auc"] == 0.15749
    assert summary["accuracy_parity_ligand_ranking_pr_auc_ci_low"] == 0.001347
    assert summary["accuracy_parity_ligand_ranking_topk_hit_rate"] == 0.1
    assert "DRD2/HTR2A/OPRM1" in summary[
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
    assert summary["official_results_required_count"] == 1
    assert summary["policy_decision_required_count"] == 1
    assert summary["product_commercial_independence_status"] == "blocked_product_commercial_independence_gate"
    assert summary["product_commercial_independent_claim_allowed"] is False
    assert summary["product_commercial_independence_blocker_count"] == 1
    assert summary["product_commercial_independence_license_present"] is False
    assert summary["product_commercial_independence_check_count"] == 10
    assert summary["goal_api_surface_contract_status"] == "goal_api_surface_contract_ready"
    assert summary["goal_api_surface_ready"] is True
    assert summary["goal_api_surface_check_count"] == 7
    assert summary["goal_api_surface_blocker_count"] == 0
    assert summary["goal_api_status_endpoint"] == "/goal/status"
    assert summary["goal_api_contract_endpoint"] == "/goal/api-contract"
    assert "APPROVE_API_DEPENDENCY_INSTALL" in summary["approval_tokens"]
    assert mod.CAMEO_OFFICIAL_RESULT_FETCH_APPROVAL_TOKEN in summary["approval_tokens"]
    assert mod.API_RUNNER_PROFILE_PROMOTION_APPROVAL_TOKEN in summary["approval_tokens"]
    assert mod.PRODUCTION_AI_REGISTRY_PROMOTION_APPROVAL_TOKEN in summary["approval_tokens"]
    assert mod.PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT_APPROVAL_TOKEN in summary["approval_tokens"]
    assert mod.ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT_APPROVAL_TOKEN in summary["approval_tokens"]
    assert summary["current_action_approval_token_count"] == 4
    assert summary["current_action_approval_tokens"] == [
        "APPROVE_API_DEPENDENCY_INSTALL",
        "APPROVE_PRODUCT_DOCKING_EXECUTION",
        "APPROVE_PRODUCT_LICENSE_FILE_CREATION",
        mod.PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT_APPROVAL_TOKEN,
    ]
    assert summary["action_executed"] is False
    assert summary["delete_executed"] is False
    assert summary["external_state_mutated"] is False
    assert by_id["cameo_official_results"]["kit_status"] == "operator_input_required"
    assert by_id["cameo_official_results"]["current_action_surfaced"] is True
    assert by_id["cameo_official_results"]["operator_input_required_now"] is True
    assert by_id["cameo_official_results"]["release_burndown_surfaced"] is True
    assert by_id["cameo_official_results"]["release_sequence"] == "3"
    assert by_id["cameo_official_results"]["release_burndown_status"] == "official_results_required"
    assert by_id["cameo_official_result_fetch_preflight"]["kit_status"] == "approval_required"
    assert by_id["cameo_official_result_fetch_preflight"]["current_action_surfaced"] is False
    assert by_id["cameo_official_result_fetch_preflight"]["operator_input_required"] is True
    assert by_id["cameo_official_result_fetch_preflight"]["operator_input_required_now"] is False
    assert by_id["cameo_official_result_fetch_preflight"]["source_gate_status"] == (
        "blocked_cameo_official_result_fetch_preflight"
    )
    assert by_id["cameo_official_result_fetch_preflight"]["template_path"] == (
        "runs/cameo_official_result_fetch_operator_approval_template_current.csv"
    )
    assert by_id["cameo_official_result_fetch_preflight"]["intake_path"] == (
        "runs/cameo_official_result_fetch_operator_approval_intake.csv"
    )
    assert by_id["cameo_official_result_fetch_preflight"]["approval_token_required"] == (
        mod.CAMEO_OFFICIAL_RESULT_FETCH_APPROVAL_TOKEN
    )
    assert by_id["cameo_official_result_fetch_preflight"]["release_sequence"] == "3"
    assert by_id["cameo_api_dependency_install"]["template_required"] is False
    assert by_id["cameo_api_dependency_install"]["kit_status"] == "approval_required"
    assert by_id["cameo_api_dependency_install"]["release_sequence"] == "4"
    assert by_id["cameo_public_registration"]["kit_status"] == "approval_required"
    assert by_id["cameo_public_registration"]["current_action_surfaced"] is False
    assert by_id["cameo_public_registration"]["operator_input_required"] is True
    assert by_id["cameo_public_registration"]["operator_input_required_now"] is False
    assert by_id["cameo_public_registration"]["release_sequence"] == "4"
    assert by_id["cleanup_execution_approval"]["current_action_surfaced"] is False
    assert by_id["cleanup_execution_approval"]["operator_input_required"] is True
    assert by_id["cleanup_execution_approval"]["operator_input_required_now"] is False
    assert by_id["cleanup_execution_approval"]["release_sequence"] == "6;7"
    assert by_id["cleanup_execution_approval"]["release_burndown_status"] == "approval_required"
    assert by_id["product_license_decision"]["related_source_json"] == mod.DEFAULT_PRODUCT_COMMERCIAL_INDEPENDENCE_JSON
    assert by_id["product_license_decision"]["related_source_status"] == "blocked_product_commercial_independence_gate"
    assert by_id["product_license_decision"]["release_sequence"] == "2"
    assert by_id["api_runner_profile_promotion_operator_receipt"]["kit_status"] == "approval_required"
    assert by_id["api_runner_profile_promotion_operator_receipt"]["current_action_surfaced"] is False
    assert by_id["api_runner_profile_promotion_operator_receipt"]["operator_input_required"] is True
    assert by_id["api_runner_profile_promotion_operator_receipt"]["operator_input_required_now"] is False
    assert by_id["api_runner_profile_promotion_operator_receipt"]["source_gate_status"] == (
        "blocked_api_runner_profile_promotion_operator_receipt"
    )
    assert by_id["api_runner_profile_promotion_operator_receipt"]["template_path"] == (
        "runs/api_runner_profile_promotion_operator_template_current.csv"
    )
    assert by_id["api_runner_profile_promotion_operator_receipt"]["approval_token_required"] == (
        mod.API_RUNNER_PROFILE_PROMOTION_APPROVAL_TOKEN
    )
    assert by_id["production_ai_gpu_return"]["kit_status"] == "operator_input_required"
    assert by_id["production_ai_gpu_return"]["current_action_surfaced"] is True
    assert by_id["production_ai_gpu_return"]["operator_input_required_now"] is True
    assert by_id["production_ai_gpu_return"]["source_gate_status"] == (
        "blocked_product_production_ai_gpu_return_intake"
    )
    assert by_id["production_ai_gpu_return"]["release_sequence"] == "0"
    assert by_id["production_ai_gpu_return"]["release_phase"] == (
        "P0_product_ai_architecture_production_inference_closure"
    )
    assert by_id["production_ai_gpu_return_summary"]["kit_status"] == "operator_input_required"
    assert by_id["production_ai_gpu_return_summary"]["current_action_surfaced"] is True
    assert by_id["production_ai_gpu_return_summary"]["operator_input_required_now"] is True
    assert by_id["production_ai_gpu_return_summary"]["template_path"] == (
        "runs/residual_force_trajectory_regeneration_current_summary_template.json"
    )
    assert by_id["production_ai_gpu_return_summary"]["intake_path"] == (
        "runs/residual_force_trajectory_regeneration_current_summary.json"
    )
    assert "out_manifest_csv" in by_id["production_ai_gpu_return_summary"]["recommended_action"]
    assert "out_summary_json" in by_id["production_ai_gpu_return_summary"]["recommended_action"]
    assert by_id["production_ai_gpu_return_summary"]["release_sequence"] == "0"
    assert by_id["scope_transporter_manual_review"]["kit_status"] == "review_required"
    assert by_id["scope_transporter_manual_review"]["current_action_surfaced"] is True
    assert by_id["scope_transporter_manual_review"]["operator_input_required_now"] is True
    assert by_id["scope_transporter_manual_review"]["source_gate_status"] == (
        "product_scope_breadth_evidence_intake_readiness_ready"
    )
    assert by_id["scope_transporter_manual_review"]["related_source_status"] == (
        "product_scope_breadth_evidence_priority_packet_ready"
    )
    assert by_id["scope_transporter_manual_review"]["template_path"] == (
        "runs/transporter_manual_review_intake_template_current.csv"
    )
    assert by_id["scope_transporter_manual_review"]["release_sequence"] == "0"
    assert by_id["scope_pxr_exact_evidence_review"]["kit_status"] == "review_required"
    assert by_id["scope_pxr_exact_evidence_review"]["current_action_surfaced"] is True
    assert by_id["scope_pxr_exact_evidence_review"]["operator_input_required_now"] is True
    assert by_id["scope_pxr_exact_evidence_review"]["template_path"] == (
        "runs/pxr_exact_evidence_review_intake_template_current.csv"
    )
    assert by_id["scope_pxr_exact_evidence_review"]["release_sequence"] == "0"
    assert by_id["product_scope_breadth_evidence_receipt"]["kit_status"] == "operator_input_required"
    assert by_id["product_scope_breadth_evidence_receipt"]["current_action_surfaced"] is True
    assert by_id["product_scope_breadth_evidence_receipt"]["operator_input_required_now"] is True
    assert by_id["product_scope_breadth_evidence_receipt"]["source_gate_status"] == (
        "blocked_product_scope_breadth_evidence_receipt"
    )
    assert by_id["product_scope_breadth_evidence_receipt"]["template_path"] == (
        "config/product_scope_breadth_evidence_receipt_current.csv"
    )
    assert by_id["product_scope_breadth_evidence_receipt"]["intake_path"] == (
        "config/product_scope_breadth_evidence_receipt_current.csv"
    )
    assert by_id["product_scope_breadth_evidence_receipt"]["approval_token_required"] == (
        mod.PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT_APPROVAL_TOKEN
    )
    assert by_id["engine_refinement_claim_promotion_action_board"]["kit_status"] == "operator_input_required"
    assert by_id["engine_refinement_claim_promotion_action_board"]["current_action_surfaced"] is True
    assert by_id["engine_refinement_claim_promotion_action_board"]["operator_input_required_now"] is True
    assert by_id["engine_refinement_claim_promotion_action_board"]["template_required"] is False
    assert by_id["engine_refinement_claim_promotion_action_board"]["template_path"] == (
        "runs/engine_refinement_claim_promotion_action_board_current.csv"
    )
    assert by_id["engine_refinement_claim_evidence_receipt"]["kit_status"] == "operator_input_required"
    assert by_id["engine_refinement_claim_evidence_receipt"]["current_action_surfaced"] is True
    assert by_id["engine_refinement_claim_evidence_receipt"]["operator_input_required_now"] is True
    assert by_id["engine_refinement_claim_evidence_receipt"]["template_required"] is True
    assert by_id["engine_refinement_claim_evidence_receipt"]["source_gate_status"] == (
        "blocked_engine_refinement_claim_evidence_receipt"
    )
    assert by_id["engine_refinement_claim_evidence_receipt"]["template_path"] == (
        "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
    )
    assert by_id["engine_refinement_claim_evidence_receipt"]["intake_path"] == (
        "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
    )
    assert by_id["engine_refinement_claim_evidence_receipt"]["approval_token_required"] == (
        mod.ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT_APPROVAL_TOKEN
    )
    assert by_id["accuracy_ligand_ranking_repair"]["kit_status"] == "not_surfaced"
    assert by_id["accuracy_ligand_ranking_repair"]["current_action_surfaced"] is False
    assert by_id["accuracy_ligand_ranking_repair"]["operator_input_required"] is False
    assert by_id["accuracy_ligand_ranking_repair"]["template_required"] is False
    assert by_id["accuracy_ligand_ranking_repair"]["source_gate_json"] == (
        mod.DEFAULT_ACCURACY_PARITY_SCORECARD_JSON
    )
    assert by_id["protected_cleanup_policy"]["kit_status"] == "policy_decision_required"
    assert by_id["protected_cleanup_policy"]["operator_input_required_now"] is True
    assert by_id["protected_cleanup_policy"]["release_burndown_status"] == "policy_decision_required"
    assert by_id["goal_api_status_surface"]["template_required"] is False
    assert by_id["goal_api_status_surface"]["operator_input_required"] is False
    assert by_id["goal_api_status_surface"]["kit_status"] == "ready"
    assert by_id["goal_api_status_surface"]["api_endpoints"] == "/goal/status;/goal/api-contract"
    assert by_id["goal_api_status_surface"]["release_burndown_surfaced"] is False


def test_goal_operator_intake_kit_surfaces_accuracy_ligand_ranking_action(tmp_path: Path) -> None:
    action_board = _action_board()
    action_board["rows"].append(
        {
            "lane_id": "product_accuracy_parity",
            "action_type": "repair_ligand_ranking_parity",
            "status": "required",
            "required_input": "ACCURACY:ligand_ranking",
            "artifact_path": mod.DEFAULT_ACCURACY_PARITY_SCORECARD_JSON,
            "approval_token": "",
        }
    )
    action_board["summary"]["action_count"] = len(action_board["rows"])

    source_packets = _source_packets()
    source_packets[mod.DEFAULT_ACCURACY_PARITY_SCORECARD_JSON] = {
        "summary": {"status": "blocked_accuracy_parity"}
    }
    payload = mod.build_goal_operator_intake_kit(
        action_board_packet=action_board,
        release_burndown_packet=_release_burndown(),
        source_packets=source_packets,
        out_dir=tmp_path / "kit",
    )

    by_id = {row["kit_entry_id"]: row for row in payload["rows"]}
    accuracy = by_id["accuracy_ligand_ranking_repair"]
    assert accuracy["kit_status"] == "operator_input_required"
    assert accuracy["current_action_surfaced"] is True
    assert accuracy["operator_input_required"] is True
    assert accuracy["operator_input_required_now"] is True
    assert accuracy["source_gate_status"] == "blocked_accuracy_parity"
    assert accuracy["source_artifacts"] == mod.DEFAULT_ACCURACY_PARITY_SCORECARD_JSON
    assert accuracy["input_kind"] == "ligand_ranking_parity_repair_action"
    assert "PR-AUC" in accuracy["recommended_action"]


def test_goal_operator_intake_kit_surfaces_registry_promotion_receipt_for_current_action(tmp_path: Path) -> None:
    action_board = _action_board()
    registry_action = {
        "lane_id": "product_ai_production",
        "action_type": "complete_residual_registry_guarded_promotion",
        "status": "required",
        "artifact_path": "runs/product_goal_completion_audit_current.json;runs/residual_model_registry_current.json",
        "approval_token": mod.PRODUCTION_AI_REGISTRY_PROMOTION_APPROVAL_TOKEN,
        "required_input": (
            "production_promotion_allowed;customer_facing_auto_correction_allowed;"
            "customer_facing_score_mutation_allowed;customer_facing_ranking_mutation_allowed;"
            "default_residual_mode;trained_model_checkpoint_count"
        ),
    }
    action_board["rows"] = [registry_action]
    action_board["summary"].update(
        {
            "primary_action_id": "product_ai_production:complete_residual_registry_guarded_promotion",
            "top_action_id": "product_ai_production:complete_residual_registry_guarded_promotion",
            "primary_action_type": "complete_residual_registry_guarded_promotion",
            "primary_action_required_input": registry_action["required_input"],
            "primary_action_artifact_path": registry_action["artifact_path"],
        }
    )

    payload = mod.build_goal_operator_intake_kit(
        action_board_packet=action_board,
        release_burndown_packet=_release_burndown(),
        source_packets=_source_packets(),
        out_dir=tmp_path / "kit",
    )

    summary = payload["summary"]
    by_id = {row["kit_entry_id"]: row for row in payload["rows"]}
    registry = by_id["production_ai_registry_promotion"]
    assert summary["primary_action_id"] == "product_ai_production:complete_residual_registry_guarded_promotion"
    assert summary["current_action_approval_tokens"] == [
        mod.PRODUCTION_AI_REGISTRY_PROMOTION_APPROVAL_TOKEN
    ]
    assert registry["kit_status"] == "operator_input_required"
    assert registry["current_action_surfaced"] is True
    assert registry["operator_input_required_now"] is True
    assert registry["source_gate_status"] == "blocked_production_ai_registry_promotion_operator_receipt"
    assert registry["related_source_json"] == mod.DEFAULT_PRODUCT_GOAL_COMPLETION_AUDIT_JSON
    assert registry["priority_source_json"] == mod.DEFAULT_PRODUCTION_AI_REGISTRY_PROMOTION_PRIORITY_JSON
    assert registry["priority_top_gate_id"] == "default_residual_mode_guarded"
    assert registry["priority_top_priority_bucket"] == "guarded_residual_mode_selection_required"
    assert registry["template_path"] == "config/production_ai_registry_promotion_operator_receipt_current.csv"
    assert registry["intake_path"] == "config/production_ai_registry_promotion_operator_receipt_current.csv"
    assert registry["approval_token_required"] == mod.PRODUCTION_AI_REGISTRY_PROMOTION_APPROVAL_TOKEN


def test_goal_operator_intake_kit_suppresses_stale_api_install_entry_when_runtime_ready(tmp_path: Path) -> None:
    action_board = _action_board()
    action_board["rows"] = [
        row for row in action_board["rows"] if row["action_type"] != "repair_cameo_receiver_runtime_smoke"
    ]

    payload = mod.build_goal_operator_intake_kit(
        action_board_packet=action_board,
        release_burndown_packet=_release_burndown_runtime_ready_registration_only(),
        source_packets=_source_packets(),
        out_dir=tmp_path / "kit",
    )

    by_id = {row["kit_entry_id"]: row for row in payload["rows"]}
    api_entry = by_id["cameo_api_dependency_install"]
    registration_entry = by_id["cameo_public_registration"]
    assert api_entry["kit_status"] == "not_surfaced"
    assert api_entry["approval_token_required"] == ""
    assert api_entry["release_burndown_surfaced"] is False
    assert registration_entry["kit_status"] == "approval_required"
    assert registration_entry["release_burndown_surfaced"] is True
    assert "APPROVE_API_DEPENDENCY_INSTALL" not in payload["summary"]["approval_tokens"]
    assert "APPROVE_API_DEPENDENCY_INSTALL" not in payload["summary"]["current_action_approval_tokens"]


def test_goal_operator_intake_kit_blocks_when_required_template_is_missing(tmp_path: Path) -> None:
    missing_template = tmp_path / "missing.csv"
    original_catalog = mod.CATALOG
    try:
        mod.CATALOG = [
            {
                "kit_entry_id": "missing",
                "lane_id": "test",
                "action_types": ["fill"],
                "input_kind": "approval_intake",
                "source_gate_json": "",
                "template_path": str(missing_template),
                "intake_path": str(tmp_path / "intake.csv"),
            }
        ]
        payload = mod.build_goal_operator_intake_kit(
            action_board_packet={"rows": []},
            source_packets={},
            out_dir=tmp_path / "kit",
        )
    finally:
        mod.CATALOG = original_catalog

    assert payload["summary"]["status"] == "blocked_goal_operator_intake_kit"
    assert payload["summary"]["template_missing_count"] == 1
    assert payload["rows"][0]["template_present"] is False


def test_goal_operator_intake_kit_tool_writes_manifest_and_copies_templates(tmp_path: Path) -> None:
    template_names = [
        "cameo_official.csv",
        "cameo_official_result_fetch.csv",
        "cameo_registration.csv",
        "product_execution.csv",
        "api_runner_profile_promotion.csv",
        "product_license.csv",
        "gpu_return_manifest.csv",
        "gpu_return_summary.json",
        "production_ai_registry_promotion.csv",
        "scope_transporter_manual_review.csv",
        "scope_pxr_exact_evidence_review.csv",
        "product_scope_breadth_evidence_receipt.csv",
        "engine_refinement_claim_evidence_receipt.csv",
        "cleanup_approval.csv",
        "protected_policy.csv",
    ]
    template_paths = [tmp_path / name for name in template_names]
    for path in template_paths:
        path.write_text("field\nOPERATOR_FILL\n", encoding="utf-8")

    original_catalog = mod.CATALOG
    try:
        mod.CATALOG = [
            {**entry, "template_path": str(path)}
            for entry, path in zip([entry for entry in original_catalog if entry.get("template_required") is not False], template_paths)
        ] + [entry for entry in original_catalog if entry.get("template_required") is False]
        action_board = tmp_path / "action_board.json"
        action_board.write_text(json.dumps(_action_board()) + "\n", encoding="utf-8")
        release_burndown = tmp_path / "release_burndown.json"
        release_burndown.write_text(json.dumps(_release_burndown()) + "\n", encoding="utf-8")
        source_paths: dict[str, Path] = {}
        for source_path, packet in _source_packets().items():
            path = tmp_path / Path(source_path).name
            path.write_text(json.dumps(packet) + "\n", encoding="utf-8")
            source_paths[source_path] = path
        out_dir = tmp_path / "kit"
        out_json = out_dir / "manifest.json"
        out_csv = out_dir / "manifest.csv"
        out_md = out_dir / "README.md"

        mod.main(
            [
                "--action-board-json",
                str(action_board),
                "--release-burndown-json",
                str(release_burndown),
                "--cameo-official-results-gate-json",
                str(source_paths[mod.DEFAULT_CAMEO_OFFICIAL_RESULTS_GATE_JSON]),
                "--cameo-official-result-fetch-preflight-json",
                str(source_paths[mod.DEFAULT_CAMEO_OFFICIAL_RESULT_FETCH_PREFLIGHT_JSON]),
                "--cameo-registration-gate-json",
                str(source_paths[mod.DEFAULT_CAMEO_REGISTRATION_GATE_JSON]),
                "--product-execution-gate-json",
                str(source_paths[mod.DEFAULT_PRODUCT_EXECUTION_GATE_JSON]),
                "--api-runner-profile-promotion-receipt-json",
                str(source_paths[mod.DEFAULT_API_RUNNER_PROFILE_PROMOTION_RECEIPT_JSON]),
                "--production-ai-registry-promotion-receipt-json",
                str(source_paths[mod.DEFAULT_PRODUCTION_AI_REGISTRY_PROMOTION_RECEIPT_JSON]),
                "--production-ai-registry-promotion-priority-json",
                str(source_paths[mod.DEFAULT_PRODUCTION_AI_REGISTRY_PROMOTION_PRIORITY_JSON]),
                "--product-commercial-independence-json",
                str(source_paths[mod.DEFAULT_PRODUCT_COMMERCIAL_INDEPENDENCE_JSON]),
                "--product-license-gate-json",
                str(source_paths[mod.DEFAULT_PRODUCT_LICENSE_GATE_JSON]),
                "--production-ai-gpu-return-intake-json",
                str(source_paths[mod.DEFAULT_PRODUCTION_AI_GPU_RETURN_INTAKE_JSON]),
                "--product-scope-evidence-intake-readiness-json",
                str(source_paths[mod.DEFAULT_PRODUCT_SCOPE_EVIDENCE_INTAKE_READINESS_JSON]),
                "--product-scope-evidence-priority-json",
                str(source_paths[mod.DEFAULT_PRODUCT_SCOPE_EVIDENCE_PRIORITY_JSON]),
                "--product-scope-breadth-evidence-receipt-json",
                str(source_paths[mod.DEFAULT_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT_JSON]),
                "--cleanup-approval-gate-json",
                str(source_paths[mod.DEFAULT_CLEANUP_APPROVAL_GATE_JSON]),
                "--protected-policy-gate-json",
                str(source_paths[mod.DEFAULT_PROTECTED_POLICY_GATE_JSON]),
                "--engine-refinement-claim-evidence-receipt-json",
                str(source_paths[mod.DEFAULT_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT_JSON]),
                "--goal-api-surface-contract-json",
                str(source_paths[mod.DEFAULT_GOAL_API_SURFACE_CONTRACT_JSON]),
                "--out-dir",
                str(out_dir),
                "--out-json",
                str(out_json),
                "--out-csv",
                str(out_csv),
                "--out-md",
                str(out_md),
            ]
        )
    finally:
        mod.CATALOG = original_catalog

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["template_copied_count"] == 15
    assert payload["summary"]["release_burndown_linked_entry_count"] == 12
    assert payload["summary"]["goal_api_surface_contract_status"] == "goal_api_surface_contract_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("kit_entry_id,lane_id,")
    md = out_md.read_text(encoding="utf-8")
    assert "Goal Operator Intake Kit" in md
    assert "release sequence" in md
    assert (out_dir / "templates" / "cameo_official_result_fetch.csv").read_text(
        encoding="utf-8"
    ).startswith("field")
    assert (out_dir / "templates" / "product_license.csv").read_text(encoding="utf-8").startswith("field")
    assert (out_dir / "templates" / "gpu_return_summary.json").read_text(encoding="utf-8").startswith("field")
    assert (out_dir / "templates" / "production_ai_registry_promotion.csv").read_text(
        encoding="utf-8"
    ).startswith("field")
    assert (out_dir / "templates" / "scope_transporter_manual_review.csv").read_text(
        encoding="utf-8"
    ).startswith("field")
    assert (out_dir / "templates" / "scope_pxr_exact_evidence_review.csv").read_text(
        encoding="utf-8"
    ).startswith("field")
