from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _run_script(path: str) -> dict:
    proc = subprocess.run(
        [sys.executable, path],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(proc.stdout)


def test_check_independent_product_readiness_script_reports_restricted_ready_with_claim_boundary() -> None:
    payload = _run_script("scripts/check_independent_product_readiness.py")
    summary = payload["summary"]

    assert summary["status"] == "independent_product_readiness_verified"
    assert summary["independent_restricted_product_ready"] is True
    assert summary["full_commercial_claim_promotion_ready"] is False
    assert summary["full_commercial_science_claim_blocked"] is True
    assert summary["full_commercial_claim_boundaries_explicit"] is True
    assert summary["accuracy_parity_ligand_ranking_metric_thresholds_pass"] is True
    assert summary["accuracy_parity_ligand_ranking_metric_blocker_count"] == 0
    assert summary["accuracy_parity_ligand_ranking_claim_scope_lock_only"] is True
    assert summary["full_commercial_open_gap_ids"] == []
    assert summary["science_accuracy_frontier_public_benchmark_science_ready"] is True
    assert summary["science_accuracy_frontier_public_benchmark_materialized_metric_ready"] is True
    assert summary["science_accuracy_frontier_public_benchmark_materialized_apply_ready"] is True
    assert summary["science_accuracy_frontier_public_benchmark_materialized_row_count"] == 8
    assert summary["science_accuracy_frontier_public_benchmark_materialized_blocked_row_count"] == 0
    assert summary["science_accuracy_frontier_public_benchmark_materialized_metric_evidence_pass_row_count"] == 8
    assert summary["science_accuracy_frontier_public_benchmark_materialized_metric_evidence_blocked_row_count"] == 0
    assert summary["science_accuracy_frontier_public_benchmark_materialized_free_energy_pair_count"] == 8
    assert summary["science_accuracy_frontier_public_benchmark_materialized_free_energy_fit_pair_count"] == 5
    assert summary["science_accuracy_frontier_public_benchmark_materialized_free_energy_holdout_pair_count"] == 3
    assert summary["science_accuracy_frontier_public_benchmark_materialized_free_energy_spearman"] == 0.6190476190476191
    assert summary["science_accuracy_frontier_public_benchmark_materialized_free_energy_spearman_gate_ready"] is True
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_materialized_free_energy_spearman_bootstrap_p05"
        ]
        == -0.14285714285714285
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_materialized_free_energy_spearman_bootstrap_p50"
        ]
        == 0.6428571428571429
    )
    assert summary[
        "science_accuracy_frontier_public_benchmark_materialized_free_energy_spearman_bootstrap_p95"
    ] == 1.0
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_materialized_claim_grade_statistical_support_ready"
        ]
        is False
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_materialized_claim_grade_statistical_support_blocker_count"
        ]
        == 3
    )
    assert summary[
        "science_accuracy_frontier_public_benchmark_materialized_claim_grade_statistical_support_blockers"
    ] == [
        "claim_grade_public_benchmark_pair_count_below_minimum",
        "claim_grade_public_benchmark_holdout_pair_count_below_minimum",
        "claim_grade_public_benchmark_bootstrap_spearman_low_below_minimum",
    ]
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_readiness_present"
        ]
        is True
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_readiness_ready"
        ]
        is True
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_all_candidates_ready"
        ]
        is False
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_row_count"
        ]
        == 17
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_candidate_ready_count"
        ]
        == 0
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_candidate_blocked_count"
        ]
        == 17
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_input_artifact_contract_ready"
        ]
        is False
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_required_input_artifact_count"
        ]
        == 34
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_present_required_input_artifact_count"
        ]
        == 17
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_count"
        ]
        == 17
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_row_count"
        ]
        == 17
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_coordinate_validation_pass_row_count"
        ]
        == 0
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_coordinate_validation_blocked_row_count"
        ]
        == 17
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_existing_metric_source_payload_count"
        ]
        == 0
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_planned_metric_source_payload_count"
        ]
        == 51
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_required_metric_source_payloads"
        ]
        == "dockq;lddt_pli;internal_deltaG"
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_field_count"
        ]
        == 11
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_fields"
        ]
        == (
            "metric_name;target_id;pose_id;value;method;input_artifacts;input_artifact_sha256s;"
            "operator_id;reviewed_at_utc;license_ok;external_engine_calls"
        )
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_present"
        ]
        is True
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready"
        ]
        is True
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_status"
        ]
        == "refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready"
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_r4_row_count"
        ]
        == 17
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_r4_ready_for_review_row_count"
        ]
        == 17
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_r4_blocked_row_count"
        ]
        == 0
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_r4_fetch_required_row_count"
        ]
        == 17
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_r4_metric_materialization_blocked_row_count"
        ]
        == 17
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_r4_planned_metric_source_payload_count"
        ]
        == 51
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_r4_authorized_for_external_download"
        ]
        is False
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_r4_download_executed"
        ]
        is False
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_r4_external_state_mutated"
        ]
        is False
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_r4_approval_token_required"
        ]
        == "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD"
    )
    assert (
        "openmm_schrodinger_public_benchmark_statistical_support_metric_sources_not_materialized"
        in summary["science_accuracy_frontier_blockers"]
    )
    assert (
        "openmm_schrodinger_public_benchmark_statistical_support_coordinate_fetch_r4_approval_required"
        in summary["science_accuracy_frontier_blockers"]
    )
    assert summary["science_accuracy_frontier_public_benchmark_receptor_coordinate_validation_min_protein_like_residues"] == 5
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_receptor_coordinate_intake_suggested_public_url_row_count"
        ]
        == 8
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_receptor_coordinate_intake_suggested_local_path_row_count"
        ]
        == 8
    )
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_receptor_coordinate_intake_operator_review_required_row_count"
        ]
        == 8
    )
    assert summary["science_accuracy_frontier_public_benchmark_metric_evidence_blocked_row_count"] == 8
    assert (
        summary[
            "science_accuracy_frontier_public_benchmark_metric_evidence_missing_required_input_artifact_row_count"
        ]
        == 0
    )
    assert summary["science_accuracy_frontier_public_benchmark_receptor_coordinate_validation_ready_row_count"] == 8
    assert summary["science_accuracy_frontier_public_benchmark_receptor_coordinate_validation_blocked_row_count"] == 0
    assert summary["full_commercial_release_blocker_ids"] == [
        "R8_full_scope_claim_closure",
        "R9_engine_refinement_claim_promotion",
        "ACCURACY:ligand_ranking",
    ]
    assert summary["blocker_count"] == 0
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False
    assert {
        "release_source_of_truth_ready",
        "release_refresh_final_gates_verified",
        "full_commercial_claim_boundaries_explicit",
    }.issubset({row["check"] for row in payload["rows"]})
    boundary = {
        row["check"]: row
        for row in payload["rows"]
    }["full_commercial_claim_boundaries_explicit"]
    assert "ligand_metric_thresholds_pass=True" in boundary["observed"]
    assert "ligand_metric_blocker_count=0" in boundary["observed"]
    assert "ligand_claim_scope_lock_only=True" in boundary["observed"]
    assert "openmm_schrodinger_public_benchmark_science_ready=True" in boundary["observed"]
    assert "public_benchmark_materialized_metric_ready=True" in boundary["observed"]
    assert "public_benchmark_materialized_apply_ready=True" in boundary["observed"]
    assert "public_benchmark_materialized_bootstrap_p05=-0.14285714285714285" in boundary["observed"]
    assert "public_benchmark_materialized_claim_grade_statistical_support_ready=False" in boundary["observed"]
    assert "coordinate_fetch_r4_preflight_ready=True" in boundary["observed"]
    assert "coordinate_fetch_r4_fetch_required=17" in boundary["observed"]
    assert "coordinate_fetch_r4_download_executed=False" in boundary["observed"]


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
