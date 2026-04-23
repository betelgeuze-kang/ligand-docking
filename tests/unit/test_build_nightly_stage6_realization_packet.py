from __future__ import annotations

from tools import build_nightly_stage6_realization_packet as mod


def test_build_nightly_stage6_realization_packet_marks_lane_ready(tmp_path) -> None:
    aspirin_manifest = tmp_path / "aspirin_manifest.csv"
    aspirin_manifest.write_text("queue_id,mean_min_distance_A\nA,1.603783567547798\n", encoding="utf-8")
    imatinib_manifest = tmp_path / "imatinib_manifest.csv"
    imatinib_manifest.write_text("queue_id,mean_min_distance_A\nB,2.214552210569382\n", encoding="utf-8")

    payload = mod.build_payload(
        tuning_payload={
            "summary": {
                "packet_artifact": "runs/nightly_stage6_tuning_packet_current.md",
                "primary_gate_threshold": 2.5,
                "primary_gate_value": 2.655771412402392,
            },
            "rows": [
                {"row_key": "EGFR_KINASE::aspirin", "mean_min_distance_A": 2.9039315617084505},
                {"row_key": "HIV1_PROTEASE::imatinib", "mean_min_distance_A": 2.6980009883642198},
                {"row_key": "HIV1_PROTEASE::aspirin", "mean_min_distance_A": 2.6603709310293198},
                {"row_key": "EGFR_KINASE::imatinib", "mean_min_distance_A": 2.352404027231578},
            ],
        },
        promotion_payload={
            "summary": {
                "packet_artifact": "runs/nightly_stage6_probe_promotion_packet_current.md",
                "apply_preview_csv_artifact": "runs/nightly_stage6_probe_promotion_apply_preview_current.csv",
                "canonical_retry_lane_ready": True,
            },
            "rows": [
                {
                    "row_key": "HIV1_PROTEASE::aspirin",
                    "promotion_decision": "promote_probe_as_retry_replacement",
                    "canonical_fallback_preset_id": "target_forced_adress_uncapped_probe",
                    "canonical_fallback_retry_manifest_artifact": str(aspirin_manifest),
                    "canonical_fallback_retry_command_str": "python3 tools/generate_ligand_trajectory_engine.py --queue-csv runs/nightly_stage6_retry_subset_hiv1_protease_aspirin.csv",
                    "original_mean_min_distance_A": 2.6603709310293198,
                    "promoted_mean_min_distance_A": 1.603783567547798,
                    "distance_delta_A": -1.0565873634815217,
                    "strategy_reason": "force_target",
                    "promoted_seed": "156993",
                    "retry_lane_role": "retry_cleanup_from_best_replica",
                },
                {
                    "row_key": "HIV1_PROTEASE::imatinib",
                    "promotion_decision": "promote_probe_as_retry_replacement",
                    "canonical_fallback_preset_id": "target_forced_adress_uncapped_probe",
                    "canonical_fallback_retry_manifest_artifact": str(imatinib_manifest),
                    "canonical_fallback_retry_command_str": "python3 tools/generate_ligand_trajectory_engine.py --queue-csv runs/nightly_stage6_retry_subset_hiv1_protease_imatinib.csv",
                    "original_mean_min_distance_A": 2.6980009883642198,
                    "promoted_mean_min_distance_A": 2.214552210569382,
                    "distance_delta_A": -0.48344877779483797,
                    "strategy_reason": "force_target",
                    "promoted_seed": "464162",
                    "retry_lane_role": "retry_from_best_replica",
                },
            ],
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "nightly_stage6_realization_packet_ready"
    assert summary["realization_row_count"] == 2
    assert summary["primary_realization_row_key"] == "HIV1_PROTEASE::aspirin"
    assert summary["primary_canonical_retry_preset_id"] == "target_forced_adress_uncapped_probe"
    assert round(summary["realized_gate_mean_min_distance_A"], 3) == 2.269
    assert summary["realized_gate_pass"] is True
    assert summary["realization_ready"] is True
    assert "stage6 realization lane" in summary["next_required_step"]

    rows = payload["rows"]
    assert rows[0]["realization_manifest_present"] is True
    assert rows[0]["canonical_retry_preset_id"] == "target_forced_adress_uncapped_probe"
