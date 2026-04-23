from __future__ import annotations

from tools import build_transporter_manual_review_launchboard as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_transporter_manual_review_launchboard_sets_open_now_and_finish_line() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "target_count": 2,
                "first_wave_target": "AQP1",
                "second_wave_target": "GLUT1",
                "next_required_step": "Work AQP1 first.",
            }
        },
        {
            "summary": {
                "binder_pending_manual_verdict_count": 6,
                "console_rule": "Open AQP1 first.",
                "aqp1_open_source_confirmation": "runs/aqp1_first_wave_source_confirmation_packet_current.md",
                "aqp1_open_follow_on": "runs/aqp1_first_wave_follow_on_packet_current.md",
                "glut1_open_source_confirmation": "runs/glut1_second_wave_source_confirmation_packet_current.md",
                "glut1_second_wave_source_confirmation_ready": True,
                "glut1_second_wave_source_confirmation_primary_focus_ligand": "cytochalasin B",
            }
        },
        {
            "summary": {"next_required_step": "Open packets strictly in order."},
            "rows": [
                {
                    "stage_order": 1,
                    "target_id": "AQP1",
                    "review_mode": "seed_row_packet",
                    "open_packet": "runs/aqp1_first_seed_row_packet_current.md",
                    "pending_count": 3,
                    "start_label": "bacopaside II",
                    "open_after_exhausted": "runs/aqp1_seed_row_sync_apply_preview_current.md",
                },
                {
                    "stage_order": 2,
                    "target_id": "AQP1",
                    "review_mode": "seed_row_sync_preview",
                    "open_packet": "runs/aqp1_seed_row_sync_apply_preview_current.md",
                    "pending_count": 3,
                    "start_label": "bacopaside II",
                    "open_after_exhausted": "runs/aqp1_negative_review_handoff_packet_current.md",
                },
            ],
        },
        {
            "summary": {"negative_slot_count_total": 6},
        },
        {
            "target_packets": [
                {"target_id": "AQP1", "pending_manual_verdict_count": 3},
                {"target_id": "GLUT1", "pending_manual_verdict_count": 3},
            ]
        },
        {"rows": []},
    )
    assert payload["summary"]["today_open_now"] == "runs/aqp1_first_seed_row_packet_current.md"
    assert payload["summary"]["today_open_now_label"] == "bacopaside II"
    _contains_tokens(payload["summary"]["today_finish_line"], "3", "aqp1", "binder", "manual verdict")
    assert payload["rows"][0]["open_after_exhausted"] == "runs/aqp1_seed_row_sync_apply_preview_current.md"


def test_build_transporter_manual_review_launchboard_checklist_mentions_glut1_block() -> None:
    payload = mod.build_payload(
        {"summary": {"target_count": 2, "first_wave_target": "AQP1", "second_wave_target": "GLUT1", "next_required_step": "quick"}},
        {
            "summary": {
                "binder_pending_manual_verdict_count": 0,
                "console_rule": "rule",
                "aqp1_open_source_confirmation": "runs/aqp1_first_wave_source_confirmation_packet_current.md",
                "aqp1_open_follow_on": "runs/aqp1_first_wave_follow_on_packet_current.md",
                "glut1_open_source_confirmation": "runs/glut1_second_wave_source_confirmation_packet_current.md",
                "glut1_second_wave_source_confirmation_ready": True,
                "glut1_second_wave_source_confirmation_primary_focus_ligand": "cytochalasin B",
                "glut1_direct_quantitative_binding_count": 1,
                "glut1_exact_target_pair_activity_count": 2,
                "glut1_structured_pair_absent_count": 1,
            }
        },
        {"summary": {"next_required_step": "day2"}, "rows": []},
        {"summary": {"negative_slot_count_total": 6}},
        {"target_packets": []},
        {"rows": []},
    )
    assert any(
        all(token in item.lower() for token in ("do not skip ahead", "glut1"))
        for item in payload["checklist"]
    )
    assert any("exact-source scope packet" in item.lower() for item in payload["checklist"])
    assert any("cytochalasin b" in item.lower() for item in payload["checklist"])


def test_build_transporter_manual_review_launchboard_switches_to_blocker_closure_when_pending_is_zero() -> None:
    payload = mod.build_payload(
        {"summary": {"target_count": 2, "first_wave_target": "AQP1", "second_wave_target": "GLUT1", "next_required_step": "quick"}},
        {
            "summary": {
                "binder_pending_manual_verdict_count": 0,
                "console_rule": "rule",
                "aqp1_open_source_confirmation": "runs/aqp1_first_wave_source_confirmation_packet_current.md",
                "aqp1_open_follow_on": "runs/aqp1_first_wave_follow_on_packet_current.md",
                "aqp1_open_follow_on_blocker_decomposition": "runs/aqp1_follow_on_blocker_decomposition_current.md",
                "glut1_open_source_confirmation": "runs/glut1_second_wave_source_confirmation_packet_current.md",
                "glut1_second_wave_source_confirmation_ready": True,
                "glut1_second_wave_source_confirmation_primary_focus_ligand": "cytochalasin B",
                "glut1_direct_quantitative_binding_count": 1,
                "glut1_exact_target_pair_activity_count": 2,
                "glut1_structured_pair_absent_count": 1,
                "aqp1_follow_on_blocker_decomposition_row_count": 2,
                "aqp1_follow_on_blocker_decomposition_follow_on_targets": "core_binder_02, core_binder_03",
                "aqp1_follow_on_blocker_decomposition_primary_focus_ligand": "AqB013",
                "aqp1_follow_on_blocker_decomposition_exact_human_guardrail_ligand": "AqB013",
                "aqp1_follow_on_blocker_decomposition_exact_human_nonbinding_count": 1,
                "aqp1_follow_on_blocker_decomposition_exact_target_pair_absent_count": 1,
                "aqp1_follow_on_blocker_decomposition_next_required_step": "Keep core_binder_02 as the guardrail while core_binder_03 closes the target-pair gap.",
            }
        },
        {
            "summary": {"next_required_step": "day2"},
            "rows": [
                {
                    "stage_order": 1,
                    "target_id": "AQP1",
                    "review_mode": "seed_row_packet",
                    "open_packet": "runs/aqp1_first_seed_row_packet_current.md",
                    "pending_count": 0,
                    "start_label": "bacopaside II",
                    "open_after_exhausted": "runs/aqp1_seed_row_sync_apply_preview_current.md",
                }
            ],
        },
        {"summary": {"negative_slot_count_total": 6}},
        {"target_packets": [{"target_id": "AQP1", "pending_manual_verdict_count": 0}]},
        {
            "rows": [
                {"target_id": "AQP1", "packet_step": "core_binder_01"},
                {"target_id": "AQP1", "packet_step": "core_binder_02"},
                {"target_id": "AQP1", "packet_step": "core_binder_03"},
            ]
        },
    )
    assert payload["summary"]["current_phase"] == "blocker_closure_seed_row_promotion"
    _contains_tokens(payload["summary"]["today_finish_line"], "aqp1", "seed-row", "blocker-closure")
    assert ",," not in payload["summary"]["today_finish_line"]
    assert any(
        all(token in item.lower() for token in ("seed-row", "blocker-closure"))
        for item in payload["checklist"]
    )
    assert payload["summary"]["today_open_source_confirmation"] == "runs/aqp1_first_wave_source_confirmation_packet_current.md"
    assert payload["summary"]["today_open_follow_on"] == "runs/aqp1_first_wave_follow_on_packet_current.md"
    assert payload["summary"]["glut1_open_source_confirmation"] == "runs/glut1_second_wave_source_confirmation_packet_current.md"
    assert payload["summary"]["glut1_second_wave_source_confirmation_ready"] is True
    assert payload["summary"]["glut1_second_wave_source_confirmation_primary_focus_ligand"] == "cytochalasin B"
    assert payload["summary"]["today_open_follow_on_blocker_decomposition"] == "runs/aqp1_follow_on_blocker_decomposition_current.md"
    assert payload["summary"]["aqp1_follow_on_blocker_decomposition_ready"] is True
    _contains_tokens(payload["summary"]["today_finish_line"], "follow-on blocker decomposition", "guardrail", "target-pair")
    _contains_tokens(payload["summary"]["today_finish_line"], "glut1", "cytochalasin b")
    assert any("follow-on blocker decomposition" in item.lower() for item in payload["checklist"])
    assert any("cytochalasin b" in item.lower() for item in payload["checklist"])
    assert "core_binder_02, core_binder_03" in payload["summary"]["aqp1_follow_on_seed_targets"]
    assert "aqp1_first_wave_follow_on_packet_current.md" in payload["summary"]["today_finish_line"]
    assert payload["rows"][0]["review_mode"] == "seed_row_promotion"


def test_build_transporter_manual_review_launchboard_propagates_glut1_second_wave_source_confirmation_rule() -> None:
    payload = mod.build_payload(
        {"summary": {"target_count": 2, "first_wave_target": "AQP1", "second_wave_target": "GLUT1", "next_required_step": "quick"}},
        {
            "summary": {
                "binder_pending_manual_verdict_count": 0,
                "console_rule": "rule",
                "aqp1_open_source_confirmation": "runs/aqp1_first_wave_source_confirmation_packet_current.md",
                "aqp1_open_follow_on": "runs/aqp1_first_wave_follow_on_packet_current.md",
            }
        },
        {
            "summary": {
                "next_required_step": "Open `runs/glut1_second_wave_source_confirmation_packet_current.md` before GLUT1 manual-verdict work.",
            },
            "rows": [],
        },
        {"summary": {"negative_slot_count_total": 6}},
        {"target_packets": []},
        {"rows": []},
    )

    assert "runs/glut1_second_wave_source_confirmation_packet_current.md" in payload["summary"]["day2_rule"]
