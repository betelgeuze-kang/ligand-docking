from __future__ import annotations

from tools import build_wetlab_master_terminal_review as mod


def test_build_wetlab_master_terminal_review_marks_complete() -> None:
    master_queue = {
        "summary": {
            "queue_target_count": 13,
            "resolved_target_count": 13,
            "running_target_count": 0,
            "ready_now_target_count": 0,
            "active_target_id": "",
            "stack_gate_states": {
                "priority3": {"chain_rank": 1, "queue_target_count": 3, "resolved_target_count": 3, "all_rows_resolved": True},
                "next3": {"chain_rank": 2, "queue_target_count": 3, "resolved_target_count": 3, "all_rows_resolved": True},
                "final2": {"chain_rank": 3, "queue_target_count": 2, "resolved_target_count": 2, "all_rows_resolved": True},
                "wave2": {"chain_rank": 4, "queue_target_count": 5, "resolved_target_count": 5, "all_rows_resolved": True},
            },
        }
    }
    master_console = {"summary": {}}
    export_bundle = {"summary": {"ready_to_send_count": 5}, "rows": [{"track_id": "DNDi_IPK", "status": "ready_to_send"}, {"track_id": "READDI_Korea", "status": "ready_to_send"}]}
    outreach = {"summary": {"primary_track_order": "DNDi_IPK -> M4K_open_science -> READDI_Korea -> oncology_condition_aware -> SGC_dark_kinase"}}

    payload = mod.build_payload(master_queue, master_console, export_bundle, outreach)
    summary = payload["summary"]
    assert summary["status"] == "wetlab_master_terminal_review_ready"
    assert summary["campaign_terminal_state"] == "complete"
    assert summary["all_chains_resolved"] is True
    assert summary["resolved_target_count"] == 13
    assert len(payload["rows"]) == 4
    assert payload["rows"][-1]["terminal_state"] == "complete"
