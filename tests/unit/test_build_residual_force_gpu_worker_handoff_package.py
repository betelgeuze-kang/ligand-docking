from __future__ import annotations

import json
from pathlib import Path

from tools import build_residual_force_gpu_worker_handoff_package as mod


def _packet(summary: dict[str, object]) -> dict[str, object]:
    return {"summary": summary}


def test_gpu_worker_handoff_package_builds_commands_for_gpu_blocker(tmp_path: Path) -> None:
    queue_csv = tmp_path / "q.csv"
    queue_csv.write_text("queue_id,expected_regenerated_trajectory_npz\nq1,a.npz\n", encoding="utf-8")
    full_command = (
        f"python3 tools/generate_ligand_trajectory_engine.py --queue-csv {queue_csv} "
        "--out-root runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames "
        "--frames 120 --out-manifest-csv runs/residual_force_trajectory_regeneration_current_manifest.csv "
        "--out-summary-json runs/residual_force_trajectory_regeneration_current_summary.json "
        "--out-summary-md runs/residual_force_trajectory_regeneration_current_summary.md "
        "--out-progress-json runs/residual_force_trajectory_regeneration_current_progress.json"
    )
    payload = mod.build_residual_force_gpu_worker_handoff_package(
        regeneration_queue_packet=_packet(
            {
                "regeneration_queue_execution_ready": True,
                "queue_rows": 768,
                "regeneration_queue_csv": str(queue_csv),
                "engine_command": full_command,
            }
        ),
        execution_probe_packet=_packet(
            {
                "engine_runtime_ready": False,
                "gpu_backend_unavailable": True,
                "pilot_abort_reason": "RuntimeError: GPU-only mode enabled but CUDA is unavailable.",
            }
        ),
        return_manifest_template_packet=_packet(
            {
                "return_manifest_template_ready": True,
                "template_csv": str(tmp_path / "template.csv"),
                "template_row_count": 768,
            }
        ),
        return_summary_template_packet=_packet(
            {
                "return_summary_template_ready": True,
                "expected_queue_rows": 768,
                "actual_summary_return_path": "runs/residual_force_trajectory_regeneration_current_summary.json",
                "required_summary_fields": ["queue_rows", "processed_rows", "ok_rows", "failed_rows", "aborted_early"],
                "required_completion_rule": "processed_rows>=expected_queue_rows;ok_rows>=expected_queue_rows",
                "template_payload_json": "runs/residual_force_trajectory_regeneration_current_summary_template.json",
            }
        ),
    )

    summary = payload["summary"]
    assert summary["status"] == "residual_force_gpu_worker_handoff_package_ready"
    assert summary["gpu_worker_handoff_ready"] is True
    assert summary["gpu_worker_handoff_required"] is True
    assert "--max-jobs 2" in summary["tiny_pilot_command"]
    assert "residual_force_trajectory_regeneration_pilot_summary.json" in summary["tiny_pilot_command"]
    assert summary["full_regeneration_command"] == full_command
    assert summary["queue_csv_present"] is True
    assert summary["queue_csv_sha256"]
    assert summary["queue_identity_columns_present"] is True
    assert summary["return_manifest_schema_contract_ready"] is True
    assert summary["return_manifest_template_ready"] is True
    assert summary["return_manifest_template_row_count_matches_queue"] is True
    assert summary["return_summary_template_ready"] is True
    assert summary["return_summary_template_row_count_matches_queue"] is True
    assert summary["return_summary_template_payload_json"] == (
        "runs/residual_force_trajectory_regeneration_current_summary_template.json"
    )
    assert summary["return_summary_actual_path"] == "runs/residual_force_trajectory_regeneration_current_summary.json"
    assert summary["operator_transfer_manifest_ready"] is True
    assert summary["operator_transfer_outbound_artifact_count"] == 10
    assert str(queue_csv) in summary["operator_transfer_outbound_artifacts"]
    assert "tools/generate_ligand_trajectory_engine.py" in summary["operator_transfer_outbound_artifacts"]
    assert "tools/build_rocm_environment_manifest.py" in summary["operator_transfer_outbound_artifacts"]
    assert "native PDB files referenced by regeneration_queue_csv.native_pdb_path" in summary[
        "operator_transfer_outbound_artifacts"
    ]
    assert summary["operator_transfer_inbound_artifact_count"] == 5
    assert summary["operator_transfer_first_return_artifact"] == "runs/rocm_environment_manifest_current.json"
    assert summary["worker_rocm_manifest_return_required"] is True
    assert summary["worker_rocm_manifest_return_artifact"] == "runs/rocm_environment_manifest_current.json"
    assert summary["worker_rocm_manifest_validation_command"] == "python3 tools/build_rocm_environment_manifest.py"
    assert "visible_device_count>0" in summary["worker_rocm_manifest_completion_rule"]
    assert summary["operator_transfer_return_manifest_artifact"] == (
        "runs/residual_force_trajectory_regeneration_current_manifest.csv"
    )
    assert summary["operator_transfer_acceptance_artifact"] == (
        "runs/residual_force_gpu_worker_return_receipt_current.json"
    )
    assert summary["operator_transfer_acceptance_ready_key"] == "gpu_worker_return_receipt_ready"
    assert "build_residual_force_gpu_worker_return_receipt.py" in summary[
        "operator_transfer_post_return_validation_command"
    ]
    assert "processed_rows" in summary["return_summary_required_fields"]
    assert "queue_id" in summary["return_manifest_queue_id_columns"]
    assert "trajectory_npz" in summary["return_manifest_npz_columns"]
    assert "queue_row_fingerprint" in summary["return_manifest_fingerprint_columns"]
    assert "queue_row_fingerprint" in summary["return_manifest_required_identity_rule"]
    assert summary["post_run_validation_commands"][0] == "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
    assert "python3 tools/build_residual_uncertainty_policy_evidence_contract.py" in summary["post_run_validation_commands"]
    assert "python3 tools/build_residual_model_registry.py" in summary["post_run_validation_commands"]
    assert "python3 tools/build_product_ai_architecture_gap_closure.py" in summary["post_run_validation_commands"]
    assert summary["post_return_promotion_ladder_ready"] is True
    assert summary["post_return_promotion_ladder_stage_count"] == 10
    assert summary["post_return_promotion_ladder_missing_stages"] == []
    assert summary["post_return_output_contract_ready"] is True
    assert summary["post_return_required_production_output_fields"] == [
        "delta_score",
        "corrected_score",
        "delta_energy",
        "delta_force",
        "uncertainty",
        "abstention_reason",
        "stage2_route_decision",
    ]
    assert summary["post_return_gpu_unlock_output_fields"] == [
        "delta_force",
        "uncertainty",
        "abstention_reason",
        "stage2_route_decision",
    ]
    assert summary["post_return_min_expected_label_rows"] == 768
    ladder = {stage["stage_id"]: stage for stage in summary["post_return_promotion_ladder"]}
    assert ladder["gpu_return_receipt"]["ready_key"] == "gpu_worker_return_receipt_ready"
    assert ladder["production_checkpoint_preflight"]["ready_key"] == "checkpoint_preflight_ready"
    assert ladder["residual_model_registry"]["ready_key"] == "production_promotion_allowed"
    assert ladder["product_ai_architecture_gap_closure"]["ready_key"] == "all_gaps_closed"
    assert ladder["product_goal_completion_audit"]["ready_key"] == "goal_complete"
    assert "runs/residual_model_registry_current.json::production_promotion_allowed=True" in summary[
        "post_return_promotion_ladder_ready_keys"
    ]
    rows_by_step = {row["step_id"]: row for row in payload["rows"]}
    assert "verify_post_return_production_promotion_ladder" in rows_by_step
    assert "verify_post_return_production_output_contract" in rows_by_step
    assert "return_worker_rocm_environment_manifest" in rows_by_step
    assert rows_by_step["verify_post_return_production_output_contract"]["status"] == "pending"
    assert "visible_device_count>0" in rows_by_step["return_worker_rocm_environment_manifest"]["acceptance"]
    post_run_command = rows_by_step["run_post_regeneration_validation_chain"]["command"]
    assert post_run_command.index("build_residual_force_gpu_worker_return_receipt.py") < post_run_command.index(
        "build_residual_force_derivation_validation.py"
    )
    assert post_run_command.index("build_residual_uncertainty_policy_evidence_contract.py") < post_run_command.index(
        "build_residual_production_training_data_contract.py"
    )
    assert post_run_command.index("train_residual_production_score_model.py") < post_run_command.index(
        "build_residual_production_checkpoint_sidecar.py"
    )
    assert post_run_command.index("build_residual_model_registry.py") < post_run_command.index(
        "build_product_ai_architecture_execution_backlog.py"
    )
    assert post_run_command.index("build_product_ai_architecture_execution_backlog.py") < post_run_command.index(
        "build_product_ai_architecture_gap_closure.py"
    )
    assert payload["rows"][1]["step_id"] == "use_prefilled_return_manifest_template"
    assert payload["rows"][2]["step_id"] == "use_prefilled_return_summary_template"
    assert "residual_force_trajectory_regeneration_current_summary_template.json" in rows_by_step[
        "use_prefilled_return_summary_template"
    ]["command"]
    assert rows_by_step["run_post_regeneration_validation_chain"]["step_id"] == "run_post_regeneration_validation_chain"


def test_gpu_worker_handoff_blocks_without_queue_command() -> None:
    payload = mod.build_residual_force_gpu_worker_handoff_package(
        regeneration_queue_packet=_packet({"regeneration_queue_execution_ready": True, "queue_rows": 2}),
        execution_probe_packet=_packet({"engine_runtime_ready": False, "gpu_backend_unavailable": True}),
    )

    assert payload["summary"]["status"] == "blocked_residual_force_gpu_worker_handoff_package"
    assert "engine_command" in payload["summary"]["blockers"]
    assert "return_manifest_template_ready" in payload["summary"]["blockers"]
    assert "return_summary_template_ready" in payload["summary"]["blockers"]


def test_gpu_worker_handoff_blocks_without_queue_identity_csv(tmp_path: Path) -> None:
    queue_csv = tmp_path / "q.csv"
    queue_csv.write_text("ligand_id\nlig1\n", encoding="utf-8")
    payload = mod.build_residual_force_gpu_worker_handoff_package(
        regeneration_queue_packet=_packet(
            {
                "regeneration_queue_execution_ready": True,
                "queue_rows": 1,
                "regeneration_queue_csv": str(queue_csv),
                "engine_command": f"python3 tools/generate_ligand_trajectory_engine.py --queue-csv {queue_csv}",
            }
        ),
        execution_probe_packet=_packet({"engine_runtime_ready": False, "gpu_backend_unavailable": True}),
        return_manifest_template_packet=_packet(
            {
                "return_manifest_template_ready": True,
                "template_csv": str(tmp_path / "template.csv"),
                "template_row_count": 1,
            }
        ),
        return_summary_template_packet=_packet(
            {
                "return_summary_template_ready": True,
                "expected_queue_rows": 1,
                "actual_summary_return_path": "runs/residual_force_trajectory_regeneration_current_summary.json",
            }
        ),
    )

    assert payload["summary"]["gpu_worker_handoff_ready"] is False
    assert payload["summary"]["queue_identity_columns_present"] is False
    assert "queue_identity_columns" in payload["summary"]["blockers"]


def test_gpu_worker_handoff_cli_writes_outputs(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    queue_csv = tmp_path / "q.csv"
    probe = tmp_path / "probe.json"
    template = tmp_path / "template.json"
    summary_template = tmp_path / "summary_template.json"
    out_json = tmp_path / "handoff.json"
    out_csv = tmp_path / "handoff.csv"
    out_md = tmp_path / "handoff.md"
    queue_csv.write_text("queue_id,expected_regenerated_trajectory_npz\nq1,a.npz\n", encoding="utf-8")
    queue.write_text(
        json.dumps(
            _packet(
                {
                    "regeneration_queue_execution_ready": True,
                    "queue_rows": 1,
                    "regeneration_queue_csv": str(queue_csv),
                    "engine_command": f"python3 tools/generate_ligand_trajectory_engine.py --queue-csv {queue_csv} --out-root runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames --frames 120",
                }
            )
        )
        + "\n",
        encoding="utf-8",
    )
    probe.write_text(json.dumps(_packet({"engine_runtime_ready": False, "gpu_backend_unavailable": True})) + "\n", encoding="utf-8")
    template.write_text(
        json.dumps(_packet({"return_manifest_template_ready": True, "template_csv": str(tmp_path / "template.csv"), "template_row_count": 1}))
        + "\n",
        encoding="utf-8",
    )
    summary_template.write_text(
        json.dumps(
            _packet(
                {
                    "return_summary_template_ready": True,
                    "expected_queue_rows": 1,
                    "actual_summary_return_path": "runs/residual_force_trajectory_regeneration_current_summary.json",
                    "required_summary_fields": ["queue_rows", "processed_rows", "ok_rows", "failed_rows", "aborted_early"],
                    "required_completion_rule": "processed_rows>=expected_queue_rows;ok_rows>=expected_queue_rows",
                    "template_payload_json": "runs/residual_force_trajectory_regeneration_current_summary_template.json",
                }
            )
        )
        + "\n",
        encoding="utf-8",
    )

    mod.main(
        [
            "--regeneration-queue-json",
            str(queue),
            "--execution-probe-json",
            str(probe),
            "--return-manifest-template-json",
            str(template),
            "--return-summary-template-json",
            str(summary_template),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["gpu_worker_handoff_ready"] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["return_manifest_template_ready"] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["return_summary_template_ready"] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["return_summary_template_payload_json"] == (
        "runs/residual_force_trajectory_regeneration_current_summary_template.json"
    )
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["operator_transfer_manifest_ready"] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["post_return_output_contract_ready"] is True
    assert "run_full_regeneration_queue" in out_csv.read_text(encoding="utf-8")
    md = out_md.read_text(encoding="utf-8")
    assert "Residual Force GPU Worker Handoff Package" in md
    assert "post_return_gpu_unlock_output_fields" in md
    assert "Operator Transfer Manifest" in md
    assert "Copy To GPU Worker" in md
    assert "worker_rocm_manifest_completion_rule" in md
    assert "residual_force_trajectory_regeneration_current_summary_template.json" in md
