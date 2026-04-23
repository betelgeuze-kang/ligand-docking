from __future__ import annotations

from pathlib import Path

from tools.apply_idp_3bead_holdout_archive_first import apply_manifest


def test_apply_idp_3bead_holdout_archive_first_moves_matching_prefix(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    archive_root = runs / "archive" / "idp_holdout_batch1"

    prefix = "idp_3bead_holdout_v7_fastpair_2026-03-16_r1"
    (runs / f"{prefix}_combined_gate_summary.json").write_text("{}", encoding="utf-8")
    (runs / f"{prefix}_fold1_alpha_eval_corrected_targets.csv").write_text("a,b\n", encoding="utf-8")
    (runs / "idp_3bead_holdout_v7_anchor_commercial_pretest_r1_summary.json").write_text("{}", encoding="utf-8")

    manifest = {
        "rows": [
            {
                "prefix": prefix,
                "classification": "legacy_branch_candidate",
                "file_count": 2,
                "size_mb": 0.01,
            }
        ]
    }

    cwd = Path.cwd()
    try:
        # apply_manifest resolves runs/ from cwd, so run inside tmp root
        import os
        os.chdir(tmp_path)
        payload = apply_manifest(manifest, archive_root=str(archive_root))
    finally:
        os.chdir(cwd)

    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["status"] == "idp_3bead_holdout_archive_first_apply_report_ready"
    assert summary["applied_row_count"] == 1
    assert summary["moved_file_count"] == 2
    assert row["status"] == "archived"
    assert not (runs / f"{prefix}_combined_gate_summary.json").exists()
    assert (runs / "idp_3bead_holdout_v7_anchor_commercial_pretest_r1_summary.json").exists()
    assert (archive_root / prefix / f"{prefix}_combined_gate_summary.json").exists()
