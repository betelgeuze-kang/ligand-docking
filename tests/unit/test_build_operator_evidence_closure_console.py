from __future__ import annotations

from tools import build_operator_evidence_closure_console as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_operator_evidence_closure_console() -> None:
    payload = mod.build_payload(
        {
            "summary": {"run_now_count": 4, "prepare_next_count": 2, "manual_review_only_count": 1},
            "rows": [
                {"priority_lane": "run_now", "family": "gpcr", "runtime_scope_now": "endpoint_only", "next_required_step": "keep blocked"},
                {"priority_lane": "prepare_next", "family": "non_kinase_enzyme_ca2", "runtime_scope_now": "partial", "next_required_step": "fill rows"},
                {"priority_lane": "manual_review_only", "family": "transporter", "runtime_scope_now": "draft", "next_required_step": "review only"},
            ],
        },
        {
            "summary": {"run_now_family_count": 2},
            "rows": [
                {
                    "family": "gpcr",
                    "safe_scope_now": "chembl50_v4_locked_decoy_apply_safe_endpoint",
                    "primary_handoff_note": "Use the apply-safe endpoint only; keep router promotion blocked.",
                }
            ],
        },
        {"summary": {"sequence_count": 5}, "rows": []},
        {
            "summary": {"handoff_row_count": 7},
            "handoff_rows": [
                {"family": "ca2", "packet_step": "core_non_binder_01", "ligand": "acetaminophen", "next_required_action": "manual_negative_evidence_review"}
            ],
        },
        {
            "summary": {"reviewer_row_count": 10},
            "reviewer_rows": [
                {"family": "ca2", "packet_step": "core_non_binder_01", "ligand": "acetaminophen", "next_required_action": "manual_negative_evidence_review"}
            ],
        },
        {
            "summary": {
                "today_open_now": "runs/ca2_evidence_closure_commit_packet_current.md",
                "next_required_step": "Open CA2 commit first, then PXR commit.",
            }
        },
        {
            "summary": {"queue_row_count": 13},
            "rows": [
                {"family": "aqp1", "item_id": "core_binder_01", "candidate_or_ligand": "bacopaside II", "recommended_action": "fill_manual_verdict_update"}
            ],
        },
        {
            "summary": {"target_count": 2, "pending_manual_verdict_count": 0},
            "review_rows": [
                {"target_id": "AQP1", "first_candidate": "bacopaside II", "start_artifact": "runs/aqp1_binder_review_brief_current.md"}
            ],
        },
        {
            "summary": {"target_count": 2},
            "target_rows": [
                {
                    "target": "aqp1",
                    "open_first": "runs/aqp1_binder_review_brief_current.md",
                    "operator_instruction": "Start here today.",
                },
                {
                    "target": "glut1",
                    "open_first": "runs/glut1_candidate_verdict_sheet_current.md",
                    "operator_instruction": "Open only after AQP1 is exhausted.",
                },
            ],
        },
        {
            "summary": {
                "target_count": 2,
                "first_wave_target": "AQP1",
                "current_phase": "blocker_closure_seed_row_promotion",
                "today_open_now": "runs/aqp1_first_seed_row_packet_current.md",
                "today_finish_line": "Manual verdict backlog is cleared. Use AQP1 first to stage the first non-authoritative seed-row sync preview, then continue blocker closure before touching GLUT1.",
            }
        },
    )
    assert payload["summary"]["run_now_count"] == 1
    assert payload["summary"]["partial_handoff_row_count"] == 10
    assert payload["summary"]["partial_commit_ready"] is True
    assert payload["summary"]["manual_queue_row_count"] == 13
    assert payload["summary"]["transporter_pending_manual_verdict_count"] == 0
    assert payload["summary"]["transporter_current_phase"] == "blocker_closure_seed_row_promotion"
    assert payload["summary"]["console_row_count"] == 6
    _contains_tokens(payload["summary"]["next_required_step"], "transporter", "blocker", "closure")
    assert payload["rows"][0]["console_lane"] == "run_now"
    assert payload["rows"][0]["focus"] == "chembl50_v4_locked_decoy_apply_safe_endpoint"
    assert payload["rows"][1]["console_lane"] == "partial_closure"
    assert payload["rows"][2]["console_lane"] == "partial_commit"
    assert payload["rows"][2]["focus"] == "runs/ca2_evidence_closure_commit_packet_current.md"
    assert payload["rows"][3]["console_lane"] == "manual_queue"
    assert payload["rows"][4]["console_lane"] == "transporter_today"
    assert payload["rows"][4]["focus"] == "runs/aqp1_first_seed_row_packet_current.md"
    _contains_tokens(payload["rows"][4]["next_action"], "seed-row", "sync", "preview")
    assert payload["rows"][5]["focus"] == "runs/glut1_candidate_verdict_sheet_current.md"
    _contains_tokens(payload["rows"][5]["next_action"], "after", "aqp1", "exhausted")
