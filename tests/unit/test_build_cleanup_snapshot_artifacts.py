from __future__ import annotations

import json
from pathlib import Path

from tools import build_cleanup_snapshot_artifacts as mod


def _preflight_packet(target: Path, snapshot_artifact: Path) -> dict:
    return {
        "summary": {"status": "blocked_cleanup_snapshot_preflight"},
        "rows": [
            {
                "lane": "casp17_external_pool",
                "path": str(target),
                "recommended_action": "externalize",
                "approval_token": "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS",
                "snapshot_artifact": str(snapshot_artifact),
                "snapshot_required": True,
            },
            {
                "lane": "build_output",
                "path": str(target / "ignored"),
                "recommended_action": "delete_candidate",
                "approval_token": "APPROVE_DELETE_REGENERABLE_LOCAL_ARTIFACTS",
                "snapshot_artifact": str(snapshot_artifact.with_name("ignored.snapshot.json")),
                "snapshot_required": False,
            },
        ],
    }


def test_cleanup_snapshot_artifacts_writes_local_metadata_snapshot(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "alpha.txt").write_text("alpha\n", encoding="utf-8")
    nested = target / "nested"
    nested.mkdir()
    (nested / "beta.txt").write_text("beta\n", encoding="utf-8")
    snapshot_artifact = tmp_path / "snapshots" / "target.snapshot.json"

    payload = mod.build_cleanup_snapshot_artifacts(
        cleanup_snapshot_preflight_packet=_preflight_packet(target, snapshot_artifact),
        max_listing_entries=2,
    )

    summary = payload["summary"]
    assert summary["status"] == "cleanup_snapshot_artifacts_ready"
    assert summary["snapshot_artifact_count"] == 1
    assert summary["snapshot_ready_count"] == 1
    assert summary["listing_truncated_count"] == 1
    assert summary["total_file_count"] == 2
    assert summary["total_dir_count"] == 2
    assert len(summary["snapshot_set_fingerprint_sha256"]) == 64
    assert summary["snapshot_created"] is True
    assert summary["delete_executed"] is False
    assert summary["external_state_mutated"] is False

    snapshot = json.loads(snapshot_artifact.read_text(encoding="utf-8"))
    snapshot_summary = snapshot["summary"]
    assert snapshot_summary["status"] == "cleanup_snapshot_artifact_ready"
    assert snapshot_summary["entry_count"] == 4
    assert snapshot_summary["file_count"] == 2
    assert snapshot_summary["dir_count"] == 2
    assert snapshot_summary["listing_entry_count"] == 2
    assert snapshot_summary["listing_truncated"] is True
    assert len(snapshot_summary["metadata_fingerprint_sha256"]) == 64
    assert snapshot_summary["snapshot_created"] is True
    assert snapshot_summary["delete_executed"] is False
    assert snapshot_summary["external_state_mutated"] is False


def test_cleanup_snapshot_artifacts_blocks_missing_target(tmp_path: Path) -> None:
    missing_target = tmp_path / "missing"
    snapshot_artifact = tmp_path / "snapshots" / "missing.snapshot.json"

    payload = mod.build_cleanup_snapshot_artifacts(
        cleanup_snapshot_preflight_packet=_preflight_packet(missing_target, snapshot_artifact),
    )

    assert payload["summary"]["status"] == "blocked_cleanup_snapshot_artifacts"
    assert payload["summary"]["snapshot_blocked_count"] == 1
    assert payload["rows"][0]["snapshot_status"] == "blocked_cleanup_snapshot_artifact"
    snapshot = json.loads(snapshot_artifact.read_text(encoding="utf-8"))
    assert snapshot["blockers"] == ["target_path_missing"]
    assert snapshot["summary"]["target_exists"] is False
    assert snapshot["summary"]["delete_executed"] is False
    assert snapshot["summary"]["external_state_mutated"] is False


def test_cleanup_snapshot_artifacts_tool_writes_outputs(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "alpha.txt").write_text("alpha\n", encoding="utf-8")
    snapshot_artifact = tmp_path / "snapshots" / "target.snapshot.json"
    preflight_json = tmp_path / "preflight.json"
    out_json = tmp_path / "artifacts.json"
    out_csv = tmp_path / "artifacts.csv"
    out_md = tmp_path / "artifacts.md"
    preflight_json.write_text(json.dumps(_preflight_packet(target, snapshot_artifact)) + "\n", encoding="utf-8")

    mod.main(
        [
            "--cleanup-snapshot-preflight-json",
            str(preflight_json),
            "--max-listing-entries",
            "10",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "cleanup_snapshot_artifacts_ready"
    assert snapshot_artifact.is_file()
    assert out_csv.read_text(encoding="utf-8").startswith("lane,path,")
    assert "Cleanup Snapshot Artifacts" in out_md.read_text(encoding="utf-8")
