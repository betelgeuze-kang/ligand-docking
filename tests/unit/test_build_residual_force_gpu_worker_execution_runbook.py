from __future__ import annotations

import json
import os
from pathlib import Path

from tools.product import build_residual_force_gpu_worker_execution_runbook as mod


def _dispatch_bundle_packet() -> dict[str, object]:
    return {
        "summary": {
            "status": "residual_force_gpu_worker_dispatch_bundle_ready",
            "dispatch_bundle_ready": True,
            "bundle_tar_path": "runs/residual_force_gpu_worker_dispatch_bundle_current.tar.gz",
            "bundle_tar_exists": True,
            "bundle_tar_sha256": "abc123",
            "queue_rows": 768,
            "tiny_pilot_command": "python3 tools/generate_ligand_trajectory_engine.py --frames 4",
            "full_regeneration_command": (
                "python3 tools/generate_ligand_trajectory_engine.py --frames 120 --prod-mode"
            ),
            "acceptance_contract": {
                "worker_rocm_manifest_completion_rule": (
                    "manifest_ready=true;rocm_stack_detected=true;torch_rocm_ready=true;"
                    "amd_gpu_detected=true;visible_device_count>0"
                ),
                "post_return_validation_command": (
                    "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
                ),
                "inbound_artifacts": [
                    "runs/rocm_environment_manifest_current.json",
                    "runs/residual_force_trajectory_regeneration_current_summary.json",
                    "runs/residual_force_trajectory_regeneration_current_manifest.csv",
                    "regenerated NPZ bundles referenced by returned manifest NPZ path columns",
                    (
                        "runs/residual_force_trajectory_regeneration_execution_probe_current.json "
                        "after rerun on the returned pilot/full run evidence"
                    ),
                ],
            },
        },
        "rows": [],
        "blockers": [],
    }


def test_build_payload_writes_worker_runbook_script(tmp_path: Path) -> None:
    out_sh = tmp_path / "worker_runbook.sh"
    out_packager_sh = tmp_path / "return_packager.sh"

    payload = mod.build_payload(
        dispatch_bundle=_dispatch_bundle_packet(),
        dispatch_bundle_path="runs/residual_force_gpu_worker_dispatch_bundle_current.json",
        out_sh=str(out_sh),
        out_return_packager_sh=str(out_packager_sh),
        return_bundle_tar="runs/test_return_bundle.tar.gz",
    )
    summary = payload["summary"]

    assert summary["status"] == "residual_force_gpu_worker_execution_runbook_ready"
    assert summary["execution_runbook_ready"] is True
    assert summary["dispatch_bundle_ready"] is True
    assert summary["worker_script_exists"] is True
    assert summary["worker_script_executable"] is True
    assert summary["return_packager_script_exists"] is True
    assert summary["return_packager_script_executable"] is True
    assert summary["return_bundle_tar_path"] == "runs/test_return_bundle.tar.gz"
    assert summary["return_packager_command"] == f"bash {out_packager_sh}"
    assert summary["manifest_npz_path_columns"] == [
        "expected_regenerated_trajectory_npz",
        "trajectory_npz",
        "output_npz",
        "generated_npz",
    ]
    assert os.access(out_sh, os.X_OK)
    assert os.access(out_packager_sh, os.X_OK)
    assert summary["step_count"] == 8
    assert summary["worker_executable_step_count"] == 6
    assert summary["required_return_artifact_count"] == 5
    assert summary["execution_enabled"] is False
    assert summary["full_regeneration_executed"] is False
    assert summary["external_state_mutated"] is False
    assert not payload["blockers"]

    script = out_sh.read_text(encoding="utf-8")
    assert "sha256sum -c -" in script
    assert "python3 tools/build_rocm_environment_manifest.py" in script
    assert "python3 tools/generate_ligand_trajectory_engine.py --frames 120 --prod-mode" in script
    assert "Required return artifacts" in script

    packager = out_packager_sh.read_text(encoding="utf-8")
    assert "residual_force_trajectory_regeneration_current_manifest.csv" in packager
    assert "expected_regenerated_trajectory_npz" in packager
    assert "tar -czf" in packager
    assert "sha256sum" in packager


def test_main_writes_json_csv_md_and_script(tmp_path: Path) -> None:
    in_json = tmp_path / "dispatch_bundle.json"
    out_json = tmp_path / "runbook.json"
    out_csv = tmp_path / "runbook.csv"
    out_md = tmp_path / "runbook.md"
    out_sh = tmp_path / "runbook.sh"
    out_packager_sh = tmp_path / "return_packager.sh"
    in_json.write_text(json.dumps(_dispatch_bundle_packet()) + "\n", encoding="utf-8")

    mod.main(
        [
            "--dispatch-bundle-json",
            str(in_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
            "--out-sh",
            str(out_sh),
            "--out-return-packager-sh",
            str(out_packager_sh),
            "--return-bundle-tar",
            "runs/test_return_bundle.tar.gz",
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["execution_runbook_ready"] is True
    assert out_csv.read_text(encoding="utf-8").startswith("step_id,")
    assert "# Residual Force GPU Worker Execution Runbook" in out_md.read_text(encoding="utf-8")
    assert out_sh.exists()
    assert out_packager_sh.exists()
    assert payload["summary"]["return_packager_script_path"] == str(out_packager_sh)


def test_blocked_without_ready_dispatch_bundle(tmp_path: Path) -> None:
    payload = mod.build_payload(
        dispatch_bundle={"summary": {"dispatch_bundle_ready": False}},
        out_sh=str(tmp_path / "runbook.sh"),
        out_return_packager_sh=str(tmp_path / "return_packager.sh"),
    )

    assert payload["summary"]["status"] == "blocked_residual_force_gpu_worker_execution_runbook"
    assert payload["summary"]["execution_runbook_ready"] is False
    assert payload["summary"]["worker_script_exists"] is False
    assert payload["summary"]["return_packager_script_exists"] is False
    assert payload["blockers"] == [{"code": "dispatch_bundle_not_ready"}]
