from __future__ import annotations

from tools import build_transporter_reviewer_day_plan as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_transporter_reviewer_day_plan() -> None:
    payload = mod.build_payload(
        {
            "summary": {"pending_manual_verdict_count": 6},
            "target_rows": [
                {
                    "target_id": "AQP1",
                    "draft_apply_status": "manual_verdict_pending",
                    "pending_manual_verdict_count": 3,
                    "note_template_count": 3,
                    "placeholder_driven_rows": 6,
                },
                {
                    "target_id": "GLUT1",
                    "draft_apply_status": "manual_verdict_pending",
                    "pending_manual_verdict_count": 3,
                    "note_template_count": 3,
                    "placeholder_driven_rows": 6,
                },
            ],
        },
        {
            "summary": {"template_row_count": 6},
            "rows": [
                {"target_id": "AQP1", "candidate_name": "bacopaside II", "packet_step": "core_binder_01"},
                {"target_id": "AQP1", "candidate_name": "AqB013", "packet_step": "core_binder_02"},
                {"target_id": "AQP1", "candidate_name": "AqB011", "packet_step": "core_binder_03"},
                {"target_id": "GLUT1", "candidate_name": "cytochalasin B", "packet_step": "core_binder_01"},
                {"target_id": "GLUT1", "candidate_name": "WZB117", "packet_step": "core_binder_02"},
                {"target_id": "GLUT1", "candidate_name": "STF-31", "packet_step": "core_binder_03"},
            ],
        },
        {"summary": {"ready_for_reviewer_fill_count": 3}},
        {"summary": {"row_count": 6}},
        {"rows": []},
    )

    assert payload["summary"]["target_count"] == 2
    assert payload["summary"]["pending_manual_verdict_count"] == 6
    assert payload["summary"]["aqp1_ready_for_today"] is True
    assert payload["summary"]["glut1_ready_for_today"] is True
    assert payload["review_rows"][0]["target_id"] == "AQP1"
    assert payload["review_rows"][0]["wave_priority"] == "today_first"
    assert payload["review_rows"][0]["first_candidate"] == "bacopaside II"
    assert payload["review_rows"][1]["target_id"] == "GLUT1"
    assert payload["review_rows"][1]["wave_priority"] == "today_second"


def test_build_transporter_reviewer_day_plan_propagates_primary_probe_resolution_handoff() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "pending_manual_verdict_count": 0,
                "aqp1_exact_human_activity_count": 1,
                "aqp1_quantitative_provenance_focus_ligand": "AqB013",
                "aqp1_quantitative_provenance_signal": "exact_human_activity_present_leave_kcal_blank",
            },
            "target_rows": [
                {
                    "target_id": "AQP1",
                    "draft_apply_status": "manual_verdict_complete",
                    "pending_manual_verdict_count": 0,
                    "note_template_count": 3,
                    "placeholder_driven_rows": 6,
                    "exact_human_activity_count": 1,
                    "quantitative_provenance_focus_ligand": "AqB013",
                    "quantitative_provenance_signal": "exact_human_activity_present_leave_kcal_blank",
                },
                {
                    "target_id": "GLUT1",
                    "draft_apply_status": "manual_verdict_complete",
                    "pending_manual_verdict_count": 0,
                    "note_template_count": 3,
                    "placeholder_driven_rows": 6,
                },
            ],
        },
        {
            "summary": {"template_row_count": 6},
            "rows": [
                {"target_id": "AQP1", "candidate_name": "bacopaside II", "packet_step": "core_binder_01"},
                {"target_id": "GLUT1", "candidate_name": "cytochalasin B", "packet_step": "core_binder_01"},
            ],
        },
        {"summary": {"ready_for_reviewer_fill_count": 3}},
        {"summary": {"row_count": 6}},
        {
            "rows": [
                {"target_id": "AQP1", "packet_step": "core_binder_02"},
                {"target_id": "AQP1", "packet_step": "core_binder_03"},
            ]
        },
        {
            "summary": {
                "aqp1_negative_primary_probe_resolution_artifact": "runs/aqp1_negative_primary_probe_resolution_packet_current.md",
                "aqp1_negative_primary_probe_resolution_candidate": "sodium nitroprusside",
                "aqp1_negative_primary_probe_resolution_decision": "keep_review_only_no_authoritative_negative_promotion",
                "aqp1_negative_primary_probe_resolution_solvent_fallback_candidate": "dimethyl sulfoxide",
            }
        },
    )

    assert payload["summary"]["aqp1_negative_primary_probe_resolution_ready"] is True
    assert payload["summary"]["aqp1_negative_primary_probe_resolution_artifact"] == "runs/aqp1_negative_primary_probe_resolution_packet_current.md"
    _contains_tokens(
        payload["review_rows"][0]["today_focus"],
        "primary-probe resolution",
        "sodium nitroprusside",
        "dimethyl sulfoxide",
    )
    _contains_tokens(
        payload["summary"]["day_goal"],
        "primary-probe resolution",
        "sodium nitroprusside",
    )
    _contains_tokens(
        payload["summary"]["next_required_step"],
        "primary-probe resolution",
        "dimethyl sulfoxide",
    )
