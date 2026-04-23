from __future__ import annotations

from pathlib import Path

from tools import build_runs_cleanup_audit as mod


def _touch(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def test_build_runs_cleanup_audit(tmp_path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    _touch(runs / "external_validation_2026-03-22_big.json", 4096)
    _touch(runs / "external_validation_2026-03-22_bigger.csv", 4096)
    _touch(runs / "idp_3bead_holdout_v7_fold1.json", 1024)
    _touch(runs / "idp_summary_current.json", 512)

    payload = mod.build_payload(str(runs), top_n=3)
    summary = payload["summary"]
    assert summary["top_level_file_count"] == 4
    assert summary["current_artifact_file_count"] == 1
    assert summary["archive_only_cleanup_recommended"] is True
    assert summary["raw_prune_scanned_files"] >= 3
    assert payload["rows"][0]["prefix"] == "external_validation_2026-03-22"
    assert payload["rows"][0]["candidate_status"] == "review_archive_candidate"
