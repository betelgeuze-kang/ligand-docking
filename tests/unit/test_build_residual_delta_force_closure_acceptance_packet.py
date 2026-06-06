from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_residual_delta_force_closure_acceptance_packet as mod


def _packet(summary: dict[str, object]) -> dict[str, object]:
    return {"summary": summary}


def test_delta_force_closure_acceptance_packet_surfaces_next_failed_stage() -> None:
    payload = mod.build_residual_delta_force_closure_acceptance_packet(
        output_head_gap_packet=_packet(
            {
                "output_head_gap_contract_ready": True,
                "production_output_heads_complete": False,
                "first_blocked_output_field": "delta_force",
                "blocked_output_fields": ["delta_force"],
                "ready_output_field_count": 6,
                "blocked_output_field_count": 1,
            }
        ),
        energy_force_work_order_packet=_packet(
            {
                "delta_energy_label_evidence_ready": True,
                "delta_force_label_evidence_ready": False,
                "delta_force_derivation_validation_ready": False,
                "force_gpu_worker_return_receipt_ready": False,
                "force_gpu_worker_return_receipt_next_required_step": "Return GPU summary.",
            }
        ),
        gpu_return_intake_packet=_packet(
            {
                "operator_return_bundle_contract_ready": True,
                "operator_return_required_artifact_count": 5,
                "operator_return_required_artifacts": ["summary.json", "manifest.csv"],
                "operator_return_next_artifact_id": "returned_summary_json",
                "operator_return_next_artifact_path": "summary.json",
                "operator_return_next_artifact_failed_check_ids": [
                    "actual_summary_returned_complete"
                ],
                "operator_return_next_artifact_completion_packet": {
                    "required_fields_or_columns": ["queue_rows", "backend_counts"]
                },
                "operator_return_manifest_required_columns": [
                    "queue_id",
                    "expected_regenerated_trajectory_npz",
                ],
            }
        ),
        force_gpu_handoff_packet=_packet(
            {
                "gpu_worker_handoff_ready": True,
                "operator_transfer_post_return_validation_command": (
                    "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
                ),
            }
        ),
        training_data_packet=_packet({"production_training_data_ready": False}),
        score_model_packet=_packet({"score_model_production_checkpoint_ready": False}),
        sidecar_packet=_packet({"sidecar_ready": False}),
        preflight_packet=_packet({"checkpoint_preflight_ready": False}),
        registry_packet=_packet({"production_promotion_allowed": False}),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_residual_delta_force_closure_acceptance_packet"
    assert summary["packet_ready"] is True
    assert summary["delta_force_closure_ready"] is False
    assert summary["first_blocked_output_field"] == "delta_force"
    assert summary["delta_energy_label_evidence_ready"] is True
    assert summary["delta_force_label_evidence_ready"] is False
    assert summary["operator_return_bundle_contract_ready"] is True
    assert summary["return_summary_required_fields"] == ["queue_rows", "backend_counts"]
    assert summary["next_stage_id"] == "gpu_worker_return_receipt"
    assert summary["next_stage_validation_command"] == (
        "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
    )
    assert "gpu_worker_return_receipt" in summary["closure_failed_stage_ids"]
    assert payload["rows"][0]["status"] == "fail"
    assert payload["rows"][0]["execution_enabled"] is False


def test_delta_force_closure_acceptance_packet_complete_when_all_stages_pass() -> None:
    ready = mod.build_residual_delta_force_closure_acceptance_packet(
        output_head_gap_packet=_packet(
            {
                "output_head_gap_contract_ready": True,
                "production_output_heads_complete": True,
                "first_blocked_output_field": "",
                "blocked_output_fields": ["delta_force"],
                "ready_output_field_count": 7,
                "blocked_output_field_count": 0,
            }
        ),
        energy_force_work_order_packet=_packet(
            {
                "delta_energy_label_evidence_ready": True,
                "delta_force_label_evidence_ready": True,
                "delta_force_derivation_validation_ready": True,
                "force_gpu_worker_return_receipt_ready": True,
            }
        ),
        gpu_return_intake_packet=_packet({"operator_return_bundle_contract_ready": True}),
        force_gpu_handoff_packet=_packet({"gpu_worker_handoff_ready": True}),
        training_data_packet=_packet({"production_training_data_ready": True}),
        score_model_packet=_packet({"score_model_production_checkpoint_ready": True}),
        sidecar_packet=_packet({"sidecar_ready": True}),
        preflight_packet=_packet({"checkpoint_preflight_ready": True}),
        registry_packet=_packet({"production_promotion_allowed": True}),
    )

    assert ready["summary"]["status"] == "residual_delta_force_closure_acceptance_complete"
    assert ready["summary"]["delta_force_closure_ready"] is True
    assert ready["summary"]["closure_failed_stage_count"] == 0
    assert all(row["status"] == "pass" for row in ready["rows"])


def test_delta_force_closure_acceptance_packet_cli_writes_outputs(tmp_path: Path) -> None:
    paths = {
        "output": tmp_path / "output.json",
        "work": tmp_path / "work.json",
        "return": tmp_path / "return.json",
        "handoff": tmp_path / "handoff.json",
        "training": tmp_path / "training.json",
        "score": tmp_path / "score.json",
        "sidecar": tmp_path / "sidecar.json",
        "preflight": tmp_path / "preflight.json",
        "registry": tmp_path / "registry.json",
    }
    paths["output"].write_text(
        json.dumps(
            _packet(
                {
                    "output_head_gap_contract_ready": True,
                    "production_output_heads_complete": False,
                    "first_blocked_output_field": "delta_force",
                    "blocked_output_fields": ["delta_force"],
                }
            )
        )
        + "\n",
        encoding="utf-8",
    )
    paths["work"].write_text(
        json.dumps(_packet({"force_gpu_worker_return_receipt_ready": False})) + "\n",
        encoding="utf-8",
    )
    paths["return"].write_text(
        json.dumps(_packet({"operator_return_bundle_contract_ready": True})) + "\n",
        encoding="utf-8",
    )
    paths["handoff"].write_text(
        json.dumps(_packet({"gpu_worker_handoff_ready": True})) + "\n",
        encoding="utf-8",
    )
    for key in ["training", "score", "sidecar", "preflight", "registry"]:
        paths[key].write_text(json.dumps(_packet({})) + "\n", encoding="utf-8")

    out_json = tmp_path / "packet.json"
    out_csv = tmp_path / "packet.csv"
    out_md = tmp_path / "packet.md"
    mod.main(
        [
            "--output-head-gap-json",
            str(paths["output"]),
            "--energy-force-work-order-json",
            str(paths["work"]),
            "--gpu-return-intake-json",
            str(paths["return"]),
            "--force-gpu-handoff-json",
            str(paths["handoff"]),
            "--training-data-json",
            str(paths["training"]),
            "--score-model-json",
            str(paths["score"]),
            "--sidecar-json",
            str(paths["sidecar"]),
            "--preflight-json",
            str(paths["preflight"]),
            "--registry-json",
            str(paths["registry"]),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["summary"]["packet_type"] == "residual_delta_force_closure_acceptance_packet"
    assert data["summary"]["packet_ready"] is True
    assert out_csv.read_text(encoding="utf-8").startswith("stage_id,status,")
    assert "Residual Delta Force Closure Acceptance Packet" in out_md.read_text(encoding="utf-8")
