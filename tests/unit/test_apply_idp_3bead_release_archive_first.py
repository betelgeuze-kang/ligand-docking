from __future__ import annotations

from pathlib import Path

from tools.apply_idp_3bead_release_archive_first import apply_manifest


def test_apply_idp_3bead_release_archive_first_moves_matching_prefix(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    archive_root = runs / "archive" / "idp_release_batch1"

    prefix = "idp_3bead_release_smoke_current_2026-03-22_external-foo"
    (runs / f"{prefix}_summary.json").write_text("{}", encoding="utf-8")
    (runs / f"{prefix}_fold1_eval_corrected_targets.csv").write_text("a,b\n", encoding="utf-8")
    (runs / "idp_3bead_release_smoke_summary_current.json").write_text("{}", encoding="utf-8")

    manifest = {
        "rows": [
            {
                "prefix": prefix,
                "classification": "historical_release_smoke_candidate",
                "recommended_disposition": "archive_first",
                "file_count": 2,
                "size_mb": 0.01,
            }
        ]
    }

    cwd = Path.cwd()
    try:
        import os

        os.chdir(tmp_path)
        payload = apply_manifest(manifest, archive_root=str(archive_root))
    finally:
        os.chdir(cwd)

    assert payload["summary"]["status"] == "idp_3bead_release_archive_first_apply_report_ready"
    assert payload["summary"]["applied_row_count"] == 1
    assert payload["summary"]["moved_file_count"] == 2
    assert not (runs / f"{prefix}_summary.json").exists()
    assert (runs / "idp_3bead_release_smoke_summary_current.json").exists()
    assert (archive_root / prefix / f"{prefix}_summary.json").exists()

