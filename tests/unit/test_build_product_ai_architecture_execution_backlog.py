from __future__ import annotations

import json
from pathlib import Path

from tools import build_product_ai_architecture_execution_backlog as mod


def _packet(summary: dict[str, object], rows: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {"summary": summary, "rows": rows or []}


def test_execution_backlog_prioritizes_training_blockers_before_scope() -> None:
    payload = mod.build_product_ai_architecture_execution_backlog(
        architecture_packet=_packet({"all_gaps_closed": False, "open_gap_count": 2}),
        training_data_packet=_packet(
            {"production_training_data_ready": False},
            [
                {"check_id": "schema", "status": "pass"},
                {
                    "check_id": "supervised_ligand_dataset_breadth",
                    "status": "fail",
                    "source_artifact": "runs/train.json",
                    "observed": "rows=10",
                    "required": ">=1000 rows",
                    "next_action": "materialize broad dataset",
                },
            ],
        ),
        checkpoint_work_order_packet=_packet(
            {
                "checkpoint_preflight_ready": False,
                "candidate_checkpoint_count": 3,
                "ready_checkpoint_count": 0,
                "compatible_candidate_count": 0,
                "sidecar_builder_ready": False,
                "sidecar_builder_status": "blocked_residual_production_checkpoint_sidecar",
                "sidecar_builder_training_data_contract_ready": False,
                "sidecar_builder_force_gpu_return_receipt_ready": False,
                "sidecar_builder_force_gpu_return_receipt_operator_verified": False,
                "sidecar_builder_force_gpu_return_receipt_operator_verified_true_count": 0,
                "sidecar_builder_force_gpu_return_receipt_expected_queue_rows": 768,
                "sidecar_builder_blockers": ["production_output_heads_complete", "force_gpu_return_receipt_ready"],
                "sidecar_builder_missing_production_output_fields": ["delta_force"],
                "sidecar_builder_training_contract_missing_label_fields": ["delta_force"],
                "checkpoint_closure_blockers": [
                    "sidecar_missing_production_output:delta_force",
                    "training_missing_label:delta_force",
                    "force_gpu_return_receipt_operator_not_verified",
                ],
                "registry_checkpoint_missing_output_fields": ["delta_force"],
                "registry_checkpoint_missing_adapter_output_policy_fields": ["delta_force"],
            }
        ),
        scope_work_order_packet=_packet(
            {"scope_breadth_ready": False},
            [
                {
                    "domain": "transporter",
                    "observed": "placeholder=6",
                    "acceptance_criteria": "placeholder=0",
                    "next_action": "replace placeholders",
                    "verification": "python3 tools/build_product_scope_breadth_contract.py",
                }
            ],
        ),
    )

    rows = payload["rows"]
    assert payload["summary"]["status"] == "product_ai_architecture_execution_backlog_ready"
    assert rows[0]["work_item_id"] == "training_data.supervised_ligand_dataset_breadth"
    assert rows[1]["work_item_id"] == "checkpoint_work_order.ready_checkpoint"
    assert "sidecar_builder_ready=False" in rows[1]["observed"]
    assert "sidecar_training_data_ready=False" in rows[1]["observed"]
    assert "sidecar_force_receipt_ready=False" in rows[1]["observed"]
    assert "sidecar_force_receipt_operator_verified=False" in rows[1]["observed"]
    assert "sidecar_force_receipt_operator_verified_true_count=0" in rows[1]["observed"]
    assert "sidecar_force_receipt_expected_queue_rows=768" in rows[1]["observed"]
    assert "sidecar_builder_blockers=production_output_heads_complete,force_gpu_return_receipt_ready" in rows[1]["observed"]
    assert "sidecar_missing_production_output_fields=delta_force" in rows[1]["observed"]
    assert "sidecar_training_contract_missing_label_fields=delta_force" in rows[1]["observed"]
    assert "checkpoint_closure_blockers=sidecar_missing_production_output:delta_force,training_missing_label:delta_force,force_gpu_return_receipt_operator_not_verified" in rows[1]["observed"]
    assert "registry_checkpoint_missing_output_fields=delta_force" in rows[1]["observed"]
    assert "registry_checkpoint_missing_adapter_output_policy_fields=delta_force" in rows[1]["observed"]
    assert "train_residual_production_score_model.py" in rows[1]["verification_command"]
    assert "build_residual_production_checkpoint_sidecar.py" in rows[1]["verification_command"]
    assert rows[1]["verification_command"].index("train_residual_production_score_model.py") < rows[1][
        "verification_command"
    ].index("build_residual_production_checkpoint_sidecar.py")
    assert rows[1]["verification_command"].index("build_residual_production_checkpoint_sidecar.py") < rows[1][
        "verification_command"
    ].index("build_residual_production_checkpoint_preflight.py")
    assert "build_residual_production_checkpoint_work_order.py" in rows[1]["verification_command"]
    assert "build_residual_model_registry.py" in rows[1]["verification_command"]
    assert rows[2]["work_item_id"] == "scope_breadth.transporter"


def test_execution_backlog_splits_missing_production_output_heads_before_parent_checkpoint() -> None:
    payload = mod.build_product_ai_architecture_execution_backlog(
        architecture_packet=_packet({"all_gaps_closed": False, "open_gap_count": 2}),
        training_data_packet=_packet(
            {"production_training_data_ready": False},
            [
                {
                    "check_id": "production_residual_output_head",
                    "status": "fail",
                    "source_artifact": "runs/residual_production_checkpoint_work_order_current.json",
                    "score_model_artifact": "runs/residual_production_score_model_current.json",
                    "observed": "checkpoint_preflight_ready=False",
                    "required": "production output head ready",
                    "next_action": "extend score candidate",
                    "missing_production_output_fields": ["delta_energy", "delta_force", "stage2_route_decision"],
                }
            ],
        ),
        checkpoint_work_order_packet=_packet(
            {"checkpoint_preflight_ready": False, "candidate_checkpoint_count": 3, "ready_checkpoint_count": 0, "compatible_candidate_count": 0}
        ),
        scope_work_order_packet=_packet({"scope_breadth_ready": True}),
        force_receipt_packet=_packet(
            {
                "gpu_worker_return_receipt_ready": False,
                "blockers": [
                    "full_regeneration_summary_complete",
                    "full_regeneration_manifest_operator_verified",
                ],
                "full_regeneration_summary_manifest_bound": False,
                "summary_manifest_csv": "runs/other_manifest.csv",
                "full_regeneration_summary_out_manifest_csv_present": False,
                "summary_out_manifest_csv": "",
                "full_regeneration_summary_out_manifest_csv_bound": False,
                "full_regeneration_summary_out_summary_json_bound": False,
                "summary_out_summary_json": "",
                "full_regeneration_summary_manifest_row_counts_consistent": False,
                "expected_queue_rows": 768,
                "manifest_ok_row_count": 0,
                "manifest_status_placeholder_count": 1,
                "manifest_status_invalid_count": 2,
                "manifest_allowed_ok_status_values": ["ok", "ok_npz_bundle"],
                "full_regeneration_manifest_npz_paths_complete": False,
                "manifest_npz_path_present_count": 0,
                "manifest_npz_path_missing_count": 2,
                "manifest_ok_row_missing_npz_path_count": 1,
                "manifest_operator_verified_missing_npz_path_count": 1,
                "full_regeneration_manifest_npz_files_exist": False,
                "manifest_npz_file_existing_count": 0,
                "manifest_npz_file_missing_count": 2,
                "manifest_ok_row_missing_npz_file_count": 1,
                "manifest_operator_verified_missing_npz_file_count": 1,
                "full_regeneration_manifest_npz_files_valid": False,
                "manifest_npz_file_valid_count": 0,
                "manifest_npz_file_invalid_count": 2,
                "manifest_ok_row_invalid_npz_file_count": 1,
                "manifest_operator_verified_invalid_npz_file_count": 1,
                "full_regeneration_manifest_npz_schema_valid": False,
                "manifest_npz_schema_valid_count": 0,
                "manifest_npz_schema_invalid_count": 2,
                "manifest_ok_row_invalid_npz_schema_count": 1,
                "manifest_operator_verified_invalid_npz_schema_count": 1,
                "full_regeneration_manifest_npz_identity_valid": False,
                "manifest_npz_identity_valid_count": 0,
                "manifest_npz_identity_invalid_count": 2,
                "manifest_ok_row_invalid_npz_identity_count": 1,
                "manifest_operator_verified_invalid_npz_identity_count": 1,
                "full_regeneration_manifest_operator_verified": False,
                "manifest_operator_verified_true_count": 0,
                "manifest_operator_verification_column_present": False,
                "queue_manifest_identity_coverage_ready": False,
                "manifest_matched_queue_fingerprint_count": 0,
                "queue_fingerprint_count": 768,
            }
        ),
    )

    rows = payload["rows"]
    assert rows[0]["work_item_id"] == "training_data.production_residual_output_head.delta_energy"
    assert rows[1]["work_item_id"] == "training_data.production_residual_output_head.delta_force"
    assert rows[2]["work_item_id"] == "training_data.production_residual_output_head.stage2_route_decision"
    assert rows[3]["work_item_id"] == "checkpoint_work_order.ready_checkpoint"
    assert "runs/residual_production_score_model_current.json" == rows[0]["source_artifact"]
    assert "missing_production_output_field=delta_energy" in rows[0]["observed"]
    assert "train_residual_production_score_model.py" in rows[0]["verification_command"]
    assert "build_residual_production_checkpoint_sidecar.py" in rows[0]["verification_command"]
    assert rows[0]["verification_command"].index("train_residual_production_score_model.py") < rows[0][
        "verification_command"
    ].index("build_residual_production_checkpoint_sidecar.py")
    assert "build_residual_model_registry.py" in rows[0]["verification_command"]


def test_execution_backlog_prioritizes_energy_force_label_evidence_before_output_heads() -> None:
    payload = mod.build_product_ai_architecture_execution_backlog(
        architecture_packet=_packet({"all_gaps_closed": False, "open_gap_count": 2}),
        training_data_packet=_packet(
            {"production_training_data_ready": False},
            [
                {
                    "check_id": "production_delta_energy_label_evidence",
                    "status": "fail",
                    "source_artifact": "runs/residual_production_supervised_dataset_current.json",
                    "observed": "missing_production_output_labels=delta_energy,delta_force",
                    "required": "delta_energy labels",
                    "next_action": "materialize delta_energy labels",
                },
                {
                    "check_id": "production_delta_force_label_evidence",
                    "status": "fail",
                    "source_artifact": "runs/residual_production_supervised_dataset_current.json",
                    "observed": "missing_production_output_labels=delta_energy,delta_force",
                    "required": "delta_force labels",
                    "next_action": "materialize delta_force labels",
                },
                {
                    "check_id": "production_residual_output_head",
                    "status": "fail",
                    "source_artifact": "runs/residual_production_checkpoint_work_order_current.json",
                    "score_model_artifact": "runs/residual_production_score_model_current.json",
                    "observed": "missing_production_output_fields=delta_energy,delta_force",
                    "required": "production output head ready",
                    "next_action": "extend score candidate",
                    "missing_production_output_fields": ["delta_energy", "delta_force"],
                },
            ],
        ),
        checkpoint_work_order_packet=_packet(
            {"checkpoint_preflight_ready": False, "candidate_checkpoint_count": 3, "ready_checkpoint_count": 0, "compatible_candidate_count": 0}
        ),
        scope_work_order_packet=_packet({"scope_breadth_ready": True}),
        force_receipt_packet=_packet(
            {
                "gpu_worker_return_receipt_ready": False,
                "blockers": [
                    "full_regeneration_summary_complete",
                    "full_regeneration_manifest_operator_verified",
                ],
                "full_regeneration_summary_manifest_bound": False,
                "summary_manifest_csv": "runs/other_manifest.csv",
                "full_regeneration_summary_out_manifest_csv_present": False,
                "summary_out_manifest_csv": "",
                "full_regeneration_summary_out_manifest_csv_bound": False,
                "full_regeneration_summary_out_summary_json_bound": False,
                "summary_out_summary_json": "",
                "full_regeneration_summary_manifest_row_counts_consistent": False,
                "expected_queue_rows": 768,
                "manifest_ok_row_count": 0,
                "manifest_status_placeholder_count": 1,
                "manifest_status_invalid_count": 2,
                "manifest_allowed_ok_status_values": ["ok", "ok_npz_bundle"],
                "full_regeneration_manifest_npz_paths_complete": False,
                "manifest_npz_path_present_count": 0,
                "manifest_npz_path_missing_count": 2,
                "manifest_ok_row_missing_npz_path_count": 1,
                "manifest_operator_verified_missing_npz_path_count": 1,
                "full_regeneration_manifest_npz_files_exist": False,
                "manifest_npz_file_existing_count": 0,
                "manifest_npz_file_missing_count": 2,
                "manifest_ok_row_missing_npz_file_count": 1,
                "manifest_operator_verified_missing_npz_file_count": 1,
                "full_regeneration_manifest_npz_files_valid": False,
                "manifest_npz_file_valid_count": 0,
                "manifest_npz_file_invalid_count": 2,
                "manifest_ok_row_invalid_npz_file_count": 1,
                "manifest_operator_verified_invalid_npz_file_count": 1,
                "full_regeneration_manifest_npz_schema_valid": False,
                "manifest_npz_schema_valid_count": 0,
                "manifest_npz_schema_invalid_count": 2,
                "manifest_ok_row_invalid_npz_schema_count": 1,
                "manifest_operator_verified_invalid_npz_schema_count": 1,
                "full_regeneration_manifest_npz_identity_valid": False,
                "manifest_npz_identity_valid_count": 0,
                "manifest_npz_identity_invalid_count": 2,
                "manifest_ok_row_invalid_npz_identity_count": 1,
                "manifest_operator_verified_invalid_npz_identity_count": 1,
                "full_regeneration_manifest_operator_verified": False,
                "manifest_operator_verified_true_count": 0,
                "manifest_operator_verification_column_present": False,
                "queue_manifest_identity_coverage_ready": False,
                "manifest_matched_queue_fingerprint_count": 0,
                "queue_fingerprint_count": 768,
            }
        ),
    )

    rows = payload["rows"]
    assert rows[0]["work_item_id"] == "training_data.production_delta_energy_label_evidence"
    assert rows[1]["work_item_id"] == "training_data.production_delta_force_label_evidence"
    assert "gpu_worker_return_receipt_blockers=full_regeneration_summary_complete,full_regeneration_manifest_operator_verified" in rows[1]["observed"]
    assert "gpu_worker_return_summary_manifest_bound=False" in rows[1]["observed"]
    assert "gpu_worker_return_summary_manifest_csv=runs/other_manifest.csv" in rows[1]["observed"]
    assert "gpu_worker_return_summary_out_manifest_csv_present=False" in rows[1]["observed"]
    assert "gpu_worker_return_summary_out_manifest_csv=" in rows[1]["observed"]
    assert "gpu_worker_return_summary_out_manifest_csv_bound=False" in rows[1]["observed"]
    assert "gpu_worker_return_summary_out_summary_json_bound=False" in rows[1]["observed"]
    assert "gpu_worker_return_summary_out_summary_json=" in rows[1]["observed"]
    assert "gpu_worker_return_summary_manifest_row_counts_consistent=False" in rows[1]["observed"]
    assert "gpu_worker_return_expected_queue_rows=768" in rows[1]["observed"]
    assert "gpu_worker_return_manifest_ok_row_count=0" in rows[1]["observed"]
    assert "gpu_worker_return_manifest_status_placeholder_count=1" in rows[1]["observed"]
    assert "gpu_worker_return_manifest_status_invalid_count=2" in rows[1]["observed"]
    assert "gpu_worker_return_manifest_allowed_ok_status_values=ok,ok_npz_bundle" in rows[1]["observed"]
    assert "gpu_worker_return_manifest_npz_paths_complete=False" in rows[1]["observed"]
    assert "gpu_worker_return_manifest_ok_row_missing_npz_path_count=1" in rows[1]["observed"]
    assert "gpu_worker_return_manifest_npz_files_exist=False" in rows[1]["observed"]
    assert "gpu_worker_return_manifest_ok_row_missing_npz_file_count=1" in rows[1]["observed"]
    assert "gpu_worker_return_manifest_npz_files_valid=False" in rows[1]["observed"]
    assert "gpu_worker_return_manifest_ok_row_invalid_npz_file_count=1" in rows[1]["observed"]
    assert "gpu_worker_return_manifest_npz_schema_valid=False" in rows[1]["observed"]
    assert "gpu_worker_return_manifest_ok_row_invalid_npz_schema_count=1" in rows[1]["observed"]
    assert "gpu_worker_return_manifest_npz_identity_valid=False" in rows[1]["observed"]
    assert "gpu_worker_return_manifest_ok_row_invalid_npz_identity_count=1" in rows[1]["observed"]
    assert "gpu_worker_return_manifest_operator_verified=False" in rows[1]["observed"]
    assert "gpu_worker_return_operator_verified_true_count=0" in rows[1]["observed"]
    assert "gpu_worker_return_queue_fingerprints=768" in rows[1]["observed"]
    assert rows[2]["work_item_id"] == "training_data.production_residual_output_head.delta_energy"
    assert rows[3]["work_item_id"] == "training_data.production_residual_output_head.delta_force"
    assert "build_residual_force_gpu_worker_return_manifest_template.py" in rows[1]["verification_command"]
    assert "build_residual_force_gpu_worker_return_summary_template.py" in rows[1]["verification_command"]
    assert "build_residual_force_gpu_worker_return_receipt.py" in rows[1]["verification_command"]
    assert "build_residual_uncertainty_policy_evidence_contract.py" in rows[1]["verification_command"]
    assert rows[1]["verification_command"].index("build_residual_force_gpu_worker_return_manifest_template.py") < rows[1][
        "verification_command"
    ].index("build_residual_force_gpu_worker_return_summary_template.py")
    assert rows[1]["verification_command"].index("build_residual_force_gpu_worker_return_summary_template.py") < rows[1][
        "verification_command"
    ].index("build_residual_force_gpu_worker_handoff_package.py")
    assert rows[1]["verification_command"].index("build_residual_force_gpu_worker_return_receipt.py") < rows[1][
        "verification_command"
    ].index("build_residual_force_derivation_validation.py")
    assert rows[1]["verification_command"].index("build_residual_uncertainty_policy_evidence_contract.py") < rows[1][
        "verification_command"
    ].index("build_residual_production_training_data_contract.py")
    assert "build_residual_energy_force_label_validation.py" in rows[1]["verification_command"]
    assert payload["summary"]["primary_work_item_id"] == "training_data.production_delta_energy_label_evidence"


def test_execution_backlog_clear_when_architecture_complete() -> None:
    payload = mod.build_product_ai_architecture_execution_backlog(
        architecture_packet=_packet({"all_gaps_closed": True, "open_gap_count": 0}),
        training_data_packet=_packet({"production_training_data_ready": True}),
        checkpoint_work_order_packet=_packet({"checkpoint_preflight_ready": True}),
        scope_work_order_packet=_packet({"scope_breadth_ready": True}),
    )

    assert payload["summary"]["backlog_clear"] is True
    assert payload["summary"]["work_item_count"] == 0


def test_execution_backlog_uses_scope_closure_checklist_when_available() -> None:
    payload = mod.build_product_ai_architecture_execution_backlog(
        architecture_packet=_packet({"all_gaps_closed": False, "open_gap_count": 1}),
        training_data_packet=_packet({"production_training_data_ready": True}),
        checkpoint_work_order_packet=_packet({"checkpoint_preflight_ready": True}),
        scope_work_order_packet=_packet(
            {"scope_breadth_ready": False},
            [{"domain": "transporter", "observed": "p0_open=6", "acceptance_criteria": "p0_open=0"}],
        ),
        scope_closure_checklist_packet=_packet(
            {
                "closure_checklist_ready": True,
                "blocker_class_counts": {
                    "direct_binding_evidence_missing": 1,
                    "explicit_general_platform_flag_missing": 1,
                },
                "first_scientific_blocker": "AQP1.core_binder_01",
                "manual_review_subcheck_count": 5,
                "transporter_manual_review_subcheck_count": 5,
                "transporter_identity_scaffold_confirmation_required_count": 1,
                "transporter_direct_binding_or_kcal_confirmation_required_count": 1,
                "transporter_negative_quantitative_confirmation_required_count": 0,
                "transporter_direct_binding_missing_count": 1,
                "transporter_negative_quantitative_missing_count": 0,
                "pxr_reconciled_blocked_row_count": 0,
                "pxr_conflict_resolution_count": 0,
                "pxr_quantitative_missing_count": 0,
                "general_claim_blocker_count": 1,
                "ready_for_apply_count": 0,
                "authoritative_apply_allowed": False,
                "claim_boundary_detail": (
                    "allowed_scope_families=gpcr,ion_channel,kinase;"
                    "blocked_claim_scopes=transporter_domain_promotion,general_protein_ligand_platform;"
                    "claim_blocked_domains=transporter;general_platform_claim_allowed=False"
                ),
            },
            [
                {
                    "domain": "transporter",
                    "item_id": "AQP1.core_binder_01",
                    "closure_lane": "scientific_slot_assignment",
                    "current_state": "functional_quantitative_surrogate_review_only",
                    "missing_fields": "",
                    "manual_review_blockers": "review_only_or_functional_surrogate",
                    "manual_review_subchecks": "direct_binding_or_claim_safe_kcal_confirmed=false;ligand_identity_confirmed=false",
                    "candidate_ligand_id": "chembl_chembl195380",
                    "candidate_reference_binding_kcal_mol": "-7.5970",
                    "candidate_source": "chembl_activity::CHEMBL195380::IC50_2700.0_nM::source_CHEMBL5230131",
                    "blocker_class": "direct_binding_evidence_missing",
                    "customer_claim_impact": "blocks transporter binder coverage and transporter domain promotion",
                    "acceptance_criteria": "Exact direct-binding/kcal evidence replaces functional-surrogate-only blocker.",
                    "close_action": "Curate exact direct-binding evidence.",
                    "verification_command": "python3 tools/build_product_scope_breadth_closure_checklist.py",
                    "ready_for_apply": False,
                    "scope_promotion_allowed": False,
                },
                {
                    "domain": "general_protein_ligand",
                    "item_id": "explicit_general_platform_flag",
                    "closure_lane": "product_claim_flag",
                    "current_state": "current=False;required=True",
                    "manual_review_blockers": "claim_gate_waits_on_scientific_scope",
                    "acceptance_criteria": "True",
                    "close_action": "Set flag after scientific gates.",
                    "ready_for_apply": False,
                    "scope_promotion_allowed": False,
                },
            ],
        ),
    )

    assert payload["summary"]["scope_closure_checklist_used"] is True
    assert payload["summary"]["scope_closure_checklist_item_count"] == 2
    assert payload["summary"]["scope_closure_blocker_class_counts"]["direct_binding_evidence_missing"] == 1
    assert "scope_closure_first_scientific_blocker=AQP1.core_binder_01" in payload["summary"]["scope_closure_detail"]
    assert "scope_closure_manual_review_subcheck_count=5" in payload["summary"]["scope_closure_detail"]
    assert "scope_closure_transporter_identity_scaffold_confirmation_required_count=1" in payload["summary"]["scope_closure_detail"]
    assert payload["summary"]["scope_closure_transporter_manual_review_subcheck_count"] == 5
    assert payload["summary"]["scope_closure_transporter_direct_binding_or_kcal_confirmation_required_count"] == 1
    assert "scope_closure_general_claim_blocker_count=1" in payload["summary"]["scope_closure_detail"]
    assert "scope_closure_authoritative_apply_allowed=False" in payload["summary"]["scope_closure_detail"]
    assert "scope_claim_boundary=allowed_scope_families=gpcr,ion_channel,kinase" in payload["summary"]["scope_closure_detail"]
    assert "blocked_claim_scopes=transporter_domain_promotion,general_protein_ligand_platform" in payload["summary"]["scope_closure_detail"]
    assert payload["summary"]["work_item_count"] == 2
    assert payload["rows"][0]["work_item_id"] == "scope_breadth.transporter.AQP1.core_binder_01"
    assert "review_only_or_functional_surrogate" in payload["rows"][0]["observed"]
    assert "manual_review_subchecks=direct_binding_or_claim_safe_kcal_confirmed=false;ligand_identity_confirmed=false" in payload["rows"][0]["observed"]
    assert "candidate_ligand_id=chembl_chembl195380" in payload["rows"][0]["observed"]
    assert "candidate_reference_binding_kcal_mol=-7.5970" in payload["rows"][0]["observed"]
    assert "candidate_source=chembl_activity::CHEMBL195380::IC50_2700.0_nM::source_CHEMBL5230131" in payload["rows"][0]["observed"]
    assert "blocker_class=direct_binding_evidence_missing" in payload["rows"][0]["observed"]
    assert "blocks transporter binder coverage" in payload["rows"][0]["observed"]
    assert payload["rows"][1]["work_item_id"] == "scope_breadth.general_protein_ligand.explicit_general_platform_flag"


def test_execution_backlog_scope_deferred_items_do_not_block_backlog_clear() -> None:
    payload = mod.build_product_ai_architecture_execution_backlog(
        architecture_packet=_packet({"all_gaps_closed": True, "open_gap_count": 0}),
        training_data_packet=_packet({"production_training_data_ready": True}),
        checkpoint_work_order_packet=_packet({"checkpoint_preflight_ready": True}),
        scope_work_order_packet=_packet(
            {"scope_breadth_ready": False},
            [
                {
                    "domain": "transporter",
                    "observed": "p0_open=3",
                    "acceptance_criteria": "p0_open=0",
                    "next_action": "close AQP1 evidence",
                    "verification": "python3 tools/build_product_scope_breadth_contract.py",
                }
            ],
        ),
    )

    assert payload["summary"]["work_item_count"] == 1
    assert payload["summary"]["release_blocking_work_item_count"] == 0
    assert payload["summary"]["scope_deferred_work_item_count"] == 1
    assert payload["summary"]["backlog_clear"] is True
    assert payload["rows"][0]["release_blocker"] is False


def test_execution_backlog_cli_writes_outputs(tmp_path: Path) -> None:
    architecture = tmp_path / "architecture.json"
    training = tmp_path / "training.json"
    checkpoint = tmp_path / "checkpoint.json"
    scope = tmp_path / "scope.json"
    closure = tmp_path / "closure.json"
    architecture.write_text(json.dumps(_packet({"all_gaps_closed": False, "open_gap_count": 1})) + "\n", encoding="utf-8")
    training.write_text(
        json.dumps(
            _packet(
                {"production_training_data_ready": False},
                [{"check_id": "dataset", "status": "fail", "observed": "rows=0", "required": "rows", "next_action": "build dataset"}],
            )
        )
        + "\n",
        encoding="utf-8",
    )
    checkpoint.write_text(json.dumps(_packet({"checkpoint_preflight_ready": True})) + "\n", encoding="utf-8")
    scope.write_text(json.dumps(_packet({"scope_breadth_ready": True})) + "\n", encoding="utf-8")
    closure.write_text(json.dumps(_packet({"closure_checklist_ready": False})) + "\n", encoding="utf-8")
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    mod.main(
        [
            "--architecture-json",
            str(architecture),
            "--training-data-json",
            str(training),
            "--checkpoint-work-order-json",
            str(checkpoint),
            "--scope-work-order-json",
            str(scope),
        "--scope-closure-checklist-json",
        str(closure),
        "--force-receipt-json",
        str(tmp_path / "missing_force_receipt.json"),
        "--out-json",
        str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["work_item_count"] == 1
    assert "training_data.dataset" in out_csv.read_text(encoding="utf-8")
    assert "Product AI Architecture Execution Backlog" in out_md.read_text(encoding="utf-8")
