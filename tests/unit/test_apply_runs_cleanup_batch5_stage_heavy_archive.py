from __future__ import annotations

import json
from pathlib import Path

from tools import apply_runs_cleanup_batch5_stage_heavy_archive as mod


def test_apply_manifest_moves_only_batch5_heavy_rows(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    archive_root = runs / "archive" / "batch5_stage_heavy"

    files = [
        "ligand_blind_gpcr_demo_stage2_traj_manifest.csv",
        "ligand_blind_gpcr_demo_stage2_active_learning_summary.json",
        "ligand_blind_gpcr_demo_stage3_scores.csv",
        "ligand_blind_gpcr_demo_stage3_summary.json",
    ]
    for index, name in enumerate(files):
        (runs / name).write_text(f"payload-{index}", encoding="utf-8")

    manifest = {
        "summary": {"runs_dir": str(runs), "status": "runs_cleanup_batch5_stage_heavy_review_manifest_ready"},
        "rows": [
            {
                "family_id": "ligand_blind_gpcr",
                "group_id": "stage2_traj_manifest_bundle",
                "stage_id": "stage2",
                "recommended_disposition": "review_for_archive_after_sampling",
                "match_count": 1,
                "size_mb": 0.01,
            },
            {
                "family_id": "ligand_blind_gpcr",
                "group_id": "stage3_scores_bundle",
                "stage_id": "stage3",
                "recommended_disposition": "review_for_archive_after_sampling",
                "match_count": 1,
                "size_mb": 0.01,
            },
        ],
    }
    signoff = {
        "summary": {"status": "runs_cleanup_batch5_family_signoff_note_ready"},
        "rows": [
            {
                "family_id": "ligand_blind_gpcr",
                "signoff_recommendation": "approve_archive_after_sampling",
            }
        ],
    }

    payload = mod.apply_manifest(manifest, signoff, archive_root=str(archive_root))
    summary = payload["summary"]
    rows = {(row["family_id"], row["group_id"]): row for row in payload["rows"]}

    assert summary["status"] == "runs_cleanup_batch5_stage_heavy_apply_report_ready"
    assert summary["applied_row_count"] == 2
    assert summary["moved_file_count"] == 2
    assert not (runs / "ligand_blind_gpcr_demo_stage2_traj_manifest.csv").exists()
    assert not (runs / "ligand_blind_gpcr_demo_stage3_scores.csv").exists()
    assert (runs / "ligand_blind_gpcr_demo_stage2_active_learning_summary.json").exists()
    assert (runs / "ligand_blind_gpcr_demo_stage3_summary.json").exists()
    assert (
        archive_root / "ligand_blind_gpcr" / "stage2_traj_manifest_bundle" / "ligand_blind_gpcr_demo_stage2_traj_manifest.csv"
    ).exists()
    assert (
        archive_root / "ligand_blind_gpcr" / "stage3_scores_bundle" / "ligand_blind_gpcr_demo_stage3_scores.csv"
    ).exists()
    assert rows[("ligand_blind_gpcr", "stage2_traj_manifest_bundle")]["status"] == "archived"
    assert rows[("ligand_blind_gpcr", "stage3_scores_bundle")]["status"] == "archived"


def test_main_skips_when_signoff_is_missing(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "ligand_blind_gpcr_demo_stage3_scores.csv").write_text("payload", encoding="utf-8")

    manifest_json = runs / "runs_cleanup_batch5_stage_heavy_review_manifest_current.json"
    manifest_json.write_text(
        json.dumps(
            {
                "summary": {"runs_dir": str(runs)},
                "rows": [
                    {
                        "family_id": "ligand_blind_gpcr",
                        "group_id": "stage3_scores_bundle",
                        "stage_id": "stage3",
                        "recommended_disposition": "review_for_archive_after_sampling",
                        "match_count": 1,
                        "size_mb": 0.01,
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    signoff_json = runs / "runs_cleanup_batch5_family_signoff_note_current.json"
    signoff_json.write_text(json.dumps({"summary": {}, "rows": []}), encoding="utf-8")

    out_json = runs / "runs_cleanup_batch5_stage_heavy_apply_report_current.json"
    out_csv = runs / "runs_cleanup_batch5_stage_heavy_apply_report_current.csv"
    out_md = runs / "runs_cleanup_batch5_stage_heavy_apply_report_current.md"
    archive_root = runs / "archive" / "batch5_stage_heavy"

    mod.main(
        [
            "--manifest-json",
            str(manifest_json),
            "--signoff-json",
            str(signoff_json),
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
    assert row["status"] == "family_signoff_missing_or_not_approved"
    assert (runs / "ligand_blind_gpcr_demo_stage3_scores.csv").exists()
