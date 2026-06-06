from __future__ import annotations

import json
from pathlib import Path

from tools import build_amd_hardware_throughput_scorecard as mod


def _rocm_ready() -> dict[str, object]:
    return {
        "summary": {
            "status": "rocm_environment_manifest_ready",
            "manifest_ready": True,
            "torch_rocm_ready": True,
            "visible_device_count": 1,
            "device_names": ["AMD Radeon RX 7900 XTX"],
        }
    }


def _measurements_ready() -> dict[str, object]:
    return {
        "summary": {
            "ligands_per_hour": 12000.0,
            "poses_per_sec": 80.0,
            "score_evaluations_per_sec": 25000.0,
            "vram_gb_per_1k_ligands": 1.8,
            "cpu_vs_rocm_speedup": 7.5,
            "failure_rate": 0.01,
            "fixed_seed_reproducible": True,
        }
    }


def test_build_amd_hardware_throughput_scorecard_ready() -> None:
    payload = mod.build_amd_hardware_throughput_scorecard(
        rocm_manifest_packet=_rocm_ready(),
        measurement_packet=_measurements_ready(),
    )

    summary = payload["summary"]
    assert summary["status"] == "amd_hardware_throughput_scorecard_ready"
    assert summary["scorecard_ready"] is True
    assert summary["measurement_metric_pass_count"] == 7
    assert summary["fail_count"] == 0
    assert summary["commercial_compute_default"] == "rocm_hip"
    assert summary["device_names"] == ["AMD Radeon RX 7900 XTX"]
    assert summary["benchmark_executed"] is False
    assert summary["external_state_mutated"] is False


def test_build_amd_hardware_throughput_scorecard_blocks_missing_metrics() -> None:
    payload = mod.build_amd_hardware_throughput_scorecard(
        rocm_manifest_packet=_rocm_ready(),
        measurement_packet={"summary": {"ligands_per_hour": 100.0}},
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_amd_hardware_throughput_scorecard"
    assert summary["scorecard_ready"] is False
    assert summary["measurement_metric_pass_count"] == 1
    assert summary["fail_count"] == 6


def test_amd_hardware_throughput_scorecard_cli_writes_outputs(tmp_path: Path) -> None:
    rocm_path = tmp_path / "rocm.json"
    measurements_path = tmp_path / "measurements.json"
    out_json = tmp_path / "scorecard.json"
    out_csv = tmp_path / "scorecard.csv"
    out_md = tmp_path / "scorecard.md"
    rocm_path.write_text(json.dumps(_rocm_ready()) + "\n", encoding="utf-8")
    measurements_path.write_text(json.dumps(_measurements_ready()) + "\n", encoding="utf-8")

    mod.main(
        [
            "--rocm-manifest-json",
            str(rocm_path),
            "--measurement-json",
            str(measurements_path),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["scorecard_ready"] is True
    assert "metric_id" in out_csv.read_text(encoding="utf-8")
    assert "AMD Hardware Throughput Scorecard" in out_md.read_text(encoding="utf-8")
