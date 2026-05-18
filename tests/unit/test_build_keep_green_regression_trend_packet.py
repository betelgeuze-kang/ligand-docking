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
        lane_history_payloads=[],
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


def test_build_keep_green_regression_trend_packet_uses_lane_history_for_non_nightly_lanes() -> None:
    nightly_gate, viewer_refresh, wetlab_gate, refresh = _green_payloads()
    lane_history = []
    for lane_id in ["viewer", "wetlab", "refresh"]:
        for index in range(1, 4):
            lane_history.append(
                {
                    "lane_id": lane_id,
                    "run_label": f"sample_{index}",
                    "generated_at_local": f"2026-05-1{index}T00:00:00",
                    "pass": True,
                    "artifact": f"runs/{lane_id}_current.md",
                }
            )

    payload = mod.build_payload(
        nightly_gate,
        viewer_refresh,
        wetlab_gate,
        refresh,
        nightly_history_payloads=[
            {"run_label": "sample_1", "generated_at_local": "2026-05-11T00:00:00", "pass": True},
            {"run_label": "sample_2", "generated_at_local": "2026-05-12T00:00:00", "pass": True},
            {"run_label": "sample_3", "generated_at_local": "2026-05-13T00:00:00", "pass": True},
        ],
        lane_history_payloads=lane_history,
    )

    summary = payload["summary"]
    rows = {row["lane_id"]: row for row in payload["rows"]}
    assert summary["sufficient_repeated_history"] is True
    assert summary["commercial_trend_status"] == "sufficient_repeated_history"
    assert summary["repeated_history_ready_lane_count"] == 4
    assert summary["insufficient_history_lane_count"] == 0
    assert summary["lane_history_sample_count"] == 9
    assert rows["viewer"]["repeated_history_ready"] is True
    assert rows["wetlab"]["recent_pass_streak"] == 3
    assert rows["refresh"]["status"] == "keep_green_history_ready"


def test_keep_green_history_accepts_tagged_smoke_top_level_and_skips_stage_children(
    tmp_path: Path, monkeypatch
) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    (runs / "ligand_htvs_nightly_2026-05-13_goal_closure_summary.json").write_text(
        json.dumps(
            {
                "generated_at_local": "2026-05-13T22:50:53",
                "run_scope": "smoke",
                "pass": True,
                "service_result": {"status": "ok", "error_code": "HTVS_OK"},
                "stages": {
                    "stage2_trajectory_generation": {"pass": True},
                    "stage6_operational_gate": {"pass": True},
                },
            }
        ),
        encoding="utf-8",
    )
    (runs / "ligand_htvs_nightly_2026-05-13_goal_closure_stage5_ranking_summary.json").write_text(
        json.dumps(
            {
                "generated_at_local": "2026-05-13T22:50:53",
                "pass": True,
                "metrics": {"mean_min_distance_A": 2.26},
            }
        ),
        encoding="utf-8",
    )

    rows = mod._load_nightly_history_from_runs(limit=10)

    assert [row["artifact"] for row in rows] == [
        "runs/ligand_htvs_nightly_2026-05-13_goal_closure_summary.json"
    ]
    assert rows[0]["run_label"] == "2026-05-13_goal_closure"
    assert rows[0]["pass"] is True


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
    assert payload["summary"]["wetlab_current_green"] is True
    assert payload["summary"]["commercial_trend_status"] == "baseline_green_needs_repeated_history"
    assert payload["rows"][0]["lane_id"] == "nightly"
    assert out_csv.exists()
    assert out_md.exists()
