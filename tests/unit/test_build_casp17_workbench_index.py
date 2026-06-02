import json
from pathlib import Path

from tools import build_casp17_workbench_index as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_casp17_workbench_index_links_target_and_benchmark_state(tmp_path):
    target_json = tmp_path / "target_folders.json"
    target_object_folder_audit_json = tmp_path / "target_object_folder_audit.json"
    target_object_viewer_smoke_json = tmp_path / "target_object_viewer_smoke.json"
    target_object_model_review_json = tmp_path / "target_object_model_review.json"
    protein_object_library_json = tmp_path / "protein_object_library.json"
    protein_object_library_completion_audit_json = tmp_path / "protein_object_library_completion_audit.json"
    protein_object_library_navigation_catalog_json = tmp_path / "protein_object_library_navigation_catalog.json"
    molecular_object_atlas_json = tmp_path / "molecular_object_atlas.json"
    molecular_object_atlas_completion_audit_json = tmp_path / "molecular_object_atlas_completion_audit.json"
    molecular_object_metric_handoff_json = tmp_path / "molecular_object_metric_handoff.json"
    molecular_object_metric_handoff_completion_audit_json = (
        tmp_path / "molecular_object_metric_handoff_completion_audit.json"
    )
    raw_ranked_model_quarantine_json = tmp_path / "raw_ranked_model_quarantine.json"
    current_submission_gate_json = tmp_path / "current_submission_gate.json"
    current_sidechain_repack_json = tmp_path / "current_sidechain_repack.json"
    current_submission_package_preflight_json = tmp_path / "current_submission_package_preflight.json"
    current_submission_deadline_guard_json = tmp_path / "current_submission_deadline_guard.json"
    current_upload_queue_json = tmp_path / "current_upload_queue.json"
    current_upload_review_packet_json = tmp_path / "current_upload_review_packet.json"
    current_prospective_strict_blind_escrow_json = (
        tmp_path / "current_prospective_strict_blind_escrow.json"
    )
    closure_json = tmp_path / "closure.json"
    goal_scorecard_json = tmp_path / "goal_scorecard.json"
    historical_winner_normalized_bands_json = tmp_path / "historical_winner_normalized_bands.json"
    historical_winner_normalized_unlock_plan_json = (
        tmp_path / "historical_winner_normalized_unlock_plan.json"
    )
    win_tier_metric_surface_contract_json = tmp_path / "win_tier_metric_surface_contract.json"
    win_tier_critical_path_board_json = tmp_path / "win_tier_critical_path_board.json"
    organic_ligand_slot_candidate_packet_json = tmp_path / "organic_ligand_slot_candidate_packet.json"
    organic_ligand_slot_promotion_action_board_json = (
        tmp_path / "organic_ligand_slot_promotion_action_board.json"
    )
    active_scope_decision_json = tmp_path / "active_scope_decision.json"
    organizer_notice_json = tmp_path / "organizer_notice.json"
    massivefold_external_pool_intake_json = tmp_path / "massivefold_external_pool_intake.json"
    rna_hybrid_massivefold_priority_queue_json = tmp_path / "rna_hybrid_massivefold_priority_queue.json"
    protein_complex_massivefold_priority_queue_json = (
        tmp_path / "protein_complex_massivefold_priority_queue.json"
    )
    massivefold_acquisition_verification_board_json = (
        tmp_path / "massivefold_acquisition_verification_board.json"
    )
    protein_complex_massivefold_acquisition_verification_board_json = (
        tmp_path / "protein_complex_massivefold_acquisition_verification_board.json"
    )
    massivefold_model_pool_index_json = tmp_path / "massivefold_model_pool_index.json"
    massivefold_representative_viewer_packet_json = (
        tmp_path / "massivefold_representative_viewer_packet.json"
    )
    massivefold_representative_rerank_packet_json = (
        tmp_path / "massivefold_representative_rerank_packet.json"
    )
    massivefold_rna_model_selection_coverage_json = (
        tmp_path / "massivefold_rna_model_selection_coverage.json"
    )
    massivefold_rna_model_selection_input_packet_json = (
        tmp_path / "massivefold_rna_model_selection_input_packet.json"
    )
    massivefold_rna_self_assessment_packet_json = (
        tmp_path / "massivefold_rna_self_assessment_packet.json"
    )
    protein_complex_massivefold_model_selection_coverage_json = (
        tmp_path / "protein_complex_massivefold_model_selection_coverage.json"
    )
    protein_complex_massivefold_self_assessment_packet_json = (
        tmp_path / "protein_complex_massivefold_self_assessment_packet.json"
    )
    massivefold_model1_risk_queue_json = tmp_path / "massivefold_model1_risk_queue.json"
    massivefold_critical_rerank_experiment_json = (
        tmp_path / "massivefold_critical_rerank_experiment.json"
    )
    massivefold_critical_rerank_score_ledger_json = (
        tmp_path / "massivefold_critical_rerank_score_ledger.json"
    )
    massivefold_model1_selection_calibration_gate_json = (
        tmp_path / "massivefold_model1_selection_calibration_gate.json"
    )
    massivefold_model1_probe_worklist_json = tmp_path / "massivefold_model1_probe_worklist.json"
    massivefold_model1_probe_outcome_json = tmp_path / "massivefold_model1_probe_outcome.json"
    massivefold_model1_freeze_decision_packet_json = (
        tmp_path / "massivefold_model1_freeze_decision_packet.json"
    )
    massivefold_model_selection_ledger_json = tmp_path / "massivefold_model_selection_ledger.json"
    massivefold_model1_combined_selector_overlay_json = (
        tmp_path / "massivefold_model1_combined_selector_overlay.json"
    )
    massivefold_freeze_ready_review_packet_json = (
        tmp_path / "massivefold_freeze_ready_review_packet.json"
    )
    massivefold_hold_probe_review_packet_json = (
        tmp_path / "massivefold_hold_probe_review_packet.json"
    )
    massivefold_probe_required_targeted_probe_packet_json = (
        tmp_path / "massivefold_probe_required_targeted_probe_packet.json"
    )
    massivefold_post_probe_selector_decision_packet_json = (
        tmp_path / "massivefold_post_probe_selector_decision_packet.json"
    )
    massivefold_watch_manual_action_packet_json = (
        tmp_path / "massivefold_watch_manual_action_packet.json"
    )
    massivefold_freeze_candidate_format_preflight_json = (
        tmp_path / "massivefold_freeze_candidate_format_preflight.json"
    )
    massivefold_freeze_candidate_escrow_json = tmp_path / "massivefold_freeze_candidate_escrow.json"
    massivefold_freeze_candidate_protein_library_json = (
        tmp_path / "massivefold_freeze_candidate_protein_library.json"
    )
    capri_round65_readiness_json = tmp_path / "capri_round65_readiness.json"
    capri_round65_format_preflight_json = tmp_path / "capri_round65_format_preflight.json"
    scaffold_json = tmp_path / "scaffold.json"
    inventory_json = tmp_path / "inventory.json"
    dashboard_json = tmp_path / "dashboard.json"
    historical_identity_seed_inventory_json = tmp_path / "historical_identity_seed_inventory.json"
    historical_identity_seed_clearance_json = tmp_path / "historical_identity_seed_clearance.json"
    historical_identity_seed_clearance_action_bundle_json = (
        tmp_path / "historical_identity_seed_clearance_action_bundle.json"
    )
    historical_identity_seed_clearance_field_board_json = (
        tmp_path / "historical_identity_seed_clearance_field_board.json"
    )
    historical_seed_no_leak_provenance_dossiers_json = (
        tmp_path / "historical_seed_no_leak_provenance_dossiers.json"
    )
    historical_seed_no_leak_gap_repair_plan_json = tmp_path / "historical_seed_no_leak_gap_repair_plan.json"
    historical_seed_current_target_prefill_json = tmp_path / "historical_seed_current_target_prefill.json"
    historical_seed_native_authority_audit_json = tmp_path / "historical_seed_native_authority_audit.json"
    historical_seed_native_replacement_candidates_json = (
        tmp_path / "historical_seed_native_replacement_candidates.json"
    )
    historical_seed_complex_source_authority_candidates_json = (
        tmp_path / "historical_seed_complex_source_authority_candidates.json"
    )
    historical_seed_chronology_candidate_board_json = tmp_path / "historical_seed_chronology_candidate_board.json"
    historical_seed_authoritative_chronology_audit_json = (
        tmp_path / "historical_seed_authoritative_chronology_audit.json"
    )
    historical_seed_lane_decision_packet_json = tmp_path / "historical_seed_lane_decision_packet.json"
    historical_seed_strict_blind_replacement_queue_json = (
        tmp_path / "historical_seed_strict_blind_replacement_queue.json"
    )
    historical_seed_strict_blind_replacement_intake_json = (
        tmp_path / "historical_seed_strict_blind_replacement_intake.json"
    )
    historical_seed_strict_blind_replacement_evidence_dropzones_json = (
        tmp_path / "historical_seed_strict_blind_replacement_evidence_dropzones.json"
    )
    historical_seed_strict_blind_replacement_evidence_action_board_json = (
        tmp_path / "historical_seed_strict_blind_replacement_evidence_action_board.json"
    )
    historical_seed_strict_blind_replacement_evidence_quality_audit_json = (
        tmp_path / "historical_seed_strict_blind_replacement_evidence_quality_audit.json"
    )
    historical_seed_strict_blind_replacement_evidence_import_gate_json = (
        tmp_path / "historical_seed_strict_blind_replacement_evidence_import_gate.json"
    )
    historical_seed_strict_blind_replacement_operator_value_gate_json = (
        tmp_path / "historical_seed_strict_blind_replacement_operator_value_gate.json"
    )
    historical_seed_strict_blind_replacement_operator_action_board_json = (
        tmp_path / "historical_seed_strict_blind_replacement_operator_action_board.json"
    )
    historical_seed_strict_blind_replacement_promotion_gate_json = (
        tmp_path / "historical_seed_strict_blind_replacement_promotion_gate.json"
    )
    historical_seed_strict_blind_replacement_cycle_json = (
        tmp_path / "historical_seed_strict_blind_replacement_cycle.json"
    )
    historical_seed_strict_blind_replacement_first_slot_kit_json = (
        tmp_path / "historical_seed_strict_blind_replacement_first_slot_kit.json"
    )
    historical_seed_strict_blind_replacement_first_slot_local_candidate_board_json = (
        tmp_path / "historical_seed_strict_blind_replacement_first_slot_local_candidate_board.json"
    )
    historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_json = (
        tmp_path / "historical_seed_strict_blind_replacement_first_slot_candidate_repair_board.json"
    )
    historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_json = (
        tmp_path / "historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board.json"
    )
    historical_seed_strict_blind_replacement_first_slot_source_route_board_json = (
        tmp_path / "historical_seed_strict_blind_replacement_first_slot_source_route_board.json"
    )
    historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_json = (
        tmp_path / "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates.json"
    )
    historical_seed_official_archive_baseline_lane_json = (
        tmp_path / "historical_seed_official_archive_baseline_lane.json"
    )
    official_archive_first_baseline_acquisition_audit_json = (
        tmp_path / "official_archive_first_baseline_acquisition_audit.json"
    )
    official_archive_first_baseline_model_pool_json = (
        tmp_path / "official_archive_first_baseline_model_pool.json"
    )
    official_archive_first_baseline_score_ledger_json = (
        tmp_path / "official_archive_first_baseline_score_ledger.json"
    )
    official_archive_first_baseline_replay_comparison_json = (
        tmp_path / "official_archive_first_baseline_replay_comparison.json"
    )
    official_archive_first_baseline_model1_gap_triage_json = (
        tmp_path / "official_archive_first_baseline_model1_gap_triage.json"
    )
    official_archive_first_baseline_model1_gap_viewer_packet_json = (
        tmp_path / "official_archive_first_baseline_model1_gap_viewer_packet.json"
    )
    official_archive_first_baseline_model1_gap_feature_probe_json = (
        tmp_path / "official_archive_first_baseline_model1_gap_feature_probe.json"
    )
    official_archive_first_baseline_model1_gap_consensus_probe_json = (
        tmp_path / "official_archive_first_baseline_model1_gap_consensus_probe.json"
    )
    official_archive_first_baseline_model1_gap_combined_selector_ledger_json = (
        tmp_path / "official_archive_first_baseline_model1_gap_combined_selector_ledger.json"
    )
    strict_blind_first_slot_source_bridge_json = tmp_path / "strict_blind_first_slot_source_bridge.json"
    strict_blind_internal_prediction_source_audit_json = (
        tmp_path / "strict_blind_internal_prediction_source_audit.json"
    )
    strict_blind_internal_candidate_filesystem_sweep_json = (
        tmp_path / "strict_blind_internal_candidate_filesystem_sweep.json"
    )
    strict_blind_unknown_candidate_triage_json = (
        tmp_path / "strict_blind_unknown_candidate_triage.json"
    )
    strict_blind_internal_like_source_review_json = (
        tmp_path / "strict_blind_internal_like_source_review.json"
    )
    strict_blind_internal_prediction_source_gate_json = (
        tmp_path / "strict_blind_internal_prediction_source_gate.json"
    )
    strict_blind_source_gate_field_board_json = tmp_path / "strict_blind_source_gate_field_board.json"
    strict_blind_source_gate_operator_packet_json = (
        tmp_path / "strict_blind_source_gate_operator_packet.json"
    )
    strict_blind_source_gate_source_request_packet_json = (
        tmp_path / "strict_blind_source_gate_source_request_packet.json"
    )
    strict_blind_source_request_resolution_board_json = (
        tmp_path / "strict_blind_source_request_resolution_board.json"
    )
    strict_blind_source_request_fulfillment_gate_json = (
        tmp_path / "strict_blind_source_request_fulfillment_gate.json"
    )
    strict_blind_source_request_operator_fill_worklist_json = (
        tmp_path / "strict_blind_source_request_operator_fill_worklist.json"
    )
    strict_blind_source_request_operator_sync_plan_json = (
        tmp_path / "strict_blind_source_request_operator_sync_plan.json"
    )
    strict_blind_source_request_closure_board_json = (
        tmp_path / "strict_blind_source_request_closure_board.json"
    )
    strict_blind_first_source_request_pickup_json = (
        tmp_path / "strict_blind_first_source_request_pickup.json"
    )
    strict_blind_first_unlock_handoff_json = tmp_path / "strict_blind_first_unlock_handoff.json"
    strict_blind_first_unlock_evidence_packet_json = (
        tmp_path / "strict_blind_first_unlock_evidence_packet.json"
    )
    strict_blind_first_unlock_evidence_review_gate_json = (
        tmp_path / "strict_blind_first_unlock_evidence_review_gate.json"
    )
    strict_blind_first_slot_source_gate_blocker_ledger_json = (
        tmp_path / "strict_blind_first_slot_source_gate_blocker_ledger.json"
    )
    strict_blind_first_unlock_evidence_sync_plan_json = (
        tmp_path / "strict_blind_first_unlock_evidence_sync_plan.json"
    )
    strict_blind_internal_prediction_source_apply_plan_json = (
        tmp_path / "strict_blind_internal_prediction_source_apply_plan.json"
    )
    strict_blind_first_slot_closure_kit_json = tmp_path / "strict_blind_first_slot_closure_kit.json"
    strict_blind_batch_closure_runway_json = tmp_path / "strict_blind_batch_closure_runway.json"
    historical_seed_ablation_candidate_manifests_json = (
        tmp_path / "historical_seed_ablation_candidate_manifests.json"
    )
    historical_seed_ablation_gap_repair_plan_json = tmp_path / "historical_seed_ablation_gap_repair_plan.json"
    historical_seed_top5_candidate_pools_json = tmp_path / "historical_seed_top5_candidate_pools.json"
    historical_seed_internal_score_candidates_json = (
        tmp_path / "historical_seed_internal_score_candidates.json"
    )
    historical_seed_native_oracle_metric_candidates_json = (
        tmp_path / "historical_seed_native_oracle_metric_candidates.json"
    )
    historical_seed_calibration_candidate_ledgers_json = (
        tmp_path / "historical_seed_calibration_candidate_ledgers.json"
    )
    historical_seed_calibration_field_candidates_json = (
        tmp_path / "historical_seed_calibration_field_candidates.json"
    )
    historical_seed_clearance_fill_candidate_packet_json = (
        tmp_path / "historical_seed_clearance_fill_candidate_packet.json"
    )
    historical_seed_clearance_execution_board_json = (
        tmp_path / "historical_seed_clearance_execution_board.json"
    )
    historical_seed_first_clearance_operator_kit_json = (
        tmp_path / "historical_seed_first_clearance_operator_kit.json"
    )
    historical_seed_first_clearance_no_leak_gate_json = (
        tmp_path / "historical_seed_first_clearance_no_leak_gate.json"
    )
    historical_seed_first_clearance_no_leak_evidence_packet_json = (
        tmp_path / "historical_seed_first_clearance_no_leak_evidence_packet.json"
    )
    historical_seed_first_clearance_no_leak_evidence_review_gate_json = (
        tmp_path / "historical_seed_first_clearance_no_leak_evidence_review_gate.json"
    )
    historical_seed_first_clearance_no_leak_evidence_sync_plan_json = (
        tmp_path / "historical_seed_first_clearance_no_leak_evidence_sync_plan.json"
    )
    historical_seed_first_clearance_closure_board_json = (
        tmp_path / "historical_seed_first_clearance_closure_board.json"
    )
    historical_seed_clearance_to_identity_intake_sync_json = (
        tmp_path / "historical_seed_clearance_to_identity_intake_sync.json"
    )
    sidechain_native_benchmark_json = tmp_path / "sidechain_native_benchmark.json"
    competitive_batch_json = tmp_path / "competitive_batch.json"
    competitive_row_fill_status_json = tmp_path / "competitive_row_fill_status.json"
    competitive_row_fill_worklist_json = tmp_path / "competitive_row_fill_worklist.json"
    competitive_evidence_dropzone_json = tmp_path / "competitive_evidence_dropzone.json"
    competitive_evidence_import_json = tmp_path / "competitive_evidence_import.json"
    competitive_evidence_round_json = tmp_path / "competitive_evidence_round.json"
    competitive_unlock_priority_json = tmp_path / "competitive_unlock_priority.json"
    competitive_identity_unlock_json = tmp_path / "competitive_identity_unlock.json"
    competitive_identity_round_json = tmp_path / "competitive_identity_round.json"
    competitive_identity_intake_json = tmp_path / "competitive_identity_intake.json"
    competitive_identity_sync_json = tmp_path / "competitive_identity_sync.json"
    competitive_identity_candidate_json = tmp_path / "competitive_identity_candidate.json"
    competitive_identity_source_repair_json = tmp_path / "competitive_identity_source_repair.json"
    competitive_floor_unblock_map_json = tmp_path / "competitive_floor_unblock_map.json"
    competitive_target_identity_discovery_json = tmp_path / "competitive_target_identity_discovery.json"
    competitive_target_identity_clearance_json = tmp_path / "competitive_target_identity_clearance.json"
    competitive_target_identity_clearance_workorder_json = tmp_path / "competitive_target_identity_clearance_workorder.json"
    competitive_target_identity_clearance_operator_intake_json = (
        tmp_path / "competitive_target_identity_clearance_operator_intake.json"
    )
    competitive_target_identity_clearance_native_candidate_json = (
        tmp_path / "competitive_target_identity_clearance_native_candidate.json"
    )
    competitive_target_identity_clearance_adjudication_json = (
        tmp_path / "competitive_target_identity_clearance_adjudication.json"
    )
    competitive_target_identity_clearance_replacement_queue_json = (
        tmp_path / "competitive_target_identity_clearance_replacement_queue.json"
    )
    competitive_target_identity_clearance_replacement_source_repair_json = (
        tmp_path / "competitive_target_identity_clearance_replacement_source_repair.json"
    )
    competitive_target_identity_clearance_replacement_scorecard_json = (
        tmp_path / "competitive_target_identity_clearance_replacement_scorecard.json"
    )
    competitive_target_identity_clearance_replacement_workorder_json = (
        tmp_path / "competitive_target_identity_clearance_replacement_workorder.json"
    )
    competitive_target_identity_clearance_replacement_workorder_audit_json = (
        tmp_path / "competitive_target_identity_clearance_replacement_workorder_audit.json"
    )
    competitive_target_identity_clearance_replacement_pickup_json = (
        tmp_path / "competitive_target_identity_clearance_replacement_pickup.json"
    )
    competitive_target_identity_clearance_replacement_duplicate_resolution_json = (
        tmp_path / "competitive_target_identity_clearance_replacement_duplicate_resolution.json"
    )
    competitive_target_identity_clearance_replacement_decision_bundle_json = (
        tmp_path / "competitive_target_identity_clearance_replacement_decision_bundle.json"
    )
    competitive_target_identity_clearance_replacement_decision_preflight_json = (
        tmp_path / "competitive_target_identity_clearance_replacement_decision_preflight.json"
    )
    competitive_target_identity_clearance_manifest_sync_json = (
        tmp_path / "competitive_target_identity_clearance_manifest_sync.json"
    )
    competitive_target_identity_clearance_workorder_audit_json = (
        tmp_path / "competitive_target_identity_clearance_workorder_audit.json"
    )
    competitive_target_identity_metric_runway_json = (
        tmp_path / "competitive_target_identity_metric_runway.json"
    )
    competitive_floor_native_dropzone_registry_json = (
        tmp_path / "competitive_floor_native_dropzone_registry.json"
    )
    competitive_floor_native_provenance_operator_packet_json = (
        tmp_path / "competitive_floor_native_provenance_operator_packet.json"
    )
    competitive_floor_native_provenance_operator_packet_completion_audit_json = (
        tmp_path / "competitive_floor_native_provenance_operator_packet_completion_audit.json"
    )
    competitive_floor_native_provenance_metric_unlock_bridge_json = (
        tmp_path / "competitive_floor_native_provenance_metric_unlock_bridge.json"
    )
    competitive_floor_first_native_provenance_unlock_kit_json = (
        tmp_path / "competitive_floor_first_native_provenance_unlock_kit.json"
    )
    competitive_floor_batch_native_provenance_unlock_kit_json = (
        tmp_path / "competitive_floor_batch_native_provenance_unlock_kit.json"
    )
    competitive_floor_batch_native_provenance_unlock_kit_completion_audit_json = (
        tmp_path / "competitive_floor_batch_native_provenance_unlock_kit_completion_audit.json"
    )
    competitive_floor_batch_native_provenance_value_gate_json = (
        tmp_path / "competitive_floor_batch_native_provenance_value_gate.json"
    )
    competitive_floor_batch_native_provenance_value_action_board_json = (
        tmp_path / "competitive_floor_batch_native_provenance_value_action_board.json"
    )
    competitive_floor_batch_native_provenance_value_action_board_completion_audit_json = (
        tmp_path / "competitive_floor_batch_native_provenance_value_action_board_completion_audit.json"
    )
    competitive_floor_batch_native_provenance_operator_fill_preflight_json = (
        tmp_path / "competitive_floor_batch_native_provenance_operator_fill_preflight.json"
    )
    competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_json = (
        tmp_path / "competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit.json"
    )
    competitive_target_identity_clearance_action_board_json = (
        tmp_path / "competitive_target_identity_clearance_action_board.json"
    )
    competitive_target_identity_clearance_action_bundle_json = (
        tmp_path / "competitive_target_identity_clearance_action_bundle.json"
    )
    competitive_target_identity_clearance_promotion_json = (
        tmp_path / "competitive_target_identity_clearance_promotion.json"
    )
    competitive_target_identity_clearance_intake_staging_json = (
        tmp_path / "competitive_target_identity_clearance_intake_staging.json"
    )
    competitive_target_identity_clearance_candidate_intake_sync_json = (
        tmp_path / "competitive_target_identity_clearance_candidate_intake_sync.json"
    )
    competitive_target_identity_clearance_cycle_json = tmp_path / "competitive_target_identity_clearance_cycle.json"
    competitive_identity_cycle_json = tmp_path / "competitive_identity_cycle.json"
    competitive_file_source_plan_json = tmp_path / "competitive_file_source_plan.json"
    competitive_value_entry_plan_json = tmp_path / "competitive_value_entry_plan.json"
    competitive_execution_board_json = tmp_path / "competitive_execution_board.json"
    competitive_readiness_gate_json = tmp_path / "competitive_readiness_gate.json"
    competitive_value_ledger_json = tmp_path / "competitive_value_ledger.json"
    competitive_evidence_intake_json = tmp_path / "competitive_evidence_intake.json"
    competitive_patch_gate_json = tmp_path / "competitive_patch_gate.json"
    competitive_apply_plan_json = tmp_path / "competitive_apply_plan.json"
    competitive_operator_template_json = tmp_path / "competitive_operator_template.json"
    competitive_operator_preflight_json = tmp_path / "competitive_operator_preflight.json"
    bundle_json = tmp_path / "bundle.json"

    _write_json(
        target_json,
        {
            "summary": {
                "packet_type": "casp17_target_model_folders",
                "ready_count": 2,
                "blocked_count": 0,
                "target_count": 2,
                "total_object_count": 4,
                "total_object_projection_files": 4,
                "total_object_viewer_files": 4,
                "object_catalog_md": "casp17/casp17_target_object_models_current.md",
            },
            "rows": [
                {
                    "target_id": "T0001",
                    "folder_status": "ready",
                    "protein_name": "Example A",
                    "folder_path": "casp17/targets_current/T0001_Example_A",
                },
                {
                    "target_id": "H0002",
                    "folder_status": "ready",
                    "protein_name": "Example B",
                    "folder_path": "casp17/targets_current/H0002_Example_B",
                },
            ],
        },
    )
    _write_json(
        target_object_folder_audit_json,
        {
            "summary": {
                "folder_audit_status": "pass",
                "object_row_count": 4,
                "pass_count": 4,
                "blocked_count": 0,
                "chain_isolation_pass_count": 4,
                "protein_atom_pass_count": 4,
                "coordinate_valid_pass_count": 4,
                "total_protein_atom_count": 4,
            }
        },
    )
    _write_json(
        target_object_viewer_smoke_json,
        {
            "summary": {
                "smoke_status": "pass",
                "object_row_count": 4,
                "pass_count": 4,
                "blocked_count": 0,
            }
        },
    )
    _write_json(
        target_object_model_review_json,
        {
            "summary": {
                "object_model_review_status": "pass",
                "object_count": 4,
                "pass_count": 4,
                "blocked_count": 0,
                "review_md_count": 4,
                "viewer_local_pass_count": 4,
                "protein_atom_count": 4,
                "ca_atom_count": 4,
                "residue_count": 4,
                "min_radius_of_gyration": 1.2,
                "max_radius_of_gyration": 9.4,
                "gallery_status": "pass",
                "gallery_html_path": "casp17/casp17_target_object_model_review_gallery_current.html",
            }
        },
    )
    _write_json(
        protein_object_library_json,
        {
            "summary": {
                "protein_object_library_status": "pass",
                "protein_folder_count": 2,
                "object_folder_count": 4,
                "pass_count": 4,
                "blocked_count": 0,
                "model_pointer_count": 4,
                "projection_pointer_count": 4,
                "viewer_pointer_count": 4,
                "library_dir": "casp17/protein_object_library_current",
            }
        },
    )
    _write_json(
        protein_object_library_completion_audit_json,
        {
            "summary": {
                "completion_audit_status": "pass",
                "protein_folder_count": 2,
                "protein_folder_pass_count": 2,
                "protein_folder_blocked_count": 0,
                "object_folder_count": 4,
                "object_pass_count": 4,
                "object_blocked_count": 0,
                "model_file_present_count": 4,
                "projection_file_present_count": 4,
                "viewer_file_present_count": 4,
                "object_manifest_present_count": 4,
                "protein_manifest_present_count": 2,
                "next_action": "keep protein-name folders green",
            }
        },
    )
    _write_json(
        protein_object_library_navigation_catalog_json,
        {
            "summary": {
                "navigation_catalog_status": "protein_object_library_navigation_catalog_ready",
                "protein_count": 2,
                "protein_pass_count": 2,
                "protein_blocked_count": 0,
                "object_count": 4,
                "object_pass_count": 4,
                "object_blocked_count": 0,
                "protein_readme_link_count": 2,
                "protein_manifest_link_count": 2,
                "largest_protein_key": "H9002_Example_Fab_Complex",
                "largest_object_count": 3,
                "html_catalog_path": "casp17/casp17_protein_object_library_navigation_catalog_current.html",
                "next_action": "use protein-name navigation catalog",
            }
        },
    )
    _write_json(
        molecular_object_atlas_json,
        {
            "summary": {
                "casp17_3d_molecular_object_atlas_status": (
                    "casp17_3d_molecular_object_atlas_ready_review_only"
                ),
                "protein_count": 5,
                "protein_pass_count": 5,
                "protein_blocked_count": 0,
                "object_count": 14,
                "object_pass_count": 14,
                "object_blocked_count": 0,
                "current_object_count": 4,
                "massivefold_freeze_object_count": 10,
                "current_protein_count": 2,
                "massivefold_freeze_protein_count": 4,
                "overlap_protein_count": 1,
                "model_link_count": 14,
                "viewer_link_count": 14,
                "projection_link_count": 14,
                "top5_link_count": 10,
                "escrow_link_count": 10,
                "model_sha256_count": 10,
                "top5_sha256_count": 10,
                "native_accuracy_count": 0,
                "competitive_proof_eligible_count": 0,
                "author_serialized_count": 0,
                "first_protein_key": "H9002_Example_Fab_Complex",
                "first_object_key": "current_chain_A",
                "first_blocked_protein_key": "",
                "html_atlas_path": "casp17/casp17_3d_molecular_object_atlas_current.html",
                "next_action": "inspect every CASP17 3D object by protein name",
            }
        },
    )
    _write_json(
        molecular_object_atlas_completion_audit_json,
        {
            "summary": {
                "atlas_completion_audit_status": (
                    "casp17_3d_molecular_object_atlas_completion_audit_pass"
                ),
                "protein_count": 5,
                "protein_folder_present_count": 5,
                "protein_readme_present_count": 5,
                "protein_manifest_present_count": 5,
                "object_count": 14,
                "object_pass_count": 14,
                "object_blocked_count": 0,
                "current_object_count": 4,
                "massivefold_freeze_object_count": 10,
                "atlas_object_folder_present_count": 14,
                "atlas_object_readme_present_count": 14,
                "atlas_object_manifest_present_count": 14,
                "model_link_present_count": 14,
                "viewer_link_present_count": 14,
                "projection_link_present_count": 14,
                "top5_link_present_count": 10,
                "escrow_link_present_count": 10,
                "object_coordinate_copy_count": 0,
                "atlas_coordinate_copy_count": 0,
                "competitive_proof_eligible_count": 0,
                "author_serialized_count": 0,
                "first_protein_key": "H9002_Example_Fab_Complex",
                "first_object_key": "current_chain_A",
                "first_blocked_protein_key": "",
                "html_audit_path": (
                    "casp17/casp17_3d_molecular_object_atlas_completion_audit_current.html"
                ),
                "next_action": "use this green audit as the 3D object organization gate",
            }
        },
    )
    _write_json(
        molecular_object_metric_handoff_json,
        {
            "summary": {
                "metric_handoff_status": (
                    "casp17_3d_molecular_object_metric_handoff_ready_review_only_ligand_gap"
                ),
                "protein_count": 5,
                "protein_handoff_folder_expected_count": 5,
                "object_count": 14,
                "object_ready_count": 14,
                "object_blocked_count": 0,
                "object_handoff_folder_expected_count": 14,
                "current_object_count": 4,
                "massivefold_freeze_object_count": 10,
                "metric_requirement_count": 118,
                "required_metric_count": 11,
                "covered_required_metric_count": 9,
                "missing_required_metric_count": 2,
                "missing_required_metric_names": "LDDT-PLI,BiSyRMSD",
                "ligand_metric_gap_count": 2,
                "monomer_object_count": 1,
                "complex_object_count": 12,
                "rna_hybrid_object_count": 1,
                "ligand_object_count": 0,
                "native_accuracy_count": 0,
                "competitive_proof_eligible_count": 0,
                "author_serialized_count": 0,
                "first_protein_key": "H9002_Example_Fab_Complex",
                "first_object_key": "current_chain_A",
                "first_blocked_protein_key": "",
                "html_handoff_path": (
                    "casp17/casp17_3d_molecular_object_metric_handoff_current.html"
                ),
                "next_action": "connect each 3D object to required win-tier metrics",
            }
        },
    )
    _write_json(
        molecular_object_metric_handoff_completion_audit_json,
        {
            "summary": {
                "metric_handoff_completion_audit_status": (
                    "casp17_3d_molecular_object_metric_handoff_completion_audit_pass"
                ),
                "protein_count": 5,
                "protein_folder_present_count": 5,
                "protein_readme_present_count": 5,
                "protein_manifest_present_count": 5,
                "object_count": 14,
                "object_pass_count": 14,
                "object_blocked_count": 0,
                "current_object_count": 4,
                "massivefold_freeze_object_count": 10,
                "handoff_object_folder_present_count": 14,
                "handoff_object_manifest_present_count": 14,
                "metric_requirements_csv_present_count": 14,
                "metric_handoff_md_present_count": 14,
                "metric_requirement_count": 118,
                "metric_requirement_csv_row_count": 118,
                "metric_requirement_csv_mismatch_count": 0,
                "metric_evidence_awaiting_count": 14,
                "model_link_present_count": 14,
                "viewer_link_present_count": 14,
                "projection_link_present_count": 14,
                "top5_link_present_count": 10,
                "escrow_link_present_count": 10,
                "object_coordinate_copy_count": 0,
                "out_dir_coordinate_copy_count": 0,
                "competitive_proof_eligible_count": 0,
                "author_serialized_count": 0,
                "first_protein_key": "H9002_Example_Fab_Complex",
                "first_object_key": "current_chain_A",
                "first_blocked_protein_key": "",
                "html_audit_path": (
                    "casp17/casp17_3d_molecular_object_metric_handoff_completion_audit_current.html"
                ),
                "next_action": "use green metric handoff completion audit",
            }
        },
    )
    _write_json(
        raw_ranked_model_quarantine_json,
        {
            "summary": {
                "raw_ranked_model_quarantine_status": "pass",
                "target_count": 3,
                "raw_ranked_model_count": 15,
                "quarantined_count": 15,
                "linked_object_library_count": 15,
                "author_record_present_count": 15,
                "complete_top5_target_count": 3,
                "total_atom_record_count": 42000,
            }
        },
    )
    _write_json(
        current_submission_gate_json,
        {
            "summary": {
                "submission_go_count": 19,
                "submission_no_go_count": 0,
                "target_row_count": 19,
                "framework_gate_pass": True,
                "registration_action": "user_register_regular_group_now_submission_gated",
                "registration_class_recommendation": "regular_prediction_group",
                "server_registration_ready": False,
                "shape_sanity_status": "pass",
                "shape_sanity_pass_count": 19,
                "shape_sanity_blocked_count": 0,
                "shape_sanity_target_count": 19,
                "lane_target_counts": {"difficult_protein_complexes": 19},
            }
        },
    )
    _write_json(
        current_sidechain_repack_json,
        {
            "summary": {
                "sidechain_repack_status": "pass",
                "pass_count": 19,
                "blocked_count": 0,
                "target_count": 19,
                "total_soft_clash_delta": 529,
                "total_soft_clash_count_before": 1955,
                "total_soft_clash_count_after": 1426,
                "total_improved_residue_count": 7179,
                "total_repacked_residue_count": 15657,
                "revert_guard_count": 8,
            }
        },
    )
    _write_json(
        current_submission_package_preflight_json,
        {
            "summary": {
                "package_preflight_status": "ready",
                "package_mode": "manifest_only_no_author_code_export",
                "ready_count": 19,
                "blocked_count": 0,
                "target_count": 19,
                "candidate_file_present_count": 19,
                "candidate_sha256_count": 19,
                "format_pass_count": 19,
                "author_record_pass_count": 19,
                "sidechain_repack_pass_count": 19,
                "submission_gate_status": "current_casp17_submission_gate_ready",
                "submission_gate_go_count": 19,
                "submission_gate_no_go_count": 0,
                "submission_gate_target_count": 19,
                "server_registration_ready": False,
                "next_action": "final local review before operator-approved upload",
            }
        },
    )
    _write_json(
        current_submission_deadline_guard_json,
        {
            "summary": {
                "deadline_guard_status": "partial_current_upload_window_ready",
                "current_date": "2026-06-02",
                "upload_window_ready_count": 11,
                "deadline_blocked_count": 8,
                "target_count": 19,
                "human_expired_count": 8,
                "human_expiring_today_count": 2,
                "human_future_count": 9,
                "qa_open_count": 15,
                "qa_expired_count": 4,
                "qa_unknown_count": 0,
                "package_preflight_status": "ready",
                "package_ready_count": 19,
                "package_blocked_count": 0,
                "package_target_count": 19,
                "watchlist_stale": True,
                "watchlist_stale_days": 7,
                "first_blocked_target_id": "T1331",
                "first_blocked_reason": "human_submission_deadline_expired",
                "nearest_open_target_id": "H2319",
                "nearest_open_human_expiration": "2026-06-02",
                "nearest_open_days_to_human_expiration": 0,
                "next_action": "submit or archive only targets whose human deadline remains open",
            }
        },
    )
    _write_json(
        current_upload_queue_json,
        {
            "summary": {
                "upload_queue_status": "official_verified_current_upload_queue_partial",
                "current_date": "2026-06-02",
                "target_count": 19,
                "upload_ready_count": 10,
                "blocked_count": 9,
                "ready_today_count": 2,
                "ready_soon_count": 4,
                "ready_future_count": 4,
                "official_target_count": 77,
                "official_direct_match_count": 18,
                "official_phase_mapped_count": 1,
                "official_missing_count": 0,
                "official_cancelled_count": 1,
                "official_expired_count": 9,
                "official_local_deadline_mismatch_count": 1,
                "official_source": "https://predictioncenter.org/casp17/targetlist.cgi?type=csv",
                "first_upload_target_id": "H2319",
                "first_upload_human_expiration": "2026-06-02",
                "first_blocked_target_id": "H1335",
                "first_blocked_reason": "official_human_deadline_expired",
                "next_action": "work queue_rank > 0 only",
            }
        },
    )
    _write_json(
        current_upload_review_packet_json,
        {
            "summary": {
                "review_packet_status": "current_upload_review_packet_ready",
                "review_target_count": 10,
                "review_ready_count": 10,
                "review_blocked_count": 0,
                "urgency_today_count": 2,
                "urgency_soon_count": 4,
                "urgency_future_count": 4,
                "candidate_present_count": 10,
                "object_catalog_pass_count": 10,
                "viewer_link_count": 10,
                "upload_queue_status": "official_verified_current_upload_queue_partial",
                "upload_ready_count": 10,
                "upload_blocked_count": 9,
                "upload_target_count": 19,
                "first_review_target_id": "H2319",
                "first_review_md": (
                    "casp17/current_upload_review_packet/"
                    "01_h2319_human_astrovirus_va1_capsid_spike_-_antibody_7c8_complex/"
                    "UPLOAD_REVIEW.md"
                ),
                "first_blocked_target_id": "",
                "first_blocker": "",
                "next_action": "open each UPLOAD_REVIEW.md in queue_rank order",
            }
        },
    )
    _write_json(
        current_prospective_strict_blind_escrow_json,
        {
            "summary": {
                "prospective_escrow_status": (
                    "current_prospective_strict_blind_escrow_ready_native_pending_partial_upload_window"
                ),
                "target_count": 19,
                "escrow_ready_count": 19,
                "escrow_blocked_count": 0,
                "upload_ready_count": 10,
                "upload_blocked_count": 9,
                "sha256_match_count": 19,
                "review_link_count": 10,
                "native_pending_count": 19,
                "external_timestamp_required_count": 19,
                "competitive_proof_eligible_count": 0,
                "author_serialized_count": 0,
                "manifest_signature_sha256": "abc123",
                "first_upload_ready_target_id": "H2319",
                "first_upload_blocked_target_id": "H1335",
                "next_action": "externally timestamp the escrow manifest",
            }
        },
    )
    _write_json(
        closure_json,
        {
            "summary": {
                "closure_status": "blocked_input",
                "closed_count": 4,
                "not_closed_count": 5,
                "requirement_count": 9,
                "current_proven_level": "review_quality",
                "next_unclosed_level": "competitive_floor",
                "first_operator_input_action_id": "historical_benchmark_inputs",
                "first_operator_input_blockers": "ready_total_below_threshold",
                "historical_input_workorder_count": 40,
                "historical_core_workorder_count": 40,
                "historical_missing_core_file_count": 80,
                "historical_missing_ablation_layer_file_count": 400,
                "benchmark_operator_ready_count": 0,
                "benchmark_operator_blocked_count": 40,
                "benchmark_missing_win_total_rows": 40,
            }
        },
    )
    _write_json(
        goal_scorecard_json,
        {
            "summary": {
                "scorecard_status": "blocked_input",
                "row_count": 10,
                "pass_count": 1,
                "partial_count": 0,
                "blocked_count": 9,
                "first_blocked_gate": "historical_identity_clearance",
                "first_blocked_next_action": (
                    "Replace placeholder benchmark/target IDs with operator-cleared historical non-CASP17 targets."
                ),
            }
        },
    )
    _write_json(
        historical_winner_normalized_bands_json,
        {
            "summary": {
                "historical_winner_normalized_bands_status": "blocked_strict_blind_metrics_missing",
                "band_count": 5,
                "top5_or_better_count": 0,
                "winner_proximity_count": 0,
                "blocked_band_count": 5,
                "strict_blind_ready_slot_count": 0,
                "strict_blind_slot_count": 40,
                "metric_surface_ready_row_count": 0,
                "metric_surface_row_count": 440,
                "official_archive_baseline_candidate_count": 24,
                "official_archive_competitive_proof_eligible_count": 0,
                "first_blocked_band_id": "casp15_regular_domain",
                "first_blocker": "strict_blind_historical_metric_surface_missing",
                "first_next_action": "score CASP15-style no-leak regular-domain replay rows",
            }
        },
    )
    _write_json(
        historical_winner_normalized_unlock_plan_json,
        {
            "summary": {
                "historical_winner_normalized_unlock_plan_status": (
                    "awaiting_historical_winner_normalized_unlocks"
                ),
                "action_count": 6,
                "ready_action_count": 1,
                "blocked_action_count": 5,
                "strict_blind_ready_slot_count": 0,
                "strict_blind_slot_count": 40,
                "metric_surface_ready_row_count": 0,
                "metric_surface_row_count": 440,
                "sidechain_native_pass_count": 0,
                "sidechain_native_benchmark_count": 40,
                "winner_band_top5_or_better_count": 0,
                "winner_band_count": 5,
                "first_blocked_action_id": "close_first_source_request",
                "first_blocked_gate": "strict_blind_internal_prediction_source",
                "first_blocker": "prediction_not_before_native",
                "first_next_action": "attach pre-native source",
            }
        },
    )
    _write_json(
        win_tier_metric_surface_contract_json,
        {
            "summary": {
                "metric_surface_contract_status": (
                    "awaiting_strict_blind_evidence_files_and_ligand_category_slots"
                ),
                "required_metric_count": 11,
                "covered_required_metric_count": 11,
                "strict_blind_slot_count": 40,
                "ready_slot_count": 0,
                "blocked_slot_count": 40,
                "metric_surface_row_count": 440,
                "ready_metric_row_count": 0,
                "blocked_metric_row_count": 440,
                "organic_ligand_slot_count": 0,
                "official_archive_baseline_policy": "excluded_from_competitive_proof",
                "first_blocked_metric": "GDT_TS",
                "first_blocked_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "next_action": "fill strict-blind prediction/native/no-leak evidence",
            }
        },
    )
    _write_json(
        win_tier_critical_path_board_json,
        {
            "summary": {
                "critical_path_status": "competitive_proof_blocked_on_strict_blind_evidence",
                "stage_count": 9,
                "stage_ready_count": 3,
                "stage_blocked_count": 6,
                "three_d_object_ready_count": 4,
                "three_d_object_count": 4,
                "external_model_selection_ready_target_count": 4,
                "external_model_selection_target_count": 4,
                "external_model_selection_model1_count": 4,
                "external_model_selection_top5_count": 20,
                "strict_blind_ready_slot_count": 0,
                "strict_blind_slot_count": 40,
                "strict_blind_evidence_file_missing_count": 240,
                "strict_blind_operator_open_value_count": 400,
                "first_blocked_stage_id": "strict_blind_batch_closure_runway",
                "first_blocker": "internal_prediction_source_gate",
                "first_next_action": "set source_id to an internal pre-native prediction source",
            }
        },
    )
    _write_json(
        organic_ligand_slot_candidate_packet_json,
        {
            "summary": {
                "organic_ligand_slot_candidate_status": (
                    "organic_ligand_slot_candidates_ready_for_operator_review"
                ),
                "candidate_count": 2,
                "chembl_candidate_count": 1,
                "bindingdb_candidate_count": 1,
                "review_ready_candidate_count": 2,
                "competitive_proof_eligible_count": 0,
                "strict_blind_promotion_blocked_count": 2,
                "local_reference_present_count": 2,
                "prediction_present_count": 2,
                "ligand_mol2_present_count": 2,
                "ligand_template_present_count": 2,
                "lddt_pli_required_count": 2,
                "bisyrmsd_required_count": 2,
                "affinity_label_candidate_count": 1,
                "metric_contract_ligand_slot_gap_count": 0,
                "first_candidate_target_id": (
                    "HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005"
                ),
                "first_candidate_ligand_id": "tcruzi_pde_external_pdeb1_010_chembl4453005",
                "next_action": "choose review-ready organic ligand candidates only after direct authority",
            }
        },
    )
    _write_json(
        organic_ligand_slot_promotion_action_board_json,
        {
            "summary": {
                "organic_ligand_slot_promotion_action_board_status": (
                    "awaiting_organic_ligand_strict_blind_evidence"
                ),
                "candidate_count": 2,
                "action_count": 18,
                "open_action_count": 16,
                "reference_file_preflight_pass_count": 2,
                "operator_evidence_required_count": 8,
                "numeric_value_required_count": 1,
                "affinity_source_required_count": 1,
                "metric_input_required_count": 4,
                "slot_mapping_required_count": 2,
                "proof_ready_candidate_count": 0,
                "competitive_proof_eligible_count": 0,
                "strict_blind_promotion_blocked_count": 2,
                "first_open_action_id": "organic_ligand_promotion_action_002",
                "first_open_target_id": (
                    "HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005"
                ),
                "first_open_action_type": "direct_native_or_source_authority",
                "next_action": "work the direct-authority, no-leak, chronology, ligand-pose, affinity, and metric-input actions",
            }
        },
    )
    _write_json(
        capri_round65_readiness_json,
        {
            "summary": {
                "capri_readiness_status": "blocked_registration_role_selection",
                "round_status": "Active",
                "registration_end": "2026-06-01 midnight",
                "registration_days_remaining": 1,
                "registration_gate_status": "operator_input_required",
                "registration_ready_field_count": 0,
                "registration_required_field_count": 4,
                "role_selection_status": "operator_input_required",
                "target_count": 13,
                "active_target_count": 11,
                "closed_target_count": 2,
                "scorer_priority_target_count": 4,
                "predictor_priority_target_count": 7,
                "blocked_target_count": 11,
                "format_preflight_target_count": 0,
                "target_folder_count": 13,
                "first_open_target_id": "T329",
                "first_next_action": "confirm CASP ID, CAPRI registration, selected role, and submitter contact",
            }
        },
    )
    _write_json(
        active_scope_decision_json,
        {
            "summary": {
                "scope_decision_status": "casp17_only_active",
                "active_competition_scope": "casp17_only",
                "casp17_continuation_status": "active",
                "casp17_priority_status": "historical_benchmark_then_competitive_floor",
                "capri_round65_participation_status": "deferred_pi_required",
                "capri_round65_hold_reason": (
                    "operator_not_pi_capri_registration_requires_pi_or_research_group_lead"
                ),
                "capri_round65_artifact_policy": "preserve_context_no_registration_no_submission",
                "active_lane_count": 3,
                "deferred_lane_count": 1,
                "row_count": 4,
                "first_next_action": (
                    "clear historical non-CASP17 target identity, no-leak provenance, native files, and prediction files"
                ),
            }
        },
    )
    _write_json(
        organizer_notice_json,
        {
            "summary": {
                "organizer_notice_status": "organizer_notice_intake_ready",
                "source_notice_ref": "operator_email_excerpt_casp17_organizer",
                "r2345_first_request_status": "ignored_invalid_dna_t_in_rna_sequence",
                "r2345_replacement_request_status": "accepted_second_request_only",
                "r2345_sequence_validation_gate": "rna_sequence_requires_acgu_no_t",
                "massivefold_generation_scope": "all_human_rna_and_hybrid_targets_plus_protein_targets",
                "massivefold_first_rna_hybrid_set_target_id": "R2341",
                "massivefold_link_count": 3,
                "massivefold_rna_hybrid_link_count": 2,
                "massivefold_protein_complex_link_count": 1,
                "massivefold_r2341_link_present": True,
                "massivefold_r2345_link_present": True,
                "massivefold_model_pool_policy": "external_rerank_accuracy_estimation_pool",
                "massivefold_internal_prediction_policy": "do_not_mark_as_internal_prediction",
                "large_download_policy": "tarballs_not_downloaded_by_notice_packet",
                "next_action": "keep R2345 first request quarantined",
            }
        },
    )
    _write_json(
        massivefold_external_pool_intake_json,
        {
            "summary": {
                "massivefold_external_pool_intake_status": "massivefold_external_pool_intake_ready",
                "massivefold_pool_count": 3,
                "ready_pool_count": 3,
                "blocked_pool_count": 0,
                "rna_hybrid_pool_count": 2,
                "protein_complex_pool_count": 1,
                "competitive_proof_eligible_count": 0,
                "internal_prediction_blocked_count": 3,
                "total_declared_size_bytes": 5100000000,
                "largest_model_set_id": "H2335_T335",
                "r2341_pool_present": True,
                "r2345_pool_present": True,
                "download_policy": "operator_explicit_download_required_no_automatic_tarball_fetch",
                "next_action": "download selected tarballs only into the external-pool lane",
            }
        },
    )
    _write_json(
        rna_hybrid_massivefold_priority_queue_json,
        {
            "summary": {
                "rna_hybrid_massivefold_priority_queue_status": (
                    "rna_hybrid_massivefold_priority_queue_ready"
                ),
                "queue_row_count": 2,
                "ready_queue_row_count": 2,
                "blocked_queue_row_count": 0,
                "first_priority_target_id": "R2341",
                "first_priority_reason": "organizer_notice_first_rna_massivefold_set_available",
                "r2341_queue_rank": 1,
                "r2345_queue_rank": 2,
                "r2345_invalid_request_status": "ignored_invalid_dna_t_in_rna_sequence",
                "r2345_active_request_status": "accepted_second_request_only",
                "r2345_sequence_guard": (
                    "ignore_0930_pacific_invalid_dna_t_request_use_1130_replacement_only"
                ),
                "competitive_proof_eligible_count": 0,
                "internal_prediction_blocked_count": 2,
                "total_declared_size_bytes": 913683813,
                "download_policy": "operator_explicit_download_required_no_automatic_tarball_fetch",
                "next_action": "start with R2341 for rule-checked external-pool acquisition and reranking",
            }
        },
    )
    _write_json(
        protein_complex_massivefold_priority_queue_json,
        {
            "summary": {
                "protein_complex_massivefold_priority_queue_status": (
                    "protein_complex_massivefold_priority_queue_ready"
                ),
                "queue_row_count": 1,
                "ready_queue_row_count": 1,
                "blocked_queue_row_count": 0,
                "first_priority_target_id": "H1311",
                "first_priority_model_set_id": "H1311_T327",
                "first_priority_reason": (
                    "protein_heteromer_or_immune_complex_massivefold_pool_from_organizer_ftp_listing"
                ),
                "largest_model_set_id": "H1311_T327",
                "largest_pool_size_bytes": 1934629344,
                "competitive_proof_eligible_count": 0,
                "internal_prediction_blocked_count": 1,
                "total_declared_size_bytes": 1934629344,
                "download_policy": "operator_explicit_download_required_no_automatic_tarball_fetch",
                "next_action": "start with the first protein/complex MassiveFold pool",
            }
        },
    )
    _write_json(
        massivefold_acquisition_verification_board_json,
        {
            "summary": {
                "massivefold_acquisition_verification_status": (
                    "massivefold_external_pool_acquisition_verified"
                ),
                "acquisition_pool_count": 2,
                "verified_pool_count": 2,
                "open_acquisition_action_count": 0,
                "tarball_present_count": 2,
                "size_match_count": 2,
                "sha256_record_present_count": 2,
                "sha256_verified_count": 2,
                "listing_present_count": 2,
                "listing_entry_count": 16080,
                "first_priority_target_id": "R2341",
                "first_open_target_id": "",
                "first_open_status": "",
                "r2341_verification_status": "verified_for_external_rerank_intake",
                "r2345_verification_status": "verified_for_external_rerank_intake",
                "download_policy": "download_only_to_external_pool_lane_and_preserve_hash_listing",
                "next_action": "use verified external tarballs only as review-only model-selection inputs",
            }
        },
    )
    _write_json(
        protein_complex_massivefold_acquisition_verification_board_json,
        {
            "summary": {
                "massivefold_acquisition_verification_status": (
                    "awaiting_massivefold_external_pool_acquisition"
                ),
                "acquisition_pool_count": 1,
                "verified_pool_count": 0,
                "open_acquisition_action_count": 1,
                "tarball_present_count": 0,
                "size_match_count": 0,
                "sha256_record_present_count": 0,
                "sha256_verified_count": 0,
                "listing_present_count": 0,
                "listing_entry_count": 0,
                "first_priority_target_id": "H1311",
                "first_open_target_id": "H1311",
                "first_open_status": "open_tarball_download_required",
                "download_policy": "download_only_to_external_pool_lane_and_preserve_hash_listing",
                "next_action": "download the tarball into the external-pool downloads folder",
            }
        },
    )
    _write_json(
        massivefold_model_pool_index_json,
        {
            "summary": {
                "massivefold_model_pool_index_status": (
                    "massivefold_model_pool_representatives_extracted"
                ),
                "target_id": "R2341",
                "model_count": 8040,
                "protocol_bucket_count": 8,
                "selected_extract_count": 40,
                "selected_extracted_count": 40,
                "selected_extract_pending_count": 0,
                "basic_count": 1005,
                "wo_templates_count": 1005,
                "wo_unpaired_count": 1005,
                "wo_paired_count": 1005,
                "first_selected_model": (
                    "Model_1_af3_woUnpaired_woPaired_woTemplates_af3_seed_210550_sample_3_pred_718.cif"
                ),
                "first_selected_protocol": "woUnpaired_woPaired_woTemplates",
                "extraction_manifest": (
                    "casp17/massivefold_model_pool_index/r2341/balanced_extract_members.txt"
                ),
                "tarball_sha256": "cfaaad6299ff4a5cd3e78c53d3a32e660ab95ce67f4b6e1ba42277d479fde3ea",
                "next_action": "run external rerank and accuracy-estimation calibration",
            }
        },
    )
    _write_json(
        massivefold_representative_viewer_packet_json,
        {
            "summary": {
                "massivefold_representative_viewer_status": (
                    "massivefold_representative_viewers_ready"
                ),
                "target_id": "R2341",
                "selected_model_count": 40,
                "viewer_ready_count": 40,
                "viewer_blocked_count": 0,
                "coordinate_valid_count": 40,
                "model_cif_present_count": 40,
                "projection_ready_count": 40,
                "atom_count_total": 159280,
                "display_atom_count_total": 36000,
                "residue_count_total": 7440,
                "protocol_bucket_count": 8,
                "first_viewer_html": (
                    "casp17/massivefold_representative_viewers/r2341/"
                    "selection_001_woUnpaired_woPaired_woTemplates_model_1/viewer.html"
                ),
                "gallery_html_path": "casp17/casp17_massivefold_representative_viewer_gallery_current.html",
                "next_action": "open the per-selection viewers for manual conformation triage",
            }
        },
    )
    _write_json(
        massivefold_representative_rerank_packet_json,
        {
            "summary": {
                "massivefold_representative_rerank_status": (
                    "massivefold_representative_rerank_ready_review_only"
                ),
                "target_id": "R2341",
                "candidate_count": 40,
                "model1_candidate_count": 1,
                "top5_candidate_count": 5,
                "top5_protocol_count": 5,
                "review_candidate_count": 35,
                "competitive_proof_eligible_count": 0,
                "confidence_score_min": 48.2803,
                "confidence_score_max": 53.0992,
                "model1_filename": "Model_2_af3_basic_af3_seed_672131_sample_4_pred_869.cif",
                "model1_protocol": "basic",
                "model1_confidence_score": 53.0992,
                "model1_viewer_html": (
                    "casp17/massivefold_representative_viewers/r2341/"
                    "selection_031_basic_model_2/viewer.html"
                ),
                "top5_manifest_csv": "casp17/massivefold_representative_rerank/r2341/top5_manifest.csv",
                "next_action": "use the review-only model1/top5 picks as accuracy-estimation inputs",
            }
        },
    )
    _write_json(
        massivefold_rna_model_selection_coverage_json,
        {
            "summary": {
                "massivefold_rna_model_selection_coverage_status": (
                    "massivefold_rna_model_selection_coverage_ready_review_only"
                ),
                "target_count": 2,
                "ready_target_count": 2,
                "partial_target_count": 0,
                "verified_acquisition_count": 2,
                "representative_extracted_target_count": 2,
                "viewer_ready_target_count": 2,
                "rerank_ready_target_count": 2,
                "selected_model_count": 80,
                "extracted_model_count": 80,
                "viewer_ready_model_count": 80,
                "top5_candidate_count": 10,
                "model1_candidate_count": 2,
                "first_partial_target_id": "",
                "next_action": (
                    "use R2341/R2345 review-only model1/top5 picks as RNA model-selection inputs"
                ),
            }
        },
    )
    _write_json(
        massivefold_rna_model_selection_input_packet_json,
        {
            "summary": {
                "massivefold_rna_model_selection_input_status": (
                    "massivefold_rna_model_selection_input_packet_ready_external_only"
                ),
                "target_count": 2,
                "ready_target_count": 2,
                "blocked_target_count": 0,
                "model1_input_count": 2,
                "top5_input_count": 10,
                "missing_artifact_count": 0,
                "r2345_sequence_guard": (
                    "ignore_0930_pacific_invalid_dna_t_request_use_1130_replacement_only"
                ),
                "internal_prediction_policy": "do_not_mark_as_internal_prediction",
                "first_blocked_target_id": "",
                "next_action": "feed RNA model-selection inputs into self-assessment",
            }
        },
    )
    _write_json(
        massivefold_rna_self_assessment_packet_json,
        {
            "summary": {
                "massivefold_rna_self_assessment_status": (
                    "massivefold_rna_self_assessment_ready_external_only"
                ),
                "target_count": 2,
                "ready_target_count": 2,
                "blocked_target_count": 0,
                "candidate_count": 10,
                "model1_input_count": 2,
                "top5_input_count": 10,
                "low_margin_target_count": 1,
                "low_margin_threshold": 1.0,
                "r2345_sequence_guard": (
                    "ignore_0930_pacific_invalid_dna_t_request_use_1130_replacement_only"
                ),
                "internal_prediction_policy": "do_not_mark_as_internal_prediction",
                "first_blocked_target_id": "",
                "next_action": "use RNA self-assessment features for calibration",
            }
        },
    )
    _write_json(
        protein_complex_massivefold_model_selection_coverage_json,
        {
            "summary": {
                "protein_complex_massivefold_model_selection_coverage_status": (
                    "protein_complex_massivefold_model_selection_coverage_ready_review_only"
                ),
                "target_count": 2,
                "ready_target_count": 2,
                "partial_target_count": 0,
                "verified_acquisition_count": 2,
                "representative_extracted_target_count": 2,
                "viewer_ready_target_count": 2,
                "rerank_ready_target_count": 2,
                "selected_model_count": 260,
                "extracted_model_count": 260,
                "viewer_ready_model_count": 260,
                "top5_candidate_count": 10,
                "model1_candidate_count": 2,
                "first_partial_target_id": "",
                "next_action": (
                    "use H1311/T2313 review-only model1/top5 picks as protein/complex model-selection inputs"
                ),
            }
        },
    )
    _write_json(
        protein_complex_massivefold_self_assessment_packet_json,
        {
            "summary": {
                "protein_complex_massivefold_self_assessment_status": (
                    "protein_complex_massivefold_self_assessment_ready_external_only"
                ),
                "target_count": 2,
                "ready_target_count": 2,
                "blocked_target_count": 0,
                "heteromer_or_immune_complex_count": 1,
                "candidate_count": 10,
                "model1_input_count": 2,
                "top5_input_count": 10,
                "missing_artifact_count": 0,
                "low_margin_target_count": 1,
                "low_margin_threshold": 2.0,
                "internal_prediction_policy": "do_not_mark_as_internal_prediction",
                "first_blocked_target_id": "",
                "next_action": "use protein/complex self-assessment features for calibration",
            }
        },
    )
    _write_json(
        massivefold_model1_risk_queue_json,
        {
            "summary": {
                "massivefold_model1_risk_queue_status": (
                    "massivefold_model1_risk_queue_ready_external_only"
                ),
                "target_count": 4,
                "ready_target_count": 4,
                "blocked_target_count": 0,
                "low_margin_target_count": 2,
                "critical_margin_target_count": 1,
                "rna_hybrid_target_count": 2,
                "protein_complex_target_count": 2,
                "first_priority_target_id": "H1311",
                "first_priority_group": "protein_complex",
                "first_priority_gap": "0.05",
                "first_priority_risk_tier": "critical_model1_margin",
                "internal_prediction_policy": "do_not_mark_as_internal_prediction",
                "next_action": "work low-margin model1 targets first",
            }
        },
    )
    _write_json(
        massivefold_critical_rerank_experiment_json,
        {
            "summary": {
                "massivefold_critical_rerank_experiment_status": (
                    "massivefold_critical_rerank_experiment_ready_external_only"
                ),
                "experiment_count": 2,
                "ready_experiment_count": 2,
                "blocked_experiment_count": 0,
                "rna_hybrid_experiment_count": 1,
                "protein_complex_experiment_count": 1,
                "high_diversity_review_count": 1,
                "geometry_review_count": 1,
                "low_confidence_review_count": 1,
                "first_experiment_target_id": "R2350",
                "first_experiment_group": "rna_hybrid",
                "first_experiment_gap": "0.02",
                "first_experiment_order": "top5_diversity_then_geometry_then_model1_gap",
                "rerank_formula_id": "gap_plus_geometry_plus_diversity_penalty_v1",
                "internal_prediction_policy": "do_not_mark_as_internal_prediction",
                "next_action": "run the critical no-native rerank probes",
            }
        },
    )
    _write_json(
        massivefold_critical_rerank_score_ledger_json,
        {
            "summary": {
                "massivefold_critical_rerank_score_ledger_status": (
                    "massivefold_critical_rerank_score_ledger_ready_external_only"
                ),
                "ledger_count": 2,
                "ready_ledger_count": 2,
                "blocked_ledger_count": 0,
                "immediate_rerank_required_count": 0,
                "calibrate_before_model1_freeze_count": 2,
                "critical_watch_count": 0,
                "rna_hybrid_ledger_count": 1,
                "protein_complex_ledger_count": 1,
                "top_risk_target_id": "R2350",
                "top_risk_group": "rna_hybrid",
                "top_risk_score": "66",
                "top_risk_band": "calibrate_before_model1_freeze",
                "top_rerank_action": "run_targeted_probe_then_freeze_model1_if_consistent",
                "internal_prediction_policy": "do_not_mark_as_internal_prediction",
                "next_action": "review the top score-ledger rows first",
            }
        },
    )
    _write_json(
        massivefold_model1_selection_calibration_gate_json,
        {
            "summary": {
                "massivefold_model1_selection_calibration_gate_status": (
                    "massivefold_model1_selection_calibration_gate_ready_external_only"
                ),
                "freeze_gate_status": "model1_freeze_blocked_by_calibration",
                "gate_count": 2,
                "ready_gate_count": 2,
                "blocked_gate_count": 0,
                "hold_model1_freeze_count": 1,
                "watch_probe_count": 1,
                "probe_required_count": 2,
                "freeze_ready_count": 0,
                "rna_hybrid_gate_count": 1,
                "protein_complex_gate_count": 1,
                "first_gate_target_id": "R2350",
                "first_gate_group": "rna_hybrid",
                "top_risk_score": "66",
                "first_gate_decision": "hold_model1_freeze_probe_required",
                "first_gate_probe_type": "top5_rerank_consistency_probe",
                "selection_rule_id": "no_native_model1_selection_gate_v1",
                "internal_prediction_policy": "do_not_mark_as_internal_prediction",
                "next_action": "run required no-native probes",
            }
        },
    )
    _write_json(
        massivefold_model1_probe_worklist_json,
        {
            "summary": {
                "massivefold_model1_probe_worklist_status": (
                    "massivefold_model1_probe_worklist_ready_external_only"
                ),
                "workitem_count": 2,
                "ready_workitem_count": 2,
                "blocked_workitem_count": 0,
                "top5_rerank_consistency_probe_count": 1,
                "lightweight_rescore_probe_count": 1,
                "priority1_workitem_count": 1,
                "priority2_workitem_count": 1,
                "rna_hybrid_workitem_count": 1,
                "protein_complex_workitem_count": 1,
                "first_workitem_target_id": "R2350",
                "first_workitem_group": "rna_hybrid",
                "first_workitem_risk_score": "66",
                "first_workitem_probe_type": "top5_rerank_consistency_probe",
                "freeze_unlock_policy": "freeze_after_probe_allowed_only_if_exit_criterion_passes",
                "internal_prediction_policy": "do_not_mark_as_internal_prediction",
                "next_action": "execute priority-1 no-native probes",
            }
        },
    )
    _write_json(
        massivefold_model1_probe_outcome_json,
        {
            "summary": {
                "massivefold_model1_probe_outcome_status": (
                    "massivefold_model1_probe_outcome_ready_external_only"
                ),
                "outcome_count": 2,
                "ready_outcome_count": 2,
                "blocked_outcome_count": 0,
                "probe_pass_count": 2,
                "probe_fail_count": 0,
                "freeze_ready_recommendation_count": 2,
                "top5_probe_outcome_count": 1,
                "lightweight_probe_outcome_count": 1,
                "rna_hybrid_outcome_count": 1,
                "protein_complex_outcome_count": 1,
                "first_outcome_target_id": "R2350",
                "first_outcome_group": "rna_hybrid",
                "first_outcome_result": "probe_pass_model1_retained",
                "first_outcome_margin": "0.1",
                "first_freeze_recommendation": (
                    "conditional_model1_freeze_ready_external_only"
                ),
                "scoring_rule_id": "no_native_probe_rescore_v1",
                "internal_prediction_policy": "do_not_mark_as_internal_prediction",
                "next_action": "feed probe outcomes into freeze decision packet",
            }
        },
    )
    _write_json(
        massivefold_model1_freeze_decision_packet_json,
        {
            "summary": {
                "massivefold_model1_freeze_decision_packet_status": (
                    "massivefold_model1_freeze_decision_packet_ready_external_only"
                ),
                "decision_count": 2,
                "ready_decision_count": 2,
                "blocked_decision_count": 0,
                "freeze_ready_total_count": 1,
                "freeze_blocked_total_count": 1,
                "conditional_freeze_ready_count": 1,
                "watch_freeze_ready_count": 0,
                "manual_review_blocked_count": 1,
                "rna_hybrid_decision_count": 1,
                "protein_complex_decision_count": 1,
                "first_freeze_ready_target_id": "R2350",
                "first_freeze_ready_group": "rna_hybrid",
                "first_freeze_ready_decision": "freeze_ready_external_only_conditional",
                "first_blocked_target_id": "H2312",
                "first_blocked_group": "protein_complex",
                "first_blocked_decision": "freeze_blocked_manual_review",
                "decision_rule_id": "no_native_model1_freeze_decision_v1",
                "internal_prediction_policy": "do_not_mark_as_internal_prediction",
                "next_action": "feed freeze-ready decisions into model-selection ledger",
            }
        },
    )
    _write_json(
        massivefold_model_selection_ledger_json,
        {
            "summary": {
                "massivefold_model_selection_ledger_status": (
                    "massivefold_model_selection_ledger_ready_external_only"
                ),
                "ledger_count": 15,
                "ready_ledger_count": 15,
                "blocked_ledger_count": 0,
                "conditional_selected_count": 2,
                "watch_selected_count": 1,
                "manual_review_blocked_count": 1,
                "review_only_unfrozen_count": 11,
                "freeze_ready_selected_count": 3,
                "rna_hybrid_ledger_count": 6,
                "protein_complex_ledger_count": 9,
                "first_ledger_target_id": "R2350",
                "first_ledger_group": "rna_hybrid",
                "first_ledger_decision": "external_model1_selected_conditional",
                "first_manual_review_target_id": "R2352",
                "ledger_rule_id": "no_native_massivefold_model_selection_ledger_v1",
                "internal_prediction_policy": "do_not_mark_as_internal_prediction",
                "next_action": "use this external-only ledger for accuracy-estimation review",
            }
        },
    )
    _write_json(
        massivefold_model1_combined_selector_overlay_json,
        {
            "summary": {
                "massivefold_model1_combined_selector_overlay_status": (
                    "massivefold_model1_combined_selector_overlay_ready_external_only"
                ),
                "overlay_count": 4,
                "overlay_ready_count": 4,
                "overlay_blocked_count": 0,
                "freeze_ready_overlay_count": 1,
                "not_freeze_ready_overlay_count": 3,
                "manual_blocked_overlay_count": 1,
                "interface_hold_overlay_count": 1,
                "weak_probe_hold_overlay_count": 0,
                "probe_required_overlay_count": 1,
                "review_watch_overlay_count": 0,
                "unknown_hold_overlay_count": 0,
                "rna_hybrid_overlay_count": 2,
                "protein_complex_overlay_count": 2,
                "baseline_capture_rate": "0.500",
                "baseline_non_capture_rate": "0.500",
                "first_overlay_target_id": "R2352",
                "first_overlay_decision": "selector_blocked_manual_review",
                "first_overlay_action": "do_not_freeze_model1_external_only",
                "first_freeze_ready_target_id": "R2350",
                "first_freeze_ready_action": "carry_model1_as_external_only_freeze_ready",
                "competitive_proof_eligible": False,
                "internal_prediction_policy": "do_not_mark_as_internal_prediction",
                "next_action": "keep selector overlay external-only until strict-blind proof exists",
            }
        },
    )
    _write_json(
        massivefold_freeze_ready_review_packet_json,
        {
            "summary": {
                "massivefold_freeze_ready_review_packet_status": (
                    "massivefold_freeze_ready_review_packet_ready_external_only"
                ),
                "freeze_ready_target_count": 2,
                "ready_review_count": 2,
                "blocked_review_count": 0,
                "model_present_count": 2,
                "viewer_present_count": 2,
                "projection_present_count": 2,
                "top5_manifest_present_count": 2,
                "top5_candidate_total": 10,
                "first_review_target_id": "R2350",
                "first_review_model_filename": "Model_20_af3_woPaired_seed_1.cif",
                "first_review_viewer_html": "casp17/viewers/r2350/viewer.html",
                "first_review_md": "casp17/review/r2350/FREEZE_READY_REVIEW.md",
                "review_html": "casp17/casp17_massivefold_freeze_ready_review_packet_current.html",
                "competitive_proof_eligible": False,
                "internal_prediction_policy": "do_not_mark_as_internal_prediction",
                "next_action": "operator visually inspects freeze-ready model1/top5 viewers",
            }
        },
    )
    _write_json(
        massivefold_hold_probe_review_packet_json,
        {
            "summary": {
                "massivefold_hold_probe_review_packet_status": (
                    "massivefold_hold_probe_review_packet_ready_external_only"
                ),
                "hold_probe_review_count": 3,
                "ready_review_count": 3,
                "blocked_review_count": 0,
                "manual_blocked_review_count": 1,
                "interface_hold_review_count": 1,
                "probe_required_review_count": 1,
                "weak_probe_hold_review_count": 0,
                "unknown_hold_review_count": 0,
                "model_present_count": 3,
                "viewer_present_count": 3,
                "projection_present_count": 3,
                "top5_manifest_present_count": 3,
                "alternate_present_count": 1,
                "top5_candidate_total": 15,
                "first_review_target_id": "R2352",
                "first_review_class": "manual_blocked_review",
                "first_review_action": "do_not_freeze_model1_external_only",
                "first_review_model_filename": "Model_15_af3_woUnpaired_seed_1.cif",
                "first_review_viewer_html": "casp17/viewers/r2352/viewer.html",
                "review_html": "casp17/casp17_massivefold_hold_probe_review_packet_current.html",
                "competitive_proof_eligible": False,
                "internal_prediction_policy": "do_not_mark_as_internal_prediction",
                "next_action": "operator reviews manual block, interface hold, and probe-required viewers",
            }
        },
    )
    _write_json(
        massivefold_probe_required_targeted_probe_packet_json,
        {
            "summary": {
                "massivefold_probe_required_targeted_probe_packet_status": (
                    "massivefold_probe_required_targeted_probe_packet_ready_external_only"
                ),
                "probe_target_count": 3,
                "ready_probe_count": 3,
                "blocked_probe_count": 0,
                "probe_pass_count": 2,
                "probe_watch_count": 1,
                "probe_fail_count": 0,
                "freeze_candidate_count": 2,
                "watch_recommendation_count": 1,
                "manual_review_recommendation_count": 0,
                "rna_hybrid_probe_count": 1,
                "protein_complex_probe_count": 2,
                "model_present_count": 3,
                "viewer_present_count": 3,
                "projection_present_count": 3,
                "top_candidate_present_count": 3,
                "top_candidate_viewer_present_count": 3,
                "top5_manifest_present_count": 3,
                "top5_candidate_total": 15,
                "clear_margin_threshold": "0.5",
                "first_probe_target_id": "H1311",
                "first_probe_result": "probe_pass_model1_retained_clear",
                "first_probe_margin": "0.75",
                "first_probe_recommendation": "external_model1_freeze_candidate_after_probe",
                "probe_html": "casp17/casp17_massivefold_probe_required_targeted_probe_packet_current.html",
                "competitive_proof_eligible": False,
                "internal_prediction_policy": "do_not_mark_as_internal_prediction",
                "next_action": "feed clear/watch/fail probe recommendations into overlay review",
            }
        },
    )
    _write_json(
        massivefold_post_probe_selector_decision_packet_json,
        {
            "summary": {
                "massivefold_post_probe_selector_decision_packet_status": (
                    "massivefold_post_probe_selector_decision_packet_ready_external_only"
                ),
                "decision_count": 5,
                "ready_decision_count": 5,
                "blocked_decision_count": 0,
                "freeze_candidate_count": 2,
                "watch_decision_count": 2,
                "manual_block_decision_count": 1,
                "existing_freeze_candidate_count": 1,
                "probe_freeze_candidate_count": 1,
                "probe_watch_count": 1,
                "interface_hold_count": 1,
                "manual_review_after_probe_failure_count": 0,
                "manual_block_count": 1,
                "rna_hybrid_decision_count": 2,
                "protein_complex_decision_count": 3,
                "model_present_count": 5,
                "viewer_present_count": 5,
                "projection_present_count": 5,
                "top5_manifest_present_count": 5,
                "alternate_present_count": 1,
                "first_decision_target_id": "R2352",
                "first_decision_class": "manual_block",
                "first_selector_decision": "external_model1_freeze_blocked_manual_review",
                "first_selected_model_filename": "Model_15_af3_woUnpaired_seed_1.cif",
                "decision_html": "casp17/casp17_massivefold_post_probe_selector_decision_packet_current.html",
                "competitive_proof_eligible": False,
                "internal_prediction_policy": "do_not_mark_as_internal_prediction",
                "next_action": "review watch/manual/interface rows before formatting",
            }
        },
    )
    _write_json(
        massivefold_watch_manual_action_packet_json,
        {
            "summary": {
                "massivefold_watch_manual_action_packet_status": (
                    "massivefold_watch_manual_action_packet_ready_external_only"
                ),
                "action_count": 5,
                "ready_action_count": 5,
                "blocked_action_count": 0,
                "manual_alternate_review_count": 1,
                "interface_geometry_review_count": 1,
                "low_margin_top5_review_count": 3,
                "priority1_action_count": 2,
                "priority2_action_count": 3,
                "rna_hybrid_action_count": 2,
                "protein_complex_action_count": 3,
                "model_present_count": 5,
                "viewer_present_count": 5,
                "projection_present_count": 5,
                "top5_manifest_present_count": 5,
                "alternate_present_count": 1,
                "first_action_target_id": "R2352",
                "first_action_class": "manual_alternate_review",
                "first_action_priority": "1",
                "first_exit_criterion": "operator records manual decision",
                "action_html": "casp17/casp17_massivefold_watch_manual_action_packet_current.html",
                "competitive_proof_eligible": False,
                "internal_prediction_policy": "do_not_mark_as_internal_prediction",
                "next_action": "operator resolves the five watch/manual/interface actions",
            }
        },
    )
    _write_json(
        massivefold_freeze_candidate_format_preflight_json,
        {
            "summary": {
                "massivefold_freeze_candidate_format_preflight_status": (
                    "massivefold_freeze_candidate_format_preflight_ready_external_only"
                ),
                "freeze_candidate_count": 10,
                "ready_preflight_count": 10,
                "blocked_preflight_count": 0,
                "existing_freeze_candidate_count": 2,
                "probe_freeze_candidate_count": 8,
                "rna_hybrid_preflight_count": 4,
                "protein_complex_preflight_count": 6,
                "selected_pdb_count": 6,
                "selected_cif_count": 4,
                "packaged_pdb_count": 0,
                "packaged_cif_count": 10,
                "target_id_format_ok_count": 10,
                "selected_extension_ok_count": 10,
                "packaged_extension_ok_count": 10,
                "model_present_count": 10,
                "model_nonempty_count": 10,
                "viewer_present_count": 10,
                "projection_present_count": 10,
                "top5_manifest_present_count": 10,
                "first_preflight_target_id": "H2319",
                "first_preflight_model_filename": "Model_1_afm_basic_model_4_multimer_v3_pred_25.pdb",
                "preflight_html": "casp17/casp17_massivefold_freeze_candidate_format_preflight_current.html",
                "competitive_proof_eligible": False,
                "internal_prediction_policy": "do_not_mark_as_internal_prediction",
                "next_action": "run official CASP rule checks only after operator approval",
            }
        },
    )
    _write_json(
        massivefold_freeze_candidate_escrow_json,
        {
            "summary": {
                "massivefold_freeze_candidate_escrow_status": (
                    "massivefold_freeze_candidate_escrow_ready_external_only"
                ),
                "escrow_count": 10,
                "ready_escrow_count": 10,
                "blocked_escrow_count": 0,
                "model_sha256_count": 10,
                "top5_sha256_count": 10,
                "model_present_count": 10,
                "viewer_present_count": 10,
                "projection_present_count": 10,
                "top5_manifest_present_count": 10,
                "existing_freeze_candidate_count": 2,
                "probe_freeze_candidate_count": 8,
                "rna_hybrid_escrow_count": 4,
                "protein_complex_escrow_count": 6,
                "native_pending_count": 10,
                "competitive_proof_eligible_count": 0,
                "author_serialized_count": 0,
                "first_escrow_target_id": "H2319",
                "first_blocked_target_id": "",
                "manifest_signature_sha256": "freezeabc123",
                "internal_prediction_policy": "do_not_mark_as_internal_prediction",
                "next_action": "hold these external-only hashes for rule-checked formatting review",
            }
        },
    )
    _write_json(
        massivefold_freeze_candidate_protein_library_json,
        {
            "summary": {
                "massivefold_freeze_candidate_protein_library_status": (
                    "massivefold_freeze_candidate_protein_library_ready_external_only"
                ),
                "protein_count": 10,
                "protein_ready_count": 10,
                "protein_blocked_count": 0,
                "object_count": 10,
                "object_ready_count": 10,
                "object_blocked_count": 0,
                "model_link_count": 10,
                "viewer_link_count": 10,
                "projection_link_count": 10,
                "top5_link_count": 10,
                "escrow_link_count": 10,
                "model_sha256_count": 10,
                "top5_sha256_count": 10,
                "current_name_count": 5,
                "official_name_count": 10,
                "rna_hybrid_count": 4,
                "protein_complex_count": 6,
                "competitive_proof_eligible_count": 0,
                "author_serialized_count": 0,
                "first_protein_key": "H2319_Human_astrovirus_VA1_capsid_spike_antibody_7C8_complex",
                "first_blocked_protein_key": "",
                "html_catalog_path": (
                    "casp17/casp17_massivefold_freeze_candidate_protein_library_current.html"
                ),
                "internal_prediction_policy": "do_not_mark_as_internal_prediction",
                "next_action": "open protein-name folders for external-only visual review",
            }
        },
    )
    _write_json(
        capri_round65_format_preflight_json,
        {
            "summary": {
                "format_preflight_status": "blocked_format_preflight",
                "target_count": 13,
                "active_target_count": 11,
                "closed_target_count": 2,
                "local_pass_count": 0,
                "blocked_target_count": 11,
                "checked_submission_count": 0,
                "target_template_missing_count": 11,
                "candidate_submission_missing_count": 11,
                "format_error_count": 0,
                "first_blocked_target_id": "T329",
                "first_next_action": (
                    "place target_template.pdb and candidate_submission.pdb, then rerun local format preflight"
                ),
            }
        },
    )
    _write_json(
        scaffold_json,
        {
            "summary": {
                "scaffold_status": "ready",
                "ready_count": 0,
                "blocked_count": 40,
                "row_count": 40,
                "missing_evidence_item_count": 1310,
            }
        },
    )
    _write_json(
        inventory_json,
        {
            "summary": {
                "inventory_status": "blocked",
                "ready_row_count": 0,
                "blocked_row_count": 40,
                "row_count": 40,
                "required_file_count": 480,
                "present_file_count": 0,
                "missing_file_count": 480,
            }
        },
    )
    _write_json(
        dashboard_json,
        {
            "summary": {
                "dashboard_status": "ready",
                "ready_count": 0,
                "blocked_count": 40,
                "row_count": 40,
                "needs_target_replacement_count": 40,
                "needs_core_file_count": 40,
                "needs_ablation_layer_count": 40,
                "needs_calibration_count": 40,
                "needs_provenance_count": 40,
            },
            "rows": [
                {
                    "row_rank": 1,
                    "operator_row_status": "blocked",
                    "next_action": "Replace placeholder target/benchmark IDs with a cleared historical non-CASP17 protein target.",
                }
            ],
        },
    )
    _write_json(
        historical_identity_seed_inventory_json,
        {
            "summary": {
                "seed_inventory_status": "batch_seed_shape_ready_operator_clearance_required",
                "seed_candidate_count": 17,
                "monomer_seed_candidate_count": 10,
                "complex_seed_candidate_count": 7,
                "eligible_monomer_seed_count": 10,
                "eligible_complex_seed_count": 7,
                "batch_seed_slot_count": 15,
                "candidate_manifest_row_count": 15,
                "operator_clearance_required_count": 15,
                "candidate_manifest_csv": "runs/casp17_historical_benchmark_manifest_seed_current.csv",
                "first_seed_target_id": "HIST_BBA5",
                "first_next_action": "operator must verify no-leak provenance, chronology, calibration values, and ablation files before promotion",
            }
        },
    )
    _write_json(
        historical_identity_seed_clearance_json,
        {
            "summary": {
                "seed_clearance_status": "awaiting_seed_clearance",
                "template_status": "created",
                "seed_inventory_status": "batch_seed_shape_ready_operator_clearance_required",
                "operator_clearance_csv": "runs/casp17_historical_identity_seed_operator_clearance_current.csv",
                "cleared_manifest_csv": "runs/casp17_historical_benchmark_manifest_seed_cleared_current.csv",
                "seed_row_count": 15,
                "ready_seed_count": 0,
                "awaiting_seed_count": 15,
                "cleared_manifest_row_count": 0,
                "blocking_field_count": 270,
                "phase_open_counts": {
                    "identity": 0,
                    "core_files": 0,
                    "no_leak_provenance": 15,
                    "calibration": 15,
                    "ablation": 15,
                },
                "first_open_target_id": "HIST_BBA5",
                "first_open_next_action": "fill operator no-leak evidence, chronology, and leakage controls",
            }
        },
    )
    _write_json(
        historical_identity_seed_clearance_action_bundle_json,
        {
            "summary": {
                "seed_clearance_action_bundle_status": "open_actions",
                "target_count": 15,
                "action_count": 45,
                "open_action_count": 45,
                "target_folder_count": 15,
                "action_folder_count": 45,
                "bundle_file_count": 90,
                "identity_action_count": 0,
                "core_file_action_count": 0,
                "no_leak_action_count": 15,
                "calibration_action_count": 15,
                "ablation_action_count": 15,
                "first_open_action_md": (
                    "casp17/historical_identity_seed_clearance_action_bundle/"
                    "01_HIST_BBA5/action_001_no_leak_provenance/ACTION.md"
                ),
            }
        },
    )
    _write_json(
        historical_identity_seed_clearance_field_board_json,
        {
            "summary": {
                "field_board_status": "operator_field_fill_required",
                "seed_row_count": 15,
                "core_file_pass_count": 15,
                "blocked_core_file_count": 0,
                "operator_field_fill_required_count": 15,
                "ready_for_cleared_seed_manifest_count": 0,
                "no_leak_open_field_count": 165,
                "calibration_open_field_count": 90,
                "ablation_open_field_count": 15,
                "total_open_field_count": 270,
                "first_open_target_id": "HIST_BBA5",
                "first_open_field": "no_leak_evidence_ref",
                "first_next_action": "fill no-leak evidence, chronology, leakage controls, and operator clearance first",
            }
        },
    )
    _write_json(
        historical_seed_no_leak_provenance_dossiers_json,
        {
            "summary": {
                "no_leak_dossier_status": "operator_provenance_review_required",
                "seed_row_count": 15,
                "dossier_count": 15,
                "core_input_pass_count": 15,
                "current_target_prefilled_false_count": 15,
                "operator_review_required_count": 15,
                "ready_for_no_leak_clearance_count": 0,
                "operator_required_open_field_count": 150,
                "chronology_evidence_gap_count": 15,
                "negative_leakage_control_gap_count": 15,
                "mtime_order_risk_count": 15,
                "blocked_core_provenance_input_count": 0,
                "blocked_current_target_risk_count": 0,
                "first_open_target_id": "HIST_BBA5",
                "first_next_action": "attach independent no-leak evidence and operator clearance before setting leakage_clearance",
            }
        },
    )
    _write_json(
        historical_seed_no_leak_gap_repair_plan_json,
        {
            "summary": {
                "no_leak_gap_repair_status": "no_leak_gap_repair_required",
                "seed_row_count": 15,
                "repair_csv_count": 15,
                "field_count": 150,
                "operator_required_field_count": 150,
                "weak_local_candidate_field_count": 30,
                "authoritative_candidate_field_count": 0,
                "chronology_field_count": 45,
                "negative_control_field_count": 45,
                "clearance_field_count": 60,
                "mtime_risk_row_count": 15,
                "first_open_target_id": "HIST_BBA5",
                "first_next_action": (
                    "attach independent no-leak evidence, authoritative dates, negative controls, and operator clearance"
                ),
            }
        },
    )
    _write_json(
        historical_seed_current_target_prefill_json,
        {
            "summary": {
                "prefill_status": "applied",
                "apply_mode": "apply",
                "row_count": 15,
                "ready_to_apply_count": 0,
                "applied_count": 15,
                "already_safe_false_count": 0,
                "blocked_count": 0,
                "current_target_collision_count": 0,
                "remaining_open_current_target_count": 0,
                "hist_prefix_pass_count": 15,
                "first_next_action": "set current_casp17_target=false",
            }
        },
    )
    _write_json(
        historical_seed_native_authority_audit_json,
        {
            "summary": {
                "native_authority_audit_status": "blocked_native_authority",
                "seed_row_count": 15,
                "native_authority_pass_count": 0,
                "native_authority_blocked_count": 15,
                "placeholder_native_count": 10,
                "ca_only_native_count": 10,
                "local_generated_native_without_authority_count": 5,
                "authority_ref_missing_count": 15,
                "first_blocked_target_id": "HIST_BBA5",
                "first_blocked_next_action": (
                    "replace the placeholder or CA-only native with an authoritative all-atom native/reference PDB"
                ),
            }
        },
    )
    _write_json(
        historical_seed_native_replacement_candidates_json,
        {
            "summary": {
                "native_replacement_candidate_status": "partial_native_replacement_candidates_ready",
                "candidate_row_count": 17,
                "operator_review_ready_count": 10,
                "source_download_required_count": 0,
                "candidate_file_blocked_count": 0,
                "complex_authority_required_count": 7,
                "monomer_candidate_count": 10,
                "candidate_dir": "casp17/historical_seed_native_replacement_candidates",
                "first_blocked_target_id": (
                    "HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005"
                ),
                "first_blocked_next_action": (
                    "attach external native/source authority for this complex reference or replace the seed row"
                ),
            }
        },
    )
    _write_json(
        historical_seed_complex_source_authority_candidates_json,
        {
            "summary": {
                "complex_source_authority_candidate_status": (
                    "complex_homolog_source_authority_candidates_ready_claim_limited"
                ),
                "candidate_row_count": 7,
                "operator_review_ready_count": 7,
                "direct_source_authority_ready_count": 0,
                "homolog_source_authority_ready_count": 7,
                "source_authority_blocked_count": 0,
                "operator_apply_allowed_count": 0,
                "claim_promotion_allowed_count": 0,
                "protein_authority_ref": "rcsb:3V94;chain:B;doi:10.2210/pdb3v94/pdb",
                "first_blocked_target_id": (
                    "HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005"
                ),
                "first_next_action": (
                    "operator may cite this as source authority only after accepting the homolog-only claim boundary"
                ),
            }
        },
    )
    _write_json(
        historical_seed_chronology_candidate_board_json,
        {
            "summary": {
                "chronology_board_status": "operator_evidence_required",
                "row_count": 15,
                "operator_chronology_ready_count": 0,
                "operator_ready_mtime_warning_count": 0,
                "operator_evidence_required_count": 15,
                "blocked_chronology_conflict_count": 0,
                "prediction_path_date_count": 10,
                "file_mtime_candidate_count": 15,
                "file_mtime_order_risk_count": 15,
                "first_open_target_id": "HIST_BBA5",
                "first_next_action": (
                    "fill prediction_created_at, native_release_date, and before-native confirmation "
                    "from operator evidence"
                ),
            }
        },
    )
    _write_json(
        historical_seed_authoritative_chronology_audit_json,
        {
            "summary": {
                "authoritative_chronology_audit_status": "post_native_prediction_chronology_blocked",
                "seed_row_count": 17,
                "native_authority_date_count": 10,
                "prediction_date_candidate_count": 10,
                "before_native_candidate_count": 0,
                "post_native_blocked_count": 10,
                "evidence_required_count": 7,
                "native_authority_not_pass_count": 7,
                "missing_native_authority_date_count": 7,
                "missing_prediction_date_count": 7,
                "first_blocked_target_id": "HIST_BBA5",
                "first_next_action": (
                    "replace with a pre-native blind prediction artifact, or keep this row in a separate "
                    "post-native retrospective lane with explicit no-template evidence"
                ),
            }
        },
    )
    _write_json(
        historical_seed_lane_decision_packet_json,
        {
            "summary": {
                "lane_decision_status": "strict_blind_replacement_required",
                "seed_row_count": 17,
                "strict_blind_eligible_count": 0,
                "retrospective_calibration_review_count": 10,
                "authority_or_replacement_required_count": 7,
                "competitive_proof_allowed_count": 0,
                "identity_intake_allowed_count": 0,
                "sidechain_native_benchmark_allowed_count": 0,
                "strict_blind_replacement_required_count": 17,
                "operator_decision_required_count": 17,
                "first_blocked_target_id": "HIST_BBA5",
                "first_next_action": (
                    "keep this row outside competitive proof unless operator supplies a pre-native blind "
                    "prediction artifact; otherwise use only for retrospective no-template calibration review"
                ),
            }
        },
    )
    _write_json(
        historical_seed_strict_blind_replacement_queue_json,
        {
            "summary": {
                "strict_blind_replacement_queue_status": "strict_blind_replacement_queue_open",
                "scaffold_slot_count": 40,
                "monomer_slot_count": 25,
                "complex_slot_count": 15,
                "strict_blind_replacement_required_count": 40,
                "strict_blind_ready_slot_count": 0,
                "competitive_proof_allowed_slot_count": 0,
                "requirement_field_count": 640,
                "current_seed_count": 17,
                "current_seed_strict_blind_count": 0,
                "current_seed_retrospective_count": 10,
                "current_seed_authority_required_count": 7,
                "current_seed_competitive_allowed_count": 0,
                "first_open_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "first_next_action": (
                    "select a non-current historical target with pre-native internal prediction, "
                    "authoritative native, no-leak evidence, ablation layers, calibration values, "
                    "and operator clearance"
                ),
            }
        },
    )
    _write_json(
        historical_seed_strict_blind_replacement_intake_json,
        {
            "summary": {
                "strict_blind_replacement_intake_status": "awaiting_strict_blind_replacement_intake",
                "intake_slot_count": 40,
                "required_field_count": 640,
                "filled_field_count": 0,
                "missing_field_count": 640,
                "ready_for_preflight_count": 0,
                "blocked_or_awaiting_count": 40,
                "created_template_count": 40,
                "preserved_template_count": 0,
                "first_open_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "first_next_action": (
                    "fill replacement_candidate_intake.csv with strict-blind evidence, then rerun intake preflight"
                ),
            }
        },
    )
    _write_json(
        historical_seed_strict_blind_replacement_evidence_dropzones_json,
        {
            "summary": {
                "strict_blind_replacement_evidence_dropzone_status": "awaiting_strict_blind_evidence_files",
                "dropzone_count": 40,
                "ready_for_intake_patch_count": 0,
                "awaiting_file_count": 40,
                "file_required_count": 240,
                "file_present_count": 0,
                "file_missing_count": 240,
                "operator_value_required_count": 400,
                "patch_preview_count": 40,
                "first_open_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "first_next_action": (
                    "place strict-blind evidence files in this dropzone, then rerun dropzone and intake preflight"
                ),
            }
        },
    )
    _write_json(
        historical_seed_strict_blind_replacement_evidence_quality_audit_json,
        {
            "summary": {
                "strict_blind_replacement_evidence_quality_audit_status": (
                    "awaiting_strict_blind_evidence_quality_files"
                ),
                "slot_count": 40,
                "ready_for_quality_review_count": 0,
                "awaiting_evidence_files_count": 40,
                "blocked_evidence_quality_count": 0,
                "file_required_count": 240,
                "file_present_count": 0,
                "file_missing_count": 240,
                "pdb_valid_slot_count": 0,
                "pdb_invalid_slot_count": 0,
                "supporting_valid_slot_count": 0,
                "supporting_invalid_slot_count": 0,
                "prediction_native_distinct_count": 0,
                "prediction_native_identical_count": 0,
                "first_open_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "first_open_status": "awaiting_evidence_files",
                "first_next_action": (
                    "place all six strict-blind evidence files in the dropzone and rerun dropzones/quality audit"
                ),
            }
        },
    )
    _write_json(
        historical_seed_strict_blind_replacement_evidence_action_board_json,
        {
            "summary": {
                "strict_blind_replacement_evidence_action_board_status": (
                    "awaiting_strict_blind_evidence_actions"
                ),
                "action_count": 240,
                "ready_for_quality_audit_count": 0,
                "open_missing_file_count": 240,
                "blocked_count": 0,
                "prediction_pdb_missing_count": 40,
                "native_pdb_missing_count": 40,
                "native_authority_missing_count": 40,
                "no_leak_evidence_missing_count": 40,
                "ablation_manifest_missing_count": 40,
                "calibration_values_missing_count": 40,
                "first_open_action_id": "strict_blind_evidence_001",
                "first_open_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "first_open_field": "prediction_pdb",
                "first_next_action": (
                    "place prediction_pdb evidence at casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/prediction/replacement_prediction.pdb"
                ),
            }
        },
    )
    _write_json(
        historical_seed_strict_blind_replacement_evidence_import_gate_json,
        {
            "summary": {
                "strict_blind_replacement_evidence_import_gate_status": (
                    "awaiting_strict_blind_evidence_import"
                ),
                "apply_mode": "dry_run",
                "action_count": 640,
                "file_action_count": 240,
                "operator_value_action_count": 400,
                "ready_for_apply_count": 0,
                "applied_count": 0,
                "already_applied_count": 0,
                "operator_value_present_count": 0,
                "awaiting_file_count": 240,
                "awaiting_operator_value_count": 400,
                "blocked_count": 0,
                "first_open_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "first_open_field": "prediction_pdb",
                "first_open_status": "awaiting_file",
                "first_next_action": (
                    "place the missing evidence file in the strict-blind dropzone and rerun dropzones/import gate"
                ),
            }
        },
    )
    _write_json(
        historical_seed_strict_blind_replacement_operator_value_gate_json,
        {
            "summary": {
                "strict_blind_replacement_operator_value_gate_status": "awaiting_operator_values",
                "apply_mode": "dry_run",
                "template_count": 40,
                "created_template_count": 40,
                "preserved_template_count": 0,
                "action_count": 400,
                "ready_for_apply_count": 0,
                "applied_count": 0,
                "already_applied_count": 0,
                "awaiting_operator_value_count": 400,
                "awaiting_evidence_ref_count": 0,
                "awaiting_operator_clearance_count": 0,
                "blocked_count": 0,
                "first_open_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "first_open_field": "replacement_target_id",
                "first_open_status": "awaiting_operator_value",
                "first_next_action": (
                    "fill operator_value for replacement_target_id in replacement_operator_values.csv"
                ),
            }
        },
    )
    _write_json(
        historical_seed_strict_blind_replacement_operator_action_board_json,
        {
            "summary": {
                "strict_blind_replacement_operator_action_board_status": (
                    "awaiting_strict_blind_operator_actions"
                ),
                "action_count": 400,
                "ready_for_apply_count": 0,
                "applied_count": 0,
                "already_applied_count": 0,
                "open_operator_value_count": 400,
                "open_evidence_ref_count": 400,
                "open_operator_clearance_count": 400,
                "blocked_count": 0,
                "replacement_target_id_missing_count": 40,
                "replacement_benchmark_id_missing_count": 40,
                "target_identity_non_current_missing_count": 40,
                "prediction_created_at_missing_count": 40,
                "native_release_date_missing_count": 40,
                "prediction_before_native_missing_count": 40,
                "public_template_false_missing_count": 40,
                "other_team_false_missing_count": 40,
                "post_release_false_missing_count": 40,
                "operator_clearance_value_missing_count": 40,
                "first_open_action_id": "strict_blind_operator_001",
                "first_open_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "first_open_field": "replacement_target_id",
                "first_open_status": "open_operator_value",
                "first_next_action": "fill operator_value for replacement_target_id in replacement_operator_values.csv",
            }
        },
    )
    _write_json(
        historical_seed_strict_blind_replacement_promotion_gate_json,
        {
            "summary": {
                "strict_blind_replacement_promotion_gate_status": (
                    "awaiting_strict_blind_replacement_promotion"
                ),
                "slot_count": 40,
                "ready_for_competitive_proof_count": 0,
                "awaiting_file_evidence_count": 40,
                "awaiting_operator_values_count": 40,
                "awaiting_apply_count": 0,
                "awaiting_intake_preflight_count": 40,
                "blocked_review_count": 0,
                "intake_ready_count": 0,
                "file_complete_slot_count": 0,
                "operator_complete_slot_count": 0,
                "file_awaiting_action_count": 240,
                "operator_awaiting_action_count": 400,
                "first_open_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "first_open_phase": "file_evidence",
                "first_open_status": "awaiting_file_evidence",
                "first_next_action": (
                    "place required strict-blind evidence files, rerun dropzones/import gate"
                ),
            }
        },
    )
    _write_json(
        historical_seed_strict_blind_replacement_cycle_json,
        {
            "summary": {
                "strict_blind_replacement_cycle_status": "awaiting_evidence_files",
                "slot_count": 40,
                "promotion_ready_count": 0,
                "evidence_file_present_count": 0,
                "evidence_file_missing_count": 240,
                "quality_ready_count": 0,
                "quality_awaiting_count": 40,
                "quality_blocked_count": 0,
                "import_ready_count": 0,
                "import_awaiting_file_count": 240,
                "import_awaiting_operator_count": 400,
                "operator_ready_count": 0,
                "operator_awaiting_value_count": 400,
                "operator_action_board_ready_count": 0,
                "operator_action_board_action_count": 400,
                "operator_action_board_open_value_count": 400,
                "operator_action_board_open_evidence_count": 400,
                "operator_action_board_open_clearance_count": 400,
                "first_blocking_stage": "evidence_dropzones",
                "first_open_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "first_next_action": "place strict-blind evidence files",
            }
        },
    )
    _write_json(
        historical_seed_strict_blind_replacement_first_slot_kit_json,
        {
            "summary": {
                "strict_blind_replacement_first_slot_kit_status": "awaiting_first_slot_evidence_files",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "scope": "monomer",
                "evidence_action_count": 6,
                "evidence_ready_count": 0,
                "evidence_open_count": 6,
                "evidence_blocked_count": 0,
                "operator_action_count": 10,
                "operator_ready_count": 0,
                "operator_open_count": 10,
                "operator_blocked_count": 0,
                "operator_open_value_count": 10,
                "operator_open_evidence_count": 10,
                "operator_open_clearance_count": 10,
                "first_open_action_group": "evidence_file",
                "first_open_action_id": "strict_blind_evidence_001",
                "first_open_field": "prediction_pdb",
                "first_open_status": "open_missing_file",
                "first_next_action": "place prediction_pdb evidence",
                "kit_folder": "casp17/historical_seed_strict_blind_replacement_first_slot_kit/hist_REQUIRED_MONOMER_001",
            }
        },
    )
    _write_json(
        historical_seed_strict_blind_replacement_first_slot_local_candidate_board_json,
        {
            "summary": {
                "strict_blind_replacement_first_slot_local_candidate_board_status": (
                    "first_slot_local_candidates_review_only"
                ),
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "scope": "monomer",
                "candidate_count": 15,
                "ready_for_first_slot_count": 0,
                "strict_blind_eligible_count": 0,
                "material_present_count": 15,
                "prediction_present_count": 15,
                "native_present_count": 15,
                "native_authority_present_count": 15,
                "blocked_chronology_count": 10,
                "blocked_no_leak_count": 15,
                "blocked_ablation_count": 14,
                "blocked_calibration_count": 15,
                "first_review_target_id": "HIST_BBA5",
                "first_review_benchmark_id": "hist_seed_bba5",
                "first_review_status": "blocked_chronology_not_strict_blind",
                "first_review_next_action": (
                    "find or attach a prediction artifact created before authoritative native release"
                ),
            }
        },
    )
    _write_json(
        historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_json,
        {
            "summary": {
                "strict_blind_replacement_first_slot_candidate_repair_board_status": (
                    "awaiting_first_slot_candidate_repairs"
                ),
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "candidate_count": 17,
                "action_count": 96,
                "open_repair_action_count": 79,
                "blocked_action_count": 17,
                "chronology_action_count": 17,
                "no_leak_action_count": 17,
                "ablation_action_count": 17,
                "calibration_action_count": 17,
                "prediction_file_action_count": 2,
                "native_file_action_count": 2,
                "native_authority_action_count": 7,
                "eligibility_action_count": 17,
                "first_open_action_id": "first_slot_repair_001",
                "first_open_target_id": "HIST_BBA5",
                "first_open_repair_class": "chronology",
                "first_open_blocker": "prediction_not_before_native",
                "first_open_status": "open_repair_action",
                "first_next_action": (
                    "attach a prediction artifact created before the authoritative native release date"
                ),
            }
        },
    )
    _write_json(
        historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_json,
        {
            "summary": {
                "strict_blind_replacement_first_slot_repair_feasibility_board_status": (
                    "first_slot_current_local_candidate_source_required"
                ),
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "candidate_count": 17,
                "action_count": 96,
                "not_repairable_with_current_prediction_count": 17,
                "blocked_by_post_native_prediction_count": 17,
                "external_pre_native_artifact_required_action_count": 34,
                "external_pre_native_artifact_required_target_count": 17,
                "repairable_operator_source_required_count": 11,
                "repairable_operator_evidence_required_count": 51,
                "needs_chronology_date_evidence_count": 0,
                "blocked_by_primary_repairs_count": 0,
                "repairable_current_prediction_pre_native_count": 0,
                "first_external_action_id": "first_slot_repair_001",
                "first_external_target_id": "HIST_BBA5",
                "first_external_blocker": "prediction_not_before_native",
                "first_external_next_route": "source_external_pre_native_prediction_or_replace_candidate",
                "first_actionable_action_id": "first_slot_repair_011",
                "first_actionable_target_id": "HIST_COMPLEX_01",
                "first_actionable_status": "repairable_operator_source_required",
                "first_actionable_required_input": "attach authoritative native/source reference",
            }
        },
    )
    _write_json(
        historical_seed_strict_blind_replacement_first_slot_source_route_board_json,
        {
            "summary": {
                "strict_blind_replacement_first_slot_source_route_board_status": (
                    "first_slot_requires_pre_native_monomer_source_or_replacement"
                ),
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "required_scope": "monomer",
                "route_count": 17,
                "in_scope_route_count": 10,
                "out_of_scope_route_count": 7,
                "allowed_for_first_slot_count": 0,
                "in_scope_external_required_count": 10,
                "in_scope_external_action_count": 20,
                "out_of_scope_source_required_count": 7,
                "out_of_scope_date_required_count": 7,
                "first_external_route_id": "first_slot_source_route_001",
                "first_external_target_id": "HIST_BBA5",
                "first_external_prediction_created_at": "2026-02-19",
                "first_external_native_release_date": "2004-05-13",
                "first_external_next_action": (
                    "source a pre-native prediction archive for this monomer or replace with a strict-blind monomer candidate"
                ),
            }
        },
    )
    _write_json(
        historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_json,
        {
            "summary": {
                "strict_blind_replacement_first_slot_official_archive_source_candidates_status": (
                    "first_slot_official_archive_native_authority_candidates_available"
                ),
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "required_scope": "monomer",
                "source_count": 2,
                "source_competitions": "CASP15,CASP16",
                "candidate_count": 24,
                "pre_native_candidate_count": 24,
                "ready_candidate_count": 24,
                "blocked_candidate_count": 0,
                "native_authority_ready_count": 24,
                "native_authority_lookup_required_count": 0,
                "native_pdb_download_ready_count": 24,
                "native_mmcif_only_count": 0,
                "targetlist_metadata_present_count": 24,
                "targetlist_capri_marker_count": 3,
                "targetlist_special_mode_count": 2,
                "regular_monomer_count": 13,
                "domain_subunit_count": 9,
                "variant_count": 2,
                "first_ready_candidate_id": "official_archive_source_001",
                "first_ready_competition": "CASP16",
                "first_ready_target_id": "T1210",
                "first_ready_prediction_archive_modified_at": "2024-05-30 09:21",
                "first_ready_native_public_anchor_date": "2025-02-01",
                "first_ready_native_pdb_code": "9enr",
                "first_ready_native_pdb_url": "https://www.rcsb.org/structure/9enr",
                "first_ready_native_structure_file_url": "https://files.rcsb.org/download/9ENR.pdb",
                "first_ready_native_structure_file_format": "pdb",
                "first_ready_native_pdb_download_status": "pdb_available",
                "first_ready_targetlist_target_url": "https://predictioncenter.org/casp16/target.cgi?id=60&view=all",
                "first_ready_prediction_tarball_url": (
                    "https://predictioncenter.org/download_area/CASP16/predictions/regular/T1210.tar.gz"
                ),
            }
        },
    )
    _write_json(
        historical_seed_official_archive_baseline_lane_json,
        {
            "summary": {
                "official_archive_baseline_lane_status": "official_archive_baseline_lane_ready",
                "source_candidate_count": 24,
                "source_ready_candidate_count": 24,
                "baseline_candidate_count": 24,
                "ready_count": 24,
                "blocked_count": 0,
                "competitive_proof_eligible_count": 0,
                "strict_blind_import_blocked_count": 24,
                "other_team_model_baseline_only_count": 24,
                "strict_blind_intake_policy": "do_not_import_as_internal_prediction",
                "first_baseline_candidate_id": "official_archive_baseline_001",
                "first_competition": "CASP16",
                "first_target_id": "T1210",
                "first_native_pdb_code": "9enr",
                "first_acquisition_manifest": (
                    "casp17/historical_seed_official_archive_baseline_lane/001_casp16_t1210/"
                    "ACQUISITION_MANIFEST.md"
                ),
                "next_action": (
                    "keep official CASP archive submissions in the baseline replay lane; do not feed them into "
                    "strict-blind competitive proof or internal prediction dropzones"
                ),
            }
        },
    )
    _write_json(
        official_archive_first_baseline_acquisition_audit_json,
        {
            "summary": {
                "official_archive_first_baseline_acquisition_audit_status": (
                    "official_archive_first_baseline_acquired"
                ),
                "first_baseline_candidate_id": "official_archive_baseline_001",
                "first_competition": "CASP16",
                "first_target_id": "T1210",
                "first_native_pdb_code": "9ENR",
                "ready_artifact_count": 2,
                "blocked_artifact_count": 0,
                "artifact_count": 2,
                "tarball_present": True,
                "tarball_size_bytes": 25069184,
                "tarball_model_count": 357,
                "native_pdb_present": True,
                "native_pdb_atom_count": 7051,
                "competitive_proof_eligible": False,
                "strict_blind_intake_policy": "do_not_import_as_internal_prediction",
                "next_action": (
                    "extract and score the baseline-only model1/best-of-5 set without importing it "
                    "as internal proof"
                ),
            }
        },
    )
    _write_json(
        official_archive_first_baseline_model_pool_json,
        {
            "summary": {
                "official_archive_first_baseline_model_pool_status": (
                    "official_archive_first_baseline_model_pool_ready"
                ),
                "first_baseline_candidate_id": "official_archive_baseline_001",
                "first_competition": "CASP16",
                "first_target_id": "T1210",
                "first_native_pdb_code": "9ENR",
                "expected_model_count": 357,
                "ready_model_count": 357,
                "blocked_model_count": 0,
                "group_count": 74,
                "model1_count": 73,
                "top5_model_count": 348,
                "complete_top5_group_count": 67,
                "extra_model_count": 9,
                "competitive_proof_eligible": False,
                "strict_blind_intake_policy": "do_not_import_as_internal_prediction",
                "model1_manifest_csv": "casp17/official_archive_first_baseline_model_pool/model1_manifest.csv",
                "top5_manifest_csv": "casp17/official_archive_first_baseline_model_pool/top5_manifest.csv",
                "next_action": (
                    "score baseline-only model1 and best-of-5 against the native PDB without importing "
                    "as internal proof"
                ),
            }
        },
    )
    _write_json(
        official_archive_first_baseline_score_ledger_json,
        {
            "summary": {
                "official_archive_first_baseline_score_ledger_status": (
                    "official_archive_first_baseline_score_ledger_ready_baseline_only"
                ),
                "first_baseline_candidate_id": "official_archive_baseline_001",
                "first_competition": "CASP16",
                "first_target_id": "T1210",
                "first_native_pdb_code": "9ENR",
                "top5_model_count": 348,
                "scored_model_count": 348,
                "ready_model_count": 348,
                "blocked_model_count": 0,
                "group_count": 74,
                "model1_group_count": 73,
                "best_top5_group_count": 74,
                "complete_top5_group_count": 67,
                "top5_improved_group_count": 41,
                "mean_model1_gdt_ts_proxy": "55.123",
                "mean_best_top5_gdt_ts_proxy": "62.456",
                "mean_best_minus_model1_gdt_ts_proxy": "7.333",
                "max_gap_group_id": "999",
                "max_best_minus_model1_gdt_ts_proxy": "22.100",
                "competitive_proof_eligible": False,
                "strict_blind_intake_policy": "do_not_import_as_internal_prediction",
                "group_score_csv": "casp17/official_archive_first_baseline_score_ledger/group_score_ledger.csv",
                "model_score_csv": "casp17/official_archive_first_baseline_score_ledger/model_score_rows.csv",
                "next_action": (
                    "use the baseline-only score ledger for historical replay calibration; keep "
                    "strict-blind proof blocked"
                ),
            }
        },
    )
    _write_json(
        official_archive_first_baseline_replay_comparison_json,
        {
            "summary": {
                "official_archive_first_baseline_replay_comparison_status": (
                    "official_archive_first_baseline_replay_comparison_ready_baseline_only"
                ),
                "first_baseline_candidate_id": "official_archive_baseline_001",
                "first_competition": "CASP16",
                "first_target_id": "T1210",
                "first_native_pdb_code": "9ENR",
                "band_count": 3,
                "direct_comparable_band_count": 0,
                "blocked_band_count": 3,
                "direct_comparison_status": "not_directly_comparable_proxy_single_target_not_sum_zscore",
                "scored_model_count": 348,
                "group_count": 74,
                "ready_group_count": 73,
                "model1_best_group_count": 32,
                "top5_improved_group_count": 41,
                "model1_best_rate": "0.438",
                "top5_improved_rate": "0.562",
                "mean_model1_gdt_ts_proxy": "55.123",
                "mean_best_top5_gdt_ts_proxy": "62.456",
                "mean_best_minus_model1_gdt_ts_proxy": "7.333",
                "competitive_proof_eligible": False,
                "strict_blind_intake_policy": "do_not_import_as_internal_prediction",
                "comparison_csv": (
                    "casp17/official_archive_first_baseline_replay_comparison/"
                    "winner_band_comparison.csv"
                ),
                "next_action": (
                    "keep this as baseline-only model-selection calibration, then close "
                    "strict-blind source evidence before any winner-normalized competitive claim"
                ),
            }
        },
    )
    _write_json(
        official_archive_first_baseline_model1_gap_triage_json,
        {
            "summary": {
                "official_archive_first_baseline_model1_gap_triage_status": (
                    "official_archive_first_baseline_model1_gap_triage_ready_baseline_only"
                ),
                "first_baseline_candidate_id": "official_archive_baseline_001",
                "first_competition": "CASP16",
                "first_target_id": "T1210",
                "first_native_pdb_code": "9ENR",
                "group_count": 74,
                "ready_group_count": 73,
                "blocked_group_count": 1,
                "model1_best_group_count": 32,
                "top5_improved_group_count": 41,
                "model1_best_rate": "0.438",
                "top5_improved_rate": "0.562",
                "small_gap_count": 10,
                "medium_gap_count": 20,
                "large_gap_count": 8,
                "catastrophic_gap_count": 3,
                "calibration_case_count": 41,
                "critical_calibration_case_count": 11,
                "first_triage_group_id": "999",
                "first_triage_band": "catastrophic_model1_selection_gap",
                "first_triage_delta": "70.000",
                "first_triage_action": "critical_model1_failure_case_for_accuracy_estimation_training",
                "competitive_proof_eligible": False,
                "strict_blind_intake_policy": "do_not_import_as_internal_prediction",
                "triage_csv": "casp17/official_archive_first_baseline_model1_gap_triage/model1_gap_triage.csv",
                "top_gap_worklist_csv": (
                    "casp17/official_archive_first_baseline_model1_gap_triage/top_gap_worklist.csv"
                ),
                "next_action": (
                    "use high-gap baseline-only cases to calibrate no-native model1 selection features; "
                    "keep strict-blind competitive proof blocked until internal evidence is supplied"
                ),
            }
        },
    )
    _write_json(
        official_archive_first_baseline_model1_gap_viewer_packet_json,
        {
            "summary": {
                "official_archive_first_baseline_model1_gap_viewer_packet_status": (
                    "official_archive_first_baseline_model1_gap_viewer_packet_ready_baseline_only"
                ),
                "first_baseline_candidate_id": "official_archive_baseline_001",
                "first_competition": "CASP16",
                "first_target_id": "T1210",
                "first_native_pdb_code": "9ENR",
                "selected_case_count": 11,
                "viewer_ready_count": 11,
                "viewer_blocked_count": 0,
                "catastrophic_case_count": 3,
                "large_case_count": 8,
                "copied_model_pair_count": 11,
                "native_reference_ready": True,
                "first_viewer_group_id": "999",
                "first_viewer_band": "catastrophic_model1_selection_gap",
                "first_viewer_delta": "70.000",
                "first_viewer_html": (
                    "casp17/official_archive_first_baseline_model1_gap_viewer_packet/"
                    "t1210_group_999_delta_70_000/viewer.html"
                ),
                "first_projection_svg": (
                    "casp17/official_archive_first_baseline_model1_gap_viewer_packet/"
                    "t1210_group_999_delta_70_000/projection.svg"
                ),
                "gallery_html": "casp17/official_archive_first_baseline_model1_gap_viewer_packet/gallery.html",
                "manifest_csv": "casp17/official_archive_first_baseline_model1_gap_viewer_packet/viewer_manifest.csv",
                "competitive_proof_eligible": False,
                "strict_blind_intake_policy": "do_not_import_as_internal_prediction",
                "next_action": (
                    "inspect high-gap overlay viewers and translate recurring model1-selection failures "
                    "into no-native accuracy-estimation features; keep strict-blind proof blocked"
                ),
            }
        },
    )
    _write_json(
        official_archive_first_baseline_model1_gap_feature_probe_json,
        {
            "summary": {
                "official_archive_first_baseline_model1_gap_feature_probe_status": (
                    "official_archive_first_baseline_model1_gap_feature_probe_ready_baseline_only"
                ),
                "first_baseline_candidate_id": "official_archive_baseline_001",
                "first_competition": "CASP16",
                "first_target_id": "T1210",
                "first_native_pdb_code": "9ENR",
                "selected_case_count": 11,
                "feature_ready_count": 11,
                "feature_blocked_count": 0,
                "matrix_row_count": 22,
                "supports_best_top5_count": 4,
                "supports_model1_count": 1,
                "ambiguous_count": 6,
                "supports_best_top5_rate": "0.364",
                "catastrophic_case_count": 3,
                "large_case_count": 8,
                "first_signal_group_id": "999",
                "first_signal": "supports_best_top5",
                "first_model1_geometry_risk_score": "122.500",
                "first_best_top5_geometry_risk_score": "7.500",
                "first_risk_delta_model1_minus_best": "115.000",
                "feature_probe_csv": "casp17/official_archive_first_baseline_model1_gap_feature_probe/feature_probe.csv",
                "pair_feature_matrix_csv": (
                    "casp17/official_archive_first_baseline_model1_gap_feature_probe/"
                    "pair_feature_matrix.csv"
                ),
                "competitive_proof_eligible": False,
                "strict_blind_intake_policy": "do_not_import_as_internal_prediction",
                "next_action": (
                    "use native-free feature signals to tune model1 selection calibration, then repeat on "
                    "strict-blind eligible internal predictions only"
                ),
            }
        },
    )
    _write_json(
        official_archive_first_baseline_model1_gap_consensus_probe_json,
        {
            "summary": {
                "official_archive_first_baseline_model1_gap_consensus_probe_status": (
                    "official_archive_first_baseline_model1_gap_consensus_probe_ready_baseline_only"
                ),
                "first_baseline_candidate_id": "official_archive_baseline_001",
                "first_competition": "CASP16",
                "first_target_id": "T1210",
                "first_native_pdb_code": "9ENR",
                "selected_case_count": 11,
                "consensus_ready_count": 11,
                "consensus_blocked_count": 0,
                "pairwise_row_count": 110,
                "supports_best_top5_count": 5,
                "supports_model1_count": 2,
                "ambiguous_count": 4,
                "supports_best_top5_rate": "0.455",
                "consensus_top_matches_best_count": 3,
                "consensus_top_matches_model1_count": 2,
                "catastrophic_case_count": 3,
                "large_case_count": 8,
                "first_signal_group_id": "999",
                "first_signal": "supports_best_top5",
                "first_model1_consensus_rank": "5",
                "first_best_top5_consensus_rank": "1",
                "first_consensus_top_model_id": "T1210TS999_4",
                "first_consensus_margin_model1_minus_best": "12.345",
                "consensus_probe_csv": "casp17/official_archive_first_baseline_model1_gap_consensus_probe/consensus_probe.csv",
                "pairwise_consensus_matrix_csv": (
                    "casp17/official_archive_first_baseline_model1_gap_consensus_probe/"
                    "pairwise_consensus_matrix.csv"
                ),
                "competitive_proof_eligible": False,
                "strict_blind_intake_policy": "do_not_import_as_internal_prediction",
                "next_action": (
                    "combine consensus-rank, diversity, and confidence features into a no-native model1 "
                    "selector; repeat only on strict-blind eligible internal predictions before competitive claims"
                ),
            }
        },
    )
    _write_json(
        official_archive_first_baseline_model1_gap_combined_selector_ledger_json,
        {
            "summary": {
                "official_archive_first_baseline_model1_gap_combined_selector_ledger_status": (
                    "official_archive_first_baseline_model1_gap_combined_selector_ledger_ready_baseline_only"
                ),
                "first_baseline_candidate_id": "official_archive_baseline_001",
                "first_competition": "CASP16",
                "first_target_id": "T1210",
                "first_native_pdb_code": "9ENR",
                "selected_case_count": 11,
                "selector_ready_count": 11,
                "selector_blocked_count": 0,
                "promote_best_top5_count": 5,
                "retain_model1_count": 5,
                "hold_manual_review_count": 1,
                "corrected_model1_failure_count": 5,
                "retained_model1_failure_count": 5,
                "manual_hold_model1_failure_count": 1,
                "false_positive_demote_count": 0,
                "baseline_capture_rate": "0.455",
                "baseline_non_capture_rate": "0.545",
                "catastrophic_case_count": 3,
                "large_case_count": 8,
                "first_selector_group_id": "999",
                "first_selector_decision": "promote_best_top5",
                "first_selected_model_id": "T1210TS999_4",
                "first_baseline_result": "corrected_model1_failure_baseline_proxy",
                "combined_selector_csv": (
                    "casp17/official_archive_first_baseline_model1_gap_combined_selector_ledger/"
                    "combined_selector_ledger.csv"
                ),
                "competitive_proof_eligible": False,
                "strict_blind_intake_policy": "do_not_import_as_internal_prediction",
                "next_action": (
                    "apply this conservative combined selector design to external CASP17 MassiveFold model1 "
                    "freeze ledgers, then repeat on strict-blind eligible internal predictions before competitive claims"
                ),
            }
        },
    )
    _write_json(
        strict_blind_first_slot_source_bridge_json,
        {
            "summary": {
                "source_bridge_status": "first_slot_source_bridge_internal_prediction_required",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "required_scope": "monomer",
                "official_candidate_count": 24,
                "official_ready_candidate_count": 24,
                "native_authority_bridge_ready_count": 2,
                "official_prediction_baseline_only_count": 24,
                "strict_blind_import_blocked_count": 24,
                "operator_only_field_count": 6,
                "internal_prediction_blocked_count": 1,
                "auto_apply_allowed_count": 0,
                "bridge_row_count": 9,
                "first_candidate_competition": "CASP16",
                "first_candidate_target_id": "T1210",
                "first_candidate_native_pdb_code": "9enr",
                "first_blocker": "internal_pre_native_prediction_pdb_required",
                "first_next_action": (
                    "provide a pre-native internal prediction PDB; use official archive files only for "
                    "native authority/baseline review"
                ),
                "bridge_folder": (
                    "casp17/historical_seed_strict_blind_first_slot_source_bridge/"
                    "hist_REQUIRED_MONOMER_001"
                ),
            }
        },
    )
    _write_json(
        strict_blind_internal_prediction_source_audit_json,
        {
            "summary": {
                "internal_prediction_source_audit_status": "internal_prediction_source_missing_for_first_slot",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "required_scope": "monomer",
                "first_open_field": "prediction_pdb",
                "local_candidate_count": 17,
                "local_strict_blind_eligible_count": 0,
                "source_route_count": 17,
                "source_route_allowed_count": 0,
                "official_baseline_candidate_count": 24,
                "official_strict_blind_blocked_count": 24,
                "native_authority_bridge_ready_count": 2,
                "internal_prediction_blocked_count": 1,
                "allowed_internal_source_count": 0,
                "template_count": 1,
                "row_count": 6,
                "first_blocker": "pre_native_internal_prediction_pdb_missing",
                "internal_source_manifest_template": (
                    "casp17/strict_blind_internal_prediction_source_audit/"
                    "hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv"
                ),
                "next_action": "fill internal prediction source manifest and place verified PDB",
            }
        },
    )
    _write_json(
        strict_blind_internal_candidate_filesystem_sweep_json,
        {
            "summary": {
                "filesystem_sweep_status": "strict_blind_filesystem_sweep_operator_review_required",
                "scan_root": ".",
                "scanned_structure_file_count": 9968,
                "atom_like_file_count": 9968,
                "verified_pre_native_internal_count": 0,
                "unknown_possible_internal_review_count": 4551,
                "current_casp17_or_review_only_count": 1810,
                "massivefold_external_baseline_only_count": 2895,
                "official_archive_baseline_only_count": 387,
                "native_or_reference_not_prediction_count": 257,
                "historical_seed_top5_post_native_review_only_count": 75,
                "strict_blind_dropzone_unverified_count": 0,
                "source_gate_status": "awaiting_internal_prediction_source_gate_fields",
                "source_gate_first_blocker": "internal_source_id_missing_or_external",
                "first_unknown_sample_path": "archives/old_internal/candidate.pdb",
                "next_action": "review unknown_possible_internal_review samples",
            }
        },
    )
    _write_json(
        strict_blind_unknown_candidate_triage_json,
        {
            "summary": {
                "unknown_candidate_triage_status": (
                    "strict_blind_unknown_triage_internal_like_review_required"
                ),
                "unknown_possible_internal_review_count": 4551,
                "filesystem_sweep_unknown_count": 4551,
                "promotion_ready_count": 0,
                "internal_like_review_count": 166,
                "public_structure_count": 3962,
                "run_review_count": 406,
                "archive_review_count": 16,
                "data_other_count": 0,
                "tmp_misc_count": 1,
                "other_unclassified_count": 0,
                "source_gate_status": "awaiting_internal_prediction_source_gate_fields",
                "source_gate_first_blocker": "internal_source_id_missing_or_external",
                "first_internal_like_sample_path": (
                    "data/internal_structures/nightly/internal_candidate.pdb"
                ),
                "next_action": "start with internal_structure_archive_unverified rows",
            }
        },
    )
    _write_json(
        strict_blind_internal_like_source_review_json,
        {
            "summary": {
                "internal_like_source_review_status": "strict_blind_internal_like_source_review_all_post_native",
                "triage_internal_like_count": 166,
                "triage_count_match": "True",
                "internal_like_candidate_count": 166,
                "mapped_candidate_count": 166,
                "unmapped_candidate_count": 0,
                "pre_native_candidate_count": 0,
                "same_day_timestamp_required_count": 0,
                "post_native_blocked_count": 166,
                "prediction_date_missing_count": 0,
                "promotion_ready_count": 0,
                "target_count": 10,
                "target_all_post_native_count": 10,
                "target_pre_native_candidate_count": 0,
                "earliest_prediction_date": "2026-02-19",
                "latest_prediction_date": "2026-02-22",
                "first_blocked_candidate_path": (
                    "data/internal_structures/nightly/2026-02-19-run/internal_post_bba5_sample000_step00020.pdb"
                ),
                "first_blocked_target_id": "HIST_BBA5",
                "first_blocker": "prediction_not_before_native",
                "next_action": "treat these internal-like files as post-native blockers",
            }
        },
    )
    _write_json(
        strict_blind_internal_prediction_source_gate_json,
        {
            "summary": {
                "internal_prediction_source_gate_status": "awaiting_internal_prediction_source_gate_fields",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "required_scope": "monomer",
                "manifest_csv": (
                    "casp17/strict_blind_internal_prediction_source_audit/"
                    "hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv"
                ),
                "manifest_row_count": 1,
                "check_count": 16,
                "pass_count": 3,
                "blocked_count": 13,
                "manifest_prediction_pdb": "",
                "prediction_dropzone": (
                    "casp17/historical_seed_strict_blind_replacement_evidence_dropzones/"
                    "01_hist_required_monomer_001/prediction/replacement_prediction.pdb"
                ),
                "source_id": "",
                "first_blocked_check": "source_id_internal",
                "first_blocker": "internal_source_id_missing_or_external",
                "first_next_action": "set source_id to an internal pre-native prediction source",
            }
        },
    )
    _write_json(
        strict_blind_source_gate_field_board_json,
        {
            "summary": {
                "source_gate_field_board_status": "awaiting_source_gate_field_fills",
                "source_gate_status": "awaiting_internal_prediction_source_gate_fields",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "required_scope": "monomer",
                "manifest_csv": (
                    "casp17/strict_blind_internal_prediction_source_audit/"
                    "hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv"
                ),
                "source_gate_check_count": 16,
                "source_gate_pass_count": 3,
                "source_gate_blocked_count": 13,
                "field_action_count": 11,
                "manifest_value_action_count": 9,
                "file_action_count": 2,
                "manifest_file_action_count": 0,
                "blocked_check_covered_count": 13,
                "first_field_key": "source_id",
                "first_fill_kind": "manifest_value",
                "first_blockers": "internal_source_id_missing_or_external",
                "first_next_action": "set source_id to an internal pre-native prediction source",
                "board_dir": "casp17/strict_blind_source_gate_field_board/hist_REQUIRED_MONOMER_001",
            }
        },
    )
    _write_json(
        strict_blind_source_gate_operator_packet_json,
        {
            "summary": {
                "source_gate_operator_packet_status": "awaiting_source_gate_operator_values",
                "source_gate_field_board_status": "awaiting_source_gate_field_fills",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "required_scope": "monomer",
                "operator_csv": (
                    "casp17/strict_blind_source_gate_operator_packet/"
                    "hist_REQUIRED_MONOMER_001/source_gate_operator_values.csv"
                ),
                "manifest_csv": (
                    "casp17/strict_blind_internal_prediction_source_audit/"
                    "hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv"
                ),
                "field_action_count": 11,
                "operator_ready_count": 0,
                "operator_awaiting_count": 11,
                "manifest_patch_count": 9,
                "file_copy_count": 1,
                "derived_check_count": 1,
                "patch_ready_count": 0,
                "patch_awaiting_count": 11,
                "first_field_key": "source_id",
                "first_operator_status": "awaiting_operator_value",
                "first_next_action": "fill source_id",
                "packet_dir": "casp17/strict_blind_source_gate_operator_packet/hist_REQUIRED_MONOMER_001",
            }
        },
    )
    _write_json(
        strict_blind_source_gate_source_request_packet_json,
        {
            "summary": {
                "source_request_packet_status": "awaiting_pre_native_source_or_candidate_replacement",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "required_scope": "monomer",
                "source_route_board_status": "first_slot_requires_pre_native_monomer_source_or_replacement",
                "operator_packet_status": "awaiting_source_gate_operator_values",
                "operator_csv": (
                    "casp17/strict_blind_source_gate_operator_packet/"
                    "hist_REQUIRED_MONOMER_001/source_gate_operator_values.csv"
                ),
                "request_count": 17,
                "pre_native_source_required_count": 10,
                "candidate_replacement_required_count": 7,
                "operator_evidence_repair_required_count": 0,
                "operator_template_ready_count": 0,
                "operator_template_awaiting_count": 17,
                "operator_field_count": 187,
                "operator_field_filled_count": 0,
                "operator_field_missing_count": 187,
                "monomer_request_count": 10,
                "complex_request_count": 7,
                "first_request_id": "source_request_001",
                "first_request_target_id": "HIST_BBA5",
                "first_request_kind": "pre_native_prediction_source_required",
                "first_request_blocker": "prediction_not_before_native",
                "first_missing_operator_field": "source_id",
                "first_next_action": (
                    "attach a prediction artifact created before the authoritative native release date"
                ),
                "request_dir": "casp17/strict_blind_source_gate_source_request_packet",
            }
        },
    )
    _write_json(
        strict_blind_source_request_resolution_board_json,
        {
            "summary": {
                "source_request_resolution_board_status": "source_request_resolution_all_current_candidates_blocked",
                "source_request_packet_status": "awaiting_pre_native_source_or_candidate_replacement",
                "internal_like_source_review_status": "strict_blind_internal_like_source_review_all_post_native",
                "request_count": 17,
                "ready_for_source_gate_count": 0,
                "blocked_request_count": 17,
                "monomer_request_count": 10,
                "complex_request_count": 7,
                "all_post_native_monomer_request_count": 10,
                "candidate_replacement_required_count": 7,
                "pre_native_review_possible_count": 0,
                "chronology_review_missing_count": 0,
                "internal_like_post_native_candidate_count": 166,
                "internal_like_pre_native_candidate_count": 0,
                "first_blocked_request_id": "source_request_001",
                "first_blocked_target_id": "HIST_BBA5",
                "first_blocker": "all_internal_like_candidates_post_native",
                "next_action": "replace the 10 monomer requests with pre-native internal prediction artifacts",
            }
        },
    )
    _write_json(
        strict_blind_source_request_fulfillment_gate_json,
        {
            "summary": {
                "source_request_fulfillment_gate_status": "awaiting_source_request_operator_values",
                "source_request_packet_status": "awaiting_pre_native_source_or_candidate_replacement",
                "source_gate_operator_packet_status": "awaiting_source_gate_operator_values",
                "request_count": 17,
                "ready_request_count": 0,
                "blocked_request_count": 17,
                "operator_field_count": 187,
                "operator_field_filled_count": 0,
                "operator_field_missing_count": 187,
                "operator_evidence_ref_count": 0,
                "operator_evidence_ref_missing_count": 153,
                "prediction_pdb_valid_count": 0,
                "chronology_pass_count": 0,
                "internal_source_pass_count": 0,
                "first_blocked_request_id": "source_request_001",
                "first_blocked_target_id": "HIST_BBA5",
                "first_blocker": "source_id_missing",
                "first_next_action": "fill operator_value for source_id",
            }
        },
    )
    _write_json(
        strict_blind_source_request_operator_fill_worklist_json,
        {
            "summary": {
                "source_request_operator_fill_worklist_status": "awaiting_source_request_operator_values",
                "source_request_packet_status": "awaiting_pre_native_source_or_candidate_replacement",
                "fulfillment_gate_status": "awaiting_source_request_operator_values",
                "request_count": 17,
                "field_action_count": 187,
                "field_ready_count": 0,
                "operator_value_missing_count": 187,
                "operator_evidence_missing_count": 153,
                "candidate_replacement_field_count": 77,
                "first_fill_id": "source_request_operator_fill_001",
                "first_request_id": "source_request_001",
                "first_target_id": "HIST_BBA5",
                "first_field_key": "source_id",
                "first_blocker": "operator_value_missing",
                "first_next_action": "fill operator_value for source_id",
            }
        },
    )
    _write_json(
        strict_blind_source_request_operator_sync_plan_json,
        {
            "summary": {
                "source_request_operator_sync_plan_status": "awaiting_source_request_fulfillment",
                "sync_mode": "dry_run",
                "fulfillment_gate_status": "awaiting_source_request_operator_values",
                "ready_request_count": 0,
                "blocked_request_count": 17,
                "selected_request_id": "",
                "selected_target_id": "",
                "destination_operator_csv": (
                    "casp17/strict_blind_source_gate_operator_packet/"
                    "hist_REQUIRED_MONOMER_001/source_gate_operator_values.csv"
                ),
                "sync_action_count": 0,
                "ready_sync_action_count": 0,
                "blocked_sync_action_count": 1,
                "applied_sync_action_count": 0,
                "first_action_id": "source_request_sync_blocker_001",
                "first_blocker": "source_id_missing",
                "first_next_action": "fill operator_value for source_id",
            }
        },
    )
    _write_json(
        strict_blind_source_request_closure_board_json,
        {
            "summary": {
                "strict_blind_source_request_closure_board_status": (
                    "awaiting_strict_blind_source_request_closure"
                ),
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "required_scope": "monomer",
                "stage_count": 13,
                "ready_stage_count": 0,
                "blocked_stage_count": 13,
                "first_blocked_stage_id": "source_request_packet",
                "first_blocked_stage_status": "awaiting_pre_native_source_or_candidate_replacement",
                "first_blocker": "prediction_not_before_native",
                "next_action": "attach pre-native source",
                "source_request_status": "awaiting_pre_native_source_or_candidate_replacement",
                "fulfillment_gate_status": "awaiting_source_request_operator_values",
                "operator_fill_worklist_status": "awaiting_source_request_operator_values",
                "operator_sync_plan_status": "awaiting_source_request_fulfillment",
                "first_unlock_handoff_status": "awaiting_first_unlock_operator_values",
                "first_unlock_evidence_packet_status": "awaiting_first_unlock_evidence_collection",
                "first_unlock_evidence_review_gate_status": "awaiting_first_unlock_evidence_review",
                "first_unlock_evidence_sync_plan_status": "awaiting_first_unlock_evidence_review",
                "source_gate_operator_packet_status": "awaiting_source_gate_operator_values",
                "internal_prediction_source_gate_status": "awaiting_internal_prediction_source_gate_fields",
                "internal_prediction_apply_plan_status": "blocked_until_internal_prediction_source_gate_passes",
                "first_slot_closure_kit_status": "blocked_on_internal_prediction_source_gate",
                "batch_closure_runway_status": "blocked_on_first_slot_internal_prediction_source",
            }
        },
    )
    _write_json(
        strict_blind_first_source_request_pickup_json,
        {
            "summary": {
                "first_source_request_pickup_status": "first_source_request_requires_pre_native_source",
                "source_request_packet_status": "awaiting_pre_native_source_or_candidate_replacement",
                "source_route_board_status": "first_slot_requires_pre_native_monomer_source_or_replacement",
                "repair_feasibility_status": "first_slot_current_local_candidate_source_required",
                "evidence_packet_status": "awaiting_first_unlock_evidence_collection",
                "request_id": "source_request_001",
                "candidate_target_id": "HIST_BBA5",
                "candidate_scope": "monomer",
                "request_kind": "pre_native_prediction_source_required",
                "current_prediction_pdb": (
                    "data/internal_structures_refined/nightly/2026-02-19-ops-full-dashboard-r1/"
                    "visual_post_internal_post_bba5_sample000_step00020.pdb"
                ),
                "current_prediction_created_at": "2026-02-19",
                "native_release_date": "2004-05-13",
                "current_prediction_before_native": "False",
                "pickup_option_count": 3,
                "ready_option_count": 0,
                "blocked_option_count": 3,
                "in_scope_external_required_count": 10,
                "external_pre_native_artifact_required_target_count": 10,
                "pickup_folder": (
                    "casp17/strict_blind_first_source_request_pickup/"
                    "source_request_001_hist_bba5"
                ),
                "operator_decision_template_csv": (
                    "casp17/strict_blind_first_source_request_pickup/"
                    "source_request_001_hist_bba5/operator_decision_template.csv"
                ),
                "required_files_manifest_csv": (
                    "casp17/strict_blind_first_source_request_pickup/"
                    "source_request_001_hist_bba5/required_files_manifest.csv"
                ),
                "first_action_id": "first_source_pickup_001",
                "first_blocker": "prediction_not_before_native",
                "first_next_action": (
                    "attach a prediction artifact created before the authoritative native release date"
                ),
            }
        },
    )
    _write_json(
        strict_blind_first_unlock_handoff_json,
        {
            "summary": {
                "first_unlock_handoff_status": "awaiting_first_unlock_operator_values",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "request_id": "source_request_001",
                "candidate_target_id": "HIST_BBA5",
                "field_count": 11,
                "ready_field_count": 0,
                "blocked_field_count": 11,
                "first_blocked_field_key": "source_id",
                "first_blocker": "operator_value_missing",
                "first_next_action": "fill operator_value for source_id",
                "operator_template_csv": (
                    "casp17/strict_blind_source_gate_source_request_packet/"
                    "source_request_001/operator_source_values_template.csv"
                ),
                "prediction_dropzone": (
                    "casp17/historical_seed_strict_blind_replacement_evidence_dropzones/"
                    "01_hist_required_monomer_001/prediction/replacement_prediction.pdb"
                ),
                "current_prediction_created_at": "2026-02-19",
                "current_native_release_date": "2004-05-13",
            }
        },
    )
    _write_json(
        strict_blind_first_unlock_evidence_packet_json,
        {
            "summary": {
                "first_unlock_evidence_packet_status": "awaiting_first_unlock_evidence_collection",
                "request_id": "source_request_001",
                "candidate_target_id": "HIST_BBA5",
                "field_count": 11,
                "ready_field_count": 0,
                "open_field_count": 11,
                "evidence_stub_count": 11,
                "file_field_count": 2,
                "first_open_field": "source_id",
                "first_blocker": "operator_value_missing",
                "first_next_action": (
                    "collect evidence in "
                    "casp17/strict_blind_first_unlock_evidence_packet/"
                    "source_request_001_hist_bba5/field_evidence/source_id.md"
                    ", then fill operator_value and operator_evidence_ref for source_id"
                ),
                "packet_folder": (
                    "casp17/strict_blind_first_unlock_evidence_packet/"
                    "source_request_001_hist_bba5"
                ),
                "operator_evidence_template_csv": (
                    "casp17/strict_blind_first_unlock_evidence_packet/"
                    "source_request_001_hist_bba5/operator_evidence_template.csv"
                ),
                "dropzone_manifest_csv": (
                    "casp17/strict_blind_first_unlock_evidence_packet/"
                    "source_request_001_hist_bba5/dropzone_manifest.csv"
                ),
            }
        },
    )
    _write_json(
        strict_blind_first_unlock_evidence_review_gate_json,
        {
            "summary": {
                "first_unlock_evidence_review_gate_status": "awaiting_first_unlock_evidence_review",
                "request_id": "source_request_001",
                "candidate_target_id": "HIST_BBA5",
                "field_count": 11,
                "ready_field_count": 0,
                "blocked_field_count": 11,
                "template_operator_value_missing_count": 11,
                "template_operator_evidence_ref_missing_count": 0,
                "template_operator_clearance_missing_count": 11,
                "template_operator_id_missing_count": 11,
                "stub_present_count": 11,
                "stub_evidence_missing_count": 11,
                "policy_pass_count": 0,
                "policy_blocked_count": 11,
                "file_ready_count": 0,
                "file_blocked_count": 2,
                "first_blocked_field": "source_id",
                "first_blocker": "template_operator_value_missing",
                "first_next_action": (
                    "fill operator_value for source_id in operator_evidence_template.csv"
                ),
            }
        },
    )
    _write_json(
        strict_blind_first_slot_source_gate_blocker_ledger_json,
        {
            "summary": {
                "strict_blind_first_slot_source_gate_blocker_ledger_status": (
                    "awaiting_first_slot_source_gate_operator_evidence"
                ),
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "required_scope": "monomer",
                "ledger_field_count": 11,
                "ready_field_count": 0,
                "blocked_field_count": 11,
                "source_gate_pass_count": 3,
                "source_gate_blocked_count": 13,
                "source_gate_check_count": 16,
                "operator_ready_count": 0,
                "operator_awaiting_count": 11,
                "review_ready_field_count": 0,
                "review_blocked_field_count": 11,
                "file_ready_count": 0,
                "file_blocked_count": 2,
                "first_blocked_field": "source_id",
                "first_blocker": "template_operator_value_missing",
                "first_next_action": (
                    "fill operator_value for source_id in operator_evidence_template.csv"
                ),
            }
        },
    )
    _write_json(
        strict_blind_first_unlock_evidence_sync_plan_json,
        {
            "summary": {
                "first_unlock_evidence_sync_plan_status": "awaiting_first_unlock_evidence_review",
                "sync_mode": "dry_run",
                "review_gate_status": "awaiting_first_unlock_evidence_review",
                "request_id": "source_request_001",
                "candidate_target_id": "HIST_BBA5",
                "action_count": 11,
                "ready_action_count": 0,
                "blocked_action_count": 11,
                "applied_action_count": 0,
                "review_ready_field_count": 0,
                "review_blocked_field_count": 11,
                "destination_operator_csv": (
                    "casp17/strict_blind_source_gate_operator_packet/"
                    "hist_REQUIRED_MONOMER_001/source_gate_operator_values.csv"
                ),
                "first_action_id": "first_unlock_evidence_sync_001",
                "first_blocked_field": "source_id",
                "first_blocker": "template_operator_value_missing",
                "first_next_action": (
                    "complete first-unlock evidence review before syncing into the source gate"
                ),
            }
        },
    )
    _write_json(
        strict_blind_internal_prediction_source_apply_plan_json,
        {
            "summary": {
                "internal_prediction_source_apply_plan_status": (
                    "blocked_until_internal_prediction_source_gate_passes"
                ),
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "required_scope": "monomer",
                "gate_status": "awaiting_internal_prediction_source_gate_fields",
                "source_bridge_status": "first_slot_source_bridge_internal_prediction_required",
                "action_count": 16,
                "ready_action_count": 0,
                "blocked_action_count": 16,
                "file_action_count": 1,
                "operator_value_action_count": 10,
                "supplemental_evidence_action_count": 5,
                "first_blocked_action_id": "internal_prediction_apply_001",
                "first_blocker": "internal_prediction_source_gate_not_ready",
                "first_next_action": (
                    "copy verified internal prediction PDB into the first-slot prediction dropzone"
                ),
                "prediction_source": "",
                "prediction_destination": (
                    "casp17/historical_seed_strict_blind_replacement_evidence_dropzones/"
                    "01_hist_required_monomer_001/prediction/replacement_prediction.pdb"
                ),
            }
        },
    )
    _write_json(
        strict_blind_first_slot_closure_kit_json,
        {
            "summary": {
                "first_slot_closure_kit_status": "blocked_on_internal_prediction_source_gate",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "required_scope": "monomer",
                "step_count": 7,
                "step_ready_count": 0,
                "step_blocked_count": 7,
                "fill_item_count": 60,
                "source_gate_fill_count": 11,
                "source_request_fill_count": 17,
                "file_fill_count": 12,
                "operator_fill_count": 20,
                "source_gate_status": "awaiting_internal_prediction_source_gate_fields",
                "source_gate_operator_packet_status": "awaiting_source_gate_operator_values",
                "source_gate_operator_ready_count": 0,
                "source_gate_operator_awaiting_count": 11,
                "source_gate_operator_field_action_count": 11,
                "source_gate_operator_patch_ready_count": 0,
                "source_gate_operator_patch_awaiting_count": 11,
                "source_gate_operator_packet_csv": (
                    "casp17/strict_blind_source_gate_operator_packet/"
                    "hist_REQUIRED_MONOMER_001/source_gate_operator_values.csv"
                ),
                "source_gate_operator_packet_dir": (
                    "casp17/strict_blind_source_gate_operator_packet/hist_REQUIRED_MONOMER_001"
                ),
                "source_gate_source_request_packet_status": (
                    "awaiting_pre_native_source_or_candidate_replacement"
                ),
                "source_gate_source_request_count": 17,
                "source_gate_pre_native_source_request_count": 10,
                "source_gate_candidate_replacement_request_count": 7,
                "source_gate_operator_evidence_repair_request_count": 0,
                "apply_plan_status": "blocked_until_internal_prediction_source_gate_passes",
                "dropzone_status": "awaiting_strict_blind_evidence_files",
                "operator_gate_status": "awaiting_operator_values",
                "intake_preflight_status": "awaiting_operator_input",
                "first_blocked_step": "internal_prediction_source_gate",
                "first_blocker": "internal_source_id_missing_or_external",
                "first_next_action": "set source_id to an internal pre-native prediction source",
                "kit_folder": "casp17/strict_blind_first_slot_closure_kit/hist_REQUIRED_MONOMER_001",
            }
        },
    )
    _write_json(
        strict_blind_batch_closure_runway_json,
        {
            "summary": {
                "batch_closure_runway_status": "blocked_on_first_slot_internal_prediction_source",
                "slot_count": 40,
                "ready_slot_count": 0,
                "blocked_slot_count": 40,
                "source_gate_blocked_count": 1,
                "evidence_file_blocked_count": 39,
                "operator_value_blocked_count": 0,
                "intake_preflight_blocked_count": 0,
                "file_present_count": 0,
                "file_missing_count": 240,
                "operator_ready_count": 0,
                "operator_open_count": 400,
                "intake_filled_count": 0,
                "intake_missing_count": 640,
                "first_blocked_rank": 1,
                "first_blocked_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "first_blocking_stage": "internal_prediction_source_gate",
                "first_blocker": "internal_source_id_missing_or_external",
                "first_next_action": "set source_id to an internal pre-native prediction source",
            }
        },
    )
    _write_json(
        historical_seed_ablation_candidate_manifests_json,
        {
            "summary": {
                "ablation_candidate_status": "operator_ablation_review_required",
                "seed_row_count": 15,
                "candidate_manifest_count": 15,
                "candidate_row_count": 50,
                "selected_prediction_present_count": 15,
                "native_reference_present_count": 15,
                "baseline_candidate_present_count": 1,
                "operator_review_required_count": 15,
                "ready_for_operator_reference_count": 0,
                "layer_evidence_gap_count": 14,
                "blocked_core_candidate_input_count": 0,
                "first_open_target_id": "HIST_BBA5",
                "first_next_action": "attach real ablation layer evidence before setting ablation_manifest_ref",
            }
        },
    )
    _write_json(
        historical_seed_ablation_gap_repair_plan_json,
        {
            "summary": {
                "ablation_gap_repair_status": "ablation_gap_repair_required",
                "seed_row_count": 15,
                "repair_csv_count": 15,
                "real_ablation_candidate_count": 1,
                "missing_real_ablation_candidate_count": 19,
                "top5_review_decoy_count": 60,
                "top5_selected_copy_count": 15,
                "ready_for_operator_review_count": 1,
                "gap_repair_required_count": 14,
                "blocked_core_ablation_input_count": 0,
                "first_open_target_id": "HIST_BBA5",
                "first_next_action": (
                    "generate or attach true same-run/pre-minimization ablation layers; "
                    "keep top5 decoys as review-only context"
                ),
            }
        },
    )
    _write_json(
        historical_seed_top5_candidate_pools_json,
        {
            "summary": {
                "top5_candidate_pool_status": "top5_candidate_pool_ready_for_review",
                "seed_row_count": 15,
                "pool_count": 15,
                "candidate_model_count": 75,
                "complete_top5_pool_count": 15,
                "candidate_pool_gap_count": 0,
                "selected_source_present_count": 15,
                "generated_perturbation_count": 60,
                "blocked_selected_source_count": 0,
                "first_open_target_id": "HIST_BBA5",
                "first_next_action": (
                    "feed candidate pool into calibration ledger, then attach native oracle metrics "
                    "and internal scores"
                ),
            }
        },
    )
    _write_json(
        historical_seed_calibration_candidate_ledgers_json,
        {
            "summary": {
                "calibration_candidate_status": "operator_calibration_review_required",
                "seed_row_count": 15,
                "ledger_count": 15,
                "candidate_model_count": 76,
                "top5_candidate_pool_ready_count": 15,
                "selected_prediction_candidate_count": 15,
                "selected_model_rank_candidate_count": 15,
                "native_oracle_metric_available_count": 76,
                "internal_score_available_count": 76,
                "ready_for_calibration_fill_count": 0,
                "operator_review_required_count": 15,
                "blocked_selected_prediction_count": 0,
                "open_calibration_field_count": 90,
                "first_open_target_id": "HIST_BBA5",
                "first_next_action": "operator-fill calibration fields after no-leak provenance clearance",
            }
        },
    )
    _write_json(
        historical_seed_internal_score_candidates_json,
        {
            "summary": {
                "internal_score_candidate_status": "internal_score_candidates_ready_for_review",
                "seed_row_count": 15,
                "candidate_count": 76,
                "scored_candidate_count": 76,
                "top5_scored_ready_count": 15,
                "selected_score_candidate_count": 15,
                "blocked_candidate_input_count": 0,
                "first_open_target_id": "HIST_BBA5",
                "first_next_action": (
                    "feed internal scores into calibration ledger, then attach native oracle metrics"
                ),
            }
        },
    )
    _write_json(
        historical_seed_native_oracle_metric_candidates_json,
        {
            "summary": {
                "native_metric_candidate_status": "native_oracle_metric_candidates_ready_for_review",
                "seed_row_count": 15,
                "candidate_count": 76,
                "metric_candidate_count": 76,
                "top5_native_metric_ready_count": 15,
                "selected_native_metric_candidate_count": 15,
                "best_native_metric_candidate_count": 15,
                "blocked_candidate_input_count": 0,
                "first_open_target_id": "HIST_BBA5",
                "first_next_action": (
                    "feed native metrics into calibration ledger, then keep no-leak provenance and operator fill separate"
                ),
            }
        },
    )
    _write_json(
        historical_seed_clearance_to_identity_intake_sync_json,
        {
            "summary": {
                "seed_to_identity_sync_status": "waiting_on_cleared_seed_manifest",
                "apply_mode": "dry_run",
                "seed_manifest_row_count": 0,
                "eligible_seed_row_count": 0,
                "ready_to_sync_count": 0,
                "waiting_intake_count": 15,
                "blocked_count": 0,
                "applied_count": 0,
                "intake_row_count": 15,
                "first_next_action": "clear historical seed rows before syncing competitive identity intake",
            }
        },
    )
    _write_json(
        historical_seed_calibration_field_candidates_json,
        {
            "summary": {
                "calibration_field_candidate_status": "calibration_field_candidates_ready_for_operator_apply",
                "seed_row_count": 15,
                "field_candidate_count": 90,
                "proposed_field_count": 90,
                "already_matching_field_count": 0,
                "conflict_field_count": 0,
                "blocked_field_count": 0,
                "ready_to_apply_row_count": 15,
                "blocked_row_count": 0,
                "first_open_target_id": "HIST_BBA5",
                "first_next_action": (
                    "operator may apply calibration field candidates after no-leak provenance clearance"
                ),
            }
        },
    )
    _write_json(
        historical_seed_clearance_fill_candidate_packet_json,
        {
            "summary": {
                "clearance_fill_candidate_status": "operator_provenance_required_with_field_candidates",
                "seed_row_count": 15,
                "field_count": 255,
                "proposed_field_count": 91,
                "already_matching_field_count": 0,
                "operator_required_field_count": 150,
                "blocked_field_count": 14,
                "conflict_field_count": 0,
                "calibration_candidate_count": 90,
                "ablation_candidate_count": 1,
                "no_leak_manual_field_count": 150,
                "partial_candidate_row_count": 15,
                "full_clearance_ready_row_count": 0,
                "blocked_row_count": 15,
                "first_open_target_id": "HIST_BBA5",
                "first_next_action": (
                    "complete no-leak provenance and repair blocked ablation fields before any cleared manifest promotion"
                ),
            }
        },
    )
    _write_json(
        historical_seed_clearance_execution_board_json,
        {
            "summary": {
                "execution_board_status": "first_row_operator_no_leak_only",
                "seed_row_count": 15,
                "operator_no_leak_only_row_count": 1,
                "ablation_repair_required_row_count": 14,
                "operator_no_leak_field_count": 150,
                "proposed_field_count": 91,
                "calibration_candidate_count": 90,
                "ablation_candidate_count": 1,
                "blocked_ablation_field_count": 14,
                "first_execution_target_id": "HIST_CHIGNOLIN",
                "first_execution_status": "operator_no_leak_only",
                "first_execution_next_action": (
                    "fill operator no-leak evidence fields, then apply prepared calibration and ablation candidates"
                ),
                "first_execution_folder": (
                    "casp17/historical_seed_clearance_execution_board/02_hist_chignolin"
                ),
            }
        },
    )
    _write_json(
        historical_seed_first_clearance_operator_kit_json,
        {
            "summary": {
                "first_clearance_kit_status": "operator_no_leak_intake_ready",
                "target_id": "HIST_CHIGNOLIN",
                "benchmark_id": "hist_seed_chignolin",
                "scope": "monomer",
                "no_leak_field_count": 10,
                "ready_candidate_field_count": 7,
                "total_field_count": 17,
                "calibration_candidate_count": 6,
                "ablation_candidate_count": 1,
                "weak_hint_count": 2,
                "promotion_preview_status": "waiting_on_operator_no_leak_fields",
                "kit_folder": "casp17/historical_seed_first_clearance_operator_kit/HIST_CHIGNOLIN",
                "no_leak_operator_intake_csv": (
                    "casp17/historical_seed_first_clearance_operator_kit/"
                    "HIST_CHIGNOLIN/no_leak_operator_intake.csv"
                ),
                "next_action": (
                    "fill no_leak_operator_intake.csv with independent evidence, then review promotion_preview.csv"
                ),
            }
        },
    )
    _write_json(
        historical_seed_first_clearance_no_leak_gate_json,
        {
            "summary": {
                "first_clearance_no_leak_gate_status": "awaiting_operator_no_leak_values",
                "target_id": "HIST_CHIGNOLIN",
                "benchmark_id": "hist_seed_chignolin",
                "field_count": 10,
                "ready_field_count": 0,
                "blocked_field_count": 10,
                "operator_value_present_count": 0,
                "operator_value_missing_count": 10,
                "operator_clearance_present_count": 0,
                "operator_clearance_missing_count": 10,
                "policy_pass_count": 0,
                "policy_blocked_count": 10,
                "weak_hint_count": 2,
                "first_blocked_field": "no_leak_evidence_ref",
                "first_blocker": "operator_value_missing",
                "no_leak_operator_intake_csv": (
                    "casp17/historical_seed_first_clearance_operator_kit/"
                    "HIST_CHIGNOLIN/no_leak_operator_intake.csv"
                ),
                "next_action": "fill all operator no-leak gate fields",
            }
        },
    )
    _write_json(
        historical_seed_first_clearance_no_leak_evidence_packet_json,
        {
            "summary": {
                "first_clearance_no_leak_evidence_packet_status": (
                    "awaiting_first_clearance_no_leak_evidence_collection"
                ),
                "no_leak_gate_status": "awaiting_operator_no_leak_values",
                "target_id": "HIST_CHIGNOLIN",
                "benchmark_id": "hist_seed_chignolin",
                "packet_folder": "casp17/historical_seed_first_clearance_no_leak_evidence_packet/hist_chignolin",
                "action_md": (
                    "casp17/historical_seed_first_clearance_no_leak_evidence_packet/"
                    "hist_chignolin/ACTION.md"
                ),
                "operator_evidence_template_csv": (
                    "casp17/historical_seed_first_clearance_no_leak_evidence_packet/"
                    "hist_chignolin/operator_evidence_template.csv"
                ),
                "field_count": 10,
                "open_field_count": 10,
                "ready_field_count": 0,
                "evidence_stub_count": 10,
                "weak_hint_count": 2,
                "first_open_field": "no_leak_evidence_ref",
                "first_open_kind": "independent_no_leak_evidence",
                "first_blocker": "operator_value_missing",
                "next_action": "collect evidence for no_leak_evidence_ref",
            }
        },
    )
    _write_json(
        historical_seed_first_clearance_no_leak_evidence_review_gate_json,
        {
            "summary": {
                "first_clearance_no_leak_evidence_review_gate_status": (
                    "awaiting_first_clearance_no_leak_evidence_review"
                ),
                "target_id": "HIST_CHIGNOLIN",
                "benchmark_id": "hist_seed_chignolin",
                "operator_evidence_template_csv": (
                    "casp17/historical_seed_first_clearance_no_leak_evidence_packet/"
                    "hist_chignolin/operator_evidence_template.csv"
                ),
                "field_count": 10,
                "ready_field_count": 0,
                "blocked_field_count": 10,
                "template_operator_value_missing_count": 10,
                "template_operator_clearance_missing_count": 10,
                "template_operator_id_missing_count": 10,
                "stub_present_count": 10,
                "stub_evidence_missing_count": 10,
                "policy_pass_count": 0,
                "policy_blocked_count": 10,
                "first_blocked_field": "no_leak_evidence_ref",
                "first_blocker": "template_operator_value_missing",
                "next_action": "fill operator_value for no_leak_evidence_ref",
            }
        },
    )
    _write_json(
        historical_seed_first_clearance_no_leak_evidence_sync_plan_json,
        {
            "summary": {
                "first_clearance_no_leak_evidence_sync_plan_status": (
                    "awaiting_first_clearance_no_leak_evidence_review"
                ),
                "sync_mode": "dry_run",
                "review_gate_status": "awaiting_first_clearance_no_leak_evidence_review",
                "target_id": "HIST_CHIGNOLIN",
                "benchmark_id": "hist_seed_chignolin",
                "destination_intake_csv": (
                    "casp17/historical_seed_first_clearance_operator_kit/"
                    "HIST_CHIGNOLIN/no_leak_operator_intake.csv"
                ),
                "action_count": 10,
                "ready_action_count": 0,
                "blocked_action_count": 10,
                "applied_action_count": 0,
                "review_ready_field_count": 0,
                "review_blocked_field_count": 10,
                "first_blocked_field": "no_leak_evidence_ref",
                "first_blocker": "template_operator_value_missing",
                "next_action": "complete the no-leak evidence review gate before syncing into the intake",
            }
        },
    )
    _write_json(
        historical_seed_first_clearance_closure_board_json,
        {
            "summary": {
                "first_clearance_closure_board_status": "awaiting_first_clearance_no_leak_closure",
                "target_id": "HIST_CHIGNOLIN",
                "benchmark_id": "hist_seed_chignolin",
                "stage_count": 7,
                "ready_stage_count": 1,
                "blocked_stage_count": 6,
                "first_blocked_stage_id": "evidence_packet",
                "first_blocked_stage_status": "awaiting_first_clearance_no_leak_evidence_collection",
                "first_blocker": "operator_value_missing",
                "operator_kit_status": "operator_no_leak_intake_ready",
                "no_leak_gate_status": "awaiting_operator_no_leak_values",
                "evidence_packet_status": "awaiting_first_clearance_no_leak_evidence_collection",
                "evidence_review_gate_status": "awaiting_first_clearance_no_leak_evidence_review",
                "evidence_sync_plan_status": "awaiting_first_clearance_no_leak_evidence_review",
                "promotion_preview_status": "waiting_on_operator_no_leak_fields",
                "identity_sync_status": "waiting_on_cleared_seed_manifest",
                "next_action": "collect evidence for no_leak_evidence_ref",
            }
        },
    )
    _write_json(
        sidechain_native_benchmark_json,
        {
            "summary": {
                "sidechain_native_benchmark_status": "blocked",
                "manifest_csv": "runs/casp17_historical_benchmark_manifest_draft_from_operator_current.csv",
                "benchmark_count": 40,
                "pass_count": 0,
                "blocked_count": 40,
                "core_input_blocked_count": 40,
                "leakage_clearance_blocked_count": 40,
                "prediction_pdb_missing_count": 40,
                "native_pdb_missing_count": 40,
                "missing_core_file_count": 80,
                "exactness_blocked_count": 0,
                "metric_threshold_blocked_count": 0,
                "first_blocked_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "first_blocked_blockers": (
                    "leakage_clearance_missing_or_not_clear,native_pdb_missing,prediction_pdb_missing"
                ),
                "first_open_next_action": "place the cleared prediction/native PDB files for this benchmark row.",
                "workorder_action_count": 120,
                "open_workorder_action_count": 120,
                "workorder_json": "runs/casp17_sidechain_native_input_workorder_current.json",
                "workorder_md": "runs/casp17_sidechain_native_input_workorder_current.md",
            }
        },
    )
    _write_json(
        competitive_batch_json,
        {
            "summary": {
                "batch_status": "ready_for_fill",
                "row_count": 15,
                "copied_row_scaffold_count": 15,
                "missing_evidence_item_count": 490,
            }
        },
    )
    _write_json(
        competitive_row_fill_status_json,
        {
            "summary": {
                "row_fill_status": "awaiting_fill",
                "row_count": 15,
                "row_fill_filled_count": 0,
                "ready_for_operator_template_count": 0,
                "blocked_or_awaiting_count": 15,
                "missing_required_field_count": 480,
                "placeholder_field_count": 0,
                "missing_local_file_count": 180,
                "first_open_next_action": "copy row_fill_template.csv to row_fill.csv and replace placeholders",
            }
        },
    )
    _write_json(
        competitive_row_fill_worklist_json,
        {
            "summary": {
                "worklist_status": "open_actions",
                "row_count": 15,
                "guide_md_count": 15,
                "open_action_count": 450,
                "first_action_blocker": "target_id_placeholder",
                "first_action_recommended_action": "replace placeholder with a cleared historical non-current CASP target ID",
            }
        },
    )
    _write_json(
        competitive_evidence_dropzone_json,
        {
            "summary": {
                "dropzone_status": "open_actions",
                "dropzone_count": 15,
                "manifest_count": 15,
                "open_action_count": 450,
                "file_action_count": 180,
                "first_action_blocker": "target_id_placeholder",
                "first_action_note": "replace target_id in row_fill.csv",
            }
        },
    )
    _write_json(
        competitive_evidence_import_json,
        {
            "summary": {
                "import_status": "awaiting_import",
                "action_count": 450,
                "ready_for_apply_count": 0,
                "applied_count": 0,
                "already_imported_count": 0,
                "awaiting_import_file_count": 180,
                "awaiting_import_value_count": 270,
                "awaiting_clearance_count": 0,
                "awaiting_evidence_ref_count": 0,
                "blocked_count": 0,
                "first_open_status": "awaiting_import_file",
                "first_open_next_action": "enter source_path",
            }
        },
    )
    _write_json(
        competitive_evidence_round_json,
        {
            "summary": {
                "round_status": "awaiting_import",
                "stage_count": 5,
                "import_ready_for_apply_count": 0,
                "import_applied_count": 0,
                "import_awaiting_file_count": 180,
                "import_awaiting_value_count": 270,
                "intake_patch_candidate_count": 0,
                "patch_gate_ready_to_patch_count": 0,
                "apply_plan_planned_patch_count": 0,
                "first_next_action": "enter source_path",
            }
        },
    )
    _write_json(
        competitive_unlock_priority_json,
        {
            "summary": {
                "unlock_status": "identity_unlock_required",
                "phase_row_count": 60,
                "identity_open_action_count": 30,
                "target_id_open_count": 15,
                "file_actions_waiting_on_identity_count": 180,
                "first_open_phase": "identity_unlock",
                "first_open_next_action": "fill benchmark_id and target_id values first",
            }
        },
    )
    _write_json(
        competitive_identity_unlock_json,
        {
            "summary": {
                "identity_unlock_status": "awaiting_identity",
                "row_count": 15,
                "ready_for_import_count": 0,
                "awaiting_identity_count": 15,
                "blocked_identity_count": 0,
                "file_actions_unlocked_count": 0,
                "first_open_status": "awaiting_identity",
                "first_open_blockers": "proposed_benchmark_id_required,proposed_target_id_required",
            }
        },
    )
    _write_json(
        competitive_identity_round_json,
        {
            "summary": {
                "identity_round_status": "awaiting_identity",
                "row_count": 15,
                "identity_ready_for_import_count": 0,
                "identity_awaiting_count": 15,
                "identity_blocked_count": 0,
                "import_ready_for_apply_count": 0,
                "import_applied_count": 0,
                "identity_open_action_count": 30,
                "target_id_open_count": 15,
                "file_actions_waiting_on_identity_count": 180,
                "first_next_action": "fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance",
            }
        },
    )
    _write_json(
        competitive_identity_intake_json,
        {
            "summary": {
                "identity_intake_status": "awaiting_identity",
                "row_count": 15,
                "ready_for_identity_apply_count": 0,
                "awaiting_identity_count": 15,
                "blocked_identity_count": 0,
                "missing_field_count": 60,
                "file_actions_unlocked_count": 0,
                "first_open_next_action": "fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance",
            }
        },
    )
    _write_json(
        competitive_identity_sync_json,
        {
            "summary": {
                "identity_intake_sync_status": "awaiting_intake",
                "row_count": 15,
                "synced_count": 0,
                "ready_to_sync_count": 0,
                "awaiting_intake_count": 15,
                "blocked_count": 0,
                "missing_field_count": 60,
                "kit_mismatch_count": 0,
                "applied_sync_count": 0,
                "first_open_next_action": "fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance in the intake bundle",
            }
        },
    )
    _write_json(
        competitive_identity_candidate_json,
        {
            "summary": {
                "identity_candidate_status": "awaiting_candidate_sources",
                "row_count": 15,
                "ready_for_intake_count": 0,
                "awaiting_candidate_source_count": 15,
                "source_candidate_count": 55,
                "source_ready_candidate_count": 0,
                "source_blocked_candidate_count": 55,
                "applied_intake_count": 0,
                "operator_preflight_status": "blocked",
                "first_open_next_action": "populate the historical/operator manifest",
            }
        },
    )
    _write_json(
        competitive_identity_source_repair_json,
        {
            "summary": {
                "source_repair_status": "awaiting_target_identity",
                "source_candidate_count": 40,
                "source_ready_candidate_count": 0,
                "blocked_source_row_count": 40,
                "repair_action_count": 200,
                "target_identity_action_count": 40,
                "core_file_action_count": 40,
                "provenance_action_count": 40,
                "ablation_action_count": 40,
                "calibration_action_count": 40,
                "first_open_phase": "target_identity",
                "first_open_next_action": "replace REQUIRED target/benchmark placeholders",
            }
        },
    )
    _write_json(
        competitive_floor_unblock_map_json,
        {
            "summary": {
                "unblock_map_status": "awaiting_candidate_source_repair",
                "row_count": 15,
                "ready_for_intake_count": 0,
                "awaiting_candidate_source_count": 15,
                "source_candidate_count": 55,
                "source_ready_candidate_count": 0,
                "source_blocked_candidate_count": 55,
                "phase_open_counts": {
                    "target_identity": 15,
                    "core_files": 15,
                    "no_leak_provenance": 15,
                    "ablation_files": 15,
                    "calibration_values": 15,
                },
                "blocking_field_count": 285,
                "blocking_phase_count": 75,
                "first_open_dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                "first_open_phase": "target_identity",
                "first_open_next_action": "replace REQUIRED target/benchmark placeholders",
            }
        },
    )
    _write_json(
        competitive_target_identity_discovery_json,
        {
            "summary": {
                "target_identity_discovery_status": "review_required",
                "discovered_target_count": 19,
                "operator_review_target_count": 3,
                "open_current_target_count": 16,
                "closed_watchlist_target_count": 3,
                "unknown_local_target_count": 0,
                "synthetic_test_artifact_count": 0,
                "ready_for_identity_intake_count": 0,
                "first_open_next_action": "operator must confirm historical eligibility",
            }
        },
    )
    _write_json(
        competitive_target_identity_clearance_json,
        {
            "summary": {
                "clearance_queue_status": "awaiting_target_identity_clearance",
                "review_target_count": 3,
                "prediction_present_count": 3,
                "ts_prediction_present_count": 3,
                "native_present_count": 0,
                "provenance_cleared_count": 0,
                "ready_for_manifest_scaffold_count": 0,
                "awaiting_prediction_or_ts_count": 0,
                "awaiting_native_or_clearance_count": 3,
                "awaiting_no_leak_clearance_count": 0,
                "first_open_next_action": "provide a cleared native PDB and complete no-leak/operator provenance review",
            }
        },
    )
    _write_json(
        competitive_target_identity_clearance_workorder_json,
        {
            "summary": {
                "clearance_workorder_status": "awaiting_native_or_provenance",
                "workorder_count": 3,
                "ready_for_manifest_stub_count": 0,
                "native_and_provenance_required_count": 3,
                "native_required_count": 0,
                "provenance_required_count": 0,
                "native_dropzone_count": 3,
                "native_dropzone_readme_count": 3,
                "provenance_template_count": 3,
                "manifest_stub_count": 3,
                "provenance_template_preserved_count": 3,
                "provenance_template_refreshed_count": 0,
                "manifest_stub_preserved_count": 3,
                "manifest_stub_refreshed_count": 0,
                "first_open_next_action": "place a cleared native PDB and complete the no-leak provenance template",
            }
        },
    )
    _write_json(
        competitive_target_identity_clearance_operator_intake_json,
        {
            "summary": {
                "operator_intake_status": "awaiting_input",
                "row_count": 3,
                "ready_to_apply_count": 0,
                "awaiting_input_count": 3,
                "blocked_count": 0,
                "applied_count": 0,
                "native_copied_count": 0,
                "provenance_patched_count": 0,
                "first_open_next_action": "fill native_source_pdb, no_leak_evidence_ref, operator, dates, and true/false provenance controls",
            }
        },
    )
    _write_json(
        competitive_target_identity_clearance_native_candidate_json,
        {
            "summary": {
                "native_candidate_packet_status": "review_required",
                "candidate_row_count": 4,
                "operator_review_required_count": 0,
                "relaxed_review_count": 1,
                "blocked_candidate_count": 2,
                "current_target_collision_count": 2,
                "no_candidate_target_count": 1,
                "search_prepared_count": 0,
                "first_open_next_action": "inspect title/entities manually before considering as a native candidate",
            }
        },
    )
    _write_json(
        competitive_target_identity_clearance_adjudication_json,
        {
            "summary": {
                "adjudication_packet_status": "blocked_candidate_risk",
                "target_count": 3,
                "replacement_required_count": 2,
                "manual_native_search_required_count": 1,
                "operator_review_required_count": 0,
                "safe_to_apply_operator_intake_count": 0,
                "adjudication_md_count": 3,
                "first_open_next_action": "replace this clearance target or provide independent operator proof",
            }
        },
    )
    _write_json(
        competitive_target_identity_clearance_replacement_queue_json,
        {
            "summary": {
                "replacement_queue_status": "blocked_replacement_candidates",
                "replacement_required_target_count": 2,
                "candidate_row_count": 8,
                "ready_candidate_count": 0,
                "blocked_missing_prediction_count": 6,
                "blocked_current_collision_count": 1,
                "operator_source_repair_required_count": 1,
                "first_open_next_action": "generate or locate local internal prediction/TS artifacts",
            }
        },
    )
    _write_json(
        competitive_target_identity_clearance_replacement_source_repair_json,
        {
            "summary": {
                "replacement_source_repair_status": "awaiting_sequence",
                "candidate_count": 4,
                "source_ready_count": 0,
                "ready_for_prediction_count": 1,
                "ready_for_validation_scorecard_count": 1,
                "awaiting_sequence_count": 1,
                "blocked_cancelled_count": 1,
                "blocked_current_collision_count": 1,
                "source_repair_md_count": 4,
                "first_open_next_action": "provide reviewed FASTA before local prediction can be generated",
            }
        },
    )
    _write_json(
        competitive_target_identity_clearance_replacement_scorecard_json,
        {
            "summary": {
                "replacement_scorecard_status": "replacement_scorecard_blocked",
                "candidate_count": 4,
                "pass_count": 1,
                "blocked_count": 3,
                "scorecard_json_count": 1,
                "first_open_next_action": "repair replacement source evidence before clearance review",
            }
        },
    )
    _write_json(
        competitive_target_identity_clearance_replacement_workorder_json,
        {
            "summary": {
                "replacement_workorder_status": "partial_replacement_workorders_ready_for_operator_intake",
                "replacement_target_count": 2,
                "workorder_row_count": 2,
                "selected_workorder_count": 1,
                "duplicate_candidate_blocked_count": 1,
                "no_ready_candidate_blocked_count": 0,
                "native_dropzone_count": 1,
                "native_dropzone_readme_count": 1,
                "provenance_template_count": 1,
                "manifest_stub_count": 1,
                "first_open_next_action": "choose a different ready replacement candidate",
            }
        },
    )
    _write_json(
        competitive_floor_native_dropzone_registry_json,
        {
            "summary": {
                "native_dropzone_registry_status": "awaiting_native_files",
                "dropzone_count": 4,
                "primary_dropzone_count": 3,
                "replacement_dropzone_count": 1,
                "dropzone_readme_count": 4,
                "native_present_count": 0,
                "blocked_dropzone_count": 4,
                "unexpected_coordinate_count": 0,
                "coordinate_copy_count": 0,
                "proof_eligible_count": 0,
                "author_serialized_count": 0,
                "first_blocked_target_id": "H1319",
                "first_blocked_blockers": "native_pdb_missing",
                "first_blocked_next_action": "place the operator-cleared native PDB at the expected native_dropzone_pdb path",
            }
        },
    )
    _write_json(
        competitive_target_identity_clearance_replacement_workorder_audit_json,
        {
            "summary": {
                "clearance_workorder_audit_status": "blocked",
                "audit_target_count": 2,
                "audit_pass_count": 0,
                "audit_blocked_count": 2,
                "prediction_present_count": 2,
                "native_valid_count": 0,
                "provenance_ready_count": 0,
                "manifest_stub_ready_count": 0,
                "native_prediction_distinct_count": 0,
                "native_prediction_waiting_count": 2,
                "first_blocked_next_action": "place the cleared native PDB in the per-target native dropzone",
            }
        },
    )
    _write_json(
        competitive_target_identity_clearance_replacement_pickup_json,
        {
            "summary": {
                "replacement_pickup_status": "open_actions",
                "row_count": 2,
                "selected_count": 1,
                "ready_for_operator_intake_count": 0,
                "awaiting_operator_pickup_count": 1,
                "blocked_selection_count": 1,
                "native_missing_count": 1,
                "provenance_required_field_count": 11,
                "operator_action_count": 4,
                "first_open_next_action": "place the cleared native PDB in the native dropzone",
            }
        },
    )
    _write_json(
        competitive_target_identity_clearance_replacement_duplicate_resolution_json,
        {
            "summary": {
                "duplicate_resolution_status": "operator_decision_required",
                "duplicate_replace_target_count": 1,
                "candidate_row_count": 4,
                "safe_unique_ready_candidate_count": 0,
                "duplicate_ready_candidate_count": 1,
                "blocked_duplicate_count": 1,
                "blocked_cancelled_count": 1,
                "blocked_current_collision_count": 2,
                "blocked_missing_prediction_count": 3,
                "first_open_next_action": (
                    "choose a new non-colliding closed protein replacement target or explicitly approve duplicate "
                    "candidate reuse with no-leak rationale"
                ),
            }
        },
    )
    _write_json(
        competitive_target_identity_clearance_replacement_decision_bundle_json,
        {
            "summary": {
                "decision_bundle_status": "open_operator_decision",
                "decision_target_count": 1,
                "ready_decision_count": 0,
                "open_decision_count": 1,
                "decision_folder_count": 1,
                "candidate_resolution_csv_count": 1,
                "new_unique_template_count": 1,
                "duplicate_exception_template_count": 1,
                "candidate_row_count": 4,
                "safe_unique_ready_candidate_count": 0,
                "duplicate_ready_candidate_count": 1,
                "first_open_next_action": (
                    "fill the new unique candidate intake template or explicitly approve duplicate candidate reuse "
                    "with no-leak rationale, then rerun replacement workorders"
                ),
            }
        },
    )
    _write_json(
        competitive_target_identity_clearance_replacement_decision_preflight_json,
        {
            "summary": {
                "decision_preflight_status": "awaiting_operator_decision",
                "decision_row_count": 1,
                "ready_new_unique_count": 0,
                "ready_duplicate_exception_count": 0,
                "awaiting_operator_decision_count": 1,
                "conflict_count": 0,
                "new_unique_blocker_count": 1,
                "duplicate_exception_blocker_count": 1,
                "first_open_next_action": (
                    "fill either the new unique candidate intake or the duplicate reuse exception, then rerun this "
                    "preflight"
                ),
            }
        },
    )
    _write_json(
        competitive_target_identity_clearance_manifest_sync_json,
        {
            "summary": {
                "clearance_manifest_sync_status": "awaiting_provenance",
                "sync_row_count": 3,
                "ready_to_sync_count": 0,
                "awaiting_provenance_count": 3,
                "blocked_count": 0,
                "synced_count": 0,
                "changed_field_count": 0,
                "applied_field_count": 0,
                "first_open_next_action": "complete the no-leak provenance template before syncing the manifest stub",
            }
        },
    )
    _write_json(
        competitive_target_identity_clearance_workorder_audit_json,
        {
            "summary": {
                "clearance_workorder_audit_status": "blocked",
                "audit_target_count": 3,
                "audit_pass_count": 0,
                "audit_blocked_count": 3,
                "prediction_present_count": 3,
                "prediction_protein_atom_count": 3,
                "prediction_coordinate_valid_count": 3,
                "identity_discovery_blocked_count": 3,
                "identity_discovery_cleared_count": 0,
                "native_valid_count": 0,
                "native_protein_atom_count": 0,
                "native_coordinate_valid_count": 0,
                "provenance_ready_count": 0,
                "evidence_ref_present_count": 0,
                "evidence_ref_blocked_count": 3,
                "evidence_ref_waiting_count": 0,
                "evidence_ref_verified_count": 0,
                "evidence_ref_content_blocked_count": 0,
                "manifest_stub_ready_count": 0,
                "manifest_provenance_matched_count": 0,
                "manifest_provenance_mismatch_count": 0,
                "native_prediction_distinct_count": 0,
                "native_prediction_same_count": 0,
                "native_prediction_waiting_count": 3,
                "first_blocked_next_action": "place the cleared native PDB in the per-target native dropzone",
            }
        },
    )
    _write_json(
        competitive_target_identity_metric_runway_json,
        {
            "summary": {
                "metric_runway_status": (
                    "casp17_competitive_floor_target_identity_metric_runway_blocked_awaiting_native_provenance"
                ),
                "target_count": 3,
                "target_ready_count": 0,
                "target_blocked_count": 3,
                "complex_target_count": 3,
                "monomer_target_count": 0,
                "metric_requirement_count": 27,
                "prediction_present_count": 3,
                "native_present_count": 0,
                "provenance_ready_count": 0,
                "evidence_ref_ready_count": 0,
                "native_candidate_count": 5,
                "native_candidate_blocked_count": 4,
                "native_candidate_no_candidate_count": 1,
                "competitive_proof_eligible_count": 0,
                "author_serialized_count": 0,
                "first_target_id": "H1319",
                "first_blocked_target_id": "H1319",
                "first_blocker": "native_pdb_missing",
                "html_runway_path": "casp17/casp17_competitive_floor_target_identity_metric_runway_current.html",
                "next_action": "fill native/provenance workorders",
            }
        },
    )
    _write_json(
        competitive_floor_native_provenance_operator_packet_json,
        {
            "summary": {
                "operator_packet_status": (
                    "casp17_competitive_floor_native_provenance_operator_packet_open_actions"
                ),
                "target_count": 3,
                "target_open_count": 3,
                "target_ready_count": 0,
                "action_count": 12,
                "open_action_count": 12,
                "native_action_count": 3,
                "evidence_action_count": 3,
                "provenance_action_count": 3,
                "manifest_action_count": 3,
                "metric_requirement_count": 27,
                "prediction_present_count": 3,
                "native_present_count": 0,
                "provenance_ready_count": 0,
                "evidence_ref_ready_count": 0,
                "native_candidate_count": 5,
                "native_candidate_blocked_count": 4,
                "native_candidate_no_candidate_count": 1,
                "competitive_proof_eligible_count": 0,
                "author_serialized_count": 0,
                "first_target_id": "H1319",
                "first_open_target_id": "H1319",
                "html_packet_path": (
                    "casp17/casp17_competitive_floor_native_provenance_operator_packet_current.html"
                ),
                "next_action": "fill each target packet",
            }
        },
    )
    _write_json(
        competitive_floor_native_provenance_operator_packet_completion_audit_json,
        {
            "summary": {
                "operator_packet_completion_audit_status": (
                    "casp17_competitive_floor_native_provenance_operator_packet_completion_audit_pass"
                ),
                "target_count": 3,
                "target_pass_count": 3,
                "target_blocked_count": 0,
                "packet_folder_present_count": 3,
                "packet_readme_present_count": 3,
                "packet_manifest_present_count": 3,
                "actions_csv_present_count": 3,
                "native_candidates_csv_present_count": 3,
                "action_expected_row_count": 12,
                "action_csv_row_count": 12,
                "action_csv_mismatch_count": 0,
                "native_candidate_expected_row_count": 5,
                "native_candidate_csv_row_count": 5,
                "native_candidate_csv_mismatch_count": 0,
                "native_action_csv_count": 3,
                "evidence_action_csv_count": 3,
                "provenance_action_csv_count": 3,
                "manifest_action_csv_count": 3,
                "metric_requirement_count": 27,
                "prediction_present_count": 3,
                "ts_prediction_present_count": 3,
                "native_dropzone_path_present_count": 3,
                "native_file_present_count": 0,
                "provenance_template_present_count": 3,
                "manifest_stub_present_count": 3,
                "metric_runway_present_count": 3,
                "workorder_folder_present_count": 3,
                "packet_coordinate_copy_count": 0,
                "out_dir_coordinate_copy_count": 0,
                "competitive_proof_eligible_count": 0,
                "author_serialized_count": 0,
                "first_target_id": "H1319",
                "first_blocked_target_id": "",
                "html_audit_path": (
                    "casp17/casp17_competitive_floor_native_provenance_operator_packet_completion_audit_current.html"
                ),
                "next_action": "use the packet-file audit before native/provenance fill",
            }
        },
    )
    _write_json(
        competitive_floor_native_provenance_metric_unlock_bridge_json,
        {
            "summary": {
                "metric_unlock_bridge_status": (
                    "casp17_competitive_floor_native_provenance_metric_unlock_bridge_blocked_awaiting_operator_values"
                ),
                "target_count": 3,
                "target_ready_count": 0,
                "target_blocked_count": 3,
                "packet_pass_count": 3,
                "workorder_audit_pass_count": 0,
                "metric_runway_ready_count": 0,
                "metric_requirement_count": 27,
                "prediction_present_count": 3,
                "ts_prediction_present_count": 3,
                "native_dropzone_path_present_count": 3,
                "native_file_present_count": 0,
                "provenance_template_present_count": 3,
                "manifest_stub_present_count": 3,
                "metric_runway_present_count": 3,
                "workorder_present_count": 3,
                "packet_action_count": 12,
                "packet_native_action_count": 3,
                "packet_evidence_action_count": 3,
                "packet_provenance_action_count": 3,
                "packet_manifest_action_count": 3,
                "native_candidate_count": 5,
                "native_candidate_blocked_count": 4,
                "native_candidate_no_candidate_count": 1,
                "provenance_ready_count": 0,
                "evidence_ref_verified_count": 0,
                "identity_discovery_cleared_count": 0,
                "competitive_proof_eligible_count": 0,
                "author_serialized_count": 0,
                "first_target_id": "H1319",
                "first_blocked_target_id": "H1319",
                "first_blocker": "native_pdb_missing",
                "first_next_action": "place operator-cleared native PDB in the native dropzone",
                "html_bridge_path": (
                    "casp17/casp17_competitive_floor_native_provenance_metric_unlock_bridge_current.html"
                ),
                "next_action": "fill native/provenance values, then rerun audits",
            }
        },
    )
    _write_json(
        competitive_floor_first_native_provenance_unlock_kit_json,
        {
            "summary": {
                "first_unlock_kit_status": (
                    "casp17_competitive_floor_first_native_provenance_unlock_kit_ready_for_operator_fill"
                ),
                "target_count": 1,
                "target_id": "H1319",
                "target_name": "Human astrovirus VA1 capsid spike - antibody 7C8 complex",
                "required_field_count": 13,
                "required_action_count": 4,
                "action_bundle_action_count": 4,
                "packet_file_pass": True,
                "metric_runway_ready": False,
                "workorder_audit_pass": False,
                "prediction_present_count": 1,
                "ts_prediction_present_count": 1,
                "native_dropzone_path_present_count": 1,
                "native_file_present_count": 0,
                "provenance_template_present_count": 1,
                "manifest_stub_present_count": 1,
                "metric_runway_present_count": 1,
                "workorder_present_count": 1,
                "provenance_ready_count": 0,
                "evidence_ref_verified_count": 0,
                "identity_discovery_cleared_count": 0,
                "competitive_proof_eligible_count": 0,
                "author_serialized_count": 0,
                "coordinate_copy_count": 0,
                "kit_folder": (
                    "casp17/competitive_floor_first_native_provenance_unlock_kit/"
                    "H1319_Human_astrovirus_VA1_capsid_spike_antibody_7C8_complex"
                ),
                "first_blocker": "native_pdb_missing",
                "next_action": "place operator-cleared native PDB in the native dropzone",
            }
        },
    )
    _write_json(
        competitive_floor_batch_native_provenance_unlock_kit_json,
        {
            "summary": {
                "batch_unlock_kit_status": (
                    "casp17_competitive_floor_batch_native_provenance_unlock_kit_ready_for_operator_fill"
                ),
                "target_count": 3,
                "target_ready_for_operator_fill_count": 3,
                "target_blocked_count": 0,
                "target_ids": "H1319,H1321,H2324",
                "required_field_per_target_count": 13,
                "required_field_total_count": 39,
                "required_action_count": 12,
                "action_bundle_action_count": 12,
                "packet_file_pass_count": 3,
                "metric_runway_ready_count": 0,
                "workorder_audit_pass_count": 0,
                "prediction_present_count": 3,
                "ts_prediction_present_count": 3,
                "native_dropzone_path_present_count": 3,
                "native_file_present_count": 0,
                "provenance_template_present_count": 3,
                "manifest_stub_present_count": 3,
                "metric_runway_present_count": 3,
                "workorder_present_count": 3,
                "provenance_ready_count": 0,
                "evidence_ref_verified_count": 0,
                "identity_discovery_cleared_count": 0,
                "competitive_proof_eligible_count": 0,
                "author_serialized_count": 0,
                "coordinate_copy_count": 0,
                "batch_folder": "casp17/competitive_floor_batch_native_provenance_unlock_kit",
                "first_blocked_target_id": "H1319",
                "first_blocker": "native_pdb_missing",
                "next_action": "fill batch native/provenance values",
            }
        },
    )
    _write_json(
        competitive_floor_batch_native_provenance_unlock_kit_completion_audit_json,
        {
            "summary": {
                "batch_unlock_kit_completion_audit_status": (
                    "casp17_competitive_floor_batch_native_provenance_unlock_kit_completion_audit_pass"
                ),
                "target_count": 3,
                "target_pass_count": 3,
                "target_blocked_count": 0,
                "batch_file_present_count": 6,
                "batch_file_expected_count": 6,
                "batch_operator_fill_intake_expected_rows": 3,
                "batch_operator_fill_intake_csv_rows": 3,
                "batch_operator_fill_intake_row_mismatch_count": 0,
                "batch_required_actions_expected_rows": 12,
                "batch_required_actions_csv_rows": 12,
                "batch_required_actions_row_mismatch_count": 0,
                "target_folder_present_count": 3,
                "target_readme_present_count": 3,
                "target_manifest_present_count": 3,
                "target_operator_fill_intake_present_count": 3,
                "target_required_actions_present_count": 3,
                "target_rerun_commands_present_count": 3,
                "target_operator_fill_intake_expected_rows": 3,
                "target_operator_fill_intake_csv_rows": 3,
                "target_operator_fill_intake_row_mismatch_count": 0,
                "target_required_actions_expected_rows": 12,
                "target_required_actions_csv_rows": 12,
                "target_required_actions_row_mismatch_count": 0,
                "coordinate_copy_count": 0,
                "target_coordinate_copy_count": 0,
                "native_file_present_count": 0,
                "provenance_ready_count": 0,
                "evidence_ref_verified_count": 0,
                "identity_discovery_cleared_count": 0,
                "competitive_proof_eligible_count": 0,
                "author_serialized_count": 0,
                "first_blocked_target_id": "",
                "first_blocker": "",
                "next_action": "fill batch native/provenance operator values",
            }
        },
    )
    _write_json(
        competitive_floor_batch_native_provenance_value_gate_json,
        {
            "summary": {
                "batch_native_provenance_value_gate_status": (
                    "casp17_competitive_floor_batch_native_provenance_value_gate_blocked_awaiting_operator_values"
                ),
                "target_count": 3,
                "target_ready_count": 0,
                "target_blocked_count": 3,
                "required_field_per_target_count": 13,
                "required_field_total_count": 39,
                "ready_value_count": 3,
                "blocked_value_count": 36,
                "native_source_ready_count": 0,
                "evidence_ref_ready_count": 0,
                "clearance_ready_count": 0,
                "date_ready_count": 0,
                "boolean_ready_count": 0,
                "coordinate_copy_count": 0,
                "target_coordinate_copy_count": 0,
                "competitive_proof_eligible_count": 0,
                "author_serialized_count": 0,
                "first_blocked_target_id": "H1319",
                "first_blocker": "native_source_pdb_required",
                "next_action": "Fill blocked batch native/provenance values, then rerun this value gate.",
            }
        },
    )
    _write_json(
        competitive_floor_batch_native_provenance_value_action_board_json,
        {
            "summary": {
                "batch_native_provenance_value_action_board_status": (
                    "casp17_competitive_floor_batch_native_provenance_value_action_board_open_actions"
                ),
                "target_count": 3,
                "target_with_open_action_count": 3,
                "target_ready_count": 0,
                "action_count": 36,
                "open_action_count": 36,
                "native_action_count": 3,
                "evidence_action_count": 3,
                "clearance_action_count": 6,
                "operator_action_count": 3,
                "date_action_count": 6,
                "boolean_action_count": 15,
                "review_action_count": 0,
                "coordinate_copy_count": 0,
                "competitive_proof_eligible_count": 0,
                "author_serialized_count": 0,
                "first_open_target_id": "H1319",
                "first_open_field": "native_source_pdb",
                "first_open_blocker": "native_source_pdb_required",
                "next_action": "Fill native_source_pdb in batch intake.",
            }
        },
    )
    _write_json(
        competitive_floor_batch_native_provenance_value_action_board_completion_audit_json,
        {
            "summary": {
                "batch_native_provenance_value_action_board_completion_audit_status": (
                    "casp17_competitive_floor_batch_native_provenance_value_action_board_completion_audit_pass"
                ),
                "target_count": 3,
                "target_pass_count": 3,
                "target_blocked_count": 0,
                "action_expected_count": 36,
                "action_board_json_rows": 36,
                "action_json_row_mismatch_count": 0,
                "target_folder_present_count": 3,
                "target_readme_present_count": 3,
                "target_value_actions_present_count": 3,
                "target_value_actions_expected_rows": 36,
                "target_value_actions_csv_rows": 36,
                "target_value_actions_row_mismatch_count": 0,
                "coordinate_copy_count": 0,
                "target_coordinate_copy_count": 0,
                "competitive_proof_eligible_count": 0,
                "author_serialized_count": 0,
                "first_blocked_target_id": "",
                "first_blocker": "",
                "next_action": "Fill the 36 operator values in the batch intake CSV, then rerun the value gate.",
            }
        },
    )
    _write_json(
        competitive_floor_batch_native_provenance_operator_fill_preflight_json,
        {
            "summary": {
                "batch_native_provenance_operator_fill_preflight_status": (
                    "casp17_competitive_floor_batch_native_provenance_operator_fill_preflight_ready_for_operator_fill"
                ),
                "target_count": 3,
                "target_ready_for_fill_count": 3,
                "target_blocked_count": 0,
                "open_action_count": 36,
                "native_action_count": 3,
                "evidence_action_count": 3,
                "clearance_action_count": 6,
                "operator_action_count": 3,
                "date_action_count": 6,
                "boolean_action_count": 15,
                "review_action_count": 0,
                "coordinate_copy_count": 0,
                "target_coordinate_copy_count": 0,
                "competitive_proof_eligible_count": 0,
                "author_serialized_count": 0,
                "first_ready_target_id": "H1319",
                "first_blocked_target_id": "",
                "first_blocker": "",
                "next_action": "Fill the target operator templates or batch intake CSV, then rerun the value gate.",
            }
        },
    )
    _write_json(
        competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_json,
        {
            "summary": {
                "batch_native_provenance_operator_fill_preflight_completion_audit_status": (
                    "casp17_competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_pass"
                ),
                "target_count": 3,
                "target_pass_count": 3,
                "target_blocked_count": 0,
                "root_manifest_present": 1,
                "target_folder_count": 3,
                "target_readme_count": 3,
                "target_operator_template_file_count": 3,
                "target_field_policy_file_count": 3,
                "operator_template_expected_rows": 3,
                "operator_template_csv_rows": 3,
                "operator_template_row_mismatch_count": 0,
                "field_policy_expected_rows": 36,
                "field_policy_csv_rows": 36,
                "field_policy_row_mismatch_count": 0,
                "coordinate_copy_count": 0,
                "target_coordinate_copy_count": 0,
                "competitive_proof_eligible_count": 0,
                "author_serialized_count": 0,
                "first_blocked_target_id": "",
                "first_blocker": "",
                "next_action": "Fill the target operator templates or batch intake CSV, then rerun the value gate.",
            }
        },
    )
    _write_json(
        competitive_target_identity_clearance_action_board_json,
        {
            "summary": {
                "action_board_status": "open_actions",
                "target_count": 3,
                "action_count": 12,
                "open_action_count": 12,
                "native_action_count": 3,
                "evidence_action_count": 3,
                "provenance_action_count": 3,
                "manifest_action_count": 3,
                "first_open_next_action": "place an operator-cleared native PDB in the native dropzone",
            }
        },
    )
    _write_json(
        competitive_target_identity_clearance_action_bundle_json,
        {
            "summary": {
                "action_bundle_status": "open_actions",
                "target_count": 3,
                "action_count": 12,
                "open_action_count": 12,
                "bundle_file_count": 24,
                "action_folder_count": 12,
                "native_action_count": 3,
                "evidence_action_count": 3,
                "provenance_action_count": 3,
                "manifest_action_count": 3,
                "first_open_action_md": (
                    "casp17/competitive_floor_target_identity_clearance_action_bundle/"
                    "H1001_Example/action_001_native_dropzone/ACTION.md"
                ),
            }
        },
    )
    _write_json(
        competitive_target_identity_clearance_promotion_json,
        {
            "summary": {
                "clearance_promotion_status": "blocked_by_audit",
                "promotion_row_count": 3,
                "promoted_manifest_count": 0,
                "blocked_count": 3,
                "ready_for_operator_manifest_import_count": 0,
                "audit_pass_count": 0,
                "manifest_ready_count": 0,
                "first_open_next_action": "clear the blocked audit rows before manifest promotion",
            }
        },
    )
    _write_json(
        competitive_target_identity_clearance_intake_staging_json,
        {
            "summary": {
                "clearance_intake_staging_status": "waiting_on_promoted_manifest",
                "promoted_manifest_row_count": 0,
                "staged_identity_count": 0,
                "blocked_assignment_count": 0,
                "open_identity_intake_slot_count": 15,
                "candidate_intake_row_count": 15,
                "first_open_next_action": "wait for promoted clearance manifest rows",
            }
        },
    )
    _write_json(
        competitive_target_identity_clearance_candidate_intake_sync_json,
        {
            "summary": {
                "candidate_intake_sync_status": "waiting_on_staged_identity",
                "sync_row_count": 15,
                "ready_to_apply_count": 0,
                "waiting_on_staged_identity_count": 15,
                "blocked_count": 0,
                "applied_row_count": 0,
                "first_open_next_action": "wait for clearance intake staging to produce staged_for_operator_review rows",
            }
        },
    )
    _write_json(
        competitive_target_identity_clearance_cycle_json,
        {
            "summary": {
                "clearance_cycle_status": "awaiting_operator_intake",
                "stage_count": 8,
                "ready_stage_count": 0,
                "blocked_stage_count": 8,
                "operator_intake_status": "awaiting_input",
                "manifest_sync_status": "awaiting_provenance",
                "audit_status": "blocked",
                "promotion_status": "blocked_by_audit",
                "staged_identity_count": 0,
                "first_next_action": "fill native_source_pdb, no_leak_evidence_ref, operator, dates, and true/false provenance controls",
            }
        },
    )
    _write_json(
        competitive_identity_cycle_json,
        {
            "summary": {
                "identity_cycle_status": "awaiting_intake",
                "stage_count": 7,
                "ready_stage_count": 1,
                "blocked_stage_count": 6,
                "sync_status": "awaiting_intake",
                "sync_ready_to_sync_count": 0,
                "sync_awaiting_count": 15,
                "sync_missing_field_count": 60,
                "readiness_gate_status": "awaiting_identity",
                "first_next_action": "fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance",
            }
        },
    )
    _write_json(
        competitive_file_source_plan_json,
        {
            "summary": {
                "file_source_status": "waiting_on_identity",
                "file_action_count": 180,
                "waiting_on_identity_count": 180,
                "identity_blocked_file_count": 0,
                "awaiting_source_path_count": 0,
                "ready_for_import_count": 0,
                "already_imported_count": 0,
                "blocked_file_source_count": 0,
                "first_open_next_action": "fill and apply the compact identity unlock kit first",
                "first_open_blocker": "target_identity_required",
            }
        },
    )
    _write_json(
        competitive_value_entry_plan_json,
        {
            "summary": {
                "value_entry_status": "waiting_on_identity",
                "value_action_count": 270,
                "target_identity_action_count": 30,
                "provenance_action_count": 150,
                "calibration_action_count": 90,
                "waiting_on_identity_count": 270,
                "ready_from_identity_kit_count": 0,
                "awaiting_value_count": 0,
                "awaiting_clearance_count": 0,
                "awaiting_evidence_ref_count": 0,
                "ready_for_import_count": 0,
                "blocked_value_count": 0,
                "first_open_next_action": "fill and apply the compact identity unlock kit first",
                "first_open_blocker": "target_identity_required",
            }
        },
    )
    _write_json(
        competitive_execution_board_json,
        {
            "summary": {
                "execution_board_status": "awaiting_identity",
                "row_count": 15,
                "awaiting_identity_row_count": 15,
                "ready_for_identity_apply_row_count": 0,
                "awaiting_file_source_row_count": 0,
                "awaiting_value_row_count": 0,
                "ready_for_evidence_import_row_count": 0,
                "blocked_row_count": 0,
                "total_file_action_count": 180,
                "total_value_action_count": 270,
                "total_ready_action_count": 0,
                "total_blocked_action_count": 450,
                "first_open_status": "awaiting_identity",
                "first_open_next_action": "fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance",
            }
        },
    )
    _write_json(
        competitive_readiness_gate_json,
        {
            "summary": {
                "readiness_gate_status": "awaiting_identity",
                "gate_count": 6,
                "pass_count": 0,
                "blocked_gate_count": 6,
                "first_blocked_gate_id": "identity_gate",
                "first_blocked_status": "awaiting_identity",
                "first_blocked_next_action": "fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance",
            }
        },
    )
    _write_json(
        competitive_value_ledger_json,
        {
            "summary": {
                "value_ledger_status": "awaiting_values",
                "ledger_count": 15,
                "action_count": 270,
                "ready_for_intake_count": 0,
                "awaiting_value_count": 270,
                "awaiting_clearance_count": 0,
                "awaiting_evidence_ref_count": 0,
                "blocked_count": 0,
                "first_open_status": "awaiting_value",
                "first_open_next_action": "enter the cleared historical target_id",
            }
        },
    )
    _write_json(
        competitive_evidence_intake_json,
        {
            "summary": {
                "intake_status": "awaiting_evidence",
                "action_count": 450,
                "patch_candidate_count": 0,
                "row_fill_file_present_count": 0,
                "field_present_count": 0,
                "awaiting_dropzone_file_count": 180,
                "awaiting_operator_value_count": 270,
                "ambiguous_file_candidate_count": 0,
                "row_fill_blocked_count": 0,
                "first_open_status": "awaiting_operator_value",
                "first_open_next_action": "fill benchmark_id in row_fill.csv",
            }
        },
    )
    _write_json(
        competitive_patch_gate_json,
        {
            "summary": {
                "patch_gate_status": "awaiting_evidence",
                "action_count": 450,
                "ready_to_patch_count": 0,
                "awaiting_evidence_count": 450,
                "conflict_count": 0,
                "blocked_count": 0,
                "first_open_status": "awaiting_evidence",
                "first_open_next_action": "provide the missing cleared evidence",
            }
        },
    )
    _write_json(
        competitive_apply_plan_json,
        {
            "summary": {
                "apply_plan_status": "awaiting_evidence",
                "action_count": 450,
                "planned_patch_count": 0,
                "awaiting_evidence_count": 450,
                "blocked_count": 0,
                "applied_count": 0,
                "first_open_status": "awaiting_evidence",
                "first_open_next_action": "wait for cleared evidence",
            }
        },
    )
    _write_json(
        competitive_operator_template_json,
        {
            "summary": {
                "template_status": "blocked",
                "row_count": 15,
                "ready_for_preflight_count": 0,
                "blocked_count": 15,
                "row_fill_candidate_count": 0,
                "missing_file_count": 180,
                "placeholder_file_path_count": 180,
                "provenance_blocker_count": 150,
                "calibration_blocker_count": 90,
            }
        },
    )
    _write_json(
        competitive_operator_preflight_json,
        {
            "summary": {
                "operator_preflight_status": "blocked",
                "row_count": 15,
                "ready_count": 0,
                "blocked_count": 15,
                "first_blocked_blockers": "placeholder_target_id",
            }
        },
    )
    _write_json(
        bundle_json,
        {"summary": {"bundle_status": "ready", "artifact_count": 3, "missing_bundle_count": 0}},
    )

    args = mod.parse_args(
        [
            "--target-model-folders-json",
            str(target_json),
            "--target-object-folder-audit-json",
            str(target_object_folder_audit_json),
            "--target-object-viewer-smoke-json",
            str(target_object_viewer_smoke_json),
            "--target-object-model-review-json",
            str(target_object_model_review_json),
            "--protein-object-library-json",
            str(protein_object_library_json),
            "--protein-object-library-completion-audit-json",
            str(protein_object_library_completion_audit_json),
            "--protein-object-library-navigation-catalog-json",
            str(protein_object_library_navigation_catalog_json),
            "--molecular-object-atlas-json",
            str(molecular_object_atlas_json),
            "--molecular-object-atlas-completion-audit-json",
            str(molecular_object_atlas_completion_audit_json),
            "--molecular-object-metric-handoff-json",
            str(molecular_object_metric_handoff_json),
            "--molecular-object-metric-handoff-completion-audit-json",
            str(molecular_object_metric_handoff_completion_audit_json),
            "--raw-ranked-model-quarantine-json",
            str(raw_ranked_model_quarantine_json),
            "--current-submission-gate-json",
            str(current_submission_gate_json),
            "--current-sidechain-repack-json",
            str(current_sidechain_repack_json),
            "--current-submission-package-preflight-json",
            str(current_submission_package_preflight_json),
            "--current-submission-deadline-guard-json",
            str(current_submission_deadline_guard_json),
            "--current-upload-queue-json",
            str(current_upload_queue_json),
            "--current-upload-review-packet-json",
            str(current_upload_review_packet_json),
            "--current-prospective-strict-blind-escrow-json",
            str(current_prospective_strict_blind_escrow_json),
            "--win-gap-closure-json",
            str(closure_json),
            "--win-tier-goal-scorecard-json",
            str(goal_scorecard_json),
            "--historical-winner-normalized-bands-json",
            str(historical_winner_normalized_bands_json),
            "--historical-winner-normalized-unlock-plan-json",
            str(historical_winner_normalized_unlock_plan_json),
            "--win-tier-metric-surface-contract-json",
            str(win_tier_metric_surface_contract_json),
            "--win-tier-critical-path-board-json",
            str(win_tier_critical_path_board_json),
            "--organic-ligand-slot-candidate-packet-json",
            str(organic_ligand_slot_candidate_packet_json),
            "--organic-ligand-slot-promotion-action-board-json",
            str(organic_ligand_slot_promotion_action_board_json),
            "--active-scope-decision-json",
            str(active_scope_decision_json),
            "--organizer-notice-packet-json",
            str(organizer_notice_json),
            "--massivefold-external-pool-intake-json",
            str(massivefold_external_pool_intake_json),
            "--rna-hybrid-massivefold-priority-queue-json",
            str(rna_hybrid_massivefold_priority_queue_json),
            "--protein-complex-massivefold-priority-queue-json",
            str(protein_complex_massivefold_priority_queue_json),
            "--massivefold-acquisition-verification-board-json",
            str(massivefold_acquisition_verification_board_json),
            "--protein-complex-massivefold-acquisition-verification-board-json",
            str(protein_complex_massivefold_acquisition_verification_board_json),
            "--massivefold-model-pool-index-json",
            str(massivefold_model_pool_index_json),
            "--massivefold-representative-viewer-packet-json",
            str(massivefold_representative_viewer_packet_json),
            "--massivefold-representative-rerank-packet-json",
            str(massivefold_representative_rerank_packet_json),
            "--massivefold-rna-model-selection-coverage-json",
            str(massivefold_rna_model_selection_coverage_json),
            "--massivefold-rna-model-selection-input-packet-json",
            str(massivefold_rna_model_selection_input_packet_json),
            "--massivefold-rna-self-assessment-packet-json",
            str(massivefold_rna_self_assessment_packet_json),
            "--protein-complex-massivefold-model-selection-coverage-json",
            str(protein_complex_massivefold_model_selection_coverage_json),
            "--protein-complex-massivefold-self-assessment-packet-json",
            str(protein_complex_massivefold_self_assessment_packet_json),
            "--massivefold-model1-risk-queue-json",
            str(massivefold_model1_risk_queue_json),
            "--massivefold-critical-rerank-experiment-json",
            str(massivefold_critical_rerank_experiment_json),
            "--massivefold-critical-rerank-score-ledger-json",
            str(massivefold_critical_rerank_score_ledger_json),
            "--massivefold-model1-selection-calibration-gate-json",
            str(massivefold_model1_selection_calibration_gate_json),
            "--massivefold-model1-probe-worklist-json",
            str(massivefold_model1_probe_worklist_json),
            "--massivefold-model1-probe-outcome-json",
            str(massivefold_model1_probe_outcome_json),
            "--massivefold-model1-freeze-decision-packet-json",
            str(massivefold_model1_freeze_decision_packet_json),
            "--massivefold-model-selection-ledger-json",
            str(massivefold_model_selection_ledger_json),
            "--massivefold-model1-combined-selector-overlay-json",
            str(massivefold_model1_combined_selector_overlay_json),
            "--massivefold-freeze-ready-review-packet-json",
            str(massivefold_freeze_ready_review_packet_json),
            "--massivefold-hold-probe-review-packet-json",
            str(massivefold_hold_probe_review_packet_json),
            "--massivefold-probe-required-targeted-probe-packet-json",
            str(massivefold_probe_required_targeted_probe_packet_json),
            "--massivefold-post-probe-selector-decision-packet-json",
            str(massivefold_post_probe_selector_decision_packet_json),
            "--massivefold-watch-manual-action-packet-json",
            str(massivefold_watch_manual_action_packet_json),
            "--massivefold-freeze-candidate-format-preflight-json",
            str(massivefold_freeze_candidate_format_preflight_json),
            "--massivefold-freeze-candidate-escrow-json",
            str(massivefold_freeze_candidate_escrow_json),
            "--massivefold-freeze-candidate-protein-library-json",
            str(massivefold_freeze_candidate_protein_library_json),
            "--capri-round65-readiness-json",
            str(capri_round65_readiness_json),
            "--capri-round65-format-preflight-json",
            str(capri_round65_format_preflight_json),
            "--input-scaffold-json",
            str(scaffold_json),
            "--input-inventory-json",
            str(inventory_json),
            "--operator-dashboard-json",
            str(dashboard_json),
            "--historical-identity-seed-inventory-json",
            str(historical_identity_seed_inventory_json),
            "--historical-identity-seed-clearance-json",
            str(historical_identity_seed_clearance_json),
            "--historical-identity-seed-clearance-action-bundle-json",
            str(historical_identity_seed_clearance_action_bundle_json),
            "--historical-identity-seed-clearance-field-board-json",
            str(historical_identity_seed_clearance_field_board_json),
            "--historical-seed-no-leak-provenance-dossiers-json",
            str(historical_seed_no_leak_provenance_dossiers_json),
            "--historical-seed-no-leak-gap-repair-plan-json",
            str(historical_seed_no_leak_gap_repair_plan_json),
            "--historical-seed-current-target-prefill-json",
            str(historical_seed_current_target_prefill_json),
            "--historical-seed-native-authority-audit-json",
            str(historical_seed_native_authority_audit_json),
            "--historical-seed-native-replacement-candidates-json",
            str(historical_seed_native_replacement_candidates_json),
            "--historical-seed-complex-source-authority-candidates-json",
            str(historical_seed_complex_source_authority_candidates_json),
            "--historical-seed-chronology-candidate-board-json",
            str(historical_seed_chronology_candidate_board_json),
            "--historical-seed-authoritative-chronology-audit-json",
            str(historical_seed_authoritative_chronology_audit_json),
            "--historical-seed-lane-decision-packet-json",
            str(historical_seed_lane_decision_packet_json),
            "--historical-seed-strict-blind-replacement-queue-json",
            str(historical_seed_strict_blind_replacement_queue_json),
            "--historical-seed-strict-blind-replacement-intake-json",
            str(historical_seed_strict_blind_replacement_intake_json),
            "--historical-seed-strict-blind-replacement-evidence-dropzones-json",
            str(historical_seed_strict_blind_replacement_evidence_dropzones_json),
            "--historical-seed-strict-blind-replacement-evidence-action-board-json",
            str(historical_seed_strict_blind_replacement_evidence_action_board_json),
            "--historical-seed-strict-blind-replacement-evidence-quality-audit-json",
            str(historical_seed_strict_blind_replacement_evidence_quality_audit_json),
            "--historical-seed-strict-blind-replacement-evidence-import-gate-json",
            str(historical_seed_strict_blind_replacement_evidence_import_gate_json),
            "--historical-seed-strict-blind-replacement-operator-value-gate-json",
            str(historical_seed_strict_blind_replacement_operator_value_gate_json),
            "--historical-seed-strict-blind-replacement-operator-action-board-json",
            str(historical_seed_strict_blind_replacement_operator_action_board_json),
            "--historical-seed-strict-blind-replacement-promotion-gate-json",
            str(historical_seed_strict_blind_replacement_promotion_gate_json),
            "--historical-seed-strict-blind-replacement-cycle-json",
            str(historical_seed_strict_blind_replacement_cycle_json),
            "--historical-seed-strict-blind-replacement-first-slot-kit-json",
            str(historical_seed_strict_blind_replacement_first_slot_kit_json),
            "--historical-seed-strict-blind-replacement-first-slot-local-candidate-board-json",
            str(historical_seed_strict_blind_replacement_first_slot_local_candidate_board_json),
            "--historical-seed-strict-blind-replacement-first-slot-candidate-repair-board-json",
            str(historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_json),
            "--historical-seed-strict-blind-replacement-first-slot-repair-feasibility-board-json",
            str(historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_json),
            "--historical-seed-strict-blind-replacement-first-slot-source-route-board-json",
            str(historical_seed_strict_blind_replacement_first_slot_source_route_board_json),
            "--historical-seed-strict-blind-replacement-first-slot-official-archive-source-candidates-json",
            str(historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_json),
            "--historical-seed-official-archive-baseline-lane-json",
            str(historical_seed_official_archive_baseline_lane_json),
            "--official-archive-first-baseline-acquisition-audit-json",
            str(official_archive_first_baseline_acquisition_audit_json),
            "--official-archive-first-baseline-model-pool-json",
            str(official_archive_first_baseline_model_pool_json),
            "--official-archive-first-baseline-score-ledger-json",
            str(official_archive_first_baseline_score_ledger_json),
            "--official-archive-first-baseline-replay-comparison-json",
            str(official_archive_first_baseline_replay_comparison_json),
            "--official-archive-first-baseline-model1-gap-triage-json",
            str(official_archive_first_baseline_model1_gap_triage_json),
            "--official-archive-first-baseline-model1-gap-viewer-packet-json",
            str(official_archive_first_baseline_model1_gap_viewer_packet_json),
            "--official-archive-first-baseline-model1-gap-feature-probe-json",
            str(official_archive_first_baseline_model1_gap_feature_probe_json),
            "--official-archive-first-baseline-model1-gap-consensus-probe-json",
            str(official_archive_first_baseline_model1_gap_consensus_probe_json),
            "--official-archive-first-baseline-model1-gap-combined-selector-ledger-json",
            str(official_archive_first_baseline_model1_gap_combined_selector_ledger_json),
            "--strict-blind-first-slot-source-bridge-json",
            str(strict_blind_first_slot_source_bridge_json),
            "--strict-blind-internal-prediction-source-audit-json",
            str(strict_blind_internal_prediction_source_audit_json),
            "--strict-blind-internal-candidate-filesystem-sweep-json",
            str(strict_blind_internal_candidate_filesystem_sweep_json),
            "--strict-blind-unknown-candidate-triage-json",
            str(strict_blind_unknown_candidate_triage_json),
            "--strict-blind-internal-like-source-review-json",
            str(strict_blind_internal_like_source_review_json),
            "--strict-blind-internal-prediction-source-gate-json",
            str(strict_blind_internal_prediction_source_gate_json),
            "--strict-blind-source-gate-field-board-json",
            str(strict_blind_source_gate_field_board_json),
            "--strict-blind-source-gate-operator-packet-json",
            str(strict_blind_source_gate_operator_packet_json),
            "--strict-blind-source-gate-source-request-packet-json",
            str(strict_blind_source_gate_source_request_packet_json),
            "--strict-blind-source-request-resolution-board-json",
            str(strict_blind_source_request_resolution_board_json),
            "--strict-blind-source-request-fulfillment-gate-json",
            str(strict_blind_source_request_fulfillment_gate_json),
            "--strict-blind-source-request-operator-fill-worklist-json",
            str(strict_blind_source_request_operator_fill_worklist_json),
            "--strict-blind-source-request-operator-sync-plan-json",
            str(strict_blind_source_request_operator_sync_plan_json),
            "--strict-blind-source-request-closure-board-json",
            str(strict_blind_source_request_closure_board_json),
            "--strict-blind-first-source-request-pickup-json",
            str(strict_blind_first_source_request_pickup_json),
            "--strict-blind-first-unlock-handoff-json",
            str(strict_blind_first_unlock_handoff_json),
            "--strict-blind-first-unlock-evidence-packet-json",
            str(strict_blind_first_unlock_evidence_packet_json),
            "--strict-blind-first-unlock-evidence-review-gate-json",
            str(strict_blind_first_unlock_evidence_review_gate_json),
            "--strict-blind-first-slot-source-gate-blocker-ledger-json",
            str(strict_blind_first_slot_source_gate_blocker_ledger_json),
            "--strict-blind-first-unlock-evidence-sync-plan-json",
            str(strict_blind_first_unlock_evidence_sync_plan_json),
            "--strict-blind-internal-prediction-source-apply-plan-json",
            str(strict_blind_internal_prediction_source_apply_plan_json),
            "--strict-blind-first-slot-closure-kit-json",
            str(strict_blind_first_slot_closure_kit_json),
            "--strict-blind-batch-closure-runway-json",
            str(strict_blind_batch_closure_runway_json),
            "--historical-seed-ablation-candidate-manifests-json",
            str(historical_seed_ablation_candidate_manifests_json),
            "--historical-seed-ablation-gap-repair-plan-json",
            str(historical_seed_ablation_gap_repair_plan_json),
            "--historical-seed-top5-candidate-pools-json",
            str(historical_seed_top5_candidate_pools_json),
            "--historical-seed-internal-score-candidates-json",
            str(historical_seed_internal_score_candidates_json),
            "--historical-seed-native-oracle-metric-candidates-json",
            str(historical_seed_native_oracle_metric_candidates_json),
            "--historical-seed-calibration-candidate-ledgers-json",
            str(historical_seed_calibration_candidate_ledgers_json),
            "--historical-seed-calibration-field-candidates-json",
            str(historical_seed_calibration_field_candidates_json),
            "--historical-seed-clearance-fill-candidate-packet-json",
            str(historical_seed_clearance_fill_candidate_packet_json),
            "--historical-seed-clearance-execution-board-json",
            str(historical_seed_clearance_execution_board_json),
            "--historical-seed-first-clearance-operator-kit-json",
            str(historical_seed_first_clearance_operator_kit_json),
            "--historical-seed-first-clearance-no-leak-gate-json",
            str(historical_seed_first_clearance_no_leak_gate_json),
            "--historical-seed-first-clearance-no-leak-evidence-packet-json",
            str(historical_seed_first_clearance_no_leak_evidence_packet_json),
            "--historical-seed-first-clearance-no-leak-evidence-review-gate-json",
            str(historical_seed_first_clearance_no_leak_evidence_review_gate_json),
            "--historical-seed-first-clearance-no-leak-evidence-sync-plan-json",
            str(historical_seed_first_clearance_no_leak_evidence_sync_plan_json),
            "--historical-seed-first-clearance-closure-board-json",
            str(historical_seed_first_clearance_closure_board_json),
            "--historical-seed-clearance-to-identity-intake-sync-json",
            str(historical_seed_clearance_to_identity_intake_sync_json),
            "--sidechain-native-benchmark-json",
            str(sidechain_native_benchmark_json),
            "--competitive-batch-json",
            str(competitive_batch_json),
            "--competitive-row-fill-status-json",
            str(competitive_row_fill_status_json),
            "--competitive-row-fill-worklist-json",
            str(competitive_row_fill_worklist_json),
            "--competitive-evidence-dropzone-json",
            str(competitive_evidence_dropzone_json),
            "--competitive-evidence-import-json",
            str(competitive_evidence_import_json),
            "--competitive-evidence-round-json",
            str(competitive_evidence_round_json),
            "--competitive-unlock-priority-json",
            str(competitive_unlock_priority_json),
            "--competitive-identity-unlock-kit-json",
            str(competitive_identity_unlock_json),
            "--competitive-identity-round-json",
            str(competitive_identity_round_json),
            "--competitive-identity-intake-json",
            str(competitive_identity_intake_json),
            "--competitive-identity-sync-json",
            str(competitive_identity_sync_json),
            "--competitive-identity-candidate-json",
            str(competitive_identity_candidate_json),
            "--competitive-identity-source-repair-json",
            str(competitive_identity_source_repair_json),
            "--competitive-floor-unblock-map-json",
            str(competitive_floor_unblock_map_json),
            "--competitive-target-identity-discovery-json",
            str(competitive_target_identity_discovery_json),
            "--competitive-target-identity-clearance-queue-json",
            str(competitive_target_identity_clearance_json),
            "--competitive-target-identity-clearance-workorder-json",
            str(competitive_target_identity_clearance_workorder_json),
            "--competitive-target-identity-clearance-operator-intake-json",
            str(competitive_target_identity_clearance_operator_intake_json),
            "--competitive-target-identity-clearance-native-candidate-json",
            str(competitive_target_identity_clearance_native_candidate_json),
            "--competitive-target-identity-clearance-adjudication-json",
            str(competitive_target_identity_clearance_adjudication_json),
            "--competitive-target-identity-clearance-replacement-queue-json",
            str(competitive_target_identity_clearance_replacement_queue_json),
            "--competitive-target-identity-clearance-replacement-source-repair-json",
            str(competitive_target_identity_clearance_replacement_source_repair_json),
            "--competitive-target-identity-clearance-replacement-scorecard-json",
            str(competitive_target_identity_clearance_replacement_scorecard_json),
            "--competitive-target-identity-clearance-replacement-workorder-json",
            str(competitive_target_identity_clearance_replacement_workorder_json),
            "--competitive-target-identity-clearance-replacement-workorder-audit-json",
            str(competitive_target_identity_clearance_replacement_workorder_audit_json),
            "--competitive-target-identity-clearance-replacement-pickup-json",
            str(competitive_target_identity_clearance_replacement_pickup_json),
            "--competitive-target-identity-clearance-replacement-duplicate-resolution-json",
            str(competitive_target_identity_clearance_replacement_duplicate_resolution_json),
            "--competitive-target-identity-clearance-replacement-decision-bundle-json",
            str(competitive_target_identity_clearance_replacement_decision_bundle_json),
            "--competitive-target-identity-clearance-replacement-decision-preflight-json",
            str(competitive_target_identity_clearance_replacement_decision_preflight_json),
            "--competitive-target-identity-clearance-manifest-sync-json",
            str(competitive_target_identity_clearance_manifest_sync_json),
            "--competitive-target-identity-clearance-workorder-audit-json",
            str(competitive_target_identity_clearance_workorder_audit_json),
            "--competitive-target-identity-metric-runway-json",
            str(competitive_target_identity_metric_runway_json),
            "--competitive-floor-native-dropzone-registry-json",
            str(competitive_floor_native_dropzone_registry_json),
            "--competitive-floor-native-provenance-operator-packet-json",
            str(competitive_floor_native_provenance_operator_packet_json),
            "--competitive-floor-native-provenance-operator-packet-completion-audit-json",
            str(competitive_floor_native_provenance_operator_packet_completion_audit_json),
            "--competitive-floor-native-provenance-metric-unlock-bridge-json",
            str(competitive_floor_native_provenance_metric_unlock_bridge_json),
            "--competitive-floor-first-native-provenance-unlock-kit-json",
            str(competitive_floor_first_native_provenance_unlock_kit_json),
            "--competitive-floor-batch-native-provenance-unlock-kit-json",
            str(competitive_floor_batch_native_provenance_unlock_kit_json),
            "--competitive-floor-batch-native-provenance-unlock-kit-completion-audit-json",
            str(competitive_floor_batch_native_provenance_unlock_kit_completion_audit_json),
            "--competitive-floor-batch-native-provenance-value-gate-json",
            str(competitive_floor_batch_native_provenance_value_gate_json),
            "--competitive-floor-batch-native-provenance-value-action-board-json",
            str(competitive_floor_batch_native_provenance_value_action_board_json),
            "--competitive-floor-batch-native-provenance-value-action-board-completion-audit-json",
            str(competitive_floor_batch_native_provenance_value_action_board_completion_audit_json),
            "--competitive-floor-batch-native-provenance-operator-fill-preflight-json",
            str(competitive_floor_batch_native_provenance_operator_fill_preflight_json),
            "--competitive-floor-batch-native-provenance-operator-fill-preflight-completion-audit-json",
            str(competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_json),
            "--competitive-target-identity-clearance-action-board-json",
            str(competitive_target_identity_clearance_action_board_json),
            "--competitive-target-identity-clearance-action-bundle-json",
            str(competitive_target_identity_clearance_action_bundle_json),
            "--competitive-target-identity-clearance-promotion-plan-json",
            str(competitive_target_identity_clearance_promotion_json),
            "--competitive-target-identity-clearance-intake-staging-json",
            str(competitive_target_identity_clearance_intake_staging_json),
            "--competitive-target-identity-clearance-candidate-intake-sync-json",
            str(competitive_target_identity_clearance_candidate_intake_sync_json),
            "--competitive-target-identity-clearance-cycle-json",
            str(competitive_target_identity_clearance_cycle_json),
            "--competitive-identity-cycle-json",
            str(competitive_identity_cycle_json),
            "--competitive-file-source-plan-json",
            str(competitive_file_source_plan_json),
            "--competitive-value-entry-plan-json",
            str(competitive_value_entry_plan_json),
            "--competitive-execution-board-json",
            str(competitive_execution_board_json),
            "--competitive-readiness-gate-json",
            str(competitive_readiness_gate_json),
            "--competitive-value-ledger-json",
            str(competitive_value_ledger_json),
            "--competitive-evidence-intake-json",
            str(competitive_evidence_intake_json),
            "--competitive-patch-gate-json",
            str(competitive_patch_gate_json),
            "--competitive-apply-plan-json",
            str(competitive_apply_plan_json),
            "--competitive-operator-template-json",
            str(competitive_operator_template_json),
            "--competitive-operator-preflight-json",
            str(competitive_operator_preflight_json),
            "--data-bundle-json",
            str(bundle_json),
            "--out-json",
            str(tmp_path / "index.json"),
            "--out-csv",
            str(tmp_path / "index.csv"),
            "--out-md",
            str(tmp_path / "WORKBENCH.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod._write_md(args.out_md, payload)
    workbench_md = Path(args.out_md).read_text(encoding="utf-8")

    assert payload["summary"]["workbench_status"] == "ready_for_operator_fill"
    assert "- goal objective addendum: `casp17/CASP17_WIN_TIER_GOAL.md`" in workbench_md
    assert "competitive proof `15-25 -> 85-90`" in workbench_md
    assert "leaderboard `top-5/top-3/top-1-2` by category" in workbench_md
    assert "active competition scope: `casp17_only`" in workbench_md
    assert "protein object library completion audit: `pass`" in workbench_md
    assert "proteins pass/blocked/total `2/0/2`" in workbench_md
    assert "protein object library navigation catalog: `protein_object_library_navigation_catalog_ready`" in workbench_md
    assert "readme/manifest links `2/2`" in workbench_md
    assert "CASP17 3D molecular object atlas: `casp17_3d_molecular_object_atlas_ready_review_only`" in workbench_md
    assert "proteins pass/blocked/total `5/0/5` objects pass/blocked/total `14/0/14`" in workbench_md
    assert "source objects current/massivefold `4/10`" in workbench_md
    assert "source proteins current/massivefold/overlap `2/4/1`" in workbench_md
    assert "links model/viewer/projection/top5/escrow `14/14/14/10/10`" in workbench_md
    assert "native/proof/author `0/0/0` first `H9002_Example_Fab_Complex` `current_chain_A`" in workbench_md
    assert (
        "CASP17 3D molecular object atlas completion audit: "
        "`casp17_3d_molecular_object_atlas_completion_audit_pass`"
    ) in workbench_md
    assert "proteins folder/readme/manifest/total `5/5/5/5`" in workbench_md
    assert "objects pass/blocked/total `14/0/14` source objects current/massivefold `4/10`" in workbench_md
    assert "object folder/readme/manifest `14/14/14`" in workbench_md
    assert "coordinate copies object/atlas `0/0` proof/author `0/0`" in workbench_md
    assert (
        "CASP17 3D molecular object metric handoff: "
        "`casp17_3d_molecular_object_metric_handoff_ready_review_only_ligand_gap`"
    ) in workbench_md
    assert "metric requirements `118` required metrics covered/total/missing `9/11/2`" in workbench_md
    assert "missing `LDDT-PLI,BiSyRMSD` families monomer/complex/rna/ligand `1/12/1/0`" in workbench_md
    assert (
        "CASP17 3D molecular object metric handoff completion audit: "
        "`casp17_3d_molecular_object_metric_handoff_completion_audit_pass`"
    ) in workbench_md
    assert "object files folder/manifest/csv/md `14/14/14/14`" in workbench_md
    assert "metric rows expected/csv/mismatch `118/118/0` evidence awaiting `14`" in workbench_md
    assert "coordinate copies object/out_dir `0/0` proof/author `0/0`" in workbench_md
    assert (
        "competitive native/provenance operator packet: "
        "`casp17_competitive_floor_native_provenance_operator_packet_open_actions`"
    ) in workbench_md
    assert "targets open/ready/total `3/0/3` actions open/total `12/12`" in workbench_md
    assert "lanes native/evidence/provenance/manifest `3/3/3/3` metric requirements `27`" in workbench_md
    assert (
        "competitive native/provenance operator packet completion audit: "
        "`casp17_competitive_floor_native_provenance_operator_packet_completion_audit_pass`"
    ) in workbench_md
    assert "targets pass/blocked/total `3/0/3`" in workbench_md
    assert "packet files folder/readme/manifest/actions/native-candidates `3/3/3/3/3`" in workbench_md
    assert "action rows expected/csv/mismatch `12/12/0`" in workbench_md
    assert "native candidates expected/csv/mismatch `5/5/0`" in workbench_md
    assert "inputs prediction/ts/native-path/native-file/provenance/manifest/runway/workorder `3/3/3/0/3/3/3/3`" in workbench_md
    assert "coordinate copies target/out-dir `0/0` proof/author `0/0`" in workbench_md
    assert (
        "competitive native/provenance metric unlock bridge: "
        "`casp17_competitive_floor_native_provenance_metric_unlock_bridge_blocked_awaiting_operator_values`"
    ) in workbench_md
    assert "targets ready/blocked/total `0/3/3` packet/workorder/runway ready `3/0/0`" in workbench_md
    assert "metric requirements `27` inputs prediction/ts/native-path/native-file/provenance-template/manifest/runway/workorder `3/3/3/0/3/3/3/3`" in workbench_md
    assert "actions native/evidence/provenance/manifest/total `3/3/3/3/12`" in workbench_md
    assert "native candidates blocked/no-candidate/total `4/1/5`" in workbench_md
    assert "provenance/evidence/identity `0/0/0` proof/author `0/0`" in workbench_md
    assert (
        "competitive first native/provenance unlock kit: "
        "`casp17_competitive_floor_first_native_provenance_unlock_kit_ready_for_operator_fill`"
    ) in workbench_md
    assert "target `H1319` fields/actions/bundle `13/4/4`" in workbench_md
    assert (
        "inputs prediction/ts/native-path/native-file/provenance/manifest/runway/workorder "
        "`1/1/1/0/1/1/1/1`"
    ) in workbench_md
    assert (
        "competitive batch native/provenance unlock kit: "
        "`casp17_competitive_floor_batch_native_provenance_unlock_kit_ready_for_operator_fill`"
    ) in workbench_md
    assert "targets ready/blocked/total `3/0/3` ids `H1319,H1321,H2324`" in workbench_md
    assert "fields per-target/total `13/39` actions required/bundle `12/12`" in workbench_md
    assert (
        "inputs prediction/ts/native-path/native-file/provenance/manifest/runway/workorder "
        "`3/3/3/0/3/3/3/3`"
    ) in workbench_md
    assert (
        "competitive batch native/provenance unlock kit completion audit: "
        "`casp17_competitive_floor_batch_native_provenance_unlock_kit_completion_audit_pass`"
    ) in workbench_md
    assert "targets pass/blocked/total `3/0/3` batch files `6/6`" in workbench_md
    assert "batch intake expected/csv/mismatch `3/3/0`" in workbench_md
    assert "batch actions expected/csv/mismatch `12/12/0`" in workbench_md
    assert "target files folder/readme/manifest/intake/actions/rerun `3/3/3/3/3/3`" in workbench_md
    assert "coordinate copies batch/target `0/0`" in workbench_md
    assert (
        "competitive batch native/provenance value gate: "
        "`casp17_competitive_floor_batch_native_provenance_value_gate_blocked_awaiting_operator_values`"
    ) in workbench_md
    assert "targets ready/blocked/total `0/3/3` fields per-target/total `13/39`" in workbench_md
    assert "values ready/blocked `3/36` native/evidence `0/0`" in workbench_md
    assert "clearance/date/boolean `0/0/0` coordinate copies batch/target `0/0`" in workbench_md
    assert "proof/author `0/0` first `H1319` `native_source_pdb_required`" in workbench_md
    assert (
        "competitive batch native/provenance value action board: "
        "`casp17_competitive_floor_batch_native_provenance_value_action_board_open_actions`"
    ) in workbench_md
    assert "targets open/ready/total `3/0/3` actions open/total `36/36`" in workbench_md
    assert "lanes native/evidence/clearance/operator/date/boolean/review `3/3/6/3/6/15/0`" in workbench_md
    assert "coordinate copies `0` proof/author `0/0` first `H1319` `native_source_pdb`" in workbench_md
    assert (
        "competitive batch native/provenance value action board completion audit: "
        "`casp17_competitive_floor_batch_native_provenance_value_action_board_completion_audit_pass`"
    ) in workbench_md
    assert "targets pass/blocked/total `3/0/3` actions expected/json/mismatch `36/36/0`" in workbench_md
    assert "target files folder/readme/actions `3/3/3`" in workbench_md
    assert "target rows expected/csv/mismatch `36/36/0` coordinate copies board/target `0/0`" in workbench_md
    assert (
        "competitive batch native/provenance operator fill preflight: "
        "`casp17_competitive_floor_batch_native_provenance_operator_fill_preflight_ready_for_operator_fill`"
    ) in workbench_md
    assert "targets ready/blocked/total `3/0/3` actions open `36`" in workbench_md
    assert "actions native/evidence/clearance/operator/date/boolean/review `3/3/6/3/6/15/0`" in workbench_md
    assert "coordinate copies preflight/target `0/0` proof/author `0/0` first `H1319` `-` `-`" in workbench_md
    assert (
        "competitive batch native/provenance operator fill preflight completion audit: "
        "`casp17_competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_pass`"
    ) in workbench_md
    assert "targets pass/blocked/total `3/0/3` root manifest `1`" in workbench_md
    assert "target files folder/readme/template/policy `3/3/3/3`" in workbench_md
    assert "template rows expected/csv/mismatch `3/3/0`" in workbench_md
    assert "field policy expected/csv/mismatch `36/36/0` coordinate copies preflight/target `0/0`" in workbench_md
    assert "current CASP17 submission gate: `current_casp17_submission_gate_ready`" in workbench_md
    assert "go/no-go/total `19/0/19` framework `True` shape `pass` `19/0/19`" in workbench_md
    assert "difficult lane `19` server `False`" in workbench_md
    assert "current CASP17 sidechain repack: `pass` pass/blocked/total `19/0/19`" in workbench_md
    assert "soft-clash before/after/delta `1955/1426/529` improved/repacked `7179/15657`" in workbench_md
    assert "current CASP17 submission package preflight: `ready` ready/blocked/total `19/0/19`" in workbench_md
    assert "files/format/author/sidechain/sha256 `19/19/19/19/19`" in workbench_md
    assert "gate `current_casp17_submission_gate_ready` `19/0/19` server `False`" in workbench_md
    assert (
        "current CASP17 submission deadline guard: `partial_current_upload_window_ready` "
        "date `2026-06-02` ready/blocked/total `11/8/19`"
    ) in workbench_md
    assert "expired/today/future `8/2/9` QA open/expired/unknown `15/4/0`" in workbench_md
    assert "package `ready` `19/0/19` watchlist stale `True` `7`" in workbench_md
    assert "first `T1331` `human_submission_deadline_expired` nearest `H2319` `2026-06-02` `0`" in workbench_md
    assert (
        "current CASP17 official upload queue: `official_verified_current_upload_queue_partial` "
        "date `2026-06-02` ready/blocked/total `10/9/19`"
    ) in workbench_md
    assert "today/soon/future `2/4/4` official targets/direct/mapped/missing `77/18/1/0`" in workbench_md
    assert "expired/cancelled/mismatch `9/1/1` first upload `H2319` `2026-06-02`" in workbench_md
    assert "first blocked `H1335` `official_human_deadline_expired`" in workbench_md
    assert (
        "current CASP17 upload review packet: `current_upload_review_packet_ready` "
        "reviews ready/blocked/total `10/0/10`"
    ) in workbench_md
    assert "urgency today/soon/future `2/4/4` candidate/object/viewer `10/10/10`" in workbench_md
    assert "first `H2319` `casp17/current_upload_review_packet/" in workbench_md
    assert (
        "current CASP17 prospective strict-blind escrow: "
        "`current_prospective_strict_blind_escrow_ready_native_pending_partial_upload_window` "
        "escrow ready/blocked/total `19/0/19`"
    ) in workbench_md
    assert "upload ready/blocked `10/9` sha/review/native/ext-ts `19/10/19/19`" in workbench_md
    assert "proof `0` author-serialized `0` first upload/blocked `H2319`/`H1335`" in workbench_md
    assert "win-tier metric surface contract: `awaiting_strict_blind_evidence_files_and_ligand_category_slots`" in workbench_md
    assert "metrics covered/required `11/11`" in workbench_md
    assert "win-tier critical path board: `competitive_proof_blocked_on_strict_blind_evidence`" in workbench_md
    assert "3D objects `4/4` external targets `4/4` model1/top5 `4/20`" in workbench_md
    assert "strict slots `0/40` missing evidence/operator-open `240/400`" in workbench_md
    assert "organic ligand slot candidates: `organic_ligand_slot_candidates_ready_for_operator_review`" in workbench_md
    assert "review/proof/total `2/0/2`" in workbench_md
    assert "ChEMBL/BindingDB `1/1`" in workbench_md
    assert "organic ligand strict-blind promotion board: `awaiting_organic_ligand_strict_blind_evidence`" in workbench_md
    assert "candidates/actions/open `2/18/16`" in workbench_md
    assert "operator/numeric/affinity-source `8/1/1`" in workbench_md
    assert "organizer notice intake: `organizer_notice_intake_ready`" in workbench_md
    assert "R2345 first/second `ignored_invalid_dna_t_in_rna_sequence`/`accepted_second_request_only`" in workbench_md
    assert "MassiveFold scope `all_human_rna_and_hybrid_targets_plus_protein_targets`" in workbench_md
    assert "MassiveFold external pool intake: `massivefold_external_pool_intake_ready`" in workbench_md
    assert "pools ready/blocked/total `3/0/3`" in workbench_md
    assert "RNA/hybrid MassiveFold priority queue: `rna_hybrid_massivefold_priority_queue_ready`" in workbench_md
    assert "R2341/R2345 rank `1/2`" in workbench_md
    assert "R2345 invalid/active `ignored_invalid_dna_t_in_rna_sequence`/`accepted_second_request_only`" in workbench_md
    assert "Protein/complex MassiveFold priority queue: `protein_complex_massivefold_priority_queue_ready`" in workbench_md
    assert "rows ready/blocked/total `1/0/1`" in workbench_md
    assert "first `H1311` `H1311_T327`" in workbench_md
    assert "MassiveFold acquisition verification: `massivefold_external_pool_acquisition_verified`" in workbench_md
    assert "pools verified/open/total `2/0/2`" in workbench_md
    assert "R2341/R2345 `verified_for_external_rerank_intake`/`verified_for_external_rerank_intake`" in workbench_md
    assert "Protein/complex MassiveFold acquisition verification: `awaiting_massivefold_external_pool_acquisition`" in workbench_md
    assert "pools verified/open/total `0/1/1`" in workbench_md
    assert "first/open `H1311`/`H1311` `open_tarball_download_required`" in workbench_md
    assert "MassiveFold model pool index: `massivefold_model_pool_representatives_extracted`" in workbench_md
    assert "models/protocols `8040/8`" in workbench_md
    assert "selected/extracted/pending `40/40/0`" in workbench_md
    assert "MassiveFold representative viewers: `massivefold_representative_viewers_ready`" in workbench_md
    assert "selected/ready/blocked `40/40/0`" in workbench_md
    assert "coordinate/model/projection `40/40/40`" in workbench_md
    assert "atoms/displayed/residues `159280/36000/7440`" in workbench_md
    assert "MassiveFold representative rerank: `massivefold_representative_rerank_ready_review_only`" in workbench_md
    assert "candidates/model1/top5 `40/1/5`" in workbench_md
    assert "top5 protocols `5`" in workbench_md
    assert "review/proof-eligible `35/0`" in workbench_md
    assert "Model_2_af3_basic_af3_seed_672131_sample_4_pred_869.cif" in workbench_md
    assert (
        "MassiveFold RNA model-selection coverage: "
        "`massivefold_rna_model_selection_coverage_ready_review_only`"
    ) in workbench_md
    assert "targets ready/partial/total `2/0/2`" in workbench_md
    assert "models selected/extracted/viewer `80/80/80`" in workbench_md
    assert "model1/top5 `2/10`" in workbench_md
    assert (
        "MassiveFold RNA model-selection inputs: "
        "`massivefold_rna_model_selection_input_packet_ready_external_only`"
    ) in workbench_md
    assert "targets ready/blocked/total `2/0/2` model1/top5 `2/10`" in workbench_md
    assert "R2345 guard `ignore_0930_pacific_invalid_dna_t_request_use_1130_replacement_only`" in workbench_md
    assert (
        "MassiveFold RNA self-assessment: "
        "`massivefold_rna_self_assessment_ready_external_only`"
    ) in workbench_md
    assert "candidates/model1/top5 `10/2/10` low-margin `1`" in workbench_md
    assert (
        "Protein/complex MassiveFold model-selection coverage: "
        "`protein_complex_massivefold_model_selection_coverage_ready_review_only`"
    ) in workbench_md
    assert "models selected/extracted/viewer `260/260/260`" in workbench_md
    assert (
        "Protein/complex MassiveFold self-assessment: "
        "`protein_complex_massivefold_self_assessment_ready_external_only`"
    ) in workbench_md
    assert "heteromer/immune `1` candidates/model1/top5 `10/2/10`" in workbench_md
    assert "missing `0` low-margin `1` threshold `2.0`" in workbench_md
    assert (
        "MassiveFold model1 risk queue: "
        "`massivefold_model1_risk_queue_ready_external_only`"
    ) in workbench_md
    assert "low-margin/critical `2/1` RNA/protein-complex `2/2`" in workbench_md
    assert "first `H1311` `protein_complex` gap `0.05` tier `critical_model1_margin`" in workbench_md
    assert (
        "MassiveFold critical rerank experiment: "
        "`massivefold_critical_rerank_experiment_ready_external_only`"
    ) in workbench_md
    assert "experiments ready/blocked/total `2/0/2` RNA/protein-complex `1/1`" in workbench_md
    assert "review flags diversity/geometry/low-conf `1/1/1`" in workbench_md
    assert "first `R2350` `rna_hybrid` gap `0.02`" in workbench_md
    assert (
        "MassiveFold critical rerank score ledger: "
        "`massivefold_critical_rerank_score_ledger_ready_external_only`"
    ) in workbench_md
    assert "rows ready/blocked/total `2/0/2` bands immediate/calibrate/watch `0/2/0`" in workbench_md
    assert "top `R2350` `rna_hybrid` score `66` band `calibrate_before_model1_freeze`" in workbench_md
    assert (
        "MassiveFold model1 selection calibration gate: "
        "`massivefold_model1_selection_calibration_gate_ready_external_only`"
    ) in workbench_md
    assert "freeze `model1_freeze_blocked_by_calibration` gates ready/blocked/total `2/0/2`" in workbench_md
    assert "hold/watch/probe/freeze `1/1/2/0` RNA/protein-complex `1/1`" in workbench_md
    assert "decision `hold_model1_freeze_probe_required` probe `top5_rerank_consistency_probe`" in workbench_md
    assert (
        "MassiveFold model1 probe worklist: "
        "`massivefold_model1_probe_worklist_ready_external_only`"
    ) in workbench_md
    assert "workitems ready/blocked/total `2/0/2` probes top5/lightweight `1/1`" in workbench_md
    assert "priority 1/2 `1/1` RNA/protein-complex `1/1`" in workbench_md
    assert "unlock `freeze_after_probe_allowed_only_if_exit_criterion_passes`" in workbench_md
    assert (
        "MassiveFold model1 probe outcome: "
        "`massivefold_model1_probe_outcome_ready_external_only`"
    ) in workbench_md
    assert "outcomes ready/blocked/total `2/0/2` pass/fail/freeze-ready `2/0/2`" in workbench_md
    assert "result `probe_pass_model1_retained` margin `0.1`" in workbench_md
    assert "recommendation `conditional_model1_freeze_ready_external_only`" in workbench_md
    assert (
        "MassiveFold model1 freeze decision packet: "
        "`massivefold_model1_freeze_decision_packet_ready_external_only`"
    ) in workbench_md
    assert "decisions ready/blocked/total `2/0/2` freeze-ready/blocked `1/1`" in workbench_md
    assert "conditional/watch/manual `1/0/1` RNA/protein-complex `1/1`" in workbench_md
    assert (
        "MassiveFold model-selection ledger: "
        "`massivefold_model_selection_ledger_ready_external_only`"
    ) in workbench_md
    assert "ledgers ready/blocked/total `15/0/15` selected conditional/watch `2/1`" in workbench_md
    assert "manual/review-only `1/11` freeze-ready `3` RNA/protein-complex `6/9`" in workbench_md
    assert (
        "MassiveFold model1 combined selector overlay: "
        "`massivefold_model1_combined_selector_overlay_ready_external_only`"
    ) in workbench_md
    assert "overlay ready/blocked/total `4/0/4` freeze-ready/not-freeze-ready `1/3`" in workbench_md
    assert "manual/interface/weak/probe/watch/unknown `1/1/0/1/0/0`" in workbench_md
    assert "baseline `0.500`/`0.500` first `R2352` `selector_blocked_manual_review`" in workbench_md
    assert (
        "MassiveFold freeze-ready review packet: "
        "`massivefold_freeze_ready_review_packet_ready_external_only`"
    ) in workbench_md
    assert "reviews ready/blocked/total `2/0/2` model/viewer/projection/top5 `2/2/2/2`" in workbench_md
    assert "top5 total `10` first `R2350` `Model_20_af3_woPaired_seed_1.cif`" in workbench_md
    assert (
        "MassiveFold hold/probe review packet: "
        "`massivefold_hold_probe_review_packet_ready_external_only`"
    ) in workbench_md
    assert "reviews ready/blocked/total `3/0/3` manual/interface/probe/weak/unknown `1/1/1/0/0`" in workbench_md
    assert "model/viewer/projection/top5/alternate `3/3/3/3/1` top5 total `15`" in workbench_md
    assert "first `R2352` `manual_blocked_review` `do_not_freeze_model1_external_only`" in workbench_md
    assert (
        "MassiveFold probe-required targeted probe packet: "
        "`massivefold_probe_required_targeted_probe_packet_ready_external_only`"
    ) in workbench_md
    assert "probes ready/blocked/total `3/0/3` pass/watch/fail `2/1/0`" in workbench_md
    assert "recommendations freeze/watch/manual `2/1/0` RNA/protein-complex `1/2`" in workbench_md
    assert "artifacts model/viewer/projection/top/top-viewer/top5 `3/3/3/3/3/3`" in workbench_md
    assert "top5 total `15` margin `0.5` first `H1311` `probe_pass_model1_retained_clear`" in workbench_md
    assert (
        "MassiveFold post-probe selector decision packet: "
        "`massivefold_post_probe_selector_decision_packet_ready_external_only`"
    ) in workbench_md
    assert "decisions ready/blocked/total `5/0/5` freeze/watch/manual `2/2/1`" in workbench_md
    assert "freeze existing/probe `1/1` watch probe/interface `1/1`" in workbench_md
    assert "manual probe/manual-block `0/1` RNA/protein-complex `2/3`" in workbench_md
    assert "artifacts model/viewer/projection/top5/alternate `5/5/5/5/1`" in workbench_md
    assert "first `R2352` `manual_block` `external_model1_freeze_blocked_manual_review`" in workbench_md
    assert (
        "MassiveFold watch/manual action packet: "
        "`massivefold_watch_manual_action_packet_ready_external_only`"
    ) in workbench_md
    assert "actions ready/blocked/total `5/0/5` manual/interface/low-margin `1/1/3`" in workbench_md
    assert "priority 1/2 `2/3` RNA/protein-complex `2/3`" in workbench_md
    assert "artifacts model/viewer/projection/top5/alternate `5/5/5/5/1`" in workbench_md
    assert "first `R2352` `manual_alternate_review` priority `1`" in workbench_md
    assert (
        "MassiveFold freeze-candidate format preflight: "
        "`massivefold_freeze_candidate_format_preflight_ready_external_only`"
    ) in workbench_md
    assert "preflight ready/blocked/total `10/0/10` freeze existing/probe `2/8`" in workbench_md
    assert "RNA/protein-complex `4/6` selected pdb/cif `6/4`" in workbench_md
    assert "packaged pdb/cif `0/10`" in workbench_md
    assert (
        "checks target/selected-ext/packaged-ext/model/nonempty/viewer/projection/top5 "
        "`10/10/10/10/10/10/10/10`"
    ) in workbench_md
    assert "first `H2319` `Model_1_afm_basic_model_4_multimer_v3_pred_25.pdb`" in workbench_md
    assert (
        "MassiveFold freeze-candidate escrow: "
        "`massivefold_freeze_candidate_escrow_ready_external_only`"
    ) in workbench_md
    assert "escrow ready/blocked/total `10/0/10` sha model/top5 `10/10`" in workbench_md
    assert "artifacts model/viewer/projection/top5 `10/10/10/10`" in workbench_md
    assert "freeze existing/probe `2/8` RNA/protein-complex `4/6`" in workbench_md
    assert "native/proof/author `10/0/0` first `H2319` blocked `-`" in workbench_md
    assert "manifest `freezeabc123` policy `do_not_mark_as_internal_prediction`" in workbench_md
    assert (
        "MassiveFold freeze-candidate protein library: "
        "`massivefold_freeze_candidate_protein_library_ready_external_only`"
    ) in workbench_md
    assert "proteins ready/blocked/total `10/0/10` objects ready/blocked/total `10/0/10`" in workbench_md
    assert "links model/viewer/projection/top5/escrow `10/10/10/10/10`" in workbench_md
    assert "sha model/top5 `10/10` name current/official `5/10` RNA/protein-complex `4/6`" in workbench_md
    assert "proof/author `0/0`" in workbench_md
    assert "casp17/casp17_massivefold_freeze_candidate_protein_library_current.html" in workbench_md
    assert "CAPRI Round 65 readiness context: `deferred_pi_required`" in workbench_md
    assert "CAPRI Round 65 format preflight context: `deferred_pi_required`" in workbench_md
    assert "historical seed official archive baseline lane: `official_archive_baseline_lane_ready`" in workbench_md
    assert "proof-eligible/strict-blocked/other-team `0/24/24`" in workbench_md
    assert (
        "official archive first baseline acquisition audit: `official_archive_first_baseline_acquired`"
        in workbench_md
    )
    assert "artifacts ready/blocked/total `2/0/2`" in workbench_md
    assert "tar present/size/models `True` `25069184` `357`" in workbench_md
    assert "proof `False` policy `do_not_import_as_internal_prediction`" in workbench_md
    assert "official archive first baseline model pool: `official_archive_first_baseline_model_pool_ready`" in workbench_md
    assert "models ready/blocked/expected `357/0/357`" in workbench_md
    assert "groups/model1/top5/complete/extra `74/73/348/67/9`" in workbench_md
    assert (
        "official archive first baseline score ledger: "
        "`official_archive_first_baseline_score_ledger_ready_baseline_only`"
    ) in workbench_md
    assert "models ready/blocked/scored/top5 `348/0/348/348`" in workbench_md
    assert "groups/model1/best/complete/improved `74/73/74/67/41`" in workbench_md
    assert "mean model1/best/gap `55.123` `62.456` `7.333`" in workbench_md
    assert (
        "official archive first baseline replay comparison: "
        "`official_archive_first_baseline_replay_comparison_ready_baseline_only`"
    ) in workbench_md
    assert "bands comparable/blocked/total `0/3/3`" in workbench_md
    assert "direct `not_directly_comparable_proxy_single_target_not_sum_zscore`" in workbench_md
    assert "model1-best/top5-improved `32/73` `41/73`" in workbench_md
    assert "rates `0.438` `0.562`" in workbench_md
    assert (
        "official archive first baseline model1 gap triage: "
        "`official_archive_first_baseline_model1_gap_triage_ready_baseline_only`"
    ) in workbench_md
    assert "groups ready/blocked/total `73/1/74`" in workbench_md
    assert "gaps small/medium/large/catastrophic `10/20/8/3`" in workbench_md
    assert "calibration/critical `41/11`" in workbench_md
    assert "first triage `999` `catastrophic_model1_selection_gap` delta `70.000`" in workbench_md
    assert (
        "official archive first baseline model1 gap viewer packet: "
        "`official_archive_first_baseline_model1_gap_viewer_packet_ready_baseline_only`"
    ) in workbench_md
    assert "viewers ready/blocked/selected `11/0/11`" in workbench_md
    assert "catastrophic/large `3/8` copied pairs/native `11` `True`" in workbench_md
    assert "first viewer `999` `catastrophic_model1_selection_gap` delta `70.000`" in workbench_md
    assert (
        "official archive first baseline model1 gap feature probe: "
        "`official_archive_first_baseline_model1_gap_feature_probe_ready_baseline_only`"
    ) in workbench_md
    assert "features ready/blocked/selected `11/0/11`" in workbench_md
    assert "signals best/model1/ambiguous `4/1/6` rate `0.364`" in workbench_md
    assert "first signal `999` `supports_best_top5` model1/best/delta `122.500` `7.500` `115.000`" in workbench_md
    assert (
        "official archive first baseline model1 gap consensus probe: "
        "`official_archive_first_baseline_model1_gap_consensus_probe_ready_baseline_only`"
    ) in workbench_md
    assert "consensus ready/blocked/selected `11/0/11`" in workbench_md
    assert "signals best/model1/ambiguous `5/2/4` rate `0.455`" in workbench_md
    assert "top matches best/model1 `3/2`" in workbench_md
    assert "first signal `999` `supports_best_top5` ranks/top/margin `5` `1` `T1210TS999_4` `12.345`" in workbench_md
    assert (
        "official archive first baseline model1 gap combined selector: "
        "`official_archive_first_baseline_model1_gap_combined_selector_ledger_ready_baseline_only`"
    ) in workbench_md
    assert "selector ready/blocked/selected `11/0/11`" in workbench_md
    assert "decisions promote/retain/hold `5/5/1`" in workbench_md
    assert "baseline corrected/retained/manual/false-positive `5/5/1/0`" in workbench_md
    assert "capture/non-capture `0.455` `0.545`" in workbench_md
    assert "first selector `999` `promote_best_top5` selected `T1210TS999_4`" in workbench_md
    assert "strict-blind first slot source bridge: `first_slot_source_bridge_internal_prediction_required`" in workbench_md
    assert "official ready/total `24/24` native-bridge `2`" in workbench_md
    assert "baseline-only/strict-blocked `24/24` operator-only/internal-blocked `6/1`" in workbench_md
    assert "strict-blind internal prediction source audit: `internal_prediction_source_missing_for_first_slot`" in workbench_md
    assert "local eligible/total `0/17` routes allowed/total `0/17`" in workbench_md
    assert "allowed/template `0/1` blocker `pre_native_internal_prediction_pdb_missing`" in workbench_md
    assert (
        "strict-blind internal candidate filesystem sweep: "
        "`strict_blind_filesystem_sweep_operator_review_required`"
    ) in workbench_md
    assert "files/atom-like `9968/9968` verified/unknown `0/4551`" in workbench_md
    assert "current/MassiveFold/official/native/top5/dropzone `1810/2895/387/257/75/0`" in workbench_md
    assert (
        "strict-blind unknown candidate triage: "
        "`strict_blind_unknown_triage_internal_like_review_required`"
    ) in workbench_md
    assert "unknown/sweep `4551/4551` promotion/internal-like `0/166`" in workbench_md
    assert "public/run/archive/data/tmp/other `3962/406/16/0/1/0`" in workbench_md
    assert (
        "strict-blind internal-like source review: "
        "`strict_blind_internal_like_source_review_all_post_native`"
    ) in workbench_md
    assert "candidates/triage `166/166` match `True`" in workbench_md
    assert "mapped/pre/post/same/missing/unmapped `166/0/166/0/0/0`" in workbench_md
    assert "targets/all-post/pre-targets `10/10/0`" in workbench_md
    assert "range `2026-02-19`-`2026-02-22` first `HIST_BBA5` `prediction_not_before_native`" in workbench_md
    assert "strict-blind internal prediction source gate: `awaiting_internal_prediction_source_gate_fields`" in workbench_md
    assert "checks pass/blocked/total `3/13/16`" in workbench_md
    assert "first `source_id_internal` `internal_source_id_missing_or_external`" in workbench_md
    assert "strict-blind source gate field board: `awaiting_source_gate_field_fills`" in workbench_md
    assert "actions manifest/file/manifest-file/total `9/2/0/11`" in workbench_md
    assert "blocked checks covered `13`" in workbench_md
    assert "strict-blind source gate operator packet: `awaiting_source_gate_operator_values`" in workbench_md
    assert "operator ready/awaiting/total `0/11/11`" in workbench_md
    assert "strict-blind source gate source requests: `awaiting_pre_native_source_or_candidate_replacement`" in workbench_md
    assert "requests pre-native/replacement/operator-repair/total `10/7/0/17`" in workbench_md
    assert "templates ready/awaiting `0/17`" in workbench_md
    assert "fields filled/missing/total `0/187/187`" in workbench_md
    assert (
        "strict-blind source request resolution board: "
        "`source_request_resolution_all_current_candidates_blocked`"
    ) in workbench_md
    assert "requests ready/blocked/total `0/17/17` monomer/complex `10/7`" in workbench_md
    assert "postnative/replacement/pre-review/missing `10/7/0/0`" in workbench_md
    assert "internal-like post/pre `166/0` first `source_request_001` `HIST_BBA5`" in workbench_md
    assert "strict-blind source request fulfillment gate: `awaiting_source_request_operator_values`" in workbench_md
    assert "requests ready/blocked/total `0/17/17`" in workbench_md
    assert "evidence present/missing `0/153`" in workbench_md
    assert "validation pdb/chronology/internal-source `0/0/0`" in workbench_md
    assert "strict-blind source request operator fill worklist: `awaiting_source_request_operator_values`" in workbench_md
    assert "fields ready/value-missing/evidence-missing/total `0/187/153/187`" in workbench_md
    assert "strict-blind source request operator sync plan: `awaiting_source_request_fulfillment`" in workbench_md
    assert "actions ready/blocked/applied/total `0/1/0/0`" in workbench_md
    assert "strict-blind internal prediction source apply plan: `blocked_until_internal_prediction_source_gate_passes`" in workbench_md
    assert "actions ready/blocked/total `0/16/16`" in workbench_md
    assert "file/operator/supp `1/10/5`" in workbench_md
    assert "strict-blind first slot closure kit: `blocked_on_internal_prediction_source_gate`" in workbench_md
    assert "steps ready/blocked/total `0/7/7`" in workbench_md
    assert "fills source-gate/source-request/file/operator/total `11/17/12/20/60`" in workbench_md
    assert "source-requests `10/7/0/17`" in workbench_md
    assert "strict-blind batch closure runway: `blocked_on_first_slot_internal_prediction_source`" in workbench_md
    assert "slots ready/blocked/total `0/40/40`" in workbench_md
    assert "blocked source/evidence/operator/intake `1/39/0/0`" in workbench_md
    assert payload["summary"]["target_model_ready_count"] == 2
    assert payload["summary"]["target_model_object_count"] == 4
    assert payload["summary"]["target_model_object_projection_count"] == 4
    assert payload["summary"]["target_model_object_viewer_count"] == 4
    assert payload["summary"]["target_object_folder_audit_status"] == "pass"
    assert payload["summary"]["target_object_folder_audit_pass_count"] == 4
    assert payload["summary"]["target_object_folder_chain_isolation_pass_count"] == 4
    assert payload["summary"]["target_object_folder_protein_atom_pass_count"] == 4
    assert payload["summary"]["target_object_folder_coordinate_valid_pass_count"] == 4
    assert payload["summary"]["target_object_folder_total_protein_atom_count"] == 4
    assert payload["summary"]["target_object_viewer_smoke_status"] == "pass"
    assert payload["summary"]["target_object_viewer_smoke_pass_count"] == 4
    assert payload["summary"]["target_object_model_review_status"] == "pass"
    assert payload["summary"]["target_object_model_review_pass_count"] == 4
    assert payload["summary"]["target_object_model_review_blocked_count"] == 0
    assert payload["summary"]["target_object_model_review_total"] == 4
    assert payload["summary"]["target_object_model_review_md_count"] == 4
    assert payload["summary"]["target_object_model_review_viewer_local_pass_count"] == 4
    assert payload["summary"]["target_object_model_review_protein_atom_count"] == 4
    assert payload["summary"]["target_object_model_review_ca_atom_count"] == 4
    assert payload["summary"]["target_object_model_review_residue_count"] == 4
    assert payload["summary"]["target_object_model_review_min_radius"] == 1.2
    assert payload["summary"]["target_object_model_review_max_radius"] == 9.4
    assert payload["summary"]["target_object_model_review_gallery_status"] == "pass"
    assert (
        payload["summary"]["target_object_model_review_gallery_html"]
        == "casp17/casp17_target_object_model_review_gallery_current.html"
    )
    assert payload["summary"]["protein_object_library_status"] == "pass"
    assert payload["summary"]["protein_object_library_protein_folder_count"] == 2
    assert payload["summary"]["protein_object_library_object_folder_count"] == 4
    assert payload["summary"]["protein_object_library_pass_count"] == 4
    assert payload["summary"]["protein_object_library_blocked_count"] == 0
    assert payload["summary"]["protein_object_library_model_pointer_count"] == 4
    assert payload["summary"]["protein_object_library_projection_pointer_count"] == 4
    assert payload["summary"]["protein_object_library_viewer_pointer_count"] == 4
    assert payload["summary"]["protein_object_library_dir"] == "casp17/protein_object_library_current"
    assert payload["summary"]["protein_object_library_completion_status"] == "pass"
    assert payload["summary"]["protein_object_library_completion_protein_pass_count"] == 2
    assert payload["summary"]["protein_object_library_completion_protein_blocked_count"] == 0
    assert payload["summary"]["protein_object_library_completion_object_pass_count"] == 4
    assert payload["summary"]["protein_object_library_completion_object_blocked_count"] == 0
    assert payload["summary"]["protein_object_library_completion_model_count"] == 4
    assert payload["summary"]["protein_object_library_completion_projection_count"] == 4
    assert payload["summary"]["protein_object_library_completion_viewer_count"] == 4
    assert payload["summary"]["protein_object_library_completion_object_manifest_count"] == 4
    assert payload["summary"]["protein_object_library_completion_protein_manifest_count"] == 2
    assert payload["summary"]["protein_object_library_navigation_status"] == (
        "protein_object_library_navigation_catalog_ready"
    )
    assert payload["summary"]["protein_object_library_navigation_protein_pass_count"] == 2
    assert payload["summary"]["protein_object_library_navigation_protein_blocked_count"] == 0
    assert payload["summary"]["protein_object_library_navigation_object_pass_count"] == 4
    assert payload["summary"]["protein_object_library_navigation_object_blocked_count"] == 0
    assert payload["summary"]["protein_object_library_navigation_readme_link_count"] == 2
    assert payload["summary"]["protein_object_library_navigation_manifest_link_count"] == 2
    assert payload["summary"]["protein_object_library_navigation_largest_protein_key"] == (
        "H9002_Example_Fab_Complex"
    )
    assert payload["summary"]["protein_object_library_navigation_largest_object_count"] == 3
    assert payload["summary"]["protein_object_library_navigation_html"] == (
        "casp17/casp17_protein_object_library_navigation_catalog_current.html"
    )
    assert payload["summary"]["casp17_3d_molecular_object_atlas_status"] == (
        "casp17_3d_molecular_object_atlas_ready_review_only"
    )
    assert payload["summary"]["casp17_3d_molecular_object_atlas_protein_count"] == 5
    assert payload["summary"]["casp17_3d_molecular_object_atlas_protein_pass_count"] == 5
    assert payload["summary"]["casp17_3d_molecular_object_atlas_protein_blocked_count"] == 0
    assert payload["summary"]["casp17_3d_molecular_object_atlas_object_count"] == 14
    assert payload["summary"]["casp17_3d_molecular_object_atlas_object_pass_count"] == 14
    assert payload["summary"]["casp17_3d_molecular_object_atlas_object_blocked_count"] == 0
    assert payload["summary"]["casp17_3d_molecular_object_atlas_current_object_count"] == 4
    assert payload["summary"]["casp17_3d_molecular_object_atlas_massivefold_object_count"] == 10
    assert payload["summary"]["casp17_3d_molecular_object_atlas_current_protein_count"] == 2
    assert payload["summary"]["casp17_3d_molecular_object_atlas_massivefold_protein_count"] == 4
    assert payload["summary"]["casp17_3d_molecular_object_atlas_overlap_protein_count"] == 1
    assert payload["summary"]["casp17_3d_molecular_object_atlas_model_link_count"] == 14
    assert payload["summary"]["casp17_3d_molecular_object_atlas_viewer_link_count"] == 14
    assert payload["summary"]["casp17_3d_molecular_object_atlas_projection_link_count"] == 14
    assert payload["summary"]["casp17_3d_molecular_object_atlas_top5_link_count"] == 10
    assert payload["summary"]["casp17_3d_molecular_object_atlas_escrow_link_count"] == 10
    assert payload["summary"]["casp17_3d_molecular_object_atlas_model_sha256_count"] == 10
    assert payload["summary"]["casp17_3d_molecular_object_atlas_top5_sha256_count"] == 10
    assert payload["summary"]["casp17_3d_molecular_object_atlas_native_accuracy_count"] == 0
    assert payload["summary"]["casp17_3d_molecular_object_atlas_proof_eligible_count"] == 0
    assert payload["summary"]["casp17_3d_molecular_object_atlas_author_serialized_count"] == 0
    assert payload["summary"]["casp17_3d_molecular_object_atlas_first_protein_key"] == (
        "H9002_Example_Fab_Complex"
    )
    assert payload["summary"]["casp17_3d_molecular_object_atlas_first_object_key"] == "current_chain_A"
    assert payload["summary"]["casp17_3d_molecular_object_atlas_first_blocked_protein_key"] == ""
    assert payload["summary"]["casp17_3d_molecular_object_atlas_html"] == (
        "casp17/casp17_3d_molecular_object_atlas_current.html"
    )
    assert payload["summary"]["casp17_3d_molecular_object_atlas_completion_audit_status"] == (
        "casp17_3d_molecular_object_atlas_completion_audit_pass"
    )
    assert payload["summary"]["casp17_3d_molecular_object_atlas_completion_audit_protein_count"] == 5
    assert payload["summary"]["casp17_3d_molecular_object_atlas_completion_audit_protein_folder_count"] == 5
    assert payload["summary"]["casp17_3d_molecular_object_atlas_completion_audit_protein_readme_count"] == 5
    assert payload["summary"]["casp17_3d_molecular_object_atlas_completion_audit_protein_manifest_count"] == 5
    assert payload["summary"]["casp17_3d_molecular_object_atlas_completion_audit_object_count"] == 14
    assert payload["summary"]["casp17_3d_molecular_object_atlas_completion_audit_object_pass_count"] == 14
    assert payload["summary"]["casp17_3d_molecular_object_atlas_completion_audit_object_blocked_count"] == 0
    assert payload["summary"]["casp17_3d_molecular_object_atlas_completion_audit_current_object_count"] == 4
    assert payload["summary"]["casp17_3d_molecular_object_atlas_completion_audit_massivefold_object_count"] == 10
    assert payload["summary"]["casp17_3d_molecular_object_atlas_completion_audit_object_folder_count"] == 14
    assert payload["summary"]["casp17_3d_molecular_object_atlas_completion_audit_object_readme_count"] == 14
    assert payload["summary"]["casp17_3d_molecular_object_atlas_completion_audit_object_manifest_count"] == 14
    assert payload["summary"]["casp17_3d_molecular_object_atlas_completion_audit_model_link_count"] == 14
    assert payload["summary"]["casp17_3d_molecular_object_atlas_completion_audit_viewer_link_count"] == 14
    assert payload["summary"]["casp17_3d_molecular_object_atlas_completion_audit_projection_link_count"] == 14
    assert payload["summary"]["casp17_3d_molecular_object_atlas_completion_audit_top5_link_count"] == 10
    assert payload["summary"]["casp17_3d_molecular_object_atlas_completion_audit_escrow_link_count"] == 10
    assert payload["summary"]["casp17_3d_molecular_object_atlas_completion_audit_object_coordinate_copy_count"] == 0
    assert payload["summary"]["casp17_3d_molecular_object_atlas_completion_audit_atlas_coordinate_copy_count"] == 0
    assert payload["summary"]["casp17_3d_molecular_object_atlas_completion_audit_proof_eligible_count"] == 0
    assert payload["summary"]["casp17_3d_molecular_object_atlas_completion_audit_author_serialized_count"] == 0
    assert payload["summary"]["casp17_3d_molecular_object_atlas_completion_audit_first_protein_key"] == (
        "H9002_Example_Fab_Complex"
    )
    assert payload["summary"]["casp17_3d_molecular_object_atlas_completion_audit_first_object_key"] == (
        "current_chain_A"
    )
    assert payload["summary"]["casp17_3d_molecular_object_atlas_completion_audit_first_blocked_protein_key"] == ""
    assert payload["summary"]["casp17_3d_molecular_object_atlas_completion_audit_html"] == (
        "casp17/casp17_3d_molecular_object_atlas_completion_audit_current.html"
    )
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_status"] == (
        "casp17_3d_molecular_object_metric_handoff_ready_review_only_ligand_gap"
    )
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_protein_count"] == 5
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_object_count"] == 14
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_object_ready_count"] == 14
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_object_blocked_count"] == 0
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_current_object_count"] == 4
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_massivefold_object_count"] == 10
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_metric_requirement_count"] == 118
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_covered_required_metric_count"] == 9
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_required_metric_count"] == 11
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_missing_required_metric_count"] == 2
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_missing_required_metric_names"] == (
        "LDDT-PLI,BiSyRMSD"
    )
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_ligand_gap_count"] == 2
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_monomer_object_count"] == 1
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_complex_object_count"] == 12
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_rna_hybrid_object_count"] == 1
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_ligand_object_count"] == 0
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_protein_folder_count"] == 5
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_object_folder_count"] == 14
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_native_accuracy_count"] == 0
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_proof_eligible_count"] == 0
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_author_serialized_count"] == 0
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_first_protein_key"] == (
        "H9002_Example_Fab_Complex"
    )
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_first_object_key"] == (
        "current_chain_A"
    )
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_first_blocked_protein_key"] == ""
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_html"] == (
        "casp17/casp17_3d_molecular_object_metric_handoff_current.html"
    )
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_status"] == (
        "casp17_3d_molecular_object_metric_handoff_completion_audit_pass"
    )
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_protein_count"] == 5
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_protein_folder_count"] == 5
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_protein_readme_count"] == 5
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_protein_manifest_count"] == 5
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_object_count"] == 14
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_object_pass_count"] == 14
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_object_blocked_count"] == 0
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_current_object_count"] == 4
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_massivefold_object_count"] == 10
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_object_folder_count"] == 14
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_object_manifest_count"] == 14
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_metric_csv_count"] == 14
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_metric_md_count"] == 14
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_metric_requirement_count"] == 118
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_metric_csv_row_count"] == 118
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_metric_csv_mismatch_count"] == 0
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_metric_evidence_awaiting_count"] == 14
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_model_link_count"] == 14
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_viewer_link_count"] == 14
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_projection_link_count"] == 14
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_top5_link_count"] == 10
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_escrow_link_count"] == 10
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_object_coordinate_copy_count"] == 0
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_out_dir_coordinate_copy_count"] == 0
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_proof_eligible_count"] == 0
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_author_serialized_count"] == 0
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_first_protein_key"] == (
        "H9002_Example_Fab_Complex"
    )
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_first_object_key"] == (
        "current_chain_A"
    )
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_first_blocked_protein_key"] == ""
    assert payload["summary"]["casp17_3d_molecular_object_metric_handoff_completion_audit_html"] == (
        "casp17/casp17_3d_molecular_object_metric_handoff_completion_audit_current.html"
    )
    assert payload["summary"]["raw_ranked_model_quarantine_status"] == "pass"
    assert payload["summary"]["raw_ranked_model_quarantine_target_count"] == 3
    assert payload["summary"]["raw_ranked_model_quarantine_model_count"] == 15
    assert payload["summary"]["raw_ranked_model_quarantine_quarantined_count"] == 15
    assert payload["summary"]["raw_ranked_model_quarantine_linked_count"] == 15
    assert payload["summary"]["raw_ranked_model_quarantine_author_present_count"] == 15
    assert payload["summary"]["raw_ranked_model_quarantine_top5_count"] == 3
    assert payload["summary"]["raw_ranked_model_quarantine_atom_count"] == 42000
    assert payload["summary"]["current_submission_gate_status"] == "current_casp17_submission_gate_ready"
    assert payload["summary"]["current_submission_gate_go_count"] == 19
    assert payload["summary"]["current_submission_gate_no_go_count"] == 0
    assert payload["summary"]["current_submission_gate_target_count"] == 19
    assert payload["summary"]["current_submission_gate_framework_gate_pass"] == "True"
    assert payload["summary"]["current_submission_gate_shape_status"] == "pass"
    assert payload["summary"]["current_submission_gate_shape_pass_count"] == 19
    assert payload["summary"]["current_submission_gate_shape_blocked_count"] == 0
    assert payload["summary"]["current_submission_gate_shape_target_count"] == 19
    assert payload["summary"]["current_submission_gate_difficult_lane_count"] == 19
    assert payload["summary"]["current_submission_gate_server_ready"] == "False"
    assert payload["summary"]["current_sidechain_repack_status"] == "pass"
    assert payload["summary"]["current_sidechain_repack_pass_count"] == 19
    assert payload["summary"]["current_sidechain_repack_blocked_count"] == 0
    assert payload["summary"]["current_sidechain_repack_target_count"] == 19
    assert payload["summary"]["current_sidechain_repack_soft_delta"] == 529
    assert payload["summary"]["current_sidechain_repack_soft_before"] == 1955
    assert payload["summary"]["current_sidechain_repack_soft_after"] == 1426
    assert payload["summary"]["current_sidechain_repack_improved_residue_count"] == 7179
    assert payload["summary"]["current_sidechain_repack_repacked_residue_count"] == 15657
    assert payload["summary"]["current_sidechain_repack_revert_guard_count"] == 8
    assert payload["summary"]["current_submission_package_preflight_status"] == "ready"
    assert payload["summary"]["current_submission_package_preflight_ready_count"] == 19
    assert payload["summary"]["current_submission_package_preflight_blocked_count"] == 0
    assert payload["summary"]["current_submission_package_preflight_target_count"] == 19
    assert payload["summary"]["current_submission_package_preflight_file_present_count"] == 19
    assert payload["summary"]["current_submission_package_preflight_sha256_count"] == 19
    assert payload["summary"]["current_submission_package_preflight_format_pass_count"] == 19
    assert payload["summary"]["current_submission_package_preflight_author_pass_count"] == 19
    assert payload["summary"]["current_submission_package_preflight_sidechain_pass_count"] == 19
    assert payload["summary"]["current_submission_package_preflight_gate_status"] == (
        "current_casp17_submission_gate_ready"
    )
    assert payload["summary"]["current_submission_package_preflight_gate_go_count"] == 19
    assert payload["summary"]["current_submission_package_preflight_gate_no_go_count"] == 0
    assert payload["summary"]["current_submission_package_preflight_gate_target_count"] == 19
    assert payload["summary"]["current_submission_package_preflight_server_ready"] == "False"
    assert payload["summary"]["current_submission_package_preflight_package_mode"] == (
        "manifest_only_no_author_code_export"
    )
    assert payload["summary"]["current_submission_deadline_guard_status"] == (
        "partial_current_upload_window_ready"
    )
    assert payload["summary"]["current_submission_deadline_guard_current_date"] == "2026-06-02"
    assert payload["summary"]["current_submission_deadline_guard_ready_count"] == 11
    assert payload["summary"]["current_submission_deadline_guard_blocked_count"] == 8
    assert payload["summary"]["current_submission_deadline_guard_target_count"] == 19
    assert payload["summary"]["current_submission_deadline_guard_human_expired_count"] == 8
    assert payload["summary"]["current_submission_deadline_guard_human_expiring_today_count"] == 2
    assert payload["summary"]["current_submission_deadline_guard_human_future_count"] == 9
    assert payload["summary"]["current_submission_deadline_guard_qa_open_count"] == 15
    assert payload["summary"]["current_submission_deadline_guard_qa_expired_count"] == 4
    assert payload["summary"]["current_submission_deadline_guard_qa_unknown_count"] == 0
    assert payload["summary"]["current_submission_deadline_guard_package_status"] == "ready"
    assert payload["summary"]["current_submission_deadline_guard_package_ready_count"] == 19
    assert payload["summary"]["current_submission_deadline_guard_package_blocked_count"] == 0
    assert payload["summary"]["current_submission_deadline_guard_package_target_count"] == 19
    assert payload["summary"]["current_submission_deadline_guard_watchlist_stale"] == "True"
    assert payload["summary"]["current_submission_deadline_guard_watchlist_stale_days"] == 7
    assert payload["summary"]["current_submission_deadline_guard_first_blocked_target_id"] == "T1331"
    assert payload["summary"]["current_submission_deadline_guard_first_blocked_reason"] == (
        "human_submission_deadline_expired"
    )
    assert payload["summary"]["current_submission_deadline_guard_nearest_open_target_id"] == "H2319"
    assert payload["summary"]["current_submission_deadline_guard_nearest_open_human_expiration"] == (
        "2026-06-02"
    )
    assert payload["summary"]["current_submission_deadline_guard_nearest_open_days"] == 0
    assert payload["summary"]["current_upload_queue_status"] == (
        "official_verified_current_upload_queue_partial"
    )
    assert payload["summary"]["current_upload_queue_current_date"] == "2026-06-02"
    assert payload["summary"]["current_upload_queue_ready_count"] == 10
    assert payload["summary"]["current_upload_queue_blocked_count"] == 9
    assert payload["summary"]["current_upload_queue_target_count"] == 19
    assert payload["summary"]["current_upload_queue_ready_today_count"] == 2
    assert payload["summary"]["current_upload_queue_ready_soon_count"] == 4
    assert payload["summary"]["current_upload_queue_ready_future_count"] == 4
    assert payload["summary"]["current_upload_queue_official_target_count"] == 77
    assert payload["summary"]["current_upload_queue_official_direct_match_count"] == 18
    assert payload["summary"]["current_upload_queue_official_phase_mapped_count"] == 1
    assert payload["summary"]["current_upload_queue_official_missing_count"] == 0
    assert payload["summary"]["current_upload_queue_official_cancelled_count"] == 1
    assert payload["summary"]["current_upload_queue_official_expired_count"] == 9
    assert payload["summary"]["current_upload_queue_official_mismatch_count"] == 1
    assert payload["summary"]["current_upload_queue_first_upload_target_id"] == "H2319"
    assert payload["summary"]["current_upload_queue_first_upload_human_expiration"] == "2026-06-02"
    assert payload["summary"]["current_upload_queue_first_blocked_target_id"] == "H1335"
    assert payload["summary"]["current_upload_queue_first_blocked_reason"] == (
        "official_human_deadline_expired"
    )
    assert payload["summary"]["current_upload_review_packet_status"] == (
        "current_upload_review_packet_ready"
    )
    assert payload["summary"]["current_upload_review_packet_review_count"] == 10
    assert payload["summary"]["current_upload_review_packet_ready_count"] == 10
    assert payload["summary"]["current_upload_review_packet_blocked_count"] == 0
    assert payload["summary"]["current_upload_review_packet_urgency_today_count"] == 2
    assert payload["summary"]["current_upload_review_packet_urgency_soon_count"] == 4
    assert payload["summary"]["current_upload_review_packet_urgency_future_count"] == 4
    assert payload["summary"]["current_upload_review_packet_candidate_count"] == 10
    assert payload["summary"]["current_upload_review_packet_object_catalog_count"] == 10
    assert payload["summary"]["current_upload_review_packet_viewer_count"] == 10
    assert payload["summary"]["current_upload_review_packet_first_target_id"] == "H2319"
    assert payload["summary"]["current_upload_review_packet_first_review_md"].endswith(
        "UPLOAD_REVIEW.md"
    )
    assert payload["summary"]["current_prospective_strict_blind_escrow_status"] == (
        "current_prospective_strict_blind_escrow_ready_native_pending_partial_upload_window"
    )
    assert payload["summary"]["current_prospective_strict_blind_escrow_target_count"] == 19
    assert payload["summary"]["current_prospective_strict_blind_escrow_ready_count"] == 19
    assert payload["summary"]["current_prospective_strict_blind_escrow_blocked_count"] == 0
    assert payload["summary"]["current_prospective_strict_blind_escrow_upload_ready_count"] == 10
    assert payload["summary"]["current_prospective_strict_blind_escrow_upload_blocked_count"] == 9
    assert payload["summary"]["current_prospective_strict_blind_escrow_sha256_match_count"] == 19
    assert payload["summary"]["current_prospective_strict_blind_escrow_review_link_count"] == 10
    assert payload["summary"]["current_prospective_strict_blind_escrow_native_pending_count"] == 19
    assert (
        payload["summary"]["current_prospective_strict_blind_escrow_external_timestamp_required_count"]
        == 19
    )
    assert (
        payload["summary"]["current_prospective_strict_blind_escrow_competitive_proof_eligible_count"]
        == 0
    )
    assert payload["summary"]["current_prospective_strict_blind_escrow_author_serialized_count"] == 0
    assert payload["summary"]["current_prospective_strict_blind_escrow_first_upload_ready_target_id"] == (
        "H2319"
    )
    assert payload["summary"]["current_prospective_strict_blind_escrow_first_upload_blocked_target_id"] == (
        "H1335"
    )
    assert payload["summary"]["current_prospective_strict_blind_escrow_manifest_signature_sha256"] == (
        "abc123"
    )
    assert payload["summary"]["benchmark_rows_total"] == 40
    assert payload["summary"]["competitive_batch_status"] == "ready_for_fill"
    assert payload["summary"]["competitive_batch_row_count"] == 15
    assert payload["summary"]["competitive_batch_missing_evidence_item_count"] == 490
    assert payload["summary"]["competitive_row_fill_status"] == "awaiting_fill"
    assert payload["summary"]["competitive_row_fill_filled_count"] == 0
    assert payload["summary"]["competitive_row_fill_row_count"] == 15
    assert payload["summary"]["competitive_row_fill_worklist_status"] == "open_actions"
    assert payload["summary"]["competitive_row_fill_worklist_open_action_count"] == 450
    assert payload["summary"]["competitive_row_fill_worklist_guide_count"] == 15
    assert payload["summary"]["competitive_evidence_dropzone_status"] == "open_actions"
    assert payload["summary"]["competitive_evidence_dropzone_count"] == 15
    assert payload["summary"]["competitive_evidence_dropzone_manifest_count"] == 15
    assert payload["summary"]["competitive_evidence_dropzone_open_action_count"] == 450
    assert payload["summary"]["competitive_evidence_dropzone_file_action_count"] == 180
    assert payload["summary"]["competitive_evidence_import_status"] == "awaiting_import"
    assert payload["summary"]["competitive_evidence_import_action_count"] == 450
    assert payload["summary"]["competitive_evidence_import_ready_for_apply_count"] == 0
    assert payload["summary"]["competitive_evidence_import_applied_count"] == 0
    assert payload["summary"]["competitive_evidence_import_awaiting_file_count"] == 180
    assert payload["summary"]["competitive_evidence_import_awaiting_value_count"] == 270
    assert payload["summary"]["competitive_evidence_import_blocked_count"] == 0
    assert payload["summary"]["competitive_evidence_round_status"] == "awaiting_import"
    assert payload["summary"]["competitive_evidence_round_stage_count"] == 5
    assert payload["summary"]["competitive_evidence_round_import_ready_for_apply_count"] == 0
    assert payload["summary"]["competitive_evidence_round_import_applied_count"] == 0
    assert payload["summary"]["competitive_evidence_round_patch_candidate_count"] == 0
    assert payload["summary"]["competitive_evidence_round_apply_plan_planned_patch_count"] == 0
    assert payload["summary"]["competitive_unlock_priority_status"] == "identity_unlock_required"
    assert payload["summary"]["competitive_unlock_priority_phase_row_count"] == 60
    assert payload["summary"]["competitive_unlock_priority_identity_open_action_count"] == 30
    assert payload["summary"]["competitive_unlock_priority_target_id_open_count"] == 15
    assert payload["summary"]["competitive_unlock_priority_file_waiting_on_identity_count"] == 180
    assert payload["summary"]["competitive_identity_unlock_status"] == "awaiting_identity"
    assert payload["summary"]["competitive_identity_unlock_row_count"] == 15
    assert payload["summary"]["competitive_identity_unlock_ready_count"] == 0
    assert payload["summary"]["competitive_identity_unlock_awaiting_count"] == 15
    assert payload["summary"]["competitive_identity_unlock_blocked_count"] == 0
    assert payload["summary"]["competitive_identity_unlock_file_actions_unlocked_count"] == 0
    assert payload["summary"]["competitive_identity_round_status"] == "awaiting_identity"
    assert payload["summary"]["competitive_identity_round_row_count"] == 15
    assert payload["summary"]["competitive_identity_round_ready_for_import_count"] == 0
    assert payload["summary"]["competitive_identity_round_awaiting_count"] == 15
    assert payload["summary"]["competitive_identity_round_blocked_count"] == 0
    assert payload["summary"]["competitive_identity_round_import_ready_for_apply_count"] == 0
    assert payload["summary"]["competitive_identity_round_import_applied_count"] == 0
    assert payload["summary"]["competitive_identity_round_target_id_open_count"] == 15
    assert payload["summary"]["competitive_identity_round_file_waiting_on_identity_count"] == 180
    assert payload["summary"]["competitive_identity_intake_status"] == "awaiting_identity"
    assert payload["summary"]["competitive_identity_intake_row_count"] == 15
    assert payload["summary"]["competitive_identity_intake_ready_count"] == 0
    assert payload["summary"]["competitive_identity_intake_awaiting_count"] == 15
    assert payload["summary"]["competitive_identity_intake_blocked_count"] == 0
    assert payload["summary"]["competitive_identity_intake_missing_field_count"] == 60
    assert payload["summary"]["competitive_identity_intake_file_actions_unlocked_count"] == 0
    assert payload["summary"]["competitive_identity_sync_status"] == "awaiting_intake"
    assert payload["summary"]["competitive_identity_sync_row_count"] == 15
    assert payload["summary"]["competitive_identity_sync_synced_count"] == 0
    assert payload["summary"]["competitive_identity_sync_ready_to_sync_count"] == 0
    assert payload["summary"]["competitive_identity_sync_awaiting_count"] == 15
    assert payload["summary"]["competitive_identity_sync_blocked_count"] == 0
    assert payload["summary"]["competitive_identity_sync_missing_field_count"] == 60
    assert payload["summary"]["competitive_identity_sync_kit_mismatch_count"] == 0
    assert payload["summary"]["competitive_identity_sync_applied_count"] == 0
    assert payload["summary"]["competitive_identity_candidate_status"] == "awaiting_candidate_sources"
    assert payload["summary"]["competitive_identity_candidate_row_count"] == 15
    assert payload["summary"]["competitive_identity_candidate_ready_count"] == 0
    assert payload["summary"]["competitive_identity_candidate_awaiting_count"] == 15
    assert payload["summary"]["competitive_identity_candidate_source_count"] == 55
    assert payload["summary"]["competitive_identity_candidate_source_ready_count"] == 0
    assert payload["summary"]["competitive_identity_candidate_source_blocked_count"] == 55
    assert payload["summary"]["competitive_identity_candidate_applied_count"] == 0
    assert payload["summary"]["competitive_identity_candidate_operator_preflight_status"] == "blocked"
    assert payload["summary"]["competitive_floor_unblock_map_status"] == "awaiting_candidate_source_repair"
    assert payload["summary"]["competitive_floor_unblock_map_row_count"] == 15
    assert payload["summary"]["competitive_floor_unblock_map_ready_count"] == 0
    assert payload["summary"]["competitive_floor_unblock_map_awaiting_count"] == 15
    assert payload["summary"]["competitive_floor_unblock_map_source_count"] == 55
    assert payload["summary"]["competitive_floor_unblock_map_source_ready_count"] == 0
    assert payload["summary"]["competitive_floor_unblock_map_source_blocked_count"] == 55
    assert payload["summary"]["competitive_floor_unblock_map_blocking_field_count"] == 285
    assert payload["summary"]["competitive_floor_unblock_map_blocking_phase_count"] == 75
    assert payload["summary"]["competitive_floor_unblock_map_target_identity_open_count"] == 15
    assert payload["summary"]["competitive_floor_unblock_map_core_files_open_count"] == 15
    assert payload["summary"]["competitive_floor_unblock_map_no_leak_provenance_open_count"] == 15
    assert payload["summary"]["competitive_floor_unblock_map_ablation_files_open_count"] == 15
    assert payload["summary"]["competitive_floor_unblock_map_calibration_values_open_count"] == 15
    assert payload["summary"]["competitive_floor_unblock_map_first_open_phase"] == "target_identity"
    assert payload["summary"]["competitive_identity_source_repair_status"] == "awaiting_target_identity"
    assert payload["summary"]["competitive_identity_source_repair_action_count"] == 200
    assert payload["summary"]["competitive_identity_source_repair_blocked_source_count"] == 40
    assert payload["summary"]["competitive_identity_source_repair_target_identity_count"] == 40
    assert payload["summary"]["competitive_identity_source_repair_core_file_count"] == 40
    assert payload["summary"]["competitive_identity_source_repair_provenance_count"] == 40
    assert payload["summary"]["competitive_identity_source_repair_ablation_count"] == 40
    assert payload["summary"]["competitive_identity_source_repair_calibration_count"] == 40
    assert payload["summary"]["competitive_identity_source_repair_first_phase"] == "target_identity"
    assert payload["summary"]["competitive_target_identity_discovery_status"] == "review_required"
    assert payload["summary"]["competitive_target_identity_discovery_count"] == 19
    assert payload["summary"]["competitive_target_identity_operator_review_count"] == 3
    assert payload["summary"]["competitive_target_identity_open_current_count"] == 16
    assert payload["summary"]["competitive_target_identity_closed_watchlist_count"] == 3
    assert payload["summary"]["competitive_target_identity_unknown_local_count"] == 0
    assert payload["summary"]["competitive_target_identity_synthetic_count"] == 0
    assert payload["summary"]["competitive_target_identity_ready_for_intake_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_status"] == "awaiting_target_identity_clearance"
    assert payload["summary"]["competitive_target_identity_clearance_review_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_prediction_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_ts_prediction_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_native_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_provenance_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_ready_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_awaiting_prediction_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_awaiting_native_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_awaiting_no_leak_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_workorder_status"] == "awaiting_native_or_provenance"
    assert payload["summary"]["competitive_target_identity_clearance_workorder_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_workorder_ready_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_workorder_native_provenance_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_workorder_native_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_workorder_provenance_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_workorder_dropzone_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_workorder_dropzone_readme_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_workorder_template_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_workorder_stub_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_workorder_template_preserved_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_workorder_template_refreshed_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_workorder_stub_preserved_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_workorder_stub_refreshed_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_operator_intake_status"] == "awaiting_input"
    assert payload["summary"]["competitive_target_identity_clearance_operator_intake_row_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_operator_intake_ready_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_operator_intake_awaiting_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_operator_intake_blocked_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_operator_intake_applied_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_operator_intake_native_copied_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_operator_intake_provenance_patched_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_native_candidate_status"] == "review_required"
    assert payload["summary"]["competitive_target_identity_clearance_native_candidate_row_count"] == 4
    assert payload["summary"]["competitive_target_identity_clearance_native_candidate_operator_review_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_native_candidate_relaxed_review_count"] == 1
    assert payload["summary"]["competitive_target_identity_clearance_native_candidate_blocked_count"] == 2
    assert payload["summary"]["competitive_target_identity_clearance_native_candidate_collision_count"] == 2
    assert payload["summary"]["competitive_target_identity_clearance_native_candidate_no_candidate_count"] == 1
    assert payload["summary"]["competitive_target_identity_clearance_native_candidate_prepared_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_adjudication_status"] == "blocked_candidate_risk"
    assert payload["summary"]["competitive_target_identity_clearance_adjudication_target_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_adjudication_replacement_required_count"] == 2
    assert payload["summary"]["competitive_target_identity_clearance_adjudication_manual_native_search_count"] == 1
    assert payload["summary"]["competitive_target_identity_clearance_adjudication_operator_review_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_adjudication_safe_apply_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_adjudication_md_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_replacement_queue_status"] == "blocked_replacement_candidates"
    assert payload["summary"]["competitive_target_identity_clearance_replacement_queue_target_count"] == 2
    assert payload["summary"]["competitive_target_identity_clearance_replacement_queue_candidate_count"] == 8
    assert payload["summary"]["competitive_target_identity_clearance_replacement_queue_ready_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_replacement_queue_missing_prediction_count"] == 6
    assert payload["summary"]["competitive_target_identity_clearance_replacement_queue_current_collision_count"] == 1
    assert payload["summary"]["competitive_target_identity_clearance_replacement_queue_source_repair_count"] == 1
    assert payload["summary"]["competitive_target_identity_clearance_replacement_source_repair_status"] == "awaiting_sequence"
    assert payload["summary"]["competitive_target_identity_clearance_replacement_source_repair_candidate_count"] == 4
    assert payload["summary"]["competitive_target_identity_clearance_replacement_source_repair_ready_count"] == 2
    assert payload["summary"]["competitive_target_identity_clearance_replacement_source_repair_source_ready_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_replacement_source_repair_ready_prediction_count"] == 1
    assert (
        payload["summary"][
            "competitive_target_identity_clearance_replacement_source_repair_ready_validation_scorecard_count"
        ]
        == 1
    )
    assert payload["summary"]["competitive_target_identity_clearance_replacement_source_repair_awaiting_sequence_count"] == 1
    assert payload["summary"]["competitive_target_identity_clearance_replacement_source_repair_blocked_cancelled_count"] == 1
    assert payload["summary"]["competitive_target_identity_clearance_replacement_source_repair_current_collision_count"] == 1
    assert payload["summary"]["competitive_target_identity_clearance_replacement_source_repair_md_count"] == 4
    assert payload["summary"]["competitive_target_identity_clearance_replacement_scorecard_status"] == "replacement_scorecard_blocked"
    assert payload["summary"]["competitive_target_identity_clearance_replacement_scorecard_candidate_count"] == 4
    assert payload["summary"]["competitive_target_identity_clearance_replacement_scorecard_pass_count"] == 1
    assert payload["summary"]["competitive_target_identity_clearance_replacement_scorecard_blocked_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_replacement_scorecard_json_count"] == 1
    assert payload["summary"]["competitive_target_identity_clearance_replacement_workorder_status"] == (
        "partial_replacement_workorders_ready_for_operator_intake"
    )
    assert payload["summary"]["competitive_target_identity_clearance_replacement_workorder_target_count"] == 2
    assert payload["summary"]["competitive_target_identity_clearance_replacement_workorder_row_count"] == 2
    assert payload["summary"]["competitive_target_identity_clearance_replacement_workorder_selected_count"] == 1
    assert payload["summary"]["competitive_target_identity_clearance_replacement_workorder_duplicate_count"] == 1
    assert payload["summary"]["competitive_target_identity_clearance_replacement_workorder_no_ready_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_replacement_workorder_dropzone_count"] == 1
    assert payload["summary"]["competitive_target_identity_clearance_replacement_workorder_dropzone_readme_count"] == 1
    assert payload["summary"]["competitive_target_identity_clearance_replacement_workorder_template_count"] == 1
    assert payload["summary"]["competitive_target_identity_clearance_replacement_workorder_stub_count"] == 1
    assert payload["summary"]["competitive_floor_native_dropzone_registry_status"] == "awaiting_native_files"
    assert payload["summary"]["competitive_floor_native_dropzone_registry_count"] == 4
    assert payload["summary"]["competitive_floor_native_dropzone_registry_primary_count"] == 3
    assert payload["summary"]["competitive_floor_native_dropzone_registry_replacement_count"] == 1
    assert payload["summary"]["competitive_floor_native_dropzone_registry_readme_count"] == 4
    assert payload["summary"]["competitive_floor_native_dropzone_registry_native_count"] == 0
    assert payload["summary"]["competitive_floor_native_dropzone_registry_blocked_count"] == 4
    assert payload["summary"]["competitive_floor_native_dropzone_registry_unexpected_coordinate_count"] == 0
    assert payload["summary"]["competitive_floor_native_dropzone_registry_coordinate_copy_count"] == 0
    assert payload["summary"]["competitive_floor_native_dropzone_registry_proof_eligible_count"] == 0
    assert payload["summary"]["competitive_floor_native_dropzone_registry_author_serialized_count"] == 0
    assert payload["summary"]["competitive_floor_native_dropzone_registry_first_blocked_target_id"] == "H1319"
    assert payload["summary"]["competitive_floor_native_dropzone_registry_first_blocked_blockers"] == (
        "native_pdb_missing"
    )
    assert payload["summary"]["competitive_target_identity_clearance_replacement_workorder_audit_status"] == "blocked"
    assert payload["summary"]["competitive_target_identity_clearance_replacement_workorder_audit_target_count"] == 2
    assert payload["summary"]["competitive_target_identity_clearance_replacement_workorder_audit_pass_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_replacement_workorder_audit_blocked_count"] == 2
    assert payload["summary"]["competitive_target_identity_clearance_replacement_workorder_audit_prediction_count"] == 2
    assert payload["summary"]["competitive_target_identity_clearance_replacement_workorder_audit_native_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_replacement_workorder_audit_provenance_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_replacement_workorder_audit_manifest_count"] == 0
    assert (
        payload["summary"][
            "competitive_target_identity_clearance_replacement_workorder_audit_native_prediction_waiting_count"
        ]
        == 2
    )
    assert payload["summary"]["competitive_target_identity_clearance_replacement_pickup_status"] == "open_actions"
    assert payload["summary"]["competitive_target_identity_clearance_replacement_pickup_row_count"] == 2
    assert payload["summary"]["competitive_target_identity_clearance_replacement_pickup_selected_count"] == 1
    assert payload["summary"]["competitive_target_identity_clearance_replacement_pickup_ready_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_replacement_pickup_awaiting_count"] == 1
    assert payload["summary"]["competitive_target_identity_clearance_replacement_pickup_blocked_selection_count"] == 1
    assert payload["summary"]["competitive_target_identity_clearance_replacement_pickup_native_missing_count"] == 1
    assert payload["summary"]["competitive_target_identity_clearance_replacement_pickup_required_field_count"] == 11
    assert payload["summary"]["competitive_target_identity_clearance_replacement_pickup_operator_action_count"] == 4
    assert payload["summary"]["competitive_target_identity_clearance_replacement_duplicate_resolution_status"] == (
        "operator_decision_required"
    )
    assert payload["summary"]["competitive_target_identity_clearance_replacement_duplicate_resolution_target_count"] == 1
    assert (
        payload["summary"]["competitive_target_identity_clearance_replacement_duplicate_resolution_candidate_count"]
        == 4
    )
    assert (
        payload["summary"]["competitive_target_identity_clearance_replacement_duplicate_resolution_safe_unique_count"]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_target_identity_clearance_replacement_duplicate_resolution_duplicate_ready_count"
        ]
        == 1
    )
    assert (
        payload["summary"][
            "competitive_target_identity_clearance_replacement_duplicate_resolution_blocked_duplicate_count"
        ]
        == 1
    )
    assert payload["summary"]["competitive_target_identity_clearance_replacement_duplicate_resolution_cancelled_count"] == 1
    assert (
        payload["summary"][
            "competitive_target_identity_clearance_replacement_duplicate_resolution_current_collision_count"
        ]
        == 2
    )
    assert (
        payload["summary"][
            "competitive_target_identity_clearance_replacement_duplicate_resolution_missing_prediction_count"
        ]
        == 3
    )
    assert payload["summary"]["competitive_target_identity_clearance_replacement_decision_bundle_status"] == (
        "open_operator_decision"
    )
    assert payload["summary"]["competitive_target_identity_clearance_replacement_decision_bundle_target_count"] == 1
    assert payload["summary"]["competitive_target_identity_clearance_replacement_decision_bundle_ready_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_replacement_decision_bundle_open_count"] == 1
    assert payload["summary"]["competitive_target_identity_clearance_replacement_decision_bundle_folder_count"] == 1
    assert (
        payload["summary"]["competitive_target_identity_clearance_replacement_decision_bundle_candidate_csv_count"]
        == 1
    )
    assert (
        payload["summary"][
            "competitive_target_identity_clearance_replacement_decision_bundle_new_unique_template_count"
        ]
        == 1
    )
    assert (
        payload["summary"][
            "competitive_target_identity_clearance_replacement_decision_bundle_duplicate_exception_count"
        ]
        == 1
    )
    assert payload["summary"]["competitive_target_identity_clearance_replacement_decision_bundle_candidate_count"] == 4
    assert (
        payload["summary"]["competitive_target_identity_clearance_replacement_decision_bundle_safe_unique_count"]
        == 0
    )
    assert (
        payload["summary"]["competitive_target_identity_clearance_replacement_decision_bundle_duplicate_ready_count"]
        == 1
    )
    assert payload["summary"]["competitive_target_identity_clearance_replacement_decision_preflight_status"] == (
        "awaiting_operator_decision"
    )
    assert payload["summary"]["competitive_target_identity_clearance_replacement_decision_preflight_row_count"] == 1
    assert (
        payload["summary"]["competitive_target_identity_clearance_replacement_decision_preflight_ready_new_count"]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_target_identity_clearance_replacement_decision_preflight_ready_duplicate_count"
        ]
        == 0
    )
    assert payload["summary"]["competitive_target_identity_clearance_replacement_decision_preflight_awaiting_count"] == 1
    assert payload["summary"]["competitive_target_identity_clearance_replacement_decision_preflight_conflict_count"] == 0
    assert (
        payload["summary"][
            "competitive_target_identity_clearance_replacement_decision_preflight_new_unique_blocker_count"
        ]
        == 1
    )
    assert (
        payload["summary"][
            "competitive_target_identity_clearance_replacement_decision_preflight_duplicate_exception_blocker_count"
        ]
        == 1
    )
    assert payload["summary"]["competitive_target_identity_clearance_manifest_sync_status"] == "awaiting_provenance"
    assert payload["summary"]["competitive_target_identity_clearance_manifest_sync_row_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_manifest_sync_ready_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_manifest_sync_awaiting_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_manifest_sync_blocked_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_manifest_sync_synced_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_manifest_sync_changed_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_manifest_sync_applied_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_workorder_audit_status"] == "blocked"
    assert payload["summary"]["competitive_target_identity_clearance_workorder_audit_target_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_workorder_audit_pass_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_workorder_audit_blocked_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_workorder_audit_prediction_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_workorder_audit_prediction_protein_atom_count"] == 3
    assert (
        payload["summary"]["competitive_target_identity_clearance_workorder_audit_prediction_coordinate_valid_count"]
        == 3
    )
    assert (
        payload["summary"]["competitive_target_identity_clearance_workorder_audit_identity_discovery_blocked_count"]
        == 3
    )
    assert (
        payload["summary"]["competitive_target_identity_clearance_workorder_audit_identity_discovery_cleared_count"]
        == 0
    )
    assert payload["summary"]["competitive_target_identity_clearance_workorder_audit_native_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_workorder_audit_native_protein_atom_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_workorder_audit_native_coordinate_valid_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_workorder_audit_provenance_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_workorder_audit_evidence_ref_count"] == 0
    assert (
        payload["summary"]["competitive_target_identity_clearance_workorder_audit_evidence_ref_blocked_count"]
        == 3
    )
    assert (
        payload["summary"]["competitive_target_identity_clearance_workorder_audit_evidence_ref_waiting_count"]
        == 0
    )
    assert (
        payload["summary"]["competitive_target_identity_clearance_workorder_audit_evidence_ref_verified_count"]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_target_identity_clearance_workorder_audit_evidence_ref_content_blocked_count"
        ]
        == 0
    )
    assert payload["summary"]["competitive_target_identity_clearance_workorder_audit_manifest_count"] == 0
    assert (
        payload["summary"][
            "competitive_target_identity_clearance_workorder_audit_manifest_provenance_matched_count"
        ]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_target_identity_clearance_workorder_audit_manifest_provenance_mismatch_count"
        ]
        == 0
    )
    assert (
        payload["summary"]["competitive_target_identity_clearance_workorder_audit_native_prediction_distinct_count"]
        == 0
    )
    assert (
        payload["summary"]["competitive_target_identity_clearance_workorder_audit_native_prediction_same_count"]
        == 0
    )
    assert (
        payload["summary"]["competitive_target_identity_clearance_workorder_audit_native_prediction_waiting_count"]
        == 3
    )
    assert payload["summary"]["competitive_target_identity_metric_runway_status"] == (
        "casp17_competitive_floor_target_identity_metric_runway_blocked_awaiting_native_provenance"
    )
    assert payload["summary"]["competitive_target_identity_metric_runway_target_count"] == 3
    assert payload["summary"]["competitive_target_identity_metric_runway_ready_count"] == 0
    assert payload["summary"]["competitive_target_identity_metric_runway_blocked_count"] == 3
    assert payload["summary"]["competitive_target_identity_metric_runway_complex_count"] == 3
    assert payload["summary"]["competitive_target_identity_metric_runway_monomer_count"] == 0
    assert payload["summary"]["competitive_target_identity_metric_runway_metric_requirement_count"] == 27
    assert payload["summary"]["competitive_target_identity_metric_runway_prediction_count"] == 3
    assert payload["summary"]["competitive_target_identity_metric_runway_native_count"] == 0
    assert payload["summary"]["competitive_target_identity_metric_runway_provenance_count"] == 0
    assert payload["summary"]["competitive_target_identity_metric_runway_evidence_ref_count"] == 0
    assert payload["summary"]["competitive_target_identity_metric_runway_native_candidate_count"] == 5
    assert payload["summary"]["competitive_target_identity_metric_runway_native_candidate_blocked_count"] == 4
    assert payload["summary"]["competitive_target_identity_metric_runway_native_candidate_no_candidate_count"] == 1
    assert payload["summary"]["competitive_target_identity_metric_runway_proof_eligible_count"] == 0
    assert payload["summary"]["competitive_target_identity_metric_runway_author_serialized_count"] == 0
    assert payload["summary"]["competitive_target_identity_metric_runway_first_target_id"] == "H1319"
    assert payload["summary"]["competitive_target_identity_metric_runway_first_blocked_target_id"] == "H1319"
    assert payload["summary"]["competitive_target_identity_metric_runway_first_blocker"] == "native_pdb_missing"
    assert payload["summary"]["competitive_target_identity_metric_runway_html"] == (
        "casp17/casp17_competitive_floor_target_identity_metric_runway_current.html"
    )
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_status"] == (
        "casp17_competitive_floor_native_provenance_operator_packet_open_actions"
    )
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_target_count"] == 3
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_target_open_count"] == 3
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_target_ready_count"] == 0
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_action_count"] == 12
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_open_action_count"] == 12
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_native_action_count"] == 3
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_evidence_action_count"] == 3
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_provenance_action_count"] == 3
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_manifest_action_count"] == 3
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_metric_requirement_count"] == 27
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_prediction_count"] == 3
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_native_count"] == 0
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_provenance_count"] == 0
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_evidence_ref_count"] == 0
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_native_candidate_count"] == 5
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_native_candidate_blocked_count"] == 4
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_native_candidate_no_candidate_count"] == 1
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_proof_eligible_count"] == 0
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_author_serialized_count"] == 0
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_first_target_id"] == "H1319"
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_first_open_target_id"] == "H1319"
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_html"] == (
        "casp17/casp17_competitive_floor_native_provenance_operator_packet_current.html"
    )
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_completion_audit_status"] == (
        "casp17_competitive_floor_native_provenance_operator_packet_completion_audit_pass"
    )
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_completion_audit_target_count"] == 3
    assert (
        payload["summary"]["competitive_floor_native_provenance_operator_packet_completion_audit_target_pass_count"]
        == 3
    )
    assert (
        payload["summary"]["competitive_floor_native_provenance_operator_packet_completion_audit_target_blocked_count"]
        == 0
    )
    assert (
        payload["summary"]["competitive_floor_native_provenance_operator_packet_completion_audit_packet_folder_count"]
        == 3
    )
    assert (
        payload["summary"]["competitive_floor_native_provenance_operator_packet_completion_audit_packet_readme_count"]
        == 3
    )
    assert (
        payload["summary"]["competitive_floor_native_provenance_operator_packet_completion_audit_packet_manifest_count"]
        == 3
    )
    assert (
        payload["summary"]["competitive_floor_native_provenance_operator_packet_completion_audit_actions_csv_count"]
        == 3
    )
    assert (
        payload["summary"][
            "competitive_floor_native_provenance_operator_packet_completion_audit_native_candidates_csv_count"
        ]
        == 3
    )
    assert (
        payload["summary"][
            "competitive_floor_native_provenance_operator_packet_completion_audit_action_expected_row_count"
        ]
        == 12
    )
    assert (
        payload["summary"]["competitive_floor_native_provenance_operator_packet_completion_audit_action_csv_row_count"]
        == 12
    )
    assert (
        payload["summary"][
            "competitive_floor_native_provenance_operator_packet_completion_audit_action_csv_mismatch_count"
        ]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_floor_native_provenance_operator_packet_completion_audit_native_candidate_expected_row_count"
        ]
        == 5
    )
    assert (
        payload["summary"][
            "competitive_floor_native_provenance_operator_packet_completion_audit_native_candidate_csv_row_count"
        ]
        == 5
    )
    assert (
        payload["summary"][
            "competitive_floor_native_provenance_operator_packet_completion_audit_native_candidate_csv_mismatch_count"
        ]
        == 0
    )
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_completion_audit_native_action_count"] == 3
    assert (
        payload["summary"]["competitive_floor_native_provenance_operator_packet_completion_audit_evidence_action_count"]
        == 3
    )
    assert (
        payload["summary"][
            "competitive_floor_native_provenance_operator_packet_completion_audit_provenance_action_count"
        ]
        == 3
    )
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_completion_audit_manifest_action_count"] == 3
    assert (
        payload["summary"][
            "competitive_floor_native_provenance_operator_packet_completion_audit_metric_requirement_count"
        ]
        == 27
    )
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_completion_audit_prediction_count"] == 3
    assert (
        payload["summary"]["competitive_floor_native_provenance_operator_packet_completion_audit_ts_prediction_count"]
        == 3
    )
    assert (
        payload["summary"][
            "competitive_floor_native_provenance_operator_packet_completion_audit_native_dropzone_path_count"
        ]
        == 3
    )
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_completion_audit_native_file_count"] == 0
    assert (
        payload["summary"][
            "competitive_floor_native_provenance_operator_packet_completion_audit_provenance_template_count"
        ]
        == 3
    )
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_completion_audit_manifest_stub_count"] == 3
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_completion_audit_metric_runway_count"] == 3
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_completion_audit_workorder_count"] == 3
    assert (
        payload["summary"][
            "competitive_floor_native_provenance_operator_packet_completion_audit_packet_coordinate_copy_count"
        ]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_floor_native_provenance_operator_packet_completion_audit_out_dir_coordinate_copy_count"
        ]
        == 0
    )
    assert (
        payload["summary"]["competitive_floor_native_provenance_operator_packet_completion_audit_proof_eligible_count"]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_floor_native_provenance_operator_packet_completion_audit_author_serialized_count"
        ]
        == 0
    )
    assert (
        payload["summary"]["competitive_floor_native_provenance_operator_packet_completion_audit_first_target_id"]
        == "H1319"
    )
    assert (
        payload["summary"][
            "competitive_floor_native_provenance_operator_packet_completion_audit_first_blocked_target_id"
        ]
        == ""
    )
    assert payload["summary"]["competitive_floor_native_provenance_operator_packet_completion_audit_html"] == (
        "casp17/casp17_competitive_floor_native_provenance_operator_packet_completion_audit_current.html"
    )
    assert payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_status"] == (
        "casp17_competitive_floor_native_provenance_metric_unlock_bridge_blocked_awaiting_operator_values"
    )
    assert payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_target_count"] == 3
    assert payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_target_ready_count"] == 0
    assert payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_target_blocked_count"] == 3
    assert payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_packet_pass_count"] == 3
    assert (
        payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_workorder_audit_pass_count"]
        == 0
    )
    assert payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_metric_runway_ready_count"] == 0
    assert payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_metric_requirement_count"] == 27
    assert payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_prediction_count"] == 3
    assert payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_ts_prediction_count"] == 3
    assert (
        payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_native_dropzone_path_count"]
        == 3
    )
    assert payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_native_file_count"] == 0
    assert payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_provenance_template_count"] == 3
    assert payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_manifest_stub_count"] == 3
    assert payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_metric_runway_count"] == 3
    assert payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_workorder_count"] == 3
    assert payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_packet_action_count"] == 12
    assert payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_packet_native_action_count"] == 3
    assert payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_packet_evidence_action_count"] == 3
    assert (
        payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_packet_provenance_action_count"]
        == 3
    )
    assert payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_packet_manifest_action_count"] == 3
    assert payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_native_candidate_count"] == 5
    assert (
        payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_native_candidate_blocked_count"]
        == 4
    )
    assert (
        payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_native_candidate_no_candidate_count"]
        == 1
    )
    assert payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_provenance_ready_count"] == 0
    assert (
        payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_evidence_ref_verified_count"]
        == 0
    )
    assert (
        payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_identity_discovery_cleared_count"]
        == 0
    )
    assert payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_proof_eligible_count"] == 0
    assert payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_author_serialized_count"] == 0
    assert payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_first_target_id"] == "H1319"
    assert (
        payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_first_blocked_target_id"]
        == "H1319"
    )
    assert (
        payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_first_blocker"]
        == "native_pdb_missing"
    )
    assert payload["summary"]["competitive_floor_native_provenance_metric_unlock_bridge_html"] == (
        "casp17/casp17_competitive_floor_native_provenance_metric_unlock_bridge_current.html"
    )
    assert payload["summary"]["competitive_floor_first_native_provenance_unlock_kit_status"] == (
        "casp17_competitive_floor_first_native_provenance_unlock_kit_ready_for_operator_fill"
    )
    assert payload["summary"]["competitive_floor_first_native_provenance_unlock_kit_target_id"] == "H1319"
    assert payload["summary"]["competitive_floor_first_native_provenance_unlock_kit_target_count"] == 1
    assert payload["summary"]["competitive_floor_first_native_provenance_unlock_kit_required_field_count"] == 13
    assert payload["summary"]["competitive_floor_first_native_provenance_unlock_kit_required_action_count"] == 4
    assert payload["summary"]["competitive_floor_first_native_provenance_unlock_kit_action_bundle_action_count"] == 4
    assert payload["summary"]["competitive_floor_first_native_provenance_unlock_kit_packet_file_pass"] == "True"
    assert payload["summary"]["competitive_floor_first_native_provenance_unlock_kit_metric_runway_ready"] == "False"
    assert payload["summary"]["competitive_floor_first_native_provenance_unlock_kit_workorder_audit_pass"] == "False"
    assert payload["summary"]["competitive_floor_first_native_provenance_unlock_kit_prediction_count"] == 1
    assert payload["summary"]["competitive_floor_first_native_provenance_unlock_kit_ts_prediction_count"] == 1
    assert payload["summary"]["competitive_floor_first_native_provenance_unlock_kit_native_dropzone_path_count"] == 1
    assert payload["summary"]["competitive_floor_first_native_provenance_unlock_kit_native_file_count"] == 0
    assert payload["summary"]["competitive_floor_first_native_provenance_unlock_kit_provenance_template_count"] == 1
    assert payload["summary"]["competitive_floor_first_native_provenance_unlock_kit_manifest_stub_count"] == 1
    assert payload["summary"]["competitive_floor_first_native_provenance_unlock_kit_metric_runway_count"] == 1
    assert payload["summary"]["competitive_floor_first_native_provenance_unlock_kit_workorder_count"] == 1
    assert payload["summary"]["competitive_floor_first_native_provenance_unlock_kit_provenance_ready_count"] == 0
    assert payload["summary"]["competitive_floor_first_native_provenance_unlock_kit_evidence_ref_verified_count"] == 0
    assert (
        payload["summary"]["competitive_floor_first_native_provenance_unlock_kit_identity_discovery_cleared_count"]
        == 0
    )
    assert payload["summary"]["competitive_floor_first_native_provenance_unlock_kit_proof_eligible_count"] == 0
    assert payload["summary"]["competitive_floor_first_native_provenance_unlock_kit_author_serialized_count"] == 0
    assert payload["summary"]["competitive_floor_first_native_provenance_unlock_kit_coordinate_copy_count"] == 0
    assert (
        payload["summary"]["competitive_floor_first_native_provenance_unlock_kit_folder"]
        == (
            "casp17/competitive_floor_first_native_provenance_unlock_kit/"
            "H1319_Human_astrovirus_VA1_capsid_spike_antibody_7C8_complex"
        )
    )
    assert (
        payload["summary"]["competitive_floor_first_native_provenance_unlock_kit_first_blocker"]
        == "native_pdb_missing"
    )
    assert payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_status"] == (
        "casp17_competitive_floor_batch_native_provenance_unlock_kit_ready_for_operator_fill"
    )
    assert payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_target_count"] == 3
    assert payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_target_ready_count"] == 3
    assert payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_target_blocked_count"] == 0
    assert payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_target_ids"] == "H1319,H1321,H2324"
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_required_field_per_target_count"]
        == 13
    )
    assert payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_required_field_total_count"] == 39
    assert payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_required_action_count"] == 12
    assert payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_action_bundle_action_count"] == 12
    assert payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_packet_file_pass_count"] == 3
    assert payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_metric_runway_ready_count"] == 0
    assert payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_workorder_audit_pass_count"] == 0
    assert payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_prediction_count"] == 3
    assert payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_ts_prediction_count"] == 3
    assert payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_native_dropzone_path_count"] == 3
    assert payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_native_file_count"] == 0
    assert payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_provenance_template_count"] == 3
    assert payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_manifest_stub_count"] == 3
    assert payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_metric_runway_count"] == 3
    assert payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_workorder_count"] == 3
    assert payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_provenance_ready_count"] == 0
    assert payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_evidence_ref_verified_count"] == 0
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_identity_discovery_cleared_count"]
        == 0
    )
    assert payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_proof_eligible_count"] == 0
    assert payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_author_serialized_count"] == 0
    assert payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_coordinate_copy_count"] == 0
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_folder"]
        == "casp17/competitive_floor_batch_native_provenance_unlock_kit"
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_first_blocked_target_id"]
        == "H1319"
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_first_blocker"]
        == "native_pdb_missing"
    )
    assert payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_completion_audit_status"] == (
        "casp17_competitive_floor_batch_native_provenance_unlock_kit_completion_audit_pass"
    )
    assert payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_completion_audit_target_count"] == 3
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_completion_audit_target_pass_count"]
        == 3
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_completion_audit_target_blocked_count"]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_unlock_kit_completion_audit_batch_file_present_count"
        ]
        == 6
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_unlock_kit_completion_audit_batch_file_expected_count"
        ]
        == 6
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_unlock_kit_completion_audit_batch_intake_expected_count"
        ]
        == 3
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_completion_audit_batch_intake_csv_count"]
        == 3
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_unlock_kit_completion_audit_batch_intake_mismatch_count"
        ]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_unlock_kit_completion_audit_batch_action_expected_count"
        ]
        == 12
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_completion_audit_batch_action_csv_count"]
        == 12
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_unlock_kit_completion_audit_batch_action_mismatch_count"
        ]
        == 0
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_completion_audit_target_folder_count"]
        == 3
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_completion_audit_target_readme_count"]
        == 3
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_completion_audit_target_manifest_count"]
        == 3
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_unlock_kit_completion_audit_target_intake_file_count"
        ]
        == 3
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_unlock_kit_completion_audit_target_action_file_count"
        ]
        == 3
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_unlock_kit_completion_audit_target_rerun_file_count"
        ]
        == 3
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_unlock_kit_completion_audit_target_intake_expected_count"
        ]
        == 3
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_completion_audit_target_intake_csv_count"]
        == 3
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_unlock_kit_completion_audit_target_intake_mismatch_count"
        ]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_unlock_kit_completion_audit_target_action_expected_count"
        ]
        == 12
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_completion_audit_target_action_csv_count"]
        == 12
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_unlock_kit_completion_audit_target_action_mismatch_count"
        ]
        == 0
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_completion_audit_coordinate_copy_count"]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_unlock_kit_completion_audit_target_coordinate_copy_count"
        ]
        == 0
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_completion_audit_native_file_count"]
        == 0
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_completion_audit_provenance_ready_count"]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_unlock_kit_completion_audit_evidence_ref_verified_count"
        ]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_unlock_kit_completion_audit_identity_discovery_cleared_count"
        ]
        == 0
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_completion_audit_proof_eligible_count"]
        == 0
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_unlock_kit_completion_audit_author_serialized_count"]
        == 0
    )
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_gate_status"] == (
        "casp17_competitive_floor_batch_native_provenance_value_gate_blocked_awaiting_operator_values"
    )
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_gate_target_count"] == 3
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_gate_target_ready_count"] == 0
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_gate_target_blocked_count"] == 3
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_value_gate_required_field_per_target_count"]
        == 13
    )
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_gate_required_field_total_count"] == 39
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_gate_ready_value_count"] == 3
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_gate_blocked_value_count"] == 36
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_gate_native_source_ready_count"] == 0
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_gate_evidence_ref_ready_count"] == 0
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_gate_clearance_ready_count"] == 0
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_gate_date_ready_count"] == 0
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_gate_boolean_ready_count"] == 0
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_gate_coordinate_copy_count"] == 0
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_gate_target_coordinate_copy_count"] == 0
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_gate_proof_eligible_count"] == 0
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_gate_author_serialized_count"] == 0
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_value_gate_first_blocked_target_id"]
        == "H1319"
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_value_gate_first_blocker"]
        == "native_source_pdb_required"
    )
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_action_board_status"] == (
        "casp17_competitive_floor_batch_native_provenance_value_action_board_open_actions"
    )
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_action_board_target_count"] == 3
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_action_board_target_open_count"] == 3
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_action_board_target_ready_count"] == 0
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_action_board_action_count"] == 36
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_action_board_open_action_count"] == 36
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_action_board_native_action_count"] == 3
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_action_board_evidence_action_count"] == 3
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_action_board_clearance_action_count"] == 6
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_action_board_operator_action_count"] == 3
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_action_board_date_action_count"] == 6
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_action_board_boolean_action_count"] == 15
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_action_board_review_action_count"] == 0
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_action_board_coordinate_copy_count"] == 0
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_action_board_proof_eligible_count"] == 0
    assert payload["summary"]["competitive_floor_batch_native_provenance_value_action_board_author_serialized_count"] == 0
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_value_action_board_first_open_target_id"]
        == "H1319"
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_value_action_board_first_open_field"]
        == "native_source_pdb"
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_value_action_board_first_open_blocker"]
        == "native_source_pdb_required"
    )
    assert payload["summary"][
        "competitive_floor_batch_native_provenance_value_action_board_completion_audit_status"
    ] == "casp17_competitive_floor_batch_native_provenance_value_action_board_completion_audit_pass"
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_value_action_board_completion_audit_target_count"]
        == 3
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_value_action_board_completion_audit_target_pass_count"
        ]
        == 3
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_value_action_board_completion_audit_target_blocked_count"
        ]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_value_action_board_completion_audit_action_expected_count"
        ]
        == 36
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_value_action_board_completion_audit_action_json_count"
        ]
        == 36
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_value_action_board_completion_audit_action_mismatch_count"
        ]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_value_action_board_completion_audit_target_folder_count"
        ]
        == 3
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_value_action_board_completion_audit_target_readme_count"
        ]
        == 3
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_value_action_board_completion_audit_target_action_file_count"
        ]
        == 3
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_value_action_board_completion_audit_target_action_expected_count"
        ]
        == 36
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_value_action_board_completion_audit_target_action_csv_count"
        ]
        == 36
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_value_action_board_completion_audit_target_action_mismatch_count"
        ]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_value_action_board_completion_audit_coordinate_copy_count"
        ]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_value_action_board_completion_audit_target_coordinate_copy_count"
        ]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_value_action_board_completion_audit_proof_eligible_count"
        ]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_value_action_board_completion_audit_author_serialized_count"
        ]
        == 0
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_operator_fill_preflight_status"]
        == "casp17_competitive_floor_batch_native_provenance_operator_fill_preflight_ready_for_operator_fill"
    )
    assert payload["summary"]["competitive_floor_batch_native_provenance_operator_fill_preflight_target_count"] == 3
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_operator_fill_preflight_target_ready_count"]
        == 3
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_operator_fill_preflight_target_blocked_count"]
        == 0
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_operator_fill_preflight_open_action_count"]
        == 36
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_operator_fill_preflight_native_action_count"]
        == 3
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_operator_fill_preflight_evidence_action_count"]
        == 3
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_operator_fill_preflight_clearance_action_count"]
        == 6
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_operator_fill_preflight_operator_action_count"]
        == 3
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_operator_fill_preflight_date_action_count"]
        == 6
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_operator_fill_preflight_boolean_action_count"]
        == 15
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_operator_fill_preflight_review_action_count"]
        == 0
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_operator_fill_preflight_coordinate_copy_count"]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_operator_fill_preflight_target_coordinate_copy_count"
        ]
        == 0
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_operator_fill_preflight_proof_eligible_count"]
        == 0
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_operator_fill_preflight_author_serialized_count"]
        == 0
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_operator_fill_preflight_first_ready_target_id"]
        == "H1319"
    )
    assert (
        payload["summary"]["competitive_floor_batch_native_provenance_operator_fill_preflight_first_blocked_target_id"]
        == ""
    )
    assert payload["summary"]["competitive_floor_batch_native_provenance_operator_fill_preflight_first_blocker"] == ""
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_status"
        ]
        == "casp17_competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_pass"
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_target_count"
        ]
        == 3
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_target_pass_count"
        ]
        == 3
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_target_blocked_count"
        ]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_root_manifest_present"
        ]
        == 1
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_target_folder_count"
        ]
        == 3
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_target_readme_count"
        ]
        == 3
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_target_operator_template_file_count"
        ]
        == 3
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_target_field_policy_file_count"
        ]
        == 3
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_operator_template_expected_rows"
        ]
        == 3
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_operator_template_csv_rows"
        ]
        == 3
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_operator_template_row_mismatch_count"
        ]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_field_policy_expected_rows"
        ]
        == 36
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_field_policy_csv_rows"
        ]
        == 36
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_field_policy_row_mismatch_count"
        ]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_coordinate_copy_count"
        ]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_target_coordinate_copy_count"
        ]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_proof_eligible_count"
        ]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_author_serialized_count"
        ]
        == 0
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_first_blocked_target_id"
        ]
        == ""
    )
    assert (
        payload["summary"][
            "competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_first_blocker"
        ]
        == ""
    )
    assert payload["summary"]["competitive_target_identity_clearance_action_board_status"] == "open_actions"
    assert payload["summary"]["competitive_target_identity_clearance_action_board_action_count"] == 12
    assert payload["summary"]["competitive_target_identity_clearance_action_board_open_count"] == 12
    assert payload["summary"]["competitive_target_identity_clearance_action_board_native_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_action_board_evidence_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_action_board_provenance_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_action_board_manifest_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_action_bundle_status"] == "open_actions"
    assert payload["summary"]["competitive_target_identity_clearance_action_bundle_action_count"] == 12
    assert payload["summary"]["competitive_target_identity_clearance_action_bundle_open_count"] == 12
    assert payload["summary"]["competitive_target_identity_clearance_action_bundle_file_count"] == 24
    assert payload["summary"]["competitive_target_identity_clearance_action_bundle_folder_count"] == 12
    assert payload["summary"]["competitive_target_identity_clearance_action_bundle_target_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_action_bundle_native_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_action_bundle_evidence_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_action_bundle_provenance_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_action_bundle_manifest_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_promotion_status"] == "blocked_by_audit"
    assert payload["summary"]["competitive_target_identity_clearance_promotion_row_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_promotion_promoted_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_promotion_blocked_count"] == 3
    assert payload["summary"]["competitive_target_identity_clearance_promotion_ready_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_promotion_audit_pass_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_intake_staging_status"] == "waiting_on_promoted_manifest"
    assert payload["summary"]["competitive_target_identity_clearance_intake_staging_promoted_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_intake_staging_staged_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_intake_staging_blocked_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_intake_staging_open_slot_count"] == 15
    assert payload["summary"]["competitive_target_identity_clearance_intake_staging_candidate_row_count"] == 15
    assert payload["summary"]["competitive_target_identity_clearance_candidate_intake_sync_status"] == "waiting_on_staged_identity"
    assert payload["summary"]["competitive_target_identity_clearance_candidate_intake_sync_row_count"] == 15
    assert payload["summary"]["competitive_target_identity_clearance_candidate_intake_sync_ready_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_candidate_intake_sync_waiting_count"] == 15
    assert payload["summary"]["competitive_target_identity_clearance_candidate_intake_sync_blocked_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_candidate_intake_sync_applied_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_cycle_status"] == "awaiting_operator_intake"
    assert payload["summary"]["competitive_target_identity_clearance_cycle_stage_count"] == 8
    assert payload["summary"]["competitive_target_identity_clearance_cycle_ready_stage_count"] == 0
    assert payload["summary"]["competitive_target_identity_clearance_cycle_blocked_stage_count"] == 8
    assert payload["summary"]["competitive_target_identity_clearance_cycle_manifest_sync_status"] == "awaiting_provenance"
    assert payload["summary"]["competitive_target_identity_clearance_cycle_audit_status"] == "blocked"
    assert payload["summary"]["competitive_target_identity_clearance_cycle_promotion_status"] == "blocked_by_audit"
    assert payload["summary"]["competitive_target_identity_clearance_cycle_staged_count"] == 0
    assert payload["summary"]["competitive_identity_cycle_status"] == "awaiting_intake"
    assert payload["summary"]["competitive_identity_cycle_stage_count"] == 7
    assert payload["summary"]["competitive_identity_cycle_ready_stage_count"] == 1
    assert payload["summary"]["competitive_identity_cycle_blocked_stage_count"] == 6
    assert payload["summary"]["competitive_identity_cycle_sync_status"] == "awaiting_intake"
    assert payload["summary"]["competitive_identity_cycle_sync_ready_to_sync_count"] == 0
    assert payload["summary"]["competitive_identity_cycle_sync_awaiting_count"] == 15
    assert payload["summary"]["competitive_identity_cycle_missing_field_count"] == 60
    assert payload["summary"]["competitive_identity_cycle_readiness_gate_status"] == "awaiting_identity"
    assert payload["summary"]["competitive_file_source_plan_status"] == "waiting_on_identity"
    assert payload["summary"]["competitive_file_source_plan_action_count"] == 180
    assert payload["summary"]["competitive_file_source_plan_waiting_on_identity_count"] == 180
    assert payload["summary"]["competitive_file_source_plan_identity_blocked_count"] == 0
    assert payload["summary"]["competitive_file_source_plan_awaiting_source_path_count"] == 0
    assert payload["summary"]["competitive_file_source_plan_ready_for_import_count"] == 0
    assert payload["summary"]["competitive_file_source_plan_already_imported_count"] == 0
    assert payload["summary"]["competitive_file_source_plan_blocked_count"] == 0
    assert payload["summary"]["competitive_value_entry_plan_status"] == "waiting_on_identity"
    assert payload["summary"]["competitive_value_entry_plan_action_count"] == 270
    assert payload["summary"]["competitive_value_entry_plan_target_identity_count"] == 30
    assert payload["summary"]["competitive_value_entry_plan_provenance_count"] == 150
    assert payload["summary"]["competitive_value_entry_plan_calibration_count"] == 90
    assert payload["summary"]["competitive_value_entry_plan_waiting_on_identity_count"] == 270
    assert payload["summary"]["competitive_value_entry_plan_ready_from_identity_kit_count"] == 0
    assert payload["summary"]["competitive_value_entry_plan_awaiting_value_count"] == 0
    assert payload["summary"]["competitive_value_entry_plan_awaiting_clearance_count"] == 0
    assert payload["summary"]["competitive_value_entry_plan_awaiting_ref_count"] == 0
    assert payload["summary"]["competitive_value_entry_plan_ready_for_import_count"] == 0
    assert payload["summary"]["competitive_value_entry_plan_blocked_count"] == 0
    assert payload["summary"]["competitive_execution_board_status"] == "awaiting_identity"
    assert payload["summary"]["competitive_execution_board_row_count"] == 15
    assert payload["summary"]["competitive_execution_board_awaiting_identity_row_count"] == 15
    assert payload["summary"]["competitive_execution_board_ready_for_identity_apply_row_count"] == 0
    assert payload["summary"]["competitive_execution_board_awaiting_file_source_row_count"] == 0
    assert payload["summary"]["competitive_execution_board_awaiting_value_row_count"] == 0
    assert payload["summary"]["competitive_execution_board_ready_for_evidence_import_row_count"] == 0
    assert payload["summary"]["competitive_execution_board_blocked_row_count"] == 0
    assert payload["summary"]["competitive_execution_board_total_file_action_count"] == 180
    assert payload["summary"]["competitive_execution_board_total_value_action_count"] == 270
    assert payload["summary"]["competitive_execution_board_total_ready_action_count"] == 0
    assert payload["summary"]["competitive_execution_board_total_blocked_action_count"] == 450
    assert payload["summary"]["competitive_readiness_gate_status"] == "awaiting_identity"
    assert payload["summary"]["competitive_readiness_gate_count"] == 6
    assert payload["summary"]["competitive_readiness_gate_pass_count"] == 0
    assert payload["summary"]["competitive_readiness_gate_blocked_count"] == 6
    assert payload["summary"]["competitive_readiness_gate_first_blocked_gate_id"] == "identity_gate"
    assert payload["summary"]["competitive_readiness_gate_first_blocked_status"] == "awaiting_identity"
    assert payload["summary"]["competitive_value_ledger_status"] == "awaiting_values"
    assert payload["summary"]["competitive_value_ledger_count"] == 15
    assert payload["summary"]["competitive_value_ledger_action_count"] == 270
    assert payload["summary"]["competitive_value_ledger_ready_for_intake_count"] == 0
    assert payload["summary"]["competitive_value_ledger_awaiting_value_count"] == 270
    assert payload["summary"]["competitive_evidence_intake_status"] == "awaiting_evidence"
    assert payload["summary"]["competitive_evidence_intake_action_count"] == 450
    assert payload["summary"]["competitive_evidence_intake_patch_candidate_count"] == 0
    assert payload["summary"]["competitive_evidence_intake_awaiting_file_count"] == 180
    assert payload["summary"]["competitive_evidence_intake_awaiting_value_count"] == 270
    assert payload["summary"]["competitive_patch_gate_status"] == "awaiting_evidence"
    assert payload["summary"]["competitive_patch_gate_action_count"] == 450
    assert payload["summary"]["competitive_patch_gate_ready_to_patch_count"] == 0
    assert payload["summary"]["competitive_patch_gate_awaiting_evidence_count"] == 450
    assert payload["summary"]["competitive_patch_gate_conflict_count"] == 0
    assert payload["summary"]["competitive_apply_plan_status"] == "awaiting_evidence"
    assert payload["summary"]["competitive_apply_plan_action_count"] == 450
    assert payload["summary"]["competitive_apply_plan_planned_patch_count"] == 0
    assert payload["summary"]["competitive_apply_plan_awaiting_evidence_count"] == 450
    assert payload["summary"]["competitive_apply_plan_applied_count"] == 0
    assert payload["summary"]["competitive_operator_template_status"] == "blocked"
    assert payload["summary"]["competitive_operator_template_row_count"] == 15
    assert payload["summary"]["competitive_operator_template_row_fill_count"] == 0
    assert payload["summary"]["competitive_operator_preflight_status"] == "blocked"
    assert payload["summary"]["competitive_operator_preflight_row_count"] == 15
    assert payload["summary"]["missing_file_count"] == 480
    assert payload["summary"]["win_tier_goal_scorecard_status"] == "blocked_input"
    assert payload["summary"]["win_tier_goal_scorecard_pass_count"] == 1
    assert payload["summary"]["win_tier_goal_scorecard_blocked_count"] == 9
    assert payload["summary"]["win_tier_goal_scorecard_first_blocked_gate"] == "historical_identity_clearance"
    assert payload["summary"]["historical_winner_normalized_bands_status"] == (
        "blocked_strict_blind_metrics_missing"
    )
    assert payload["summary"]["historical_winner_normalized_bands_band_count"] == 5
    assert payload["summary"]["historical_winner_normalized_bands_top5_or_better_count"] == 0
    assert payload["summary"]["historical_winner_normalized_bands_winner_proximity_count"] == 0
    assert payload["summary"]["historical_winner_normalized_bands_blocked_band_count"] == 5
    assert payload["summary"]["historical_winner_normalized_bands_strict_ready_slot_count"] == 0
    assert payload["summary"]["historical_winner_normalized_bands_strict_slot_count"] == 40
    assert payload["summary"]["historical_winner_normalized_bands_metric_surface_ready_row_count"] == 0
    assert payload["summary"]["historical_winner_normalized_bands_metric_surface_row_count"] == 440
    assert payload["summary"]["historical_winner_normalized_bands_official_archive_candidate_count"] == 24
    assert payload["summary"]["historical_winner_normalized_bands_official_archive_proof_eligible_count"] == 0
    assert payload["summary"]["historical_winner_normalized_bands_first_blocked_band"] == (
        "casp15_regular_domain"
    )
    assert payload["summary"]["historical_winner_normalized_bands_first_blocker"] == (
        "strict_blind_historical_metric_surface_missing"
    )
    assert payload["summary"]["historical_winner_normalized_unlock_plan_status"] == (
        "awaiting_historical_winner_normalized_unlocks"
    )
    assert payload["summary"]["historical_winner_normalized_unlock_plan_action_count"] == 6
    assert payload["summary"]["historical_winner_normalized_unlock_plan_ready_action_count"] == 1
    assert payload["summary"]["historical_winner_normalized_unlock_plan_blocked_action_count"] == 5
    assert payload["summary"]["historical_winner_normalized_unlock_plan_strict_ready_slot_count"] == 0
    assert payload["summary"]["historical_winner_normalized_unlock_plan_strict_slot_count"] == 40
    assert payload["summary"]["historical_winner_normalized_unlock_plan_metric_surface_ready_row_count"] == 0
    assert payload["summary"]["historical_winner_normalized_unlock_plan_metric_surface_row_count"] == 440
    assert payload["summary"]["historical_winner_normalized_unlock_plan_sidechain_native_pass_count"] == 0
    assert payload["summary"]["historical_winner_normalized_unlock_plan_sidechain_native_benchmark_count"] == 40
    assert payload["summary"]["historical_winner_normalized_unlock_plan_winner_band_top5_or_better_count"] == 0
    assert payload["summary"]["historical_winner_normalized_unlock_plan_winner_band_count"] == 5
    assert payload["summary"]["historical_winner_normalized_unlock_plan_first_blocked_action"] == (
        "close_first_source_request"
    )
    assert payload["summary"]["historical_winner_normalized_unlock_plan_first_blocked_gate"] == (
        "strict_blind_internal_prediction_source"
    )
    assert payload["summary"]["historical_winner_normalized_unlock_plan_first_blocker"] == (
        "prediction_not_before_native"
    )
    assert payload["summary"]["win_tier_metric_surface_contract_status"] == (
        "awaiting_strict_blind_evidence_files_and_ligand_category_slots"
    )
    assert payload["summary"]["win_tier_metric_surface_contract_covered_metric_count"] == 11
    assert payload["summary"]["win_tier_metric_surface_contract_required_metric_count"] == 11
    assert payload["summary"]["win_tier_metric_surface_contract_blocked_slot_count"] == 40
    assert payload["summary"]["win_tier_metric_surface_contract_blocked_metric_row_count"] == 440
    assert payload["summary"]["win_tier_metric_surface_contract_ligand_slot_count"] == 0
    assert payload["summary"]["win_tier_metric_surface_contract_official_archive_policy"] == (
        "excluded_from_competitive_proof"
    )
    assert payload["summary"]["win_tier_metric_surface_contract_first_blocked_metric"] == "GDT_TS"
    assert payload["summary"]["win_tier_critical_path_status"] == (
        "competitive_proof_blocked_on_strict_blind_evidence"
    )
    assert payload["summary"]["win_tier_critical_path_stage_ready_count"] == 3
    assert payload["summary"]["win_tier_critical_path_stage_blocked_count"] == 6
    assert payload["summary"]["win_tier_critical_path_3d_ready_count"] == 4
    assert payload["summary"]["win_tier_critical_path_external_ready_target_count"] == 4
    assert payload["summary"]["win_tier_critical_path_external_model1_count"] == 4
    assert payload["summary"]["win_tier_critical_path_external_top5_count"] == 20
    assert payload["summary"]["win_tier_critical_path_strict_ready_slot_count"] == 0
    assert payload["summary"]["win_tier_critical_path_strict_slot_count"] == 40
    assert payload["summary"]["win_tier_critical_path_missing_evidence_file_count"] == 240
    assert payload["summary"]["win_tier_critical_path_operator_open_value_count"] == 400
    assert payload["summary"]["win_tier_critical_path_first_blocked_stage"] == (
        "strict_blind_batch_closure_runway"
    )
    assert payload["summary"]["strict_blind_first_slot_source_bridge_status"] == (
        "first_slot_source_bridge_internal_prediction_required"
    )
    assert payload["summary"]["strict_blind_first_slot_source_bridge_native_ready_count"] == 2
    assert payload["summary"]["strict_blind_first_slot_source_bridge_baseline_only_count"] == 24
    assert payload["summary"]["strict_blind_first_slot_source_bridge_strict_blocked_count"] == 24
    assert payload["summary"]["strict_blind_first_slot_source_bridge_operator_only_count"] == 6
    assert payload["summary"]["strict_blind_first_slot_source_bridge_internal_prediction_blocked_count"] == 1
    assert payload["summary"]["strict_blind_first_slot_source_bridge_auto_apply_count"] == 0
    assert payload["summary"]["strict_blind_internal_prediction_source_audit_status"] == (
        "internal_prediction_source_missing_for_first_slot"
    )
    assert payload["summary"]["strict_blind_internal_prediction_source_audit_local_eligible_count"] == 0
    assert payload["summary"]["strict_blind_internal_prediction_source_audit_source_route_allowed_count"] == 0
    assert payload["summary"]["strict_blind_internal_prediction_source_audit_official_blocked_count"] == 24
    assert payload["summary"]["strict_blind_internal_prediction_source_audit_native_ready_count"] == 2
    assert payload["summary"]["strict_blind_internal_prediction_source_audit_internal_blocked_count"] == 1
    assert payload["summary"]["strict_blind_internal_prediction_source_audit_allowed_internal_source_count"] == 0
    assert payload["summary"]["strict_blind_internal_prediction_source_audit_template_count"] == 1
    assert payload["summary"]["strict_blind_internal_candidate_filesystem_sweep_status"] == (
        "strict_blind_filesystem_sweep_operator_review_required"
    )
    assert payload["summary"]["strict_blind_internal_candidate_filesystem_sweep_file_count"] == 9968
    assert payload["summary"]["strict_blind_internal_candidate_filesystem_sweep_atom_like_count"] == 9968
    assert payload["summary"]["strict_blind_internal_candidate_filesystem_sweep_verified_count"] == 0
    assert payload["summary"]["strict_blind_internal_candidate_filesystem_sweep_unknown_count"] == 4551
    assert payload["summary"]["strict_blind_internal_candidate_filesystem_sweep_current_count"] == 1810
    assert payload["summary"]["strict_blind_internal_candidate_filesystem_sweep_massivefold_count"] == 2895
    assert payload["summary"]["strict_blind_internal_candidate_filesystem_sweep_official_count"] == 387
    assert payload["summary"]["strict_blind_internal_candidate_filesystem_sweep_native_count"] == 257
    assert payload["summary"]["strict_blind_internal_candidate_filesystem_sweep_top5_count"] == 75
    assert payload["summary"]["strict_blind_internal_candidate_filesystem_sweep_dropzone_count"] == 0
    assert payload["summary"]["strict_blind_internal_candidate_filesystem_sweep_first_unknown"] == (
        "archives/old_internal/candidate.pdb"
    )
    assert payload["summary"]["strict_blind_unknown_candidate_triage_status"] == (
        "strict_blind_unknown_triage_internal_like_review_required"
    )
    assert payload["summary"]["strict_blind_unknown_candidate_triage_unknown_count"] == 4551
    assert payload["summary"]["strict_blind_unknown_candidate_triage_sweep_unknown_count"] == 4551
    assert payload["summary"]["strict_blind_unknown_candidate_triage_promotion_ready_count"] == 0
    assert payload["summary"]["strict_blind_unknown_candidate_triage_internal_like_count"] == 166
    assert payload["summary"]["strict_blind_unknown_candidate_triage_public_count"] == 3962
    assert payload["summary"]["strict_blind_unknown_candidate_triage_run_review_count"] == 406
    assert payload["summary"]["strict_blind_unknown_candidate_triage_archive_count"] == 16
    assert payload["summary"]["strict_blind_unknown_candidate_triage_data_other_count"] == 0
    assert payload["summary"]["strict_blind_unknown_candidate_triage_tmp_misc_count"] == 1
    assert payload["summary"]["strict_blind_unknown_candidate_triage_other_count"] == 0
    assert payload["summary"]["strict_blind_unknown_candidate_triage_first_internal"] == (
        "data/internal_structures/nightly/internal_candidate.pdb"
    )
    assert payload["summary"]["strict_blind_internal_like_source_review_status"] == (
        "strict_blind_internal_like_source_review_all_post_native"
    )
    assert payload["summary"]["strict_blind_internal_like_source_review_candidate_count"] == 166
    assert payload["summary"]["strict_blind_internal_like_source_review_triage_internal_like_count"] == 166
    assert payload["summary"]["strict_blind_internal_like_source_review_triage_count_match"] == "True"
    assert payload["summary"]["strict_blind_internal_like_source_review_mapped_candidate_count"] == 166
    assert payload["summary"]["strict_blind_internal_like_source_review_pre_native_candidate_count"] == 0
    assert payload["summary"]["strict_blind_internal_like_source_review_post_native_blocked_count"] == 166
    assert payload["summary"]["strict_blind_internal_like_source_review_same_day_timestamp_required_count"] == 0
    assert payload["summary"]["strict_blind_internal_like_source_review_prediction_date_missing_count"] == 0
    assert payload["summary"]["strict_blind_internal_like_source_review_unmapped_candidate_count"] == 0
    assert payload["summary"]["strict_blind_internal_like_source_review_promotion_ready_count"] == 0
    assert payload["summary"]["strict_blind_internal_like_source_review_target_count"] == 10
    assert payload["summary"]["strict_blind_internal_like_source_review_target_all_post_native_count"] == 10
    assert payload["summary"]["strict_blind_internal_like_source_review_target_pre_native_candidate_count"] == 0
    assert payload["summary"]["strict_blind_internal_like_source_review_earliest_prediction_date"] == "2026-02-19"
    assert payload["summary"]["strict_blind_internal_like_source_review_latest_prediction_date"] == "2026-02-22"
    assert payload["summary"]["strict_blind_internal_like_source_review_first_blocked_target_id"] == "HIST_BBA5"
    assert payload["summary"]["strict_blind_internal_like_source_review_first_blocker"] == "prediction_not_before_native"
    assert payload["summary"]["strict_blind_internal_prediction_source_gate_status"] == (
        "awaiting_internal_prediction_source_gate_fields"
    )
    assert payload["summary"]["strict_blind_internal_prediction_source_gate_manifest_row_count"] == 1
    assert payload["summary"]["strict_blind_internal_prediction_source_gate_pass_count"] == 3
    assert payload["summary"]["strict_blind_internal_prediction_source_gate_blocked_count"] == 13
    assert payload["summary"]["strict_blind_internal_prediction_source_gate_check_count"] == 16
    assert payload["summary"]["strict_blind_internal_prediction_source_gate_first_blocked_check"] == (
        "source_id_internal"
    )
    assert payload["summary"]["strict_blind_internal_prediction_source_gate_first_blocker"] == (
        "internal_source_id_missing_or_external"
    )
    assert payload["summary"]["strict_blind_source_gate_field_board_status"] == (
        "awaiting_source_gate_field_fills"
    )
    assert payload["summary"]["strict_blind_source_gate_field_board_field_action_count"] == 11
    assert payload["summary"]["strict_blind_source_gate_field_board_manifest_value_action_count"] == 9
    assert payload["summary"]["strict_blind_source_gate_field_board_file_action_count"] == 2
    assert payload["summary"]["strict_blind_source_gate_field_board_manifest_file_action_count"] == 0
    assert payload["summary"]["strict_blind_source_gate_field_board_blocked_check_covered_count"] == 13
    assert payload["summary"]["strict_blind_source_gate_field_board_first_field_key"] == "source_id"
    assert payload["summary"]["strict_blind_source_gate_field_board_first_blockers"] == (
        "internal_source_id_missing_or_external"
    )
    assert payload["summary"]["strict_blind_source_gate_operator_packet_status"] == (
        "awaiting_source_gate_operator_values"
    )
    assert payload["summary"]["strict_blind_source_gate_operator_packet_field_action_count"] == 11
    assert payload["summary"]["strict_blind_source_gate_operator_packet_operator_ready_count"] == 0
    assert payload["summary"]["strict_blind_source_gate_operator_packet_operator_awaiting_count"] == 11
    assert payload["summary"]["strict_blind_source_gate_operator_packet_manifest_patch_count"] == 9
    assert payload["summary"]["strict_blind_source_gate_operator_packet_file_copy_count"] == 1
    assert payload["summary"]["strict_blind_source_gate_operator_packet_derived_check_count"] == 1
    assert payload["summary"]["strict_blind_source_gate_operator_packet_patch_ready_count"] == 0
    assert payload["summary"]["strict_blind_source_gate_operator_packet_patch_awaiting_count"] == 11
    assert payload["summary"]["strict_blind_source_gate_operator_packet_first_field_key"] == "source_id"
    assert payload["summary"]["strict_blind_source_gate_operator_packet_first_operator_status"] == (
        "awaiting_operator_value"
    )
    assert payload["summary"]["strict_blind_source_gate_source_request_packet_status"] == (
        "awaiting_pre_native_source_or_candidate_replacement"
    )
    assert payload["summary"]["strict_blind_source_gate_source_request_packet_request_count"] == 17
    assert payload["summary"]["strict_blind_source_gate_source_request_packet_pre_native_source_count"] == 10
    assert payload["summary"]["strict_blind_source_gate_source_request_packet_candidate_replacement_count"] == 7
    assert payload["summary"]["strict_blind_source_gate_source_request_packet_operator_repair_count"] == 0
    assert payload["summary"]["strict_blind_source_gate_source_request_packet_operator_template_ready_count"] == 0
    assert payload["summary"]["strict_blind_source_gate_source_request_packet_operator_template_awaiting_count"] == 17
    assert payload["summary"]["strict_blind_source_gate_source_request_packet_operator_field_count"] == 187
    assert payload["summary"]["strict_blind_source_gate_source_request_packet_operator_field_filled_count"] == 0
    assert payload["summary"]["strict_blind_source_gate_source_request_packet_operator_field_missing_count"] == 187
    assert payload["summary"]["strict_blind_source_gate_source_request_packet_monomer_request_count"] == 10
    assert payload["summary"]["strict_blind_source_gate_source_request_packet_complex_request_count"] == 7
    assert payload["summary"]["strict_blind_source_gate_source_request_packet_first_request_id"] == (
        "source_request_001"
    )
    assert payload["summary"]["strict_blind_source_gate_source_request_packet_first_target_id"] == "HIST_BBA5"
    assert payload["summary"]["strict_blind_source_gate_source_request_packet_first_kind"] == (
        "pre_native_prediction_source_required"
    )
    assert payload["summary"]["strict_blind_source_gate_source_request_packet_first_blocker"] == (
        "prediction_not_before_native"
    )
    assert payload["summary"]["strict_blind_source_gate_source_request_packet_first_missing_operator_field"] == (
        "source_id"
    )
    assert payload["summary"]["strict_blind_source_request_resolution_board_status"] == (
        "source_request_resolution_all_current_candidates_blocked"
    )
    assert payload["summary"]["strict_blind_source_request_resolution_board_request_count"] == 17
    assert payload["summary"]["strict_blind_source_request_resolution_board_ready_count"] == 0
    assert payload["summary"]["strict_blind_source_request_resolution_board_blocked_count"] == 17
    assert payload["summary"]["strict_blind_source_request_resolution_board_monomer_count"] == 10
    assert payload["summary"]["strict_blind_source_request_resolution_board_complex_count"] == 7
    assert payload["summary"]["strict_blind_source_request_resolution_board_all_post_native_monomer_count"] == 10
    assert payload["summary"]["strict_blind_source_request_resolution_board_candidate_replacement_required_count"] == 7
    assert payload["summary"]["strict_blind_source_request_resolution_board_pre_native_review_possible_count"] == 0
    assert payload["summary"]["strict_blind_source_request_resolution_board_chronology_review_missing_count"] == 0
    assert payload["summary"]["strict_blind_source_request_resolution_board_internal_like_post_native_candidate_count"] == 166
    assert payload["summary"]["strict_blind_source_request_resolution_board_internal_like_pre_native_candidate_count"] == 0
    assert payload["summary"]["strict_blind_source_request_resolution_board_first_blocked_request_id"] == (
        "source_request_001"
    )
    assert payload["summary"]["strict_blind_source_request_resolution_board_first_blocked_target_id"] == "HIST_BBA5"
    assert payload["summary"]["strict_blind_source_request_resolution_board_first_blocker"] == (
        "all_internal_like_candidates_post_native"
    )
    assert payload["summary"]["strict_blind_source_request_fulfillment_gate_status"] == (
        "awaiting_source_request_operator_values"
    )
    assert payload["summary"]["strict_blind_source_request_fulfillment_gate_ready_request_count"] == 0
    assert payload["summary"]["strict_blind_source_request_fulfillment_gate_blocked_request_count"] == 17
    assert payload["summary"]["strict_blind_source_request_fulfillment_gate_request_count"] == 17
    assert payload["summary"]["strict_blind_source_request_fulfillment_gate_operator_field_filled_count"] == 0
    assert payload["summary"]["strict_blind_source_request_fulfillment_gate_operator_field_missing_count"] == 187
    assert payload["summary"]["strict_blind_source_request_fulfillment_gate_operator_evidence_ref_count"] == 0
    assert payload["summary"]["strict_blind_source_request_fulfillment_gate_operator_evidence_ref_missing_count"] == 153
    assert payload["summary"]["strict_blind_source_request_fulfillment_gate_prediction_pdb_valid_count"] == 0
    assert payload["summary"]["strict_blind_source_request_fulfillment_gate_chronology_pass_count"] == 0
    assert payload["summary"]["strict_blind_source_request_fulfillment_gate_internal_source_pass_count"] == 0
    assert payload["summary"]["strict_blind_source_request_fulfillment_gate_first_blocker"] == "source_id_missing"
    assert payload["summary"]["strict_blind_source_request_operator_fill_worklist_status"] == (
        "awaiting_source_request_operator_values"
    )
    assert payload["summary"]["strict_blind_source_request_operator_fill_worklist_field_ready_count"] == 0
    assert payload["summary"]["strict_blind_source_request_operator_fill_worklist_operator_value_missing_count"] == 187
    assert payload["summary"]["strict_blind_source_request_operator_fill_worklist_operator_evidence_missing_count"] == 153
    assert payload["summary"]["strict_blind_source_request_operator_fill_worklist_field_action_count"] == 187
    assert payload["summary"]["strict_blind_source_request_operator_fill_worklist_candidate_replacement_field_count"] == 77
    assert payload["summary"]["strict_blind_source_request_operator_fill_worklist_first_request_id"] == (
        "source_request_001"
    )
    assert payload["summary"]["strict_blind_source_request_operator_fill_worklist_first_field_key"] == "source_id"
    assert payload["summary"]["strict_blind_source_request_operator_fill_worklist_first_blocker"] == (
        "operator_value_missing"
    )
    assert payload["summary"]["strict_blind_source_request_operator_sync_plan_status"] == (
        "awaiting_source_request_fulfillment"
    )
    assert payload["summary"]["strict_blind_source_request_operator_sync_plan_mode"] == "dry_run"
    assert payload["summary"]["strict_blind_source_request_operator_sync_plan_ready_request_count"] == 0
    assert payload["summary"]["strict_blind_source_request_operator_sync_plan_blocked_request_count"] == 17
    assert payload["summary"]["strict_blind_source_request_operator_sync_plan_sync_action_count"] == 0
    assert payload["summary"]["strict_blind_source_request_operator_sync_plan_ready_sync_action_count"] == 0
    assert payload["summary"]["strict_blind_source_request_operator_sync_plan_blocked_sync_action_count"] == 1
    assert payload["summary"]["strict_blind_source_request_operator_sync_plan_applied_sync_action_count"] == 0
    assert payload["summary"]["strict_blind_source_request_operator_sync_plan_first_blocker"] == "source_id_missing"
    assert payload["summary"]["strict_blind_source_request_closure_board_status"] == (
        "awaiting_strict_blind_source_request_closure"
    )
    assert payload["summary"]["strict_blind_source_request_closure_board_required_benchmark_id"] == (
        "hist_REQUIRED_MONOMER_001"
    )
    assert payload["summary"]["strict_blind_source_request_closure_board_required_target_id"] == (
        "REQUIRED_MONOMER_001"
    )
    assert payload["summary"]["strict_blind_source_request_closure_board_required_scope"] == "monomer"
    assert payload["summary"]["strict_blind_source_request_closure_board_stage_count"] == 13
    assert payload["summary"]["strict_blind_source_request_closure_board_ready_stage_count"] == 0
    assert payload["summary"]["strict_blind_source_request_closure_board_blocked_stage_count"] == 13
    assert payload["summary"]["strict_blind_source_request_closure_board_first_blocked_stage_id"] == (
        "source_request_packet"
    )
    assert payload["summary"]["strict_blind_source_request_closure_board_first_blocked_stage_status"] == (
        "awaiting_pre_native_source_or_candidate_replacement"
    )
    assert payload["summary"]["strict_blind_source_request_closure_board_first_blocker"] == (
        "prediction_not_before_native"
    )
    assert payload["summary"]["strict_blind_source_request_closure_board_next_action"] == (
        "attach pre-native source"
    )
    assert payload["summary"]["strict_blind_source_request_closure_board_source_request_status"] == (
        "awaiting_pre_native_source_or_candidate_replacement"
    )
    assert payload["summary"]["strict_blind_source_request_closure_board_fulfillment_gate_status"] == (
        "awaiting_source_request_operator_values"
    )
    assert payload["summary"]["strict_blind_source_request_closure_board_operator_fill_worklist_status"] == (
        "awaiting_source_request_operator_values"
    )
    assert payload["summary"]["strict_blind_source_request_closure_board_operator_sync_plan_status"] == (
        "awaiting_source_request_fulfillment"
    )
    assert payload["summary"]["strict_blind_source_request_closure_board_first_unlock_handoff_status"] == (
        "awaiting_first_unlock_operator_values"
    )
    assert payload["summary"][
        "strict_blind_source_request_closure_board_first_unlock_evidence_packet_status"
    ] == "awaiting_first_unlock_evidence_collection"
    assert payload["summary"][
        "strict_blind_source_request_closure_board_first_unlock_evidence_review_gate_status"
    ] == "awaiting_first_unlock_evidence_review"
    assert payload["summary"][
        "strict_blind_source_request_closure_board_first_unlock_evidence_sync_plan_status"
    ] == "awaiting_first_unlock_evidence_review"
    assert payload["summary"]["strict_blind_source_request_closure_board_source_gate_operator_packet_status"] == (
        "awaiting_source_gate_operator_values"
    )
    assert payload["summary"][
        "strict_blind_source_request_closure_board_internal_prediction_source_gate_status"
    ] == "awaiting_internal_prediction_source_gate_fields"
    assert payload["summary"][
        "strict_blind_source_request_closure_board_internal_prediction_apply_plan_status"
    ] == "blocked_until_internal_prediction_source_gate_passes"
    assert payload["summary"]["strict_blind_source_request_closure_board_first_slot_closure_kit_status"] == (
        "blocked_on_internal_prediction_source_gate"
    )
    assert payload["summary"]["strict_blind_source_request_closure_board_batch_closure_runway_status"] == (
        "blocked_on_first_slot_internal_prediction_source"
    )
    assert payload["summary"]["strict_blind_first_source_request_pickup_status"] == (
        "first_source_request_requires_pre_native_source"
    )
    assert payload["summary"]["strict_blind_first_source_request_pickup_request_id"] == "source_request_001"
    assert payload["summary"]["strict_blind_first_source_request_pickup_candidate_target_id"] == "HIST_BBA5"
    assert payload["summary"]["strict_blind_first_source_request_pickup_candidate_scope"] == "monomer"
    assert payload["summary"]["strict_blind_first_source_request_pickup_request_kind"] == (
        "pre_native_prediction_source_required"
    )
    assert payload["summary"]["strict_blind_first_source_request_pickup_current_prediction_before_native"] == (
        "False"
    )
    assert payload["summary"]["strict_blind_first_source_request_pickup_current_prediction_created_at"] == (
        "2026-02-19"
    )
    assert payload["summary"]["strict_blind_first_source_request_pickup_native_release_date"] == (
        "2004-05-13"
    )
    assert payload["summary"]["strict_blind_first_source_request_pickup_option_count"] == 3
    assert payload["summary"]["strict_blind_first_source_request_pickup_ready_option_count"] == 0
    assert payload["summary"]["strict_blind_first_source_request_pickup_blocked_option_count"] == 3
    assert payload["summary"]["strict_blind_first_source_request_pickup_external_required_count"] == 10
    assert payload["summary"]["strict_blind_first_source_request_pickup_external_target_count"] == 10
    assert payload["summary"]["strict_blind_first_source_request_pickup_first_action_id"] == (
        "first_source_pickup_001"
    )
    assert payload["summary"]["strict_blind_first_source_request_pickup_first_blocker"] == (
        "prediction_not_before_native"
    )
    assert payload["summary"]["strict_blind_first_unlock_handoff_status"] == (
        "awaiting_first_unlock_operator_values"
    )
    assert payload["summary"]["strict_blind_first_unlock_handoff_required_benchmark_id"] == (
        "hist_REQUIRED_MONOMER_001"
    )
    assert payload["summary"]["strict_blind_first_unlock_handoff_required_target_id"] == (
        "REQUIRED_MONOMER_001"
    )
    assert payload["summary"]["strict_blind_first_unlock_handoff_request_id"] == "source_request_001"
    assert payload["summary"]["strict_blind_first_unlock_handoff_candidate_target_id"] == "HIST_BBA5"
    assert payload["summary"]["strict_blind_first_unlock_handoff_field_count"] == 11
    assert payload["summary"]["strict_blind_first_unlock_handoff_ready_field_count"] == 0
    assert payload["summary"]["strict_blind_first_unlock_handoff_blocked_field_count"] == 11
    assert payload["summary"]["strict_blind_first_unlock_handoff_first_blocked_field_key"] == "source_id"
    assert payload["summary"]["strict_blind_first_unlock_handoff_first_blocker"] == "operator_value_missing"
    assert payload["summary"]["strict_blind_first_unlock_handoff_first_next_action"] == (
        "fill operator_value for source_id"
    )
    assert payload["summary"]["strict_blind_first_unlock_handoff_current_prediction_created_at"] == (
        "2026-02-19"
    )
    assert payload["summary"]["strict_blind_first_unlock_handoff_current_native_release_date"] == (
        "2004-05-13"
    )
    assert payload["summary"]["strict_blind_first_unlock_evidence_packet_status"] == (
        "awaiting_first_unlock_evidence_collection"
    )
    assert payload["summary"]["strict_blind_first_unlock_evidence_packet_request_id"] == (
        "source_request_001"
    )
    assert payload["summary"]["strict_blind_first_unlock_evidence_packet_candidate_target_id"] == (
        "HIST_BBA5"
    )
    assert payload["summary"]["strict_blind_first_unlock_evidence_packet_field_count"] == 11
    assert payload["summary"]["strict_blind_first_unlock_evidence_packet_ready_field_count"] == 0
    assert payload["summary"]["strict_blind_first_unlock_evidence_packet_open_field_count"] == 11
    assert payload["summary"]["strict_blind_first_unlock_evidence_packet_evidence_stub_count"] == 11
    assert payload["summary"]["strict_blind_first_unlock_evidence_packet_file_field_count"] == 2
    assert payload["summary"]["strict_blind_first_unlock_evidence_packet_first_open_field"] == (
        "source_id"
    )
    assert payload["summary"]["strict_blind_first_unlock_evidence_packet_first_blocker"] == (
        "operator_value_missing"
    )
    assert payload["summary"]["strict_blind_first_unlock_evidence_review_gate_status"] == (
        "awaiting_first_unlock_evidence_review"
    )
    assert payload["summary"]["strict_blind_first_unlock_evidence_review_gate_request_id"] == (
        "source_request_001"
    )
    assert payload["summary"]["strict_blind_first_unlock_evidence_review_gate_candidate_target_id"] == (
        "HIST_BBA5"
    )
    assert payload["summary"]["strict_blind_first_unlock_evidence_review_gate_field_count"] == 11
    assert payload["summary"]["strict_blind_first_unlock_evidence_review_gate_ready_field_count"] == 0
    assert payload["summary"]["strict_blind_first_unlock_evidence_review_gate_blocked_field_count"] == 11
    assert payload["summary"][
        "strict_blind_first_unlock_evidence_review_gate_template_operator_value_missing_count"
    ] == 11
    assert payload["summary"][
        "strict_blind_first_unlock_evidence_review_gate_template_operator_evidence_ref_missing_count"
    ] == 0
    assert payload["summary"][
        "strict_blind_first_unlock_evidence_review_gate_template_operator_clearance_missing_count"
    ] == 11
    assert payload["summary"][
        "strict_blind_first_unlock_evidence_review_gate_template_operator_id_missing_count"
    ] == 11
    assert payload["summary"]["strict_blind_first_unlock_evidence_review_gate_stub_present_count"] == 11
    assert payload["summary"][
        "strict_blind_first_unlock_evidence_review_gate_stub_evidence_missing_count"
    ] == 11
    assert payload["summary"]["strict_blind_first_unlock_evidence_review_gate_policy_pass_count"] == 0
    assert payload["summary"]["strict_blind_first_unlock_evidence_review_gate_policy_blocked_count"] == 11
    assert payload["summary"]["strict_blind_first_unlock_evidence_review_gate_file_ready_count"] == 0
    assert payload["summary"]["strict_blind_first_unlock_evidence_review_gate_file_blocked_count"] == 2
    assert payload["summary"]["strict_blind_first_unlock_evidence_review_gate_first_blocked_field"] == (
        "source_id"
    )
    assert payload["summary"]["strict_blind_first_unlock_evidence_review_gate_first_blocker"] == (
        "template_operator_value_missing"
    )
    assert payload["summary"]["strict_blind_first_slot_source_gate_blocker_ledger_status"] == (
        "awaiting_first_slot_source_gate_operator_evidence"
    )
    assert payload["summary"]["strict_blind_first_slot_source_gate_blocker_ledger_required_benchmark_id"] == (
        "hist_REQUIRED_MONOMER_001"
    )
    assert payload["summary"]["strict_blind_first_slot_source_gate_blocker_ledger_required_target_id"] == (
        "REQUIRED_MONOMER_001"
    )
    assert payload["summary"]["strict_blind_first_slot_source_gate_blocker_ledger_required_scope"] == "monomer"
    assert payload["summary"]["strict_blind_first_slot_source_gate_blocker_ledger_field_count"] == 11
    assert payload["summary"]["strict_blind_first_slot_source_gate_blocker_ledger_ready_field_count"] == 0
    assert payload["summary"]["strict_blind_first_slot_source_gate_blocker_ledger_blocked_field_count"] == 11
    assert payload["summary"]["strict_blind_first_slot_source_gate_blocker_ledger_gate_pass_count"] == 3
    assert payload["summary"]["strict_blind_first_slot_source_gate_blocker_ledger_gate_blocked_count"] == 13
    assert payload["summary"]["strict_blind_first_slot_source_gate_blocker_ledger_gate_check_count"] == 16
    assert payload["summary"]["strict_blind_first_slot_source_gate_blocker_ledger_operator_ready_count"] == 0
    assert payload["summary"]["strict_blind_first_slot_source_gate_blocker_ledger_operator_awaiting_count"] == 11
    assert payload["summary"]["strict_blind_first_slot_source_gate_blocker_ledger_review_ready_count"] == 0
    assert payload["summary"]["strict_blind_first_slot_source_gate_blocker_ledger_review_blocked_count"] == 11
    assert payload["summary"]["strict_blind_first_slot_source_gate_blocker_ledger_file_ready_count"] == 0
    assert payload["summary"]["strict_blind_first_slot_source_gate_blocker_ledger_file_blocked_count"] == 2
    assert payload["summary"]["strict_blind_first_slot_source_gate_blocker_ledger_first_blocked_field"] == (
        "source_id"
    )
    assert payload["summary"]["strict_blind_first_slot_source_gate_blocker_ledger_first_blocker"] == (
        "template_operator_value_missing"
    )
    assert payload["summary"]["strict_blind_first_unlock_evidence_sync_plan_status"] == (
        "awaiting_first_unlock_evidence_review"
    )
    assert payload["summary"]["strict_blind_first_unlock_evidence_sync_plan_mode"] == "dry_run"
    assert payload["summary"]["strict_blind_first_unlock_evidence_sync_plan_review_gate_status"] == (
        "awaiting_first_unlock_evidence_review"
    )
    assert payload["summary"]["strict_blind_first_unlock_evidence_sync_plan_request_id"] == (
        "source_request_001"
    )
    assert payload["summary"]["strict_blind_first_unlock_evidence_sync_plan_candidate_target_id"] == (
        "HIST_BBA5"
    )
    assert payload["summary"]["strict_blind_first_unlock_evidence_sync_plan_action_count"] == 11
    assert payload["summary"]["strict_blind_first_unlock_evidence_sync_plan_ready_action_count"] == 0
    assert payload["summary"]["strict_blind_first_unlock_evidence_sync_plan_blocked_action_count"] == 11
    assert payload["summary"]["strict_blind_first_unlock_evidence_sync_plan_applied_action_count"] == 0
    assert payload["summary"]["strict_blind_first_unlock_evidence_sync_plan_review_ready_field_count"] == 0
    assert payload["summary"]["strict_blind_first_unlock_evidence_sync_plan_review_blocked_field_count"] == 11
    assert payload["summary"]["strict_blind_first_unlock_evidence_sync_plan_first_action_id"] == (
        "first_unlock_evidence_sync_001"
    )
    assert payload["summary"]["strict_blind_first_unlock_evidence_sync_plan_first_blocked_field"] == (
        "source_id"
    )
    assert payload["summary"]["strict_blind_first_unlock_evidence_sync_plan_first_blocker"] == (
        "template_operator_value_missing"
    )
    assert payload["summary"]["strict_blind_internal_prediction_source_apply_plan_status"] == (
        "blocked_until_internal_prediction_source_gate_passes"
    )
    assert payload["summary"]["strict_blind_internal_prediction_source_apply_plan_ready_action_count"] == 0
    assert payload["summary"]["strict_blind_internal_prediction_source_apply_plan_blocked_action_count"] == 16
    assert payload["summary"]["strict_blind_internal_prediction_source_apply_plan_action_count"] == 16
    assert payload["summary"]["strict_blind_internal_prediction_source_apply_plan_file_action_count"] == 1
    assert payload["summary"]["strict_blind_internal_prediction_source_apply_plan_operator_value_action_count"] == 10
    assert payload["summary"]["strict_blind_internal_prediction_source_apply_plan_supplemental_action_count"] == 5
    assert payload["summary"]["strict_blind_internal_prediction_source_apply_plan_first_blocked_action_id"] == (
        "internal_prediction_apply_001"
    )
    assert payload["summary"]["strict_blind_internal_prediction_source_apply_plan_first_blocker"] == (
        "internal_prediction_source_gate_not_ready"
    )
    assert payload["summary"]["strict_blind_first_slot_closure_kit_status"] == (
        "blocked_on_internal_prediction_source_gate"
    )
    assert payload["summary"]["strict_blind_first_slot_closure_kit_step_ready_count"] == 0
    assert payload["summary"]["strict_blind_first_slot_closure_kit_step_blocked_count"] == 7
    assert payload["summary"]["strict_blind_first_slot_closure_kit_step_count"] == 7
    assert payload["summary"]["strict_blind_first_slot_closure_kit_source_gate_fill_count"] == 11
    assert payload["summary"]["strict_blind_first_slot_closure_kit_source_request_fill_count"] == 17
    assert payload["summary"]["strict_blind_first_slot_closure_kit_file_fill_count"] == 12
    assert payload["summary"]["strict_blind_first_slot_closure_kit_operator_fill_count"] == 20
    assert payload["summary"]["strict_blind_first_slot_closure_kit_fill_item_count"] == 60
    assert payload["summary"]["strict_blind_first_slot_closure_kit_source_request_packet_status"] == (
        "awaiting_pre_native_source_or_candidate_replacement"
    )
    assert payload["summary"]["strict_blind_first_slot_closure_kit_source_request_count"] == 17
    assert payload["summary"]["strict_blind_first_slot_closure_kit_source_request_pre_native_count"] == 10
    assert payload["summary"]["strict_blind_first_slot_closure_kit_source_request_candidate_replacement_count"] == 7
    assert payload["summary"]["strict_blind_first_slot_closure_kit_source_request_operator_repair_count"] == 0
    assert payload["summary"]["strict_blind_first_slot_closure_kit_first_blocked_step"] == (
        "internal_prediction_source_gate"
    )
    assert payload["summary"]["strict_blind_first_slot_closure_kit_first_blocker"] == (
        "internal_source_id_missing_or_external"
    )
    assert payload["summary"]["strict_blind_batch_closure_runway_status"] == (
        "blocked_on_first_slot_internal_prediction_source"
    )
    assert payload["summary"]["strict_blind_batch_closure_runway_ready_slot_count"] == 0
    assert payload["summary"]["strict_blind_batch_closure_runway_blocked_slot_count"] == 40
    assert payload["summary"]["strict_blind_batch_closure_runway_slot_count"] == 40
    assert payload["summary"]["strict_blind_batch_closure_runway_source_gate_blocked_count"] == 1
    assert payload["summary"]["strict_blind_batch_closure_runway_evidence_blocked_count"] == 39
    assert payload["summary"]["strict_blind_batch_closure_runway_file_missing_count"] == 240
    assert payload["summary"]["strict_blind_batch_closure_runway_operator_open_count"] == 400
    assert payload["summary"]["strict_blind_batch_closure_runway_first_blocked_benchmark_id"] == (
        "hist_REQUIRED_MONOMER_001"
    )
    assert payload["summary"]["organic_ligand_slot_candidate_status"] == (
        "organic_ligand_slot_candidates_ready_for_operator_review"
    )
    assert payload["summary"]["organic_ligand_slot_candidate_count"] == 2
    assert payload["summary"]["organic_ligand_slot_candidate_chembl_count"] == 1
    assert payload["summary"]["organic_ligand_slot_candidate_bindingdb_count"] == 1
    assert payload["summary"]["organic_ligand_slot_candidate_review_ready_count"] == 2
    assert payload["summary"]["organic_ligand_slot_candidate_proof_eligible_count"] == 0
    assert payload["summary"]["organic_ligand_slot_candidate_strict_blocked_count"] == 2
    assert payload["summary"]["organic_ligand_slot_candidate_reference_present_count"] == 2
    assert payload["summary"]["organic_ligand_slot_candidate_prediction_present_count"] == 2
    assert payload["summary"]["organic_ligand_slot_candidate_ligand_mol2_present_count"] == 2
    assert payload["summary"]["organic_ligand_slot_candidate_lddt_pli_required_count"] == 2
    assert payload["summary"]["organic_ligand_slot_candidate_bisyrmsd_required_count"] == 2
    assert payload["summary"]["organic_ligand_slot_candidate_affinity_label_candidate_count"] == 1
    assert payload["summary"]["organic_ligand_slot_candidate_first_target_id"] == (
        "HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005"
    )
    assert payload["summary"]["organic_ligand_slot_promotion_action_board_status"] == (
        "awaiting_organic_ligand_strict_blind_evidence"
    )
    assert payload["summary"]["organic_ligand_slot_promotion_candidate_count"] == 2
    assert payload["summary"]["organic_ligand_slot_promotion_action_count"] == 18
    assert payload["summary"]["organic_ligand_slot_promotion_open_action_count"] == 16
    assert payload["summary"]["organic_ligand_slot_promotion_reference_preflight_pass_count"] == 2
    assert payload["summary"]["organic_ligand_slot_promotion_operator_evidence_required_count"] == 8
    assert payload["summary"]["organic_ligand_slot_promotion_numeric_value_required_count"] == 1
    assert payload["summary"]["organic_ligand_slot_promotion_affinity_source_required_count"] == 1
    assert payload["summary"]["organic_ligand_slot_promotion_metric_input_required_count"] == 4
    assert payload["summary"]["organic_ligand_slot_promotion_slot_mapping_required_count"] == 2
    assert payload["summary"]["organic_ligand_slot_promotion_proof_ready_candidate_count"] == 0
    assert payload["summary"]["organic_ligand_slot_promotion_first_open_action_type"] == (
        "direct_native_or_source_authority"
    )
    assert payload["summary"]["active_scope_decision_status"] == "casp17_only_active"
    assert payload["summary"]["active_competition_scope"] == "casp17_only"
    assert payload["summary"]["active_scope_casp17_continuation_status"] == "active"
    assert payload["summary"]["active_scope_casp17_priority_status"] == "historical_benchmark_then_competitive_floor"
    assert payload["summary"]["active_scope_capri_round65_participation_status"] == "deferred_pi_required"
    assert payload["summary"]["active_scope_active_lane_count"] == 3
    assert payload["summary"]["active_scope_deferred_lane_count"] == 1
    assert payload["summary"]["active_scope_row_count"] == 4
    assert payload["summary"]["organizer_notice_status"] == "organizer_notice_intake_ready"
    assert payload["summary"]["organizer_notice_r2345_first_request_status"] == (
        "ignored_invalid_dna_t_in_rna_sequence"
    )
    assert payload["summary"]["organizer_notice_r2345_replacement_request_status"] == "accepted_second_request_only"
    assert payload["summary"]["organizer_notice_massivefold_generation_scope"] == (
        "all_human_rna_and_hybrid_targets_plus_protein_targets"
    )
    assert payload["summary"]["organizer_notice_massivefold_first_rna_hybrid_set_target_id"] == "R2341"
    assert payload["summary"]["organizer_notice_massivefold_link_count"] == 3
    assert payload["summary"]["organizer_notice_massivefold_rna_hybrid_link_count"] == 2
    assert payload["summary"]["organizer_notice_massivefold_internal_prediction_policy"] == (
        "do_not_mark_as_internal_prediction"
    )
    assert payload["summary"]["massivefold_external_pool_intake_status"] == "massivefold_external_pool_intake_ready"
    assert payload["summary"]["massivefold_external_pool_count"] == 3
    assert payload["summary"]["massivefold_external_pool_ready_count"] == 3
    assert payload["summary"]["massivefold_external_pool_rna_hybrid_count"] == 2
    assert payload["summary"]["massivefold_external_pool_protein_complex_count"] == 1
    assert payload["summary"]["massivefold_external_pool_proof_eligible_count"] == 0
    assert payload["summary"]["massivefold_external_pool_internal_blocked_count"] == 3
    assert payload["summary"]["massivefold_external_pool_largest_model_set_id"] == "H2335_T335"
    assert payload["summary"]["massivefold_external_pool_download_policy"] == (
        "operator_explicit_download_required_no_automatic_tarball_fetch"
    )
    assert payload["summary"]["rna_hybrid_massivefold_priority_queue_status"] == (
        "rna_hybrid_massivefold_priority_queue_ready"
    )
    assert payload["summary"]["rna_hybrid_massivefold_priority_queue_count"] == 2
    assert payload["summary"]["rna_hybrid_massivefold_priority_queue_ready_count"] == 2
    assert payload["summary"]["rna_hybrid_massivefold_priority_queue_first_target_id"] == "R2341"
    assert payload["summary"]["rna_hybrid_massivefold_priority_queue_r2341_rank"] == 1
    assert payload["summary"]["rna_hybrid_massivefold_priority_queue_r2345_rank"] == 2
    assert payload["summary"]["rna_hybrid_massivefold_priority_queue_r2345_invalid_status"] == (
        "ignored_invalid_dna_t_in_rna_sequence"
    )
    assert payload["summary"]["rna_hybrid_massivefold_priority_queue_r2345_active_status"] == (
        "accepted_second_request_only"
    )
    assert payload["summary"]["rna_hybrid_massivefold_priority_queue_proof_eligible_count"] == 0
    assert payload["summary"]["rna_hybrid_massivefold_priority_queue_internal_blocked_count"] == 2
    assert payload["summary"]["protein_complex_massivefold_priority_queue_status"] == (
        "protein_complex_massivefold_priority_queue_ready"
    )
    assert payload["summary"]["protein_complex_massivefold_priority_queue_count"] == 1
    assert payload["summary"]["protein_complex_massivefold_priority_queue_ready_count"] == 1
    assert payload["summary"]["protein_complex_massivefold_priority_queue_first_target_id"] == "H1311"
    assert payload["summary"]["protein_complex_massivefold_priority_queue_first_model_set_id"] == "H1311_T327"
    assert payload["summary"]["protein_complex_massivefold_priority_queue_largest_model_set_id"] == "H1311_T327"
    assert payload["summary"]["protein_complex_massivefold_priority_queue_largest_size_bytes"] == 1934629344
    assert payload["summary"]["protein_complex_massivefold_priority_queue_proof_eligible_count"] == 0
    assert payload["summary"]["protein_complex_massivefold_priority_queue_internal_blocked_count"] == 1
    assert payload["summary"]["massivefold_acquisition_verification_status"] == (
        "massivefold_external_pool_acquisition_verified"
    )
    assert payload["summary"]["massivefold_acquisition_verification_pool_count"] == 2
    assert payload["summary"]["massivefold_acquisition_verification_verified_count"] == 2
    assert payload["summary"]["massivefold_acquisition_verification_open_count"] == 0
    assert payload["summary"]["massivefold_acquisition_verification_tarball_present_count"] == 2
    assert payload["summary"]["massivefold_acquisition_verification_sha256_record_count"] == 2
    assert payload["summary"]["massivefold_acquisition_verification_sha256_verified_count"] == 2
    assert payload["summary"]["massivefold_acquisition_verification_listing_present_count"] == 2
    assert payload["summary"]["massivefold_acquisition_verification_listing_entry_count"] == 16080
    assert payload["summary"]["massivefold_acquisition_verification_first_priority_target_id"] == "R2341"
    assert payload["summary"]["massivefold_acquisition_verification_first_open_target_id"] == ""
    assert payload["summary"]["massivefold_acquisition_verification_r2341_status"] == (
        "verified_for_external_rerank_intake"
    )
    assert payload["summary"]["massivefold_acquisition_verification_r2345_status"] == (
        "verified_for_external_rerank_intake"
    )
    assert payload["summary"]["protein_complex_massivefold_acquisition_verification_status"] == (
        "awaiting_massivefold_external_pool_acquisition"
    )
    assert payload["summary"]["protein_complex_massivefold_acquisition_verification_pool_count"] == 1
    assert payload["summary"]["protein_complex_massivefold_acquisition_verification_verified_count"] == 0
    assert payload["summary"]["protein_complex_massivefold_acquisition_verification_open_count"] == 1
    assert payload["summary"]["protein_complex_massivefold_acquisition_verification_tarball_present_count"] == 0
    assert payload["summary"]["protein_complex_massivefold_acquisition_verification_sha256_record_count"] == 0
    assert payload["summary"]["protein_complex_massivefold_acquisition_verification_first_priority_target_id"] == "H1311"
    assert payload["summary"]["protein_complex_massivefold_acquisition_verification_first_open_target_id"] == "H1311"
    assert payload["summary"]["protein_complex_massivefold_acquisition_verification_first_open_status"] == (
        "open_tarball_download_required"
    )
    assert payload["summary"]["massivefold_model_pool_index_status"] == (
        "massivefold_model_pool_representatives_extracted"
    )
    assert payload["summary"]["massivefold_model_pool_index_target_id"] == "R2341"
    assert payload["summary"]["massivefold_model_pool_index_model_count"] == 8040
    assert payload["summary"]["massivefold_model_pool_index_protocol_count"] == 8
    assert payload["summary"]["massivefold_model_pool_index_selected_count"] == 40
    assert payload["summary"]["massivefold_model_pool_index_extracted_count"] == 40
    assert payload["summary"]["massivefold_model_pool_index_pending_count"] == 0
    assert payload["summary"]["massivefold_model_pool_index_basic_count"] == 1005
    assert payload["summary"]["massivefold_model_pool_index_wo_templates_count"] == 1005
    assert payload["summary"]["massivefold_model_pool_index_first_selected_protocol"] == (
        "woUnpaired_woPaired_woTemplates"
    )
    assert payload["summary"]["massivefold_representative_viewer_status"] == (
        "massivefold_representative_viewers_ready"
    )
    assert payload["summary"]["massivefold_representative_viewer_target_id"] == "R2341"
    assert payload["summary"]["massivefold_representative_viewer_selected_count"] == 40
    assert payload["summary"]["massivefold_representative_viewer_ready_count"] == 40
    assert payload["summary"]["massivefold_representative_viewer_blocked_count"] == 0
    assert payload["summary"]["massivefold_representative_viewer_coordinate_count"] == 40
    assert payload["summary"]["massivefold_representative_viewer_model_cif_count"] == 40
    assert payload["summary"]["massivefold_representative_viewer_projection_count"] == 40
    assert payload["summary"]["massivefold_representative_viewer_atom_count"] == 159280
    assert payload["summary"]["massivefold_representative_viewer_display_atom_count"] == 36000
    assert payload["summary"]["massivefold_representative_viewer_residue_count"] == 7440
    assert payload["summary"]["massivefold_representative_viewer_protocol_count"] == 8
    assert payload["summary"]["massivefold_representative_rerank_status"] == (
        "massivefold_representative_rerank_ready_review_only"
    )
    assert payload["summary"]["massivefold_representative_rerank_target_id"] == "R2341"
    assert payload["summary"]["massivefold_representative_rerank_candidate_count"] == 40
    assert payload["summary"]["massivefold_representative_rerank_model1_count"] == 1
    assert payload["summary"]["massivefold_representative_rerank_top5_count"] == 5
    assert payload["summary"]["massivefold_representative_rerank_top5_protocol_count"] == 5
    assert payload["summary"]["massivefold_representative_rerank_review_candidate_count"] == 35
    assert payload["summary"]["massivefold_representative_rerank_proof_eligible_count"] == 0
    assert payload["summary"]["massivefold_representative_rerank_model1_protocol"] == "basic"
    assert payload["summary"]["massivefold_rna_model_selection_coverage_status"] == (
        "massivefold_rna_model_selection_coverage_ready_review_only"
    )
    assert payload["summary"]["massivefold_rna_model_selection_coverage_target_count"] == 2
    assert payload["summary"]["massivefold_rna_model_selection_coverage_ready_target_count"] == 2
    assert payload["summary"]["massivefold_rna_model_selection_coverage_partial_target_count"] == 0
    assert payload["summary"]["massivefold_rna_model_selection_coverage_verified_acquisition_count"] == 2
    assert payload["summary"]["massivefold_rna_model_selection_coverage_representative_extracted_target_count"] == 2
    assert payload["summary"]["massivefold_rna_model_selection_coverage_viewer_ready_target_count"] == 2
    assert payload["summary"]["massivefold_rna_model_selection_coverage_rerank_ready_target_count"] == 2
    assert payload["summary"]["massivefold_rna_model_selection_coverage_selected_model_count"] == 80
    assert payload["summary"]["massivefold_rna_model_selection_coverage_extracted_model_count"] == 80
    assert payload["summary"]["massivefold_rna_model_selection_coverage_viewer_ready_model_count"] == 80
    assert payload["summary"]["massivefold_rna_model_selection_coverage_top5_candidate_count"] == 10
    assert payload["summary"]["massivefold_rna_model_selection_coverage_model1_candidate_count"] == 2
    assert payload["summary"]["massivefold_rna_model_selection_input_status"] == (
        "massivefold_rna_model_selection_input_packet_ready_external_only"
    )
    assert payload["summary"]["massivefold_rna_model_selection_input_target_count"] == 2
    assert payload["summary"]["massivefold_rna_model_selection_input_ready_target_count"] == 2
    assert payload["summary"]["massivefold_rna_model_selection_input_blocked_target_count"] == 0
    assert payload["summary"]["massivefold_rna_model_selection_input_model1_count"] == 2
    assert payload["summary"]["massivefold_rna_model_selection_input_top5_count"] == 10
    assert payload["summary"]["massivefold_rna_model_selection_input_missing_artifact_count"] == 0
    assert payload["summary"]["massivefold_rna_model_selection_input_r2345_guard"] == (
        "ignore_0930_pacific_invalid_dna_t_request_use_1130_replacement_only"
    )
    assert payload["summary"]["massivefold_rna_model_selection_input_policy"] == (
        "do_not_mark_as_internal_prediction"
    )
    assert payload["summary"]["massivefold_rna_self_assessment_status"] == (
        "massivefold_rna_self_assessment_ready_external_only"
    )
    assert payload["summary"]["massivefold_rna_self_assessment_target_count"] == 2
    assert payload["summary"]["massivefold_rna_self_assessment_ready_target_count"] == 2
    assert payload["summary"]["massivefold_rna_self_assessment_blocked_target_count"] == 0
    assert payload["summary"]["massivefold_rna_self_assessment_candidate_count"] == 10
    assert payload["summary"]["massivefold_rna_self_assessment_model1_count"] == 2
    assert payload["summary"]["massivefold_rna_self_assessment_top5_count"] == 10
    assert payload["summary"]["massivefold_rna_self_assessment_low_margin_count"] == 1
    assert payload["summary"]["massivefold_rna_self_assessment_low_margin_threshold"] == "1.0"
    assert payload["summary"]["massivefold_rna_self_assessment_r2345_guard"] == (
        "ignore_0930_pacific_invalid_dna_t_request_use_1130_replacement_only"
    )
    assert payload["summary"]["massivefold_rna_self_assessment_policy"] == (
        "do_not_mark_as_internal_prediction"
    )
    assert payload["summary"]["protein_complex_massivefold_model_selection_coverage_status"] == (
        "protein_complex_massivefold_model_selection_coverage_ready_review_only"
    )
    assert payload["summary"]["protein_complex_massivefold_model_selection_coverage_target_count"] == 2
    assert payload["summary"]["protein_complex_massivefold_model_selection_coverage_ready_target_count"] == 2
    assert payload["summary"]["protein_complex_massivefold_model_selection_coverage_partial_target_count"] == 0
    assert (
        payload["summary"][
            "protein_complex_massivefold_model_selection_coverage_verified_acquisition_count"
        ]
        == 2
    )
    assert (
        payload["summary"][
            "protein_complex_massivefold_model_selection_coverage_representative_extracted_target_count"
        ]
        == 2
    )
    assert payload["summary"]["protein_complex_massivefold_model_selection_coverage_viewer_ready_target_count"] == 2
    assert payload["summary"]["protein_complex_massivefold_model_selection_coverage_rerank_ready_target_count"] == 2
    assert payload["summary"]["protein_complex_massivefold_model_selection_coverage_selected_model_count"] == 260
    assert payload["summary"]["protein_complex_massivefold_model_selection_coverage_extracted_model_count"] == 260
    assert payload["summary"]["protein_complex_massivefold_model_selection_coverage_viewer_ready_model_count"] == 260
    assert payload["summary"]["protein_complex_massivefold_model_selection_coverage_top5_candidate_count"] == 10
    assert payload["summary"]["protein_complex_massivefold_model_selection_coverage_model1_candidate_count"] == 2
    assert payload["summary"]["protein_complex_massivefold_self_assessment_status"] == (
        "protein_complex_massivefold_self_assessment_ready_external_only"
    )
    assert payload["summary"]["protein_complex_massivefold_self_assessment_target_count"] == 2
    assert payload["summary"]["protein_complex_massivefold_self_assessment_ready_target_count"] == 2
    assert payload["summary"]["protein_complex_massivefold_self_assessment_blocked_target_count"] == 0
    assert payload["summary"]["protein_complex_massivefold_self_assessment_heteromer_count"] == 1
    assert payload["summary"]["protein_complex_massivefold_self_assessment_candidate_count"] == 10
    assert payload["summary"]["protein_complex_massivefold_self_assessment_model1_count"] == 2
    assert payload["summary"]["protein_complex_massivefold_self_assessment_top5_count"] == 10
    assert payload["summary"]["protein_complex_massivefold_self_assessment_missing_artifact_count"] == 0
    assert payload["summary"]["protein_complex_massivefold_self_assessment_low_margin_count"] == 1
    assert payload["summary"]["protein_complex_massivefold_self_assessment_low_margin_threshold"] == "2.0"
    assert payload["summary"]["protein_complex_massivefold_self_assessment_policy"] == (
        "do_not_mark_as_internal_prediction"
    )
    assert payload["summary"]["massivefold_model1_risk_queue_status"] == (
        "massivefold_model1_risk_queue_ready_external_only"
    )
    assert payload["summary"]["massivefold_model1_risk_queue_target_count"] == 4
    assert payload["summary"]["massivefold_model1_risk_queue_ready_target_count"] == 4
    assert payload["summary"]["massivefold_model1_risk_queue_blocked_target_count"] == 0
    assert payload["summary"]["massivefold_model1_risk_queue_low_margin_count"] == 2
    assert payload["summary"]["massivefold_model1_risk_queue_critical_count"] == 1
    assert payload["summary"]["massivefold_model1_risk_queue_rna_hybrid_count"] == 2
    assert payload["summary"]["massivefold_model1_risk_queue_protein_complex_count"] == 2
    assert payload["summary"]["massivefold_model1_risk_queue_first_target_id"] == "H1311"
    assert payload["summary"]["massivefold_model1_risk_queue_first_group"] == "protein_complex"
    assert payload["summary"]["massivefold_model1_risk_queue_first_gap"] == "0.05"
    assert payload["summary"]["massivefold_model1_risk_queue_first_tier"] == "critical_model1_margin"
    assert payload["summary"]["massivefold_model1_risk_queue_policy"] == (
        "do_not_mark_as_internal_prediction"
    )
    assert payload["summary"]["massivefold_critical_rerank_experiment_status"] == (
        "massivefold_critical_rerank_experiment_ready_external_only"
    )
    assert payload["summary"]["massivefold_critical_rerank_experiment_count"] == 2
    assert payload["summary"]["massivefold_critical_rerank_ready_experiment_count"] == 2
    assert payload["summary"]["massivefold_critical_rerank_blocked_experiment_count"] == 0
    assert payload["summary"]["massivefold_critical_rerank_rna_hybrid_count"] == 1
    assert payload["summary"]["massivefold_critical_rerank_protein_complex_count"] == 1
    assert payload["summary"]["massivefold_critical_rerank_high_diversity_count"] == 1
    assert payload["summary"]["massivefold_critical_rerank_geometry_review_count"] == 1
    assert payload["summary"]["massivefold_critical_rerank_low_confidence_review_count"] == 1
    assert payload["summary"]["massivefold_critical_rerank_first_target_id"] == "R2350"
    assert payload["summary"]["massivefold_critical_rerank_first_group"] == "rna_hybrid"
    assert payload["summary"]["massivefold_critical_rerank_first_gap"] == "0.02"
    assert payload["summary"]["massivefold_critical_rerank_first_order"] == (
        "top5_diversity_then_geometry_then_model1_gap"
    )
    assert payload["summary"]["massivefold_critical_rerank_formula_id"] == (
        "gap_plus_geometry_plus_diversity_penalty_v1"
    )
    assert payload["summary"]["massivefold_critical_rerank_policy"] == (
        "do_not_mark_as_internal_prediction"
    )
    assert payload["summary"]["massivefold_critical_rerank_score_ledger_status"] == (
        "massivefold_critical_rerank_score_ledger_ready_external_only"
    )
    assert payload["summary"]["massivefold_critical_rerank_score_ledger_count"] == 2
    assert payload["summary"]["massivefold_critical_rerank_score_ledger_ready_count"] == 2
    assert payload["summary"]["massivefold_critical_rerank_score_ledger_blocked_count"] == 0
    assert payload["summary"]["massivefold_critical_rerank_score_ledger_immediate_count"] == 0
    assert payload["summary"]["massivefold_critical_rerank_score_ledger_calibrate_count"] == 2
    assert payload["summary"]["massivefold_critical_rerank_score_ledger_watch_count"] == 0
    assert payload["summary"]["massivefold_critical_rerank_score_ledger_rna_hybrid_count"] == 1
    assert payload["summary"]["massivefold_critical_rerank_score_ledger_protein_complex_count"] == 1
    assert payload["summary"]["massivefold_critical_rerank_score_ledger_top_target_id"] == "R2350"
    assert payload["summary"]["massivefold_critical_rerank_score_ledger_top_group"] == "rna_hybrid"
    assert payload["summary"]["massivefold_critical_rerank_score_ledger_top_score"] == "66"
    assert payload["summary"]["massivefold_critical_rerank_score_ledger_top_band"] == (
        "calibrate_before_model1_freeze"
    )
    assert payload["summary"]["massivefold_critical_rerank_score_ledger_top_action"] == (
        "run_targeted_probe_then_freeze_model1_if_consistent"
    )
    assert payload["summary"]["massivefold_critical_rerank_score_ledger_policy"] == (
        "do_not_mark_as_internal_prediction"
    )
    assert payload["summary"]["massivefold_model1_selection_calibration_gate_status"] == (
        "massivefold_model1_selection_calibration_gate_ready_external_only"
    )
    assert payload["summary"]["massivefold_model1_selection_calibration_gate_freeze_status"] == (
        "model1_freeze_blocked_by_calibration"
    )
    assert payload["summary"]["massivefold_model1_selection_calibration_gate_count"] == 2
    assert payload["summary"]["massivefold_model1_selection_calibration_gate_ready_count"] == 2
    assert payload["summary"]["massivefold_model1_selection_calibration_gate_blocked_count"] == 0
    assert payload["summary"]["massivefold_model1_selection_calibration_gate_hold_count"] == 1
    assert payload["summary"]["massivefold_model1_selection_calibration_gate_watch_count"] == 1
    assert payload["summary"]["massivefold_model1_selection_calibration_gate_probe_required_count"] == 2
    assert payload["summary"]["massivefold_model1_selection_calibration_gate_freeze_ready_count"] == 0
    assert payload["summary"]["massivefold_model1_selection_calibration_gate_rna_hybrid_count"] == 1
    assert payload["summary"]["massivefold_model1_selection_calibration_gate_protein_complex_count"] == 1
    assert payload["summary"]["massivefold_model1_selection_calibration_gate_first_target_id"] == "R2350"
    assert payload["summary"]["massivefold_model1_selection_calibration_gate_first_group"] == "rna_hybrid"
    assert payload["summary"]["massivefold_model1_selection_calibration_gate_top_risk_score"] == "66"
    assert payload["summary"]["massivefold_model1_selection_calibration_gate_first_decision"] == (
        "hold_model1_freeze_probe_required"
    )
    assert payload["summary"]["massivefold_model1_selection_calibration_gate_first_probe"] == (
        "top5_rerank_consistency_probe"
    )
    assert payload["summary"]["massivefold_model1_selection_calibration_gate_rule_id"] == (
        "no_native_model1_selection_gate_v1"
    )
    assert payload["summary"]["massivefold_model1_selection_calibration_gate_policy"] == (
        "do_not_mark_as_internal_prediction"
    )
    assert payload["summary"]["massivefold_model1_probe_worklist_status"] == (
        "massivefold_model1_probe_worklist_ready_external_only"
    )
    assert payload["summary"]["massivefold_model1_probe_worklist_count"] == 2
    assert payload["summary"]["massivefold_model1_probe_worklist_ready_count"] == 2
    assert payload["summary"]["massivefold_model1_probe_worklist_blocked_count"] == 0
    assert payload["summary"]["massivefold_model1_probe_worklist_top5_count"] == 1
    assert payload["summary"]["massivefold_model1_probe_worklist_lightweight_count"] == 1
    assert payload["summary"]["massivefold_model1_probe_worklist_priority1_count"] == 1
    assert payload["summary"]["massivefold_model1_probe_worklist_priority2_count"] == 1
    assert payload["summary"]["massivefold_model1_probe_worklist_rna_hybrid_count"] == 1
    assert payload["summary"]["massivefold_model1_probe_worklist_protein_complex_count"] == 1
    assert payload["summary"]["massivefold_model1_probe_worklist_first_target_id"] == "R2350"
    assert payload["summary"]["massivefold_model1_probe_worklist_first_group"] == "rna_hybrid"
    assert payload["summary"]["massivefold_model1_probe_worklist_first_score"] == "66"
    assert payload["summary"]["massivefold_model1_probe_worklist_first_probe"] == (
        "top5_rerank_consistency_probe"
    )
    assert payload["summary"]["massivefold_model1_probe_worklist_unlock_policy"] == (
        "freeze_after_probe_allowed_only_if_exit_criterion_passes"
    )
    assert payload["summary"]["massivefold_model1_probe_worklist_policy"] == (
        "do_not_mark_as_internal_prediction"
    )
    assert payload["summary"]["massivefold_model1_probe_outcome_status"] == (
        "massivefold_model1_probe_outcome_ready_external_only"
    )
    assert payload["summary"]["massivefold_model1_probe_outcome_count"] == 2
    assert payload["summary"]["massivefold_model1_probe_outcome_ready_count"] == 2
    assert payload["summary"]["massivefold_model1_probe_outcome_blocked_count"] == 0
    assert payload["summary"]["massivefold_model1_probe_outcome_pass_count"] == 2
    assert payload["summary"]["massivefold_model1_probe_outcome_fail_count"] == 0
    assert payload["summary"]["massivefold_model1_probe_outcome_freeze_ready_count"] == 2
    assert payload["summary"]["massivefold_model1_probe_outcome_top5_count"] == 1
    assert payload["summary"]["massivefold_model1_probe_outcome_lightweight_count"] == 1
    assert payload["summary"]["massivefold_model1_probe_outcome_rna_hybrid_count"] == 1
    assert payload["summary"]["massivefold_model1_probe_outcome_protein_complex_count"] == 1
    assert payload["summary"]["massivefold_model1_probe_outcome_first_target_id"] == "R2350"
    assert payload["summary"]["massivefold_model1_probe_outcome_first_group"] == "rna_hybrid"
    assert payload["summary"]["massivefold_model1_probe_outcome_first_result"] == (
        "probe_pass_model1_retained"
    )
    assert payload["summary"]["massivefold_model1_probe_outcome_first_margin"] == "0.1"
    assert payload["summary"]["massivefold_model1_probe_outcome_first_recommendation"] == (
        "conditional_model1_freeze_ready_external_only"
    )
    assert payload["summary"]["massivefold_model1_probe_outcome_rule_id"] == (
        "no_native_probe_rescore_v1"
    )
    assert payload["summary"]["massivefold_model1_probe_outcome_policy"] == (
        "do_not_mark_as_internal_prediction"
    )
    assert payload["summary"]["massivefold_model1_freeze_decision_packet_status"] == (
        "massivefold_model1_freeze_decision_packet_ready_external_only"
    )
    assert payload["summary"]["massivefold_model1_freeze_decision_packet_count"] == 2
    assert payload["summary"]["massivefold_model1_freeze_decision_packet_ready_count"] == 2
    assert payload["summary"]["massivefold_model1_freeze_decision_packet_blocked_count"] == 0
    assert payload["summary"]["massivefold_model1_freeze_decision_packet_freeze_ready_count"] == 1
    assert payload["summary"]["massivefold_model1_freeze_decision_packet_freeze_blocked_count"] == 1
    assert payload["summary"]["massivefold_model1_freeze_decision_packet_conditional_count"] == 1
    assert payload["summary"]["massivefold_model1_freeze_decision_packet_watch_count"] == 0
    assert payload["summary"]["massivefold_model1_freeze_decision_packet_manual_review_count"] == 1
    assert payload["summary"]["massivefold_model1_freeze_decision_packet_rna_hybrid_count"] == 1
    assert payload["summary"]["massivefold_model1_freeze_decision_packet_protein_complex_count"] == 1
    assert payload["summary"]["massivefold_model1_freeze_decision_packet_first_ready_target_id"] == "R2350"
    assert payload["summary"]["massivefold_model1_freeze_decision_packet_first_ready_group"] == "rna_hybrid"
    assert payload["summary"]["massivefold_model1_freeze_decision_packet_first_ready_decision"] == (
        "freeze_ready_external_only_conditional"
    )
    assert payload["summary"]["massivefold_model1_freeze_decision_packet_first_blocked_target_id"] == "H2312"
    assert payload["summary"]["massivefold_model1_freeze_decision_packet_first_blocked_group"] == (
        "protein_complex"
    )
    assert payload["summary"]["massivefold_model1_freeze_decision_packet_first_blocked_decision"] == (
        "freeze_blocked_manual_review"
    )
    assert payload["summary"]["massivefold_model1_freeze_decision_packet_rule_id"] == (
        "no_native_model1_freeze_decision_v1"
    )
    assert payload["summary"]["massivefold_model1_freeze_decision_packet_policy"] == (
        "do_not_mark_as_internal_prediction"
    )
    assert payload["summary"]["massivefold_model_selection_ledger_status"] == (
        "massivefold_model_selection_ledger_ready_external_only"
    )
    assert payload["summary"]["massivefold_model_selection_ledger_count"] == 15
    assert payload["summary"]["massivefold_model_selection_ledger_ready_count"] == 15
    assert payload["summary"]["massivefold_model_selection_ledger_blocked_count"] == 0
    assert payload["summary"]["massivefold_model_selection_ledger_conditional_count"] == 2
    assert payload["summary"]["massivefold_model_selection_ledger_watch_count"] == 1
    assert payload["summary"]["massivefold_model_selection_ledger_manual_review_count"] == 1
    assert payload["summary"]["massivefold_model_selection_ledger_review_only_count"] == 11
    assert payload["summary"]["massivefold_model_selection_ledger_freeze_ready_count"] == 3
    assert payload["summary"]["massivefold_model_selection_ledger_rna_hybrid_count"] == 6
    assert payload["summary"]["massivefold_model_selection_ledger_protein_complex_count"] == 9
    assert payload["summary"]["massivefold_model_selection_ledger_first_target_id"] == "R2350"
    assert payload["summary"]["massivefold_model_selection_ledger_first_group"] == "rna_hybrid"
    assert payload["summary"]["massivefold_model_selection_ledger_first_decision"] == (
        "external_model1_selected_conditional"
    )
    assert payload["summary"]["massivefold_model_selection_ledger_first_manual_review_target_id"] == (
        "R2352"
    )
    assert payload["summary"]["massivefold_model_selection_ledger_rule_id"] == (
        "no_native_massivefold_model_selection_ledger_v1"
    )
    assert payload["summary"]["massivefold_model_selection_ledger_policy"] == (
        "do_not_mark_as_internal_prediction"
    )
    assert payload["summary"]["massivefold_model1_combined_selector_overlay_status"] == (
        "massivefold_model1_combined_selector_overlay_ready_external_only"
    )
    assert payload["summary"]["massivefold_model1_combined_selector_overlay_count"] == 4
    assert payload["summary"]["massivefold_model1_combined_selector_overlay_ready_count"] == 4
    assert payload["summary"]["massivefold_model1_combined_selector_overlay_blocked_count"] == 0
    assert payload["summary"]["massivefold_model1_combined_selector_overlay_freeze_ready_count"] == 1
    assert (
        payload["summary"]["massivefold_model1_combined_selector_overlay_not_freeze_ready_count"]
        == 3
    )
    assert payload["summary"]["massivefold_model1_combined_selector_overlay_manual_blocked_count"] == 1
    assert payload["summary"]["massivefold_model1_combined_selector_overlay_interface_hold_count"] == 1
    assert payload["summary"]["massivefold_model1_combined_selector_overlay_weak_probe_hold_count"] == 0
    assert payload["summary"]["massivefold_model1_combined_selector_overlay_probe_required_count"] == 1
    assert payload["summary"]["massivefold_model1_combined_selector_overlay_review_watch_count"] == 0
    assert payload["summary"]["massivefold_model1_combined_selector_overlay_unknown_hold_count"] == 0
    assert payload["summary"]["massivefold_model1_combined_selector_overlay_rna_hybrid_count"] == 2
    assert payload["summary"]["massivefold_model1_combined_selector_overlay_protein_complex_count"] == 2
    assert payload["summary"]["massivefold_model1_combined_selector_overlay_baseline_capture_rate"] == "0.500"
    assert payload["summary"]["massivefold_model1_combined_selector_overlay_baseline_non_capture_rate"] == (
        "0.500"
    )
    assert payload["summary"]["massivefold_model1_combined_selector_overlay_first_target_id"] == "R2352"
    assert payload["summary"]["massivefold_model1_combined_selector_overlay_first_decision"] == (
        "selector_blocked_manual_review"
    )
    assert payload["summary"]["massivefold_model1_combined_selector_overlay_first_action"] == (
        "do_not_freeze_model1_external_only"
    )
    assert payload["summary"]["massivefold_model1_combined_selector_overlay_first_freeze_ready_target_id"] == (
        "R2350"
    )
    assert payload["summary"]["massivefold_model1_combined_selector_overlay_first_freeze_ready_action"] == (
        "carry_model1_as_external_only_freeze_ready"
    )
    assert payload["summary"]["massivefold_model1_combined_selector_overlay_policy"] == (
        "do_not_mark_as_internal_prediction"
    )
    assert payload["summary"]["massivefold_model1_combined_selector_overlay_proof_eligible"] == (
        "False"
    )
    assert payload["summary"]["massivefold_freeze_ready_review_packet_status"] == (
        "massivefold_freeze_ready_review_packet_ready_external_only"
    )
    assert payload["summary"]["massivefold_freeze_ready_review_packet_count"] == 2
    assert payload["summary"]["massivefold_freeze_ready_review_packet_ready_count"] == 2
    assert payload["summary"]["massivefold_freeze_ready_review_packet_blocked_count"] == 0
    assert payload["summary"]["massivefold_freeze_ready_review_packet_model_present_count"] == 2
    assert payload["summary"]["massivefold_freeze_ready_review_packet_viewer_present_count"] == 2
    assert payload["summary"]["massivefold_freeze_ready_review_packet_projection_present_count"] == 2
    assert payload["summary"]["massivefold_freeze_ready_review_packet_top5_manifest_present_count"] == 2
    assert payload["summary"]["massivefold_freeze_ready_review_packet_top5_total"] == 10
    assert payload["summary"]["massivefold_freeze_ready_review_packet_first_target_id"] == "R2350"
    assert payload["summary"]["massivefold_freeze_ready_review_packet_first_model_filename"] == (
        "Model_20_af3_woPaired_seed_1.cif"
    )
    assert payload["summary"]["massivefold_freeze_ready_review_packet_first_viewer_html"] == (
        "casp17/viewers/r2350/viewer.html"
    )
    assert payload["summary"]["massivefold_freeze_ready_review_packet_html"] == (
        "casp17/casp17_massivefold_freeze_ready_review_packet_current.html"
    )
    assert payload["summary"]["massivefold_freeze_ready_review_packet_policy"] == (
        "do_not_mark_as_internal_prediction"
    )
    assert payload["summary"]["massivefold_freeze_ready_review_packet_proof_eligible"] == (
        "False"
    )
    assert payload["summary"]["massivefold_hold_probe_review_packet_status"] == (
        "massivefold_hold_probe_review_packet_ready_external_only"
    )
    assert payload["summary"]["massivefold_hold_probe_review_packet_count"] == 3
    assert payload["summary"]["massivefold_hold_probe_review_packet_ready_count"] == 3
    assert payload["summary"]["massivefold_hold_probe_review_packet_blocked_count"] == 0
    assert payload["summary"]["massivefold_hold_probe_review_packet_manual_blocked_count"] == 1
    assert payload["summary"]["massivefold_hold_probe_review_packet_interface_hold_count"] == 1
    assert payload["summary"]["massivefold_hold_probe_review_packet_probe_required_count"] == 1
    assert payload["summary"]["massivefold_hold_probe_review_packet_weak_probe_hold_count"] == 0
    assert payload["summary"]["massivefold_hold_probe_review_packet_unknown_hold_count"] == 0
    assert payload["summary"]["massivefold_hold_probe_review_packet_model_present_count"] == 3
    assert payload["summary"]["massivefold_hold_probe_review_packet_viewer_present_count"] == 3
    assert payload["summary"]["massivefold_hold_probe_review_packet_projection_present_count"] == 3
    assert payload["summary"]["massivefold_hold_probe_review_packet_top5_manifest_present_count"] == 3
    assert payload["summary"]["massivefold_hold_probe_review_packet_alternate_present_count"] == 1
    assert payload["summary"]["massivefold_hold_probe_review_packet_top5_total"] == 15
    assert payload["summary"]["massivefold_hold_probe_review_packet_first_target_id"] == "R2352"
    assert payload["summary"]["massivefold_hold_probe_review_packet_first_class"] == (
        "manual_blocked_review"
    )
    assert payload["summary"]["massivefold_hold_probe_review_packet_first_action"] == (
        "do_not_freeze_model1_external_only"
    )
    assert payload["summary"]["massivefold_hold_probe_review_packet_first_model_filename"] == (
        "Model_15_af3_woUnpaired_seed_1.cif"
    )
    assert payload["summary"]["massivefold_hold_probe_review_packet_first_viewer_html"] == (
        "casp17/viewers/r2352/viewer.html"
    )
    assert payload["summary"]["massivefold_hold_probe_review_packet_html"] == (
        "casp17/casp17_massivefold_hold_probe_review_packet_current.html"
    )
    assert payload["summary"]["massivefold_hold_probe_review_packet_policy"] == (
        "do_not_mark_as_internal_prediction"
    )
    assert payload["summary"]["massivefold_hold_probe_review_packet_proof_eligible"] == (
        "False"
    )
    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_status"] == (
        "massivefold_probe_required_targeted_probe_packet_ready_external_only"
    )
    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_count"] == 3
    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_ready_count"] == 3
    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_blocked_count"] == 0
    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_pass_count"] == 2
    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_watch_count"] == 1
    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_fail_count"] == 0
    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_freeze_candidate_count"] == 2
    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_watch_recommendation_count"] == 1
    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_manual_review_count"] == 0
    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_rna_hybrid_count"] == 1
    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_protein_complex_count"] == 2
    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_model_present_count"] == 3
    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_viewer_present_count"] == 3
    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_projection_present_count"] == 3
    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_top_candidate_present_count"] == 3
    assert (
        payload["summary"]["massivefold_probe_required_targeted_probe_packet_top_candidate_viewer_present_count"]
        == 3
    )
    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_top5_manifest_present_count"] == 3
    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_top5_total"] == 15
    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_clear_margin"] == "0.5"
    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_first_target_id"] == "H1311"
    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_first_result"] == (
        "probe_pass_model1_retained_clear"
    )
    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_first_margin"] == "0.75"
    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_first_recommendation"] == (
        "external_model1_freeze_candidate_after_probe"
    )
    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_html"] == (
        "casp17/casp17_massivefold_probe_required_targeted_probe_packet_current.html"
    )
    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_policy"] == (
        "do_not_mark_as_internal_prediction"
    )
    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_proof_eligible"] == (
        "False"
    )
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_status"] == (
        "massivefold_post_probe_selector_decision_packet_ready_external_only"
    )
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_count"] == 5
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_ready_count"] == 5
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_blocked_count"] == 0
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_freeze_count"] == 2
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_watch_count"] == 2
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_manual_count"] == 1
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_existing_freeze_count"] == 1
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_probe_freeze_count"] == 1
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_probe_watch_count"] == 1
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_interface_hold_count"] == 1
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_probe_manual_count"] == 0
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_manual_block_count"] == 1
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_rna_hybrid_count"] == 2
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_protein_complex_count"] == 3
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_model_present_count"] == 5
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_viewer_present_count"] == 5
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_projection_present_count"] == 5
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_top5_manifest_present_count"] == 5
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_alternate_present_count"] == 1
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_first_target_id"] == "R2352"
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_first_class"] == "manual_block"
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_first_decision"] == (
        "external_model1_freeze_blocked_manual_review"
    )
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_first_model_filename"] == (
        "Model_15_af3_woUnpaired_seed_1.cif"
    )
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_html"] == (
        "casp17/casp17_massivefold_post_probe_selector_decision_packet_current.html"
    )
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_policy"] == (
        "do_not_mark_as_internal_prediction"
    )
    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_proof_eligible"] == (
        "False"
    )
    assert payload["summary"]["massivefold_watch_manual_action_packet_status"] == (
        "massivefold_watch_manual_action_packet_ready_external_only"
    )
    assert payload["summary"]["massivefold_watch_manual_action_packet_count"] == 5
    assert payload["summary"]["massivefold_watch_manual_action_packet_ready_count"] == 5
    assert payload["summary"]["massivefold_watch_manual_action_packet_blocked_count"] == 0
    assert payload["summary"]["massivefold_watch_manual_action_packet_manual_count"] == 1
    assert payload["summary"]["massivefold_watch_manual_action_packet_interface_count"] == 1
    assert payload["summary"]["massivefold_watch_manual_action_packet_low_margin_count"] == 3
    assert payload["summary"]["massivefold_watch_manual_action_packet_priority1_count"] == 2
    assert payload["summary"]["massivefold_watch_manual_action_packet_priority2_count"] == 3
    assert payload["summary"]["massivefold_watch_manual_action_packet_rna_hybrid_count"] == 2
    assert payload["summary"]["massivefold_watch_manual_action_packet_protein_complex_count"] == 3
    assert payload["summary"]["massivefold_watch_manual_action_packet_model_present_count"] == 5
    assert payload["summary"]["massivefold_watch_manual_action_packet_viewer_present_count"] == 5
    assert payload["summary"]["massivefold_watch_manual_action_packet_projection_present_count"] == 5
    assert payload["summary"]["massivefold_watch_manual_action_packet_top5_manifest_present_count"] == 5
    assert payload["summary"]["massivefold_watch_manual_action_packet_alternate_present_count"] == 1
    assert payload["summary"]["massivefold_watch_manual_action_packet_first_target_id"] == "R2352"
    assert payload["summary"]["massivefold_watch_manual_action_packet_first_class"] == (
        "manual_alternate_review"
    )
    assert payload["summary"]["massivefold_watch_manual_action_packet_first_priority"] == "1"
    assert payload["summary"]["massivefold_watch_manual_action_packet_html"] == (
        "casp17/casp17_massivefold_watch_manual_action_packet_current.html"
    )
    assert payload["summary"]["massivefold_watch_manual_action_packet_policy"] == (
        "do_not_mark_as_internal_prediction"
    )
    assert payload["summary"]["massivefold_watch_manual_action_packet_proof_eligible"] == (
        "False"
    )
    assert payload["summary"]["massivefold_freeze_candidate_format_preflight_status"] == (
        "massivefold_freeze_candidate_format_preflight_ready_external_only"
    )
    assert payload["summary"]["massivefold_freeze_candidate_format_preflight_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_format_preflight_ready_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_format_preflight_blocked_count"] == 0
    assert payload["summary"]["massivefold_freeze_candidate_format_preflight_existing_count"] == 2
    assert payload["summary"]["massivefold_freeze_candidate_format_preflight_probe_count"] == 8
    assert payload["summary"]["massivefold_freeze_candidate_format_preflight_rna_hybrid_count"] == 4
    assert payload["summary"]["massivefold_freeze_candidate_format_preflight_protein_complex_count"] == 6
    assert payload["summary"]["massivefold_freeze_candidate_format_preflight_selected_pdb_count"] == 6
    assert payload["summary"]["massivefold_freeze_candidate_format_preflight_selected_cif_count"] == 4
    assert payload["summary"]["massivefold_freeze_candidate_format_preflight_packaged_pdb_count"] == 0
    assert payload["summary"]["massivefold_freeze_candidate_format_preflight_packaged_cif_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_format_preflight_target_id_ok_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_format_preflight_selected_ext_ok_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_format_preflight_packaged_ext_ok_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_format_preflight_model_present_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_format_preflight_model_nonempty_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_format_preflight_viewer_present_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_format_preflight_projection_present_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_format_preflight_top5_manifest_present_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_format_preflight_first_target_id"] == "H2319"
    assert payload["summary"]["massivefold_freeze_candidate_format_preflight_first_model_filename"] == (
        "Model_1_afm_basic_model_4_multimer_v3_pred_25.pdb"
    )
    assert payload["summary"]["massivefold_freeze_candidate_format_preflight_html"] == (
        "casp17/casp17_massivefold_freeze_candidate_format_preflight_current.html"
    )
    assert payload["summary"]["massivefold_freeze_candidate_format_preflight_policy"] == (
        "do_not_mark_as_internal_prediction"
    )
    assert payload["summary"]["massivefold_freeze_candidate_format_preflight_proof_eligible"] == (
        "False"
    )
    assert payload["summary"]["massivefold_freeze_candidate_escrow_status"] == (
        "massivefold_freeze_candidate_escrow_ready_external_only"
    )
    assert payload["summary"]["massivefold_freeze_candidate_escrow_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_escrow_ready_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_escrow_blocked_count"] == 0
    assert payload["summary"]["massivefold_freeze_candidate_escrow_model_sha256_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_escrow_top5_sha256_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_escrow_model_present_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_escrow_viewer_present_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_escrow_projection_present_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_escrow_top5_manifest_present_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_escrow_existing_count"] == 2
    assert payload["summary"]["massivefold_freeze_candidate_escrow_probe_count"] == 8
    assert payload["summary"]["massivefold_freeze_candidate_escrow_rna_hybrid_count"] == 4
    assert payload["summary"]["massivefold_freeze_candidate_escrow_protein_complex_count"] == 6
    assert payload["summary"]["massivefold_freeze_candidate_escrow_native_pending_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_escrow_proof_eligible_count"] == 0
    assert payload["summary"]["massivefold_freeze_candidate_escrow_author_serialized_count"] == 0
    assert payload["summary"]["massivefold_freeze_candidate_escrow_first_target_id"] == "H2319"
    assert payload["summary"]["massivefold_freeze_candidate_escrow_first_blocked_target_id"] == ""
    assert payload["summary"]["massivefold_freeze_candidate_escrow_manifest_signature_sha256"] == (
        "freezeabc123"
    )
    assert payload["summary"]["massivefold_freeze_candidate_escrow_policy"] == (
        "do_not_mark_as_internal_prediction"
    )
    assert payload["summary"]["massivefold_freeze_candidate_protein_library_status"] == (
        "massivefold_freeze_candidate_protein_library_ready_external_only"
    )
    assert payload["summary"]["massivefold_freeze_candidate_protein_library_protein_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_protein_library_protein_ready_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_protein_library_protein_blocked_count"] == 0
    assert payload["summary"]["massivefold_freeze_candidate_protein_library_object_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_protein_library_object_ready_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_protein_library_object_blocked_count"] == 0
    assert payload["summary"]["massivefold_freeze_candidate_protein_library_model_link_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_protein_library_viewer_link_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_protein_library_projection_link_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_protein_library_top5_link_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_protein_library_escrow_link_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_protein_library_model_sha256_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_protein_library_top5_sha256_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_protein_library_current_name_count"] == 5
    assert payload["summary"]["massivefold_freeze_candidate_protein_library_official_name_count"] == 10
    assert payload["summary"]["massivefold_freeze_candidate_protein_library_rna_hybrid_count"] == 4
    assert payload["summary"]["massivefold_freeze_candidate_protein_library_protein_complex_count"] == 6
    assert payload["summary"]["massivefold_freeze_candidate_protein_library_proof_eligible_count"] == 0
    assert payload["summary"]["massivefold_freeze_candidate_protein_library_author_serialized_count"] == 0
    assert payload["summary"]["massivefold_freeze_candidate_protein_library_first_protein_key"] == (
        "H2319_Human_astrovirus_VA1_capsid_spike_antibody_7C8_complex"
    )
    assert payload["summary"]["massivefold_freeze_candidate_protein_library_first_blocked_protein_key"] == ""
    assert payload["summary"]["massivefold_freeze_candidate_protein_library_html"] == (
        "casp17/casp17_massivefold_freeze_candidate_protein_library_current.html"
    )
    assert payload["summary"]["massivefold_freeze_candidate_protein_library_policy"] == (
        "do_not_mark_as_internal_prediction"
    )
    assert payload["summary"]["capri_round65_readiness_status"] == "blocked_registration_role_selection"
    assert payload["summary"]["capri_round65_round_status"] == "Active"
    assert payload["summary"]["capri_round65_registration_end"] == "2026-06-01 midnight"
    assert payload["summary"]["capri_round65_registration_days_remaining"] == 1
    assert payload["summary"]["capri_round65_registration_gate_status"] == "operator_input_required"
    assert payload["summary"]["capri_round65_registration_ready_field_count"] == 0
    assert payload["summary"]["capri_round65_registration_required_field_count"] == 4
    assert payload["summary"]["capri_round65_role_selection_status"] == "operator_input_required"
    assert payload["summary"]["capri_round65_target_count"] == 13
    assert payload["summary"]["capri_round65_active_target_count"] == 11
    assert payload["summary"]["capri_round65_closed_target_count"] == 2
    assert payload["summary"]["capri_round65_scorer_priority_target_count"] == 4
    assert payload["summary"]["capri_round65_predictor_priority_target_count"] == 7
    assert payload["summary"]["capri_round65_blocked_target_count"] == 11
    assert payload["summary"]["capri_round65_readiness_format_preflight_target_count"] == 0
    assert payload["summary"]["capri_round65_target_folder_count"] == 13
    assert payload["summary"]["capri_round65_first_open_target_id"] == "T329"
    assert payload["summary"]["capri_round65_format_preflight_status"] == "blocked_format_preflight"
    assert payload["summary"]["capri_round65_format_preflight_target_count"] == 13
    assert payload["summary"]["capri_round65_format_preflight_active_target_count"] == 11
    assert payload["summary"]["capri_round65_format_preflight_closed_target_count"] == 2
    assert payload["summary"]["capri_round65_format_preflight_local_pass_count"] == 0
    assert payload["summary"]["capri_round65_format_preflight_blocked_count"] == 11
    assert payload["summary"]["capri_round65_format_preflight_checked_count"] == 0
    assert payload["summary"]["capri_round65_format_preflight_template_missing_count"] == 11
    assert payload["summary"]["capri_round65_format_preflight_candidate_missing_count"] == 11
    assert payload["summary"]["capri_round65_format_preflight_error_count"] == 0
    assert payload["summary"]["capri_round65_format_preflight_first_blocked_target_id"] == "T329"
    assert payload["summary"]["win_gap_closure_status"] == "blocked_input"
    assert payload["summary"]["win_gap_closed_count"] == 4
    assert payload["summary"]["win_gap_not_closed_count"] == 5
    assert payload["summary"]["historical_input_workorder_count"] == 40
    assert payload["summary"]["historical_core_workorder_count"] == 40
    assert payload["summary"]["historical_missing_core_file_count"] == 80
    assert payload["summary"]["historical_missing_ablation_layer_file_count"] == 400
    assert payload["summary"]["benchmark_operator_ready_count"] == 0
    assert payload["summary"]["benchmark_operator_blocked_count"] == 40
    assert payload["summary"]["benchmark_missing_win_total_rows"] == 40
    assert payload["summary"]["operator_dashboard_status"] == "ready"
    assert payload["summary"]["operator_dashboard_row_count"] == 40
    assert payload["summary"]["operator_dashboard_ready_count"] == 0
    assert payload["summary"]["operator_dashboard_blocked_count"] == 40
    assert payload["summary"]["operator_dashboard_needs_target_replacement_count"] == 40
    assert payload["summary"]["operator_dashboard_needs_core_file_count"] == 40
    assert payload["summary"]["operator_dashboard_needs_ablation_layer_count"] == 40
    assert payload["summary"]["operator_dashboard_needs_calibration_count"] == 40
    assert payload["summary"]["operator_dashboard_needs_provenance_count"] == 40
    assert payload["summary"]["historical_identity_seed_inventory_status"] == (
        "batch_seed_shape_ready_operator_clearance_required"
    )
    assert payload["summary"]["historical_identity_seed_candidate_count"] == 17
    assert payload["summary"]["historical_identity_seed_monomer_count"] == 10
    assert payload["summary"]["historical_identity_seed_complex_count"] == 7
    assert payload["summary"]["historical_identity_seed_eligible_monomer_count"] == 10
    assert payload["summary"]["historical_identity_seed_eligible_complex_count"] == 7
    assert payload["summary"]["historical_identity_seed_batch_slot_count"] == 15
    assert payload["summary"]["historical_identity_seed_manifest_row_count"] == 15
    assert payload["summary"]["historical_identity_seed_operator_clearance_required_count"] == 15
    assert payload["summary"]["historical_identity_seed_first_target_id"] == "HIST_BBA5"
    assert payload["summary"]["historical_identity_seed_clearance_status"] == "awaiting_seed_clearance"
    assert payload["summary"]["historical_identity_seed_clearance_template_status"] == "created"
    assert payload["summary"]["historical_identity_seed_clearance_seed_count"] == 15
    assert payload["summary"]["historical_identity_seed_clearance_ready_count"] == 0
    assert payload["summary"]["historical_identity_seed_clearance_awaiting_count"] == 15
    assert payload["summary"]["historical_identity_seed_clearance_cleared_manifest_count"] == 0
    assert payload["summary"]["historical_identity_seed_clearance_blocking_field_count"] == 270
    assert payload["summary"]["historical_identity_seed_clearance_identity_open_count"] == 0
    assert payload["summary"]["historical_identity_seed_clearance_core_files_open_count"] == 0
    assert payload["summary"]["historical_identity_seed_clearance_no_leak_open_count"] == 15
    assert payload["summary"]["historical_identity_seed_clearance_calibration_open_count"] == 15
    assert payload["summary"]["historical_identity_seed_clearance_ablation_open_count"] == 15
    assert payload["summary"]["historical_identity_seed_clearance_first_target_id"] == "HIST_BBA5"
    assert payload["summary"]["historical_identity_seed_clearance_operator_csv"] == (
        "runs/casp17_historical_identity_seed_operator_clearance_current.csv"
    )
    assert payload["summary"]["historical_identity_seed_clearance_cleared_manifest_csv"] == (
        "runs/casp17_historical_benchmark_manifest_seed_cleared_current.csv"
    )
    assert payload["summary"]["historical_identity_seed_clearance_action_bundle_status"] == "open_actions"
    assert payload["summary"]["historical_identity_seed_clearance_action_bundle_target_count"] == 15
    assert payload["summary"]["historical_identity_seed_clearance_action_bundle_action_count"] == 45
    assert payload["summary"]["historical_identity_seed_clearance_action_bundle_open_count"] == 45
    assert payload["summary"]["historical_identity_seed_clearance_action_bundle_folder_count"] == 45
    assert payload["summary"]["historical_identity_seed_clearance_action_bundle_file_count"] == 90
    assert payload["summary"]["historical_identity_seed_clearance_action_bundle_identity_count"] == 0
    assert payload["summary"]["historical_identity_seed_clearance_action_bundle_core_count"] == 0
    assert payload["summary"]["historical_identity_seed_clearance_action_bundle_no_leak_count"] == 15
    assert payload["summary"]["historical_identity_seed_clearance_action_bundle_calibration_count"] == 15
    assert payload["summary"]["historical_identity_seed_clearance_action_bundle_ablation_count"] == 15
    assert payload["summary"]["historical_identity_seed_clearance_action_bundle_first_action"].endswith(
        "action_001_no_leak_provenance/ACTION.md"
    )
    assert payload["summary"]["historical_identity_seed_clearance_field_board_status"] == (
        "operator_field_fill_required"
    )
    assert payload["summary"]["historical_identity_seed_clearance_field_board_seed_count"] == 15
    assert payload["summary"]["historical_identity_seed_clearance_field_board_core_pass_count"] == 15
    assert payload["summary"]["historical_identity_seed_clearance_field_board_blocked_core_count"] == 0
    assert payload["summary"]["historical_identity_seed_clearance_field_board_operator_fill_count"] == 15
    assert payload["summary"]["historical_identity_seed_clearance_field_board_ready_count"] == 0
    assert payload["summary"]["historical_identity_seed_clearance_field_board_no_leak_open_count"] == 165
    assert payload["summary"]["historical_identity_seed_clearance_field_board_calibration_open_count"] == 90
    assert payload["summary"]["historical_identity_seed_clearance_field_board_ablation_open_count"] == 15
    assert payload["summary"]["historical_identity_seed_clearance_field_board_total_open_count"] == 270
    assert payload["summary"]["historical_identity_seed_clearance_field_board_first_target_id"] == "HIST_BBA5"
    assert payload["summary"]["historical_identity_seed_clearance_field_board_first_field"] == (
        "no_leak_evidence_ref"
    )
    assert payload["summary"]["historical_identity_seed_clearance_field_board_first_next_action"] == (
        "fill no-leak evidence, chronology, leakage controls, and operator clearance first"
    )
    assert payload["summary"]["historical_seed_no_leak_provenance_dossiers_status"] == (
        "operator_provenance_review_required"
    )
    assert payload["summary"]["historical_seed_no_leak_provenance_dossiers_seed_count"] == 15
    assert payload["summary"]["historical_seed_no_leak_provenance_dossiers_dossier_count"] == 15
    assert payload["summary"]["historical_seed_no_leak_provenance_dossiers_core_pass_count"] == 15
    assert payload["summary"]["historical_seed_no_leak_provenance_dossiers_current_false_count"] == 15
    assert payload["summary"]["historical_seed_no_leak_provenance_dossiers_operator_review_count"] == 15
    assert payload["summary"]["historical_seed_no_leak_provenance_dossiers_ready_count"] == 0
    assert payload["summary"]["historical_seed_no_leak_provenance_dossiers_open_field_count"] == 150
    assert payload["summary"]["historical_seed_no_leak_provenance_dossiers_chronology_gap_count"] == 15
    assert payload["summary"]["historical_seed_no_leak_provenance_dossiers_negative_control_gap_count"] == 15
    assert payload["summary"]["historical_seed_no_leak_provenance_dossiers_mtime_risk_count"] == 15
    assert payload["summary"]["historical_seed_no_leak_provenance_dossiers_core_blocked_count"] == 0
    assert payload["summary"]["historical_seed_no_leak_provenance_dossiers_current_risk_count"] == 0
    assert payload["summary"]["historical_seed_no_leak_provenance_dossiers_first_target_id"] == "HIST_BBA5"
    assert payload["summary"]["historical_seed_no_leak_provenance_dossiers_first_next_action"] == (
        "attach independent no-leak evidence and operator clearance before setting leakage_clearance"
    )
    assert payload["summary"]["historical_seed_no_leak_gap_repair_plan_status"] == "no_leak_gap_repair_required"
    assert payload["summary"]["historical_seed_no_leak_gap_repair_plan_seed_count"] == 15
    assert payload["summary"]["historical_seed_no_leak_gap_repair_plan_repair_csv_count"] == 15
    assert payload["summary"]["historical_seed_no_leak_gap_repair_plan_field_count"] == 150
    assert payload["summary"]["historical_seed_no_leak_gap_repair_plan_operator_required_count"] == 150
    assert payload["summary"]["historical_seed_no_leak_gap_repair_plan_weak_count"] == 30
    assert payload["summary"]["historical_seed_no_leak_gap_repair_plan_authoritative_count"] == 0
    assert payload["summary"]["historical_seed_no_leak_gap_repair_plan_chronology_count"] == 45
    assert payload["summary"]["historical_seed_no_leak_gap_repair_plan_negative_control_count"] == 45
    assert payload["summary"]["historical_seed_no_leak_gap_repair_plan_clearance_count"] == 60
    assert payload["summary"]["historical_seed_no_leak_gap_repair_plan_mtime_risk_count"] == 15
    assert payload["summary"]["historical_seed_no_leak_gap_repair_plan_first_target_id"] == "HIST_BBA5"
    assert payload["summary"]["historical_seed_current_target_prefill_status"] == "applied"
    assert payload["summary"]["historical_seed_current_target_prefill_apply_mode"] == "apply"
    assert payload["summary"]["historical_seed_current_target_prefill_row_count"] == 15
    assert payload["summary"]["historical_seed_current_target_prefill_ready_to_apply_count"] == 0
    assert payload["summary"]["historical_seed_current_target_prefill_applied_count"] == 15
    assert payload["summary"]["historical_seed_current_target_prefill_already_count"] == 0
    assert payload["summary"]["historical_seed_current_target_prefill_blocked_count"] == 0
    assert payload["summary"]["historical_seed_current_target_prefill_collision_count"] == 0
    assert payload["summary"]["historical_seed_current_target_prefill_remaining_open_count"] == 0
    assert payload["summary"]["historical_seed_current_target_prefill_hist_prefix_count"] == 15
    assert payload["summary"]["historical_seed_current_target_prefill_first_next_action"] == (
        "set current_casp17_target=false"
    )
    assert payload["summary"]["historical_seed_native_authority_audit_status"] == "blocked_native_authority"
    assert payload["summary"]["historical_seed_native_authority_audit_seed_count"] == 15
    assert payload["summary"]["historical_seed_native_authority_audit_pass_count"] == 0
    assert payload["summary"]["historical_seed_native_authority_audit_blocked_count"] == 15
    assert payload["summary"]["historical_seed_native_authority_audit_placeholder_count"] == 10
    assert payload["summary"]["historical_seed_native_authority_audit_ca_only_count"] == 10
    assert payload["summary"]["historical_seed_native_authority_audit_local_generated_no_authority_count"] == 5
    assert payload["summary"]["historical_seed_native_authority_audit_ref_missing_count"] == 15
    assert payload["summary"]["historical_seed_native_authority_audit_first_target_id"] == "HIST_BBA5"
    assert payload["summary"]["historical_seed_native_replacement_candidates_status"] == (
        "partial_native_replacement_candidates_ready"
    )
    assert payload["summary"]["historical_seed_native_replacement_candidates_candidate_count"] == 17
    assert payload["summary"]["historical_seed_native_replacement_candidates_ready_count"] == 10
    assert payload["summary"]["historical_seed_native_replacement_candidates_download_required_count"] == 0
    assert payload["summary"]["historical_seed_native_replacement_candidates_file_blocked_count"] == 0
    assert payload["summary"]["historical_seed_native_replacement_candidates_complex_authority_count"] == 7
    assert payload["summary"]["historical_seed_native_replacement_candidates_monomer_count"] == 10
    assert payload["summary"]["historical_seed_native_replacement_candidates_candidate_dir"] == (
        "casp17/historical_seed_native_replacement_candidates"
    )
    assert payload["summary"]["historical_seed_complex_source_authority_candidates_status"] == (
        "complex_homolog_source_authority_candidates_ready_claim_limited"
    )
    assert payload["summary"]["historical_seed_complex_source_authority_candidates_candidate_count"] == 7
    assert payload["summary"]["historical_seed_complex_source_authority_candidates_review_ready_count"] == 7
    assert payload["summary"]["historical_seed_complex_source_authority_candidates_direct_count"] == 0
    assert payload["summary"]["historical_seed_complex_source_authority_candidates_homolog_count"] == 7
    assert payload["summary"]["historical_seed_complex_source_authority_candidates_blocked_count"] == 0
    assert payload["summary"]["historical_seed_complex_source_authority_candidates_operator_apply_count"] == 0
    assert payload["summary"]["historical_seed_complex_source_authority_candidates_claim_promotion_count"] == 0
    assert payload["summary"]["historical_seed_complex_source_authority_candidates_protein_ref"] == (
        "rcsb:3V94;chain:B;doi:10.2210/pdb3v94/pdb"
    )
    assert payload["summary"]["historical_seed_chronology_candidate_board_status"] == (
        "operator_evidence_required"
    )
    assert payload["summary"]["historical_seed_chronology_candidate_board_row_count"] == 15
    assert payload["summary"]["historical_seed_chronology_candidate_board_ready_count"] == 0
    assert payload["summary"]["historical_seed_chronology_candidate_board_warning_count"] == 0
    assert payload["summary"]["historical_seed_chronology_candidate_board_evidence_required_count"] == 15
    assert payload["summary"]["historical_seed_chronology_candidate_board_conflict_count"] == 0
    assert payload["summary"]["historical_seed_chronology_candidate_board_path_date_count"] == 10
    assert payload["summary"]["historical_seed_chronology_candidate_board_mtime_count"] == 15
    assert payload["summary"]["historical_seed_chronology_candidate_board_mtime_risk_count"] == 15
    assert payload["summary"]["historical_seed_chronology_candidate_board_first_target_id"] == "HIST_BBA5"
    assert payload["summary"]["historical_seed_ablation_candidate_manifests_status"] == (
        "operator_ablation_review_required"
    )
    assert payload["summary"]["historical_seed_ablation_candidate_manifests_seed_count"] == 15
    assert payload["summary"]["historical_seed_ablation_candidate_manifests_manifest_count"] == 15
    assert payload["summary"]["historical_seed_ablation_candidate_manifests_candidate_row_count"] == 50
    assert payload["summary"]["historical_seed_ablation_candidate_manifests_selected_present_count"] == 15
    assert payload["summary"]["historical_seed_ablation_candidate_manifests_native_present_count"] == 15
    assert payload["summary"]["historical_seed_ablation_candidate_manifests_baseline_count"] == 1
    assert payload["summary"]["historical_seed_ablation_candidate_manifests_layer_gap_count"] == 14
    assert payload["summary"]["historical_seed_ablation_candidate_manifests_operator_review_count"] == 15
    assert payload["summary"]["historical_seed_ablation_candidate_manifests_ready_count"] == 0
    assert payload["summary"]["historical_seed_ablation_candidate_manifests_core_blocked_count"] == 0
    assert payload["summary"]["historical_seed_ablation_candidate_manifests_first_target_id"] == "HIST_BBA5"
    assert payload["summary"]["historical_seed_ablation_candidate_manifests_first_next_action"] == (
        "attach real ablation layer evidence before setting ablation_manifest_ref"
    )
    assert payload["summary"]["historical_seed_ablation_gap_repair_plan_status"] == (
        "ablation_gap_repair_required"
    )
    assert payload["summary"]["historical_seed_ablation_gap_repair_plan_seed_count"] == 15
    assert payload["summary"]["historical_seed_ablation_gap_repair_plan_repair_csv_count"] == 15
    assert payload["summary"]["historical_seed_ablation_gap_repair_plan_real_count"] == 1
    assert payload["summary"]["historical_seed_ablation_gap_repair_plan_missing_real_count"] == 19
    assert payload["summary"]["historical_seed_ablation_gap_repair_plan_top5_decoy_count"] == 60
    assert payload["summary"]["historical_seed_ablation_gap_repair_plan_top5_copy_count"] == 15
    assert payload["summary"]["historical_seed_ablation_gap_repair_plan_ready_count"] == 1
    assert payload["summary"]["historical_seed_ablation_gap_repair_plan_gap_count"] == 14
    assert payload["summary"]["historical_seed_ablation_gap_repair_plan_core_blocked_count"] == 0
    assert payload["summary"]["historical_seed_ablation_gap_repair_plan_first_target_id"] == "HIST_BBA5"
    assert payload["summary"]["historical_seed_top5_candidate_pools_status"] == (
        "top5_candidate_pool_ready_for_review"
    )
    assert payload["summary"]["historical_seed_top5_candidate_pools_seed_count"] == 15
    assert payload["summary"]["historical_seed_top5_candidate_pools_pool_count"] == 15
    assert payload["summary"]["historical_seed_top5_candidate_pools_candidate_model_count"] == 75
    assert payload["summary"]["historical_seed_top5_candidate_pools_complete_count"] == 15
    assert payload["summary"]["historical_seed_top5_candidate_pools_gap_count"] == 0
    assert payload["summary"]["historical_seed_top5_candidate_pools_source_present_count"] == 15
    assert payload["summary"]["historical_seed_top5_candidate_pools_generated_perturbation_count"] == 60
    assert payload["summary"]["historical_seed_top5_candidate_pools_blocked_source_count"] == 0
    assert payload["summary"]["historical_seed_top5_candidate_pools_first_target_id"] == "HIST_BBA5"
    assert payload["summary"]["historical_seed_internal_score_candidates_status"] == (
        "internal_score_candidates_ready_for_review"
    )
    assert payload["summary"]["historical_seed_internal_score_candidates_seed_count"] == 15
    assert payload["summary"]["historical_seed_internal_score_candidates_candidate_count"] == 76
    assert payload["summary"]["historical_seed_internal_score_candidates_scored_count"] == 76
    assert payload["summary"]["historical_seed_internal_score_candidates_top5_scored_count"] == 15
    assert payload["summary"]["historical_seed_internal_score_candidates_selected_score_count"] == 15
    assert payload["summary"]["historical_seed_internal_score_candidates_blocked_count"] == 0
    assert payload["summary"]["historical_seed_internal_score_candidates_first_target_id"] == "HIST_BBA5"
    assert payload["summary"]["historical_seed_native_oracle_metric_candidates_status"] == (
        "native_oracle_metric_candidates_ready_for_review"
    )
    assert payload["summary"]["historical_seed_native_oracle_metric_candidates_seed_count"] == 15
    assert payload["summary"]["historical_seed_native_oracle_metric_candidates_candidate_count"] == 76
    assert payload["summary"]["historical_seed_native_oracle_metric_candidates_metric_count"] == 76
    assert payload["summary"]["historical_seed_native_oracle_metric_candidates_top5_ready_count"] == 15
    assert payload["summary"]["historical_seed_native_oracle_metric_candidates_selected_count"] == 15
    assert payload["summary"]["historical_seed_native_oracle_metric_candidates_best_count"] == 15
    assert payload["summary"]["historical_seed_native_oracle_metric_candidates_blocked_count"] == 0
    assert payload["summary"]["historical_seed_native_oracle_metric_candidates_first_target_id"] == "HIST_BBA5"
    assert payload["summary"]["historical_seed_calibration_candidate_ledgers_status"] == (
        "operator_calibration_review_required"
    )
    assert payload["summary"]["historical_seed_calibration_candidate_ledgers_seed_count"] == 15
    assert payload["summary"]["historical_seed_calibration_candidate_ledgers_ledger_count"] == 15
    assert payload["summary"]["historical_seed_calibration_candidate_ledgers_candidate_model_count"] == 76
    assert payload["summary"]["historical_seed_calibration_candidate_ledgers_top5_ready_count"] == 15
    assert payload["summary"]["historical_seed_calibration_candidate_ledgers_selected_prediction_count"] == 15
    assert payload["summary"]["historical_seed_calibration_candidate_ledgers_selected_rank_candidate_count"] == 15
    assert payload["summary"]["historical_seed_calibration_candidate_ledgers_native_metric_count"] == 76
    assert payload["summary"]["historical_seed_calibration_candidate_ledgers_internal_score_count"] == 76
    assert payload["summary"]["historical_seed_calibration_candidate_ledgers_ready_count"] == 0
    assert payload["summary"]["historical_seed_calibration_candidate_ledgers_operator_review_count"] == 15
    assert payload["summary"]["historical_seed_calibration_candidate_ledgers_blocked_selected_prediction_count"] == 0
    assert payload["summary"]["historical_seed_calibration_candidate_ledgers_open_field_count"] == 90
    assert payload["summary"]["historical_seed_calibration_candidate_ledgers_first_target_id"] == "HIST_BBA5"
    assert payload["summary"]["historical_seed_calibration_candidate_ledgers_first_next_action"] == (
        "operator-fill calibration fields after no-leak provenance clearance"
    )
    assert payload["summary"]["historical_seed_calibration_field_candidates_status"] == (
        "calibration_field_candidates_ready_for_operator_apply"
    )
    assert payload["summary"]["historical_seed_calibration_field_candidates_seed_count"] == 15
    assert payload["summary"]["historical_seed_calibration_field_candidates_field_count"] == 90
    assert payload["summary"]["historical_seed_calibration_field_candidates_proposed_count"] == 90
    assert payload["summary"]["historical_seed_calibration_field_candidates_matching_count"] == 0
    assert payload["summary"]["historical_seed_calibration_field_candidates_conflict_count"] == 0
    assert payload["summary"]["historical_seed_calibration_field_candidates_blocked_field_count"] == 0
    assert payload["summary"]["historical_seed_calibration_field_candidates_ready_count"] == 15
    assert payload["summary"]["historical_seed_calibration_field_candidates_blocked_row_count"] == 0
    assert payload["summary"]["historical_seed_calibration_field_candidates_first_target_id"] == "HIST_BBA5"
    assert payload["summary"]["historical_seed_clearance_fill_candidate_packet_status"] == (
        "operator_provenance_required_with_field_candidates"
    )
    assert payload["summary"]["historical_seed_clearance_fill_candidate_packet_seed_count"] == 15
    assert payload["summary"]["historical_seed_clearance_fill_candidate_packet_field_count"] == 255
    assert payload["summary"]["historical_seed_clearance_fill_candidate_packet_proposed_count"] == 91
    assert payload["summary"]["historical_seed_clearance_fill_candidate_packet_operator_required_count"] == 150
    assert payload["summary"]["historical_seed_clearance_fill_candidate_packet_blocked_field_count"] == 14
    assert payload["summary"]["historical_seed_clearance_fill_candidate_packet_conflict_count"] == 0
    assert payload["summary"]["historical_seed_clearance_fill_candidate_packet_calibration_count"] == 90
    assert payload["summary"]["historical_seed_clearance_fill_candidate_packet_ablation_count"] == 1
    assert payload["summary"]["historical_seed_clearance_fill_candidate_packet_no_leak_manual_count"] == 150
    assert payload["summary"]["historical_seed_clearance_fill_candidate_packet_partial_row_count"] == 15
    assert payload["summary"]["historical_seed_clearance_fill_candidate_packet_full_ready_row_count"] == 0
    assert payload["summary"]["historical_seed_clearance_fill_candidate_packet_blocked_row_count"] == 15
    assert payload["summary"]["historical_seed_clearance_fill_candidate_packet_first_target_id"] == "HIST_BBA5"
    assert payload["summary"]["historical_seed_clearance_execution_board_status"] == (
        "first_row_operator_no_leak_only"
    )
    assert payload["summary"]["historical_seed_clearance_execution_board_seed_count"] == 15
    assert payload["summary"]["historical_seed_clearance_execution_board_no_leak_only_count"] == 1
    assert payload["summary"]["historical_seed_clearance_execution_board_ablation_repair_count"] == 14
    assert payload["summary"]["historical_seed_clearance_execution_board_operator_no_leak_field_count"] == 150
    assert payload["summary"]["historical_seed_clearance_execution_board_proposed_field_count"] == 91
    assert payload["summary"]["historical_seed_clearance_execution_board_calibration_count"] == 90
    assert payload["summary"]["historical_seed_clearance_execution_board_ablation_count"] == 1
    assert payload["summary"]["historical_seed_clearance_execution_board_blocked_ablation_count"] == 14
    assert payload["summary"]["historical_seed_clearance_execution_board_first_target_id"] == "HIST_CHIGNOLIN"
    assert payload["summary"]["historical_seed_clearance_execution_board_first_status"] == "operator_no_leak_only"
    assert payload["summary"]["historical_seed_clearance_execution_board_first_folder"] == (
        "casp17/historical_seed_clearance_execution_board/02_hist_chignolin"
    )
    assert payload["summary"]["historical_seed_first_clearance_operator_kit_status"] == (
        "operator_no_leak_intake_ready"
    )
    assert payload["summary"]["historical_seed_first_clearance_operator_kit_target_id"] == "HIST_CHIGNOLIN"
    assert payload["summary"]["historical_seed_first_clearance_operator_kit_benchmark_id"] == (
        "hist_seed_chignolin"
    )
    assert payload["summary"]["historical_seed_first_clearance_operator_kit_no_leak_count"] == 10
    assert payload["summary"]["historical_seed_first_clearance_operator_kit_ready_count"] == 7
    assert payload["summary"]["historical_seed_first_clearance_operator_kit_total_count"] == 17
    assert payload["summary"]["historical_seed_first_clearance_operator_kit_calibration_count"] == 6
    assert payload["summary"]["historical_seed_first_clearance_operator_kit_ablation_count"] == 1
    assert payload["summary"]["historical_seed_first_clearance_operator_kit_weak_count"] == 2
    assert payload["summary"]["historical_seed_first_clearance_operator_kit_preview_status"] == (
        "waiting_on_operator_no_leak_fields"
    )
    assert payload["summary"]["historical_seed_first_clearance_no_leak_gate_status"] == (
        "awaiting_operator_no_leak_values"
    )
    assert payload["summary"]["historical_seed_first_clearance_no_leak_gate_target_id"] == "HIST_CHIGNOLIN"
    assert payload["summary"]["historical_seed_first_clearance_no_leak_gate_benchmark_id"] == (
        "hist_seed_chignolin"
    )
    assert payload["summary"]["historical_seed_first_clearance_no_leak_gate_field_count"] == 10
    assert payload["summary"]["historical_seed_first_clearance_no_leak_gate_ready_count"] == 0
    assert payload["summary"]["historical_seed_first_clearance_no_leak_gate_blocked_count"] == 10
    assert payload["summary"]["historical_seed_first_clearance_no_leak_gate_value_missing_count"] == 10
    assert payload["summary"]["historical_seed_first_clearance_no_leak_gate_clearance_missing_count"] == 10
    assert payload["summary"]["historical_seed_first_clearance_no_leak_gate_policy_blocked_count"] == 10
    assert payload["summary"]["historical_seed_first_clearance_no_leak_gate_first_blocked_field"] == (
        "no_leak_evidence_ref"
    )
    assert payload["summary"]["historical_seed_first_clearance_no_leak_gate_first_blocker"] == (
        "operator_value_missing"
    )
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_packet_status"] == (
        "awaiting_first_clearance_no_leak_evidence_collection"
    )
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_packet_target_id"] == (
        "HIST_CHIGNOLIN"
    )
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_packet_benchmark_id"] == (
        "hist_seed_chignolin"
    )
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_packet_field_count"] == 10
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_packet_ready_count"] == 0
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_packet_open_count"] == 10
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_packet_stub_count"] == 10
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_packet_weak_count"] == 2
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_packet_first_open_field"] == (
        "no_leak_evidence_ref"
    )
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_packet_first_open_kind"] == (
        "independent_no_leak_evidence"
    )
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_review_gate_status"] == (
        "awaiting_first_clearance_no_leak_evidence_review"
    )
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_review_gate_target_id"] == (
        "HIST_CHIGNOLIN"
    )
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_review_gate_benchmark_id"] == (
        "hist_seed_chignolin"
    )
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_review_gate_field_count"] == 10
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_review_gate_ready_count"] == 0
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_review_gate_blocked_count"] == 10
    assert (
        payload["summary"][
            "historical_seed_first_clearance_no_leak_evidence_review_gate_template_value_missing_count"
        ]
        == 10
    )
    assert (
        payload["summary"][
            "historical_seed_first_clearance_no_leak_evidence_review_gate_stub_evidence_missing_count"
        ]
        == 10
    )
    assert (
        payload["summary"][
            "historical_seed_first_clearance_no_leak_evidence_review_gate_policy_blocked_count"
        ]
        == 10
    )
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_review_gate_first_blocker"] == (
        "template_operator_value_missing"
    )
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_sync_plan_status"] == (
        "awaiting_first_clearance_no_leak_evidence_review"
    )
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_sync_plan_mode"] == "dry_run"
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_sync_plan_review_status"] == (
        "awaiting_first_clearance_no_leak_evidence_review"
    )
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_sync_plan_target_id"] == (
        "HIST_CHIGNOLIN"
    )
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_sync_plan_benchmark_id"] == (
        "hist_seed_chignolin"
    )
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_sync_plan_action_count"] == 10
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_sync_plan_ready_count"] == 0
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_sync_plan_blocked_count"] == 10
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_sync_plan_applied_count"] == 0
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_sync_plan_review_blocked_count"] == 10
    assert payload["summary"]["historical_seed_first_clearance_no_leak_evidence_sync_plan_first_blocker"] == (
        "template_operator_value_missing"
    )
    assert payload["summary"]["historical_seed_first_clearance_closure_board_status"] == (
        "awaiting_first_clearance_no_leak_closure"
    )
    assert payload["summary"]["historical_seed_first_clearance_closure_board_target_id"] == "HIST_CHIGNOLIN"
    assert payload["summary"]["historical_seed_first_clearance_closure_board_benchmark_id"] == (
        "hist_seed_chignolin"
    )
    assert payload["summary"]["historical_seed_first_clearance_closure_board_stage_count"] == 7
    assert payload["summary"]["historical_seed_first_clearance_closure_board_ready_count"] == 1
    assert payload["summary"]["historical_seed_first_clearance_closure_board_blocked_count"] == 6
    assert payload["summary"]["historical_seed_first_clearance_closure_board_first_stage"] == (
        "evidence_packet"
    )
    assert payload["summary"]["historical_seed_first_clearance_closure_board_first_stage_status"] == (
        "awaiting_first_clearance_no_leak_evidence_collection"
    )
    assert payload["summary"]["historical_seed_first_clearance_closure_board_first_blocker"] == (
        "operator_value_missing"
    )
    assert payload["summary"]["historical_seed_first_clearance_closure_board_operator_kit_status"] == (
        "operator_no_leak_intake_ready"
    )
    assert payload["summary"]["historical_seed_first_clearance_closure_board_no_leak_gate_status"] == (
        "awaiting_operator_no_leak_values"
    )
    assert payload["summary"]["historical_seed_clearance_to_identity_intake_sync_status"] == (
        "waiting_on_cleared_seed_manifest"
    )
    assert payload["summary"]["historical_seed_clearance_to_identity_intake_sync_apply_mode"] == "dry_run"
    assert payload["summary"]["historical_seed_clearance_to_identity_intake_sync_seed_row_count"] == 0
    assert payload["summary"]["historical_seed_clearance_to_identity_intake_sync_eligible_count"] == 0
    assert payload["summary"]["historical_seed_clearance_to_identity_intake_sync_ready_count"] == 0
    assert payload["summary"]["historical_seed_clearance_to_identity_intake_sync_waiting_count"] == 15
    assert payload["summary"]["historical_seed_clearance_to_identity_intake_sync_blocked_count"] == 0
    assert payload["summary"]["historical_seed_clearance_to_identity_intake_sync_intake_row_count"] == 15
    assert payload["summary"]["historical_seed_clearance_to_identity_intake_sync_applied_count"] == 0
    assert payload["summary"]["historical_seed_clearance_to_identity_intake_sync_first_next_action"] == (
        "clear historical seed rows before syncing competitive identity intake"
    )
    assert payload["summary"]["sidechain_native_benchmark_status"] == "blocked"
    assert payload["summary"]["sidechain_native_benchmark_count"] == 40
    assert payload["summary"]["sidechain_native_pass_count"] == 0
    assert payload["summary"]["sidechain_native_blocked_count"] == 40
    assert payload["summary"]["sidechain_native_core_input_blocked_count"] == 40
    assert payload["summary"]["sidechain_native_leakage_blocked_count"] == 40
    assert payload["summary"]["sidechain_native_prediction_missing_count"] == 40
    assert payload["summary"]["sidechain_native_native_missing_count"] == 40
    assert payload["summary"]["sidechain_native_missing_core_file_count"] == 80
    assert payload["summary"]["sidechain_native_first_blocked_benchmark_id"] == "hist_REQUIRED_MONOMER_001"
    assert "prediction_pdb_missing" in payload["summary"]["sidechain_native_first_blocked_blockers"]
    assert payload["summary"]["sidechain_native_workorder_action_count"] == 120
    assert payload["summary"]["sidechain_native_open_workorder_action_count"] == 120
    assert payload["summary"]["sidechain_native_workorder_json"] == (
        "runs/casp17_sidechain_native_input_workorder_current.json"
    )
    assert payload["summary"]["sidechain_native_workorder_md"] == (
        "runs/casp17_sidechain_native_input_workorder_current.md"
    )
    assert payload["summary"]["first_operator_input_action_id"] == "historical_benchmark_inputs"
    assert len(payload["target_rows"]) == 2
    by_id = {row["artifact_id"]: row for row in payload["rows"]}
    assert by_id["target_model_folders"]["status"] == "ready"
    assert by_id["target_object_catalog"]["status"] == "ready"
    assert "protein_atom_objects:4" in by_id["target_object_folder_audit"]["blockers"]
    assert "coordinate_valid_objects:4" in by_id["target_object_folder_audit"]["blockers"]
    assert "total_protein_atoms:4" in by_id["target_object_folder_audit"]["blockers"]
    assert by_id["target_object_viewer_smoke"]["status"] == "pass"
    assert by_id["target_object_model_review"]["status"] == "pass"
    assert by_id["target_object_model_review"]["ready_count"] == 4
    assert "review_md:4" in by_id["target_object_model_review"]["blockers"]
    assert "gallery:pass" in by_id["target_object_model_review"]["blockers"]
    assert by_id["protein_object_library"]["status"] == "pass"
    assert by_id["protein_object_library"]["ready_count"] == 4
    assert "protein_folders:2" in by_id["protein_object_library"]["blockers"]
    assert "model_projection_viewer:4/4/4" in by_id["protein_object_library"]["blockers"]
    assert by_id["protein_object_library_completion_audit"]["status"] == "pass"
    assert by_id["protein_object_library_completion_audit"]["ready_count"] == 4
    assert by_id["protein_object_library_completion_audit"]["blocked_count"] == 0
    assert by_id["protein_object_library_completion_audit"]["total_count"] == 4
    assert "proteins:2/0/2" in by_id["protein_object_library_completion_audit"]["blockers"]
    assert "assets:4/4/4" in by_id["protein_object_library_completion_audit"]["blockers"]
    assert "manifests:4/2" in by_id["protein_object_library_completion_audit"]["blockers"]
    assert by_id["protein_object_library_navigation_catalog"]["status"] == (
        "protein_object_library_navigation_catalog_ready"
    )
    assert by_id["protein_object_library_navigation_catalog"]["ready_count"] == 4
    assert by_id["protein_object_library_navigation_catalog"]["blocked_count"] == 0
    assert by_id["protein_object_library_navigation_catalog"]["total_count"] == 4
    assert "proteins:2/0/2" in by_id["protein_object_library_navigation_catalog"]["blockers"]
    assert "links:2/2" in by_id["protein_object_library_navigation_catalog"]["blockers"]
    assert "largest:H9002_Example_Fab_Complex/3" in by_id[
        "protein_object_library_navigation_catalog"
    ]["blockers"]
    assert by_id["casp17_3d_molecular_object_atlas"]["status"] == (
        "casp17_3d_molecular_object_atlas_ready_review_only"
    )
    assert by_id["casp17_3d_molecular_object_atlas"]["ready_count"] == 14
    assert by_id["casp17_3d_molecular_object_atlas"]["blocked_count"] == 0
    assert by_id["casp17_3d_molecular_object_atlas"]["total_count"] == 14
    assert "proteins:5/0/5" in by_id["casp17_3d_molecular_object_atlas"]["blockers"]
    assert "objects:14/0/14" in by_id["casp17_3d_molecular_object_atlas"]["blockers"]
    assert "source_objects:4/10" in by_id["casp17_3d_molecular_object_atlas"]["blockers"]
    assert "source_proteins:2/4/overlap:1" in by_id["casp17_3d_molecular_object_atlas"]["blockers"]
    assert "links:14/14/14/10/10" in by_id["casp17_3d_molecular_object_atlas"]["blockers"]
    assert "sha:10/10" in by_id["casp17_3d_molecular_object_atlas"]["blockers"]
    assert "native_proof_author:0/0/0" in by_id["casp17_3d_molecular_object_atlas"]["blockers"]
    assert "first:H9002_Example_Fab_Complex/current_chain_A" in by_id[
        "casp17_3d_molecular_object_atlas"
    ]["blockers"]
    assert by_id["casp17_3d_molecular_object_atlas_completion_audit"]["status"] == (
        "casp17_3d_molecular_object_atlas_completion_audit_pass"
    )
    assert by_id["casp17_3d_molecular_object_atlas_completion_audit"]["ready_count"] == 14
    assert by_id["casp17_3d_molecular_object_atlas_completion_audit"]["blocked_count"] == 0
    assert by_id["casp17_3d_molecular_object_atlas_completion_audit"]["total_count"] == 14
    assert "proteins:5/5/5/5" in by_id[
        "casp17_3d_molecular_object_atlas_completion_audit"
    ]["blockers"]
    assert "objects:14/0/14" in by_id[
        "casp17_3d_molecular_object_atlas_completion_audit"
    ]["blockers"]
    assert "atlas_object_files:14/14/14" in by_id[
        "casp17_3d_molecular_object_atlas_completion_audit"
    ]["blockers"]
    assert "links:14/14/14/10/10" in by_id[
        "casp17_3d_molecular_object_atlas_completion_audit"
    ]["blockers"]
    assert "coordinate_copies:0/0" in by_id[
        "casp17_3d_molecular_object_atlas_completion_audit"
    ]["blockers"]
    assert "proof_author:0/0" in by_id[
        "casp17_3d_molecular_object_atlas_completion_audit"
    ]["blockers"]
    assert by_id["casp17_3d_molecular_object_metric_handoff"]["status"] == (
        "casp17_3d_molecular_object_metric_handoff_ready_review_only_ligand_gap"
    )
    assert by_id["casp17_3d_molecular_object_metric_handoff"]["ready_count"] == 14
    assert by_id["casp17_3d_molecular_object_metric_handoff"]["blocked_count"] == 0
    assert by_id["casp17_3d_molecular_object_metric_handoff"]["total_count"] == 14
    assert "objects:14/0/14" in by_id["casp17_3d_molecular_object_metric_handoff"]["blockers"]
    assert "source_objects:4/10" in by_id["casp17_3d_molecular_object_metric_handoff"]["blockers"]
    assert "metric_requirements:118" in by_id["casp17_3d_molecular_object_metric_handoff"]["blockers"]
    assert "covered_required:9/11" in by_id["casp17_3d_molecular_object_metric_handoff"]["blockers"]
    assert "missing_required:2/LDDT-PLI,BiSyRMSD" in by_id[
        "casp17_3d_molecular_object_metric_handoff"
    ]["blockers"]
    assert "ligand_gap:2" in by_id["casp17_3d_molecular_object_metric_handoff"]["blockers"]
    assert "families:1/12/1/0" in by_id["casp17_3d_molecular_object_metric_handoff"]["blockers"]
    assert "folders:5/14" in by_id["casp17_3d_molecular_object_metric_handoff"]["blockers"]
    assert "native_proof_author:0/0/0" in by_id[
        "casp17_3d_molecular_object_metric_handoff"
    ]["blockers"]
    assert by_id["casp17_3d_molecular_object_metric_handoff_completion_audit"]["status"] == (
        "casp17_3d_molecular_object_metric_handoff_completion_audit_pass"
    )
    assert by_id["casp17_3d_molecular_object_metric_handoff_completion_audit"]["ready_count"] == 14
    assert by_id["casp17_3d_molecular_object_metric_handoff_completion_audit"]["blocked_count"] == 0
    assert by_id["casp17_3d_molecular_object_metric_handoff_completion_audit"]["total_count"] == 14
    assert "proteins:5/5/5/5" in by_id[
        "casp17_3d_molecular_object_metric_handoff_completion_audit"
    ]["blockers"]
    assert "objects:14/0/14" in by_id[
        "casp17_3d_molecular_object_metric_handoff_completion_audit"
    ]["blockers"]
    assert "object_files:14/14/14/14" in by_id[
        "casp17_3d_molecular_object_metric_handoff_completion_audit"
    ]["blockers"]
    assert "metric_rows:118/118/mismatch:0" in by_id[
        "casp17_3d_molecular_object_metric_handoff_completion_audit"
    ]["blockers"]
    assert "evidence_awaiting:14" in by_id[
        "casp17_3d_molecular_object_metric_handoff_completion_audit"
    ]["blockers"]
    assert "coordinate_copies:0/0" in by_id[
        "casp17_3d_molecular_object_metric_handoff_completion_audit"
    ]["blockers"]
    assert "proof_author:0/0" in by_id[
        "casp17_3d_molecular_object_metric_handoff_completion_audit"
    ]["blockers"]
    assert by_id["raw_ranked_model_quarantine"]["status"] == "pass"
    assert by_id["raw_ranked_model_quarantine"]["ready_count"] == 15
    assert by_id["raw_ranked_model_quarantine"]["blocked_count"] == 0
    assert "author_present:15" in by_id["raw_ranked_model_quarantine"]["blockers"]
    assert by_id["current_casp17_submission_gate"]["status"] == "current_casp17_submission_gate_ready"
    assert by_id["current_casp17_submission_gate"]["ready_count"] == 19
    assert by_id["current_casp17_submission_gate"]["blocked_count"] == 0
    assert by_id["current_casp17_submission_gate"]["total_count"] == 19
    assert "go/no-go/total:19/0/19" in by_id["current_casp17_submission_gate"]["blockers"]
    assert "framework:True" in by_id["current_casp17_submission_gate"]["blockers"]
    assert "shape:pass/19/19" in by_id["current_casp17_submission_gate"]["blockers"]
    assert "lane_difficult:19" in by_id["current_casp17_submission_gate"]["blockers"]
    assert "server:False" in by_id["current_casp17_submission_gate"]["blockers"]
    assert by_id["current_casp17_sidechain_repack"]["status"] == "pass"
    assert by_id["current_casp17_sidechain_repack"]["ready_count"] == 19
    assert by_id["current_casp17_sidechain_repack"]["blocked_count"] == 0
    assert by_id["current_casp17_sidechain_repack"]["total_count"] == 19
    assert "pass/blocked/total:19/0/19" in by_id["current_casp17_sidechain_repack"]["blockers"]
    assert "soft_delta:529" in by_id["current_casp17_sidechain_repack"]["blockers"]
    assert "soft_before_after:1955/1426" in by_id["current_casp17_sidechain_repack"]["blockers"]
    assert "improved/repacked:7179/15657" in by_id["current_casp17_sidechain_repack"]["blockers"]
    assert "revert_guard:8" in by_id["current_casp17_sidechain_repack"]["blockers"]
    assert by_id["current_casp17_submission_package_preflight"]["status"] == "ready"
    assert by_id["current_casp17_submission_package_preflight"]["ready_count"] == 19
    assert by_id["current_casp17_submission_package_preflight"]["blocked_count"] == 0
    assert by_id["current_casp17_submission_package_preflight"]["total_count"] == 19
    assert "gate:current_casp17_submission_gate_ready/19/0/19" in by_id[
        "current_casp17_submission_package_preflight"
    ]["blockers"]
    assert "files:19" in by_id["current_casp17_submission_package_preflight"]["blockers"]
    assert "format:19" in by_id["current_casp17_submission_package_preflight"]["blockers"]
    assert "author:19" in by_id["current_casp17_submission_package_preflight"]["blockers"]
    assert "sidechain:19" in by_id["current_casp17_submission_package_preflight"]["blockers"]
    assert "sha256:19" in by_id["current_casp17_submission_package_preflight"]["blockers"]
    assert "server:False" in by_id["current_casp17_submission_package_preflight"]["blockers"]
    assert by_id["current_casp17_submission_deadline_guard"]["status"] == (
        "partial_current_upload_window_ready"
    )
    assert by_id["current_casp17_submission_deadline_guard"]["ready_count"] == 11
    assert by_id["current_casp17_submission_deadline_guard"]["blocked_count"] == 8
    assert by_id["current_casp17_submission_deadline_guard"]["total_count"] == 19
    assert "date:2026-06-02" in by_id["current_casp17_submission_deadline_guard"]["blockers"]
    assert "expired/today/future:8/2/9" in by_id["current_casp17_submission_deadline_guard"]["blockers"]
    assert "qa:15/4/0" in by_id["current_casp17_submission_deadline_guard"]["blockers"]
    assert "package:ready/19/0/19" in by_id["current_casp17_submission_deadline_guard"]["blockers"]
    assert "watchlist_stale:True/7" in by_id["current_casp17_submission_deadline_guard"]["blockers"]
    assert "first:T1331/human_submission_deadline_expired" in by_id[
        "current_casp17_submission_deadline_guard"
    ]["blockers"]
    assert "nearest:H2319/2026-06-02" in by_id["current_casp17_submission_deadline_guard"]["blockers"]
    assert by_id["current_casp17_upload_queue"]["status"] == (
        "official_verified_current_upload_queue_partial"
    )
    assert by_id["current_casp17_upload_queue"]["ready_count"] == 10
    assert by_id["current_casp17_upload_queue"]["blocked_count"] == 9
    assert by_id["current_casp17_upload_queue"]["total_count"] == 19
    assert "targets:77" in by_id["current_casp17_upload_queue"]["blockers"]
    assert "direct/mapped/missing:18/1/0" in by_id["current_casp17_upload_queue"]["blockers"]
    assert "ready/blocked:10/9" in by_id["current_casp17_upload_queue"]["blockers"]
    assert "today/soon/future:2/4/4" in by_id["current_casp17_upload_queue"]["blockers"]
    assert "expired/cancelled/mismatch:9/1/1" in by_id["current_casp17_upload_queue"]["blockers"]
    assert "first_ready:H2319/2026-06-02" in by_id["current_casp17_upload_queue"]["blockers"]
    assert "first_blocked:H1335/official_human_deadline_expired" in by_id[
        "current_casp17_upload_queue"
    ]["blockers"]
    assert by_id["current_casp17_upload_review_packet"]["status"] == (
        "current_upload_review_packet_ready"
    )
    assert by_id["current_casp17_upload_review_packet"]["ready_count"] == 10
    assert by_id["current_casp17_upload_review_packet"]["blocked_count"] == 0
    assert by_id["current_casp17_upload_review_packet"]["total_count"] == 10
    assert "queue:official_verified_current_upload_queue_partial/10/9/19" in by_id[
        "current_casp17_upload_review_packet"
    ]["blockers"]
    assert "urgency:2/4/4" in by_id["current_casp17_upload_review_packet"]["blockers"]
    assert "candidate/object/viewer:10/10/10" in by_id[
        "current_casp17_upload_review_packet"
    ]["blockers"]
    assert "first:H2319/casp17/current_upload_review_packet/" in by_id[
        "current_casp17_upload_review_packet"
    ]["blockers"]
    assert by_id["current_casp17_prospective_strict_blind_escrow"]["status"] == (
        "current_prospective_strict_blind_escrow_ready_native_pending_partial_upload_window"
    )
    assert by_id["current_casp17_prospective_strict_blind_escrow"]["ready_count"] == 19
    assert by_id["current_casp17_prospective_strict_blind_escrow"]["blocked_count"] == 0
    assert by_id["current_casp17_prospective_strict_blind_escrow"]["total_count"] == 19
    assert "upload:10/9" in by_id["current_casp17_prospective_strict_blind_escrow"]["blockers"]
    assert "sha/review/native/ext-ts:19/10/19/19" in by_id[
        "current_casp17_prospective_strict_blind_escrow"
    ]["blockers"]
    assert "proof:0,author:0" in by_id["current_casp17_prospective_strict_blind_escrow"]["blockers"]
    assert "first_upload:H2319" in by_id["current_casp17_prospective_strict_blind_escrow"]["blockers"]
    assert "first_blocked_upload:H1335" in by_id[
        "current_casp17_prospective_strict_blind_escrow"
    ]["blockers"]
    assert by_id["win_tier_goal_scorecard"]["status"] == "blocked_input"
    assert by_id["win_tier_goal_scorecard"]["ready_count"] == 1
    assert "historical_identity_clearance" in by_id["win_tier_goal_scorecard"]["blockers"]
    assert by_id["historical_winner_normalized_bands"]["status"] == (
        "blocked_strict_blind_metrics_missing"
    )
    assert by_id["historical_winner_normalized_bands"]["ready_count"] == 0
    assert by_id["historical_winner_normalized_bands"]["blocked_count"] == 5
    assert by_id["historical_winner_normalized_bands"]["total_count"] == 5
    assert "bands:0/0/5/5" in by_id["historical_winner_normalized_bands"]["blockers"]
    assert "strict:0/40" in by_id["historical_winner_normalized_bands"]["blockers"]
    assert "metrics:0/440" in by_id["historical_winner_normalized_bands"]["blockers"]
    assert "official_archive:24/0" in by_id["historical_winner_normalized_bands"]["blockers"]
    assert "first:casp15_regular_domain/strict_blind_historical_metric_surface_missing" in by_id[
        "historical_winner_normalized_bands"
    ]["blockers"]
    assert by_id["historical_winner_normalized_unlock_plan"]["status"] == (
        "awaiting_historical_winner_normalized_unlocks"
    )
    assert by_id["historical_winner_normalized_unlock_plan"]["ready_count"] == 1
    assert by_id["historical_winner_normalized_unlock_plan"]["blocked_count"] == 5
    assert by_id["historical_winner_normalized_unlock_plan"]["total_count"] == 6
    assert "actions:1/5/6" in by_id["historical_winner_normalized_unlock_plan"]["blockers"]
    assert "strict:0/40" in by_id["historical_winner_normalized_unlock_plan"]["blockers"]
    assert "metrics:0/440" in by_id["historical_winner_normalized_unlock_plan"]["blockers"]
    assert "sidechain:0/40" in by_id["historical_winner_normalized_unlock_plan"]["blockers"]
    assert "winner_bands:0/5" in by_id["historical_winner_normalized_unlock_plan"]["blockers"]
    assert "first:close_first_source_request/strict_blind_internal_prediction_source/prediction_not_before_native" in by_id[
        "historical_winner_normalized_unlock_plan"
    ]["blockers"]
    assert by_id["win_tier_metric_surface_contract"]["status"] == (
        "awaiting_strict_blind_evidence_files_and_ligand_category_slots"
    )
    assert by_id["win_tier_metric_surface_contract"]["ready_count"] == 0
    assert by_id["win_tier_metric_surface_contract"]["blocked_count"] == 440
    assert by_id["win_tier_metric_surface_contract"]["total_count"] == 440
    assert "metrics:11/11" in by_id["win_tier_metric_surface_contract"]["blockers"]
    assert "slots:0/40/40" in by_id["win_tier_metric_surface_contract"]["blockers"]
    assert "ligand_slots:0" in by_id["win_tier_metric_surface_contract"]["blockers"]
    assert "official_archive:excluded_from_competitive_proof" in by_id[
        "win_tier_metric_surface_contract"
    ]["blockers"]
    assert by_id["win_tier_critical_path_board"]["status"] == (
        "competitive_proof_blocked_on_strict_blind_evidence"
    )
    assert by_id["win_tier_critical_path_board"]["ready_count"] == 3
    assert by_id["win_tier_critical_path_board"]["blocked_count"] == 6
    assert by_id["win_tier_critical_path_board"]["total_count"] == 9
    assert "3d:4/4" in by_id["win_tier_critical_path_board"]["blockers"]
    assert "external:4/4" in by_id["win_tier_critical_path_board"]["blockers"]
    assert "model1/top5:4/20" in by_id["win_tier_critical_path_board"]["blockers"]
    assert "strict:0/40" in by_id["win_tier_critical_path_board"]["blockers"]
    assert "missing_files:240" in by_id["win_tier_critical_path_board"]["blockers"]
    assert by_id["organic_ligand_slot_candidate_packet"]["status"] == (
        "organic_ligand_slot_candidates_ready_for_operator_review"
    )
    assert by_id["organic_ligand_slot_candidate_packet"]["ready_count"] == 2
    assert by_id["organic_ligand_slot_candidate_packet"]["blocked_count"] == 2
    assert by_id["organic_ligand_slot_candidate_packet"]["total_count"] == 2
    assert "chembl/bindingdb:1/1" in by_id["organic_ligand_slot_candidate_packet"]["blockers"]
    assert "proof_eligible:0" in by_id["organic_ligand_slot_candidate_packet"]["blockers"]
    assert "strict_blocked:2" in by_id["organic_ligand_slot_candidate_packet"]["blockers"]
    assert "metrics:2/2" in by_id["organic_ligand_slot_candidate_packet"]["blockers"]
    assert by_id["organic_ligand_slot_promotion_action_board"]["status"] == (
        "awaiting_organic_ligand_strict_blind_evidence"
    )
    assert by_id["organic_ligand_slot_promotion_action_board"]["ready_count"] == 2
    assert by_id["organic_ligand_slot_promotion_action_board"]["blocked_count"] == 16
    assert by_id["organic_ligand_slot_promotion_action_board"]["total_count"] == 18
    assert "candidates:2" in by_id["organic_ligand_slot_promotion_action_board"]["blockers"]
    assert "operator:8" in by_id["organic_ligand_slot_promotion_action_board"]["blockers"]
    assert "numeric:1" in by_id["organic_ligand_slot_promotion_action_board"]["blockers"]
    assert "affinity_source:1" in by_id["organic_ligand_slot_promotion_action_board"]["blockers"]
    assert "metric:4" in by_id["organic_ligand_slot_promotion_action_board"]["blockers"]
    assert "slot:2" in by_id["organic_ligand_slot_promotion_action_board"]["blockers"]
    assert by_id["active_scope_decision"]["status"] == "casp17_only_active"
    assert by_id["active_scope_decision"]["ready_count"] == 3
    assert by_id["active_scope_decision"]["total_count"] == 4
    assert "scope:casp17_only" in by_id["active_scope_decision"]["blockers"]
    assert "capri:deferred_pi_required" in by_id["active_scope_decision"]["blockers"]
    assert by_id["organizer_notice_packet"]["status"] == "organizer_notice_intake_ready"
    assert by_id["organizer_notice_packet"]["ready_count"] == 3
    assert by_id["organizer_notice_packet"]["total_count"] == 3
    assert "r2345_first:ignored_invalid_dna_t_in_rna_sequence" in by_id["organizer_notice_packet"]["blockers"]
    assert "scope:all_human_rna_and_hybrid_targets_plus_protein_targets" in by_id[
        "organizer_notice_packet"
    ]["blockers"]
    assert "massivefold_rna_hybrid:2" in by_id["organizer_notice_packet"]["blockers"]
    assert "policy:do_not_mark_as_internal_prediction" in by_id["organizer_notice_packet"]["blockers"]
    assert by_id["massivefold_external_pool_intake"]["status"] == "massivefold_external_pool_intake_ready"
    assert by_id["massivefold_external_pool_intake"]["ready_count"] == 3
    assert by_id["massivefold_external_pool_intake"]["blocked_count"] == 0
    assert by_id["massivefold_external_pool_intake"]["total_count"] == 3
    assert "rna_hybrid:2" in by_id["massivefold_external_pool_intake"]["blockers"]
    assert "protein_complex:1" in by_id["massivefold_external_pool_intake"]["blockers"]
    assert "proof_eligible:0" in by_id["massivefold_external_pool_intake"]["blockers"]
    assert "internal_blocked:3" in by_id["massivefold_external_pool_intake"]["blockers"]
    assert "largest:H2335_T335" in by_id["massivefold_external_pool_intake"]["blockers"]
    assert by_id["rna_hybrid_massivefold_priority_queue"]["status"] == (
        "rna_hybrid_massivefold_priority_queue_ready"
    )
    assert by_id["rna_hybrid_massivefold_priority_queue"]["ready_count"] == 2
    assert by_id["rna_hybrid_massivefold_priority_queue"]["blocked_count"] == 0
    assert by_id["rna_hybrid_massivefold_priority_queue"]["total_count"] == 2
    assert "first:R2341" in by_id["rna_hybrid_massivefold_priority_queue"]["blockers"]
    assert "r2341_rank:1" in by_id["rna_hybrid_massivefold_priority_queue"]["blockers"]
    assert "r2345_rank:2" in by_id["rna_hybrid_massivefold_priority_queue"]["blockers"]
    assert "r2345_invalid:ignored_invalid_dna_t_in_rna_sequence" in by_id[
        "rna_hybrid_massivefold_priority_queue"
    ]["blockers"]
    assert "proof_eligible:0" in by_id["rna_hybrid_massivefold_priority_queue"]["blockers"]
    assert by_id["protein_complex_massivefold_priority_queue"]["status"] == (
        "protein_complex_massivefold_priority_queue_ready"
    )
    assert by_id["protein_complex_massivefold_priority_queue"]["ready_count"] == 1
    assert by_id["protein_complex_massivefold_priority_queue"]["blocked_count"] == 0
    assert by_id["protein_complex_massivefold_priority_queue"]["total_count"] == 1
    assert "first:H1311" in by_id["protein_complex_massivefold_priority_queue"]["blockers"]
    assert "model_set:H1311_T327" in by_id["protein_complex_massivefold_priority_queue"]["blockers"]
    assert "largest:H1311_T327" in by_id["protein_complex_massivefold_priority_queue"]["blockers"]
    assert "proof_eligible:0" in by_id["protein_complex_massivefold_priority_queue"]["blockers"]
    assert by_id["massivefold_acquisition_verification_board"]["status"] == (
        "massivefold_external_pool_acquisition_verified"
    )
    assert by_id["massivefold_acquisition_verification_board"]["ready_count"] == 2
    assert by_id["massivefold_acquisition_verification_board"]["blocked_count"] == 0
    assert by_id["massivefold_acquisition_verification_board"]["total_count"] == 2
    assert "first:R2341" in by_id["massivefold_acquisition_verification_board"]["blockers"]
    assert "download:2" in by_id["massivefold_acquisition_verification_board"]["blockers"]
    assert "hash:2" in by_id["massivefold_acquisition_verification_board"]["blockers"]
    assert "listing:2" in by_id["massivefold_acquisition_verification_board"]["blockers"]
    assert "r2341:verified_for_external_rerank_intake" in by_id[
        "massivefold_acquisition_verification_board"
    ]["blockers"]
    assert "r2345:verified_for_external_rerank_intake" in by_id[
        "massivefold_acquisition_verification_board"
    ]["blockers"]
    assert by_id["protein_complex_massivefold_acquisition_verification_board"]["status"] == (
        "awaiting_massivefold_external_pool_acquisition"
    )
    assert by_id["protein_complex_massivefold_acquisition_verification_board"]["ready_count"] == 0
    assert by_id["protein_complex_massivefold_acquisition_verification_board"]["blocked_count"] == 1
    assert by_id["protein_complex_massivefold_acquisition_verification_board"]["total_count"] == 1
    assert "first:H1311" in by_id[
        "protein_complex_massivefold_acquisition_verification_board"
    ]["blockers"]
    assert "open:H1311" in by_id[
        "protein_complex_massivefold_acquisition_verification_board"
    ]["blockers"]
    assert "status:open_tarball_download_required" in by_id[
        "protein_complex_massivefold_acquisition_verification_board"
    ]["blockers"]
    assert by_id["massivefold_model_pool_index"]["status"] == (
        "massivefold_model_pool_representatives_extracted"
    )
    assert by_id["massivefold_model_pool_index"]["ready_count"] == 40
    assert by_id["massivefold_model_pool_index"]["blocked_count"] == 0
    assert by_id["massivefold_model_pool_index"]["total_count"] == 40
    assert "target:R2341" in by_id["massivefold_model_pool_index"]["blockers"]
    assert "models:8040" in by_id["massivefold_model_pool_index"]["blockers"]
    assert "protocols:8" in by_id["massivefold_model_pool_index"]["blockers"]
    assert "extracted:40" in by_id["massivefold_model_pool_index"]["blockers"]
    assert "sha:cfaaad6299ff" in by_id["massivefold_model_pool_index"]["blockers"]
    assert by_id["massivefold_representative_viewer_packet"]["status"] == (
        "massivefold_representative_viewers_ready"
    )
    assert by_id["massivefold_representative_viewer_packet"]["ready_count"] == 40
    assert by_id["massivefold_representative_viewer_packet"]["blocked_count"] == 0
    assert by_id["massivefold_representative_viewer_packet"]["total_count"] == 40
    assert "target:R2341" in by_id["massivefold_representative_viewer_packet"]["blockers"]
    assert "viewers:40" in by_id["massivefold_representative_viewer_packet"]["blockers"]
    assert "coordinates:40" in by_id["massivefold_representative_viewer_packet"]["blockers"]
    assert "projection:40" in by_id["massivefold_representative_viewer_packet"]["blockers"]
    assert by_id["massivefold_representative_rerank_packet"]["status"] == (
        "massivefold_representative_rerank_ready_review_only"
    )
    assert by_id["massivefold_representative_rerank_packet"]["ready_count"] == 5
    assert by_id["massivefold_representative_rerank_packet"]["blocked_count"] == 35
    assert by_id["massivefold_representative_rerank_packet"]["total_count"] == 40
    assert "target:R2341" in by_id["massivefold_representative_rerank_packet"]["blockers"]
    assert "model1:1" in by_id["massivefold_representative_rerank_packet"]["blockers"]
    assert "top5:5" in by_id["massivefold_representative_rerank_packet"]["blockers"]
    assert "proof_eligible:0" in by_id["massivefold_representative_rerank_packet"]["blockers"]
    assert by_id["massivefold_rna_model_selection_coverage"]["status"] == (
        "massivefold_rna_model_selection_coverage_ready_review_only"
    )
    assert by_id["massivefold_rna_model_selection_coverage"]["ready_count"] == 2
    assert by_id["massivefold_rna_model_selection_coverage"]["blocked_count"] == 0
    assert by_id["massivefold_rna_model_selection_coverage"]["total_count"] == 2
    assert "targets:2" in by_id["massivefold_rna_model_selection_coverage"]["blockers"]
    assert "verified:2" in by_id["massivefold_rna_model_selection_coverage"]["blockers"]
    assert "models:80/80/80" in by_id["massivefold_rna_model_selection_coverage"]["blockers"]
    assert "model1/top5:2/10" in by_id["massivefold_rna_model_selection_coverage"]["blockers"]
    assert by_id["massivefold_rna_model_selection_input_packet"]["status"] == (
        "massivefold_rna_model_selection_input_packet_ready_external_only"
    )
    assert by_id["massivefold_rna_model_selection_input_packet"]["ready_count"] == 2
    assert by_id["massivefold_rna_model_selection_input_packet"]["blocked_count"] == 0
    assert by_id["massivefold_rna_model_selection_input_packet"]["total_count"] == 2
    assert "targets:2" in by_id["massivefold_rna_model_selection_input_packet"]["blockers"]
    assert "model1/top5:2/10" in by_id["massivefold_rna_model_selection_input_packet"]["blockers"]
    assert "missing:0" in by_id["massivefold_rna_model_selection_input_packet"]["blockers"]
    assert "r2345_guard:ignore_0930_pacific_invalid_dna_t_request_use_1130_replacement_only" in by_id[
        "massivefold_rna_model_selection_input_packet"
    ]["blockers"]
    assert "policy:do_not_mark_as_internal_prediction" in by_id[
        "massivefold_rna_model_selection_input_packet"
    ]["blockers"]
    assert by_id["massivefold_rna_self_assessment_packet"]["status"] == (
        "massivefold_rna_self_assessment_ready_external_only"
    )
    assert by_id["massivefold_rna_self_assessment_packet"]["ready_count"] == 2
    assert by_id["massivefold_rna_self_assessment_packet"]["blocked_count"] == 0
    assert by_id["massivefold_rna_self_assessment_packet"]["total_count"] == 2
    assert "targets:2" in by_id["massivefold_rna_self_assessment_packet"]["blockers"]
    assert "candidates:10" in by_id["massivefold_rna_self_assessment_packet"]["blockers"]
    assert "model1/top5:2/10" in by_id["massivefold_rna_self_assessment_packet"]["blockers"]
    assert "low_margin:1" in by_id["massivefold_rna_self_assessment_packet"]["blockers"]
    assert "r2345_guard:ignore_0930_pacific_invalid_dna_t_request_use_1130_replacement_only" in by_id[
        "massivefold_rna_self_assessment_packet"
    ]["blockers"]
    assert "policy:do_not_mark_as_internal_prediction" in by_id[
        "massivefold_rna_self_assessment_packet"
    ]["blockers"]
    assert by_id["protein_complex_massivefold_model_selection_coverage"]["status"] == (
        "protein_complex_massivefold_model_selection_coverage_ready_review_only"
    )
    assert by_id["protein_complex_massivefold_model_selection_coverage"]["ready_count"] == 2
    assert by_id["protein_complex_massivefold_model_selection_coverage"]["blocked_count"] == 0
    assert by_id["protein_complex_massivefold_model_selection_coverage"]["total_count"] == 2
    assert "targets:2" in by_id["protein_complex_massivefold_model_selection_coverage"]["blockers"]
    assert "verified:2" in by_id["protein_complex_massivefold_model_selection_coverage"]["blockers"]
    assert "models:260/260/260" in by_id["protein_complex_massivefold_model_selection_coverage"]["blockers"]
    assert "model1/top5:2/10" in by_id["protein_complex_massivefold_model_selection_coverage"]["blockers"]
    assert by_id["protein_complex_massivefold_self_assessment_packet"]["status"] == (
        "protein_complex_massivefold_self_assessment_ready_external_only"
    )
    assert by_id["protein_complex_massivefold_self_assessment_packet"]["ready_count"] == 2
    assert by_id["protein_complex_massivefold_self_assessment_packet"]["blocked_count"] == 0
    assert by_id["protein_complex_massivefold_self_assessment_packet"]["total_count"] == 2
    assert "targets:2" in by_id["protein_complex_massivefold_self_assessment_packet"]["blockers"]
    assert "heteromer:1" in by_id["protein_complex_massivefold_self_assessment_packet"]["blockers"]
    assert "candidates:10" in by_id["protein_complex_massivefold_self_assessment_packet"]["blockers"]
    assert "model1/top5:2/10" in by_id["protein_complex_massivefold_self_assessment_packet"]["blockers"]
    assert "missing:0" in by_id["protein_complex_massivefold_self_assessment_packet"]["blockers"]
    assert "low_margin:1" in by_id["protein_complex_massivefold_self_assessment_packet"]["blockers"]
    assert "policy:do_not_mark_as_internal_prediction" in by_id[
        "protein_complex_massivefold_self_assessment_packet"
    ]["blockers"]
    assert by_id["massivefold_model1_risk_queue"]["status"] == (
        "massivefold_model1_risk_queue_ready_external_only"
    )
    assert by_id["massivefold_model1_risk_queue"]["ready_count"] == 4
    assert by_id["massivefold_model1_risk_queue"]["blocked_count"] == 0
    assert by_id["massivefold_model1_risk_queue"]["total_count"] == 4
    assert "targets:4" in by_id["massivefold_model1_risk_queue"]["blockers"]
    assert "low_margin:2" in by_id["massivefold_model1_risk_queue"]["blockers"]
    assert "critical:1" in by_id["massivefold_model1_risk_queue"]["blockers"]
    assert "rna/protein:2/2" in by_id["massivefold_model1_risk_queue"]["blockers"]
    assert "first:H1311" in by_id["massivefold_model1_risk_queue"]["blockers"]
    assert "tier:critical_model1_margin" in by_id["massivefold_model1_risk_queue"]["blockers"]
    assert "policy:do_not_mark_as_internal_prediction" in by_id[
        "massivefold_model1_risk_queue"
    ]["blockers"]
    assert by_id["massivefold_critical_rerank_experiment"]["status"] == (
        "massivefold_critical_rerank_experiment_ready_external_only"
    )
    assert by_id["massivefold_critical_rerank_experiment"]["ready_count"] == 2
    assert by_id["massivefold_critical_rerank_experiment"]["blocked_count"] == 0
    assert by_id["massivefold_critical_rerank_experiment"]["total_count"] == 2
    assert "experiments:2" in by_id["massivefold_critical_rerank_experiment"]["blockers"]
    assert "rna/protein:1/1" in by_id["massivefold_critical_rerank_experiment"]["blockers"]
    assert "reviews:1/1/1" in by_id["massivefold_critical_rerank_experiment"]["blockers"]
    assert "first:R2350" in by_id["massivefold_critical_rerank_experiment"]["blockers"]
    assert "formula:gap_plus_geometry_plus_diversity_penalty_v1" in by_id[
        "massivefold_critical_rerank_experiment"
    ]["blockers"]
    assert "policy:do_not_mark_as_internal_prediction" in by_id[
        "massivefold_critical_rerank_experiment"
    ]["blockers"]
    assert by_id["massivefold_critical_rerank_score_ledger"]["status"] == (
        "massivefold_critical_rerank_score_ledger_ready_external_only"
    )
    assert by_id["massivefold_critical_rerank_score_ledger"]["ready_count"] == 2
    assert by_id["massivefold_critical_rerank_score_ledger"]["blocked_count"] == 0
    assert by_id["massivefold_critical_rerank_score_ledger"]["total_count"] == 2
    assert "ledger:2" in by_id["massivefold_critical_rerank_score_ledger"]["blockers"]
    assert "bands:0/2/0" in by_id["massivefold_critical_rerank_score_ledger"]["blockers"]
    assert "rna/protein:1/1" in by_id["massivefold_critical_rerank_score_ledger"]["blockers"]
    assert "top:R2350" in by_id["massivefold_critical_rerank_score_ledger"]["blockers"]
    assert "score:66" in by_id["massivefold_critical_rerank_score_ledger"]["blockers"]
    assert "action:run_targeted_probe_then_freeze_model1_if_consistent" in by_id[
        "massivefold_critical_rerank_score_ledger"
    ]["blockers"]
    assert "policy:do_not_mark_as_internal_prediction" in by_id[
        "massivefold_critical_rerank_score_ledger"
    ]["blockers"]
    assert by_id["massivefold_model1_selection_calibration_gate"]["status"] == (
        "massivefold_model1_selection_calibration_gate_ready_external_only"
    )
    assert by_id["massivefold_model1_selection_calibration_gate"]["ready_count"] == 2
    assert by_id["massivefold_model1_selection_calibration_gate"]["blocked_count"] == 0
    assert by_id["massivefold_model1_selection_calibration_gate"]["total_count"] == 2
    assert "gates:2" in by_id["massivefold_model1_selection_calibration_gate"]["blockers"]
    assert "freeze_gate:model1_freeze_blocked_by_calibration" in by_id[
        "massivefold_model1_selection_calibration_gate"
    ]["blockers"]
    assert "hold/watch/probe/freeze:1/1/2/0" in by_id[
        "massivefold_model1_selection_calibration_gate"
    ]["blockers"]
    assert "rna/protein:1/1" in by_id["massivefold_model1_selection_calibration_gate"]["blockers"]
    assert "first:R2350" in by_id["massivefold_model1_selection_calibration_gate"]["blockers"]
    assert "decision:hold_model1_freeze_probe_required" in by_id[
        "massivefold_model1_selection_calibration_gate"
    ]["blockers"]
    assert "rule:no_native_model1_selection_gate_v1" in by_id[
        "massivefold_model1_selection_calibration_gate"
    ]["blockers"]
    assert "policy:do_not_mark_as_internal_prediction" in by_id[
        "massivefold_model1_selection_calibration_gate"
    ]["blockers"]
    assert by_id["massivefold_model1_probe_worklist"]["status"] == (
        "massivefold_model1_probe_worklist_ready_external_only"
    )
    assert by_id["massivefold_model1_probe_worklist"]["ready_count"] == 2
    assert by_id["massivefold_model1_probe_worklist"]["blocked_count"] == 0
    assert by_id["massivefold_model1_probe_worklist"]["total_count"] == 2
    assert "workitems:2" in by_id["massivefold_model1_probe_worklist"]["blockers"]
    assert "probes:1/1" in by_id["massivefold_model1_probe_worklist"]["blockers"]
    assert "priority:1/1" in by_id["massivefold_model1_probe_worklist"]["blockers"]
    assert "rna/protein:1/1" in by_id["massivefold_model1_probe_worklist"]["blockers"]
    assert "first:R2350" in by_id["massivefold_model1_probe_worklist"]["blockers"]
    assert "probe:top5_rerank_consistency_probe" in by_id["massivefold_model1_probe_worklist"]["blockers"]
    assert "unlock:freeze_after_probe_allowed_only_if_exit_criterion_passes" in by_id[
        "massivefold_model1_probe_worklist"
    ]["blockers"]
    assert "policy:do_not_mark_as_internal_prediction" in by_id[
        "massivefold_model1_probe_worklist"
    ]["blockers"]
    assert by_id["massivefold_model1_probe_outcome"]["status"] == (
        "massivefold_model1_probe_outcome_ready_external_only"
    )
    assert by_id["massivefold_model1_probe_outcome"]["ready_count"] == 2
    assert by_id["massivefold_model1_probe_outcome"]["blocked_count"] == 0
    assert by_id["massivefold_model1_probe_outcome"]["total_count"] == 2
    assert "outcomes:2" in by_id["massivefold_model1_probe_outcome"]["blockers"]
    assert "pass/fail/freeze:2/0/2" in by_id["massivefold_model1_probe_outcome"]["blockers"]
    assert "probes:1/1" in by_id["massivefold_model1_probe_outcome"]["blockers"]
    assert "rna/protein:1/1" in by_id["massivefold_model1_probe_outcome"]["blockers"]
    assert "first:R2350" in by_id["massivefold_model1_probe_outcome"]["blockers"]
    assert "result:probe_pass_model1_retained" in by_id["massivefold_model1_probe_outcome"]["blockers"]
    assert "recommendation:conditional_model1_freeze_ready_external_only" in by_id[
        "massivefold_model1_probe_outcome"
    ]["blockers"]
    assert "rule:no_native_probe_rescore_v1" in by_id["massivefold_model1_probe_outcome"]["blockers"]
    assert "policy:do_not_mark_as_internal_prediction" in by_id[
        "massivefold_model1_probe_outcome"
    ]["blockers"]
    assert by_id["massivefold_model1_freeze_decision_packet"]["status"] == (
        "massivefold_model1_freeze_decision_packet_ready_external_only"
    )
    assert by_id["massivefold_model1_freeze_decision_packet"]["ready_count"] == 2
    assert by_id["massivefold_model1_freeze_decision_packet"]["blocked_count"] == 0
    assert by_id["massivefold_model1_freeze_decision_packet"]["total_count"] == 2
    assert "decisions:2" in by_id["massivefold_model1_freeze_decision_packet"]["blockers"]
    assert "freeze-ready/blocked:1/1" in by_id[
        "massivefold_model1_freeze_decision_packet"
    ]["blockers"]
    assert "conditional/watch/manual:1/0/1" in by_id[
        "massivefold_model1_freeze_decision_packet"
    ]["blockers"]
    assert "rna/protein:1/1" in by_id["massivefold_model1_freeze_decision_packet"]["blockers"]
    assert "first-ready:R2350" in by_id["massivefold_model1_freeze_decision_packet"]["blockers"]
    assert "first-blocked:H2312" in by_id["massivefold_model1_freeze_decision_packet"]["blockers"]
    assert "rule:no_native_model1_freeze_decision_v1" in by_id[
        "massivefold_model1_freeze_decision_packet"
    ]["blockers"]
    assert "policy:do_not_mark_as_internal_prediction" in by_id[
        "massivefold_model1_freeze_decision_packet"
    ]["blockers"]
    assert by_id["massivefold_model_selection_ledger"]["status"] == (
        "massivefold_model_selection_ledger_ready_external_only"
    )
    assert by_id["massivefold_model_selection_ledger"]["ready_count"] == 15
    assert by_id["massivefold_model_selection_ledger"]["blocked_count"] == 0
    assert by_id["massivefold_model_selection_ledger"]["total_count"] == 15
    assert "ledgers:15" in by_id["massivefold_model_selection_ledger"]["blockers"]
    assert "selected:2/1" in by_id["massivefold_model_selection_ledger"]["blockers"]
    assert "manual/review:1/11" in by_id["massivefold_model_selection_ledger"]["blockers"]
    assert "freeze-ready:3" in by_id["massivefold_model_selection_ledger"]["blockers"]
    assert "rna/protein:6/9" in by_id["massivefold_model_selection_ledger"]["blockers"]
    assert "first:R2350" in by_id["massivefold_model_selection_ledger"]["blockers"]
    assert "decision:external_model1_selected_conditional" in by_id[
        "massivefold_model_selection_ledger"
    ]["blockers"]
    assert "manual:R2352" in by_id["massivefold_model_selection_ledger"]["blockers"]
    assert "rule:no_native_massivefold_model_selection_ledger_v1" in by_id[
        "massivefold_model_selection_ledger"
    ]["blockers"]
    assert "policy:do_not_mark_as_internal_prediction" in by_id[
        "massivefold_model_selection_ledger"
    ]["blockers"]
    assert by_id["massivefold_model1_combined_selector_overlay"]["status"] == (
        "massivefold_model1_combined_selector_overlay_ready_external_only"
    )
    assert by_id["massivefold_model1_combined_selector_overlay"]["ready_count"] == 4
    assert by_id["massivefold_model1_combined_selector_overlay"]["blocked_count"] == 0
    assert by_id["massivefold_model1_combined_selector_overlay"]["total_count"] == 4
    assert "overlay:4/0/4" in by_id["massivefold_model1_combined_selector_overlay"]["blockers"]
    assert "freeze:1/3" in by_id["massivefold_model1_combined_selector_overlay"]["blockers"]
    assert "holds:1/1/0/1/0/0" in by_id[
        "massivefold_model1_combined_selector_overlay"
    ]["blockers"]
    assert "baseline:0.500/0.500" in by_id[
        "massivefold_model1_combined_selector_overlay"
    ]["blockers"]
    assert "first:R2352/selector_blocked_manual_review" in by_id[
        "massivefold_model1_combined_selector_overlay"
    ]["blockers"]
    assert "first_freeze:R2350/carry_model1_as_external_only_freeze_ready" in by_id[
        "massivefold_model1_combined_selector_overlay"
    ]["blockers"]
    assert "proof_eligible:False" in by_id[
        "massivefold_model1_combined_selector_overlay"
    ]["blockers"]
    assert "policy:do_not_mark_as_internal_prediction" in by_id[
        "massivefold_model1_combined_selector_overlay"
    ]["blockers"]
    assert by_id["massivefold_freeze_ready_review_packet"]["status"] == (
        "massivefold_freeze_ready_review_packet_ready_external_only"
    )
    assert by_id["massivefold_freeze_ready_review_packet"]["ready_count"] == 2
    assert by_id["massivefold_freeze_ready_review_packet"]["blocked_count"] == 0
    assert by_id["massivefold_freeze_ready_review_packet"]["total_count"] == 2
    assert "reviews:2/0/2" in by_id["massivefold_freeze_ready_review_packet"]["blockers"]
    assert "artifacts:2/2/2/2" in by_id["massivefold_freeze_ready_review_packet"]["blockers"]
    assert "top5:10" in by_id["massivefold_freeze_ready_review_packet"]["blockers"]
    assert "first:R2350/Model_20_af3_woPaired_seed_1.cif" in by_id[
        "massivefold_freeze_ready_review_packet"
    ]["blockers"]
    assert "proof_eligible:False" in by_id["massivefold_freeze_ready_review_packet"]["blockers"]
    assert "policy:do_not_mark_as_internal_prediction" in by_id[
        "massivefold_freeze_ready_review_packet"
    ]["blockers"]
    assert by_id["massivefold_hold_probe_review_packet"]["status"] == (
        "massivefold_hold_probe_review_packet_ready_external_only"
    )
    assert by_id["massivefold_hold_probe_review_packet"]["ready_count"] == 3
    assert by_id["massivefold_hold_probe_review_packet"]["blocked_count"] == 0
    assert by_id["massivefold_hold_probe_review_packet"]["total_count"] == 3
    assert "reviews:3/0/3" in by_id["massivefold_hold_probe_review_packet"]["blockers"]
    assert "classes:1/1/1/0/0" in by_id["massivefold_hold_probe_review_packet"]["blockers"]
    assert "artifacts:3/3/3/3/alt:1" in by_id["massivefold_hold_probe_review_packet"]["blockers"]
    assert "top5:15" in by_id["massivefold_hold_probe_review_packet"]["blockers"]
    assert "first:R2352/manual_blocked_review" in by_id[
        "massivefold_hold_probe_review_packet"
    ]["blockers"]
    assert "proof_eligible:False" in by_id["massivefold_hold_probe_review_packet"]["blockers"]
    assert "policy:do_not_mark_as_internal_prediction" in by_id[
        "massivefold_hold_probe_review_packet"
    ]["blockers"]
    assert by_id["massivefold_probe_required_targeted_probe_packet"]["status"] == (
        "massivefold_probe_required_targeted_probe_packet_ready_external_only"
    )
    assert by_id["massivefold_probe_required_targeted_probe_packet"]["ready_count"] == 3
    assert by_id["massivefold_probe_required_targeted_probe_packet"]["blocked_count"] == 0
    assert by_id["massivefold_probe_required_targeted_probe_packet"]["total_count"] == 3
    assert "probes:3/0/3" in by_id["massivefold_probe_required_targeted_probe_packet"]["blockers"]
    assert "pass_watch_fail:2/1/0" in by_id[
        "massivefold_probe_required_targeted_probe_packet"
    ]["blockers"]
    assert "recommend:2/1/0" in by_id[
        "massivefold_probe_required_targeted_probe_packet"
    ]["blockers"]
    assert "rna_protein:1/2" in by_id[
        "massivefold_probe_required_targeted_probe_packet"
    ]["blockers"]
    assert "artifacts:3/3/3/3/3/3" in by_id[
        "massivefold_probe_required_targeted_probe_packet"
    ]["blockers"]
    assert "top5:15" in by_id["massivefold_probe_required_targeted_probe_packet"]["blockers"]
    assert "first:H1311/probe_pass_model1_retained_clear" in by_id[
        "massivefold_probe_required_targeted_probe_packet"
    ]["blockers"]
    assert "margin:0.75" in by_id["massivefold_probe_required_targeted_probe_packet"]["blockers"]
    assert "proof_eligible:False" in by_id[
        "massivefold_probe_required_targeted_probe_packet"
    ]["blockers"]
    assert "policy:do_not_mark_as_internal_prediction" in by_id[
        "massivefold_probe_required_targeted_probe_packet"
    ]["blockers"]
    assert by_id["massivefold_post_probe_selector_decision_packet"]["status"] == (
        "massivefold_post_probe_selector_decision_packet_ready_external_only"
    )
    assert by_id["massivefold_post_probe_selector_decision_packet"]["ready_count"] == 5
    assert by_id["massivefold_post_probe_selector_decision_packet"]["blocked_count"] == 0
    assert by_id["massivefold_post_probe_selector_decision_packet"]["total_count"] == 5
    assert "decisions:5/0/5" in by_id[
        "massivefold_post_probe_selector_decision_packet"
    ]["blockers"]
    assert "freeze_watch_manual:2/2/1" in by_id[
        "massivefold_post_probe_selector_decision_packet"
    ]["blockers"]
    assert "freeze_existing_probe:1/1" in by_id[
        "massivefold_post_probe_selector_decision_packet"
    ]["blockers"]
    assert "watch_probe_interface:1/1" in by_id[
        "massivefold_post_probe_selector_decision_packet"
    ]["blockers"]
    assert "manual_probe_manual:0/1" in by_id[
        "massivefold_post_probe_selector_decision_packet"
    ]["blockers"]
    assert "rna_protein:2/3" in by_id[
        "massivefold_post_probe_selector_decision_packet"
    ]["blockers"]
    assert "artifacts:5/5/5/5/alt:1" in by_id[
        "massivefold_post_probe_selector_decision_packet"
    ]["blockers"]
    assert "first:R2352/manual_block" in by_id[
        "massivefold_post_probe_selector_decision_packet"
    ]["blockers"]
    assert "proof_eligible:False" in by_id[
        "massivefold_post_probe_selector_decision_packet"
    ]["blockers"]
    assert "policy:do_not_mark_as_internal_prediction" in by_id[
        "massivefold_post_probe_selector_decision_packet"
    ]["blockers"]
    assert by_id["massivefold_watch_manual_action_packet"]["status"] == (
        "massivefold_watch_manual_action_packet_ready_external_only"
    )
    assert by_id["massivefold_watch_manual_action_packet"]["ready_count"] == 5
    assert by_id["massivefold_watch_manual_action_packet"]["blocked_count"] == 0
    assert by_id["massivefold_watch_manual_action_packet"]["total_count"] == 5
    assert "actions:5/0/5" in by_id["massivefold_watch_manual_action_packet"]["blockers"]
    assert "classes:1/1/3" in by_id["massivefold_watch_manual_action_packet"]["blockers"]
    assert "priority:2/3" in by_id["massivefold_watch_manual_action_packet"]["blockers"]
    assert "rna_protein:2/3" in by_id["massivefold_watch_manual_action_packet"]["blockers"]
    assert "artifacts:5/5/5/5/alt:1" in by_id[
        "massivefold_watch_manual_action_packet"
    ]["blockers"]
    assert "first:R2352/manual_alternate_review" in by_id[
        "massivefold_watch_manual_action_packet"
    ]["blockers"]
    assert "proof_eligible:False" in by_id["massivefold_watch_manual_action_packet"]["blockers"]
    assert "policy:do_not_mark_as_internal_prediction" in by_id[
        "massivefold_watch_manual_action_packet"
    ]["blockers"]
    assert by_id["massivefold_freeze_candidate_format_preflight"]["status"] == (
        "massivefold_freeze_candidate_format_preflight_ready_external_only"
    )
    assert by_id["massivefold_freeze_candidate_format_preflight"]["ready_count"] == 10
    assert by_id["massivefold_freeze_candidate_format_preflight"]["blocked_count"] == 0
    assert by_id["massivefold_freeze_candidate_format_preflight"]["total_count"] == 10
    assert "preflight:10/0/10" in by_id["massivefold_freeze_candidate_format_preflight"]["blockers"]
    assert "freeze_existing_probe:2/8" in by_id[
        "massivefold_freeze_candidate_format_preflight"
    ]["blockers"]
    assert "rna_protein:4/6" in by_id["massivefold_freeze_candidate_format_preflight"]["blockers"]
    assert "selected_pdb_cif:6/4" in by_id[
        "massivefold_freeze_candidate_format_preflight"
    ]["blockers"]
    assert "packaged_pdb_cif:0/10" in by_id[
        "massivefold_freeze_candidate_format_preflight"
    ]["blockers"]
    assert "checks:10/10/10/10/10/10/10" in by_id[
        "massivefold_freeze_candidate_format_preflight"
    ]["blockers"]
    assert "first:H2319" in by_id["massivefold_freeze_candidate_format_preflight"]["blockers"]
    assert "proof_eligible:False" in by_id[
        "massivefold_freeze_candidate_format_preflight"
    ]["blockers"]
    assert "policy:do_not_mark_as_internal_prediction" in by_id[
        "massivefold_freeze_candidate_format_preflight"
    ]["blockers"]
    assert by_id["massivefold_freeze_candidate_escrow"]["status"] == (
        "massivefold_freeze_candidate_escrow_ready_external_only"
    )
    assert by_id["massivefold_freeze_candidate_escrow"]["ready_count"] == 10
    assert by_id["massivefold_freeze_candidate_escrow"]["blocked_count"] == 0
    assert by_id["massivefold_freeze_candidate_escrow"]["total_count"] == 10
    assert "escrow:10/0/10" in by_id["massivefold_freeze_candidate_escrow"]["blockers"]
    assert "sha_model_top5:10/10" in by_id["massivefold_freeze_candidate_escrow"]["blockers"]
    assert "artifacts:10/10/10/10" in by_id["massivefold_freeze_candidate_escrow"]["blockers"]
    assert "freeze_existing_probe:2/8" in by_id["massivefold_freeze_candidate_escrow"]["blockers"]
    assert "rna_protein:4/6" in by_id["massivefold_freeze_candidate_escrow"]["blockers"]
    assert "native_proof_author:10/0/0" in by_id["massivefold_freeze_candidate_escrow"]["blockers"]
    assert "first:H2319" in by_id["massivefold_freeze_candidate_escrow"]["blockers"]
    assert "blocked:-" in by_id["massivefold_freeze_candidate_escrow"]["blockers"]
    assert by_id["massivefold_freeze_candidate_protein_library"]["status"] == (
        "massivefold_freeze_candidate_protein_library_ready_external_only"
    )
    assert by_id["massivefold_freeze_candidate_protein_library"]["ready_count"] == 10
    assert by_id["massivefold_freeze_candidate_protein_library"]["blocked_count"] == 0
    assert by_id["massivefold_freeze_candidate_protein_library"]["total_count"] == 10
    assert "library:10/0/10" in by_id["massivefold_freeze_candidate_protein_library"]["blockers"]
    assert "objects:10/0/10" in by_id["massivefold_freeze_candidate_protein_library"]["blockers"]
    assert "links:10/10/10/10/10" in by_id["massivefold_freeze_candidate_protein_library"]["blockers"]
    assert "sha_model_top5:10/10" in by_id["massivefold_freeze_candidate_protein_library"]["blockers"]
    assert "name_sources:5/10" in by_id["massivefold_freeze_candidate_protein_library"]["blockers"]
    assert "rna_protein:4/6" in by_id["massivefold_freeze_candidate_protein_library"]["blockers"]
    assert "proof_author:0/0" in by_id["massivefold_freeze_candidate_protein_library"]["blockers"]
    assert "blocked:-" in by_id["massivefold_freeze_candidate_protein_library"]["blockers"]
    assert by_id["capri_round65_readiness"]["status"] == "deferred_pi_required"
    assert by_id["capri_round65_readiness"]["ready_count"] == 0
    assert by_id["capri_round65_readiness"]["blocked_count"] == 0
    assert by_id["capri_round65_readiness"]["total_count"] == 13
    assert "not_active_scope" in by_id["capri_round65_readiness"]["blockers"]
    assert "operator_not_pi" in by_id["capri_round65_readiness"]["blockers"]
    assert by_id["capri_round65_format_preflight"]["status"] == "deferred_pi_required"
    assert by_id["capri_round65_format_preflight"]["ready_count"] == 0
    assert by_id["capri_round65_format_preflight"]["blocked_count"] == 0
    assert by_id["capri_round65_format_preflight"]["total_count"] == 13
    assert "not_active_scope" in by_id["capri_round65_format_preflight"]["blockers"]
    assert "capri:deferred_pi_required" in by_id["capri_round65_format_preflight"]["blockers"]
    assert by_id["historical_seed_no_leak_provenance_dossiers"]["status"] == (
        "operator_provenance_review_required"
    )
    assert by_id["historical_seed_no_leak_provenance_dossiers"]["blocked_count"] == 15
    assert "current_false:15" in by_id["historical_seed_no_leak_provenance_dossiers"]["blockers"]
    assert "open_fields:150" in by_id["historical_seed_no_leak_provenance_dossiers"]["blockers"]
    assert by_id["historical_seed_no_leak_gap_repair_plan"]["status"] == "no_leak_gap_repair_required"
    assert by_id["historical_seed_no_leak_gap_repair_plan"]["ready_count"] == 0
    assert by_id["historical_seed_no_leak_gap_repair_plan"]["blocked_count"] == 15
    assert "fields:150" in by_id["historical_seed_no_leak_gap_repair_plan"]["blockers"]
    assert "operator_required:150" in by_id["historical_seed_no_leak_gap_repair_plan"]["blockers"]
    assert "weak:30" in by_id["historical_seed_no_leak_gap_repair_plan"]["blockers"]
    assert "authoritative:0" in by_id["historical_seed_no_leak_gap_repair_plan"]["blockers"]
    assert "mtime_risk:15" in by_id["historical_seed_no_leak_gap_repair_plan"]["blockers"]
    assert by_id["historical_seed_ablation_candidate_manifests"]["status"] == (
        "operator_ablation_review_required"
    )
    assert by_id["historical_seed_ablation_candidate_manifests"]["blocked_count"] == 15
    assert "baseline_candidates:1" in by_id["historical_seed_ablation_candidate_manifests"]["blockers"]
    assert "layer_gaps:14" in by_id["historical_seed_ablation_candidate_manifests"]["blockers"]
    assert by_id["historical_seed_ablation_gap_repair_plan"]["status"] == "ablation_gap_repair_required"
    assert by_id["historical_seed_ablation_gap_repair_plan"]["ready_count"] == 1
    assert by_id["historical_seed_ablation_gap_repair_plan"]["blocked_count"] == 14
    assert "real:1" in by_id["historical_seed_ablation_gap_repair_plan"]["blockers"]
    assert "missing_real:19" in by_id["historical_seed_ablation_gap_repair_plan"]["blockers"]
    assert "top5_decoys:60" in by_id["historical_seed_ablation_gap_repair_plan"]["blockers"]
    assert "top5_copy:15" in by_id["historical_seed_ablation_gap_repair_plan"]["blockers"]
    assert by_id["historical_seed_top5_candidate_pools"]["status"] == "top5_candidate_pool_ready_for_review"
    assert by_id["historical_seed_top5_candidate_pools"]["ready_count"] == 15
    assert "models:75" in by_id["historical_seed_top5_candidate_pools"]["blockers"]
    assert "complete_top5:15" in by_id["historical_seed_top5_candidate_pools"]["blockers"]
    assert by_id["historical_seed_internal_score_candidates"]["status"] == (
        "internal_score_candidates_ready_for_review"
    )
    assert by_id["historical_seed_internal_score_candidates"]["ready_count"] == 15
    assert by_id["historical_seed_internal_score_candidates"]["blocked_count"] == 0
    assert "models:76" in by_id["historical_seed_internal_score_candidates"]["blockers"]
    assert "scored:76" in by_id["historical_seed_internal_score_candidates"]["blockers"]
    assert "selected_scores:15" in by_id["historical_seed_internal_score_candidates"]["blockers"]
    assert by_id["historical_seed_native_oracle_metric_candidates"]["status"] == (
        "native_oracle_metric_candidates_ready_for_review"
    )
    assert by_id["historical_seed_native_oracle_metric_candidates"]["ready_count"] == 15
    assert by_id["historical_seed_native_oracle_metric_candidates"]["blocked_count"] == 0
    assert "models:76" in by_id["historical_seed_native_oracle_metric_candidates"]["blockers"]
    assert "metric_ready:76" in by_id["historical_seed_native_oracle_metric_candidates"]["blockers"]
    assert "best_native:15" in by_id["historical_seed_native_oracle_metric_candidates"]["blockers"]
    assert by_id["historical_seed_calibration_candidate_ledgers"]["status"] == (
        "operator_calibration_review_required"
    )
    assert by_id["historical_seed_calibration_candidate_ledgers"]["blocked_count"] == 15
    assert "models:76" in by_id["historical_seed_calibration_candidate_ledgers"]["blockers"]
    assert "top5_ready:15" in by_id["historical_seed_calibration_candidate_ledgers"]["blockers"]
    assert "native_metrics:76" in by_id["historical_seed_calibration_candidate_ledgers"]["blockers"]
    assert "internal_scores:76" in by_id["historical_seed_calibration_candidate_ledgers"]["blockers"]
    assert "open_fields:90" in by_id["historical_seed_calibration_candidate_ledgers"]["blockers"]
    assert by_id["historical_seed_calibration_field_candidates"]["status"] == (
        "calibration_field_candidates_ready_for_operator_apply"
    )
    assert by_id["historical_seed_calibration_field_candidates"]["ready_count"] == 15
    assert by_id["historical_seed_calibration_field_candidates"]["blocked_count"] == 0
    assert "fields:90" in by_id["historical_seed_calibration_field_candidates"]["blockers"]
    assert "proposed:90" in by_id["historical_seed_calibration_field_candidates"]["blockers"]
    assert "conflicts:0" in by_id["historical_seed_calibration_field_candidates"]["blockers"]
    assert "blocked_fields:0" in by_id["historical_seed_calibration_field_candidates"]["blockers"]
    assert by_id["historical_seed_clearance_fill_candidate_packet"]["status"] == (
        "operator_provenance_required_with_field_candidates"
    )
    assert by_id["historical_seed_clearance_fill_candidate_packet"]["ready_count"] == 15
    assert by_id["historical_seed_clearance_fill_candidate_packet"]["blocked_count"] == 15
    assert "fields:255" in by_id["historical_seed_clearance_fill_candidate_packet"]["blockers"]
    assert "proposed:91" in by_id["historical_seed_clearance_fill_candidate_packet"]["blockers"]
    assert "operator_required:150" in by_id["historical_seed_clearance_fill_candidate_packet"]["blockers"]
    assert "blocked_fields:14" in by_id["historical_seed_clearance_fill_candidate_packet"]["blockers"]
    assert "calibration:90" in by_id["historical_seed_clearance_fill_candidate_packet"]["blockers"]
    assert "ablation:1" in by_id["historical_seed_clearance_fill_candidate_packet"]["blockers"]
    assert by_id["historical_seed_clearance_execution_board"]["status"] == "first_row_operator_no_leak_only"
    assert by_id["historical_seed_clearance_execution_board"]["ready_count"] == 1
    assert by_id["historical_seed_clearance_execution_board"]["blocked_count"] == 14
    assert by_id["historical_seed_clearance_execution_board"]["total_count"] == 15
    assert "first:HIST_CHIGNOLIN" in by_id["historical_seed_clearance_execution_board"]["blockers"]
    assert "status:operator_no_leak_only" in by_id["historical_seed_clearance_execution_board"]["blockers"]
    assert "blocked_ablation:14" in by_id["historical_seed_clearance_execution_board"]["blockers"]
    assert by_id["historical_seed_first_clearance_operator_kit"]["status"] == "operator_no_leak_intake_ready"
    assert by_id["historical_seed_first_clearance_operator_kit"]["ready_count"] == 7
    assert by_id["historical_seed_first_clearance_operator_kit"]["blocked_count"] == 10
    assert by_id["historical_seed_first_clearance_operator_kit"]["total_count"] == 17
    assert "target:HIST_CHIGNOLIN" in by_id["historical_seed_first_clearance_operator_kit"]["blockers"]
    assert "preview:waiting_on_operator_no_leak_fields" in (
        by_id["historical_seed_first_clearance_operator_kit"]["blockers"]
    )
    assert "weak:2" in by_id["historical_seed_first_clearance_operator_kit"]["blockers"]
    assert by_id["historical_seed_first_clearance_no_leak_gate"]["status"] == (
        "awaiting_operator_no_leak_values"
    )
    assert by_id["historical_seed_first_clearance_no_leak_gate"]["ready_count"] == 0
    assert by_id["historical_seed_first_clearance_no_leak_gate"]["blocked_count"] == 10
    assert by_id["historical_seed_first_clearance_no_leak_gate"]["total_count"] == 10
    assert "first:no_leak_evidence_ref" in by_id["historical_seed_first_clearance_no_leak_gate"]["blockers"]
    assert "blocker:operator_value_missing" in by_id["historical_seed_first_clearance_no_leak_gate"]["blockers"]
    assert "values_missing:10" in by_id["historical_seed_first_clearance_no_leak_gate"]["blockers"]
    assert "clearance_missing:10" in by_id["historical_seed_first_clearance_no_leak_gate"]["blockers"]
    assert by_id["historical_seed_first_clearance_no_leak_evidence_packet"]["status"] == (
        "awaiting_first_clearance_no_leak_evidence_collection"
    )
    assert by_id["historical_seed_first_clearance_no_leak_evidence_packet"]["ready_count"] == 0
    assert by_id["historical_seed_first_clearance_no_leak_evidence_packet"]["blocked_count"] == 10
    assert by_id["historical_seed_first_clearance_no_leak_evidence_packet"]["total_count"] == 10
    assert "first:no_leak_evidence_ref" in (
        by_id["historical_seed_first_clearance_no_leak_evidence_packet"]["blockers"]
    )
    assert "kind:independent_no_leak_evidence" in (
        by_id["historical_seed_first_clearance_no_leak_evidence_packet"]["blockers"]
    )
    assert "stubs:10" in by_id["historical_seed_first_clearance_no_leak_evidence_packet"]["blockers"]
    assert by_id["historical_seed_first_clearance_no_leak_evidence_review_gate"]["status"] == (
        "awaiting_first_clearance_no_leak_evidence_review"
    )
    assert by_id["historical_seed_first_clearance_no_leak_evidence_review_gate"]["ready_count"] == 0
    assert by_id["historical_seed_first_clearance_no_leak_evidence_review_gate"]["blocked_count"] == 10
    assert by_id["historical_seed_first_clearance_no_leak_evidence_review_gate"]["total_count"] == 10
    assert "first:no_leak_evidence_ref" in (
        by_id["historical_seed_first_clearance_no_leak_evidence_review_gate"]["blockers"]
    )
    assert "blocker:template_operator_value_missing" in (
        by_id["historical_seed_first_clearance_no_leak_evidence_review_gate"]["blockers"]
    )
    assert "template_missing:10" in (
        by_id["historical_seed_first_clearance_no_leak_evidence_review_gate"]["blockers"]
    )
    assert "stub_evidence_missing:10" in (
        by_id["historical_seed_first_clearance_no_leak_evidence_review_gate"]["blockers"]
    )
    assert by_id["historical_seed_first_clearance_no_leak_evidence_sync_plan"]["status"] == (
        "awaiting_first_clearance_no_leak_evidence_review"
    )
    assert by_id["historical_seed_first_clearance_no_leak_evidence_sync_plan"]["ready_count"] == 0
    assert by_id["historical_seed_first_clearance_no_leak_evidence_sync_plan"]["blocked_count"] == 10
    assert by_id["historical_seed_first_clearance_no_leak_evidence_sync_plan"]["total_count"] == 10
    assert "mode:dry_run" in by_id["historical_seed_first_clearance_no_leak_evidence_sync_plan"]["blockers"]
    assert "review:awaiting_first_clearance_no_leak_evidence_review" in (
        by_id["historical_seed_first_clearance_no_leak_evidence_sync_plan"]["blockers"]
    )
    assert "blocker:template_operator_value_missing" in (
        by_id["historical_seed_first_clearance_no_leak_evidence_sync_plan"]["blockers"]
    )
    assert by_id["historical_seed_first_clearance_closure_board"]["status"] == (
        "awaiting_first_clearance_no_leak_closure"
    )
    assert by_id["historical_seed_first_clearance_closure_board"]["ready_count"] == 1
    assert by_id["historical_seed_first_clearance_closure_board"]["blocked_count"] == 6
    assert by_id["historical_seed_first_clearance_closure_board"]["total_count"] == 7
    assert "first:evidence_packet" in by_id["historical_seed_first_clearance_closure_board"]["blockers"]
    assert "status:awaiting_first_clearance_no_leak_evidence_collection" in (
        by_id["historical_seed_first_clearance_closure_board"]["blockers"]
    )
    assert "blocker:operator_value_missing" in (
        by_id["historical_seed_first_clearance_closure_board"]["blockers"]
    )
    assert "kit:operator_no_leak_intake_ready" in (
        by_id["historical_seed_first_clearance_closure_board"]["blockers"]
    )
    assert by_id["competitive_floor_batch"]["status"] == "ready_for_fill"
    assert by_id["competitive_floor_row_fill_status"]["status"] == "awaiting_fill"
    assert by_id["competitive_floor_row_fill_worklist"]["status"] == "open_actions"
    assert by_id["competitive_floor_evidence_import"]["status"] == "awaiting_import"
    assert by_id["competitive_floor_evidence_round"]["status"] == "awaiting_import"
    assert by_id["competitive_floor_unlock_priority"]["status"] == "identity_unlock_required"
    assert by_id["competitive_floor_identity_unlock_kit"]["status"] == "awaiting_identity"
    assert by_id["competitive_floor_identity_unlock_round"]["status"] == "awaiting_identity"
    assert by_id["competitive_floor_identity_intake_bundle"]["status"] == "awaiting_identity"
    assert by_id["competitive_floor_identity_intake_sync"]["status"] == "awaiting_intake"
    assert by_id["competitive_floor_identity_candidate_packet"]["status"] == "awaiting_candidate_sources"
    assert by_id["competitive_floor_unblock_map"]["status"] == "awaiting_candidate_source_repair"
    assert by_id["competitive_floor_unblock_map"]["ready_count"] == 0
    assert by_id["competitive_floor_unblock_map"]["blocked_count"] == 15
    assert "phase_open:15/15/15/15/15" in by_id["competitive_floor_unblock_map"]["blockers"]
    assert "blocking_fields:285" in by_id["competitive_floor_unblock_map"]["blockers"]
    assert by_id["competitive_floor_identity_source_repair_plan"]["status"] == "awaiting_target_identity"
    assert by_id["competitive_floor_target_identity_discovery"]["status"] == "review_required"
    assert by_id["competitive_floor_target_identity_clearance_queue"]["status"] == "awaiting_target_identity_clearance"
    assert by_id["competitive_floor_target_identity_clearance_workorder"]["status"] == "awaiting_native_or_provenance"
    assert by_id["competitive_floor_target_identity_clearance_operator_intake"]["status"] == "awaiting_input"
    assert by_id["competitive_floor_target_identity_clearance_operator_intake"]["blocked_count"] == 3
    assert "awaiting:3" in by_id["competitive_floor_target_identity_clearance_operator_intake"]["blockers"]
    assert by_id["competitive_floor_target_identity_clearance_native_candidates"]["status"] == "review_required"
    assert by_id["competitive_floor_target_identity_clearance_native_candidates"]["ready_count"] == 1
    assert by_id["competitive_floor_target_identity_clearance_native_candidates"]["blocked_count"] == 3
    assert "collisions:2" in by_id["competitive_floor_target_identity_clearance_native_candidates"]["blockers"]
    assert by_id["competitive_floor_target_identity_clearance_adjudication"]["status"] == "blocked_candidate_risk"
    assert by_id["competitive_floor_target_identity_clearance_adjudication"]["blocked_count"] == 3
    assert "replacement:2" in by_id["competitive_floor_target_identity_clearance_adjudication"]["blockers"]
    assert by_id["competitive_floor_target_identity_clearance_replacement_queue"]["status"] == "blocked_replacement_candidates"
    assert by_id["competitive_floor_target_identity_clearance_replacement_queue"]["blocked_count"] == 8
    assert "replacement_targets:2" in by_id["competitive_floor_target_identity_clearance_replacement_queue"]["blockers"]
    assert by_id["competitive_floor_target_identity_clearance_replacement_source_repair"]["status"] == "awaiting_sequence"
    assert by_id["competitive_floor_target_identity_clearance_replacement_source_repair"]["ready_count"] == 2
    assert by_id["competitive_floor_target_identity_clearance_replacement_source_repair"]["blocked_count"] == 2
    assert "ready_prediction:1" in by_id["competitive_floor_target_identity_clearance_replacement_source_repair"]["blockers"]
    assert "cancelled:1" in by_id["competitive_floor_target_identity_clearance_replacement_source_repair"]["blockers"]
    assert by_id["competitive_floor_target_identity_clearance_replacement_scorecard"]["status"] == "replacement_scorecard_blocked"
    assert by_id["competitive_floor_target_identity_clearance_replacement_scorecard"]["ready_count"] == 1
    assert by_id["competitive_floor_target_identity_clearance_replacement_scorecard"]["blocked_count"] == 3
    assert "scorecard_json:1" in by_id["competitive_floor_target_identity_clearance_replacement_scorecard"]["blockers"]
    assert by_id["competitive_floor_target_identity_clearance_replacement_workorder"]["status"] == (
        "partial_replacement_workorders_ready_for_operator_intake"
    )
    assert by_id["competitive_floor_target_identity_clearance_replacement_workorder"]["ready_count"] == 1
    assert by_id["competitive_floor_target_identity_clearance_replacement_workorder"]["blocked_count"] == 1
    assert "duplicate:1" in by_id["competitive_floor_target_identity_clearance_replacement_workorder"]["blockers"]
    assert by_id["competitive_floor_native_dropzone_registry"]["status"] == "awaiting_native_files"
    assert by_id["competitive_floor_native_dropzone_registry"]["ready_count"] == 0
    assert by_id["competitive_floor_native_dropzone_registry"]["blocked_count"] == 4
    assert by_id["competitive_floor_native_dropzone_registry"]["total_count"] == 4
    assert "primary/replacement:3/1" in by_id["competitive_floor_native_dropzone_registry"]["blockers"]
    assert "readmes/native:4/0" in by_id["competitive_floor_native_dropzone_registry"]["blockers"]
    assert "proof_author:0/0" in by_id["competitive_floor_native_dropzone_registry"]["blockers"]
    assert by_id["competitive_floor_target_identity_clearance_replacement_workorder_audit"]["status"] == "blocked"
    assert by_id["competitive_floor_target_identity_clearance_replacement_workorder_audit"]["blocked_count"] == 2
    assert "prediction:2" in by_id["competitive_floor_target_identity_clearance_replacement_workorder_audit"]["blockers"]
    assert "waiting:2" in by_id["competitive_floor_target_identity_clearance_replacement_workorder_audit"]["blockers"]
    assert by_id["competitive_floor_target_identity_clearance_replacement_pickup"]["status"] == "open_actions"
    assert by_id["competitive_floor_target_identity_clearance_replacement_pickup"]["blocked_count"] == 2
    assert "selected:1" in by_id["competitive_floor_target_identity_clearance_replacement_pickup"]["blockers"]
    assert "operator_actions:4" in by_id["competitive_floor_target_identity_clearance_replacement_pickup"]["blockers"]
    assert by_id["competitive_floor_target_identity_clearance_replacement_duplicate_resolution"]["status"] == (
        "operator_decision_required"
    )
    assert by_id["competitive_floor_target_identity_clearance_replacement_duplicate_resolution"]["ready_count"] == 0
    assert by_id["competitive_floor_target_identity_clearance_replacement_duplicate_resolution"]["blocked_count"] == 4
    assert (
        "duplicate_ready:1"
        in by_id["competitive_floor_target_identity_clearance_replacement_duplicate_resolution"]["blockers"]
    )
    assert (
        "current_collision:2"
        in by_id["competitive_floor_target_identity_clearance_replacement_duplicate_resolution"]["blockers"]
    )
    assert by_id["competitive_floor_target_identity_clearance_replacement_decision_bundle"]["status"] == (
        "open_operator_decision"
    )
    assert by_id["competitive_floor_target_identity_clearance_replacement_decision_bundle"]["ready_count"] == 0
    assert by_id["competitive_floor_target_identity_clearance_replacement_decision_bundle"]["blocked_count"] == 1
    assert (
        "new_unique_templates:1"
        in by_id["competitive_floor_target_identity_clearance_replacement_decision_bundle"]["blockers"]
    )
    assert (
        "duplicate_exception_templates:1"
        in by_id["competitive_floor_target_identity_clearance_replacement_decision_bundle"]["blockers"]
    )
    assert by_id["competitive_floor_target_identity_clearance_replacement_decision_preflight"]["status"] == (
        "awaiting_operator_decision"
    )
    assert by_id["competitive_floor_target_identity_clearance_replacement_decision_preflight"]["ready_count"] == 0
    assert by_id["competitive_floor_target_identity_clearance_replacement_decision_preflight"]["blocked_count"] == 1
    assert (
        "new_unique_blockers:1"
        in by_id["competitive_floor_target_identity_clearance_replacement_decision_preflight"]["blockers"]
    )
    assert (
        "duplicate_exception_blockers:1"
        in by_id["competitive_floor_target_identity_clearance_replacement_decision_preflight"]["blockers"]
    )
    assert by_id["competitive_floor_target_identity_clearance_manifest_sync"]["status"] == "awaiting_provenance"
    assert by_id["competitive_floor_target_identity_clearance_manifest_sync"]["blocked_count"] == 3
    assert by_id["competitive_floor_target_identity_clearance_workorder_audit"]["status"] == "blocked"
    assert "prediction_protein_atoms:3" in by_id["competitive_floor_target_identity_clearance_workorder_audit"]["blockers"]
    assert "prediction_coordinate_valid:3" in by_id["competitive_floor_target_identity_clearance_workorder_audit"]["blockers"]
    assert (
        "identity_discovery_blocked:3"
        in by_id["competitive_floor_target_identity_clearance_workorder_audit"]["blockers"]
    )
    assert by_id["competitive_floor_target_identity_metric_runway"]["status"] == (
        "casp17_competitive_floor_target_identity_metric_runway_blocked_awaiting_native_provenance"
    )
    assert by_id["competitive_floor_target_identity_metric_runway"]["ready_count"] == 0
    assert by_id["competitive_floor_target_identity_metric_runway"]["blocked_count"] == 3
    assert by_id["competitive_floor_target_identity_metric_runway"]["total_count"] == 3
    assert "targets:0/3/3" in by_id["competitive_floor_target_identity_metric_runway"]["blockers"]
    assert "families:3/0" in by_id["competitive_floor_target_identity_metric_runway"]["blockers"]
    assert "metric_requirements:27" in by_id["competitive_floor_target_identity_metric_runway"]["blockers"]
    assert "prediction_native_provenance_evidence:3/0/0/0" in by_id[
        "competitive_floor_target_identity_metric_runway"
    ]["blockers"]
    assert "native_candidates:4/1/5" in by_id["competitive_floor_target_identity_metric_runway"]["blockers"]
    assert "proof_author:0/0" in by_id["competitive_floor_target_identity_metric_runway"]["blockers"]
    assert by_id["competitive_floor_native_provenance_operator_packet"]["status"] == (
        "casp17_competitive_floor_native_provenance_operator_packet_open_actions"
    )
    assert by_id["competitive_floor_native_provenance_operator_packet"]["ready_count"] == 0
    assert by_id["competitive_floor_native_provenance_operator_packet"]["blocked_count"] == 3
    assert by_id["competitive_floor_native_provenance_operator_packet"]["total_count"] == 3
    assert "targets:3/0/3" in by_id["competitive_floor_native_provenance_operator_packet"]["blockers"]
    assert "actions:12/12" in by_id["competitive_floor_native_provenance_operator_packet"]["blockers"]
    assert "lanes:3/3/3/3" in by_id["competitive_floor_native_provenance_operator_packet"]["blockers"]
    assert "metric_requirements:27" in by_id["competitive_floor_native_provenance_operator_packet"]["blockers"]
    assert "prediction_native_provenance_evidence:3/0/0/0" in by_id[
        "competitive_floor_native_provenance_operator_packet"
    ]["blockers"]
    assert "native_candidates:4/1/5" in by_id["competitive_floor_native_provenance_operator_packet"]["blockers"]
    assert "proof_author:0/0" in by_id["competitive_floor_native_provenance_operator_packet"]["blockers"]
    assert by_id["competitive_floor_native_provenance_operator_packet_completion_audit"]["status"] == (
        "casp17_competitive_floor_native_provenance_operator_packet_completion_audit_pass"
    )
    assert by_id["competitive_floor_native_provenance_operator_packet_completion_audit"]["ready_count"] == 3
    assert by_id["competitive_floor_native_provenance_operator_packet_completion_audit"]["blocked_count"] == 0
    assert by_id["competitive_floor_native_provenance_operator_packet_completion_audit"]["total_count"] == 3
    assert "targets:3/0/3" in by_id[
        "competitive_floor_native_provenance_operator_packet_completion_audit"
    ]["blockers"]
    assert "packet_files:3/3/3/3/3" in by_id[
        "competitive_floor_native_provenance_operator_packet_completion_audit"
    ]["blockers"]
    assert "action_rows:12/12/mismatch:0" in by_id[
        "competitive_floor_native_provenance_operator_packet_completion_audit"
    ]["blockers"]
    assert "native_candidates:5/5/mismatch:0" in by_id[
        "competitive_floor_native_provenance_operator_packet_completion_audit"
    ]["blockers"]
    assert "inputs:3/3/3/0/3/3/3/3" in by_id[
        "competitive_floor_native_provenance_operator_packet_completion_audit"
    ]["blockers"]
    assert "coordinate_copies:0/0" in by_id[
        "competitive_floor_native_provenance_operator_packet_completion_audit"
    ]["blockers"]
    assert "proof_author:0/0" in by_id[
        "competitive_floor_native_provenance_operator_packet_completion_audit"
    ]["blockers"]
    assert by_id["competitive_floor_native_provenance_metric_unlock_bridge"]["status"] == (
        "casp17_competitive_floor_native_provenance_metric_unlock_bridge_blocked_awaiting_operator_values"
    )
    assert by_id["competitive_floor_native_provenance_metric_unlock_bridge"]["ready_count"] == 0
    assert by_id["competitive_floor_native_provenance_metric_unlock_bridge"]["blocked_count"] == 3
    assert by_id["competitive_floor_native_provenance_metric_unlock_bridge"]["total_count"] == 3
    assert "targets:0/3/3" in by_id["competitive_floor_native_provenance_metric_unlock_bridge"]["blockers"]
    assert "packet/workorder/runway:3/0/0" in by_id[
        "competitive_floor_native_provenance_metric_unlock_bridge"
    ]["blockers"]
    assert "metric_requirements:27" in by_id[
        "competitive_floor_native_provenance_metric_unlock_bridge"
    ]["blockers"]
    assert "inputs:3/3/3/0/3/3/3/3" in by_id[
        "competitive_floor_native_provenance_metric_unlock_bridge"
    ]["blockers"]
    assert "actions:3/3/3/3/12" in by_id[
        "competitive_floor_native_provenance_metric_unlock_bridge"
    ]["blockers"]
    assert "native_candidates:4/1/5" in by_id[
        "competitive_floor_native_provenance_metric_unlock_bridge"
    ]["blockers"]
    assert "provenance_evidence_identity:0/0/0" in by_id[
        "competitive_floor_native_provenance_metric_unlock_bridge"
    ]["blockers"]
    assert "proof_author:0/0" in by_id[
        "competitive_floor_native_provenance_metric_unlock_bridge"
    ]["blockers"]
    assert by_id["competitive_floor_first_native_provenance_unlock_kit"]["status"] == (
        "casp17_competitive_floor_first_native_provenance_unlock_kit_ready_for_operator_fill"
    )
    assert by_id["competitive_floor_first_native_provenance_unlock_kit"]["ready_count"] == 1
    assert by_id["competitive_floor_first_native_provenance_unlock_kit"]["blocked_count"] == 0
    assert by_id["competitive_floor_first_native_provenance_unlock_kit"]["total_count"] == 1
    assert "target:H1319" in by_id["competitive_floor_first_native_provenance_unlock_kit"]["blockers"]
    assert "fields:13" in by_id["competitive_floor_first_native_provenance_unlock_kit"]["blockers"]
    assert "actions:4" in by_id["competitive_floor_first_native_provenance_unlock_kit"]["blockers"]
    assert "bundle_actions:4" in by_id["competitive_floor_first_native_provenance_unlock_kit"]["blockers"]
    assert "packet_pass:True" in by_id["competitive_floor_first_native_provenance_unlock_kit"]["blockers"]
    assert "metric_ready:False" in by_id["competitive_floor_first_native_provenance_unlock_kit"]["blockers"]
    assert "workorder_pass:False" in by_id["competitive_floor_first_native_provenance_unlock_kit"]["blockers"]
    assert "inputs:1/1/1/0/1/1/1/1" in by_id[
        "competitive_floor_first_native_provenance_unlock_kit"
    ]["blockers"]
    assert "provenance_evidence_identity:0/0/0" in by_id[
        "competitive_floor_first_native_provenance_unlock_kit"
    ]["blockers"]
    assert "proof_author:0/0" in by_id["competitive_floor_first_native_provenance_unlock_kit"]["blockers"]
    assert "coordinate_copies:0" in by_id["competitive_floor_first_native_provenance_unlock_kit"]["blockers"]
    assert by_id["competitive_floor_batch_native_provenance_unlock_kit"]["status"] == (
        "casp17_competitive_floor_batch_native_provenance_unlock_kit_ready_for_operator_fill"
    )
    assert by_id["competitive_floor_batch_native_provenance_unlock_kit"]["ready_count"] == 3
    assert by_id["competitive_floor_batch_native_provenance_unlock_kit"]["blocked_count"] == 0
    assert by_id["competitive_floor_batch_native_provenance_unlock_kit"]["total_count"] == 3
    assert "targets:3/0/3" in by_id["competitive_floor_batch_native_provenance_unlock_kit"]["blockers"]
    assert "target_ids:H1319,H1321,H2324" in by_id[
        "competitive_floor_batch_native_provenance_unlock_kit"
    ]["blockers"]
    assert "fields:13/39" in by_id["competitive_floor_batch_native_provenance_unlock_kit"]["blockers"]
    assert "actions:12/12" in by_id["competitive_floor_batch_native_provenance_unlock_kit"]["blockers"]
    assert "packet/workorder/runway:3/0/0" in by_id[
        "competitive_floor_batch_native_provenance_unlock_kit"
    ]["blockers"]
    assert "inputs:3/3/3/0/3/3/3/3" in by_id[
        "competitive_floor_batch_native_provenance_unlock_kit"
    ]["blockers"]
    assert "provenance_evidence_identity:0/0/0" in by_id[
        "competitive_floor_batch_native_provenance_unlock_kit"
    ]["blockers"]
    assert "proof_author:0/0" in by_id["competitive_floor_batch_native_provenance_unlock_kit"]["blockers"]
    assert "coordinate_copies:0" in by_id["competitive_floor_batch_native_provenance_unlock_kit"]["blockers"]
    assert by_id["competitive_floor_batch_native_provenance_unlock_kit_completion_audit"]["status"] == (
        "casp17_competitive_floor_batch_native_provenance_unlock_kit_completion_audit_pass"
    )
    assert by_id["competitive_floor_batch_native_provenance_unlock_kit_completion_audit"]["ready_count"] == 3
    assert by_id["competitive_floor_batch_native_provenance_unlock_kit_completion_audit"]["blocked_count"] == 0
    assert by_id["competitive_floor_batch_native_provenance_unlock_kit_completion_audit"]["total_count"] == 3
    assert "targets:3/0/3" in by_id[
        "competitive_floor_batch_native_provenance_unlock_kit_completion_audit"
    ]["blockers"]
    assert "batch_files:6/6" in by_id[
        "competitive_floor_batch_native_provenance_unlock_kit_completion_audit"
    ]["blockers"]
    assert "batch_intake:3/3/mismatch:0" in by_id[
        "competitive_floor_batch_native_provenance_unlock_kit_completion_audit"
    ]["blockers"]
    assert "batch_actions:12/12/mismatch:0" in by_id[
        "competitive_floor_batch_native_provenance_unlock_kit_completion_audit"
    ]["blockers"]
    assert "target_files:3/3/3/3/3/3" in by_id[
        "competitive_floor_batch_native_provenance_unlock_kit_completion_audit"
    ]["blockers"]
    assert "target_intake:3/3/mismatch:0" in by_id[
        "competitive_floor_batch_native_provenance_unlock_kit_completion_audit"
    ]["blockers"]
    assert "target_actions:12/12/mismatch:0" in by_id[
        "competitive_floor_batch_native_provenance_unlock_kit_completion_audit"
    ]["blockers"]
    assert "coordinate_copies:0/0" in by_id[
        "competitive_floor_batch_native_provenance_unlock_kit_completion_audit"
    ]["blockers"]
    assert "native_provenance_evidence_identity:0/0/0/0" in by_id[
        "competitive_floor_batch_native_provenance_unlock_kit_completion_audit"
    ]["blockers"]
    assert "proof_author:0/0" in by_id[
        "competitive_floor_batch_native_provenance_unlock_kit_completion_audit"
    ]["blockers"]
    assert by_id["competitive_floor_target_identity_clearance_action_board"]["status"] == "open_actions"
    assert by_id["competitive_floor_target_identity_clearance_action_board"]["blocked_count"] == 12
    assert "native:3" in by_id["competitive_floor_target_identity_clearance_action_board"]["blockers"]
    assert by_id["competitive_floor_target_identity_clearance_action_bundle"]["status"] == "open_actions"
    assert by_id["competitive_floor_target_identity_clearance_action_bundle"]["blocked_count"] == 12
    assert "files:24" in by_id["competitive_floor_target_identity_clearance_action_bundle"]["blockers"]
    assert by_id["competitive_floor_target_identity_clearance_promotion_plan"]["status"] == "blocked_by_audit"
    assert by_id["competitive_floor_target_identity_clearance_promotion_plan"]["blocked_count"] == 3
    assert by_id["competitive_floor_target_identity_clearance_intake_staging"]["status"] == "waiting_on_promoted_manifest"
    assert by_id["competitive_floor_target_identity_clearance_intake_staging"]["ready_count"] == 0
    assert by_id["competitive_floor_target_identity_clearance_candidate_intake_sync"]["status"] == "waiting_on_staged_identity"
    assert by_id["competitive_floor_target_identity_clearance_candidate_intake_sync"]["blocked_count"] == 15
    assert by_id["competitive_floor_target_identity_clearance_cycle"]["status"] == "awaiting_operator_intake"
    assert by_id["competitive_floor_target_identity_clearance_cycle"]["blocked_count"] == 8
    assert by_id["competitive_floor_identity_cycle"]["status"] == "awaiting_intake"
    assert by_id["competitive_floor_file_source_plan"]["status"] == "waiting_on_identity"
    assert by_id["competitive_floor_value_entry_plan"]["status"] == "waiting_on_identity"
    assert by_id["competitive_floor_execution_board"]["status"] == "awaiting_identity"
    assert by_id["competitive_floor_readiness_gate"]["status"] == "awaiting_identity"
    assert by_id["competitive_floor_operator_template"]["status"] == "blocked"
    assert by_id["competitive_floor_operator_preflight"]["status"] == "blocked"
    assert by_id["benchmark_input_inventory"]["status"] == "blocked"
    assert "cleared historical" in by_id["benchmark_input_inventory"]["next_action"]
    assert by_id["historical_identity_seed_inventory"]["status"] == (
        "batch_seed_shape_ready_operator_clearance_required"
    )
    assert by_id["historical_identity_seed_inventory"]["ready_count"] == 15
    assert by_id["historical_identity_seed_inventory"]["blocked_count"] == 15
    assert "monomer_complex:10/7" in by_id["historical_identity_seed_inventory"]["blockers"]
    assert "manifest:15" in by_id["historical_identity_seed_inventory"]["blockers"]
    assert by_id["historical_identity_seed_clearance_workorder"]["status"] == "awaiting_seed_clearance"
    assert by_id["historical_identity_seed_clearance_workorder"]["ready_count"] == 0
    assert by_id["historical_identity_seed_clearance_workorder"]["blocked_count"] == 15
    assert by_id["historical_identity_seed_clearance_workorder"]["total_count"] == 15
    assert "phase_open:0/0/15/15/15" in by_id["historical_identity_seed_clearance_workorder"]["blockers"]
    assert "cleared_manifest:0" in by_id["historical_identity_seed_clearance_workorder"]["blockers"]
    assert "blocking_fields:270" in by_id["historical_identity_seed_clearance_workorder"]["blockers"]
    assert by_id["historical_identity_seed_clearance_action_bundle"]["status"] == "open_actions"
    assert by_id["historical_identity_seed_clearance_action_bundle"]["blocked_count"] == 45
    assert by_id["historical_identity_seed_clearance_action_bundle"]["total_count"] == 45
    assert "targets:15" in by_id["historical_identity_seed_clearance_action_bundle"]["blockers"]
    assert "folders:45" in by_id["historical_identity_seed_clearance_action_bundle"]["blockers"]
    assert "files:90" in by_id["historical_identity_seed_clearance_action_bundle"]["blockers"]
    assert "lanes:0/0/15/15/15" in by_id["historical_identity_seed_clearance_action_bundle"]["blockers"]
    assert by_id["historical_identity_seed_clearance_field_board"]["status"] == "operator_field_fill_required"
    assert by_id["historical_identity_seed_clearance_field_board"]["ready_count"] == 0
    assert by_id["historical_identity_seed_clearance_field_board"]["blocked_count"] == 15
    assert by_id["historical_identity_seed_clearance_field_board"]["total_count"] == 15
    assert "core:15/0" in by_id["historical_identity_seed_clearance_field_board"]["blockers"]
    assert "open_fields:165/90/15/270" in by_id["historical_identity_seed_clearance_field_board"]["blockers"]
    assert "ready:0" in by_id["historical_identity_seed_clearance_field_board"]["blockers"]
    assert by_id["historical_seed_current_target_prefill"]["status"] == "applied"
    assert by_id["historical_seed_current_target_prefill"]["ready_count"] == 15
    assert by_id["historical_seed_current_target_prefill"]["blocked_count"] == 0
    assert by_id["historical_seed_current_target_prefill"]["total_count"] == 15
    assert "mode:apply" in by_id["historical_seed_current_target_prefill"]["blockers"]
    assert "collisions:0" in by_id["historical_seed_current_target_prefill"]["blockers"]
    assert "remaining_open:0" in by_id["historical_seed_current_target_prefill"]["blockers"]
    assert by_id["historical_seed_native_authority_audit"]["status"] == "blocked_native_authority"
    assert by_id["historical_seed_native_authority_audit"]["ready_count"] == 0
    assert by_id["historical_seed_native_authority_audit"]["blocked_count"] == 15
    assert "placeholder:10" in by_id["historical_seed_native_authority_audit"]["blockers"]
    assert "ca_only:10" in by_id["historical_seed_native_authority_audit"]["blockers"]
    assert "local_generated_no_authority:5" in by_id["historical_seed_native_authority_audit"]["blockers"]
    assert "ref_missing:15" in by_id["historical_seed_native_authority_audit"]["blockers"]
    assert by_id["historical_seed_native_replacement_candidates"]["status"] == (
        "partial_native_replacement_candidates_ready"
    )
    assert by_id["historical_seed_native_replacement_candidates"]["ready_count"] == 10
    assert by_id["historical_seed_native_replacement_candidates"]["blocked_count"] == 7
    assert by_id["historical_seed_native_replacement_candidates"]["total_count"] == 17
    assert "review_ready:10" in by_id["historical_seed_native_replacement_candidates"]["blockers"]
    assert "download:0" in by_id["historical_seed_native_replacement_candidates"]["blockers"]
    assert "file_blocked:0" in by_id["historical_seed_native_replacement_candidates"]["blockers"]
    assert "complex_authority:7" in by_id["historical_seed_native_replacement_candidates"]["blockers"]
    assert by_id["historical_seed_complex_source_authority_candidates"]["status"] == (
        "complex_homolog_source_authority_candidates_ready_claim_limited"
    )
    assert by_id["historical_seed_complex_source_authority_candidates"]["ready_count"] == 7
    assert by_id["historical_seed_complex_source_authority_candidates"]["blocked_count"] == 0
    assert by_id["historical_seed_complex_source_authority_candidates"]["total_count"] == 7
    assert "direct:0" in by_id["historical_seed_complex_source_authority_candidates"]["blockers"]
    assert "homolog:7" in by_id["historical_seed_complex_source_authority_candidates"]["blockers"]
    assert "operator_apply:0" in by_id["historical_seed_complex_source_authority_candidates"]["blockers"]
    assert "claim_promotion:0" in by_id["historical_seed_complex_source_authority_candidates"]["blockers"]
    assert by_id["historical_seed_chronology_candidate_board"]["status"] == "operator_evidence_required"
    assert by_id["historical_seed_chronology_candidate_board"]["ready_count"] == 0
    assert by_id["historical_seed_chronology_candidate_board"]["blocked_count"] == 15
    assert by_id["historical_seed_chronology_candidate_board"]["total_count"] == 15
    assert "path_dates:10" in by_id["historical_seed_chronology_candidate_board"]["blockers"]
    assert "mtimes:15" in by_id["historical_seed_chronology_candidate_board"]["blockers"]
    assert "mtime_risk:15" in by_id["historical_seed_chronology_candidate_board"]["blockers"]
    assert by_id["historical_seed_authoritative_chronology_audit"]["status"] == (
        "post_native_prediction_chronology_blocked"
    )
    assert by_id["historical_seed_authoritative_chronology_audit"]["ready_count"] == 0
    assert by_id["historical_seed_authoritative_chronology_audit"]["blocked_count"] == 17
    assert by_id["historical_seed_authoritative_chronology_audit"]["total_count"] == 17
    assert "native_dates:10" in by_id["historical_seed_authoritative_chronology_audit"]["blockers"]
    assert "prediction_dates:10" in by_id["historical_seed_authoritative_chronology_audit"]["blockers"]
    assert "post_native:10" in by_id["historical_seed_authoritative_chronology_audit"]["blockers"]
    assert "evidence_required:7" in by_id["historical_seed_authoritative_chronology_audit"]["blockers"]
    assert by_id["historical_seed_lane_decision_packet"]["status"] == "strict_blind_replacement_required"
    assert by_id["historical_seed_lane_decision_packet"]["ready_count"] == 0
    assert by_id["historical_seed_lane_decision_packet"]["blocked_count"] == 17
    assert by_id["historical_seed_lane_decision_packet"]["total_count"] == 17
    assert "strict_blind:0" in by_id["historical_seed_lane_decision_packet"]["blockers"]
    assert "retrospective:10" in by_id["historical_seed_lane_decision_packet"]["blockers"]
    assert "authority_required:7" in by_id["historical_seed_lane_decision_packet"]["blockers"]
    assert "competitive:0" in by_id["historical_seed_lane_decision_packet"]["blockers"]
    assert "replacement_required:17" in by_id["historical_seed_lane_decision_packet"]["blockers"]
    assert by_id["historical_seed_strict_blind_replacement_queue"]["status"] == (
        "strict_blind_replacement_queue_open"
    )
    assert by_id["historical_seed_strict_blind_replacement_queue"]["ready_count"] == 0
    assert by_id["historical_seed_strict_blind_replacement_queue"]["blocked_count"] == 40
    assert by_id["historical_seed_strict_blind_replacement_queue"]["total_count"] == 40
    assert "slots:40" in by_id["historical_seed_strict_blind_replacement_queue"]["blockers"]
    assert "monomer_complex:25/15" in by_id["historical_seed_strict_blind_replacement_queue"]["blockers"]
    assert "replacement_required:40" in by_id["historical_seed_strict_blind_replacement_queue"]["blockers"]
    assert "current_seed_competitive:0" in by_id["historical_seed_strict_blind_replacement_queue"]["blockers"]
    assert "fields:640" in by_id["historical_seed_strict_blind_replacement_queue"]["blockers"]
    assert by_id["historical_seed_strict_blind_replacement_intake"]["status"] == (
        "awaiting_strict_blind_replacement_intake"
    )
    assert by_id["historical_seed_strict_blind_replacement_intake"]["ready_count"] == 0
    assert by_id["historical_seed_strict_blind_replacement_intake"]["blocked_count"] == 40
    assert by_id["historical_seed_strict_blind_replacement_intake"]["total_count"] == 40
    assert "slots:40" in by_id["historical_seed_strict_blind_replacement_intake"]["blockers"]
    assert "ready:0" in by_id["historical_seed_strict_blind_replacement_intake"]["blockers"]
    assert "awaiting:40" in by_id["historical_seed_strict_blind_replacement_intake"]["blockers"]
    assert "missing:640" in by_id["historical_seed_strict_blind_replacement_intake"]["blockers"]
    assert "fields:640" in by_id["historical_seed_strict_blind_replacement_intake"]["blockers"]
    assert by_id["historical_seed_strict_blind_replacement_evidence_dropzones"]["status"] == (
        "awaiting_strict_blind_evidence_files"
    )
    assert by_id["historical_seed_strict_blind_replacement_evidence_dropzones"]["ready_count"] == 0
    assert by_id["historical_seed_strict_blind_replacement_evidence_dropzones"]["blocked_count"] == 40
    assert by_id["historical_seed_strict_blind_replacement_evidence_dropzones"]["total_count"] == 40
    assert "dropzones:40" in by_id["historical_seed_strict_blind_replacement_evidence_dropzones"]["blockers"]
    assert "files_present:0" in by_id["historical_seed_strict_blind_replacement_evidence_dropzones"]["blockers"]
    assert "files_missing:240" in by_id["historical_seed_strict_blind_replacement_evidence_dropzones"]["blockers"]
    assert "operator_values:400" in by_id["historical_seed_strict_blind_replacement_evidence_dropzones"]["blockers"]
    assert by_id["historical_seed_strict_blind_replacement_evidence_action_board"]["status"] == (
        "awaiting_strict_blind_evidence_actions"
    )
    assert by_id["historical_seed_strict_blind_replacement_evidence_action_board"]["ready_count"] == 0
    assert by_id["historical_seed_strict_blind_replacement_evidence_action_board"]["blocked_count"] == 240
    assert by_id["historical_seed_strict_blind_replacement_evidence_action_board"]["total_count"] == 240
    assert "actions:240" in by_id["historical_seed_strict_blind_replacement_evidence_action_board"]["blockers"]
    assert "open:240" in by_id["historical_seed_strict_blind_replacement_evidence_action_board"]["blockers"]
    assert "missing_by_field:40/40/40/40/40/40" in by_id[
        "historical_seed_strict_blind_replacement_evidence_action_board"
    ]["blockers"]
    assert by_id["historical_seed_strict_blind_replacement_evidence_quality_audit"]["status"] == (
        "awaiting_strict_blind_evidence_quality_files"
    )
    assert by_id["historical_seed_strict_blind_replacement_evidence_quality_audit"]["ready_count"] == 0
    assert by_id["historical_seed_strict_blind_replacement_evidence_quality_audit"]["blocked_count"] == 40
    assert by_id["historical_seed_strict_blind_replacement_evidence_quality_audit"]["total_count"] == 40
    assert "awaiting:40" in by_id["historical_seed_strict_blind_replacement_evidence_quality_audit"]["blockers"]
    assert "files:0/240/240" in by_id["historical_seed_strict_blind_replacement_evidence_quality_audit"]["blockers"]
    assert "pdb_slots:0/0" in by_id["historical_seed_strict_blind_replacement_evidence_quality_audit"]["blockers"]
    assert by_id["historical_seed_strict_blind_replacement_evidence_import_gate"]["status"] == (
        "awaiting_strict_blind_evidence_import"
    )
    assert by_id["historical_seed_strict_blind_replacement_evidence_import_gate"]["ready_count"] == 0
    assert by_id["historical_seed_strict_blind_replacement_evidence_import_gate"]["blocked_count"] == 640
    assert by_id["historical_seed_strict_blind_replacement_evidence_import_gate"]["total_count"] == 640
    assert "mode:dry_run" in by_id["historical_seed_strict_blind_replacement_evidence_import_gate"]["blockers"]
    assert "actions:640" in by_id["historical_seed_strict_blind_replacement_evidence_import_gate"]["blockers"]
    assert "file_operator:240/400" in by_id["historical_seed_strict_blind_replacement_evidence_import_gate"]["blockers"]
    assert "awaiting_file:240" in by_id["historical_seed_strict_blind_replacement_evidence_import_gate"]["blockers"]
    assert "awaiting_operator:400" in by_id["historical_seed_strict_blind_replacement_evidence_import_gate"]["blockers"]
    assert by_id["historical_seed_strict_blind_replacement_operator_value_gate"]["status"] == (
        "awaiting_operator_values"
    )
    assert by_id["historical_seed_strict_blind_replacement_operator_value_gate"]["ready_count"] == 0
    assert by_id["historical_seed_strict_blind_replacement_operator_value_gate"]["blocked_count"] == 400
    assert by_id["historical_seed_strict_blind_replacement_operator_value_gate"]["total_count"] == 400
    assert "mode:dry_run" in by_id["historical_seed_strict_blind_replacement_operator_value_gate"]["blockers"]
    assert "templates:40" in by_id["historical_seed_strict_blind_replacement_operator_value_gate"]["blockers"]
    assert "actions:400" in by_id["historical_seed_strict_blind_replacement_operator_value_gate"]["blockers"]
    assert "awaiting_value:400" in by_id["historical_seed_strict_blind_replacement_operator_value_gate"]["blockers"]
    assert by_id["historical_seed_strict_blind_replacement_operator_action_board"]["status"] == (
        "awaiting_strict_blind_operator_actions"
    )
    assert by_id["historical_seed_strict_blind_replacement_operator_action_board"]["ready_count"] == 0
    assert by_id["historical_seed_strict_blind_replacement_operator_action_board"]["blocked_count"] == 400
    assert by_id["historical_seed_strict_blind_replacement_operator_action_board"]["total_count"] == 400
    assert "actions:400" in by_id["historical_seed_strict_blind_replacement_operator_action_board"]["blockers"]
    assert "open_value:400" in by_id["historical_seed_strict_blind_replacement_operator_action_board"]["blockers"]
    assert "open_evidence:400" in by_id["historical_seed_strict_blind_replacement_operator_action_board"]["blockers"]
    assert "open_clearance:400" in by_id["historical_seed_strict_blind_replacement_operator_action_board"]["blockers"]
    assert "missing_by_field:40/40/40/40/40/40/40/40/40/40" in by_id[
        "historical_seed_strict_blind_replacement_operator_action_board"
    ]["blockers"]
    assert by_id["historical_seed_strict_blind_replacement_promotion_gate"]["status"] == (
        "awaiting_strict_blind_replacement_promotion"
    )
    assert by_id["historical_seed_strict_blind_replacement_promotion_gate"]["ready_count"] == 0
    assert by_id["historical_seed_strict_blind_replacement_promotion_gate"]["blocked_count"] == 40
    assert by_id["historical_seed_strict_blind_replacement_promotion_gate"]["total_count"] == 40
    assert "ready:0" in by_id["historical_seed_strict_blind_replacement_promotion_gate"]["blockers"]
    assert "awaiting_file:40" in by_id["historical_seed_strict_blind_replacement_promotion_gate"]["blockers"]
    assert "awaiting_operator:40" in by_id["historical_seed_strict_blind_replacement_promotion_gate"]["blockers"]
    assert "awaiting_intake:40" in by_id["historical_seed_strict_blind_replacement_promotion_gate"]["blockers"]
    assert "complete_slots:0/0/0" in by_id["historical_seed_strict_blind_replacement_promotion_gate"]["blockers"]
    assert by_id["historical_seed_strict_blind_replacement_cycle"]["status"] == "awaiting_evidence_files"
    assert by_id["historical_seed_strict_blind_replacement_cycle"]["ready_count"] == 0
    assert by_id["historical_seed_strict_blind_replacement_cycle"]["blocked_count"] == 40
    assert by_id["historical_seed_strict_blind_replacement_cycle"]["total_count"] == 40
    assert "stage:evidence_dropzones" in by_id["historical_seed_strict_blind_replacement_cycle"]["blockers"]
    assert "files:0/240" in by_id["historical_seed_strict_blind_replacement_cycle"]["blockers"]
    assert "operator_awaiting:400" in by_id["historical_seed_strict_blind_replacement_cycle"]["blockers"]
    assert "operator_board:400/400/400" in by_id["historical_seed_strict_blind_replacement_cycle"]["blockers"]
    assert by_id["historical_seed_strict_blind_replacement_first_slot_kit"]["status"] == (
        "awaiting_first_slot_evidence_files"
    )
    assert by_id["historical_seed_strict_blind_replacement_first_slot_kit"]["ready_count"] == 0
    assert by_id["historical_seed_strict_blind_replacement_first_slot_kit"]["blocked_count"] == 16
    assert by_id["historical_seed_strict_blind_replacement_first_slot_kit"]["total_count"] == 16
    assert "benchmark:hist_REQUIRED_MONOMER_001" in by_id[
        "historical_seed_strict_blind_replacement_first_slot_kit"
    ]["blockers"]
    assert "evidence:0/6/0" in by_id["historical_seed_strict_blind_replacement_first_slot_kit"]["blockers"]
    assert "operator:0/10/0" in by_id["historical_seed_strict_blind_replacement_first_slot_kit"]["blockers"]
    assert "operator_open:10/10/10" in by_id[
        "historical_seed_strict_blind_replacement_first_slot_kit"
    ]["blockers"]
    assert by_id["historical_seed_strict_blind_replacement_first_slot_local_candidate_board"]["status"] == (
        "first_slot_local_candidates_review_only"
    )
    assert by_id["historical_seed_strict_blind_replacement_first_slot_local_candidate_board"]["ready_count"] == 0
    assert by_id["historical_seed_strict_blind_replacement_first_slot_local_candidate_board"]["blocked_count"] == 15
    assert by_id["historical_seed_strict_blind_replacement_first_slot_local_candidate_board"]["total_count"] == 15
    assert "candidates:0/0/15/15" in by_id[
        "historical_seed_strict_blind_replacement_first_slot_local_candidate_board"
    ]["blockers"]
    assert "present:15/15/15" in by_id[
        "historical_seed_strict_blind_replacement_first_slot_local_candidate_board"
    ]["blockers"]
    assert "blocked:10/15/14/15" in by_id[
        "historical_seed_strict_blind_replacement_first_slot_local_candidate_board"
    ]["blockers"]
    assert by_id["historical_seed_strict_blind_replacement_first_slot_candidate_repair_board"]["status"] == (
        "awaiting_first_slot_candidate_repairs"
    )
    assert by_id["historical_seed_strict_blind_replacement_first_slot_candidate_repair_board"]["ready_count"] == 0
    assert by_id["historical_seed_strict_blind_replacement_first_slot_candidate_repair_board"]["blocked_count"] == 96
    assert by_id["historical_seed_strict_blind_replacement_first_slot_candidate_repair_board"]["total_count"] == 96
    assert "actions:79/17/96" in by_id[
        "historical_seed_strict_blind_replacement_first_slot_candidate_repair_board"
    ]["blockers"]
    assert "classes:17/17/17/17" in by_id[
        "historical_seed_strict_blind_replacement_first_slot_candidate_repair_board"
    ]["blockers"]
    assert "source:2/2/7" in by_id[
        "historical_seed_strict_blind_replacement_first_slot_candidate_repair_board"
    ]["blockers"]
    assert "eligibility:17" in by_id[
        "historical_seed_strict_blind_replacement_first_slot_candidate_repair_board"
    ]["blockers"]
    assert by_id["historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board"]["status"] == (
        "first_slot_current_local_candidate_source_required"
    )
    assert by_id["historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board"]["ready_count"] == 62
    assert by_id["historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board"]["blocked_count"] == 34
    assert by_id["historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board"]["total_count"] == 96
    assert "post_native:17/17" in by_id[
        "historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board"
    ]["blockers"]
    assert "external:34/17" in by_id[
        "historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board"
    ]["blockers"]
    assert "repairable:11/51/0" in by_id[
        "historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board"
    ]["blockers"]
    assert "primary:0" in by_id[
        "historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board"
    ]["blockers"]
    assert by_id["historical_seed_strict_blind_replacement_first_slot_source_route_board"]["status"] == (
        "first_slot_requires_pre_native_monomer_source_or_replacement"
    )
    assert by_id["historical_seed_strict_blind_replacement_first_slot_source_route_board"]["ready_count"] == 0
    assert by_id["historical_seed_strict_blind_replacement_first_slot_source_route_board"]["blocked_count"] == 10
    assert by_id["historical_seed_strict_blind_replacement_first_slot_source_route_board"]["total_count"] == 17
    assert "scope:10/7/17" in by_id[
        "historical_seed_strict_blind_replacement_first_slot_source_route_board"
    ]["blockers"]
    assert "allowed:0" in by_id[
        "historical_seed_strict_blind_replacement_first_slot_source_route_board"
    ]["blockers"]
    assert "external:10/20" in by_id[
        "historical_seed_strict_blind_replacement_first_slot_source_route_board"
    ]["blockers"]
    assert "out_scope_repair:7/7" in by_id[
        "historical_seed_strict_blind_replacement_first_slot_source_route_board"
    ]["blockers"]
    assert by_id[
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates"
    ]["status"] == "first_slot_official_archive_native_authority_candidates_available"
    assert by_id[
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates"
    ]["ready_count"] == 24
    assert by_id[
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates"
    ]["blocked_count"] == 0
    assert by_id[
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates"
    ]["total_count"] == 24
    assert "sources:2" in by_id[
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates"
    ]["blockers"]
    assert "candidates:24/0/24" in by_id[
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates"
    ]["blockers"]
    assert "native:24/0" in by_id[
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates"
    ]["blockers"]
    assert "pdb:24/0" in by_id[
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates"
    ]["blockers"]
    assert "metadata:24" in by_id[
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates"
    ]["blockers"]
    assert "capri_deferred:3" in by_id[
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates"
    ]["blockers"]
    assert "cat:13/9/2" in by_id[
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates"
    ]["blockers"]
    assert "first:CASP16/T1210/9enr" in by_id[
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates"
    ]["blockers"]
    assert by_id["historical_seed_official_archive_baseline_lane"]["status"] == (
        "official_archive_baseline_lane_ready"
    )
    assert by_id["historical_seed_official_archive_baseline_lane"]["ready_count"] == 24
    assert by_id["historical_seed_official_archive_baseline_lane"]["blocked_count"] == 0
    assert by_id["historical_seed_official_archive_baseline_lane"]["total_count"] == 24
    assert "source_ready:24/24" in by_id["historical_seed_official_archive_baseline_lane"]["blockers"]
    assert "proof_eligible:0" in by_id["historical_seed_official_archive_baseline_lane"]["blockers"]
    assert "strict_blind_blocked:24" in by_id["historical_seed_official_archive_baseline_lane"]["blockers"]
    assert "other_team_baseline:24" in by_id["historical_seed_official_archive_baseline_lane"]["blockers"]
    assert "first:CASP16/T1210/9enr" in by_id["historical_seed_official_archive_baseline_lane"]["blockers"]
    assert by_id["official_archive_first_baseline_acquisition_audit"]["status"] == (
        "official_archive_first_baseline_acquired"
    )
    assert by_id["official_archive_first_baseline_acquisition_audit"]["ready_count"] == 2
    assert by_id["official_archive_first_baseline_acquisition_audit"]["blocked_count"] == 0
    assert by_id["official_archive_first_baseline_acquisition_audit"]["total_count"] == 2
    assert "first:CASP16/T1210/9ENR" in by_id[
        "official_archive_first_baseline_acquisition_audit"
    ]["blockers"]
    assert "artifacts:2/0/2" in by_id["official_archive_first_baseline_acquisition_audit"]["blockers"]
    assert "tar_models:357" in by_id["official_archive_first_baseline_acquisition_audit"]["blockers"]
    assert "native_atoms:7051" in by_id["official_archive_first_baseline_acquisition_audit"]["blockers"]
    assert "proof_eligible:False" in by_id[
        "official_archive_first_baseline_acquisition_audit"
    ]["blockers"]
    assert by_id["official_archive_first_baseline_model_pool"]["status"] == (
        "official_archive_first_baseline_model_pool_ready"
    )
    assert by_id["official_archive_first_baseline_model_pool"]["ready_count"] == 357
    assert by_id["official_archive_first_baseline_model_pool"]["blocked_count"] == 0
    assert by_id["official_archive_first_baseline_model_pool"]["total_count"] == 357
    assert "first:CASP16/T1210/9ENR" in by_id[
        "official_archive_first_baseline_model_pool"
    ]["blockers"]
    assert "models:357/0/357" in by_id["official_archive_first_baseline_model_pool"]["blockers"]
    assert "groups:74" in by_id["official_archive_first_baseline_model_pool"]["blockers"]
    assert "model1:73" in by_id["official_archive_first_baseline_model_pool"]["blockers"]
    assert "top5:348" in by_id["official_archive_first_baseline_model_pool"]["blockers"]
    assert "complete_top5:67" in by_id["official_archive_first_baseline_model_pool"]["blockers"]
    assert "proof_eligible:False" in by_id["official_archive_first_baseline_model_pool"]["blockers"]
    assert by_id["official_archive_first_baseline_score_ledger"]["status"] == (
        "official_archive_first_baseline_score_ledger_ready_baseline_only"
    )
    assert by_id["official_archive_first_baseline_score_ledger"]["ready_count"] == 348
    assert by_id["official_archive_first_baseline_score_ledger"]["blocked_count"] == 0
    assert by_id["official_archive_first_baseline_score_ledger"]["total_count"] == 348
    assert "first:CASP16/T1210/9ENR" in by_id[
        "official_archive_first_baseline_score_ledger"
    ]["blockers"]
    assert "models:348/0/348" in by_id["official_archive_first_baseline_score_ledger"]["blockers"]
    assert "model1:73" in by_id["official_archive_first_baseline_score_ledger"]["blockers"]
    assert "best_top5:74" in by_id["official_archive_first_baseline_score_ledger"]["blockers"]
    assert "improved:41" in by_id["official_archive_first_baseline_score_ledger"]["blockers"]
    assert "mean_model1:55.123" in by_id["official_archive_first_baseline_score_ledger"]["blockers"]
    assert "mean_best:62.456" in by_id["official_archive_first_baseline_score_ledger"]["blockers"]
    assert "proof_eligible:False" in by_id["official_archive_first_baseline_score_ledger"]["blockers"]
    assert by_id["official_archive_first_baseline_replay_comparison"]["status"] == (
        "official_archive_first_baseline_replay_comparison_ready_baseline_only"
    )
    assert by_id["official_archive_first_baseline_replay_comparison"]["ready_count"] == 0
    assert by_id["official_archive_first_baseline_replay_comparison"]["blocked_count"] == 3
    assert by_id["official_archive_first_baseline_replay_comparison"]["total_count"] == 3
    assert "first:CASP16/T1210/9ENR" in by_id[
        "official_archive_first_baseline_replay_comparison"
    ]["blockers"]
    assert "bands:0/3/3" in by_id["official_archive_first_baseline_replay_comparison"]["blockers"]
    assert "direct:not_directly_comparable_proxy_single_target_not_sum_zscore" in by_id[
        "official_archive_first_baseline_replay_comparison"
    ]["blockers"]
    assert "model1_best:32/73" in by_id["official_archive_first_baseline_replay_comparison"]["blockers"]
    assert "top5_improved:41/73" in by_id["official_archive_first_baseline_replay_comparison"]["blockers"]
    assert "rates:0.438/0.562" in by_id["official_archive_first_baseline_replay_comparison"]["blockers"]
    assert "proof_eligible:False" in by_id["official_archive_first_baseline_replay_comparison"]["blockers"]
    assert by_id["official_archive_first_baseline_model1_gap_triage"]["status"] == (
        "official_archive_first_baseline_model1_gap_triage_ready_baseline_only"
    )
    assert by_id["official_archive_first_baseline_model1_gap_triage"]["ready_count"] == 73
    assert by_id["official_archive_first_baseline_model1_gap_triage"]["blocked_count"] == 1
    assert by_id["official_archive_first_baseline_model1_gap_triage"]["total_count"] == 74
    assert "first:CASP16/T1210/9ENR" in by_id[
        "official_archive_first_baseline_model1_gap_triage"
    ]["blockers"]
    assert "groups:73/1/74" in by_id["official_archive_first_baseline_model1_gap_triage"]["blockers"]
    assert "model1_best:32/73" in by_id["official_archive_first_baseline_model1_gap_triage"]["blockers"]
    assert "top5_improved:41/73" in by_id["official_archive_first_baseline_model1_gap_triage"]["blockers"]
    assert "rates:0.438/0.562" in by_id["official_archive_first_baseline_model1_gap_triage"]["blockers"]
    assert "gaps:10/20/8/3" in by_id["official_archive_first_baseline_model1_gap_triage"]["blockers"]
    assert "critical:11" in by_id["official_archive_first_baseline_model1_gap_triage"]["blockers"]
    assert "first_triage:999/catastrophic_model1_selection_gap/70.000" in by_id[
        "official_archive_first_baseline_model1_gap_triage"
    ]["blockers"]
    assert "proof_eligible:False" in by_id["official_archive_first_baseline_model1_gap_triage"]["blockers"]
    assert by_id["official_archive_first_baseline_model1_gap_viewer_packet"]["status"] == (
        "official_archive_first_baseline_model1_gap_viewer_packet_ready_baseline_only"
    )
    assert by_id["official_archive_first_baseline_model1_gap_viewer_packet"]["ready_count"] == 11
    assert by_id["official_archive_first_baseline_model1_gap_viewer_packet"]["blocked_count"] == 0
    assert by_id["official_archive_first_baseline_model1_gap_viewer_packet"]["total_count"] == 11
    assert "first:CASP16/T1210/9ENR" in by_id[
        "official_archive_first_baseline_model1_gap_viewer_packet"
    ]["blockers"]
    assert "viewers:11/0/11" in by_id["official_archive_first_baseline_model1_gap_viewer_packet"]["blockers"]
    assert "cases:3/8" in by_id["official_archive_first_baseline_model1_gap_viewer_packet"]["blockers"]
    assert "pairs:11" in by_id["official_archive_first_baseline_model1_gap_viewer_packet"]["blockers"]
    assert "native:True" in by_id["official_archive_first_baseline_model1_gap_viewer_packet"]["blockers"]
    assert "first_viewer:999/catastrophic_model1_selection_gap/70.000" in by_id[
        "official_archive_first_baseline_model1_gap_viewer_packet"
    ]["blockers"]
    assert "proof_eligible:False" in by_id["official_archive_first_baseline_model1_gap_viewer_packet"]["blockers"]
    assert by_id["official_archive_first_baseline_model1_gap_feature_probe"]["status"] == (
        "official_archive_first_baseline_model1_gap_feature_probe_ready_baseline_only"
    )
    assert by_id["official_archive_first_baseline_model1_gap_feature_probe"]["ready_count"] == 11
    assert by_id["official_archive_first_baseline_model1_gap_feature_probe"]["blocked_count"] == 0
    assert by_id["official_archive_first_baseline_model1_gap_feature_probe"]["total_count"] == 11
    assert "first:CASP16/T1210/9ENR" in by_id[
        "official_archive_first_baseline_model1_gap_feature_probe"
    ]["blockers"]
    assert "features:11/0/11" in by_id["official_archive_first_baseline_model1_gap_feature_probe"]["blockers"]
    assert "signals:4/1/6" in by_id["official_archive_first_baseline_model1_gap_feature_probe"]["blockers"]
    assert "rate:0.364" in by_id["official_archive_first_baseline_model1_gap_feature_probe"]["blockers"]
    assert "cases:3/8" in by_id["official_archive_first_baseline_model1_gap_feature_probe"]["blockers"]
    assert "matrix:22" in by_id["official_archive_first_baseline_model1_gap_feature_probe"]["blockers"]
    assert "first_signal:999/supports_best_top5/115.000" in by_id[
        "official_archive_first_baseline_model1_gap_feature_probe"
    ]["blockers"]
    assert "proof_eligible:False" in by_id["official_archive_first_baseline_model1_gap_feature_probe"]["blockers"]
    assert by_id["official_archive_first_baseline_model1_gap_consensus_probe"]["status"] == (
        "official_archive_first_baseline_model1_gap_consensus_probe_ready_baseline_only"
    )
    assert by_id["official_archive_first_baseline_model1_gap_consensus_probe"]["ready_count"] == 11
    assert by_id["official_archive_first_baseline_model1_gap_consensus_probe"]["blocked_count"] == 0
    assert by_id["official_archive_first_baseline_model1_gap_consensus_probe"]["total_count"] == 11
    assert "first:CASP16/T1210/9ENR" in by_id[
        "official_archive_first_baseline_model1_gap_consensus_probe"
    ]["blockers"]
    assert "consensus:11/0/11" in by_id["official_archive_first_baseline_model1_gap_consensus_probe"]["blockers"]
    assert "signals:5/2/4" in by_id["official_archive_first_baseline_model1_gap_consensus_probe"]["blockers"]
    assert "rate:0.455" in by_id["official_archive_first_baseline_model1_gap_consensus_probe"]["blockers"]
    assert "top_matches:3/2" in by_id["official_archive_first_baseline_model1_gap_consensus_probe"]["blockers"]
    assert "pairs:110" in by_id["official_archive_first_baseline_model1_gap_consensus_probe"]["blockers"]
    assert "first_signal:999/supports_best_top5/12.345" in by_id[
        "official_archive_first_baseline_model1_gap_consensus_probe"
    ]["blockers"]
    assert "proof_eligible:False" in by_id["official_archive_first_baseline_model1_gap_consensus_probe"]["blockers"]
    assert by_id["official_archive_first_baseline_model1_gap_combined_selector_ledger"]["status"] == (
        "official_archive_first_baseline_model1_gap_combined_selector_ledger_ready_baseline_only"
    )
    assert by_id["official_archive_first_baseline_model1_gap_combined_selector_ledger"]["ready_count"] == 11
    assert by_id["official_archive_first_baseline_model1_gap_combined_selector_ledger"]["blocked_count"] == 0
    assert by_id["official_archive_first_baseline_model1_gap_combined_selector_ledger"]["total_count"] == 11
    assert "first:CASP16/T1210/9ENR" in by_id[
        "official_archive_first_baseline_model1_gap_combined_selector_ledger"
    ]["blockers"]
    assert "selector:11/0/11" in by_id[
        "official_archive_first_baseline_model1_gap_combined_selector_ledger"
    ]["blockers"]
    assert "decisions:5/5/1" in by_id[
        "official_archive_first_baseline_model1_gap_combined_selector_ledger"
    ]["blockers"]
    assert "baseline:5/5/1/0" in by_id[
        "official_archive_first_baseline_model1_gap_combined_selector_ledger"
    ]["blockers"]
    assert "rates:0.455/0.545" in by_id[
        "official_archive_first_baseline_model1_gap_combined_selector_ledger"
    ]["blockers"]
    assert "first_selector:999/promote_best_top5/corrected_model1_failure_baseline_proxy" in by_id[
        "official_archive_first_baseline_model1_gap_combined_selector_ledger"
    ]["blockers"]
    assert "proof_eligible:False" in by_id[
        "official_archive_first_baseline_model1_gap_combined_selector_ledger"
    ]["blockers"]
    assert by_id["strict_blind_first_slot_source_bridge"]["status"] == (
        "first_slot_source_bridge_internal_prediction_required"
    )
    assert by_id["strict_blind_first_slot_source_bridge"]["ready_count"] == 2
    assert by_id["strict_blind_first_slot_source_bridge"]["blocked_count"] == 7
    assert by_id["strict_blind_first_slot_source_bridge"]["total_count"] == 9
    assert "official:24/24" in by_id["strict_blind_first_slot_source_bridge"]["blockers"]
    assert "native_bridge:2" in by_id["strict_blind_first_slot_source_bridge"]["blockers"]
    assert "baseline_only:24" in by_id["strict_blind_first_slot_source_bridge"]["blockers"]
    assert "strict_blocked:24" in by_id["strict_blind_first_slot_source_bridge"]["blockers"]
    assert "operator_only:6" in by_id["strict_blind_first_slot_source_bridge"]["blockers"]
    assert "internal_prediction_blocked:1" in by_id["strict_blind_first_slot_source_bridge"]["blockers"]
    assert "auto_apply:0" in by_id["strict_blind_first_slot_source_bridge"]["blockers"]
    assert by_id["strict_blind_internal_prediction_source_audit"]["status"] == (
        "internal_prediction_source_missing_for_first_slot"
    )
    assert by_id["strict_blind_internal_prediction_source_audit"]["ready_count"] == 0
    assert by_id["strict_blind_internal_prediction_source_audit"]["blocked_count"] == 1
    assert by_id["strict_blind_internal_prediction_source_audit"]["total_count"] == 6
    assert "local:0/17" in by_id["strict_blind_internal_prediction_source_audit"]["blockers"]
    assert "routes:0/17" in by_id["strict_blind_internal_prediction_source_audit"]["blockers"]
    assert "official_blocked:24" in by_id["strict_blind_internal_prediction_source_audit"]["blockers"]
    assert "internal_blocked:1" in by_id["strict_blind_internal_prediction_source_audit"]["blockers"]
    assert "template:1" in by_id["strict_blind_internal_prediction_source_audit"]["blockers"]
    assert by_id["strict_blind_internal_candidate_filesystem_sweep"]["status"] == (
        "strict_blind_filesystem_sweep_operator_review_required"
    )
    assert by_id["strict_blind_internal_candidate_filesystem_sweep"]["ready_count"] == 0
    assert by_id["strict_blind_internal_candidate_filesystem_sweep"]["blocked_count"] == 4551
    assert by_id["strict_blind_internal_candidate_filesystem_sweep"]["total_count"] == 9968
    assert "files/atom:9968/9968" in by_id[
        "strict_blind_internal_candidate_filesystem_sweep"
    ]["blockers"]
    assert "verified:0" in by_id["strict_blind_internal_candidate_filesystem_sweep"]["blockers"]
    assert "unknown:4551" in by_id["strict_blind_internal_candidate_filesystem_sweep"]["blockers"]
    assert "current/mf/official/native/top5/dropzone:1810/2895/387/257/75/0" in by_id[
        "strict_blind_internal_candidate_filesystem_sweep"
    ]["blockers"]
    assert by_id["strict_blind_unknown_candidate_triage"]["status"] == (
        "strict_blind_unknown_triage_internal_like_review_required"
    )
    assert by_id["strict_blind_unknown_candidate_triage"]["ready_count"] == 0
    assert by_id["strict_blind_unknown_candidate_triage"]["blocked_count"] == 166
    assert by_id["strict_blind_unknown_candidate_triage"]["total_count"] == 4551
    assert "unknown:4551" in by_id["strict_blind_unknown_candidate_triage"]["blockers"]
    assert "internal_like:166" in by_id["strict_blind_unknown_candidate_triage"]["blockers"]
    assert "promotion_ready:0" in by_id["strict_blind_unknown_candidate_triage"]["blockers"]
    assert "public/run/archive/data/tmp/other:3962/406/16/0/1/0" in by_id[
        "strict_blind_unknown_candidate_triage"
    ]["blockers"]
    assert by_id["strict_blind_internal_like_source_review"]["status"] == (
        "strict_blind_internal_like_source_review_all_post_native"
    )
    assert by_id["strict_blind_internal_like_source_review"]["ready_count"] == 0
    assert by_id["strict_blind_internal_like_source_review"]["blocked_count"] == 166
    assert by_id["strict_blind_internal_like_source_review"]["total_count"] == 166
    assert "candidates:166/triage:166" in by_id["strict_blind_internal_like_source_review"]["blockers"]
    assert "mapped/pre/post/same/missing/unmapped:166/0/166/0/0/0" in by_id[
        "strict_blind_internal_like_source_review"
    ]["blockers"]
    assert "targets/all-post/pre-targets:10/10/0" in by_id[
        "strict_blind_internal_like_source_review"
    ]["blockers"]
    assert by_id["strict_blind_internal_prediction_source_gate"]["status"] == (
        "awaiting_internal_prediction_source_gate_fields"
    )
    assert by_id["strict_blind_internal_prediction_source_gate"]["ready_count"] == 3
    assert by_id["strict_blind_internal_prediction_source_gate"]["blocked_count"] == 13
    assert by_id["strict_blind_internal_prediction_source_gate"]["total_count"] == 16
    assert "manifest_rows:1" in by_id["strict_blind_internal_prediction_source_gate"]["blockers"]
    assert "first:source_id_internal/internal_source_id_missing_or_external" in by_id[
        "strict_blind_internal_prediction_source_gate"
    ]["blockers"]
    assert by_id["strict_blind_source_gate_field_board"]["status"] == "awaiting_source_gate_field_fills"
    assert by_id["strict_blind_source_gate_field_board"]["ready_count"] == 0
    assert by_id["strict_blind_source_gate_field_board"]["blocked_count"] == 11
    assert by_id["strict_blind_source_gate_field_board"]["total_count"] == 11
    assert "checks:3/13/16" in by_id["strict_blind_source_gate_field_board"]["blockers"]
    assert "actions:9/2/0/11" in by_id["strict_blind_source_gate_field_board"]["blockers"]
    assert "covered:13" in by_id["strict_blind_source_gate_field_board"]["blockers"]
    assert "first:source_id/internal_source_id_missing_or_external" in by_id[
        "strict_blind_source_gate_field_board"
    ]["blockers"]
    assert by_id["strict_blind_source_gate_operator_packet"]["status"] == (
        "awaiting_source_gate_operator_values"
    )
    assert by_id["strict_blind_source_gate_operator_packet"]["ready_count"] == 0
    assert by_id["strict_blind_source_gate_operator_packet"]["blocked_count"] == 11
    assert by_id["strict_blind_source_gate_operator_packet"]["total_count"] == 11
    assert "operator:0/11/11" in by_id["strict_blind_source_gate_operator_packet"]["blockers"]
    assert "patch:0/11" in by_id["strict_blind_source_gate_operator_packet"]["blockers"]
    assert "actions:9/1/1" in by_id["strict_blind_source_gate_operator_packet"]["blockers"]
    assert "first:source_id/awaiting_operator_value" in by_id[
        "strict_blind_source_gate_operator_packet"
    ]["blockers"]
    assert by_id["strict_blind_source_gate_source_request_packet"]["status"] == (
        "awaiting_pre_native_source_or_candidate_replacement"
    )
    assert by_id["strict_blind_source_gate_source_request_packet"]["ready_count"] == 0
    assert by_id["strict_blind_source_gate_source_request_packet"]["blocked_count"] == 17
    assert by_id["strict_blind_source_gate_source_request_packet"]["total_count"] == 17
    assert "requests:10/7/0/17" in by_id["strict_blind_source_gate_source_request_packet"]["blockers"]
    assert "scope:10/7" in by_id["strict_blind_source_gate_source_request_packet"]["blockers"]
    assert "templates:0/17" in by_id["strict_blind_source_gate_source_request_packet"]["blockers"]
    assert "fields:0/187/187" in by_id["strict_blind_source_gate_source_request_packet"]["blockers"]
    assert "first:source_request_001/HIST_BBA5/pre_native_prediction_source_required/prediction_not_before_native" in by_id[
        "strict_blind_source_gate_source_request_packet"
    ]["blockers"]
    assert by_id["strict_blind_source_request_resolution_board"]["status"] == (
        "source_request_resolution_all_current_candidates_blocked"
    )
    assert by_id["strict_blind_source_request_resolution_board"]["ready_count"] == 0
    assert by_id["strict_blind_source_request_resolution_board"]["blocked_count"] == 17
    assert by_id["strict_blind_source_request_resolution_board"]["total_count"] == 17
    assert "requests:0/17/17" in by_id["strict_blind_source_request_resolution_board"]["blockers"]
    assert "monomer/complex:10/7" in by_id["strict_blind_source_request_resolution_board"]["blockers"]
    assert "postnative/replacement/prenative-review/missing:10/7/0/0" in by_id[
        "strict_blind_source_request_resolution_board"
    ]["blockers"]
    assert "internal-like-post/pre:166/0" in by_id["strict_blind_source_request_resolution_board"]["blockers"]
    assert "first:source_request_001/HIST_BBA5/all_internal_like_candidates_post_native" in by_id[
        "strict_blind_source_request_resolution_board"
    ]["blockers"]
    assert by_id["strict_blind_source_request_fulfillment_gate"]["status"] == (
        "awaiting_source_request_operator_values"
    )
    assert by_id["strict_blind_source_request_fulfillment_gate"]["ready_count"] == 0
    assert by_id["strict_blind_source_request_fulfillment_gate"]["blocked_count"] == 17
    assert by_id["strict_blind_source_request_fulfillment_gate"]["total_count"] == 17
    assert "fields:0/187/187" in by_id["strict_blind_source_request_fulfillment_gate"]["blockers"]
    assert "evidence:0/153" in by_id["strict_blind_source_request_fulfillment_gate"]["blockers"]
    assert "validation:0/0/0" in by_id["strict_blind_source_request_fulfillment_gate"]["blockers"]
    assert "first:source_request_001/source_id_missing" in by_id[
        "strict_blind_source_request_fulfillment_gate"
    ]["blockers"]
    assert by_id["strict_blind_source_request_operator_fill_worklist"]["status"] == (
        "awaiting_source_request_operator_values"
    )
    assert by_id["strict_blind_source_request_operator_fill_worklist"]["ready_count"] == 0
    assert by_id["strict_blind_source_request_operator_fill_worklist"]["blocked_count"] == 187
    assert by_id["strict_blind_source_request_operator_fill_worklist"]["total_count"] == 187
    assert "fields:0/187/153/187" in by_id["strict_blind_source_request_operator_fill_worklist"][
        "blockers"
    ]
    assert "first:source_request_operator_fill_001/source_request_001/source_id/operator_value_missing" in by_id[
        "strict_blind_source_request_operator_fill_worklist"
    ]["blockers"]
    assert by_id["strict_blind_source_request_operator_sync_plan"]["status"] == (
        "awaiting_source_request_fulfillment"
    )
    assert by_id["strict_blind_source_request_operator_sync_plan"]["ready_count"] == 0
    assert by_id["strict_blind_source_request_operator_sync_plan"]["blocked_count"] == 1
    assert by_id["strict_blind_source_request_operator_sync_plan"]["total_count"] == 0
    assert "actions:0/1/0/0" in by_id["strict_blind_source_request_operator_sync_plan"]["blockers"]
    assert "first:source_request_sync_blocker_001/source_id_missing" in by_id[
        "strict_blind_source_request_operator_sync_plan"
    ]["blockers"]
    assert by_id["strict_blind_source_request_closure_board"]["status"] == (
        "awaiting_strict_blind_source_request_closure"
    )
    assert by_id["strict_blind_source_request_closure_board"]["ready_count"] == 0
    assert by_id["strict_blind_source_request_closure_board"]["blocked_count"] == 13
    assert by_id["strict_blind_source_request_closure_board"]["total_count"] == 13
    assert "required:hist_REQUIRED_MONOMER_001/REQUIRED_MONOMER_001/monomer" in by_id[
        "strict_blind_source_request_closure_board"
    ]["blockers"]
    assert "stages:0/13/13" in by_id["strict_blind_source_request_closure_board"]["blockers"]
    assert "awaiting_first_unlock_operator_values" in by_id[
        "strict_blind_source_request_closure_board"
    ]["blockers"]
    assert "awaiting_first_unlock_evidence_review" in by_id[
        "strict_blind_source_request_closure_board"
    ]["blockers"]
    assert "awaiting_pre_native_source_or_candidate_replacement" in by_id[
        "strict_blind_source_request_closure_board"
    ]["blockers"]
    assert "first:source_request_packet/awaiting_pre_native_source_or_candidate_replacement/prediction_not_before_native" in by_id[
        "strict_blind_source_request_closure_board"
    ]["blockers"]
    assert by_id["strict_blind_first_source_request_pickup"]["status"] == (
        "first_source_request_requires_pre_native_source"
    )
    assert by_id["strict_blind_first_source_request_pickup"]["ready_count"] == 0
    assert by_id["strict_blind_first_source_request_pickup"]["blocked_count"] == 3
    assert by_id["strict_blind_first_source_request_pickup"]["total_count"] == 3
    assert "request:source_request_001/HIST_BBA5/monomer" in by_id[
        "strict_blind_first_source_request_pickup"
    ]["blockers"]
    assert "dates:2026-02-19/2004-05-13/before:False" in by_id[
        "strict_blind_first_source_request_pickup"
    ]["blockers"]
    assert "options:0/3/3" in by_id["strict_blind_first_source_request_pickup"]["blockers"]
    assert "external:10/10" in by_id["strict_blind_first_source_request_pickup"]["blockers"]
    assert "first:first_source_pickup_001/prediction_not_before_native" in by_id[
        "strict_blind_first_source_request_pickup"
    ]["blockers"]
    assert by_id["strict_blind_first_unlock_handoff"]["status"] == "awaiting_first_unlock_operator_values"
    assert by_id["strict_blind_first_unlock_handoff"]["ready_count"] == 0
    assert by_id["strict_blind_first_unlock_handoff"]["blocked_count"] == 11
    assert by_id["strict_blind_first_unlock_handoff"]["total_count"] == 11
    assert "request:source_request_001/HIST_BBA5" in by_id["strict_blind_first_unlock_handoff"][
        "blockers"
    ]
    assert "fields:0/11/11" in by_id["strict_blind_first_unlock_handoff"]["blockers"]
    assert "first:source_id/operator_value_missing" in by_id["strict_blind_first_unlock_handoff"][
        "blockers"
    ]
    assert by_id["strict_blind_first_unlock_evidence_packet"]["status"] == (
        "awaiting_first_unlock_evidence_collection"
    )
    assert by_id["strict_blind_first_unlock_evidence_packet"]["ready_count"] == 0
    assert by_id["strict_blind_first_unlock_evidence_packet"]["blocked_count"] == 11
    assert by_id["strict_blind_first_unlock_evidence_packet"]["total_count"] == 11
    assert "request:source_request_001/HIST_BBA5" in by_id[
        "strict_blind_first_unlock_evidence_packet"
    ]["blockers"]
    assert "fields:0/11/11" in by_id["strict_blind_first_unlock_evidence_packet"]["blockers"]
    assert "stubs:11" in by_id["strict_blind_first_unlock_evidence_packet"]["blockers"]
    assert "files:2" in by_id["strict_blind_first_unlock_evidence_packet"]["blockers"]
    assert "first:source_id/operator_value_missing" in by_id[
        "strict_blind_first_unlock_evidence_packet"
    ]["blockers"]
    assert by_id["strict_blind_first_unlock_evidence_review_gate"]["status"] == (
        "awaiting_first_unlock_evidence_review"
    )
    assert by_id["strict_blind_first_unlock_evidence_review_gate"]["ready_count"] == 0
    assert by_id["strict_blind_first_unlock_evidence_review_gate"]["blocked_count"] == 11
    assert by_id["strict_blind_first_unlock_evidence_review_gate"]["total_count"] == 11
    assert "request:source_request_001/HIST_BBA5" in by_id[
        "strict_blind_first_unlock_evidence_review_gate"
    ]["blockers"]
    assert "fields:0/11/11" in by_id["strict_blind_first_unlock_evidence_review_gate"]["blockers"]
    assert "template_missing:11/0/11/11" in by_id[
        "strict_blind_first_unlock_evidence_review_gate"
    ]["blockers"]
    assert "stub:11/11" in by_id["strict_blind_first_unlock_evidence_review_gate"]["blockers"]
    assert "policy:0/11" in by_id["strict_blind_first_unlock_evidence_review_gate"]["blockers"]
    assert "file:0/2" in by_id["strict_blind_first_unlock_evidence_review_gate"]["blockers"]
    assert "first:source_id/template_operator_value_missing" in by_id[
        "strict_blind_first_unlock_evidence_review_gate"
    ]["blockers"]
    assert by_id["strict_blind_first_slot_source_gate_blocker_ledger"]["status"] == (
        "awaiting_first_slot_source_gate_operator_evidence"
    )
    assert by_id["strict_blind_first_slot_source_gate_blocker_ledger"]["ready_count"] == 0
    assert by_id["strict_blind_first_slot_source_gate_blocker_ledger"]["blocked_count"] == 11
    assert by_id["strict_blind_first_slot_source_gate_blocker_ledger"]["total_count"] == 11
    assert "required:hist_REQUIRED_MONOMER_001/REQUIRED_MONOMER_001" in by_id[
        "strict_blind_first_slot_source_gate_blocker_ledger"
    ]["blockers"]
    assert "fields:0/11/11" in by_id[
        "strict_blind_first_slot_source_gate_blocker_ledger"
    ]["blockers"]
    assert "gate:3/13/16" in by_id["strict_blind_first_slot_source_gate_blocker_ledger"]["blockers"]
    assert "operator:0/11" in by_id["strict_blind_first_slot_source_gate_blocker_ledger"]["blockers"]
    assert "review:0/11" in by_id["strict_blind_first_slot_source_gate_blocker_ledger"]["blockers"]
    assert "file:0/2" in by_id["strict_blind_first_slot_source_gate_blocker_ledger"]["blockers"]
    assert "first:source_id/template_operator_value_missing" in by_id[
        "strict_blind_first_slot_source_gate_blocker_ledger"
    ]["blockers"]
    assert by_id["strict_blind_first_unlock_evidence_sync_plan"]["status"] == (
        "awaiting_first_unlock_evidence_review"
    )
    assert by_id["strict_blind_first_unlock_evidence_sync_plan"]["ready_count"] == 0
    assert by_id["strict_blind_first_unlock_evidence_sync_plan"]["blocked_count"] == 11
    assert by_id["strict_blind_first_unlock_evidence_sync_plan"]["total_count"] == 11
    assert "mode:dry_run" in by_id["strict_blind_first_unlock_evidence_sync_plan"]["blockers"]
    assert "review:awaiting_first_unlock_evidence_review" in by_id[
        "strict_blind_first_unlock_evidence_sync_plan"
    ]["blockers"]
    assert "request:source_request_001/HIST_BBA5" in by_id[
        "strict_blind_first_unlock_evidence_sync_plan"
    ]["blockers"]
    assert "actions:0/11/0/11" in by_id["strict_blind_first_unlock_evidence_sync_plan"]["blockers"]
    assert "first:first_unlock_evidence_sync_001/template_operator_value_missing" in by_id[
        "strict_blind_first_unlock_evidence_sync_plan"
    ]["blockers"]
    assert by_id["strict_blind_internal_prediction_source_apply_plan"]["status"] == (
        "blocked_until_internal_prediction_source_gate_passes"
    )
    assert by_id["strict_blind_internal_prediction_source_apply_plan"]["ready_count"] == 0
    assert by_id["strict_blind_internal_prediction_source_apply_plan"]["blocked_count"] == 16
    assert by_id["strict_blind_internal_prediction_source_apply_plan"]["total_count"] == 16
    assert "gate:awaiting_internal_prediction_source_gate_fields" in by_id[
        "strict_blind_internal_prediction_source_apply_plan"
    ]["blockers"]
    assert "file/operator/supp:1/10/5" in by_id["strict_blind_internal_prediction_source_apply_plan"][
        "blockers"
    ]
    assert "first:internal_prediction_apply_001/internal_prediction_source_gate_not_ready" in by_id[
        "strict_blind_internal_prediction_source_apply_plan"
    ]["blockers"]
    assert by_id["strict_blind_first_slot_closure_kit"]["status"] == "blocked_on_internal_prediction_source_gate"
    assert by_id["strict_blind_first_slot_closure_kit"]["ready_count"] == 0
    assert by_id["strict_blind_first_slot_closure_kit"]["blocked_count"] == 7
    assert by_id["strict_blind_first_slot_closure_kit"]["total_count"] == 7
    assert "fills:11/17/12/20/60" in by_id["strict_blind_first_slot_closure_kit"]["blockers"]
    assert "first:internal_prediction_source_gate/internal_source_id_missing_or_external" in by_id[
        "strict_blind_first_slot_closure_kit"
    ]["blockers"]
    assert by_id["strict_blind_batch_closure_runway"]["status"] == (
        "blocked_on_first_slot_internal_prediction_source"
    )
    assert by_id["strict_blind_batch_closure_runway"]["ready_count"] == 0
    assert by_id["strict_blind_batch_closure_runway"]["blocked_count"] == 40
    assert by_id["strict_blind_batch_closure_runway"]["total_count"] == 40
    assert "source/evidence/operator/intake:1/39/0/0" in by_id["strict_blind_batch_closure_runway"][
        "blockers"
    ]
    assert "files:0/240" in by_id["strict_blind_batch_closure_runway"]["blockers"]
    assert "operators:0/400" in by_id["strict_blind_batch_closure_runway"]["blockers"]
    assert by_id["historical_seed_clearance_to_identity_intake_sync"]["status"] == (
        "waiting_on_cleared_seed_manifest"
    )
    assert by_id["historical_seed_clearance_to_identity_intake_sync"]["ready_count"] == 0
    assert by_id["historical_seed_clearance_to_identity_intake_sync"]["blocked_count"] == 15
    assert "eligible:0" in by_id["historical_seed_clearance_to_identity_intake_sync"]["blockers"]
    assert "waiting:15" in by_id["historical_seed_clearance_to_identity_intake_sync"]["blockers"]
    assert by_id["sidechain_native_benchmark"]["status"] == "blocked"
    assert by_id["sidechain_native_benchmark"]["blocked_count"] == 40
    assert "prediction_pdb_missing" in by_id["sidechain_native_benchmark"]["blockers"]


def test_build_casp17_workbench_index_blocks_missing_target_folders(tmp_path):
    target_json = tmp_path / "target_folders.json"
    _write_json(
        target_json,
        {
            "summary": {"packet_type": "casp17_target_model_folders", "ready_count": 1, "blocked_count": 1, "target_count": 2},
            "rows": [
                {"target_id": "T0001", "folder_status": "ready"},
                {"target_id": "T0002", "folder_status": "blocked"},
            ],
        },
    )

    args = mod.parse_args(
        [
            "--target-model-folders-json",
            str(target_json),
            "--organizer-notice-packet-json",
            str(tmp_path / "missing_organizer_notice.json"),
            "--protein-object-library-completion-audit-json",
            str(tmp_path / "missing_protein_object_library_completion_audit.json"),
            "--massivefold-external-pool-intake-json",
            str(tmp_path / "missing_massivefold_external_pool_intake.json"),
            "--rna-hybrid-massivefold-priority-queue-json",
            str(tmp_path / "missing_rna_hybrid_massivefold_priority_queue.json"),
            "--protein-complex-massivefold-priority-queue-json",
            str(tmp_path / "missing_protein_complex_massivefold_priority_queue.json"),
            "--massivefold-acquisition-verification-board-json",
            str(tmp_path / "missing_massivefold_acquisition_verification_board.json"),
            "--protein-complex-massivefold-acquisition-verification-board-json",
            str(tmp_path / "missing_protein_complex_massivefold_acquisition_verification_board.json"),
            "--massivefold-model-pool-index-json",
            str(tmp_path / "missing_massivefold_model_pool_index.json"),
            "--massivefold-representative-viewer-packet-json",
            str(tmp_path / "missing_massivefold_representative_viewer_packet.json"),
            "--massivefold-representative-rerank-packet-json",
            str(tmp_path / "missing_massivefold_representative_rerank_packet.json"),
            "--organic-ligand-slot-candidate-packet-json",
            str(tmp_path / "missing_organic_ligand_slot_candidate_packet.json"),
            "--organic-ligand-slot-promotion-action-board-json",
            str(tmp_path / "missing_organic_ligand_slot_promotion_action_board.json"),
            "--historical-winner-normalized-bands-json",
            str(tmp_path / "missing_historical_winner_normalized_bands.json"),
            "--historical-winner-normalized-unlock-plan-json",
            str(tmp_path / "missing_historical_winner_normalized_unlock_plan.json"),
            "--win-tier-critical-path-board-json",
            str(tmp_path / "missing_win_tier_critical_path_board.json"),
            "--target-object-viewer-smoke-json",
            str(tmp_path / "missing_object_viewer_smoke.json"),
            "--target-object-model-review-json",
            str(tmp_path / "missing_object_model_review.json"),
            "--win-gap-closure-json",
            str(tmp_path / "missing_closure.json"),
            "--input-scaffold-json",
            str(tmp_path / "missing_scaffold.json"),
            "--input-inventory-json",
            str(tmp_path / "missing_inventory.json"),
            "--operator-dashboard-json",
            str(tmp_path / "missing_dashboard.json"),
            "--historical-identity-seed-inventory-json",
            str(tmp_path / "missing_historical_identity_seed_inventory.json"),
            "--historical-identity-seed-clearance-json",
            str(tmp_path / "missing_historical_identity_seed_clearance.json"),
            "--historical-identity-seed-clearance-action-bundle-json",
            str(tmp_path / "missing_historical_identity_seed_clearance_action_bundle.json"),
            "--historical-identity-seed-clearance-field-board-json",
            str(tmp_path / "missing_historical_identity_seed_clearance_field_board.json"),
            "--historical-seed-current-target-prefill-json",
            str(tmp_path / "missing_historical_seed_current_target_prefill.json"),
            "--historical-seed-native-authority-audit-json",
            str(tmp_path / "missing_historical_seed_native_authority_audit.json"),
            "--historical-seed-native-replacement-candidates-json",
            str(tmp_path / "missing_historical_seed_native_replacement_candidates.json"),
            "--historical-seed-complex-source-authority-candidates-json",
            str(tmp_path / "missing_historical_seed_complex_source_authority_candidates.json"),
            "--historical-seed-chronology-candidate-board-json",
            str(tmp_path / "missing_historical_seed_chronology_candidate_board.json"),
            "--historical-seed-authoritative-chronology-audit-json",
            str(tmp_path / "missing_historical_seed_authoritative_chronology_audit.json"),
            "--historical-seed-lane-decision-packet-json",
            str(tmp_path / "missing_historical_seed_lane_decision_packet.json"),
            "--historical-seed-strict-blind-replacement-queue-json",
            str(tmp_path / "missing_historical_seed_strict_blind_replacement_queue.json"),
            "--historical-seed-strict-blind-replacement-intake-json",
            str(tmp_path / "missing_historical_seed_strict_blind_replacement_intake.json"),
            "--historical-seed-strict-blind-replacement-evidence-dropzones-json",
            str(tmp_path / "missing_historical_seed_strict_blind_replacement_evidence_dropzones.json"),
            "--historical-seed-strict-blind-replacement-evidence-action-board-json",
            str(tmp_path / "missing_historical_seed_strict_blind_replacement_evidence_action_board.json"),
            "--historical-seed-strict-blind-replacement-evidence-quality-audit-json",
            str(tmp_path / "missing_historical_seed_strict_blind_replacement_evidence_quality_audit.json"),
            "--historical-seed-strict-blind-replacement-evidence-import-gate-json",
            str(tmp_path / "missing_historical_seed_strict_blind_replacement_evidence_import_gate.json"),
            "--historical-seed-strict-blind-replacement-operator-value-gate-json",
            str(tmp_path / "missing_historical_seed_strict_blind_replacement_operator_value_gate.json"),
            "--historical-seed-strict-blind-replacement-operator-action-board-json",
            str(tmp_path / "missing_historical_seed_strict_blind_replacement_operator_action_board.json"),
            "--historical-seed-strict-blind-replacement-promotion-gate-json",
            str(tmp_path / "missing_historical_seed_strict_blind_replacement_promotion_gate.json"),
            "--historical-seed-strict-blind-replacement-cycle-json",
            str(tmp_path / "missing_historical_seed_strict_blind_replacement_cycle.json"),
            "--historical-seed-strict-blind-replacement-first-slot-kit-json",
            str(tmp_path / "missing_historical_seed_strict_blind_replacement_first_slot_kit.json"),
            "--historical-seed-strict-blind-replacement-first-slot-local-candidate-board-json",
            str(tmp_path / "missing_historical_seed_strict_blind_replacement_first_slot_local_candidate_board.json"),
            "--historical-seed-strict-blind-replacement-first-slot-candidate-repair-board-json",
            str(tmp_path / "missing_historical_seed_strict_blind_replacement_first_slot_candidate_repair_board.json"),
            "--historical-seed-strict-blind-replacement-first-slot-repair-feasibility-board-json",
            str(tmp_path / "missing_historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board.json"),
            "--historical-seed-strict-blind-replacement-first-slot-source-route-board-json",
            str(tmp_path / "missing_historical_seed_strict_blind_replacement_first_slot_source_route_board.json"),
            "--historical-seed-strict-blind-replacement-first-slot-official-archive-source-candidates-json",
            str(tmp_path / "missing_historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates.json"),
            "--historical-seed-official-archive-baseline-lane-json",
            str(tmp_path / "missing_historical_seed_official_archive_baseline_lane.json"),
            "--official-archive-first-baseline-acquisition-audit-json",
            str(tmp_path / "missing_official_archive_first_baseline_acquisition_audit.json"),
            "--official-archive-first-baseline-model-pool-json",
            str(tmp_path / "missing_official_archive_first_baseline_model_pool.json"),
            "--official-archive-first-baseline-score-ledger-json",
            str(tmp_path / "missing_official_archive_first_baseline_score_ledger.json"),
            "--official-archive-first-baseline-replay-comparison-json",
            str(tmp_path / "missing_official_archive_first_baseline_replay_comparison.json"),
            "--official-archive-first-baseline-model1-gap-triage-json",
            str(tmp_path / "missing_official_archive_first_baseline_model1_gap_triage.json"),
            "--official-archive-first-baseline-model1-gap-viewer-packet-json",
            str(tmp_path / "missing_official_archive_first_baseline_model1_gap_viewer_packet.json"),
            "--official-archive-first-baseline-model1-gap-feature-probe-json",
            str(tmp_path / "missing_official_archive_first_baseline_model1_gap_feature_probe.json"),
            "--official-archive-first-baseline-model1-gap-consensus-probe-json",
            str(tmp_path / "missing_official_archive_first_baseline_model1_gap_consensus_probe.json"),
            "--official-archive-first-baseline-model1-gap-combined-selector-ledger-json",
            str(tmp_path / "missing_official_archive_first_baseline_model1_gap_combined_selector_ledger.json"),
            "--strict-blind-first-slot-source-bridge-json",
            str(tmp_path / "missing_strict_blind_first_slot_source_bridge.json"),
            "--strict-blind-internal-prediction-source-audit-json",
            str(tmp_path / "missing_strict_blind_internal_prediction_source_audit.json"),
            "--strict-blind-internal-prediction-source-gate-json",
            str(tmp_path / "missing_strict_blind_internal_prediction_source_gate.json"),
            "--strict-blind-source-gate-field-board-json",
            str(tmp_path / "missing_strict_blind_source_gate_field_board.json"),
            "--strict-blind-source-gate-operator-packet-json",
            str(tmp_path / "missing_strict_blind_source_gate_operator_packet.json"),
            "--strict-blind-source-gate-source-request-packet-json",
            str(tmp_path / "missing_strict_blind_source_gate_source_request_packet.json"),
            "--strict-blind-source-request-fulfillment-gate-json",
            str(tmp_path / "missing_strict_blind_source_request_fulfillment_gate.json"),
            "--strict-blind-source-request-operator-fill-worklist-json",
            str(tmp_path / "missing_strict_blind_source_request_operator_fill_worklist.json"),
            "--strict-blind-source-request-operator-sync-plan-json",
            str(tmp_path / "missing_strict_blind_source_request_operator_sync_plan.json"),
            "--strict-blind-source-request-closure-board-json",
            str(tmp_path / "missing_strict_blind_source_request_closure_board.json"),
            "--strict-blind-first-source-request-pickup-json",
            str(tmp_path / "missing_strict_blind_first_source_request_pickup.json"),
            "--strict-blind-first-unlock-handoff-json",
            str(tmp_path / "missing_strict_blind_first_unlock_handoff.json"),
            "--strict-blind-first-unlock-evidence-packet-json",
            str(tmp_path / "missing_strict_blind_first_unlock_evidence_packet.json"),
            "--strict-blind-first-unlock-evidence-review-gate-json",
            str(tmp_path / "missing_strict_blind_first_unlock_evidence_review_gate.json"),
            "--strict-blind-first-slot-source-gate-blocker-ledger-json",
            str(tmp_path / "missing_strict_blind_first_slot_source_gate_blocker_ledger.json"),
            "--strict-blind-first-unlock-evidence-sync-plan-json",
            str(tmp_path / "missing_strict_blind_first_unlock_evidence_sync_plan.json"),
            "--strict-blind-internal-prediction-source-apply-plan-json",
            str(tmp_path / "missing_strict_blind_internal_prediction_source_apply_plan.json"),
            "--strict-blind-first-slot-closure-kit-json",
            str(tmp_path / "missing_strict_blind_first_slot_closure_kit.json"),
            "--strict-blind-batch-closure-runway-json",
            str(tmp_path / "missing_strict_blind_batch_closure_runway.json"),
            "--historical-seed-first-clearance-operator-kit-json",
            str(tmp_path / "missing_historical_seed_first_clearance_operator_kit.json"),
            "--historical-seed-first-clearance-no-leak-gate-json",
            str(tmp_path / "missing_historical_seed_first_clearance_no_leak_gate.json"),
            "--historical-seed-first-clearance-no-leak-evidence-packet-json",
            str(tmp_path / "missing_historical_seed_first_clearance_no_leak_evidence_packet.json"),
            "--historical-seed-first-clearance-no-leak-evidence-review-gate-json",
            str(tmp_path / "missing_historical_seed_first_clearance_no_leak_evidence_review_gate.json"),
            "--historical-seed-first-clearance-no-leak-evidence-sync-plan-json",
            str(tmp_path / "missing_historical_seed_first_clearance_no_leak_evidence_sync_plan.json"),
            "--historical-seed-first-clearance-closure-board-json",
            str(tmp_path / "missing_historical_seed_first_clearance_closure_board.json"),
            "--historical-seed-clearance-to-identity-intake-sync-json",
            str(tmp_path / "missing_historical_seed_clearance_to_identity_intake_sync.json"),
            "--sidechain-native-benchmark-json",
            str(tmp_path / "missing_sidechain_native_benchmark.json"),
            "--competitive-batch-json",
            str(tmp_path / "missing_competitive_batch.json"),
            "--competitive-row-fill-status-json",
            str(tmp_path / "missing_competitive_row_fill_status.json"),
            "--competitive-row-fill-worklist-json",
            str(tmp_path / "missing_competitive_row_fill_worklist.json"),
            "--competitive-identity-candidate-json",
            str(tmp_path / "missing_competitive_identity_candidate.json"),
            "--competitive-identity-source-repair-json",
            str(tmp_path / "missing_competitive_identity_source_repair.json"),
            "--competitive-floor-unblock-map-json",
            str(tmp_path / "missing_competitive_floor_unblock_map.json"),
            "--competitive-target-identity-discovery-json",
            str(tmp_path / "missing_competitive_target_identity_discovery.json"),
            "--competitive-target-identity-clearance-queue-json",
            str(tmp_path / "missing_competitive_target_identity_clearance.json"),
            "--competitive-target-identity-clearance-workorder-json",
            str(tmp_path / "missing_competitive_target_identity_clearance_workorder.json"),
            "--competitive-target-identity-clearance-operator-intake-json",
            str(tmp_path / "missing_competitive_target_identity_clearance_operator_intake.json"),
            "--competitive-target-identity-clearance-native-candidate-json",
            str(tmp_path / "missing_competitive_target_identity_clearance_native_candidate.json"),
            "--competitive-target-identity-clearance-adjudication-json",
            str(tmp_path / "missing_competitive_target_identity_clearance_adjudication.json"),
            "--competitive-target-identity-clearance-replacement-queue-json",
            str(tmp_path / "missing_competitive_target_identity_clearance_replacement_queue.json"),
            "--competitive-target-identity-clearance-replacement-source-repair-json",
            str(tmp_path / "missing_competitive_target_identity_clearance_replacement_source_repair.json"),
            "--competitive-target-identity-clearance-replacement-scorecard-json",
            str(tmp_path / "missing_competitive_target_identity_clearance_replacement_scorecard.json"),
            "--competitive-target-identity-clearance-replacement-duplicate-resolution-json",
            str(tmp_path / "missing_competitive_target_identity_clearance_replacement_duplicate_resolution.json"),
            "--competitive-target-identity-clearance-replacement-decision-bundle-json",
            str(tmp_path / "missing_competitive_target_identity_clearance_replacement_decision_bundle.json"),
            "--competitive-target-identity-clearance-replacement-decision-preflight-json",
            str(tmp_path / "missing_competitive_target_identity_clearance_replacement_decision_preflight.json"),
            "--competitive-target-identity-clearance-manifest-sync-json",
            str(tmp_path / "missing_competitive_target_identity_clearance_manifest_sync.json"),
            "--competitive-target-identity-clearance-workorder-audit-json",
            str(tmp_path / "missing_competitive_target_identity_clearance_workorder_audit.json"),
            "--competitive-target-identity-metric-runway-json",
            str(tmp_path / "missing_competitive_target_identity_metric_runway.json"),
            "--competitive-floor-native-provenance-operator-packet-json",
            str(tmp_path / "missing_competitive_floor_native_provenance_operator_packet.json"),
            "--competitive-floor-native-provenance-operator-packet-completion-audit-json",
            str(tmp_path / "missing_competitive_floor_native_provenance_operator_packet_completion_audit.json"),
            "--competitive-floor-native-provenance-metric-unlock-bridge-json",
            str(tmp_path / "missing_competitive_floor_native_provenance_metric_unlock_bridge.json"),
            "--competitive-floor-first-native-provenance-unlock-kit-json",
            str(tmp_path / "missing_competitive_floor_first_native_provenance_unlock_kit.json"),
            "--competitive-floor-batch-native-provenance-unlock-kit-json",
            str(tmp_path / "missing_competitive_floor_batch_native_provenance_unlock_kit.json"),
            "--competitive-floor-batch-native-provenance-unlock-kit-completion-audit-json",
            str(tmp_path / "missing_competitive_floor_batch_native_provenance_unlock_kit_completion_audit.json"),
            "--competitive-floor-batch-native-provenance-value-gate-json",
            str(tmp_path / "missing_competitive_floor_batch_native_provenance_value_gate.json"),
            "--competitive-floor-batch-native-provenance-value-action-board-json",
            str(tmp_path / "missing_competitive_floor_batch_native_provenance_value_action_board.json"),
            "--competitive-floor-batch-native-provenance-value-action-board-completion-audit-json",
            str(
                tmp_path
                / "missing_competitive_floor_batch_native_provenance_value_action_board_completion_audit.json"
            ),
            "--competitive-floor-batch-native-provenance-operator-fill-preflight-json",
            str(tmp_path / "missing_competitive_floor_batch_native_provenance_operator_fill_preflight.json"),
            "--competitive-floor-batch-native-provenance-operator-fill-preflight-completion-audit-json",
            str(
                tmp_path
                / "missing_competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit.json"
            ),
            "--competitive-target-identity-clearance-action-board-json",
            str(tmp_path / "missing_competitive_target_identity_clearance_action_board.json"),
            "--competitive-target-identity-clearance-action-bundle-json",
            str(tmp_path / "missing_competitive_target_identity_clearance_action_bundle.json"),
            "--competitive-target-identity-clearance-promotion-plan-json",
            str(tmp_path / "missing_competitive_target_identity_clearance_promotion.json"),
            "--competitive-target-identity-clearance-intake-staging-json",
            str(tmp_path / "missing_competitive_target_identity_clearance_intake_staging.json"),
            "--competitive-target-identity-clearance-candidate-intake-sync-json",
            str(tmp_path / "missing_competitive_target_identity_clearance_candidate_intake_sync.json"),
            "--competitive-target-identity-clearance-cycle-json",
            str(tmp_path / "missing_competitive_target_identity_clearance_cycle.json"),
            "--competitive-identity-cycle-json",
            str(tmp_path / "missing_competitive_identity_cycle.json"),
            "--competitive-operator-template-json",
            str(tmp_path / "missing_competitive_operator_template.json"),
            "--competitive-operator-preflight-json",
            str(tmp_path / "missing_competitive_operator_preflight.json"),
            "--data-bundle-json",
            str(tmp_path / "missing_bundle.json"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["workbench_status"] == "blocked"
    by_id = {row["artifact_id"]: row for row in payload["rows"]}
    assert by_id["target_model_folders"]["status"] == "blocked"
    assert "T0002" in by_id["target_model_folders"]["blockers"]
