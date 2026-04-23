from __future__ import annotations

import json
from pathlib import Path

from tools import apply_runs_cleanup_batch4_archive_first as mod
from tools import build_runs_cleanup_batch4_archive_first_manifest as manifest_mod


def test_apply_manifest_moves_only_archive_first_rows(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    archive_root = runs / "archive" / "batch4_archive_first"

    files = [
        "ligand_blind_gpcr_demo_stage1_queue.csv",
        "ligand_blind_gpcr_demo_stage1_ligands.json",
        "ligand_blind_gpcr_demo_stage2_active_learning_summary.json",
        "ligand_blind_gpcr_demo_stage2_active_learning_summary.md",
        "ligand_blind_gpcr_demo_stage2_active_learning_target_weights.csv",
        "ligand_blind_gpcr_demo_stage2_traj_manifest.csv",
        "ligand_blind_gpcr_demo_stage3_summary.json",
        "ligand_blind_gpcr_demo_stage3_summary.md",
        "ligand_blind_gpcr_demo_stage3_scores.csv",
    ]
    for index, name in enumerate(files):
        (runs / name).write_text(f"payload-{index}", encoding="utf-8")

    review_json = tmp_path / "batch4_stage_review_manifest_current.json"
    review_json.write_text(
        json.dumps({"summary": {"status": "runs_cleanup_batch4_stage_review_manifest_ready"}, "stage_reviews": []}),
        encoding="utf-8",
    )
    manifest = manifest_mod.build_payload(str(runs), str(review_json))
    payload = mod.apply_manifest(manifest, archive_root=str(archive_root))

    summary = payload["summary"]
    rows = {(row["family_id"], row["group_id"]): row for row in payload["rows"]}

    assert summary["status"] == "runs_cleanup_batch4_archive_first_apply_report_ready"
    assert summary["applied_row_count"] == 3
    assert summary["moved_file_count"] == 7

    assert not (runs / "ligand_blind_gpcr_demo_stage1_queue.csv").exists()
    assert not (runs / "ligand_blind_gpcr_demo_stage2_active_learning_summary.json").exists()
    assert not (runs / "ligand_blind_gpcr_demo_stage3_summary.md").exists()
    assert not (runs / "ligand_blind_gpcr_demo_stage2_active_learning_target_weights.csv").exists()
    assert (runs / "ligand_blind_gpcr_demo_stage2_traj_manifest.csv").exists()
    assert (runs / "ligand_blind_gpcr_demo_stage3_scores.csv").exists()

    assert (archive_root / "ligand_blind_gpcr" / "stage1_all" / "ligand_blind_gpcr_demo_stage1_queue.csv").exists()
    assert (
        archive_root
        / "ligand_blind_gpcr"
        / "stage2_light_bundle"
        / "ligand_blind_gpcr_demo_stage2_active_learning_summary.json"
    ).exists()
    assert (
        archive_root / "ligand_blind_gpcr" / "stage3_summary_only" / "ligand_blind_gpcr_demo_stage3_summary.md"
    ).exists()

    assert rows[("ligand_blind_gpcr", "stage1_all")]["status"] == "archived"
    assert rows[("ligand_blind_gpcr", "stage2_light_bundle")]["status"] == "archived"
    assert rows[("ligand_blind_gpcr", "stage3_summary_only")]["status"] == "archived"


def test_main_writes_report_artifacts_and_skips_destination_conflicts(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()

    source_name = "ligand_blind_gpcr_demo_stage2_active_learning_summary.json"
    (runs / source_name).write_text("source-payload", encoding="utf-8")

    manifest_json = runs / "runs_cleanup_batch4_archive_first_manifest_current.json"
    manifest_json.write_text(
        json.dumps(
            {
                "summary": {"runs_dir": str(runs)},
                "rows": [
                    {
                        "family_id": "ligand_blind_gpcr",
                        "group_id": "stage2_light_bundle",
                        "stage_id": "stage2",
                        "recommended_disposition": "archive_first",
                        "match_count": 1,
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    archive_root = runs / "archive" / "batch4_archive_first"
    conflict_dir = archive_root / "ligand_blind_gpcr" / "stage2_light_bundle"
    conflict_dir.mkdir(parents=True, exist_ok=True)
    (conflict_dir / source_name).write_text("existing-archive-copy", encoding="utf-8")

    out_json = runs / "runs_cleanup_batch4_archive_first_apply_report_current.json"
    out_csv = runs / "runs_cleanup_batch4_archive_first_apply_report_current.csv"
    out_md = runs / "runs_cleanup_batch4_archive_first_apply_report_current.md"

    mod.main(
        [
            "--manifest-json",
            str(manifest_json),
            "--archive-root",
            str(archive_root),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    summary = payload["summary"]
    row = payload["rows"][0]

    assert out_csv.exists()
    assert out_md.exists()
    assert summary["applied_row_count"] == 0
    assert summary["moved_file_count"] == 0
    assert row["status"] == "destination_conflict_skipped"
    assert row["destination_conflict_count"] == 1
    assert (runs / source_name).exists()
    assert (conflict_dir / source_name).read_text(encoding="utf-8") == "existing-archive-copy"


def test_apply_manifest_marks_already_archived_when_active_root_is_empty(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    archive_root = runs / "archive" / "batch4_archive_first"
    archived_dir = archive_root / "ligand_blind_gpcr" / "stage3_summary_only"
    archived_dir.mkdir(parents=True, exist_ok=True)
    (archived_dir / "ligand_blind_gpcr_demo_stage3_summary.json").write_text("done", encoding="utf-8")
    (archived_dir / "ligand_blind_gpcr_demo_stage3_summary.md").write_text("done", encoding="utf-8")

    manifest = {
        "summary": {"runs_dir": str(runs)},
        "rows": [
            {
                "family_id": "ligand_blind_gpcr",
                "group_id": "stage3_summary_only",
                "stage_id": "stage3",
                "recommended_disposition": "archive_first",
                "match_count": 2,
            }
        ],
    }

    payload = mod.apply_manifest(manifest, archive_root=str(archive_root))
    summary = payload["summary"]
    row = payload["rows"][0]

    assert summary["applied_row_count"] == 0
    assert summary["already_archived_row_count"] == 1
    assert summary["already_archived_file_count"] == 2
    assert row["status"] == "already_archived"
    assert row["already_archived_file_count"] == 2
