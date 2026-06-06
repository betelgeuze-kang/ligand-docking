from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools import build_amd_hardware_throughput_measurements as mod


def _rocm_ready() -> dict[str, object]:
    return {
        "summary": {
            "status": "rocm_environment_manifest_ready",
            "manifest_ready": True,
            "device_names": ["AMD Radeon RX 6900 XT"],
        }
    }


def _runner(**kwargs: Any) -> dict[str, object]:
    return {
        "status": "amd_hardware_throughput_measurements_ready",
        "measurement_ready": True,
        "device": "cuda",
        "device_name": "AMD Radeon RX 6900 XT",
        "torch_version": "2.4.0+rocm6.0",
        "torch_hip_version": "6.0.2",
        "ligands_per_hour": 10000.0,
        "poses_per_sec": 75.0,
        "score_evaluations_per_sec": 750.0,
        "vram_gb_per_1k_ligands": 0.5,
        "cpu_vs_rocm_speedup": 2.5,
        "failure_rate": 0.0,
        "fixed_seed_reproducible": True,
        "benchmark_kind": "fake_rocm_smoke",
        "ligand_count": kwargs["ligand_count"],
        "poses_per_ligand": kwargs["poses_per_ligand"],
        "feature_dim": kwargs["feature_dim"],
        "iterations": kwargs["iterations"],
        "warmup_iterations": kwargs["warmup_iterations"],
        "seed": kwargs["seed"],
    }


def test_build_amd_hardware_throughput_measurements_ready() -> None:
    payload = mod.build_amd_hardware_throughput_measurements(
        rocm_manifest_packet=_rocm_ready(),
        benchmark_runner=_runner,
        ligand_count=8,
        poses_per_ligand=4,
        iterations=2,
    )

    summary = payload["summary"]
    assert summary["status"] == "amd_hardware_throughput_measurements_ready"
    assert summary["measurement_ready"] is True
    assert summary["rocm_environment_manifest_ready"] is True
    assert summary["commercial_compute_default"] == "rocm_hip"
    assert summary["ligands_per_hour"] == 10000.0
    assert summary["fixed_seed_reproducible"] is True
    assert summary["benchmark_executed"] is True
    assert summary["external_state_mutated"] is False


def test_build_amd_hardware_throughput_measurements_blocks_without_rocm_manifest() -> None:
    payload = mod.build_amd_hardware_throughput_measurements(
        rocm_manifest_packet={"summary": {"status": "blocked_rocm_environment_manifest", "manifest_ready": False}},
        benchmark_runner=_runner,
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_amd_hardware_throughput_measurements"
    assert summary["measurement_ready"] is False
    assert summary["benchmark_executed"] is False
    assert summary["error_count"] == 1


def test_amd_hardware_throughput_measurements_cli_writes_blocked_outputs(tmp_path: Path) -> None:
    manifest = tmp_path / "rocm.json"
    out_json = tmp_path / "measurements.json"
    out_md = tmp_path / "measurements.md"
    manifest.write_text(json.dumps({"summary": {"status": "blocked_rocm_environment_manifest", "manifest_ready": False}}) + "\n", encoding="utf-8")

    mod.main(["--rocm-manifest-json", str(manifest), "--out-json", str(out_json), "--out-md", str(out_md)])

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "blocked_amd_hardware_throughput_measurements"
    assert "AMD Hardware Throughput Measurements" in out_md.read_text(encoding="utf-8")
