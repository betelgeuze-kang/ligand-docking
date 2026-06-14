from __future__ import annotations

import json
from pathlib import Path

from tools.gpcr_replay import build_gpcr_active_scorer_promotion_decision_packet as active_mod
from tools.gpcr_replay import build_gpcr_commercial_phase_ab_closure_chain as phase_ab_mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _restricted_pass_scorecard(*, pr_auc: float = 0.871853) -> dict:
    return {
        "summary": {
            "status": "blocked_accuracy_parity",
            "pass_row_count": 4,
            "restricted_pass_row_count": 1,
            "blocked_row_count": 0,
            "missing_row_count": 0,
            "overall_commercial_tool_accuracy_parity_allowed": False,
            "schrodinger_class_claim_allowed": False,
            "top_blockers": ["ligand_ranking:broad_gpcr_claim_not_allowed"],
        },
        "rows": [
            {
                "axis": "ligand_ranking",
                "status": "restricted_pass",
                "blockers": ["broad_gpcr_claim_not_allowed"],
                "claim_promotion_allowed": False,
                "commercial_parity_claim_allowed": False,
                "metrics": {
                    "ranking_pr_auc": pr_auc,
                    "ranking_pr_auc_ci_low": 0.761168,
                    "ranking_topk_hit_rate": 1.0,
                    "crossfit_validation_ready": True,
                    "gpcr_conditional_prior_boundary_ready": True,
                    "gpcr_oprm1_pose_repair_evidence_ready": True,
                },
                "thresholds": {
                    "ranking_pr_auc_min": 0.55,
                    "ranking_pr_auc_ci_low_min": 0.45,
                    "ranking_topk_hit_rate_min": 0.5,
                },
            }
        ],
    }


def test_active_scorer_treats_restricted_pass_accuracy_as_metric_ready(tmp_path: Path) -> None:
    phase_ab = tmp_path / "phase_ab.json"
    operational = tmp_path / "operational.json"
    repeat = tmp_path / "repeat.json"
    scorecard = tmp_path / "scorecard.json"
    approval = tmp_path / "approval.json"
    bundle = tmp_path / "bundle.json"
    delivery = tmp_path / "delivery.json"
    registry = tmp_path / "registry.json"

    _write_json(phase_ab, {"summary": {"phase_a_claim_closure_ready": True, "phase_b_product_delivery_ready": True}})
    _write_json(
        operational,
        {
            "summary": {
                "status": "guarded_operational_gate_refresh_complete_claim_locked",
                "lanes": {"guarded_100k_rerun_readiness": {"summary": {"launch_status": "eligible"}}},
            }
        },
    )
    _write_json(repeat, {"summary": {"status": "independent_repeat_passed_claim_locked"}})
    _write_json(scorecard, _restricted_pass_scorecard())
    _write_json(approval, {"summary": {"authorized_for_execution": True}})
    _write_json(bundle, {"summary": {"status": "product_bundle_contract_ready", "bundle_validation_passed": True}})
    _write_json(delivery, {"summary": {"delivery_ready_claim_allowed": True}})
    _write_json(registry, {"summary": {"production_promotion_allowed": False}})

    payload = active_mod.build_packet(
        phase_ab_chain_json=phase_ab,
        operational_gate_json=operational,
        independent_repeat_json=repeat,
        scorecard_json=scorecard,
        approval_gate_json=approval,
        bundle_contract_json=bundle,
        delivery_evidence_json=delivery,
        residual_registry_json=registry,
        generated_at_local="2026-06-14T00:00:00+09:00",
    )
    summary = payload["summary"]

    assert summary["accuracy_parity_metric_ready"] is True
    assert summary["accuracy_parity_claim_scope_lock_only"] is True
    assert summary["accuracy_parity_metric_blockers"] == []
    assert "accuracy_parity_scorecard_not_green" not in summary["blockers"]
    assert summary["blockers"] == ["residual_registry_production_promotion_not_allowed"]
    assert summary["active_scorer_apply_allowed"] is False
    assert summary["claim_promotion_allowed"] is False


def test_active_scorer_blocks_when_restricted_pass_metrics_do_not_clear() -> None:
    readiness = active_mod.scorecard_metric_ready_under_claim_lock(_restricted_pass_scorecard(pr_auc=0.4))

    assert readiness["metric_ready"] is False
    assert "ranking_pr_auc_below_threshold" in readiness["metric_blockers"]


def test_phase_ab_defaults_to_rank_rescue_accuracy_parity_evidence() -> None:
    assert (
        phase_ab_mod.ACCURACY_PARITY_RANK_RESCUE_EVIDENCE_JSON
        == "runs/gpcr_rank_rescue_crossfit_repeat_r1_evidence_packet_current.json"
    )


def test_phase_ab_accepts_restricted_pass_accuracy_metric_scope(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(phase_ab_mod, "ROOT", tmp_path)
    monkeypatch.setattr(phase_ab_mod, "_run", lambda _cmd: None)

    runs = tmp_path / "runs"
    _write_json(
        runs / "gpcr_guarded_operational_gate_refresh_chain_current.json",
        {"summary": {"status": "guarded_operational_gate_refresh_complete_claim_locked", "blockers": []}},
    )
    _write_json(runs / "accuracy_parity_scorecard_current.json", _restricted_pass_scorecard())
    _write_json(
        runs / "gpcr_a1_accuracy_repair_queue_current.json",
        {"summary": {"full_guarded_100k_review_passed": True}},
    )
    _write_json(
        runs / "gpcr_a1_independent_repeat_packet_current.json",
        {"summary": {"status": "independent_repeat_passed_claim_locked", "blockers": []}},
    )
    _write_json(
        runs / "gpcr_frozen_ranking_quality_repair_chain_current.json",
        {"summary": {"status": "ranking_quality_repair_chain_complete_claim_locked", "blockers": []}},
    )

    payload = phase_ab_mod.build_packet(skip_phase_b=True, generated_at_local="2026-06-14T00:00:00+09:00")
    summary = payload["summary"]

    assert summary["phase_a_claim_closure_ready"] is True
    assert summary["accuracy_parity_metric_ready"] is True
    assert summary["accuracy_parity_claim_scope_lock_only"] is True
    assert "phase_a:accuracy_parity_scorecard_not_green" not in summary["blockers"]
