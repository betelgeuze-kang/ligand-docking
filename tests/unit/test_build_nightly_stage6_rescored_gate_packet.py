from __future__ import annotations

from tools import build_nightly_stage6_rescored_gate_packet as mod


def test_build_nightly_stage6_rescored_gate_packet_replaces_realized_rows() -> None:
    payload = mod.build_payload(
        tuning_payload={
            "summary": {
                "packet_artifact": "runs/nightly_stage6_tuning_packet_current.md",
                "primary_gate_threshold": 2.5,
                "primary_gate_value": 2.6557714124023915,
            },
            "rows": [
                {
                    "row_key": "EGFR_KINASE::aspirin",
                    "target": "EGFR_KINASE",
                    "ligand_id": "aspirin",
                    "mean_min_distance_A": 2.9100263017416,
                    "distance_over_threshold": 0.41002630174159993,
                    "tuning_priority_rank": 1,
                },
                {
                    "row_key": "HIV1_PROTEASE::imatinib",
                    "target": "HIV1_PROTEASE",
                    "ligand_id": "imatinib",
                    "mean_min_distance_A": 2.6980009883642198,
                    "distance_over_threshold": 0.19800098836421975,
                    "tuning_priority_rank": 2,
                },
                {
                    "row_key": "HIV1_PROTEASE::aspirin",
                    "target": "HIV1_PROTEASE",
                    "ligand_id": "aspirin",
                    "mean_min_distance_A": 2.6603709310293198,
                    "distance_over_threshold": 0.16037093102931976,
                    "tuning_priority_rank": 3,
                },
                {
                    "row_key": "EGFR_KINASE::imatinib",
                    "target": "EGFR_KINASE",
                    "ligand_id": "imatinib",
                    "mean_min_distance_A": 2.3546874284744264,
                    "distance_over_threshold": 0.0,
                    "tuning_priority_rank": 4,
                },
            ],
        },
        realization_payload={
            "summary": {
                "packet_artifact": "runs/nightly_stage6_realization_packet_current.md",
                "apply_preview_csv_artifact": "runs/nightly_stage6_probe_promotion_apply_preview_current.csv",
                "primary_realization_row_key": "HIV1_PROTEASE::aspirin",
                "realization_ready": True,
            },
            "rows": [
                {
                    "row_key": "HIV1_PROTEASE::aspirin",
                    "canonical_retry_preset_id": "target_forced_adress_uncapped_probe",
                    "realization_manifest_artifact": "runs/nightly_stage6_retry_runs/hiv1_protease_aspirin/target_forced_adress_uncapped_probe_manifest.csv",
                    "realization_manifest_present": True,
                    "canonical_retry_command_str": "python3 tools/generate_ligand_trajectory_engine.py --queue-csv runs/nightly_stage6_retry_subset_hiv1_protease_aspirin.csv",
                    "realized_mean_min_distance_A": 1.603783567547798,
                },
                {
                    "row_key": "HIV1_PROTEASE::imatinib",
                    "canonical_retry_preset_id": "target_forced_adress_uncapped_probe",
                    "realization_manifest_artifact": "runs/nightly_stage6_retry_runs/hiv1_protease_imatinib/target_forced_adress_uncapped_probe_manifest.csv",
                    "realization_manifest_present": True,
                    "canonical_retry_command_str": "python3 tools/generate_ligand_trajectory_engine.py --queue-csv runs/nightly_stage6_retry_subset_hiv1_protease_imatinib.csv",
                    "realized_mean_min_distance_A": 2.214552210569382,
                },
            ],
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "nightly_stage6_rescored_gate_packet_ready"
    assert summary["replaced_row_count"] == 2
    assert summary["untouched_row_count"] == 2
    assert summary["primary_applied_row_key"] == "HIV1_PROTEASE::aspirin"
    assert summary["primary_anchor_row_key"] == "EGFR_KINASE::imatinib"
    assert round(summary["rescored_gate_mean_min_distance_A"], 3) == 2.271
    assert summary["rescored_gate_pass"] is True
    assert summary["downstream_rerun_ready"] is True
    assert "downstream nightly scoring" in summary["next_required_step"]

    rows = payload["rows"]
    assert rows[1]["lane_status"] == "canonical_retry_replacement"
    assert rows[2]["lane_status"] == "canonical_retry_replacement"
    assert rows[3]["lane_status"] == "kept_anchor_row"
