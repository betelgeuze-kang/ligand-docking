from __future__ import annotations

from tools import build_wetlab_sarscov2_mpro_exploratory_retry_lane as mod


def test_build_wetlab_sarscov2_mpro_exploratory_retry_lane_uses_gate45_and_legacy_shard() -> None:
    payload = mod.build_payload(
        execution_queue_payload={"rows": [{"target_id": "SARS-CoV-2 Mpro", "shard_id": "01_of_20", "queue_status": "explicit_hold"}]},
        throughput_bridge_payload={
            "rows": [
                {"command_kind": "throughput_preflight_tuned_gate45", "command": "python3 tools/run_ligand_htvs_pipeline.py --gate45"},
                {"command_kind": "throughput_execute_tuned_gate45", "command": "python3 tools/run_ligand_htvs_pipeline.py --execute-gate45"},
            ]
        },
        stage6_tuning_surface_payload={
            "summary": {
                "status": "wetlab_sarscov2_mpro_stage6_tuning_surface_ready",
                "target_id": "SARS-CoV-2 Mpro",
                "recommended_observed_threshold_A": 4.5,
            }
        },
        legacy_mapping_fix_lane_payload={"summary": {"shard_id": "01_of_20"}},
    )

    summary = payload["summary"]
    assert summary["target_id"] == "SARS-CoV-2 Mpro"
    assert summary["shard_id"] == "01_of_20"
    assert summary["selected_command_kind"] == "throughput_preflight_tuned_gate45"
    assert summary["selected_threshold_A"] == 4.5
    assert summary["ready_for_manual_retry"] is True
