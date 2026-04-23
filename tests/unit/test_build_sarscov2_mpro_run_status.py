from __future__ import annotations

from tools import build_sarscov2_mpro_run_status as mod
from tools.wetlab_target_render_utils import load_json


def test_build_sarscov2_mpro_run_status_defaults_to_ready_to_launch() -> None:
    payload = mod.build_payload(load_json(mod.DEFAULT_LAUNCH_JSON), {})
    summary = payload["summary"]

    assert summary["status"] == "sarscov2_mpro_run_status_ready"
    assert summary["execution_state"] == "ready_to_launch"
    assert summary["queue_status_now"] == "ready_first"
    assert summary["caix_gate_state"] == "blocked_by_mpro_first_slot"
    assert summary["caix_next_queue_state"] == "blocked_on_previous_review"


def test_build_sarscov2_mpro_run_status_opens_caix_after_completed_record() -> None:
    payload = mod.build_payload(
        load_json(mod.DEFAULT_LAUNCH_JSON),
        {"summary": {"status": "completed", "run_started": True}},
    )
    summary = payload["summary"]

    assert summary["execution_state"] == "result_ready"
    assert summary["result_review_ready"] is True
    assert summary["caix_gate_state"] == "open_for_caix_review"
    assert summary["caix_next_queue_state"] == "ready_after_previous_review"
