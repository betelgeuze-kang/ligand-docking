from __future__ import annotations

from pathlib import Path

from tools import run_wetlab_broad_screen_primary_runner as mod


def test_runner_captures_heartbeat_pid(monkeypatch, tmp_path: Path) -> None:
    bridge_payload = {
        "summary": {},
        "structured": {
            "preferred_summary_json": str(tmp_path / "summary.json"),
            "preferred_summary_md": str(tmp_path / "summary.md"),
            "preferred_log_path": str(tmp_path / "compute.log"),
            "preferred_pid_path": str(tmp_path / "compute.pid"),
            "preferred_out_prefix": str(tmp_path / "out"),
            "artifact_dir": str(tmp_path / "artifacts"),
        },
        "rows": [
            {"command_kind": "throughput_preflight_tuned_gate55", "enabled": True, "command": "echo run"},
        ],
    }
    monkeypatch.setattr(mod.bridge_mod, "build_payload", lambda **kwargs: bridge_payload)
    monkeypatch.setattr(mod.runtime_mod, "run_event", lambda **kwargs: {"event": kwargs["event"]})
    monkeypatch.setattr(mod, "load_json", lambda path: {})
    monkeypatch.setattr(mod, "maybe_load_json", lambda path: {})

    class DummyProc:
        pid = 54321

    monkeypatch.setattr(mod.subprocess, "run", lambda *args, **kwargs: type("R", (), {"stdout": "12345\n"})())
    monkeypatch.setattr(mod.subprocess, "Popen", lambda *args, **kwargs: DummyProc())
    monkeypatch.setattr(mod, "write_artifact", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    payload = mod.run(
        target_id="CA IX",
        shard_id="11_of_20",
        python_bin="python3",
        command_kind="auto",
        execution_queue_json="runs/q.json",
        compound_universe_json="runs/u.json",
        portfolio_json="runs/p.json",
        target_native_csv="config/t.csv",
        interval_sec=30.0,
        replace_heartbeat=True,
    )

    assert payload["summary"]["heartbeat_pid"] == 12345
    assert payload["summary"]["compute_pid"] == 54321
    assert payload["summary"]["watcher_pid"] == 12345
    assert payload["rows"][0]["heartbeat_pid_path"].endswith("wetlab_broad_screen_heartbeat_loop.pid")
    assert payload["rows"][0]["watcher_pid_path"].endswith("wetlab_broad_screen_primary_watch_loop.pid")
