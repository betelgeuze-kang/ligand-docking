from __future__ import annotations

from tools import build_wetlab_priority3_runtime_event as mod


def test_apply_runtime_event_start_updates_progress_only_and_refreshes(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], python_bin: str) -> None:
        calls.append(cmd)

    def fake_summary(path_like: str) -> dict[str, object]:
        if path_like.endswith("sarscov2_mpro_run_record_current.json"):
            return {
                "status": "sarscov2_mpro_run_record_ready",
                "execution_state": "running",
                "queue_status_now": "running_active_slot",
            }
        if path_like.endswith("sarscov2_mpro_run_status_current.json"):
            return {
                "status": "sarscov2_mpro_run_status_ready",
                "execution_state": "running",
            }
        return {}

    monkeypatch.setattr(mod, "_run", fake_run)
    monkeypatch.setattr(mod, "_summary", fake_summary)

    result = mod.apply_runtime_event(
        target_key="sarscov2_mpro",
        event="start",
        python_bin="python3",
        active_stage_label="fluorogenic_primary_assay",
        started_at="2026-03-29T18:00:00",
        updated_at="2026-03-29T18:00:00",
    )

    assert calls[0][0] == "tools/build_sarscov2_mpro_live_progress.py"
    assert "--status" in calls[0]
    assert "running" in calls[0]
    assert calls[1] == ["tools/build_wetlab_priority3_gate_refresh.py"]
    assert result["execution_state"] == "running"
    assert result["queue_status_now"] == "running_active_slot"


def test_apply_runtime_event_complete_updates_result_and_refreshes(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], python_bin: str) -> None:
        calls.append(cmd)

    def fake_summary(path_like: str) -> dict[str, object]:
        if path_like.endswith("caix_run_record_current.json"):
            return {
                "status": "caix_run_record_ready",
                "execution_state": "result_ready",
                "queue_status_now": "result_ready_for_review",
            }
        if path_like.endswith("caix_result_review_current.json"):
            return {
                "status": "caix_result_review_ready",
                "result_review_gate_status": "result_ready",
            }
        return {}

    monkeypatch.setattr(mod, "_run", fake_run)
    monkeypatch.setattr(mod, "_summary", fake_summary)

    result = mod.apply_runtime_event(
        target_key="caix",
        event="complete",
        python_bin="python3",
        active_stage_label="acidic_buffer_primary_assay",
        decision_case="caix_condition_pass",
        action="advance_to_successor_gate",
        started_at="2026-03-29T18:00:00",
        updated_at="2026-03-29T19:00:00",
        completed_at="2026-03-29T19:15:00",
    )

    assert calls[0][0] == "tools/build_caix_live_progress.py"
    assert calls[1][0] == "tools/build_caix_result_summary.py"
    assert calls[2] == ["tools/build_wetlab_priority3_gate_refresh.py"]
    assert result["execution_state"] == "result_ready"
    assert result["gate_status"] == "caix_result_review_ready"


def test_build_payload_exposes_runtime_artifacts() -> None:
    payload = mod.build_payload(
        {
            "target_id": "T. cruzi PDE",
            "event": "hold",
            "progress_command": "tools/build_tcruzi_pde_live_progress.py --status explicit_hold",
            "result_command": "tools/build_tcruzi_pde_result_summary.py --status explicit_hold",
            "run_record_status": "tcruzi_pde_run_record_ready",
            "execution_state": "explicit_hold",
            "queue_status_now": "explicit_hold_ready_for_wave2_release",
            "gate_status": "tcruzi_pde_result_review_ready",
            "gate_execution_state": "explicit_hold",
        }
    )
    summary = payload["summary"]

    assert summary["status"] == "wetlab_priority3_runtime_event_applied"
    assert summary["target_id"] == "T. cruzi PDE"
    assert summary["event"] == "hold"
    assert summary["execution_state"] == "explicit_hold"
    assert summary["run_record_artifact"] == "runs/tcruzi_pde_run_record_current.md"
