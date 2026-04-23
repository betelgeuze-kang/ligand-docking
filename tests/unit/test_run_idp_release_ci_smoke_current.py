import sys

from tools import run_idp_release_ci_smoke_current as ci


def test_run_ci_smoke_invokes_pytest_and_smoke(monkeypatch, tmp_path):
    calls = []

    def _fake_run(cmd):
        calls.append(list(cmd))
        if cmd[:3] == [sys.executable, "-m", "pytest"]:
            return {"cmd": list(cmd), "rc": 0, "stdout_tail": "pytest ok", "stderr_tail": ""}
        runner_json = tmp_path / "smoke_runner.json"
        runner_json.write_text('{"pass": true}', encoding="utf-8")
        return {"cmd": list(cmd), "rc": 0, "stdout_tail": "", "stderr_tail": ""}

    def _fake_load_json(path):
        if str(path).endswith("_runner.json"):
            return {"pass": True}
        raise AssertionError(path)

    monkeypatch.setattr(ci, "_run", _fake_run)
    monkeypatch.setattr(ci, "_load_json", _fake_load_json)

    args = ci.build_parser().parse_args(
        [
            "--device",
            "cpu",
            "--smoke-out-prefix",
            str(tmp_path / "smoke"),
            "--out-json",
            str(tmp_path / "ci.json"),
            "--out-md",
            str(tmp_path / "ci.md"),
        ]
    )
    payload = ci.run_ci_smoke(args)

    assert payload["pass"] is True
    assert calls[0][:3] == [sys.executable, "-m", "pytest"]
    assert "tools/run_idp_3bead_release_smoke_current.py" in calls[1]
