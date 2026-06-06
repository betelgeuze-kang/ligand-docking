from __future__ import annotations

import json
from pathlib import Path

from tools import build_residual_force_trajectory_regeneration_execution_probe as mod


def _packet(summary: dict[str, object]) -> dict[str, object]:
    return {"summary": summary}


def test_execution_probe_blocks_gpu_unavailable_pilot() -> None:
    payload = mod.build_residual_force_trajectory_regeneration_execution_probe(
        regeneration_queue_packet=_packet({"regeneration_queue_execution_ready": True, "queue_rows": 2}),
        pilot_summary_packet={
            "processed_rows": 1,
            "ok_rows": 0,
            "failed_rows": 1,
            "aborted_early": True,
            "abort_reason": "RuntimeError: GPU-only mode enabled but CUDA is unavailable.",
            "force_backend_requested": "auto",
            "require_rust_hip": True,
            "backend_counts": {},
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_residual_force_trajectory_regeneration_execution_probe"
    assert summary["engine_runtime_ready"] is False
    assert summary["gpu_backend_unavailable"] is True
    assert "gpu_backend_available" in summary["blockers"]


def test_execution_probe_ready_after_successful_pilot() -> None:
    payload = mod.build_residual_force_trajectory_regeneration_execution_probe(
        regeneration_queue_packet=_packet({"regeneration_queue_execution_ready": True, "queue_rows": 2}),
        pilot_summary_packet={
            "processed_rows": 2,
            "ok_rows": 2,
            "failed_rows": 0,
            "aborted_early": False,
            "abort_reason": "",
            "backend_counts": {"rust_hip": 2},
        },
    )

    assert payload["summary"]["status"] == "residual_force_trajectory_regeneration_execution_probe_ready"
    assert payload["summary"]["engine_runtime_ready"] is True
    assert payload["summary"]["blockers"] == []


def test_execution_probe_cli_writes_outputs(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    pilot = tmp_path / "pilot.json"
    out_json = tmp_path / "probe.json"
    out_csv = tmp_path / "probe.csv"
    out_md = tmp_path / "probe.md"
    queue.write_text(json.dumps(_packet({"regeneration_queue_execution_ready": True, "queue_rows": 2})) + "\n", encoding="utf-8")
    pilot.write_text(
        json.dumps({"processed_rows": 1, "ok_rows": 0, "failed_rows": 1, "aborted_early": True, "abort_reason": "GPU-only mode enabled but CUDA is unavailable."}) + "\n",
        encoding="utf-8",
    )

    mod.main(
        [
            "--regeneration-queue-json",
            str(queue),
            "--pilot-summary-json",
            str(pilot),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["gpu_backend_unavailable"] is True
    assert "gpu_backend_available" in out_csv.read_text(encoding="utf-8")
    assert "Residual Force Trajectory Regeneration Execution Probe" in out_md.read_text(encoding="utf-8")
