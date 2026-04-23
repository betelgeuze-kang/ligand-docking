from __future__ import annotations

from pathlib import Path

from tools import run_wetlab_broad_screen_antitarget_runner as mod


class _FakeCompleted:
    def __init__(self, stdout: str = "") -> None:
        self.stdout = stdout


class _FakePopen:
    def __init__(self, *args, **kwargs) -> None:
        self.pid = 43210


def test_antitarget_runner_starts_compute_attached_row(tmp_path: Path, monkeypatch) -> None:
    log_path = tmp_path / "throughput.log"
    pid_path = tmp_path / "throughput.pid"
    summary_json = tmp_path / "throughput_summary.json"
    summary_md = tmp_path / "throughput_summary.md"

    monkeypatch.setattr(mod, "load_json", lambda path: {"rows": []})
    monkeypatch.setattr(mod, "maybe_load_json", lambda path: None)
    monkeypatch.setattr(
        mod.bridge_mod,
        "build_payload",
        lambda **kwargs: {
            "summary": {},
            "structured": {
                "preferred_log_path": str(log_path),
                "preferred_pid_path": str(pid_path),
                "preferred_summary_json": str(summary_json),
                "preferred_summary_md": str(summary_md),
            },
            "rows": [
                {
                    "command_kind": "throughput_preflight_tuned_gate55",
                    "enabled": True,
                    "command": "echo antitarget",
                }
            ],
        },
    )

    recorded_events: list[dict] = []

    monkeypatch.setattr(mod.runtime_mod, "run_event", lambda **kwargs: recorded_events.append(kwargs) or {"event": "start"})
    monkeypatch.setattr(mod.subprocess, "run", lambda *args, **kwargs: _FakeCompleted(stdout="22222\n"))
    monkeypatch.setattr(mod.subprocess, "Popen", _FakePopen)
    monkeypatch.setattr(mod, "write_artifact", lambda *args, **kwargs: None)

    payload = mod.run(
        primary_target_id="CA IX",
        anti_target_id="CA II",
        shard_id="06_of_20",
        python_bin="python3",
        command_kind="auto",
        antitarget_execution_queue_json="runs/antitarget_execution_queue.json",
        primary_queue_json="runs/broad_queue.json",
        compound_universe_json="runs/compound_universe.json",
        portfolio_json="runs/portfolio.json",
        target_native_csv="config/real_drug_targets_native_v1.csv",
        interval_sec=30.0,
        replace_heartbeat=True,
    )

    assert recorded_events
    event = recorded_events[0]
    assert event["runner_kind"] == "compute_attached"
    assert event["compute_pid"] == 43210
    assert event["compute_pid_path"] == str(pid_path)
    assert event["compute_summary_json"] == str(summary_json)
    assert payload["summary"]["selected_command_kind"] == "throughput_preflight_tuned_gate55"
    assert payload["summary"]["watcher_pid"] == 22222
    assert payload["rows"][0]["watcher_pid_path"].endswith("wetlab_broad_screen_antitarget_watcher_loop.pid")
