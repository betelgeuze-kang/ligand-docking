from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_append_keep_green_lane_history_cli(tmp_path: Path) -> None:
    nightly = tmp_path / "nightly.json"
    viewer = tmp_path / "viewer.json"
    wetlab = tmp_path / "wetlab.json"
    refresh = tmp_path / "refresh.json"
    history = tmp_path / "history.jsonl"
    out_json = tmp_path / "append.json"
    out_md = tmp_path / "append.md"

    _write_json(
        nightly,
        {
            "summary": {
                "status": "nightly_gate_green",
                "downstream_execute_gate_pass": True,
                "stage6_gate_failed": False,
                "gate_failed_metric_count": 0,
            }
        },
    )
    _write_json(
        viewer,
        {
            "overall_ok": True,
            "summary": {
                "compare_writeback_wrapper_gap_count": 0,
                "compare_writeback_mesh_probe_unavailable_count": 0,
            },
        },
    )
    _write_json(
        wetlab,
        {
            "summary": {
                "selected_allatom_wetlab_gate_pass": True,
                "selected_allatom_final_gate_pass": True,
                "hard_block_count": 0,
                "semi_hard_block_count": 0,
                "missing_metric_count": 0,
            }
        },
    )
    _write_json(refresh, {"summary": {"overall_ok": True, "failed_count": 0}})

    subprocess.run(
        [
            sys.executable,
            "tools/append_keep_green_lane_history.py",
            "--nightly-gate-json",
            str(nightly),
            "--viewer-refresh-json",
            str(viewer),
            "--wetlab-gate-json",
            str(wetlab),
            "--refresh-json",
            str(refresh),
            "--history-jsonl",
            str(history),
            "--run-label",
            "sample_1",
            "--generated-at-local",
            "2026-05-11T00:00:00+09:00",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in history.read_text(encoding="utf-8").splitlines()]
    assert payload["summary"]["lane_count"] == 4
    assert payload["summary"]["lane_pass_count"] == 4
    assert payload["summary"]["appended_row_count"] == 4
    assert {row["lane_id"] for row in rows} == {"nightly", "viewer", "wetlab", "refresh"}
    assert out_md.exists()
