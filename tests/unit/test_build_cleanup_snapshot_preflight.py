from __future__ import annotations

import json
from pathlib import Path

from tools import build_cleanup_snapshot_preflight as mod


def _transition_work_order() -> dict:
    return {
        "summary": {"status": "transition_cleanup_work_order_ready"},
        "rows": [
            {
                "work_order_status": "approval_gated",
                "lane": "casp17_external_pool",
                "path": "casp17/massivefold_external_pool_intake",
                "recommended_action": "externalize",
                "approval_token": "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS",
                "size_gb": 32.36,
                "postcheck": "snapshot present",
            },
            {
                "work_order_status": "approval_gated",
                "lane": "build_output",
                "path": "rust_engine/target",
                "recommended_action": "delete_candidate",
                "approval_token": "APPROVE_DELETE_REGENERABLE_LOCAL_ARTIFACTS",
                "size_gb": 0.639,
                "postcheck": "compile passes",
            },
            {
                "work_order_status": "review_only",
                "lane": "legacy_trajectory_frames",
                "path": "runs/example/stage2_traj_frames",
                "recommended_action": "review_only",
                "size_gb": 1.0,
            },
        ],
    }


def _ligand_preflight() -> dict:
    return {
        "summary": {
            "status": "ligand_heavy_cleanup_execution_preflight_ready",
            "approval_token_required": "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS",
            "candidate_size_gb": 6.011,
            "existing_candidate_count": 1,
        },
        "rows": [{"path": "/mnt/heavy/run/stage2_trajectory_frames", "preflight_status": "pass"}],
    }


def _ligand_work_order() -> dict:
    return {
        "summary": {
            "status": "cleanup_work_order_ready",
            "approval_token_required": "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS",
            "source_approval_json": "runs/ligand_heavy_cleanup_approval_packet_current.json",
        }
    }


def test_cleanup_snapshot_preflight_blocks_missing_archive_externalize_snapshot(tmp_path: Path) -> None:
    payload = mod.build_cleanup_snapshot_preflight(
        transition_cleanup_work_order_packet=_transition_work_order(),
        ligand_cleanup_preflight_packet=_ligand_preflight(),
        ligand_cleanup_work_order_packet=_ligand_work_order(),
        snapshot_dir=str(tmp_path / "snapshots"),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_cleanup_snapshot_preflight"
    assert summary["row_count"] == 3
    assert summary["snapshot_required_count"] == 1
    assert summary["snapshot_missing_count"] == 1
    assert summary["frozen_manifest_ready_count"] >= 2
    externalize = next(row for row in payload["rows"] if row["recommended_action"] == "externalize")
    assert externalize["preflight_status"] == "blocked"
    assert externalize["blockers"] == "snapshot_artifact_missing"
    delete_candidate = next(row for row in payload["rows"] if row["recommended_action"] == "delete_candidate")
    assert delete_candidate["preflight_status"] == "pass"
    ligand = next(row for row in payload["rows"] if row["lane"] == "ligand_heavy_cleanup")
    assert ligand["frozen_manifest_present"] is True
    assert summary["snapshot_created"] is False
    assert summary["delete_executed"] is False
    assert summary["external_state_mutated"] is False


def test_cleanup_snapshot_preflight_passes_when_required_snapshot_exists(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "snapshots"
    snapshot_path = mod._snapshot_path(
        str(snapshot_dir),
        lane="casp17_external_pool",
        action="externalize",
        path="casp17/massivefold_external_pool_intake",
    )
    Path(snapshot_path).parent.mkdir(parents=True, exist_ok=True)
    Path(snapshot_path).write_text(json.dumps({"listing": []}) + "\n", encoding="utf-8")

    payload = mod.build_cleanup_snapshot_preflight(
        transition_cleanup_work_order_packet=_transition_work_order(),
        ligand_cleanup_preflight_packet=_ligand_preflight(),
        ligand_cleanup_work_order_packet=_ligand_work_order(),
        snapshot_dir=str(snapshot_dir),
    )

    assert payload["summary"]["status"] == "cleanup_snapshot_preflight_ready"
    assert payload["summary"]["snapshot_missing_count"] == 0


def test_cleanup_snapshot_preflight_tool_writes_outputs(tmp_path: Path) -> None:
    transition_json = tmp_path / "transition.json"
    ligand_preflight_json = tmp_path / "ligand_preflight.json"
    ligand_work_order_json = tmp_path / "ligand_work_order.json"
    out_json = tmp_path / "snapshot.json"
    out_csv = tmp_path / "snapshot.csv"
    out_md = tmp_path / "snapshot.md"
    transition_json.write_text(json.dumps(_transition_work_order()) + "\n", encoding="utf-8")
    ligand_preflight_json.write_text(json.dumps(_ligand_preflight()) + "\n", encoding="utf-8")
    ligand_work_order_json.write_text(json.dumps(_ligand_work_order()) + "\n", encoding="utf-8")

    mod.main(
        [
            "--transition-cleanup-work-order-json",
            str(transition_json),
            "--ligand-cleanup-preflight-json",
            str(ligand_preflight_json),
            "--ligand-cleanup-work-order-json",
            str(ligand_work_order_json),
            "--snapshot-dir",
            str(tmp_path / "snapshots"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "blocked_cleanup_snapshot_preflight"
    assert out_csv.read_text(encoding="utf-8").startswith("source_artifact,lane,")
    assert "Cleanup Snapshot Preflight" in out_md.read_text(encoding="utf-8")
