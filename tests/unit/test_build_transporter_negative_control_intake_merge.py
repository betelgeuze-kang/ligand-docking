from __future__ import annotations

from tools.product.build_transporter_negative_control_intake_merge import build_payload, merge_intake_into_template


def test_intake_merge_patches_documented_blocked_row_into_template() -> None:
    template_packet = {
        "rows": [
            {
                "item_id": "AQP1.core_non_binder_01",
                "target_id": "AQP1",
                "packet_step": "core_non_binder_01",
                "review_row_id": "transporter_review_AQP1.core_non_binder_01",
                "replacement_ligand_id": "chembl_a",
                "replacement_reference_binding_kcal_mol": "",
                "negative_reference_binding_kcal_mol": "",
                "reviewer_notes": "",
            }
        ]
    }
    intake_rows = [
        {
            "item_id": "AQP1.core_non_binder_01",
            "replacement_reference_binding_kcal_mol": "KEEP_BLOCKED",
            "negative_reference_binding_kcal_mol": "KEEP_BLOCKED",
            "reviewer_notes": "PMID 12345 inactive ChEMBL row",
        }
    ]
    merged_rows, patched_fields, patched_rows = merge_intake_into_template(template_packet, intake_rows)
    assert patched_rows == 1
    assert patched_fields >= 2
    assert merged_rows[0]["reviewer_notes"].startswith("PMID")
    payload = build_payload(
        template_packet=template_packet,
        intake_rows=intake_rows,
        template_path="runs/transporter_manual_review_intake_template_current.json",
        intake_path="runs/transporter_negative_control_operator_intake_export_current.csv",
    )
    assert payload["summary"]["documented_blocked_field_count"] >= 2
