from __future__ import annotations

import pytest

from tools import build_tcruzi_pde_run_record as mod
from tools.wetlab_target_render_utils import load_json


def test_build_tcruzi_pde_run_record_defaults_to_blocked_when_caix_gate_is_closed() -> None:
    payload = mod.build_payload(
        load_json(mod.DEFAULT_LAUNCH_JSON),
        {},
        load_json(mod.DEFAULT_GO_NO_GO_JSON),
    )
    summary = payload["summary"]

    assert summary["status"] == "tcruzi_pde_run_record_ready"
    assert summary["execution_state"] == "blocked_on_previous_review"
    assert summary["queue_status_now"] == "blocked_on_previous_review"
    assert summary["run_started"] is False
    assert summary["result_review_ready"] is False
    assert summary["upstream_gate_open"] is False


def test_build_tcruzi_pde_run_record_becomes_ready_after_caix_gate_opens() -> None:
    payload = mod.build_payload(
        load_json(mod.DEFAULT_LAUNCH_JSON),
        {
            "summary": {
                "status": "caix_result_review_ready",
                "successor_gate_open": True,
                "caix_review_state": "caix_result_review_resolved",
            }
        },
        load_json(mod.DEFAULT_GO_NO_GO_JSON),
    )
    summary = payload["summary"]

    assert summary["execution_state"] == "ready_to_launch"
    assert summary["queue_status_now"] == "ready_after_previous_review"
    assert summary["run_started"] is False
    assert summary["result_review_ready"] is False


def test_build_tcruzi_pde_run_record_marks_running_from_live_progress() -> None:
    payload = mod.build_payload(
        load_json(mod.DEFAULT_LAUNCH_JSON),
        {
            "summary": {
                "status": "caix_result_review_ready",
                "successor_gate_open": True,
                "caix_review_state": "caix_result_review_resolved",
            }
        },
        load_json(mod.DEFAULT_GO_NO_GO_JSON),
        live_progress={
            "summary": {
                "status": "running",
                "run_started": True,
                "active_stage_label": "parasite_vs_human_primary_assay",
            }
        },
    )
    summary = payload["summary"]

    assert summary["live_progress_detected"] is True
    assert summary["execution_state"] == "running"
    assert summary["queue_status_now"] == "running_active_slot"
    assert summary["current_stage"] == "parasite_vs_human_primary_assay"
    assert summary["result_review_ready"] is False


def test_build_tcruzi_pde_run_record_becomes_result_ready_from_summary() -> None:
    payload = mod.build_payload(
        load_json(mod.DEFAULT_LAUNCH_JSON),
        {
            "summary": {
                "status": "caix_result_review_ready",
                "successor_gate_open": True,
                "caix_review_state": "caix_result_review_resolved",
            }
        },
        load_json(mod.DEFAULT_GO_NO_GO_JSON),
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
    assert summary["queue_status_now"] == "result_ready_for_wave2_release"
    assert summary["result_review_ready"] is True
    assert summary["explicit_hold"] is False


def test_build_tcruzi_pde_run_record_rejects_running_before_upstream_gate_opens() -> None:
    with pytest.raises(ValueError):
        mod.build_payload(
            load_json(mod.DEFAULT_LAUNCH_JSON),
            {},
            load_json(mod.DEFAULT_GO_NO_GO_JSON),
            run_state="running",
        )
