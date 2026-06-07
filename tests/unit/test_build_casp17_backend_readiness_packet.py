from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_probe(path: Path, probe: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(probe, indent=2), encoding="utf-8")


def _run_builder(tmp_path: Path, probe: dict) -> dict:
    probe_json = tmp_path / "probe.json"
    out_json = tmp_path / "readiness.json"
    _write_probe(probe_json, probe)
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_backend_readiness_packet.py"),
            "--probe-json",
            str(probe_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(tmp_path / "readiness.csv"),
            "--out-md",
            str(tmp_path / "readiness.md"),
        ],
        cwd=ROOT,
        check=True,
    )
    return json.loads(out_json.read_text(encoding="utf-8"))


def test_backend_readiness_reports_rocm_gpu_without_backend(tmp_path: Path) -> None:
    payload = _run_builder(
        tmp_path,
        {
            "commands": {"rocm-smi": "/usr/local/bin/rocm-smi", "rocminfo": "/usr/bin/rocminfo"},
            "python_modules": {"torch": True, "esm": False, "transformers": False, "colabfold": False, "jax": False},
            "torch": {
                "present": True,
                "version": "2.6.0+rocm6.1",
                "cuda_available": True,
                "device_count": 1,
                "device_names": ["AMD Radeon RX 6900 XT"],
            },
            "rocm": {"rocm_smi_present": True, "rocminfo_present": True},
            "nvidia": {"nvidia_smi_present": False},
        },
    )

    summary = payload["summary"]
    assert summary["accelerator_status"] == "rocm_gpu_ready"
    assert summary["backend_status"] == "rocm_gpu_without_structure_backend"
    assert summary["ready_for_launch_packet"] is False
    assert "missing_structure_prediction_backend" in summary["blockers"]
    lanes = [row["lane"] for row in payload["recommendations"]]
    assert "attach_existing_structure_with_provenance" in lanes
    assert "rocm_esmfold_environment_candidate" in lanes
    attach_row = next(row for row in payload["recommendations"] if row["lane"] == "attach_existing_structure_with_provenance")
    assert "build_casp17_existing_structure_intake_builder.py" in attach_row["command"]


def test_backend_readiness_accepts_detected_cli_backend(tmp_path: Path) -> None:
    payload = _run_builder(
        tmp_path,
        {
            "commands": {"colabfold_batch": "/opt/cf/colabfold_batch", "nvidia-smi": "/usr/bin/nvidia-smi"},
            "python_modules": {"torch": True, "jax": True, "colabfold": True},
            "torch": {
                "present": True,
                "version": "2.6.0+cu124",
                "cuda_available": True,
                "device_count": 1,
                "device_names": ["NVIDIA RTX 4090"],
            },
            "rocm": {"rocm_smi_present": False, "rocminfo_present": False},
            "nvidia": {"nvidia_smi_present": True},
        },
    )

    summary = payload["summary"]
    assert summary["accelerator_status"] == "cuda_gpu_ready"
    assert summary["backend_status"] == "backend_cli_ready"
    assert summary["selected_backend"] == "colabfold_batch"
    assert summary["ready_for_launch_packet"] is True
    assert summary["blockers"] == []
    lanes = [row["lane"] for row in payload["recommendations"]]
    assert "attach_existing_structure_with_provenance" in lanes


def test_backend_readiness_blocks_cpu_only_without_backend(tmp_path: Path) -> None:
    payload = _run_builder(
        tmp_path,
        {
            "commands": {},
            "python_modules": {"torch": True},
            "torch": {"present": True, "version": "2.6.0", "cuda_available": False, "device_count": 0, "device_names": []},
            "rocm": {"rocm_smi_present": False, "rocminfo_present": False},
            "nvidia": {"nvidia_smi_present": False},
        },
    )

    summary = payload["summary"]
    assert summary["accelerator_status"] == "gpu_not_detected"
    assert summary["backend_status"] == "backend_missing"
    lanes = [row["lane"] for row in payload["recommendations"]]
    assert "gpu_enablement_first" in lanes
