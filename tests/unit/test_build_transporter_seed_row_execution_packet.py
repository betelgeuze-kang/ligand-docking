from __future__ import annotations

from tools import build_transporter_seed_row_execution_packet as mod


def test_build_transporter_seed_row_execution_packet() -> None:
    rows = mod.build_rows(
        seed_board={
            "rows": [
                {
                    "packet_step": "core_binder_01",
                    "target_id": "AQP1",
                    "wave": "first",
                    "promotion_class": "seed_now",
                    "source_anchor": "PMID 27474162",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
                    "blocker_link": "placeholder_packet_rows; workbook_seed_rows_empty",
                }
            ]
        },
        seed_packet={"summary": {"candidate_name": "bacopaside II", "required_seed_field_count": 5}},
        fill_draft={
            "summary": {"safe_prefill_field_count": 1},
            "rows": [
                {"field_name": "replacement_ligand_id", "suggested_value": "bacopaside II", "staged_fill_value": "", "reviewer_safe_now": "no", "field_status": "needs_curated_identifier", "note": "id"},
                {"field_name": "replacement_reference_binding_kcal_mol", "suggested_value": "", "staged_fill_value": "", "reviewer_safe_now": "no", "field_status": "needs_curated_binding", "note": "bind"},
                {"field_name": "replacement_source", "suggested_value": "PMID 27474162", "staged_fill_value": "PMID 27474162", "reviewer_safe_now": "yes", "field_status": "reviewer_safe_context", "note": "src"},
                {"field_name": "replacement_smiles", "suggested_value": "", "staged_fill_value": "", "reviewer_safe_now": "no", "field_status": "needs_curated_structure", "note": "smiles"},
                {"field_name": "replacement_scaffold", "suggested_value": "", "staged_fill_value": "", "reviewer_safe_now": "no", "field_status": "needs_curated_scaffold", "note": "scaf"},
            ],
        },
        sync_preview={
            "summary": {"safe_staged_field_count": 1, "unresolved_field_count": 4},
            "row": {"unresolved_fields": "replacement_ligand_id,replacement_reference_binding_kcal_mol,replacement_smiles,replacement_scaffold"},
        },
        workbook={
            "workbook_rows": [
                {
                    "packet_step": "core_binder_01",
                    "replacement_ligand_id": "",
                    "replacement_reference_binding_kcal_mol": "",
                    "replacement_source": "",
                    "replacement_smiles": "",
                    "replacement_scaffold": "",
                    "apply_reference_row": "yes",
                    "apply_split_row": "yes",
                    "apply_meta_row": "yes",
                }
            ]
        },
        ledger={
            "rows": [
                {
                    "proposed_packet_step": "core_binder_01",
                    "confidence": "medium",
                    "promotion_policy": "draft_first_wave_manual_review",
                    "anchor": "PMID 27474162",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
                    "potency_or_signal": "IC50 18 uM",
                    "caution": "functional only",
                    "assay_surface": "oocyte swelling",
                }
            ]
        },
        blocker={
            "summary": {"top_blocker_id": "placeholder_packet_rows", "top_blocker_signal": "placeholder_driven_rows=12; ready_for_apply_rows=0"},
            "rows": [
                {"blocker_id": "placeholder_packet_rows", "blocker_status": "blocked", "current_signal": "placeholder_driven_rows=12; ready_for_apply_rows=0", "next_action": "replace placeholder rows"},
                {"blocker_id": "workbook_seed_rows_empty", "blocker_status": "blocked", "current_signal": "ready_for_apply_rows=0", "next_action": "fill seed rows"},
            ],
        },
        packet_step="core_binder_01",
    )
    summary = mod.build_summary(
        seed_board={"rows": [{"packet_step": "core_binder_01", "target_id": "AQP1", "wave": "first", "promotion_class": "seed_now", "source_anchor": "PMID 27474162", "source_url": "https://pubmed.ncbi.nlm.nih.gov/27474162/", "triple_sync_required": "reference+split+meta"}]},
        seed_packet={"summary": {"candidate_name": "bacopaside II", "required_seed_field_count": 5}},
        fill_draft={"summary": {"safe_prefill_field_count": 1}},
        sync_preview={"summary": {"safe_staged_field_count": 1, "unresolved_field_count": 4}},
        workbook={"workbook_rows": [{"packet_step": "core_binder_01", "apply_reference_row": "yes", "apply_split_row": "yes", "apply_meta_row": "yes"}]},
        fill_queue={"summary": {"queue_count": 6}},
        ledger={"rows": [{"proposed_packet_step": "core_binder_01", "confidence": "medium"}]},
        blocker={"summary": {"top_blocker_id": "placeholder_packet_rows", "top_blocker_signal": "placeholder_driven_rows=12; ready_for_apply_rows=0"}},
        packet_step="core_binder_01",
        rows=rows,
    )

    assert summary["target_id"] == "AQP1"
    assert summary["packet_step"] == "core_binder_01"
    assert summary["safe_staged_field_count"] == 1
    assert summary["authoritative_apply_allowed"] is False
    assert rows[0]["field_name"] == "replacement_ligand_id"
    assert rows[2]["field_name"] == "replacement_source"
    assert rows[2]["stage_now"] == "yes"
    assert any(row["field_name"] == "blocker::placeholder_packet_rows" for row in rows)
    assert any(row["field_name"] == "evidence_anchor" for row in rows)
