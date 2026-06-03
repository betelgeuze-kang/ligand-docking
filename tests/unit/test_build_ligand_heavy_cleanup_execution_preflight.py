from __future__ import annotations

import json
from pathlib import Path

from tools import build_ligand_heavy_cleanup_execution_preflight as mod


def _make_candidate_tree(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "ligand_heavy_runs"
    run_path = root / "ligand_old"
    payload = run_path / "stage2_trajectory_frames"
    payload.mkdir(parents=True)
    (payload / "frame_001.xtc").write_bytes(b"heavy")
    return root, run_path, payload


def _approval_packet(root: Path, run_path: Path, payload: Path) -> dict:
    return {
        "summary": {
            "status": "approval_packet_ready",
            "candidate_count": 1,
            "candidate_bytes": 5,
            "candidate_size_gb": 0.0,
            "approval_token_required": "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS",
            "delete_executed": False,
            "external_state_mutated": False,
        },
        "rows": [
            {
                "root": str(root),
                "path": str(payload),
                "run_path": str(run_path),
                "run_name": run_path.name,
                "payload_name": payload.name,
                "size_bytes": 5,
                "deletion_scope": "payload_directory_only",
                "parent_run_preserved": True,
            }
        ],
    }


def _work_order(root: Path) -> dict:
    return {
        "summary": {
            "status": "cleanup_work_order_ready",
            "candidate_count": 1,
            "approval_token_required": "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS",
            "delete_enabled": False,
            "delete_executed": False,
            "external_state_mutated": False,
        },
        "commands": {
            "refresh_dry_run_command": f"python3 tools/cleanup_ligand_heavy_runs.py --root {root} --keep-recent 2 --older-than-days 7",
            "execute_after_approval_command": f"python3 tools/cleanup_ligand_heavy_runs.py --root {root} --keep-recent 2 --older-than-days 7 --execute",
        },
    }


def test_ligand_heavy_cleanup_execution_preflight_ready(tmp_path: Path) -> None:
    root, run_path, payload = _make_candidate_tree(tmp_path)

    result = mod.build_execution_preflight(_approval_packet(root, run_path, payload), _work_order(root))

    assert result["summary"]["status"] == "ligand_heavy_cleanup_execution_preflight_ready"
    assert result["summary"]["delete_enabled"] is False
    assert result["summary"]["delete_executed"] is False
    assert result["summary"]["external_state_mutated"] is False
    assert result["rows"][0]["preflight_status"] == "pass"


def test_ligand_heavy_cleanup_execution_preflight_blocks_missing_candidate(tmp_path: Path) -> None:
    root, run_path, payload = _make_candidate_tree(tmp_path)
    for child in payload.iterdir():
        child.unlink()
    payload.rmdir()

    result = mod.build_execution_preflight(_approval_packet(root, run_path, payload), _work_order(root))

    assert result["summary"]["status"] == "blocked_ligand_heavy_cleanup_execution_preflight"
    assert any(blocker["code"] == "cleanup_candidate_blocked" for blocker in result["blockers"])
    assert "candidate_path_missing_refresh_required" in result["rows"][0]["blockers"]


def test_ligand_heavy_cleanup_execution_preflight_tool_writes_outputs(tmp_path: Path) -> None:
    root, run_path, payload = _make_candidate_tree(tmp_path)
    approval_json = tmp_path / "approval.json"
    work_order_json = tmp_path / "work_order.json"
    out_json = tmp_path / "preflight.json"
    out_csv = tmp_path / "preflight.csv"
    out_md = tmp_path / "preflight.md"
    approval_json.write_text(json.dumps(_approval_packet(root, run_path, payload)) + "\n", encoding="utf-8")
    work_order_json.write_text(json.dumps(_work_order(root)) + "\n", encoding="utf-8")

    mod.main(
        [
            "--approval-json",
            str(approval_json),
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

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "ligand_heavy_cleanup_execution_preflight_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("path,root,")
    assert "Ligand Heavy Cleanup Execution Preflight" in out_md.read_text(encoding="utf-8")
