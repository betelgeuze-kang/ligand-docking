from __future__ import annotations

import pytest

from tools.gpcr_replay import build_gpcr_coverage_v2_crossfit_rank_rescue_shadow_replay as mod


pytest.importorskip("sklearn")


def test_crossfit_replay_builds_out_of_fold_scores(tmp_path):
    scores_csv = tmp_path / "scores.csv"
    labels_csv = tmp_path / "labels.csv"
    scores_csv.write_text(
        "\n".join(
            [
                "target,ligand_id,binding_score_composite_v7,ligand_affinity_hint,contact_fraction,mean_min_distance_A,pose_preservation_support,trajectory_npz,export_rank",
                "T1,L1,-10,0.9,0.9,3.1,0.9,a.npz,1",
                "T1,L2,-9,0.8,0.8,3.2,0.8,a.npz,2",
                "T1,D1,-1,0.1,0.1,8.0,0.1,a.npz,3",
                "T1,D2,-2,0.1,0.2,7.0,0.1,a.npz,4",
                "T2,L3,-11,0.9,0.9,3.0,0.9,a.npz,5",
                "T2,L4,-8,0.8,0.8,3.3,0.8,a.npz,6",
                "T2,D3,-1,0.1,0.1,8.2,0.1,a.npz,7",
                "T2,D4,-2,0.1,0.2,7.4,0.1,a.npz,8",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    labels_csv.write_text(
        "\n".join(
            [
                "target,ligand_id,is_binder",
                "T1,L1,1",
                "T1,L2,1",
                "T1,D1,0",
                "T1,D2,0",
                "T2,L3,1",
                "T2,L4,1",
                "T2,D3,0",
                "T2,D4,0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    replay_df, payload = mod.build_replay(
        stage3_scores_csv=scores_csv,
        feature_cache_csv="",
        labels_csv=labels_csv,
        folds=2,
        seed=3,
        min_numeric_coverage=0.5,
    )

    summary = payload["summary"]
    assert summary["input_rows"] == 8
    assert summary["positive_count"] == 4
    assert summary["out_of_fold_scoring"] is True
    assert summary["same_row_label_leakage"] is False
    assert summary["same_ligand_label_leakage"] is False
    assert summary["validation_claim_promotion_allowed"] is True
    assert summary["diagnostic_weight_search_used_labels"] is False
    assert summary["score_finite_row_count"] == 8
    assert mod.SCORE_COL in replay_df.columns
    assert "ligand_affinity_hint" not in summary["score_features_used"]
    assert "export_rank" not in summary["score_features_used"]
