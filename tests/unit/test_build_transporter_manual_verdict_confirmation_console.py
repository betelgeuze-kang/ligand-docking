from __future__ import annotations

from tools import build_transporter_manual_verdict_confirmation_console as mod


def test_build_transporter_manual_verdict_confirmation_console() -> None:
    payload = mod.build_payload(
        {
            "summary": {"commit_ready_count": 3},
            "rows": [
                {
                    "priority_rank": "1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "bacopaside II",
                    "commit_value_verdict": "keep_review_only",
                    "commit_value_confidence": "medium",
                    "stop_condition": "no_local_aqp1_binder_evidence_curated",
                    "commit_value_note": "note a",
                    "manual_verdict_update": "",
                    "manual_confidence_update": "",
                    "manual_decision_note": "",
                }
            ],
        },
        {
            "summary": {"staged_confirmation_count": 3},
            "rows": [
                {
                    "priority_rank": 1,
                    "packet_step": "core_binder_01",
                    "candidate_name": "cytochalasin B",
                    "staged_manual_verdict": "keep_review_only",
                    "staged_manual_confidence_update": "strong_structural",
                    "promotion_blocker": "no_local_glut1_binder_evidence_curated",
                    "staged_manual_decision_note": "note g",
                    "manual_verdict_update": "",
                    "manual_confidence_update": "",
                    "manual_decision_note": "",
                    "update_status": "pending_manual_verdict",
                }
            ],
        },
        {
            "summary": {
                "today_open_now_label": "bacopaside II",
                "glut1_open_source_confirmation": "runs/glut1_second_wave_source_confirmation_packet_current.md",
                "glut1_second_wave_source_confirmation_ready": True,
                "glut1_second_wave_source_confirmation_primary_focus_ligand": "cytochalasin B",
                "glut1_direct_quantitative_binding_count": 1,
                "glut1_exact_target_pair_activity_count": 2,
                "glut1_structured_pair_absent_count": 1,
            }
        },
    )

    assert payload["summary"]["target_count"] == 2
    assert payload["summary"]["row_count"] == 2
    assert payload["summary"]["pending_manual_verdict_count"] == 2
    assert payload["summary"]["aqp1_commit_ready_count"] == 3
    assert payload["summary"]["glut1_commit_ready_count"] == 3
    assert payload["summary"]["today_open_now"] == "runs/aqp1_manual_verdict_commit_packet_current.md"
    assert payload["summary"]["today_open_card"] == "runs/aqp1_binder_confirmation_card_current.md"
    assert payload["summary"]["next_wave_packet"] == "runs/glut1_manual_verdict_commit_packet_current.md"
    assert payload["summary"]["next_wave_card"] == "runs/glut1_binder_confirmation_card_current.md"
    assert payload["summary"]["glut1_open_source_confirmation"] == "runs/glut1_second_wave_source_confirmation_packet_current.md"
    assert payload["summary"]["glut1_second_wave_source_confirmation_ready"] is True
    assert payload["summary"]["glut1_second_wave_source_confirmation_primary_focus_ligand"] == "cytochalasin B"
    assert payload["summary"]["glut1_direct_quantitative_binding_count"] == 1
    assert payload["summary"]["glut1_exact_target_pair_activity_count"] == 2
    assert payload["summary"]["glut1_structured_pair_absent_count"] == 1
    assert "cytochalasin B" in payload["summary"]["next_required_step"]
    assert "glut1_second_wave_source_confirmation_packet_current.md" in payload["checklist"][-1]
    assert "cytochalasin B" in payload["checklist"][-1]
    assert "WZB117" in payload["checklist"][-1]
    assert "STF-31" in payload["checklist"][-1]
    assert payload["rows"][0]["target_id"] == "AQP1"
    assert payload["rows"][0]["confirmation_card"] == "runs/aqp1_binder_confirmation_card_current.md"
    assert payload["rows"][0]["commit_packet"] == "runs/aqp1_manual_verdict_commit_packet_current.md"
    assert payload["rows"][0]["open_source_confirmation"] == ""
    assert payload["rows"][1]["target_id"] == "GLUT1"
    assert payload["rows"][1]["confirmation_card"] == "runs/glut1_binder_confirmation_card_current.md"
    assert payload["rows"][1]["commit_packet"] == "runs/glut1_manual_verdict_commit_packet_current.md"
    assert payload["rows"][1]["open_source_confirmation"] == "runs/glut1_second_wave_source_confirmation_packet_current.md"
    assert payload["rows"][1]["source_confirmation_primary_focus_ligand"] == "cytochalasin B"
    assert payload["rows"][1]["source_confirmation_direct_quantitative_binding_count"] == 1
    assert payload["rows"][1]["source_confirmation_exact_target_pair_activity_count"] == 2
    assert payload["rows"][1]["source_confirmation_structured_pair_absent_count"] == 1
