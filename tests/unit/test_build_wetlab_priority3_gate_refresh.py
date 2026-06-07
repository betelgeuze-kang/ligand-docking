from __future__ import annotations

import sys

from tools import build_wetlab_priority3_gate_refresh as mod


def test_build_wetlab_priority3_gate_refresh_runs_chain() -> None:
    rows = mod.run_refresh(sys.executable)
    payload = mod.build_payload(rows)
    summary = payload["summary"]

    assert summary["status"] == "wetlab_priority3_gate_refresh_ready"
    assert summary["step_count"] == len(mod.DEFAULT_STEPS)
    assert len(rows) == len(mod.DEFAULT_STEPS)
    assert rows[0]["step_id"] == "mpro_run_record"
    assert rows[4]["step_id"] == "tcruzi_run_record"
    assert rows[-1]["step_id"] == "partnering_stack"
    assert summary["ready_now_target_count"] == 0
    assert summary["resolved_target_count"] == 3
    assert summary["blocked_on_previous_review_count"] >= 0
    assert "partner export bundle" in summary["next_required_step"]
    assert "explicit R4 confirmation" in summary["next_required_step"]
