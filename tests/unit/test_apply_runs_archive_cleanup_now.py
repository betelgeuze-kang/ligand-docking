from __future__ import annotations

import json
import os
from pathlib import Path

from tools.apply_runs_archive_cleanup_now import apply_manifest


def test_apply_runs_archive_cleanup_now_compresses_live_archive_dir(tmp_path: Path) -> None:
    archive = tmp_path / "runs" / "archive"
    archive.mkdir(parents=True)
    live_dir = archive / "runs_cleanup_batch3_archive_first_current"
    live_dir.mkdir()
    (live_dir / "artifact.txt").write_text("payload", encoding="utf-8")

    manifest = {
        "rows": [
            {
                "archive_item": "runs_cleanup_batch3_archive_first_current",
                "recommended_disposition": "apply_now",
                "size_mb": 0.01,
            }
        ]
    }

    cwd = Path.cwd()
    try:
        os.chdir(tmp_path)
        payload = apply_manifest(manifest)
    finally:
        os.chdir(cwd)

    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["status"] == "runs_archive_cleanup_apply_report_ready"
    assert summary["applied_row_count"] == 1
    assert row["status"] == "compressed_and_removed_dir"
    assert not live_dir.exists()
    assert (archive / "runs_cleanup_batch3_archive_first_current.tar.gz").exists()
