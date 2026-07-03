from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest


def _load_module(monkeypatch, artifact_path: Path, claim_unlock_path: Path | None = None):
    pytest.importorskip("fastapi")
    import importlib

    mod = importlib.import_module("api.product_gpcr_hard_decoy")
    monkeypatch.setattr(mod, "GPCR_HARD_DECOY_SUITE_ARTIFACT", artifact_path)
    monkeypatch.setattr(
        mod,
        "GPCR_HARD_DECOY_CLAIM_UNLOCK_AUDIT_ARTIFACT",
        claim_unlock_path or artifact_path.parent / "missing_claim_unlock_audit.json",
    )
    return mod


def _write_artifact(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "packet_type": "gpcr_hard_decoy_suite_report",
                "schema_version": "gpcr_hard_decoy_suite_report_v1",
                "materializer_status": "materialized",
                "summary": {
                    "schema_version": "gpcr_hard_decoy_suite_v1",
                    "status": "broad_family_locked",
                    "family_claim_safe": False,
                    "required_target_ids": ["DRD2", "HTR2A", "OPRM1"],
                    "target_count": 3,
                    "green_target_ids": ["HTR2A"],
                    "blocked_target_ids": ["DRD2", "OPRM1"],
                    "missing_required_target_ids": [],
                    "first_blocked_required_target": "DRD2",
                    "gate": {"ci_low_min": 0.45, "top20_min": 0.2},
                    "claim_boundary": "GPCR hard-decoy suite contract ...",
                    "execution_enabled": False,
                    "external_state_mutated": False,
                    "docking_results_emitted": False,
                },
                "targets": [
                    {
                        "target_id": "DRD2",
                        "gate_status": "blocked",
                        "claim_safe": False,
                        "ranking_pr_auc": 0.41,
                        "ranking_pr_auc_ci_low": 0.32,
                        "top20_hit_rate": 0.1,
                        "decoys_above_positive_count": 2,
                        "positive_target_rank": 3,
                        "anchor_margin_a": -0.5,
                        "positive_anchor_distance_a": 5.1,
                        "top_decoy_anchor_distance_a": 4.6,
                        "decoy_class_counts": {"over_anchored": 1, "same_signature": 1},
                        "root_cause_tags": "over_anchored;same_signature",
                        "blockers": ["ranking_pr_auc_ci_low_below_min"],
                        "execution_enabled": True,
                        "external_state_mutated": True,
                        "claim_promotion_allowed": True,
                    },
                    {
                        "target_id": "HTR2A",
                        "gate_status": "green",
                        "claim_safe": True,
                        "ranking_pr_auc": 0.71,
                        "ranking_pr_auc_ci_low": 0.56,
                        "top20_hit_rate": 1.0,
                        "decoys_above_positive_count": 0,
                        "positive_target_rank": 1,
                        "anchor_margin_a": 0.25,
                        "positive_anchor_distance_a": 4.2,
                        "top_decoy_anchor_distance_a": 4.45,
                    },
                    {"target_id": "OPRM1", "gate_status": "blocked", "claim_safe": False},
                ],
                "claim_boundary": "GPCR hard-decoy suite contract ...",
            }
        ),
        encoding="utf-8",
    )


def _write_claim_unlock_audit(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "gpcr_hard_decoy_claim_unlock_metric_evidence_ready_promotion_locked",
                    "hard_decoy_metric_claim_unlock_ready": True,
                    "phase3_exit_metric_conditions_ready": True,
                    "operator_claim_review_ready": True,
                    "broad_promotion_remains_locked": True,
                    "router_claim_allowed": True,
                    "platform_claim_allowed": True,
                    "claim_promotion_allowed": True,
                    "effective_phase3_metrics": {
                        "ranking_pr_auc_ci_low": 0.5597832604695224,
                        "top20_hit_rate": 1.0,
                        "decoys_above_positive_count": 0,
                        "anchor_margin_nonnegative": True,
                        "source": (
                            "claim_locked_official_suite_plus_preregistered_replay_plus_"
                            "independent_repeat"
                        ),
                    },
                    "promotion_blocker_count": 2,
                    "promotion_blockers": [
                        "broad_scope:formal_broad_claim_review_not_approved",
                        "scorer_router_promotion_gate_not_ready",
                    ],
                    "promotion_work_order_ready": False,
                    "promotion_work_order_row_count": 2,
                    "promotion_work_order_lane_count": 2,
                    "promotion_work_order_primary_lane_id": "broad_scope_review",
                    "promotion_work_order_primary_blocker": (
                        "broad_scope:formal_broad_claim_review_not_approved"
                    ),
                    "next_required_step": (
                        "Phase 3 hard-decoy metric evidence is ready, but broad promotion remains locked."
                    ),
                },
                "promotion_work_order_rows": [
                    {
                        "lane_id": "broad_scope_review",
                        "blocker": "broad_scope:formal_broad_claim_review_not_approved",
                        "required_action": "Complete and approve the GPCR broad-claim review receipt.",
                        "source_artifact": "runs/gpcr_broad_claim_scope_readiness_current.json",
                        "execution_enabled": True,
                        "external_state_mutated": True,
                        "claim_promotion_allowed": True,
                    },
                    {
                        "lane_id": "scorer_router_promotion",
                        "blocker": "scorer_router_promotion_gate_not_ready",
                        "required_action": "Refresh scorer/router promotion readiness until the gate is ready.",
                        "source_artifact": "runs/gpcr_broad_claim_scope_readiness_current.json",
                        "execution_enabled": True,
                        "external_state_mutated": True,
                        "claim_promotion_allowed": True,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def test_gpcr_hard_decoy_route_missing_artifact_fail_closed(tmp_path, monkeypatch) -> None:
    mod = _load_module(monkeypatch, tmp_path / "nope.json")
    payload = asyncio.run(mod.get_product_gpcr_hard_decoy_suite_report())

    assert payload["status"] == "missing_gpcr_hard_decoy_suite_report"
    assert payload["family_claim_safe"] is False
    assert payload["required_target_ids"] == ["DRD2", "HTR2A", "OPRM1"]
    assert payload["missing_required_target_ids"] == ["DRD2", "HTR2A", "OPRM1"]
    assert payload["first_blocked_required_target"] == "DRD2"
    assert payload["target_count"] == 0
    assert payload["targets"] == []
    assert payload["blocker_panel_ready"] is False
    assert payload["target_rows"] == []
    assert payload["blocker_row_count"] == 1
    assert payload["blocker_rows"][0]["blocker_id"] == "gpcr_hard_decoy_suite_report_missing"
    assert payload["blocker_rows"][0]["claim_promotion_allowed"] is False
    assert payload["claim_promotion_allowed"] is False
    assert payload["execution_enabled"] is False
    assert payload["docking_results_emitted"] is False
    assert payload["external_state_mutated"] is False


def test_gpcr_hard_decoy_route_present_artifact_response(tmp_path, monkeypatch) -> None:
    artifact = tmp_path / "gpcr_hard_decoy_suite_current.json"
    _write_artifact(artifact)
    mod = _load_module(monkeypatch, artifact)
    payload = asyncio.run(mod.get_product_gpcr_hard_decoy_suite_report())

    assert payload["status"] == "broad_family_locked"
    assert payload["schema_version"] == "gpcr_hard_decoy_suite_v1"
    assert payload["family_claim_safe"] is False
    assert payload["green_target_ids"] == ["HTR2A"]
    assert payload["blocked_target_ids"] == ["DRD2", "OPRM1"]
    assert payload["first_blocked_required_target"] == "DRD2"
    assert payload["gate"] == {"ci_low_min": 0.45, "top20_min": 0.2}
    assert len(payload["targets"]) == 3
    assert payload["blocker_panel_ready"] is True
    assert payload["target_metric_row_count"] == 3
    assert payload["target_metric_green_row_count"] == 1
    assert payload["blocker_row_count"] == 3
    assert payload["blocker_rows"][0]["blocker_id"] == "broad_gpcr_claim_locked"
    assert payload["blocker_rows"][0]["blocker_type"] == "family_claim_lock"
    assert payload["blocker_rows"][0]["claim_promotion_allowed"] is False
    assert payload["target_rows"][0] == {
        "target_id": "DRD2",
        "gate_status": "blocked",
        "claim_safe": False,
        "metric_gate_pass": False,
        "ranking_pr_auc": 0.41,
        "ranking_pr_auc_ci_low": 0.32,
        "top20_hit_rate": 0.1,
        "decoys_above_positive_count": 2,
        "positive_target_rank": 3,
        "positive_count": 0,
        "retained_positive_count": 0,
        "retained_target_row_count": 0,
        "anchor_margin_a": -0.5,
        "positive_not_out_anchored": False,
        "positive_anchor_distance_a": 5.1,
        "top_decoy_anchor_distance_a": 4.6,
        "top_decoy_retained_count": 0,
        "decoy_class_counts": {"over_anchored": 1, "same_signature": 1},
        "root_cause_tags": ["over_anchored", "same_signature"],
        "blockers": ["ranking_pr_auc_ci_low_below_min"],
        "operator_action_required": True,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_promotion_allowed": False,
    }
    assert payload["target_rows"][1]["metric_gate_pass"] is True
    assert payload["target_rows"][1]["operator_action_required"] is False
    assert payload["target_rows"][1]["claim_promotion_allowed"] is False
    assert payload["claim_promotion_allowed"] is False
    assert payload["claim_unlock_audit_present"] is False
    assert payload["hard_decoy_metric_claim_unlock_ready"] is False
    assert payload["broad_promotion_remains_locked"] is True
    assert payload["execution_enabled"] is False
    assert payload["docking_results_emitted"] is False
    assert payload["external_state_mutated"] is False


def test_gpcr_hard_decoy_route_surfaces_claim_unlock_promotion_work_order(
    tmp_path,
    monkeypatch,
) -> None:
    artifact = tmp_path / "gpcr_hard_decoy_suite_current.json"
    claim_unlock = tmp_path / "gpcr_hard_decoy_claim_unlock_audit_current.json"
    _write_artifact(artifact)
    _write_claim_unlock_audit(claim_unlock)
    mod = _load_module(monkeypatch, artifact, claim_unlock)

    payload = asyncio.run(mod.get_product_gpcr_hard_decoy_suite_report())

    assert payload["claim_unlock_audit_present"] is True
    assert payload["claim_unlock_audit_status"] == (
        "gpcr_hard_decoy_claim_unlock_metric_evidence_ready_promotion_locked"
    )
    assert payload["hard_decoy_metric_claim_unlock_ready"] is True
    assert payload["phase3_exit_metric_conditions_ready"] is True
    assert payload["operator_claim_review_ready"] is True
    assert payload["broad_promotion_remains_locked"] is True
    assert payload["router_claim_allowed"] is False
    assert payload["platform_claim_allowed"] is False
    assert payload["claim_unlock_claim_promotion_allowed"] is False
    assert payload["effective_phase3_metric_source"] == (
        "claim_locked_official_suite_plus_preregistered_replay_plus_independent_repeat"
    )
    assert payload["effective_phase3_ranking_pr_auc_ci_low"] == 0.5597832604695224
    assert payload["effective_phase3_top20_hit_rate"] == 1.0
    assert payload["effective_phase3_decoys_above_positive_count"] == 0
    assert payload["effective_phase3_anchor_margin_nonnegative"] is True
    assert payload["promotion_blocker_count"] == 2
    assert payload["promotion_work_order_ready"] is False
    assert payload["promotion_work_order_row_count"] == 2
    assert payload["promotion_work_order_lane_count"] == 2
    assert payload["promotion_work_order_primary_lane_id"] == "broad_scope_review"
    assert payload["promotion_work_order_primary_blocker"] == (
        "broad_scope:formal_broad_claim_review_not_approved"
    )
    assert payload["promotion_work_order_primary_required_action"] == (
        "Complete and approve the GPCR broad-claim review receipt."
    )
    assert payload["promotion_work_order_rows"][0]["execution_enabled"] is False
    assert payload["promotion_work_order_rows"][0]["docking_results_emitted"] is False
    assert payload["promotion_work_order_rows"][0]["external_state_mutated"] is False
    assert payload["promotion_work_order_rows"][0]["claim_promotion_allowed"] is False
    assert payload["claim_promotion_allowed"] is False


def test_gpcr_hard_decoy_route_does_not_promote_broad_claim(tmp_path, monkeypatch) -> None:
    artifact = tmp_path / "gpcr_hard_decoy_suite_current.json"
    _write_artifact(artifact)
    mod = _load_module(monkeypatch, artifact)
    payload = asyncio.run(mod.get_product_gpcr_hard_decoy_suite_report())

    # Locked family must stay non-claimable.
    assert payload["family_claim_safe"] is False
    assert payload["status"] == "broad_family_locked"

    # Missing-artifact claim boundary explicitly disclaims promotion.
    missing_mod = _load_module(monkeypatch, tmp_path / "gone.json")
    missing_payload = asyncio.run(missing_mod.get_product_gpcr_hard_decoy_suite_report())
    boundary = missing_payload["claim_boundary"]
    assert "does not run scoring" in boundary
    assert "generate decoys" in boundary
    assert "relax thresholds" in boundary
    assert "promote broad-GPCR claims" in boundary


def test_gpcr_hard_decoy_route_invalid_json_fail_closed(tmp_path, monkeypatch) -> None:
    artifact = tmp_path / "gpcr_hard_decoy_suite_current.json"
    artifact.write_text("{ not valid json", encoding="utf-8")
    mod = _load_module(monkeypatch, artifact)
    payload = asyncio.run(mod.get_product_gpcr_hard_decoy_suite_report())

    assert payload["status"] == "missing_gpcr_hard_decoy_suite_report"
    assert payload["family_claim_safe"] is False
