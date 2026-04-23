from __future__ import annotations

from tools import build_tcruzi_pde_result_review as mod
from tools.wetlab_target_render_utils import load_json


def test_build_tcruzi_pde_result_review_blocks_then_opens_final_gate() -> None:
    launch_payload = load_json(mod.DEFAULT_LAUNCH_JSON)

    blocked = mod.build_payload({}, launch_payload)
    blocked_summary = blocked["summary"]

    assert blocked_summary["status"] == "tcruzi_pde_result_review_ready"
    assert blocked_summary["queue_status_now"] == "blocked_on_previous_review"
    assert blocked_summary["execution_gate_open"] is False
    assert blocked_summary["wave2_release_blocked"] is True
    assert blocked["rows"][0]["gate_status"] == "pending_upstream_review"

    ready = mod.build_payload(
        {
            "summary": {
                "successor_gate_open": True,
                "caix_review_state": "caix_result_review_resolved",
                "status": "caix_result_review_ready",
            }
        },
        launch_payload,
    )
    ready_summary = ready["summary"]

    assert ready_summary["status"] == "tcruzi_pde_result_review_ready"
    assert ready_summary["upstream_dependency_status"] == "caix_result_review_ready"
    assert ready_summary["execution_gate_open"] is True
    assert ready_summary["queue_status_now"] == "ready_after_previous_review"
    assert ready_summary["result_review_gate_status"] == "ready_for_final_result_review"
    assert ready_summary["wave2_release_blocked"] is True
    assert ready_summary["final_review_role"] == "final_review_step_before_any_wave2_release"
    assert ready["rows"][0]["release_effect"] == "unlock_tcruzi_execution"


def test_build_tcruzi_pde_result_review_opens_wave2_when_live_run_record_is_result_ready() -> None:
    launch_payload = load_json(mod.DEFAULT_LAUNCH_JSON)

    payload = mod.build_payload(
        {
            "summary": {
                "successor_gate_open": True,
                "caix_review_state": "caix_result_review_resolved",
                "status": "caix_result_review_ready",
            }
        },
        launch_payload,
        {"summary": {"execution_state": "result_ready", "run_started": True, "result_review_ready": True}},
    )
    summary = payload["summary"]

    assert summary["tcruzi_run_record_detected"] is True
    assert summary["tcruzi_execution_state"] == "result_ready"
    assert summary["queue_status_now"] == "result_ready_for_wave2_release"
    assert summary["result_review_gate_status"] == "result_ready"
    assert summary["wave2_release_gate_status"] == "open_after_tcruzi_result_ready"
    assert summary["wave2_release_blocked"] is False
