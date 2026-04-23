from __future__ import annotations

from tools import build_caix_result_review as mod
from tools.wetlab_target_render_utils import load_json


def test_build_caix_result_review_defaults_to_hold_without_mpro_resolution() -> None:
    payload = mod.build_payload(
        {},
        load_json(mod.DEFAULT_CAIX_LAUNCH_JSON),
        load_json(mod.DEFAULT_TCRUZI_LAUNCH_JSON),
    )
    summary = payload["summary"]

    assert summary["status"] == "caix_result_review_ready"
    assert summary["mpro_gate_state"] == "awaiting_result_context"
    assert summary["caix_gate_open"] is False
    assert summary["caix_gate_decision"] == "hold_until_mpro_result_ready_or_explicit_hold"
    assert summary["caix_review_state"] == "blocked_on_mpro_result_review"
    assert summary["caix_run_record_detected"] is False
    assert summary["caix_run_record_status"] == "not_detected"
    assert summary["successor_gate_open"] is False
    assert summary["successor_target"] == "T. cruzi PDE"


def test_build_caix_result_review_opens_when_mpro_is_result_ready() -> None:
    payload = mod.build_payload(
        {"summary": {"execution_state": "result_ready"}},
        load_json(mod.DEFAULT_CAIX_LAUNCH_JSON),
        load_json(mod.DEFAULT_TCRUZI_LAUNCH_JSON),
    )
    summary = payload["summary"]

    assert summary["mpro_gate_state"] == "result_ready"
    assert summary["caix_gate_open"] is True
    assert summary["caix_gate_decision"] == "open_for_caix_execution"
    assert summary["caix_review_state"] == "ready_to_capture_caix_result_review"
    assert summary["queue_status_now"] == "ready_after_previous_review"
    assert summary["successor_gate_state"] == "blocked_on_caix_result_review"
    assert summary["tcruzi_next_queue_state"] == "blocked_on_previous_review"


def test_build_caix_result_review_opens_tcruzi_when_caix_run_record_is_result_ready() -> None:
    payload = mod.build_payload(
        {"summary": {"execution_state": "result_ready"}},
        load_json(mod.DEFAULT_CAIX_LAUNCH_JSON),
        load_json(mod.DEFAULT_TCRUZI_LAUNCH_JSON),
        {"summary": {"execution_state": "result_ready", "run_started": True, "result_review_ready": True}},
    )
    summary = payload["summary"]

    assert summary["caix_run_record_detected"] is True
    assert summary["caix_execution_state"] == "result_ready"
    assert summary["caix_result_review_ready"] is True
    assert summary["caix_review_state"] == "caix_result_review_resolved"
    assert summary["queue_status_now"] == "result_ready_for_successor"
    assert summary["successor_gate_open"] is True
    assert summary["successor_gate_state"] == "open_for_tcruzi_execution"
    assert summary["tcruzi_next_queue_state"] == "ready_after_previous_review"


def test_build_caix_result_review_opens_tcruzi_when_caix_record_is_ready() -> None:
    payload = mod.build_payload(
        {"summary": {"execution_state": "result_ready"}},
        load_json(mod.DEFAULT_CAIX_LAUNCH_JSON),
        load_json(mod.DEFAULT_TCRUZI_LAUNCH_JSON),
        {"summary": {"status": "caix_run_record_ready", "result_review_ready": True, "inferred_run_state": "completed"}},
    )
    summary = payload["summary"]

    assert summary["caix_result_review_ready"] is True
    assert summary["successor_gate_open"] is True
    assert summary["successor_gate_state"] == "open_for_tcruzi_execution"


def test_build_caix_result_review_preserves_blocked_run_record_state() -> None:
    payload = mod.build_payload(
        {"summary": {"execution_state": "ready_to_launch"}},
        load_json(mod.DEFAULT_CAIX_LAUNCH_JSON),
        load_json(mod.DEFAULT_TCRUZI_LAUNCH_JSON),
        {"summary": {"execution_state": "blocked_on_previous_review", "result_review_ready": False}},
    )
    summary = payload["summary"]

    assert summary["caix_run_record_detected"] is True
    assert summary["caix_execution_state"] == "blocked_on_previous_review"
    assert summary["caix_result_review_ready"] is False
    assert summary["successor_gate_open"] is False
