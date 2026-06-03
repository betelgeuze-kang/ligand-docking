from __future__ import annotations

import json
from pathlib import Path

from tools import build_large_cleanup_surface_drilldown as mod


def _write_bytes(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def _action_board(surface: Path, payload_surface: Path) -> dict:
    return {
        "summary": {"status": "operator_actions_required"},
        "rows": [
            {
                "action_type": "review_large_cleanup_surface",
                "status": "review_required",
                "artifact_path": str(surface),
                "size_gb": 0.001,
            },
            {
                "action_type": "review_large_cleanup_surface",
                "status": "review_required",
                "artifact_path": str(payload_surface),
                "size_gb": 0.001,
            },
        ],
    }


def _dry_run(surface: Path, payload_surface: Path) -> dict:
    payload = surface / "external_validation_old" / "stage2_trajectory_frames"
    return {
        "summary": {"status": "dry_run", "execute": False},
        "rows": [
            {
                "path": str(payload),
                "status": "kept_recent_slot",
                "reason": "protected by keep-recent",
            },
            {
                "path": str(payload_surface),
                "status": "dry_run_delete",
                "reason": "eligible heavy payload for deletion",
            },
        ],
    }


def test_large_cleanup_surface_drilldown_finds_known_payload_children(tmp_path: Path) -> None:
    surface = tmp_path / "ligand_heavy_runs"
    run_with_payload = surface / "external_validation_old"
    run_without_payload = surface / "manual_review_run"
    payload_surface = tmp_path / "runs" / "legacy" / "stage2_traj_frames"
    _write_bytes(run_with_payload / "stage2_trajectory_frames" / "traj.xtc", 12)
    _write_bytes(run_with_payload / "manifest.json", 2)
    _write_bytes(run_without_payload / "summary.json", 4)
    _write_bytes(payload_surface / "traj.xtc", 8)

    payload = mod.build_drilldown(_action_board(surface, payload_surface), ligand_heavy_dry_run_packet=_dry_run(surface, payload_surface))
    rows = payload["rows"]

    assert payload["summary"]["status"] == "large_cleanup_surface_drilldown_ready"
    assert payload["summary"]["surface_count"] == 2
    assert payload["summary"]["known_payload_row_count"] == 2
    assert payload["summary"]["dry_run_delete_payload_row_count"] == 1
    assert payload["summary"]["dry_run_protected_payload_row_count"] == 1
    assert payload["summary"]["delete_enabled"] is False
    assert payload["summary"]["delete_executed"] is False
    assert payload["summary"]["external_state_mutated"] is False
    assert any(row["status"] == "known_payloads_protected_by_dry_run" and row["source_dry_run_status"] == "kept_recent_slot" for row in rows)
    assert any(row["scope"] == "known_payload_surface" and row["source_dry_run_status"] == "dry_run_delete" for row in rows)
    assert any(row["status"] == "review_no_known_payload" for row in rows)


def test_large_cleanup_surface_drilldown_tool_writes_outputs(tmp_path: Path) -> None:
    surface = tmp_path / "ligand_heavy_runs"
    payload_surface = tmp_path / "runs" / "legacy" / "stage2_traj_frames"
    _write_bytes(surface / "external_validation_old" / "stage2_trajectory_frames" / "traj.xtc", 12)
    _write_bytes(payload_surface / "traj.xtc", 8)
    action_board_json = tmp_path / "action_board.json"
    dry_run_json = tmp_path / "dry_run.json"
    out_json = tmp_path / "drilldown.json"
    out_csv = tmp_path / "drilldown.csv"
    out_md = tmp_path / "drilldown.md"
    action_board_json.write_text(json.dumps(_action_board(surface, payload_surface)) + "\n", encoding="utf-8")
    dry_run_json.write_text(json.dumps(_dry_run(surface, payload_surface)) + "\n", encoding="utf-8")

    mod.main(
        [
            "--action-board-json",
            str(action_board_json),
            "--ligand-heavy-dry-run-json",
            str(dry_run_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "large_cleanup_surface_drilldown_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("surface_path,")
    assert "Large Cleanup Surface Drilldown" in out_md.read_text(encoding="utf-8")
