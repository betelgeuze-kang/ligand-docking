from __future__ import annotations

from tools.product import build_transporter_donor_policy_blocker_packet as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_transporter_donor_policy_blocker_packet_payload() -> None:
    payload = mod.build_payload(
        checklist_payload={
            "summary": {
                "decision_status": "scaffold_default_keep_existing_fit_donor_pool",
                "scaffold_fit_donor_target": "EGFR_KINASE",
                "reopen_ready": False,
                "blocked_check_count": 3,
                "ready_check_count": 0,
            },
            "rows": [
                {
                    "check_id": "candidate_has_non_placeholder_packet_row",
                    "status": "blocked",
                    "current_value": "aqp1_binder_defer=3; glut1_binder_defer=3",
                    "ready_when": "At least one transporter binder row is no longer placeholder-driven.",
                },
                {
                    "check_id": "p0_scaffold_open_count_zero",
                    "status": "blocked",
                    "current_value": "9",
                    "ready_when": "Transporter P0 open count reaches 0.",
                },
                {
                    "check_id": "manual_review_only_is_not_authoritative_apply",
                    "status": "blocked",
                    "current_value": "aqp1_keep_review_only=3; glut1_keep_review_only=3",
                    "ready_when": "A reviewed transporter candidate is upgraded from manual-review only to a claim-safe packet row with provenance.",
                },
            ],
        },
        dashboard_payload={
            "summary": {
                "target_count": 2,
                "binder_seed_row_count": 6,
                "binder_pending_manual_verdict_count": 0,
                "binder_completed_manual_verdict_count": 6,
                "negative_slot_count_total": 6,
                "negative_review_row_count": 6,
                "placeholder_row_count_total": 12,
            },
            "target_rows": [
                {
                    "target_id": "AQP1",
                    "binder_pending_manual_verdict_count": 3,
                    "negative_slot_count": 3,
                    "placeholder_rows": 6,
                    "local_evidence_status": "draft_only_local_evidence_blocked",
                    "next_required_step": "Keep AQP1 authoritative apply blocked.",
                },
                {
                    "target_id": "GLUT1",
                    "binder_pending_manual_verdict_count": 3,
                    "negative_slot_count": 3,
                    "placeholder_rows": 6,
                    "local_evidence_status": "draft_only_local_evidence_blocked",
                    "next_required_step": "Keep GLUT1 authoritative apply blocked.",
                },
            ],
        },
        binder_day_plan_payload={
            "review_rows": [
                {
                    "target_id": "AQP1",
                    "wave_priority": "today_first",
                    "first_candidate": "bacopaside II",
                },
                {
                    "target_id": "GLUT1",
                    "wave_priority": "today_second",
                    "first_candidate": "cytochalasin B",
                },
            ]
        },
        negative_day_plan_payload={
            "target_rows": [
                {"target_id": "AQP1", "wave_priority": "today_first"},
                {"target_id": "GLUT1", "wave_priority": "today_second"},
            ]
        },
    )

    assert payload["summary"]["decision_status"] == "scaffold_default_keep_existing_fit_donor_pool"
    assert payload["summary"]["reopen_ready"] is False
    assert payload["summary"]["blocked_check_count"] == 3
    assert payload["summary"]["current_phase"] == "blocker_closure_seed_row_promotion"
    assert payload["summary"]["binder_seed_row_count"] == 6
    assert payload["summary"]["binder_pending_manual_verdict_count"] == 0
    assert payload["summary"]["binder_completed_manual_verdict_count"] == 6
    assert payload["summary"]["negative_slot_count_total"] == 6
    assert payload["summary"]["placeholder_row_count_total"] == 12
    assert payload["summary"]["blocker_packet_ready"] is True

    blocker_rows = {row["check_id"]: row for row in payload["blocker_rows"]}
    assert blocker_rows["candidate_has_non_placeholder_packet_row"]["blocker_scope"] == "binder_day_plan"
    _contains_tokens(
        blocker_rows["candidate_has_non_placeholder_packet_row"]["unblock_today_action"],
        "seed-row",
        "sync",
        "placeholder-driven",
    )
    assert blocker_rows["p0_scaffold_open_count_zero"]["blocker_scope"] == "target_packet_backlog"
    assert blocker_rows["manual_review_only_is_not_authoritative_apply"]["blocker_scope"] == "negative_review_and_promotion_gate"

    target_rows = {row["target_id"]: row for row in payload["target_rows"]}
    assert target_rows["AQP1"]["binder_wave_priority"] == "today_first"
    assert target_rows["AQP1"]["binder_first_candidate"] == "bacopaside II"
    assert target_rows["GLUT1"]["negative_wave_priority"] == "today_second"


def test_build_transporter_donor_policy_blocker_packet_switches_wording_after_manual_verdict_closure() -> None:
    payload = mod.build_payload(
        checklist_payload={
            "summary": {
                "decision_status": "scaffold_default_keep_existing_fit_donor_pool",
                "scaffold_fit_donor_target": "EGFR_KINASE",
                "reopen_ready": False,
                "blocked_check_count": 3,
                "ready_check_count": 0,
            },
            "rows": [],
        },
        dashboard_payload={
            "summary": {
                "target_count": 2,
                "binder_seed_row_count": 6,
                "binder_pending_manual_verdict_count": 0,
                "binder_completed_manual_verdict_count": 6,
                "negative_slot_count_total": 6,
                "negative_review_row_count": 6,
                "placeholder_row_count_total": 12,
            },
            "target_rows": [],
        },
        binder_day_plan_payload={"review_rows": []},
        negative_day_plan_payload={"target_rows": []},
    )
    assert payload["summary"]["current_phase"] == "blocker_closure_seed_row_promotion"
    assert payload["summary"]["binder_pending_manual_verdict_count"] == 0
    assert payload["summary"]["binder_seed_row_count"] == 6
    _contains_tokens(payload["summary"]["next_required_step"], "during", "seed-row", "blocker", "closure")
