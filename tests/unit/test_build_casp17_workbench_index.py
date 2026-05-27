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
    closure_json = tmp_path / "closure.json"
    goal_scorecard_json = tmp_path / "goal_scorecard.json"
    scaffold_json = tmp_path / "scaffold.json"
    inventory_json = tmp_path / "inventory.json"
    dashboard_json = tmp_path / "dashboard.json"
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
    competitive_target_identity_clearance_manifest_sync_json = (
        tmp_path / "competitive_target_identity_clearance_manifest_sync.json"
    )
    competitive_target_identity_clearance_workorder_audit_json = (
        tmp_path / "competitive_target_identity_clearance_workorder_audit.json"
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
                "source_candidate_count": 40,
                "source_ready_candidate_count": 0,
                "source_blocked_candidate_count": 40,
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
                "provenance_template_count": 1,
                "manifest_stub_count": 1,
                "first_open_next_action": "choose a different ready replacement candidate",
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
            "--win-gap-closure-json",
            str(closure_json),
            "--win-tier-goal-scorecard-json",
            str(goal_scorecard_json),
            "--input-scaffold-json",
            str(scaffold_json),
            "--input-inventory-json",
            str(inventory_json),
            "--operator-dashboard-json",
            str(dashboard_json),
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
            "--competitive-target-identity-clearance-manifest-sync-json",
            str(competitive_target_identity_clearance_manifest_sync_json),
            "--competitive-target-identity-clearance-workorder-audit-json",
            str(competitive_target_identity_clearance_workorder_audit_json),
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
    assert payload["summary"]["competitive_identity_candidate_source_count"] == 40
    assert payload["summary"]["competitive_identity_candidate_source_ready_count"] == 0
    assert payload["summary"]["competitive_identity_candidate_source_blocked_count"] == 40
    assert payload["summary"]["competitive_identity_candidate_applied_count"] == 0
    assert payload["summary"]["competitive_identity_candidate_operator_preflight_status"] == "blocked"
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
    assert payload["summary"]["competitive_target_identity_clearance_replacement_workorder_template_count"] == 1
    assert payload["summary"]["competitive_target_identity_clearance_replacement_workorder_stub_count"] == 1
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
    assert by_id["win_tier_goal_scorecard"]["status"] == "blocked_input"
    assert by_id["win_tier_goal_scorecard"]["ready_count"] == 1
    assert "historical_identity_clearance" in by_id["win_tier_goal_scorecard"]["blockers"]
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
    assert by_id["competitive_floor_target_identity_clearance_replacement_workorder_audit"]["status"] == "blocked"
    assert by_id["competitive_floor_target_identity_clearance_replacement_workorder_audit"]["blocked_count"] == 2
    assert "prediction:2" in by_id["competitive_floor_target_identity_clearance_replacement_workorder_audit"]["blockers"]
    assert "waiting:2" in by_id["competitive_floor_target_identity_clearance_replacement_workorder_audit"]["blockers"]
    assert by_id["competitive_floor_target_identity_clearance_manifest_sync"]["status"] == "awaiting_provenance"
    assert by_id["competitive_floor_target_identity_clearance_manifest_sync"]["blocked_count"] == 3
    assert by_id["competitive_floor_target_identity_clearance_workorder_audit"]["status"] == "blocked"
    assert "prediction_protein_atoms:3" in by_id["competitive_floor_target_identity_clearance_workorder_audit"]["blockers"]
    assert "prediction_coordinate_valid:3" in by_id["competitive_floor_target_identity_clearance_workorder_audit"]["blockers"]
    assert (
        "identity_discovery_blocked:3"
        in by_id["competitive_floor_target_identity_clearance_workorder_audit"]["blockers"]
    )
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
            "--competitive-target-identity-clearance-manifest-sync-json",
            str(tmp_path / "missing_competitive_target_identity_clearance_manifest_sync.json"),
            "--competitive-target-identity-clearance-workorder-audit-json",
            str(tmp_path / "missing_competitive_target_identity_clearance_workorder_audit.json"),
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
