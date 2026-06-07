from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_product_scope_breadth_closure_checklist as mod


ROOT = Path(__file__).resolve().parents[2]


def _transporter() -> dict[str, object]:
    return {
        "summary": {
            "candidate_row_count": 3,
            "candidate_ready_for_apply_count": 0,
            "negative_value_review_required_count": 1,
        },
        "rows": [
            {
                "item_id": "AQP1.core_binder_01",
                "candidate_mode": "functional_quantitative_surrogate_review_only",
                "required_missing_fields": "",
                "manual_review_blockers": "review_only_or_functional_surrogate;manual_ligand_identity_and_scaffold_confirmation_required",
                "candidate_ready_for_apply": False,
                "slot_triage_bucket": "functional_quantitative_only_direct_gap_open",
                "packet_step": "core_binder_01",
            },
            {
                "item_id": "GLUT1_4PYP.core_binder_03",
                "candidate_mode": "direct_quantitative_replacement_candidate",
                "required_missing_fields": "",
                "manual_review_blockers": "manual_ligand_identity_and_scaffold_confirmation_required",
                "candidate_ready_for_apply": False,
                "slot_triage_bucket": "candidate_assignment_required_from_local_pool",
                "packet_step": "core_binder_03",
                "replacement_ligand_id": "bindingdb_50010273",
                "replacement_reference_binding_kcal_mol": "-9.5497",
                "replacement_source": "bindingdb_affinity::50010273::KD_100.0_nM::source_1956039",
                "replacement_scaffold": "heuristic::polyoxygenated_macrocycle",
                "candidate_activity_type": "KD",
                "candidate_activity_value": "100.0",
                "candidate_activity_units": "nM",
            },
            {
                "item_id": "GLUT1_4PYP.core_non_binder_01",
                "candidate_mode": "inactive_nonquantitative_replacement_candidate_requires_negative_value_review",
                "required_missing_fields": "replacement_reference_binding_kcal_mol",
                "manual_review_blockers": "negative_quantitative_value_required;manual_ligand_identity_and_scaffold_confirmation_required",
                "candidate_ready_for_apply": False,
                "slot_triage_bucket": "candidate_assignment_required_from_local_pool",
                "packet_step": "core_non_binder_01",
            },
        ],
    }


def _pxr() -> dict[str, object]:
    return {
        "summary": {"reconciled_blocked_row_count": 1, "claim_safe_quantitative_ready_count": 0},
        "rows": [
            {
                "packet_step": "ood_fit_binder_01",
                "candidate_name": "bexarotene",
                "reconciliation_status": "capture_or_workbook_present_but_authoritative_apply_blocked",
                "readiness_missing_fields": "replacement_reference_binding_kcal_mol",
                "fail_closed_blockers": "claim_safe_quantitative_value_missing",
                "request_mode": "exact_human_pxr_quantitative_binder_value_required",
                "readiness_ready_for_apply": False,
            }
        ],
    }


def _general() -> dict[str, object]:
    return {
        "summary": {
            "blocker_count": 2,
            "allowed_scope_families": ["gpcr", "ion_channel", "kinase"],
            "missing_domains": ["transporter", "pxr"],
        },
        "rows": [
            {
                "check_id": "domain_ready.transporter",
                "check_type": "breadth_domain",
                "release_blocker": True,
                "current_value": "blocked",
                "required_value": "ready",
                "next_action": "finish transporter",
            },
            {
                "check_id": "api_surface_ready",
                "check_type": "product_surface",
                "release_blocker": False,
                "current_value": "True",
                "required_value": "True",
                "next_action": "keep green",
            },
        ],
    }


def test_product_scope_breadth_closure_checklist_merges_science_and_claim_gate_rows() -> None:
    payload = mod.build_payload(
        transporter_workbook_payload=_transporter(),
        pxr_reconciliation_payload=_pxr(),
        general_blocker_payload=_general(),
    )

    summary = payload["summary"]
    assert summary["checklist_row_count"] == 5
    assert summary["transporter_row_count"] == 3
    assert summary["transporter_candidate_ready_for_apply_count"] == 0
    assert summary["transporter_negative_value_review_required_count"] == 1
    assert summary["pxr_reconciled_blocked_row_count"] == 1
    assert summary["general_claim_blocker_count"] == 2
    assert summary["field_missing_row_count"] == 2
    assert summary["manual_review_blocked_row_count"] == 5
    assert summary["manual_review_subcheck_count"] == 14
    assert summary["transporter_manual_review_subcheck_count"] == 14
    assert summary["transporter_identity_scaffold_confirmation_required_count"] == 3
    assert summary["transporter_direct_binding_or_kcal_confirmation_required_count"] == 1
    assert summary["transporter_negative_quantitative_confirmation_required_count"] == 1
    assert summary["ready_for_apply_count"] == 0
    assert summary["blocker_class_counts"]["direct_binding_evidence_missing"] == 1
    assert summary["blocker_class_counts"]["exact_negative_quantitative_value_missing"] == 1
    assert summary["blocker_class_counts"]["exact_human_pxr_quantitative_value_missing"] == 1
    assert summary["blocker_class_counts"]["scientific_domain_gate_not_ready"] == 1
    assert summary["transporter_direct_binding_missing_count"] == 1
    assert summary["transporter_negative_quantitative_missing_count"] == 1
    assert summary["pxr_quantitative_missing_count"] == 1
    assert summary["general_claim_gate_blocker_count"] == 1
    assert summary["allowed_scope_families"] == ["gpcr", "ion_channel", "kinase"]
    assert summary["allowed_scope_family_count"] == 3
    assert summary["claim_blocked_domains"] == ["transporter", "pxr"]
    assert summary["blocked_claim_scope_count"] == 3
    assert summary["blocked_claim_scopes"] == [
        "transporter_domain_promotion",
        "pxr_domain_promotion",
        "general_protein_ligand_platform",
    ]
    assert "allowed_scope_families=gpcr,ion_channel,kinase" in summary["claim_boundary_detail"]
    assert "general_platform_claim_allowed=False" in summary["claim_boundary_detail"]
    claim_rows = {row["claim_scope"]: row for row in summary["claim_boundary_matrix"]}
    assert claim_rows["current_restricted_delivery_scope"]["claim_status"] == "allowed"
    assert "gpcr,ion_channel,kinase" in claim_rows["current_restricted_delivery_scope"]["allowed_wording"]
    assert claim_rows["transporter_domain_promotion"]["claim_status"] == "blocked"
    assert "current_direct_binding_missing=1" in claim_rows["transporter_domain_promotion"]["required_evidence_to_expand"]
    assert claim_rows["pxr_domain_promotion"]["claim_status"] == "blocked"
    assert "current_pxr_reconciled_blocked_rows=1" in claim_rows["pxr_domain_promotion"]["required_evidence_to_expand"]
    assert claim_rows["general_protein_ligand_platform"]["claim_status"] == "blocked"
    assert "missing_domains=transporter,pxr" in claim_rows["general_protein_ligand_platform"]["required_evidence_to_expand"]
    assert summary["first_scientific_blocker"] == "AQP1.core_binder_01"
    assert summary["scope_promotion_allowed"] is False
    assert payload["rows"][0]["domain"] == "transporter"
    assert payload["rows"][0]["blocker_class"] == "direct_binding_evidence_missing"
    assert "transporter binder coverage" in payload["rows"][0]["customer_claim_impact"]
    assert "direct-binding" in payload["rows"][0]["acceptance_criteria"]
    assert "build_transporter_manual_review_intake_template.py" in payload["rows"][0]["verification_command"]
    assert "product/build_transporter_blocker_capture_sheet.py" in payload["rows"][0]["verification_command"]
    assert "build_product_scope_breadth_work_order.py" in payload["rows"][0]["verification_command"]
    assert "build_product_ai_architecture_execution_backlog.py" in payload["rows"][0]["verification_command"]
    assert payload["rows"][0]["verification_command"].index("build_product_ai_architecture_execution_backlog.py") < payload[
        "rows"
    ][0]["verification_command"].index("build_product_ai_architecture_gap_closure.py")
    assert "transporter_manual_review_intake_template_current.json" in payload["rows"][0]["source_artifact"]
    direct_candidate = payload["rows"][1]
    assert direct_candidate["blocker_class"] == "manual_identity_scaffold_confirmation_required"
    assert direct_candidate["candidate_ligand_id"] == "bindingdb_50010273"
    assert direct_candidate["candidate_reference_binding_kcal_mol"] == "-9.5497"
    assert direct_candidate["candidate_activity_signal"] == "KD=100.0nM"
    assert direct_candidate["manual_review_subcheck_count"] == 4
    assert "ligand_identity_confirmed=false" in direct_candidate["manual_review_subchecks"]
    assert "split_meta_synchronization_confirmed=false" in direct_candidate["manual_review_subchecks"]
    assert payload["rows"][3]["domain"] == "pxr"
    assert payload["rows"][3]["blocker_class"] == "exact_human_pxr_quantitative_value_missing"
    assert "Exact human NR1I2/PXR" in payload["rows"][3]["acceptance_criteria"]
    assert "build_pxr_blocked_evidence_request_packet.py" in payload["rows"][3]["verification_command"]
    assert "build_pxr_exact_evidence_review_intake_template.py" in payload["rows"][3]["verification_command"]
    assert "build_product_scope_breadth_work_order.py" in payload["rows"][3]["verification_command"]
    assert "pxr_exact_evidence_review_intake_template_current.json" in payload["rows"][3]["source_artifact"]
    assert payload["rows"][4]["item_id"] == "domain_ready.transporter"
    assert payload["rows"][4]["blocker_class"] == "scientific_domain_gate_not_ready"
    assert "build_product_scope_breadth_work_order.py" in payload["rows"][4]["verification_command"]


def test_product_scope_breadth_closure_checklist_cli_writes_outputs(tmp_path: Path) -> None:
    transporter = tmp_path / "transporter.json"
    pxr = tmp_path / "pxr.json"
    general = tmp_path / "general.json"
    out_json = tmp_path / "checklist.json"
    out_csv = tmp_path / "checklist.csv"
    out_md = tmp_path / "checklist.md"
    transporter.write_text(json.dumps(_transporter()), encoding="utf-8")
    pxr.write_text(json.dumps(_pxr()), encoding="utf-8")
    general.write_text(json.dumps(_general()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "tools/build_product_scope_breadth_closure_checklist.py",
            "--transporter-workbook-json",
            str(transporter),
            "--pxr-reconciliation-json",
            str(pxr),
            "--general-blocker-json",
            str(general),
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

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["closure_checklist_ready"] is True
    assert "blocker_class" in out_csv.read_text(encoding="utf-8")
    md = out_md.read_text(encoding="utf-8")
    assert "Product Scope Breadth Closure Checklist" in md
    assert "Claim Boundary Matrix" in md
