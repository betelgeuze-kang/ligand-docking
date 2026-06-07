from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools import build_residual_production_checkpoint_preflight as mod


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _policy_fields() -> dict[str, object]:
    return {
        "adapter_output_policy": {field: f"policy_for_{field}" for field in mod.REQUIRED_OUTPUT_FIELDS},
        "physics_guard_policy": "fail_closed_physics_guard",
        "abstention_policy": "abstain_on_uncertainty_or_contract_violation",
    }


def _ready_contract_artifacts(tmp_path: Path) -> dict[str, object]:
    training = tmp_path / "training_data_contract.json"
    receipt = tmp_path / "force_receipt.json"
    training.write_text(
        json.dumps({"summary": {"status": "residual_production_training_data_contract_ready", "production_training_data_ready": True}})
        + "\n",
        encoding="utf-8",
    )
    receipt.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "residual_force_gpu_worker_return_receipt_ready",
                    "gpu_worker_return_receipt_ready": True,
                    "queue_manifest_identity_coverage_ready": True,
                    "full_regeneration_manifest_operator_verified": True,
                    "expected_queue_rows": 2,
                    "manifest_ok_row_count": 2,
                    "manifest_operator_verified_true_count": 2,
                    "manifest_status_placeholder_count": 0,
                    "manifest_status_invalid_count": 0,
                    "manifest_allowed_ok_status_values": [
                        "ok",
                        "ok_full_regeneration",
                        "ok_npz_bundle",
                        "ok_regenerated_npz",
                    ],
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "production_training_data_contract_artifact": str(training),
        "force_gpu_worker_return_receipt_artifact": str(receipt),
    }


def test_checkpoint_preflight_blocks_unlabeled_checkpoint(tmp_path: Path) -> None:
    ckpt = tmp_path / "model.pth"
    ckpt.write_bytes(b"weights")

    payload = mod.build_residual_production_checkpoint_preflight(models_dir=str(tmp_path))

    summary = payload["summary"]
    assert summary["status"] == "blocked_residual_production_checkpoint_preflight"
    assert summary["candidate_checkpoint_count"] == 1
    assert summary["ready_checkpoint_count"] == 0
    row = payload["rows"][0]
    assert row["metadata_present"] is False
    assert "missing_sidecar_metadata" in row["blockers"]
    assert row["ready_for_guarded_promotion"] is False


def test_checkpoint_preflight_accepts_guarded_sidecar(tmp_path: Path) -> None:
    ckpt = tmp_path / "residual_model.pth"
    ckpt.write_bytes(b"production candidate")
    sidecar = tmp_path / "residual_model.pth.json"
    sidecar.write_text(
        json.dumps(
            {
                "component_id": "topograph_corrector",
                "model_family": "protein_ligand_residual_v1",
                "checkpoint_sha256": _sha256(ckpt),
                "required_output_fields": mod.REQUIRED_OUTPUT_FIELDS,
                "benchmark_gate_artifacts": [{"status": "ready"}],
                "uncertainty_calibrated": True,
                "physics_guard_bound": True,
                "promotion_mode": "production_guarded",
                **_policy_fields(),
                **_ready_contract_artifacts(tmp_path),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    payload = mod.build_residual_production_checkpoint_preflight(models_dir=str(tmp_path))

    summary = payload["summary"]
    assert summary["status"] == "residual_production_checkpoint_preflight_ready"
    assert summary["checkpoint_preflight_ready"] is True
    assert summary["ready_checkpoint_count"] == 1
    assert payload["rows"][0]["ready_for_guarded_promotion"] is True
    assert payload["rows"][0]["adapter_output_policy_complete"] is True
    assert payload["rows"][0]["production_training_data_contract_ready"] is True
    assert payload["rows"][0]["force_gpu_worker_return_receipt_ready"] is True


def test_checkpoint_preflight_rejects_sidecar_missing_policy_contract(tmp_path: Path) -> None:
    ckpt = tmp_path / "residual_model.pth"
    ckpt.write_bytes(b"production candidate")
    sidecar = tmp_path / "residual_model.pth.json"
    sidecar.write_text(
        json.dumps(
            {
                "component_id": "topograph_corrector",
                "model_family": "protein_ligand_residual_v1",
                "checkpoint_sha256": _sha256(ckpt),
                "required_output_fields": mod.REQUIRED_OUTPUT_FIELDS,
                "benchmark_gate_artifacts": [{"status": "ready"}],
                "uncertainty_calibrated": True,
                "physics_guard_bound": True,
                "promotion_mode": "production_guarded",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    payload = mod.build_residual_production_checkpoint_preflight(models_dir=str(tmp_path))

    row = payload["rows"][0]
    assert row["ready_for_guarded_promotion"] is False
    assert "missing_metadata_fields:adapter_output_policy,physics_guard_policy,abstention_policy,production_training_data_contract_artifact,force_gpu_worker_return_receipt_artifact" in row["blockers"]
    assert "missing_adapter_output_policy:delta_score,corrected_score,delta_energy,delta_force,uncertainty,abstention_reason,stage2_route_decision" in row["blockers"]
    assert "missing_physics_guard_policy" in row["blockers"]
    assert "missing_abstention_policy" in row["blockers"]
    assert "production_training_data_contract_not_ready" in row["blockers"]
    assert "force_gpu_worker_return_receipt_not_ready" in row["blockers"]


def test_checkpoint_preflight_rejects_sidecar_when_linked_model_artifact_is_not_production_ready(tmp_path: Path) -> None:
    ckpt = tmp_path / "residual_model.pth"
    ckpt.write_bytes(b"score-only candidate")
    training_artifact = tmp_path / "residual_score_model.json"
    training_artifact.write_text(
        json.dumps(
            {
                "status": "residual_production_score_model_trained",
                "production_checkpoint_ready": False,
                "missing_production_output_fields": ["delta_energy", "delta_force"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    sidecar = tmp_path / "residual_model.pth.json"
    sidecar.write_text(
        json.dumps(
            {
                "component_id": "topograph_corrector",
                "model_family": "protein_ligand_residual_v1",
                "checkpoint_sha256": _sha256(ckpt),
                "required_output_fields": mod.REQUIRED_OUTPUT_FIELDS,
                "benchmark_gate_artifacts": [
                    {
                        "artifact": str(training_artifact),
                        "status": "ready",
                    }
                ],
                "uncertainty_calibrated": True,
                "physics_guard_bound": True,
                "promotion_mode": "production_guarded",
                **_policy_fields(),
                **_ready_contract_artifacts(tmp_path),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    payload = mod.build_residual_production_checkpoint_preflight(models_dir=str(tmp_path))

    summary = payload["summary"]
    assert summary["status"] == "blocked_residual_production_checkpoint_preflight"
    assert summary["ready_checkpoint_count"] == 0
    row = payload["rows"][0]
    assert row["benchmark_gate_artifacts_present"] is True
    assert row["benchmark_gate_artifacts_ready"] is False
    assert "benchmark_gate_artifacts_not_all_ready" in row["blockers"]


def test_checkpoint_preflight_cli_writes_outputs(tmp_path: Path) -> None:
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "model.pth").write_bytes(b"weights")
    out_json = tmp_path / "preflight.json"
    out_csv = tmp_path / "preflight.csv"
    out_md = tmp_path / "preflight.md"

    mod.main(
        [
            "--models-dir",
            str(models_dir),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["candidate_checkpoint_count"] == 1
    assert "checkpoint_path" in out_csv.read_text(encoding="utf-8")
    assert "Residual Production Checkpoint Preflight" in out_md.read_text(encoding="utf-8")
