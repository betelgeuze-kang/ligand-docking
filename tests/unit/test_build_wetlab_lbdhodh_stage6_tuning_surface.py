from __future__ import annotations

import json
from pathlib import Path

from tools import build_wetlab_lbdhodh_stage6_tuning_surface as mod


def test_build_wetlab_lbdhodh_stage6_tuning_surface_summarizes_band() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {"target_id": "Leishmania braziliensis DHODH", "shard_id": "01_of_20", "queue_status": "explicit_hold"},
                {"target_id": "Leishmania braziliensis DHODH", "shard_id": "02_of_20", "queue_status": "explicit_hold"},
                {"target_id": "Leishmania braziliensis DHODH", "shard_id": "03_of_20", "queue_status": "explicit_hold"},
                {"target_id": "Leishmania braziliensis DHODH", "shard_id": "06_of_20", "queue_status": "ready_after_previous_shard"},
            ]
        },
        {
            "structured": {"preferred_summary_json": "runs/wetlab_broad_screen_throughput/leishmania_braziliensis_dhodh/06_of_20/throughput_run_gate51_summary.json"},
            "rows": [
                {"command_kind": "throughput_preflight_tuned_gate51", "command": "python3 tools/run_ligand_htvs_pipeline.py --gate51"},
                {"command_kind": "throughput_preflight_tuned_gate55", "command": "python3 tools/run_ligand_htvs_pipeline.py --gate55"},
            ],
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_lbdhodh_stage6_tuning_surface_ready"
    assert summary["target_id"] == "Leishmania braziliensis DHODH"
    assert summary["next_retry_shard_id"] == "06_of_20"
    assert summary["recommended_observed_threshold_A"] >= 5.0
    assert summary["immediately_runnable_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["immediately_runnable_threshold_A"] == 5.1

    candidate_rows = [row for row in payload["rows"] if row.get("row_kind") == "threshold_candidate"]
    labels = {row["candidate_label"] for row in candidate_rows}
    assert {"candidate_5.0", "candidate_5.05", "candidate_5.1", "candidate_5.5"}.issubset(labels)


def test_build_wetlab_lbdhodh_stage6_tuning_surface_uses_csv_fallback(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    shard_dir = tmp_path / "runs" / "wetlab_broad_screen_throughput" / "leishmania_braziliensis_dhodh" / "07_of_20"
    shard_dir.mkdir(parents=True, exist_ok=True)
    summary_path = shard_dir / "throughput_run_gate55_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "service_result": {
                    "status": "error",
                    "error_code": "HTVS_GATE_FAILED",
                    "failed_stage": "stage6_operational_gate",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (shard_dir / "throughput_run_gate55_stage3_scores.csv").write_text(
        "queue_id,mean_min_distance_A\n1,5.02\n2,5.08\n",
        encoding="utf-8",
    )

    payload = mod.build_payload(
        {"rows": [{"target_id": "Leishmania braziliensis DHODH", "shard_id": "07_of_20", "queue_status": "explicit_hold"}]},
        {"rows": [{"command_kind": "throughput_preflight_tuned_gate51", "command": "python3 tools/run_ligand_htvs_pipeline.py --gate51"}]},
    )

    summary = payload["summary"]
    assert summary["observed_row_count"] == 1
    assert summary["recommended_observed_threshold_A"] == 5.05
    assert summary["telemetry_fallback_applied_count"] == 1
    row = next(row for row in payload["rows"] if row.get("row_kind") == "stage6_retry_observation")
    assert row["mean_min_distance_A"] == 5.05
    assert row["mean_min_distance_A_source"] == "stage3_scores_mean(fallback)"
    assert row["stage6_failed_metric_threshold"] == 5.5
    assert summary["immediately_runnable_command_kind"] == "throughput_preflight_tuned_gate51"
