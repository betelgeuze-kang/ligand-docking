from __future__ import annotations

from tools.wetlab import build_sarscov2_plpro_result_review as mod
from tools.wetlab_target_render_utils import load_json


def test_build_sarscov2_plpro_result_review_stays_blocked_without_cruzain_resolution() -> None:
    payload = mod.build_payload({}, load_json(mod.DEFAULT_PLPRO_LAUNCH_JSON), load_json(mod.DEFAULT_ALK2_LAUNCH_JSON))
    summary = payload["summary"]

    assert summary["status"] == "sarscov2_plpro_result_review_ready"
    assert summary["plpro_gate_open"] is False
    assert summary["queue_status_now"] == "blocked_on_previous_review"
    assert summary["successor_gate_open"] is False


def test_build_sarscov2_plpro_result_review_opens_alk2_after_resolved_plpro_record() -> None:
    payload = mod.build_payload(
        {"summary": {"execution_state": "result_ready"}},
        load_json(mod.DEFAULT_PLPRO_LAUNCH_JSON),
        load_json(mod.DEFAULT_ALK2_LAUNCH_JSON),
        {"summary": {"status": "completed", "run_started": True}},
    )
    summary = payload["summary"]

    assert summary["plpro_gate_open"] is True
    assert summary["plpro_result_review_ready"] is True
    assert summary["successor_gate_open"] is True
    assert summary["alk2_next_queue_state"] == "ready_after_previous_review"
