from __future__ import annotations

from tools.product import build_ca2_evidence_closure_commit_packet as mod


def test_build_ca2_evidence_closure_commit_packet() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "packet_step": "core_non_binder_01",
                    "current_missing_fields": "replacement_reference_binding_kcal_mol",
                    "next_required_action": "manual_negative_evidence_review",
                },
                {
                    "packet_step": "core_non_binder_02",
                    "current_missing_fields": "replacement_reference_binding_kcal_mol",
                    "next_required_action": "manual_negative_evidence_review",
                },
            ]
        },
        {
            "today_focus_rows": [
                {"packet_step": "core_non_binder_01", "ligand": "acetaminophen", "day_queue_rank": 1},
                {"packet_step": "core_non_binder_02", "ligand": "metformin", "day_queue_rank": 2},
            ]
        },
        {
            "rows": [
                {"packet_step": "core_non_binder_01", "draft_manual_decision_note": "note 1"},
                {"packet_step": "core_non_binder_02", "draft_manual_decision_note": "note 2"},
            ]
        },
        {
            "rows": [
                {"packet_step": "core_non_binder_01", "review_reason": "reason 1", "quantitative_value_available": "no"},
                {"packet_step": "core_non_binder_02", "review_reason": "reason 2", "quantitative_value_available": "no"},
            ]
        },
        {
            "workbook_rows": [
                {"packet_step": "core_non_binder_01", "missing_fields": "replacement_reference_binding_kcal_mol"},
                {"packet_step": "core_non_binder_02", "missing_fields": "replacement_reference_binding_kcal_mol"},
            ]
        },
    )
    assert payload["summary"]["family"] == "ca2"
    assert payload["summary"]["commit_row_count"] == 2
    assert payload["summary"]["authoritative_apply_allowed_count"] == 0
    assert payload["rows"][0]["must_remain_blank_fields"] == "replacement_reference_binding_kcal_mol"
    assert payload["rows"][0]["authoritative_apply_allowed_now"] == "no"
    assert payload["rows"][0]["auto_promote_allowed"] == "no"
    assert "manual_decision_note" in payload["rows"][0]["confirm_now_fields"]
    assert payload["rows"][1]["draft_manual_decision_note"] == "note 2"
