from __future__ import annotations

from tools.build_idp_kalman_shadow_disagreement_summary import build_payload


def test_build_idp_kalman_shadow_disagreement_summary() -> None:
    holdout_summary = {
        "fold_count": 2,
        "combined_corrected_eval_json": "runs/fake_corrected_eval.json",
    }
    corrected_eval = {
        "targets": [
            {
                "holdout_fold": "fus_lcd",
                "kf_shadow_enabled": True,
                "kf_shadow_status": "identity_shadow",
                "kf_shadow_family_token": "idp",
                "kf_shadow_support_count": 11,
                "kf_shadow_obs_noise_scale": 0.15,
                "kf_shadow_process_noise_scale": 0.03,
                "kf_shadow_mean_abs_delta": 0.0,
                "kf_shadow_max_abs_delta": 0.0,
                "would_have_changed_state": False,
                "would_have_changed_gate": False,
            },
            {
                "holdout_fold": "tau_k18",
                "kf_shadow_enabled": True,
                "kf_shadow_status": "identity_shadow",
                "kf_shadow_family_token": "idp",
                "kf_shadow_support_count": 11,
                "kf_shadow_obs_noise_scale": 0.15,
                "kf_shadow_process_noise_scale": 0.03,
                "kf_shadow_mean_abs_delta": 0.0,
                "kf_shadow_max_abs_delta": 0.0,
                "would_have_changed_state": False,
                "would_have_changed_gate": False,
            },
        ]
    }
    payload = build_payload(holdout_summary, corrected_eval)
    assert payload["summary"]["fold_count"] == 2
    assert payload["summary"]["target_row_count"] == 2
    assert payload["summary"]["kf_schema_row_count"] == 2
    assert payload["summary"]["kf_identity_shadow_ready"] is True
    assert payload["overall"]["would_have_changed_state_count"] == 0
    assert payload["overall"]["would_have_changed_gate_count"] == 0
    assert len(payload["fold_rows"]) == 2
    assert payload["fold_rows"][0]["kf_statuses"] == "identity_shadow"
