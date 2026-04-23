from __future__ import annotations

import sys
from pathlib import Path

from tools import launch_wetlab_broad_screen_primary_watch_loop as mod


def test_main_recovers_stale_pid_and_launches_new_process(monkeypatch, tmp_path: Path, capsys) -> None:
    pid_file = tmp_path / "watch.pid"
    log_file = tmp_path / "watch.log"
    pid_file.write_text("999999\n", encoding="utf-8")

    monkeypatch.setattr(mod, "_pid_alive", lambda pid: False)

    class DummyProc:
        pid = 43210

    monkeypatch.setattr(mod.subprocess, "Popen", lambda *args, **kwargs: DummyProc())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_wetlab_broad_screen_primary_watch_loop.py",
            "--pid-file",
            str(pid_file),
            "--log-file",
            str(log_file),
        ],
    )

    rc = mod.main()
    out = capsys.readouterr().out.strip()

    assert rc == 0
    assert out == "43210"
    assert pid_file.read_text(encoding="utf-8").strip() == "43210"


def test_main_reuses_live_process_without_replace(monkeypatch, tmp_path: Path, capsys) -> None:
    pid_file = tmp_path / "watch.pid"
    log_file = tmp_path / "watch.log"
    pid_file.write_text("12345\n", encoding="utf-8")

    monkeypatch.setattr(mod, "_pid_alive", lambda pid: True)
    popen_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    monkeypatch.setattr(mod.subprocess, "Popen", lambda *args, **kwargs: popen_calls.append((args, kwargs)))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_wetlab_broad_screen_primary_watch_loop.py",
            "--pid-file",
            str(pid_file),
            "--log-file",
            str(log_file),
        ],
    )

    rc = mod.main()
    out = capsys.readouterr().out.strip()

    assert rc == 0
    assert out == "12345"
    assert not popen_calls
