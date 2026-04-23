from __future__ import annotations

from tools import build_wetlab_master_runtime_runbook as mod


def test_build_wetlab_master_runtime_runbook_concatenates_chain_rows() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "ready_now_target_count": 1,
                "blocked_on_previous_review_count": 6,
                "blocked_on_target_content_count": 2,
                "wave2_release_gate_status": "open_after_lbdhodh_result_ready",
                "wave2_release_blocked": False,
                "wave2_ready": False,
                "wave2_queue_status": "blocked_on_target_content",
            }
        },
        {"rows": [{"target_id": "SARS-CoV-2 Mpro", "event": "start"}]},
        {"rows": [{"target_id": "Cruzain", "event": "start"}]},
        {"rows": [{"target_id": "STK17B (DRAK2)", "event": "start"}]},
        {"rows": [{"target_id": "Cathepsin K", "event": "start"}]},
    )
    summary = payload["summary"]

    assert summary["status"] == "wetlab_master_runtime_runbook_ready"
    assert summary["chain_count"] == 4
    assert summary["command_row_count"] == 4
    assert summary["ready_now_target_count"] == 1
    assert summary["blocked_on_previous_review_count"] == 6
    assert summary["blocked_on_target_content_count"] == 2
    assert summary["wave2_release_gate_status"] == "open_after_lbdhodh_result_ready"
    assert summary["wave2_release_blocked"] is False
    assert summary["wave2_ready"] is False
    assert summary["wave2_queue_status"] == "blocked_on_target_content"
    assert summary["next_required_step"] == "Use the chain-specific runtime command for the first actionable target shown in the master queue, and keep every downstream chain blocked until upstream reviews resolve."
    assert payload["rows"][0]["chain_id"] == "priority3"
    assert payload["rows"][2]["chain_id"] == "final2"
    assert payload["rows"][3]["chain_id"] == "wave2"
