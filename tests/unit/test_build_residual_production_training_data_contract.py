from __future__ import annotations

import json
from pathlib import Path

from tools import build_residual_production_training_data_contract as mod


def _packet(summary: dict[str, object]) -> dict[str, object]:
    return {"summary": summary}


def test_training_data_contract_blocks_smoke_aux_only_state() -> None:
    payload = mod.build_residual_production_training_data_contract(
        residual_shadow_packet=_packet(
            {
                "residual_shadow_ab_ready": True,
                "residual_output_fields": list(mod.REQUIRED_OUTPUT_FIELDS),
            }
        ),
        assist_gate_packet=_packet({"assist_promotion_allowed": True}),
        public_assist_gate_packet=_packet({"assist_comparison_gate_ready": True}),
        checkpoint_work_order_packet=_packet({"checkpoint_preflight_ready": False, "ready_checkpoint_count": 0}),
        aux_summary_packets=[
            (
                "runs/smoke_trajectory_aux_summary.json",
                {
                    "ok": True,
                    "rows_emitted": 256,
                    "binder_rows": 9,
                    "unknown_label_rows": 72,
                    "targets": 1,
                    "feature_dim": 18,
                },
            ),
            (
                "runs/smoke_trajectory_aux_train_summary.json",
                {
                    "ok": True,
                    "checkpoint": "models/smoke.pt",
                    "train_rows": 147,
                    "val_rows": 37,
                    "feature_dim": 18,
                    "best": {"pr_auc": 0.28},
                },
            ),
        ],
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_residual_production_training_data_contract"
    assert summary["primary_blocker"] == "supervised_ligand_dataset_breadth"
    assert "production_residual_output_head" in summary["failed_check_ids"]


def test_training_data_contract_ready_with_broad_dataset_and_preflight_checkpoint(tmp_path: Path) -> None:
    checkpoint = tmp_path / "protein_ligand_residual.pt"
    checkpoint.write_bytes(b"checkpoint")

    payload = mod.build_residual_production_training_data_contract(
        residual_shadow_packet=_packet(
            {
                "residual_shadow_ab_ready": True,
                "residual_output_fields": list(mod.REQUIRED_OUTPUT_FIELDS),
            }
        ),
        assist_gate_packet=_packet({"assist_promotion_allowed": True}),
        public_assist_gate_packet=_packet({"assist_comparison_gate_ready": True}),
        checkpoint_work_order_packet=_packet({"checkpoint_preflight_ready": True, "ready_checkpoint_count": 1}),
        aux_summary_packets=[
            (
                "runs/broad_trajectory_aux_summary.json",
                {
                    "ok": True,
                    "rows_emitted": 1500,
                    "binder_rows": 500,
                    "unknown_label_rows": 0,
                    "targets": 4,
                    "feature_dim": 18,
                },
            ),
            (
                "runs/broad_trajectory_aux_train_summary.json",
                {
                    "ok": True,
                    "checkpoint": str(checkpoint),
                    "train_rows": 1200,
                    "val_rows": 200,
                    "feature_dim": 18,
                    "best": {"pr_auc": 0.72},
                },
            ),
        ],
    )

    assert payload["summary"]["status"] == "residual_production_training_data_contract_ready"
    assert payload["summary"]["production_training_data_ready"] is True
    assert payload["summary"]["fail_check_count"] == 0


def test_training_data_contract_accepts_supervised_dataset_packet() -> None:
    payload = mod.build_residual_production_training_data_contract(
        residual_shadow_packet=_packet(
            {
                "residual_shadow_ab_ready": True,
                "residual_output_fields": list(mod.REQUIRED_OUTPUT_FIELDS),
            }
        ),
        assist_gate_packet=_packet({"assist_promotion_allowed": True}),
        public_assist_gate_packet=_packet({"assist_comparison_gate_ready": True}),
        checkpoint_work_order_packet=_packet({"checkpoint_preflight_ready": False, "ready_checkpoint_count": 0}),
        supervised_dataset_packet=_packet(
            {
                "production_supervised_dataset_ready": True,
                "rows_emitted": 1500,
                "binder_rows": 500,
                "negative_rows": 1000,
                "unknown_label_rows": 0,
                "targets": 4,
                "feature_dim": 4,
            }
        ),
        aux_summary_packets=[],
    )

    dataset_row = next(row for row in payload["rows"] if row["check_id"] == "supervised_ligand_dataset_breadth")
    assert dataset_row["status"] == "pass"
    assert payload["summary"]["primary_blocker"] == "auxiliary_training_quality_floor"


def test_training_data_contract_accepts_score_model_training_packet(tmp_path: Path) -> None:
    checkpoint = tmp_path / "score_model.pt"
    checkpoint.write_bytes(b"checkpoint")
    payload = mod.build_residual_production_training_data_contract(
        residual_shadow_packet=_packet(
            {
                "residual_shadow_ab_ready": True,
                "residual_output_fields": list(mod.REQUIRED_OUTPUT_FIELDS),
            }
        ),
        assist_gate_packet=_packet({"assist_promotion_allowed": True}),
        public_assist_gate_packet=_packet({"assist_comparison_gate_ready": True}),
        checkpoint_work_order_packet=_packet({"checkpoint_preflight_ready": False, "ready_checkpoint_count": 0}),
        supervised_dataset_packet=_packet(
            {
                "production_supervised_dataset_ready": True,
                "rows_emitted": 1500,
                "binder_rows": 500,
                "negative_rows": 1000,
                "unknown_label_rows": 0,
                "targets": 4,
                "feature_dim": 4,
            }
        ),
        score_model_packet=_packet(
            {
                "checkpoint": str(checkpoint),
                "train_rows": 1200,
                "val_rows": 200,
                "feature_dim": 6,
                "best": {"pr_auc": 0.61},
                "learned_output_fields": ["delta_score", "corrected_score", "uncertainty"],
                "policy_output_fields": ["abstention_reason", "stage2_route_decision"],
                "policy_output_adapter_ready": True,
            }
        ),
        aux_summary_packets=[],
    )

    training_row = next(row for row in payload["rows"] if row["check_id"] == "auxiliary_training_quality_floor")
    assert training_row["status"] == "pass"
    assert payload["summary"]["primary_blocker"] == "production_residual_output_head"


def test_training_data_contract_exposes_missing_production_output_fields(tmp_path: Path) -> None:
    checkpoint = tmp_path / "score_model.pt"
    checkpoint.write_bytes(b"checkpoint")
    payload = mod.build_residual_production_training_data_contract(
        residual_shadow_packet=_packet(
            {
                "residual_shadow_ab_ready": True,
                "residual_output_fields": list(mod.REQUIRED_OUTPUT_FIELDS),
            }
        ),
        assist_gate_packet=_packet({"assist_promotion_allowed": True}),
        public_assist_gate_packet=_packet({"assist_comparison_gate_ready": True}),
        checkpoint_work_order_packet=_packet({"checkpoint_preflight_ready": False, "ready_checkpoint_count": 0}),
        supervised_dataset_packet=_packet(
            {
                "production_supervised_dataset_ready": True,
                "rows_emitted": 1500,
                "binder_rows": 500,
                "negative_rows": 1000,
                "unknown_label_rows": 0,
                "targets": 4,
                "feature_dim": 4,
            }
        ),
        score_model_packet=_packet(
            {
                "checkpoint": str(checkpoint),
                "train_rows": 1200,
                "val_rows": 200,
                "feature_dim": 6,
                "best": {"pr_auc": 0.61},
                "production_checkpoint_ready": False,
                "missing_production_output_fields": ["delta_energy", "delta_force"],
                "learned_output_fields": ["delta_score", "corrected_score", "uncertainty"],
                "policy_output_fields": ["abstention_reason", "stage2_route_decision"],
                "policy_output_adapter_ready": True,
            }
        ),
        aux_summary_packets=[],
    )

    row = next(row for row in payload["rows"] if row["check_id"] == "production_residual_output_head")
    assert row["missing_production_output_fields"] == ["delta_energy", "delta_force"]
    assert row["score_model_production_checkpoint_ready"] is False
    assert "missing_production_output_fields=delta_energy,delta_force" in row["observed"]
    assert payload["summary"]["production_missing_output_fields"] == ["delta_energy", "delta_force"]


def test_training_data_contract_blocks_uncertainty_policy_when_missing_labels_and_no_sidecar(tmp_path: Path) -> None:
    checkpoint = tmp_path / "score_model.pt"
    checkpoint.write_bytes(b"checkpoint")
    payload = mod.build_residual_production_training_data_contract(
        residual_shadow_packet=_packet(
            {
                "residual_shadow_ab_ready": True,
                "residual_output_fields": list(mod.REQUIRED_OUTPUT_FIELDS),
                "abstention_fields_present": True,
            }
        ),
        assist_gate_packet=_packet({"assist_promotion_allowed": True}),
        public_assist_gate_packet=_packet({"assist_comparison_gate_ready": True}),
        checkpoint_work_order_packet=_packet({"checkpoint_preflight_ready": False, "ready_checkpoint_count": 0}),
        supervised_dataset_packet=_packet(
            {
                "production_supervised_dataset_ready": True,
                "rows_emitted": 1500,
                "binder_rows": 500,
                "negative_rows": 1000,
                "unknown_label_rows": 0,
                "targets": 4,
                "feature_dim": 4,
                "label_fields": ["is_binder", "reference_binding_kcal_mol", "delta_score", "corrected_score"],
                "missing_production_output_labels": ["uncertainty", "abstention_reason", "stage2_route_decision"],
            }
        ),
        score_model_packet=_packet(
            {
                "checkpoint": str(checkpoint),
                "train_rows": 1200,
                "val_rows": 200,
                "feature_dim": 6,
                "best": {"pr_auc": 0.61},
                "learned_output_fields": ["delta_score", "corrected_score", "uncertainty"],
                "policy_output_fields": ["abstention_reason", "stage2_route_decision"],
                "policy_output_adapter_ready": True,
            }
        ),
        aux_summary_packets=[],
    )

    row = next(row for row in payload["rows"] if row["check_id"] == "production_uncertainty_abstention_route_policy")
    assert row["status"] == "fail"
    assert "missing_uncertainty_policy_labels=uncertainty,abstention_reason,stage2_route_decision" in row["observed"]
    assert "policy_output_adapter_ready=True" in row["observed"]
    assert "checkpoint_preflight_ready=False" in row["observed"]
    assert "policy_contract_ready=False" in row["observed"]
    assert payload["summary"]["uncertainty_policy_evidence_ready"] is False
    assert payload["summary"]["uncertainty_policy_contract_ready"] is False
    assert payload["summary"]["missing_uncertainty_policy_label_fields"] == [
        "uncertainty",
        "abstention_reason",
        "stage2_route_decision",
    ]


def test_training_data_contract_accepts_uncertainty_policy_contract_without_policy_labels(tmp_path: Path) -> None:
    checkpoint = tmp_path / "score_model.pt"
    checkpoint.write_bytes(b"checkpoint")
    payload = mod.build_residual_production_training_data_contract(
        residual_shadow_packet=_packet(
            {
                "residual_shadow_ab_ready": True,
                "residual_output_fields": list(mod.REQUIRED_OUTPUT_FIELDS),
                "abstention_fields_present": True,
            }
        ),
        assist_gate_packet=_packet({"assist_promotion_allowed": True}),
        public_assist_gate_packet=_packet({"assist_comparison_gate_ready": True}),
        checkpoint_work_order_packet=_packet({"checkpoint_preflight_ready": False, "ready_checkpoint_count": 0}),
        supervised_dataset_packet=_packet(
            {
                "production_supervised_dataset_ready": True,
                "rows_emitted": 1500,
                "binder_rows": 500,
                "negative_rows": 1000,
                "unknown_label_rows": 0,
                "targets": 4,
                "feature_dim": 4,
                "label_fields": ["is_binder", "reference_binding_kcal_mol", "delta_score", "corrected_score"],
                "missing_production_output_labels": ["uncertainty", "abstention_reason", "stage2_route_decision"],
            }
        ),
        score_model_packet=_packet(
            {
                "checkpoint": str(checkpoint),
                "train_rows": 1200,
                "val_rows": 200,
                "feature_dim": 6,
                "best": {"pr_auc": 0.61},
                "learned_output_fields": ["delta_score", "corrected_score", "uncertainty"],
                "policy_output_fields": ["abstention_reason", "stage2_route_decision"],
                "policy_output_adapter_ready": True,
            }
        ),
        uncertainty_policy_evidence_packet=_packet(
            {
                "status": "residual_uncertainty_policy_evidence_contract_ready",
                "uncertainty_policy_evidence_ready": True,
            }
        ),
        aux_summary_packets=[],
    )

    row = next(row for row in payload["rows"] if row["check_id"] == "production_uncertainty_abstention_route_policy")
    assert row["status"] == "pass"
    assert "policy_contract_ready=True" in row["observed"]
    assert payload["summary"]["uncertainty_policy_evidence_ready"] is True
    assert payload["summary"]["uncertainty_policy_contract_ready"] is True


def test_training_data_contract_blocks_energy_force_heads_until_labels_exist(tmp_path: Path) -> None:
    checkpoint = tmp_path / "score_model.pt"
    checkpoint.write_bytes(b"checkpoint")
    payload = mod.build_residual_production_training_data_contract(
        residual_shadow_packet=_packet(
            {
                "residual_shadow_ab_ready": True,
                "residual_output_fields": list(mod.REQUIRED_OUTPUT_FIELDS),
            }
        ),
        assist_gate_packet=_packet({"assist_promotion_allowed": True}),
        public_assist_gate_packet=_packet({"assist_comparison_gate_ready": True}),
        checkpoint_work_order_packet=_packet({"checkpoint_preflight_ready": False, "ready_checkpoint_count": 0}),
        supervised_dataset_packet=_packet(
            {
                "production_supervised_dataset_ready": True,
                "rows_emitted": 1500,
                "binder_rows": 500,
                "negative_rows": 1000,
                "unknown_label_rows": 0,
                "targets": 4,
                "feature_dim": 4,
                "label_fields": ["is_binder", "reference_binding_kcal_mol", "delta_score", "corrected_score"],
                "missing_production_output_labels": ["delta_energy", "delta_force", "uncertainty"],
            }
        ),
        score_model_packet=_packet(
            {
                "checkpoint": str(checkpoint),
                "train_rows": 1200,
                "val_rows": 200,
                "feature_dim": 6,
                "best": {"pr_auc": 0.61},
                "production_checkpoint_ready": False,
                "missing_production_output_fields": ["delta_energy", "delta_force"],
                "learned_output_fields": ["delta_score", "corrected_score", "uncertainty"],
                "policy_output_fields": ["abstention_reason", "stage2_route_decision"],
                "policy_output_adapter_ready": True,
            }
        ),
        energy_force_label_work_order_packet=_packet(
            {
                "delta_energy_label_evidence_ready": False,
                "delta_force_label_evidence_ready": False,
                "force_artifact_recovery_required": True,
                "force_artifact_missing_trajectory_npz_rows": 2,
                "force_artifact_top_missing_prefix": "/missing/runA",
                "force_derivation_effective_min_existing_npz_rows": 2,
                "force_derivation_existing_npz_floor_capped_by_available_paths": True,
                "force_trajectory_regeneration_queue_execution_ready": True,
                "force_trajectory_regeneration_queue_rows": 2,
                "force_trajectory_regeneration_engine_runtime_ready": False,
                "force_trajectory_regeneration_gpu_backend_unavailable": True,
                "force_gpu_worker_handoff_ready": True,
                "force_gpu_worker_handoff_required": True,
                "force_gpu_worker_return_receipt_ready": False,
                "force_gpu_worker_return_receipt_blockers": ["full_regeneration_summary_complete"],
                "force_gpu_worker_return_summary_manifest_bound": False,
                "force_gpu_worker_return_summary_manifest_csv": "runs/other_manifest.csv",
                "force_gpu_worker_return_summary_out_manifest_csv_present": False,
                "force_gpu_worker_return_summary_out_manifest_csv": "",
                "force_gpu_worker_return_summary_out_manifest_csv_bound": False,
                "force_gpu_worker_return_summary_out_summary_json_bound": False,
                "force_gpu_worker_return_summary_out_summary_json": "",
                "force_gpu_worker_return_summary_manifest_row_counts_consistent": False,
                "force_gpu_worker_return_summary_ok_rows": 0,
                "force_gpu_worker_return_manifest_ok_row_count": 0,
                "force_gpu_worker_return_manifest_status_placeholder_count": 1,
                "force_gpu_worker_return_manifest_status_invalid_count": 2,
                "force_gpu_worker_return_manifest_allowed_ok_status_values": ["ok", "ok_npz_bundle"],
                "force_gpu_worker_return_manifest_npz_paths_complete": False,
                "force_gpu_worker_return_manifest_npz_path_present_count": 0,
                "force_gpu_worker_return_manifest_npz_path_missing_count": 2,
                "force_gpu_worker_return_manifest_ok_row_missing_npz_path_count": 1,
                "force_gpu_worker_return_manifest_operator_verified_missing_npz_path_count": 1,
                "force_gpu_worker_return_manifest_npz_files_exist": False,
                "force_gpu_worker_return_manifest_npz_file_existing_count": 0,
                "force_gpu_worker_return_manifest_npz_file_missing_count": 2,
                "force_gpu_worker_return_manifest_ok_row_missing_npz_file_count": 1,
                "force_gpu_worker_return_manifest_operator_verified_missing_npz_file_count": 1,
                "force_gpu_worker_return_manifest_npz_files_valid": False,
                "force_gpu_worker_return_manifest_npz_file_valid_count": 0,
                "force_gpu_worker_return_manifest_npz_file_invalid_count": 2,
                "force_gpu_worker_return_manifest_ok_row_invalid_npz_file_count": 1,
                "force_gpu_worker_return_manifest_operator_verified_invalid_npz_file_count": 1,
                "force_gpu_worker_return_manifest_npz_schema_valid": False,
                "force_gpu_worker_return_manifest_npz_schema_valid_count": 0,
                "force_gpu_worker_return_manifest_npz_schema_invalid_count": 2,
                "force_gpu_worker_return_manifest_ok_row_invalid_npz_schema_count": 1,
                "force_gpu_worker_return_manifest_operator_verified_invalid_npz_schema_count": 1,
                "force_gpu_worker_return_manifest_npz_identity_valid": False,
                "force_gpu_worker_return_manifest_npz_identity_valid_count": 0,
                "force_gpu_worker_return_manifest_npz_identity_invalid_count": 2,
                "force_gpu_worker_return_manifest_ok_row_invalid_npz_identity_count": 1,
                "force_gpu_worker_return_manifest_operator_verified_invalid_npz_identity_count": 1,
                "force_gpu_worker_return_identity_coverage_ready": False,
                "force_gpu_worker_return_matched_queue_id_count": 0,
                "force_gpu_worker_return_matched_expected_npz_count": 0,
                "force_gpu_worker_return_missing_queue_id_count": 2,
                "force_gpu_worker_return_missing_expected_npz_count": 2,
            }
        ),
        aux_summary_packets=[],
    )

    energy_row = next(row for row in payload["rows"] if row["check_id"] == "production_delta_energy_label_evidence")
    force_row = next(row for row in payload["rows"] if row["check_id"] == "production_delta_force_label_evidence")
    assert energy_row["status"] == "fail"
    assert force_row["status"] == "fail"
    assert "artifact_recovery_required=True" in force_row["observed"]
    assert "missing_trajectory_npz_rows=2" in force_row["observed"]
    assert "top_missing_prefix=/missing/runA" in force_row["observed"]
    assert "effective_min_existing_npz_rows=2" in force_row["observed"]
    assert "existing_npz_floor_capped_by_available_paths=True" in force_row["observed"]
    assert "trajectory_regeneration_queue_execution_ready=True" in force_row["observed"]
    assert "trajectory_regeneration_queue_rows=2" in force_row["observed"]
    assert "trajectory_regeneration_engine_runtime_ready=False" in force_row["observed"]
    assert "trajectory_regeneration_gpu_backend_unavailable=True" in force_row["observed"]
    assert "gpu_worker_handoff_ready=True" in force_row["observed"]
    assert "gpu_worker_handoff_required=True" in force_row["observed"]
    assert "gpu_worker_return_receipt_ready=False" in force_row["observed"]
    assert "gpu_worker_return_receipt_blockers=full_regeneration_summary_complete" in force_row["observed"]
    assert "gpu_worker_return_summary_manifest_bound=False" in force_row["observed"]
    assert "gpu_worker_return_summary_manifest_csv=runs/other_manifest.csv" in force_row["observed"]
    assert "gpu_worker_return_summary_out_manifest_csv_present=False" in force_row["observed"]
    assert "gpu_worker_return_summary_out_manifest_csv=" in force_row["observed"]
    assert "gpu_worker_return_summary_out_manifest_csv_bound=False" in force_row["observed"]
    assert "gpu_worker_return_summary_out_summary_json_bound=False" in force_row["observed"]
    assert "gpu_worker_return_summary_out_summary_json=" in force_row["observed"]
    assert "gpu_worker_return_summary_manifest_row_counts_consistent=False" in force_row["observed"]
    assert "gpu_worker_return_summary_ok_rows=0" in force_row["observed"]
    assert "gpu_worker_return_manifest_ok_row_count=0" in force_row["observed"]
    assert "gpu_worker_return_manifest_status_placeholder_count=1" in force_row["observed"]
    assert "gpu_worker_return_manifest_status_invalid_count=2" in force_row["observed"]
    assert "gpu_worker_return_manifest_allowed_ok_status_values=ok,ok_npz_bundle" in force_row["observed"]
    assert "gpu_worker_return_manifest_npz_paths_complete=False" in force_row["observed"]
    assert "gpu_worker_return_manifest_ok_row_missing_npz_path_count=1" in force_row["observed"]
    assert "gpu_worker_return_manifest_npz_files_exist=False" in force_row["observed"]
    assert "gpu_worker_return_manifest_ok_row_missing_npz_file_count=1" in force_row["observed"]
    assert "gpu_worker_return_manifest_npz_files_valid=False" in force_row["observed"]
    assert "gpu_worker_return_manifest_ok_row_invalid_npz_file_count=1" in force_row["observed"]
    assert "gpu_worker_return_manifest_npz_schema_valid=False" in force_row["observed"]
    assert "gpu_worker_return_manifest_ok_row_invalid_npz_schema_count=1" in force_row["observed"]
    assert "gpu_worker_return_manifest_npz_identity_valid=False" in force_row["observed"]
    assert "gpu_worker_return_manifest_ok_row_invalid_npz_identity_count=1" in force_row["observed"]
    assert "gpu_worker_return_identity_coverage_ready=False" in force_row["observed"]
    assert "gpu_worker_return_matched_queue_id_count=0" in force_row["observed"]
    assert "gpu_worker_return_missing_queue_id_count=2" in force_row["observed"]
    assert payload["summary"]["primary_blocker"] == "production_delta_energy_label_evidence"
    assert payload["summary"]["missing_energy_force_label_fields"] == ["delta_energy", "delta_force"]


def test_training_data_contract_accepts_validated_energy_force_work_order(tmp_path: Path) -> None:
    checkpoint = tmp_path / "score_model.pt"
    checkpoint.write_bytes(b"checkpoint")
    payload = mod.build_residual_production_training_data_contract(
        residual_shadow_packet=_packet(
            {
                "residual_shadow_ab_ready": True,
                "residual_output_fields": list(mod.REQUIRED_OUTPUT_FIELDS),
            }
        ),
        assist_gate_packet=_packet({"assist_promotion_allowed": True}),
        public_assist_gate_packet=_packet({"assist_comparison_gate_ready": True}),
        checkpoint_work_order_packet=_packet({"checkpoint_preflight_ready": False, "ready_checkpoint_count": 0}),
        supervised_dataset_packet=_packet(
            {
                "production_supervised_dataset_ready": True,
                "rows_emitted": 1500,
                "binder_rows": 500,
                "negative_rows": 1000,
                "unknown_label_rows": 0,
                "targets": 4,
                "feature_dim": 4,
                "label_fields": ["is_binder", "reference_binding_kcal_mol", "delta_score", "corrected_score"],
                "missing_production_output_labels": ["delta_energy", "delta_force"],
            }
        ),
        score_model_packet=_packet(
            {
                "checkpoint": str(checkpoint),
                "train_rows": 1200,
                "val_rows": 200,
                "feature_dim": 6,
                "best": {"pr_auc": 0.61},
                "production_checkpoint_ready": False,
                "missing_production_output_fields": ["delta_energy", "delta_force"],
                "learned_output_fields": ["delta_score", "corrected_score", "uncertainty"],
                "policy_output_fields": ["abstention_reason", "stage2_route_decision"],
                "policy_output_adapter_ready": True,
            }
        ),
        energy_force_label_work_order_packet=_packet(
            {
                "delta_energy_label_evidence_ready": True,
                "delta_force_label_evidence_ready": True,
                "energy_proxy_rows": 1500,
                "delta_energy_proxy_validation_ready": True,
                "force_derivation_input_ready": True,
                "delta_force_derivation_validation_ready": True,
            }
        ),
        aux_summary_packets=[],
    )

    energy_row = next(row for row in payload["rows"] if row["check_id"] == "production_delta_energy_label_evidence")
    force_row = next(row for row in payload["rows"] if row["check_id"] == "production_delta_force_label_evidence")
    assert energy_row["status"] == "pass"
    assert force_row["status"] == "pass"
    assert payload["summary"]["delta_energy_label_evidence_ready"] is True
    assert payload["summary"]["delta_force_label_evidence_ready"] is True
    assert payload["summary"]["uncertainty_policy_evidence_ready"] is True
    assert payload["summary"]["primary_blocker"] == "production_residual_output_head"


def test_training_data_contract_cli_writes_outputs(tmp_path: Path) -> None:
    residual = tmp_path / "residual.json"
    assist = tmp_path / "assist.json"
    public = tmp_path / "public.json"
    work = tmp_path / "work.json"
    aux = tmp_path / "tiny_trajectory_aux_summary.json"
    residual.write_text(
        json.dumps(_packet({"residual_shadow_ab_ready": True, "residual_output_fields": list(mod.REQUIRED_OUTPUT_FIELDS)})) + "\n",
        encoding="utf-8",
    )
    assist.write_text(json.dumps(_packet({"assist_promotion_allowed": True})) + "\n", encoding="utf-8")
    public.write_text(json.dumps(_packet({"assist_comparison_gate_ready": True})) + "\n", encoding="utf-8")
    work.write_text(json.dumps(_packet({"checkpoint_preflight_ready": False, "ready_checkpoint_count": 0})) + "\n", encoding="utf-8")
    aux.write_text(json.dumps({"ok": True, "rows_emitted": 10, "binder_rows": 1, "unknown_label_rows": 0, "targets": 1}) + "\n", encoding="utf-8")
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    mod.main(
        [
            "--residual-shadow-json",
            str(residual),
            "--assist-gate-json",
            str(assist),
            "--public-assist-gate-json",
            str(public),
            "--checkpoint-work-order-json",
            str(work),
            "--aux-summary-glob",
            str(tmp_path / "*trajectory_aux*summary.json"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["check_count"] == 9
    assert "supervised_ligand_dataset_breadth" in out_csv.read_text(encoding="utf-8")
    assert "Residual Production Training Data Contract" in out_md.read_text(encoding="utf-8")
