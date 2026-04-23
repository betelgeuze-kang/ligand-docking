from __future__ import annotations

from tools import build_nightly_stage6_tuning_packet as mod


def test_build_nightly_stage6_tuning_packet_identifies_full_topk_band() -> None:
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
                    "ranking_eval_unique_keys": 4,
                    "ranking_ood_unique_keys": 6,
                    "ranking_expected_score_coverage_ratio": 1.0,
                    "ranking_auc": 1.0,
                    "ranking_pr_auc": 1.0,
                    "ranking_ef1": 2.0,
                    "ranking_bedroc": 1.0,
                    "ranking_ece": 0.2486,
                    "min_frames_observed": 100,
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
    )

    summary = payload["summary"]
    assert summary["status"] == "nightly_stage6_tuning_packet_ready"
    assert summary["topk_equals_full_unique_band"] is True
    assert summary["rows_above_threshold_count"] == 3
    assert summary["minimum_rows_to_touch_if_clamped_to_threshold"] == 3
    assert summary["primary_focus_row_key"] == "EGFR_KINASE::aspirin"
    assert round(summary["aggregate_distance_reduction_needed_A"], 3) == 0.621
    assert "full unique band" in summary["next_required_step"]
    assert payload["rows"][0]["role"] == "eval"
    assert payload["rows"][0]["row_key"] == "EGFR_KINASE::aspirin"
    assert round(payload["rows"][0]["distance_over_threshold"], 3) == 0.404
