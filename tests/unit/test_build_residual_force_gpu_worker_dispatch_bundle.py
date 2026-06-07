from __future__ import annotations

import json
import tarfile
from pathlib import Path

from tools.product import build_residual_force_gpu_worker_dispatch_bundle as mod


def _dispatch_manifest(tmp_path: Path) -> dict:
    handoff = tmp_path / "handoff.json"
    queue = tmp_path / "queue.csv"
    native = tmp_path / "native.pdb"
    tool = tmp_path / "tool.py"
    handoff.write_text('{"summary": {"gpu_worker_handoff_ready": true}}\n', encoding="utf-8")
    queue.write_text("queue_id,native_pdb_path\nq1,native.pdb\n", encoding="utf-8")
    native.write_text("ATOM      1  CA  GLY A   1       0.0     0.0     0.0  1.00 10.00           C\n", encoding="utf-8")
    tool.write_text("print('ok')\n", encoding="utf-8")
    return {
        "summary": {
            "status": "residual_force_gpu_worker_dispatch_manifest_ready",
            "dispatch_manifest_ready": True,
            "local_artifact_missing_count": 0,
            "native_pdb_dependency_count": 1,
            "native_pdb_missing_count": 0,
            "queue_rows": 1,
            "outbound_artifact_count": 3,
            "inbound_artifact_count": 5,
            "acceptance_contract": {"return_receipt_ready_key": "gpu_worker_return_receipt_ready"},
            "tiny_pilot_command": "python3 tools/generate_ligand_trajectory_engine.py --max-jobs 2",
            "full_regeneration_command": "python3 tools/generate_ligand_trajectory_engine.py --prod-mode",
            "post_run_validation_commands": ["python3 tools/build_residual_force_gpu_worker_return_receipt.py"],
            "post_run_validation_command_count": 1,
        },
        "rows": [
            {
                "artifact": str(handoff),
                "role": "dispatch_source",
                "local_file_reference": True,
                "exists_now": True,
            },
            {
                "artifact": str(queue),
                "role": "outbound_to_gpu_worker",
                "local_file_reference": True,
                "exists_now": True,
            },
            {
                "artifact": str(tool),
                "role": "outbound_to_gpu_worker",
                "local_file_reference": True,
                "exists_now": True,
            },
            {
                "artifact": str(native),
                "role": "native_pdb_dependency",
                "local_file_reference": True,
                "exists_now": True,
            },
        ],
    }


def test_gpu_worker_dispatch_bundle_creates_tar_from_manifest_rows(tmp_path: Path) -> None:
    out_tar = tmp_path / "dispatch_bundle.tar.gz"
    payload = mod.build_payload(
        dispatch_manifest=_dispatch_manifest(tmp_path),
        dispatch_path=str(tmp_path / "dispatch.json"),
        out_tar=str(out_tar),
    )
    summary = payload["summary"]

    assert summary["status"] == "residual_force_gpu_worker_dispatch_bundle_ready"
    assert summary["dispatch_bundle_ready"] is True
    assert summary["dispatch_manifest_ready"] is True
    assert summary["bundle_tar_exists"] is True
    assert summary["bundle_tar_size_bytes"] > 0
    assert len(summary["bundle_tar_sha256"]) == 64
    assert summary["bundle_member_count"] == 4
    assert summary["source_artifact_count"] == 4
    assert summary["local_artifact_missing_count"] == 0
    assert summary["native_pdb_dependency_count"] == 1
    assert summary["native_pdb_missing_count"] == 0
    assert summary["queue_rows"] == 1
    assert summary["acceptance_contract"]["return_receipt_ready_key"] == "gpu_worker_return_receipt_ready"
    assert summary["execution_enabled"] is False
    assert summary["full_regeneration_executed"] is False
    assert summary["model_promoted"] is False
    assert payload["blockers"] == []

    with tarfile.open(out_tar, "r:gz") as tar:
        members = set(tar.getnames())
    assert members == {row["bundle_arcname"] for row in payload["rows"]}
    assert all(row["included_in_bundle"] is True for row in payload["rows"])
    assert all(row["execution_enabled"] is False for row in payload["rows"])


def test_gpu_worker_dispatch_bundle_blocks_when_manifest_not_ready(tmp_path: Path) -> None:
    out_tar = tmp_path / "blocked_bundle.tar.gz"
    manifest = _dispatch_manifest(tmp_path)
    manifest["summary"]["dispatch_manifest_ready"] = False

    payload = mod.build_payload(
        dispatch_manifest=manifest,
        dispatch_path=str(tmp_path / "dispatch.json"),
        out_tar=str(out_tar),
    )

    assert payload["summary"]["status"] == "blocked_residual_force_gpu_worker_dispatch_bundle"
    assert payload["summary"]["dispatch_bundle_ready"] is False
    assert payload["summary"]["bundle_tar_exists"] is False
    assert payload["summary"]["bundle_member_count"] == 0
    assert payload["summary"]["source_artifact_count"] == 4
    assert {"code": "dispatch_manifest_not_ready"} in payload["blockers"]
    assert not out_tar.exists()


def test_gpu_worker_dispatch_bundle_cli_writes_outputs(tmp_path: Path) -> None:
    dispatch_json = tmp_path / "dispatch.json"
    out_tar = tmp_path / "dispatch_bundle.tar.gz"
    out_json = tmp_path / "dispatch_bundle.json"
    out_csv = tmp_path / "dispatch_bundle.csv"
    out_md = tmp_path / "dispatch_bundle.md"
    dispatch_json.write_text(json.dumps(_dispatch_manifest(tmp_path)) + "\n", encoding="utf-8")

    mod.main(
        [
            "--dispatch-json",
            str(dispatch_json),
            "--out-tar",
            str(out_tar),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["dispatch_bundle_ready"] is True
    assert out_tar.exists()
    assert out_csv.read_text(encoding="utf-8").startswith("artifact,")
    assert out_md.read_text(encoding="utf-8").startswith("# Residual Force GPU Worker Dispatch Bundle")
