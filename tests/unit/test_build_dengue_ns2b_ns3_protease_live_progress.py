from __future__ import annotations

from tools import build_dengue_ns2b_ns3_protease_live_progress as mod


def test_build_dengue_ns2b_ns3_protease_live_progress_defaults_to_not_started() -> None:
    payload = mod.build_payload({"summary": {"status": "dengue_ns2b_ns3_protease_launch_packet_ready", "partner_track_id": "IPK_dengue"}})
    summary = payload["summary"]

    assert summary["status"] == "not_started"
    assert summary["artifact_kind"] == "live_progress"
    assert summary["run_started"] is False
    assert summary["current_stage"] == "launch_packet_frozen_pending_execution"


def test_build_dengue_ns2b_ns3_protease_live_progress_marks_running() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "dengue_ns2b_ns3_protease_launch_packet_ready", "partner_track_id": "IPK_dengue"}},
        status="running",
        active_stage_label="flaviviral_shallow_pocket_primary_assay",
        started_at="2026-03-30T02:00:00",
        updated_at="2026-03-30T02:20:00",
    )
    summary = payload["summary"]

    assert summary["status"] == "running"
    assert summary["run_started"] is True
    assert summary["active_stage_label"] == "flaviviral_shallow_pocket_primary_assay"
    assert summary["current_stage"] == "flaviviral_shallow_pocket_primary_assay"
