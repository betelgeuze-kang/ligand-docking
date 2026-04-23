from __future__ import annotations

from tools import build_tcruzi_pde_live_progress as mod
from tools.wetlab_target_render_utils import load_json


def test_build_tcruzi_pde_live_progress_defaults_to_not_started() -> None:
    payload = mod.build_payload(load_json(mod.DEFAULT_LAUNCH_JSON))
    summary = payload["summary"]

    assert summary["status"] == "not_started"
    assert summary["artifact_kind"] == "live_progress"
    assert summary["run_started"] is False
    assert summary["current_stage"] == "launch_packet_frozen_pending_execution"


def test_build_tcruzi_pde_live_progress_marks_running() -> None:
    payload = mod.build_payload(
        load_json(mod.DEFAULT_LAUNCH_JSON),
        status="running",
        active_stage_label="parasite_vs_human_primary_assay",
        started_at="2026-03-29T12:00:00",
        updated_at="2026-03-29T12:15:00",
    )
    summary = payload["summary"]

    assert summary["status"] == "running"
    assert summary["run_started"] is True
    assert summary["active_stage_label"] == "parasite_vs_human_primary_assay"
    assert summary["current_stage"] == "parasite_vs_human_primary_assay"
