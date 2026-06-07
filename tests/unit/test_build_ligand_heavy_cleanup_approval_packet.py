from __future__ import annotations

import json
from pathlib import Path

from tools import build_ligand_heavy_cleanup_approval_packet as mod


def test_ligand_heavy_cleanup_approval_packet_collects_dry_run_delete_rows(tmp_path: Path) -> None:
    dry_run = {
        "summary": {
            "status": "dry_run",
            "execute": False,
            "planned_delete_count": 2,
            "planned_delete_bytes": 3072,
            "deleted_count": 0,
            "deleted_bytes": 0,
        },
        "rows": [
            {
                "root": "/mnt/a/ligand_heavy_runs",
                "path": "/mnt/a/ligand_heavy_runs/ligand_old/stage2_trajectory_frames",
                "name": "stage2_trajectory_frames",
                "age_days": 30.5,
                "size_bytes": 1024,
                "run_path": "/mnt/a/ligand_heavy_runs/ligand_old",
                "run_name": "ligand_old",
                "status": "dry_run_delete",
                "reason": "would be removed; pass --execute to delete",
            },
            {
                "root": "/mnt/a/ligand_heavy_runs",
                "path": "/mnt/a/ligand_heavy_runs/ligand_new/stage2_trajectory_frames",
                "name": "stage2_trajectory_frames",
                "age_days": 2.0,
                "size_bytes": 2048,
                "run_path": "/mnt/a/ligand_heavy_runs/ligand_new",
                "run_name": "ligand_new",
                "status": "kept_too_recent",
                "reason": "payload mtime is newer than older-than-days",
            },
        ],
    }

    payload = mod.build_approval_packet(dry_run, input_json="dry_run.json")

    summary = payload["summary"]
    assert summary["status"] == "approval_packet_ready"
    assert summary["candidate_count"] == 1
    assert summary["candidate_bytes"] == 1024
    assert summary["approval_token_required"] == "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS"
    assert summary["delete_executed"] is False
    assert summary["external_state_mutated"] is False
    assert payload["rows"][0]["deletion_scope"] == "payload_directory_only"
    assert payload["rows"][0]["parent_run_preserved"] is True


def test_ligand_heavy_cleanup_approval_packet_blocks_executed_source_report() -> None:
    payload = mod.build_approval_packet(
        {
            "summary": {
                "status": "cleanup_executed",
                "execute": True,
                "planned_delete_count": 1,
                "planned_delete_bytes": 1024,
                "deleted_count": 1,
            },
            "rows": [
                {
                    "path": "/mnt/a/ligand_heavy_runs/ligand_old/stage2_trajectory_frames",
                    "name": "stage2_trajectory_frames",
                    "run_name": "ligand_old",
                    "size_bytes": 1024,
                    "status": "dry_run_delete",
                }
            ],
        }
    )

    assert payload["summary"]["status"] == "blocked_approval_packet"
    assert "source_report_was_not_dry_run" in payload["summary"]["blockers"]
    assert "source_report_already_deleted_payloads" in payload["summary"]["blockers"]


def test_ligand_heavy_cleanup_approval_packet_tool_writes_outputs(tmp_path: Path) -> None:
    dry_run_json = tmp_path / "dry_run.json"
    out_json = tmp_path / "packet.json"
    out_csv = tmp_path / "packet.csv"
    out_md = tmp_path / "packet.md"
    dry_run_json.write_text(
        json.dumps(
            {
                "summary": {"status": "dry_run", "execute": False, "planned_delete_count": 1, "planned_delete_bytes": 4096, "deleted_count": 0},
                "rows": [
                    {
                        "path": "/mnt/a/ligand_heavy_runs/run_old/stage2_trajectory_frames",
                        "name": "stage2_trajectory_frames",
                        "run_name": "run_old",
                        "size_bytes": 4096,
                        "status": "dry_run_delete",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    mod.main(["--dry-run-json", str(dry_run_json), "--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "approval_packet_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("root,path,")
    assert "Ligand Heavy Cleanup Approval Packet" in out_md.read_text(encoding="utf-8")
