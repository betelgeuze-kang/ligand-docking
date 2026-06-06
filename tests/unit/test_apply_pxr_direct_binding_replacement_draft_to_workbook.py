from __future__ import annotations

from tools.product import apply_pxr_direct_binding_replacement_draft_to_workbook as mod


def test_apply_pxr_direct_binding_replacement_draft_requires_balanced_ready_rows() -> None:
    rows = []
    for index in range(5):
        rows.append(
            {
                "packet": "core" if index < 2 else "ood",
                "packet_step": f"nonbinder_{index}",
                "replacement_ligand_id": f"weak_{index}",
                "replacement_is_binder": "0",
                "replacement_reference_binding_kcal_mol": "-6.9",
                "replacement_source": f"chembl_direct_binding::weak::{index}",
                "row_ready_for_apply": "yes",
                "required_missing_fields": "",
            }
        )
    rows.append(
        {
            "packet": "ood",
            "packet_step": "binder_0",
            "replacement_ligand_id": "strong_0",
            "replacement_is_binder": "1",
            "replacement_reference_binding_kcal_mol": "-10.5",
            "replacement_source": "chembl_direct_binding::strong::0",
            "row_ready_for_apply": "yes",
            "required_missing_fields": "",
        }
    )

    payload = mod.build_payload(
        draft_summary={"draft_ready": True, "blocked_row_count_after_draft": 0},
        draft_rows=rows,
    )

    summary = payload["summary"]
    assert summary["status"] == "pxr_direct_binding_replacement_authoritative_workbook_applied"
    assert summary["workbook_apply_ready"] is True
    assert summary["direct_binding_overlay_row_count"] == 6
    assert summary["nonbinder_weak_control_overlay_row_count"] == 5
    assert summary["binder_direct_overlay_row_count"] == 1
    assert summary["authoritative_replacement_fields_touched"] is True


def test_apply_pxr_direct_binding_replacement_draft_blocks_unbalanced_rows() -> None:
    rows = [
        {
            "packet_step": "binder_only",
            "replacement_ligand_id": "strong",
            "replacement_is_binder": "1",
            "replacement_reference_binding_kcal_mol": "-10.5",
            "replacement_source": "chembl_direct_binding::strong",
            "row_ready_for_apply": "yes",
            "required_missing_fields": "",
        }
        for _ in range(6)
    ]

    payload = mod.build_payload(
        draft_summary={"draft_ready": True, "blocked_row_count_after_draft": 0},
        draft_rows=rows,
    )

    assert payload["summary"]["workbook_apply_ready"] is False
    assert payload["summary"]["nonbinder_weak_control_overlay_row_count"] == 0
