from __future__ import annotations

from tools.wetlab import build_cruzain_run_status as mod
from tools.wetlab_target_render_utils import load_json


def test_build_cruzain_run_status_defaults_to_blocked_until_priority3_resolves() -> None:
    payload = mod.build_payload({}, load_json(mod.DEFAULT_LAUNCH_JSON), {"summary": {"status": "ready_to_launch"}})
    summary = payload["summary"]

    assert summary["status"] == "cruzain_run_status_ready"
    assert summary["execution_state"] == "blocked_on_previous_review"
    assert summary["queue_status_now"] == "blocked_on_previous_review"
    assert summary["plpro_gate_state"] == "blocked_by_cruzain_first_slot"


def test_build_cruzain_run_status_opens_plpro_after_resolved_record() -> None:
    payload = mod.build_payload(
        {"summary": {"wave2_release_blocked": False, "wave2_release_gate_status": "open_after_tcruzi_result_ready"}},
        load_json(mod.DEFAULT_LAUNCH_JSON),
        {"summary": {"status": "completed", "run_started": True}},
    )
    summary = payload["summary"]

    assert summary["execution_state"] == "result_ready"
    assert summary["result_review_ready"] is True
    assert summary["plpro_gate_state"] == "open_for_plpro_review"
    assert summary["plpro_next_queue_state"] == "ready_after_previous_review"
