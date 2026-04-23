from __future__ import annotations

from tools import build_nightly_stage6_tuning_sweep_packet as mod


def test_build_nightly_stage6_tuning_sweep_packet_builds_retry_presets() -> None:
    payload = mod.build_payload(
        latest_nightly_payload={
            "stages": {
                "stage2_trajectory_generation": {
                    "cmd": [
                        "/usr/bin/python3",
                        "tools/generate_ligand_trajectory_engine.py",
                        "--queue-csv",
                        "runs/ligand_htvs_nightly_2026-04-21_stage1_queue.csv",
                        "--out-root",
                        "runs/ligand_htvs_nightly_2026-04-21_stage2_traj_frames",
                        "--frames",
                        "100",
                        "--seed",
                        "7",
                        "--step-size",
                        "0.04",
                        "--noise-scale",
                        "0.15",
                        "--pocket-attract-base",
                        "0.16",
                        "--protein-repulse",
                        "0.22",
                        "--out-manifest-csv",
                        "runs/ligand_htvs_nightly_2026-04-21_stage2_traj_manifest.csv",
                        "--out-summary-json",
                        "runs/ligand_htvs_nightly_2026-04-21_stage2_traj_summary.json",
                        "--out-summary-md",
                        "runs/ligand_htvs_nightly_2026-04-21_stage2_traj_summary.md",
                        "--out-progress-json",
                        "runs/ligand_htvs_nightly_2026-04-21_stage2_traj_progress.json",
                    ]
                }
            }
        },
        latest_nightly_artifact="runs/ligand_htvs_nightly_2026-04-21_summary.json",
        tuning_payload={"summary": {"packet_artifact": "runs/nightly_stage6_tuning_packet_current.md"}},
        tuning_artifact="runs/nightly_stage6_tuning_packet_current.md",
        followup_payload={
            "summary": {
                "packet_artifact": "runs/nightly_stage6_followup_retry_packet_current.md",
            },
            "rows": [
                {
                    "row_key": "HIV1_PROTEASE::imatinib",
                    "culprit_kind": "binder_recovery",
                    "action_bucket": "retry",
                    "recommended_action": "retry_from_best_replica",
                    "retry_anchor_queue_id": "HIV1_PROTEASE__rep0004__imatinib",
                    "retry_anchor_seed": "564907",
                    "retry_anchor_trajectory_npz": "runs/ligand_htvs_nightly_2026-04-21_stage2_traj_frames/shard_00000/HIV1_PROTEASE__rep0004__imatinib.npz",
                    "distance_over_threshold": 0.20565606713295015,
                },
                {
                    "row_key": "HIV1_PROTEASE::aspirin",
                    "culprit_kind": "decoy_cleanup",
                    "action_bucket": "retry",
                    "recommended_action": "retry_cleanup_from_best_replica",
                    "retry_anchor_queue_id": "HIV1_PROTEASE__rep0023__aspirin",
                    "retry_anchor_seed": "290187",
                    "retry_anchor_trajectory_npz": "runs/ligand_htvs_nightly_2026-04-21_stage2_traj_frames/shard_00000/HIV1_PROTEASE__rep0023__aspirin.npz",
                    "distance_over_threshold": 0.15866986602544797,
                },
                {
                    "row_key": "EGFR_KINASE::aspirin",
                    "culprit_kind": "decoy_cleanup",
                    "action_bucket": "closure",
                    "recommended_action": "close_decoy_without_retry",
                },
            ],
        },
        followup_artifact="runs/nightly_stage6_followup_retry_packet_current.md",
        stage1_queue_rows=[
            {"queue_id": "HIV1_PROTEASE__rep0004__imatinib", "target": "HIV1_PROTEASE", "ligand_id": "imatinib"},
            {"queue_id": "HIV1_PROTEASE__rep0023__aspirin", "target": "HIV1_PROTEASE", "ligand_id": "aspirin"},
        ],
        stage1_queue_artifact="runs/ligand_htvs_nightly_2026-04-21_stage1_queue.csv",
    )

    summary = payload["summary"]
    assert summary["status"] == "nightly_stage6_tuning_sweep_packet_ready"
    assert summary["retry_row_count"] == 2
    assert summary["closure_row_count"] == 1
    assert summary["sweep_preset_row_count"] == 8
    assert summary["retry_subset_queue_count"] == 2
    assert summary["retry_anchor_present_count"] == 2
    assert summary["primary_focus_row_key"] == "HIV1_PROTEASE::imatinib"
    assert summary["primary_preset_id"] == "anchor_replay_baseline"
    assert summary["primary_subset_queue_csv_artifact"] == "runs/nightly_stage6_retry_subset_hiv1_protease_imatinib.csv"

    rows = payload["rows"]
    assert len(rows) == 8
    first = rows[0]
    assert first["preset_id"] == "anchor_replay_baseline"
    assert first["subset_queue_csv_artifact"] == "runs/nightly_stage6_retry_subset_hiv1_protease_imatinib.csv"
    assert "--queue-csv runs/nightly_stage6_retry_subset_hiv1_protease_imatinib.csv" in first["retry_command_str"]
    assert "--no-resume-existing" in first["retry_command_str"]
    assert "tools/generate_ligand_trajectory_engine.py" in first["retry_command_str"]

    target_forced_replay = [row for row in rows if row["preset_id"] == "target_forced_adress_replay"][0]
    assert target_forced_replay["row_key"] == "HIV1_PROTEASE::imatinib"
    assert target_forced_replay["frames"] == 100
    assert "--dynamic-adress-force-targets HIV1_PROTEASE" in target_forced_replay["retry_command_str"]
    assert "--dynamic-adress-min-affinity 0.70" in target_forced_replay["retry_command_str"]

    uncapped_probe = [row for row in rows if row["preset_id"] == "target_forced_adress_uncapped_probe" and row["row_key"] == "HIV1_PROTEASE::imatinib"][0]
    assert "--dynamic-adress-max-all-atom-radius-A 12.0" in uncapped_probe["retry_command_str"]
    assert "--dynamic-adress-max-atom-ratio 0.2" in uncapped_probe["retry_command_str"]
    assert "--dynamic-adress-cap-force-core-on-radius" not in uncapped_probe["retry_command_str"]

    geometry_bias = [row for row in rows if row["preset_id"] == "target_forced_adress_geometry_bias"][0]
    assert geometry_bias["row_key"] == "HIV1_PROTEASE::imatinib"
    assert geometry_bias["frames"] == 120
    assert round(geometry_bias["pocket_attract_base"], 3) == 0.19
    assert round(geometry_bias["protein_repulse"], 3) == 0.19

    cleanup_probe = [row for row in rows if row["preset_id"] == "target_forced_adress_consistency_probe"][0]
    assert cleanup_probe["row_key"] == "HIV1_PROTEASE::aspirin"
    assert cleanup_probe["subset_queue_csv_artifact"] == "runs/nightly_stage6_retry_subset_hiv1_protease_aspirin.csv"
    assert "--dynamic-adress-force-targets HIV1_PROTEASE" in cleanup_probe["retry_command_str"]

    adress_only_probe = [row for row in rows if row["preset_id"] == "adress_only_boundary_probe"][0]
    assert adress_only_probe["row_key"] == "HIV1_PROTEASE::aspirin"
    assert "--strategy-mode adress_only" in adress_only_probe["retry_command_str"]


def test_build_nightly_stage6_tuning_sweep_packet_reads_nested_smoke_stage2() -> None:
    payload = mod.build_payload(
        latest_nightly_payload={
            "stages": {
                "smoke": {
                    "stages": {
                        "stage2_trajectory_generation": {
                            "cmd": [
                                "/usr/bin/python3",
                                "tools/generate_ligand_trajectory_engine.py",
                                "--queue-csv",
                                "runs/smoke_stage1_queue.csv",
                                "--out-root",
                                "runs/smoke_stage2_traj_frames",
                                "--frames",
                                "100",
                                "--noise-scale",
                                "0.15",
                                "--pocket-attract-base",
                                "0.16",
                                "--protein-repulse",
                                "0.22",
                                "--out-manifest-csv",
                                "runs/smoke_stage2_traj_manifest.csv",
                                "--out-summary-json",
                                "runs/smoke_stage2_traj_summary.json",
                                "--out-summary-md",
                                "runs/smoke_stage2_traj_summary.md",
                                "--out-progress-json",
                                "runs/smoke_stage2_traj_progress.json",
                            ]
                        }
                    }
                }
            }
        },
        latest_nightly_artifact="runs/ligand_htvs_nightly_2026-04-22_summary.json",
        tuning_payload={"summary": {"packet_artifact": "runs/nightly_stage6_tuning_packet_current.md"}},
        tuning_artifact="runs/nightly_stage6_tuning_packet_current.md",
        followup_payload={
            "summary": {"packet_artifact": "runs/nightly_stage6_followup_retry_packet_current.md"},
            "rows": [
                {
                    "row_key": "HIV1_PROTEASE::imatinib",
                    "culprit_kind": "binder_recovery",
                    "action_bucket": "retry",
                    "recommended_action": "retry_from_best_replica",
                    "retry_anchor_queue_id": "HIV1_PROTEASE__rep0004__imatinib",
                    "retry_anchor_seed": "564907",
                    "retry_anchor_trajectory_npz": "runs/smoke_stage2_traj_frames/shard_00000/HIV1_PROTEASE__rep0004__imatinib.npz",
                    "distance_over_threshold": 0.2056,
                }
            ],
        },
        followup_artifact="runs/nightly_stage6_followup_retry_packet_current.md",
        stage1_queue_rows=[
            {"queue_id": "HIV1_PROTEASE__rep0004__imatinib", "target": "HIV1_PROTEASE", "ligand_id": "imatinib"},
        ],
        stage1_queue_artifact="runs/smoke_stage1_queue.csv",
    )

    assert payload["summary"]["baseline_queue_csv_artifact"] == "runs/smoke_stage1_queue.csv"
    assert "tools/generate_ligand_trajectory_engine.py" in payload["rows"][0]["retry_command_str"]
