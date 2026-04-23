from __future__ import annotations

from tools import build_tcruzi_pde_result_summary as mod
from tools.wetlab_target_render_utils import load_json


def test_build_tcruzi_pde_result_summary_defaults_to_not_ready() -> None:
    payload = mod.build_payload(
        load_json(mod.DEFAULT_LAUNCH_JSON),
        load_json(mod.DEFAULT_GO_NO_GO_JSON),
    )
    summary = payload["summary"]

    assert summary["status"] == "not_ready"
    assert summary["artifact_kind"] == "result_summary"
    assert summary["result_review_ready"] is False
    assert summary["explicit_hold"] is False


def test_build_tcruzi_pde_result_summary_marks_completed() -> None:
    payload = mod.build_payload(
        load_json(mod.DEFAULT_LAUNCH_JSON),
        load_json(mod.DEFAULT_GO_NO_GO_JSON),
        status="completed",
        decision_case="tcruzi_parasite_selective_pass",
        action="advance_to_wave2_release_review",
        started_at="2026-03-29T12:00:00",
        completed_at="2026-03-29T15:10:00",
    )
    summary = payload["summary"]

    assert summary["status"] == "completed"
    assert summary["result_review_ready"] is True
    assert summary["decision_case"] == "tcruzi_parasite_selective_pass"
    assert summary["action"] == "advance_to_wave2_release_review"
    assert summary["completed_at"] == "2026-03-29T15:10:00"
