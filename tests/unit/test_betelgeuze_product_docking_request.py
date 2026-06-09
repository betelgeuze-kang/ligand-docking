from __future__ import annotations

import json
from pathlib import Path

from betelgeuze_product.docking_request import build_docking_job_record, persist_docking_job_record, validate_docking_request


def test_docking_request_accepts_restricted_scope_but_keeps_execution_disabled() -> None:
    record = build_docking_job_record(
        {
            "request_type": "structure_analysis_ligand_docking",
            "family": "gpcr",
            "target_id": "ADRB2",
            "pdb_content": "ATOM      1  CA  GLY A   1      12.104  13.207  14.321  1.00 10.00           C\n",
            "ligands": [{"ligand_id": "lig_1", "smiles": "CCO"}],
        },
        job_id="job_001",
    )

    assert record["status"] == "accepted_fail_closed"
    assert record["validation_status"] == "pass"
    assert record["family"] == "gpcr"
    assert record["structure_source_kind"] == "pdb_content"
    assert record["ligand_count"] == 1
    assert record["structure_analysis_status"] == "structure_analysis_ready"
    assert record["structure_atom_count"] == 1
    assert record["structure_chain_count"] == 1
    assert record["execution_enabled"] is False
    assert record["docking_results_emitted"] is False
    assert record["production_ai_inference_subject_active"] is False
    assert record["production_ai_correction_applied"] is False
    assert record["production_ai_abstention_enforced"] is True
    assert record["production_ai_default_residual_mode"] == "shadow"
    assert record["production_ai_promotion_allowed"] is False
    assert record["production_ai_customer_facing_auto_correction_allowed"] is False
    assert record["production_ai_customer_facing_score_mutation_allowed"] is False
    assert record["production_ai_customer_facing_ranking_mutation_allowed"] is False
    assert record["production_ai_trained_checkpoint_count"] == 0
    assert record["production_ai_selected_sidecar_ready"] is False
    assert record["production_ai_selected_sidecar_missing_output_fields"] == ["delta_force"]
    assert "production checkpoint preflight is blocked" in record["production_ai_blocked_reason"]
    assert "production checkpoint preflight is blocked" in record["production_ai_abstention_reason"]
    assert "force-label evidence" in record["production_ai_what_would_change_decision"]
    assert record["scope_claim_guard_ready"] is True
    assert record["scope_claim_allowed_for_request"] is True
    assert record["scope_claim_status"] == "allowed_restricted_delivery_scope"
    assert record["allowed_scope_families"] == ["gpcr", "ion_channel", "kinase"]
    assert record["blocked_claim_scopes"] == [
        "transporter_domain_promotion",
        "pxr_domain_promotion",
        "general_protein_ligand_platform",
    ]
    assert record["general_platform_claim_allowed"] is False
    assert record["ai_decision_graph_trace_ready"] is True
    assert record["ai_decision_graph_ordered_path"] == [
        "structure_quality",
        "binding_site_context",
        "pose_generation_contract",
        "scoring_ranking_gate",
        "uncertainty_abstention_guard",
        "report_bundle_contract",
        "customer_report_ux",
    ]
    assert record["ai_decision_graph_node_count"] == 7
    assert record["ai_decision_graph_edge_count"] == 6
    assert record["ai_decision_graph_abstention_node_id"] == "uncertainty_abstention_guard"
    assert record["ai_decision_graph_current_node_id"] == "customer_report_ux"
    assert record["ai_decision_graph_trace"][0]["node_id"] == "structure_quality"
    assert record["ai_decision_graph_trace"][2]["node_id"] == "pose_generation_contract"
    assert record["ai_decision_graph_trace"][2]["executed"] is False
    assert record["ai_decision_graph_trace"][4]["abstained"] is True
    assert record["ai_decision_graph_edges"][0] == {
        "from_node": "structure_quality",
        "to_node": "binding_site_context",
        "status": "ready",
    }
    assert record["customer_report_explanation_ready"] is True
    assert record["customer_report_card_ready"] is True
    assert record["customer_report_delivery_contract_ready"] is True
    assert record["customer_report_evidence_binding_ready"] is True
    assert record["customer_report_required_block_count"] == 6
    assert record["customer_report_ready_block_count"] == 6
    assert record["customer_report_blocked_block_count"] == 0
    assert record["customer_report_section_count"] == 6
    assert record["customer_report_required_blocks"] == [
        "binding_site_explanation",
        "pose_comparison",
        "interaction_rationale",
        "uncertainty_narrative",
        "scope_claim_limit",
        "counterfactual_rescue_suggestion",
    ]
    assert record["customer_report_missing_blocks"] == []
    assert record["customer_report_primary_abstention_reason"] == record["production_ai_abstention_reason"]
    assert record["customer_report_what_would_change_decision"] == record["production_ai_what_would_change_decision"]
    assert record["customer_report_card"]["target_id"] == "ADRB2"
    assert record["customer_report_card"]["family"] == "gpcr"
    assert record["customer_report_card"]["production_ai_correction_applied"] is False
    assert record["customer_report_sections"][0]["section_id"] == "binding_site_explanation"
    assert any(
        section["section_id"] == "counterfactual_rescue_suggestion"
        and "force-label evidence" in section["narrative"]
        for section in record["customer_report_sections"]
    )
    assert record["status_snapshot_persisted"] is True
    assert record["status_snapshot"]["status"] == "accepted_fail_closed"
    assert record["status_snapshot"]["request_sha256"] == record["request_sha256"]
    assert record["progress_percent"] == 0.0
    assert record["progress_state"] == "ledger_intake_recorded"
    assert record["current_step"] == "contract_validation"
    assert record["worker_state"] == "not_started_fail_closed"
    assert record["queue_status"] == "queued_fail_closed"
    assert record["queue_position"] == 0
    assert record["max_retry_attempts"] == 3
    assert record["retry_policy"] == "operator_requested_retry_child_preserves_request_sha256_max_3"
    assert record["retry_limit_reached"] is False
    assert record["progress_percent_range_valid"] is True
    assert record["status_progress_contract_ready"] is True
    assert record["workflow_controls_ready"] is True
    assert record["workflow_control_links"]["self"] == "/product/docking/jobs/job_001"
    assert record["workflow_control_links"]["history"] == "/product/docking/jobs/job_001/history"
    assert record["workflow_control_links"]["cancel"] == "/product/docking/jobs/job_001/cancel"
    assert record["workflow_control_links"]["retry"] == "/product/docking/jobs/job_001/retry"
    assert record["workflow_allowed_actions"] == ["view_status", "view_history", "cancel", "retry"]
    assert record["workflow_disabled_actions"] == []
    assert record["workflow_next_customer_actions"] == record["workflow_allowed_actions"]
    assert record["status_transition_contract"]["current_status"] == "accepted_fail_closed"
    assert record["status_transition_contract"]["queue_status"] == "queued_fail_closed"
    assert record["status_transition_contract"]["fail_closed"] is True
    assert record["status_snapshot"]["queue_status"] == "queued_fail_closed"
    assert record["status_snapshot"]["status_progress_contract_ready"] is True
    assert record["job_retention_policy"] == "local_job_ledger_retain_90_days_minimum"
    assert record["job_retention_days"] == 90
    assert record["rerun_manifest_ready"] is True
    assert record["rerun_manifest"]["request_sha256"] == record["request_sha256"]
    assert record["reproducible_rerun_ready"] is True
    assert record["long_running_status_persistence_ready"] is True
    assert record["external_state_mutated"] is False


def test_docking_job_record_requires_customer_facing_permission_for_ai_subject() -> None:
    record = build_docking_job_record(
        {
            "request_type": "structure_analysis_ligand_docking",
            "family": "gpcr",
            "target_id": "ADRB2",
            "pdb_content": "ATOM      1  CA  GLY A   1      12.104  13.207  14.321  1.00 10.00           C\n",
            "ligands": [{"ligand_id": "lig_1", "smiles": "CCO"}],
        },
        job_id="job_ai_ready",
        residual_registry_packet={
            "summary": {
                "default_residual_mode": "production_guarded",
                "production_promotion_allowed": True,
                "trained_model_checkpoint_count": 1,
                "selected_sidecar_ready": True,
                "selected_sidecar_missing_output_fields": [],
            }
        },
    )

    assert record["production_ai_inference_subject_active"] is False
    assert record["production_ai_promotion_allowed"] is True
    assert record["production_ai_customer_facing_auto_correction_allowed"] is False
    assert record["production_ai_customer_facing_score_mutation_allowed"] is False
    assert record["production_ai_customer_facing_ranking_mutation_allowed"] is False
    assert record["production_ai_correction_applied"] is False
    assert record["production_ai_abstention_enforced"] is True
    assert record["production_ai_abstention_reason"] == "production_ai_inference_subject_not_active"
    assert record["ai_decision_graph_trace_ready"] is True
    assert record["ai_decision_graph_abstention_node_id"] == "uncertainty_abstention_guard"
    assert record["customer_report_explanation_ready"] is True
    assert record["customer_report_card_ready"] is True
    assert record["customer_report_ready_block_count"] == 6
    assert record["customer_report_card"]["production_ai_inference_subject_active"] is False
    assert record["execution_enabled"] is False
    assert record["docking_results_emitted"] is False


def test_docking_job_record_marks_ai_subject_only_when_customer_facing_permissions_are_ready() -> None:
    record = build_docking_job_record(
        {
            "request_type": "structure_analysis_ligand_docking",
            "family": "gpcr",
            "target_id": "ADRB2",
            "pdb_content": "ATOM      1  CA  GLY A   1      12.104  13.207  14.321  1.00 10.00           C\n",
            "ligands": [{"ligand_id": "lig_1", "smiles": "CCO"}],
        },
        job_id="job_ai_customer_ready",
        residual_registry_packet={
            "summary": {
                "default_residual_mode": "production_guarded",
                "production_promotion_allowed": True,
                "customer_facing_auto_correction_allowed": True,
                "customer_facing_score_mutation_allowed": True,
                "customer_facing_ranking_mutation_allowed": True,
                "trained_model_checkpoint_count": 1,
                "selected_sidecar_ready": True,
                "selected_sidecar_missing_output_fields": [],
            }
        },
    )

    assert record["production_ai_inference_subject_active"] is True
    assert record["production_ai_customer_facing_auto_correction_allowed"] is True
    assert record["production_ai_customer_facing_score_mutation_allowed"] is True
    assert record["production_ai_customer_facing_ranking_mutation_allowed"] is False
    assert record["production_ai_correction_applied"] is False
    assert record["production_ai_abstention_enforced"] is False
    assert record["production_ai_abstention_reason"] == ""
    assert record["production_ai_what_would_change_decision"] == ""
    assert record["ai_decision_graph_trace_ready"] is True
    assert record["ai_decision_graph_abstention_node_id"] == ""
    assert record["ai_decision_graph_trace"][4]["status"] == "ready"
    assert record["customer_report_primary_abstention_reason"] == ""
    assert record["customer_report_card_ready"] is True
    assert record["customer_report_card"]["production_ai_inference_subject_active"] is True
    assert record["customer_report_sections"][3]["section_id"] == "uncertainty_narrative"
    assert record["execution_enabled"] is False
    assert record["docking_results_emitted"] is False


def test_docking_job_record_allows_ranking_mutation_only_when_shadow_lock_is_released() -> None:
    record = build_docking_job_record(
        {
            "request_type": "structure_analysis_ligand_docking",
            "family": "gpcr",
            "target_id": "ADRB2",
            "pdb_content": "ATOM      1  CA  GLY A   1      12.104  13.207  14.321  1.00 10.00           C\n",
            "ligands": [{"ligand_id": "lig_1", "smiles": "CCO"}],
        },
        job_id="job_ai_ranking_unlocked",
        residual_registry_packet={
            "summary": {
                "default_residual_mode": "production_guarded",
                "production_promotion_allowed": True,
                "customer_facing_auto_correction_allowed": True,
                "customer_facing_score_mutation_allowed": True,
                "customer_facing_ranking_mutation_allowed": True,
                "trained_model_checkpoint_count": 1,
                "selected_sidecar_ready": True,
                "selected_sidecar_missing_output_fields": [],
            }
        },
        shadow_only_active_locked=False,
    )

    assert record["production_ai_inference_subject_active"] is True
    assert record["production_ai_customer_facing_ranking_mutation_allowed"] is True


def test_docking_request_blocks_scope_widening_and_missing_ligand_source() -> None:
    validation = validate_docking_request(
        {
            "family": "transporter",
            "target_id": "AQP1",
            "pdb_id": "1J4N",
            "ligands": [{"ligand_id": "lig_1"}],
        }
    )
    codes = {blocker["code"] for blocker in validation["blockers"]}

    assert validation["status"] == "fail"
    assert "scope_family_not_delivery_ready" in codes
    assert "ligand_source_missing" in codes


def test_docking_job_record_explains_blocked_scope_for_customer_report() -> None:
    record = build_docking_job_record(
        {
            "family": "transporter",
            "target_id": "AQP1",
            "pdb_id": "1J4N",
            "ligands": [{"ligand_id": "lig_1", "smiles": "CCO"}],
        },
        job_id="job_scope_blocked",
        scope_claim_guard_packet={
            "summary": {
                "closure_checklist_ready": True,
                "allowed_scope_families": ["gpcr", "ion_channel", "kinase"],
                "blocked_claim_scopes": [
                    "transporter_domain_promotion",
                    "pxr_domain_promotion",
                    "general_protein_ligand_platform",
                ],
                "claim_blocked_domains": ["transporter", "pxr"],
                "general_platform_claim_allowed": False,
                "claim_boundary_detail": "allowed_scope_families=gpcr,ion_channel,kinase",
                "next_required_step": "Close transporter/PXR scientific rows first.",
            }
        },
    )

    assert record["status"] == "blocked_contract_validation"
    assert record["scope_claim_allowed_for_request"] is False
    assert record["scope_claim_status"] == "blocked_scope_family_not_delivery_ready"
    assert record["blocked_claim_scopes"] == [
        "transporter_domain_promotion",
        "pxr_domain_promotion",
        "general_protein_ligand_platform",
    ]
    assert record["claim_blocked_domains"] == ["transporter", "pxr"]
    assert record["ai_decision_graph_trace_ready"] is True
    assert record["ai_decision_graph_trace"][4]["evidence"]["scope_claim_allowed_for_request"] is False
    assert record["customer_report_primary_abstention_reason"] == record["production_ai_abstention_reason"]
    assert "force-label evidence" in record["customer_report_what_would_change_decision"]
    assert record["customer_report_card"]["scope_claim_allowed_for_request"] is False
    assert any(
        section["section_id"] == "scope_claim_limit"
        and "outside the restricted delivery scope" in section["narrative"]
        for section in record["customer_report_sections"]
    )


def test_docking_request_blocks_duplicate_ligands_and_multiple_structure_sources() -> None:
    validation = validate_docking_request(
        {
            "family": "kinase",
            "target_id": "ABL1",
            "pdb_id": "2HYY",
            "pdb_path": "local.pdb",
            "ligands": [{"ligand_id": "dup", "smiles": "CCO"}, {"ligand_id": "dup", "smiles": "CCC"}],
        }
    )
    codes = {blocker["code"] for blocker in validation["blockers"]}

    assert validation["status"] == "fail"
    assert "multiple_structure_sources" in codes
    assert "duplicate_ligand_ids" in codes


def test_persist_docking_job_record_writes_local_ledger(tmp_path: Path) -> None:
    record = build_docking_job_record(
        {
            "family": "ion_channel",
            "target_id": "TRPV1",
            "mmcif_path": "trpv1.cif",
            "ligands": [{"ligand_id": "cap", "compound_id": "CHEMBL123"}],
        },
        job_id="job_ledger",
    )

    out_path = persist_docking_job_record(record, tmp_path)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert payload["job_id"] == "job_ledger"
    assert payload["status"] == "accepted_fail_closed"
    assert payload["heavy_artifact_policy"] == "manifest_first_externalize_before_delete"
    assert payload["rerun_manifest_ready"] is True
    assert payload["status_snapshot_persisted"] is True
