from __future__ import annotations

import json
from pathlib import Path

from tools import build_wetlab_primary_stage6_failure_surface as mod


def test_build_wetlab_primary_stage6_failure_surface_summarizes_stage1_and_stage6_failures(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    base = tmp_path / "runs" / "wetlab_broad_screen_throughput"
    (base / "sars_cov_2_mpro" / "01_of_20").mkdir(parents=True, exist_ok=True)
    (base / "t_cruzi_pde" / "08_of_20").mkdir(parents=True, exist_ok=True)

    (base / "sars_cov_2_mpro" / "01_of_20" / "throughput_run_summary.json").write_text(
        json.dumps(
            {
                "failed_stage": "stage1_ligand_mapping",
                "service_result": {"status": "error", "error_code": "HTVS_MAPPING_FAILED", "failed_stage": "stage1_ligand_mapping"},
                "stages": {"stage1_ligand_mapping": {"pass": False}},
            }
        ),
        encoding="utf-8",
    )
    (base / "t_cruzi_pde" / "08_of_20" / "throughput_run_summary.json").write_text(
        json.dumps(
            {
                "failed_stage": "stage6_operational_gate",
                "service_result": {"status": "error", "error_code": "HTVS_GATE_FAILED", "failed_stage": "stage6_operational_gate"},
                "stages": {
                    "stage6_operational_gate": {
                        "pass": False,
                        "mean_min_distance_A": 5.0,
                        "failed_metrics": [{"metric": "mean_min_distance_A", "value": 5.0, "threshold": 2.5}],
                        "min_frames_observed": 162,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_payload(
        {
            "rows": [
                {
                    "target_id": "SARS-CoV-2 Mpro",
                    "target_slug": "sars_cov_2_mpro",
                    "shard_id": "01_of_20",
                    "queue_status": "explicit_hold",
                    "notes": "auto_hold_from_primary_watcher_runtime_validation_only",
                },
                {
                    "target_id": "T. cruzi PDE",
                    "target_slug": "t_cruzi_pde",
                    "shard_id": "08_of_20",
                    "queue_status": "explicit_hold",
                    "notes": "auto_hold_from_primary_watcher_runtime_validation_only",
                },
            ]
        },
        targets=["SARS-CoV-2 Mpro", "T. cruzi PDE"],
    )

    summary = payload["summary"]
    assert summary["surface_row_count"] == 2
    assert summary["auto_hold_row_count"] == 2
    assert summary["watcher_pending_failure_row_count"] == 0
    assert summary["sparse_top_level_row_count"] == 2
    assert summary["stage1_mapping_failed_count"] == 1
    assert summary["stage6_failed_count"] == 1
    assert summary["max_stage6_distance_over_threshold_A"] == 2.5
    detail_rows = [row for row in payload["rows"] if row.get("shard_id")]
    assert any(row["failure_mode"] == "stage1_mapping_failed" for row in detail_rows)
    assert any(row["failure_mode"] == "stage6_distance_gate_failed" for row in detail_rows)
    stage6_row = next(row for row in detail_rows if row["failure_mode"] == "stage6_distance_gate_failed")
    assert stage6_row["summary_top_level_sparse"] is True
    assert stage6_row["summary_service_status"] == "error"
    assert stage6_row["summary_service_error_code"] == "HTVS_GATE_FAILED"
    assert stage6_row["stage6_failed_metric"] == "mean_min_distance_A"
    assert stage6_row["stage6_failed_metric_value"] == 5.0
    assert stage6_row["stage6_failed_metric_threshold"] == 2.5
    assert stage6_row["stage6_failed_metric_delta"] == 2.5
    assert stage6_row["watcher_consumption_state"] == "consumed_auto_hold"


def test_build_wetlab_primary_stage6_failure_surface_includes_running_failure_rows_with_sparse_top_level_summary(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    base = tmp_path / "runs" / "wetlab_broad_screen_throughput"
    (base / "stk17b_drak2" / "07_of_20").mkdir(parents=True, exist_ok=True)

    (base / "stk17b_drak2" / "07_of_20" / "throughput_run_summary.json").write_text(
        json.dumps(
            {
                "status": None,
                "error_code": None,
                "failed_stage": "stage6_operational_gate",
                "service_result": {"status": "error", "error_code": "HTVS_GATE_FAILED", "failed_stage": "stage6_operational_gate"},
                "stages": {
                    "stage6_operational_gate": {
                        "pass": False,
                        "mean_min_distance_A": 4.403879428355941,
                        "mean_min_distance_A_all": 4.403879428355941,
                        "mean_min_distance_A_source": "scores_all_mean(fallback)",
                        "failed_metrics": [{"metric": "mean_min_distance_A", "value": 4.403879428355941, "threshold": 2.5}],
                        "min_frames_observed": 138,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_payload(
        {
            "rows": [
                {
                    "target_id": "STK17B (DRAK2)",
                    "target_slug": "stk17b_drak2",
                    "shard_id": "07_of_20",
                    "queue_status": "running",
                    "notes": "launched_by_primary_runner_throughput_preflight_runtime_validation_only",
                }
            ]
        },
        targets=["STK17B (DRAK2)"],
    )

    summary = payload["summary"]
    assert summary["surface_row_count"] == 1
    assert summary["auto_hold_row_count"] == 0
    assert summary["watcher_pending_failure_row_count"] == 1
    assert summary["sparse_top_level_row_count"] == 1
    assert summary["stage6_failed_count"] == 1

    rollup = next(row for row in payload["rows"] if row.get("target_id") == "STK17B (DRAK2)" and not row.get("shard_id"))
    assert rollup["watcher_pending_failure_row_count"] == 1
    assert rollup["recommended_action"] == "watcher reconciliation required before continuing"

    detail = next(row for row in payload["rows"] if row.get("shard_id") == "07_of_20")
    assert detail["queue_status_kind"] == "running"
    assert detail["summary_top_level_sparse"] is True
    assert detail["summary_service_status"] == "error"
    assert detail["summary_service_error_code"] == "HTVS_GATE_FAILED"
    assert detail["stage6_failed_metric"] == "mean_min_distance_A"
    assert detail["stage6_failed_metric_value"] == 4.403879428355941
    assert detail["stage6_failed_metric_threshold"] == 2.5
    assert detail["mean_min_distance_A_source"] == "scores_all_mean(fallback)"
    assert detail["watcher_consumption_state"] == "summary_failed_but_queue_running"


def test_build_wetlab_primary_stage6_failure_surface_reads_gate55_summary_when_default_missing(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    base = tmp_path / "runs" / "wetlab_broad_screen_throughput"
    (base / "stk17b_drak2" / "13_of_20").mkdir(parents=True, exist_ok=True)

    (base / "stk17b_drak2" / "13_of_20" / "throughput_run_gate55_summary.json").write_text(
        json.dumps(
            {
                "failed_stage": "stage6_operational_gate",
                "service_result": {"status": "error", "error_code": "HTVS_GATE_FAILED", "failed_stage": "stage6_operational_gate"},
                "stages": {
                    "stage6_operational_gate": {
                        "pass": False,
                        "mean_min_distance_A": 4.41,
                        "mean_min_distance_A_all": 4.41,
                        "mean_min_distance_A_source": "scores_all_mean(fallback)",
                        "failed_metrics": [{"metric": "mean_min_distance_A", "value": 4.41, "threshold": 2.5}],
                        "min_frames_observed": 138,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_payload(
        {
            "rows": [
                {
                    "target_id": "STK17B (DRAK2)",
                    "target_slug": "stk17b_drak2",
                    "shard_id": "13_of_20",
                    "queue_status": "explicit_hold",
                    "notes": "auto_hold_from_primary_watcher_runtime_validation_only",
                }
            ]
        },
        targets=["STK17B (DRAK2)"],
    )

    detail = next(row for row in payload["rows"] if row.get("shard_id") == "13_of_20")
    assert detail["summary_service_status"] == "error"
    assert detail["stage6_failed_metric_value"] == 4.41
    assert detail["summary_json"].endswith("throughput_run_gate55_summary.json")
