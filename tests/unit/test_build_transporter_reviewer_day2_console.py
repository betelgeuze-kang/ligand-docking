from __future__ import annotations

import pytest

from tools.product import build_transporter_reviewer_day2_console as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_transporter_reviewer_day2_console_builds_stage_chain() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "binder_pending_manual_verdict_count": 6,
                "console_rule": "Open AQP1 first, then GLUT1.",
                "glut1_open_source_confirmation": "runs/glut1_second_wave_source_confirmation_packet_current.md",
                "glut1_second_wave_source_confirmation_ready": True,
                "glut1_second_wave_source_confirmation_primary_focus_ligand": "cytochalasin B",
                "glut1_direct_quantitative_binding_count": 1,
                "glut1_exact_target_pair_activity_count": 2,
                "glut1_structured_pair_absent_count": 1,
            }
        },
        {
            "summary": {"day_goal": "Finish binders first."},
            "review_rows": [
                {
                    "target_id": "AQP1",
                    "first_candidate": "bacopaside II",
                    "today_focus": "Fill 3 AQP1 binder verdicts.",
                    "completion_rule": "Finish all 3 AQP1 binder rows.",
                },
                {
                    "target_id": "GLUT1",
                    "first_candidate": "cytochalasin B",
                    "today_focus": "Fill 3 GLUT1 binder verdicts.",
                    "completion_rule": "Finish all 3 GLUT1 binder rows.",
                },
            ],
        },
        {
            "summary": {
                "today_first_target": "AQP1",
                "today_second_target": "GLUT1",
                "negative_slot_count_total": 6,
                "day_goal": "Finish negatives after binders.",
            },
            "target_rows": [
                {"target_id": "AQP1", "negative_slot_count": 3, "next_required_step": "AQP1 negatives."},
                {"target_id": "GLUT1", "negative_slot_count": 3, "next_required_step": "GLUT1 negatives."},
            ],
            "review_rows": [
                {"target_id": "AQP1", "review_phase": "caution_references_second"},
                {"target_id": "AQP1", "review_phase": "caution_references_second"},
                {"target_id": "GLUT1", "review_phase": "caution_references_second"},
                {"target_id": "GLUT1", "review_phase": "caution_references_second"},
            ],
        },
        {
            "target_packets": [
                {"target_id": "AQP1", "pending_manual_verdict_count": 3},
                {"target_id": "GLUT1", "pending_manual_verdict_count": 3},
            ]
        },
        {"summary": {"candidate_name": "bacopaside II"}},
        {"summary": {"candidate_name": "bacopaside II", "safe_staged_field_count": 1}},
        {"summary": {"candidate_name": "bacopaside II", "safe_staged_field_count": 1}},
        {"rows": []},
    )
    assert payload["summary"]["stage_count"] == 4
    assert payload["rows"][0]["open_packet"] == "runs/aqp1_manual_verdict_packet_current.md"
    assert payload["rows"][0]["open_after_exhausted"] == "runs/aqp1_negative_review_handoff_packet_current.md"
    assert payload["rows"][2]["open_packet"] == "runs/glut1_manual_verdict_packet_current.md"
    assert payload["rows"][3]["open_after_exhausted"] == "stop_reviewer_day2_console"
    assert payload["summary"]["glut1_open_source_confirmation"] == "runs/glut1_second_wave_source_confirmation_packet_current.md"
    assert payload["summary"]["glut1_second_wave_source_confirmation_ready"] is True
    assert payload["summary"]["glut1_second_wave_source_confirmation_primary_focus_ligand"] == "cytochalasin B"
    _contains_tokens(payload["rows"][2]["current_focus"], "cytochalasin b", "wzb117", "stf-31")


def test_build_transporter_reviewer_day2_console_uses_negative_counts_for_exhaustion() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "binder_pending_manual_verdict_count": 0,
                "console_rule": "rule",
                "glut1_open_source_confirmation": "runs/glut1_second_wave_source_confirmation_packet_current.md",
                "glut1_second_wave_source_confirmation_ready": True,
                "glut1_second_wave_source_confirmation_primary_focus_ligand": "cytochalasin B",
            }
        },
        {"summary": {"day_goal": "goal"}, "review_rows": []},
        {
            "summary": {"today_first_target": "AQP1", "today_second_target": "GLUT1", "negative_slot_count_total": 6, "day_goal": "neg goal"},
            "target_rows": [
                {"target_id": "AQP1", "negative_slot_count": 3},
                {"target_id": "GLUT1", "negative_slot_count": 3},
            ],
            "review_rows": [
                {"target_id": "AQP1", "review_phase": "caution_references_second"},
                {"target_id": "GLUT1", "review_phase": "caution_references_second"},
            ],
        },
        {"target_packets": []},
        {"summary": {"candidate_name": "bacopaside II"}},
        {"summary": {"candidate_name": "bacopaside II", "safe_staged_field_count": 1}},
        {"summary": {"candidate_name": "bacopaside II", "safe_staged_field_count": 1}},
        {
            "rows": [
                {"target_id": "AQP1", "packet_step": "core_binder_01"},
                {"target_id": "AQP1", "packet_step": "core_binder_02"},
                {"target_id": "AQP1", "packet_step": "core_binder_03"},
            ]
        },
    )
    neg_rows = [r for r in payload["rows"] if r["review_mode"] == "negative_review"]
    _contains_tokens(neg_rows[0]["exhaustion_rule"], "3", "negative slots")
    _contains_tokens(neg_rows[0]["exhaustion_rule"], "1", "caution/defer", "reference")
    assert payload["rows"][0]["open_packet"] == "runs/aqp1_first_seed_row_packet_current.md"
    assert payload["rows"][1]["open_packet"] == "runs/transporter_seed_row_execution_packet_current.md"
    assert payload["rows"][2]["open_packet"] == "runs/aqp1_seed_row_sync_apply_preview_current.md"
    assert payload["summary"]["aqp1_follow_on_seed_targets"] == "core_binder_02, core_binder_03"
    _contains_tokens(payload["summary"]["next_required_step"], "glut1", "cytochalasin b")


@pytest.mark.xfail(
    reason="GLUT1 second-wave source-confirmation stage is not yet inserted into the day-2 console stage chain.",
    strict=True,
)
def test_build_transporter_reviewer_day2_console_promotes_glut1_second_wave_source_confirmation_stage() -> None:
    payload = mod.build_payload(
        {"summary": {"binder_pending_manual_verdict_count": 0, "console_rule": "rule"}},
        {"summary": {"day_goal": "goal"}, "review_rows": []},
        {
            "summary": {
                "today_first_target": "AQP1",
                "today_second_target": "GLUT1",
                "negative_slot_count_total": 6,
                "day_goal": "neg goal",
            },
            "target_rows": [
                {"target_id": "AQP1", "negative_slot_count": 3},
                {"target_id": "GLUT1", "negative_slot_count": 3},
            ],
            "review_rows": [
                {"target_id": "AQP1", "review_phase": "caution_references_second"},
                {"target_id": "GLUT1", "review_phase": "caution_references_second"},
            ],
        },
        {"target_packets": []},
        {"summary": {"candidate_name": "bacopaside II"}},
        {"summary": {"candidate_name": "bacopaside II", "safe_staged_field_count": 1}},
        {"summary": {"candidate_name": "bacopaside II", "safe_staged_field_count": 1}},
        {"rows": [{"target_id": "AQP1", "packet_step": "core_binder_02"}, {"target_id": "AQP1", "packet_step": "core_binder_03"}]},
    )

    assert payload["rows"][4]["open_packet"] == "runs/glut1_second_wave_source_confirmation_packet_current.md"
