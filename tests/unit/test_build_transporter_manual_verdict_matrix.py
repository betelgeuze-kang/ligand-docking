from __future__ import annotations

from tools import build_transporter_manual_verdict_matrix as mod


def test_build_transporter_manual_verdict_matrix() -> None:
    payload = mod.build_payload(
        {
            "sheet_rows": [
                {
                    "priority_rank": "1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "bacopaside II",
                    "current_recommended_verdict": "keep_review_only",
                    "suggested_manual_verdict": "keep_review_only",
                    "manual_verdict_update": "",
                    "update_status": "pending_manual_verdict",
                }
            ]
        },
        {
            "sheet_rows": [
                {
                    "priority_rank": "1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "cytochalasin B",
                    "current_recommended_verdict": "keep_review_only",
                    "suggested_manual_verdict": "keep_review_only",
                    "manual_verdict_update": "",
                    "update_status": "pending_manual_verdict",
                }
            ]
        },
        {
            "rows": [
                {
                    "target_id": "AQP1",
                    "packet_step": "core_binder_01",
                    "manual_decision_note_template": "note a",
                },
                {
                    "target_id": "GLUT1",
                    "packet_step": "core_binder_01",
                    "manual_decision_note_template": "note g",
                },
            ]
        },
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
    assert payload["summary"]["row_count"] == 2
    assert payload["summary"]["pending_manual_verdict_count"] == 2
    assert payload["summary"]["note_template_ready_count"] == 2
    assert payload["summary"]["aqp1_pending_count"] == 1
    assert payload["summary"]["glut1_pending_count"] == 1
    assert payload["summary"]["glut1_open_source_confirmation"] == "runs/glut1_second_wave_source_confirmation_packet_current.md"
    assert payload["summary"]["glut1_second_wave_source_confirmation_ready"] is True
    assert payload["summary"]["glut1_second_wave_source_confirmation_primary_focus_ligand"] == "cytochalasin B"
    assert payload["summary"]["glut1_direct_quantitative_binding_count"] == 1
    assert payload["summary"]["glut1_exact_target_pair_activity_count"] == 2
    assert payload["summary"]["glut1_structured_pair_absent_count"] == 1
    assert "cytochalasin B" in payload["summary"]["next_required_step"]
    assert payload["rows"][0]["note_template_ready"] == "1"
    assert payload["rows"][0]["open_source_confirmation"] == ""
    assert payload["rows"][1]["open_source_confirmation"] == "runs/glut1_second_wave_source_confirmation_packet_current.md"
    assert payload["rows"][1]["source_confirmation_primary_focus_ligand"] == "cytochalasin B"
    assert payload["rows"][1]["source_confirmation_direct_quantitative_binding_count"] == 1
    assert payload["rows"][1]["source_confirmation_exact_target_pair_activity_count"] == 2
    assert payload["rows"][1]["source_confirmation_structured_pair_absent_count"] == 1
