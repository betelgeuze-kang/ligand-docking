from __future__ import annotations

from pathlib import Path

from tools.cleanup import build_runs_cleanup_manifest as mod


def _touch(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def test_build_runs_cleanup_manifest(tmp_path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    _touch(runs / "external_validation_2026-03-22_big.json", 4096)
    _touch(runs / "external_validation_2026-03-22_bigger.csv", 4096)
    _touch(runs / "external_validation_2026-03-23_a.md", 1024)
    audit = {"summary": {"raw_prune_safe_to_execute_now": False}}

    payload = mod.build_payload(str(runs), audit, "2026-03-29")
    summary = payload["summary"]
    rows = {row["prefix"]: row for row in payload["rows"]}

    assert summary["status"] == "runs_cleanup_manifest_ready"
    assert summary["archive_candidate_batch_count"] >= 2
    assert summary["archive_candidate_file_count"] == 3
    assert summary["raw_prune_safe_to_execute_now"] is False
    assert rows["external_validation_2026-03-22"]["archive_now"] is True
    assert rows["external_validation_2026-03-22"]["file_count"] == 2
    assert rows["idp_3bead_holdout"]["archive_now"] is False
    assert rows["*_current.*"]["archive_now"] is False
