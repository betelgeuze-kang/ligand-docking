from __future__ import annotations

from tools.wetlab import build_wetlab_tcruzi_pde_exploratory_retry_lane as mod


def test_build_wetlab_tcruzi_pde_exploratory_retry_lane_prefers_gate51() -> None:
    payload = mod.build_payload(
        execution_queue_payload={
            "rows": [
                {"target_id": "T. cruzi PDE", "shard_id": "01_of_20", "queue_status": "explicit_hold"},
            ]
        },
        throughput_bridge_payload={
            "rows": [
                {"command_kind": "throughput_preflight_tuned_gate51", "command": "python3 tools/run_ligand_htvs_pipeline.py --gate51"},
                {"command_kind": "throughput_execute_tuned_gate51", "command": "python3 tools/run_ligand_htvs_pipeline.py --execute-gate51"},
            ]
        },
        stage6_tuning_surface_payload={
            "summary": {
                "status": "wetlab_tcruzi_pde_stage6_tuning_surface_ready",
                "target_id": "T. cruzi PDE",
                "campaign_start_shard_id": "01_of_20",
                "recommended_observed_threshold_A": 5.1,
            }
        },
        legacy_mapping_fix_lane_payload={"summary": {"shard_id": "07_of_20"}},
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_tcruzi_pde_exploratory_retry_lane_ready"
    assert summary["target_id"] == "T. cruzi PDE"
    assert summary["shard_id"] == "07_of_20"
    assert summary["selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["selected_threshold_A"] == 5.1
    assert summary["recommended_retry_mode"] == "guarded_tuned_gate51_candidate"
    assert summary["ready_for_manual_retry"] is True
