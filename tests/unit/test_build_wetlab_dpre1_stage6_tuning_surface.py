from __future__ import annotations

from tools import build_wetlab_dpre1_stage6_tuning_surface as mod


def test_build_wetlab_dpre1_stage6_tuning_surface_summarizes_gate51_band() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {"target_id": "DprE1", "shard_id": "01_of_20", "queue_status": "explicit_hold"},
                {"target_id": "DprE1", "shard_id": "02_of_20", "queue_status": "explicit_hold"},
                {"target_id": "DprE1", "shard_id": "03_of_20", "queue_status": "explicit_hold"},
                {"target_id": "DprE1", "shard_id": "04_of_20", "queue_status": "ready_after_previous_shard"},
            ]
        },
        {
            "structured": {"preferred_summary_json": "runs/wetlab_broad_screen_throughput/dpre1/04_of_20/throughput_run_gate51_summary.json"},
            "rows": [
                {"command_kind": "throughput_preflight_tuned_gate51", "command": "python3 tools/run_ligand_htvs_pipeline.py --gate51"},
                {"command_kind": "throughput_preflight_tuned_gate55", "command": "python3 tools/run_ligand_htvs_pipeline.py --gate55"},
            ],
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_dpre1_stage6_tuning_surface_ready"
    assert summary["target_id"] == "DprE1"
    assert summary["next_retry_shard_id"] == "04_of_20"
    assert summary["recommended_observed_threshold_A"] == 5.05
    assert summary["immediately_runnable_threshold_A"] == 5.1
    assert summary["immediately_runnable_command_kind"] == "throughput_preflight_tuned_gate51"

    candidate_rows = [row for row in payload["rows"] if row.get("row_kind") == "threshold_candidate"]
    labels = {row["candidate_label"] for row in candidate_rows}
    assert {"candidate_5.0", "candidate_5.05", "candidate_5.1", "candidate_5.5"}.issubset(labels)
