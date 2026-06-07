from __future__ import annotations

import json
from pathlib import Path

from tools import build_cleanup_payload_manifest_lock as mod


def _dossier(snapshot_fingerprint: str = "a" * 64) -> dict:
    return {
        "summary": {"status": "cleanup_execution_approval_dossier_ready"},
        "rows": [
            {
                "lane": "casp17_external_pool",
                "operation_class": "transition_cleanup",
                "recommended_action": "externalize",
                "path": "casp17/pool",
                "approval_status": "approval_required",
                "approval_token_required": "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS",
                "size_gb": 32.36,
                "candidate_count": 1,
                "preflight_status": "pass",
                "snapshot_required": True,
                "snapshot_present": True,
                "snapshot_artifact": "runs/cleanup_snapshots/casp17.snapshot.json",
                "snapshot_fingerprint_sha256": snapshot_fingerprint,
                "postcheck": "listing present",
                "approval_promoted": True,
            },
            {
                "lane": "protected_cleanup",
                "operation_class": "protected_not_promoted",
                "recommended_action": "keep_protected_until_explicit_policy_change",
                "path": "/mnt/recent_big",
                "approval_status": "policy_blocked_not_promoted",
                "size_gb": 396.794,
                "candidate_count": 1,
                "protected_policy_change_required": True,
                "approval_promoted": False,
            },
        ],
    }


def test_cleanup_payload_manifest_lock_fingerprints_ready_dossier() -> None:
    payload = mod.build_cleanup_payload_manifest_lock(dossier_packet=_dossier())

    summary = payload["summary"]
    assert summary["status"] == "cleanup_payload_manifest_lock_ready"
    assert summary["row_count"] == 2
    assert summary["approval_row_count"] == 1
    assert summary["protected_not_promoted_row_count"] == 1
    assert summary["blocked_row_count"] == 0
    assert len(summary["payload_manifest_fingerprint_sha256"]) == 64
    casp17 = next(row for row in payload["rows"] if row["lane"] == "casp17_external_pool")
    assert casp17["lock_status"] == "locked"
    assert len(casp17["payload_fingerprint_sha256"]) == 64
    assert summary["delete_executed"] is False
    assert summary["external_state_mutated"] is False


def test_cleanup_payload_manifest_lock_blocks_missing_required_snapshot_fingerprint() -> None:
    payload = mod.build_cleanup_payload_manifest_lock(dossier_packet=_dossier(snapshot_fingerprint=""))

    assert payload["summary"]["status"] == "blocked_cleanup_payload_manifest_lock"
    assert "required_snapshot_fingerprint_missing" in payload["summary"]["blockers"]
    casp17 = next(row for row in payload["rows"] if row["lane"] == "casp17_external_pool")
    assert casp17["lock_status"] == "blocked"


def test_cleanup_payload_manifest_lock_tool_writes_outputs(tmp_path: Path) -> None:
    dossier_json = tmp_path / "dossier.json"
    out_json = tmp_path / "lock.json"
    out_csv = tmp_path / "lock.csv"
    out_md = tmp_path / "lock.md"
    dossier_json.write_text(json.dumps(_dossier()) + "\n", encoding="utf-8")

    mod.main(
        [
            "--dossier-json",
            str(dossier_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "cleanup_payload_manifest_lock_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("lane,operation_class,")
    assert "Cleanup Payload Manifest Lock" in out_md.read_text(encoding="utf-8")
