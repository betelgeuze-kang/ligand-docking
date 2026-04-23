from __future__ import annotations

from tools import build_gpcr_residual_progression_comparison as mod


def test_build_gpcr_residual_progression_comparison() -> None:
    v3 = {
        "rows": [
            {
                "task_id": "gpcr_core_full",
                "baseline_pr_auc": 1.0,
                "shadow_pr_auc": 0.9484,
                "apply_pr_auc": 0.9484,
                "baseline_ef1": 98.2,
                "shadow_ef1": 98.2,
                "apply_ef1": 98.2,
                "delta_pr_auc_apply_vs_baseline": -0.0516,
                "delta_ef1_apply_vs_baseline": 0.0,
            },
            {
                "task_id": "gpcr_chembl50_full",
                "baseline_pr_auc": 0.9880,
                "shadow_pr_auc": 0.9883,
                "apply_pr_auc": 0.9898,
                "baseline_ef1": 88.5,
                "shadow_ef1": 88.5,
                "apply_ef1": 90.3,
                "delta_pr_auc_apply_vs_baseline": 0.0017,
                "delta_ef1_apply_vs_baseline": 1.7,
            },
        ]
    }
    v4 = {
        "rows": [
            {
                "task_id": "gpcr_core_full",
                "baseline_pr_auc": 1.0,
                "shadow_pr_auc": 1.0,
                "apply_pr_auc": 1.0,
                "baseline_ef1": 98.2,
                "shadow_ef1": 98.2,
                "apply_ef1": 98.2,
                "delta_pr_auc_apply_vs_baseline": 0.0,
                "delta_ef1_apply_vs_baseline": 0.0,
            },
            {
                "task_id": "gpcr_chembl50_full",
                "baseline_pr_auc": 0.9880,
                "shadow_pr_auc": 0.9886,
                "apply_pr_auc": 0.9879,
                "baseline_ef1": 88.5,
                "shadow_ef1": 88.5,
                "apply_ef1": 90.3,
                "delta_pr_auc_apply_vs_baseline": -0.0001,
                "delta_ef1_apply_vs_baseline": 1.7,
            },
        ]
    }
    payload = mod.build_payload(v3, v4)
    assert payload["summary"]["task_count"] == 2
    assert payload["summary"]["core_v4_apply_preserves_baseline"] is True
    assert payload["summary"]["chembl50_v4_apply_has_ef1_gain"] is True
