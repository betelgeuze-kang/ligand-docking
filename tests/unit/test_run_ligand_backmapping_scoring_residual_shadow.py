from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from tools import run_ligand_backmapping_scoring as mod


def _shadow_args(**overrides):
    base = dict(
        residual_prototype_enabled=True,
        residual_prototype_mode="shadow_only",
        residual_prototype_family="gpcr",
        residual_prototype_spec_json="",
        residual_prototype_runtime_hook_ready=True,
        residual_prototype_max_abs_delta_score=1.5,
        residual_prototype_yellow_band_abs_delta_score=0.75,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def test_apply_residual_prototype_shadow_emits_shadow_columns_without_changing_active_score():
    result_df = pd.DataFrame(
        [
            {"ligand_id": "binder_a", "binding_score_composite_v7": -8.2},
            {"ligand_id": "decoy_b", "binding_score_composite_v7": -6.5},
            {"ligand_id": "decoy_c", "binding_score_composite_v7": -5.9},
        ]
    )
    z_e = pd.Series([-1.0, 0.8, 0.5], dtype=float)
    z_d = pd.Series([-0.5, 1.1, 0.9], dtype=float)
    z_s = pd.Series([0.8, -0.4, -0.2], dtype=float)
    z_c = pd.Series([1.0, -0.7, -0.5], dtype=float)
    z_aff = pd.Series([-0.4, 1.2, 0.7], dtype=float)
    z_logp = pd.Series([0.1, -0.6, -0.3], dtype=float)
    z_rot = pd.Series([0.0, 1.4, 0.9], dtype=float)
    z_hd = pd.Series([0.0, 1.2, 0.6], dtype=float)
    z_ha = pd.Series([0.1, 1.0, 0.8], dtype=float)

    out_df, meta = mod._apply_residual_prototype_shadow(
        result_df.copy(),
        _shadow_args(),
        z_e=z_e,
        z_d=z_d,
        z_s=z_s,
        z_c=z_c,
        z_aff=z_aff,
        z_logp=z_logp,
        z_rot=z_rot,
        z_hd=z_hd,
        z_ha=z_ha,
    )

    assert meta["status"] == "shadow_ready"
    assert meta["active_score_col"] == "binding_score_composite_v7"
    assert meta["shadow_score_col"] == "binding_score_composite_v7_residual_shadow"
    assert int(meta["positive_delta_count"]) >= 1
    assert float(meta["max_delta"]) <= 1.5
    assert "residual_shadow_delta" in out_df.columns
    assert "binding_score_composite_v7_residual_shadow" in out_df.columns
    assert "binding_score_composite_v7_residual_active" in out_df.columns
    np.testing.assert_allclose(
        out_df["binding_score_composite_v7_residual_active"].to_numpy(dtype=float),
        out_df["binding_score_composite_v7"].to_numpy(dtype=float),
    )
    assert bool(out_df["residual_shadow_runtime_hook_ready"].all()) is True


def test_apply_residual_prototype_shadow_apply_mode_switches_active_score_column():
    result_df = pd.DataFrame(
        [
            {"ligand_id": "decoy_a", "binding_score_composite_v7": -6.0},
            {"ligand_id": "decoy_b", "binding_score_composite_v7": -5.5},
        ]
    )
    one = pd.Series([1.0, 0.5], dtype=float)
    zero = pd.Series([0.0, 0.0], dtype=float)

    out_df, meta = mod._apply_residual_prototype_shadow(
        result_df.copy(),
        _shadow_args(residual_prototype_mode="apply"),
        z_e=zero,
        z_d=one,
        z_s=zero,
        z_c=zero,
        z_aff=zero,
        z_logp=zero,
        z_rot=one,
        z_hd=one,
        z_ha=one,
    )

    assert meta["status"] == "apply_ready"
    assert meta["active_score_col"] == "binding_score_composite_v7_residual_active"
    assert not np.allclose(
        out_df["binding_score_composite_v7_residual_active"].to_numpy(dtype=float),
        out_df["binding_score_composite_v7"].to_numpy(dtype=float),
    )


def test_apply_residual_prototype_shadow_narrow_v2_gates_out_supported_rows(tmp_path):
    spec_json = tmp_path / "narrow_v2.json"
    spec_json.write_text(
        json.dumps(
            {
                "prototype": {
                    "constraints": {
                        "max_abs_delta_score": 0.75,
                        "yellow_band_abs_delta_score": 0.35,
                    },
                    "tuning": {
                        "variant": "narrow_v2",
                        "prior_weight_h_donors": 0.22,
                        "prior_weight_h_acceptors": 0.20,
                        "prior_weight_rot_bonds": 0.10,
                        "prior_weight_neg_logp": 0.06,
                        "weakness_weight_distance": 0.80,
                        "weakness_weight_neg_contact": 0.70,
                        "weakness_weight_neg_stability": 0.25,
                        "weakness_weight_energy": 0.15,
                        "support_weight_neg_energy": 0.20,
                        "support_weight_contact": 0.35,
                        "support_weight_stability": 0.10,
                        "support_weight_neg_distance": 0.35,
                        "interaction_bias": 0.20,
                        "affinity_mismatch_weight": 0.12,
                        "affinity_interaction_bias": 0.15,
                        "support_penalty_weight": 0.08,
                        "min_prior_pressure_for_delta": 0.85,
                        "min_structural_weakness_for_delta": 0.90,
                        "max_structural_support_for_delta": 0.20,
                        "min_raw_delta_for_activation": 0.25,
                        "require_distance_above_z": 0.35,
                        "require_contact_below_z": -0.20,
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    result_df = pd.DataFrame(
        [
            {"ligand_id": "weak_decoy", "binding_score_composite_v7": -6.2},
            {"ligand_id": "supported_decoy", "binding_score_composite_v7": -6.1},
        ]
    )
    z_e = pd.Series([1.2, -0.4], dtype=float)
    z_d = pd.Series([1.5, -0.3], dtype=float)
    z_s = pd.Series([-0.6, 0.5], dtype=float)
    z_c = pd.Series([-1.3, 0.8], dtype=float)
    z_aff = pd.Series([1.2, 0.7], dtype=float)
    z_logp = pd.Series([-0.4, -0.4], dtype=float)
    z_rot = pd.Series([2.2, 1.3], dtype=float)
    z_hd = pd.Series([2.0, 1.2], dtype=float)
    z_ha = pd.Series([1.9, 1.1], dtype=float)

    out_df, meta = mod._apply_residual_prototype_shadow(
        result_df.copy(),
        _shadow_args(
            residual_prototype_mode="apply",
            residual_prototype_spec_json=str(spec_json),
            residual_prototype_max_abs_delta_score=None,
            residual_prototype_yellow_band_abs_delta_score=None,
        ),
        z_e=z_e,
        z_d=z_d,
        z_s=z_s,
        z_c=z_c,
        z_aff=z_aff,
        z_logp=z_logp,
        z_rot=z_rot,
        z_hd=z_hd,
        z_ha=z_ha,
    )

    assert meta["tuning_variant"] == "narrow_v2"
    deltas = out_df["residual_shadow_delta"].to_numpy(dtype=float)
    assert deltas[0] > 0.0
    assert deltas[1] == 0.0


def test_apply_residual_prototype_shadow_linear_rescore_replace_mode(tmp_path):
    spec_json = tmp_path / "linear_rescore.json"
    spec_json.write_text(
        json.dumps(
            {
                "prototype": {
                    "linear_rescore": {
                        "enabled": True,
                        "combine_mode": "replace",
                        "intercept": 0.25,
                        "terms": [
                            {"feature": "binding_score_composite_v7", "weight": 1.0},
                            {"feature": "z_ligand_h_donors", "weight": 2.0},
                            {"feature": "residual_shadow_prior_pressure", "weight": 0.5},
                        ],
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    result_df = pd.DataFrame(
        [
            {"ligand_id": "binder_a", "binding_score_composite_v7": -8.0},
            {"ligand_id": "decoy_b", "binding_score_composite_v7": -8.0},
        ]
    )
    zero = pd.Series([0.0, 0.0], dtype=float)
    z_hd = pd.Series([-1.0, 1.0], dtype=float)

    out_df, meta = mod._apply_residual_prototype_shadow(
        result_df.copy(),
        _shadow_args(
            residual_prototype_mode="apply",
            residual_prototype_spec_json=str(spec_json),
        ),
        z_e=zero,
        z_d=zero,
        z_s=zero,
        z_c=zero,
        z_aff=zero,
        z_logp=zero,
        z_rot=zero,
        z_hd=z_hd,
        z_ha=zero,
    )

    assert meta["linear_rescore_enabled"] is True
    assert meta["linear_rescore_status"] == "applied"
    assert meta["linear_rescore_term_count"] == 3
    assert meta["linear_rescore_missing_terms"] == []
    assert meta["shadow_score_col"] == "binding_score_composite_v7_residual_shadow"
    assert out_df.loc[0, "binding_score_composite_v7_residual_shadow"] < out_df.loc[1, "binding_score_composite_v7_residual_shadow"]
    np.testing.assert_allclose(
        out_df["binding_score_composite_v7_residual_active"].to_numpy(dtype=float),
        out_df["binding_score_composite_v7_residual_shadow"].to_numpy(dtype=float),
    )
