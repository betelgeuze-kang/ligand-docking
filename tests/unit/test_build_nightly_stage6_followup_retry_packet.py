from __future__ import annotations

from tools import build_nightly_stage6_followup_retry_packet as mod


def _stage4_row(
    queue_id: str,
    target: str,
    ligand_id: str,
    replica_idx: int,
    mean_min_distance_A: float,
    proxy: float,
    calibrated: float,
) -> dict[str, object]:
    return {
        "queue_id": queue_id,
        "target": target,
        "ligand_id": ligand_id,
        "replica_idx": replica_idx,
        "mean_min_distance_A": mean_min_distance_A,
        "binding_energy_mmpbsa_kcal_mol_proxy": proxy,
        "binding_energy_mmpbsa_kcal_mol_calibrated": calibrated,
        "trajectory_npz": f"runs/ligand_htvs_nightly_2026-04-21_stage2_traj_frames/shard_00000/{queue_id}.npz",
    }


def _stage2_row(
    queue_id: str,
    target: str,
    ligand_id: str,
    mean_min_distance_A: float,
    seed: int,
) -> dict[str, object]:
    return {
        "queue_id": queue_id,
        "target": target,
        "ligand_id": ligand_id,
        "status": "ok",
        "seed": seed,
        "mean_min_distance_A": mean_min_distance_A,
        "trajectory_npz": f"runs/ligand_htvs_nightly_2026-04-21_stage2_traj_frames/shard_00000/{queue_id}.npz",
    }


def test_build_nightly_stage6_followup_retry_packet_classifies_rows() -> None:
    payload = mod.build_payload(
        latest_nightly_payload={
            "stages": {
                "stage6_operational_gate": {
                    "failed_metrics": [
                        {
                            "metric": "mean_min_distance_A",
                            "value": 2.655165582969785,
                            "threshold": 2.5,
                        }
                    ],
                    "mean_min_distance_A": 2.655165582969785,
                    "mean_min_distance_A_source": "eval_unique_topk",
                    "mean_min_distance_A_topk_k": 4,
                }
            }
        },
        latest_nightly_artifact="runs/ligand_htvs_nightly_2026-04-21_summary.json",
        stage5_payload={
            "distance_topk_k": 4,
            "mean_min_distance_A_topk_unique": 2.655165582969785,
        },
        stage5_artifact="runs/ligand_htvs_nightly_2026-04-21_stage5_ranking_summary.json",
        stage5_rows=[
            {"target": "HIV1_PROTEASE", "ligand_id": "imatinib", "role": "eval"},
            {"target": "EGFR_KINASE", "ligand_id": "imatinib", "role": "eval"},
            {"target": "HIV1_PROTEASE", "ligand_id": "aspirin", "role": "eval"},
            {"target": "EGFR_KINASE", "ligand_id": "aspirin", "role": "eval"},
        ],
        stage5_rows_artifact="runs/ligand_htvs_nightly_2026-04-21_stage5_ranking_rows.csv",
        stage5_unique_rows=[
            {
                "target": "HIV1_PROTEASE",
                "ligand_id": "imatinib",
                "is_binder": 1,
                "reference_binding_kcal_mol": -5.4,
                "binding_energy_mmpbsa_kcal_mol_proxy": -1.7507244479,
                "binding_energy_mmpbsa_kcal_mol_calibrated": -6.3915784848,
                "mean_min_distance_A": 2.7056560671,
            },
            {
                "target": "EGFR_KINASE",
                "ligand_id": "imatinib",
                "is_binder": 1,
                "reference_binding_kcal_mol": -7.4,
                "binding_energy_mmpbsa_kcal_mol_proxy": -1.6939277540,
                "binding_energy_mmpbsa_kcal_mol_calibrated": -8.0434620657,
                "mean_min_distance_A": 2.3524048370,
            },
            {
                "target": "HIV1_PROTEASE",
                "ligand_id": "aspirin",
                "is_binder": 0,
                "reference_binding_kcal_mol": -1.0,
                "binding_energy_mmpbsa_kcal_mol_proxy": -0.9406890114,
                "binding_energy_mmpbsa_kcal_mol_calibrated": -0.7818180237,
                "mean_min_distance_A": 2.6586698660,
            },
            {
                "target": "EGFR_KINASE",
                "ligand_id": "aspirin",
                "is_binder": 0,
                "reference_binding_kcal_mol": -1.1,
                "binding_energy_mmpbsa_kcal_mol_proxy": -0.8100479933,
                "binding_energy_mmpbsa_kcal_mol_calibrated": -2.9447355483,
                "mean_min_distance_A": 2.9039315617,
            },
        ],
        stage5_unique_artifact="runs/ligand_htvs_nightly_2026-04-21_stage5_ranking_unique.csv",
        stage5_topk_rows=[{"k": 4, "hit_rate": 0.5, "hits": 2}],
        stage5_topk_artifact="runs/ligand_htvs_nightly_2026-04-21_stage5_ranking_topk.csv",
        stage2_manifest_rows=[
            _stage2_row("EGFR_KINASE__rep0005__aspirin", "EGFR_KINASE", "aspirin", 2.911202566623688, 816626),
            _stage2_row("EGFR_KINASE__rep0011__aspirin", "EGFR_KINASE", "aspirin", 2.9004392862319945, 261801),
            _stage2_row("EGFR_KINASE__rep0017__aspirin", "EGFR_KINASE", "aspirin", 2.893298408985138, 482058),
            _stage2_row("EGFR_KINASE__rep0023__aspirin", "EGFR_KINASE", "aspirin", 2.910785984992981, 229064),
            _stage2_row("EGFR_KINASE__rep0004__imatinib", "EGFR_KINASE", "imatinib", 2.346886703968048, 16016),
            _stage2_row("EGFR_KINASE__rep0010__imatinib", "EGFR_KINASE", "imatinib", 2.353137197494507, 943952),
            _stage2_row("EGFR_KINASE__rep0016__imatinib", "EGFR_KINASE", "imatinib", 2.3574133813381195, 524615),
            _stage2_row("EGFR_KINASE__rep0022__imatinib", "EGFR_KINASE", "imatinib", 2.3521820652484893, 36001),
            _stage2_row("HIV1_PROTEASE__rep0005__aspirin", "HIV1_PROTEASE", "aspirin", 2.64482021689415, 746279),
            _stage2_row("HIV1_PROTEASE__rep0011__aspirin", "HIV1_PROTEASE", "aspirin", 2.8257911586761475, 37607),
            _stage2_row("HIV1_PROTEASE__rep0017__aspirin", "HIV1_PROTEASE", "aspirin", 2.8803127145767213, 396127),
            _stage2_row("HIV1_PROTEASE__rep0023__aspirin", "HIV1_PROTEASE", "aspirin", 2.283755373954773, 290187),
            _stage2_row("HIV1_PROTEASE__rep0004__imatinib", "HIV1_PROTEASE", "imatinib", 2.356958012580872, 564907),
            _stage2_row("HIV1_PROTEASE__rep0010__imatinib", "HIV1_PROTEASE", "imatinib", 2.8107700610160826, 1423),
            _stage2_row("HIV1_PROTEASE__rep0016__imatinib", "HIV1_PROTEASE", "imatinib", 2.800697741508484, 486610),
            _stage2_row("HIV1_PROTEASE__rep0022__imatinib", "HIV1_PROTEASE", "imatinib", 2.854198453426361, 618643),
        ],
        stage2_manifest_artifact="runs/ligand_htvs_nightly_2026-04-21_stage2_traj_manifest.csv",
        stage2_summary_payload={"ok_rows": 72, "processed_rows": 72, "min_frames_written": 100},
        stage2_summary_artifact="runs/ligand_htvs_nightly_2026-04-21_stage2_traj_summary.json",
        stage4_score_rows=[
            _stage4_row("EGFR_KINASE__rep0005__aspirin", "EGFR_KINASE", "aspirin", 5, 2.911202566623688, -0.8098891736697701, -2.9417932525411024),
            _stage4_row("EGFR_KINASE__rep0011__aspirin", "EGFR_KINASE", "aspirin", 11, 2.9004392862319945, -0.8086084624694899, -2.955430357042366),
            _stage4_row("EGFR_KINASE__rep0017__aspirin", "EGFR_KINASE", "aspirin", 17, 2.893298408985138, -0.8112834506233362, -2.938557013292739),
            _stage4_row("EGFR_KINASE__rep0023__aspirin", "EGFR_KINASE", "aspirin", 23, 2.910785984992981, -0.8104108863465811, -2.943161570299508),
            _stage4_row("EGFR_KINASE__rep0004__imatinib", "EGFR_KINASE", "imatinib", 4, 2.346886703968048, -1.693998709312802, -8.041113718790417),
            _stage4_row("EGFR_KINASE__rep0010__imatinib", "EGFR_KINASE", "imatinib", 10, 2.353137197494507, -1.69107756966879, -8.0621648380014),
            _stage4_row("EGFR_KINASE__rep0016__imatinib", "EGFR_KINASE", "imatinib", 16, 2.3574133813381195, -1.6968205267063765, -8.022981717936876),
            _stage4_row("EGFR_KINASE__rep0022__imatinib", "EGFR_KINASE", "imatinib", 22, 2.3521820652484893, -1.6938142102841744, -8.047587987961382),
            _stage4_row("HIV1_PROTEASE__rep0005__aspirin", "HIV1_PROTEASE", "aspirin", 5, 2.64482021689415, -0.9393071908344104, -0.7120056140044585),
            _stage4_row("HIV1_PROTEASE__rep0011__aspirin", "HIV1_PROTEASE", "aspirin", 11, 2.8257911586761475, -0.9538540164211348, -0.9189672037805001),
            _stage4_row("HIV1_PROTEASE__rep0017__aspirin", "HIV1_PROTEASE", "aspirin", 17, 2.8803127145767213, -0.9991432331222114, -0.2567009888228246),
            _stage4_row("HIV1_PROTEASE__rep0023__aspirin", "HIV1_PROTEASE", "aspirin", 23, 2.283755373954773, -0.8704516051229215, -1.2395982882272103),
            _stage4_row("HIV1_PROTEASE__rep0004__imatinib", "HIV1_PROTEASE", "imatinib", 4, 2.356958012580872, -1.5880179996348098, -7.011881868916186),
            _stage4_row("HIV1_PROTEASE__rep0010__imatinib", "HIV1_PROTEASE", "imatinib", 10, 2.8107700610160826, -1.7344385316581203, -6.716117503768588),
            _stage4_row("HIV1_PROTEASE__rep0016__imatinib", "HIV1_PROTEASE", "imatinib", 16, 2.800697741508484, -1.7168780540896886, -6.869252060651994),
            _stage4_row("HIV1_PROTEASE__rep0022__imatinib", "HIV1_PROTEASE", "imatinib", 22, 2.854198453426361, -1.963563206411144, -4.969062505780706),
        ],
        stage4_scores_artifact="runs/ligand_htvs_nightly_2026-04-21_stage4_calibration_scores.csv",
    )

    summary = payload["summary"]
    assert summary["status"] == "nightly_stage6_followup_retry_packet_ready"
    assert summary["retry_row_count"] == 2
    assert summary["closure_row_count"] == 2
    assert summary["closure_without_retry_count"] == 1
    assert summary["keep_anchor_row_count"] == 1
    assert summary["primary_execution_focus_row_key"] == "EGFR_KINASE::aspirin"
    assert summary["primary_retry_row_key"] == "HIV1_PROTEASE::imatinib"
    assert summary["primary_closure_row_key"] == "EGFR_KINASE::aspirin"
    assert summary["replica_rows_joined"] == 16
    assert summary["action_lines"][0].startswith("Close `EGFR_KINASE::aspirin`")
    assert "HIV1_PROTEASE__rep0004__imatinib" in summary["next_required_step"]
    assert "HIV1_PROTEASE__rep0023__aspirin" in summary["next_required_step"]

    rows = {row["row_key"]: row for row in payload["rows"]}

    egfr_aspirin = rows["EGFR_KINASE::aspirin"]
    assert egfr_aspirin["culprit_kind"] == "decoy_cleanup"
    assert egfr_aspirin["action_bucket"] == "closure"
    assert egfr_aspirin["recommended_action"] == "close_decoy_without_retry"
    assert egfr_aspirin["closure_evidence_queue_id"] == "EGFR_KINASE__rep0017__aspirin"
    assert egfr_aspirin["replica_above_threshold_count"] == 4
    assert egfr_aspirin["replica_below_threshold_count"] == 0
    assert round(egfr_aspirin["replica_distance_spread_A"], 3) == 0.018

    hiv_imatinib = rows["HIV1_PROTEASE::imatinib"]
    assert hiv_imatinib["culprit_kind"] == "binder_recovery"
    assert hiv_imatinib["action_bucket"] == "retry"
    assert hiv_imatinib["recommended_action"] == "retry_from_best_replica"
    assert hiv_imatinib["retry_anchor_queue_id"] == "HIV1_PROTEASE__rep0004__imatinib"
    assert hiv_imatinib["retry_anchor_seed"] == "564907"
    assert round(hiv_imatinib["retry_anchor_mean_min_distance_A"], 3) == 2.357

    hiv_aspirin = rows["HIV1_PROTEASE::aspirin"]
    assert hiv_aspirin["culprit_kind"] == "decoy_cleanup"
    assert hiv_aspirin["action_bucket"] == "retry"
    assert hiv_aspirin["recommended_action"] == "retry_cleanup_from_best_replica"
    assert hiv_aspirin["retry_anchor_queue_id"] == "HIV1_PROTEASE__rep0023__aspirin"
    assert hiv_aspirin["retry_anchor_seed"] == "290187"
    assert hiv_aspirin["replica_below_threshold_count"] == 1

    egfr_imatinib = rows["EGFR_KINASE::imatinib"]
    assert egfr_imatinib["culprit_kind"] == "keep_anchor"
    assert egfr_imatinib["action_bucket"] == "closure"
    assert egfr_imatinib["recommended_action"] == "keep_as_anchor"
    assert egfr_imatinib["closure_evidence_queue_id"] == "EGFR_KINASE__rep0004__imatinib"
