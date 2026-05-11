from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_keep_green_regression_trend_packet as mod


ROOT = Path(__file__).resolve().parents[2]


def _green_payloads() -> tuple[dict, dict, dict, dict]:
    nightly_gate = {
        "summary": {
            "packet_artifact": "runs/nightly_gate_burndown_packet_current.md",
            "status": "nightly_gate_green",
            "status_line": "nightly green",
            "downstream_execute_gate_pass": True,
            "stage6_gate_failed": False,
            "gate_failed_metric_count": 0,
        }
    }
    viewer_refresh = {
        "overall_ok": True,
        "summary": {
            "compare_writeback_wrapper_gap_count": 0,
            "compare_writeback_mesh_probe_unavailable_count": 0,
            "compare_writeback_geometry_burndown_status_line": "viewer green",
        },
    }
    wetlab_gate = {
        "summary": {
            "packet_artifact": "runs/wetlab_selected_allatom_gate_burndown_packet_current.md",
            "selected_allatom_wetlab_gate_pass": True,
            "selected_allatom_final_gate_pass": True,
            "hard_block_count": 0,
            "semi_hard_block_count": 0,
            "missing_metric_count": 0,
            "next_required_step": "wetlab green",
        }
    }
    refresh = {"summary": {"overall_ok": True, "failed_count": 0, "next_required_step": "refresh green"}}
    return nightly_gate, viewer_refresh, wetlab_gate, refresh


def test_build_keep_green_regression_trend_packet_marks_baseline_history_gap() -> None:
    nightly_gate, viewer_refresh, wetlab_gate, refresh = _green_payloads()
    payload = mod.build_payload(
        nightly_gate,
        viewer_refresh,
        wetlab_gate,
        refresh,
        nightly_history_payloads=[
            {"run_label": "sample_1", "generated_at_local": "2026-05-09T00:00:00", "pass": False},
            {"run_label": "sample_2", "generated_at_local": "2026-05-10T00:00:00", "pass": True},
            {"run_label": "sample_3", "generated_at_local": "2026-05-11T00:00:00", "pass": True},
        ],
    )

    summary = payload["summary"]
    rows = {row["lane_id"]: row for row in payload["rows"]}
    assert summary["all_current_green"] is True
    assert summary["sufficient_repeated_history"] is False
    assert summary["commercial_trend_status"] == "baseline_green_needs_repeated_history"
    assert summary["nightly_history_sample_count"] == 3
    assert summary["nightly_history_pass_count"] == 2
    assert summary["nightly_recent_pass_streak"] == 2
    assert rows["nightly"]["status"] == "keep_green_needs_more_history"
    assert rows["viewer"]["current_green"] is True
    assert rows["wetlab"]["current_green"] is True
    assert rows["refresh"]["current_green"] is True


def test_build_keep_green_regression_trend_packet_cli(tmp_path: Path) -> None:
    out_json = tmp_path / "keep_green_regression_trend_packet.json"
    out_csv = tmp_path / "keep_green_regression_trend_packet.csv"
    out_md = tmp_path / "keep_green_regression_trend_packet.md"

    subprocess.run(
        [
            sys.executable,
            "tools/build_keep_green_regression_trend_packet.py",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["packet_artifact"] == "runs/keep_green_regression_trend_packet_current.md"
    assert payload["summary"]["lane_count"] == 4
    assert payload["summary"]["all_current_green"] is True
    assert payload["rows"][0]["lane_id"] == "nightly"
    assert out_csv.exists()
    assert out_md.exists()
