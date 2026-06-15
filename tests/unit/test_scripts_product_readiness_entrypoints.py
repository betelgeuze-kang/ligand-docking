from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _run_script(path: str, *, check: bool = True) -> dict:
    proc = subprocess.run(
        [sys.executable, path],
        cwd=ROOT,
        check=check,
        text=True,
        capture_output=True,
    )
    return json.loads(proc.stdout)


def test_check_independent_product_readiness_script_reports_current_blockers() -> None:
    payload = _run_script("scripts/check_independent_product_readiness.py", check=False)
    summary = payload["summary"]

    assert summary["status"] in {
        "independent_product_readiness_verified",
        "blocked_independent_product_readiness",
    }
    assert summary["independent_restricted_product_ready"] is False
    assert summary["full_commercial_claim_promotion_ready"] is False
    assert summary["full_commercial_science_claim_blocked"] is True
    assert summary["full_commercial_claim_boundaries_explicit"] is True
    assert summary["accuracy_parity_ligand_ranking_metric_thresholds_pass"] is True
    assert summary["accuracy_parity_ligand_ranking_metric_blocker_count"] == 0
    assert summary["accuracy_parity_ligand_ranking_claim_scope_lock_only"] is True
    assert summary["full_commercial_open_gap_ids"] == []
    assert summary["science_accuracy_frontier_blockers"] == [
        "gpcr_broad_claim_review_not_approved",
        "gpcr_scorer_router_promotion_not_approved",
        "openmm_schrodinger_public_benchmark_not_promoted_to_canonical_intake",
        "openmm_schrodinger_public_benchmark_statistical_support_not_claim_grade",
        "openmm_schrodinger_public_benchmark_statistical_support_metric_source_payload_operator_receipt_not_ready",
        "openmm_schrodinger_public_benchmark_bootstrap_driver_operator_chain_not_closed",
        "engine_refinement_claim_evidence_receipt_not_ready",
    ]
    assert summary["science_accuracy_frontier_public_benchmark_bootstrap_driver_operator_chain_rollup_present"] is True
    assert summary["science_accuracy_frontier_public_benchmark_bootstrap_driver_operator_chain_status"] == (
        "blocked_refine_tier_public_benchmark_bootstrap_driver_operator_chain_rollup"
    )
    assert summary["science_accuracy_frontier_public_benchmark_bootstrap_driver_operator_chain_surface_ready"] is True
    assert summary["science_accuracy_frontier_public_benchmark_bootstrap_driver_operator_chain_closure_ready"] is False
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_bootstrap_driver_operator_chain_operator_only_pending_field_count"
        ]
        == 30
    )
    assert summary[
        "science_accuracy_frontier_public_benchmark_bootstrap_driver_operator_chain_final_blocker"
    ] == "operator_only_placeholders_unfilled"
    assert summary["science_accuracy_frontier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready"] is False
    assert summary["science_accuracy_frontier_public_benchmark_materialized_metric_ready"] is True
    assert summary["science_accuracy_frontier_public_benchmark_materialized_apply_ready"] is True
    assert summary["full_commercial_release_blocker_ids"] == [
        "R8_full_scope_claim_closure",
        "R9_engine_refinement_claim_promotion",
        "ACCURACY:ligand_ranking",
    ]
    assert summary["blocker_count"] == 1
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False
    rows = {row["check"]: row for row in payload["rows"]}
    assert rows["release_source_of_truth_ready"]["status"] == "pass"
    assert rows["release_refresh_final_gates_verified"]["status"] == "fail"
    assert rows["full_commercial_claim_boundaries_explicit"]["status"] == "pass"
    boundary = rows["full_commercial_claim_boundaries_explicit"]
    assert "ligand_metric_thresholds_pass=True" in boundary["observed"]
    assert "ligand_metric_blocker_count=0" in boundary["observed"]
    assert "ligand_claim_scope_lock_only=True" in boundary["observed"]
    assert "gpcr_broad_claim_review_receipt_ready=False" in boundary["observed"]
    assert "gpcr_broad_claim_review_receipt_blocked=2" in boundary["observed"]
    assert "gpcr_broad_claim_review_receipt_review_surface_ready=2" in boundary["observed"]
    assert "gpcr_broad_claim_review_receipt_manual_field_pending=16" in boundary["observed"]
    assert "gpcr_broad_claim_review_receipt_evidence_artifact_present=0" in boundary["observed"]
    assert "openmm_schrodinger_public_benchmark_science_ready=True" in boundary["observed"]
    assert "public_benchmark_materialized_metric_ready=True" in boundary["observed"]
    assert "public_benchmark_materialized_apply_ready=True" in boundary["observed"]
    assert "public_benchmark_materialized_bootstrap_p05=-0.14285714285714285" in boundary["observed"]
    assert "public_benchmark_materialized_claim_grade_statistical_support_ready=False" in boundary["observed"]
    assert "coordinate_fetch_r4_preflight_ready=True" in boundary["observed"]
    assert "coordinate_fetch_r4_download_executed=False" in boundary["observed"]
    assert "coordinate_fetch_operator_receipt_ready=False" in boundary["observed"]
    assert "metric_source_payload_receipt_ready=False" in boundary["observed"]
    assert "coordinate_intake_ready=True" in boundary["observed"]
    assert "coordinate_intake_missing=0" in boundary["observed"]


def test_verify_quality_gate_script_rebuilds_operational_quality_fail_closed() -> None:
    payload = _run_script("scripts/verify_quality_gate.py")
    summary = payload["summary"]

    assert summary["status"] == "product_quality_gate_verified"
    assert summary["quality_gate_ready"] is True
    assert summary["blocker_count"] == 0
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False
    rows = {row["check"]: row for row in payload["rows"]}
    assert rows["fail_closed_execution_posture"]["status"] == "pass"
    assert rows["production_ai_correction_guarded"]["status"] == "pass"
