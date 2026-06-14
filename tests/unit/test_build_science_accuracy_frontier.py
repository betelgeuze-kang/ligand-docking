from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_science_accuracy_frontier as mod


def _write(path: Path, summary: dict) -> None:
    path.write_text(json.dumps({"summary": summary}) + "\n", encoding="utf-8")


def _write_inputs(
    tmp_path: Path,
    *,
    ready: bool = False,
    materialized_candidate_ready: bool = False,
) -> dict[str, Path]:
    paths = {
        "accuracy_json": tmp_path / "accuracy.json",
        "gpcr_broad_json": tmp_path / "gpcr.json",
        "engine_refinement_json": tmp_path / "engine.json",
        "public_benchmark_json": tmp_path / "public.json",
        "public_benchmark_materialization_json": tmp_path / "public_materialization.json",
        "public_benchmark_materialized_apply_json": tmp_path / "public_materialized_apply.json",
        "public_benchmark_statistical_support_work_order_json": tmp_path / "public_stat_work_order.json",
        "public_benchmark_statistical_support_metric_materialization_readiness_json": (
            tmp_path / "public_stat_metric_materialization_readiness.json"
        ),
        "engine_receipt_json": tmp_path / "receipt.json",
        "engine_priority_json": tmp_path / "priority.json",
        "pose_sampling_json": tmp_path / "pose.json",
    }
    _write(
        paths["accuracy_json"],
        {
            "status": "blocked_accuracy_parity",
            "accuracy_parity_ligand_ranking_metric_thresholds_pass": True,
            "accuracy_parity_ligand_ranking_claim_scope_lock_only": True,
            "accuracy_parity_ligand_ranking_metric_blocker_count": 0,
            "blocked_row_count": 0,
            "missing_row_count": 0,
        },
    )
    _write(
        paths["gpcr_broad_json"],
        {
            "status": (
                "gpcr_broad_claim_scope_ready"
                if ready
                else "blocked_gpcr_broad_claim_scope_readiness"
            ),
            "target_heldout_family_guardrail_ready": True,
            "guarded_100k_claim_review_inputs_ready": True,
            "target_heldout_broad_scope_review_input_ready": True,
            "accuracy_parity_metric_ready": True,
            "claim_promotion_allowed": ready,
            "router_claim_allowed": ready,
            "blocker_count": 0 if ready else 2,
        },
    )
    _write(
        paths["engine_refinement_json"],
        {
            "status": "engine_refinement_tier_ready",
            "engine_refinement_tier_ready": True,
            "blocked_count": 0,
            "claim_promotion_allowed": ready,
            "claim_promotion_blocker_count": 0 if ready else 6,
        },
    )
    _write(
        paths["public_benchmark_json"],
        {
            "status": (
                "refine_tier_public_benchmark_ready"
                if ready
                else "blocked_refine_tier_public_benchmark_readiness"
            ),
            "claim_grade_public_benchmark_ready": ready,
            "operator_work_order_ready": not ready,
            "blocker_count": 0 if ready else 6,
            "min_total_rows_required": 8,
            "row_count": 8 if ready else 0,
            "work_order_row_count": 0 if ready else 8,
            "work_order_seeded_row_count": 0 if ready else 8,
            "work_order_prefilled_operator_field_count": 0 if ready else 40,
            "work_order_pending_operator_field_count": 0 if ready else 56,
            "work_order_experimental_deltaG_prefilled_count": 0 if ready else 8,
            "work_order_experimental_deltaG_source_parsed_count": 0 if ready else 285,
            "work_order_pending_license_ok_count": 0 if ready else 8,
            "work_order_pending_dockq_count": 0 if ready else 8,
            "work_order_pending_lddt_pli_count": 0 if ready else 8,
            "work_order_pending_internal_deltaG_count": 0 if ready else 8,
            "work_order_pending_experimental_deltaG_count": 0,
            "work_order_remaining_nonlicense_science_field_count": 0 if ready else 48,
            "work_order_current_local_source_prefill_ready_field_count": 0,
            "work_order_local_receptor_coordinate_file_count": 0 if ready else 8,
            "work_order_tar_ligand_pose_member_count": 0 if ready else 23062,
            "work_order_tar_receptor_coordinate_member_count": 0,
            "work_order_tar_ligand_only_archive_count": 0 if ready else 2,
            "work_order_science_input_gap_row_count": 0 if ready else 8,
            "work_order_science_input_gap_blocked_row_count": 0 if ready else 8,
            "work_order_local_ligand_pose_artifact_count": 0 if ready else 8,
            "work_order_missing_ligand_pose_artifact_count": 0,
            "work_order_receptor_coordinate_ready_row_count": 0 if ready else 8,
            "work_order_missing_receptor_coordinate_row_count": 0,
            "work_order_receptor_coordinate_intake_row_count": 0 if ready else 8,
            "work_order_receptor_coordinate_intake_matched_row_count": 0 if ready else 8,
            "work_order_receptor_coordinate_intake_missing_row_count": 0,
            "work_order_receptor_coordinate_intake_suggested_public_url_row_count": 0 if ready else 8,
            "work_order_receptor_coordinate_intake_suggested_local_path_row_count": 0 if ready else 8,
            "work_order_receptor_coordinate_intake_operator_review_required_row_count": 0 if ready else 8,
            "work_order_receptor_coordinate_validation_row_count": 0 if ready else 8,
            "work_order_receptor_coordinate_validation_ready_row_count": 0 if ready else 8,
            "work_order_receptor_coordinate_validation_blocked_row_count": 0,
            "work_order_receptor_coordinate_validation_missing_row_count": 0,
            "work_order_receptor_coordinate_validation_below_min_atom_row_count": 0,
            "work_order_receptor_coordinate_validation_below_min_macromolecule_row_count": 0,
            "work_order_receptor_coordinate_validation_below_min_protein_like_row_count": 0,
            "work_order_receptor_coordinate_validation_min_atom_records": 20,
            "work_order_receptor_coordinate_validation_min_macromolecule_atom_records": 20,
            "work_order_receptor_coordinate_validation_min_distinct_residues": 5,
            "work_order_receptor_coordinate_validation_min_protein_like_residues": 5,
            "work_order_metric_evidence_required": True,
            "work_order_metric_evidence_row_count": 0 if ready else 8,
            "work_order_metric_evidence_ready_row_count": 0,
            "work_order_metric_evidence_blocked_row_count": 0 if ready else 8,
            "work_order_metric_evidence_missing_required_input_artifact_row_count": 0,
            "work_order_metric_evidence_missing_required_input_artifact_sha256_row_count": 0,
            "work_order_metric_evidence_missing_dockq_source_row_count": 0 if ready else 8,
            "work_order_metric_evidence_missing_lddt_pli_source_row_count": 0 if ready else 8,
            "work_order_metric_evidence_missing_internal_deltaG_source_row_count": 0 if ready else 8,
            "work_order_ligand_pose_only_row_count": 0,
            "work_order_missing_interaction_metric_source_row_count": 0 if ready else 8,
            "work_order_missing_internal_deltaG_source_row_count": 0 if ready else 8,
            "work_order_seed_interaction_metric_column_count": 0,
            "work_order_seed_internal_deltaG_column_count": 0,
            "work_order_seed_candidate_row_count": 0 if ready else 5824,
            "work_order_seed_distinct_target_count": 0 if ready else 284,
        },
    )
    _write(
        paths["public_benchmark_materialization_json"],
        {
            "status": (
                "refine_tier_public_benchmark_metric_sources_materialized"
                if materialized_candidate_ready
                else "blocked_refine_tier_public_benchmark_metric_source_materialization"
            ),
            "work_order_row_count": 8,
            "materialized_row_count": 8 if materialized_candidate_ready else 0,
            "blocked_row_count": 0 if materialized_candidate_ready else 8,
            "metric_evidence_row_count": 8,
            "metric_evidence_pass_row_count": 8 if materialized_candidate_ready else 0,
            "metric_evidence_blocked_row_count": 0 if materialized_candidate_ready else 8,
            "free_energy_pair_count": 8 if materialized_candidate_ready else 0,
            "free_energy_fit_pair_count": 5 if materialized_candidate_ready else 0,
            "free_energy_holdout_pair_count": 3 if materialized_candidate_ready else 0,
            "free_energy_unknown_split_pair_count": 0,
            "free_energy_spearman": 0.6190476190476191 if materialized_candidate_ready else None,
            "free_energy_spearman_gate_ready": materialized_candidate_ready,
            "free_energy_spearman_bootstrap_p05": -0.14285714285714285
            if materialized_candidate_ready
            else None,
            "free_energy_spearman_bootstrap_p50": 0.6428571428571429
            if materialized_candidate_ready
            else None,
            "free_energy_spearman_bootstrap_p95": 1.0 if materialized_candidate_ready else None,
            "claim_grade_public_benchmark_statistical_support_ready": False,
            "claim_grade_public_benchmark_statistical_support_blocker_count": (
                3 if materialized_candidate_ready else 0
            ),
            "claim_grade_public_benchmark_statistical_support_blockers": (
                [
                    "claim_grade_public_benchmark_pair_count_below_minimum",
                    "claim_grade_public_benchmark_holdout_pair_count_below_minimum",
                    "claim_grade_public_benchmark_bootstrap_spearman_low_below_minimum",
                ]
                if materialized_candidate_ready
                else []
            ),
            "min_claim_grade_public_benchmark_pairs_required": 25,
            "min_claim_grade_holdout_pairs_required": 8,
            "min_claim_grade_bootstrap_spearman_low_required": 0.5,
        },
    )
    _write(
        paths["public_benchmark_materialized_apply_json"],
        {
            "status": (
                "refine_tier_public_benchmark_work_order_apply_ready"
                if materialized_candidate_ready
                else "blocked_refine_tier_public_benchmark_work_order_apply"
            ),
            "apply_ready": materialized_candidate_ready,
            "blocked_row_count": 0 if materialized_candidate_ready else 8,
            "metric_evidence_pass_row_count": 8 if materialized_candidate_ready else 0,
            "metric_evidence_contract_blocked_row_count": 0 if materialized_candidate_ready else 8,
        },
    )
    _write(
        paths["public_benchmark_statistical_support_work_order_json"],
        {
            "status": "refine_tier_public_benchmark_statistical_support_work_order_ready",
            "work_order_ready": True,
            "claim_grade_public_benchmark_statistical_support_ready": ready,
            "canonical_intake_promotion_allowed": ready,
            "expansion_slot_count": 17 if materialized_candidate_ready and not ready else 0,
            "minimum_new_pair_count": 17 if materialized_candidate_ready and not ready else 0,
            "minimum_new_holdout_pair_count": 5 if materialized_candidate_ready and not ready else 0,
            "minimum_new_fit_or_holdout_pair_count": 12 if materialized_candidate_ready and not ready else 0,
            "bootstrap_retest_required": not ready,
        },
    )
    _write(
        paths["public_benchmark_statistical_support_metric_materialization_readiness_json"],
        {
            "status": (
                "refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_ready"
            ),
            "metric_materialization_readiness_ready": True,
            "metric_materialization_all_candidates_ready": ready,
            "metric_materialization_row_count": 17 if materialized_candidate_ready and not ready else 0,
            "metric_materialization_candidate_ready_count": 0,
            "metric_materialization_candidate_blocked_count": 17 if materialized_candidate_ready and not ready else 0,
            "coordinate_validation_pass_row_count": 0,
            "coordinate_validation_blocked_row_count": 17 if materialized_candidate_ready and not ready else 0,
            "existing_metric_source_payload_count": 0,
            "planned_metric_source_payload_count": 51 if materialized_candidate_ready and not ready else 0,
            "required_metric_source_payloads": "dockq;lddt_pli;internal_deltaG",
            "claim_grade_statistical_support_ready": ready,
            "next_required_step": (
                "After operator-approved coordinate fetch and post-fetch validation, require all 17 "
                "statistical-support candidates to pass coordinate validation before materializing "
                "DockQ, lDDT-PLI, and internal DeltaG source payloads and rerunning bootstrap "
                "Spearman p05."
            ),
        },
    )
    _write(
        paths["engine_receipt_json"],
        {
            "status": (
                "engine_refinement_claim_evidence_receipt_ready"
                if ready
                else "blocked_engine_refinement_claim_evidence_receipt"
            ),
            "claim_promotion_evidence_receipt_ready": ready,
            "blocked_row_count": 0 if ready else 6,
        },
    )
    _write(
        paths["engine_priority_json"],
        {
            "status": (
                "engine_refinement_claim_evidence_priority_packet_ready"
                if ready
                else "blocked_engine_refinement_claim_evidence_priority_packet"
            ),
            "priority_packet_ready": True,
            "top_blocker_id": "" if ready else "public_benchmark_gate_not_ready",
            "top_required_input": "" if ready else "runs/refine_tier_public_benchmark_work_order_current.csv",
        },
    )
    _write(
        paths["pose_sampling_json"],
        {
            "status": "product_pose_sampling_readiness_ready",
            "pose_generation_contract_ready": True,
            "pocket_detection_ready": True,
        },
    )
    return paths


def test_science_accuracy_frontier_blocks_commercial_parity_without_public_r9_evidence(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path, ready=False)

    payload = mod.build_science_accuracy_frontier(**paths)
    summary = payload["summary"]

    assert summary["status"] == "blocked_science_accuracy_frontier"
    assert summary["restricted_science_accuracy_ready"] is True
    assert summary["broad_commercial_accuracy_claim_ready"] is False
    assert summary["gpcr_ligand_metric_ready"] is True
    assert summary["gpcr_target_heldout_guarded_inputs_ready"] is True
    assert summary["engine_refinement_internal_surface_ready"] is True
    assert summary["openmm_schrodinger_public_benchmark_ready"] is False
    assert summary["openmm_schrodinger_public_benchmark_science_ready"] is False
    assert summary["public_benchmark_materialized_metric_ready"] is False
    assert summary["public_benchmark_materialized_apply_ready"] is False
    assert summary["public_benchmark_materialized_row_count"] == 0
    assert summary["public_benchmark_materialized_blocked_row_count"] == 8
    assert summary["public_benchmark_materialized_metric_evidence_pass_row_count"] == 0
    assert summary["public_benchmark_materialized_metric_evidence_blocked_row_count"] == 8
    assert summary["public_benchmark_materialized_free_energy_pair_count"] == 0
    assert summary["public_benchmark_materialized_free_energy_fit_pair_count"] == 0
    assert summary["public_benchmark_materialized_free_energy_holdout_pair_count"] == 0
    assert summary["public_benchmark_materialized_free_energy_spearman"] is None
    assert summary["public_benchmark_materialized_free_energy_spearman_gate_ready"] is False
    assert summary["public_benchmark_materialized_free_energy_spearman_bootstrap_p05"] is None
    assert summary["public_benchmark_materialized_claim_grade_statistical_support_ready"] is False
    assert summary["public_benchmark_materialized_claim_grade_statistical_support_blocker_count"] == 0
    assert summary["public_benchmark_statistical_support_work_order_ready"] is True
    assert summary["public_benchmark_statistical_support_work_order_expansion_slot_count"] == 0
    assert summary["public_benchmark_statistical_support_metric_materialization_readiness_ready"] is True
    assert summary["public_benchmark_statistical_support_metric_materialization_all_candidates_ready"] is False
    assert summary["public_benchmark_statistical_support_metric_materialization_row_count"] == 0
    assert summary["public_benchmark_statistical_support_metric_materialization_planned_metric_source_payload_count"] == 0
    assert summary["engine_refinement_claim_evidence_receipt_ready"] is False
    assert summary["public_benchmark_work_order_seeded_row_count"] == 8
    assert summary["public_benchmark_work_order_prefilled_operator_field_count"] == 40
    assert summary["public_benchmark_work_order_pending_operator_field_count"] == 56
    assert summary["public_benchmark_work_order_experimental_deltaG_prefilled_count"] == 8
    assert summary["public_benchmark_work_order_experimental_deltaG_source_parsed_count"] == 285
    assert summary["public_benchmark_work_order_pending_license_ok_count"] == 8
    assert summary["public_benchmark_work_order_pending_dockq_count"] == 8
    assert summary["public_benchmark_work_order_pending_lddt_pli_count"] == 8
    assert summary["public_benchmark_work_order_pending_internal_deltaG_count"] == 8
    assert summary["public_benchmark_work_order_pending_experimental_deltaG_count"] == 0
    assert summary["public_benchmark_work_order_remaining_nonlicense_science_field_count"] == 48
    assert summary["public_benchmark_work_order_current_local_source_prefill_ready_field_count"] == 0
    assert summary["public_benchmark_work_order_local_receptor_coordinate_file_count"] == 8
    assert summary["public_benchmark_work_order_tar_ligand_pose_member_count"] == 23062
    assert summary["public_benchmark_work_order_tar_receptor_coordinate_member_count"] == 0
    assert summary["public_benchmark_work_order_tar_ligand_only_archive_count"] == 2
    assert summary["public_benchmark_work_order_science_input_gap_row_count"] == 8
    assert summary["public_benchmark_work_order_science_input_gap_blocked_row_count"] == 8
    assert summary["public_benchmark_work_order_local_ligand_pose_artifact_count"] == 8
    assert summary["public_benchmark_work_order_missing_ligand_pose_artifact_count"] == 0
    assert summary["public_benchmark_work_order_receptor_coordinate_ready_row_count"] == 8
    assert summary["public_benchmark_work_order_missing_receptor_coordinate_row_count"] == 0
    assert summary["public_benchmark_work_order_receptor_coordinate_intake_row_count"] == 8
    assert summary["public_benchmark_work_order_receptor_coordinate_intake_matched_row_count"] == 8
    assert summary["public_benchmark_work_order_receptor_coordinate_intake_missing_row_count"] == 0
    assert summary["public_benchmark_work_order_receptor_coordinate_intake_suggested_public_url_row_count"] == 8
    assert summary["public_benchmark_work_order_receptor_coordinate_intake_suggested_local_path_row_count"] == 8
    assert summary["public_benchmark_work_order_receptor_coordinate_intake_operator_review_required_row_count"] == 8
    assert summary["public_benchmark_work_order_receptor_coordinate_validation_row_count"] == 8
    assert summary["public_benchmark_work_order_receptor_coordinate_validation_ready_row_count"] == 8
    assert summary["public_benchmark_work_order_receptor_coordinate_validation_blocked_row_count"] == 0
    assert summary["public_benchmark_work_order_receptor_coordinate_validation_missing_row_count"] == 0
    assert summary["public_benchmark_work_order_receptor_coordinate_validation_below_min_atom_row_count"] == 0
    assert summary["public_benchmark_work_order_receptor_coordinate_validation_below_min_macromolecule_row_count"] == 0
    assert summary["public_benchmark_work_order_receptor_coordinate_validation_below_min_protein_like_row_count"] == 0
    assert summary["public_benchmark_work_order_receptor_coordinate_validation_min_atom_records"] == 20
    assert summary["public_benchmark_work_order_receptor_coordinate_validation_min_macromolecule_atom_records"] == 20
    assert summary["public_benchmark_work_order_receptor_coordinate_validation_min_distinct_residues"] == 5
    assert summary["public_benchmark_work_order_receptor_coordinate_validation_min_protein_like_residues"] == 5
    assert summary["public_benchmark_work_order_metric_evidence_required"] is True
    assert summary["public_benchmark_work_order_metric_evidence_row_count"] == 8
    assert summary["public_benchmark_work_order_metric_evidence_ready_row_count"] == 0
    assert summary["public_benchmark_work_order_metric_evidence_blocked_row_count"] == 8
    assert summary["public_benchmark_work_order_metric_evidence_missing_required_input_artifact_row_count"] == 0
    assert summary["public_benchmark_work_order_metric_evidence_missing_required_input_artifact_sha256_row_count"] == 0
    assert summary["public_benchmark_work_order_metric_evidence_missing_dockq_source_row_count"] == 8
    assert summary["public_benchmark_work_order_metric_evidence_missing_lddt_pli_source_row_count"] == 8
    assert summary["public_benchmark_work_order_metric_evidence_missing_internal_deltaG_source_row_count"] == 8
    assert summary["public_benchmark_work_order_ligand_pose_only_row_count"] == 0
    assert summary["public_benchmark_work_order_missing_interaction_metric_source_row_count"] == 8
    assert summary["public_benchmark_work_order_missing_internal_deltaG_source_row_count"] == 8
    assert summary["public_benchmark_work_order_seed_interaction_metric_column_count"] == 0
    assert summary["public_benchmark_work_order_seed_internal_deltaG_column_count"] == 0
    assert summary["public_benchmark_work_order_seed_candidate_row_count"] == 5824
    assert summary["public_benchmark_work_order_seed_distinct_target_count"] == 284
    assert summary["blocker_count"] == 4
    assert summary["blockers"] == [
        "gpcr_broad_claim_review_not_approved",
        "gpcr_scorer_router_promotion_not_approved",
        "openmm_schrodinger_public_benchmark_metric_candidate_not_ready",
        "engine_refinement_claim_evidence_receipt_not_ready",
    ]
    assert summary["external_state_mutated"] is False


def test_science_accuracy_frontier_distinguishes_materialized_r9_metric_candidate_from_promotion(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path, ready=False, materialized_candidate_ready=True)

    payload = mod.build_science_accuracy_frontier(**paths)
    summary = payload["summary"]

    assert summary["status"] == "blocked_science_accuracy_frontier"
    assert summary["restricted_science_accuracy_ready"] is True
    assert summary["openmm_schrodinger_public_benchmark_ready"] is False
    assert summary["openmm_schrodinger_public_benchmark_science_ready"] is True
    assert summary["public_benchmark_materialized_metric_ready"] is True
    assert summary["public_benchmark_materialized_apply_ready"] is True
    assert summary["public_benchmark_materialized_row_count"] == 8
    assert summary["public_benchmark_materialized_blocked_row_count"] == 0
    assert summary["public_benchmark_materialized_metric_evidence_pass_row_count"] == 8
    assert summary["public_benchmark_materialized_metric_evidence_blocked_row_count"] == 0
    assert summary["public_benchmark_materialized_free_energy_pair_count"] == 8
    assert summary["public_benchmark_materialized_free_energy_fit_pair_count"] == 5
    assert summary["public_benchmark_materialized_free_energy_holdout_pair_count"] == 3
    assert summary["public_benchmark_materialized_free_energy_spearman"] == 0.6190476190476191
    assert summary["public_benchmark_materialized_free_energy_spearman_gate_ready"] is True
    assert summary["public_benchmark_materialized_free_energy_spearman_bootstrap_p05"] == -0.14285714285714285
    assert summary["public_benchmark_materialized_free_energy_spearman_bootstrap_p50"] == 0.6428571428571429
    assert summary["public_benchmark_materialized_free_energy_spearman_bootstrap_p95"] == 1.0
    assert summary["public_benchmark_materialized_claim_grade_statistical_support_ready"] is False
    assert summary["public_benchmark_materialized_claim_grade_statistical_support_blocker_count"] == 3
    assert summary["public_benchmark_materialized_claim_grade_statistical_support_blockers"] == [
        "claim_grade_public_benchmark_pair_count_below_minimum",
        "claim_grade_public_benchmark_holdout_pair_count_below_minimum",
        "claim_grade_public_benchmark_bootstrap_spearman_low_below_minimum",
    ]
    assert summary["public_benchmark_statistical_support_work_order_ready"] is True
    assert summary["public_benchmark_statistical_support_work_order_expansion_slot_count"] == 17
    assert summary["public_benchmark_statistical_support_work_order_minimum_new_pair_count"] == 17
    assert summary["public_benchmark_statistical_support_work_order_minimum_new_holdout_pair_count"] == 5
    assert summary["public_benchmark_statistical_support_work_order_minimum_new_fit_or_holdout_pair_count"] == 12
    assert summary["public_benchmark_statistical_support_work_order_bootstrap_retest_required"] is True
    assert summary["public_benchmark_statistical_support_work_order_canonical_intake_promotion_allowed"] is False
    assert summary["public_benchmark_statistical_support_metric_materialization_readiness_present"] is True
    assert summary["public_benchmark_statistical_support_metric_materialization_readiness_ready"] is True
    assert summary["public_benchmark_statistical_support_metric_materialization_all_candidates_ready"] is False
    assert summary["public_benchmark_statistical_support_metric_materialization_row_count"] == 17
    assert summary["public_benchmark_statistical_support_metric_materialization_candidate_ready_count"] == 0
    assert summary["public_benchmark_statistical_support_metric_materialization_candidate_blocked_count"] == 17
    assert (
        summary[
            "public_benchmark_statistical_support_metric_materialization_coordinate_validation_pass_row_count"
        ]
        == 0
    )
    assert (
        summary[
            "public_benchmark_statistical_support_metric_materialization_coordinate_validation_blocked_row_count"
        ]
        == 17
    )
    assert (
        summary[
            "public_benchmark_statistical_support_metric_materialization_existing_metric_source_payload_count"
        ]
        == 0
    )
    assert (
        summary[
            "public_benchmark_statistical_support_metric_materialization_planned_metric_source_payload_count"
        ]
        == 51
    )
    assert summary[
        "public_benchmark_statistical_support_metric_materialization_required_metric_source_payloads"
    ] == "dockq;lddt_pli;internal_deltaG"
    assert summary["blockers"] == [
        "gpcr_broad_claim_review_not_approved",
        "gpcr_scorer_router_promotion_not_approved",
        "openmm_schrodinger_public_benchmark_not_promoted_to_canonical_intake",
        "openmm_schrodinger_public_benchmark_statistical_support_not_claim_grade",
        "openmm_schrodinger_public_benchmark_statistical_support_metric_sources_not_materialized",
        "engine_refinement_claim_evidence_receipt_not_ready",
    ]
    assert "current 8-row materialized R9 metric evidence" in summary["next_required_step"]
    assert "coordinate validation/materialization" in summary["next_required_step"]


def test_science_accuracy_frontier_can_turn_ready_when_claim_evidence_is_ready(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path, ready=True)

    payload = mod.build_science_accuracy_frontier(**paths)
    summary = payload["summary"]

    assert summary["status"] == "science_accuracy_frontier_commercial_parity_ready"
    assert summary["restricted_science_accuracy_ready"] is True
    assert summary["broad_commercial_accuracy_claim_ready"] is True
    assert summary["openmm_schrodinger_claim_ready"] is True
    assert summary["blocker_count"] == 0


def test_science_accuracy_frontier_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, ready=False)
    out_json = tmp_path / "frontier.json"
    out_md = tmp_path / "frontier.md"

    mod.main(
        [
            "--accuracy-json",
            str(paths["accuracy_json"]),
            "--gpcr-broad-json",
            str(paths["gpcr_broad_json"]),
            "--engine-refinement-json",
            str(paths["engine_refinement_json"]),
            "--public-benchmark-json",
            str(paths["public_benchmark_json"]),
            "--public-benchmark-materialization-json",
            str(paths["public_benchmark_materialization_json"]),
            "--public-benchmark-materialized-apply-json",
            str(paths["public_benchmark_materialized_apply_json"]),
            "--public-benchmark-statistical-support-work-order-json",
            str(paths["public_benchmark_statistical_support_work_order_json"]),
            "--public-benchmark-statistical-support-metric-materialization-readiness-json",
            str(paths["public_benchmark_statistical_support_metric_materialization_readiness_json"]),
            "--engine-receipt-json",
            str(paths["engine_receipt_json"]),
            "--engine-priority-json",
            str(paths["engine_priority_json"]),
            "--pose-sampling-json",
            str(paths["pose_sampling_json"]),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "blocked_science_accuracy_frontier"
    assert "Science Accuracy Frontier" in out_md.read_text(encoding="utf-8")
