from __future__ import annotations

import json
from pathlib import Path

from tools.cleanup import build_transition_cleanup_execution_preflight as mod


def _work_order(tmp_path: Path) -> dict:
    external_pool = tmp_path / "casp17" / "massivefold_external_pool_intake"
    archive = tmp_path / "runs" / "archive"
    target = tmp_path / "rust_engine" / "target"
    review = tmp_path / "runs" / "legacy" / "stage2_traj_frames"
    for path in (external_pool, archive, target, review):
        path.mkdir(parents=True, exist_ok=True)
        (path / "stub.bin").write_bytes(b"x")
    return {
        "summary": {
            "status": "transition_cleanup_work_order_ready",
            "approval_gated_count": 3,
            "review_only_count": 1,
            "missing_noop_count": 1,
            "delete_enabled": False,
            "action_executed": False,
            "external_state_mutated": False,
        },
        "rows": [
            {
                "path": str(external_pool),
                "lane": "casp17_external_pool",
                "recommended_action": "externalize",
                "work_order_status": "approval_gated",
                "operator_approval_required": True,
                "approval_token": "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS",
                "exists": True,
                "size_bytes": 1,
                "size_gb": 0.0,
                "delete_enabled": False,
                "action_executed": False,
                "external_state_mutated": False,
            },
            {
                "path": str(archive),
                "lane": "legacy_runs_archive",
                "recommended_action": "archive",
                "work_order_status": "approval_gated",
                "operator_approval_required": True,
                "approval_token": "APPROVE_ARCHIVE_LEGACY_RUNS",
                "exists": True,
                "size_bytes": 1,
                "size_gb": 0.0,
                "delete_enabled": False,
                "action_executed": False,
                "external_state_mutated": False,
            },
            {
                "path": str(target),
                "lane": "build_output",
                "recommended_action": "delete_candidate",
                "work_order_status": "approval_gated",
                "operator_approval_required": True,
                "approval_token": "APPROVE_DELETE_REGENERABLE_LOCAL_ARTIFACTS",
                "exists": True,
                "size_bytes": 1,
                "size_gb": 0.0,
                "delete_enabled": False,
                "action_executed": False,
                "external_state_mutated": False,
            },
            {
                "path": str(review),
                "lane": "legacy_trajectory_frames",
                "recommended_action": "review_for_stage2_traj_frames",
                "work_order_status": "review_only",
                "operator_approval_required": False,
                "approval_token": "",
                "exists": True,
                "size_bytes": 1,
                "size_gb": 0.0,
                "delete_enabled": False,
                "action_executed": False,
                "external_state_mutated": False,
            },
            {
                "path": str(tmp_path / "missing_root"),
                "lane": "ligand_heavy_runs_config_root",
                "recommended_action": "review_for_ligand_heavy_payload_cleanup",
                "work_order_status": "missing_noop",
                "operator_approval_required": False,
                "approval_token": "",
                "exists": False,
                "size_bytes": 0,
                "size_gb": 0.0,
                "delete_enabled": False,
                "action_executed": False,
                "external_state_mutated": False,
            },
        ],
    }


def test_transition_cleanup_execution_preflight_ready(tmp_path: Path) -> None:
    payload = mod.build_execution_preflight(_work_order(tmp_path))

    assert payload["summary"]["status"] == "transition_cleanup_execution_preflight_ready"
    assert payload["summary"]["approval_gated_count"] == 3
    assert payload["summary"]["review_only_count"] == 1
    assert payload["summary"]["delete_enabled"] is False
    assert payload["summary"]["action_executed"] is False
    assert payload["summary"]["external_state_mutated"] is False
    assert all(row["preflight_status"] == "pass" for row in payload["rows"])


def test_transition_cleanup_execution_preflight_blocks_missing_approval_path(tmp_path: Path) -> None:
    work_order = _work_order(tmp_path)
    approval_row = work_order["rows"][0]
    target = Path(approval_row["path"])
    (target / "stub.bin").unlink()
    target.rmdir()

    payload = mod.build_execution_preflight(work_order)

    assert payload["summary"]["status"] == "blocked_transition_cleanup_execution_preflight"
    assert any("approval_candidate_missing_refresh_required" in blocker["reason"] for blocker in payload["blockers"])


def test_transition_cleanup_execution_preflight_tool_writes_outputs(tmp_path: Path) -> None:
    work_order_json = tmp_path / "work_order.json"
    out_json = tmp_path / "preflight.json"
    out_csv = tmp_path / "preflight.csv"
    out_md = tmp_path / "preflight.md"
    work_order_json.write_text(json.dumps(_work_order(tmp_path)) + "\n", encoding="utf-8")

    mod.main(
        [
            "--work-order-json",
            str(work_order_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "transition_cleanup_execution_preflight_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("path,resolved_path,")
    assert "Transition Cleanup Execution Preflight" in out_md.read_text(encoding="utf-8")
