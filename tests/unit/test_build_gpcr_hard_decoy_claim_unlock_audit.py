from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_gpcr_hard_decoy_claim_unlock_audit as mod


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _official_diagnostic_green() -> dict[str, object]:
    return {
        "summary": {
            "status": "claim_locked_gpcr_hard_decoy_diagnostic_probe",
            "claim_locked": True,
            "claim_lock_reason": "current failure slice rescue rule",
            "diagnostic_status_before_claim_lock": "gpcr_hard_decoy_family_ready",
            "diagnostic_family_claim_safe_before_claim_lock": True,
            "required_target_ids": ["DRD2", "HTR2A", "OPRM1"],
            "green_target_ids": ["DRD2", "HTR2A", "OPRM1"],
            "blocked_target_ids": [],
            "missing_required_target_ids": [],
        }
    }


def _preregistered_replay(*, ci_low: float = 0.5597832604) -> dict[str, object]:
    return {
        "status": "gpcr_hard_decoy_adora2a_preregistered_replay_gate_pass_claim_locked",
        "claim_promotion_allowed": False,
        "canonical_runner_shadow_only_active_locked": True,
        "pre_registered_runner_replay_complete": True,
        "runner_replay_closure_gate_pass": True,
        "score_matches_probe": True,
        "runner_replay_target_heldout": {
            "ranking_pr_auc_ci_low": ci_low,
            "top20_hit_rate": 1.0,
            "target_decoys_above_positive_total": 0,
            "all_required_targets_decoy_clear": True,
            "all_required_targets_anchor_margin_nonnegative": True,
        },
    }


def _independent_repeat(*, passed: bool = True) -> dict[str, object]:
    return {
        "summary": {
            "status": "independent_repeat_passed_claim_locked" if passed else "independent_repeat_blocked",
            "independent_repeat_completed": passed,
            "independent_repeat_ready": False,
            "independent_repeat_result_passed": passed,
            "claim_promotion_allowed": False,
            "ranking_pr_auc_ci_low": 0.761167863,
            "ranking_top20_hit_rate": 1.0,
        }
    }


def _restricted_pass_scorecard() -> dict[str, object]:
    return {
        "summary": {
            "status": "blocked_accuracy_parity",
            "blocked_row_count": 0,
            "missing_row_count": 0,
        },
        "rows": [
            {
                "axis": "ligand_ranking",
                "status": "restricted_pass",
                "blockers": ["broad_gpcr_claim_not_allowed"],
                "claim_promotion_allowed": False,
                "commercial_parity_claim_allowed": False,
                "metrics": {
                    "ranking_pr_auc": 0.871853,
                    "ranking_pr_auc_ci_low": 0.761168,
                    "ranking_topk_hit_rate": 1.0,
                    "gpcr_conditional_prior_boundary_ready": True,
                    "gpcr_oprm1_pose_repair_evidence_ready": True,
                    "crossfit_validation_ready": True,
                },
                "thresholds": {
                    "ranking_pr_auc_min": 0.55,
                    "ranking_pr_auc_ci_low_min": 0.45,
                    "ranking_topk_hit_rate_min": 0.5,
                },
            }
        ],
    }


def _broad_scope_blocked() -> dict[str, object]:
    return {
        "summary": {
            "status": "blocked_gpcr_broad_claim_scope_readiness",
            "target_heldout_broad_scope_review_approved": False,
            "scorer_router_promotion_gate_ready": False,
            "blockers": [
                "formal_broad_claim_review_not_approved",
                "scorer_router_promotion_gate_not_approved",
            ],
        }
    }


def _active_scorer_blocked() -> dict[str, object]:
    return {
        "summary": {
            "status": "blocked_gpcr_active_scorer_promotion_decision",
            "active_scorer_apply_allowed": False,
            "blockers": ["residual_registry_production_promotion_not_allowed"],
        }
    }


def test_claim_unlock_audit_marks_metric_ready_but_promotion_locked(tmp_path: Path) -> None:
    official = tmp_path / "official.json"
    preregistered = tmp_path / "preregistered.json"
    repeat = tmp_path / "repeat.json"
    scorecard = tmp_path / "scorecard.json"
    broad = tmp_path / "broad.json"
    active = tmp_path / "active.json"
    _write_json(official, _official_diagnostic_green())
    _write_json(preregistered, _preregistered_replay())
    _write_json(repeat, _independent_repeat())
    _write_json(scorecard, _restricted_pass_scorecard())
    _write_json(broad, _broad_scope_blocked())
    _write_json(active, _active_scorer_blocked())

    payload = mod.build_gpcr_hard_decoy_claim_unlock_audit(
        official_suite_json=official,
        preregistered_replay_json=preregistered,
        independent_repeat_json=repeat,
        accuracy_scorecard_json=scorecard,
        broad_scope_readiness_json=broad,
        active_scorer_decision_json=active,
    )

    summary = payload["summary"]
    assert summary["status"] == "gpcr_hard_decoy_claim_unlock_metric_evidence_ready_promotion_locked"
    assert summary["phase3_exit_metric_conditions_ready"] is True
    assert summary["hard_decoy_metric_claim_unlock_ready"] is True
    assert summary["independent_repeat_ready_to_launch"] is False
    assert summary["independent_repeat_result_passed"] is True
    assert summary["metric_blockers"] == []
    assert summary["claim_promotion_allowed"] is False
    assert summary["broad_promotion_remains_locked"] is True
    assert "active_scorer_apply_not_allowed" in summary["promotion_blockers"]
    assert summary["effective_phase3_metrics"]["ranking_pr_auc_ci_low"] == 0.5597832604
    assert summary["effective_phase3_metrics"]["decoys_above_positive_count"] == 0


def test_claim_unlock_audit_blocks_without_independent_repeat_pass(tmp_path: Path) -> None:
    official = tmp_path / "official.json"
    preregistered = tmp_path / "preregistered.json"
    repeat = tmp_path / "repeat.json"
    scorecard = tmp_path / "scorecard.json"
    broad = tmp_path / "broad.json"
    active = tmp_path / "active.json"
    _write_json(official, _official_diagnostic_green())
    _write_json(preregistered, _preregistered_replay())
    _write_json(repeat, _independent_repeat(passed=False))
    _write_json(scorecard, _restricted_pass_scorecard())
    _write_json(broad, _broad_scope_blocked())
    _write_json(active, _active_scorer_blocked())

    payload = mod.build_gpcr_hard_decoy_claim_unlock_audit(
        official_suite_json=official,
        preregistered_replay_json=preregistered,
        independent_repeat_json=repeat,
        accuracy_scorecard_json=scorecard,
        broad_scope_readiness_json=broad,
        active_scorer_decision_json=active,
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_gpcr_hard_decoy_claim_unlock_audit"
    assert summary["phase3_exit_metric_conditions_ready"] is False
    assert "independent_repeat_metric_evidence_not_passed" in summary["metric_blockers"]


def test_main_writes_claim_unlock_audit_artifacts(tmp_path: Path) -> None:
    official = tmp_path / "official.json"
    preregistered = tmp_path / "preregistered.json"
    repeat = tmp_path / "repeat.json"
    scorecard = tmp_path / "scorecard.json"
    broad = tmp_path / "broad.json"
    active = tmp_path / "active.json"
    out_json = tmp_path / "audit.json"
    out_md = tmp_path / "audit.md"
    _write_json(official, _official_diagnostic_green())
    _write_json(preregistered, _preregistered_replay())
    _write_json(repeat, _independent_repeat())
    _write_json(scorecard, _restricted_pass_scorecard())
    _write_json(broad, _broad_scope_blocked())
    _write_json(active, _active_scorer_blocked())

    rc = mod.main(
        [
            "--official-suite-json",
            str(official),
            "--preregistered-replay-json",
            str(preregistered),
            "--independent-repeat-json",
            str(repeat),
            "--accuracy-scorecard-json",
            str(scorecard),
            "--broad-scope-readiness-json",
            str(broad),
            "--active-scorer-decision-json",
            str(active),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["packet_type"] == "gpcr_hard_decoy_claim_unlock_audit"
    assert payload["summary"]["phase3_exit_metric_conditions_ready"] is True
    assert out_md.read_text(encoding="utf-8").startswith("# GPCR Hard-Decoy Claim-Unlock Audit")
