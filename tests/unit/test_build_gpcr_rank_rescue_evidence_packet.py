from __future__ import annotations

from tools import build_gpcr_rank_rescue_evidence_packet as mod


def test_build_packet_keeps_metric_pass_claim_locked(tmp_path):
    ranking_json = tmp_path / "ranking.json"
    replay_json = tmp_path / "replay.json"
    weight_json = tmp_path / "weights.json"
    ranking_json.write_text(
        """
{
  "metrics": {
    "pr_auc_unique_key": 0.74,
    "positive_count_unique_key": 34,
    "probability_score_col_used": "shadow_score"
  },
  "metrics_ci_unique": {"pr_auc": {"low": 0.60}},
  "topk_unique": [{"k": 20, "hit_rate": 0.85}]
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    replay_json.write_text(
        """
{
  "summary": {
    "diagnostic_weight_search_used_labels": true,
    "claim_promotion_allowed": false
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    weight_json.write_text(
        """
{
  "diagnostic_weight_search_used_labels": true
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    packet = mod.build_packet(
        ranking_json=ranking_json,
        replay_json=replay_json,
        weight_spec_json=weight_json,
        independent_repeat_completed=False,
    )

    summary = packet["summary"]
    assert summary["status"] == "metric_pass_claim_locked"
    assert summary["metric_thresholds_pass"] is True
    assert summary["claim_promotion_allowed"] is False
    assert "label_derived_weight_selection_requires_independent_repeat" in summary["blockers"]
    assert "independent_repeat_missing" in summary["blockers"]
    assert "ranking_pr_auc_below_threshold" not in summary["blockers"]


def test_build_packet_keeps_metric_blockers_when_thresholds_fail(tmp_path):
    ranking_json = tmp_path / "ranking.json"
    replay_json = tmp_path / "replay.json"
    weight_json = tmp_path / "weights.json"
    ranking_json.write_text(
        """
{
  "metrics": {"pr_auc": 0.40, "positive_count": 10},
  "metrics_ci": {"pr_auc": {"low": 0.20}},
  "topk": [{"k": 20, "hit_rate": 0.10}]
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    replay_json.write_text('{"summary": {"claim_promotion_allowed": false}}\n', encoding="utf-8")
    weight_json.write_text("{}\n", encoding="utf-8")

    packet = mod.build_packet(
        ranking_json=ranking_json,
        replay_json=replay_json,
        weight_spec_json=weight_json,
        independent_repeat_completed=True,
    )

    summary = packet["summary"]
    assert summary["status"] == "metric_blocked_claim_locked"
    assert summary["metric_thresholds_pass"] is False
    assert "ranking_pr_auc_below_threshold" in summary["blockers"]
    assert "ranking_pr_auc_ci_low_below_threshold" in summary["blockers"]
    assert "topk_hit_rate_below_threshold" in summary["blockers"]


def test_build_packet_accepts_independent_crossfit_validation(tmp_path):
    ranking_json = tmp_path / "ranking.json"
    replay_json = tmp_path / "replay.json"
    ranking_json.write_text(
        """
{
  "metrics": {
    "pr_auc_unique_key": 0.70,
    "positive_count_unique_key": 34,
    "probability_score_col_used": "crossfit_score"
  },
  "metrics_ci_unique": {"pr_auc": {"low": 0.55}},
  "topk_unique": [{"k": 20, "hit_rate": 0.80}]
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    replay_json.write_text(
        """
{
  "summary": {
    "diagnostic_weight_search_used_labels": false,
    "out_of_fold_scoring": true,
    "same_row_label_leakage": false,
    "same_ligand_label_leakage": false,
    "score_feature_policy_pass": true,
    "validation_claim_promotion_allowed": true,
    "claim_promotion_allowed": true
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    packet = mod.build_packet(
        ranking_json=ranking_json,
        replay_json=replay_json,
        weight_spec_json="",
        independent_repeat_completed=True,
    )

    summary = packet["summary"]
    assert summary["status"] == "metric_pass_claim_ready"
    assert summary["claim_promotion_allowed"] is True
    assert summary["crossfit_validation_ready"] is True
    assert summary["blockers"] == []
