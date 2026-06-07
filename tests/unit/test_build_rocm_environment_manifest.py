from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from tools import build_rocm_environment_manifest as mod


def _runner(cmd: Sequence[str], _timeout_seconds: int) -> dict[str, Any]:
    stdout = {
        "rocminfo": "Agent 2\n  Name: gfx1100\n",
        "rocm-smi": "GPU[0]: Card series: AMD Radeon RX 7900 XTX\nDriver version: 6.0.2\nVRAM Total Memory: 24560 MB\n",
        "hipcc": "HIP version: 6.0.2\n",
    }.get(cmd[0], "")
    return {
        "cmd": list(cmd),
        "available": True,
        "returncode": 0,
        "ok": True,
        "stdout_excerpt": stdout,
        "stderr_excerpt": "",
    }


def test_build_rocm_environment_manifest_ready_with_rocm_torch_probe() -> None:
    payload = mod.build_rocm_environment_manifest(
        env={
            "ROCM_PATH": "/opt/rocm-6.0.2",
            "HSA_OVERRIDE_GFX_VERSION": "11.0.0",
            "PYTORCH_ROCM_ARCH": "gfx1100",
            "TORCH_BLAS_PREFER_HIPBLASLT": "0",
        },
        command_runner=_runner,
        torch_probe={
            "present": True,
            "import_error": "",
            "version": "2.4.0+rocm6.0",
            "hip_version": "6.0.2",
            "cuda_available": True,
            "device_count": 1,
            "device_names": ["AMD Radeon RX 7900 XTX"],
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "rocm_environment_manifest_ready"
    assert summary["manifest_ready"] is True
    assert summary["commercial_compute_default"] == "rocm_hip"
    assert summary["cpu_fallback_available"] is True
    assert summary["rocm_version"] == "6.0.2"
    assert summary["torch_rocm_ready"] is True
    assert summary["device_names"] == ["AMD Radeon RX 7900 XTX"]
    assert summary["next_required_step"] == "Build AMD hardware throughput scorecard next."
    assert summary["gpu_visibility_diagnostic_packet_ready"] is True
    assert summary["gpu_visibility_diagnostic_command_count"] == 5
    assert "python3 tools/build_rocm_environment_manifest.py" in summary[
        "gpu_visibility_diagnostic_commands"
    ]
    assert any("torch.cuda.device_count" in command for command in summary["gpu_visibility_diagnostic_commands"])
    assert summary["gpu_visibility_diagnostic_required_fields"] == [
        "manifest_ready",
        "rocm_stack_detected",
        "torch_rocm_ready",
        "amd_gpu_detected",
        "visible_device_count",
        "device_names",
        "torch_version",
        "torch_hip_version",
    ]
    assert "visible_device_count>0" in summary["gpu_visibility_diagnostic_completion_rule"]
    assert summary["execution_enabled"] is False
    assert summary["benchmark_executed"] is False
    assert summary["external_state_mutated"] is False


def test_build_rocm_environment_manifest_keeps_gpu_visibility_as_next_step() -> None:
    payload = mod.build_rocm_environment_manifest(
        env={
            "ROCM_PATH": "/opt/rocm-6.0.2",
            "PYTORCH_ROCM_ARCH": "gfx1100",
        },
        command_runner=_runner,
        torch_probe={
            "present": True,
            "import_error": "",
            "version": "2.4.0+rocm6.0",
            "hip_version": "6.0.2",
            "cuda_available": False,
            "device_count": 0,
            "device_names": [],
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "rocm_environment_manifest_ready"
    assert summary["manifest_ready"] is True
    assert summary["torch_rocm_ready"] is False
    assert summary["visible_device_count"] == 0
    assert summary["gpu_visibility_torch_probe_command"].startswith("python3 -c")
    assert summary["next_required_step"] == (
        "Expose a visible ROCm/HIP AMD GPU device to PyTorch before production regeneration."
    )


def test_build_rocm_environment_manifest_blocks_without_rocm_torch() -> None:
    payload = mod.build_rocm_environment_manifest(
        env={},
        torch_probe={
            "present": False,
            "import_error": "ModuleNotFoundError",
            "version": "",
            "hip_version": "",
            "cuda_available": False,
            "device_count": 0,
            "device_names": [],
        },
        probe_commands=False,
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_rocm_environment_manifest"
    assert summary["manifest_ready"] is False
    assert summary["torch_rocm_ready"] is False
    assert summary["missing_manifest_field_count"] > 0


def test_rocm_environment_manifest_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    out_json = tmp_path / "rocm.json"
    out_md = tmp_path / "rocm.md"

    mod.main(["--skip-command-probes", "--out-json", str(out_json), "--out-md", str(out_md)])

    assert out_json.exists()
    assert out_md.exists()
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["packet_type"] == "rocm_environment_manifest"
    md = out_md.read_text(encoding="utf-8")
    assert "ROCm Environment Manifest" in md
    assert "GPU Visibility Diagnostics" in md
