from __future__ import annotations

from tools.wetlab import build_wetlab_stk17b_stage6_tuning_surface as mod


def test_build_wetlab_stk17b_stage6_tuning_surface_summarizes_retry_band() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "target_id": "STK17B (DRAK2)",
                    "shard_id": "13_of_20",
                    "failed_stage": "stage6_operational_gate",
                    "queue_status": "explicit_hold",
                    "mean_min_distance_A": 4.403,
                    "stage6_failed_metric_threshold": 2.5,
                    "stage6_failed_metric_delta": 1.903,
                    "distance_over_threshold_A": 1.903,
                    "min_frames_observed": 138,
                    "mean_min_distance_A_source": "scores_all_mean(fallback)",
                    "summary_json": "runs/a.json",
                },
                {
                    "target_id": "STK17B (DRAK2)",
                    "shard_id": "14_of_20",
                    "failed_stage": "stage6_operational_gate",
                    "queue_status": "explicit_hold",
                    "mean_min_distance_A": 4.389,
                    "stage6_failed_metric_threshold": 2.5,
                    "stage6_failed_metric_delta": 1.889,
                    "distance_over_threshold_A": 1.889,
                    "min_frames_observed": 138,
                    "mean_min_distance_A_source": "scores_all_mean(fallback)",
                    "summary_json": "runs/b.json",
                },
                {
                    "target_id": "STK17B (DRAK2)",
                    "shard_id": "15_of_20",
                    "failed_stage": "stage6_operational_gate",
                    "queue_status": "explicit_hold",
                    "mean_min_distance_A": 4.381,
                    "stage6_failed_metric_threshold": 2.5,
                    "stage6_failed_metric_delta": 1.881,
                    "distance_over_threshold_A": 1.881,
                    "min_frames_observed": 138,
                    "mean_min_distance_A_source": "scores_all_mean(fallback)",
                    "summary_json": "runs/c.json",
                },
            ]
        },
        {"summary": {"target_id": "STK17B (DRAK2)", "campaign_start_shard_id": "13_of_20", "shard_id": "16_of_20"}},
        {
            "summary": {
                "exploratory_success_shard_id": "17_of_20",
                "exploratory_success_threshold_A": 4.5,
            }
        },
        {
            "summary": {
                "shard_id": "18_of_20",
                "followup_start_shard_id": "18_of_20",
                "selected_threshold_A": 4.5,
            }
        },
    )

    summary = payload["summary"]
    assert summary["campaign_stage6_row_count"] == 3
    assert summary["campaign_start_shard_id"] == "13_of_20"
    assert summary["current_gate_threshold_A"] == 2.5
    assert summary["exploratory_success_threshold_A"] == 4.5
    assert summary["exploratory_success_shard_id"] == "17_of_20"
    assert summary["exploratory_followup_hold_shard_id"] == "18_of_20"
    assert summary["median_mean_min_distance_A"] == 4.389
    assert summary["max_mean_min_distance_A"] == 4.403
    assert summary["recommended_relaxed_threshold_A"] >= 4.45

    comparison_rows = [row for row in payload["rows"] if row.get("row_kind") == "exploratory_success_hold_comparison"]
    assert [row["shard_id"] for row in comparison_rows] == ["17_of_20", "18_of_20"]
    success_row = comparison_rows[0]
    hold_row = comparison_rows[1]
    assert success_row["gate_threshold_A"] == 4.5
    assert hold_row["gate_threshold_A"] == 4.5
    assert success_row["summary_json"].endswith("17_of_20/throughput_run_gate45_summary.json")
    assert hold_row["summary_json"].endswith("18_of_20/throughput_run_gate45_summary.json")

    candidate_rows = [row for row in payload["rows"] if row.get("row_kind") == "threshold_candidate"]
    assert len(candidate_rows) == 3
    max_plus_margin = next(row for row in candidate_rows if row["candidate_label"] == "max_plus_margin")
    assert max_plus_margin["campaign_stage6_pass_count"] == 3

    detail_rows = [row for row in payload["rows"] if row.get("row_kind") == "stage6_retry_observation"]
    assert [row["shard_id"] for row in detail_rows] == ["13_of_20", "14_of_20", "15_of_20"]


def test_build_wetlab_stk17b_stage6_tuning_surface_falls_back_to_first_followup_shard_id() -> None:
    payload = mod.build_payload(
        {"rows": []},
        {"summary": {"target_id": "STK17B (DRAK2)", "campaign_start_shard_id": "13_of_20"}},
        {
            "summary": {
                "exploratory_success_shard_id": "17_of_20",
                "exploratory_success_threshold_A": 4.5,
            }
        },
        {
            "summary": {
                "shard_id": "",
                "followup_start_shard_id": "",
                "followup_shard_ids": "18_of_20;19_of_20;20_of_20",
                "selected_threshold_A": 4.5,
            }
        },
    )

    summary = payload["summary"]
    assert summary["exploratory_followup_hold_shard_id"] == "18_of_20"
    comparison_rows = [row for row in payload["rows"] if row.get("row_kind") == "exploratory_success_hold_comparison"]
    assert [row["shard_id"] for row in comparison_rows] == ["17_of_20", "18_of_20"]
