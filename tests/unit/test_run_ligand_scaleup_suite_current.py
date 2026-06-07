import json
from pathlib import Path
from types import SimpleNamespace

from tools.product import run_ligand_scaleup_suite_current as mod


def test_run_ligand_scaleup_suite_current_dry_run_default_plan(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    def _unexpected_subprocess(*args, **kwargs):
        raise AssertionError("subprocess.run should not be called in dry-run mode")

    monkeypatch.setattr(mod.subprocess, "run", _unexpected_subprocess)

    rc = mod.main([])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["execution_requested"] is False
    assert payload["dry_run"] is True
    assert payload["enabled_stage_count"] == 3
    assert payload["launch_readiness"]["ready"] is True
    assert [row["stage_id"] for row in payload["stages"]] == ["speedpack_ab", "pilot_100k", "pilot_1m"]
    assert all(bool(row["enabled"]) for row in payload["stages"])
    assert payload["stages"][0]["cmd"][1].endswith("tools/run_ligand_speedpack_ab_current.py")
    assert payload["stages"][1]["cmd"][1].endswith("tools/product/run_ligand_scaleup_100k_pilot_current.py")
    assert payload["stages"][2]["cmd"][1].endswith("tools/run_ligand_scaleup_1m_pilot_current.py")
    assert "--no-refresh-current-artifacts" in payload["stages"][0]["cmd"]
    assert "--no-refresh-current-summaries" in payload["stages"][1]["cmd"]
    assert "--no-refresh-current-summaries" in payload["stages"][2]["cmd"]
    assert payload["refresh_current_artifacts"] is False
    assert payload["refresh_current_summaries"] is False


def test_run_ligand_scaleup_suite_current_accepts_explicit_dry_run_flag(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    def _unexpected_subprocess(*args, **kwargs):
        raise AssertionError("subprocess.run should not be called in dry-run mode")

    monkeypatch.setattr(mod.subprocess, "run", _unexpected_subprocess)

    rc = mod.main(["--dry-run"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert payload["execution_requested"] is False


def test_run_ligand_scaleup_suite_current_dry_run_with_disabled_stages(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    rc = mod.main(["--no-enable-speedpack-ab", "--no-enable-1m"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["enabled_stage_count"] == 1
    assert payload["disabled_stage_count"] == 2
    enabled = {row["stage_id"]: row["enabled"] for row in payload["stages"]}
    assert enabled == {"speedpack_ab": False, "pilot_100k": True, "pilot_1m": False}


def test_run_ligand_scaleup_suite_current_dry_run_writes_current_json_and_md(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    def _unexpected_subprocess(*args, **kwargs):
        raise AssertionError("subprocess.run should not be called in dry-run mode")

    monkeypatch.setattr(mod.subprocess, "run", _unexpected_subprocess)

    rc = mod.main([])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    out_json = tmp_path / "runs/ligand_scaleup_suite_dryrun_current.json"
    out_md = tmp_path / "runs/ligand_scaleup_suite_dryrun_current.md"
    assert out_json.exists()
    assert out_md.exists()
    assert json.loads(out_json.read_text(encoding="utf-8")) == payload
    out_md_text = out_md.read_text(encoding="utf-8")
    assert "# Ligand Scale-up Suite" in out_md_text
    assert "`pilot_100k`" in out_md_text


def test_run_ligand_scaleup_suite_current_execute_runs_enabled_stages_in_order(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    calls: list[list[str]] = []

    def _fake_run(cmd, cwd=None):
        calls.append(list(cmd))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)

    rc = mod.main(
        [
            "--execute",
            "--no-enable-1m",
            "--refresh-current-artifacts",
            "--refresh-current-summaries",
            "--baseline-run-root",
            "runs/frozen_baseline",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["execution_requested"] is True
    assert payload["dry_run"] is False
    assert payload["completed_stage_count"] == 2
    assert [row["stage_id"] for row in payload["stage_results"]] == ["speedpack_ab", "pilot_100k", "pilot_1m"]
    assert payload["stage_results"][0]["ok"] is True
    assert payload["stage_results"][1]["ok"] is True
    assert payload["stage_results"][2]["skipped"] is True
    assert payload["suite_status_refreshes"] == [
        {
            "stage_id": "speedpack_ab",
            "ok": True,
            "returncode": 0,
            "cmd": calls[1],
        },
        {
            "stage_id": "pilot_100k",
            "ok": True,
            "returncode": 0,
            "cmd": calls[3],
        },
    ]
    assert payload["final_execution_summary"]["suite_status_refresh_count"] == 2
    assert payload["final_execution_summary"]["suite_status_refresh_ok_count"] == 2
    assert payload["final_execution_summary"]["current_suite_status_json"] == "runs/ligand_scaleup_suite_status_current.json"
    assert [Path(cmd[1]).name for cmd in calls] == [
        "run_ligand_speedpack_ab_current.py",
        "build_ligand_scaleup_suite_status.py",
        "run_ligand_scaleup_100k_pilot_current.py",  # product/run_ligand_scaleup_100k_pilot_current.py
        "build_ligand_scaleup_suite_status.py",
    ]
    assert "--baseline-run-root" in calls[0]
    assert "--baseline-run-root" in calls[2]
    assert "--refresh-current-artifacts" in calls[0]
    assert "--refresh-current-summaries" in calls[2]


def test_run_ligand_scaleup_suite_current_execute_can_disable_suite_status_refresh(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    calls: list[list[str]] = []

    def _fake_run(cmd, cwd=None):
        calls.append(list(cmd))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)

    rc = mod.main(["--execute", "--no-enable-100k", "--no-enable-1m", "--no-refresh-suite-status"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["suite_status_refreshes"] == []
    assert payload["final_execution_summary"]["suite_status_refresh_count"] == 0
    assert [Path(cmd[1]).name for cmd in calls] == ["run_ligand_speedpack_ab_current.py"]


def test_run_ligand_scaleup_suite_current_execute_writes_current_json_and_md(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    calls: list[list[str]] = []

    def _fake_run(cmd, cwd=None):
        calls.append(list(cmd))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)

    rc = mod.main(["--execute", "--no-enable-100k", "--no-enable-1m", "--no-refresh-suite-status"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    out_json = tmp_path / "runs/ligand_scaleup_suite_execution_current.json"
    out_md = tmp_path / "runs/ligand_scaleup_suite_execution_current.md"
    assert out_json.exists()
    assert out_md.exists()
    assert json.loads(out_json.read_text(encoding="utf-8")) == payload
    out_md_text = out_md.read_text(encoding="utf-8")
    assert "## Execution Summary" in out_md_text
    assert "`speedpack_ab`" in out_md_text
    assert [Path(cmd[1]).name for cmd in calls] == ["run_ligand_speedpack_ab_current.py"]
