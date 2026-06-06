from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from tools.product import replay_gpcr_residual_shadow_scores as mod

ROOT = Path(__file__).resolve().parents[2]


def _write_v6_spec(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "prototype": {
                    "constraints": {
                        "claim_locked_candidate": True,
                        "shadow_only_candidate": True,
                        "active_score_locked_to_base": True,
                        "scorer_apply_allowed": False,
                    },
                    "tuning": {
                        "variant": "gpcr_core_class_a_motif_shadow_v6",
                        "scope": "class_a_aminergic_opioid_like_orthosteric_sublane",
                    },
                    "linear_rescore": {
                        "enabled": True,
                        "combine_mode": "replace",
                        "intercept": 0.0,
                        "terms": [
                            {"feature": "binding_score_composite_v7_prior_active", "weight": 1.0},
                            {"feature": "class_a_orthosteric_motif_support_proxy", "weight": -0.75},
                            {"feature": "class_a_prior_overreward_invalid_overanchor_pressure", "weight": 1.10},
                        ],
                    },
                }
            }
        ),
        encoding="utf-8",
    )


def _write_v8_spec(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "prototype": {
                    "constraints": {
                        "claim_locked_candidate": True,
                        "shadow_only_candidate": True,
                        "score_only_candidate": True,
                        "active_score_locked_to_base": True,
                        "requires_precomputed_atom_window_features": True,
                        "scorer_apply_allowed": False,
                    },
                    "tuning": {
                        "variant": "gpcr_core_direct_atom_anchor_window_shadow_v8",
                        "scope": "class_a_aminergic_opioid_like_orthosteric_sublane",
                    },
                    "linear_rescore": {
                        "enabled": True,
                        "combine_mode": "replace",
                        "intercept": 0.0,
                        "terms": [
                            {"feature": "binding_score_composite_v7_prior_active", "weight": 1.0},
                            {"feature": "class_a_direct_atom_window_anchor_geometry_proxy", "weight": -0.75},
                            {"feature": "class_a_atom_window_pose_survival_proxy", "weight": -0.20},
                            {"feature": "class_a_hydrophobic_overcontact_pressure_v8", "weight": 1.35},
                        ],
                    },
                }
            }
        ),
        encoding="utf-8",
    )


def _fixture_scores() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "queue_id": "drd2_pos",
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "pos",
                "ligand_smiles": "CN(C)CCc1ccccc1",
                "binding_energy_mmpbsa_kcal_mol_proxy": -1.2,
                "mean_min_distance_A": 3.2,
                "stability_score": 0.9,
                "contact_fraction": 0.8,
                "binding_energy_mmpbsa_std": 0.1,
                "ligand_affinity_hint": 0.4,
                "ligand_onsps_norm": 0.2,
                "ligand_mw": 280.0,
                "ligand_logp": 2.1,
                "ligand_rot_bonds": 5,
                "ligand_h_donors": 1,
                "ligand_h_acceptors": 2,
            },
            {
                "queue_id": "drd2_decoy",
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy",
                "ligand_smiles": "CCCCCCc1ccccc1",
                "binding_energy_mmpbsa_kcal_mol_proxy": -0.8,
                "mean_min_distance_A": 2.1,
                "stability_score": 0.2,
                "contact_fraction": 1.0,
                "binding_energy_mmpbsa_std": 0.2,
                "ligand_affinity_hint": 1.4,
                "ligand_onsps_norm": 0.3,
                "ligand_mw": 300.0,
                "ligand_logp": 4.8,
                "ligand_rot_bonds": 7,
                "ligand_h_donors": 0,
                "ligand_h_acceptors": 0,
            },
        ]
    )


def test_build_replay_keeps_active_score_locked_and_emits_v6_shadow_terms(tmp_path: Path) -> None:
    spec_json = tmp_path / "v6.json"
    scores_csv = tmp_path / "scores.csv"
    _write_v6_spec(spec_json)
    _fixture_scores().to_csv(scores_csv, index=False)

    replay_df, payload = mod.build_replay(
        input_scores_csv=scores_csv,
        residual_prototype_spec_json=spec_json,
    )

    assert payload["summary"]["status"] == "ready_for_evaluation"
    assert payload["summary"]["active_score_locked_to_base"] is True
    assert payload["residual_prototype"]["tuning_variant"] == "gpcr_core_class_a_motif_shadow_v6"
    assert payload["residual_prototype"]["shadow_only_active_locked"] is True
    np.testing.assert_allclose(
        replay_df["binding_score_composite_v7_residual_active"].to_numpy(dtype=float),
        replay_df["binding_score_composite_v7"].to_numpy(dtype=float),
    )
    assert replay_df.loc[0, "class_a_orthosteric_motif_support_proxy"] > 0.0
    assert replay_df.loc[1, "class_a_prior_overreward_invalid_overanchor_pressure"] > 0.0


def test_replay_cli_writes_scores_and_summary(tmp_path: Path) -> None:
    spec_json = tmp_path / "v6.json"
    scores_csv = tmp_path / "scores.csv"
    out_scores = tmp_path / "out_scores.csv"
    out_json = tmp_path / "summary.json"
    out_md = tmp_path / "summary.md"
    _write_v6_spec(spec_json)
    _fixture_scores().to_csv(scores_csv, index=False)

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/product/replay_gpcr_residual_shadow_scores.py"),
            "--input-scores-csv",
            str(scores_csv),
            "--residual-prototype-spec-json",
            str(spec_json),
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
    assert payload["summary"]["status"] == "ready_for_evaluation"
    assert payload["summary"]["claim_promotion_allowed"] is False
    assert "GPCR Residual Shadow Replay" in out_md.read_text(encoding="utf-8")
    assert "binding_score_composite_v7_residual_shadow" in replay_df.columns


def test_build_replay_merges_atom_window_feature_cache_for_v8(tmp_path: Path) -> None:
    spec_json = tmp_path / "v8.json"
    scores_csv = tmp_path / "scores.csv"
    cache_csv = tmp_path / "cache.csv"
    _write_v8_spec(spec_json)
    _fixture_scores().to_csv(scores_csv, index=False)
    pd.DataFrame(
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "pos",
                "class_a_atom_anchor_available": 1,
                "class_a_atom_anchor_min_distance_A": 3.0,
                "class_a_atom_anchor_p10_distance_A": 3.1,
                "class_a_atom_anchor_mean_distance_A": 3.4,
                "class_a_atom_anchor_contact_fraction_le_2p8A": 0.0,
                "class_a_atom_anchor_contact_fraction_2p8_4p2A": 0.9,
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy",
                "class_a_atom_anchor_available": 1,
                "class_a_atom_anchor_min_distance_A": 2.1,
                "class_a_atom_anchor_p10_distance_A": 2.3,
                "class_a_atom_anchor_mean_distance_A": 2.5,
                "class_a_atom_anchor_contact_fraction_le_2p8A": 0.8,
                "class_a_atom_anchor_contact_fraction_2p8_4p2A": 0.1,
            },
        ]
    ).to_csv(cache_csv, index=False)

    replay_df, payload = mod.build_replay(
        input_scores_csv=scores_csv,
        residual_prototype_spec_json=spec_json,
        feature_cache_csv=cache_csv,
    )

    assert payload["summary"]["status"] == "ready_for_evaluation"
    assert payload["summary"]["feature_cache_enabled"] is True
    assert payload["summary"]["feature_cache_matched_row_count"] == 2
    assert payload["feature_cache"]["matched_row_count"] == 2
    assert payload["residual_prototype"]["tuning_variant"] == "gpcr_core_direct_atom_anchor_window_shadow_v8"
    assert payload["residual_prototype"]["class_a_atom_anchor_feature_available_count"] == 2
    assert replay_df.loc[0, "class_a_direct_atom_window_anchor_geometry_proxy"] > 0.0
    assert replay_df.loc[1, "class_a_hydrophobic_overcontact_pressure_v8"] > 0.0


def test_build_replay_resets_stale_prior_active_to_base_by_default(tmp_path: Path) -> None:
    spec_json = tmp_path / "v8.json"
    scores_csv = tmp_path / "scores.csv"
    cache_csv = tmp_path / "cache.csv"
    _write_v8_spec(spec_json)
    scores = _fixture_scores()
    scores["binding_score_composite_v7_residual_active"] = 999.0
    scores.to_csv(scores_csv, index=False)
    pd.DataFrame(
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "pos",
                "class_a_atom_anchor_available": 1,
                "class_a_atom_anchor_min_distance_A": 3.0,
                "class_a_atom_anchor_p10_distance_A": 3.1,
                "class_a_atom_anchor_mean_distance_A": 3.4,
                "class_a_atom_anchor_contact_fraction_le_2p8A": 0.0,
                "class_a_atom_anchor_contact_fraction_2p8_4p2A": 0.9,
            }
        ]
    ).to_csv(cache_csv, index=False)

    replay_df, payload = mod.build_replay(
        input_scores_csv=scores_csv,
        residual_prototype_spec_json=spec_json,
        feature_cache_csv=cache_csv,
    )

    assert payload["summary"]["reset_prior_active_to_base"] is True
    assert replay_df["binding_score_composite_v7_prior_active"].max() < 999.0
