from __future__ import annotations

import json
from pathlib import Path

from tools import build_product_goal_completion_audit as mod


def _architecture(*, release_ready: bool = False, commercial_ready: bool = False) -> dict:
    return {
        "summary": {
            "status": "product_architecture_contract_ready" if release_ready else "blocked_product_architecture_contract",
            "architecture_release_ready": release_ready,
            "structure_analysis_product_surface_ready": True,
            "ligand_docking_execution_contract_ready": True,
            "scoring_ranking_contract_ready": True,
            "local_delivery_bundle_validation_ready": True,
            "product_service_boundary_ready": True,
            "product_api_contract_ready": True,
            "public_benchmark_validation_ready": True,
            "public_benchmark_requires_24h_server": False,
            "public_benchmark_requires_competition_season": False,
            "public_benchmark_requires_paid_vps": False,
            "commercial_independence_ready": commercial_ready,
        },
        "production_inference_acceptance_matrix": [
            {
                "stage_id": "gpu_return_acceptance",
                "status": "blocked",
                "release_blocker": True,
                "artifact": "runs/residual_force_gpu_worker_return_receipt_current.json",
                "validation_command": "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
                "required_checks": ["force_gpu_worker_return_receipt_ready"],
                "unlock_fields": [
                    "delta_force",
                    "uncertainty",
                    "abstention_reason",
                    "stage2_route_decision",
                ],
                "next_action": (
                    "Return full regeneration summary/manifest, NPZ paths, operator verification, identity coverage, "
                    "and post-run force derivation validation."
                ),
            },
            {
                "stage_id": "force_derivation_acceptance",
                "status": "blocked",
                "release_blocker": True,
                "artifact": "runs/residual_force_derivation_validation_current.json",
                "validation_command": "python3 tools/build_residual_force_derivation_validation.py",
                "required_checks": [
                    "force_gpu_worker_return_receipt_ready",
                    "delta_force_derivation_validation_ready",
                ],
                "unlock_fields": ["delta_force"],
                "next_action": "Rerun force derivation validation after the GPU return receipt is accepted.",
            },
            {
                "stage_id": "production_training_data_acceptance",
                "status": "blocked",
                "release_blocker": True,
                "artifact": "runs/residual_production_training_data_contract_current.json",
                "validation_command": "python3 tools/build_residual_production_training_data_contract.py",
                "required_checks": ["production_training_data_ready"],
                "unlock_fields": [
                    "delta_force",
                    "uncertainty",
                    "abstention_reason",
                    "stage2_route_decision",
                ],
                "next_action": "Run the full GPU regeneration command and return the current summary JSON.",
            },
            {
                "stage_id": "production_score_model_acceptance",
                "status": "blocked",
                "release_blocker": True,
                "artifact": "runs/residual_production_score_model_current.json",
                "validation_command": "python3 tools/train_residual_production_score_model.py",
                "required_checks": [
                    "ready_checkpoint_count_positive",
                    "production_output_policy_complete",
                ],
                "unlock_fields": [
                    "delta_score",
                    "corrected_score",
                    "delta_energy",
                    "delta_force",
                    "uncertainty",
                    "abstention_reason",
                    "stage2_route_decision",
                ],
                "next_action": "Train or rebuild a production residual score model with the full output-head contract.",
            },
            {
                "stage_id": "checkpoint_sidecar_acceptance",
                "status": "blocked",
                "release_blocker": True,
                "artifact": "runs/residual_production_checkpoint_sidecar_current.json",
                "validation_command": "python3 tools/build_residual_production_checkpoint_sidecar.py",
                "required_checks": [
                    "selected_sidecar_ready",
                    "selected_sidecar_training_contract_ready",
                    "selected_sidecar_force_receipt_ready",
                ],
                "unlock_fields": ["delta_force"],
                "next_action": "Build sidecar metadata with full output contract and force-receipt provenance.",
            },
            {
                "stage_id": "checkpoint_preflight_acceptance",
                "status": "blocked",
                "release_blocker": True,
                "artifact": "runs/residual_production_checkpoint_work_order_current.json",
                "validation_command": (
                    "python3 tools/build_residual_production_checkpoint_preflight.py && "
                    "python3 tools/build_residual_production_checkpoint_work_order.py"
                ),
                "required_checks": [
                    "checkpoint_preflight_ready",
                    "ready_checkpoint_count_positive",
                ],
                "unlock_fields": [],
                "next_action": "Rerun checkpoint preflight after the sidecar and output contracts are ready.",
            },
            {
                "stage_id": "registry_guarded_promotion_acceptance",
                "status": "blocked",
                "release_blocker": True,
                "artifact": "runs/residual_model_registry_current.json",
                "validation_command": (
                    "python3 tools/build_residual_model_registry.py && "
                    "python3 tools/build_product_production_ai_checkpoint_readiness.py"
                ),
                "required_checks": [
                    "registry_customer_facing_promotion_allowed",
                    "trained_model_checkpoint_count_positive",
                    "default_residual_mode_guarded",
                ],
                "unlock_fields": [],
                "next_action": "Rebuild the residual registry after a preflight-ready checkpoint is available.",
            },
        ],
    }


def _release_dossier(*, release_ready: bool = False, commercial_ready: bool = False) -> dict:
    return {
        "summary": {
            "status": "product_release_operations_dossier_ready" if release_ready else "blocked_product_release_operations_dossier",
            "architecture_release_ready": release_ready,
            "commercial_independence_ready": commercial_ready,
            "bundle_validation_passed": release_ready,
            "delivery_ready_claim_allowed": release_ready,
            "pilot_delivery_ready": release_ready,
        }
    }


def _public_benchmark() -> dict:
    return {
        "summary": {
            "status": "product_public_benchmark_contract_ready",
            "public_benchmark_validation_ready": True,
            "ready_required_suite_count": 5,
            "blocked_suite_count": 0,
            "suite_no_external_dependency_count": 5,
        }
    }


def _commercial(*, ready: bool = False) -> dict:
    return {
        "summary": {
            "status": "product_commercial_independence_gate_ready" if ready else "blocked_product_commercial_independence_gate",
            "commercial_independent_product_claim_allowed": ready,
            "license_present": ready,
            "dependency_provenance_manifest_present": True,
            "reproducible_install_manifest_ready": True,
            "local_delivery_bundle_ready": True,
            "local_self_hosted_api_cli_ready": True,
            "local_self_hosted_operation_ready": True,
            "external_saas_runtime_dependency_count": 0,
        }
    }


def _license_work_order(*, ready: bool = False) -> dict:
    return {
        "summary": {
            "status": "product_license_file_creation_work_order_ready" if ready else "blocked_product_license_file_creation_work_order",
            "license_file_creation_review_ready": ready,
        }
    }


def _cameo() -> dict:
    return {
        "summary": {
            "receiver_api_readiness_ready": True,
            "validation_operations_surface_ready": True,
            "local_validation_protocol_ready": True,
            "cameo_live_validation_required_for_product_release": False,
            "registration_required_for_product_release": False,
            "official_results_required_for_product_release": False,
        }
    }


def _release_gate(*, ready: bool = False) -> dict:
    return {
        "summary": {
            "status": "goal_release_ready" if ready else "blocked_goal_release_decision",
            "release_allowed": ready,
            "cameo_official_results_pending_honest": True,
            "cameo_no_local_native_accuracy_substitution": True,
        }
    }


def _bottleneck() -> dict:
    return {
        "summary": {
            "status": "goal_bottleneck_briefing_ready",
            "primary_bottleneck_phase": "P1_product_commercial_independence",
            "primary_bottleneck_kind": "operator_approval_required",
            "approval_tokens_required": ["APPROVE_PRODUCT_LICENSE_FILE_CREATION"],
        }
    }


def _burndown() -> dict:
    return {
        "summary": {"status": "goal_release_burndown_work_order_ready"},
        "rows": [
            {
                "phase": "P1_product_commercial_independence",
                "command": "python3 tools/fill_product_license_decision_operator_intake.py --approval-token APPROVE_PRODUCT_LICENSE_FILE_CREATION",
                "license_local_source_command_examples": (
                    "python3 tools/fill_product_license_decision_operator_intake.py "
                    "--approval-token APPROVE_PRODUCT_LICENSE_FILE_CREATION "
                    "--spdx-license-id Apache-2.0 "
                    "--license-text-source /usr/share/common-licenses/Apache-2.0 "
                    "--copyright-holder OPERATOR_FILL_HOLDER "
                    "--effective-year OPERATOR_FILL_YEAR "
                    "--out-csv runs/product_license_decision_operator_intake.csv"
                ),
            }
        ],
    }


def _production_ai_bottleneck() -> dict:
    return {
        "summary": {
            "status": "goal_bottleneck_briefing_ready",
            "primary_bottleneck_phase": "P0_product_ai_architecture_production_inference_closure",
            "primary_bottleneck_kind": "production_ai_checkpoint_evidence_required",
            "approval_tokens_required": [],
        }
    }


def _production_ai_burndown() -> dict:
    command = (
        "python3 tools/build_residual_force_gpu_worker_return_receipt.py && "
        "python3 tools/build_residual_force_derivation_validation.py && "
        "python3 tools/build_residual_production_training_data_contract.py && "
        "python3 tools/build_residual_production_checkpoint_preflight.py && "
        "python3 tools/build_residual_model_registry.py && "
        "python3 tools/build_product_goal_completion_audit.py"
    )
    return {
        "summary": {"status": "goal_release_burndown_work_order_ready"},
        "rows": [
            {
                "phase": "P0_product_ai_architecture_production_inference_closure",
                "command": command,
            }
        ],
    }


def _residual_model_registry() -> dict:
    return {
        "summary": {
            "status": "residual_model_registry_ready",
            "registry_ready": True,
            "product_model_layer_ready": True,
            "default_residual_mode": "shadow",
            "production_promotion_allowed": False,
            "production_mode_allowed": False,
            "customer_facing_auto_correction_allowed": False,
            "customer_facing_score_mutation_allowed": False,
            "customer_facing_ranking_mutation_allowed": False,
            "trained_model_checkpoint_count": 0,
            "checkpoint_preflight_ready": False,
            "production_checkpoint_blocked": True,
            "production_promotion_blocked_reason": "production checkpoint preflight is blocked",
            "checkpoint_primary_blocker": "missing_output_fields:delta_force",
            "checkpoint_missing_output_fields": ["delta_force"],
            "checkpoint_missing_adapter_output_policy_fields": ["delta_force"],
            "selected_sidecar_ready": False,
            "selected_sidecar_missing_output_fields": ["delta_force"],
        }
    }


def _ai_gap(*, ready: bool = True) -> dict:
    rows = [
        {
            "gap_id": "production_ai_inference_checkpoint",
            "domain": "ai_inference",
            "status": "closed" if ready else "open",
            "observed": "trained_model_checkpoint_count=1" if ready else "trained_model_checkpoint_count=0",
        },
        {
            "gap_id": "closed_loop_structure_docking_ai_graph",
            "domain": "ai_decision_graph",
            "status": "closed",
            "observed": "closed_loop_decision_graph_ready=True",
        },
        {
            "gap_id": "durable_job_orchestration",
            "domain": "product_operations",
            "status": "closed",
            "observed": (
                "queue_lifecycle_progress_ready=True;"
                "customer_run_history_lineage_ready=True;"
                "worker_backend_contract_ready=True"
            ),
        },
        {
            "gap_id": "production_trajectory_sla",
            "domain": "runtime_sla",
            "status": "closed",
            "observed": (
                "production_trajectory_sla_ready=True;"
                "sla_claim_tier=restricted_family_sla;"
                "current_rocm_baseline_claim_scope=single_target_gpcr_baseline;"
                "current_rocm_baseline_production_profile_enabled=False;"
                "rocm_baseline_profile_gap_acknowledged=True;"
                "restricted_sla_backed_by_historical_profile_artifacts=True;"
                "broad_platform_sla_allowed=False"
            ),
        },
        {
            "gap_id": "scope_breadth_expansion",
            "domain": "scientific_scope",
            "status": "closed" if ready else "open",
            "observed": "general_platform_claim_allowed=True" if ready else "blocked_claim_scopes=transporter_domain_promotion",
        },
        {
            "gap_id": "ai_analysis_report_ux",
            "domain": "customer_ux",
            "status": "closed",
            "observed": (
                "ai_report_ux_ready=True;"
                "counterfactual_rescue_suggestion_ready=True;"
                "customer_report_delivery_contract_ready=True;"
                "customer_report_evidence_binding_ready=True;"
                "customer_report_viewer_binding_ready=True;"
                "viewer_customer_report_binding_ready=True;"
                "customer_report_ready_block_count=6;"
                "customer_report_required_block_count=6;"
                "customer_report_blocked_block_count=0"
            ),
        },
        {
            "gap_id": "security_deployment_operations",
            "domain": "security_deployment",
            "status": "closed",
            "observed": (
                "security_deployment_ready=True;"
                "hosted_deployment_contract_ready=True;"
                "hosted_deployment_currently_satisfied=False;"
                "hosted_deployment_next_stage_id=operator_exposure_approval;"
                "hosted_external_exposure_allowed=False;"
                "hosted_secret_injection_ready=False;"
                "tls_termination_operator_verified=False"
            ),
        },
    ]
    open_rows = [row for row in rows if row["status"] != "closed"]
    gap_blocker_matrix = []
    if not ready:
        gap_blocker_matrix = [
            {
                "gap_id": "production_ai_inference_checkpoint",
                "primary_blocker_id": "production_gpu_execution_environment_ready",
                "blocker_stage_id": "production_gpu_execution_environment_acceptance",
                "blocker_artifact": "runs/rocm_environment_manifest_current.json",
                "observed": "torch_rocm_ready=False;visible_device_count=0",
                "required": "ROCm/HIP runtime is visible to PyTorch with at least one AMD GPU",
                "next_action": (
                    "Expose a visible ROCm/HIP AMD GPU device to PyTorch before production regeneration."
                ),
                "validation_command": "python3 tools/build_rocm_environment_manifest.py",
                "operator_input_fields": ["visible_device_count"],
                "next_after_blocker_stage_id": "gpu_return_acceptance",
                "next_after_blocker_artifact": "runs/residual_force_gpu_worker_return_receipt_current.json",
                "next_after_blocker_validation_command": (
                    "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
                ),
                "next_after_blocker_next_action": (
                    "Return full regeneration summary/manifest, NPZ paths, operator verification, identity coverage, and post-run force derivation validation."
                ),
                "next_after_blocker_required_checks": ["gpu_worker_return_receipt_ready"],
                "next_after_blocker_unlock_fields": [
                    "summary_manifest_bound",
                    "identity_coverage_ready",
                    "post_run_derivation_validation_ready",
                    "production_gpu_backend_provenance_ready",
                ],
                "parallelizable_workstream": False,
                "unlock_claim": "production_ai_inference_subject",
            },
            {
                "gap_id": "scope_breadth_expansion",
                "primary_blocker_id": "AQP1.core_binder_01",
                "blocker_stage_id": "transporter_claim_acceptance",
                "blocker_artifact": "runs/transporter_manual_review_intake_template_current.csv",
                "observed": "transporter_unresolved_slots=11;next_slot_id=AQP1.core_binder_01",
                "required": "exact target-pair transporter evidence resolves the next open P0 slot",
                "next_action": "Acquire exact AQP1 binder kcal evidence.",
                "validation_command": "python3 tools/build_product_scope_breadth_contract.py",
                "operator_input_fields": ["target_id", "candidate_ligand_id", "reference_binding_kcal_mol"],
                "required_exact_evidence_fields": [
                    "target_id",
                    "candidate_ligand_id",
                    "direct_binding_or_claim_safe_kcal_basis",
                    "reference_binding_kcal_mol",
                ],
                "required_claim_guardrails": [
                    "functional_surrogate_does_not_authorize_direct_binding_claim",
                ],
                "claim_safe_completion_rule": (
                    "Provide exact target-pair quantitative evidence before promotion."
                ),
                "source_modality_triage_artifact": (
                    "runs/aqp1_binding_source_modality_triage_current.json"
                ),
                "source_modality_triage_decision": (
                    "keep_blocked_until_direct_experimental_or_operator_verified_claim_safe_binding_kcal"
                ),
                "source_modality_direct_experimental_binding_row_count": 0,
                "source_modality_claim_safe_binding_kcal_ready_count": 0,
                "source_modality_computational_binding_energy_row_count": 1,
                "source_modality_best_computational_binding_energy_kcal_mol": "-34.48",
                "parallelizable_workstream": True,
                "unlock_claim": "transporter_domain_promotion",
            },
        ]
    return {
        "summary": {
            "status": "product_ai_architecture_gap_closure_complete" if ready else "blocked_product_ai_architecture_gap_closure",
            "all_gaps_closed": ready,
            "gap_count": len(rows),
            "closed_gap_count": len(rows) - len(open_rows),
            "open_gap_count": len(open_rows),
            "closed_gap_ids": [row["gap_id"] for row in rows if row["status"] == "closed"],
            "open_gap_ids": [row["gap_id"] for row in open_rows],
            "current_primary_open_gap": "none" if ready else open_rows[0]["gap_id"],
            "gap_blocker_matrix_ready": True,
            "gap_blocker_matrix_count": len(gap_blocker_matrix),
            "gap_blocker_matrix": gap_blocker_matrix,
            "current_primary_blocker_gap_id": gap_blocker_matrix[0]["gap_id"] if gap_blocker_matrix else "",
            "current_primary_blocker_id": gap_blocker_matrix[0]["primary_blocker_id"] if gap_blocker_matrix else "",
            "current_primary_blocker_artifact": gap_blocker_matrix[0]["blocker_artifact"] if gap_blocker_matrix else "",
            "current_primary_blocker_validation_command": (
                gap_blocker_matrix[0]["validation_command"] if gap_blocker_matrix else ""
            ),
            "parallelizable_gap_blocker_count": 1 if gap_blocker_matrix else 0,
            "parallelizable_gap_blocker_ids": ["AQP1.core_binder_01"] if gap_blocker_matrix else [],
            "first_parallelizable_gap_id": "scope_breadth_expansion" if gap_blocker_matrix else "",
            "first_parallelizable_blocker_id": "AQP1.core_binder_01" if gap_blocker_matrix else "",
            "first_parallelizable_blocker_artifact": (
                "runs/transporter_manual_review_intake_template_current.csv" if gap_blocker_matrix else ""
            ),
            "first_parallelizable_blocker_next_action": (
                "Acquire exact AQP1 binder kcal evidence." if gap_blocker_matrix else ""
            ),
            "first_parallelizable_blocker_validation_command": (
                "python3 tools/build_product_scope_breadth_contract.py" if gap_blocker_matrix else ""
            ),
            "first_parallelizable_blocker_operator_input_fields": (
                ["target_id", "candidate_ligand_id", "reference_binding_kcal_mol"]
                if gap_blocker_matrix
                else []
            ),
            "first_parallelizable_blocker_required_exact_evidence_fields": (
                [
                    "target_id",
                    "candidate_ligand_id",
                    "direct_binding_or_claim_safe_kcal_basis",
                    "reference_binding_kcal_mol",
                ]
                if gap_blocker_matrix
                else []
            ),
            "first_parallelizable_blocker_required_claim_guardrails": (
                ["functional_surrogate_does_not_authorize_direct_binding_claim"]
                if gap_blocker_matrix
                else []
            ),
            "first_parallelizable_blocker_claim_safe_completion_rule": (
                "Provide exact target-pair quantitative evidence before promotion."
                if gap_blocker_matrix
                else ""
            ),
            "first_parallelizable_blocker_unlock_claim": (
                "transporter_domain_promotion" if gap_blocker_matrix else ""
            ),
            "first_parallelizable_blocker_source_modality_triage_artifact": (
                "runs/aqp1_binding_source_modality_triage_current.json"
                if gap_blocker_matrix
                else ""
            ),
            "first_parallelizable_blocker_source_modality_triage_decision": (
                "keep_blocked_until_direct_experimental_or_operator_verified_claim_safe_binding_kcal"
                if gap_blocker_matrix
                else ""
            ),
            "first_parallelizable_blocker_source_modality_direct_experimental_binding_row_count": (
                0 if gap_blocker_matrix else 0
            ),
            "first_parallelizable_blocker_source_modality_claim_safe_binding_kcal_ready_count": (
                0 if gap_blocker_matrix else 0
            ),
            "first_parallelizable_blocker_source_modality_computational_binding_energy_row_count": (
                1 if gap_blocker_matrix else 0
            ),
            "first_parallelizable_blocker_source_modality_best_computational_binding_energy_kcal_mol": (
                "-34.48" if gap_blocker_matrix else ""
            ),
        },
        "rows": rows,
    }


def _ai_backlog(*, ready: bool = True, observed: str = "") -> dict:
    primary_id = "none" if ready else "scope_breadth.transporter.AQP1.core_binder_01"
    work_item_count = 0 if ready else 21
    return {
        "summary": {
            "status": "product_ai_architecture_execution_backlog_clear" if ready else "product_ai_architecture_execution_backlog_ready",
            "backlog_clear": ready,
            "work_item_count": work_item_count,
            "release_blocking_work_item_count": 0,
            "scope_deferred_work_item_count": 0 if ready else work_item_count,
            "primary_work_item_id": primary_id,
            "scope_closure_detail": ""
            if ready
            else (
                "scope_closure_blocker_classes=direct_binding_evidence_missing=4,exact_negative_quantitative_value_missing=6;"
                "scope_closure_first_scientific_blocker=AQP1.core_binder_01;"
                "scope_closure_manual_review_subcheck_count=54;"
                "scope_closure_transporter_manual_review_subcheck_count=54;"
                "scope_closure_transporter_identity_scaffold_confirmation_required_count=11;"
                "scope_closure_transporter_direct_binding_or_kcal_confirmation_required_count=4;"
                "scope_closure_transporter_negative_quantitative_confirmation_required_count=6;"
                "scope_closure_pxr_reconciled_blocked_row_count=6;"
                "scope_closure_general_claim_blocker_count=4;"
                "scope_closure_authoritative_apply_allowed=False"
            ),
        },
        "rows": []
        if ready
        else [
            {
                "work_item_id": primary_id,
                "acceptance_criteria": "primary acceptance gate",
                "observed": observed or "manual_review_placeholders=11",
                "next_action": "close primary backlog row",
                "source_artifact": "runs/source_artifact.json",
                "verification_command": "python3 tools/verify_primary.py",
            }
        ],
    }


def _checkpoint_readiness() -> dict:
    return {
        "summary": {
            "status": "blocked_product_production_ai_checkpoint_readiness",
            "production_ai_checkpoint_ready": False,
            "failed_check_ids": ["production_training_data_ready", "force_gpu_worker_return_receipt_ready"],
            "first_failed_check_id": "production_training_data_ready",
            "first_failed_source_artifact": "runs/residual_production_training_data_contract_current.json",
            "first_failed_observed": "production_training_data_ready=False;missing=delta_force,uncertainty",
            "first_failed_required": "production training-data contract is ready with required output labels",
            "first_failed_next_action": "Close production training-data failed checks before checkpoint promotion.",
            "production_gpu_execution_environment_ready": False,
            "production_gpu_execution_environment_artifact_path": (
                "runs/rocm_environment_manifest_current.json"
            ),
            "production_gpu_execution_environment_status": "rocm_environment_manifest_ready",
            "production_gpu_rocm_manifest_ready": True,
            "production_gpu_rocm_stack_detected": True,
            "production_gpu_rocm_torch_ready": False,
            "production_gpu_rocm_amd_gpu_detected": True,
            "production_gpu_rocm_visible_device_count": 0,
            "production_gpu_rocm_device_names": [],
            "production_gpu_rocm_torch_version": "2.6.0+rocm6.1",
            "production_gpu_rocm_torch_hip_version": "6.1.40091-a8dbc0c19",
            "production_gpu_rocm_next_required_step": (
                "Expose at least one AMD ROCm/HIP device to PyTorch before running production regeneration."
            ),
            "production_gpu_rocm_visibility_diagnostic_commands": [
                "python3 tools/build_rocm_environment_manifest.py",
                "rocminfo",
                "python3 -c \"import torch; print(torch.cuda.device_count())\"",
            ],
            "production_gpu_rocm_visibility_diagnostic_command_count": 3,
            "production_gpu_rocm_visibility_diagnostic_required_fields": [
                "torch_rocm_ready",
                "visible_device_count",
                "device_names",
            ],
            "production_gpu_rocm_visibility_diagnostic_required_field_count": 3,
            "production_gpu_rocm_visibility_diagnostic_completion_rule": (
                "torch_rocm_ready=true; visible_device_count>0; device_names nonempty"
            ),
            "production_gpu_rocm_visibility_diagnostic_return_artifacts": [
                "runs/rocm_environment_manifest_current.json",
            ],
            "force_gpu_worker_handoff_ready": True,
            "force_gpu_worker_operator_action_required": True,
            "force_gpu_worker_operator_transfer_manifest_ready": True,
            "force_gpu_worker_operator_transfer_outbound_artifact_count": 9,
            "force_gpu_worker_operator_transfer_outbound_artifacts": [
                "runs/residual_force_trajectory_regeneration_queue_current.json",
                "runs/residual_force_trajectory_regeneration_queue_current.csv",
                "runs/residual_force_gpu_worker_return_manifest_template_current.json",
                "runs/residual_force_gpu_worker_return_manifest_template_current.csv",
                "runs/residual_force_gpu_worker_return_summary_template_current.json",
                "runs/residual_force_trajectory_regeneration_current_summary_template.json",
                "tools/generate_ligand_trajectory_engine.py",
                "tools/build_residual_force_trajectory_regeneration_execution_probe.py",
                "native PDB files referenced by regeneration_queue_csv.native_pdb_path",
            ],
            "force_gpu_worker_operator_transfer_inbound_artifact_count": 4,
            "force_gpu_worker_operator_transfer_inbound_artifacts": [
                "runs/residual_force_trajectory_regeneration_current_summary.json",
                "runs/residual_force_trajectory_regeneration_current_manifest.csv",
                "regenerated NPZ bundles referenced by returned manifest NPZ path columns",
                "runs/residual_force_trajectory_regeneration_execution_probe_current.json after rerun on the returned pilot/full run evidence",
            ],
            "force_gpu_worker_operator_transfer_first_return_artifact": (
                "runs/residual_force_trajectory_regeneration_current_summary.json"
            ),
            "force_gpu_worker_operator_transfer_return_manifest_artifact": (
                "runs/residual_force_trajectory_regeneration_current_manifest.csv"
            ),
            "force_gpu_worker_operator_transfer_acceptance_artifact": (
                "runs/residual_force_gpu_worker_return_receipt_current.json"
            ),
            "force_gpu_worker_operator_transfer_acceptance_ready_key": "gpu_worker_return_receipt_ready",
            "force_gpu_worker_operator_transfer_post_return_validation_command": (
                "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
            ),
            "force_gpu_worker_full_regeneration_command": "python3 tools/generate_ligand_trajectory_engine.py --prod-mode",
            "force_gpu_worker_post_return_validation_command": "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
            "force_gpu_worker_post_run_validation_commands": [
                "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
                "python3 tools/build_product_goal_completion_audit.py",
            ],
            "force_gpu_worker_post_return_required_production_output_fields": [
                "delta_score",
                "corrected_score",
                "delta_energy",
                "delta_force",
                "uncertainty",
                "abstention_reason",
                "stage2_route_decision",
            ],
            "force_gpu_worker_post_return_gpu_unlock_artifacts": [
                "runs/residual_force_gpu_worker_return_receipt_current.json",
                "runs/residual_production_training_data_contract_current.json",
            ],
            "force_gpu_worker_post_return_unlock_output_fields": [
                "delta_force",
                "uncertainty",
                "abstention_reason",
                "stage2_route_decision",
            ],
            "force_gpu_worker_post_return_min_expected_label_rows": 768,
            "force_gpu_worker_post_return_promotion_ladder_stage_count": 10,
            "force_gpu_worker_post_return_promotion_ladder_contract_ready": True,
            "force_gpu_worker_post_return_promotion_ladder_currently_satisfied": False,
            "force_gpu_worker_post_return_promotion_ladder_current_blocked_stage_count": 7,
            "force_gpu_worker_post_return_promotion_ladder_current_blocked_stage_ids": [
                "gpu_return_acceptance",
                "force_derivation_acceptance",
            ],
            "force_gpu_worker_post_return_promotion_ladder_current_next_stage_id": (
                "gpu_return_acceptance"
            ),
            "force_gpu_worker_post_return_promotion_ladder_current_next_stage_artifact": (
                "runs/residual_force_gpu_worker_return_receipt_current.json"
            ),
            "force_gpu_worker_post_return_promotion_ladder_current_next_stage_validation_command": (
                "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
            ),
            "force_gpu_worker_post_return_promotion_ladder_stage_ids": [
                "gpu_return_receipt",
                "product_goal_completion_audit",
            ],
            "force_gpu_worker_post_return_promotion_ladder_missing_ready_keys": [],
            "production_inference_acceptance_matrix_ready": True,
            "production_inference_acceptance_stage_count": 7,
            "production_inference_acceptance_ready_stage_count": 0,
            "production_inference_acceptance_blocked_stage_count": 7,
            "production_inference_acceptance_stage_ids": [
                "gpu_return_acceptance",
                "force_derivation_acceptance",
                "production_training_data_acceptance",
                "production_score_model_acceptance",
                "checkpoint_sidecar_acceptance",
                "checkpoint_preflight_acceptance",
                "registry_guarded_promotion_acceptance",
            ],
            "production_inference_acceptance_ready_stage_ids": [],
            "production_inference_acceptance_blocked_stage_ids": [
                "gpu_return_acceptance",
                "force_derivation_acceptance",
                "production_training_data_acceptance",
                "production_score_model_acceptance",
                "checkpoint_sidecar_acceptance",
                "checkpoint_preflight_acceptance",
                "registry_guarded_promotion_acceptance",
            ],
            "production_inference_acceptance_next_stage_id": "gpu_return_acceptance",
            "production_inference_acceptance_next_stage_artifact": (
                "runs/residual_force_gpu_worker_return_receipt_current.json"
            ),
            "production_inference_acceptance_next_stage_validation_command": (
                "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
            ),
            "production_inference_acceptance_next_stage_release_effect": (
                "returned GPU trajectory summary/manifest can be trusted as production force-label evidence"
            ),
            "production_inference_acceptance_next_stage_unlock_fields": [
                "delta_force",
                "uncertainty",
                "abstention_reason",
                "stage2_route_decision",
            ],
            "production_inference_acceptance_next_stage_required_checks": [
                "force_gpu_worker_return_receipt_ready"
            ],
            "production_inference_acceptance_next_stage_next_action": (
                "Return full regeneration summary/manifest, NPZ paths, operator verification, identity coverage, "
                "and post-run force derivation validation."
            ),
            "production_inference_actionable_blocker_stage_id": "gpu_return_acceptance",
            "production_inference_actionable_blocker_check_id": "force_gpu_worker_return_receipt_ready",
            "production_inference_actionable_blocker_artifact": (
                "runs/residual_force_gpu_worker_return_receipt_current.json"
            ),
            "production_inference_actionable_blocker_observed": (
                "gpu_worker_return_receipt_ready=False;expected_queue_rows=768"
            ),
            "production_inference_actionable_blocker_required": (
                "GPU return receipt covers queue, manifest, operator verification, and post-run force derivation"
            ),
            "production_inference_actionable_blocker_next_action": (
                "Return full regeneration summary/manifest, NPZ paths, operator verification, identity coverage, "
                "and post-run force derivation validation."
            ),
            "production_inference_actionable_blocker_validation_command": (
                "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
            ),
            "production_inference_actionable_blocker_unlock_fields": [
                "delta_force",
                "uncertainty",
                "abstention_reason",
                "stage2_route_decision",
            ],
            "production_inference_actionable_blocker_downstream_blocked_stage_count": 6,
            "production_inference_next_after_actionable_blocker_stage_id": "force_derivation_acceptance",
            "production_inference_next_after_actionable_blocker_artifact": (
                "runs/residual_force_derivation_validation_current.json"
            ),
            "production_inference_next_after_actionable_blocker_validation_command": (
                "python3 tools/build_residual_force_derivation_validation.py"
            ),
            "production_inference_next_after_actionable_blocker_required_checks": [
                "force_gpu_worker_return_receipt_ready",
                "delta_force_derivation_validation_ready",
            ],
            "production_inference_next_after_actionable_blocker_unlock_fields": ["delta_force"],
            "production_inference_next_after_actionable_blocker_next_action": (
                "Rerun force derivation validation after the GPU return receipt is accepted."
            ),
            "production_inference_actionable_blocker_blocks_registry_promotion": True,
            "production_inference_actionable_operator_completion_packet_ready": True,
            "production_inference_actionable_operator_completion_packet_artifact": (
                "runs/residual_force_gpu_worker_return_receipt_current.json"
            ),
            "production_inference_actionable_operator_completion_artifact_id": "gpu_worker_return_receipt_json",
            "production_inference_actionable_operator_completion_artifact_path": (
                "runs/residual_force_gpu_worker_return_receipt_current.json"
            ),
            "production_inference_actionable_operator_completion_expected_queue_rows": 768,
            "production_inference_actionable_operator_completion_required_fields_or_columns": [
                "manifest_csv",
                "summary_json",
                "operator_verified",
                "backend_counts",
            ],
            "production_inference_actionable_operator_completion_diagnostic_commands": [
                "python3 tools/build_rocm_environment_manifest.py",
                "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
            ],
            "production_inference_actionable_operator_completion_diagnostic_command_count": 2,
            "production_inference_actionable_operator_completion_diagnostic_required_fields": [
                "operator_verified",
                "backend_counts",
            ],
            "production_inference_actionable_operator_completion_diagnostic_required_field_count": 2,
            "production_inference_actionable_operator_completion_diagnostic_completion_rule": (
                "operator_verified=true; backend_counts includes production ROCm/HIP rows"
            ),
            "production_inference_actionable_operator_completion_diagnostic_return_artifacts": [
                "runs/residual_force_gpu_worker_return_receipt_current.json",
            ],
            "production_inference_actionable_operator_completion_torch_visibility_probe_command": (
                "python3 -c \"import torch; print(torch.cuda.device_count())\""
            ),
            "production_inference_actionable_operator_completion_failed_check_ids": [
                "gpu_worker_return_receipt_ready"
            ],
            "production_inference_actionable_operator_completion_template_payload_json": (
                "runs/residual_force_gpu_worker_return_summary_template_current.json"
            ),
            "production_inference_actionable_operator_completion_validation_command": (
                "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
            ),
            "production_inference_actionable_operator_completion_full_regeneration_command": (
                "python3 tools/generate_ligand_trajectory_engine.py --prod-mode"
            ),
            "production_inference_actionable_operator_completion_completion_rule": (
                "gpu_worker_return_receipt_ready=true; operator_verified=true; expected_queue_rows=768"
            ),
            "production_inference_actionable_operator_completion_backend_provenance_completion_rule": (
                "backend_counts includes production ROCm/HIP rows"
            ),
            "production_inference_actionable_operator_completion_next_action": (
                "Return the production GPU summary, manifest, NPZ bundles, and operator verification."
            ),
            "production_inference_actionable_operator_completion_packet": {
                "artifact_id": "gpu_worker_return_receipt_json",
                "artifact_path": "runs/residual_force_gpu_worker_return_receipt_current.json",
                "completion_rule": (
                    "gpu_worker_return_receipt_ready=true; operator_verified=true; expected_queue_rows=768"
                ),
                "expected_queue_rows": 768,
                "diagnostic_command_count": 2,
                "worker_runtime_receipt_contract": {
                    "artifact_id": "rocm_worker_runtime_receipt",
                    "completion_rule": "manifest_ready=true; torch_rocm_ready=true; visible_device_count>0",
                },
            },
            "production_inference_worker_runtime_receipt_contract_ready": True,
            "production_inference_worker_runtime_receipt_contract": {
                "contract_ready": True,
                "artifact_id": "rocm_worker_runtime_receipt",
                "required_fields_or_columns": [
                    "manifest_ready",
                    "torch_rocm_ready",
                    "amd_gpu_detected",
                    "visible_device_count",
                    "backend_counts",
                ],
                "completion_rule": (
                    "manifest_ready=true; torch_rocm_ready=true; visible_device_count>0"
                ),
                "post_environment_next_stage_id": "gpu_return_acceptance",
                "post_environment_next_artifact": (
                    "runs/residual_force_gpu_worker_return_receipt_current.json"
                ),
                "post_environment_validation_command": (
                    "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
                ),
                "full_regeneration_command": (
                    "python3 tools/generate_ligand_trajectory_engine.py --prod-mode"
                ),
                "guardrails": [
                    "cpu_fallback_does_not_satisfy_production_inference",
                ],
            },
            "production_inference_worker_runtime_receipt_required_fields_or_columns": [
                "manifest_ready",
                "torch_rocm_ready",
                "amd_gpu_detected",
                "visible_device_count",
                "backend_counts",
            ],
            "production_inference_worker_runtime_receipt_required_field_count": 5,
            "production_inference_worker_runtime_receipt_completion_rule": (
                "manifest_ready=true; torch_rocm_ready=true; visible_device_count>0"
            ),
            "production_inference_worker_runtime_receipt_post_environment_next_stage_id": (
                "gpu_return_acceptance"
            ),
            "production_inference_worker_runtime_receipt_post_environment_next_artifact": (
                "runs/residual_force_gpu_worker_return_receipt_current.json"
            ),
            "production_inference_worker_runtime_receipt_post_environment_validation_command": (
                "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
            ),
            "production_inference_worker_runtime_receipt_full_regeneration_command": (
                "python3 tools/generate_ligand_trajectory_engine.py --prod-mode"
            ),
            "production_inference_worker_runtime_receipt_guardrails": [
                "cpu_fallback_does_not_satisfy_production_inference",
            ],
            "gpu_receipt_manifest_identity_row_count": 0,
            "gpu_receipt_manifest_matched_queue_id_count": 0,
            "gpu_receipt_manifest_matched_expected_npz_count": 0,
            "gpu_receipt_manifest_matched_queue_fingerprint_count": 0,
            "force_derivation_input_ready": False,
            "delta_force_derivation_validation_ready": False,
        },
        "production_inference_acceptance_matrix": _architecture()["production_inference_acceptance_matrix"],
    }


def _gpu_return_intake() -> dict:
    return {
        "summary": {
            "status": "blocked_product_production_ai_gpu_return_intake",
            "gpu_return_intake_ready": True,
            "gpu_return_artifacts_ready": False,
            "check_count": 18,
            "fail_check_count": 15,
            "failed_check_ids": [
                "actual_summary_returned_complete",
                "actual_summary_manifest_bound",
                "actual_summary_out_manifest_csv_present",
                "actual_summary_out_manifest_csv_bound",
                "actual_summary_out_summary_json_bound",
                "actual_summary_manifest_row_counts_consistent",
                "actual_manifest_returned_complete",
                "actual_manifest_npz_paths_complete",
                "actual_manifest_npz_files_exist",
                "actual_manifest_npz_files_valid",
                "actual_manifest_npz_schema_valid",
                "actual_manifest_npz_identity_valid",
                "actual_manifest_operator_verified",
                "queue_manifest_identity_coverage",
                "post_run_force_derivation_validation",
            ],
            "operator_return_bundle_contract_ready": True,
            "operator_return_blocker_count": 15,
            "first_failed_check_id": "actual_summary_returned_complete",
            "first_failed_source_artifact": "runs/residual_force_trajectory_regeneration_current_summary.json",
            "first_failed_observed": (
                "summary_present=False;summary_complete=False;processed_rows=0;ok_rows=0"
            ),
            "first_failed_required": "actual returned summary satisfies the full-regeneration completion rule",
            "first_failed_next_action": (
                "Return runs/residual_force_trajectory_regeneration_current_summary.json after the full GPU run."
            ),
            "operator_return_required_artifacts": [
                "runs/residual_force_trajectory_regeneration_current_summary.json",
                "runs/residual_force_trajectory_regeneration_current_manifest.csv",
                "regenerated NPZ bundles referenced by the returned manifest",
                "runs/residual_force_derivation_validation_current.json",
            ],
            "operator_return_required_artifact_count": 4,
            "operator_return_artifact_completion_matrix_count": 4,
            "operator_return_artifact_completion_matrix": [
                {
                    "artifact_id": "returned_summary_json",
                    "artifact_path": "runs/residual_force_trajectory_regeneration_current_summary.json",
                    "status": "blocked",
                    "failed_check_ids": ["actual_summary_returned_complete"],
                    "required_fields_or_columns": [
                        "queue_rows",
                        "processed_rows",
                        "ok_rows",
                    ],
                },
                {
                    "artifact_id": "returned_manifest_csv",
                    "artifact_path": "runs/residual_force_trajectory_regeneration_current_manifest.csv",
                    "status": "blocked",
                    "failed_check_ids": ["actual_manifest_returned_complete"],
                    "required_fields_or_columns": [
                        "queue_id",
                        "expected_regenerated_trajectory_npz",
                        "status",
                        "operator_verified_npz_exists",
                    ],
                },
                {
                    "artifact_id": "returned_npz_bundles",
                    "artifact_path": "regenerated NPZ bundles referenced by manifest",
                    "status": "blocked",
                    "failed_check_ids": ["actual_manifest_npz_files_exist"],
                    "required_fields_or_columns": [
                        "protein_ca",
                        "ligand_frames",
                        "queue_id",
                    ],
                },
                {
                    "artifact_id": "post_run_force_derivation_validation",
                    "artifact_path": "runs/residual_force_derivation_validation_current.json",
                    "status": "blocked",
                    "failed_check_ids": ["post_run_force_derivation_validation"],
                    "required_fields_or_columns": ["delta_force"],
                },
            ],
            "operator_return_artifact_completion_blocker_count": 4,
            "operator_return_next_artifact_completion_packet_ready": True,
            "operator_return_next_artifact_completion_packet": {
                "artifact_id": "returned_summary_json",
                "artifact_path": "runs/residual_force_trajectory_regeneration_current_summary.json",
                "template_payload_json": "runs/residual_force_trajectory_regeneration_current_summary_template.json",
                "template_payload": {
                    "queue_rows": 768,
                    "processed_rows": "GPU_WORKER_FILL_PROCESSED_ROWS",
                    "ok_rows": "GPU_WORKER_FILL_OK_ROWS",
                    "failed_rows": "GPU_WORKER_FILL_FAILED_ROWS",
                    "out_manifest_csv": "runs/residual_force_trajectory_regeneration_current_manifest.csv",
                    "out_summary_json": "runs/residual_force_trajectory_regeneration_current_summary.json",
                    "prod_mode": True,
                    "require_rust_hip": True,
                    "backend_counts": {"rust_hip_rollout": "GPU_WORKER_FILL_OK_ROWS"},
                },
                "completion_rule": "queue_rows equals expected_queue_rows; processed_rows>=expected_queue_rows",
                "backend_provenance_completion_rule": "backend_counts has rust_hip* rows",
                "full_regeneration_command": "python3 tools/generate_ligand_trajectory_engine.py --prod-mode",
                "validation_command": "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
                "failed_check_ids": ["actual_summary_returned_complete"],
            },
            "operator_return_next_artifact_id": "returned_summary_json",
            "operator_return_next_artifact_path": (
                "runs/residual_force_trajectory_regeneration_current_summary.json"
            ),
            "operator_return_next_artifact_failed_check_ids": [
                "actual_summary_returned_complete",
            ],
            "operator_return_manifest_required_columns": [
                "queue_id",
                "expected_regenerated_trajectory_npz",
                "status",
                "operator_verified_npz_exists",
            ],
            "operator_return_validation_ladder_ready": True,
            "operator_return_handoff_binding_ready": True,
            "operator_return_handoff_queue_csv": "runs/residual_force_trajectory_regeneration_queue_current.csv",
            "operator_return_handoff_queue_csv_sha256": "a" * 64,
            "operator_return_handoff_full_regeneration_command": (
                "python3 tools/generate_ligand_trajectory_engine.py --prod-mode"
            ),
            "operator_return_handoff_return_manifest_schema_contract_ready": True,
            "operator_return_handoff_return_manifest_required_identity_rule": (
                "Every returned manifest row must include queue_id or queue_row_fingerprint."
            ),
            "operator_return_handoff_return_manifest_fingerprint_columns": [
                "queue_row_fingerprint",
                "source_queue_row_fingerprint",
            ],
            "operator_return_handoff_return_manifest_queue_id_columns": [
                "queue_id",
                "source_queue_id",
            ],
            "operator_return_handoff_return_manifest_npz_columns": [
                "expected_regenerated_trajectory_npz",
                "trajectory_npz",
            ],
            "operator_acceptance_matrix_ready": True,
            "operator_acceptance_stage_count": 5,
            "operator_acceptance_ready_stage_count": 1,
            "operator_acceptance_blocked_stage_count": 4,
            "operator_acceptance_stage_ids": [
                "gpu_return_templates_preflight",
                "returned_summary_acceptance",
                "returned_manifest_npz_acceptance",
                "force_derivation_acceptance",
                "post_return_promotion_chain",
            ],
            "operator_acceptance_ready_stage_ids": ["gpu_return_templates_preflight"],
            "operator_acceptance_blocked_stage_ids": [
                "returned_summary_acceptance",
                "returned_manifest_npz_acceptance",
                "force_derivation_acceptance",
                "post_return_promotion_chain",
            ],
            "operator_acceptance_next_stage_id": "returned_summary_acceptance",
            "operator_acceptance_next_stage_artifact": (
                "runs/residual_force_trajectory_regeneration_current_summary.json"
            ),
            "operator_acceptance_next_stage_validation_command": (
                "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
            ),
            "operator_acceptance_next_stage_release_effect": (
                "returned summary is complete and bound to the returned manifest"
            ),
            "operator_acceptance_next_stage_unlock_fields": [],
            "operator_acceptance_next_stage_required_checks": [
                "actual_summary_returned_complete",
                "actual_summary_manifest_bound",
                "actual_summary_out_manifest_csv_present",
                "actual_summary_out_manifest_csv_bound",
                "actual_summary_out_summary_json_bound",
                "actual_summary_manifest_row_counts_consistent",
            ],
            "operator_acceptance_next_stage_next_action": (
                "Return the completed GPU summary JSON with out_manifest_csv and out_summary_json bound."
            ),
            "operator_acceptance_stage_check_matrix": [
                {
                    "stage_id": "gpu_return_templates_preflight",
                    "status": "ready",
                    "failed_check_ids": [],
                    "failed_check_count": 0,
                    "failed_checks": [],
                    "unmatched_required_check_ids": [],
                    "unmatched_required_check_count": 0,
                },
                {
                    "stage_id": "returned_summary_acceptance",
                    "status": "blocked",
                    "failed_check_ids": ["actual_summary_returned_complete"],
                    "failed_check_count": 1,
                    "failed_checks": [
                        {
                            "check_id": "actual_summary_returned_complete",
                            "observed": "summary_present=False;summary_complete=False",
                        }
                    ],
                    "unmatched_required_check_ids": [],
                    "unmatched_required_check_count": 0,
                },
            ],
            "operator_acceptance_stage_check_matrix_count": 2,
            "operator_acceptance_current_blocked_stage_check_matrix": [
                {
                    "stage_id": "returned_summary_acceptance",
                    "status": "blocked",
                    "failed_check_ids": ["actual_summary_returned_complete"],
                    "failed_check_count": 1,
                    "failed_checks": [
                        {
                            "check_id": "actual_summary_returned_complete",
                            "observed": "summary_present=False;summary_complete=False",
                        }
                    ],
                    "unmatched_required_check_ids": [],
                    "unmatched_required_check_count": 0,
                },
            ],
            "operator_acceptance_current_blocked_stage_check_matrix_count": 1,
            "expected_queue_rows": 768,
            "manifest_template_csv": "runs/residual_force_gpu_worker_return_manifest_template_current.csv",
            "summary_template_csv": "runs/residual_force_gpu_worker_return_summary_template_current.csv",
            "summary_template_payload_json": (
                "runs/residual_force_trajectory_regeneration_current_summary_template.json"
            ),
            "summary_template_required_fields": [
                "queue_rows",
                "processed_rows",
                "ok_rows",
                "failed_rows",
                "aborted_early",
                "out_manifest_csv",
                "out_summary_json",
                "prod_mode",
                "require_rust_hip",
                "backend_counts",
            ],
            "summary_template_completion_rule": (
                "queue_rows equals expected_queue_rows; processed_rows>=expected_queue_rows; "
                "ok_rows>=expected_queue_rows"
            ),
            "summary_template_backend_provenance_contract_ready": True,
            "summary_template_required_backend_provenance_fields": [
                "prod_mode",
                "require_rust_hip",
                "backend_counts",
            ],
            "summary_template_backend_provenance_completion_rule": (
                "prod_mode=true; require_rust_hip=true; backend_counts has rust_hip* rows >= "
                "expected_queue_rows and no CPU/PyTorch fallback rows"
            ),
            "manifest_template_row_count": 768,
            "manifest_status_placeholder_count": 1,
            "manifest_status_invalid_count": 2,
            "manifest_ok_row_count": 0,
            "manifest_operator_verified": False,
            "manifest_operator_verified_true_count": 0,
            "manifest_operator_verification_column_present": False,
            "identity_coverage_ready": False,
            "queue_fingerprint_count": 768,
            "matched_queue_fingerprint_count": 0,
            "manifest_operator_verification_placeholder_count": 768,
            "manifest_npz_paths_complete": False,
            "manifest_npz_files_exist": False,
            "manifest_npz_files_valid": False,
            "manifest_npz_schema_valid": False,
            "manifest_npz_identity_valid": False,
            "manifest_npz_path_present_count": 0,
            "manifest_npz_path_missing_count": 0,
            "manifest_ok_row_missing_npz_path_count": 0,
            "manifest_operator_verified_missing_npz_path_count": 0,
            "manifest_npz_file_existing_count": 0,
            "manifest_npz_file_missing_count": 0,
            "manifest_ok_row_missing_npz_file_count": 0,
            "manifest_operator_verified_missing_npz_file_count": 0,
            "manifest_npz_file_valid_count": 0,
            "manifest_npz_file_invalid_count": 0,
            "manifest_ok_row_invalid_npz_file_count": 0,
            "manifest_operator_verified_invalid_npz_file_count": 0,
            "manifest_npz_schema_valid_count": 0,
            "manifest_npz_schema_invalid_count": 0,
            "manifest_ok_row_invalid_npz_schema_count": 0,
            "manifest_operator_verified_invalid_npz_schema_count": 0,
            "manifest_npz_identity_valid_count": 0,
            "manifest_npz_identity_invalid_count": 0,
            "manifest_ok_row_invalid_npz_identity_count": 0,
            "manifest_operator_verified_invalid_npz_identity_count": 0,
            "actual_summary_return_path": "runs/residual_force_trajectory_regeneration_current_summary.json",
            "actual_manifest_return_path": "runs/residual_force_trajectory_regeneration_current_manifest.csv",
            "summary_manifest_bound": False,
            "summary_manifest_csv": "",
            "summary_out_manifest_csv_present": False,
            "summary_out_manifest_csv": "",
            "summary_out_manifest_csv_bound": False,
            "summary_out_summary_json_bound": False,
            "summary_out_summary_json": "",
            "summary_manifest_row_counts_consistent": False,
            "post_return_validation_command": "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
            "next_required_step": (
                "Run the full GPU regeneration, return the summary JSON and completed identity-locked manifest CSV."
            ),
        },
        "blockers": [
            {
                "check_id": "actual_summary_returned_complete",
                "status": "fail",
                "source_artifact": "runs/residual_force_trajectory_regeneration_current_summary.json",
                "observed": "summary_present=False;summary_complete=False",
                "required": "actual returned summary satisfies the full-regeneration completion rule",
                "next_action": (
                    "Return runs/residual_force_trajectory_regeneration_current_summary.json after the full GPU run."
                ),
                "release_blocker": True,
                "execution_enabled": False,
                "external_state_mutated": False,
            },
            {
                "check_id": "actual_summary_manifest_bound",
                "status": "fail",
                "source_artifact": "runs/residual_force_trajectory_regeneration_current_summary.json",
                "observed": "summary_manifest_bound=False",
                "required": "actual returned summary points to the same manifest CSV being verified",
                "next_action": "Return a bound summary JSON.",
                "release_blocker": True,
                "execution_enabled": False,
                "external_state_mutated": False,
            },
        ],
        "operator_return_artifact_completion_matrix": [
            {
                "artifact_id": "returned_summary_json",
                "status": "blocked",
                "artifact_path": "runs/residual_force_trajectory_regeneration_current_summary.json",
                "failed_check_ids": ["actual_summary_returned_complete"],
                "failed_check_count": 1,
            },
            {
                "artifact_id": "returned_manifest_csv",
                "status": "blocked",
                "artifact_path": "runs/residual_force_trajectory_regeneration_current_manifest.csv",
                "failed_check_ids": ["actual_manifest_returned_complete"],
                "failed_check_count": 1,
            },
            {
                "artifact_id": "regenerated_npz_bundles",
                "status": "blocked",
                "artifact_path": "regenerated NPZ bundles referenced by the returned manifest",
                "failed_check_ids": ["actual_manifest_npz_paths_complete"],
                "failed_check_count": 1,
            },
            {
                "artifact_id": "post_run_force_derivation_validation",
                "status": "blocked",
                "artifact_path": "runs/residual_force_derivation_validation_current.json",
                "failed_check_ids": ["post_run_force_derivation_validation"],
                "failed_check_count": 1,
            },
        ],
        "operator_return_artifact_completion_blocker_matrix": [
            {
                "artifact_id": "returned_summary_json",
                "status": "blocked",
                "artifact_path": "runs/residual_force_trajectory_regeneration_current_summary.json",
                "failed_check_ids": ["actual_summary_returned_complete"],
                "failed_check_count": 1,
            },
        ],
        "operator_acceptance_matrix": [
            {
                "stage_id": "gpu_return_templates_preflight",
                "status": "ready",
                "artifact": "runs/residual_force_gpu_worker_handoff_package_current.json",
                "required_checks": [
                    "gpu_handoff_ready",
                    "manifest_template_ready",
                    "summary_template_ready",
                ],
                "validation_command": "python3 tools/generate_ligand_trajectory_engine.py --prod-mode",
                "release_effect": "operator can run the exact identity-locked GPU regeneration queue",
                "unlock_fields": [],
                "next_action": "",
                "release_blocker": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            },
            {
                "stage_id": "returned_summary_acceptance",
                "status": "blocked",
                "artifact": "runs/residual_force_trajectory_regeneration_current_summary.json",
                "required_checks": [
                    "actual_summary_returned_complete",
                    "actual_summary_manifest_bound",
                ],
                "validation_command": "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
                "release_effect": "returned summary is complete and bound to the returned manifest",
                "unlock_fields": [],
                "next_action": "Return the completed GPU summary JSON.",
                "release_blocker": True,
                "execution_enabled": False,
                "external_state_mutated": False,
            },
        ],
    }


def _promotion_workbench() -> dict:
    return {
        "summary": {
            "status": "blocked_product_production_ai_promotion_workbench",
            "promotion_workbench_ready": True,
            "production_ai_promotion_ready": False,
            "first_blocked_stage_id": "gpu_return_receipt",
            "first_blocked_stage_artifact": "runs/residual_force_gpu_worker_return_receipt_current.json",
            "first_blocked_stage_ready_key": "gpu_worker_return_receipt_ready",
            "post_return_promotion_ladder_blocked_stage_count": 10,
            "blocked_stage_ids": [
                "gpu_return_receipt",
                "force_derivation_validation",
                "production_training_data_contract",
            ],
        }
    }


def _scope_priority() -> dict:
    return {
        "summary": {
            "priority_packet_ready": True,
            "queue_item_count": 21,
            "open_item_count": 21,
            "local_crosscheck_candidate_count": 11,
            "external_primary_exact_evidence_required_count": 6,
            "all_operator_packet_bindings_ready": True,
            "operator_packet_binding_ready_count": 21,
            "operator_packet_binding_missing_count": 0,
            "top_required_evidence_type": "exact_transporter_target_pair_quantitative_binder_kcal",
            "top_review_template_artifact": "runs/transporter_manual_review_intake_template_current.json",
            "top_apply_gate_artifact": "runs/transporter_binder_promotion_gate_current.json",
            "next_required_step": "Triage local AQP1/GLUT1 crosscheck candidates first.",
        },
        "rows": [
            {
                "priority": 1,
                "item_id": "AQP1.core_binder_01",
                "domain": "transporter",
                "evidence_priority_bucket": "local_crosscheck_review_present_but_exact_quant_required",
                "required_evidence_type": "exact_transporter_target_pair_quantitative_binder_kcal",
                "review_template_artifact": "runs/transporter_manual_review_intake_template_current.json",
                "apply_gate_artifact": "runs/transporter_binder_promotion_gate_current.json",
                "next_step": "Review local crosscheck files and capture exact evidence if present.",
            }
        ],
    }


def _scope_intake() -> dict:
    return {
        "summary": {
            "intake_readiness_ready": True,
            "row_count": 21,
            "local_crosscheck_triage_item_count": 10,
            "local_crosscheck_intake_ready_count": 10,
            "external_exact_evidence_required_count": 6,
            "guardrail_item_count": 5,
            "all_operator_packet_bindings_ready": True,
            "operator_packet_binding_ready_count": 21,
            "operator_packet_binding_missing_count": 0,
            "transporter_triage_packet_ready": True,
            "transporter_operator_review_evidence_matrix_ready": True,
            "transporter_claim_safe_local_evidence_ready_count": 0,
            "transporter_claim_safe_local_evidence_blocked_count": 11,
            "transporter_direct_binding_claim_blocked_count": 4,
            "transporter_negative_value_claim_blocked_count": 6,
            "transporter_top_claim_safe_blocker": "functional_assay_quantitative_but_not_direct_binding_claim_safe",
            "transporter_top_operator_next_verdict": "keep_functional_surrogate_review_only_until_direct_binding_source",
            "transporter_candidate_assignment_required_count": 7,
            "transporter_functional_quantitative_only_direct_gap_open_count": 3,
            "transporter_review_only_direct_binding_gap_count": 1,
            "transporter_candidate_ready_for_manual_review_count": 11,
            "transporter_candidate_ready_for_apply_count": 0,
            "transporter_manual_review_intake_ready": True,
            "transporter_manual_review_template_row_count": 11,
            "transporter_manual_review_direct_binding_evidence_required_count": 4,
            "transporter_manual_review_negative_quantitative_value_required_count": 6,
            "transporter_manual_review_decision_placeholder_count": 11,
            "first_review_row_id": "transporter_review_AQP1_core_binder_01",
            "first_review_item_id": "AQP1.core_binder_01",
            "first_review_target_id": "AQP1",
            "first_review_candidate_ligand_id": "aqp1_bacopaside_ii_review_seed",
            "first_review_replacement_source": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
            "first_review_replacement_reference_binding_kcal_mol": "",
            "first_review_direct_binding_evidence_required": True,
            "first_review_direct_binding_source_url_or_doi": (
                "OPERATOR_FILL_EXACT_DIRECT_BINDING_SOURCE_OR_KEEP_BLOCKED"
            ),
            "first_review_negative_quantitative_value_required": False,
            "first_review_negative_reference_binding_kcal_mol": "",
            "first_review_review_decision": "OPERATOR_FILL_APPROVE_FOR_DRAFT_OR_KEEP_BLOCKED",
            "first_review_authoritative_apply_requested": "",
            "first_review_manual_review_blockers": "replacement_reference_binding_kcal_mol",
            "first_review_review_requirements": "exact_transporter_target_pair_quantitative_binder_kcal",
            "first_review_p0_slot_overlay_required_missing_fields": "replacement_reference_binding_kcal_mol",
            "first_review_p0_slot_overlay_claim_safe_step_ready": False,
            "first_review_p0_slot_overlay_authoritative_apply_allowed": False,
            "first_review_p0_slot_overlay_scope_promotion_allowed": False,
            "next_required_step": (
                "Use ready local crosscheck rows and the transporter manual-review template for evidence triage."
            ),
        }
    }


def _scope_contract() -> dict:
    return {
        "summary": {
            "status": "blocked_product_scope_breadth_contract",
            "scope_operator_transfer_manifest_ready": True,
            "scope_operator_transfer_outbound_artifact_count": 10,
            "scope_operator_transfer_outbound_artifacts": [
                "runs/product_scope_breadth_evidence_priority_packet_current.json",
                "runs/transporter_manual_review_intake_template_current.json",
                "runs/pxr_exact_evidence_review_intake_template_current.json",
            ],
            "scope_operator_transfer_inbound_artifact_count": 4,
            "scope_operator_transfer_inbound_artifacts": [
                "completed runs/transporter_manual_review_intake_template_current.csv with OPERATOR_FILL placeholders resolved",
                "completed runs/pxr_exact_evidence_review_intake_template_current.csv with exact human NR1I2/PXR values",
            ],
            "scope_operator_transfer_first_return_artifact": (
                "completed runs/transporter_manual_review_intake_template_current.csv with OPERATOR_FILL placeholders resolved"
            ),
            "scope_operator_transfer_acceptance_artifact": "runs/product_scope_breadth_contract_current.json",
            "scope_operator_transfer_acceptance_ready_key": "scope_breadth_ready",
            "scope_operator_transfer_next_acceptance_stage": "transporter_claim_acceptance",
            "scope_operator_transfer_post_return_validation_command": (
                "python3 tools/build_transporter_manual_review_intake_template.py"
            ),
            "scope_acceptance_matrix_ready": True,
            "scope_claim_expansion_contract_ready": True,
            "scope_claim_expansion_currently_satisfied": False,
            "scope_claim_expansion_current_blocked_stage_count": 4,
            "scope_claim_expansion_current_blocked_stage_ids": [
                "transporter_claim_acceptance",
                "pxr_claim_acceptance",
            ],
            "scope_claim_expansion_current_next_stage_id": "transporter_claim_acceptance",
            "scope_claim_expansion_current_next_stage_artifact": (
                "runs/transporter_blocker_capture_sheet_current.json;"
                "runs/transporter_binder_promotion_gate_current.json;"
                "runs/product_scope_breadth_evidence_intake_readiness_current.json"
            ),
            "scope_claim_expansion_current_next_stage_validation_command": (
                "python3 tools/build_transporter_manual_review_intake_template.py && "
                "python3 tools/build_transporter_binder_promotion_gate.py && "
                "python3 tools/build_transporter_p0_closure_packet.py && "
                "python3 tools/build_product_scope_breadth_contract.py"
            ),
            "scope_claim_expansion_current_next_stage_unlock_claim_scopes": [
                "transporter_domain_promotion"
            ],
            "scope_acceptance_stage_count": 5,
            "scope_acceptance_ready_stage_count": 1,
            "scope_acceptance_blocked_stage_count": 4,
            "scope_acceptance_stage_ids": [
                "scope_evidence_acquisition_preflight",
                "transporter_claim_acceptance",
                "pxr_claim_acceptance",
                "breadth_domain_floor_acceptance",
                "general_platform_claim_acceptance",
            ],
            "scope_acceptance_ready_stage_ids": ["scope_evidence_acquisition_preflight"],
            "scope_acceptance_blocked_stage_ids": [
                "transporter_claim_acceptance",
                "pxr_claim_acceptance",
                "breadth_domain_floor_acceptance",
                "general_platform_claim_acceptance",
            ],
            "scope_acceptance_next_stage_id": "transporter_claim_acceptance",
            "scope_acceptance_next_stage_artifact": (
                "runs/transporter_blocker_capture_sheet_current.json;"
                "runs/transporter_binder_promotion_gate_current.json;"
                "runs/product_scope_breadth_evidence_intake_readiness_current.json"
            ),
            "scope_acceptance_next_stage_validation_command": (
                "python3 tools/build_transporter_manual_review_intake_template.py && "
                "python3 tools/build_transporter_binder_promotion_gate.py && "
                "python3 tools/build_transporter_p0_closure_packet.py && "
                "python3 tools/build_product_scope_breadth_contract.py"
            ),
            "scope_acceptance_next_stage_release_effect": (
                "transporter domain can move from blocked claim to evidence-ready pending product decision"
            ),
            "scope_acceptance_next_stage_unlock_claim_scopes": ["transporter_domain_promotion"],
            "scope_acceptance_next_stage_required_checks": [
                "transporter_claim_safe_local_evidence_ready",
                "transporter_direct_binding_claim_blockers_zero",
            ],
            "scope_acceptance_next_stage_next_action": (
                "Reduce transporter P0 scaffold open count to zero; claim-safe binder promotion is now present."
            ),
            "scope_acceptance_stage_evidence_matrix_count": 5,
            "scope_acceptance_current_blocked_stage_evidence_matrix_count": 4,
            "domain_count": 6,
            "ready_domain_count": 3,
            "missing_domain_count": 3,
            "ready_domains": ["ca2", "idp_broad", "all_atom"],
            "missing_domains": ["transporter", "pxr", "general_protein_ligand"],
            "first_blocked_domain": "transporter",
            "first_blocked_domain_artifact": "runs/transporter_blocker_capture_sheet_current.json",
            "first_blocked_domain_observed": "supportive=6;placeholder=0;p0_open=1;authoritative_binders=1",
            "first_blocked_domain_requirement": (
                "supportive transporter evidence, zero pending capture, zero placeholder rows, donor policy reopen "
                "ready, P0 open count zero, and at least one claim-safe binder row"
            ),
            "first_blocked_domain_next_action": (
                "Reduce transporter P0 scaffold open count to zero; claim-safe binder promotion is now present."
            ),
            "transporter_p0_readiness_matrix_ready": True,
            "transporter_p0_readiness_matrix_artifact": (
                "runs/transporter_p0_closure_readiness_matrix_current.json"
            ),
            "transporter_p0_auto_close_ready_artifact_count": 0,
            "transporter_p0_manual_or_external_required_artifact_count": 6,
            "transporter_p0_unresolved_slot_count": 11,
            "transporter_p0_auto_close_ready_slot_count": 0,
            "transporter_p0_external_exact_evidence_required_slot_count": 11,
            "transporter_p0_first_manual_or_external_required_step_id": "aqp1_ligand_reference",
            "transporter_p0_first_manual_or_external_required_slot_step": "core_binder_01",
            "transporter_p0_first_manual_or_external_required_action": (
                "Acquire exact target-pair quantitative evidence for AQP1 core_binder_01."
            ),
            "transporter_p0_evidence_acquisition_packet_ready": True,
            "transporter_p0_evidence_acquisition_artifact": (
                "runs/transporter_p0_evidence_acquisition_packet_current.json"
            ),
            "transporter_p0_evidence_acquisition_exact_request_slot_count": 11,
            "transporter_p0_evidence_acquisition_unresolved_slot_count": 11,
            "transporter_p0_evidence_acquisition_first_target_id": "AQP1",
            "transporter_p0_evidence_acquisition_first_packet_step": "core_binder_01",
            "transporter_p0_evidence_acquisition_first_replacement_ligand_id": (
                "aqp1_bacopaside_ii_review_seed"
            ),
            "transporter_p0_evidence_acquisition_first_request_mode": (
                "exact_target_pair_quantitative_binder_kcal_required"
            ),
            "transporter_p0_evidence_acquisition_first_source_signal": (
                "https://pubmed.ncbi.nlm.nih.gov/27474162/"
            ),
            "transporter_p0_evidence_acquisition_first_required_missing_fields": (
                "replacement_reference_binding_kcal_mol"
            ),
            "transporter_p0_evidence_acquisition_first_next_required_action": (
                "Acquire exact target-pair quantitative evidence."
            ),
            "transporter_p0_evidence_acquisition_next_slot_completion_packet_ready": True,
            "transporter_p0_evidence_acquisition_next_slot_completion_packet": {
                "slot_id": "AQP1.core_binder_01",
                "target_id": "AQP1",
                "candidate_ligand_id": "aqp1_bacopaside_ii_review_seed",
                "return_bundle_required_artifacts": [
                    "runs/transporter_manual_review_intake_template_current.csv",
                    "config/ligand_binding_reference_blind_aqp1_v1.csv",
                    "config/ligand_eval_splits_blind_aqp1_v1.csv",
                    "config/ligand_meta_blind_aqp1_v1.csv",
                    "runs/transporter_binder_promotion_gate_current.json",
                ],
                "return_bundle_required_artifact_count": 5,
                "required_operator_intake_columns": [
                    "target_id",
                    "candidate_ligand_id",
                    "reference_binding_kcal_mol",
                    "source_url_or_doi",
                ],
                "required_exact_evidence_fields": [
                    "target_id",
                    "candidate_ligand_id",
                    "direct_binding_or_claim_safe_kcal_basis",
                    "reference_binding_kcal_mol",
                    "source_url_or_doi",
                    "target_match_decision",
                    "operator_review_decision",
                ],
                "required_claim_guardrails": [
                    "functional_surrogate_does_not_authorize_direct_binding_claim",
                    "reference_split_meta_rows_must_be_synchronized_before_promotion",
                ],
                "completion_rule": "Provide exact target-pair quantitative evidence before promotion.",
                "next_slot_source_modality_guard_ready": True,
                "next_slot_source_modality": "functional_quantitative_surrogate",
                "next_slot_source_modality_claim_safe": False,
                "next_slot_source_modality_direct_binding_claim_allowed": False,
                "next_slot_source_modality_decision": (
                    "keep_blocked_until_exact_direct_binding_or_claim_safe_kcal"
                ),
                "next_slot_source_modality_guardrails": [
                    "functional_quantitative_surrogate_is_review_only",
                    "direct_binding_claim_requires_exact_target_pair_source",
                ],
                "next_slot_source_modality_observed_signal": (
                    "request_mode=exact_target_pair_quantitative_binder_kcal_required"
                ),
                "next_slot_source_modality_required_upgrade": (
                    "exact target-pair direct/claim-safe binding kcal/mol"
                ),
            },
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_source_count": 6,
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_result": (
                "no_public_direct_experimental_or_claim_safe_binding_kcal_for_aqp1_bacopaside_ii;"
                "chembl_aqp1_bacopaside_ii_rows=0;bindingdb_p29972_affinities=0;"
                "functional_ic50_identity_mismatch=CHEMBL195380_not_CHEMBL390758"
            ),
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_database_recheck_row_count": 2,
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_ligand_identity_mismatch_row_count": 1,
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_pubchem_cid": "9876264",
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_id": "CHEMBL390758",
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_chembl_target_id": "CHEMBL4523210",
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_bindingdb_uniprot_affinity_row_count": 0,
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_aqp1_activity_row_count": 0,
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_functional_ic50_identity_mismatch_detail": (
                "AQP1 functional IC50 2700 nM row is CHEMBL195380, "
                "while bacopaside II is CHEMBL390758."
            ),
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifacts": [
                "runs/transporter_manual_review_intake_template_current.csv",
                "config/ligand_binding_reference_blind_aqp1_v1.csv",
                "config/ligand_eval_splits_blind_aqp1_v1.csv",
                "config/ligand_meta_blind_aqp1_v1.csv",
                "runs/transporter_binder_promotion_gate_current.json",
            ],
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count": 5,
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix": [
                {
                    "artifact_id": "operator_review_row",
                    "status": "blocked",
                    "artifact_path": "runs/transporter_manual_review_intake_template_current.csv",
                }
            ],
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix_count": 5,
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_blocker_count": 5,
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id": (
                "operator_review_row"
            ),
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_path": (
                "runs/transporter_manual_review_intake_template_current.csv"
            ),
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_failed_check_ids": [
                "next_slot_required_missing_fields",
                "operator_review_row_not_operator_verified",
            ],
            "transporter_p0_evidence_acquisition_next_slot_id": "AQP1.core_binder_01",
            "transporter_p0_evidence_acquisition_next_slot_operator_review_artifact": (
                "runs/transporter_manual_review_intake_template_current.csv"
            ),
            "evidence_queue_next_operator_completion_packet_ready": True,
            "evidence_queue_next_operator_completion_slot_id": "AQP1.core_binder_01",
            "evidence_queue_next_operator_completion_expected_evidence_type": (
                "direct_or_claim_safe_binding_kcal"
            ),
            "evidence_queue_next_operator_completion_required_exact_evidence_field_count": 19,
            "evidence_queue_next_operator_completion_required_exact_evidence_fields": (
                "target_id;target_uniprot_accession;target_species;candidate_ligand_id;"
                "reference_binding_kcal_mol;source_pmid_or_document_id;evidence_sentence_or_table_locator"
            ),
            "evidence_queue_next_operator_completion_required_operator_intake_columns": (
                "target_id;candidate_ligand_id;reference_binding_kcal_mol;source_url_or_doi;smiles;scaffold;evidence_type"
            ),
            "evidence_queue_next_operator_completion_required_claim_guardrails": (
                "functional_surrogate_does_not_authorize_direct_binding_claim;"
                "scope_promotion_allowed_false_until_all_transporter_p0_slots_green"
            ),
            "evidence_queue_next_operator_completion_operator_review_artifact": (
                "runs/transporter_manual_review_intake_template_current.csv"
            ),
            "evidence_queue_next_operator_completion_post_intake_synchronization_targets": (
                "config/ligand_binding_reference_blind_aqp1_v1.csv;"
                "config/ligand_eval_splits_blind_aqp1_v1.csv;"
                "config/ligand_meta_blind_aqp1_v1.csv"
            ),
            "evidence_queue_next_operator_completion_acceptance_gate_commands": (
                "python3 tools/build_transporter_binder_promotion_gate.py;"
                "python3 tools/build_product_scope_breadth_contract.py;"
                "python3 tools/build_product_goal_completion_audit.py"
            ),
            "evidence_queue_next_operator_completion_contract_artifact": (
                "runs/transporter_p0_evidence_acquisition_packet_current.json#next_slot_completion_packet"
            ),
            "evidence_queue_next_operator_completion_aqp1_review_sidecar_ready": True,
            "evidence_queue_next_operator_completion_aqp1_functional_surrogate_artifact": (
                "runs/aqp1_functional_kcal_surrogate_packet_current.json"
            ),
            "evidence_queue_next_operator_completion_aqp1_candidate_ledger_artifact": (
                "runs/aqp1_candidate_evidence_ledger_current.json"
            ),
            "evidence_queue_next_operator_completion_aqp1_review_candidate_name": "bacopaside II",
            "evidence_queue_next_operator_completion_aqp1_review_source_anchor": "PMID 27474162",
            "evidence_queue_next_operator_completion_aqp1_review_source_url": (
                "https://pubmed.ncbi.nlm.nih.gov/27474162/"
            ),
            "evidence_queue_next_operator_completion_aqp1_review_target_uniprot": "P29972",
            "evidence_queue_next_operator_completion_aqp1_review_functional_measure": "IC50;18;uM",
            "evidence_queue_next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol": "-6.47",
            "evidence_queue_next_operator_completion_aqp1_review_assay_type_honesty": (
                "functional_ic50_derived_surrogate_not_direct_binding"
            ),
            "evidence_queue_next_operator_completion_aqp1_review_direct_binding_claim_allowed": "no",
            "evidence_queue_next_operator_completion_aqp1_review_binding_kcal_claim_allowed": "no",
            "evidence_queue_next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank": "yes",
            "evidence_queue_next_operator_completion_aqp1_review_claim_safe_functional_kcal_ready": "yes",
            "evidence_queue_next_operator_completion_aqp1_review_ledger_review_bucket": "review_only_first_wave",
            "evidence_queue_next_operator_completion_aqp1_review_ledger_promotion_policy": (
                "draft_first_wave_manual_review"
            ),
            "evidence_queue_pxr_exact_review_sidecar_row_count": 6,
            "evidence_queue_next_pxr_exact_review_sidecar_ready": True,
            "evidence_queue_next_pxr_exact_review_row_id": "pxr_review_d603772038dff21e",
            "evidence_queue_next_pxr_exact_review_candidate_name": "acetaminophen",
            "evidence_queue_next_pxr_exact_review_required_evidence_mode": (
                "exact_human_nr1i2_pxr_conflict_resolution_or_negative_value_required"
            ),
            "evidence_queue_next_pxr_exact_review_target_match_confirmed": (
                "OPERATOR_FILL_TRUE_OR_FALSE"
            ),
            "evidence_queue_next_pxr_exact_review_replacement_reference_binding_kcal_mol": (
                "OPERATOR_FILL_EXACT_HUMAN_NR1I2_PXR_KCAL_OR_KEEP_BLOCKED"
            ),
            "evidence_queue_next_pxr_exact_review_replacement_source_url_or_doi": (
                "OPERATOR_FILL_EXACT_SOURCE_URL_OR_DOI_OR_KEEP_BLOCKED"
            ),
            "evidence_queue_next_pxr_exact_review_authoritative_apply_allowed": False,
            "evidence_queue_next_pxr_exact_review_scope_promotion_allowed": False,
            "pxr_source_modality_triage_ready": True,
            "pxr_source_modality_triage_status": "blocked_pxr_source_modality_triage",
            "pxr_source_modality_triage_artifact": "runs/pxr_source_modality_triage_current.json",
            "pxr_source_modality_triage_decision": (
                "keep_blocked_until_all_pxr_rows_have_exact_human_nr1i2_pxr_direct_or_claim_safe_quantitative_evidence"
            ),
            "pxr_source_modality_activity_proxy_or_conflict_surrogate_row_count": 3,
            "pxr_source_modality_direct_or_claim_safe_quantitative_ready_count": 0,
            "pxr_source_modality_accepted_for_scope_promotion_count": 0,
            "pxr_source_modality_direct_replacement_apply_draft_ready": True,
            "pxr_source_modality_direct_replacement_apply_draft_status": (
                "pxr_direct_binding_replacement_apply_draft_ready"
            ),
            "pxr_source_modality_direct_replacement_apply_draft_artifact": (
                "runs/pxr_direct_binding_replacement_apply_draft_current.json"
            ),
            "pxr_source_modality_direct_replacement_apply_draft_workbook_row_count": 14,
            "pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_before_draft": 6,
            "pxr_source_modality_direct_replacement_apply_draft_overlay_row_count": 6,
            "pxr_source_modality_direct_replacement_apply_draft_ready_for_apply_row_count_after_draft": 14,
            "pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_after_draft": 0,
            "pxr_source_modality_direct_replacement_apply_draft_first_overlay_ligand_id": (
                "e_guggulsterone"
            ),
            "pxr_source_modality_direct_replacement_apply_draft_authoritative_fields_touched": False,
            "pxr_source_modality_next_review_row_id": "pxr_review_d603772038dff21e",
            "pxr_source_modality_next_review_candidate_name": "acetaminophen",
            "pxr_source_modality_next_review_source_modality": (
                "activity_proxy_or_conflict_surrogate"
            ),
            "pxr_source_modality_next_review_rejection_reason": (
                "activity_proxy_conflict_requires_exact_human_nr1i2_pxr_resolution"
            ),
            "transporter_target_ready_for_promotion_ids": ["GLUT1"],
            "transporter_target_blocked_for_promotion_ids": ["AQP1"],
            "transporter_primary_blocker_target_id": "AQP1",
            "transporter_primary_blocker_packet_step": "core_binder_01",
            "transporter_primary_blocker_candidate_name": "bacopaside II",
        },
        "scope_acceptance_matrix": [
            {
                "stage_id": "scope_evidence_acquisition_preflight",
                "status": "ready",
                "release_blocker": False,
                "artifact": "runs/product_scope_breadth_evidence_acquisition_queue_current.json",
                "validation_command": "python3 tools/build_product_scope_breadth_evidence_acquisition_queue.py",
                "required_checks": ["evidence_queue_ready"],
                "unlock_claim_scopes": [],
                "next_action": "",
            },
            {
                "stage_id": "transporter_claim_acceptance",
                "status": "blocked",
                "release_blocker": True,
                "artifact": (
                    "runs/transporter_blocker_capture_sheet_current.json;"
                    "runs/transporter_binder_promotion_gate_current.json;"
                    "runs/product_scope_breadth_evidence_intake_readiness_current.json"
                ),
                "validation_command": (
                    "python3 tools/build_transporter_manual_review_intake_template.py && "
                    "python3 tools/build_transporter_binder_promotion_gate.py && "
                    "python3 tools/build_transporter_p0_closure_packet.py && "
                    "python3 tools/build_product_scope_breadth_contract.py"
                ),
                "required_checks": [
                    "transporter_claim_safe_local_evidence_ready",
                    "transporter_direct_binding_claim_blockers_zero",
                ],
                "unlock_claim_scopes": ["transporter_domain_promotion"],
                "next_action": (
                    "Reduce transporter P0 scaffold open count to zero; claim-safe binder promotion is now present."
                ),
            },
            {
                "stage_id": "pxr_claim_acceptance",
                "status": "blocked",
                "release_blocker": True,
                "artifact": "runs/pxr_exact_evidence_review_intake_template_current.json",
                "validation_command": "python3 tools/build_pxr_exact_evidence_review_intake_template.py",
                "required_checks": ["pxr_exact_review_rows_filled"],
                "unlock_claim_scopes": ["pxr_domain_promotion"],
                "next_action": "Resolve remaining PXR packet-fill blocked rows.",
            },
            {
                "stage_id": "breadth_domain_floor_acceptance",
                "status": "blocked",
                "release_blocker": True,
                "artifact": "runs/product_scope_breadth_contract_current.json",
                "validation_command": "python3 tools/build_product_scope_breadth_contract.py",
                "required_checks": ["transporter_ready", "pxr_ready"],
                "unlock_claim_scopes": ["domain_floor_ready_for_general_platform_review"],
                "next_action": "Finish transporter and PXR evidence gates.",
            },
            {
                "stage_id": "general_platform_claim_acceptance",
                "status": "blocked",
                "release_blocker": True,
                "artifact": "runs/product_capability_surface_contract_current.json",
                "validation_command": "python3 tools/build_product_capability_surface_contract.py",
                "required_checks": ["all_breadth_domains_ready"],
                "unlock_claim_scopes": ["general_protein_ligand_platform"],
                "next_action": "Keep general platform wording blocked.",
            },
        ],
        "scope_acceptance_stage_evidence_matrix": [
            {
                "stage_id": "scope_evidence_acquisition_preflight",
                "status": "ready",
                "evidence_row_count": 1,
                "blocked_evidence_row_count": 0,
                "first_blocked_evidence_row": {},
            },
            {
                "stage_id": "transporter_claim_acceptance",
                "status": "blocked",
                "evidence_row_count": 11,
                "blocked_evidence_row_count": 11,
                "first_blocked_evidence_row": {
                    "evidence_row_id": "AQP1.core_binder_01",
                    "target_id": "AQP1",
                    "packet_step": "core_binder_01",
                    "required_missing_fields": "replacement_reference_binding_kcal_mol",
                },
            },
            {
                "stage_id": "pxr_claim_acceptance",
                "status": "blocked",
                "evidence_row_count": 6,
                "blocked_evidence_row_count": 6,
                "first_blocked_evidence_row": {
                    "evidence_row_id": "pxr_review_1",
                    "target_gene": "NR1I2",
                },
            },
            {
                "stage_id": "breadth_domain_floor_acceptance",
                "status": "blocked",
                "evidence_row_count": 5,
                "blocked_evidence_row_count": 2,
                "first_blocked_evidence_row": {"evidence_row_id": "transporter"},
            },
            {
                "stage_id": "general_platform_claim_acceptance",
                "status": "blocked",
                "evidence_row_count": 6,
                "blocked_evidence_row_count": 3,
                "first_blocked_evidence_row": {"evidence_row_id": "transporter"},
            },
        ],
        "scope_acceptance_current_blocked_stage_evidence_matrix": [
            {
                "stage_id": "transporter_claim_acceptance",
                "status": "blocked",
                "evidence_row_count": 11,
                "blocked_evidence_row_count": 11,
                "first_blocked_evidence_row": {
                    "evidence_row_id": "AQP1.core_binder_01",
                    "target_id": "AQP1",
                    "packet_step": "core_binder_01",
                    "required_missing_fields": "replacement_reference_binding_kcal_mol",
                },
            },
            {
                "stage_id": "pxr_claim_acceptance",
                "status": "blocked",
                "evidence_row_count": 6,
                "blocked_evidence_row_count": 6,
                "first_blocked_evidence_row": {
                    "evidence_row_id": "pxr_review_1",
                    "target_gene": "NR1I2",
                },
            },
            {
                "stage_id": "breadth_domain_floor_acceptance",
                "status": "blocked",
                "evidence_row_count": 5,
                "blocked_evidence_row_count": 2,
                "first_blocked_evidence_row": {"evidence_row_id": "transporter"},
            },
            {
                "stage_id": "general_platform_claim_acceptance",
                "status": "blocked",
                "evidence_row_count": 6,
                "blocked_evidence_row_count": 3,
                "first_blocked_evidence_row": {"evidence_row_id": "transporter"},
            },
        ],
    }


def _pxr_exact_review() -> dict:
    return {
        "summary": {
            "pxr_exact_review_intake_ready": True,
            "review_template_row_count": 6,
            "expected_blocked_row_count": 6,
            "conflict_resolution_required_count": 3,
            "kcal_placeholder_count": 6,
            "source_placeholder_count": 6,
            "target_match_placeholder_count": 6,
            "review_decision_placeholder_count": 6,
            "next_review_completion_packet_ready": True,
            "next_review_completion_packet": {
                "review_row_id": "pxr_review_d603772038dff21e",
                "candidate_name": "acetaminophen",
                "required_operator_intake_columns": [
                    "review_row_id",
                    "replacement_reference_binding_kcal_mol",
                    "replacement_source_url_or_doi",
                    "conflict_resolution_decision",
                ],
                "required_exact_evidence_fields": [
                    "review_row_id",
                    "target_gene",
                    "target_species",
                    "candidate_name",
                    "replacement_reference_binding_kcal_mol",
                    "replacement_source_url_or_doi",
                    "assay_type_and_endpoint",
                    "assay_is_direct_or_claim_safe",
                    "target_match_confirmed",
                    "review_decision",
                    "authoritative_apply_requested",
                    "conflict_resolution_decision",
                ],
                "required_claim_guardrails": [
                    "human_NR1I2_PXR_target_match_required",
                    "activity_proxy_conflict_must_be_resolved_or_deferred",
                    "review_only_or_deferred_rows_do_not_authorize_pxr_promotion",
                    "authoritative_apply_requested_only_when_direct_or_claim_safe",
                    "scope_promotion_allowed_false_until_gate_green",
                ],
                "completion_rule": (
                    "Provide exact human NR1I2/PXR quantitative kcal/source evidence, confirm target match and "
                    "assay type, resolve any activity-proxy conflict or keep the row deferred."
                ),
                "return_bundle_required_artifacts": [
                    "runs/pxr_exact_evidence_review_intake_template_current.csv",
                    "runs/pxr_packet_fill_readiness_current.json",
                    "runs/pxr_blocked_row_promotion_gate_current.json",
                    "runs/pxr_authoritative_reconciliation_packet_current.json",
                    "runs/product_scope_breadth_contract_current.json",
                ],
                "return_bundle_required_artifact_count": 5,
            },
            "next_review_return_bundle_required_artifacts": [
                "runs/pxr_exact_evidence_review_intake_template_current.csv",
                "runs/pxr_packet_fill_readiness_current.json",
                "runs/pxr_blocked_row_promotion_gate_current.json",
                "runs/pxr_authoritative_reconciliation_packet_current.json",
                "runs/product_scope_breadth_contract_current.json",
            ],
            "next_review_return_bundle_required_artifact_count": 5,
            "next_review_return_bundle_completion_matrix": [
                {
                    "artifact_id": "operator_review_row",
                    "status": "blocked",
                    "artifact_path": "runs/pxr_exact_evidence_review_intake_template_current.csv",
                    "failed_check_ids": ["next_review_placeholder_fields"],
                }
            ],
            "next_review_return_bundle_completion_matrix_count": 1,
            "next_review_return_bundle_blocker_count": 1,
            "next_review_return_bundle_next_artifact_id": "operator_review_row",
            "next_review_return_bundle_next_artifact_path": (
                "runs/pxr_exact_evidence_review_intake_template_current.csv"
            ),
            "next_review_return_bundle_next_artifact_failed_check_ids": [
                "next_review_placeholder_fields"
            ],
            "next_review_row_id": "pxr_review_d603772038dff21e",
            "next_review_candidate_name": "acetaminophen",
            "next_review_operator_review_artifact": (
                "runs/pxr_exact_evidence_review_intake_template_current.csv"
            ),
            "next_required_step": "Complete exact human NR1I2/PXR kcal/source/assay/target-match review rows.",
        }
    }


def _commercial_handoff_bundle() -> dict:
    return {
        "summary": {
            "status": "product_commercial_readiness_handoff_bundle_ready",
            "handoff_bundle_ready": True,
            "artifact_count": 3,
            "ready_artifact_count": 3,
            "blocked_artifact_count": 0,
            "blocked_artifact_ids": [],
            "artifact_reference_contract_ready": True,
            "artifact_reference_count": 13,
            "local_missing_artifact_reference_count": 0,
            "operator_return_pending_artifact_reference_count": 3,
            "first_action_id": "production_ai_return_summary",
            "first_operator_input_artifact": (
                "runs/residual_force_trajectory_regeneration_current_summary_template.json"
            ),
            "next_required_step": (
                "Return the completed GPU summary JSON with template fields, manifest binding, and GPU/HIP backend provenance."
            ),
        }
    }


def test_product_goal_completion_audit_blocks_on_license_and_release() -> None:
    payload = mod.build_product_goal_completion_audit(
        architecture_packet=_architecture(),
        release_dossier_packet=_release_dossier(),
        public_benchmark_packet=_public_benchmark(),
        commercial_independence_packet=_commercial(),
        license_work_order_packet=_license_work_order(),
        cameo_architecture_packet=_cameo(),
        release_gate_packet=_release_gate(),
        bottleneck_packet=_bottleneck(),
        burndown_packet=_burndown(),
        product_ai_architecture_gap_packet=_ai_gap(),
        product_ai_execution_backlog_packet=_ai_backlog(),
    )

    summary = payload["summary"]
    by_id = {row["requirement_id"]: row for row in payload["rows"]}
    assert summary["status"] == "blocked_product_goal_completion_audit"
    assert summary["goal_complete"] is False
    assert summary["restricted_delivery_complete"] is False
    assert summary["release_blocker_fail_count"] == 3
    assert summary["pass_count"] == 4
    assert summary["fail_count"] == 3
    assert summary["primary_bottleneck_phase"] == "P1_product_commercial_independence"
    assert summary["approval_tokens_required"] == ["APPROVE_PRODUCT_LICENSE_FILE_CREATION"]
    assert summary["next_command_candidate_count"] == 1
    assert "--license-text-source /usr/share/common-licenses/Apache-2.0" in summary["next_command_candidates"][0]
    assert by_id["R3_commercial_independence"]["status"] == "fail"
    assert by_id["R3_commercial_independence"]["approval_token_required"] == "APPROVE_PRODUCT_LICENSE_FILE_CREATION"
    assert "fill_product_license_decision_operator_intake.py" in by_id["R3_commercial_independence"]["next_command"]
    assert by_id["R5_release_decision_artifacts"]["status"] == "fail"
    assert by_id["R7_restricted_local_delivery_ready"]["status"] == "fail"
    assert by_id["R6_product_ai_architecture_gap_closure"]["status"] == "pass"
    assert by_id["R6_product_ai_architecture_gap_closure"]["release_blocker"] is False
    assert summary["product_ai_architecture_gap_status"] == "product_ai_architecture_gap_closure_complete"
    assert summary["product_ai_architecture_all_gaps_closed"] is True
    assert summary["product_ai_architecture_gap_count"] == 7
    assert summary["product_ai_architecture_closed_gap_count"] == 7
    assert summary["product_ai_architecture_open_gap_count"] == 0
    assert summary["product_ai_architecture_open_gap_ids"] == []
    assert summary["product_ai_production_checkpoint_gap_ready"] is True
    assert summary["product_ai_closed_loop_decision_graph_ready"] is True
    assert summary["product_ai_durable_job_orchestration_ready"] is True
    assert summary["product_ai_trajectory_sla_ready"] is True
    assert summary["product_ai_trajectory_sla_claim_tier"] == "restricted_family_sla"
    assert summary["product_ai_trajectory_sla_restricted_family_allowed"] is True
    assert summary["product_ai_trajectory_sla_broad_platform_allowed"] is False
    assert summary["product_ai_trajectory_sla_current_rocm_baseline_claim_scope"] == "single_target_gpcr_baseline"
    assert summary["product_ai_trajectory_sla_current_rocm_baseline_production_profile_enabled"] is False
    assert summary["product_ai_trajectory_sla_rocm_baseline_profile_gap_acknowledged"] is True
    assert summary["product_ai_scope_breadth_ready"] is True
    assert summary["product_ai_report_ux_ready"] is True
    assert summary["product_ai_report_ux_customer_report_delivery_contract_ready"] is True
    assert summary["product_ai_report_ux_customer_report_evidence_binding_ready"] is True
    assert summary["product_ai_report_ux_customer_report_viewer_binding_ready"] is True
    assert summary["product_ai_report_ux_viewer_customer_report_binding_ready"] is True
    assert summary["product_ai_report_ux_customer_report_ready_block_count"] == 6
    assert summary["product_ai_report_ux_customer_report_required_block_count"] == 6
    assert summary["product_ai_report_ux_customer_report_blocked_block_count"] == 0
    assert summary["product_ai_security_deployment_ready"] is True
    assert summary["product_ai_security_hosted_deployment_contract_ready"] is True
    assert summary["product_ai_security_hosted_deployment_currently_satisfied"] is False
    assert summary["product_ai_security_hosted_deployment_next_stage_id"] == "operator_exposure_approval"
    assert summary["product_ai_security_hosted_external_exposure_allowed"] is False
    assert summary["product_ai_security_hosted_secret_injection_ready"] is False
    assert summary["product_ai_security_tls_termination_operator_verified"] is False
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False


def test_product_goal_completion_audit_rebuilds_closed_loop_and_durable_job_observed_from_live_packets() -> None:
    payload = mod.build_product_goal_completion_audit(
        architecture_packet=_architecture(release_ready=True, commercial_ready=True),
        release_dossier_packet=_release_dossier(release_ready=True, commercial_ready=True),
        public_benchmark_packet=_public_benchmark(),
        commercial_independence_packet=_commercial(ready=True),
        license_work_order_packet=_license_work_order(ready=True),
        cameo_architecture_packet=_cameo(),
        release_gate_packet=_release_gate(ready=True),
        bottleneck_packet={"summary": {"approval_tokens_required": []}},
        burndown_packet={"summary": {}, "rows": []},
        product_ai_architecture_gap_packet=_ai_gap(ready=True),
        product_ai_execution_backlog_packet=_ai_backlog(ready=True),
        decision_graph_packet={
            "summary": {
                "closed_loop_decision_graph_ready": True,
                "structure_quality_node_ready": True,
                "binding_site_node_ready": True,
                "pose_generation_node_ready": True,
                "scoring_node_ready": True,
                "uncertainty_abstention_node_ready": True,
                "report_node_ready": True,
                "customer_report_ux_node_ready": True,
                "viewer_interaction_surface_ready": True,
                "customer_report_card_ready": True,
                "interaction_rationale_ready": True,
                "counterfactual_rescue_suggestion_ready": True,
                "evidence_traceability_ready": True,
                "fail_closed_transition_ready": True,
                "ready_edge_count": 6,
                "required_edge_count": 6,
            }
        },
        service_boundary_packet={
            "summary": {
                "status": "product_service_boundary_contract_ready",
                "api_route_count": 24,
                "missing_api_route_count": 0,
            }
        },
        product_api_contract_packet={
            "summary": {
                "status": "product_api_contract_ready",
                "expected_route_count": 24,
                "missing_route_count": 0,
            }
        },
        job_orchestration_packet={
            "summary": {
                "status": "product_job_orchestration_contract_ready",
                "queue_lifecycle_progress_ready": True,
                "customer_run_history_lineage_ready": True,
                "worker_backend_contract_ready": True,
                "worker_lease_heartbeat_ready": True,
            }
        },
    )

    summary = payload["summary"]
    assert "closed_loop=True" in summary["product_ai_closed_loop_decision_graph_observed"]
    assert "structure_quality=True" in summary["product_ai_closed_loop_decision_graph_observed"]
    assert "ready_edges=6/6" in summary["product_ai_closed_loop_decision_graph_observed"]
    assert "queue_lifecycle_progress_ready=True" in summary["product_ai_durable_job_orchestration_observed"]
    assert "worker_backend_contract_ready=True" in summary["product_ai_durable_job_orchestration_observed"]
    assert "service_status=product_service_boundary_contract_ready" in summary[
        "product_ai_durable_job_orchestration_observed"
    ]


def test_product_goal_completion_audit_blocks_on_open_ai_architecture_backlog() -> None:
    payload = mod.build_product_goal_completion_audit(
        architecture_packet=_architecture(release_ready=True, commercial_ready=True),
        release_dossier_packet=_release_dossier(release_ready=True, commercial_ready=True),
        public_benchmark_packet=_public_benchmark(),
        commercial_independence_packet=_commercial(ready=True),
        license_work_order_packet=_license_work_order(ready=True),
        cameo_architecture_packet=_cameo(),
        release_gate_packet=_release_gate(ready=True),
        bottleneck_packet={"summary": {"approval_tokens_required": []}},
        burndown_packet={"summary": {}, "rows": []},
        product_ai_architecture_gap_packet=_ai_gap(ready=False),
        product_ai_execution_backlog_packet=_ai_backlog(ready=False),
    )

    summary = payload["summary"]
    by_id = {row["requirement_id"]: row for row in payload["rows"]}
    assert summary["status"] == "product_goal_completion_audit_pass"
    assert summary["goal_complete"] is True
    assert summary["restricted_delivery_complete"] is True
    assert summary["product_ai_optional_lane_ready"] is False
    assert summary["optional_requirement_fail_count"] == 1
    assert summary["product_ai_architecture_ready"] is False
    assert summary["product_ai_architecture_gap_status"] == "blocked_product_ai_architecture_gap_closure"
    assert summary["product_ai_architecture_all_gaps_closed"] is False
    assert summary["product_ai_architecture_gap_count"] == 7
    assert summary["product_ai_architecture_closed_gap_count"] == 5
    assert summary["product_ai_architecture_open_gap_count"] == 2
    assert summary["product_ai_architecture_open_gap_ids"] == [
        "production_ai_inference_checkpoint",
        "scope_breadth_expansion",
    ]
    assert summary["product_ai_architecture_gap_blocker_matrix_ready"] is True
    assert summary["product_ai_architecture_gap_blocker_matrix_count"] == 2
    assert summary["product_ai_architecture_current_primary_blocker_id"] == (
        "production_gpu_execution_environment_ready"
    )
    assert summary["product_ai_architecture_current_primary_blocker_artifact"] == (
        "runs/rocm_environment_manifest_current.json"
    )
    assert summary["product_ai_architecture_current_primary_blocker_validation_command"] == (
        "python3 tools/build_rocm_environment_manifest.py"
    )
    assert summary["product_ai_architecture_current_primary_blocker_next_action"] == (
        "Expose a visible ROCm/HIP AMD GPU device to PyTorch before production regeneration."
    )
    assert "visible_device_count" in summary[
        "product_ai_architecture_current_primary_blocker_operator_input_fields"
    ]
    assert summary["product_ai_architecture_current_primary_blocker_unlock_claim"] == (
        "production_ai_inference_subject"
    )
    assert summary[
        "product_ai_architecture_current_primary_blocker_next_after_stage_id"
    ] == "gpu_return_acceptance"
    assert summary[
        "product_ai_architecture_current_primary_blocker_next_after_artifact"
    ] == "runs/residual_force_gpu_worker_return_receipt_current.json"
    assert summary[
        "product_ai_architecture_current_primary_blocker_next_after_validation_command"
    ] == "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
    assert "Return full regeneration summary/manifest" in summary[
        "product_ai_architecture_current_primary_blocker_next_after_next_action"
    ]
    assert summary[
        "product_ai_architecture_current_primary_blocker_next_after_required_checks"
    ] == ["gpu_worker_return_receipt_ready"]
    assert "identity_coverage_ready" in summary[
        "product_ai_architecture_current_primary_blocker_next_after_unlock_fields"
    ]
    assert summary["product_ai_architecture_parallelizable_gap_blocker_count"] == 1
    assert summary["product_ai_architecture_first_parallelizable_blocker_id"] == (
        "AQP1.core_binder_01"
    )
    assert summary["product_ai_architecture_first_parallelizable_blocker_artifact"] == (
        "runs/transporter_manual_review_intake_template_current.csv"
    )
    assert summary["product_ai_architecture_first_parallelizable_blocker_operator_input_fields"] == [
        "target_id",
        "candidate_ligand_id",
        "reference_binding_kcal_mol",
    ]
    assert "direct_binding_or_claim_safe_kcal_basis" in summary[
        "product_ai_architecture_first_parallelizable_blocker_required_exact_evidence_fields"
    ]
    assert "functional_surrogate_does_not_authorize_direct_binding_claim" in summary[
        "product_ai_architecture_first_parallelizable_blocker_required_claim_guardrails"
    ]
    assert "exact target-pair quantitative evidence" in summary[
        "product_ai_architecture_first_parallelizable_blocker_claim_safe_completion_rule"
    ]
    assert summary["product_ai_architecture_first_parallelizable_blocker_unlock_claim"] == (
        "transporter_domain_promotion"
    )
    assert summary[
        "product_ai_architecture_first_parallelizable_blocker_source_modality_triage_artifact"
    ] == "runs/aqp1_binding_source_modality_triage_current.json"
    assert summary[
        "product_ai_architecture_first_parallelizable_blocker_source_modality_triage_decision"
    ] == "keep_blocked_until_direct_experimental_or_operator_verified_claim_safe_binding_kcal"
    assert summary[
        "product_ai_architecture_first_parallelizable_blocker_source_modality_direct_experimental_binding_row_count"
    ] == 0
    assert summary[
        "product_ai_architecture_first_parallelizable_blocker_source_modality_claim_safe_binding_kcal_ready_count"
    ] == 0
    assert summary[
        "product_ai_architecture_first_parallelizable_blocker_source_modality_computational_binding_energy_row_count"
    ] == 1
    assert summary[
        "product_ai_architecture_first_parallelizable_blocker_source_modality_best_computational_binding_energy_kcal_mol"
    ] == "-34.48"
    assert summary["commercial_readiness_next_action_matrix_ready"] is True
    assert summary["commercial_readiness_next_action_matrix_count"] == 4
    assert summary["commercial_readiness_next_action_blocker_count"] == 4
    assert summary["commercial_readiness_first_next_action_id"] == "production_ai_return_summary"
    assert summary["product_ai_production_checkpoint_gap_ready"] is False
    assert "trained_model_checkpoint_count=0" in summary["product_ai_production_checkpoint_gap_observed"]
    assert summary["product_ai_closed_loop_decision_graph_ready"] is True
    assert summary["product_ai_durable_job_orchestration_ready"] is True
    assert "queue_lifecycle_progress_ready=True" in summary["product_ai_durable_job_orchestration_observed"]
    assert summary["product_ai_trajectory_sla_ready"] is True
    assert summary["product_ai_trajectory_sla_claim_tier"] == "restricted_family_sla"
    assert summary["product_ai_trajectory_sla_restricted_family_allowed"] is True
    assert summary["product_ai_trajectory_sla_broad_platform_allowed"] is False
    assert summary["product_ai_trajectory_sla_current_rocm_baseline_claim_scope"] == "single_target_gpcr_baseline"
    assert summary["product_ai_trajectory_sla_current_rocm_baseline_production_profile_enabled"] is False
    assert summary["product_ai_trajectory_sla_rocm_baseline_profile_gap_acknowledged"] is True
    assert summary["product_ai_scope_breadth_ready"] is False
    assert "transporter_domain_promotion" in summary["product_ai_scope_breadth_observed"]
    assert summary["product_ai_report_ux_ready"] is True
    assert summary["product_ai_report_ux_customer_report_delivery_contract_ready"] is True
    assert summary["product_ai_report_ux_customer_report_viewer_binding_ready"] is True
    assert summary["product_ai_report_ux_customer_report_ready_block_count"] == 6
    assert summary["product_ai_security_deployment_ready"] is True
    assert summary["product_ai_security_hosted_deployment_contract_ready"] is True
    assert summary["product_ai_security_hosted_deployment_currently_satisfied"] is False
    assert summary["pass_count"] == 6
    assert summary["fail_count"] == 1
    assert by_id["R6_product_ai_architecture_gap_closure"]["status"] == "fail"
    assert "current_primary_open_gap=production_ai_inference_checkpoint" in by_id[
        "R6_product_ai_architecture_gap_closure"
    ]["observed"]
    assert "scope_breadth.transporter.AQP1.core_binder_01" in by_id["R6_product_ai_architecture_gap_closure"]["observed"]
    assert "primary_backlog_observed=" in by_id["R6_product_ai_architecture_gap_closure"]["observed"]
    assert "gpu_worker_return_receipt_ready=" in by_id["R6_product_ai_architecture_gap_closure"]["observed"]
    assert summary["product_ai_observed_rebuilt_from_live_artifacts"] is True
    assert "scope_closure_pxr_reconciled_blocked_row_count=6" in by_id["R6_product_ai_architecture_gap_closure"]["observed"]
    assert "scope_closure_manual_review_subcheck_count=54" in by_id["R6_product_ai_architecture_gap_closure"]["observed"]
    assert "scope_closure_authoritative_apply_allowed=False" in summary["product_ai_scope_backlog_detail"]
    assert summary["product_scope_closure_blocker_class_counts"] == {
        "direct_binding_evidence_missing": 4,
        "exact_negative_quantitative_value_missing": 6,
    }
    assert summary["product_scope_first_scientific_blocker"] == "AQP1.core_binder_01"
    assert summary["product_scope_manual_review_subcheck_count"] == 54
    assert summary["product_scope_transporter_manual_review_subcheck_count"] == 54
    assert summary["product_scope_transporter_identity_scaffold_confirmation_required_count"] == 11
    assert summary["product_scope_transporter_direct_binding_or_kcal_confirmation_required_count"] == 4
    assert summary["product_scope_transporter_negative_quantitative_confirmation_required_count"] == 6
    assert summary["product_scope_transporter_direct_binding_missing_count"] == 0
    assert summary["product_scope_pxr_reconciled_blocked_row_count"] == 6
    assert summary["product_scope_general_claim_blocker_count"] == 4
    assert summary["product_scope_authoritative_apply_allowed"] is False
    assert summary["next_command_candidate_count"] == 1
    assert summary["next_command_candidates"] == ["python3 tools/verify_primary.py"]


def test_product_goal_completion_audit_uses_force_return_chain_for_production_ai_bottleneck() -> None:
    payload = mod.build_product_goal_completion_audit(
        architecture_packet=_architecture(release_ready=True, commercial_ready=True),
        release_dossier_packet=_release_dossier(release_ready=True, commercial_ready=True),
        public_benchmark_packet=_public_benchmark(),
        commercial_independence_packet=_commercial(ready=True),
        license_work_order_packet=_license_work_order(ready=True),
        cameo_architecture_packet=_cameo(),
        release_gate_packet=_release_gate(),
        bottleneck_packet=_production_ai_bottleneck(),
        burndown_packet=_production_ai_burndown(),
        product_ai_architecture_gap_packet=_ai_gap(ready=False),
        product_ai_execution_backlog_packet=_ai_backlog(
            ready=False,
            observed=(
                "missing_production_output_labels=delta_force,uncertainty;"
                "gpu_worker_return_receipt_ready=False;"
                "gpu_worker_return_receipt_blockers=full_regeneration_summary_complete,post_run_force_derivation_validation;"
                "gpu_worker_return_expected_queue_rows=768;"
                "gpu_worker_return_manifest_ok_row_count=0;"
                "gpu_worker_return_manifest_status_placeholder_count=1;"
                "gpu_worker_return_manifest_status_invalid_count=2;"
                "gpu_worker_return_manifest_operator_verified=False;"
                "gpu_worker_return_operator_verified_true_count=0;"
                "gpu_worker_return_operator_verification_column_present=False;"
                "gpu_worker_return_identity_coverage_ready=False;"
                "gpu_worker_return_matched_queue_fingerprints=0;"
                "force_derivation_input_ready=False;"
                "delta_force_derivation_validation_ready=False;"
                "gpu_worker_return_queue_fingerprints=768"
            ),
        ),
        residual_model_registry_packet=_residual_model_registry(),
        production_ai_checkpoint_readiness_packet=_checkpoint_readiness(),
        production_ai_gpu_return_intake_packet=_gpu_return_intake(),
        production_ai_promotion_workbench_packet=_promotion_workbench(),
        product_scope_breadth_contract_packet=_scope_contract(),
        scope_evidence_priority_packet=_scope_priority(),
        scope_evidence_intake_readiness_packet=_scope_intake(),
        pxr_exact_review_intake_packet=_pxr_exact_review(),
        commercial_readiness_handoff_bundle_packet=_commercial_handoff_bundle(),
        delta_force_closure_acceptance_packet={
            "summary": {
                "packet_ready": True,
                "delta_force_closure_ready": False,
                "first_blocked_output_field": "delta_force",
                "closure_failed_stage_count": 9,
                "closure_failed_stage_ids": ["gpu_worker_return_receipt"],
                "next_stage_id": "gpu_worker_return_receipt",
                "next_stage_artifact": "runs/product_production_ai_gpu_return_intake_current.json",
                "next_stage_validation_command": "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
                "next_required_step": "Return GPU summary.",
            }
        },
        scope_closure_acceptance_packet={
            "summary": {
                "packet_ready": True,
                "scope_closure_ready": False,
                "scope_acceptance_stage_count": 5,
                "scope_acceptance_blocked_stage_count": 4,
                "scope_acceptance_blocked_stage_ids": ["transporter_claim_acceptance"],
                "scope_acceptance_next_stage_id": "transporter_claim_acceptance",
                "first_blocked_evidence_row_id": "AQP1.core_binder_01",
                "first_blocked_target_id": "AQP1",
                "first_blocked_required_missing_fields": "replacement_reference_binding_kcal_mol",
                "transporter_unresolved_slot_count": 11,
                "pxr_direct_or_claim_safe_quantitative_ready_count": 0,
                "general_platform_claim_allowed": False,
                "next_required_step": "Acquire exact transporter evidence.",
            }
        },
    )

    summary = payload["summary"]
    by_id = {row["requirement_id"]: row for row in payload["rows"]}
    assert summary["primary_bottleneck_kind"] == "production_ai_checkpoint_evidence_required"
    assert "gpu_worker_return_expected_queue_rows=768" in summary["product_ai_primary_backlog_detail"]
    assert "gpu_worker_return_manifest_operator_verified=False" in summary["product_ai_primary_backlog_detail"]
    assert summary["product_ai_primary_backlog_work_item_id"] == "scope_breadth.transporter.AQP1.core_binder_01"
    assert summary["product_ai_primary_backlog_acceptance_criteria"] == "primary acceptance gate"
    assert summary["product_ai_primary_backlog_next_action"] == "close primary backlog row"
    assert summary["product_ai_primary_backlog_source_artifact"] == "runs/source_artifact.json"
    assert summary["product_ai_primary_backlog_verification_command"] == "python3 tools/verify_primary.py"
    assert summary["production_ai_inference_subject_active"] is False
    assert summary["production_ai_default_residual_mode"] == "shadow"
    assert summary["production_ai_promotion_allowed"] is False
    assert summary["production_ai_customer_facing_auto_correction_allowed"] is False
    assert summary["production_ai_customer_facing_score_mutation_allowed"] is False
    assert summary["production_ai_customer_facing_ranking_mutation_allowed"] is False
    assert summary["production_ai_trained_checkpoint_count"] == 0
    assert summary["production_ai_selected_sidecar_ready"] is False
    assert summary["production_ai_selected_sidecar_missing_output_fields"] == ["delta_force"]
    assert summary["production_ai_blocked_reason"] == "production checkpoint preflight is blocked"
    assert summary["production_ai_residual_model_registry_status"] == "residual_model_registry_ready"
    assert summary["production_ai_residual_model_registry_ready"] is True
    assert summary["production_ai_product_model_layer_ready"] is True
    assert summary["production_ai_registry_checkpoint_preflight_ready"] is False
    assert summary["production_ai_registry_production_checkpoint_blocked"] is True
    assert summary["production_ai_registry_checkpoint_primary_blocker"] == "missing_output_fields:delta_force"
    assert summary["production_ai_registry_checkpoint_missing_output_fields"] == ["delta_force"]
    assert summary["production_ai_registry_checkpoint_missing_adapter_output_policy_fields"] == ["delta_force"]
    assert summary["production_ai_gpu_worker_return_receipt_ready"] is False
    assert summary["production_ai_gpu_worker_return_receipt_blockers"] == [
        "full_regeneration_summary_complete",
        "post_run_force_derivation_validation",
    ]
    assert summary["production_ai_checkpoint_acceptance_matrix_ready"] is True
    assert summary["production_ai_checkpoint_acceptance_stage_count"] == 7
    assert summary["production_ai_checkpoint_acceptance_ready_stage_count"] == 0
    assert summary["production_ai_checkpoint_acceptance_blocked_stage_count"] == 7
    assert summary["production_ai_checkpoint_acceptance_blocked_stage_ids"][0] == "gpu_return_acceptance"
    assert len(summary["production_ai_checkpoint_acceptance_matrix"]) == 7
    assert len(summary["production_ai_checkpoint_acceptance_current_blocked_stage_matrix"]) == 7
    assert summary["production_ai_checkpoint_acceptance_release_blocker_stage_count"] == 7
    assert summary["production_ai_checkpoint_acceptance_release_blocker_stage_ids"] == [
        "gpu_return_acceptance",
        "force_derivation_acceptance",
        "production_training_data_acceptance",
        "production_score_model_acceptance",
        "checkpoint_sidecar_acceptance",
        "checkpoint_preflight_acceptance",
        "registry_guarded_promotion_acceptance",
    ]
    assert summary["production_ai_checkpoint_acceptance_matrix"][0]["stage_id"] == "gpu_return_acceptance"
    assert "delta_force" in summary["production_ai_checkpoint_acceptance_matrix"][0]["unlock_fields"]
    assert summary["production_ai_checkpoint_acceptance_next_stage_id"] == "gpu_return_acceptance"
    assert summary["production_ai_checkpoint_acceptance_next_stage_artifact"] == (
        "runs/residual_force_gpu_worker_return_receipt_current.json"
    )
    assert summary["production_ai_checkpoint_acceptance_next_stage_validation_command"] == (
        "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
    )
    assert "delta_force" in summary["production_ai_checkpoint_acceptance_next_stage_unlock_fields"]
    assert summary["production_ai_checkpoint_acceptance_next_stage_required_checks"] == [
        "force_gpu_worker_return_receipt_ready"
    ]
    assert summary["production_ai_force_gpu_operator_transfer_manifest_ready"] is True
    assert summary["production_ai_force_gpu_operator_transfer_outbound_artifact_count"] == 9
    assert "tools/generate_ligand_trajectory_engine.py" in summary[
        "production_ai_force_gpu_operator_transfer_outbound_artifacts"
    ]
    assert summary["production_ai_force_gpu_operator_transfer_inbound_artifact_count"] == 4
    assert summary["production_ai_force_gpu_operator_transfer_first_return_artifact"] == (
        "runs/residual_force_trajectory_regeneration_current_summary.json"
    )
    assert summary["production_ai_force_gpu_operator_transfer_acceptance_artifact"] == (
        "runs/residual_force_gpu_worker_return_receipt_current.json"
    )
    assert summary["production_ai_force_gpu_operator_transfer_acceptance_ready_key"] == (
        "gpu_worker_return_receipt_ready"
    )
    assert summary["production_ai_gpu_expected_queue_rows"] == 768
    assert summary["production_ai_gpu_manifest_ok_row_count"] == 0
    assert summary["production_ai_gpu_manifest_npz_paths_complete"] is False
    assert summary["production_ai_gpu_manifest_npz_files_exist"] is False
    assert summary["production_ai_gpu_manifest_npz_path_present_count"] == 0
    assert summary["production_ai_gpu_manifest_npz_path_missing_count"] == 0
    assert summary["production_ai_gpu_manifest_ok_row_missing_npz_path_count"] == 0
    assert summary["production_ai_gpu_manifest_operator_verified_missing_npz_path_count"] == 0
    assert summary["production_ai_gpu_manifest_npz_file_existing_count"] == 0
    assert summary["production_ai_gpu_manifest_npz_file_missing_count"] == 0
    assert summary["production_ai_gpu_manifest_ok_row_missing_npz_file_count"] == 0
    assert summary["production_ai_gpu_manifest_operator_verified_missing_npz_file_count"] == 0
    assert summary["production_ai_gpu_manifest_status_placeholder_count"] == 1
    assert summary["production_ai_gpu_manifest_status_invalid_count"] == 2
    assert summary["production_ai_gpu_manifest_operator_verified"] is False
    assert summary["production_ai_gpu_operator_verified_true_count"] == 0
    assert summary["production_ai_gpu_operator_verification_column_present"] is False
    assert summary["production_ai_gpu_identity_coverage_ready"] is False
    assert summary["production_ai_gpu_matched_queue_fingerprints"] == 0
    assert summary["production_ai_gpu_queue_fingerprints"] == 768
    assert summary["production_ai_force_derivation_input_ready"] is False
    assert summary["production_ai_delta_force_derivation_validation_ready"] is False
    assert summary["production_ai_missing_output_labels"] == ["delta_force", "uncertainty"]
    assert summary["production_ai_checkpoint_readiness_status"] == "blocked_product_production_ai_checkpoint_readiness"
    assert summary["production_ai_checkpoint_ready"] is False
    assert summary["production_ai_checkpoint_failed_check_ids"] == [
        "production_training_data_ready",
        "force_gpu_worker_return_receipt_ready",
    ]
    assert summary["production_ai_checkpoint_first_failed_check_id"] == "production_training_data_ready"
    assert summary["production_ai_checkpoint_first_failed_source_artifact"] == (
        "runs/residual_production_training_data_contract_current.json"
    )
    assert "training-data contract" in summary["production_ai_checkpoint_first_failed_required"]
    assert "Close production training-data" in summary["production_ai_checkpoint_first_failed_next_action"]
    assert summary["production_ai_checkpoint_actionable_blocker_stage_id"] == "gpu_return_acceptance"
    assert summary["production_ai_checkpoint_actionable_blocker_check_id"] == (
        "force_gpu_worker_return_receipt_ready"
    )
    assert summary["production_ai_checkpoint_actionable_blocker_artifact"] == (
        "runs/residual_force_gpu_worker_return_receipt_current.json"
    )
    assert "expected_queue_rows=768" in summary["production_ai_checkpoint_actionable_blocker_observed"]
    assert "GPU return receipt covers queue" in summary[
        "production_ai_checkpoint_actionable_blocker_required"
    ]
    assert "Return full regeneration summary/manifest" in summary[
        "production_ai_checkpoint_actionable_blocker_next_action"
    ]
    assert summary["production_ai_checkpoint_actionable_blocker_validation_command"] == (
        "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
    )
    assert "delta_force" in summary["production_ai_checkpoint_actionable_blocker_unlock_fields"]
    assert summary["production_ai_checkpoint_actionable_blocker_downstream_blocked_stage_count"] == 6
    assert summary["production_ai_checkpoint_next_after_actionable_blocker_stage_id"] == (
        "force_derivation_acceptance"
    )
    assert summary["production_ai_checkpoint_next_after_actionable_blocker_artifact"] == (
        "runs/residual_force_derivation_validation_current.json"
    )
    assert "delta_force_derivation_validation_ready" in summary[
        "production_ai_checkpoint_next_after_actionable_blocker_required_checks"
    ]
    assert summary["production_ai_checkpoint_next_after_actionable_blocker_unlock_fields"] == [
        "delta_force"
    ]
    assert summary["production_ai_checkpoint_actionable_blocker_blocks_registry_promotion"] is True
    assert summary["production_ai_checkpoint_actionable_operator_completion_packet_ready"] is True
    assert summary["production_ai_checkpoint_actionable_operator_completion_artifact_id"] == (
        "gpu_worker_return_receipt_json"
    )
    assert summary["production_ai_checkpoint_actionable_operator_completion_artifact_path"] == (
        "runs/residual_force_gpu_worker_return_receipt_current.json"
    )
    assert summary["production_ai_checkpoint_actionable_operator_completion_expected_queue_rows"] == 768
    assert "operator_verified" in summary[
        "production_ai_checkpoint_actionable_operator_completion_required_fields_or_columns"
    ]
    assert summary[
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_command_count"
    ] == 2
    assert "python3 tools/build_rocm_environment_manifest.py" in summary[
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_commands"
    ]
    assert summary[
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_required_fields"
    ] == ["operator_verified", "backend_counts"]
    assert "production ROCm/HIP" in summary[
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_completion_rule"
    ]
    assert summary[
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_return_artifacts"
    ] == ["runs/residual_force_gpu_worker_return_receipt_current.json"]
    assert summary[
        "production_ai_checkpoint_actionable_operator_completion_torch_visibility_probe_command"
    ].startswith("python3 -c")
    assert summary["production_ai_checkpoint_actionable_operator_completion_failed_check_ids"] == [
        "gpu_worker_return_receipt_ready"
    ]
    assert summary["production_ai_checkpoint_actionable_operator_completion_template_payload_json"] == (
        "runs/residual_force_gpu_worker_return_summary_template_current.json"
    )
    assert summary["production_ai_checkpoint_actionable_operator_completion_validation_command"] == (
        "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
    )
    assert "--prod-mode" in summary[
        "production_ai_checkpoint_actionable_operator_completion_full_regeneration_command"
    ]
    assert "expected_queue_rows=768" in summary[
        "production_ai_checkpoint_actionable_operator_completion_completion_rule"
    ]
    assert "production ROCm/HIP" in summary[
        "production_ai_checkpoint_actionable_operator_completion_backend_provenance_completion_rule"
    ]
    assert summary["production_ai_checkpoint_actionable_operator_completion_packet"]["artifact_id"] == (
        "gpu_worker_return_receipt_json"
    )
    assert summary["production_ai_gpu_return_intake_status"] == "blocked_product_production_ai_gpu_return_intake"
    assert summary["production_ai_gpu_return_intake_artifact_path"] == (
        "runs/product_production_ai_gpu_return_intake_current.json"
    )
    assert summary["production_ai_gpu_return_intake_ready"] is True
    assert summary["production_ai_gpu_return_artifacts_ready"] is False
    assert summary["production_ai_gpu_return_check_count"] == 18
    assert summary["production_ai_gpu_return_fail_check_count"] == 15
    assert summary["production_ai_gpu_return_failed_check_ids"] == [
        "actual_summary_returned_complete",
        "actual_summary_manifest_bound",
        "actual_summary_out_manifest_csv_present",
        "actual_summary_out_manifest_csv_bound",
        "actual_summary_out_summary_json_bound",
        "actual_summary_manifest_row_counts_consistent",
        "actual_manifest_returned_complete",
        "actual_manifest_npz_paths_complete",
        "actual_manifest_npz_files_exist",
        "actual_manifest_npz_files_valid",
        "actual_manifest_npz_schema_valid",
        "actual_manifest_npz_identity_valid",
        "actual_manifest_operator_verified",
        "queue_manifest_identity_coverage",
        "post_run_force_derivation_validation",
    ]
    assert summary["production_ai_gpu_return_blocker_matrix_count"] == 2
    assert summary["production_ai_gpu_return_blocker_matrix"][0]["check_id"] == (
        "actual_summary_returned_complete"
    )
    assert "summary_present=False" in summary["production_ai_gpu_return_blocker_matrix"][0]["observed"]
    assert summary["production_ai_gpu_return_operator_return_bundle_contract_ready"] is True
    assert summary["production_ai_gpu_return_operator_return_blocker_count"] == 15
    assert summary["production_ai_gpu_return_first_failed_check_id"] == "actual_summary_returned_complete"
    assert summary["production_ai_gpu_return_first_failed_source_artifact"] == (
        "runs/residual_force_trajectory_regeneration_current_summary.json"
    )
    assert "summary_present=False" in summary["production_ai_gpu_return_first_failed_observed"]
    assert "actual returned summary" in summary["production_ai_gpu_return_first_failed_required"]
    assert "Return runs/residual_force_trajectory_regeneration_current_summary.json" in summary[
        "production_ai_gpu_return_first_failed_next_action"
    ]
    assert summary["production_ai_gpu_return_required_artifacts"] == [
        "runs/residual_force_trajectory_regeneration_current_summary.json",
        "runs/residual_force_trajectory_regeneration_current_manifest.csv",
        "regenerated NPZ bundles referenced by the returned manifest",
        "runs/residual_force_derivation_validation_current.json",
    ]
    assert summary["production_ai_gpu_return_operator_return_artifact_completion_matrix_count"] == 4
    assert len(summary["production_ai_gpu_return_operator_return_artifact_completion_matrix"]) == 4
    assert summary["production_ai_gpu_return_operator_return_artifact_completion_matrix"][0][
        "artifact_id"
    ] == "returned_summary_json"
    assert summary["production_ai_gpu_return_operator_return_artifact_completion_blocker_count"] == 4
    assert summary["production_ai_gpu_return_operator_return_artifact_completion_blocker_matrix"][0][
        "artifact_id"
    ] == "returned_summary_json"
    assert summary[
        "production_ai_gpu_return_operator_return_next_artifact_completion_packet_ready"
    ] is True
    next_packet = summary["production_ai_gpu_return_operator_return_next_artifact_completion_packet"]
    assert next_packet["artifact_id"] == "returned_summary_json"
    assert next_packet["template_payload"]["queue_rows"] == 768
    assert next_packet["template_payload"]["prod_mode"] is True
    assert "--prod-mode" in next_packet["full_regeneration_command"]
    assert summary["production_ai_gpu_return_operator_return_next_artifact_id"] == (
        "returned_summary_json"
    )
    assert summary["production_ai_gpu_return_operator_return_next_artifact_path"] == (
        "runs/residual_force_trajectory_regeneration_current_summary.json"
    )
    assert summary["production_ai_gpu_return_operator_return_next_artifact_failed_check_ids"] == [
        "actual_summary_returned_complete"
    ]
    assert summary["commercial_readiness_next_action_matrix_ready"] is True
    assert summary["commercial_readiness_next_action_matrix_count"] == 5
    assert summary["commercial_readiness_next_action_blocker_count"] == 5
    assert summary["product_ai_architecture_gap_blocker_matrix_count"] == 2
    assert summary["product_ai_architecture_current_primary_blocker_id"] == (
        "production_gpu_execution_environment_ready"
    )
    assert summary["product_ai_architecture_first_parallelizable_blocker_id"] == (
        "AQP1.core_binder_01"
    )
    first_commercial_action = summary["commercial_readiness_next_action_blocker_matrix"][0]
    assert first_commercial_action["action_id"] == "production_gpu_execution_environment"
    assert first_commercial_action["gap_id"] == "production_ai_inference_checkpoint"
    assert first_commercial_action["workstream_lane_id"] == "primary_gpu_environment"
    assert first_commercial_action["parallelizable_with_primary_blocker"] is False
    assert first_commercial_action["artifact"] == "runs/rocm_environment_manifest_current.json"
    assert "visible AMD GPU device" in first_commercial_action["required_evidence"]
    assert "visible_device_count" in first_commercial_action["required_operator_inputs"]
    assert first_commercial_action["execution_command"] == "python3 tools/build_rocm_environment_manifest.py"
    assert first_commercial_action["operator_completion_packet_ready"] is True
    assert first_commercial_action["operator_completion_packet"]["artifact_id"] == (
        "rocm_environment_manifest_json"
    )
    assert first_commercial_action["operator_completion_packet"][
        "worker_runtime_receipt_contract"
    ]["artifact_id"] == "rocm_worker_runtime_receipt"
    assert "backend_counts" in first_commercial_action["operator_completion_packet"][
        "worker_runtime_receipt_required_fields_or_columns"
    ]
    assert first_commercial_action["operator_completion_packet"][
        "worker_runtime_receipt_required_field_count"
    ] == 5
    assert first_commercial_action["operator_completion_packet"][
        "post_environment_next_artifact"
    ] == "runs/residual_force_gpu_worker_return_receipt_current.json"
    assert "build_residual_force_gpu_worker_return_receipt.py" in first_commercial_action[
        "operator_completion_packet"
    ]["post_environment_validation_command"]
    assert first_commercial_action["operator_completion_packet"][
        "diagnostic_command_count"
    ] == 3
    assert "rocminfo" in first_commercial_action["operator_completion_packet"][
        "diagnostic_commands"
    ]
    assert "visible_device_count>0" in first_commercial_action["operator_completion_packet"][
        "diagnostic_completion_rule"
    ]
    assert "torch.cuda.device_count" in first_commercial_action["operator_completion_packet"][
        "torch_visibility_probe_command"
    ]
    assert summary["commercial_readiness_next_action_matrix"][1]["action_id"] == (
        "production_ai_return_summary"
    )
    assert summary["commercial_readiness_next_action_matrix"][1]["artifact"] == (
        "runs/residual_force_trajectory_regeneration_current_summary.json"
    )
    assert "processed_rows>=expected_queue_rows" in summary["commercial_readiness_next_action_matrix"][1][
        "required_evidence"
    ]
    assert "queue_rows" in summary["commercial_readiness_next_action_matrix"][1][
        "required_operator_inputs"
    ]
    assert "--prod-mode" in summary["commercial_readiness_next_action_matrix"][1][
        "execution_command"
    ]
    assert summary["commercial_readiness_next_action_matrix"][1]["operator_completion_packet_ready"] is True
    assert summary["commercial_readiness_next_action_matrix"][1]["operator_completion_packet"][
        "template_payload"
    ]["queue_rows"] == 768
    return_action = summary["commercial_readiness_next_action_matrix"][1]
    assert return_action["workstream_lane_id"] == "gpu_return_after_environment"
    assert return_action["blocked_by_action_id"] == "production_gpu_execution_environment"
    assert return_action["parallel_lane_precondition"] == "production_gpu_execution_environment_ready"
    assert return_action["return_bundle_required_artifact_count"] == 4
    assert return_action["return_bundle_required_artifacts"] == [
        "runs/residual_force_trajectory_regeneration_current_summary.json",
        "runs/residual_force_trajectory_regeneration_current_manifest.csv",
        "regenerated NPZ bundles referenced by the returned manifest",
        "runs/residual_force_derivation_validation_current.json",
    ]
    assert return_action["return_bundle_artifact_completion_matrix_count"] == 4
    assert return_action["return_bundle_artifact_completion_matrix"][1]["artifact_id"] == (
        "returned_manifest_csv"
    )
    assert return_action["return_bundle_next_artifact_id"] == "returned_summary_json"
    assert return_action["return_bundle_next_artifact_path"] == (
        "runs/residual_force_trajectory_regeneration_current_summary.json"
    )
    assert return_action["return_bundle_next_artifact_failed_check_ids"] == [
        "actual_summary_returned_complete"
    ]
    assert "operator_verified_npz_exists" in return_action["return_bundle_manifest_required_columns"]
    assert return_action["return_bundle_post_return_validation_command"] == (
        "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
    )
    assert "summary alone does not unlock production AI" in return_action["return_bundle_guardrail"]
    assert summary["commercial_readiness_next_action_matrix"][2]["action_id"] == (
        "transporter_next_slot_exact_evidence"
    )
    assert summary["commercial_readiness_next_action_matrix"][2]["workstream_lane_id"] == (
        "parallel_scope_evidence"
    )
    assert summary["commercial_readiness_next_action_matrix"][2][
        "parallelizable_with_primary_blocker"
    ] is True
    assert summary["commercial_readiness_next_action_matrix"][2][
        "parallel_primary_blocker_action_id"
    ] == "production_gpu_execution_environment"
    assert summary["commercial_readiness_next_action_matrix"][2]["next_slot_id"] == (
        "AQP1.core_binder_01"
    )
    assert summary["commercial_readiness_next_action_matrix"][2]["candidate_ligand_id"] == (
        "aqp1_bacopaside_ii_review_seed"
    )
    assert summary["commercial_readiness_next_action_matrix"][2][
        "target_ready_for_promotion_ids"
    ] == ["GLUT1"]
    assert summary["commercial_readiness_next_action_matrix"][2][
        "target_blocked_for_promotion_ids"
    ] == ["AQP1"]
    assert summary["commercial_readiness_next_action_matrix"][2]["primary_blocker_target_id"] == "AQP1"
    assert summary["commercial_readiness_next_action_matrix"][2]["primary_blocker_packet_step"] == (
        "core_binder_01"
    )
    assert summary["commercial_readiness_next_action_matrix"][2][
        "primary_blocker_candidate_name"
    ] == "bacopaside II"
    assert "blocked transporter target promotion" in summary["commercial_readiness_next_action_matrix"][2][
        "target_scope_guardrail"
    ]
    assert summary["commercial_readiness_next_action_matrix"][2]["target_scope_completion_packet"][
        "claim_safe_guardrail"
    ] == summary["commercial_readiness_next_action_matrix"][2]["target_scope_guardrail"]
    assert "reference_binding_kcal_mol" in summary["commercial_readiness_next_action_matrix"][2][
        "required_operator_inputs"
    ]
    assert "direct_binding_or_claim_safe_kcal_basis" in summary["commercial_readiness_next_action_matrix"][2][
        "required_exact_evidence_fields"
    ]
    assert "target_match_decision" in summary["commercial_readiness_next_action_matrix"][2][
        "required_exact_evidence_fields"
    ]
    assert "functional_surrogate_does_not_authorize_direct_binding_claim" in summary[
        "commercial_readiness_next_action_matrix"
    ][2]["required_claim_guardrails"]
    assert "exact target-pair quantitative evidence" in summary["commercial_readiness_next_action_matrix"][2][
        "claim_safe_completion_rule"
    ]
    assert summary["commercial_readiness_next_action_matrix"][2][
        "next_slot_source_modality_guard_ready"
    ] is True
    assert summary["commercial_readiness_next_action_matrix"][2][
        "next_slot_source_modality"
    ] == "functional_quantitative_surrogate"
    assert summary["commercial_readiness_next_action_matrix"][2][
        "next_slot_source_modality_direct_binding_claim_allowed"
    ] is False
    assert summary["commercial_readiness_next_action_matrix"][2][
        "next_slot_source_modality_decision"
    ] == "keep_blocked_until_exact_direct_binding_or_claim_safe_kcal"
    assert "functional_quantitative_surrogate_is_review_only" in summary[
        "commercial_readiness_next_action_matrix"
    ][2]["next_slot_source_modality_guardrails"]
    assert summary["commercial_readiness_next_action_matrix"][2]["operator_completion_packet_ready"] is True
    assert summary["commercial_readiness_next_action_matrix"][2]["return_bundle_required_artifact_count"] == 5
    assert summary["commercial_readiness_next_action_matrix"][2]["return_bundle_blocker_count"] == 5
    assert summary["commercial_readiness_next_action_matrix"][2]["return_bundle_next_artifact_id"] == (
        "operator_review_row"
    )
    assert summary["commercial_readiness_next_action_matrix"][2]["return_bundle_artifact_completion_matrix"][0][
        "artifact_id"
    ] == "operator_review_row"
    assert summary["commercial_readiness_next_action_matrix"][3]["action_id"] == "pxr_next_exact_review"
    assert summary["commercial_readiness_next_action_matrix"][3]["workstream_lane_id"] == (
        "parallel_scope_evidence"
    )
    assert summary["commercial_readiness_next_action_matrix"][3][
        "parallelizable_with_primary_blocker"
    ] is True
    assert summary["commercial_readiness_next_action_matrix"][3]["next_review_row_id"] == (
        "pxr_review_d603772038dff21e"
    )
    assert "replacement_source_url_or_doi" in summary["commercial_readiness_next_action_matrix"][3][
        "required_operator_inputs"
    ]
    assert "target_match_confirmed" in summary["commercial_readiness_next_action_matrix"][3][
        "required_exact_evidence_fields"
    ]
    assert "conflict_resolution_decision" in summary["commercial_readiness_next_action_matrix"][3][
        "required_exact_evidence_fields"
    ]
    assert "human_NR1I2_PXR_target_match_required" in summary["commercial_readiness_next_action_matrix"][3][
        "required_claim_guardrails"
    ]
    assert "activity-proxy conflict" in summary["commercial_readiness_next_action_matrix"][3][
        "claim_safe_completion_rule"
    ]
    assert summary["commercial_readiness_next_action_matrix"][3]["operator_completion_packet_ready"] is True
    assert summary["commercial_readiness_next_action_matrix"][3]["return_bundle_required_artifact_count"] == 5
    assert "runs/pxr_authoritative_reconciliation_packet_current.json" in summary[
        "commercial_readiness_next_action_matrix"
    ][3]["return_bundle_required_artifacts"]
    assert summary["commercial_readiness_next_action_matrix"][3]["return_bundle_blocker_count"] == 1
    assert summary["commercial_readiness_next_action_matrix"][3]["return_bundle_next_artifact_id"] == (
        "operator_review_row"
    )
    assert summary["commercial_readiness_next_action_matrix"][3]["return_bundle_artifact_completion_matrix"][0][
        "artifact_id"
    ] == "operator_review_row"
    assert summary["commercial_readiness_next_action_matrix"][4]["action_id"] == (
        "broad_platform_claim_floor"
    )
    assert summary["commercial_readiness_next_action_matrix"][4]["workstream_lane_id"] == (
        "scope_claim_floor_after_evidence"
    )
    assert summary["commercial_readiness_next_action_matrix"][4][
        "parallelizable_with_primary_blocker"
    ] is True
    assert summary["commercial_readiness_next_action_matrix"][4]["blocked_stage_evidence_count"] == 4
    assert summary["commercial_readiness_next_action_matrix"][4]["blocked_stage_dependency_count"] == 4
    assert "general_platform_claim_allowed_false" in summary[
        "commercial_readiness_next_action_matrix"
    ][4]["required_claim_guardrails"][0]
    assert "general protein-ligand platform wording blocked" in summary[
        "commercial_readiness_next_action_matrix"
    ][4]["claim_safe_completion_rule"]
    assert summary["commercial_readiness_next_action_matrix"][4]["first_blocked_stage_id"] == (
        "transporter_claim_acceptance"
    )
    assert summary["commercial_readiness_next_action_matrix"][4]["first_blocked_evidence_row_id"] == (
        "AQP1.core_binder_01"
    )
    assert summary["commercial_readiness_next_action_matrix"][4]["first_blocked_target_id"] == "AQP1"
    assert summary["commercial_readiness_next_action_matrix"][4][
        "first_blocked_required_missing_fields"
    ] == "replacement_reference_binding_kcal_mol"
    assert summary["commercial_readiness_next_action_matrix"][4]["operator_completion_packet"][
        "first_blocked_stage_id"
    ] == "transporter_claim_acceptance"
    assert "ready_restricted_families_do_not_authorize_general_protein_ligand_claim" in summary[
        "commercial_readiness_next_action_matrix"
    ][4]["operator_completion_packet"]["required_claim_guardrails"]
    assert "transporter_claim_acceptance" in summary["commercial_readiness_next_action_matrix"][4][
        "required_operator_inputs"
    ]
    assert summary["commercial_readiness_handoff_bundle_status"] == (
        "product_commercial_readiness_handoff_bundle_ready"
    )
    assert summary["commercial_readiness_handoff_bundle_ready"] is True
    assert summary["commercial_readiness_handoff_bundle_artifact_count"] == 3
    assert summary["commercial_readiness_handoff_bundle_blocked_artifact_count"] == 0
    assert summary["commercial_readiness_handoff_bundle_blocked_artifact_ids"] == []
    assert summary["commercial_readiness_handoff_bundle_artifact_reference_contract_ready"] is True
    assert summary["commercial_readiness_handoff_bundle_artifact_reference_count"] == 13
    assert summary["commercial_readiness_handoff_bundle_local_missing_artifact_reference_count"] == 0
    assert (
        summary[
            "commercial_readiness_handoff_bundle_operator_return_pending_artifact_reference_count"
        ]
        == 3
    )
    assert summary["commercial_readiness_handoff_bundle_first_action_id"] == "production_ai_return_summary"
    assert summary["commercial_readiness_handoff_bundle_first_operator_input_artifact"] == (
        "runs/residual_force_trajectory_regeneration_current_summary_template.json"
    )
    assert summary["production_ai_delta_force_closure_acceptance_packet_ready"] is True
    assert summary["production_ai_delta_force_closure_ready"] is False
    assert summary["production_ai_delta_force_closure_first_blocked_output_field"] == "delta_force"
    assert summary["production_ai_delta_force_closure_failed_stage_count"] == 9
    assert summary["production_ai_delta_force_closure_failed_stage_ids"] == [
        "gpu_worker_return_receipt"
    ]
    assert summary["production_ai_delta_force_closure_next_stage_id"] == "gpu_worker_return_receipt"
    assert "build_residual_force_gpu_worker_return_receipt.py" in summary[
        "production_ai_delta_force_closure_next_stage_validation_command"
    ]
    assert summary["product_scope_closure_acceptance_packet_ready"] is True
    assert summary["product_scope_closure_acceptance_ready"] is False
    assert summary["product_scope_closure_acceptance_stage_count"] == 5
    assert summary["product_scope_closure_acceptance_blocked_stage_count"] == 4
    assert summary["product_scope_closure_acceptance_next_stage_id"] == "transporter_claim_acceptance"
    assert summary["product_scope_closure_acceptance_first_blocked_evidence_row_id"] == (
        "AQP1.core_binder_01"
    )
    assert summary["product_scope_closure_acceptance_first_blocked_target_id"] == "AQP1"
    assert summary["product_scope_closure_acceptance_first_blocked_required_missing_fields"] == (
        "replacement_reference_binding_kcal_mol"
    )
    assert summary["production_ai_gpu_return_manifest_required_columns"] == [
        "queue_id",
        "expected_regenerated_trajectory_npz",
        "status",
        "operator_verified_npz_exists",
    ]
    assert summary["production_ai_gpu_return_validation_ladder_ready"] is True
    assert summary["production_ai_gpu_return_handoff_binding_ready"] is True
    assert summary["production_ai_gpu_return_handoff_queue_csv"] == (
        "runs/residual_force_trajectory_regeneration_queue_current.csv"
    )
    assert len(summary["production_ai_gpu_return_handoff_queue_csv_sha256"]) == 64
    assert "generate_ligand_trajectory_engine.py" in summary[
        "production_ai_gpu_return_handoff_full_regeneration_command"
    ]
    assert summary["production_ai_gpu_return_handoff_return_manifest_schema_contract_ready"] is True
    assert "queue_row_fingerprint" in summary[
        "production_ai_gpu_return_handoff_return_manifest_required_identity_rule"
    ]
    assert summary["production_ai_gpu_return_handoff_return_manifest_fingerprint_columns"] == [
        "queue_row_fingerprint",
        "source_queue_row_fingerprint",
    ]
    assert "queue_id" in summary["production_ai_gpu_return_handoff_return_manifest_queue_id_columns"]
    assert "expected_regenerated_trajectory_npz" in summary[
        "production_ai_gpu_return_handoff_return_manifest_npz_columns"
    ]
    assert summary["production_ai_gpu_return_operator_acceptance_matrix_ready"] is True
    assert len(summary["production_ai_gpu_return_operator_acceptance_matrix"]) == 2
    assert summary["production_ai_gpu_return_operator_acceptance_matrix"][0]["stage_id"] == (
        "gpu_return_templates_preflight"
    )
    assert len(summary["production_ai_gpu_return_operator_acceptance_current_blocked_stage_matrix"]) == 1
    assert summary["production_ai_gpu_return_operator_acceptance_current_blocked_stage_matrix"][0][
        "stage_id"
    ] == "returned_summary_acceptance"
    assert summary["production_ai_gpu_return_operator_acceptance_stage_check_matrix_count"] == 2
    assert summary["production_ai_gpu_return_operator_acceptance_stage_check_matrix"][1]["stage_id"] == (
        "returned_summary_acceptance"
    )
    assert summary["production_ai_gpu_return_operator_acceptance_stage_check_matrix"][1][
        "failed_check_ids"
    ] == ["actual_summary_returned_complete"]
    assert summary[
        "production_ai_gpu_return_operator_acceptance_current_blocked_stage_check_matrix_count"
    ] == 1
    assert summary["production_ai_gpu_return_operator_acceptance_current_blocked_stage_check_matrix"][0][
        "stage_id"
    ] == "returned_summary_acceptance"
    assert summary["production_ai_gpu_return_operator_acceptance_stage_count"] == 5
    assert summary["production_ai_gpu_return_operator_acceptance_ready_stage_count"] == 1
    assert summary["production_ai_gpu_return_operator_acceptance_blocked_stage_count"] == 4
    assert summary["production_ai_gpu_return_operator_acceptance_ready_stage_ids"] == [
        "gpu_return_templates_preflight"
    ]
    assert summary["production_ai_gpu_return_operator_acceptance_blocked_stage_ids"][0] == (
        "returned_summary_acceptance"
    )
    assert summary["production_ai_gpu_return_operator_acceptance_next_stage_id"] == (
        "returned_summary_acceptance"
    )
    assert summary["production_ai_gpu_return_operator_acceptance_next_stage_artifact"] == (
        "runs/residual_force_trajectory_regeneration_current_summary.json"
    )
    assert summary["production_ai_gpu_return_operator_acceptance_next_stage_validation_command"] == (
        "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
    )
    assert "summary is complete" in summary[
        "production_ai_gpu_return_operator_acceptance_next_stage_release_effect"
    ]
    assert summary["production_ai_gpu_return_operator_acceptance_next_stage_required_checks"][0] == (
        "actual_summary_returned_complete"
    )
    assert summary["production_ai_gpu_return_expected_queue_rows"] == 768
    assert summary["production_ai_gpu_return_manifest_template_csv"] == (
        "runs/residual_force_gpu_worker_return_manifest_template_current.csv"
    )
    assert summary["production_ai_gpu_return_summary_template_csv"] == (
        "runs/residual_force_gpu_worker_return_summary_template_current.csv"
    )
    assert summary["production_ai_gpu_return_summary_template_payload_json"] == (
        "runs/residual_force_trajectory_regeneration_current_summary_template.json"
    )
    assert summary["production_ai_gpu_return_summary_template_required_fields"] == [
        "queue_rows",
        "processed_rows",
        "ok_rows",
        "failed_rows",
        "aborted_early",
        "out_manifest_csv",
        "out_summary_json",
        "prod_mode",
        "require_rust_hip",
        "backend_counts",
    ]
    assert "processed_rows>=expected_queue_rows" in summary[
        "production_ai_gpu_return_summary_template_completion_rule"
    ]
    assert summary["production_ai_gpu_return_summary_template_backend_provenance_contract_ready"] is True
    assert summary["production_ai_gpu_return_summary_template_required_backend_provenance_fields"] == [
        "prod_mode",
        "require_rust_hip",
        "backend_counts",
    ]
    assert "backend_counts has rust_hip*" in summary[
        "production_ai_gpu_return_summary_template_backend_provenance_completion_rule"
    ]
    assert summary["production_ai_gpu_return_manifest_template_row_count"] == 768
    assert summary["production_ai_gpu_return_manifest_operator_verification_placeholder_count"] == 768
    assert summary["production_ai_gpu_manifest_npz_files_valid"] is False
    assert summary["production_ai_gpu_manifest_npz_file_valid_count"] == 0
    assert summary["production_ai_gpu_manifest_npz_file_invalid_count"] == 0
    assert summary["production_ai_gpu_manifest_ok_row_invalid_npz_file_count"] == 0
    assert summary["production_ai_gpu_manifest_operator_verified_invalid_npz_file_count"] == 0
    assert summary["production_ai_gpu_manifest_npz_schema_valid"] is False
    assert summary["production_ai_gpu_manifest_npz_schema_valid_count"] == 0
    assert summary["production_ai_gpu_manifest_npz_schema_invalid_count"] == 0
    assert summary["production_ai_gpu_manifest_ok_row_invalid_npz_schema_count"] == 0
    assert summary["production_ai_gpu_manifest_operator_verified_invalid_npz_schema_count"] == 0
    assert summary["production_ai_gpu_manifest_npz_identity_valid"] is False
    assert summary["production_ai_gpu_manifest_npz_identity_valid_count"] == 0
    assert summary["production_ai_gpu_manifest_npz_identity_invalid_count"] == 0
    assert summary["production_ai_gpu_manifest_ok_row_invalid_npz_identity_count"] == 0
    assert summary["production_ai_gpu_manifest_operator_verified_invalid_npz_identity_count"] == 0
    assert summary["production_ai_gpu_return_actual_summary_return_path"] == (
        "runs/residual_force_trajectory_regeneration_current_summary.json"
    )
    assert summary["production_ai_gpu_return_actual_manifest_return_path"] == (
        "runs/residual_force_trajectory_regeneration_current_manifest.csv"
    )
    assert summary["production_ai_gpu_summary_manifest_bound"] is False
    assert summary["production_ai_gpu_summary_manifest_csv"] == ""
    assert summary["production_ai_gpu_summary_out_manifest_csv_present"] is False
    assert summary["production_ai_gpu_summary_out_manifest_csv"] == ""
    assert summary["production_ai_gpu_summary_out_manifest_csv_bound"] is False
    assert summary["production_ai_gpu_summary_out_summary_json_bound"] is False
    assert summary["production_ai_gpu_summary_out_summary_json"] == ""
    assert summary["production_ai_gpu_summary_manifest_row_counts_consistent"] is False
    assert summary["production_ai_gpu_return_post_return_validation_command"] == (
        "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
    )
    assert "full GPU regeneration" in summary["production_ai_gpu_return_next_required_step"]
    assert summary["production_ai_promotion_workbench_status"] == (
        "blocked_product_production_ai_promotion_workbench"
    )
    assert summary["production_ai_promotion_workbench_ready"] is True
    assert summary["production_ai_promotion_ready"] is False
    assert summary["production_ai_promotion_first_blocked_stage_id"] == "gpu_return_receipt"
    assert summary["production_ai_promotion_first_blocked_stage_artifact"] == (
        "runs/residual_force_gpu_worker_return_receipt_current.json"
    )
    assert summary["production_ai_promotion_first_blocked_stage_ready_key"] == "gpu_worker_return_receipt_ready"
    assert summary["production_ai_promotion_blocked_stage_count"] == 10
    assert summary["production_ai_promotion_blocked_stage_ids"][0] == "gpu_return_receipt"
    assert summary["production_ai_force_gpu_worker_handoff_ready"] is True
    assert summary["production_ai_force_gpu_worker_operator_action_required"] is True
    assert "generate_ligand_trajectory_engine.py" in summary["production_ai_force_gpu_full_regeneration_command"]
    assert "build_residual_force_gpu_worker_return_receipt.py" in summary[
        "production_ai_force_gpu_post_return_validation_command"
    ]
    assert summary["production_ai_force_gpu_post_return_unlock_output_fields"] == [
        "delta_force",
        "uncertainty",
        "abstention_reason",
        "stage2_route_decision",
    ]
    assert summary["production_ai_force_gpu_post_return_required_production_output_fields"] == [
        "delta_score",
        "corrected_score",
        "delta_energy",
        "delta_force",
        "uncertainty",
        "abstention_reason",
        "stage2_route_decision",
    ]
    assert summary["production_ai_force_gpu_post_return_gpu_unlock_artifacts"] == [
        "runs/residual_force_gpu_worker_return_receipt_current.json",
        "runs/residual_production_training_data_contract_current.json",
    ]
    assert summary["production_ai_force_gpu_post_run_validation_commands"] == [
        "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
        "python3 tools/build_product_goal_completion_audit.py",
    ]
    assert summary["production_ai_force_gpu_post_return_min_expected_label_rows"] == 768
    assert summary["production_ai_force_gpu_post_return_promotion_ladder_stage_count"] == 10
    assert summary["production_ai_force_gpu_post_return_promotion_ladder_contract_ready"] is True
    assert summary["production_ai_force_gpu_post_return_promotion_ladder_currently_satisfied"] is False
    assert summary["production_ai_force_gpu_post_return_promotion_ladder_current_blocked_stage_count"] == 7
    assert summary["production_ai_force_gpu_post_return_promotion_ladder_current_blocked_stage_ids"][0] == (
        "gpu_return_acceptance"
    )
    assert summary["production_ai_force_gpu_post_return_promotion_ladder_current_next_stage_id"] == (
        "gpu_return_acceptance"
    )
    assert summary["production_ai_force_gpu_post_return_promotion_ladder_stage_ids"] == [
        "gpu_return_receipt",
        "product_goal_completion_audit",
    ]
    assert summary["production_ai_force_gpu_post_return_promotion_ladder_missing_ready_keys"] == []
    assert summary["production_ai_force_gpu_receipt_manifest_identity_row_count"] == 0
    assert summary["production_ai_force_gpu_receipt_matched_queue_id_count"] == 0
    assert summary["production_ai_force_gpu_receipt_matched_expected_npz_count"] == 0
    assert summary["production_ai_force_gpu_receipt_matched_queue_fingerprint_count"] == 0
    assert "scope_closure_first_scientific_blocker=AQP1.core_binder_01" in summary["product_ai_scope_backlog_detail"]
    assert summary["product_scope_first_scientific_blocker"] == "AQP1.core_binder_01"
    assert summary["product_scope_manual_review_subcheck_count"] == 54
    assert summary["product_scope_transporter_manual_review_subcheck_count"] == 54
    assert summary["product_scope_transporter_identity_scaffold_confirmation_required_count"] == 11
    assert summary["product_scope_transporter_direct_binding_or_kcal_confirmation_required_count"] == 4
    assert summary["product_scope_transporter_negative_quantitative_confirmation_required_count"] == 6
    assert summary["product_scope_allowed_families"] == []
    assert summary["product_scope_blocked_claim_scopes"] == []
    assert summary["product_scope_general_platform_claim_allowed"] is False
    assert summary["product_scope_domain_count"] == 6
    assert summary["product_scope_ready_domain_count"] == 3
    assert summary["product_scope_missing_domain_count"] == 3
    assert summary["product_scope_ready_domains"] == ["ca2", "idp_broad", "all_atom"]
    assert summary["product_scope_missing_domains"] == ["transporter", "pxr", "general_protein_ligand"]
    assert summary["product_scope_first_blocked_domain"] == "transporter"
    assert summary["product_scope_first_blocked_domain_artifact"] == (
        "runs/transporter_blocker_capture_sheet_current.json"
    )
    assert "p0_open=1" in summary["product_scope_first_blocked_domain_observed"]
    assert "supportive transporter evidence" in summary["product_scope_first_blocked_domain_requirement"]
    assert "Reduce transporter P0" in summary["product_scope_first_blocked_domain_next_action"]
    assert summary["product_scope_transporter_p0_readiness_matrix_ready"] is True
    assert summary["product_scope_transporter_p0_readiness_matrix_artifact"] == (
        "runs/transporter_p0_closure_readiness_matrix_current.json"
    )
    assert summary["product_scope_transporter_p0_auto_close_ready_artifact_count"] == 0
    assert summary["product_scope_transporter_p0_manual_or_external_required_artifact_count"] == 6
    assert summary["product_scope_transporter_p0_unresolved_slot_count"] == 11
    assert summary["product_scope_transporter_p0_auto_close_ready_slot_count"] == 0
    assert summary["product_scope_transporter_p0_external_exact_evidence_required_slot_count"] == 11
    assert summary["product_scope_transporter_p0_first_manual_or_external_required_step_id"] == (
        "aqp1_ligand_reference"
    )
    assert summary["product_scope_transporter_p0_first_manual_or_external_required_slot_step"] == (
        "core_binder_01"
    )
    assert summary["product_scope_transporter_p0_first_manual_or_external_required_action"].startswith(
        "Acquire exact"
    )
    assert summary["product_scope_transporter_p0_evidence_acquisition_packet_ready"] is True
    assert summary["product_scope_transporter_p0_evidence_acquisition_artifact"] == (
        "runs/transporter_p0_evidence_acquisition_packet_current.json"
    )
    assert summary["product_scope_transporter_p0_evidence_acquisition_exact_request_slot_count"] == 11
    assert summary["product_scope_transporter_p0_evidence_acquisition_unresolved_slot_count"] == 11
    assert summary["product_scope_transporter_p0_evidence_acquisition_first_target_id"] == "AQP1"
    assert summary["product_scope_transporter_p0_evidence_acquisition_first_packet_step"] == "core_binder_01"
    assert summary["product_scope_transporter_p0_evidence_acquisition_first_replacement_ligand_id"] == (
        "aqp1_bacopaside_ii_review_seed"
    )
    assert summary["product_scope_transporter_p0_evidence_acquisition_first_request_mode"] == (
        "exact_target_pair_quantitative_binder_kcal_required"
    )
    assert summary["product_scope_transporter_p0_evidence_acquisition_first_source_signal"].startswith(
        "https://pubmed"
    )
    assert summary["product_scope_transporter_p0_evidence_acquisition_first_required_missing_fields"] == (
        "replacement_reference_binding_kcal_mol"
    )
    assert summary["product_scope_transporter_p0_evidence_acquisition_first_next_required_action"].startswith(
        "Acquire exact"
    )
    assert summary[
        "product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet_ready"
    ] is True
    assert summary["product_scope_transporter_p0_evidence_acquisition_next_slot_id"] == (
        "AQP1.core_binder_01"
    )
    assert summary[
        "product_scope_transporter_p0_evidence_acquisition_next_slot_operator_review_artifact"
    ] == "runs/transporter_manual_review_intake_template_current.csv"
    assert summary[
        "product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet"
    ]["candidate_ligand_id"] == "aqp1_bacopaside_ii_review_seed"
    assert summary[
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_source_count"
    ] == 6
    public_recheck_result = summary[
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_result"
    ]
    assert "chembl_aqp1_bacopaside_ii_rows=0" in public_recheck_result
    assert "bindingdb_p29972_affinities=0" in public_recheck_result
    assert "CHEMBL195380_not_CHEMBL390758" in public_recheck_result
    assert summary[
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_database_recheck_row_count"
    ] == 2
    assert summary[
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_ligand_identity_mismatch_row_count"
    ] == 1
    assert summary[
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_pubchem_cid"
    ] == "9876264"
    assert summary[
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_id"
    ] == "CHEMBL390758"
    assert summary[
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_chembl_target_id"
    ] == "CHEMBL4523210"
    assert summary[
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_bindingdb_uniprot_affinity_row_count"
    ] == 0
    assert summary[
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_aqp1_activity_row_count"
    ] == 0
    assert "CHEMBL195380" in summary[
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_functional_ic50_identity_mismatch_detail"
    ]
    assert summary["product_scope_evidence_queue_next_operator_completion_packet_ready"] is True
    assert summary["product_scope_evidence_queue_next_operator_completion_slot_id"] == (
        "AQP1.core_binder_01"
    )
    assert summary["product_scope_evidence_queue_next_operator_completion_expected_evidence_type"] == (
        "direct_or_claim_safe_binding_kcal"
    )
    assert (
        summary["product_scope_evidence_queue_next_operator_completion_required_exact_evidence_field_count"]
        == 19
    )
    assert "target_uniprot_accession" in summary[
        "product_scope_evidence_queue_next_operator_completion_required_exact_evidence_fields"
    ]
    assert "reference_binding_kcal_mol" in summary[
        "product_scope_evidence_queue_next_operator_completion_required_operator_intake_columns"
    ]
    assert "functional_surrogate_does_not_authorize_direct_binding_claim" in summary[
        "product_scope_evidence_queue_next_operator_completion_required_claim_guardrails"
    ]
    assert summary["product_scope_evidence_queue_next_operator_completion_operator_review_artifact"] == (
        "runs/transporter_manual_review_intake_template_current.csv"
    )
    assert "ligand_binding_reference_blind_aqp1" in summary[
        "product_scope_evidence_queue_next_operator_completion_post_intake_synchronization_targets"
    ]
    assert "build_product_goal_completion_audit.py" in summary[
        "product_scope_evidence_queue_next_operator_completion_acceptance_gate_commands"
    ]
    assert summary["product_scope_evidence_queue_next_operator_completion_contract_artifact"].endswith(
        "#next_slot_completion_packet"
    )
    assert summary[
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_sidecar_ready"
    ] is True
    assert summary[
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_candidate_name"
    ] == "bacopaside II"
    assert summary[
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_source_anchor"
    ] == "PMID 27474162"
    assert summary[
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_target_uniprot"
    ] == "P29972"
    assert summary[
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol"
    ] == "-6.47"
    assert summary[
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_direct_binding_claim_allowed"
    ] == "no"
    assert summary[
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank"
    ] == "yes"
    assert summary["product_scope_evidence_queue_pxr_exact_review_sidecar_row_count"] == 6
    assert summary["product_scope_evidence_queue_next_pxr_exact_review_sidecar_ready"] is True
    assert summary["product_scope_evidence_queue_next_pxr_exact_review_row_id"] == (
        "pxr_review_d603772038dff21e"
    )
    assert summary["product_scope_evidence_queue_next_pxr_exact_review_candidate_name"] == (
        "acetaminophen"
    )
    assert summary["product_scope_evidence_queue_next_pxr_exact_review_required_evidence_mode"] == (
        "exact_human_nr1i2_pxr_conflict_resolution_or_negative_value_required"
    )
    assert summary["product_scope_evidence_queue_next_pxr_exact_review_target_match_confirmed"] == (
        "OPERATOR_FILL_TRUE_OR_FALSE"
    )
    assert summary[
        "product_scope_evidence_queue_next_pxr_exact_review_replacement_reference_binding_kcal_mol"
    ].startswith("OPERATOR_FILL_EXACT_HUMAN_NR1I2_PXR_KCAL")
    assert summary["product_scope_evidence_queue_next_pxr_exact_review_authoritative_apply_allowed"] is False
    assert summary["product_scope_evidence_queue_next_pxr_exact_review_scope_promotion_allowed"] is False
    assert summary["product_scope_general_platform_domain_floor_ready"] is False
    assert summary["product_scope_general_platform_domain_floor_missing_domain_count"] == 2
    assert summary["product_scope_general_platform_domain_floor_missing_domains"] == ["transporter", "pxr"]
    assert summary["product_scope_evidence_priority_ready"] is True
    assert summary["product_scope_evidence_priority_queue_item_count"] == 21
    assert summary["product_scope_evidence_priority_open_item_count"] == 21
    assert summary["product_scope_evidence_priority_local_crosscheck_candidate_count"] == 11
    assert summary["product_scope_evidence_priority_external_primary_exact_required_count"] == 6
    assert summary["product_scope_evidence_priority_all_operator_packet_bindings_ready"] is True
    assert summary["product_scope_evidence_priority_operator_packet_binding_ready_count"] == 21
    assert summary["product_scope_evidence_priority_operator_packet_binding_missing_count"] == 0
    assert summary["product_scope_evidence_priority_top_item_id"] == "AQP1.core_binder_01"
    assert summary["product_scope_evidence_priority_top_domain"] == "transporter"
    assert summary["product_scope_evidence_priority_top_bucket"] == "local_crosscheck_review_present_but_exact_quant_required"
    assert (
        summary["product_scope_evidence_priority_top_required_evidence_type"]
        == "exact_transporter_target_pair_quantitative_binder_kcal"
    )
    assert (
        summary["product_scope_evidence_priority_top_review_template_artifact"]
        == "runs/transporter_manual_review_intake_template_current.json"
    )
    assert (
        summary["product_scope_evidence_priority_top_apply_gate_artifact"]
        == "runs/transporter_binder_promotion_gate_current.json"
    )
    assert "Review local crosscheck files" in summary["product_scope_evidence_priority_top_next_step"]
    assert summary["product_scope_evidence_priority_next_required_step"] == (
        "Triage local AQP1/GLUT1 crosscheck candidates first."
    )
    assert summary["product_scope_evidence_intake_ready"] is True
    assert summary["product_scope_evidence_intake_row_count"] == 21
    assert summary["product_scope_evidence_intake_all_operator_packet_bindings_ready"] is True
    assert summary["product_scope_evidence_intake_operator_packet_binding_ready_count"] == 21
    assert summary["product_scope_evidence_intake_operator_packet_binding_missing_count"] == 0
    assert summary["product_scope_local_crosscheck_triage_item_count"] == 10
    assert summary["product_scope_local_crosscheck_intake_ready_count"] == 10
    assert summary["product_scope_external_exact_evidence_required_count"] == 6
    assert summary["product_scope_guardrail_item_count"] == 5
    assert summary["product_scope_transporter_triage_packet_ready"] is True
    assert summary["product_scope_transporter_operator_review_evidence_matrix_ready"] is True
    assert summary["product_scope_transporter_claim_safe_local_evidence_ready_count"] == 0
    assert summary["product_scope_transporter_claim_safe_local_evidence_blocked_count"] == 11
    assert summary["product_scope_transporter_direct_binding_claim_blocked_count"] == 4
    assert summary["product_scope_transporter_negative_value_claim_blocked_count"] == 6
    assert summary["product_scope_transporter_top_claim_safe_blocker"] == (
        "functional_assay_quantitative_but_not_direct_binding_claim_safe"
    )
    assert summary["product_scope_transporter_candidate_assignment_required_count"] == 7
    assert summary["product_scope_transporter_functional_quantitative_only_direct_gap_open_count"] == 3
    assert summary["product_scope_transporter_review_only_direct_binding_gap_count"] == 1
    assert summary["product_scope_transporter_candidate_ready_for_manual_review_count"] == 11
    assert summary["product_scope_transporter_candidate_ready_for_apply_count"] == 0
    assert summary["product_scope_transporter_manual_review_intake_ready"] is True
    assert summary["product_scope_transporter_manual_review_template_row_count"] == 11
    assert summary["product_scope_transporter_manual_review_direct_binding_evidence_required_count"] == 4
    assert summary["product_scope_transporter_manual_review_negative_quantitative_value_required_count"] == 6
    assert summary["product_scope_transporter_manual_review_decision_placeholder_count"] == 11
    assert summary["product_scope_transporter_manual_review_first_review_item_id"] == "AQP1.core_binder_01"
    assert summary["product_scope_transporter_manual_review_first_review_target_id"] == "AQP1"
    assert (
        summary["product_scope_transporter_manual_review_first_review_candidate_ligand_id"]
        == "aqp1_bacopaside_ii_review_seed"
    )
    assert summary["product_scope_transporter_manual_review_first_review_replacement_source"] == (
        "https://pubmed.ncbi.nlm.nih.gov/27474162/"
    )
    assert (
        summary["product_scope_transporter_manual_review_first_review_replacement_reference_binding_kcal_mol"]
        == ""
    )
    assert summary[
        "product_scope_transporter_manual_review_first_review_direct_binding_evidence_required"
    ] is True
    assert summary[
        "product_scope_transporter_manual_review_first_review_direct_binding_source_url_or_doi"
    ] == "OPERATOR_FILL_EXACT_DIRECT_BINDING_SOURCE_OR_KEEP_BLOCKED"
    assert summary["product_scope_transporter_manual_review_first_review_review_decision"] == (
        "OPERATOR_FILL_APPROVE_FOR_DRAFT_OR_KEEP_BLOCKED"
    )
    assert summary[
        "product_scope_transporter_manual_review_first_review_p0_slot_overlay_required_missing_fields"
    ] == "replacement_reference_binding_kcal_mol"
    assert summary[
        "product_scope_transporter_manual_review_first_review_p0_slot_overlay_scope_promotion_allowed"
    ] is False
    assert summary["product_scope_breadth_contract_status"] == "blocked_product_scope_breadth_contract"
    assert summary["product_scope_breadth_contract_artifact_path"] == (
        "runs/product_scope_breadth_contract_current.json"
    )
    assert summary["product_scope_operator_transfer_manifest_ready"] is True
    assert summary["product_scope_operator_transfer_outbound_artifact_count"] == 10
    assert "runs/transporter_manual_review_intake_template_current.json" in summary[
        "product_scope_operator_transfer_outbound_artifacts"
    ]
    assert summary["product_scope_operator_transfer_inbound_artifact_count"] == 4
    assert summary["product_scope_operator_transfer_first_return_artifact"] == (
        "completed runs/transporter_manual_review_intake_template_current.csv with OPERATOR_FILL placeholders resolved"
    )
    assert summary["product_scope_operator_transfer_acceptance_artifact"] == (
        "runs/product_scope_breadth_contract_current.json"
    )
    assert summary["product_scope_operator_transfer_acceptance_ready_key"] == "scope_breadth_ready"
    assert summary["product_scope_operator_transfer_next_acceptance_stage"] == "transporter_claim_acceptance"
    assert summary["product_scope_acceptance_matrix_ready"] is True
    assert summary["product_scope_claim_expansion_contract_ready"] is True
    assert summary["product_scope_claim_expansion_currently_satisfied"] is False
    assert summary["product_scope_claim_expansion_current_blocked_stage_count"] == 4
    assert summary["product_scope_claim_expansion_current_blocked_stage_ids"][0] == (
        "transporter_claim_acceptance"
    )
    assert summary["product_scope_claim_expansion_current_next_stage_id"] == "transporter_claim_acceptance"
    assert summary["product_scope_claim_expansion_current_next_stage_unlock_claim_scopes"] == [
        "transporter_domain_promotion"
    ]
    assert summary["product_scope_acceptance_stage_count"] == 5
    assert summary["product_scope_acceptance_ready_stage_count"] == 1
    assert summary["product_scope_acceptance_blocked_stage_count"] == 4
    assert summary["product_scope_acceptance_ready_stage_ids"] == ["scope_evidence_acquisition_preflight"]
    assert summary["product_scope_acceptance_blocked_stage_ids"][0] == "transporter_claim_acceptance"
    assert len(summary["product_scope_acceptance_matrix"]) == 5
    assert len(summary["product_scope_acceptance_current_blocked_stage_matrix"]) == 4
    assert summary["product_scope_acceptance_release_blocker_stage_count"] == 4
    assert summary["product_scope_acceptance_release_blocker_stage_ids"] == [
        "transporter_claim_acceptance",
        "pxr_claim_acceptance",
        "breadth_domain_floor_acceptance",
        "general_platform_claim_acceptance",
    ]
    assert summary["product_scope_acceptance_matrix"][1]["stage_id"] == "transporter_claim_acceptance"
    assert summary["product_scope_acceptance_matrix"][1]["unlock_claim_scopes"] == [
        "transporter_domain_promotion"
    ]
    assert summary["product_scope_acceptance_stage_evidence_matrix_count"] == 5
    assert len(summary["product_scope_acceptance_stage_evidence_matrix"]) == 5
    assert summary["product_scope_acceptance_stage_evidence_matrix"][1]["stage_id"] == (
        "transporter_claim_acceptance"
    )
    assert summary["product_scope_acceptance_stage_evidence_matrix"][1]["first_blocked_evidence_row"][
        "evidence_row_id"
    ] == "AQP1.core_binder_01"
    assert summary["product_scope_acceptance_current_blocked_stage_evidence_matrix_count"] == 4
    assert summary["product_scope_acceptance_current_blocked_stage_evidence_matrix"][0]["stage_id"] == (
        "transporter_claim_acceptance"
    )
    assert summary["product_scope_acceptance_next_stage_id"] == "transporter_claim_acceptance"
    assert summary["product_scope_acceptance_next_stage_unlock_claim_scopes"] == [
        "transporter_domain_promotion"
    ]
    assert "build_transporter_binder_promotion_gate.py" in summary[
        "product_scope_acceptance_next_stage_validation_command"
    ]
    assert summary["product_scope_acceptance_next_stage_required_checks"][0] == (
        "transporter_claim_safe_local_evidence_ready"
    )
    assert summary["product_scope_pxr_exact_review_intake_ready"] is True
    assert summary["product_scope_pxr_exact_review_template_row_count"] == 6
    assert summary["product_scope_pxr_exact_review_expected_blocked_row_count"] == 6
    assert summary["product_scope_pxr_exact_review_conflict_resolution_required_count"] == 3
    assert summary["product_scope_pxr_exact_review_kcal_placeholder_count"] == 6
    assert summary["product_scope_pxr_exact_review_source_placeholder_count"] == 6
    assert summary["product_scope_pxr_exact_review_target_match_placeholder_count"] == 6
    assert summary["product_scope_pxr_exact_review_decision_placeholder_count"] == 6
    assert summary["product_scope_pxr_exact_review_next_review_completion_packet_ready"] is True
    assert summary["product_scope_pxr_exact_review_next_review_row_id"] == (
        "pxr_review_d603772038dff21e"
    )
    assert summary["product_scope_pxr_exact_review_next_review_candidate_name"] == "acetaminophen"
    assert summary["product_scope_pxr_exact_review_next_review_operator_review_artifact"] == (
        "runs/pxr_exact_evidence_review_intake_template_current.csv"
    )
    assert summary["product_scope_pxr_exact_review_next_review_completion_packet"][
        "candidate_name"
    ] == "acetaminophen"
    assert summary[
        "product_scope_pxr_exact_review_next_review_return_bundle_required_artifact_count"
    ] == 5
    assert summary["product_scope_pxr_exact_review_next_review_return_bundle_blocker_count"] == 1
    assert summary[
        "product_scope_pxr_exact_review_next_review_return_bundle_next_artifact_id"
    ] == "operator_review_row"
    assert "exact human NR1I2/PXR" in summary["product_scope_pxr_exact_review_next_required_step"]
    assert summary["product_scope_pxr_source_modality_triage_ready"] is True
    assert summary["product_scope_pxr_source_modality_triage_artifact"] == (
        "runs/pxr_source_modality_triage_current.json"
    )
    assert summary[
        "product_scope_pxr_source_modality_activity_proxy_or_conflict_surrogate_row_count"
    ] == 3
    assert summary[
        "product_scope_pxr_source_modality_direct_or_claim_safe_quantitative_ready_count"
    ] == 0
    assert summary["product_scope_pxr_source_modality_direct_replacement_apply_draft_ready"] is True
    assert (
        summary["product_scope_pxr_source_modality_direct_replacement_apply_draft_overlay_row_count"]
        == 6
    )
    assert (
        summary[
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_ready_for_apply_row_count_after_draft"
        ]
        == 14
    )
    assert (
        summary["product_scope_pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_after_draft"]
        == 0
    )
    assert (
        summary["product_scope_pxr_source_modality_direct_replacement_apply_draft_authoritative_fields_touched"]
        is False
    )
    assert summary["product_scope_pxr_source_modality_next_review_candidate_name"] == "acetaminophen"
    assert summary["product_scope_pxr_source_modality_next_review_source_modality"] == (
        "activity_proxy_or_conflict_surrogate"
    )
    assert "build_residual_force_gpu_worker_return_receipt.py" in summary["next_command"]
    assert summary["next_command_candidate_count"] == 2
    assert summary["next_command_candidates"][0] == "python3 tools/verify_primary.py"
    assert "build_residual_force_gpu_worker_return_receipt.py" in summary["next_command_candidates"][1]
    assert "build_residual_force_derivation_validation.py" in by_id["R6_product_ai_architecture_gap_closure"][
        "next_command"
    ]
    assert by_id["R6_product_ai_architecture_gap_closure"]["next_command"] == summary["next_command"]
    assert "gpu_worker_return_operator_verified_true_count=0" in by_id["R6_product_ai_architecture_gap_closure"]["observed"]
    assert "gpu_worker_return_queue_fingerprints=768" in by_id["R6_product_ai_architecture_gap_closure"]["observed"]


def test_product_goal_completion_audit_passes_with_scope_deferred_backlog_only() -> None:
    payload = mod.build_product_goal_completion_audit(
        architecture_packet=_architecture(release_ready=True, commercial_ready=True),
        release_dossier_packet=_release_dossier(release_ready=True, commercial_ready=True),
        public_benchmark_packet=_public_benchmark(),
        commercial_independence_packet=_commercial(ready=True),
        license_work_order_packet=_license_work_order(ready=True),
        cameo_architecture_packet=_cameo(),
        release_gate_packet=_release_gate(ready=True),
        bottleneck_packet={"summary": {"approval_tokens_required": []}},
        burndown_packet={"summary": {}, "rows": []},
        product_ai_architecture_gap_packet=_ai_gap(),
        product_ai_execution_backlog_packet={
            "summary": {
                "status": "product_ai_architecture_execution_backlog_clear",
                "backlog_clear": True,
                "work_item_count": 12,
                "release_blocking_work_item_count": 0,
                "scope_deferred_work_item_count": 12,
                "primary_work_item_id": "scope_breadth.transporter.AQP1.core_non_binder_01",
            },
            "rows": [],
        },
    )

    summary = payload["summary"]
    by_id = {row["requirement_id"]: row for row in payload["rows"]}
    assert summary["goal_complete"] is True
    assert summary["product_ai_optional_lane_ready"] is True
    assert summary["product_ai_scope_deferred_work_item_count"] == 12
    assert summary["optional_requirement_fail_count"] == 0
    assert by_id["R6_product_ai_architecture_gap_closure"]["status"] == "pass"


def test_product_goal_completion_audit_passes_when_all_evidence_is_ready() -> None:
    payload = mod.build_product_goal_completion_audit(
        architecture_packet=_architecture(release_ready=True, commercial_ready=True),
        release_dossier_packet=_release_dossier(release_ready=True, commercial_ready=True),
        public_benchmark_packet=_public_benchmark(),
        commercial_independence_packet=_commercial(ready=True),
        license_work_order_packet=_license_work_order(ready=True),
        cameo_architecture_packet=_cameo(),
        release_gate_packet=_release_gate(ready=True),
        bottleneck_packet={"summary": {"approval_tokens_required": []}},
        burndown_packet={"summary": {}, "rows": []},
        product_ai_architecture_gap_packet=_ai_gap(),
        product_ai_execution_backlog_packet=_ai_backlog(),
    )

    assert payload["summary"]["status"] == "product_goal_completion_audit_pass"
    assert payload["summary"]["goal_complete"] is True
    assert payload["summary"]["restricted_delivery_complete"] is True
    assert payload["summary"]["pass_count"] == 7
    assert payload["summary"]["fail_count"] == 0
    assert payload["summary"]["next_command_candidate_count"] == 0
    assert all(row["status"] == "pass" for row in payload["rows"])


def test_build_product_goal_completion_audit_tool_writes_outputs(tmp_path: Path) -> None:
    paths = {
        "architecture": tmp_path / "architecture.json",
        "release_dossier": tmp_path / "release_dossier.json",
        "public_benchmark": tmp_path / "public_benchmark.json",
        "commercial": tmp_path / "commercial.json",
        "license_work_order": tmp_path / "license_work_order.json",
        "cameo": tmp_path / "cameo.json",
        "release_gate": tmp_path / "release_gate.json",
        "bottleneck": tmp_path / "bottleneck.json",
        "burndown": tmp_path / "burndown.json",
        "ai_gap": tmp_path / "ai_gap.json",
        "ai_backlog": tmp_path / "ai_backlog.json",
    }
    payloads = {
        "architecture": _architecture(),
        "release_dossier": _release_dossier(),
        "public_benchmark": _public_benchmark(),
        "commercial": _commercial(),
        "license_work_order": _license_work_order(),
        "cameo": _cameo(),
        "release_gate": _release_gate(),
        "bottleneck": _bottleneck(),
        "burndown": _burndown(),
        "ai_gap": _ai_gap(),
        "ai_backlog": _ai_backlog(),
    }
    for key, path in paths.items():
        path.write_text(json.dumps(payloads[key]) + "\n", encoding="utf-8")
    out_json = tmp_path / "audit.json"
    out_csv = tmp_path / "audit.csv"
    out_md = tmp_path / "audit.md"

    mod.main(
        [
            "--architecture-json",
            str(paths["architecture"]),
            "--release-dossier-json",
            str(paths["release_dossier"]),
            "--public-benchmark-json",
            str(paths["public_benchmark"]),
            "--commercial-independence-json",
            str(paths["commercial"]),
            "--license-work-order-json",
            str(paths["license_work_order"]),
            "--cameo-architecture-json",
            str(paths["cameo"]),
            "--release-gate-json",
            str(paths["release_gate"]),
            "--bottleneck-json",
            str(paths["bottleneck"]),
            "--burndown-json",
            str(paths["burndown"]),
            "--product-ai-architecture-gap-json",
            str(paths["ai_gap"]),
            "--product-ai-execution-backlog-json",
            str(paths["ai_backlog"]),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "blocked_product_goal_completion_audit"
    assert out_csv.read_text(encoding="utf-8").startswith("requirement_id,requirement,status,")
    md_text = out_md.read_text(encoding="utf-8")
    assert "Product Goal Completion Audit" in md_text
    assert "Next Command Candidates" in md_text
    assert "Commercial Readiness Next Actions" in md_text
    assert "production_ai_return_summary" in md_text
