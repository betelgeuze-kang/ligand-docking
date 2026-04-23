from __future__ import annotations

import json
from pathlib import Path

from tools import build_wetlab_stk17b_followup_review_surface as mod


def test_build_wetlab_stk17b_followup_review_surface_prefers_gate45_branch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    base = tmp_path / "runs" / "wetlab_broad_screen_throughput" / "stk17b_drak2"
    (base / "17_of_20").mkdir(parents=True, exist_ok=True)
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
        (base / shard_id).mkdir(parents=True, exist_ok=True)
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
            "summary": {
                "target_id": "STK17B (DRAK2)",
                "exploratory_success_shard_id": "17_of_20",
                "exploratory_success_threshold_A": 4.5,
            }
        },
        {
            "summary": {
                "followup_shard_ids": "18_of_20;19_of_20;20_of_20",
                "selected_threshold_A": 4.5,
            }
        },
        {
            "rows": [
                {"target_id": "STK17B (DRAK2)", "shard_id": "17_of_20", "queue_status": "result_ready", "execution_state": "result_ready", "notes": "ok"},
                {"target_id": "STK17B (DRAK2)", "shard_id": "18_of_20", "queue_status": "explicit_hold", "execution_state": "explicit_hold", "notes": "hold"},
                {"target_id": "STK17B (DRAK2)", "shard_id": "19_of_20", "queue_status": "explicit_hold", "execution_state": "explicit_hold", "notes": "hold"},
                {"target_id": "STK17B (DRAK2)", "shard_id": "20_of_20", "queue_status": "explicit_hold", "execution_state": "explicit_hold", "notes": "hold"},
            ]
        },
    )
    summary = payload["summary"]
    assert summary["decision"] == "branch_to_gate45_only_keep_default_closed"
    assert summary["default_lane_reopen_allowed"] is False
    assert summary["branch_to_gate45_only"] is True


def test_build_wetlab_stk17b_followup_review_surface_keeps_default_closed_after_gate45_followup_successes(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    base = tmp_path / "runs" / "wetlab_broad_screen_throughput" / "stk17b_drak2"
    metrics = {
        "17_of_20": 4.397296540460387,
        "18_of_20": 4.407883242584859,
        "19_of_20": 4.407804478880733,
        "20_of_20": 4.391232775836049,
    }
    for shard_id, metric in metrics.items():
        (base / shard_id).mkdir(parents=True, exist_ok=True)
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
            "summary": {
                "target_id": "STK17B (DRAK2)",
                "exploratory_success_shard_id": "17_of_20",
                "exploratory_success_threshold_A": 4.5,
            }
        },
        {
            "summary": {
                "followup_shard_ids": "18_of_20;19_of_20;20_of_20",
                "selected_threshold_A": 4.5,
            }
        },
        {
            "rows": [
                {"target_id": "STK17B (DRAK2)", "shard_id": "17_of_20", "queue_status": "result_ready", "execution_state": "result_ready", "notes": "ok"},
                {"target_id": "STK17B (DRAK2)", "shard_id": "18_of_20", "queue_status": "result_ready", "execution_state": "result_ready", "notes": "followup"},
                {"target_id": "STK17B (DRAK2)", "shard_id": "19_of_20", "queue_status": "result_ready", "execution_state": "result_ready", "notes": "followup"},
                {"target_id": "STK17B (DRAK2)", "shard_id": "20_of_20", "queue_status": "result_ready", "execution_state": "result_ready", "notes": "followup"},
            ]
        },
    )

    summary = payload["summary"]
    assert summary["decision"] == "branch_to_gate45_only_keep_default_closed"
    assert summary["default_lane_reopen_allowed"] is False
    assert summary["branch_to_gate45_only"] is True
    assert summary["followup_gate45_success_count"] == 3
    assert summary["followup_gate45_hold_count"] == 0
