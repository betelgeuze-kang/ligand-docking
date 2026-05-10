from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from tools import apply_runs_artifact_inventory_root_archive as mod


def _row(path: str, *, size: int = 9, action: str = "archive_review", group: str = "(root)") -> dict[str, str]:
    return {
        "path": path,
        "file_kind": "file",
        "size_bytes": str(size),
        "top_level_group": group,
        "cleanup_action": action,
    }


def test_apply_root_archive_moves_root_files_and_by_name_symlinks(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    selected = runs / "external_validation_2026-05-03_demo_stage3_scores.csv"
    selected.write_text("selected", encoding="utf-8")
    skipped = runs / "ligand_smiles_bead_cache.json"
    skipped.write_text("skipped", encoding="utf-8")
    current = runs / "external_validation_current.json"
    current.write_text("current", encoding="utf-8")
    by_name = runs / "_by_name" / "external_validation"
    by_name.mkdir(parents=True)
    link = by_name / selected.name
    link.symlink_to(Path("../../") / selected.name)

    payload = mod.apply_root_archive(
        [
            _row("runs/external_validation_2026-05-03_demo_stage3_scores.csv", size=8),
            _row("runs/ligand_smiles_bead_cache.json", size=7),
            _row("runs/external_validation_current.json", size=6),
        ],
        runs_dir=runs,
        archive_root=runs / "archive" / "root_batch",
        today_local=date(2026, 5, 8),
        execute=True,
    )

    summary = payload["summary"]
    assert summary["status"] == "runs_artifact_inventory_root_archive_apply_report_ready"
    assert summary["selected_root_file_count"] == 1
    assert summary["companion_symlink_count"] == 1
    assert summary["moved_entry_count"] == 2
    assert not selected.exists()
    assert not link.exists()
    assert not link.is_symlink()
    assert skipped.exists()
    assert current.exists()

    archived_file = runs / "archive" / "root_batch" / selected.name
    archived_link = runs / "archive" / "root_batch" / "_by_name" / "external_validation" / selected.name
    assert archived_file.exists()
    assert archived_link.is_symlink()
    assert archived_link.resolve() == archived_file.resolve()


def test_select_root_rows_protects_same_day_and_non_prefix_rows() -> None:
    rows = [
        _row("runs/external_validation_2026-05-08_today_stage3_scores.csv"),
        _row("runs/external_validation_2026-05-07_old_stage3_scores.csv"),
        _row("runs/tmp_admet_surface_predictive_check.json"),
    ]

    selected = mod.select_root_rows(rows, today_local=date(2026, 5, 8))

    assert [row["path"] for row in selected] == ["runs/external_validation_2026-05-07_old_stage3_scores.csv"]


def test_main_dry_run_writes_report_without_moving(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    source = runs / "ligand_stress_validation_2026-05-03_demo_stage1_ligands.json"
    source.write_text("payload", encoding="utf-8")
    inventory = runs / "runs_artifact_inventory_current.csv"
    inventory.write_text(
        "\n".join(
            [
                "path,file_kind,size_bytes,top_level_group,cleanup_action",
                "runs/ligand_stress_validation_2026-05-03_demo_stage1_ligands.json,file,8,(root),archive_review",
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
            "--runs-dir",
            str(runs),
            "--archive-root",
            str(runs / "archive" / "root_batch"),
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
    assert payload["summary"]["selected_root_file_count"] == 1
    assert payload["summary"]["moved_entry_count"] == 0
    assert source.exists()
    assert out_csv.exists()
    assert "# Runs Artifact Inventory Root Archive Apply Report" in out_md.read_text(encoding="utf-8")
