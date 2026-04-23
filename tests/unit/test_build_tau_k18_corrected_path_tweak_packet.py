from __future__ import annotations

from tools import build_tau_k18_corrected_path_tweak_packet as mod


def test_build_tau_k18_corrected_path_tweak_packet() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "operator_scope_now": "controlled_shadow_only_commercial_pretest",
                "shadow_safe_retained": True,
                "broader_promotion_blocked": True,
                "blocking_target": "tau_k18",
                "blocking_class": "corrected_path_fragility",
            }
        },
        {
            "summary": {
                "status": "fallback_trial_completed_blocker_persists",
                "primary_hotspot_metric": "anti_collapse_force_mean",
                "fallback_corrected_dominant_state_accuracy": 0.5,
                "branch_macro_f1": 0.3333,
                "llps_flag_pr_auc": 0.0,
            }
        },
        {
            "summary": {
                "primary_hotspot_metric": "anti_collapse_force_mean",
            },
            "rows": [
                {
                    "condition_group": "base",
                    "true_dominant_state": "compact_disordered",
                    "pred_state": "helix_enriched",
                    "pred_aggregation_prob": 0.25,
                    "on_anti_collapse_force_mean": 2.5,
                    "on_anti_collapse_rg_target_A": 48.9,
                    "conditional_anti_collapse_scale": 1.0,
                    "residual_target_pass": True,
                    "would_have_changed_state": False,
                    "would_have_changed_gate": False,
                }
            ],
        },
        {
            "target_overrides": {
                "tau_k18": {
                    "anti_spread_scale": 1.72,
                }
            }
        },
        out_force_policy_json="runs/idp_branch_force_policy_tau_k18_antispread195_current.json",
        out_eval_config_json="runs/tau_k18_corrected_path_antispread195_eval_current.json",
        out_prefix="runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_antispread195_r1",
        tweak_field_name="anti_spread_scale",
        new_value=1.95,
    )

    summary = payload["summary"]
    assert summary["status"] == "operator_tweak_packet_ready"
    assert summary["tweak_field"] == "target_overrides.tau_k18.anti_spread_scale"
    assert summary["original_value"] == 1.72
    assert summary["tweaked_value"] == 1.95
    assert "anti_spread_scale" in summary["tweak_rationale"]
    assert "--eval-config-json" in summary["exact_command"]
    assert "seed123_antispread195_r1" in summary["exact_command"]
    assert payload["rows"][0]["condition_group"] == "base"


def test_clone_force_policy_and_eval_config() -> None:
    force_policy = {
        "target_overrides": {
            "tau_k18": {
                "anti_spread_scale": 1.72,
                "anti_collapse_scale": 1.08,
            }
        }
    }
    eval_config = {
        "runtime": {
            "idp_branch_force_policy_json": "/tmp/original.json",
        }
    }

    tweaked_force = mod._clone_force_policy(
        force_policy,
        tweak_field_name="anti_spread_scale",
        new_value=1.95,
    )
    tweaked_eval = mod._clone_eval_config(
        eval_config,
        out_force_policy_json="runs/idp_branch_force_policy_tau_k18_antispread195_current.json",
    )

    assert tweaked_force["target_overrides"]["tau_k18"]["anti_spread_scale"] == 1.95
    assert tweaked_force["target_overrides"]["tau_k18"]["anti_collapse_scale"] == 1.08
    assert tweaked_eval["runtime"]["idp_branch_force_policy_json"].endswith(
        "runs/idp_branch_force_policy_tau_k18_antispread195_current.json"
    )
