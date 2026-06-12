from __future__ import annotations

from tools import build_nightly_stage6_execute_result_packet as mod


def test_build_nightly_stage6_execute_result_packet() -> None:
    payload = mod.build_payload(
        downstream_rerun_payload={
            "summary": {
                "packet_artifact": "runs/nightly_stage6_downstream_rerun_packet_current.md",
                "target_subset": "EGFR_KINASE,HIV1_PROTEASE",
                "primary_focus_row_key": "HIV1_PROTEASE::aspirin",
                "primary_canonical_retry_preset_id": "target_forced_adress_uncapped_probe",
                "rescored_gate_mean_min_distance_A": 2.2707623770833014,
                "gate_threshold_A": 2.5,
                "runner_execute_command": "python3 tools/product/run_ligand_htvs_nightly.py --no-dry-run",
            },
            "rows": [
                {
                    "rerun_rank": 1,
                    "row_key": "EGFR_KINASE::imatinib",
                    "target": "EGFR_KINASE",
                    "ligand_id": "imatinib",
                    "lane_status": "kept_anchor_row",
                    "canonical_retry_preset_id": "",
                    "selected_for_downstream_rerun": True,
                    "rescored_mean_min_distance_A": 2.284,
                    "gate_margin_A": 0.216,
                },
                {
                    "rerun_rank": 2,
                    "row_key": "HIV1_PROTEASE::aspirin",
                    "target": "HIV1_PROTEASE",
                    "ligand_id": "aspirin",
                    "lane_status": "canonical_retry_replacement",
                    "canonical_retry_preset_id": "target_forced_adress_uncapped_probe",
                    "selected_for_downstream_rerun": True,
                    "rescored_mean_min_distance_A": 1.604,
                    "gate_margin_A": 0.896,
                },
            ],
        },
        execute_status_payload={
            "pass": True,
            "attempt_count": 1,
            "command": {"returncode": 0},
            "artifacts": {
                "status_json": "runs/nightly_stage6_downstream_execute_current_status.json",
                "status_md": "runs/nightly_stage6_downstream_execute_current_status.md",
                "pipeline_summary_json": "runs/nightly_stage6_downstream_execute_current_summary.json",
                "pipeline_summary_md": "runs/nightly_stage6_downstream_execute_current_summary.md",
            },
        },
        execute_pipeline_summary_payload={
            "pass": True,
            "failed_stage": None,
            "stages": {
                "stage6_operational_gate": {
                    "pass": True,
                    "mean_min_distance_A": 2.268931970372796,
                    "mean_min_distance_A_source": "eval_unique_topk+gate_distance_override",
                    "mean_min_distance_A_override_applied_count": 2,
                    "ranking_topk_hit_rate": 0.5,
                }
            },
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "nightly_stage6_execute_result_packet_ready"
    assert summary["target_subset"] == "EGFR_KINASE,HIV1_PROTEASE"
    assert summary["row_count"] == 2
    assert summary["primary_focus_row_key"] == "HIV1_PROTEASE::aspirin"
    assert summary["execute_payload_pass"] is True
    assert summary["execute_gate_pass"] is True
    assert summary["execute_gate_source"] == "eval_unique_topk+gate_distance_override"
    assert summary["execute_override_applied_count"] == 2
    assert summary["execute_matches_rescored_gate"] is True
    assert summary["execute_pipeline_summary_json_artifact"] == "runs/nightly_stage6_downstream_execute_current_summary.json"
    assert payload["rows"][0]["gate_name"] == "stage6_operational_gate"
