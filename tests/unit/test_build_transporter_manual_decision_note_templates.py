from __future__ import annotations

from tools import build_transporter_manual_decision_note_templates as mod


def test_build_transporter_manual_decision_note_templates() -> None:
    payload = mod.build_payload(
        {
            "sheet_rows": [
                {
                    "priority_rank": "1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "bacopaside II",
                    "source_anchor": "PMID 27474162",
                    "suggested_manual_verdict": "keep_review_only",
                    "evidence_strength": "medium",
                    "potency_or_signal": "AQP1 water-channel IC50 18 uM",
                    "promotion_blocker": "no_local_aqp1_binder_evidence_curated",
                    "next_required_action": "manual_curated_search_or_defer",
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
                    "source_anchor": "PMID 27078104",
                    "suggested_manual_verdict": "keep_review_only",
                    "evidence_strength": "strong_structural",
                    "potency_or_signal": "structural anchor",
                    "promotion_blocker": "no_local_glut1_binder_evidence_curated",
                    "next_required_action": "manual_curated_search_or_defer",
                    "update_status": "pending_manual_verdict",
                }
            ]
        },
    )

    assert payload["summary"]["target_count"] == 2
    assert payload["summary"]["template_row_count"] == 2
    assert payload["summary"]["note_template_ready"] is True
    assert payload["summary"]["aqp1_template_count"] == 1
    assert payload["summary"]["glut1_template_count"] == 1
    assert payload["summary"]["pending_manual_verdict_count"] == 2
    assert "keep `bacopaside II` as `keep_review_only`" in payload["rows"][0]["manual_decision_note_template"]
