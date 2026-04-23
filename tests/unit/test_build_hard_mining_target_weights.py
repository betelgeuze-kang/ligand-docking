import json

import pandas as pd

from tools import build_hard_mining_target_weights as mod


def test_build_hard_mining_target_weights_selects_high_risk_targets(tmp_path):
    pair_csv = tmp_path / "pair.csv"
    acc_csv = tmp_path / "accuracy.csv"
    st2_csv = tmp_path / "stage2.csv"
    out_weights = tmp_path / "weights.csv"
    out_scores = tmp_path / "scores.csv"
    out_summary = tmp_path / "summary.json"

    pd.DataFrame(
        [
            {"target": "A", "paired": 0, "reason": "missing_pdb_or_afdb", "rmsd_aligned_A": None},
            {"target": "B", "paired": 1, "reason": "ok", "rmsd_aligned_A": 8.5},
            {"target": "C", "paired": 1, "reason": "ok", "rmsd_aligned_A": 2.0},
        ]
    ).to_csv(pair_csv, index=False)

    pd.DataFrame(
        [
            {"target": "A", "avg_rmsd_vs_native_aligned": 1.4},
            {"target": "B", "avg_rmsd_vs_native_aligned": 0.9},
            {"target": "C", "avg_rmsd_vs_native_aligned": 0.1},
        ]
    ).to_csv(acc_csv, index=False)

    pd.DataFrame(
        [
            {
                "target": "A",
                "ai_uncertainty_score_on": 0.75,
                "ai_uncertainty_fallback_ratio_on": 0.20,
                "physics_violations_on": 1.0,
            },
            {
                "target": "B",
                "ai_uncertainty_score_on": 0.40,
                "ai_uncertainty_fallback_ratio_on": 0.08,
                "physics_violations_on": 0.0,
            },
            {
                "target": "C",
                "ai_uncertainty_score_on": 0.10,
                "ai_uncertainty_fallback_ratio_on": 0.00,
                "physics_violations_on": 0.0,
            },
        ]
    ).to_csv(st2_csv, index=False)

    payload = mod.build_hard_mining_target_weights(
        targets="A,B,C",
        ood_pair_csv=str(pair_csv),
        accuracy_external_csv=str(acc_csv),
        stage2_csv=str(st2_csv),
        topk=2,
        base_weight=1.0,
        max_weight=4.0,
        weight_scale=1.0,
        unpaired_boost=2.0,
        ood_rmsd_threshold=6.0,
        native_rmsd_threshold=0.5,
        uncertainty_threshold=0.3,
        fallback_ratio_threshold=0.05,
        physics_violations_threshold=0.0,
        uncertainty_weight=0.75,
        fallback_weight=0.5,
        physics_weight=0.5,
        out_target_weights_csv=str(out_weights),
        out_score_csv=str(out_scores),
        out_summary_json=str(out_summary),
    )

    assert out_weights.exists()
    assert out_scores.exists()
    assert out_summary.exists()

    summary = payload["summary"]
    assert summary["selected_targets_count"] == 2
    assert "A" in summary["selected_targets"]
    assert "B" in summary["selected_targets"]

    weights_df = pd.read_csv(out_weights)
    a_weight = float(weights_df.loc[weights_df["target"] == "A", "multiplier"].iloc[0])
    c_weight = float(weights_df.loc[weights_df["target"] == "C", "multiplier"].iloc[0])
    assert a_weight > 1.0
    assert c_weight == 1.0

    saved = json.loads(out_summary.read_text(encoding="utf-8"))
    assert saved["summary"]["selected_targets_count"] == 2


def test_build_hard_mining_target_weights_priority_bonus_boosts_target(tmp_path):
    pair_csv = tmp_path / "pair.csv"
    out_weights = tmp_path / "weights.csv"
    out_scores = tmp_path / "scores.csv"
    out_summary = tmp_path / "summary.json"
    priority_csv = tmp_path / "priority.csv"

    pd.DataFrame(
        [
            {"target": "A", "paired": 1, "reason": "ok", "rmsd_aligned_A": 1.0},
            {"target": "B", "paired": 1, "reason": "ok", "rmsd_aligned_A": 1.0},
        ]
    ).to_csv(pair_csv, index=False)
    pd.DataFrame([{"target": "B"}]).to_csv(priority_csv, index=False)

    payload = mod.build_hard_mining_target_weights(
        targets="A,B",
        ood_pair_csv=str(pair_csv),
        accuracy_external_csv="",
        stage2_csv="",
        topk=1,
        base_weight=1.0,
        max_weight=4.0,
        weight_scale=1.0,
        unpaired_boost=0.0,
        ood_rmsd_threshold=6.0,
        native_rmsd_threshold=0.5,
        uncertainty_threshold=0.3,
        fallback_ratio_threshold=0.05,
        physics_violations_threshold=0.0,
        uncertainty_weight=0.75,
        fallback_weight=0.5,
        physics_weight=0.5,
        out_target_weights_csv=str(out_weights),
        out_score_csv=str(out_scores),
        out_summary_json=str(out_summary),
        priority_targets_csv=str(priority_csv),
        priority_target_col="target",
        priority_bonus=2.5,
    )

    assert "B" in payload["summary"]["selected_targets"]
    assert payload["summary"]["priority_targets_matched"] == 1
