from __future__ import annotations

from tools.build_product_production_ai_gpu_return_intake import (
    _read_json,
    build_product_production_ai_gpu_return_intake,
)


def test_product_production_ai_gpu_return_intake_surfaces_operator_return_gap() -> None:
    payload = build_product_production_ai_gpu_return_intake(
        handoff_packet=_read_json("runs/residual_force_gpu_worker_handoff_package_current.json"),
        return_manifest_template_packet=_read_json(
            "runs/residual_force_gpu_worker_return_manifest_template_current.json"
        ),
        return_summary_template_packet=_read_json(
            "runs/residual_force_gpu_worker_return_summary_template_current.json"
        ),
        return_receipt_packet=_read_json("runs/residual_force_gpu_worker_return_receipt_current.json"),
        worker_rocm_manifest_packet=_read_json("runs/rocm_environment_manifest_current.json"),
    )

    summary = payload["summary"]
    assert summary["status"] == "product_production_ai_gpu_return_intake_ready"
    assert summary["gpu_return_intake_ready"] is True
    assert summary["gpu_return_artifacts_ready"] is True
    assert summary["expected_queue_rows"] == 768
    assert summary["operator_return_blocker_count"] == 16
    assert summary["operator_return_bundle_contract_ready"] is True
    assert summary["operator_return_required_artifact_count"] == 5
    assert summary["operator_return_required_artifacts"] == [
        "runs/residual_force_trajectory_regeneration_current_summary.json",
        "runs/residual_force_trajectory_regeneration_current_manifest.csv",
        "regenerated NPZ bundles referenced by the returned manifest",
        "runs/residual_force_derivation_validation_current.json",
        "runs/rocm_environment_manifest_current.json",
    ]
    assert summary["operator_return_artifact_completion_matrix_count"] == 5
    assert summary["operator_return_artifact_completion_blocker_count"] == 4
    assert summary["operator_return_next_artifact_id"] == "returned_summary_json"
    assert summary["operator_return_next_artifact_path"] == (
        "runs/residual_force_trajectory_regeneration_current_summary.json"
    )
    assert summary["operator_return_next_artifact_failed_check_ids"][0] == (
        "actual_summary_returned_complete"
    )
    assert summary["operator_return_next_artifact_completion_packet_ready"] is True
    next_packet = summary["operator_return_next_artifact_completion_packet"]
    assert next_packet["artifact_id"] == "returned_summary_json"
    assert next_packet["artifact_path"] == "runs/residual_force_trajectory_regeneration_current_summary.json"
    assert next_packet["template_payload_json"] == (
        "runs/residual_force_trajectory_regeneration_current_summary_template.json"
    )
    assert next_packet["template_payload"]["queue_rows"] == 768
    assert next_packet["template_payload"]["out_manifest_csv"] == (
        "runs/residual_force_trajectory_regeneration_current_manifest.csv"
    )
    assert next_packet["template_payload"]["prod_mode"] is True
    assert next_packet["template_payload"]["require_rust_hip"] is True
    assert "--prod-mode" in next_packet["full_regeneration_command"]
    assert "processed_rows>=expected_queue_rows" in next_packet["completion_rule"]
    assert "backend_counts has rust_hip*" in next_packet["backend_provenance_completion_rule"]
    assert payload["operator_return_artifact_completion_matrix"][0]["artifact_id"] == (
        "returned_summary_json"
    )
    assert payload["operator_return_artifact_completion_matrix"][0]["failed_check_count"] == 7
    assert payload["operator_return_artifact_completion_matrix"][0]["required_fields_or_columns"] == [
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
    assert payload["operator_return_artifact_completion_blocker_matrix"][0]["artifact_id"] == (
        "returned_summary_json"
    )
    assert payload["operator_return_artifact_completion_matrix"][-1]["artifact_id"] == (
        "worker_rocm_environment_manifest"
    )
    assert payload["operator_return_artifact_completion_matrix"][-1]["failed_check_ids"] == []
    assert payload["operator_return_artifact_completion_matrix"][-1]["required_fields_or_columns"] == [
        "manifest_ready",
        "rocm_stack_detected",
        "torch_rocm_ready",
        "amd_gpu_detected",
        "visible_device_count",
    ]
    assert summary["operator_return_manifest_required_columns"] == [
        "queue_id",
        "expected_regenerated_trajectory_npz",
        "status",
        "operator_verified_npz_exists",
    ]
    assert summary["operator_return_validation_ladder_ready"] is True
    assert summary["operator_return_handoff_binding_ready"] is True
    assert summary["operator_return_handoff_queue_csv"] == (
        "runs/residual_force_trajectory_regeneration_queue_current.csv"
    )
    assert len(summary["operator_return_handoff_queue_csv_sha256"]) == 64
    assert "generate_ligand_trajectory_engine.py" in summary[
        "operator_return_handoff_full_regeneration_command"
    ]
    assert "--prod-mode" in summary["operator_return_handoff_full_regeneration_command"]
    assert summary["operator_return_handoff_return_manifest_schema_contract_ready"] is True
    assert "queue_row_fingerprint" in summary[
        "operator_return_handoff_return_manifest_required_identity_rule"
    ]
    assert "queue_row_fingerprint" in summary[
        "operator_return_handoff_return_manifest_fingerprint_columns"
    ]
    assert "queue_id" in summary["operator_return_handoff_return_manifest_queue_id_columns"]
    assert "expected_regenerated_trajectory_npz" in summary[
        "operator_return_handoff_return_manifest_npz_columns"
    ]
    assert summary["operator_acceptance_matrix_ready"] is True
    assert summary["operator_acceptance_stage_count"] == 5
    assert summary["operator_acceptance_ready_stage_count"] == 2
    assert summary["operator_acceptance_blocked_stage_count"] == 3
    assert summary["operator_acceptance_stage_ids"] == [
        "gpu_return_templates_preflight",
        "returned_summary_acceptance",
        "returned_manifest_npz_acceptance",
        "force_derivation_acceptance",
        "post_return_promotion_chain",
    ]
    assert summary["operator_acceptance_ready_stage_ids"] == [
        "gpu_return_templates_preflight",
        "post_return_promotion_chain",
    ]
    assert summary["operator_acceptance_blocked_stage_ids"][0] == "returned_summary_acceptance"
    assert summary["operator_acceptance_next_stage_id"] == "returned_summary_acceptance"
    assert summary["operator_acceptance_next_stage_artifact"] == (
        "runs/residual_force_trajectory_regeneration_current_summary.json"
    )
    assert summary["operator_acceptance_next_stage_validation_command"] == (
        "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
    )
    assert "summary is complete" in summary["operator_acceptance_next_stage_release_effect"]
    assert summary["operator_acceptance_next_stage_required_checks"] == [
        "actual_summary_returned_complete",
        "actual_summary_manifest_bound",
        "actual_summary_out_manifest_csv_present",
        "actual_summary_out_manifest_csv_bound",
        "actual_summary_out_summary_json_bound",
        "actual_summary_manifest_row_counts_consistent",
        "production_gpu_backend_provenance",
    ]
    assert "summary JSON" in summary["operator_acceptance_next_stage_next_action"]
    assert summary["operator_acceptance_stage_check_matrix_count"] == 5
    assert summary["operator_acceptance_current_blocked_stage_check_matrix_count"] == 3
    assert summary["operator_acceptance_stage_check_matrix"][1]["stage_id"] == "returned_summary_acceptance"
    assert summary["operator_acceptance_stage_check_matrix"][1]["failed_check_ids"][0] == (
        "actual_summary_returned_complete"
    )
    assert summary["operator_acceptance_stage_check_matrix"][1]["failed_checks"][0]["observed"].startswith(
        "summary_present=False"
    )
    assert summary["operator_acceptance_current_blocked_stage_check_matrix"][0]["stage_id"] == (
        "returned_summary_acceptance"
    )
    assert summary["first_failed_check_id"] == "actual_summary_returned_complete"
    assert summary["first_failed_source_artifact"] == "runs/residual_force_trajectory_regeneration_current_summary.json"
    assert "actual returned summary" in summary["first_failed_required"]
    assert "Return runs/residual_force_trajectory_regeneration_current_summary.json" in summary[
        "first_failed_next_action"
    ]
    assert summary["handoff_ready"] is True
    assert summary["operator_action_required"] is False
    assert summary["manifest_template_ready"] is True
    assert summary["manifest_template_row_count"] == 768
    assert summary["manifest_status_placeholder_count"] == 768
    assert summary["manifest_operator_verification_placeholder_count"] == 768
    assert summary["summary_template_ready"] is True
    assert summary["summary_template_csv"] == "runs/residual_force_gpu_worker_return_summary_template_current.csv"
    assert summary["summary_template_payload_json"] == (
        "runs/residual_force_trajectory_regeneration_current_summary_template.json"
    )
    assert summary["summary_template_field_count"] == 10
    assert summary["summary_template_required_fields"] == [
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
    assert "processed_rows>=expected_queue_rows" in summary["summary_template_completion_rule"]
    assert summary["summary_template_backend_provenance_contract_ready"] is True
    assert summary["summary_template_required_backend_provenance_fields"] == [
        "prod_mode",
        "require_rust_hip",
        "backend_counts",
    ]
    assert "backend_counts has rust_hip*" in summary[
        "summary_template_backend_provenance_completion_rule"
    ]
    assert summary["summary_returned"] is False
    assert summary["summary_manifest_bound"] is False
    assert summary["summary_manifest_csv"] == ""
    assert summary["summary_out_manifest_csv_present"] is False
    assert summary["summary_out_manifest_csv"] == ""
    assert summary["summary_out_manifest_csv_bound"] is False
    assert summary["summary_out_summary_json_bound"] is False
    assert summary["summary_out_summary_json"] == ""
    assert summary["summary_manifest_row_counts_consistent"] is False
    assert summary["production_gpu_backend_provenance_ready"] is False
    assert summary["worker_rocm_manifest_artifact"] == "runs/rocm_environment_manifest_current.json"
    assert summary["worker_rocm_manifest_ready"] is True
    assert summary["worker_rocm_stack_detected"] is True
    assert summary["worker_rocm_torch_ready"] is True
    assert summary["worker_rocm_amd_gpu_detected"] is True
    assert summary["worker_rocm_visible_device_count"] == 1
    assert summary["worker_rocm_device_names"] == ["AMD Radeon RX 6900 XT"]
    assert "visible_device_count>0" in summary["worker_rocm_manifest_completion_rule"]
    assert summary["production_gpu_backend_rows"] == 0
    assert summary["production_gpu_backend_non_production_rows"] == 0
    assert summary["production_gpu_backend_prod_mode"] is False
    assert summary["production_gpu_backend_require_rust_hip"] is False
    assert summary["manifest_returned"] is False
    assert summary["manifest_npz_paths_complete"] is False
    assert summary["manifest_npz_files_exist"] is False
    assert summary["manifest_npz_files_valid"] is False
    assert summary["manifest_npz_schema_valid"] is False
    assert summary["manifest_npz_identity_valid"] is False
    assert summary["manifest_npz_path_column_present"] is False
    assert summary["manifest_npz_path_present_count"] == 0
    assert summary["manifest_ok_row_missing_npz_path_count"] == 0
    assert summary["manifest_operator_verified_missing_npz_path_count"] == 0
    assert summary["manifest_npz_file_existing_count"] == 0
    assert summary["manifest_npz_file_missing_count"] == 0
    assert summary["manifest_ok_row_missing_npz_file_count"] == 0
    assert summary["manifest_operator_verified_missing_npz_file_count"] == 0
    assert summary["manifest_npz_file_valid_count"] == 0
    assert summary["manifest_npz_file_invalid_count"] == 0
    assert summary["manifest_ok_row_invalid_npz_file_count"] == 0
    assert summary["manifest_operator_verified_invalid_npz_file_count"] == 0
    assert summary["manifest_npz_schema_valid_count"] == 0
    assert summary["manifest_npz_schema_invalid_count"] == 0
    assert summary["manifest_ok_row_invalid_npz_schema_count"] == 0
    assert summary["manifest_operator_verified_invalid_npz_schema_count"] == 0
    assert summary["manifest_npz_identity_valid_count"] == 0
    assert summary["manifest_npz_identity_invalid_count"] == 0
    assert summary["manifest_ok_row_invalid_npz_identity_count"] == 0
    assert summary["manifest_operator_verified_invalid_npz_identity_count"] == 0
    assert summary["manifest_operator_verified"] is False
    assert summary["identity_coverage_ready"] is False
    assert summary["post_run_derivation_validation_ready"] is False
    assert summary["post_run_validation_command_count"] == 18
    assert summary["post_run_validation_commands"][0] == "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
    assert "python3 tools/build_residual_model_registry.py" in summary["post_run_validation_commands"]
    assert "python3 tools/build_residual_force_gpu_worker_return_receipt.py &&" in summary[
        "post_return_validation_command"
    ]
    assert "actual_summary_returned_complete" in summary["failed_check_ids"]
    assert "actual_summary_manifest_bound" in summary["failed_check_ids"]
    assert "actual_summary_out_manifest_csv_present" in summary["failed_check_ids"]
    assert "actual_summary_out_manifest_csv_bound" in summary["failed_check_ids"]
    assert "actual_summary_out_summary_json_bound" in summary["failed_check_ids"]
    assert "actual_summary_manifest_row_counts_consistent" in summary["failed_check_ids"]
    assert "production_gpu_backend_provenance" in summary["failed_check_ids"]
    assert "actual_manifest_npz_paths_complete" in summary["failed_check_ids"]
    assert "actual_manifest_npz_files_exist" in summary["failed_check_ids"]
    assert "actual_manifest_npz_files_valid" in summary["failed_check_ids"]
    assert "actual_manifest_npz_schema_valid" in summary["failed_check_ids"]
    assert "actual_manifest_npz_identity_valid" in summary["failed_check_ids"]
    assert "actual_manifest_operator_verified" in summary["failed_check_ids"]
    assert "worker_rocm_environment_manifest_ready" not in summary["failed_check_ids"]
    assert summary["execution_enabled"] is False
    assert summary["model_promoted"] is False
    assert summary["external_state_mutated"] is False
    assert len(payload["rows"]) == 20
    assert len(payload["blockers"]) == 16
    assert len(payload["operator_acceptance_matrix"]) == 5
    assert len(payload["operator_acceptance_stage_check_matrix"]) == 5
    assert payload["operator_acceptance_matrix"][0]["status"] == "ready"
    assert payload["operator_acceptance_matrix"][1]["stage_id"] == "returned_summary_acceptance"
