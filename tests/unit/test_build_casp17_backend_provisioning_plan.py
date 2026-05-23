from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_readiness(path: Path, *, summary: dict, probe: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"summary": summary, "probe": probe}, indent=2), encoding="utf-8")


def _run_builder(tmp_path: Path, *, summary: dict, probe: dict) -> dict:
    readiness_json = tmp_path / "readiness.json"
    out_json = tmp_path / "provisioning.json"
    _write_readiness(readiness_json, summary=summary, probe=probe)
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_backend_provisioning_plan.py"),
            "--backend-readiness-json",
            str(readiness_json),
            "--env-path",
            str(tmp_path / "isolated-env"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(tmp_path / "provisioning.csv"),
            "--out-md",
            str(tmp_path / "provisioning.md"),
        ],
        cwd=ROOT,
        check=True,
    )
    return json.loads(out_json.read_text(encoding="utf-8"))


def test_provisioning_plan_keeps_rocm_backend_missing_fail_closed(tmp_path: Path) -> None:
    payload = _run_builder(
        tmp_path,
        summary={
            "backend_status": "rocm_gpu_without_structure_backend",
            "accelerator_status": "rocm_gpu_ready",
            "device_names": ["AMD Radeon RX 6900 XT"],
            "blockers": ["missing_structure_prediction_backend"],
        },
        probe={
            "commands": {"python3": "/usr/bin/python3", "pip": "/usr/bin/pip", "rocm-smi": "/usr/bin/rocm-smi"},
            "python_modules": {"torch": True, "esm": False, "transformers": False},
        },
    )

    summary = payload["summary"]
    assert summary["plan_status"] == "blocked_until_rocm_structure_backend_is_wired"
    assert summary["ready_to_launch_now"] is False
    assert summary["cpu_fallback_allowed"] is False
    assert summary["installation_executed"] is False
    assert summary["backend_readiness_fingerprint"]["present"] is True
    assert summary["backend_readiness_fingerprint"]["sha256"]
    assert "missing_structure_prediction_backend" in summary["blockers"]
    lanes = [row["lane"] for row in payload["rows"]]
    assert "attach_existing_structure_with_provenance" in lanes
    assert "wire_custom_gpu_backend_command" in lanes
    assert "provision_isolated_rocm_pytorch_structure_backend" in lanes
    assert "colabfold_cuda_lane_on_rocm_host" in lanes
    attach_row = next(row for row in payload["rows"] if row["lane"] == "attach_existing_structure_with_provenance")
    assert "build_casp17_existing_structure_intake_builder.py" in attach_row["command_template"]


def test_provisioning_plan_marks_detected_cli_backend_ready(tmp_path: Path) -> None:
    payload = _run_builder(
        tmp_path,
        summary={
            "backend_status": "backend_cli_ready",
            "accelerator_status": "cuda_gpu_ready",
            "selected_backend": "colabfold_batch",
            "blockers": [],
        },
        probe={
            "commands": {
                "python3": "/usr/bin/python3",
                "pip": "/usr/bin/pip",
                "colabfold_batch": "/opt/colabfold/colabfold_batch",
            },
            "python_modules": {"torch": True, "colabfold": True, "jax": True},
        },
    )

    summary = payload["summary"]
    assert summary["plan_status"] == "backend_ready_no_provisioning_required"
    assert summary["ready_to_launch_now"] is True
    assert summary["blockers"] == []
    assert summary["installed_backend_commands"] == ["colabfold_batch"]
    lanes = [row["lane"] for row in payload["rows"]]
    assert "attach_existing_structure_with_provenance" in lanes
    assert "use_detected_colabfold_batch" in lanes


def test_provisioning_plan_blocks_cpu_fallback_when_gpu_missing(tmp_path: Path) -> None:
    payload = _run_builder(
        tmp_path,
        summary={
            "backend_status": "backend_missing",
            "accelerator_status": "gpu_not_detected",
            "blockers": ["missing_structure_prediction_backend"],
        },
        probe={"commands": {"python3": "/usr/bin/python3"}, "python_modules": {"torch": True}},
    )

    summary = payload["summary"]
    assert summary["plan_status"] == "blocked_gpu_or_backend_not_ready"
    assert summary["cpu_fallback_allowed"] is False
    assert "cpu_fallback_disallowed" in summary["blockers"]
    lanes = [row["lane"] for row in payload["rows"]]
    assert "gpu_runtime_enablement_first" in lanes


def test_provisioning_plan_missing_readiness_artifact_is_blocked(tmp_path: Path) -> None:
    out_json = tmp_path / "provisioning.json"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_backend_provisioning_plan.py"),
            "--backend-readiness-json",
            str(tmp_path / "missing.json"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(tmp_path / "provisioning.csv"),
            "--out-md",
            str(tmp_path / "provisioning.md"),
        ],
        cwd=ROOT,
        check=True,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))

    assert payload["summary"]["plan_status"] == "blocked_missing_readiness_artifact"
    assert payload["summary"]["backend_readiness_fingerprint"]["present"] is False
    assert "backend_readiness_artifact_missing" in payload["summary"]["blockers"]
