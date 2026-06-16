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
        "public_benchmark_statistical_support_coordinate_intake_json": (
            tmp_path / "public_stat_coordinate_intake.json"
        ),
        "public_benchmark_statistical_support_metric_source_templates_json": (
            tmp_path / "public_stat_metric_source_templates.json"
        ),
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_json": (
            tmp_path / "public_stat_metric_source_payload_operator_receipt.json"
        ),
        "public_benchmark_statistical_support_metric_source_candidate_fill_json": (
            tmp_path / "public_stat_metric_source_candidate_fill.json"
        ),
        "public_benchmark_residual_metric_payload_priority_packet_json": (
            tmp_path / "public_residual_metric_payload_priority_packet.json"
        ),
        "public_benchmark_seeded_metric_payload_receipt_backfill_packet_json": (
            tmp_path / "public_seeded_metric_payload_receipt_backfill_packet.json"
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_preflight_json": (
            tmp_path / "public_stat_coordinate_fetch_r4_preflight.json"
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_json": (
            tmp_path / "public_stat_coordinate_fetch_operator_receipt.json"
        ),
        "public_benchmark_claim_grade_gap_audit_json": tmp_path / "public_claim_grade_gap_audit.json",
        "public_benchmark_bootstrap_driver_operator_chain_rollup_json": (
            tmp_path / "public_bootstrap_driver_operator_chain_rollup.json"
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
            "broad_claim_review_receipt_status": (
                "gpcr_broad_claim_review_receipt_ready"
                if ready
                else "blocked_gpcr_broad_claim_review_receipt"
            ),
            "broad_claim_review_receipt_ready": ready,
            "broad_claim_review_receipt_row_count": 2,
            "broad_claim_review_receipt_pass_row_count": 2 if ready else 0,
            "broad_claim_review_receipt_blocked_row_count": 0 if ready else 2,
            "broad_claim_review_receipt_operator_review_surface_ready_count": 2,
            "broad_claim_review_receipt_operator_review_surface_blocked_count": 0,
            "broad_claim_review_receipt_evidence_artifact_present_count": 2 if ready else 0,
            "broad_claim_review_receipt_evidence_status_contract_present_count": 2,
            "broad_claim_review_receipt_expected_true_fields_present_count": 2,
            "broad_claim_review_receipt_external_engine_calls_zero_count": 2,
            "broad_claim_review_receipt_manual_field_pending_count": 0 if ready else 16,
            "broad_claim_review_receipt_first_blocked_review_id": (
                "" if ready else "target_heldout_broad_scope_review_not_approved"
            ),
            "broad_claim_review_receipt_approval_token_required": "APPROVE_GPCR_BROAD_CLAIM_REVIEW",
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
            "metric_materialization_input_artifact_contract_ready": ready,
            "required_metric_input_artifact_count": 34 if materialized_candidate_ready and not ready else 0,
            "present_required_metric_input_artifact_count": 17 if materialized_candidate_ready and not ready else 0,
            "missing_required_metric_input_artifact_count": 17 if materialized_candidate_ready and not ready else 0,
            "missing_required_metric_input_artifact_row_count": 17 if materialized_candidate_ready and not ready else 0,
            "coordinate_validation_pass_row_count": 0,
            "coordinate_validation_blocked_row_count": 17 if materialized_candidate_ready and not ready else 0,
            "existing_metric_source_payload_count": 0,
            "planned_metric_source_payload_count": 51 if materialized_candidate_ready and not ready else 0,
            "required_metric_source_payloads": "dockq;lddt_pli;internal_deltaG",
            "required_metric_source_payload_field_count": 11 if materialized_candidate_ready and not ready else 0,
            "required_metric_source_payload_fields": (
                "metric_name;target_id;pose_id;value;method;input_artifacts;input_artifact_sha256s;"
                "operator_id;reviewed_at_utc;license_ok;external_engine_calls"
            ),
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
        paths["public_benchmark_statistical_support_coordinate_intake_json"],
        {
            "status": "refine_tier_public_benchmark_statistical_support_coordinate_intake_ready",
            "coordinate_intake_ready": True,
            "coordinate_intake_row_count": 17 if materialized_candidate_ready and not ready else 0,
            "coordinate_intake_artifact_present_row_count": 0,
            "coordinate_intake_missing_row_count": 17 if materialized_candidate_ready and not ready else 0,
            "coordinate_intake_suggested_public_url_row_count": (
                17 if materialized_candidate_ready and not ready else 0
            ),
            "coordinate_intake_suggested_local_path_row_count": (
                17 if materialized_candidate_ready and not ready else 0
            ),
            "coordinate_intake_suggested_local_path_candidate_count": (
                136 if materialized_candidate_ready and not ready else 0
            ),
            "coordinate_intake_suggested_local_path_present_count": 0,
            "coordinate_intake_suggested_local_path_present_target_count": 0,
            "coordinate_intake_suggested_local_path_missing_target_count": (
                17 if materialized_candidate_ready and not ready else 0
            ),
            "coordinate_intake_expected_archive_member_example_count": (
                51 if materialized_candidate_ready and not ready else 0
            ),
            "coordinate_intake_operator_review_required_row_count": (
                17 if materialized_candidate_ready and not ready else 0
            ),
            "coordinate_validation_pass_row_count": 0,
            "coordinate_validation_blocked_row_count": 17 if materialized_candidate_ready and not ready else 0,
            "coordinate_validation_missing_row_count": 17 if materialized_candidate_ready and not ready else 0,
        },
    )
    _write(
        paths["public_benchmark_statistical_support_metric_source_templates_json"],
        {
            "status": "refine_tier_public_benchmark_statistical_support_metric_source_templates_ready",
            "metric_source_templates_ready": True,
            "metric_materialization_readiness_present": True,
            "metric_materialization_readiness_ready": True,
            "metric_materialization_row_count": 17 if materialized_candidate_ready and not ready else 0,
            "metric_materialization_candidate_ready_count": 0,
            "metric_materialization_candidate_blocked_count": (
                17 if materialized_candidate_ready and not ready else 0
            ),
            "coordinate_validation_pass_row_count": 0,
            "coordinate_validation_blocked_row_count": 17 if materialized_candidate_ready and not ready else 0,
            "planned_metric_source_payload_count": 51 if materialized_candidate_ready and not ready else 0,
            "existing_metric_source_payload_count": 0,
            "template_row_count": 51 if materialized_candidate_ready and not ready else 0,
            "template_candidate_row_count": 17 if materialized_candidate_ready and not ready else 0,
            "template_metric_name_count": 3 if materialized_candidate_ready and not ready else 0,
            "template_metric_source_artifact_path_row_count": (
                51 if materialized_candidate_ready and not ready else 0
            ),
            "template_payload_required_fields_present_row_count": (
                51 if materialized_candidate_ready and not ready else 0
            ),
            "metric_source_payload_fill_ready_row_count": 0,
            "metric_source_payload_fill_blocked_row_count": (
                51 if materialized_candidate_ready and not ready else 0
            ),
            "coordinate_validation_blocked_template_row_count": (
                51 if materialized_candidate_ready and not ready else 0
            ),
            "missing_required_input_template_row_count": (
                51 if materialized_candidate_ready and not ready else 0
            ),
            "existing_metric_source_payload_present_row_count": 0,
            "required_metric_source_payloads": "dockq;lddt_pli;internal_deltaG",
            "required_metric_source_payload_field_count": 11 if materialized_candidate_ready and not ready else 0,
            "required_metric_source_payload_fields": (
                "metric_name;target_id;pose_id;value;method;input_artifacts;input_artifact_sha256s;"
                "operator_id;reviewed_at_utc;license_ok;external_engine_calls"
            ),
            "placeholder_value_count": 51 if materialized_candidate_ready and not ready else 0,
            "placeholder_method_count": 51 if materialized_candidate_ready and not ready else 0,
            "placeholder_operator_id_count": 51 if materialized_candidate_ready and not ready else 0,
            "placeholder_reviewed_at_utc_count": 51 if materialized_candidate_ready and not ready else 0,
            "placeholder_license_ok_count": 51 if materialized_candidate_ready and not ready else 0,
            "external_engine_calls_total": 0,
            "canonical_intake_promotion_allowed": False,
            "next_required_step": (
                "After R4-approved coordinate fetch and validation, replace each operator placeholder "
                "with reviewed DockQ/lDDT-PLI/internal DeltaG values while preserving input artifact "
                "paths, hashes, license_ok=true, and external_engine_calls=0."
            ),
        },
    )
    _write(
        paths["public_benchmark_statistical_support_metric_source_payload_operator_receipt_json"],
        {
            "status": (
                "refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready"
                if ready
                else "blocked_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt"
            ),
            "operator_receipt_ready": ready,
            "receipt_csv_present": True,
            "receipt_row_count": 0 if ready or not materialized_candidate_ready else 51,
            "required_template_count": 0 if ready or not materialized_candidate_ready else 51,
            "metric_source_template_row_fingerprint_required": materialized_candidate_ready and not ready,
            "metric_source_template_row_fingerprint_verified_count": (
                51 if materialized_candidate_ready and not ready else 0
            ),
            "metric_source_template_row_fingerprint_mismatch_count": 0,
            "operator_review_surface_ready_count": 51 if materialized_candidate_ready and not ready else 0,
            "operator_review_surface_blocked_count": 0,
            "metric_source_artifact_path_present_count": (
                51 if materialized_candidate_ready and not ready else 0
            ),
            "required_metric_input_artifact_list_present_count": (
                51 if materialized_candidate_ready and not ready else 0
            ),
            "required_metric_input_artifact_sha256_list_present_count": (
                51 if materialized_candidate_ready and not ready else 0
            ),
            "required_metric_input_artifact_sha256_list_complete_count": 0,
            "required_metric_source_payload_fields_present_count": (
                51 if materialized_candidate_ready and not ready else 0
            ),
            "external_engine_calls_zero_count": 51 if materialized_candidate_ready and not ready else 0,
            "receipt_manual_field_pending_count": (
                510 if materialized_candidate_ready and not ready else 0
            ),
            "receipt_metric_value_pending_count": 51 if materialized_candidate_ready and not ready else 0,
            "receipt_method_pending_count": 51 if materialized_candidate_ready and not ready else 0,
            "receipt_input_artifacts_reviewed_pending_count": (
                51 if materialized_candidate_ready and not ready else 0
            ),
            "receipt_input_artifact_sha256s_reviewed_pending_count": (
                51 if materialized_candidate_ready and not ready else 0
            ),
            "receipt_metric_source_artifact_reviewed_pending_count": (
                51 if materialized_candidate_ready and not ready else 0
            ),
            "receipt_payload_schema_reviewed_pending_count": (
                51 if materialized_candidate_ready and not ready else 0
            ),
            "receipt_license_ok_pending_count": 51 if materialized_candidate_ready and not ready else 0,
            "receipt_operator_id_pending_count": 51 if materialized_candidate_ready and not ready else 0,
            "receipt_reviewed_at_utc_pending_count": (
                51 if materialized_candidate_ready and not ready else 0
            ),
            "receipt_approval_token_pending_count": (
                51 if materialized_candidate_ready and not ready else 0
            ),
            "pass_row_count": 0,
            "blocked_row_count": 0 if ready or not materialized_candidate_ready else 51,
            "approved_payload_count": 0,
            "template_fill_ready_row_count": 0,
            "coordinate_validation_pass_payload_row_count": 0,
            "coordinate_validation_blocked_payload_row_count": (
                51 if materialized_candidate_ready and not ready else 0
            ),
            "payload_write_allowed": False,
            "canonical_intake_promotion_allowed": False,
            "claim_promotion_allowed": False,
            "external_state_mutated": False,
            "first_blocked_template_id": (
                "r9_statistical_support_metric_source_template_001"
                if materialized_candidate_ready and not ready
                else ""
            ),
            "first_blocked_target_id": "4ivc" if materialized_candidate_ready and not ready else "",
            "first_blocked_pose_id": "4ivc_20" if materialized_candidate_ready and not ready else "",
            "first_blocked_metric_name": "dockq" if materialized_candidate_ready and not ready else "",
            "most_common_row_blocker": (
                "operator_placeholders_unfilled" if materialized_candidate_ready and not ready else ""
            ),
            "approval_token_required": "APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS",
            "blocker_count": 0 if ready or not materialized_candidate_ready else 1,
            "next_required_step": (
                "After the 17 coordinate candidates pass validation, fill all 51 metric-source payload "
                "receipt rows with numeric reviewed values."
                if materialized_candidate_ready and not ready
                else ""
            ),
        },
    )
    _write(
        paths["public_benchmark_statistical_support_metric_source_candidate_fill_json"],
        {
            "status": "blocked_refine_tier_public_benchmark_statistical_support_metric_candidates",
            "candidate_row_count": 0,
            "candidate_pass_row_count": 0,
            "candidate_blocked_row_count": 0,
            "metric_value_candidate_count": 0,
            "candidate_pair_count": 0,
            "candidate_pair_pass_count": 0,
            "combined_pair_count": 0,
            "combined_fit_pair_count": 0,
            "combined_holdout_pair_count": 0,
            "combined_free_energy_spearman": None,
            "free_energy_spearman_bootstrap_p05": None,
            "free_energy_spearman_bootstrap_p50": None,
            "free_energy_spearman_bootstrap_p95": None,
            "claim_grade_public_benchmark_statistical_support_ready": False,
            "claim_grade_public_benchmark_statistical_support_blocker_count": 0,
            "expected_metric_source_artifact_touched_count": 0,
            "payload_write_allowed": False,
            "operator_receipt_approval_filled": False,
            "canonical_intake_promotion_allowed": False,
            "claim_promotion_allowed": False,
        },
    )
    _write(
        paths["public_benchmark_residual_metric_payload_priority_packet_json"],
        {
            "status": (
                "refine_tier_public_benchmark_residual_metric_payload_priority_packet_ready"
                if materialized_candidate_ready
                else "blocked_refine_tier_public_benchmark_residual_metric_payload_priority_packet"
            ),
            "metric_payload_priority_row_count": 36 if materialized_candidate_ready else 0,
            "candidate_fill_matched_payload_count": 27 if materialized_candidate_ready else 0,
            "operator_receipt_matched_payload_count": 27 if materialized_candidate_ready else 0,
            "operator_receipt_missing_payload_count": 9 if materialized_candidate_ready else 0,
            "operator_receipt_blocked_payload_count": 27 if materialized_candidate_ready else 0,
            "existing_metric_source_artifact_present_without_receipt_count": (
                9 if materialized_candidate_ready else 0
            ),
            "metric_source_artifact_present_count": 9 if materialized_candidate_ready else 0,
            "operator_manual_pending_field_count": 270 if materialized_candidate_ready else 0,
            "residual_leverage_payload_count": 6 if materialized_candidate_ready else 0,
            "cv_worse_payload_count": 15 if materialized_candidate_ready else 0,
            "top_priority_target_id": "3n86" if materialized_candidate_ready else "",
            "top_priority_pose_id": "3n86_99" if materialized_candidate_ready else "",
            "top_priority_metric_name": "dockq" if materialized_candidate_ready else "",
            "first_missing_receipt_target_id": "2j7h" if materialized_candidate_ready else "",
            "first_missing_receipt_pose_id": "2j7h_48" if materialized_candidate_ready else "",
            "payload_write_allowed": False,
            "claim_promotion_allowed": False,
            "production_score_mutation_allowed": False,
            "external_state_mutated": False,
        },
    )
    _write(
        paths["public_benchmark_seeded_metric_payload_receipt_backfill_packet_json"],
        {
            "status": (
                "refine_tier_public_benchmark_seeded_metric_payload_receipt_backfill_packet_ready"
                if materialized_candidate_ready
                else "blocked_refine_tier_public_benchmark_seeded_metric_payload_receipt_backfill_packet"
            ),
            "payload_priority_json_present": materialized_candidate_ready,
            "seeded_backfill_row_count": 9 if materialized_candidate_ready else 0,
            "seeded_backfill_target_count": 3 if materialized_candidate_ready else 0,
            "seeded_backfill_targets": "1syi;2j7h;4e5w" if materialized_candidate_ready else "",
            "metric_source_artifact_present_count": 9 if materialized_candidate_ready else 0,
            "payload_schema_valid_count": 9 if materialized_candidate_ready else 0,
            "payload_schema_blocked_count": 0,
            "input_artifact_sha256_verified_row_count": 9 if materialized_candidate_ready else 0,
            "operator_manual_pending_field_count": 99 if materialized_candidate_ready else 0,
            "operator_receipt_backfill_ready": False,
            "canonical_receipt_write_allowed": False,
            "payload_write_allowed": False,
            "canonical_intake_promotion_allowed": False,
            "claim_promotion_allowed": False,
            "production_score_mutation_allowed": False,
            "external_state_mutated": False,
            "approval_token_required": "APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS",
        },
    )
    _write(
        paths["public_benchmark_statistical_support_coordinate_fetch_r4_preflight_json"],
        {
            "status": (
                "refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready"
                if materialized_candidate_ready and not ready
                else "blocked_refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight"
            ),
            "r4_preflight_ready": materialized_candidate_ready and not ready,
            "r4_row_count": 17 if materialized_candidate_ready and not ready else 0,
            "ready_for_r4_review_row_count": 17 if materialized_candidate_ready and not ready else 0,
            "blocked_r4_row_count": 0,
            "fetch_required_row_count": 17 if materialized_candidate_ready and not ready else 0,
            "metric_materialization_blocked_row_count": 17 if materialized_candidate_ready and not ready else 0,
            "planned_metric_source_payload_count": 51 if materialized_candidate_ready and not ready else 0,
            "authorized_for_external_download": False,
            "download_executed": False,
            "external_state_mutated": False,
            "approval_token_required": "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD",
            "execute_command": (
                "python3 tools/product/apply_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan.py "
                "--mode execute --run-post-fetch-validation --approval-token "
                "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD"
            ),
        },
    )
    _write(
        paths["public_benchmark_statistical_support_coordinate_fetch_operator_receipt_json"],
        {
            "status": (
                "refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready"
                if ready
                else "blocked_refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt"
            ),
            "operator_receipt_ready": ready,
            "receipt_csv_present": True,
            "receipt_row_count": 0 if ready or not materialized_candidate_ready else 17,
            "required_r4_review_count": 0 if ready or not materialized_candidate_ready else 17,
            "r4_preflight_row_fingerprint_required": materialized_candidate_ready and not ready,
            "r4_preflight_row_fingerprint_verified_count": (
                17 if materialized_candidate_ready and not ready else 0
            ),
            "r4_preflight_row_fingerprint_mismatch_count": 0,
            "operator_review_surface_ready_count": 17 if materialized_candidate_ready and not ready else 0,
            "operator_review_surface_blocked_count": 0,
            "source_url_present_count": 17 if materialized_candidate_ready and not ready else 0,
            "staging_destination_path_present_count": (
                17 if materialized_candidate_ready and not ready else 0
            ),
            "execute_command_present_count": 17 if materialized_candidate_ready and not ready else 0,
            "receipt_manual_field_pending_count": 187 if materialized_candidate_ready and not ready else 0,
            "pass_row_count": 0,
            "blocked_row_count": 0 if ready or not materialized_candidate_ready else 17,
            "approved_fetch_count": 0,
            "authorized_for_external_download": False,
            "download_executed": False,
            "canonical_intake_promotion_allowed": False,
            "claim_promotion_allowed": False,
            "external_state_mutated": False,
            "first_blocked_review_id": (
                "r9_statistical_support_coordinate_fetch_001"
                if materialized_candidate_ready and not ready
                else ""
            ),
            "first_blocked_target_id": "4ivc" if materialized_candidate_ready and not ready else "",
            "first_blocked_pose_id": "4ivc_20" if materialized_candidate_ready and not ready else "",
            "most_common_row_blocker": (
                "operator_placeholders_unfilled" if materialized_candidate_ready and not ready else ""
            ),
            "approval_token_required": "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD",
            "execute_command": (
                "python3 tools/product/apply_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan.py "
                "--mode execute --run-post-fetch-validation --approval-token "
                "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD"
            ),
            "blocker_count": 0 if ready or not materialized_candidate_ready else 1,
            "next_required_step": (
                "Fill all 17 coordinate fetch operator receipt rows before execute-mode download."
                if materialized_candidate_ready and not ready
                else ""
            ),
        },
    )
    _write(
        paths["public_benchmark_claim_grade_gap_audit_json"],
        {
            "status": (
                "refine_tier_public_benchmark_claim_grade_gap_audit_ready"
                if materialized_candidate_ready
                else "blocked_refine_tier_public_benchmark_claim_grade_gap_audit"
            ),
            "claim_grade_gap_audit_ready": materialized_candidate_ready,
            "claim_grade_statistical_support_ready": ready,
            "canonical_intake_promotion_allowed": ready,
            "bootstrap_retest_required": not ready,
            "observed_public_benchmark_pair_count": 8 if materialized_candidate_ready else 0,
            "observed_holdout_pair_count": 3 if materialized_candidate_ready else 0,
            "observed_bootstrap_spearman_p05": -0.14285714285714285
            if materialized_candidate_ready
            else None,
            "observed_bootstrap_spearman_p50": 0.6428571428571429 if materialized_candidate_ready else None,
            "observed_bootstrap_spearman_p95": 1.0 if materialized_candidate_ready else None,
            "bootstrap_spearman_p05_deficit": 0.6428571428571428 if materialized_candidate_ready else None,
            "minimum_new_pair_count": 17 if materialized_candidate_ready and not ready else 0,
            "minimum_new_holdout_pair_count": 5 if materialized_candidate_ready and not ready else 0,
            "coordinate_validation_pass_row_count": 0,
            "coordinate_validation_blocked_row_count": 17 if materialized_candidate_ready and not ready else 0,
            "coordinate_validation_deficit": 17 if materialized_candidate_ready and not ready else 0,
            "metric_source_payload_fill_ready_row_count": 0,
            "metric_source_payload_fill_blocked_row_count": 51
            if materialized_candidate_ready and not ready
            else 0,
            "metric_source_payload_fill_deficit": 51 if materialized_candidate_ready and not ready else 0,
            "planned_metric_source_payload_count": 51 if materialized_candidate_ready and not ready else 0,
            "coordinate_fetch_r4_fetch_required_row_count": 17 if materialized_candidate_ready and not ready else 0,
            "coordinate_fetch_r4_download_executed": False,
            "gap_row_count": 5 if materialized_candidate_ready and not ready else 0,
            "blocked_gap_row_count": 5 if materialized_candidate_ready and not ready else 0,
            "pass_gap_row_count": 0 if materialized_candidate_ready and not ready else 5,
            "blocker_count": 5 if materialized_candidate_ready and not ready else 0,
            "top_science_gap_id": (
                "coordinate_fetch_r4_approval_required" if materialized_candidate_ready and not ready else ""
            ),
            "top_statistical_gap_id": (
                "claim_grade_public_benchmark_pair_count_below_minimum"
                if materialized_candidate_ready and not ready
                else ""
            ),
            "next_required_step": (
                "Keep R9 claim-grade promotion blocked until coordinate validation and metric payloads close."
                if materialized_candidate_ready and not ready
                else ""
            ),
        },
    )
    _write(
        paths["public_benchmark_bootstrap_driver_operator_chain_rollup_json"],
        {
            "status": (
                "refine_tier_public_benchmark_bootstrap_driver_operator_chain_rollup_ready"
                if ready
                else "blocked_refine_tier_public_benchmark_bootstrap_driver_operator_chain_rollup"
            ),
            "operator_chain_surface_ready": materialized_candidate_ready and not ready or ready,
            "operator_chain_closure_ready": ready,
            "stage_count": 5 if materialized_candidate_ready or ready else 0,
            "stage_artifact_present_count": 5 if materialized_candidate_ready or ready else 0,
            "stage_surface_ready_count": 5 if ready else 4 if materialized_candidate_ready else 0,
            "source_staging_operator_manual_pending_field_count": (
                66 if materialized_candidate_ready and not ready else 0
            ),
            "machine_supported_pending_field_count": 36 if materialized_candidate_ready and not ready else 0,
            "machine_supported_prefilled_field_count": 36 if materialized_candidate_ready and not ready else 36 if ready else 0,
            "operator_only_pending_field_count": 30 if materialized_candidate_ready and not ready else 0,
            "machine_gap_pending_field_count": 0,
            "attestation_row_count": 6 if materialized_candidate_ready or ready else 0,
            "attestation_blocked_row_count": 6 if materialized_candidate_ready and not ready else 0,
            "attestation_merge_ready": ready,
            "merge_preview_pass_row_count": 6 if ready else 0,
            "merge_preview_blocked_row_count": 6 if materialized_candidate_ready and not ready else 0,
            "prefill_row_fingerprint_verified_count": 6 if materialized_candidate_ready or ready else 0,
            "prefill_row_fingerprint_mismatch_count": 0,
            "merged_candidate_row_count": 6 if ready else 0,
            "final_blocker_stage_id": (
                "attestation_merge_preview" if materialized_candidate_ready and not ready else ""
            ),
            "final_blocker": (
                "operator_only_placeholders_unfilled" if materialized_candidate_ready and not ready else ""
            ),
            "payload_write_allowed": False,
            "canonical_receipt_write_allowed": False,
            "canonical_intake_promotion_allowed": False,
            "claim_promotion_allowed": False,
            "blocker_count": 3 if materialized_candidate_ready and not ready else 0,
            "blockers": (
                [
                    "operator_attestation_rows_blocked",
                    "attestation_merge_rows_blocked",
                    "operator_chain_closure_not_ready",
                ]
                if materialized_candidate_ready and not ready
                else []
            ),
            "next_required_step": (
                "Fill the operator-only attestation rows, rerun attestation merge preview, then rerun "
                "staging apply against the merged candidate worksheet before any payload or canonical "
                "receipt write."
                if materialized_candidate_ready and not ready
                else ""
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
    assert summary["gpcr_broad_claim_review_receipt_ready"] is False
    assert summary["gpcr_broad_claim_review_receipt_blocked_row_count"] == 2
    assert summary["gpcr_broad_claim_review_receipt_operator_review_surface_ready_count"] == 2
    assert summary["gpcr_broad_claim_review_receipt_operator_review_surface_blocked_count"] == 0
    assert summary["gpcr_broad_claim_review_receipt_evidence_artifact_present_count"] == 0
    assert summary["gpcr_broad_claim_review_receipt_expected_true_fields_present_count"] == 2
    assert summary["gpcr_broad_claim_review_receipt_external_engine_calls_zero_count"] == 2
    assert summary["gpcr_broad_claim_review_receipt_manual_field_pending_count"] == 16
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
    assert (
        summary[
            "public_benchmark_statistical_support_metric_materialization_required_input_artifact_count"
        ]
        == 0
    )
    assert summary["public_benchmark_bootstrap_driver_operator_chain_rollup_present"] is True
    assert summary["public_benchmark_bootstrap_driver_operator_chain_surface_ready"] is False
    assert summary["public_benchmark_bootstrap_driver_operator_chain_closure_ready"] is False
    assert summary["public_benchmark_bootstrap_driver_operator_chain_operator_only_pending_field_count"] == 0
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
    assert summary["public_benchmark_claim_grade_gap_audit_present"] is True
    assert summary["public_benchmark_claim_grade_gap_audit_ready"] is True
    assert summary["public_benchmark_claim_grade_gap_audit_status"] == (
        "refine_tier_public_benchmark_claim_grade_gap_audit_ready"
    )
    assert summary["public_benchmark_claim_grade_gap_audit_claim_grade_statistical_support_ready"] is False
    assert summary["public_benchmark_claim_grade_gap_audit_canonical_intake_promotion_allowed"] is False
    assert summary["public_benchmark_claim_grade_gap_audit_bootstrap_retest_required"] is True
    assert summary["public_benchmark_claim_grade_gap_audit_observed_public_benchmark_pair_count"] == 8
    assert summary["public_benchmark_claim_grade_gap_audit_observed_holdout_pair_count"] == 3
    assert summary["public_benchmark_claim_grade_gap_audit_observed_bootstrap_spearman_p05"] == (
        -0.14285714285714285
    )
    assert summary["public_benchmark_claim_grade_gap_audit_bootstrap_spearman_p05_deficit"] == (
        0.6428571428571428
    )
    assert summary["public_benchmark_claim_grade_gap_audit_minimum_new_pair_count"] == 17
    assert summary["public_benchmark_claim_grade_gap_audit_minimum_new_holdout_pair_count"] == 5
    assert summary["public_benchmark_claim_grade_gap_audit_coordinate_validation_pass_row_count"] == 0
    assert summary["public_benchmark_claim_grade_gap_audit_coordinate_validation_blocked_row_count"] == 17
    assert summary["public_benchmark_claim_grade_gap_audit_coordinate_validation_deficit"] == 17
    assert summary["public_benchmark_claim_grade_gap_audit_metric_source_payload_fill_ready_row_count"] == 0
    assert summary["public_benchmark_claim_grade_gap_audit_metric_source_payload_fill_blocked_row_count"] == 51
    assert summary["public_benchmark_claim_grade_gap_audit_metric_source_payload_fill_deficit"] == 51
    assert summary["public_benchmark_claim_grade_gap_audit_planned_metric_source_payload_count"] == 51
    assert summary["public_benchmark_claim_grade_gap_audit_coordinate_fetch_r4_fetch_required_row_count"] == 17
    assert summary["public_benchmark_claim_grade_gap_audit_coordinate_fetch_r4_download_executed"] is False
    assert summary["public_benchmark_claim_grade_gap_audit_gap_row_count"] == 5
    assert summary["public_benchmark_claim_grade_gap_audit_blocked_gap_row_count"] == 5
    assert summary["public_benchmark_claim_grade_gap_audit_blocker_count"] == 5
    assert summary["public_benchmark_claim_grade_gap_audit_top_science_gap_id"] == (
        "coordinate_fetch_r4_approval_required"
    )
    assert summary["public_benchmark_claim_grade_gap_audit_top_statistical_gap_id"] == (
        "claim_grade_public_benchmark_pair_count_below_minimum"
    )
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
            "public_benchmark_statistical_support_metric_materialization_input_artifact_contract_ready"
        ]
        is False
    )
    assert (
        summary[
            "public_benchmark_statistical_support_metric_materialization_required_input_artifact_count"
        ]
        == 34
    )
    assert (
        summary[
            "public_benchmark_statistical_support_metric_materialization_present_required_input_artifact_count"
        ]
        == 17
    )
    assert (
        summary[
            "public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_count"
        ]
        == 17
    )
    assert (
        summary[
            "public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_row_count"
        ]
        == 17
    )
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
    assert (
        summary[
            "public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_field_count"
        ]
        == 11
    )
    assert summary[
        "public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_fields"
    ] == (
        "metric_name;target_id;pose_id;value;method;input_artifacts;input_artifact_sha256s;"
        "operator_id;reviewed_at_utc;license_ok;external_engine_calls"
    )
    assert summary["public_benchmark_statistical_support_metric_source_templates_present"] is True
    assert summary["public_benchmark_statistical_support_metric_source_templates_ready"] is True
    assert summary["public_benchmark_statistical_support_metric_source_templates_status"] == (
        "refine_tier_public_benchmark_statistical_support_metric_source_templates_ready"
    )
    assert summary["public_benchmark_statistical_support_metric_source_templates_template_row_count"] == 51
    assert summary[
        "public_benchmark_statistical_support_metric_source_templates_template_candidate_row_count"
    ] == 17
    assert summary["public_benchmark_statistical_support_metric_source_templates_template_metric_name_count"] == 3
    assert summary[
        "public_benchmark_statistical_support_metric_source_templates_template_metric_source_artifact_path_row_count"
    ] == 51
    assert summary[
        "public_benchmark_statistical_support_metric_source_templates_template_payload_required_fields_present_row_count"
    ] == 51
    assert summary[
        "public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count"
    ] == 0
    assert summary[
        "public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count"
    ] == 51
    assert summary[
        "public_benchmark_statistical_support_metric_source_templates_coordinate_validation_blocked_template_row_count"
    ] == 51
    assert summary[
        "public_benchmark_statistical_support_metric_source_templates_missing_required_input_template_row_count"
    ] == 51
    assert summary[
        "public_benchmark_statistical_support_metric_source_templates_existing_metric_source_payload_present_row_count"
    ] == 0
    assert summary["public_benchmark_statistical_support_metric_source_templates_placeholder_value_count"] == 51
    assert summary["public_benchmark_statistical_support_metric_source_templates_placeholder_method_count"] == 51
    assert summary["public_benchmark_statistical_support_metric_source_templates_placeholder_operator_id_count"] == 51
    assert (
        summary["public_benchmark_statistical_support_metric_source_templates_placeholder_reviewed_at_utc_count"]
        == 51
    )
    assert summary["public_benchmark_statistical_support_metric_source_templates_placeholder_license_ok_count"] == 51
    assert summary["public_benchmark_statistical_support_metric_source_templates_external_engine_calls_total"] == 0
    assert (
        summary["public_benchmark_statistical_support_metric_source_templates_canonical_intake_promotion_allowed"]
        is False
    )
    assert "external_engine_calls=0" in summary[
        "public_benchmark_statistical_support_metric_source_templates_next_required_step"
    ]
    assert (
        summary["public_benchmark_statistical_support_metric_source_payload_operator_receipt_present"]
        is True
    )
    assert (
        summary["public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready"]
        is False
    )
    assert summary["public_benchmark_statistical_support_metric_source_payload_operator_receipt_status"] == (
        "blocked_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt"
    )
    assert summary["public_benchmark_statistical_support_metric_source_payload_operator_receipt_csv_present"] is True
    assert summary["public_benchmark_statistical_support_metric_source_payload_operator_receipt_row_count"] == 51
    assert (
        summary["public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_template_count"]
        == 51
    )
    assert summary["public_benchmark_statistical_support_metric_source_payload_operator_receipt_pass_row_count"] == 0
    assert summary["public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_row_count"] == 51
    assert (
        summary["public_benchmark_statistical_support_metric_source_payload_operator_receipt_approved_payload_count"]
        == 0
    )
    assert (
        summary[
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_coordinate_validation_pass_payload_row_count"
        ]
        == 0
    )
    assert (
        summary[
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_coordinate_validation_blocked_payload_row_count"
        ]
        == 51
    )
    assert (
        summary[
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_required"
        ]
        is True
    )
    assert (
        summary[
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_verified_count"
        ]
        == 51
    )
    assert (
        summary[
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_mismatch_count"
        ]
        == 0
    )
    assert (
        summary[
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_operator_review_surface_ready_count"
        ]
        == 51
    )
    assert (
        summary[
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_operator_review_surface_blocked_count"
        ]
        == 0
    )
    assert (
        summary[
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_manual_field_pending_count"
        ]
        == 510
    )
    assert (
        summary["public_benchmark_statistical_support_metric_source_payload_operator_receipt_payload_write_allowed"]
        is False
    )
    assert (
        summary[
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_canonical_intake_promotion_allowed"
        ]
        is False
    )
    assert (
        summary["public_benchmark_statistical_support_metric_source_payload_operator_receipt_claim_promotion_allowed"]
        is False
    )
    assert (
        summary["public_benchmark_statistical_support_metric_source_payload_operator_receipt_external_state_mutated"]
        is False
    )
    assert summary[
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_first_blocked_template_id"
    ] == "r9_statistical_support_metric_source_template_001"
    assert summary[
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_first_blocked_metric_name"
    ] == "dockq"
    assert summary[
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_most_common_row_blocker"
    ] == "operator_placeholders_unfilled"
    assert summary[
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_approval_token_required"
    ] == "APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS"
    assert summary["public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocker_count"] == 1
    assert summary["public_benchmark_statistical_support_metric_source_candidate_fill_present"] is True
    assert summary["public_benchmark_statistical_support_metric_source_candidate_fill_ready"] is False
    assert summary["public_benchmark_statistical_support_coordinate_intake_present"] is True
    assert summary["public_benchmark_statistical_support_coordinate_intake_ready"] is True
    assert summary["public_benchmark_statistical_support_coordinate_intake_status"] == (
        "refine_tier_public_benchmark_statistical_support_coordinate_intake_ready"
    )
    assert summary["public_benchmark_statistical_support_coordinate_intake_row_count"] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_artifact_present_row_count"
    ] == 0
    assert summary["public_benchmark_statistical_support_coordinate_intake_missing_row_count"] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_suggested_public_url_row_count"
    ] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_row_count"
    ] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_candidate_count"
    ] == 136
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_count"
    ] == 0
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_target_count"
    ] == 0
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_missing_target_count"
    ] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_expected_archive_member_example_count"
    ] == 51
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_operator_review_required_row_count"
    ] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_coordinate_validation_pass_row_count"
    ] == 0
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_coordinate_validation_blocked_row_count"
    ] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_coordinate_validation_missing_row_count"
    ] == 17
    assert summary["public_benchmark_statistical_support_coordinate_fetch_r4_preflight_present"] is True
    assert summary["public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready"] is True
    assert summary["public_benchmark_statistical_support_coordinate_fetch_r4_preflight_status"] == (
        "refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready"
    )
    assert summary["public_benchmark_statistical_support_coordinate_fetch_r4_row_count"] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_r4_ready_for_review_row_count"
    ] == 17
    assert summary["public_benchmark_statistical_support_coordinate_fetch_r4_blocked_row_count"] == 0
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_r4_fetch_required_row_count"
    ] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_r4_metric_materialization_blocked_row_count"
    ] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_r4_planned_metric_source_payload_count"
    ] == 51
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_r4_authorized_for_external_download"
    ] is False
    assert summary["public_benchmark_statistical_support_coordinate_fetch_r4_download_executed"] is False
    assert summary["public_benchmark_statistical_support_coordinate_fetch_r4_external_state_mutated"] is False
    assert summary["public_benchmark_statistical_support_coordinate_fetch_r4_approval_token_required"] == (
        "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD"
    )
    assert summary["public_benchmark_statistical_support_coordinate_fetch_operator_receipt_present"] is True
    assert summary["public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready"] is False
    assert summary["public_benchmark_statistical_support_coordinate_fetch_operator_receipt_status"] == (
        "blocked_refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt"
    )
    assert summary["public_benchmark_statistical_support_coordinate_fetch_operator_receipt_csv_present"] is True
    assert summary["public_benchmark_statistical_support_coordinate_fetch_operator_receipt_row_count"] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_required_r4_review_count"
    ] == 17
    assert (
        summary[
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_required"
        ]
        is True
    )
    assert (
        summary[
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_verified_count"
        ]
        == 17
    )
    assert (
        summary[
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_mismatch_count"
        ]
        == 0
    )
    assert (
        summary[
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_operator_review_surface_ready_count"
        ]
        == 17
    )
    assert (
        summary[
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_operator_review_surface_blocked_count"
        ]
        == 0
    )
    assert (
        summary[
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_source_url_present_count"
        ]
        == 17
    )
    assert (
        summary[
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_staging_destination_path_present_count"
        ]
        == 17
    )
    assert (
        summary[
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_execute_command_present_count"
        ]
        == 17
    )
    assert (
        summary[
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_receipt_manual_field_pending_count"
        ]
        == 187
    )
    assert summary["public_benchmark_statistical_support_coordinate_fetch_operator_receipt_pass_row_count"] == 0
    assert summary["public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocked_row_count"] == 17
    assert summary["public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approved_fetch_count"] == 0
    assert (
        summary[
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_authorized_for_external_download"
        ]
        is False
    )
    assert summary["public_benchmark_statistical_support_coordinate_fetch_operator_receipt_download_executed"] is False
    assert (
        summary[
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_canonical_intake_promotion_allowed"
        ]
        is False
    )
    assert (
        summary["public_benchmark_statistical_support_coordinate_fetch_operator_receipt_claim_promotion_allowed"]
        is False
    )
    assert (
        summary["public_benchmark_statistical_support_coordinate_fetch_operator_receipt_external_state_mutated"]
        is False
    )
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_review_id"
    ] == "r9_statistical_support_coordinate_fetch_001"
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_target_id"
    ] == "4ivc"
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_pose_id"
    ] == "4ivc_20"
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_most_common_row_blocker"
    ] == "operator_placeholders_unfilled"
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approval_token_required"
    ] == "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD"
    assert summary["public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocker_count"] == 1
    assert summary["public_benchmark_bootstrap_driver_operator_chain_rollup_present"] is True
    assert summary["public_benchmark_bootstrap_driver_operator_chain_status"] == (
        "blocked_refine_tier_public_benchmark_bootstrap_driver_operator_chain_rollup"
    )
    assert summary["public_benchmark_bootstrap_driver_operator_chain_surface_ready"] is True
    assert summary["public_benchmark_bootstrap_driver_operator_chain_closure_ready"] is False
    assert summary["public_benchmark_bootstrap_driver_operator_chain_stage_count"] == 5
    assert summary["public_benchmark_bootstrap_driver_operator_chain_stage_artifact_present_count"] == 5
    assert summary["public_benchmark_bootstrap_driver_operator_chain_stage_surface_ready_count"] == 4
    assert (
        summary[
            "public_benchmark_bootstrap_driver_operator_chain_source_staging_operator_manual_pending_field_count"
        ]
        == 66
    )
    assert summary["public_benchmark_bootstrap_driver_operator_chain_machine_supported_pending_field_count"] == 36
    assert summary["public_benchmark_bootstrap_driver_operator_chain_machine_supported_prefilled_field_count"] == 36
    assert summary["public_benchmark_bootstrap_driver_operator_chain_operator_only_pending_field_count"] == 30
    assert summary["public_benchmark_bootstrap_driver_operator_chain_machine_gap_pending_field_count"] == 0
    assert summary["public_benchmark_bootstrap_driver_operator_chain_attestation_row_count"] == 6
    assert summary["public_benchmark_bootstrap_driver_operator_chain_attestation_blocked_row_count"] == 6
    assert summary["public_benchmark_bootstrap_driver_operator_chain_attestation_merge_ready"] is False
    assert summary["public_benchmark_bootstrap_driver_operator_chain_merge_preview_pass_row_count"] == 0
    assert summary["public_benchmark_bootstrap_driver_operator_chain_merge_preview_blocked_row_count"] == 6
    assert summary["public_benchmark_bootstrap_driver_operator_chain_prefill_row_fingerprint_verified_count"] == 6
    assert summary["public_benchmark_bootstrap_driver_operator_chain_prefill_row_fingerprint_mismatch_count"] == 0
    assert summary["public_benchmark_bootstrap_driver_operator_chain_merged_candidate_row_count"] == 0
    assert summary["public_benchmark_bootstrap_driver_operator_chain_final_blocker_stage_id"] == (
        "attestation_merge_preview"
    )
    assert summary["public_benchmark_bootstrap_driver_operator_chain_final_blocker"] == (
        "operator_only_placeholders_unfilled"
    )
    assert summary["public_benchmark_bootstrap_driver_operator_chain_payload_write_allowed"] is False
    assert summary["public_benchmark_bootstrap_driver_operator_chain_canonical_receipt_write_allowed"] is False
    assert summary["public_benchmark_bootstrap_driver_operator_chain_canonical_intake_promotion_allowed"] is False
    assert summary["public_benchmark_bootstrap_driver_operator_chain_claim_promotion_allowed"] is False
    assert summary["public_benchmark_bootstrap_driver_operator_chain_blocker_count"] == 3
    assert summary["public_benchmark_bootstrap_driver_operator_chain_blockers"] == [
        "operator_attestation_rows_blocked",
        "attestation_merge_rows_blocked",
        "operator_chain_closure_not_ready",
    ]
    assert summary["blockers"] == [
        "gpcr_broad_claim_review_not_approved",
        "gpcr_scorer_router_promotion_not_approved",
        "openmm_schrodinger_public_benchmark_not_promoted_to_canonical_intake",
        "openmm_schrodinger_public_benchmark_statistical_support_not_claim_grade",
        "openmm_schrodinger_public_benchmark_statistical_support_metric_sources_not_materialized",
        "openmm_schrodinger_public_benchmark_statistical_support_coordinate_fetch_r4_approval_required",
        "openmm_schrodinger_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_not_ready",
        "openmm_schrodinger_public_benchmark_statistical_support_metric_source_payload_operator_receipt_not_ready",
        "openmm_schrodinger_public_benchmark_bootstrap_driver_operator_chain_not_closed",
        "engine_refinement_claim_evidence_receipt_not_ready",
    ]
    assert "current 8-row materialized R9 metric evidence" in summary["next_required_step"]
    assert "coordinate-fetch R4 approval" in summary["next_required_step"]
    assert "coordinate operator receipt" in summary["next_required_step"]
    assert "metric payload receipt" in summary["next_required_step"]
    assert "bootstrap-driver operator chain closure" in summary["next_required_step"]
    assert "coordinate validation/materialization" in summary["next_required_step"]


def test_science_accuracy_frontier_surfaces_candidate_fill_quality_gap(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path, ready=False, materialized_candidate_ready=True)
    _write(
        paths["public_benchmark_statistical_support_metric_source_candidate_fill_json"],
        {
            "status": "refine_tier_public_benchmark_statistical_support_metric_candidates_ready",
            "candidate_row_count": 51,
            "candidate_pass_row_count": 51,
            "candidate_blocked_row_count": 0,
            "metric_value_candidate_count": 51,
            "candidate_pair_count": 17,
            "candidate_pair_pass_count": 17,
            "combined_pair_count": 25,
            "combined_fit_pair_count": 17,
            "combined_holdout_pair_count": 8,
            "combined_free_energy_spearman": 0.5315384615384615,
            "free_energy_spearman_bootstrap_p05": 0.23053846153846155,
            "free_energy_spearman_bootstrap_p50": 0.5492307692307692,
            "free_energy_spearman_bootstrap_p95": 0.7739230769230769,
            "claim_grade_public_benchmark_statistical_support_ready": False,
            "claim_grade_public_benchmark_statistical_support_blocker_count": 1,
            "expected_metric_source_artifact_touched_count": 0,
            "payload_write_allowed": False,
            "operator_receipt_approval_filled": False,
            "canonical_intake_promotion_allowed": False,
            "claim_promotion_allowed": False,
        },
    )

    payload = mod.build_science_accuracy_frontier(**paths)
    summary = payload["summary"]

    assert summary["public_benchmark_statistical_support_metric_source_candidate_fill_ready"] is True
    assert summary["public_benchmark_statistical_support_metric_source_candidate_fill_candidate_pass_row_count"] == 51
    assert summary["public_benchmark_statistical_support_metric_source_candidate_fill_combined_pair_count"] == 25
    assert summary["public_benchmark_statistical_support_metric_source_candidate_fill_combined_holdout_pair_count"] == 8
    assert summary["public_benchmark_statistical_support_metric_source_candidate_fill_spearman_bootstrap_p05"] == (
        0.23053846153846155
    )
    assert (
        summary[
            "public_benchmark_statistical_support_metric_source_candidate_fill_claim_grade_statistical_support_ready"
        ]
        is False
    )
    assert (
        summary[
            "public_benchmark_statistical_support_metric_source_candidate_fill_expected_metric_source_artifact_touched_count"
        ]
        == 0
    )
    assert summary["public_benchmark_statistical_support_metric_source_candidate_fill_payload_write_allowed"] is False
    assert summary["public_benchmark_residual_metric_payload_priority_packet_present"] is True
    assert summary["public_benchmark_residual_metric_payload_priority_packet_ready"] is True
    assert (
        summary[
            "public_benchmark_residual_metric_payload_priority_packet_operator_receipt_missing_payload_count"
        ]
        == 9
    )
    assert (
        summary[
            "public_benchmark_residual_metric_payload_priority_packet_existing_metric_source_artifact_present_without_receipt_count"
        ]
        == 9
    )
    assert summary["public_benchmark_residual_metric_payload_priority_packet_first_missing_receipt_target_id"] == "2j7h"
    assert summary["public_benchmark_seeded_metric_payload_receipt_backfill_packet_present"] is True
    assert summary["public_benchmark_seeded_metric_payload_receipt_backfill_packet_ready"] is True
    assert summary["public_benchmark_seeded_metric_payload_receipt_backfill_packet_seeded_backfill_row_count"] == 9
    assert (
        summary["public_benchmark_seeded_metric_payload_receipt_backfill_packet_seeded_backfill_targets"]
        == "1syi;2j7h;4e5w"
    )
    assert (
        summary["public_benchmark_seeded_metric_payload_receipt_backfill_packet_operator_receipt_backfill_ready"]
        is False
    )
    assert "25-pair R9 metric candidate preview" in summary["next_required_step"]
    assert "below the claim-grade 0.5 floor" in summary["next_required_step"]
    assert "seeded receipt gap=9 missing rows/9 backfill rows" in summary["next_required_step"]


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
            "--public-benchmark-statistical-support-coordinate-intake-json",
            str(paths["public_benchmark_statistical_support_coordinate_intake_json"]),
            "--public-benchmark-statistical-support-metric-source-templates-json",
            str(paths["public_benchmark_statistical_support_metric_source_templates_json"]),
            "--public-benchmark-statistical-support-metric-source-payload-operator-receipt-json",
            str(paths["public_benchmark_statistical_support_metric_source_payload_operator_receipt_json"]),
            "--public-benchmark-statistical-support-metric-source-candidate-fill-json",
            str(paths["public_benchmark_statistical_support_metric_source_candidate_fill_json"]),
            "--public-benchmark-residual-metric-payload-priority-packet-json",
            str(paths["public_benchmark_residual_metric_payload_priority_packet_json"]),
            "--public-benchmark-seeded-metric-payload-receipt-backfill-packet-json",
            str(paths["public_benchmark_seeded_metric_payload_receipt_backfill_packet_json"]),
            "--public-benchmark-statistical-support-coordinate-fetch-r4-preflight-json",
            str(paths["public_benchmark_statistical_support_coordinate_fetch_r4_preflight_json"]),
            "--public-benchmark-statistical-support-coordinate-fetch-operator-receipt-json",
            str(paths["public_benchmark_statistical_support_coordinate_fetch_operator_receipt_json"]),
            "--public-benchmark-claim-grade-gap-audit-json",
            str(paths["public_benchmark_claim_grade_gap_audit_json"]),
            "--public-benchmark-bootstrap-driver-operator-chain-rollup-json",
            str(paths["public_benchmark_bootstrap_driver_operator_chain_rollup_json"]),
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
