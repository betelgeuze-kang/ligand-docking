from __future__ import annotations

import json
from pathlib import Path

from tools import apply_runs_cleanup_batch3_archive_first as mod
from tools import build_runs_cleanup_batch3_review_manifest as review_mod


def test_apply_manifest_moves_only_archive_first_rows(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    archive_root = runs / "archive" / "batch3_archive_first"

    files = [
        "ligand_blind_gpcr_full_2026-03-11_r1_p0_stage0_leakage_summary.json",
        "ligand_blind_gpcr_full_2026-03-11_r1_p0_stage45_integrity_summary.md",
        "ligand_blind_gpcr_full_2026-03-11_r1_p0_stage1_queue.csv",
        "ligand_blind_trpv1_full_2026-03-11_r1_hard_decoy_split.csv",
        "ligand_stress_commercial_full_2026-03-11_r1_stage0_leakage_summary.md",
    ]
    for index, name in enumerate(files):
        (runs / name).write_text(f"payload-{index}", encoding="utf-8")

    manifest = review_mod.build_payload(str(runs))
    payload = mod.apply_manifest(manifest, archive_root=str(archive_root))

    summary = payload["summary"]
    rows = {(row["family_id"], row["subgroup_id"]): row for row in payload["rows"]}

    assert summary["status"] == "runs_cleanup_batch3_archive_first_apply_report_ready"
    assert summary["eligible_archive_first_row_count"] == 3
    assert summary["applied_row_count"] == 3
    assert summary["moved_file_count"] == 3

    assert not (runs / "ligand_blind_gpcr_full_2026-03-11_r1_p0_stage0_leakage_summary.json").exists()
    assert not (runs / "ligand_blind_gpcr_full_2026-03-11_r1_p0_stage45_integrity_summary.md").exists()
    assert not (runs / "ligand_stress_commercial_full_2026-03-11_r1_stage0_leakage_summary.md").exists()

    assert (
        archive_root
        / "ligand_blind_gpcr"
        / "stage0_leakage"
        / "ligand_blind_gpcr_full_2026-03-11_r1_p0_stage0_leakage_summary.json"
    ).exists()
    assert (
        archive_root
        / "ligand_blind_gpcr"
        / "stage4_or_45_integrity"
        / "ligand_blind_gpcr_full_2026-03-11_r1_p0_stage45_integrity_summary.md"
    ).exists()
    assert (
        archive_root
        / "ligand_stress_commercial"
        / "stage0_leakage"
        / "ligand_stress_commercial_full_2026-03-11_r1_stage0_leakage_summary.md"
    ).exists()

    assert (runs / "ligand_blind_gpcr_full_2026-03-11_r1_p0_stage1_queue.csv").exists()
    assert (runs / "ligand_blind_trpv1_full_2026-03-11_r1_hard_decoy_split.csv").exists()

    assert rows[("ligand_blind_gpcr", "stage0_leakage")]["status"] == "archived"
    assert rows[("ligand_blind_gpcr", "stage4_or_45_integrity")]["status"] == "archived"
    assert rows[("ligand_blind_gpcr", "stage1_queue_inputs")]["status"] == "skipped_non_archive_first"
    assert rows[("ligand_blind_trpv1", "hard_decoy_artifacts")]["status"] == "skipped_non_archive_first"


def test_main_writes_report_artifacts_and_skips_destination_conflicts(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()

    source_name = "ligand_blind_gpcr_full_2026-03-11_r1_p0_stage0_leakage_summary.json"
    (runs / source_name).write_text("source-payload", encoding="utf-8")

    manifest = review_mod.build_payload(str(runs))
    manifest_json = runs / "runs_cleanup_batch3_review_manifest_current.json"
    manifest_json.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    archive_root = runs / "archive" / "batch3_archive_first"
    conflict_dir = archive_root / "ligand_blind_gpcr" / "stage0_leakage"
    conflict_dir.mkdir(parents=True, exist_ok=True)
    (conflict_dir / source_name).write_text("existing-archive-copy", encoding="utf-8")

    out_json = runs / "runs_cleanup_batch3_archive_first_apply_report_current.json"
    out_csv = runs / "runs_cleanup_batch3_archive_first_apply_report_current.csv"
    out_md = runs / "runs_cleanup_batch3_archive_first_apply_report_current.md"

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
