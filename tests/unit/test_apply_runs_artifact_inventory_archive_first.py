from __future__ import annotations

import json
from pathlib import Path
from datetime import date

from tools import apply_runs_artifact_inventory_archive_first as mod


def _inventory_row(path: str, group: str, *, action: str = "archive_review", kind: str = "file", size: int = 7) -> dict[str, str]:
    return {
        "path": path,
        "file_kind": kind,
        "size_bytes": str(size),
        "top_level_group": group,
        "cleanup_action": action,
    }


def test_apply_archive_first_selects_only_high_confidence_groups(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    selected = runs / "wetlab_broad_screen_throughput" / "alk2" / "01_of_20" / "stage1.csv"
    selected.parent.mkdir(parents=True)
    selected.write_text("selected", encoding="utf-8")
    frames = runs / "ligand_htvs_nightly_2026-05-01_smoke_stage2_traj_frames" / "shard_00000" / "frame.npz"
    frames.parent.mkdir(parents=True)
    frames.write_text("frames", encoding="utf-8")
    root_file = runs / "old_2026-05-01_stage3_scores.csv"
    root_file.write_text("root", encoding="utf-8")
    current = runs / "wetlab_broad_screen_throughput" / "active_current.csv"
    current.write_text("current", encoding="utf-8")

    rows = [
        _inventory_row("runs/wetlab_broad_screen_throughput/alk2/01_of_20/stage1.csv", "wetlab_broad_screen_throughput"),
        _inventory_row(
            "runs/ligand_htvs_nightly_2026-05-01_smoke_stage2_traj_frames/shard_00000/frame.npz",
            "ligand_htvs_nightly_2026-05-01_smoke_stage2_traj_frames",
        ),
        _inventory_row("runs/old_2026-05-01_stage3_scores.csv", "(root)"),
        _inventory_row("runs/wetlab_broad_screen_throughput/active_current.csv", "wetlab_broad_screen_throughput"),
    ]

    payload = mod.apply_archive_first(
        rows,
        archive_root=runs / "archive" / "batch",
        runs_dir=runs,
        today_local=date(2026, 5, 8),
        execute=True,
    )
    summary = payload["summary"]

    assert summary["status"] == "runs_artifact_inventory_archive_first_apply_report_ready"
    assert summary["planned_file_count"] == 2
    assert summary["moved_file_count"] == 2
    assert not selected.exists()
    assert not frames.exists()
    assert root_file.exists()
    assert current.exists()
    assert (runs / "archive" / "batch" / "wetlab_broad_screen_throughput" / "alk2" / "01_of_20" / "stage1.csv").exists()
    assert (
        runs
        / "archive"
        / "batch"
        / "ligand_htvs_nightly_2026-05-01_smoke_stage2_traj_frames"
        / "shard_00000"
        / "frame.npz"
    ).exists()


def test_main_dry_run_writes_report_without_moving(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    source = runs / "wetlab_broad_screen_antitarget_throughput" / "ca_ix" / "stage1.csv"
    source.parent.mkdir(parents=True)
    source.write_text("selected", encoding="utf-8")
    inventory = runs / "runs_artifact_inventory_current.csv"
    inventory.write_text(
        "\n".join(
            [
                "path,file_kind,size_bytes,top_level_group,cleanup_action",
                "runs/wetlab_broad_screen_antitarget_throughput/ca_ix/stage1.csv,file,8,wetlab_broad_screen_antitarget_throughput,archive_review",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    out_json = runs / "report.json"
    out_csv = runs / "report.csv"
    out_md = runs / "report.md"

    mod.main(
        [
            "--inventory-csv",
            str(inventory),
            "--archive-root",
            str(runs / "archive" / "batch"),
            "--runs-dir",
            str(runs),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["execution_mode"] == "dry_run"
    assert payload["summary"]["planned_file_count"] == 1
    assert payload["summary"]["moved_file_count"] == 0
    assert source.exists()
    assert out_csv.exists()
    assert "# Runs Artifact Inventory Archive-First Apply Report" in out_md.read_text(encoding="utf-8")


def test_select_rows_protects_same_day_dated_stage_groups() -> None:
    rows = [
        _inventory_row(
            "runs/ligand_htvs_nightly_2026-05-08_smoke_stage2_traj_frames/shard/frame.npz",
            "ligand_htvs_nightly_2026-05-08_smoke_stage2_traj_frames",
        ),
        _inventory_row(
            "runs/ligand_htvs_nightly_2026-05-07_smoke_stage2_traj_frames/shard/frame.npz",
            "ligand_htvs_nightly_2026-05-07_smoke_stage2_traj_frames",
        ),
    ]

    selected = mod.select_rows(rows, today_local=date(2026, 5, 8))

    assert [row["top_level_group"] for row in selected] == [
        "ligand_htvs_nightly_2026-05-07_smoke_stage2_traj_frames"
    ]
