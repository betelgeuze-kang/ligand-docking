from __future__ import annotations

from tools.product.build_transporter_negative_control_operator_worksheet import (
    NEGATIVE_ITEM_IDS,
    _field_status,
    build_payload,
    merge_intake_export_with_template_rows,
)


def _negative_row(item_id: str, target_id: str, ligand_id: str, packet_step: str) -> dict[str, object]:
    return {
        "item_id": item_id,
        "target_id": target_id,
        "packet_step": packet_step,
        "review_row_id": f"transporter_review_{item_id}",
        "replacement_ligand_id": ligand_id,
        "replacement_smiles": "CC",
        "replacement_scaffold": "heuristic::test",
        "replacement_source": f"chembl::{ligand_id}",
        "replacement_reference_binding_kcal_mol": "",
        "negative_reference_binding_kcal_mol": "OPERATOR_FILL_EXACT_NEGATIVE_KCAL_OR_KEEP_BLOCKED",
        "negative_quantitative_value_required": True,
        "manual_ligand_identity_confirmed": "OPERATOR_FILL_TRUE_OR_FALSE",
        "manual_scaffold_confirmed": "OPERATOR_FILL_TRUE_OR_FALSE",
        "manual_source_provenance_confirmed": "OPERATOR_FILL_TRUE_OR_FALSE",
        "manual_split_meta_sync_confirmed": "OPERATOR_FILL_TRUE_OR_FALSE",
        "review_decision": "OPERATOR_FILL_APPROVE_FOR_DRAFT_OR_KEEP_BLOCKED",
        "authoritative_apply_requested": "OPERATOR_FILL_TRUE_OR_FALSE",
        "reviewer_notes": "",
    }


def test_transporter_negative_control_worksheet_exports_six_slots(tmp_path) -> None:
    rows = [
        _negative_row("AQP1.core_non_binder_01", "AQP1", "chembl_a", "core_non_binder_01"),
        _negative_row("AQP1.core_non_binder_02", "AQP1", "chembl_b", "core_non_binder_02"),
        _negative_row("AQP1.core_non_binder_03", "AQP1", "chembl_c", "core_non_binder_03"),
        _negative_row("GLUT1_4PYP.core_non_binder_01", "GLUT1_4PYP", "chembl_d", "core_non_binder_01"),
        _negative_row("GLUT1_4PYP.core_non_binder_02", "GLUT1_4PYP", "chembl_e", "core_non_binder_02"),
        _negative_row("GLUT1_4PYP.core_non_binder_03", "GLUT1_4PYP", "chembl_f", "core_non_binder_03"),
    ]
    payload = build_payload({"rows": rows}, intake_export_csv=tmp_path / "missing_intake.csv")
    summary = payload["summary"]
    assert summary["status"] == "transporter_negative_control_operator_worksheet_ready"
    assert summary["negative_control_row_count"] == len(NEGATIVE_ITEM_IDS)
    assert len(payload["intake_export_rows"]) == 6
    assert summary["operator_fill_pending_field_count"] > 0
    assert summary["documented_blocked_field_count"] == 0


def test_field_status_documented_blocked_when_primary_source_present_without_kcal() -> None:
    status = _field_status(
        "negative_reference_binding_kcal_mol",
        "KEEP_BLOCKED",
        reviewer_notes="PMID 27474162: inactive ChEMBL row, no quantitative kcal",
    )
    assert status == "documented_blocked"


def test_worksheet_preserves_existing_intake_notes_and_counts_documented_blocked(tmp_path) -> None:
    rows = [
        _negative_row("AQP1.core_non_binder_01", "AQP1", "chembl_a", "core_non_binder_01"),
        _negative_row("AQP1.core_non_binder_02", "AQP1", "chembl_b", "core_non_binder_02"),
        _negative_row("AQP1.core_non_binder_03", "AQP1", "chembl_c", "core_non_binder_03"),
        _negative_row("GLUT1_4PYP.core_non_binder_01", "GLUT1_4PYP", "chembl_d", "core_non_binder_01"),
        _negative_row("GLUT1_4PYP.core_non_binder_02", "GLUT1_4PYP", "chembl_e", "core_non_binder_02"),
        _negative_row("GLUT1_4PYP.core_non_binder_03", "GLUT1_4PYP", "chembl_f", "core_non_binder_03"),
    ]
    intake_csv = tmp_path / "intake.csv"
    intake_csv.write_text(
        "review_row_id,item_id,target_id,packet_step,replacement_ligand_id,replacement_smiles,replacement_scaffold,replacement_source,replacement_reference_binding_kcal_mol,negative_reference_binding_kcal_mol,manual_ligand_identity_confirmed,manual_scaffold_confirmed,manual_source_provenance_confirmed,manual_split_meta_sync_confirmed,review_decision,authoritative_apply_requested,reviewer_notes\n"
        "transporter_review_AQP1.core_non_binder_01,AQP1.core_non_binder_01,AQP1,core_non_binder_01,chembl_a,CC,heuristic::test,chembl::chembl_a,KEEP_BLOCKED,KEEP_BLOCKED,OPERATOR_FILL_TRUE_OR_FALSE,OPERATOR_FILL_TRUE_OR_FALSE,OPERATOR_FILL_TRUE_OR_FALSE,OPERATOR_FILL_TRUE_OR_FALSE,OPERATOR_FILL_APPROVE_FOR_DRAFT_OR_KEEP_BLOCKED,OPERATOR_FILL_TRUE_OR_FALSE,PMID 12345 inactive row\n",
        encoding="utf-8",
    )
    payload = build_payload({"rows": rows}, intake_export_csv=intake_csv)
    merged_row = payload["intake_export_rows"][0]
    assert "PMID 12345" in merged_row["reviewer_notes"]
    assert merged_row["negative_reference_binding_kcal_mol"] == "KEEP_BLOCKED"
    assert payload["summary"]["documented_blocked_field_count"] >= 2
    assert payload["summary"]["intake_preserved_row_count"] == 1


def test_merge_intake_export_with_template_rows_keeps_operator_notes() -> None:
    template_rows = [_negative_row("AQP1.core_non_binder_01", "AQP1", "chembl_a", "core_non_binder_01")]
    intake_rows = [
        {
            "item_id": "AQP1.core_non_binder_01",
            "reviewer_notes": "DOI 10.1000/example inactive evidence",
            "negative_reference_binding_kcal_mol": "KEEP_BLOCKED",
            "replacement_reference_binding_kcal_mol": "KEEP_BLOCKED",
        }
    ]
    merged, preserved = merge_intake_export_with_template_rows(template_rows, intake_rows)
    assert preserved == 1
    assert merged[0]["reviewer_notes"].startswith("DOI")
