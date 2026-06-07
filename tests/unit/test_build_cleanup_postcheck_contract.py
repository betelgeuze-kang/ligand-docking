from __future__ import annotations

import json
from pathlib import Path

from tools import build_cleanup_postcheck_contract as mod
from tools import build_cleanup_payload_manifest_lock as lock_mod


def _dossier() -> dict:
    return {
        "summary": {
            "status": "cleanup_execution_approval_dossier_ready",
            "approval_reclaim_size_gb": 39.01,
            "protected_payload_size_gb": 100.0,
        },
        "rows": [
            {
                "lane": "casp17_external_pool",
                "operation_class": "transition_cleanup",
                "recommended_action": "externalize",
                "path": "casp17/massivefold_external_pool_intake",
                "approval_status": "approval_required",
                "approval_token_required": "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS",
                "size_gb": 32.36,
                "candidate_count": 1,
                "snapshot_fingerprint_sha256": "abc",
            },
            {
                "lane": "ligand_heavy_cleanup",
                "operation_class": "ligand_heavy_stale_payload_delete",
                "recommended_action": "delete_stale_stage2_trajectory_payloads_after_approval",
                "path": "runs/ligand_heavy_cleanup_execution_preflight_current.json",
                "approval_status": "approval_required",
                "approval_token_required": "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS",
                "size_gb": 6.65,
                "candidate_count": 40,
            },
            {
                "lane": "protected_cleanup",
                "operation_class": "protected_not_promoted",
                "recommended_action": "keep_protected_until_explicit_policy_change",
                "path": "/mnt/heavy/protected",
                "approval_status": "policy_blocked_not_promoted",
                "size_gb": 100.0,
                "candidate_count": 1,
            },
        ],
    }


def _payload_lock() -> dict:
    return lock_mod.build_cleanup_payload_manifest_lock(dossier_packet=_dossier())


def test_cleanup_postcheck_contract_maps_approval_rows_to_postchecks() -> None:
    payload = mod.build_cleanup_postcheck_contract(
        dossier_packet=_dossier(),
        payload_lock_packet=_payload_lock(),
        approval_gate_packet={"summary": {"status": "blocked_cleanup_execution_operator_approval_gate"}},
        protected_policy_packet={"summary": {"status": "blocked_protected_cleanup_policy_decision_gate"}},
    )

    summary = payload["summary"]
    assert summary["status"] == "cleanup_postcheck_contract_ready"
    assert summary["postcheck_contract_ready"] is True
    assert summary["approval_row_count"] == 2
    assert summary["protected_policy_row_count"] == 1
    assert summary["blocked_row_count"] == 0
    assert summary["approval_reclaim_size_gb"] == 39.01
    assert summary["protected_payload_size_gb"] == 100.0
    assert summary["delete_executed"] is False
    assert summary["archive_executed"] is False
    assert summary["externalize_executed"] is False
    assert summary["external_state_mutated"] is False
    by_lane = {row["lane"]: row for row in payload["rows"]}
    assert "externalized payload listing" in by_lane["casp17_external_pool"]["required_postcheck"]
    assert "ligand-heavy dry-run" in by_lane["ligand_heavy_cleanup"]["required_postcheck"]
    assert by_lane["protected_cleanup"]["postcheck_status"] == "ready"


def test_cleanup_postcheck_contract_blocks_missing_payload_lock() -> None:
    payload = mod.build_cleanup_postcheck_contract(
        dossier_packet=_dossier(),
        payload_lock_packet={},
        approval_gate_packet={},
        protected_policy_packet={"summary": {"status": "blocked_protected_cleanup_policy_decision_gate"}},
    )

    assert payload["summary"]["status"] == "blocked_cleanup_postcheck_contract"
    assert payload["summary"]["postcheck_contract_ready"] is False
    assert "cleanup_payload_manifest_lock_not_ready" in payload["summary"]["blockers"]


def test_cleanup_postcheck_contract_tool_writes_outputs(tmp_path: Path) -> None:
    dossier = tmp_path / "dossier.json"
    payload_lock = tmp_path / "payload_lock.json"
    approval = tmp_path / "approval.json"
    protected = tmp_path / "protected.json"
    dossier.write_text(json.dumps(_dossier()) + "\n", encoding="utf-8")
    payload_lock.write_text(json.dumps(_payload_lock()) + "\n", encoding="utf-8")
    approval.write_text(json.dumps({"summary": {"status": "blocked_cleanup_execution_operator_approval_gate"}}) + "\n", encoding="utf-8")
    protected.write_text(json.dumps({"summary": {"status": "blocked_protected_cleanup_policy_decision_gate"}}) + "\n", encoding="utf-8")
    out_json = tmp_path / "postcheck.json"
    out_csv = tmp_path / "postcheck.csv"
    out_md = tmp_path / "postcheck.md"

    mod.main(
        [
            "--dossier-json",
            str(dossier),
            "--payload-lock-json",
            str(payload_lock),
            "--approval-gate-json",
            str(approval),
            "--protected-policy-json",
            str(protected),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "cleanup_postcheck_contract_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("lane,operation_class,")
    assert "Cleanup Postcheck Contract" in out_md.read_text(encoding="utf-8")
