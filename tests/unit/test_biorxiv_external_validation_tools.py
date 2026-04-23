from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def test_resume_biorxiv_external_validation_dry_run(tmp_path: Path) -> None:
    run_root = tmp_path / "external_validation_blind_runs_2026-03-21_unit"
    spec_json = tmp_path / "spec.json"
    _write_json(spec_json, {"protocol_id": "unit", "sets": []})
    _write_json(
        run_root / "oneshot_status.json",
        {
            "tag": "2026-03-21_unit",
            "status": "stale",
            "phase": "validation",
            "set_spec_json": str(spec_json),
            "sets": ["set3_operational_smoke", "set1_core_blind"],
        },
    )
    _write_json(
        run_root / "provenance.json",
        {
            "selected_sets": ["set3_operational_smoke", "set1_core_blind"],
            "spec_json": str(spec_json),
        },
    )
    _write_json(
        run_root / "state.json",
        {
            "out_root": str(run_root),
        },
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/resume_biorxiv_external_validation.py"),
            "--run-root",
            str(run_root),
            "--dry-run",
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["tag"] == "2026-03-21_unit"
    assert payload["status_before"] == "stale"
    assert payload["sets"] == ["set3_operational_smoke", "set1_core_blind"]
    resume_cmd = payload["resume_cmd"]
    assert "tools/run_biorxiv_external_validation_current.py" in " ".join(resume_cmd)
    assert "--tag" in resume_cmd
    assert "2026-03-21_unit" in resume_cmd


def test_monitor_biorxiv_external_validation_prints_resume_command_for_stale(tmp_path: Path) -> None:
    run_root = tmp_path / "external_validation_blind_runs_2026-03-21_stale"
    _write_json(
        run_root / "oneshot_status.json",
        {
            "tag": "2026-03-21_monitor_stale_no_process",
            "status": "running",
            "phase": "validation",
            "resume_cmd": [
                sys.executable,
                str(ROOT / "tools/resume_biorxiv_external_validation.py"),
                "--run-root",
                str(run_root),
            ],
            "validation_log": str(run_root / "validation_stage.log"),
        },
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/monitor_biorxiv_external_validation.py"),
            "--run-root",
            str(run_root),
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=True,
    )
    out = proc.stdout
    assert "status: stale" in out
    assert "resume_command:" in out
    assert "resume_biorxiv_external_validation.py" in out


def test_recover_biorxiv_external_validation_writes_stale_recovery_plan(tmp_path: Path) -> None:
    run_root = tmp_path / "external_validation_blind_runs_2026-03-21_recover"
    _write_json(
        run_root / "oneshot_status.json",
        {
            "tag": "2026-03-21_recover",
            "status": "running",
            "phase": "validation",
        },
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/recover_biorxiv_external_validation.py"),
            "--run-root",
            str(run_root),
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["effective_status"] == "stale"
    assert "build_partial_package" in payload["suggested_actions"]
    assert "resume_validation" in payload["suggested_actions"]
    assert (run_root / "recovery_plan.json").exists()
    assert (run_root / "recovery_plan.md").exists()
