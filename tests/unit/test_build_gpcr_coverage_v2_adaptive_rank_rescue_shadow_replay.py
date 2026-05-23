from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from tools import build_gpcr_coverage_v2_adaptive_rank_rescue_shadow_replay as mod

ROOT = Path(__file__).resolve().parents[2]


def _scores() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "positive_like",
                "binding_score_composite_v7_residual_active": -8.0,
                "ligand_affinity_hint": 0.8,
                "ligand_h_acceptors": 6,
                "ligand_rot_bonds": 5,
                "contact_fraction": 0.01,
                "stability_score": 0.01,
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy_like",
                "binding_score_composite_v7_residual_active": -8.0,
                "ligand_affinity_hint": 0.1,
                "ligand_h_acceptors": 1,
                "ligand_rot_bonds": 14,
                "contact_fraction": 0.0,
                "stability_score": 0.0,
            },
        ]
    )


def _cache() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "positive_like",
                "feature_cache_status": "ok",
                "ligand_mw": 420.0,
                "pose_preservation_support": 1.0,
                "v14_cationic_anchor_occupancy_support": 1.0,
                "multipolar_basic_pressure": 0.8,
                "label_free_support_pressure": 0.9,
                "pose_distortion_pressure": 0.0,
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy_like",
                "feature_cache_status": "ok",
                "ligand_mw": 240.0,
                "pose_preservation_support": 0.0,
                "v14_cationic_anchor_occupancy_support": 0.0,
                "multipolar_basic_pressure": 0.0,
                "label_free_support_pressure": 0.0,
                "pose_distortion_pressure": 1.0,
            },
        ]
    )


def test_build_replay_scores_positive_like_row_lower_and_keeps_claim_locked(tmp_path: Path) -> None:
    scores_csv = tmp_path / "scores.csv"
    cache_csv = tmp_path / "cache.csv"
    _scores().to_csv(scores_csv, index=False)
    _cache().to_csv(cache_csv, index=False)

    replay_df, payload = mod.build_replay(stage3_scores_csv=scores_csv, feature_cache_csv=cache_csv)

    score_col = payload["summary"]["score_col"]
    by_ligand = replay_df.set_index("ligand_id")
    assert by_ligand.loc["positive_like", score_col] < by_ligand.loc["decoy_like", score_col]
    assert payload["summary"]["status"] == "ready_for_evaluation_claim_locked"
    assert payload["summary"]["claim_promotion_allowed"] is False
    assert payload["summary"]["scorer_apply_allowed"] is False
    assert payload["summary"]["feature_cache_csv"].endswith("cache.csv")
    assert payload["feature_cache"]["matched_row_count"] == 2
    assert payload["summary"]["score_feature_policy_pass"] is True
    assert "target" not in payload["summary"]["score_features_used"]
    assert "ligand_id" not in payload["summary"]["score_features_used"]
    assert "is_binder" not in payload["summary"]["score_features_used"]


def test_build_replay_feature_cache_overlays_stale_stage3_feature_columns(tmp_path: Path) -> None:
    scores = _scores()
    scores["pose_preservation_support"] = 0.0
    scores_csv = tmp_path / "scores.csv"
    cache_csv = tmp_path / "cache.csv"
    scores.to_csv(scores_csv, index=False)
    _cache().to_csv(cache_csv, index=False)

    replay_df, payload = mod.build_replay(stage3_scores_csv=scores_csv, feature_cache_csv=cache_csv)

    by_ligand = replay_df.set_index("ligand_id")
    assert by_ligand.loc["positive_like", "pose_preservation_support"] == 1.0
    assert payload["feature_cache"]["overlay_replaced_column_count"] >= 1
    assert "pose_preservation_support" in payload["feature_cache"]["overlay_replaced_columns"]


def test_replay_cli_writes_artifacts(tmp_path: Path) -> None:
    scores_csv = tmp_path / "scores.csv"
    cache_csv = tmp_path / "cache.csv"
    out_scores = tmp_path / "out.csv"
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    _scores().to_csv(scores_csv, index=False)
    _cache().to_csv(cache_csv, index=False)

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_coverage_v2_adaptive_rank_rescue_shadow_replay.py"),
            "--stage3-scores-csv",
            str(scores_csv),
            "--feature-cache-csv",
            str(cache_csv),
            "--out-scores-csv",
            str(out_scores),
            "--out-summary-json",
            str(out_json),
            "--out-summary-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    replay_df = pd.read_csv(out_scores)
    assert result.returncode == 0
    assert payload["summary"]["claim_promotion_allowed"] is False
    assert payload["summary"]["diagnostic_weight_search_used_labels"] is True
    assert mod.SCORE_COL in replay_df.columns
    assert "GPCR Coverage V2 Adaptive Rank Rescue" in out_md.read_text(encoding="utf-8")
