from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_transporter_manual_review_intake_template as mod


ROOT = Path(__file__).resolve().parents[2]


def _workbook() -> dict[str, object]:
    return {
        "summary": {
            "candidate_workbook_ready": True,
            "candidate_row_count": 3,
            "candidate_ready_for_manual_review_count": 3,
        },
        "rows": [
            {
                "priority": "1",
                "target_id": "AQP1",
                "target_reference_id": "AQP1_TRANSPORT_BLIND",
                "item_id": "AQP1.core_binder_01",
                "packet_step": "core_binder_01",
                "slot_triage_bucket": "functional_quantitative_only_direct_gap_open",
                "candidate_mode": "functional_quantitative_surrogate_review_only",
                "replacement_ligand_id": "chembl_a",
                "replacement_is_binder": "1",
                "replacement_reference_binding_kcal_mol": "-7.0",
                "replacement_source": "chembl::a",
                "replacement_smiles": "CC",
                "replacement_scaffold": "heuristic::acyclic_2c",
                "manual_review_blockers": "review_only_or_functional_surrogate;manual_ligand_identity_and_scaffold_confirmation_required",
                "candidate_ready_for_manual_review": True,
            },
            {
                "priority": "2",
                "target_id": "GLUT1_4PYP",
                "target_reference_id": "GLUT1_TRANSPORT_BLIND",
                "item_id": "GLUT1_4PYP.core_binder_03",
                "packet_step": "core_binder_03",
                "slot_triage_bucket": "candidate_assignment_required_from_local_pool",
                "candidate_mode": "direct_quantitative_replacement_candidate",
                "replacement_ligand_id": "bindingdb_b",
                "replacement_is_binder": "1",
                "replacement_reference_binding_kcal_mol": "-9.0",
                "replacement_source": "bindingdb::b",
                "replacement_smiles": "CCC",
                "replacement_scaffold": "heuristic::acyclic_3c",
                "manual_review_blockers": "manual_ligand_identity_and_scaffold_confirmation_required",
                "candidate_ready_for_manual_review": True,
            },
            {
                "priority": "3",
                "target_id": "GLUT1_4PYP",
                "target_reference_id": "GLUT1_TRANSPORT_BLIND",
                "item_id": "GLUT1_4PYP.core_non_binder_01",
                "packet_step": "core_non_binder_01",
                "slot_triage_bucket": "candidate_assignment_required_from_local_pool",
                "candidate_mode": "inactive_nonquantitative_replacement_candidate_requires_negative_value_review",
                "replacement_ligand_id": "chembl_neg",
                "replacement_is_binder": "0",
                "replacement_reference_binding_kcal_mol": "",
                "replacement_source": "chembl::neg",
                "replacement_smiles": "CCCC",
                "replacement_scaffold": "heuristic::acyclic_4c",
                "required_missing_fields": "replacement_reference_binding_kcal_mol",
                "manual_review_blockers": "negative_quantitative_value_required;manual_ligand_identity_and_scaffold_confirmation_required",
                "candidate_ready_for_manual_review": True,
            },
        ],
    }


def _p0_evidence_acquisition() -> dict[str, object]:
    return {
        "summary": {"evidence_acquisition_packet_ready": True},
        "rows": [
            {
                "target_id": "AQP1",
                "packet_step": "core_binder_01",
                "replacement_ligand_id": "aqp1_bacopaside_ii_review_seed",
                "replacement_is_binder": "1",
                "required_missing_fields": "replacement_reference_binding_kcal_mol",
                "request_mode": "exact_target_pair_quantitative_binder_kcal_required",
                "evidence_state": "staged_non_authoritative_binder_missing_reference_kcal",
                "source_signal": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
                "claim_safe_step_ready": False,
                "authoritative_apply_allowed": False,
                "scope_promotion_allowed": False,
            }
        ],
    }


def _aqp1_workbook() -> dict[str, object]:
    return {
        "workbook_rows": [
            {
                "packet_step": "core_binder_01",
                "replacement_ligand_id": "aqp1_bacopaside_ii_review_seed",
                "replacement_is_binder": "1",
                "replacement_reference_binding_kcal_mol": "",
                "replacement_source": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
                "replacement_role": "far_ood_eval",
                "replacement_smiles": "CC(C)=CC1COC23CC4(CO2)C3C1(C)O",
                "replacement_scaffold": "C1CCC(OC2CCOC2)OC1",
                "required_missing_fields": "replacement_reference_binding_kcal_mol",
            }
        ]
    }


def test_transporter_manual_review_intake_template_prefills_review_requirements() -> None:
    payload = mod.build_payload(candidate_workbook_packet=_workbook())

    summary = payload["summary"]
    rows = {row["item_id"]: row for row in payload["rows"]}
    assert summary["manual_review_intake_ready"] is True
    assert summary["manual_review_template_row_count"] == 3
    assert summary["unique_review_row_id_count"] == 3
    assert summary["unique_review_row_ids_ready"] is True
    assert summary["direct_binding_evidence_required_count"] == 1
    assert summary["negative_quantitative_value_required_count"] == 1
    assert summary["manual_confirmation_required_count"] == 3
    assert summary["review_decision_placeholder_count"] == 3
    assert summary["first_review_item_id"] == "AQP1.core_binder_01"
    assert summary["first_review_target_id"] == "AQP1"
    assert summary["first_review_candidate_ligand_id"] == "chembl_a"
    assert summary["first_review_direct_binding_evidence_required"] is True
    assert summary["first_review_direct_binding_source_url_or_doi"] == mod.DIRECT_BINDING_PLACEHOLDER
    assert summary["first_review_review_decision"] == mod.REVIEW_DECISION_PLACEHOLDER
    assert summary["first_review_authoritative_apply_requested"] == mod.TRUE_FALSE_PLACEHOLDER
    assert "manual_ligand_identity_confirmation" in summary["first_review_review_requirements"]
    assert rows["AQP1.core_binder_01"]["direct_binding_source_url_or_doi"] == mod.DIRECT_BINDING_PLACEHOLDER
    assert rows["AQP1.core_binder_01"]["review_row_id"].startswith("transporter_review_")
    assert len(rows["AQP1.core_binder_01"]["source_row_fingerprint"]) == 64
    assert rows["AQP1.core_binder_01"]["negative_reference_binding_kcal_mol"] == ""
    assert rows["GLUT1_4PYP.core_non_binder_01"]["negative_reference_binding_kcal_mol"] == mod.NEGATIVE_VALUE_PLACEHOLDER
    assert rows["GLUT1_4PYP.core_binder_03"]["direct_binding_source_url_or_doi"] == ""
    assert all(row["authoritative_apply_allowed"] is False for row in payload["rows"])


def test_transporter_manual_review_intake_template_overlays_p0_next_slot_identity() -> None:
    payload = mod.build_payload(
        candidate_workbook_packet=_workbook(),
        p0_evidence_acquisition_packet=_p0_evidence_acquisition(),
        aqp1_workbook_packet=_aqp1_workbook(),
    )

    summary = payload["summary"]
    rows = {row["item_id"]: row for row in payload["rows"]}
    aqp1 = rows["AQP1.core_binder_01"]
    assert summary["manual_review_intake_ready"] is True
    assert summary["p0_slot_overlay_row_count"] == 1
    assert summary["p0_slot_overlay_candidate_changed_count"] == 1
    assert summary["p0_slot_overlay_first_item_id"] == "AQP1.core_binder_01"
    assert summary["p0_slot_overlay_first_candidate_ligand_id"] == "aqp1_bacopaside_ii_review_seed"
    assert summary["p0_slot_overlay_first_source"] == "https://pubmed.ncbi.nlm.nih.gov/27474162/"
    assert summary["first_review_candidate_ligand_id"] == "aqp1_bacopaside_ii_review_seed"
    assert summary["first_review_replacement_source"] == "https://pubmed.ncbi.nlm.nih.gov/27474162/"
    assert summary["first_review_replacement_reference_binding_kcal_mol"] == ""
    assert summary["first_review_p0_slot_overlay_required_missing_fields"] == (
        "replacement_reference_binding_kcal_mol"
    )
    assert summary["first_review_p0_slot_overlay_claim_safe_step_ready"] is False
    assert summary["first_review_p0_slot_overlay_authoritative_apply_allowed"] is False
    assert summary["first_review_p0_slot_overlay_scope_promotion_allowed"] is False
    assert aqp1["replacement_ligand_id"] == "aqp1_bacopaside_ii_review_seed"
    assert aqp1["replacement_source"] == "https://pubmed.ncbi.nlm.nih.gov/27474162/"
    assert aqp1["replacement_smiles"] == "CC(C)=CC1COC23CC4(CO2)C3C1(C)O"
    assert aqp1["replacement_reference_binding_kcal_mol"] == ""
    assert aqp1["direct_binding_source_url_or_doi"] == mod.DIRECT_BINDING_PLACEHOLDER
    assert aqp1["p0_slot_overlay_applied"] is True
    assert aqp1["p0_slot_overlay_candidate_original"] == "chembl_a"
    assert aqp1["p0_slot_overlay_required_missing_fields"] == "replacement_reference_binding_kcal_mol"
    assert aqp1["p0_slot_overlay_authoritative_apply_allowed"] is False


def test_transporter_manual_review_intake_template_blocks_without_workbook() -> None:
    payload = mod.build_payload(candidate_workbook_packet={"summary": {"candidate_workbook_ready": False}})

    summary = payload["summary"]
    assert summary["manual_review_intake_ready"] is False
    assert "candidate_workbook_ready" in summary["blockers"]
    assert "manual_review_rows" in summary["blockers"]


def test_transporter_manual_review_intake_template_cli_writes_outputs(tmp_path: Path) -> None:
    workbook = tmp_path / "workbook.json"
    out_json = tmp_path / "review.json"
    out_csv = tmp_path / "review.csv"
    out_md = tmp_path / "review.md"
    workbook.write_text(json.dumps(_workbook()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "tools/build_transporter_manual_review_intake_template.py",
            "--candidate-workbook-json",
            str(workbook),
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

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["manual_review_intake_ready"] is True
    assert "review_row_id" in out_csv.read_text(encoding="utf-8")
    assert "review_decision" in out_csv.read_text(encoding="utf-8")
    assert "Transporter Manual Review Intake Template" in out_md.read_text(encoding="utf-8")
