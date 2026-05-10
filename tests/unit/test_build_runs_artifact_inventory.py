from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_runs_artifact_inventory as mod


def _row_by_path(payload: dict, path: str) -> dict:
    rows = {row["path"]: row for row in payload["rows"]}
    return rows[path]


def test_build_inventory_protects_current_and_referenced_artifacts(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "keep_current.json").write_text("{}", encoding="utf-8")
    (runs / "referenced_evidence.dat").write_text("evidence", encoding="utf-8")
    (runs / "old_2026-03-01_stage3_scores.csv").write_text("score\n1\n", encoding="utf-8")
    (runs / "empty.tmp").write_text("", encoding="utf-8")
    nested = runs / "old_stage2_traj_frames"
    nested.mkdir()
    (nested / "frame_0001.npz").write_text("bundle", encoding="utf-8")
    archive_dir = runs / "archive" / "batch"
    archive_dir.mkdir(parents=True)

    doc = tmp_path / "commercialization_status_report.md"
    doc.write_text(
        "\n".join(
            [
                "Evidence: `runs/referenced_evidence.dat`",
                "Archive dir: `runs/archive/batch`",
                "Missing: `runs/missing_current.json`",
            ]
        ),
        encoding="utf-8",
    )

    payload = mod.build_inventory(
        runs_dir=runs,
        reference_roots=[str(doc)],
        generated_at_local="2026-05-08T00:00:00+09:00",
        top_n=10,
        large_threshold_mb=1,
    )

    summary = payload["summary"]
    assert summary["status"] == "runs_artifact_inventory_ready"
    assert summary["total_file_count"] == 5
    assert summary["referenced_existing_count"] == 2
    assert summary["referenced_missing_count"] == 1
    assert payload["missing_references"] == ["runs/missing_current.json"]

    assert _row_by_path(payload, "runs/keep_current.json")["classification"] == "keep_current_artifact"
    assert _row_by_path(payload, "runs/referenced_evidence.dat")["classification"] == "keep_referenced_evidence"
    assert _row_by_path(payload, "runs/old_2026-03-01_stage3_scores.csv")["cleanup_action"] == "archive_review"
    assert _row_by_path(payload, "runs/old_stage2_traj_frames/frame_0001.npz")["cleanup_action"] == "archive_review"
    assert _row_by_path(payload, "runs/empty.tmp")["cleanup_action"] == "delete_review"


def test_main_writes_compact_json_full_csv_and_markdown(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "active_current.json").write_text("{}", encoding="utf-8")
    (runs / "old_2026-03-01_stage3_scores.csv").write_text("score\n1\n", encoding="utf-8")
    doc = tmp_path / "status.md"
    doc.write_text("See `runs/active_current.json`.", encoding="utf-8")

    out_json = runs / "runs_artifact_inventory_current.json"
    out_csv = runs / "runs_artifact_inventory_current.csv"
    out_md = runs / "runs_artifact_inventory_current.md"

    mod.main(
        [
            "--runs-dir",
            str(runs),
            "--reference-root",
            str(doc),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
            "--top-n",
            "5",
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert "rows" not in payload
    assert payload["summary"]["total_file_count"] == 2
    with out_csv.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert {row["path"] for row in rows} == {
        "runs/active_current.json",
        "runs/old_2026-03-01_stage3_scores.csv",
    }
    assert "# Runs Artifact Inventory" in out_md.read_text(encoding="utf-8")
