from __future__ import annotations

from tools import build_sarscov2_mpro_run_record as mod
from tools.wetlab_target_render_utils import load_json


def test_build_sarscov2_mpro_run_record_defaults_to_ready_to_launch() -> None:
    payload = mod.build_payload(
        load_json(mod.DEFAULT_LAUNCH_JSON),
        load_json(mod.DEFAULT_ASSAY_JSON),
        load_json(mod.DEFAULT_GO_NO_GO_JSON),
        {},
        {},
    )
    summary = payload["summary"]

    assert summary["status"] == "ready_to_launch"
    assert summary["artifact_kind"] == "run_record"
    assert summary["run_started"] is False
    assert summary["result_review_ready"] is False
    assert summary["current_stage"] == "launch_packet_frozen_pending_execution"
    assert summary["result_class"] == "awaiting_result"
    assert summary["progress_status"] == "not_detected"
    assert summary["result_status"] == "not_detected"
    assert payload["rows"][2]["record_item"] == "live_progress"
    assert payload["rows"][2]["current_signal"] == "not_detected"


def test_build_sarscov2_mpro_run_record_marks_completed_result_ready() -> None:
    payload = mod.build_payload(
        load_json(mod.DEFAULT_LAUNCH_JSON),
        load_json(mod.DEFAULT_ASSAY_JSON),
        load_json(mod.DEFAULT_GO_NO_GO_JSON),
        {
            "summary": {
                "status": "running",
                "run_started": True,
                "active_stage_label": "host_panel",
                "started_at": "2026-03-29T09:15:00",
                "last_update_at": "2026-03-29T12:30:00",
            }
        },
        {
            "summary": {
                "status": "completed",
                "result_review_ready": True,
                "decision_case": "promote_clean_mpro_favored",
                "completed_at": "2026-03-29T16:45:00",
            }
        },
    )
    summary = payload["summary"]

    assert summary["status"] == "completed"
    assert summary["run_started"] is True
    assert summary["result_review_ready"] is True
    assert summary["explicit_hold"] is False
    assert summary["current_stage"] == "result_review_complete"
    assert summary["active_stage_label"] == "host_panel"
    assert summary["result_class"] == "promote_clean_mpro_favored"
    assert summary["started_at"] == "2026-03-29T09:15:00"
    assert summary["completed_at"] == "2026-03-29T16:45:00"
    assert payload["rows"][3]["current_signal"] == "completed"
    assert payload["rows"][3]["detail"] == "promote_clean_mpro_favored"


def test_build_sarscov2_mpro_run_record_leaves_neutral_complete_unclassified() -> None:
    payload = mod.build_payload(
        load_json(mod.DEFAULT_LAUNCH_JSON),
        load_json(mod.DEFAULT_ASSAY_JSON),
        load_json(mod.DEFAULT_GO_NO_GO_JSON),
        {
            "summary": {
                "status": "running",
                "run_started": True,
                "active_stage_label": "fluorogenic_primary_assay",
                "started_at": "2026-03-29T20:00:00",
            }
        },
        {
            "summary": {
                "status": "completed",
                "result_review_ready": True,
                "completed_at": "2026-03-29T20:30:00",
            }
        },
    )
    summary = payload["summary"]

    assert summary["status"] == "completed"
    assert summary["result_review_ready"] is True
    assert summary["explicit_hold"] is False
    assert summary["result_class"] == "result_ready_pending_classification"
    assert payload["rows"][3]["detail"] == "result_ready_pending_classification"
