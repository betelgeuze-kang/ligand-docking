from __future__ import annotations

from tools import build_transporter_apply_draft_status as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_transporter_apply_draft_status() -> None:
    payload = mod.build_payload(
        {"summary": {"binder_slot_count": 3, "pending_manual_verdict_count": 0, "completed_manual_verdict_count": 3, "suggested_prefill_count": 3, "next_required_step": "stage aqp1 seed rows"}},
        {"summary": {"binder_slot_count": 3, "pending_manual_verdict_count": 0, "completed_manual_verdict_count": 3, "suggested_prefill_count": 3, "next_required_step": "stage glut1 seed rows"}},
        {
            "rows": [
                {"target_id": "AQP1"},
                {"target_id": "AQP1"},
                {"target_id": "AQP1"},
                {"target_id": "GLUT1"},
                {"target_id": "GLUT1"},
                {"target_id": "GLUT1"},
            ]
        },
        {"summary": {"workbook_row_count": 6, "ready_seed_row_count": 0}, "workbook_rows": [{"row_ready_for_apply": "no", "placeholder_sources": "reference"}] * 6},
        {"summary": {"workbook_row_count": 6, "ready_seed_row_count": 0}, "workbook_rows": [{"row_ready_for_apply": "no", "placeholder_sources": "reference"}] * 6},
        {"summary": {"queue_count": 6, "binder_slots": 3, "non_binder_slots": 3}},
        {"summary": {"queue_count": 6, "binder_slots": 3, "non_binder_slots": 3}},
        {"summary": {"exact_human_aqp1_activity_count": 1, "primary_focus_ligand": "AqB013", "signal": "exact_human_activity_present_leave_kcal_blank"}},
        {
            "summary": {
                "row_count": 3,
                "primary_focus_ligand": "cytochalasin B",
                "direct_quantitative_binding_count": 1,
                "exact_target_pair_activity_count": 2,
                "structured_pair_absent_count": 1,
            }
        },
    )
    assert payload["summary"]["target_count"] == 2
    assert payload["summary"]["current_phase"] == "blocker_closure_seed_row_promotion"
    assert payload["summary"]["binder_slot_count"] == 6
    assert payload["summary"]["binder_seed_row_count"] == 6
    assert payload["summary"]["pending_manual_verdict_count"] == 0
    assert payload["summary"]["completed_manual_verdict_count"] == 6
    assert payload["summary"]["note_template_count"] == 6
    assert payload["summary"]["packet_queue_count"] == 12
    assert payload["summary"]["ready_for_apply_rows"] == 0
    assert payload["summary"]["aqp1_exact_human_activity_count"] == 1
    assert payload["summary"]["aqp1_quantitative_provenance_focus_ligand"] == "AqB013"
    assert payload["summary"]["aqp1_quantitative_provenance_signal"] == "exact_human_activity_present_leave_kcal_blank"
    assert payload["summary"]["glut1_second_wave_source_confirmation_ready"] is True
    assert payload["summary"]["glut1_second_wave_source_confirmation_packet_artifact"] == "runs/glut1_second_wave_source_confirmation_packet_current.md"
    assert payload["summary"]["glut1_second_wave_source_confirmation_row_count"] == 3
    assert payload["summary"]["glut1_second_wave_source_confirmation_primary_focus_ligand"] == "cytochalasin B"
    assert payload["summary"]["glut1_direct_quantitative_binding_count"] == 1
    assert payload["summary"]["glut1_exact_target_pair_activity_count"] == 2
    assert payload["summary"]["glut1_structured_pair_absent_count"] == 1
    _contains_tokens(
        payload["summary"]["next_required_step"],
        "seed-row",
        "promotion",
        "readiness",
        "GLUT1",
        "cytochalasin B",
    )
    assert payload["target_rows"][0]["draft_apply_status"] == "seed_row_promotion_blocked"
    assert payload["target_rows"][0]["binder_seed_row_count"] == 3
    assert payload["target_rows"][0]["second_wave_source_confirmation_ready"] is False
    assert payload["target_rows"][0]["direct_quantitative_binding_count"] == 0
    assert payload["target_rows"][0]["exact_human_activity_count"] == 1
    assert payload["target_rows"][0]["quantitative_provenance_signal"] == "exact_human_activity_present_leave_kcal_blank"
    _contains_tokens(payload["target_rows"][0]["next_required_step"], "exact-human-activity", "blank")
    assert payload["target_rows"][1]["second_wave_source_confirmation_ready"] is True
    assert payload["target_rows"][1]["second_wave_source_confirmation_packet_artifact"] == "runs/glut1_second_wave_source_confirmation_packet_current.md"
    assert payload["target_rows"][1]["second_wave_source_confirmation_row_count"] == 3
    assert payload["target_rows"][1]["second_wave_source_confirmation_primary_focus_ligand"] == "cytochalasin B"
    assert payload["target_rows"][1]["direct_quantitative_binding_count"] == 1
    assert payload["target_rows"][1]["exact_target_pair_activity_count"] == 2
    assert payload["target_rows"][1]["structured_pair_absent_count"] == 1
    _contains_tokens(
        payload["target_rows"][1]["next_required_step"],
        "GLUT1",
        "cytochalasin B",
        "direct_quantitative_binding_count=1",
        "blank",
    )


def test_build_transporter_apply_draft_status_defaults_glut1_source_confirmation_fields_when_missing() -> None:
    payload = mod.build_payload(
        {"summary": {"binder_slot_count": 1, "pending_manual_verdict_count": 1}},
        {"summary": {"binder_slot_count": 1, "pending_manual_verdict_count": 0}},
        {"rows": [{"target_id": "AQP1"}, {"target_id": "GLUT1"}]},
        {"summary": {"workbook_row_count": 1, "ready_seed_row_count": 0}, "workbook_rows": [{}]},
        {"summary": {"workbook_row_count": 1, "ready_seed_row_count": 0}, "workbook_rows": [{}]},
        {"summary": {"queue_count": 1, "binder_slots": 1, "non_binder_slots": 0}},
        {"summary": {"queue_count": 1, "binder_slots": 1, "non_binder_slots": 0}},
    )

    assert payload["summary"]["current_phase"] == "manual_verdict_burndown"
    assert payload["summary"]["glut1_second_wave_source_confirmation_ready"] is False
    assert payload["summary"]["glut1_second_wave_source_confirmation_packet_artifact"] == ""
    assert payload["summary"]["glut1_second_wave_source_confirmation_row_count"] == 0
    assert payload["summary"]["glut1_second_wave_source_confirmation_primary_focus_ligand"] == ""
    assert payload["summary"]["glut1_direct_quantitative_binding_count"] == 0
    assert payload["summary"]["glut1_exact_target_pair_activity_count"] == 0
    assert payload["summary"]["glut1_structured_pair_absent_count"] == 0
    assert payload["target_rows"][1]["second_wave_source_confirmation_ready"] is False
    assert payload["target_rows"][1]["second_wave_source_confirmation_packet_artifact"] == ""
    assert payload["target_rows"][1]["second_wave_source_confirmation_row_count"] == 0
    assert payload["target_rows"][1]["second_wave_source_confirmation_primary_focus_ligand"] == ""
    assert payload["target_rows"][1]["direct_quantitative_binding_count"] == 0
    assert payload["target_rows"][1]["exact_target_pair_activity_count"] == 0
    assert payload["target_rows"][1]["structured_pair_absent_count"] == 0
