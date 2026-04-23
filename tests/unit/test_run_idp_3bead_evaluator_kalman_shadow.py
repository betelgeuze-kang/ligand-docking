from __future__ import annotations

from tools.run_idp_3bead_evaluator import (
    _apply_kalman_feature_state_shadow,
    _apply_kalman_identity_shadow,
    _resolve_kf_feature_mask,
)


def test_apply_kalman_identity_shadow_adds_expected_columns() -> None:
    rows = [
        {
            "on_contact_persistence": 0.21,
            "on_rg_mean": 31.5,
            "on_sasa_proxy_mean": 6200.0,
            "on_ensemble_diversity": 1.4,
            "on_transient_helicity": 0.08,
            "branch_prior_llps_lcd": 0.7,
            "branch_prior_aggregation_prone": 0.2,
            "branch_prior_helix_tad": 0.1,
        }
    ]

    meta = _apply_kalman_identity_shadow(
        rows,
        enabled=True,
        family_token="idp",
        obs_noise_scale=0.15,
        process_noise_scale=0.03,
    )

    row = rows[0]
    assert row["kf_shadow_enabled"] is True
    assert row["kf_shadow_status"] == "identity_shadow"
    assert row["kf_on_contact_persistence"] == row["on_contact_persistence"]
    assert row["kf_on_rg_mean"] == row["on_rg_mean"]
    assert row["kf_on_sasa_proxy_mean"] == row["on_sasa_proxy_mean"]
    assert row["kf_on_ensemble_diversity"] == row["on_ensemble_diversity"]
    assert row["kf_on_transient_helicity"] == row["on_transient_helicity"]
    assert row["kf_branch_prob_llps_lcd"] == 0.7
    assert row["kf_shadow_mean_abs_delta"] == 0.0
    assert row["kf_shadow_max_abs_delta"] == 0.0
    assert row["would_have_changed_state"] is False
    assert row["would_have_changed_gate"] is False
    assert meta["enabled"] is True
    assert meta["status"] == "identity_shadow"
    assert meta["family_token"] == "idp"


def test_apply_kalman_identity_shadow_can_emit_disabled_schema() -> None:
    rows = [
        {
            "on_contact_persistence": 0.1,
            "on_rg_mean": 22.0,
            "on_sasa_proxy_mean": 5100.0,
            "on_ensemble_diversity": 1.1,
            "on_transient_helicity": 0.04,
        }
    ]

    meta = _apply_kalman_identity_shadow(
        rows,
        enabled=False,
        family_token="idp",
        obs_noise_scale=0.0,
        process_noise_scale=0.0,
    )

    row = rows[0]
    assert row["kf_shadow_enabled"] is False
    assert row["kf_shadow_status"] == "disabled"
    assert row["kf_on_contact_persistence"] == row["on_contact_persistence"]
    assert row["would_have_changed_gate"] is False
    assert meta["enabled"] is False
    assert meta["target_count"] == 1


def test_apply_kalman_feature_state_shadow_emits_smoothed_observable_labels() -> None:
    rows = [
        {
            "condition_group": "base",
            "on_contact_persistence": 0.12,
            "on_rg_mean": 30.0,
            "on_sasa_proxy_mean": 6000.0,
            "on_ensemble_diversity": 1.1,
            "on_transient_helicity": 0.08,
            "frac_aromatic": 0.10,
            "net_charge_proxy": 0.02,
            "branch_label": "llps_lcd",
            "branch_prior_llps_lcd": 0.7,
            "branch_prior_aggregation_prone": 0.2,
            "branch_prior_helix_tad": 0.1,
            "pred_state_prob_expanded_disordered": 0.15,
            "pred_state_prob_compact_disordered": 0.20,
            "pred_state_prob_sticky_condensed": 0.35,
            "pred_state_prob_helix_enriched": 0.30,
            "dominant_state_label": "sticky_condensed",
            "dynamic_llps_flag": 1,
            "dynamic_aggregation_flag": 0,
            "baseline_anchor_contact_persistence_lo": 0.20,
            "baseline_anchor_contact_persistence_hi": 0.30,
            "baseline_anchor_rg_mean_lo": 20.0,
            "baseline_anchor_rg_mean_hi": 24.0,
            "baseline_anchor_sasa_proxy_mean_lo": 4000.0,
            "baseline_anchor_sasa_proxy_mean_hi": 4500.0,
            "baseline_anchor_ensemble_diversity_lo": 0.4,
            "baseline_anchor_ensemble_diversity_hi": 0.8,
            "baseline_anchor_transient_helicity_lo": 0.10,
            "baseline_anchor_transient_helicity_hi": 0.16,
        },
        {
            "condition_group": "salt",
            "on_contact_persistence": 0.18,
            "on_rg_mean": 28.5,
            "on_sasa_proxy_mean": 5700.0,
            "on_ensemble_diversity": 0.95,
            "on_transient_helicity": 0.11,
            "frac_aromatic": 0.10,
            "net_charge_proxy": 0.02,
            "branch_label": "llps_lcd",
            "branch_prior_llps_lcd": 0.7,
            "branch_prior_aggregation_prone": 0.2,
            "branch_prior_helix_tad": 0.1,
            "pred_state_prob_expanded_disordered": 0.12,
            "pred_state_prob_compact_disordered": 0.24,
            "pred_state_prob_sticky_condensed": 0.40,
            "pred_state_prob_helix_enriched": 0.24,
            "dominant_state_label": "sticky_condensed",
            "dynamic_llps_flag": 1,
            "dynamic_aggregation_flag": 0,
            "baseline_anchor_contact_persistence_lo": 0.20,
            "baseline_anchor_contact_persistence_hi": 0.30,
            "baseline_anchor_rg_mean_lo": 20.0,
            "baseline_anchor_rg_mean_hi": 24.0,
            "baseline_anchor_sasa_proxy_mean_lo": 4000.0,
            "baseline_anchor_sasa_proxy_mean_hi": 4500.0,
            "baseline_anchor_ensemble_diversity_lo": 0.4,
            "baseline_anchor_ensemble_diversity_hi": 0.8,
            "baseline_anchor_transient_helicity_lo": 0.10,
            "baseline_anchor_transient_helicity_hi": 0.16,
        },
    ]

    meta = _apply_kalman_feature_state_shadow(
        rows,
        enabled=True,
        family_token="idp",
        obs_noise_scale=0.15,
        process_noise_scale=0.03,
        delta_cap_frac=0.25,
    )

    row = rows[0]
    assert row["kf_shadow_status"] == "feature_state_v1_shadow"
    assert row["kf_shadow_mode"] == "feature_state_v1"
    assert row["kf_shadow_anchor_feature_count"] == 5
    assert row["kf_shadow_smoothed_feature_count"] >= 1
    assert "kf_shadow_dominant_state_label" in row
    assert "kf_shadow_llps_flag" in row
    assert "kf_shadow_aggregation_flag" in row
    assert "would_have_changed_llps_flag" in row
    assert "would_have_changed_aggregation_flag" in row
    assert row["would_have_changed_gate"] is False
    assert meta["mode"] == "feature_state_v1"
    assert meta["target_count"] == 2
    assert meta["anchor_feature_count"] == 10


def test_apply_kalman_feature_state_shadow_can_limit_to_rg_sasa_only() -> None:
    rows = [
        {
            "condition_group": "base",
            "on_contact_persistence": 0.12,
            "on_rg_mean": 30.0,
            "on_sasa_proxy_mean": 6000.0,
            "on_ensemble_diversity": 1.1,
            "on_transient_helicity": 0.08,
            "frac_aromatic": 0.10,
            "net_charge_proxy": 0.02,
            "branch_label": "llps_lcd",
            "branch_prior_llps_lcd": 0.7,
            "branch_prior_aggregation_prone": 0.2,
            "branch_prior_helix_tad": 0.1,
            "pred_state_prob_expanded_disordered": 0.15,
            "pred_state_prob_compact_disordered": 0.20,
            "pred_state_prob_sticky_condensed": 0.35,
            "pred_state_prob_helix_enriched": 0.30,
            "dominant_state_label": "sticky_condensed",
            "dynamic_llps_flag": 1,
            "dynamic_aggregation_flag": 0,
            "baseline_anchor_contact_persistence_lo": 0.20,
            "baseline_anchor_contact_persistence_hi": 0.30,
            "baseline_anchor_rg_mean_lo": 20.0,
            "baseline_anchor_rg_mean_hi": 24.0,
            "baseline_anchor_sasa_proxy_mean_lo": 4000.0,
            "baseline_anchor_sasa_proxy_mean_hi": 4500.0,
            "baseline_anchor_ensemble_diversity_lo": 0.4,
            "baseline_anchor_ensemble_diversity_hi": 0.8,
            "baseline_anchor_transient_helicity_lo": 0.10,
            "baseline_anchor_transient_helicity_hi": 0.16,
        },
    ]

    meta = _apply_kalman_feature_state_shadow(
        rows,
        enabled=True,
        family_token="idp",
        obs_noise_scale=0.15,
        process_noise_scale=0.03,
        delta_cap_frac=0.25,
        feature_mask_name="rg_sasa_only",
    )

    row = rows[0]
    assert row["kf_shadow_feature_mask"] == "rg_sasa_only"
    assert row["kf_shadow_anchor_feature_count"] == 2
    assert row["kf_delta_on_contact_persistence"] == 0.0
    assert row["kf_delta_on_ensemble_diversity"] == 0.0
    assert row["kf_delta_on_transient_helicity"] == 0.0
    assert meta["feature_mask_name"] == "rg_sasa_only"
    assert meta["selected_features"] == list(_resolve_kf_feature_mask("rg_sasa_only"))
