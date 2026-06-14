from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.gpcr_replay import build_gpcr_broad_claim_scope_readiness as mod

ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _accuracy_packet() -> dict:
    return {
        "summary": {
            "status": "blocked_accuracy_parity",
            "row_count": 5,
            "pass_row_count": 4,
            "restricted_pass_row_count": 1,
            "blocked_row_count": 0,
            "missing_row_count": 0,
            "top_blockers": ["ligand_ranking:broad_gpcr_claim_not_allowed"],
        },
        "rows": [
            {
                "axis": "ligand_ranking",
                "metric_id": "ligand_ranking",
                "status": "restricted_pass",
                "blockers": ["broad_gpcr_claim_not_allowed"],
                "claim_promotion_allowed": False,
                "commercial_parity_claim_allowed": False,
                "metrics": {
                    "ranking_pr_auc": 0.87,
                    "ranking_pr_auc_ci_low": 0.76,
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


def _heldout_guardrail(status: str = "green") -> dict:
    blockers = [] if status == "green" else ["family_heldout_not_green"]
    return {
        "summary": {
            "status": status,
            "blocker_count": len(blockers),
            "blockers": blockers,
            "claim_promotion_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
        }
    }


def _guarded_readiness() -> dict:
    return {
        "summary": {
            "status": "eligible",
            "claim_review_eligible": True,
            "blocker_count": 0,
            "blockers": [],
            "claim_promotion_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
        }
    }


def _active_scorer(*, ready: bool = False) -> dict:
    return {
        "summary": {
            "status": (
                "gpcr_active_scorer_promotion_decision_ready_claim_locked"
                if ready
                else "blocked_gpcr_active_scorer_promotion_decision"
            ),
            "active_scorer_apply_allowed": ready,
            "scorer_apply_allowed": ready,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
            "promotion_scope": "guarded_operational_gpcr_ranking_only",
            "accuracy_parity_metric_ready": True,
            "accuracy_parity_claim_scope_lock_only": True,
            "accuracy_parity_ligand_ranking_status": "restricted_pass",
            "blockers": [] if ready else ["residual_registry_production_promotion_not_allowed"],
        }
    }


def _broad_review_receipt(*, ready: bool = False) -> dict:
    return {
        "summary": {
            "status": (
                "gpcr_broad_claim_review_receipt_ready"
                if ready
                else "blocked_gpcr_broad_claim_review_receipt"
            ),
            "broad_claim_review_receipt_ready": ready,
            "target_heldout_broad_scope_review_approved": ready,
            "scorer_router_promotion_gate_approved": ready,
            "receipt_row_count": 2,
            "pass_row_count": 2 if ready else 0,
            "blocked_row_count": 0 if ready else 2,
            "operator_review_surface_ready_count": 2,
            "operator_review_surface_blocked_count": 0,
            "evidence_artifact_present_count": 2 if ready else 0,
            "evidence_status_contract_present_count": 2,
            "expected_true_fields_present_count": 2,
            "external_engine_calls_zero_count": 2,
            "receipt_manual_field_pending_count": 0 if ready else 16,
            "first_blocked_review_id": "" if ready else "target_heldout_broad_scope_review_not_approved",
            "approval_token_required": "APPROVE_GPCR_BROAD_CLAIM_REVIEW",
        }
    }


def test_broad_claim_scope_splits_ready_inputs_from_missing_approval(tmp_path: Path) -> None:
    accuracy = tmp_path / "accuracy.json"
    heldout = tmp_path / "heldout.json"
    guarded = tmp_path / "guarded.json"
    active = tmp_path / "active.json"
    receipt = tmp_path / "receipt.json"
    _write_json(accuracy, _accuracy_packet())
    _write_json(heldout, _heldout_guardrail())
    _write_json(guarded, _guarded_readiness())
    _write_json(active, _active_scorer())
    _write_json(receipt, _broad_review_receipt())

    payload = mod.build_packet(
        accuracy_scorecard_json=accuracy,
        family_heldout_guardrail_json=heldout,
        guarded_100k_readiness_json=guarded,
        active_scorer_decision_json=active,
        broad_claim_review_receipt_json=receipt,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_gpcr_broad_claim_scope_readiness"
    assert summary["target_heldout_broad_scope_review_input_ready"] is True
    assert summary["accuracy_parity_metric_ready"] is True
    assert summary["accuracy_parity_claim_scope_lock_only"] is True
    assert summary["broad_claim_review_receipt_status"] == "blocked_gpcr_broad_claim_review_receipt"
    assert summary["broad_claim_review_receipt_ready"] is False
    assert summary["broad_claim_review_receipt_blocked_row_count"] == 2
    assert summary["broad_claim_review_receipt_operator_review_surface_ready_count"] == 2
    assert summary["broad_claim_review_receipt_operator_review_surface_blocked_count"] == 0
    assert summary["broad_claim_review_receipt_evidence_artifact_present_count"] == 0
    assert summary["broad_claim_review_receipt_expected_true_fields_present_count"] == 2
    assert summary["broad_claim_review_receipt_external_engine_calls_zero_count"] == 2
    assert summary["broad_claim_review_receipt_manual_field_pending_count"] == 16
    assert summary["broad_claim_review_receipt_first_blocked_review_id"] == (
        "target_heldout_broad_scope_review_not_approved"
    )
    assert summary["claim_promotion_allowed"] is False
    assert summary["router_claim_allowed"] is False
    assert summary["platform_claim_allowed"] is False
    assert summary["blockers"] == [
        "formal_broad_claim_review_not_approved",
        "scorer_router_promotion_gate_not_approved",
    ]


def test_blocked_heldout_guardrail_keeps_target_input_not_ready(tmp_path: Path) -> None:
    accuracy = tmp_path / "accuracy.json"
    heldout = tmp_path / "heldout.json"
    guarded = tmp_path / "guarded.json"
    active = tmp_path / "active.json"
    receipt = tmp_path / "receipt.json"
    _write_json(accuracy, _accuracy_packet())
    _write_json(heldout, _heldout_guardrail("blocked"))
    _write_json(guarded, _guarded_readiness())
    _write_json(active, _active_scorer())
    _write_json(receipt, _broad_review_receipt())

    payload = mod.build_packet(
        accuracy_scorecard_json=accuracy,
        family_heldout_guardrail_json=heldout,
        guarded_100k_readiness_json=guarded,
        active_scorer_decision_json=active,
        broad_claim_review_receipt_json=receipt,
    )

    assert payload["summary"]["target_heldout_broad_scope_review_input_ready"] is False
    assert "target_heldout_family_guardrail_not_green" in payload["summary"]["blockers"]


def test_cli_writes_broad_claim_scope_readiness_outputs(tmp_path: Path) -> None:
    accuracy = tmp_path / "accuracy.json"
    heldout = tmp_path / "heldout.json"
    guarded = tmp_path / "guarded.json"
    active = tmp_path / "active.json"
    receipt = tmp_path / "receipt.json"
    out_json = tmp_path / "packet.json"
    out_md = tmp_path / "packet.md"
    _write_json(accuracy, _accuracy_packet())
    _write_json(heldout, _heldout_guardrail())
    _write_json(guarded, _guarded_readiness())
    _write_json(active, _active_scorer())
    _write_json(receipt, _broad_review_receipt())

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/gpcr_replay/build_gpcr_broad_claim_scope_readiness.py"),
            "--accuracy-scorecard-json",
            str(accuracy),
            "--family-heldout-guardrail-json",
            str(heldout),
            "--guarded-100k-readiness-json",
            str(guarded),
            "--active-scorer-decision-json",
            str(active),
            "--broad-claim-review-receipt-json",
            str(receipt),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    markdown = out_md.read_text(encoding="utf-8")
    assert payload["summary"]["status"] == "blocked_gpcr_broad_claim_scope_readiness"
    assert "GPCR Broad Claim-Scope Readiness" in markdown


def test_broad_claim_scope_can_turn_ready_when_receipt_and_scorer_gate_clear(tmp_path: Path) -> None:
    accuracy = tmp_path / "accuracy.json"
    heldout = tmp_path / "heldout.json"
    guarded = tmp_path / "guarded.json"
    active = tmp_path / "active.json"
    receipt = tmp_path / "receipt.json"
    _write_json(accuracy, _accuracy_packet())
    _write_json(heldout, _heldout_guardrail())
    _write_json(guarded, _guarded_readiness())
    _write_json(active, _active_scorer(ready=True))
    _write_json(receipt, _broad_review_receipt(ready=True))

    payload = mod.build_packet(
        accuracy_scorecard_json=accuracy,
        family_heldout_guardrail_json=heldout,
        guarded_100k_readiness_json=guarded,
        active_scorer_decision_json=active,
        broad_claim_review_receipt_json=receipt,
    )
    summary = payload["summary"]

    assert summary["status"] == "gpcr_broad_claim_scope_ready"
    assert summary["target_heldout_broad_scope_review_approved"] is True
    assert summary["active_scorer_gate_ready"] is True
    assert summary["scorer_router_promotion_gate_receipt_approved"] is True
    assert summary["scorer_router_promotion_gate_ready"] is True
    assert summary["claim_promotion_allowed"] is True
    assert summary["router_claim_allowed"] is True
    assert summary["platform_claim_allowed"] is True
