from __future__ import annotations

import pytest

from tools import build_caix_run_record as mod
from tools.wetlab_target_render_utils import load_json


def test_build_caix_run_record_defaults_to_blocked_when_upstream_gate_is_closed() -> None:
    payload = mod.build_payload(
        load_json(mod.DEFAULT_LAUNCH_JSON),
        {
            "summary": {
                "status": "caix_result_review_ready",
                "caix_gate_open": False,
                "caix_review_state": "blocked_on_mpro_result_review",
            }
        },
        load_json(mod.DEFAULT_TCRUZI_LAUNCH_JSON),
    )
    summary = payload["summary"]

    assert summary["status"] == "caix_run_record_ready"
    assert summary["execution_state"] == "blocked_on_previous_review"
    assert summary["queue_status_now"] == "blocked_on_previous_review"
    assert summary["run_started"] is False
    assert summary["result_review_ready"] is False
    assert summary["successor_gate_open"] is False
    assert (
        summary["successor_gate_state"]
        == "blocked_until_caix_result_ready_or_explicit_hold"
    )


def test_build_caix_run_record_becomes_ready_to_launch_after_gate_opens() -> None:
    payload = mod.build_payload(
        load_json(mod.DEFAULT_LAUNCH_JSON),
        {
            "summary": {
                "status": "caix_result_review_ready",
                "caix_gate_open": True,
                "caix_review_state": "ready_to_capture_caix_result_review",
            }
        },
        load_json(mod.DEFAULT_TCRUZI_LAUNCH_JSON),
    )
    summary = payload["summary"]

    assert summary["execution_state"] == "ready_to_launch"
    assert summary["queue_status_now"] == "ready_after_previous_review"
    assert summary["run_started"] is False
    assert summary["result_review_ready"] is False
    assert summary["successor_gate_open"] is False


def test_build_caix_run_record_opens_tcruzi_after_result_ready() -> None:
    payload = mod.build_payload(
        load_json(mod.DEFAULT_LAUNCH_JSON),
        {
            "summary": {
                "status": "caix_result_review_ready",
                "caix_gate_open": True,
                "caix_review_state": "ready_to_capture_caix_result_review",
            }
        },
        load_json(mod.DEFAULT_TCRUZI_LAUNCH_JSON),
        run_state="result_ready",
    )
    summary = payload["summary"]

    assert summary["execution_state"] == "result_ready"
    assert summary["queue_status_now"] == "result_ready_for_review"
    assert summary["run_started"] is True
    assert summary["result_review_ready"] is True
    assert summary["successor_gate_open"] is True
    assert summary["successor_gate_state"] == "open_for_tcruzi_execution"
    assert summary["successor_next_queue_state"] == "ready_after_previous_review"


def test_build_caix_run_record_rejects_advanced_state_when_gate_is_closed() -> None:
    with pytest.raises(ValueError):
        mod.build_payload(
            load_json(mod.DEFAULT_LAUNCH_JSON),
            {
                "summary": {
                    "status": "caix_result_review_ready",
                    "caix_gate_open": False,
                    "caix_review_state": "blocked_on_mpro_result_review",
                }
            },
            load_json(mod.DEFAULT_TCRUZI_LAUNCH_JSON),
            run_state="running",
        )


def test_build_caix_run_record_marks_running_when_live_progress_exists() -> None:
    payload = mod.build_payload(
        load_json(mod.DEFAULT_LAUNCH_JSON),
        {
            "summary": {
                "status": "caix_result_review_ready",
                "caix_gate_open": True,
                "caix_review_state": "ready_to_capture_caix_result_review",
            }
        },
        load_json(mod.DEFAULT_TCRUZI_LAUNCH_JSON),
        live_progress={
            "summary": {
                "status": "running",
                "run_started": True,
                "active_stage_label": "acidic_buffer_primary_assay",
            }
        },
    )
    summary = payload["summary"]

    assert summary["live_progress_detected"] is True
    assert summary["execution_state"] == "running"
    assert summary["queue_status_now"] == "running_active_slot"
    assert summary["run_started"] is True
    assert summary["result_review_ready"] is False
    assert summary["current_stage"] == "acidic_buffer_primary_assay"
    assert summary["successor_gate_open"] is False


def test_build_caix_run_record_opens_tcruzi_from_result_summary() -> None:
    payload = mod.build_payload(
        load_json(mod.DEFAULT_LAUNCH_JSON),
        {
            "summary": {
                "status": "caix_result_review_ready",
                "caix_gate_open": True,
                "caix_review_state": "ready_to_capture_caix_result_review",
            }
        },
        load_json(mod.DEFAULT_TCRUZI_LAUNCH_JSON),
        result_summary={
            "summary": {
                "status": "completed",
                "result_review_ready": True,
            }
        },
    )
    summary = payload["summary"]

    assert summary["result_summary_detected"] is True
    assert summary["execution_state"] == "result_ready"
    assert summary["queue_status_now"] == "result_ready_for_review"
    assert summary["result_review_ready"] is True
    assert summary["successor_gate_open"] is True
    assert summary["successor_gate_state"] == "open_for_tcruzi_execution"
