from __future__ import annotations

import json
from pathlib import Path

from betelgeuze_product.production_ai_checkpoint_readiness import (
    build_product_production_ai_checkpoint_readiness,
)
from tools import build_product_production_ai_checkpoint_readiness as cli


def _packet(summary: dict[str, object]) -> dict[str, object]:
    return {"summary": summary}


def test_production_ai_checkpoint_readiness_blocks_customer_facing_inference() -> None:
    payload = build_product_production_ai_checkpoint_readiness(
        registry_packet=_packet(
            {
                "product_model_layer_ready": True,
                "default_residual_mode": "shadow",
                "production_promotion_allowed": False,
                "customer_facing_auto_correction_allowed": False,
                "customer_facing_score_mutation_allowed": False,
                "customer_facing_ranking_mutation_allowed": False,
                "trained_model_checkpoint_count": 0,
                "checkpoint_missing_output_fields": ["delta_force"],
                "checkpoint_missing_adapter_output_policy_fields": ["delta_force"],
                "selected_sidecar_ready": False,
                "selected_sidecar_status": "blocked_residual_production_checkpoint_sidecar",
                "selected_sidecar_blockers": ["force_gpu_return_receipt_ready"],
                "selected_sidecar_missing_output_fields": ["delta_force"],
                "selected_sidecar_training_contract_ready": False,
                "selected_sidecar_training_contract_missing_label_fields": ["delta_force"],
                "selected_sidecar_force_receipt_ready": False,
                "selected_sidecar_force_receipt_operator_verified": False,
                "selected_sidecar_force_receipt_operator_verified_true_count": 0,
                "selected_sidecar_force_receipt_expected_queue_rows": 768,
            }
        ),
        checkpoint_work_order_packet=_packet(
            {
                "checkpoint_preflight_ready": False,
                "candidate_checkpoint_count": 1460,
                "ready_checkpoint_count": 0,
                "checkpoint_closure_blockers": ["force_gpu_return_receipt_not_ready"],
                "next_required_step": "Return GPU force receipt.",
            }
        ),
        training_data_packet=_packet(
            {
                "production_training_data_ready": False,
                "failed_check_ids": ["production_delta_force_label_evidence"],
                "dataset_missing_output_labels": ["delta_force"],
            }
        ),
        output_head_gap_contract_packet=_packet(
            {
                "output_head_gap_contract_ready": True,
                "production_output_heads_complete": False,
                "required_output_field_count": 7,
                "ready_output_field_count": 6,
                "blocked_output_field_count": 1,
                "blocked_output_fields": ["delta_force"],
                "first_blocked_output_field": "delta_force",
                "first_blocked_output_field_blockers": [
                    "training_label_missing_or_not_ready",
                    "score_model_output_missing",
                    "sidecar_payload_output_missing",
                ],
            }
        ),
        force_gpu_worker_return_receipt_packet=_packet(
            {
                "gpu_worker_return_receipt_ready": False,
                "blockers": ["full_regeneration_manifest_complete"],
                "full_regeneration_summary_manifest_bound": False,
                "full_regeneration_summary_out_manifest_csv_bound": False,
                "full_regeneration_summary_out_summary_json_bound": False,
                "full_regeneration_summary_manifest_row_counts_consistent": False,
                "summary_manifest_csv": "",
                "summary_out_manifest_csv": "",
                "summary_out_summary_json": "",
                "expected_queue_rows": 768,
                "expected_npz_count": 768,
                "queue_id_count": 768,
                "queue_fingerprint_count": 768,
                "manifest_row_count": 0,
                "manifest_ok_row_count": 0,
                "manifest_identity_row_count": 0,
                "manifest_matched_queue_id_count": 0,
                "manifest_matched_expected_npz_count": 0,
                "manifest_matched_queue_fingerprint_count": 0,
                "full_regeneration_manifest_operator_verified": False,
                "manifest_operator_verified_true_count": 0,
                "queue_manifest_identity_coverage_ready": False,
            }
        ),
        force_gpu_worker_handoff_packet={
            "summary": {
                "gpu_worker_handoff_ready": True,
                "gpu_worker_handoff_required": True,
                "operator_action_required": True,
                "operator_transfer_manifest_ready": True,
                "operator_transfer_outbound_artifact_count": 9,
                "operator_transfer_outbound_artifacts": [
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
                "operator_transfer_inbound_artifact_count": 4,
                "operator_transfer_inbound_artifacts": [
                    "runs/residual_force_trajectory_regeneration_current_summary.json",
                    "runs/residual_force_trajectory_regeneration_current_manifest.csv",
                    "regenerated NPZ bundles referenced by returned manifest NPZ path columns",
                    "runs/residual_force_trajectory_regeneration_execution_probe_current.json after rerun on the returned pilot/full run evidence",
                ],
                "operator_transfer_first_return_artifact": (
                    "runs/residual_force_trajectory_regeneration_current_summary.json"
                ),
                "operator_transfer_return_manifest_artifact": (
                    "runs/residual_force_trajectory_regeneration_current_manifest.csv"
                ),
                "operator_transfer_acceptance_artifact": (
                    "runs/residual_force_gpu_worker_return_receipt_current.json"
                ),
                "operator_transfer_acceptance_ready_key": "gpu_worker_return_receipt_ready",
                "operator_transfer_post_return_validation_command": (
                    "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
                ),
                "return_summary_template_payload_json": (
                    "runs/residual_force_trajectory_regeneration_current_summary_template.json"
                ),
                "full_regeneration_command": "python3 tools/generate_ligand_trajectory_engine.py --prod-mode",
                "post_return_output_contract_ready": True,
                "post_return_required_production_output_fields": [
                    "delta_score",
                    "corrected_score",
                    "delta_energy",
                    "delta_force",
                    "uncertainty",
                    "abstention_reason",
                    "stage2_route_decision",
                ],
                "post_return_gpu_unlock_output_fields": [
                    "delta_force",
                    "uncertainty",
                    "abstention_reason",
                    "stage2_route_decision",
                ],
                "post_return_gpu_unlock_artifacts": [
                    "runs/residual_force_gpu_worker_return_receipt_current.json",
                    "runs/residual_production_training_data_contract_current.json",
                ],
                "post_return_min_expected_label_rows": 768,
                "post_return_promotion_ladder_ready": True,
                "post_return_promotion_ladder": [
                    {"stage_id": "gpu_return_receipt"},
                    {"stage_id": "product_goal_completion_audit"},
                ],
                "post_return_promotion_ladder_ready_keys": [
                    "runs/residual_force_gpu_worker_return_receipt_current.json::gpu_worker_return_receipt_ready=True",
                    "runs/product_goal_completion_audit_current.json::goal_complete=True",
                ],
                "post_run_validation_commands": [
                    "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
                    "python3 tools/build_product_goal_completion_audit.py",
                ],
            },
            "rows": [
                {
                    "step_id": "run_post_regeneration_validation_chain",
                    "command": "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
                }
            ],
        },
        gpu_return_intake_packet=_packet(
            {
                "operator_return_next_artifact_completion_packet": {
                    "artifact_id": "returned_summary_json",
                    "artifact_path": "runs/residual_force_trajectory_regeneration_current_summary.json",
                    "packet_ready": True,
                    "template_payload_json": "runs/residual_force_trajectory_regeneration_current_summary_template.json",
                    "expected_queue_rows": 768,
                    "actual_summary_return_path": "runs/residual_force_trajectory_regeneration_current_summary.json",
                    "actual_manifest_return_path": "runs/residual_force_trajectory_regeneration_current_manifest.csv",
                    "required_fields_or_columns": [
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
                    "failed_check_ids": [
                        "actual_summary_returned_complete",
                        "actual_summary_manifest_bound",
                    ],
                    "validation_command": "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
                    "full_regeneration_command": "python3 tools/generate_ligand_trajectory_engine.py --prod-mode",
                    "completion_rule": "queue_rows equals expected_queue_rows; processed_rows>=expected_queue_rows",
                    "backend_provenance_completion_rule": "prod_mode=true; require_rust_hip=true",
                    "next_action": "Return the completed GPU summary JSON with template fields.",
                }
            }
        ),
        rocm_environment_packet=_packet(
            {
                "status": "blocked_rocm_environment_manifest",
                "manifest_ready": False,
                "rocm_stack_detected": True,
                "torch_rocm_ready": False,
                "amd_gpu_detected": False,
                "visible_device_count": 0,
                "device_names": [],
                "torch_version": "2.6.0+rocm6.1",
                "torch_hip_version": "6.1.40091-a8dbc0c19",
                "gpu_visibility_diagnostic_packet_ready": True,
                "gpu_visibility_diagnostic_commands": [
                    "python3 tools/build_rocm_environment_manifest.py",
                    "rocminfo",
                    "rocm-smi --showproductname --showdriverversion --showmeminfo vram",
                    "hipcc --version",
                    "python3 -c \"import torch; print(torch.cuda.device_count())\"",
                ],
                "gpu_visibility_diagnostic_required_fields": [
                    "manifest_ready",
                    "rocm_stack_detected",
                    "torch_rocm_ready",
                    "amd_gpu_detected",
                    "visible_device_count",
                    "device_names",
                    "torch_version",
                    "torch_hip_version",
                ],
                "gpu_visibility_diagnostic_completion_rule": (
                    "manifest_ready=true; rocm_stack_detected=true; torch_rocm_ready=true; "
                    "amd_gpu_detected=true; visible_device_count>0; device_names nonempty"
                ),
                "gpu_visibility_diagnostic_return_artifacts": [
                    "runs/rocm_environment_manifest_current.json",
                    "runs/rocm_environment_manifest_current.md",
                ],
                "gpu_visibility_torch_probe_command": (
                    "python3 -c \"import torch; print(torch.cuda.device_count())\""
                ),
                "next_required_step": "Expose a supported AMD ROCm/HIP runtime.",
            }
        ),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_production_ai_checkpoint_readiness"
    assert summary["production_ai_checkpoint_ready"] is False
    assert summary["production_ai_inference_subject_active"] is False
    assert summary["check_count"] == 8
    assert summary["fail_check_count"] == 7
    assert "force_gpu_worker_return_receipt_ready" in summary["failed_check_ids"]
    assert "production_gpu_execution_environment_ready" in summary["failed_check_ids"]
    assert "production_output_heads_complete" in summary["failed_check_ids"]
    assert summary["first_failed_check_id"] == "registry_customer_facing_promotion_allowed"
    assert summary["first_failed_source_artifact"] == "runs/residual_model_registry_current.json"
    assert "default_residual_mode=shadow" in summary["first_failed_observed"]
    assert "production promotion" in summary["first_failed_required"]
    assert "Keep customer-facing mutation disabled" in summary["first_failed_next_action"]
    receipt_row = next(row for row in payload["rows"] if row["check_id"] == "force_gpu_worker_return_receipt_ready")
    assert "blockers=full_regeneration_manifest_complete" in receipt_row["observed"]
    assert "summary_manifest_bound=False" in receipt_row["observed"]
    assert "summary_out_manifest_csv_bound=False" in receipt_row["observed"]
    assert "summary_out_summary_json_bound=False" in receipt_row["observed"]
    assert "summary_manifest_row_counts_consistent=False" in receipt_row["observed"]
    assert summary["candidate_checkpoint_count"] == 1460
    assert summary["gpu_receipt_expected_queue_rows"] == 768
    assert summary["gpu_receipt_summary_manifest_bound"] is False
    assert summary["gpu_receipt_summary_out_manifest_csv_bound"] is False
    assert summary["gpu_receipt_summary_out_summary_json_bound"] is False
    assert summary["gpu_receipt_summary_manifest_row_counts_consistent"] is False
    assert summary["gpu_receipt_summary_manifest_csv"] == ""
    assert summary["gpu_receipt_summary_out_manifest_csv"] == ""
    assert summary["gpu_receipt_summary_out_summary_json"] == ""
    assert summary["force_gpu_worker_handoff_ready"] is True
    assert summary["production_output_head_gap_contract_ready"] is True
    assert summary["production_output_heads_complete"] is False
    assert summary["production_output_head_ready_field_count"] == 6
    assert summary["production_output_head_blocked_field_count"] == 1
    assert summary["production_output_head_blocked_fields"] == ["delta_force"]
    assert summary["production_output_head_first_blocked_field"] == "delta_force"
    assert summary["production_gpu_execution_environment_ready"] is False
    assert summary["production_gpu_execution_environment_status"] == "blocked_rocm_environment_manifest"
    assert summary["production_gpu_execution_environment_artifact_path"] == "runs/rocm_environment_manifest_current.json"
    assert summary["production_gpu_rocm_stack_detected"] is True
    assert summary["production_gpu_rocm_torch_ready"] is False
    assert summary["production_gpu_rocm_visible_device_count"] == 0
    assert summary["production_gpu_rocm_torch_version"] == "2.6.0+rocm6.1"
    assert summary["production_gpu_rocm_visibility_diagnostic_packet_ready"] is True
    assert summary["production_gpu_rocm_visibility_diagnostic_command_count"] == 5
    assert "rocminfo" in summary["production_gpu_rocm_visibility_diagnostic_commands"]
    assert "torch_version" in summary["production_gpu_rocm_visibility_diagnostic_required_fields"]
    assert "visible_device_count>0" in summary[
        "production_gpu_rocm_visibility_diagnostic_completion_rule"
    ]
    assert "runs/rocm_environment_manifest_current.json" in summary[
        "production_gpu_rocm_visibility_diagnostic_return_artifacts"
    ]
    assert summary["production_gpu_rocm_visibility_torch_probe_command"].startswith("python3 -c")
    assert "Expose a supported AMD ROCm/HIP runtime" in summary["production_gpu_rocm_next_required_step"]
    assert summary["force_gpu_worker_operator_action_required"] is True
    assert summary["force_gpu_worker_operator_transfer_manifest_ready"] is True
    assert summary["force_gpu_worker_operator_transfer_outbound_artifact_count"] == 9
    assert "tools/generate_ligand_trajectory_engine.py" in summary[
        "force_gpu_worker_operator_transfer_outbound_artifacts"
    ]
    assert summary["force_gpu_worker_operator_transfer_inbound_artifact_count"] == 4
    assert summary["force_gpu_worker_operator_transfer_first_return_artifact"] == (
        "runs/residual_force_trajectory_regeneration_current_summary.json"
    )
    assert summary["force_gpu_worker_operator_transfer_acceptance_artifact"] == (
        "runs/residual_force_gpu_worker_return_receipt_current.json"
    )
    assert summary["force_gpu_worker_operator_transfer_acceptance_ready_key"] == (
        "gpu_worker_return_receipt_ready"
    )
    assert summary["force_gpu_worker_return_summary_template_payload_json"] == (
        "runs/residual_force_trajectory_regeneration_current_summary_template.json"
    )
    assert "generate_ligand_trajectory_engine.py" in summary["force_gpu_worker_full_regeneration_command"]
    assert "build_residual_force_gpu_worker_return_receipt.py" in summary[
        "force_gpu_worker_post_return_validation_command"
    ]
    assert summary["force_gpu_worker_post_return_unlock_output_fields"] == [
        "delta_force",
        "uncertainty",
        "abstention_reason",
        "stage2_route_decision",
    ]
    assert summary["force_gpu_worker_post_return_min_expected_label_rows"] == 768
    assert summary["force_gpu_worker_post_return_promotion_ladder_ready"] is True
    assert summary["force_gpu_worker_post_return_promotion_ladder_contract_ready"] is True
    assert summary["force_gpu_worker_post_return_promotion_ladder_currently_satisfied"] is False
    assert summary["force_gpu_worker_post_return_promotion_ladder_current_blocked_stage_count"] == 8
    assert summary["force_gpu_worker_post_return_promotion_ladder_current_blocked_stage_ids"][0] == (
        "production_gpu_execution_environment_acceptance"
    )
    assert summary["force_gpu_worker_post_return_promotion_ladder_current_next_stage_id"] == (
        "production_gpu_execution_environment_acceptance"
    )
    assert summary["force_gpu_worker_post_return_promotion_ladder_current_next_stage_artifact"] == (
        "runs/rocm_environment_manifest_current.json"
    )
    assert summary["force_gpu_worker_post_return_promotion_ladder_current_next_stage_validation_command"] == (
        "python3 tools/build_rocm_environment_manifest.py"
    )
    assert summary["force_gpu_worker_post_return_promotion_ladder_stage_count"] == 2
    assert summary["force_gpu_worker_post_return_promotion_ladder_stage_ids"] == [
        "gpu_return_receipt",
        "product_goal_completion_audit",
    ]
    assert summary["force_gpu_worker_post_run_validation_commands"] == [
        "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
        "python3 tools/build_product_goal_completion_audit.py",
    ]
    assert summary["production_inference_acceptance_matrix_ready"] is True
    assert summary["production_inference_acceptance_stage_count"] == 8
    assert summary["production_inference_acceptance_ready_stage_count"] == 0
    assert summary["production_inference_acceptance_blocked_stage_count"] == 8
    assert summary["production_inference_acceptance_blocked_stage_ids"][0] == (
        "production_gpu_execution_environment_acceptance"
    )
    assert summary["production_inference_acceptance_next_stage_id"] == (
        "production_gpu_execution_environment_acceptance"
    )
    assert summary["production_inference_acceptance_next_stage_artifact"] == (
        "runs/rocm_environment_manifest_current.json"
    )
    assert summary["production_inference_acceptance_next_stage_validation_command"] == (
        "python3 tools/build_rocm_environment_manifest.py"
    )
    assert summary["production_inference_acceptance_next_stage_unlock_fields"] == [
        "manifest_ready",
        "rocm_stack_detected",
        "torch_rocm_ready",
        "amd_gpu_detected",
        "visible_device_count",
    ]
    assert summary["production_inference_acceptance_next_stage_required_checks"] == [
        "production_gpu_execution_environment_ready"
    ]
    assert summary["production_inference_actionable_blocker_stage_id"] == (
        "production_gpu_execution_environment_acceptance"
    )
    assert summary["production_inference_actionable_blocker_check_id"] == "production_gpu_execution_environment_ready"
    assert summary["production_inference_actionable_blocker_artifact"] == (
        "runs/rocm_environment_manifest_current.json"
    )
    assert "visible_device_count=0" in summary[
        "production_inference_actionable_blocker_observed"
    ]
    assert "ROCm/HIP runtime is ready" in summary[
        "production_inference_actionable_blocker_required"
    ]
    assert "Expose a visible ROCm/HIP AMD GPU device" in summary[
        "production_inference_actionable_blocker_next_action"
    ]
    assert summary["production_inference_actionable_blocker_validation_command"] == (
        "python3 tools/build_rocm_environment_manifest.py"
    )
    assert summary["production_inference_actionable_blocker_unlock_fields"] == [
        "manifest_ready",
        "rocm_stack_detected",
        "torch_rocm_ready",
        "amd_gpu_detected",
        "visible_device_count",
    ]
    assert summary["production_inference_actionable_blocker_downstream_blocked_stage_count"] == 7
    assert summary["production_inference_next_after_actionable_blocker_stage_id"] == "gpu_return_acceptance"
    assert summary["production_inference_next_after_actionable_blocker_artifact"] == (
        "runs/residual_force_gpu_worker_return_receipt_current.json"
    )
    assert summary["production_inference_next_after_actionable_blocker_validation_command"] == (
        "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
    )
    assert summary["production_inference_next_after_actionable_blocker_required_checks"] == [
        "force_gpu_worker_return_receipt_ready"
    ]
    assert summary["production_inference_next_after_actionable_blocker_unlock_fields"] == [
        "delta_force",
        "uncertainty",
        "abstention_reason",
        "stage2_route_decision",
    ]
    assert "Return full regeneration summary/manifest" in summary[
        "production_inference_next_after_actionable_blocker_next_action"
    ]
    assert summary["production_inference_actionable_blocker_blocks_registry_promotion"] is True
    assert summary["production_inference_actionable_operator_completion_packet_ready"] is True
    assert summary["production_inference_actionable_operator_completion_packet_artifact"] == (
        "runs/rocm_environment_manifest_current.json"
    )
    assert summary["production_inference_actionable_operator_completion_artifact_id"] == (
        "rocm_environment_manifest_json"
    )
    assert summary["production_inference_actionable_operator_completion_artifact_path"] == (
        "runs/rocm_environment_manifest_current.json"
    )
    assert summary["production_inference_actionable_operator_completion_expected_queue_rows"] == 0
    assert summary["production_inference_actionable_operator_completion_required_fields_or_columns"] == [
        "manifest_ready",
        "rocm_stack_detected",
        "torch_rocm_ready",
        "amd_gpu_detected",
        "visible_device_count",
    ]
    assert summary["production_inference_actionable_operator_completion_diagnostic_command_count"] == 5
    assert "hipcc --version" in summary[
        "production_inference_actionable_operator_completion_diagnostic_commands"
    ]
    assert "device_names" in summary[
        "production_inference_actionable_operator_completion_diagnostic_required_fields"
    ]
    assert summary[
        "production_inference_actionable_operator_completion_diagnostic_required_field_count"
    ] == 8
    assert "device_names nonempty" in summary[
        "production_inference_actionable_operator_completion_diagnostic_completion_rule"
    ]
    assert "runs/rocm_environment_manifest_current.md" in summary[
        "production_inference_actionable_operator_completion_diagnostic_return_artifacts"
    ]
    assert summary[
        "production_inference_actionable_operator_completion_torch_visibility_probe_command"
    ].startswith("python3 -c")
    assert summary["production_inference_actionable_operator_completion_failed_check_ids"] == []
    assert summary["production_inference_actionable_operator_completion_template_payload_json"] == ""
    assert summary["production_inference_actionable_operator_completion_validation_command"] == (
        "python3 tools/build_rocm_environment_manifest.py"
    )
    assert "visible_device_count>0" in summary[
        "production_inference_actionable_operator_completion_completion_rule"
    ]
    assert summary["production_inference_actionable_operator_completion_backend_provenance_completion_rule"] == ""
    assert summary["production_inference_worker_runtime_receipt_contract_ready"] is True
    assert summary["production_inference_worker_runtime_receipt_required_field_count"] == 11
    assert summary["production_inference_worker_runtime_receipt_required_fields_or_columns"] == [
        "manifest_ready",
        "rocm_stack_detected",
        "torch_rocm_ready",
        "amd_gpu_detected",
        "visible_device_count",
        "device_names",
        "torch_version",
        "torch_hip_version",
        "prod_mode",
        "require_rust_hip",
        "backend_counts",
    ]
    assert "prod_mode=true" in summary["production_inference_worker_runtime_receipt_completion_rule"]
    assert "require_rust_hip=true" in summary["production_inference_worker_runtime_receipt_completion_rule"]
    assert summary["production_inference_worker_runtime_receipt_post_environment_next_stage_id"] == (
        "gpu_return_acceptance"
    )
    assert summary["production_inference_worker_runtime_receipt_post_environment_next_artifact"] == (
        "runs/residual_force_gpu_worker_return_receipt_current.json"
    )
    assert summary["production_inference_worker_runtime_receipt_post_environment_validation_command"] == (
        "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
    )
    assert summary["production_inference_worker_runtime_receipt_full_regeneration_command"] == (
        "python3 tools/generate_ligand_trajectory_engine.py --prod-mode"
    )
    assert "cpu_fallback_does_not_satisfy_production_inference" in summary[
        "production_inference_worker_runtime_receipt_guardrails"
    ]
    runtime_contract = summary["production_inference_actionable_operator_completion_packet"][
        "worker_runtime_receipt_contract"
    ]
    assert runtime_contract["post_environment_next_stage_id"] == "gpu_return_acceptance"
    assert "backend_counts" in runtime_contract["required_fields_or_columns"]
    assert summary["production_inference_actionable_operator_completion_packet"]["artifact_id"] == (
        "rocm_environment_manifest_json"
    )
    assert summary["production_inference_actionable_operator_completion_packet"][
        "diagnostic_command_count"
    ] == 5
    assert len(payload["production_inference_acceptance_matrix"]) == 8
    assert summary["force_gpu_worker_post_return_gpu_unlock_artifacts"] == [
        "runs/residual_force_gpu_worker_return_receipt_current.json",
        "runs/residual_production_training_data_contract_current.json",
    ]
    assert summary["gpu_receipt_queue_id_count"] == 768
    assert summary["gpu_receipt_queue_fingerprint_count"] == 768
    assert summary["gpu_receipt_expected_npz_count"] == 768
    assert summary["gpu_receipt_manifest_identity_row_count"] == 0
    assert summary["gpu_receipt_manifest_matched_queue_id_count"] == 0
    assert summary["training_data_missing_output_labels"] == ["delta_force"]
    assert "production_gpu_execution_environment_not_ready" in summary["checkpoint_closure_blockers"]
    assert all(row["execution_enabled"] is False for row in payload["rows"])
    assert payload["blockers"]


def test_production_ai_checkpoint_readiness_ready_when_all_gates_pass() -> None:
    payload = build_product_production_ai_checkpoint_readiness(
        registry_packet=_packet(
            {
                "product_model_layer_ready": True,
                "default_residual_mode": "production_guarded",
                "production_promotion_allowed": True,
                "customer_facing_auto_correction_allowed": True,
                "customer_facing_score_mutation_allowed": True,
                "customer_facing_ranking_mutation_allowed": True,
                "trained_model_checkpoint_count": 1,
                "selected_sidecar_ready": True,
                "selected_sidecar_training_contract_ready": True,
                "selected_sidecar_force_receipt_ready": True,
            }
        ),
        checkpoint_work_order_packet=_packet({"checkpoint_preflight_ready": True, "ready_checkpoint_count": 1}),
        training_data_packet=_packet(
            {
                "production_training_data_ready": True,
                "delta_force_label_evidence_ready": True,
            }
        ),
        output_head_gap_contract_packet=_packet(
            {
                "output_head_gap_contract_ready": True,
                "production_output_heads_complete": True,
                "required_output_field_count": 7,
                "ready_output_field_count": 7,
                "blocked_output_field_count": 0,
                "blocked_output_fields": [],
            }
        ),
        force_gpu_worker_return_receipt_packet=_packet({"gpu_worker_return_receipt_ready": True}),
        rocm_environment_packet=_packet(
            {
                "status": "rocm_environment_manifest_ready",
                "manifest_ready": True,
                "rocm_stack_detected": True,
                "torch_rocm_ready": True,
                "amd_gpu_detected": True,
                "visible_device_count": 1,
                "device_names": ["AMD Radeon RX 7900 XTX"],
            }
        ),
    )

    assert payload["summary"]["status"] == "product_production_ai_checkpoint_readiness_ready"
    assert payload["summary"]["production_ai_checkpoint_ready"] is True
    assert payload["summary"]["production_ai_inference_subject_active"] is True
    assert payload["summary"]["fail_check_count"] == 0
    assert payload["summary"]["production_inference_acceptance_matrix_ready"] is True
    assert payload["summary"]["production_gpu_execution_environment_ready"] is True
    assert payload["summary"]["production_inference_acceptance_stage_count"] == 8
    assert payload["summary"]["production_inference_acceptance_blocked_stage_count"] == 0
    assert payload["summary"]["production_inference_acceptance_next_stage_id"] == ""
    assert payload["summary"]["production_inference_actionable_blocker_stage_id"] == ""
    assert payload["summary"]["production_inference_actionable_operator_completion_packet_ready"] is False
    assert payload["summary"]["production_inference_worker_runtime_receipt_contract_ready"] is False
    assert payload["summary"]["production_inference_actionable_blocker_downstream_blocked_stage_count"] == 0
    assert payload["summary"]["production_inference_next_after_actionable_blocker_stage_id"] == ""
    assert payload["summary"]["production_inference_actionable_blocker_blocks_registry_promotion"] is False
    assert payload["summary"]["first_failed_check_id"] == ""
    assert payload["summary"]["first_failed_source_artifact"] == ""


def test_force_derivation_acceptance_ready_when_delta_force_evidence_ready_without_dataset_label() -> None:
    payload = build_product_production_ai_checkpoint_readiness(
        registry_packet=_packet({"product_model_layer_ready": True, "trained_model_checkpoint_count": 1}),
        checkpoint_work_order_packet=_packet({"checkpoint_preflight_ready": True, "ready_checkpoint_count": 1}),
        training_data_packet=_packet(
            {
                "production_training_data_ready": True,
                "dataset_missing_output_labels": ["delta_force"],
                "delta_force_label_evidence_ready": True,
            }
        ),
        output_head_gap_contract_packet=_packet(
            {"output_head_gap_contract_ready": True, "production_output_heads_complete": True}
        ),
        force_gpu_worker_return_receipt_packet=_packet({"gpu_worker_return_receipt_ready": True}),
        rocm_environment_packet=_packet(
            {
                "manifest_ready": True,
                "rocm_stack_detected": True,
                "torch_rocm_ready": True,
                "amd_gpu_detected": True,
                "visible_device_count": 1,
            }
        ),
    )

    force_derivation = next(
        row
        for row in payload["production_inference_acceptance_matrix"]
        if row["stage_id"] == "force_derivation_acceptance"
    )
    assert force_derivation["status"] == "ready"


def test_build_product_production_ai_checkpoint_readiness_tool_writes_outputs(tmp_path: Path) -> None:
    paths = {
        "registry": tmp_path / "registry.json",
        "work": tmp_path / "work.json",
        "training": tmp_path / "training.json",
        "output_head_gap": tmp_path / "output_head_gap.json",
        "receipt": tmp_path / "receipt.json",
        "gpu_return_intake": tmp_path / "gpu_return_intake.json",
        "rocm": tmp_path / "rocm.json",
    }
    paths["registry"].write_text(json.dumps(_packet({"product_model_layer_ready": True})) + "\n", encoding="utf-8")
    paths["work"].write_text(json.dumps(_packet({"checkpoint_preflight_ready": False})) + "\n", encoding="utf-8")
    paths["training"].write_text(json.dumps(_packet({"production_training_data_ready": False})) + "\n", encoding="utf-8")
    paths["output_head_gap"].write_text(
        json.dumps(_packet({"production_output_heads_complete": False})) + "\n",
        encoding="utf-8",
    )
    paths["receipt"].write_text(json.dumps(_packet({"gpu_worker_return_receipt_ready": False})) + "\n", encoding="utf-8")
    paths["gpu_return_intake"].write_text(
        json.dumps(
            _packet(
                {
                    "operator_return_next_artifact_completion_packet": {
                        "packet_ready": True,
                        "artifact_id": "returned_summary_json",
                    }
                }
            )
        )
        + "\n",
        encoding="utf-8",
    )
    paths["rocm"].write_text(
        json.dumps(
            _packet(
                {
                    "status": "blocked_rocm_environment_manifest",
                    "manifest_ready": False,
                    "rocm_stack_detected": True,
                    "torch_rocm_ready": False,
                    "amd_gpu_detected": False,
                    "visible_device_count": 0,
                }
            )
        )
        + "\n",
        encoding="utf-8",
    )
    out_json = tmp_path / "readiness.json"
    out_csv = tmp_path / "readiness.csv"
    out_md = tmp_path / "readiness.md"

    cli.main(
        [
            "--registry-json",
            str(paths["registry"]),
            "--checkpoint-work-order-json",
            str(paths["work"]),
            "--training-data-json",
            str(paths["training"]),
            "--output-head-gap-contract-json",
            str(paths["output_head_gap"]),
            "--force-gpu-receipt-json",
            str(paths["receipt"]),
            "--gpu-return-intake-json",
            str(paths["gpu_return_intake"]),
            "--rocm-environment-json",
            str(paths["rocm"]),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["packet_type"] == (
        "product_production_ai_checkpoint_readiness"
    )
    assert "force_gpu_worker_return_summary_template_payload_json" in json.loads(
        out_json.read_text(encoding="utf-8")
    )["summary"]
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"][
        "production_inference_acceptance_stage_count"
    ] == 8
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"][
        "production_inference_actionable_operator_completion_packet_ready"
    ] is True
    assert out_csv.read_text(encoding="utf-8").startswith("check_id,status,")
    assert "Product Production AI Checkpoint Readiness" in out_md.read_text(encoding="utf-8")
    assert "Production Inference Acceptance Matrix" in out_md.read_text(encoding="utf-8")
