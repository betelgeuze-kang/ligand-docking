from __future__ import annotations

from tools import build_wetlab_master_execution_queue as queue_mod
from tools import build_wetlab_master_execution_console as mod


WAVE2_QUEUE_BLOCKED_UPSTREAM = {
    "summary": {
        "status": "wetlab_wave2_protein_run_queue_ready",
        "upstream_final2_gate_status": "wave2_release_blocked",
        "upstream_final2_gate_open": False,
        "ready_now_target_count": 0,
        "blocked_on_previous_review_count": 1,
        "blocked_on_target_content_count": 0,
    },
    "rows": [{"target_id": "Cathepsin K", "queue_status": "blocked_on_previous_review", "transition_status": "missing_transition_surface"}],
}

WAVE2_QUEUE_OPEN_BUT_PLACEHOLDER = {
    "summary": {
        "status": "wetlab_wave2_protein_run_queue_ready",
        "upstream_final2_gate_status": "open_after_lbdhodh_result_ready",
        "upstream_final2_gate_open": True,
        "ready_now_target_count": 0,
        "blocked_on_previous_review_count": 0,
        "blocked_on_target_content_count": 1,
    },
    "rows": [{"target_id": "Cathepsin K", "queue_status": "blocked_on_target_content", "transition_status": "missing_transition_surface"}],
}


def test_build_wetlab_master_execution_console_reports_global_state() -> None:
    master_queue = queue_mod.build_payload(
        {
            "summary": {"ready_now_target_count": 1, "blocked_on_previous_review_count": 2},
            "rows": [{"target_id": "SARS-CoV-2 Mpro", "queue_status": "ready_first", "transition_status": "sarscov2_mpro_run_status_ready"}],
        },
        {"summary": {"ready_now_target_count": 0, "blocked_on_previous_review_count": 3}, "rows": [{"target_id": "Cruzain", "queue_status": "blocked_on_previous_review"}]},
        {"summary": {"ready_now_target_count": 0, "blocked_on_previous_review_count": 1, "blocked_on_target_content_count": 1}, "rows": [{"target_id": "STK17B (DRAK2)", "queue_status": "blocked_on_previous_review"}, {"target_id": "Leishmania braziliensis DHODH", "queue_status": "blocked_on_target_content"}]},
        WAVE2_QUEUE_BLOCKED_UPSTREAM,
        {"summary": {"wave2_release_gate_status": "wave2_release_blocked", "wave2_release_blocked": True}},
    )
    payload = mod.build_payload(
        master_queue,
        {"summary": {"ready_now_target_count": 1, "blocked_on_previous_review_count": 2, "running_target_count": 0, "mpro_execution_state": "ready_to_launch", "last_runtime_target": "SARS-CoV-2 Mpro", "last_runtime_event": "reset"}},
        {"summary": {"ready_now_target_count": 0, "blocked_on_previous_review_count": 3, "running_target_count": 0, "last_runtime_target": "", "last_runtime_event": ""}},
        {"summary": {"ready_now_target_count": 0, "blocked_on_previous_review_count": 1, "running_target_count": 0, "last_runtime_target": "STK17B (DRAK2)", "last_runtime_event": "reset"}},
        {"summary": {"priority3_final_gate_open": False}},
        {"summary": {"next3_final_gate_open": False, "lbdhodh_content_ready": False, "lbdhodh_blockers": {"upstream_stk17b_result_review": "blocked", "compound_fill": "blocked"}, "rows": [{"current_signal": "blocked_on_previous_review"}]}},
        {"summary": {"status": "wetlab_master_runtime_runbook_ready"}},
        {"summary": {"ready_now_target_count": 0, "blocked_on_previous_review_count": 1, "running_target_count": 0, "last_runtime_target": "", "last_runtime_event": ""}},
        {"summary": {"final2_final_gate_open": False, "placeholder_target_count": 1, "missing_target_specific_packet_count": 1}},
    )
    summary = payload["summary"]

    assert summary["status"] == "wetlab_master_execution_console_ready"
    assert summary["chain_count"] == 4
    assert summary["queue_target_count"] == 5
    assert summary["ready_now_target_count"] == 1
    assert summary["blocked_on_previous_review_count"] == 7
    assert summary["blocked_on_target_content_count"] == 1
    assert summary["running_target_count"] == 0
    assert summary["resolved_target_count"] == 0
    assert summary["first_actionable_target"] == "SARS-CoV-2 Mpro"
    assert summary["first_actionable_chain"] == "priority3"
    assert summary["active_stack_level"] == "priority3"
    assert summary["active_target_id"] == "SARS-CoV-2 Mpro"
    assert summary["active_target_queue_status"] == "ready_first"
    assert summary["active_target_execution_state"] == "ready_to_launch"
    assert summary["wave2_release_gate_status"] == "wave2_release_blocked"
    assert summary["wave2_release_blocked"] is True
    assert summary["wave2_ready"] is False
    assert summary["wave2_queue_status"] == "blocked_on_previous_review"
    assert summary["next3_gate_open"] is False
    assert summary["final2_gate_open"] is False
    assert summary["wave2_gate_open"] is False
    assert summary["lbdhodh_stk17b_gate_state"] == "blocked_on_previous_review"
    assert summary["lbdhodh_queue_status_now"] == "blocked_on_previous_review"
    assert summary["lbdhodh_launch_readiness"] == "blocked_on_compound_fill"
    assert summary["lbdhodh_content_ready"] is False
    assert summary["master_runbook_status"] == "wetlab_master_runtime_runbook_ready"
    assert summary["next_required_step"] == "Advance the serialized wet-lab chain with SARS-CoV-2 Mpro from priority3."
    assert payload["rows"][0]["last_runtime_target"] == "SARS-CoV-2 Mpro"
    assert payload["rows"][0]["last_runtime_event"] == "reset"


def test_build_wetlab_master_execution_console_propagates_priority3_start_state_and_wave2_gate() -> None:
    master_queue = queue_mod.build_payload(
        {
            "summary": {"ready_now_target_count": 0, "blocked_on_previous_review_count": 2, "running_target_count": 1},
            "rows": [{"target_id": "SARS-CoV-2 Mpro", "queue_status": "running_first", "transition_status": "sarscov2_mpro_run_status_ready"}],
        },
        {"summary": {"ready_now_target_count": 0, "blocked_on_previous_review_count": 3}, "rows": [{"target_id": "Cruzain", "queue_status": "blocked_on_previous_review"}]},
        {"summary": {"ready_now_target_count": 0, "blocked_on_previous_review_count": 1, "blocked_on_target_content_count": 1}, "rows": [{"target_id": "STK17B (DRAK2)", "queue_status": "blocked_on_previous_review"}, {"target_id": "Leishmania braziliensis DHODH", "queue_status": "blocked_on_target_content"}]},
        WAVE2_QUEUE_OPEN_BUT_PLACEHOLDER,
    )
    payload = mod.build_payload(
        master_queue,
        {"summary": {"ready_now_target_count": 0, "blocked_on_previous_review_count": 2, "running_target_count": 1, "mpro_execution_state": "running", "last_runtime_target": "SARS-CoV-2 Mpro", "last_runtime_event": "start"}},
        {"summary": {"ready_now_target_count": 0, "blocked_on_previous_review_count": 3, "running_target_count": 0, "last_runtime_target": "", "last_runtime_event": ""}},
        {"summary": {"ready_now_target_count": 0, "blocked_on_previous_review_count": 1, "running_target_count": 0, "last_runtime_target": "STK17B (DRAK2)", "last_runtime_event": "reset"}},
        {"summary": {"priority3_final_gate_open": False}},
        {
            "summary": {
                "next3_final_gate_open": False,
                "lbdhodh_content_ready": False,
                "lbdhodh_queue_status": "blocked_on_target_content",
                "rows": [{"current_signal": "blocked_on_previous_review"}, {"current_signal": "blocked_on_target_content"}],
                "stack_gate_states": {
                    "stk17b": {"queue_status": "blocked_on_previous_review", "execution_state": "blocked_on_previous_review"},
                    "lbdhodh": {
                        "queue_status": "blocked_on_target_content",
                        "execution_state": "blocked_on_target_content",
                        "content_ready": False,
                        "upstream_gate_open": False,
                    },
                },
                "lbdhodh_blockers": {"upstream_stk17b_result_review": "blocked", "compound_fill": "blocked"},
            }
        },
        {"summary": {"status": "wetlab_master_runtime_runbook_ready"}},
        {"summary": {"ready_now_target_count": 0, "blocked_on_previous_review_count": 0, "blocked_on_target_content_count": 1, "running_target_count": 0, "last_runtime_target": "", "last_runtime_event": ""}},
        {"summary": {"final2_final_gate_open": True, "placeholder_target_count": 5, "missing_target_specific_packet_count": 5}},
    )
    summary = payload["summary"]

    assert summary["status"] == "wetlab_master_execution_console_ready"
    assert summary["queue_target_count"] == 5
    assert summary["ready_now_target_count"] == 0
    assert summary["blocked_on_previous_review_count"] == 6
    assert summary["blocked_on_target_content_count"] == 2
    assert summary["running_target_count"] == 1
    assert summary["resolved_target_count"] == 0
    assert summary["active_stack_level"] == "priority3"
    assert summary["active_target_id"] == "SARS-CoV-2 Mpro"
    assert summary["active_target_queue_status"] == "running_first"
    assert summary["active_target_execution_state"] == "running"
    assert summary["stack_gate_states"]["priority3"]["active_target_execution_state"] == "running"
    assert summary["stack_gate_states"]["priority3"]["active_target_queue_status"] == "running_first"
    assert summary["lbdhodh_blockers"] == {"upstream_stk17b_result_review": "blocked", "compound_fill": "blocked"}
    assert summary["next3_gate_open"] is False
    assert summary["final2_gate_open"] is False
    assert summary["wave2_gate_open"] is True
    assert summary["lbdhodh_stk17b_gate_state"] == "blocked_on_previous_review"
    assert summary["lbdhodh_queue_status_now"] == "blocked_on_target_content"
    assert summary["lbdhodh_launch_readiness"] == "blocked_on_compound_fill"
    assert summary["lbdhodh_content_ready"] is False
    assert summary["master_runbook_status"] == "wetlab_master_runtime_runbook_ready"
    assert summary["wave2_release_blocked"] is False
    assert summary["wave2_queue_status"] == "blocked_on_target_content"
    assert summary["next_required_step"] == "Advance the serialized wet-lab chain with SARS-CoV-2 Mpro from priority3."


def test_build_wetlab_master_execution_console_surfaces_wave2_tcruzi_krs1_when_it_is_the_active_row() -> None:
    master_queue = queue_mod.build_payload(
        {"summary": {"ready_now_target_count": 0, "blocked_on_previous_review_count": 0}, "rows": []},
        {"summary": {"ready_now_target_count": 0, "blocked_on_previous_review_count": 0}, "rows": []},
        {
            "summary": {
                "ready_now_target_count": 0,
                "blocked_on_previous_review_count": 1,
                "blocked_on_target_content_count": 1,
            },
            "rows": [
                {"target_id": "STK17B (DRAK2)", "queue_status": "blocked_on_previous_review"},
                {"target_id": "Leishmania braziliensis DHODH", "queue_status": "blocked_on_target_content"},
            ],
        },
        {
            "summary": {
                "status": "wetlab_wave2_protein_run_queue_ready",
                "upstream_final2_gate_status": "open_after_lbdhodh_result_ready",
                "upstream_final2_gate_open": True,
                "ready_now_target_count": 0,
                "blocked_on_previous_review_count": 1,
                "blocked_on_target_content_count": 0,
                "running_target_count": 0,
                "resolved_target_count": 0,
            },
            "rows": [{"target_id": "T. cruzi KRS1", "queue_status": "blocked_on_previous_review", "transition_status": "tcruzi_krs1_result_review_ready"}],
        },
        {"summary": {"wave2_release_gate_status": "open_after_tcruzi_result_ready", "wave2_release_blocked": False}},
    )
    payload = mod.build_payload(
        master_queue,
        {"summary": {"ready_now_target_count": 0, "blocked_on_previous_review_count": 0, "running_target_count": 0, "last_runtime_target": "", "last_runtime_event": ""}},
        {"summary": {"ready_now_target_count": 0, "blocked_on_previous_review_count": 0, "running_target_count": 0, "last_runtime_target": "", "last_runtime_event": ""}},
        {"summary": {"ready_now_target_count": 0, "blocked_on_previous_review_count": 0, "running_target_count": 0, "last_runtime_target": "", "last_runtime_event": ""}},
        {"summary": {"priority3_final_gate_open": False}},
        {"summary": {"next3_final_gate_open": False, "lbdhodh_content_ready": False, "rows": [{"current_signal": "blocked_on_previous_review"}]}},
        {"summary": {"status": "wetlab_master_runtime_runbook_ready"}},
        {"summary": {"ready_now_target_count": 0, "blocked_on_previous_review_count": 1, "running_target_count": 0, "last_runtime_target": "T. cruzi KRS1", "last_runtime_event": "reset"}},
        {"summary": {"final2_final_gate_open": True, "placeholder_target_count": 0, "missing_target_specific_packet_count": 0}},
    )
    summary = payload["summary"]

    assert summary["active_stack_level"] == "final2"
    assert summary["active_target_id"] == "STK17B (DRAK2)"
    assert summary["active_target_queue_status"] == "blocked_on_previous_review"
    assert summary["stack_gate_states"]["wave2"]["active_target_id"] == "T. cruzi KRS1"
    assert summary["stack_gate_states"]["wave2"]["active_target_queue_status"] == "blocked_on_previous_review"
    assert summary["wave2_gate_open"] is True
    assert summary["wave2_queue_status"] == "blocked_on_previous_review"
    assert summary["lbdhodh_blockers"] == {"upstream_stk17b_result_review": "blocked", "compound_fill": "blocked"}
