from __future__ import annotations

import json
from pathlib import Path

from tools.cleanup import build_transition_cleanup_work_order as mod


def _manifest(status: str = "transition_cleanup_manifest_dry_run_ready") -> dict:
    return {
        "summary": {
            "status": status,
            "delete_executed": False,
            "external_state_mutated": False,
        },
        "rows": [
            {
                "path": "casp17/massivefold_external_pool_intake",
                "exists": True,
                "lane": "casp17_external_pool",
                "recommended_action": "externalize",
                "operator_approval_required": True,
                "size_bytes": 2048,
                "size_gb": 0.002,
                "execution_phase": "P1_externalize_after_snapshot",
                "approval_token": "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS",
                "postcheck": "checksum present",
            },
            {
                "path": "runs/legacy/stage2_traj_frames",
                "exists": True,
                "lane": "legacy_trajectory_frames",
                "recommended_action": "review_for_stage2_traj_frames",
                "operator_approval_required": False,
                "size_bytes": 1024,
                "size_gb": 0.001,
                "execution_phase": "P0_review_only",
                "approval_token": "",
                "postcheck": "operator review",
            },
            {
                "path": "missing/root",
                "exists": False,
                "lane": "legacy_runs_archive",
                "recommended_action": "archive",
                "operator_approval_required": False,
                "size_bytes": 0,
                "size_gb": 0.0,
                "execution_phase": "P1_archive_after_snapshot",
                "approval_token": "",
                "postcheck": "noop",
            },
        ],
    }


def test_transition_cleanup_work_order_splits_approval_and_review_rows() -> None:
    payload = mod.build_work_order(_manifest(), manifest_json="manifest.json")
    summary = payload["summary"]
    rows = {row["path"]: row for row in payload["rows"]}

    assert summary["status"] == "transition_cleanup_work_order_ready"
    assert summary["approval_gated_count"] == 1
    assert summary["review_only_count"] == 1
    assert summary["missing_noop_count"] == 1
    assert summary["delete_enabled"] is False
    assert summary["action_executed"] is False
    assert summary["external_state_mutated"] is False
    assert rows["casp17/massivefold_external_pool_intake"]["work_order_status"] == "approval_gated"
    assert rows["runs/legacy/stage2_traj_frames"]["work_order_status"] == "review_only"


def test_transition_cleanup_work_order_blocks_bad_manifest() -> None:
    manifest = _manifest(status="blocked")
    manifest["summary"]["delete_executed"] = True
    payload = mod.build_work_order(manifest)
    codes = {blocker["code"] for blocker in payload["blockers"]}

    assert payload["summary"]["status"] == "blocked_transition_cleanup_work_order"
    assert "manifest_not_ready" in codes
    assert "manifest_delete_flag_invalid" in codes


def test_transition_cleanup_work_order_tool_writes_outputs(tmp_path: Path) -> None:
    manifest_json = tmp_path / "manifest.json"
    out_json = tmp_path / "work_order.json"
    out_csv = tmp_path / "work_order.csv"
    out_md = tmp_path / "work_order.md"
    manifest_json.write_text(json.dumps(_manifest()) + "\n", encoding="utf-8")

    mod.main(
        [
            "--manifest-json",
            str(manifest_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "transition_cleanup_work_order_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("path,lane,")
    assert "Transition Cleanup Work Order" in out_md.read_text(encoding="utf-8")
