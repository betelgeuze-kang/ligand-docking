from __future__ import annotations

from tools import build_wetlab_cathepsin_k_stage6_tuning_surface as mod


def test_build_wetlab_cathepsin_k_stage6_tuning_surface_summarizes_gate45_band() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {"target_id": "Cathepsin K", "shard_id": "01_of_20", "queue_status": "explicit_hold"},
                {"target_id": "Cathepsin K", "shard_id": "02_of_20", "queue_status": "explicit_hold"},
                {"target_id": "Cathepsin K", "shard_id": "03_of_20", "queue_status": "explicit_hold"},
                {"target_id": "Cathepsin K", "shard_id": "05_of_20", "queue_status": "ready_after_previous_shard"},
            ]
        },
        {
            "structured": {"preferred_summary_json": "runs/wetlab_broad_screen_throughput/cathepsin_k/05_of_20/throughput_run_gate45_summary.json"},
            "rows": [
                {"command_kind": "throughput_preflight_tuned_gate45", "command": "python3 tools/run_ligand_htvs_pipeline.py --gate45"},
                {"command_kind": "throughput_preflight_tuned_gate55", "command": "python3 tools/run_ligand_htvs_pipeline.py --gate55"},
            ],
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_cathepsin_k_stage6_tuning_surface_ready"
    assert summary["target_id"] == "Cathepsin K"
    assert summary["next_retry_shard_id"] == "05_of_20"
    assert summary["recommended_observed_threshold_A"] == 4.45
    assert summary["immediately_runnable_threshold_A"] == 4.5
    assert summary["immediately_runnable_command_kind"] == "throughput_preflight_tuned_gate45"

    candidate_rows = [row for row in payload["rows"] if row.get("row_kind") == "threshold_candidate"]
    labels = {row["candidate_label"] for row in candidate_rows}
    assert {"candidate_4.4", "candidate_4.45", "candidate_4.5", "candidate_5.1", "candidate_5.5"}.issubset(labels)
