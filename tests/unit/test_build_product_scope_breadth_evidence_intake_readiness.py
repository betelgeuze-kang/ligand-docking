from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_product_scope_breadth_evidence_intake_readiness as mod


ROOT = Path(__file__).resolve().parents[2]


def _binding_fields(domain: str, item_id: str, evidence_type: str) -> dict[str, object]:
    if domain == "transporter":
        review_template = "runs/transporter_manual_review_intake_template_current.json"
        apply_gate = "runs/transporter_binder_promotion_gate_current.json"
        command = "python3 tools/build_transporter_manual_review_intake_template.py"
    elif domain == "pxr":
        review_template = "runs/pxr_exact_evidence_review_intake_template_current.json"
        apply_gate = "runs/pxr_blocked_row_promotion_gate_current.json"
        command = "python3 tools/build_pxr_exact_evidence_review_intake_template.py"
    else:
        review_template = "runs/general_protein_ligand_claim_blocker_packet_current.json"
        apply_gate = "runs/product_scope_breadth_contract_current.json"
        command = "python3 tools/build_product_scope_breadth_contract.py"
    return {
        "required_evidence_type": evidence_type,
        "review_template_artifact": review_template,
        "apply_gate_artifact": apply_gate,
        "regeneration_commands": command,
        "operator_packet_binding_key": f"{domain}:{item_id}",
        "operator_packet_binding_ready": True,
    }


def _priority_packet(crosscheck_path: Path) -> dict[str, object]:
    return {
        "summary": {
            "priority_packet_ready": True,
            "queue_item_count": 4,
            "transporter_target_ready_for_promotion_ids": ["GLUT1"],
            "transporter_target_blocked_for_promotion_ids": ["AQP1"],
            "transporter_priority_target_ready_item_count": 1,
            "transporter_priority_target_blocked_item_count": 2,
            "transporter_primary_blocker_target_id": "AQP1",
            "transporter_primary_blocker_packet_step": "core_binder_01",
            "transporter_primary_blocker_candidate_name": "AqB013",
            "transporter_primary_blocker_signal": "target_ready_for_promotion_ids=GLUT1;target_blocked_for_promotion_ids=AQP1",
        },
        "rows": [
            {
                "priority": 1,
                "domain": "transporter",
                "item_id": "AQP1.core_binder_01",
                "target_id": "AQP1",
                "target_promotion_status": "target_blocked_for_promotion",
                "target_ready_for_promotion": False,
                "target_blocked_for_promotion": True,
                "candidate_or_check": "AqB013",
                "evidence_priority_bucket": "local_crosscheck_review_present_but_exact_quant_required",
                "local_crosscheck_paths": str(crosscheck_path),
                "source_artifact": "runs/transporter.json",
                **_binding_fields(
                    "transporter",
                    "AQP1.core_binder_01",
                    "exact_transporter_target_pair_quantitative_binder_kcal",
                ),
            },
            {
                "priority": 2,
                "domain": "pxr",
                "item_id": "ood_fit_binder_01",
                "target_id": "PXR",
                "target_promotion_status": "not_target_scored",
                "target_ready_for_promotion": False,
                "target_blocked_for_promotion": False,
                "candidate_or_check": "bexarotene",
                "evidence_priority_bucket": "external_primary_exact_evidence_required",
                "local_crosscheck_paths": "",
                "source_artifact": "runs/pxr.json",
                **_binding_fields(
                    "pxr",
                    "ood_fit_binder_01",
                    "exact_human_nr1i2_pxr_quantitative_value_with_source_and_target_match",
                ),
            },
            {
                "priority": 3,
                "domain": "transporter",
                "item_id": "GLUT1_4PYP.core_binder_02",
                "target_id": "GLUT1",
                "target_promotion_status": "target_ready_for_promotion",
                "target_ready_for_promotion": True,
                "target_blocked_for_promotion": False,
                "candidate_or_check": "glut1_placeholder_binder_02",
                "evidence_priority_bucket": "review_only_keep_blocked_until_direct_binding",
                "local_crosscheck_paths": "",
                "source_artifact": "runs/transporter.json",
                **_binding_fields(
                    "transporter",
                    "GLUT1_4PYP.core_binder_02",
                    "exact_direct_binding_kcal_or_keep_review_only_guardrail",
                ),
            },
            {
                "priority": 4,
                "domain": "general_protein_ligand",
                "item_id": "domain_ready.pxr",
                "target_id": "PXR",
                "target_promotion_status": "not_target_scored",
                "target_ready_for_promotion": False,
                "target_blocked_for_promotion": False,
                "candidate_or_check": "domain_ready.pxr",
                "evidence_priority_bucket": "claim_gate_waits_on_domain_evidence",
                "local_crosscheck_paths": "",
                "source_artifact": "runs/general.json",
                **_binding_fields(
                    "general_protein_ligand",
                    "domain_ready.pxr",
                    "domain_gate_green_and_explicit_claim_surface_update",
                ),
            },
        ],
    }


def _transporter_triage() -> dict[str, object]:
    return {
        "summary": {
            "triage_packet_ready": True,
            "operator_review_evidence_matrix_ready": True,
            "triage_row_count": 2,
            "claim_safe_local_evidence_ready_count": 0,
            "claim_safe_local_evidence_blocked_count": 2,
            "direct_binding_claim_blocked_count": 1,
            "negative_value_claim_blocked_count": 1,
            "top_claim_safe_blocker": "functional_assay_quantitative_but_not_direct_binding_claim_safe",
            "top_operator_next_verdict": "keep_functional_surrogate_review_only_until_direct_binding_source",
            "candidate_assignment_required_count": 1,
            "named_candidate_manual_match_required_count": 0,
            "functional_quantitative_only_direct_gap_open_count": 1,
            "review_only_direct_binding_gap_count": 0,
            "external_exact_candidate_required_count": 0,
            "local_crosscheck_can_close_slots_without_manual_assignment": False,
        },
        "rows": [
            {
                "item_id": "AQP1.core_binder_01",
                "slot_triage_bucket": "functional_quantitative_only_direct_gap_open",
                "direct_quantitative_record_count": 0,
                "functional_quantitative_record_count": 4,
                "not_active_nonquantitative_record_count": 1,
                "claim_safe_local_evidence_ready": False,
                "claim_safe_blocker": "functional_assay_quantitative_but_not_direct_binding_claim_safe",
                "operator_next_verdict": "keep_functional_surrogate_review_only_until_direct_binding_source",
                "best_evidence_source_file": "runs/life_science_skill_crosscheck/chembl_activity_aqp1.json",
                "best_evidence_activity_type": "IC50",
                "best_evidence_value": "20000",
                "best_evidence_units": "nM",
                "best_evidence_document_id": "CHEMBL_DOC_A",
            },
            {
                "item_id": "GLUT1_4PYP.core_binder_02",
                "slot_triage_bucket": "candidate_assignment_required_from_local_pool",
                "direct_quantitative_record_count": 2,
                "functional_quantitative_record_count": 5,
                "not_active_nonquantitative_record_count": 1,
                "claim_safe_local_evidence_ready": False,
                "claim_safe_blocker": "negative_or_inactive_row_missing_exact_quantitative_value",
                "operator_next_verdict": "fill_exact_negative_quantitative_value_or_keep_blocked",
            },
        ],
    }


def _transporter_candidate_workbook() -> dict[str, object]:
    return {
        "summary": {
            "candidate_workbook_ready": True,
            "candidate_row_count": 2,
            "candidate_ready_for_manual_review_count": 2,
            "candidate_ready_for_apply_count": 0,
            "blocked_review_only_count": 1,
            "negative_value_review_required_count": 1,
        },
        "rows": [],
    }


def _transporter_manual_review_intake() -> dict[str, object]:
    return {
        "summary": {
            "manual_review_intake_ready": True,
            "manual_review_template_row_count": 2,
            "direct_binding_evidence_required_count": 1,
            "negative_quantitative_value_required_count": 1,
            "review_decision_placeholder_count": 2,
            "first_review_row_id": "transporter_review_AQP1_core_binder_01",
            "first_review_item_id": "AQP1.core_binder_01",
            "first_review_target_id": "AQP1",
            "first_review_candidate_ligand_id": "aqp1_bacopaside_ii_review_seed",
            "first_review_replacement_source": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
            "first_review_replacement_reference_binding_kcal_mol": "",
            "first_review_direct_binding_evidence_required": True,
            "first_review_direct_binding_source_url_or_doi": (
                "OPERATOR_FILL_EXACT_DIRECT_BINDING_SOURCE_OR_KEEP_BLOCKED"
            ),
            "first_review_negative_quantitative_value_required": False,
            "first_review_negative_reference_binding_kcal_mol": "",
            "first_review_review_decision": "OPERATOR_FILL_APPROVE_FOR_DRAFT_OR_KEEP_BLOCKED",
            "first_review_authoritative_apply_requested": "",
            "first_review_manual_review_blockers": "replacement_reference_binding_kcal_mol",
            "first_review_review_requirements": "exact_transporter_target_pair_quantitative_binder_kcal",
            "first_review_p0_slot_overlay_required_missing_fields": "replacement_reference_binding_kcal_mol",
            "first_review_p0_slot_overlay_claim_safe_step_ready": False,
            "first_review_p0_slot_overlay_authoritative_apply_allowed": False,
            "first_review_p0_slot_overlay_scope_promotion_allowed": False,
        },
        "rows": [],
    }


def test_scope_breadth_evidence_intake_readiness_classifies_intake_lanes(tmp_path: Path) -> None:
    crosscheck = tmp_path / "bindingdb_aqp1_p29972.json"
    crosscheck.write_text(json.dumps({"activities": []}), encoding="utf-8")

    payload = mod.build_payload(
        priority_packet=_priority_packet(crosscheck),
        transporter_triage_packet=_transporter_triage(),
        transporter_candidate_workbook_packet=_transporter_candidate_workbook(),
        transporter_manual_review_intake_packet=_transporter_manual_review_intake(),
    )

    summary = payload["summary"]
    rows = payload["rows"]
    assert summary["intake_readiness_ready"] is True
    assert summary["local_crosscheck_triage_item_count"] == 1
    assert summary["local_crosscheck_intake_ready_count"] == 1
    assert summary["external_exact_evidence_required_count"] == 1
    assert summary["guardrail_item_count"] == 2
    assert summary["all_operator_packet_bindings_ready"] is True
    assert summary["operator_packet_binding_ready_count"] == 4
    assert summary["operator_packet_binding_missing_count"] == 0
    assert summary["next_operator_completion_item_id"] == "AQP1.core_binder_01"
    assert summary["next_operator_completion_target_id"] == "AQP1"
    assert summary["next_operator_completion_target_promotion_status"] == "target_blocked_for_promotion"
    assert summary["next_operator_completion_target_ready_for_promotion"] is False
    assert summary["next_operator_completion_target_blocked_for_promotion"] is True
    assert summary["next_operator_completion_domain"] == "transporter"
    assert summary["next_operator_completion_candidate_or_check"] == "AqB013"
    assert summary["next_operator_completion_intake_mode"] == "local_crosscheck_triage"
    assert summary["next_operator_completion_required_evidence_type"] == (
        "exact_transporter_target_pair_quantitative_binder_kcal"
    )
    assert summary["next_operator_completion_required_intake_columns"] == [
        "target_id",
        "candidate_ligand_id",
        "reference_binding_kcal_mol",
        "source_url_or_doi",
        "smiles",
        "scaffold",
        "evidence_type",
    ]
    assert summary["next_operator_completion_review_template_artifact"] == (
        "runs/transporter_manual_review_intake_template_current.json"
    )
    assert summary["next_operator_completion_operator_packet_binding_ready"] is True
    assert summary["next_operator_completion_transporter_claim_safe_blocker"] == (
        "functional_assay_quantitative_but_not_direct_binding_claim_safe"
    )
    assert summary["next_operator_completion_transporter_best_evidence_activity_type"] == "IC50"
    assert summary["transporter_target_ready_for_promotion_ids"] == ["GLUT1"]
    assert summary["transporter_target_blocked_for_promotion_ids"] == ["AQP1"]
    assert summary["transporter_priority_target_ready_item_count"] == 1
    assert summary["transporter_priority_target_blocked_item_count"] == 2
    assert summary["transporter_primary_blocker_target_id"] == "AQP1"
    assert summary["transporter_primary_blocker_packet_step"] == "core_binder_01"
    assert summary["transporter_primary_blocker_candidate_name"] == "AqB013"
    assert "target_blocked_for_promotion_ids=AQP1" in summary["transporter_primary_blocker_signal"]
    assert summary["transporter_triage_packet_ready"] is True
    assert summary["transporter_operator_review_evidence_matrix_ready"] is True
    assert summary["transporter_claim_safe_local_evidence_ready_count"] == 0
    assert summary["transporter_claim_safe_local_evidence_blocked_count"] == 2
    assert summary["transporter_direct_binding_claim_blocked_count"] == 1
    assert summary["transporter_negative_value_claim_blocked_count"] == 1
    assert summary["transporter_top_claim_safe_blocker"] == (
        "functional_assay_quantitative_but_not_direct_binding_claim_safe"
    )
    assert summary["transporter_candidate_assignment_required_count"] == 1
    assert summary["transporter_functional_quantitative_only_direct_gap_open_count"] == 1
    assert summary["transporter_candidate_workbook_ready"] is True
    assert summary["transporter_candidate_ready_for_manual_review_count"] == 2
    assert summary["transporter_candidate_ready_for_apply_count"] == 0
    assert summary["transporter_candidate_negative_value_review_required_count"] == 1
    assert summary["transporter_manual_review_intake_required"] is True
    assert summary["transporter_manual_review_intake_ready"] is True
    assert summary["transporter_manual_review_template_row_count"] == 2
    assert summary["transporter_manual_review_direct_binding_evidence_required_count"] == 1
    assert summary["transporter_manual_review_negative_quantitative_value_required_count"] == 1
    assert summary["transporter_manual_review_decision_placeholder_count"] == 2
    assert summary["first_review_item_id"] == "AQP1.core_binder_01"
    assert summary["first_review_candidate_ligand_id"] == "aqp1_bacopaside_ii_review_seed"
    assert summary["first_review_replacement_source"] == "https://pubmed.ncbi.nlm.nih.gov/27474162/"
    assert summary["first_review_replacement_reference_binding_kcal_mol"] == ""
    assert summary["first_review_direct_binding_evidence_required"] is True
    assert (
        summary["first_review_direct_binding_source_url_or_doi"]
        == "OPERATOR_FILL_EXACT_DIRECT_BINDING_SOURCE_OR_KEEP_BLOCKED"
    )
    assert summary["first_review_review_decision"] == "OPERATOR_FILL_APPROVE_FOR_DRAFT_OR_KEEP_BLOCKED"
    assert summary["first_review_p0_slot_overlay_required_missing_fields"] == (
        "replacement_reference_binding_kcal_mol"
    )
    assert summary["first_review_p0_slot_overlay_scope_promotion_allowed"] is False
    assert summary["scope_operator_transfer_manifest_ready"] is True
    assert summary["scope_operator_transfer_outbound_artifact_count"] == 10
    assert "runs/transporter_manual_review_intake_template_current.json" in summary[
        "scope_operator_transfer_outbound_artifacts"
    ]
    assert "runs/pxr_exact_evidence_review_intake_template_current.json" in summary[
        "scope_operator_transfer_outbound_artifacts"
    ]
    assert "readable local crosscheck payloads referenced by local_crosscheck_paths" in summary[
        "scope_operator_transfer_outbound_artifacts"
    ]
    assert summary["scope_operator_transfer_inbound_artifact_count"] == 4
    assert summary["scope_operator_transfer_first_return_artifact"] == (
        "completed runs/transporter_manual_review_intake_template_current.csv with OPERATOR_FILL placeholders resolved"
    )
    assert summary["scope_operator_transfer_acceptance_artifact"] == (
        "runs/product_scope_breadth_contract_current.json"
    )
    assert summary["scope_operator_transfer_acceptance_ready_key"] == "scope_breadth_ready"
    assert summary["scope_operator_transfer_next_acceptance_stage"] == "transporter_claim_acceptance"
    assert "build_transporter_manual_review_intake_template.py" in summary[
        "scope_operator_transfer_post_return_validation_command"
    ]
    assert rows[0]["target_id"] == "AQP1"
    assert rows[0]["target_promotion_status"] == "target_blocked_for_promotion"
    assert rows[0]["target_blocked_for_promotion"] is True
    assert rows[0]["evidence_intake_ready"] is True
    assert rows[0]["operator_packet_binding_ready"] is True
    assert rows[0]["review_template_artifact"] == "runs/transporter_manual_review_intake_template_current.json"
    assert rows[0]["apply_gate_artifact"] == "runs/transporter_binder_promotion_gate_current.json"
    assert rows[0]["local_crosscheck_payloads_ready"] is True
    assert rows[0]["transporter_slot_triage_bucket"] == "functional_quantitative_only_direct_gap_open"
    assert rows[0]["transporter_claim_safe_local_evidence_ready"] is False
    assert rows[0]["transporter_claim_safe_blocker"] == (
        "functional_assay_quantitative_but_not_direct_binding_claim_safe"
    )
    assert rows[0]["transporter_operator_next_verdict"] == (
        "keep_functional_surrogate_review_only_until_direct_binding_source"
    )
    assert rows[0]["transporter_best_evidence_activity_type"] == "IC50"
    assert rows[0]["transporter_functional_quantitative_record_count"] == 4
    assert "reference_binding_kcal_mol" in rows[0]["required_intake_columns"]
    assert rows[1]["intake_mode"] == "external_exact_source_required"
    assert rows[1]["external_exact_evidence_required"] is True
    assert rows[2]["target_id"] == "GLUT1"
    assert rows[2]["target_ready_for_promotion"] is True
    assert rows[2]["guardrail_ready"] is True
    assert rows[3]["intake_mode"] == "deferred_claim_gate"
    assert all(row["scope_promotion_allowed"] is False for row in rows)


def test_scope_breadth_evidence_intake_readiness_blocks_unreadable_local_payload(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"

    payload = mod.build_payload(
        priority_packet=_priority_packet(missing),
        transporter_triage_packet=_transporter_triage(),
        transporter_candidate_workbook_packet=_transporter_candidate_workbook(),
        transporter_manual_review_intake_packet=_transporter_manual_review_intake(),
    )

    summary = payload["summary"]
    first = payload["rows"][0]
    assert summary["intake_readiness_ready"] is False
    assert summary["local_crosscheck_unreadable_item_count"] == 1
    assert first["local_crosscheck_payloads_ready"] is False
    assert first["unreadable_local_payload_reasons"] == "missing"


def test_scope_breadth_evidence_intake_readiness_blocks_missing_operator_binding(tmp_path: Path) -> None:
    crosscheck = tmp_path / "bindingdb_aqp1_p29972.json"
    crosscheck.write_text(json.dumps({"activities": []}), encoding="utf-8")
    priority_packet = _priority_packet(crosscheck)
    priority_packet["rows"][0]["review_template_artifact"] = ""

    payload = mod.build_payload(
        priority_packet=priority_packet,
        transporter_triage_packet=_transporter_triage(),
        transporter_candidate_workbook_packet=_transporter_candidate_workbook(),
        transporter_manual_review_intake_packet=_transporter_manual_review_intake(),
    )

    summary = payload["summary"]
    first = payload["rows"][0]
    assert summary["intake_readiness_ready"] is False
    assert summary["all_operator_packet_bindings_ready"] is False
    assert summary["operator_packet_binding_missing_count"] == 1
    assert summary["top_unbound_item_id"] == "AQP1.core_binder_01"
    assert first["operator_packet_binding_ready"] is False


def test_scope_breadth_evidence_intake_readiness_cli_writes_outputs(tmp_path: Path) -> None:
    crosscheck = tmp_path / "chembl_activity_aqp1.json"
    crosscheck.write_text(json.dumps({"activities": []}), encoding="utf-8")
    priority = tmp_path / "priority.json"
    transporter_triage = tmp_path / "transporter_triage.json"
    candidate_workbook = tmp_path / "candidate_workbook.json"
    manual_review = tmp_path / "manual_review.json"
    out_json = tmp_path / "intake.json"
    out_csv = tmp_path / "intake.csv"
    out_md = tmp_path / "intake.md"
    priority.write_text(json.dumps(_priority_packet(crosscheck)), encoding="utf-8")
    transporter_triage.write_text(json.dumps(_transporter_triage()), encoding="utf-8")
    candidate_workbook.write_text(json.dumps(_transporter_candidate_workbook()), encoding="utf-8")
    manual_review.write_text(json.dumps(_transporter_manual_review_intake()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "tools/build_product_scope_breadth_evidence_intake_readiness.py",
            "--priority-json",
            str(priority),
            "--transporter-triage-json",
            str(transporter_triage),
            "--transporter-candidate-workbook-json",
            str(candidate_workbook),
            "--transporter-manual-review-intake-json",
            str(manual_review),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        cwd=ROOT,
        check=True,
    )

    summary = json.loads(out_json.read_text(encoding="utf-8"))["summary"]
    assert summary["intake_readiness_ready"] is True
    assert summary["transporter_triage_packet_ready"] is True
    assert summary["transporter_candidate_workbook_ready"] is True
    assert summary["transporter_manual_review_intake_ready"] is True
    assert summary["scope_operator_transfer_manifest_ready"] is True
    md = out_md.read_text(encoding="utf-8")
    assert "Product Scope Breadth Evidence Intake Readiness" in md
    assert "Operator Evidence Transfer Manifest" in md
    assert "next_operator_completion_target_id" in md
    assert "`AQP1`" in md
    assert "required_intake_columns" in out_csv.read_text(encoding="utf-8")
