from __future__ import annotations

from pathlib import Path

from tools.build_runs_cold_storage_offload_review_manifest import build_payload


def test_build_runs_cold_storage_offload_review_manifest(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    archive = runs / "archive"
    archive.mkdir(parents=True)
    (runs / "archive_2026-03-29_external_validation_batch1.tar.gz").write_bytes(b"x" * (600 * 1024 * 1024))
    (archive / "runs_cleanup_batch4_archive_first_current.tar.gz").write_bytes(b"x" * 1024)

    payload = build_payload(str(runs))
    rows = {row["path"]: row for row in payload["rows"]}

    assert payload["summary"]["status"] == "runs_cold_storage_offload_review_manifest_ready"
    assert rows["runs/archive_2026-03-29_external_validation_batch1.tar.gz"]["recommended_disposition"] == "external_offload_candidate"
    assert rows["runs/archive/runs_cleanup_batch4_archive_first_current.tar.gz"]["recommended_disposition"] == "keep_local_compact"
