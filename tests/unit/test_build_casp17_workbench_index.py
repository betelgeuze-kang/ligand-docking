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
    closure_json = tmp_path / "closure.json"
    scaffold_json = tmp_path / "scaffold.json"
    inventory_json = tmp_path / "inventory.json"
    dashboard_json = tmp_path / "dashboard.json"
    competitive_batch_json = tmp_path / "competitive_batch.json"
    competitive_row_fill_status_json = tmp_path / "competitive_row_fill_status.json"
    competitive_row_fill_worklist_json = tmp_path / "competitive_row_fill_worklist.json"
    competitive_evidence_dropzone_json = tmp_path / "competitive_evidence_dropzone.json"
    competitive_evidence_import_json = tmp_path / "competitive_evidence_import.json"
    competitive_evidence_round_json = tmp_path / "competitive_evidence_round.json"
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
            "summary": {"dashboard_status": "ready", "ready_count": 0, "blocked_count": 40, "row_count": 40},
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
            "--win-gap-closure-json",
            str(closure_json),
            "--input-scaffold-json",
            str(scaffold_json),
            "--input-inventory-json",
            str(inventory_json),
            "--operator-dashboard-json",
            str(dashboard_json),
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

    assert payload["summary"]["workbench_status"] == "ready_for_operator_fill"
    assert payload["summary"]["target_model_ready_count"] == 2
    assert payload["summary"]["target_model_object_count"] == 4
    assert payload["summary"]["target_model_object_projection_count"] == 4
    assert payload["summary"]["target_model_object_viewer_count"] == 4
    assert payload["summary"]["target_object_folder_audit_status"] == "pass"
    assert payload["summary"]["target_object_folder_audit_pass_count"] == 4
    assert payload["summary"]["target_object_folder_chain_isolation_pass_count"] == 4
    assert payload["summary"]["target_object_viewer_smoke_status"] == "pass"
    assert payload["summary"]["target_object_viewer_smoke_pass_count"] == 4
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
    assert payload["summary"]["first_operator_input_action_id"] == "historical_benchmark_inputs"
    assert len(payload["target_rows"]) == 2
    by_id = {row["artifact_id"]: row for row in payload["rows"]}
    assert by_id["target_model_folders"]["status"] == "ready"
    assert by_id["target_object_catalog"]["status"] == "ready"
    assert by_id["target_object_viewer_smoke"]["status"] == "pass"
    assert by_id["competitive_floor_batch"]["status"] == "ready_for_fill"
    assert by_id["competitive_floor_row_fill_status"]["status"] == "awaiting_fill"
    assert by_id["competitive_floor_row_fill_worklist"]["status"] == "open_actions"
    assert by_id["competitive_floor_evidence_import"]["status"] == "awaiting_import"
    assert by_id["competitive_floor_evidence_round"]["status"] == "awaiting_import"
    assert by_id["competitive_floor_operator_template"]["status"] == "blocked"
    assert by_id["competitive_floor_operator_preflight"]["status"] == "blocked"
    assert by_id["benchmark_input_inventory"]["status"] == "blocked"
    assert "cleared historical" in by_id["benchmark_input_inventory"]["next_action"]


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
            "--win-gap-closure-json",
            str(tmp_path / "missing_closure.json"),
            "--input-scaffold-json",
            str(tmp_path / "missing_scaffold.json"),
            "--input-inventory-json",
            str(tmp_path / "missing_inventory.json"),
            "--operator-dashboard-json",
            str(tmp_path / "missing_dashboard.json"),
            "--competitive-batch-json",
            str(tmp_path / "missing_competitive_batch.json"),
            "--competitive-row-fill-status-json",
            str(tmp_path / "missing_competitive_row_fill_status.json"),
            "--competitive-row-fill-worklist-json",
            str(tmp_path / "missing_competitive_row_fill_worklist.json"),
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
