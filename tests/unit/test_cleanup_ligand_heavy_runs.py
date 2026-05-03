from __future__ import annotations

import os
from pathlib import Path

import tools.cleanup_ligand_heavy_runs as mod
from tools.cleanup_ligand_heavy_runs import cleanup_heavy_runs


def _touch(path: Path, age_days: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    ts = 1_800_000_000 - (age_days * 86_400)
    os.utime(path, (ts, ts))
    os.utime(path.parent, (ts, ts))


def test_cleanup_heavy_runs_dry_run_targets_only_old_heavy_directories(tmp_path: Path) -> None:
    root = tmp_path / "ligand_heavy_runs"
    old_run = root / "ligand_stage2_20260101"
    recent_run = root / "ligand_stage2_20260430"
    evidence_dir = root / "ligand_stage2_evidence_bundle"
    summary_json = root / "ligand_stage2_20260101_summary.json"

    _touch(old_run / "stage2_trajectory_frames" / "traj.xtc", age_days=90)
    _touch(recent_run / "stage2_trajectory_frames" / "traj.xtc", age_days=1)
    _touch(evidence_dir / "stage2_trajectory_frames" / "traj.xtc", age_days=90)
    _touch(summary_json, age_days=90)

    report = cleanup_heavy_runs(
        roots=[root],
        execute=False,
        allow_prefixes=["ligand_stage2_"],
        preserve_patterns=["*evidence*"],
        keep_recent=0,
        older_than_days=30,
        now=1_800_000_000,
        process_lines=[],
    )

    rows = {row.get("run_name", Path(row["path"]).name): row for row in report["rows"]}
    assert rows["ligand_stage2_20260101"]["status"] == "dry_run_delete"
    assert rows["ligand_stage2_20260430"]["status"] == "kept_too_recent"
    assert rows["ligand_stage2_evidence_bundle"]["status"] == "kept_preserve_pattern"
    assert "ligand_stage2_20260101_summary.json" not in rows
    assert old_run.exists()
    assert (old_run / "stage2_trajectory_frames").exists()
    assert summary_json.exists()


def test_cleanup_heavy_runs_execute_removes_only_planned_directory(tmp_path: Path) -> None:
    root = tmp_path / "runs" / "local_heavy_runs"
    delete_me = root / "local_heavy_20260101"
    keep_me = root / "local_heavy_20260102"
    summary_md = root / "local_heavy_20260101_summary.md"

    _touch(delete_me / "stage2_trajectory_frames" / "part000.dcd", age_days=80)
    _touch(keep_me / "stage2_trajectory_frames" / "part000.dcd", age_days=70)
    _touch(summary_md, age_days=80)

    report = cleanup_heavy_runs(
        roots=[root],
        execute=True,
        allow_prefixes=["local_heavy_"],
        preserve_patterns=[],
        keep_recent=1,
        older_than_days=30,
        now=1_800_000_000,
        process_lines=[],
    )

    rows = {row.get("run_name", Path(row["path"]).name): row for row in report["rows"]}
    assert rows["local_heavy_20260101"]["status"] == "deleted"
    assert rows["local_heavy_20260102"]["status"] == "kept_recent_slot"
    assert delete_me.exists()
    assert not (delete_me / "stage2_trajectory_frames").exists()
    assert keep_me.exists()
    assert (keep_me / "stage2_trajectory_frames").exists()
    assert summary_md.exists()


def test_cleanup_heavy_runs_skips_active_run_markers_and_processes(tmp_path: Path) -> None:
    root = tmp_path / "ligand_heavy_runs"
    locked = root / "ligand_active_lock"
    progressing = root / "ligand_active_progress"
    in_process = root / "ligand_active_process"
    stale = root / "ligand_stale"

    _touch(locked / "stage2_trajectory_frames" / "traj.xtc", age_days=100)
    _touch(locked / "RUNNING.lock", age_days=1)
    _touch(progressing / "stage2_trajectory_frames" / "traj.xtc", age_days=100)
    _touch(progressing / "progress.json", age_days=1)
    _touch(in_process / "stage2_trajectory_frames" / "traj.xtc", age_days=100)
    _touch(stale / "stage2_trajectory_frames" / "traj.xtc", age_days=100)

    report = cleanup_heavy_runs(
        roots=[root],
        execute=True,
        allow_prefixes=["ligand_"],
        preserve_patterns=[],
        keep_recent=0,
        older_than_days=30,
        now=1_800_000_000,
        process_lines=[f"python tools/run_ligand_scaleup.py --run-root {in_process}"],
    )

    rows = {row.get("run_name", Path(row["path"]).name): row for row in report["rows"]}
    assert rows["ligand_active_lock"]["status"] == "kept_active_marker"
    assert rows["ligand_active_progress"]["status"] == "kept_active_marker"
    assert rows["ligand_active_process"]["status"] == "kept_running_process"
    assert rows["ligand_stale"]["status"] == "deleted"
    assert locked.exists()
    assert progressing.exists()
    assert in_process.exists()
    assert stale.exists()
    assert not (stale / "stage2_trajectory_frames").exists()


def test_cleanup_heavy_runs_accepts_explicit_payload_root(tmp_path: Path) -> None:
    run_dir = tmp_path / "ligand_heavy_runs" / "ligand_payload_direct"
    payload = run_dir / "stage2_trajectory_frames"
    _touch(payload / "shard_00000" / "frame.npz", age_days=60)

    report = cleanup_heavy_runs(
        roots=[payload],
        execute=True,
        allow_prefixes=["ligand_"],
        preserve_patterns=[],
        keep_recent=0,
        older_than_days=30,
        now=1_800_000_000,
        process_lines=[],
    )

    assert report["summary"]["deleted_count"] == 1
    assert run_dir.exists()
    assert not payload.exists()


def test_process_lines_ignores_cleanup_process_and_parent_shell(monkeypatch) -> None:
    monkeypatch.setattr(mod.os, "getpid", lambda: 123)
    monkeypatch.setattr(mod.os, "getppid", lambda: 122)

    def fake_check_output(cmd, text):  # noqa: ANN001
        assert cmd == ["ps", "-eo", "pid=,args="]
        assert text is True
        return "\n".join(
            [
                " 122 /bin/bash -c python3 tools/cleanup_ligand_heavy_runs.py --root runs/local_heavy_runs/run_a",
                " 123 python3 tools/cleanup_ligand_heavy_runs.py --root runs/local_heavy_runs/run_a",
                " 456 python3 tools/run_ligand_stress_validation.py --heavy-artifacts-root runs/local_heavy_runs/run_a",
            ]
        )

    monkeypatch.setattr(mod.subprocess, "check_output", fake_check_output)

    assert mod._process_lines() == [
        "456 python3 tools/run_ligand_stress_validation.py --heavy-artifacts-root runs/local_heavy_runs/run_a"
    ]
