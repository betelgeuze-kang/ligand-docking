from __future__ import annotations

from pathlib import Path

from tools import run_wetlab_next3_runtime_event as mod


def test_apply_and_log_event_appends_log_and_rebuilds(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []
    writes: list[tuple[str, str]] = []

    def fake_apply_runtime_event(**kwargs):
        calls.append(("apply", kwargs["event"]))
        return {
            "target_id": "Cruzain",
            "event": "start",
            "progress_command": "tools/build_cruzain_live_progress.py --status running",
            "result_command": "",
            "run_record_status": "blocked_on_previous_review",
            "execution_state": "running",
            "queue_status_now": "running_active_slot",
            "gate_status": "cruzain_run_status_ready",
            "gate_execution_state": "running",
        }

    def fake_write_artifact(path_like: str, title: str, payload: dict):
        writes.append((path_like, title))

    def fake_rebuild(python_bin: str) -> None:
        calls.append(("rebuild", python_bin))

    monkeypatch.setattr(mod.runtime_event_mod, "apply_runtime_event", fake_apply_runtime_event)
    monkeypatch.setattr(mod, "write_artifact", fake_write_artifact)
    monkeypatch.setattr(mod, "_rebuild_support_artifacts", fake_rebuild)

    log_path = tmp_path / "event_log.jsonl"
    row = mod.apply_and_log_event(
        target="cruzain",
        event="start",
        python_bin="python3",
        active_stage_label="parasite_cysteine_protease_primary_assay",
        started_at="2026-03-29T20:00:00",
        updated_at="2026-03-29T20:00:00",
        log_path=log_path,
    )

    assert row["event"] == "start"
    assert row["event_timestamp"] == "2026-03-29T20:00:00"
    assert writes[0][0] == mod.runtime_event_mod.DEFAULT_OUT_MD
    assert ("rebuild", "python3") in calls
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert "Cruzain" in lines[0]
