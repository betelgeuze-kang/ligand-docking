from __future__ import annotations

import json
from pathlib import Path

from tools import build_cleanup_execution_approval_dossier as mod


def _transition_preflight() -> dict:
    return {
        "summary": {"status": "transition_cleanup_execution_preflight_ready"},
        "rows": [
            {
                "lane": "casp17_external_pool",
                "recommended_action": "externalize",
                "path": "casp17/pool",
                "work_order_status": "approval_gated",
                "preflight_status": "pass",
                "approval_token": "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS",
                "size_gb": 32.36,
            },
            {
                "lane": "build_output",
                "recommended_action": "delete_candidate",
                "path": "rust_engine/target",
                "work_order_status": "approval_gated",
                "preflight_status": "pass",
                "approval_token": "APPROVE_DELETE_REGENERABLE_LOCAL_ARTIFACTS",
                "size_gb": 0.639,
            },
            {
                "lane": "legacy_trajectory_frames",
                "recommended_action": "review_for_stage2_traj_frames",
                "path": "runs/example/stage2_traj_frames",
                "work_order_status": "review_only",
                "preflight_status": "pass",
                "size_gb": 1.0,
            },
        ],
    }


def _snapshot_preflight(snapshot_present: bool = True) -> dict:
    return {
        "summary": {"status": "cleanup_snapshot_preflight_ready"},
        "rows": [
            {
                "lane": "casp17_external_pool",
                "recommended_action": "externalize",
                "path": "casp17/pool",
                "snapshot_required": True,
                "snapshot_present": snapshot_present,
                "snapshot_artifact": "runs/cleanup_snapshots/casp17.snapshot.json",
                "postcheck": "listing present",
            },
            {
                "lane": "build_output",
                "recommended_action": "delete_candidate",
                "path": "rust_engine/target",
                "snapshot_required": False,
                "snapshot_present": False,
                "postcheck": "compile passes",
            },
        ],
    }


def _snapshot_artifacts(status: str = "cleanup_snapshot_artifact_ready") -> dict:
    return {
        "summary": {
            "status": "cleanup_snapshot_artifacts_ready",
            "snapshot_artifact_count": 1,
            "snapshot_ready_count": 1 if status == "cleanup_snapshot_artifact_ready" else 0,
            "listing_truncated_count": 0,
            "total_entry_count": 12,
            "total_file_count": 10,
            "snapshot_set_fingerprint_sha256": "b" * 64,
        },
        "rows": [
            {
                "lane": "casp17_external_pool",
                "recommended_action": "externalize",
                "path": "casp17/pool",
                "snapshot_status": status,
                "snapshot_artifact": "runs/cleanup_snapshots/casp17.snapshot.json",
                "metadata_fingerprint_sha256": "a" * 64,
                "entry_count": 12,
                "file_count": 10,
                "listing_truncated": False,
            }
        ],
    }


def _ligand_preflight() -> dict:
    return {
        "summary": {
            "status": "ligand_heavy_cleanup_execution_preflight_ready",
            "approval_token_required": "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS",
            "existing_candidate_count": 40,
            "candidate_size_gb": 6.011,
        }
    }


def _protected_review() -> dict:
    return {
        "summary": {"status": "protected_cleanup_payload_review_ready"},
        "rows": [
            {
                "path": "/mnt/ligand_heavy_runs/recent_big",
                "known_payload_count": 1,
                "known_payload_size_gb": 396.794,
                "policy_change_required_for_deletion": True,
            }
        ],
    }


def _protected_policy_change_requested() -> dict:
    return {
        "summary": {
            "status": "blocked_protected_cleanup_policy_decision_gate",
            "policy_change_requested_row_count": 1,
        },
        "rows": [
            {
                "path": "/mnt/ligand_heavy_runs/recent_big",
                "policy_gate_status": "policy_change_requested",
                "operator_policy_decision": "request_policy_change",
            }
        ],
    }


def test_cleanup_execution_approval_dossier_consolidates_ready_cleanup_evidence() -> None:
    payload = mod.build_cleanup_execution_approval_dossier(
        transition_preflight_packet=_transition_preflight(),
        cleanup_snapshot_preflight_packet=_snapshot_preflight(),
        cleanup_snapshot_artifacts_packet=_snapshot_artifacts(),
        ligand_cleanup_preflight_packet=_ligand_preflight(),
        protected_cleanup_review_packet=_protected_review(),
    )

    summary = payload["summary"]
    assert summary["status"] == "cleanup_execution_approval_dossier_ready"
    assert summary["approval_row_count"] == 3
    assert summary["blocked_approval_row_count"] == 0
    assert summary["protected_not_promoted_row_count"] == 1
    assert summary["protected_policy_change_promoted_row_count"] == 0
    assert summary["snapshot_backed_approval_row_count"] == 1
    assert summary["snapshot_artifact_count"] == 1
    assert summary["snapshot_ready_count"] == 1
    assert summary["snapshot_total_entry_count"] == 12
    assert summary["snapshot_total_file_count"] == 10
    assert summary["snapshot_set_fingerprint_sha256"] == "b" * 64
    assert summary["snapshot_fingerprint_count"] == 1
    assert summary["snapshot_truncated_approval_row_count"] == 0
    assert summary["approval_token_count"] == 3
    assert "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS" in summary["approval_tokens_required"]
    assert "APPROVE_DELETE_REGENERABLE_LOCAL_ARTIFACTS" in summary["approval_tokens_required"]
    assert "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS" in summary["approval_tokens_required"]
    assert summary["approval_reclaim_size_gb"] == 39.01
    assert summary["protected_payload_size_gb"] == 396.794
    assert summary["protected_policy_change_promoted_size_gb"] == 0
    assert summary["execution_enabled"] is False
    assert summary["delete_executed"] is False
    assert summary["external_state_mutated"] is False

    casp17 = next(row for row in payload["rows"] if row["lane"] == "casp17_external_pool")
    assert casp17["snapshot_required"] is True
    assert casp17["snapshot_present"] is True
    assert casp17["snapshot_fingerprint_sha256"] == "a" * 64
    assert casp17["snapshot_entry_count"] == 12
    assert casp17["snapshot_file_count"] == 10
    assert casp17["snapshot_listing_truncated"] is False
    protected = next(row for row in payload["rows"] if row["lane"] == "protected_cleanup")
    assert protected["approval_status"] == "policy_blocked_not_promoted"
    assert protected["approval_promoted"] is False
    assert protected["protected_policy_change_required"] is True


def test_cleanup_execution_approval_dossier_promotes_requested_protected_policy_change() -> None:
    payload = mod.build_cleanup_execution_approval_dossier(
        transition_preflight_packet=_transition_preflight(),
        cleanup_snapshot_preflight_packet=_snapshot_preflight(),
        cleanup_snapshot_artifacts_packet=_snapshot_artifacts(),
        ligand_cleanup_preflight_packet=_ligand_preflight(),
        protected_cleanup_review_packet=_protected_review(),
        protected_cleanup_policy_packet=_protected_policy_change_requested(),
    )

    summary = payload["summary"]
    assert summary["status"] == "cleanup_execution_approval_dossier_ready"
    assert summary["approval_row_count"] == 4
    assert summary["protected_not_promoted_row_count"] == 0
    assert summary["protected_policy_change_promoted_row_count"] == 1
    assert summary["approval_reclaim_size_gb"] == 435.804
    assert summary["protected_payload_size_gb"] == 0
    assert summary["protected_policy_change_promoted_size_gb"] == 396.794
    protected = next(row for row in payload["rows"] if row["lane"] == "protected_cleanup")
    assert protected["approval_status"] == "approval_required"
    assert protected["operation_class"] == "protected_ligand_heavy_policy_change_delete"
    assert protected["approval_token_required"] == "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS"
    assert protected["approval_promoted"] is True
    assert protected["delete_executed"] is False


def test_cleanup_execution_approval_dossier_blocks_missing_snapshot_evidence() -> None:
    payload = mod.build_cleanup_execution_approval_dossier(
        transition_preflight_packet=_transition_preflight(),
        cleanup_snapshot_preflight_packet=_snapshot_preflight(snapshot_present=False),
        cleanup_snapshot_artifacts_packet=_snapshot_artifacts(status="blocked_cleanup_snapshot_artifact"),
        ligand_cleanup_preflight_packet=_ligand_preflight(),
        protected_cleanup_review_packet=_protected_review(),
    )

    assert payload["summary"]["status"] == "blocked_cleanup_execution_approval_dossier"
    assert payload["summary"]["blocked_approval_row_count"] == 1
    assert "required_snapshot_missing" in payload["summary"]["blockers"]
    assert "snapshot_artifact_not_ready" in payload["summary"]["blockers"]
    casp17 = next(row for row in payload["rows"] if row["lane"] == "casp17_external_pool")
    assert casp17["approval_status"] == "blocked_before_approval"
    assert casp17["delete_executed"] is False
    assert casp17["external_state_mutated"] is False


def test_cleanup_execution_approval_dossier_tool_writes_outputs(tmp_path: Path) -> None:
    paths = {
        "transition": tmp_path / "transition.json",
        "snapshot_preflight": tmp_path / "snapshot_preflight.json",
        "snapshot_artifacts": tmp_path / "snapshot_artifacts.json",
        "ligand": tmp_path / "ligand.json",
        "protected": tmp_path / "protected.json",
    }
    paths["transition"].write_text(json.dumps(_transition_preflight()) + "\n", encoding="utf-8")
    paths["snapshot_preflight"].write_text(json.dumps(_snapshot_preflight()) + "\n", encoding="utf-8")
    paths["snapshot_artifacts"].write_text(json.dumps(_snapshot_artifacts()) + "\n", encoding="utf-8")
    paths["ligand"].write_text(json.dumps(_ligand_preflight()) + "\n", encoding="utf-8")
    paths["protected"].write_text(json.dumps(_protected_review()) + "\n", encoding="utf-8")
    out_json = tmp_path / "dossier.json"
    out_csv = tmp_path / "dossier.csv"
    out_md = tmp_path / "dossier.md"

    mod.main(
        [
            "--transition-preflight-json",
            str(paths["transition"]),
            "--cleanup-snapshot-preflight-json",
            str(paths["snapshot_preflight"]),
            "--cleanup-snapshot-artifacts-json",
            str(paths["snapshot_artifacts"]),
            "--ligand-cleanup-preflight-json",
            str(paths["ligand"]),
            "--protected-cleanup-review-json",
            str(paths["protected"]),
            "--protected-cleanup-policy-json",
            str(tmp_path / "missing_policy.json"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "cleanup_execution_approval_dossier_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("lane,operation_class,")
    assert "Cleanup Execution Approval Dossier" in out_md.read_text(encoding="utf-8")
