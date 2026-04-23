from __future__ import annotations

from pathlib import Path

from tools import run_wetlab_master_runtime_event as mod


def test_master_runtime_event_registry_includes_wave2_targets() -> None:
    assert "cathepsin_k" in mod.runtime_event_mod.TARGETS
    assert mod.runtime_event_mod.TARGETS["cathepsin_k"]["chain_id"] == "wave2"
    assert "t_cruzi_krs1" in mod.runtime_event_mod.TARGETS
    assert mod.runtime_event_mod.TARGETS["t_cruzi_krs1"]["chain_id"] == "wave2"


def test_apply_and_log_event_refreshes_master_surfaces_and_appends_log(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []
    writes: list[tuple[str, str]] = []

    def fake_rebuild(python_bin: str) -> None:
        calls.append(("rebuild", python_bin))

    def fake_apply_runtime_event(**kwargs):
        calls.append(("dispatch", kwargs["event"]))
        return {
            "target_key": "sarscov2_mpro",
            "target_id": "SARS-CoV-2 Mpro",
            "chain_id": "priority3",
            "event": "start",
            "dispatch_status": "dispatched_to_chain_runner",
            "chain_event_applied": True,
            "target_queue_status_before": "ready_first",
            "target_blocked_before": False,
            "gate_status": "sarscov2_mpro_run_status_ready",
            "chain_execution_state": "running",
            "gate_execution_state": "running",
        }

    def fake_build_payload(event_result, master_queue, master_runbook, master_console):
        return {
            "summary": {
                "status": "wetlab_master_runtime_event_applied",
                "target_queue_status_after": "running_first",
                "target_blocked_after": False,
                "first_actionable_target": "SARS-CoV-2 Mpro",
                "first_actionable_chain": "priority3",
                "master_console_status": "wetlab_master_execution_console_ready",
            },
            "rows": [],
        }

    def fake_load_json(path_like: str):
        if path_like == mod.runtime_event_mod.DEFAULT_MASTER_QUEUE_JSON:
            return {"summary": {"first_actionable_target": "SARS-CoV-2 Mpro"}}
        if path_like == mod.runtime_event_mod.DEFAULT_MASTER_RUNBOOK_JSON:
            return {"summary": {"status": "wetlab_master_runtime_runbook_ready"}}
        if path_like == mod.runtime_event_mod.DEFAULT_MASTER_CONSOLE_JSON:
            return {"summary": {"status": "wetlab_master_execution_console_ready"}}
        raise AssertionError(f"unexpected load_json path: {path_like}")

    def fake_write_artifact(path_like: str, title: str, payload: dict):
        writes.append((path_like, title))

    monkeypatch.setattr(mod, "_rebuild_master_support_artifacts", fake_rebuild)
    monkeypatch.setattr(mod.runtime_event_mod, "apply_runtime_event", fake_apply_runtime_event)
    monkeypatch.setattr(mod.runtime_event_mod, "build_payload", fake_build_payload)
    monkeypatch.setattr(mod, "load_json", fake_load_json)
    monkeypatch.setattr(mod, "write_artifact", fake_write_artifact)

    log_path = tmp_path / "master_event_log.jsonl"
    row = mod.apply_and_log_event(
        target="sarscov2_mpro",
        event="start",
        python_bin="python3",
        started_at="2026-03-29T20:00:00",
        updated_at="2026-03-29T20:00:00",
        log_path=log_path,
    )

    assert calls == [("rebuild", "python3"), ("dispatch", "start"), ("rebuild", "python3")]
    assert writes[0][0] == mod.runtime_event_mod.DEFAULT_OUT_MD
    assert row["target_queue_status_after"] == "running_first"
    assert row["event_timestamp"] == "2026-03-29T20:00:00"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert "SARS-CoV-2 Mpro" in lines[0]
