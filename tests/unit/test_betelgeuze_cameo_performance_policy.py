from __future__ import annotations

from betelgeuze_cameo.performance_policy import build_cameo_performance_threshold_policy


def test_cameo_performance_threshold_policy_ready_without_external_actions() -> None:
    payload = build_cameo_performance_threshold_policy()

    summary = payload["summary"]
    assert summary["status"] == "cameo_performance_threshold_policy_ready"
    assert summary["threshold_policy_ready"] is True
    assert summary["min_model1_lddt"] == 0.70
    assert summary["min_model1_tm_score"] == 0.50
    assert summary["max_model1_rmsd_A"] == 5.0
    assert summary["official_results_fetched"] is False
    assert summary["native_local_accuracy_used"] is False
    assert summary["prediction_generation_enabled"] is False
    assert summary["outbound_email_enabled"] is False
    assert summary["external_state_mutated"] is False


def test_cameo_performance_threshold_policy_blocks_permissive_placeholders() -> None:
    payload = build_cameo_performance_threshold_policy(
        thresholds={
            "min_model1_lddt": 0.0,
            "min_model1_tm_score": 0.0,
            "max_model1_rmsd_A": 999999.0,
        }
    )

    assert payload["summary"]["status"] == "blocked_cameo_performance_threshold_policy"
    codes = {blocker["code"] for blocker in payload["blockers"]}
    assert "lddt_threshold_product_grade_not_ready" in codes
    assert "tm_score_threshold_product_grade_not_ready" in codes
    assert "rmsd_threshold_finite_not_ready" in codes
