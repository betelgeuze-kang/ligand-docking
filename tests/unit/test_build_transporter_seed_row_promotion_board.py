from __future__ import annotations

from tools import build_transporter_seed_row_promotion_board as mod


def test_build_transporter_seed_row_promotion_board_prioritizes_aqp1_first_wave_binders() -> None:
    payload = mod.build_payload(
        {
            "workbook_rows": [
                {
                    "packet_step": "core_binder_01",
                    "current_binder_label": "binder",
                    "current_ligand_id": "aqp1_placeholder_binder_01",
                    "required_missing_fields": "replacement_ligand_id,replacement_reference_binding_kcal_mol",
                },
                {
                    "packet_step": "core_non_binder_01",
                    "current_binder_label": "non_binder",
                    "current_ligand_id": "aqp1_placeholder_nonbinder_01",
                    "required_missing_fields": "replacement_ligand_id,replacement_reference_binding_kcal_mol",
                },
            ]
        },
        {
            "workbook_rows": [
                {
                    "packet_step": "core_binder_01",
                    "current_binder_label": "binder",
                    "current_ligand_id": "glut1_placeholder_binder_01",
                    "required_missing_fields": "replacement_ligand_id,replacement_reference_binding_kcal_mol",
                },
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "core_binder_01",
                    "candidate_name": "bacopaside II",
                    "source_anchor": "PMID 27474162",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
                    "current_review_bucket": "review_only_first_wave",
                    "promotion_blocker": "no_local_aqp1_binder_evidence_curated",
                    "next_required_action": "manual_curated_search_or_defer",
                    "potency_or_signal": "AQP1 water-channel IC50 18 uM",
                }
            ]
        },
        {
            "draft_rows": [
                {
                    "packet_step": "core_binder_01",
                    "candidate_name": "cytochalasin B",
                    "source_anchor": "PMID 27078104",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/27078104/",
                    "suggested_manual_verdict": "keep_review_only",
                    "promotion_blocker": "no_local_glut1_binder_evidence_curated",
                    "next_required_action": "manual_curated_search_or_defer",
                    "suggested_manual_decision_note": "Strong structural anchor",
                }
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "core_non_binder_01",
                    "label": "aqp1_placeholder_nonbinder_01",
                    "review_bucket": "review_only_negative_evidence",
                    "promotion_blocker": "no_quantitative_transporter_negative_evidence_curated",
                    "next_action": "manual_negative_evidence_review",
                    "notes": "keep review-only",
                }
            ]
        },
        {"negative_rows": []},
        {"summary": {"first_wave_target": "AQP1", "second_wave_target": "GLUT1"}},
        {"summary": {"top_blocker_id": "placeholder_packet_rows", "top_blocker_signal": "placeholder_driven_rows=12; ready_for_apply_rows=0"}},
    )
    assert payload["summary"]["seed_now_count"] == 1
    assert payload["summary"]["seed_after_aqp1_count"] == 1
    assert payload["summary"]["review_only_hold_count"] == 1
    assert payload["summary"]["aqp1_seed_surface_count"] == 1
    assert payload["summary"]["glut1_seed_surface_count"] == 1
    assert payload["rows"][0]["target_id"] == "AQP1"
    assert payload["rows"][0]["promotion_class"] == "seed_now"
    assert payload["rows"][0]["seed_packet_artifact"] == "runs/aqp1_first_seed_row_packet_current.md"
    assert payload["rows"][0]["fill_draft_artifact"] == "runs/aqp1_seed_row_fill_draft_current.md"
    assert payload["rows"][0]["sync_preview_artifact"] == "runs/aqp1_seed_row_sync_apply_preview_current.md"
    assert payload["rows"][1]["promotion_class"] == "seed_after_aqp1"
    assert payload["rows"][1]["seed_packet_artifact"] == "runs/glut1_second_wave_seed_row_packet_current.md"
    assert payload["rows"][1]["fill_draft_artifact"] == "runs/glut1_second_wave_seed_row_fill_draft_current.md"
    assert payload["rows"][1]["sync_preview_artifact"] == "runs/glut1_second_wave_seed_row_sync_apply_preview_current.md"
    assert payload["rows"][2]["promotion_class"] == "review_only_hold"
