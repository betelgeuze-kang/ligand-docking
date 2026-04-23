from __future__ import annotations

from pathlib import Path

from tools.build_runs_archive_cleanup_review_manifest import build_payload


def test_build_runs_archive_cleanup_review_manifest(tmp_path: Path) -> None:
    archive = tmp_path / "runs" / "archive"
    archive.mkdir(parents=True)
    live_dir = archive / "runs_cleanup_batch3_archive_first_current"
    live_dir.mkdir()
    (live_dir / "a.txt").write_text("x", encoding="utf-8")
    (archive / "archive_2026-03-29_external_validation_batch1.tar.gz").write_bytes(b"x" * 100)
    (archive / "runs_cleanup_batch4_archive_first_current.tar.gz").write_bytes(b"x" * 100)

    payload = build_payload(str(archive))
    rows = {row["archive_item"]: row for row in payload["rows"]}

    assert payload["summary"]["status"] == "runs_archive_cleanup_review_manifest_ready"
    assert rows["runs_cleanup_batch3_archive_first_current"]["recommended_disposition"] == "apply_now"
    assert rows["archive_2026-03-29_external_validation_batch1.tar.gz"]["recommended_disposition"] == "offload_candidate"
    assert rows["runs_cleanup_batch4_archive_first_current.tar.gz"]["recommended_disposition"] == "keep_local_compact"
