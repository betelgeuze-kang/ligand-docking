from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_storage_residual_cleanup_status as mod


def _write(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def test_storage_residual_cleanup_status_records_candidates_without_mutation(tmp_path: Path) -> None:
    _write(tmp_path / "runs" / "a.bin", 12)
    _write(tmp_path / "rust_engine" / "target" / "artifact.bin", 20)
    targets = (
        ("runs", "keep_inventory", "keep generated run history"),
        ("rust_engine/target", "delete_regenerable_build_artifact", "build artifact"),
        (".venv", "delete_regenerable_local_environment", "local env"),
    )

    payload = mod.build_storage_residual_cleanup_status(root=tmp_path, heavy_threshold_bytes=10, targets=targets)
    summary = payload["summary"]
    by_path = {row["path"]: row for row in payload["rows"]}

    assert summary["status"] == "storage_residual_cleanup_status_ready"
    assert summary["target_path_count"] == 3
    assert summary["resolved_missing_path_count"] == 1
    assert summary["operator_action_candidate_count"] == 1
    assert by_path["runs"]["status"] == "tracked_keep"
    assert by_path["rust_engine/target"]["status"] == "operator_action_candidate"
    assert by_path[".venv"]["status"] == "resolved_missing"
    assert summary["delete_executed"] is False
    assert summary["archive_executed"] is False
    assert summary["externalize_executed"] is False
    assert summary["external_state_mutated"] is False


def test_storage_residual_cleanup_status_tool_writes_outputs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo / "runs" / "a.bin", 4)
    out_json = tmp_path / "status.json"
    out_csv = tmp_path / "status.csv"
    out_md = tmp_path / "status.md"

    mod.main(
        [
            "--root",
            str(repo),
            "--heavy-threshold-bytes",
            "1",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    summary = json.loads(out_json.read_text(encoding="utf-8"))["summary"]
    assert summary["status"] == "storage_residual_cleanup_status_ready"
    assert summary["external_state_mutated"] is False
    assert out_csv.read_text(encoding="utf-8").startswith("path,exists,size_bytes,")
    assert "Storage Residual Cleanup Status" in out_md.read_text(encoding="utf-8")
