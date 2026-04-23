from __future__ import annotations

import json
from pathlib import Path

from tools import build_wetlab_stk17b_exploratory_trace as mod


def test_build_wetlab_stk17b_exploratory_trace_separates_gate45_success_from_standard_auto_holds(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    base = tmp_path / "runs" / "wetlab_broad_screen_throughput" / "stk17b_drak2"
    for shard_id in ("17_of_20", "18_of_20", "19_of_20", "20_of_20"):
        (base / shard_id).mkdir(parents=True, exist_ok=True)

    (base / "17_of_20" / "throughput_run_gate45_summary.json").write_text(
        json.dumps(
            {
                "service_result": {"status": "ok", "error_code": "HTVS_OK"},
                "stages": {
                    "stage6_operational_gate": {
                        "pass": True,
                        "mean_min_distance_A": 4.397296540460387,
                        "failed_metrics": [{"metric": "mean_min_distance_A", "value": 4.397296540460387, "threshold": 4.5}],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    for shard_id, metric in (("18_of_20", 4.407883242584859), ("19_of_20", 4.407804478880733), ("20_of_20", 4.391232775836049)):
        (base / shard_id / "throughput_run_summary.json").write_text(
            json.dumps(
                {
                    "service_result": {"status": "error", "error_code": "HTVS_GATE_FAILED", "failed_stage": "stage6_operational_gate"},
                    "stages": {
                        "stage6_operational_gate": {
                            "pass": False,
                            "mean_min_distance_A": metric,
                            "failed_metrics": [{"metric": "mean_min_distance_A", "value": metric, "threshold": 2.5}],
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

    payload = mod.build_payload(
        {
            "rows": [
                {"target_id": "STK17B (DRAK2)", "shard_id": "17_of_20", "queue_status": "result_ready", "notes": "auto_complete_from_summary_watcher_runtime_validation_only"},
                {"target_id": "STK17B (DRAK2)", "shard_id": "18_of_20", "queue_status": "explicit_hold", "notes": "auto_hold_from_primary_watcher_runtime_validation_only"},
                {"target_id": "STK17B (DRAK2)", "shard_id": "19_of_20", "queue_status": "explicit_hold", "notes": "auto_hold_from_primary_watcher_runtime_validation_only"},
                {"target_id": "STK17B (DRAK2)", "shard_id": "20_of_20", "queue_status": "explicit_hold", "notes": "auto_hold_from_primary_watcher_runtime_validation_only"},
            ]
        },
        {
            "summary": {
                "target_id": "STK17B (DRAK2)",
                "shard_id": "17_of_20",
                "campaign_start_shard_id": "13_of_20",
                "selected_command_kind": "throughput_preflight_tuned_gate45",
                "selected_threshold_A": 4.5,
            }
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_stk17b_exploratory_trace_ready"
    assert summary["exploratory_success_shard_id"] == "17_of_20"
    assert summary["exploratory_success_command_family"] == "gate45_exploratory"
    assert summary["post_success_followup_shard_count"] == 3
    assert summary["post_success_standard_auto_shard_count"] == 3
    assert summary["post_success_hold_shard_count"] == 3

    rows = {row["shard_id"]: row for row in payload["rows"]}
    assert rows["17_of_20"]["command_family"] == "gate45_exploratory"
    assert rows["17_of_20"]["launch_basis"] == "manual_exploratory_retry"
    assert rows["17_of_20"]["service_status"] == "ok"
    assert rows["17_of_20"]["threshold_observed_A"] == 4.5
    assert rows["18_of_20"]["command_family"] == "standard_auto"
    assert rows["18_of_20"]["launch_basis"] == "watcher_autostart_after_exploratory_success_default_lane"
    assert rows["18_of_20"]["service_status"] == "error"
    assert rows["18_of_20"]["error_code"] == "HTVS_GATE_FAILED"
    assert rows["18_of_20"]["failed_stage"] == "stage6_operational_gate"
    assert rows["18_of_20"]["threshold_observed_A"] == 2.5


def test_build_wetlab_stk17b_exploratory_trace_marks_gate45_followup_reruns(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    base = tmp_path / "runs" / "wetlab_broad_screen_throughput" / "stk17b_drak2"
    for shard_id in ("17_of_20", "18_of_20", "19_of_20", "20_of_20"):
        (base / shard_id).mkdir(parents=True, exist_ok=True)

    metrics = {
        "17_of_20": 4.397296540460387,
        "18_of_20": 4.407883242584859,
        "19_of_20": 4.407804478880733,
        "20_of_20": 4.391232775836049,
    }
    for shard_id, metric in metrics.items():
        (base / shard_id / "throughput_run_gate45_summary.json").write_text(
            json.dumps(
                {
                    "service_result": {"status": "ok", "error_code": "HTVS_OK"},
                    "stages": {
                        "stage6_operational_gate": {
                            "pass": True,
                            "mean_min_distance_A": metric,
                            "failed_metrics": [{"metric": "mean_min_distance_A", "value": metric, "threshold": 4.5}],
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

    payload = mod.build_payload(
        {
            "rows": [
                {"target_id": "STK17B (DRAK2)", "shard_id": "17_of_20", "queue_status": "result_ready", "notes": "manual_exploratory_retry"},
                {"target_id": "STK17B (DRAK2)", "shard_id": "18_of_20", "queue_status": "result_ready", "notes": "manual_exploratory_followup_retry"},
                {"target_id": "STK17B (DRAK2)", "shard_id": "19_of_20", "queue_status": "result_ready", "notes": "manual_exploratory_followup_retry"},
                {"target_id": "STK17B (DRAK2)", "shard_id": "20_of_20", "queue_status": "result_ready", "notes": "manual_exploratory_followup_retry"},
            ]
        },
        {
            "summary": {
                "target_id": "STK17B (DRAK2)",
                "campaign_start_shard_id": "13_of_20",
                "shard_id": "17_of_20",
                "selected_command_kind": "throughput_preflight_tuned_gate45",
                "selected_threshold_A": 4.5,
            }
        },
    )

    summary = payload["summary"]
    assert summary["post_success_standard_auto_shard_count"] == 0
    rows = {row["shard_id"]: row for row in payload["rows"]}
    assert rows["18_of_20"]["command_family"] == "gate45_exploratory"
    assert rows["18_of_20"]["launch_basis"] == "manual_exploratory_followup_retry"
    assert rows["20_of_20"]["launch_basis"] == "manual_exploratory_followup_retry"
