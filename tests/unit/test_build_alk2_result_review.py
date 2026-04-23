from __future__ import annotations

from tools import build_alk2_result_review as mod
from tools.wetlab_target_render_utils import load_json


def test_build_alk2_result_review_stays_blocked_without_plpro_resolution() -> None:
    payload = mod.build_payload({}, load_json(mod.DEFAULT_LAUNCH_JSON))
    summary = payload["summary"]

    assert summary["status"] == "alk2_result_review_ready"
    assert summary["execution_gate_open"] is False
    assert summary["queue_status_now"] == "blocked_on_previous_review"
    assert summary["next_queue_release_blocked"] is True


def test_build_alk2_result_review_opens_release_after_resolved_record() -> None:
    payload = mod.build_payload(
        {"summary": {"successor_gate_open": True, "plpro_review_state": "plpro_result_review_resolved"}},
        load_json(mod.DEFAULT_LAUNCH_JSON),
        {"summary": {"status": "completed", "run_started": True}},
    )
    summary = payload["summary"]

    assert summary["execution_gate_open"] is True
    assert summary["alk2_result_review_ready"] is True
    assert summary["next_queue_release_blocked"] is False
    assert summary["next_queue_release_gate_status"] == "open_after_alk2_result_ready"
