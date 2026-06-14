#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_ARTIFACTS = {
    "product_readiness": "runs/product_readiness_gate_current.json",
    "operational_quality": "runs/product_operational_quality_contract_current.json",
    "commercial_independence": "runs/product_commercial_independence_gate_current.json",
    "capability_surface": "runs/product_capability_surface_contract_current.json",
    "release_bundle": "runs/product_release_bundle_current.json",
    "source_of_truth": "runs/product_release_source_of_truth_gate_current.json",
    "release_refresh": "runs/product_release_current_refresh_plan_current.json",
    "goal_release": "runs/goal_release_decision_gate_current.json",
    "accuracy": "runs/accuracy_parity_scorecard_current.json",
    "master_gap": "runs/master_gap_closure_rollup_current.json",
    "science_claim": "runs/science_claim_promotion_gap_closure_current.json",
    "science_frontier": "runs/science_accuracy_frontier_current.json",
}

CLAIM_BOUNDARY = (
    "Independent product readiness check only; it reads local current artifacts and verifies the restricted "
    "self-hosted product surface, fail-closed execution posture, release source-of-truth freshness, and explicit "
    "full-commercial R8/R9/ACCURACY claim blockers. It does not run docking, enable execution, promote claims, "
    "deploy, upload, email, delete, commit, push, or mutate external state."
)


def _resolve(path_like: str | Path, *, root: Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _read_json(path_like: str | Path, *, root: Path) -> dict[str, Any]:
    path = _resolve(path_like, root=root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _csv(items: Any) -> str:
    if isinstance(items, list):
        return ",".join(str(item) for item in items)
    return str(items or "")


def _list(items: Any) -> list[str]:
    if isinstance(items, list):
        return [str(item) for item in items if str(item)]
    if isinstance(items, tuple):
        return [str(item) for item in items if str(item)]
    return [str(items)] if str(items or "") else []


def _row(check: str, passed: bool, observed: str, required: str, *, release_blocker: bool = True) -> dict[str, Any]:
    return {
        "check": check,
        "status": "pass" if passed else "fail",
        "observed": observed,
        "required": required,
        "release_blocker": bool(release_blocker and not passed),
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def build_independent_product_readiness(*, root: Path = ROOT) -> dict[str, Any]:
    packets = {name: _read_json(path, root=root) for name, path in DEFAULT_ARTIFACTS.items()}
    summaries = {name: _summary(packet) for name, packet in packets.items()}

    product = summaries["product_readiness"]
    quality = summaries["operational_quality"]
    commercial = summaries["commercial_independence"]
    surface = summaries["capability_surface"]
    bundle = summaries["release_bundle"]
    source = summaries["source_of_truth"]
    refresh = summaries["release_refresh"]
    goal_release = summaries["goal_release"]
    accuracy = summaries["accuracy"]
    master = summaries["master_gap"]
    science = summaries["science_claim"]
    science_frontier = summaries["science_frontier"]
    full_commercial_blocker_ids = _list(goal_release.get("full_commercial_release_blocker_ids"))
    expected_full_commercial_blocker_ids = [
        "R8_full_scope_claim_closure",
        "R9_engine_refinement_claim_promotion",
        "ACCURACY:ligand_ranking",
    ]
    expected_science_frontier_blockers = [
        "gpcr_broad_claim_review_not_approved",
        "gpcr_scorer_router_promotion_not_approved",
        "openmm_schrodinger_public_benchmark_not_promoted_to_canonical_intake",
        "openmm_schrodinger_public_benchmark_statistical_support_not_claim_grade",
        "openmm_schrodinger_public_benchmark_statistical_support_metric_sources_not_materialized",
        "engine_refinement_claim_evidence_receipt_not_ready",
    ]
    accuracy_top_blockers = _list(accuracy.get("top_blockers"))

    rows = [
        _row(
            "product_handoff_ready_fail_closed",
            product.get("status") == "product_handoff_ready"
            and product.get("request_contract_status") == "pass"
            and product.get("execution_enabled") is False
            and product.get("docking_results_emitted") is False
            and product.get("external_state_mutated") is False,
            (
                f"status={product.get('status')};request_contract={product.get('request_contract_status')};"
                f"execution_enabled={product.get('execution_enabled')};"
                f"docking_results_emitted={product.get('docking_results_emitted')};"
                f"external_state_mutated={product.get('external_state_mutated')}"
            ),
            "product_handoff_ready, request_contract_status=pass, execution/results/external mutation disabled",
        ),
        _row(
            "operational_quality_ready",
            quality.get("status") == "product_operational_quality_contract_ready"
            and quality.get("operational_quality_ready") is True
            and _int(quality.get("blocker_count")) == 0
            and quality.get("execution_enabled") is False
            and quality.get("external_state_mutated") is False,
            (
                f"status={quality.get('status')};ready={quality.get('operational_quality_ready')};"
                f"blocker_count={quality.get('blocker_count')};"
                f"execution_enabled={quality.get('execution_enabled')};"
                f"external_state_mutated={quality.get('external_state_mutated')}"
            ),
            "operational quality ready with zero blockers and no execution/external mutation",
        ),
        _row(
            "commercial_independence_restricted_self_hosted",
            commercial.get("status") == "product_commercial_independence_gate_ready"
            and commercial.get("commercial_independent_product_claim_allowed") is True
            and commercial.get("local_self_hosted_operation_ready") is True
            and commercial.get("general_platform_claim_allowed") is False
            and _int(commercial.get("blocker_count")) == 0,
            (
                f"status={commercial.get('status')};"
                f"commercial_independent_product_claim_allowed={commercial.get('commercial_independent_product_claim_allowed')};"
                f"local_self_hosted_operation_ready={commercial.get('local_self_hosted_operation_ready')};"
                f"general_platform_claim_allowed={commercial.get('general_platform_claim_allowed')};"
                f"blocker_count={commercial.get('blocker_count')}"
            ),
            "restricted self-hosted commercial independence ready; general platform claim remains false",
        ),
        _row(
            "capability_surface_restricted_scope_ready",
            surface.get("status") == "product_capability_surface_contract_ready"
            and surface.get("structure_analysis_capability_ready") is True
            and surface.get("ligand_docking_capability_ready") is True
            and surface.get("restricted_scope_claim_guard_ready") is True
            and surface.get("general_platform_claim_allowed") is False,
            (
                f"status={surface.get('status')};structure={surface.get('structure_analysis_capability_ready')};"
                f"ligand={surface.get('ligand_docking_capability_ready')};"
                f"restricted_scope_guard={surface.get('restricted_scope_claim_guard_ready')};"
                f"general_platform_claim_allowed={surface.get('general_platform_claim_allowed')}"
            ),
            "structure and ligand-docking capability ready under restricted scope with broad platform claim false",
        ),
        _row(
            "release_bundle_operator_review_ready",
            bundle.get("status") == "release_bundle_ready_for_operator_review"
            and bundle.get("release_bundle_ready") is True
            and _int(bundle.get("blocker_count")) == 0,
            (
                f"status={bundle.get('status')};release_bundle_ready={bundle.get('release_bundle_ready')};"
                f"artifact_count={bundle.get('artifact_count')};check_count={bundle.get('check_count')};"
                f"pass_count={bundle.get('pass_count')};blocker_count={bundle.get('blocker_count')}"
            ),
            "release bundle ready for operator review with zero bundle blockers",
        ),
        _row(
            "release_source_of_truth_ready",
            source.get("status") == "product_release_source_of_truth_gate_ready"
            and source.get("release_source_of_truth_ready") is True
            and _int(source.get("blocker_count")) == 0
            and _int(source.get("stale_artifact_count")) == 0
            and _int(source.get("readme_drift_count")) == 0,
            (
                f"status={source.get('status')};ready={source.get('release_source_of_truth_ready')};"
                f"pass_count={source.get('pass_count')};blocker_count={source.get('blocker_count')};"
                f"stale_artifact_count={source.get('stale_artifact_count')};"
                f"readme_drift_count={source.get('readme_drift_count')}"
            ),
            "source-of-truth ready with zero blockers, stale artifacts, and README drift",
        ),
        _row(
            "release_refresh_final_gates_verified",
            refresh.get("status") == "product_release_current_refresh_verified"
            and refresh.get("final_gate_verification_ready") is True
            and _int(refresh.get("final_gate_blocker_count")) == 0,
            (
                f"status={refresh.get('status')};command_count={refresh.get('command_count')};"
                f"final_gate_count={refresh.get('final_gate_count')};"
                f"final_gate_verification_ready={refresh.get('final_gate_verification_ready')};"
                f"final_gate_blocker_count={refresh.get('final_gate_blocker_count')}"
            ),
            "release refresh verified with final gate blocker count 0",
        ),
        _row(
            "full_commercial_claim_boundaries_explicit",
            (
                (
                    goal_release.get("status") == "blocked_goal_release_decision"
                    and goal_release.get("release_allowed") is False
                )
                or (
                    goal_release.get("status") == "goal_release_ready"
                    and goal_release.get("release_allowed") is True
                    and goal_release.get("restricted_release_allowed") is True
                )
            )
            and goal_release.get("full_commercial_release_allowed") is False
            and full_commercial_blocker_ids == expected_full_commercial_blocker_ids
            and goal_release.get("accuracy_parity_ligand_ranking_status") == "restricted_pass"
            and goal_release.get("accuracy_parity_ligand_ranking_blockers") == ["broad_gpcr_claim_not_allowed"]
            and goal_release.get("accuracy_parity_ligand_ranking_metric_thresholds_pass") is True
            and _int(goal_release.get("accuracy_parity_ligand_ranking_metric_blocker_count")) == 0
            and goal_release.get("accuracy_parity_ligand_ranking_claim_scope_lock_only") is True
            and goal_release.get("accuracy_parity_ligand_ranking_claim_promotion_allowed") is False
            and goal_release.get("accuracy_parity_ligand_ranking_commercial_parity_claim_allowed") is False
            and accuracy.get("status") == "blocked_accuracy_parity"
            and accuracy_top_blockers == ["ligand_ranking:broad_gpcr_claim_not_allowed"]
            and master.get("status") == "master_gap_closure_rollup_complete"
            and master.get("claim_promotion_allowed") is False
            and not _list(master.get("open_gap_ids"))
            and science.get("status") == "science_claim_promotion_gap_closure_complete"
            and science.get("claim_promotion_allowed") is False
            and not _list(science.get("open_gap_ids"))
            and science_frontier.get("status") == "blocked_science_accuracy_frontier"
            and science_frontier.get("restricted_science_accuracy_ready") is True
            and science_frontier.get("broad_commercial_accuracy_claim_ready") is False
            and science_frontier.get("openmm_schrodinger_public_benchmark_ready") is False
            and science_frontier.get("engine_refinement_claim_evidence_receipt_ready") is False
            and science_frontier.get("gpcr_broad_claim_ready") is False
            and science_frontier.get("gpcr_scorer_router_ready") is False
            and _list(science_frontier.get("blockers")) == expected_science_frontier_blockers
            and _int(science_frontier.get("blocker_count")) == len(expected_science_frontier_blockers),
            (
                f"goal_release_status={goal_release.get('status')};"
                f"release_allowed={goal_release.get('release_allowed')};"
                f"full_commercial_release_allowed={goal_release.get('full_commercial_release_allowed')};"
                f"full_commercial_blockers={_csv(full_commercial_blocker_ids)};"
                f"ligand_status={goal_release.get('accuracy_parity_ligand_ranking_status')};"
                f"ligand_blockers={_csv(goal_release.get('accuracy_parity_ligand_ranking_blockers'))};"
                f"ligand_metric_thresholds_pass="
                f"{goal_release.get('accuracy_parity_ligand_ranking_metric_thresholds_pass')};"
                f"ligand_metric_blocker_count="
                f"{goal_release.get('accuracy_parity_ligand_ranking_metric_blocker_count')};"
                f"ligand_claim_scope_lock_only="
                f"{goal_release.get('accuracy_parity_ligand_ranking_claim_scope_lock_only')};"
                f"ligand_claim_promotion_allowed="
                f"{goal_release.get('accuracy_parity_ligand_ranking_claim_promotion_allowed')};"
                f"ligand_commercial_parity_claim_allowed="
                f"{goal_release.get('accuracy_parity_ligand_ranking_commercial_parity_claim_allowed')};"
                f"master_status={master.get('status')};master_open={_csv(master.get('open_gap_ids'))};"
                f"claim_promotion_allowed={master.get('claim_promotion_allowed')};"
                f"science_status={science.get('status')};science_open={_csv(science.get('open_gap_ids'))};"
                f"science_frontier_status={science_frontier.get('status')};"
                f"restricted_science_accuracy_ready={science_frontier.get('restricted_science_accuracy_ready')};"
                f"openmm_schrodinger_public_benchmark_science_ready="
                f"{science_frontier.get('openmm_schrodinger_public_benchmark_science_ready')};"
                f"public_benchmark_materialized_metric_ready="
                f"{science_frontier.get('public_benchmark_materialized_metric_ready')};"
                f"public_benchmark_materialized_apply_ready="
                f"{science_frontier.get('public_benchmark_materialized_apply_ready')};"
                f"public_benchmark_materialized_bootstrap_p05="
                f"{science_frontier.get('public_benchmark_materialized_free_energy_spearman_bootstrap_p05')};"
                f"public_benchmark_materialized_claim_grade_statistical_support_ready="
                f"{science_frontier.get('public_benchmark_materialized_claim_grade_statistical_support_ready')};"
                f"broad_commercial_accuracy_claim_ready={science_frontier.get('broad_commercial_accuracy_claim_ready')};"
                f"science_frontier_blockers={_csv(science_frontier.get('blockers'))}"
            ),
            "full-commercial claim promotion remains explicitly blocked on R8/R9 receipts and ACCURACY broad claim lock",
            release_blocker=False,
        ),
    ]

    required_rows = [row for row in rows if row["check"] != "full_commercial_claim_boundaries_explicit"]
    blocker_rows = [row for row in required_rows if row["status"] != "pass"]
    boundary_row = next(row for row in rows if row["check"] == "full_commercial_claim_boundaries_explicit")
    independent_ready = not blocker_rows and boundary_row["status"] == "pass"

    payload = {
        "summary": {
            "packet_type": "independent_product_readiness_check",
            "status": (
                "independent_product_readiness_verified"
                if independent_ready
                else "blocked_independent_product_readiness"
            ),
            "independent_restricted_product_ready": bool(independent_ready),
            "full_commercial_claim_promotion_ready": False,
            "full_commercial_science_claim_blocked": boundary_row["status"] == "pass",
            "full_commercial_claim_boundaries_explicit": boundary_row["status"] == "pass",
            "accuracy_parity_ligand_ranking_metric_thresholds_pass": bool(
                goal_release.get("accuracy_parity_ligand_ranking_metric_thresholds_pass") is True
            ),
            "accuracy_parity_ligand_ranking_metric_blocker_count": _int(
                goal_release.get("accuracy_parity_ligand_ranking_metric_blocker_count")
            ),
            "accuracy_parity_ligand_ranking_claim_scope_lock_only": bool(
                goal_release.get("accuracy_parity_ligand_ranking_claim_scope_lock_only") is True
            ),
            "full_commercial_open_gap_ids": science.get("open_gap_ids") or [],
            "science_accuracy_frontier_status": science_frontier.get("status", ""),
            "science_accuracy_frontier_restricted_ready": bool(
                science_frontier.get("restricted_science_accuracy_ready") is True
            ),
            "science_accuracy_frontier_broad_commercial_blocked": bool(
                science_frontier.get("broad_commercial_accuracy_claim_ready") is False
                and science_frontier.get("status") == "blocked_science_accuracy_frontier"
            ),
            "science_accuracy_frontier_blockers": science_frontier.get("blockers") or [],
            "science_accuracy_frontier_public_benchmark_science_ready": bool(
                science_frontier.get("openmm_schrodinger_public_benchmark_science_ready") is True
            ),
            "science_accuracy_frontier_public_benchmark_materialized_metric_ready": bool(
                science_frontier.get("public_benchmark_materialized_metric_ready") is True
            ),
            "science_accuracy_frontier_public_benchmark_materialized_apply_ready": bool(
                science_frontier.get("public_benchmark_materialized_apply_ready") is True
            ),
            "science_accuracy_frontier_public_benchmark_materialized_row_count": _int(
                science_frontier.get("public_benchmark_materialized_row_count")
            ),
            "science_accuracy_frontier_public_benchmark_materialized_blocked_row_count": _int(
                science_frontier.get("public_benchmark_materialized_blocked_row_count")
            ),
            "science_accuracy_frontier_public_benchmark_materialized_metric_evidence_pass_row_count": _int(
                science_frontier.get("public_benchmark_materialized_metric_evidence_pass_row_count")
            ),
            "science_accuracy_frontier_public_benchmark_materialized_metric_evidence_blocked_row_count": _int(
                science_frontier.get("public_benchmark_materialized_metric_evidence_blocked_row_count")
            ),
            "science_accuracy_frontier_public_benchmark_materialized_free_energy_pair_count": _int(
                science_frontier.get("public_benchmark_materialized_free_energy_pair_count")
            ),
            "science_accuracy_frontier_public_benchmark_materialized_free_energy_fit_pair_count": _int(
                science_frontier.get("public_benchmark_materialized_free_energy_fit_pair_count")
            ),
            "science_accuracy_frontier_public_benchmark_materialized_free_energy_holdout_pair_count": _int(
                science_frontier.get("public_benchmark_materialized_free_energy_holdout_pair_count")
            ),
            "science_accuracy_frontier_public_benchmark_materialized_free_energy_spearman": _float(
                science_frontier.get("public_benchmark_materialized_free_energy_spearman")
            ),
            "science_accuracy_frontier_public_benchmark_materialized_free_energy_spearman_gate_ready": bool(
                science_frontier.get("public_benchmark_materialized_free_energy_spearman_gate_ready") is True
            ),
            "science_accuracy_frontier_public_benchmark_materialized_free_energy_spearman_bootstrap_p05": _float(
                science_frontier.get("public_benchmark_materialized_free_energy_spearman_bootstrap_p05")
            ),
            "science_accuracy_frontier_public_benchmark_materialized_free_energy_spearman_bootstrap_p50": _float(
                science_frontier.get("public_benchmark_materialized_free_energy_spearman_bootstrap_p50")
            ),
            "science_accuracy_frontier_public_benchmark_materialized_free_energy_spearman_bootstrap_p95": _float(
                science_frontier.get("public_benchmark_materialized_free_energy_spearman_bootstrap_p95")
            ),
            "science_accuracy_frontier_public_benchmark_materialized_claim_grade_statistical_support_ready": bool(
                science_frontier.get("public_benchmark_materialized_claim_grade_statistical_support_ready") is True
            ),
            "science_accuracy_frontier_public_benchmark_materialized_claim_grade_statistical_support_blocker_count": _int(
                science_frontier.get("public_benchmark_materialized_claim_grade_statistical_support_blocker_count")
            ),
            "science_accuracy_frontier_public_benchmark_materialized_claim_grade_statistical_support_blockers": (
                science_frontier.get("public_benchmark_materialized_claim_grade_statistical_support_blockers") or []
            ),
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_readiness_present": bool(
                science_frontier.get(
                    "public_benchmark_statistical_support_metric_materialization_readiness_present"
                )
                is True
            ),
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_readiness_ready": bool(
                science_frontier.get(
                    "public_benchmark_statistical_support_metric_materialization_readiness_ready"
                )
                is True
            ),
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_all_candidates_ready": bool(
                science_frontier.get(
                    "public_benchmark_statistical_support_metric_materialization_all_candidates_ready"
                )
                is True
            ),
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_row_count": _int(
                science_frontier.get("public_benchmark_statistical_support_metric_materialization_row_count")
            ),
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_candidate_ready_count": _int(
                science_frontier.get(
                    "public_benchmark_statistical_support_metric_materialization_candidate_ready_count"
                )
            ),
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_candidate_blocked_count": _int(
                science_frontier.get(
                    "public_benchmark_statistical_support_metric_materialization_candidate_blocked_count"
                )
            ),
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_input_artifact_contract_ready": bool(
                science_frontier.get(
                    "public_benchmark_statistical_support_metric_materialization_input_artifact_contract_ready"
                )
                is True
            ),
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_required_input_artifact_count": _int(
                science_frontier.get(
                    "public_benchmark_statistical_support_metric_materialization_required_input_artifact_count"
                )
            ),
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_present_required_input_artifact_count": _int(
                science_frontier.get(
                    "public_benchmark_statistical_support_metric_materialization_present_required_input_artifact_count"
                )
            ),
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_count": _int(
                science_frontier.get(
                    "public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_count"
                )
            ),
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_row_count": _int(
                science_frontier.get(
                    "public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_row_count"
                )
            ),
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_coordinate_validation_pass_row_count": _int(
                science_frontier.get(
                    "public_benchmark_statistical_support_metric_materialization_coordinate_validation_pass_row_count"
                )
            ),
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_coordinate_validation_blocked_row_count": _int(
                science_frontier.get(
                    "public_benchmark_statistical_support_metric_materialization_coordinate_validation_blocked_row_count"
                )
            ),
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_existing_metric_source_payload_count": _int(
                science_frontier.get(
                    "public_benchmark_statistical_support_metric_materialization_existing_metric_source_payload_count"
                )
            ),
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_planned_metric_source_payload_count": _int(
                science_frontier.get(
                    "public_benchmark_statistical_support_metric_materialization_planned_metric_source_payload_count"
                )
            ),
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_required_metric_source_payloads": str(
                science_frontier.get(
                    "public_benchmark_statistical_support_metric_materialization_required_metric_source_payloads",
                    "",
                )
            ),
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_field_count": _int(
                science_frontier.get(
                    "public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_field_count"
                )
            ),
            "science_accuracy_frontier_public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_fields": str(
                science_frontier.get(
                    "public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_fields",
                    "",
                )
            ),
            "science_accuracy_frontier_public_benchmark_receptor_coordinate_validation_ready_row_count": _int(
                science_frontier.get("public_benchmark_work_order_receptor_coordinate_validation_ready_row_count")
            ),
            "science_accuracy_frontier_public_benchmark_receptor_coordinate_validation_blocked_row_count": _int(
                science_frontier.get("public_benchmark_work_order_receptor_coordinate_validation_blocked_row_count")
            ),
            "science_accuracy_frontier_public_benchmark_receptor_coordinate_intake_suggested_public_url_row_count": _int(
                science_frontier.get(
                    "public_benchmark_work_order_receptor_coordinate_intake_suggested_public_url_row_count"
                )
            ),
            "science_accuracy_frontier_public_benchmark_receptor_coordinate_intake_suggested_local_path_row_count": _int(
                science_frontier.get(
                    "public_benchmark_work_order_receptor_coordinate_intake_suggested_local_path_row_count"
                )
            ),
            "science_accuracy_frontier_public_benchmark_receptor_coordinate_intake_operator_review_required_row_count": _int(
                science_frontier.get(
                    "public_benchmark_work_order_receptor_coordinate_intake_operator_review_required_row_count"
                )
            ),
            "science_accuracy_frontier_public_benchmark_receptor_coordinate_validation_min_atom_records": _int(
                science_frontier.get("public_benchmark_work_order_receptor_coordinate_validation_min_atom_records")
            ),
            "science_accuracy_frontier_public_benchmark_receptor_coordinate_validation_min_macromolecule_atom_records": _int(
                science_frontier.get(
                    "public_benchmark_work_order_receptor_coordinate_validation_min_macromolecule_atom_records"
                )
            ),
            "science_accuracy_frontier_public_benchmark_receptor_coordinate_validation_min_distinct_residues": _int(
                science_frontier.get("public_benchmark_work_order_receptor_coordinate_validation_min_distinct_residues")
            ),
            "science_accuracy_frontier_public_benchmark_receptor_coordinate_validation_min_protein_like_residues": _int(
                science_frontier.get("public_benchmark_work_order_receptor_coordinate_validation_min_protein_like_residues")
            ),
            "science_accuracy_frontier_public_benchmark_metric_evidence_ready_row_count": _int(
                science_frontier.get("public_benchmark_work_order_metric_evidence_ready_row_count")
            ),
            "science_accuracy_frontier_public_benchmark_metric_evidence_blocked_row_count": _int(
                science_frontier.get("public_benchmark_work_order_metric_evidence_blocked_row_count")
            ),
            "science_accuracy_frontier_public_benchmark_metric_evidence_missing_required_input_artifact_row_count": _int(
                science_frontier.get(
                    "public_benchmark_work_order_metric_evidence_missing_required_input_artifact_row_count"
                )
            ),
            "science_accuracy_frontier_public_benchmark_metric_evidence_missing_dockq_source_row_count": _int(
                science_frontier.get("public_benchmark_work_order_metric_evidence_missing_dockq_source_row_count")
            ),
            "science_accuracy_frontier_public_benchmark_metric_evidence_missing_lddt_pli_source_row_count": _int(
                science_frontier.get("public_benchmark_work_order_metric_evidence_missing_lddt_pli_source_row_count")
            ),
            "science_accuracy_frontier_public_benchmark_metric_evidence_missing_internal_deltaG_source_row_count": _int(
                science_frontier.get(
                    "public_benchmark_work_order_metric_evidence_missing_internal_deltaG_source_row_count"
                )
            ),
            "full_commercial_release_blocker_ids": full_commercial_blocker_ids,
            "check_count": len(rows),
            "required_check_count": len(required_rows),
            "pass_count": sum(1 for row in rows if row["status"] == "pass"),
            "blocker_count": len(blocker_rows),
            "blocked_checks": [row["check"] for row in blocker_rows],
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_boundary": CLAIM_BOUNDARY,
            "next_required_step": (
                "Independent restricted product readiness is verified; keep full-commercial claims blocked "
                "until R8/R9 evidence receipts and ACCURACY broad claim review clear."
                if independent_ready
                else "Fix the failed readiness checks, rerun the current release refresh, and retry this script."
            ),
        },
        "rows": rows,
    }
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify current independent restricted product readiness.")
    parser.add_argument("--out-json", default="", help="Optional path to write the verification payload.")
    parser.add_argument("--quiet", action="store_true", help="Do not print the JSON payload to stdout.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_independent_product_readiness(root=ROOT)
    if args.out_json:
        path = _resolve(args.out_json, root=ROOT)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    if not args.quiet:
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if payload["summary"]["independent_restricted_product_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
