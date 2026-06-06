from __future__ import annotations

from tools.gpcr_replay import build_gpcr_apply_safe_endpoint as mod


def test_build_gpcr_apply_safe_endpoint_router_blocked() -> None:
    decision_payload = {
        "decision": "no_go_for_100k_router",
        "pass_regressions": 0,
    }
    comparison_payload = {
        "rows": [
            {
                "task_id": "gpcr_core_full",
                "baseline_pass": True,
                "apply_pass": True,
                "delta_pr_auc_apply_vs_baseline": 0.0,
                "delta_ef1_apply_vs_baseline": 0.0,
                "baseline_pr_auc": 1.0,
                "apply_pr_auc": 1.0,
                "baseline_ef1": 98.2,
                "apply_ef1": 98.2,
            },
            {
                "task_id": "gpcr_chembl50_full",
                "baseline_pass": True,
                "apply_pass": True,
                "delta_pr_auc_apply_vs_baseline": -0.0001,
                "delta_ef1_apply_vs_baseline": 1.77,
                "baseline_pr_auc": 0.988,
                "apply_pr_auc": 0.9879,
                "baseline_ef1": 88.5,
                "apply_ef1": 90.3,
            },
        ]
    }
    payload = mod.build_payload(decision_payload, comparison_payload)
    assert payload["summary"]["endpoint_status"] == "locked_decoy_apply_safe_router_blocked"
    assert payload["summary"]["apply_safe"] is True
    assert payload["summary"]["chembl50_ef1_delta_vs_baseline"] == 1.77

