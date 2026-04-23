from __future__ import annotations

from tools import build_wetlab_final2_gate_refresh as mod


def test_build_wetlab_final2_gate_refresh_main_runs_refresh_by_default(monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr(mod, "_write", lambda payload: calls.append("write"))
    monkeypatch.setattr(mod, "_run", lambda python_bin: calls.append(f"run:{python_bin}"))
    monkeypatch.setattr(mod, "parse_args", lambda: type("Args", (), {"python_bin": "python3", "run": False})())

    mod.main()

    assert calls == ["write", "run:python3"]
