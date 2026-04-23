from __future__ import annotations

from tools import build_wetlab_next3_runtime_runbook as mod


def test_build_wetlab_next3_runtime_runbook() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "wetlab_next3_protein_run_queue_ready", "ready_now_target_count": 0, "blocked_on_previous_review_count": 3}},
        {"summary": {"status": "wetlab_next3_gate_refresh_ready", "cruzain_execution_state": "blocked_on_previous_review", "plpro_review_state": "blocked_on_cruzain_result_review", "alk2_execution_state": "blocked_on_previous_review"}},
    )
    summary = payload["summary"]

    assert summary["status"] == "wetlab_next3_runtime_runbook_ready"
    assert summary["command_row_count"] == 10
    assert payload["rows"][0]["target_id"] == "Cruzain"
    assert payload["rows"][4]["target_id"] == "SARS-CoV-2 PLpro"
    assert payload["rows"][7]["target_id"] == "ALK2"
