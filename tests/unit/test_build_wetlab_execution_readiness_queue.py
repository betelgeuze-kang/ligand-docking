from __future__ import annotations

from tools import build_wetlab_execution_readiness_queue as mod


def test_build_wetlab_execution_readiness_queue() -> None:
    payload = mod.build_payload(
        wetlab_dashboard_payload={
            "broad_screen_primary_watch_liveness": "stale",
            "broad_screen_antitarget_watch_liveness": "detached",
            "selected_allatom_wetlab_gate_pass": False,
            "selected_allatom_focus_label": "T. cruzi PDE / tcruzi_pde_allatom_review_packet",
            "selected_allatom_actionability_block_reason": "translation/commercial hard gate failed",
        },
        wetlab_final_payload={
            "ready_to_send_track_count": 5,
            "broad_screen_execution_ready_now_row_count": 0,
            "broad_screen_antitarget_ready_now_row_count": 1,
        },
    )

    summary = payload["summary"]
    assert summary["row_count"] == 5
    assert summary["blocked_count"] == 3
    assert summary["partial_count"] == 1
    assert summary["ready_count"] == 1
    assert summary["watch_gap_count"] == 2
    assert summary["execution_ready_now_row_count"] == 0
    assert summary["antitarget_ready_now_row_count"] == 1
    assert summary["ready_to_send_track_count"] == 5
    assert summary["selected_allatom_wetlab_gate_pass"] is False
    assert "primary_exec=0 ready_now (stale)" in summary["status_line"]
    assert "antitarget_exec=1 ready_now (detached)" in summary["status_line"]
    rows = {row["lane_id"]: row for row in payload["rows"]}
    assert rows["primary_dispatch_lane"]["status"] == "blocked"
    assert rows["antitarget_dispatch_lane"]["status"] == "partial"
    assert rows["selected_allatom_gate"]["status"] == "blocked"
    assert rows["watch_loop_recovery"]["status"] == "blocked"
    assert rows["partner_send_tracks"]["status"] == "ready"


def test_build_wetlab_execution_readiness_queue_marks_attached_watchers_as_recovered() -> None:
    payload = mod.build_payload(
        wetlab_dashboard_payload={
            "broad_screen_primary_watch_liveness": "attached",
            "broad_screen_antitarget_watch_liveness": "attached",
            "broad_screen_throughput_execute_ready": True,
            "selected_allatom_wetlab_gate_pass": False,
            "selected_allatom_focus_label": "T. cruzi PDE / tcruzi_pde_allatom_review_packet",
            "selected_allatom_actionability_block_reason": "translation/commercial hard gate failed",
        },
        wetlab_final_payload={
            "campaign_terminal_state": "complete",
            "broad_screen_execution_queue_ready": True,
            "ready_to_send_track_count": 5,
            "broad_screen_execution_ready_now_row_count": 0,
            "broad_screen_antitarget_ready_now_row_count": 1,
        },
    )

    summary = payload["summary"]
    assert summary["blocked_count"] == 1
    assert summary["partial_count"] == 0
    assert summary["ready_count"] == 4
    assert summary["watch_gap_count"] == 0
    assert "primary_exec=0 ready_now (attached; dispatch_complete)" in summary["status_line"]
    assert "antitarget_exec=1 ready_now (attached)" in summary["status_line"]
    assert "completed primary dispatch lane" in summary["next_required_step"]
    rows = {row["lane_id"]: row for row in payload["rows"]}
    assert rows["primary_dispatch_lane"]["status"] == "ready"
    assert rows["antitarget_dispatch_lane"]["status"] == "ready"
    assert "completed primary dispatch lane warm" in rows["primary_dispatch_lane"]["next_required_action"]
    assert rows["watch_loop_recovery"]["status"] == "ready"
    assert "attached antitarget watch loop" in rows["antitarget_dispatch_lane"]["next_required_action"]


def test_completed_primary_and_green_selected_gate_needs_no_new_primary_row() -> None:
    payload = mod.build_payload(
        wetlab_dashboard_payload={
            "broad_screen_primary_watch_liveness": "attached",
            "broad_screen_antitarget_watch_liveness": "attached",
            "broad_screen_throughput_execute_ready": True,
            "selected_allatom_wetlab_gate_pass": True,
            "selected_allatom_focus_label": "T. cruzi PDE / tcruzi_pde_allatom_review_packet",
        },
        wetlab_final_payload={
            "campaign_terminal_state": "complete",
            "broad_screen_execution_queue_ready": True,
            "ready_to_send_track_count": 5,
            "broad_screen_execution_ready_now_row_count": 0,
            "broad_screen_antitarget_ready_now_row_count": 1,
        },
    )

    summary = payload["summary"]
    assert summary["blocked_count"] == 0
    assert summary["partial_count"] == 0
    assert summary["watch_gap_count"] == 0
    assert "Wetlab execution readiness is green" in summary["next_required_step"]
    assert "Create at least one primary execution-ready row" not in summary["next_required_step"]
