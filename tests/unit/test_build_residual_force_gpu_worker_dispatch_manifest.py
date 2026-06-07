from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_residual_force_gpu_worker_dispatch_manifest as mod


def _handoff(tmp_path: Path) -> dict:
    queue_csv = tmp_path / "queue.csv"
    template_csv = tmp_path / "return_manifest_template.csv"
    summary_template = tmp_path / "summary_template.json"
    native_pdb = tmp_path / "native.pdb"
    tool = tmp_path / "tool.py"
    queue_csv.write_text(
        f"queue_id,expected_regenerated_trajectory_npz,native_pdb_path\nq1,out/q1.npz,{native_pdb}\n",
        encoding="utf-8",
    )
    template_csv.write_text("queue_id,status,operator_verified_npz_exists\nq1,OPERATOR_FILL,OPERATOR_FILL\n", encoding="utf-8")
    summary_template.write_text("{}\n", encoding="utf-8")
    native_pdb.write_text("ATOM      1  CA  GLY A   1       0.0     0.0     0.0  1.00 10.00           C\n", encoding="utf-8")
    tool.write_text("print('ok')\n", encoding="utf-8")
    return {
        "summary": {
            "gpu_worker_handoff_ready": True,
            "queue_rows": 1,
            "queue_csv": str(queue_csv),
            "queue_csv_sha256": "queue-sha",
            "operator_transfer_outbound_artifacts": [
                str(queue_csv),
                str(template_csv),
                str(summary_template),
                str(tool),
                "native PDB files referenced by regeneration_queue_csv.native_pdb_path",
            ],
            "operator_transfer_inbound_artifacts": [
                "runs/rocm_environment_manifest_current.json",
                "runs/residual_force_trajectory_regeneration_current_summary.json",
                "runs/residual_force_trajectory_regeneration_current_manifest.csv",
                "regenerated NPZ bundles referenced by returned manifest NPZ path columns",
                "runs/residual_force_trajectory_regeneration_execution_probe_current.json after rerun",
            ],
            "tiny_pilot_command": "python3 tools/generate_ligand_trajectory_engine.py --max-jobs 2",
            "full_regeneration_command": "python3 tools/generate_ligand_trajectory_engine.py --prod-mode",
            "post_run_validation_commands": [
                "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
                "python3 tools/build_residual_model_registry.py",
            ],
            "post_run_validation_command_count": 2,
            "operator_transfer_acceptance_artifact": "runs/residual_force_gpu_worker_return_receipt_current.json",
            "operator_transfer_acceptance_ready_key": "gpu_worker_return_receipt_ready",
            "operator_transfer_first_return_artifact": "runs/rocm_environment_manifest_current.json",
            "operator_transfer_return_manifest_artifact": (
                "runs/residual_force_trajectory_regeneration_current_manifest.csv"
            ),
            "worker_rocm_manifest_completion_rule": (
                "manifest_ready=true;rocm_stack_detected=true;torch_rocm_ready=true;"
                "amd_gpu_detected=true;visible_device_count>0"
            ),
            "operator_transfer_post_return_validation_command": (
                "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
            ),
            "return_summary_completion_rule": "processed_rows>=expected_queue_rows",
            "return_manifest_required_identity_rule": "queue_id or queue_row_fingerprint matches handoff queue",
        }
    }


def test_gpu_worker_dispatch_manifest_checks_local_handoff_artifacts(tmp_path: Path) -> None:
    handoff_json = tmp_path / "handoff.json"
    handoff_json.write_text(json.dumps(_handoff(tmp_path)) + "\n", encoding="utf-8")

    payload = mod.build_payload(handoff_package=_handoff(tmp_path), handoff_path=str(handoff_json))
    summary = payload["summary"]

    assert summary["status"] == "residual_force_gpu_worker_dispatch_manifest_ready"
    assert summary["dispatch_manifest_ready"] is True
    assert summary["handoff_package_ready"] is True
    assert summary["queue_rows"] == 1
    assert summary["outbound_artifact_count"] == 5
    assert summary["inbound_artifact_count"] == 5
    assert summary["local_artifact_missing_count"] == 0
    assert summary["native_pdb_dependency_count"] == 1
    assert summary["native_pdb_missing_count"] == 0
    assert summary["acceptance_contract"]["return_receipt_ready_key"] == "gpu_worker_return_receipt_ready"
    assert "visible_device_count>0" in summary["worker_rocm_manifest_completion_rule"]
    assert "queue_row_fingerprint" in summary["return_manifest_required_identity_rule"]
    assert summary["execution_enabled"] is False
    assert summary["model_promoted"] is False
    assert any(row["role"] == "native_pdb_dependency" and row["exists_now"] is True for row in payload["rows"])


def test_gpu_worker_dispatch_manifest_blocks_missing_local_file(tmp_path: Path) -> None:
    handoff = _handoff(tmp_path)
    handoff["summary"]["operator_transfer_outbound_artifacts"].append(str(tmp_path / "missing.json"))

    payload = mod.build_payload(handoff_package=handoff, handoff_path=str(tmp_path / "handoff.json"))

    assert payload["summary"]["dispatch_manifest_ready"] is False
    assert payload["summary"]["local_artifact_missing_count"] == 2
    assert str(tmp_path / "missing.json") in payload["summary"]["local_artifact_missing"]


def test_gpu_worker_dispatch_manifest_cli_writes_outputs(tmp_path: Path) -> None:
    handoff_json = tmp_path / "handoff.json"
    out_json = tmp_path / "dispatch.json"
    out_csv = tmp_path / "dispatch.csv"
    out_md = tmp_path / "dispatch.md"
    handoff_json.write_text(json.dumps(_handoff(tmp_path)) + "\n", encoding="utf-8")

    mod.main(
        [
            "--handoff-json",
            str(handoff_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["dispatch_manifest_ready"] is True
    assert out_csv.read_text(encoding="utf-8").startswith("artifact,")
    assert out_md.read_text(encoding="utf-8").startswith("# Residual Force GPU Worker Dispatch Manifest")
