from __future__ import annotations

import json
from pathlib import Path

from tools import build_ligand_heavy_cleanup_work_order as mod


def _approval_packet(status: str = "approval_packet_ready") -> dict:
    return {
        "summary": {
            "status": status,
            "source_dry_run_json": "dry_run.json",
            "candidate_count": 2,
            "candidate_bytes": 3072,
            "candidate_size_gb": 0.003,
            "approval_token_required": "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS",
            "delete_executed": False,
            "external_state_mutated": False,
        },
        "rows": [
            {
                "root": "/mnt/a/ligand_heavy_runs",
                "path": "/mnt/a/ligand_heavy_runs/ligand_old/stage2_trajectory_frames",
                "run_name": "ligand_old",
                "payload_name": "stage2_trajectory_frames",
            },
            {
                "root": "/mnt/a/ligand_heavy_runs",
                "path": "/mnt/a/ligand_heavy_runs/ligand_older/stage2_trajectory_frames",
                "run_name": "ligand_older",
                "payload_name": "stage2_trajectory_frames",
            },
        ],
    }


def test_ligand_heavy_cleanup_work_order_builds_approval_gated_execute_command() -> None:
    payload = mod.build_work_order(_approval_packet(), approval_json="approval.json", out_report_json="after.json")

    summary = payload["summary"]
    assert summary["status"] == "cleanup_work_order_ready"
    assert summary["approval_token_required"] == "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS"
    assert summary["delete_enabled"] is False
    assert summary["delete_executed"] is False
    assert summary["external_state_mutated"] is False
    assert payload["rows"][1]["requires_approval_token"] is True
    assert "--execute" in payload["commands"]["execute_after_approval_command"]
    assert "--execute" not in payload["commands"]["refresh_dry_run_command"]


def test_ligand_heavy_cleanup_work_order_blocks_bad_approval_packet() -> None:
    packet = _approval_packet(status="blocked_approval_packet")
    packet["summary"]["delete_executed"] = True
    payload = mod.build_work_order(packet)
    codes = {blocker["code"] for blocker in payload["blockers"]}

    assert payload["summary"]["status"] == "blocked_cleanup_work_order"
    assert "approval_packet_not_ready" in codes
    assert "approval_packet_delete_flag_invalid" in codes


def test_ligand_heavy_cleanup_work_order_tool_writes_outputs(tmp_path: Path) -> None:
    approval_json = tmp_path / "approval.json"
    out_json = tmp_path / "work_order.json"
    out_csv = tmp_path / "work_order.csv"
    out_md = tmp_path / "work_order.md"
    approval_json.write_text(json.dumps(_approval_packet()) + "\n", encoding="utf-8")

    mod.main(
        [
            "--approval-json",
            str(approval_json),
            "--out-report-json",
            str(tmp_path / "after.json"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "cleanup_work_order_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("step,command,")
    assert "Ligand Heavy Cleanup Work Order" in out_md.read_text(encoding="utf-8")
