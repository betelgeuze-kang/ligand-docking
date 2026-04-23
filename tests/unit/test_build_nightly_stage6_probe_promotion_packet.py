from __future__ import annotations

from tools import build_nightly_stage6_probe_promotion_packet as mod


def test_build_nightly_stage6_probe_promotion_packet() -> None:
    payload = mod.build_payload(
        probe_payload={
            "summary": {
                "packet_artifact": "runs/nightly_stage6_probe_result_packet_current.md",
                "gate_threshold_A": 2.5,
                "projected_gate_mean_min_distance_A": 2.2686680442094804,
                "projected_gate_pass": True,
            },
            "rows": [
                {
                    "row_key": "HIV1_PROTEASE::aspirin",
                    "probe_manifest_artifact": "runs/nightly_stage6_retry_runs/hiv1_protease_aspirin/target_forced_adress_uncapped_probe_manifest.csv",
                    "original_mean_min_distance_A": 2.658669866025448,
                    "probe_mean_min_distance_A": 1.603783567547798,
                    "distance_delta_A": -1.05488629847765,
                    "strategy_reason": "force_target",
                    "seed": "156993",
                },
                {
                    "row_key": "HIV1_PROTEASE::imatinib",
                    "probe_manifest_artifact": "runs/nightly_stage6_retry_runs/hiv1_protease_imatinib/target_forced_adress_uncapped_probe_manifest.csv",
                    "original_mean_min_distance_A": 2.70565606713295,
                    "probe_mean_min_distance_A": 2.214552210569382,
                    "distance_delta_A": -0.49110385656356836,
                    "strategy_reason": "force_target",
                    "seed": "464162",
                },
            ],
        },
        followup_payload={
            "summary": {"packet_artifact": "runs/nightly_stage6_followup_retry_packet_current.md"},
            "rows": [
                {
                    "row_key": "HIV1_PROTEASE::aspirin",
                    "recommended_action": "retry_cleanup_from_best_replica",
                    "culprit_kind": "decoy_cleanup",
                    "retry_anchor_queue_id": "HIV1_PROTEASE__rep0023__aspirin",
                    "retry_anchor_seed": "290187",
                    "retry_anchor_trajectory_npz": "runs/ligand_htvs_nightly_2026-04-21_stage2_traj_frames/shard_00000/HIV1_PROTEASE__rep0023__aspirin.npz",
                },
                {
                    "row_key": "HIV1_PROTEASE::imatinib",
                    "recommended_action": "retry_from_best_replica",
                    "culprit_kind": "binder_recovery",
                    "retry_anchor_queue_id": "HIV1_PROTEASE__rep0004__imatinib",
                    "retry_anchor_seed": "564907",
                    "retry_anchor_trajectory_npz": "runs/ligand_htvs_nightly_2026-04-21_stage2_traj_frames/shard_00000/HIV1_PROTEASE__rep0004__imatinib.npz",
                },
            ],
        },
        sweep_payload={
            "summary": {"packet_artifact": "runs/nightly_stage6_tuning_sweep_packet_current.md"},
            "rows": [
                {
                    "row_key": "HIV1_PROTEASE::aspirin",
                    "preset_id": "target_forced_adress_uncapped_probe",
                    "preset_rank": 1,
                    "subset_queue_csv_artifact": "runs/nightly_stage6_retry_subset_hiv1_protease_aspirin.csv",
                    "retry_summary_json_artifact": "runs/nightly_stage6_retry_runs/hiv1_protease_aspirin/target_forced_adress_uncapped_probe_summary.json",
                    "retry_summary_md_artifact": "runs/nightly_stage6_retry_runs/hiv1_protease_aspirin/target_forced_adress_uncapped_probe_summary.md",
                    "retry_command_str": "python3 tools/generate_ligand_trajectory_engine.py --queue-csv runs/nightly_stage6_retry_subset_hiv1_protease_aspirin.csv --dynamic-adress-max-all-atom-radius-A 12.0",
                },
                {
                    "row_key": "HIV1_PROTEASE::aspirin",
                    "preset_id": "target_forced_adress_consistency_probe",
                    "preset_rank": 2,
                    "subset_queue_csv_artifact": "runs/nightly_stage6_retry_subset_hiv1_protease_aspirin.csv",
                    "retry_summary_json_artifact": "runs/nightly_stage6_retry_runs/hiv1_protease_aspirin/target_forced_adress_consistency_probe_summary.json",
                    "retry_summary_md_artifact": "runs/nightly_stage6_retry_runs/hiv1_protease_aspirin/target_forced_adress_consistency_probe_summary.md",
                    "retry_command_str": "python3 tools/generate_ligand_trajectory_engine.py --queue-csv runs/nightly_stage6_retry_subset_hiv1_protease_aspirin.csv",
                },
                {
                    "row_key": "HIV1_PROTEASE::imatinib",
                    "preset_id": "target_forced_adress_uncapped_probe",
                    "preset_rank": 1,
                    "subset_queue_csv_artifact": "runs/nightly_stage6_retry_subset_hiv1_protease_imatinib.csv",
                    "retry_summary_json_artifact": "runs/nightly_stage6_retry_runs/hiv1_protease_imatinib/target_forced_adress_uncapped_probe_summary.json",
                    "retry_summary_md_artifact": "runs/nightly_stage6_retry_runs/hiv1_protease_imatinib/target_forced_adress_uncapped_probe_summary.md",
                    "retry_command_str": "python3 tools/generate_ligand_trajectory_engine.py --queue-csv runs/nightly_stage6_retry_subset_hiv1_protease_imatinib.csv --dynamic-adress-max-all-atom-radius-A 12.0",
                },
                {
                    "row_key": "HIV1_PROTEASE::imatinib",
                    "preset_id": "target_forced_adress_replay",
                    "preset_rank": 2,
                    "subset_queue_csv_artifact": "runs/nightly_stage6_retry_subset_hiv1_protease_imatinib.csv",
                    "retry_summary_json_artifact": "runs/nightly_stage6_retry_runs/hiv1_protease_imatinib/target_forced_adress_replay_summary.json",
                    "retry_summary_md_artifact": "runs/nightly_stage6_retry_runs/hiv1_protease_imatinib/target_forced_adress_replay_summary.md",
                    "retry_command_str": "python3 tools/generate_ligand_trajectory_engine.py --queue-csv runs/nightly_stage6_retry_subset_hiv1_protease_imatinib.csv",
                },
            ],
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "nightly_stage6_probe_promotion_packet_ready"
    assert summary["canonical_retry_lane_ready"] is True
    assert summary["promoted_row_count"] == 2
    assert summary["hold_row_count"] == 0
    assert summary["primary_promoted_row_key"] == "HIV1_PROTEASE::aspirin"
    assert summary["primary_companion_row_key"] == "HIV1_PROTEASE::imatinib"
    assert summary["primary_canonical_fallback_preset_id"] == "target_forced_adress_uncapped_probe"
    assert summary["projected_gate_pass"] is True
    assert summary["apply_preview_csv_artifact"] == "runs/nightly_stage6_probe_promotion_apply_preview_current.csv"
    assert "canonical replacement preview" in summary["next_required_step"]
    assert "same uncapped preset" in summary["next_required_step"]

    rows = payload["rows"]
    assert rows[0]["promotion_decision"] == "promote_probe_as_retry_replacement"
    assert rows[0]["canonical_source_run_label"] == "target_forced_adress_uncapped_probe"
    assert rows[0]["canonical_fallback_preset_id"] == "target_forced_adress_uncapped_probe"
    assert rows[0]["canonical_fallback_retry_manifest_artifact"] == "runs/nightly_stage6_retry_runs/hiv1_protease_aspirin/target_forced_adress_uncapped_probe_manifest.csv"
    assert rows[0]["promoted_inside_gate"] is True
    assert rows[0]["retry_lane_role"] == "retry_cleanup_from_best_replica"
    assert rows[1]["canonical_fallback_preset_id"] == "target_forced_adress_uncapped_probe"
    assert rows[1]["retry_lane_role"] == "retry_from_best_replica"
    assert payload["apply_preview_rows"][0]["source"] == "probe_promotion"
    assert payload["apply_preview_rows"][0]["canonical_fallback_preset_id"] == "target_forced_adress_uncapped_probe"


def test_build_nightly_stage6_probe_promotion_packet_holds_rows_when_projected_gate_still_fails() -> None:
    payload = mod.build_payload(
        probe_payload={
            "summary": {
                "packet_artifact": "runs/nightly_stage6_probe_result_packet_current.md",
                "gate_threshold_A": 2.5,
                "projected_gate_mean_min_distance_A": 2.611,
                "projected_gate_pass": False,
            },
            "rows": [
                {
                    "row_key": "HIV1_PROTEASE::aspirin",
                    "probe_manifest_artifact": "runs/nightly_stage6_retry_runs/hiv1_protease_aspirin/target_forced_adress_uncapped_probe_manifest.csv",
                    "original_mean_min_distance_A": 2.658669866025448,
                    "probe_mean_min_distance_A": 2.603,
                    "distance_delta_A": -0.05566986602544793,
                    "strategy_reason": "force_target",
                    "seed": "156993",
                }
            ],
        },
        followup_payload={"summary": {}, "rows": []},
    )

    summary = payload["summary"]
    assert summary["canonical_retry_lane_ready"] is False
    assert summary["promoted_row_count"] == 0
    assert summary["hold_row_count"] == 1
    assert "does not justify canonical retry-lane promotion" in summary["next_required_step"]
    assert payload["rows"][0]["promotion_decision"] == "hold_probe_for_additional_tuning"
    assert payload["apply_preview_rows"] == []
