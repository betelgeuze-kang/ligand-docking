from tools.product.build_ca2_conflict_replacement_shortlist import (
    REPLACEMENTS,
    apply_workbook_patch,
    build_payload,
    build_shortlist_rows,
)


def test_build_shortlist_rows_for_conflict_review_only() -> None:
    rows = build_shortlist_rows(
        [
            {"operator_review_bucket": "conflict_review", "packet_step": "core_non_binder_01", "packet": "core"},
            {"operator_review_bucket": "other", "packet_step": "ignored"},
        ]
    )
    assert len(rows) == 1
    assert rows[0]["primary_replacement_ligand_id"] == REPLACEMENTS["core_non_binder_01"]["primary_ligand_id"]
    assert rows[0]["replacement_status"] == "proposed_pending_verification"


def test_apply_workbook_patch_keeps_kcal_blank() -> None:
    shortlist = build_shortlist_rows(
        [{"operator_review_bucket": "conflict_review", "packet_step": "ood_non_binder_02", "packet": "ood"}]
    )
    patched = apply_workbook_patch(
        [{"packet_step": "ood_non_binder_02", "replacement_ligand_id": "ibuprofen", "notes": ""}],
        shortlist,
    )
    assert patched[0]["replacement_ligand_id"] == "benzoic_acid"
    assert patched[0]["replacement_reference_binding_kcal_mol"] == ""
    assert patched[0]["row_ready_for_apply"] == "no"


def test_build_payload_reports_conflict_count() -> None:
    payload = build_payload(
        {
            "rows": [
                {"operator_review_bucket": "conflict_review", "packet_step": step, "packet": "p"}
                for step in REPLACEMENTS
            ]
        },
        apply_patch=False,
    )
    assert payload["summary"]["conflict_row_count"] == len(REPLACEMENTS)
    assert payload["summary"]["status"] == "ca2_conflict_replacement_shortlist_ready"
