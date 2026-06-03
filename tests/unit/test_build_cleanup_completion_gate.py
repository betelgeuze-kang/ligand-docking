from __future__ import annotations

import json
from pathlib import Path

from tools import build_cleanup_completion_gate as mod


def _approval_gate(ready: bool = False) -> dict:
    return {
        "summary": {
            "status": "cleanup_execution_operator_approval_gate_ready" if ready else "blocked_cleanup_execution_operator_approval_gate",
            "authorized_row_count": 5 if ready else 0,
            "awaiting_operator_approval_row_count": 0 if ready else 5,
            "blocked_row_count": 0 if ready else 5,
            "authorized_reclaim_size_gb": 49.216 if ready else 0,
            "total_reclaim_size_gb": 49.216,
            "protected_payload_size_gb": 396.794,
        }
    }


def _transition(complete: bool = False) -> dict:
    return {
        "summary": {
            "status": "transition_cleanup_execution_complete" if complete else "transition_cleanup_execution_preflight_ready",
            "external_state_mutated": complete,
            "approval_gated_reclaim_size_gb": 43.206,
        }
    }


def _postcheck(ready: bool = True) -> dict:
    return {
        "summary": {
            "status": "cleanup_postcheck_contract_ready" if ready else "blocked_cleanup_postcheck_contract",
            "postcheck_contract_ready": ready,
            "row_count": 7 if ready else 0,
            "blocked_row_count": 0 if ready else 2,
            "global_refresh_command_count": 9 if ready else 0,
        }
    }


def _ligand(complete: bool = False) -> dict:
    return {
        "summary": {
            "status": "ligand_heavy_cleanup_execution_complete" if complete else "ligand_heavy_cleanup_execution_preflight_ready",
            "delete_executed": complete,
            "candidate_size_gb": 6.011,
        }
    }


def _protected_policy(ready: bool = False) -> dict:
    return {
        "summary": {
            "status": "protected_cleanup_policy_decision_gate_ready" if ready else "blocked_protected_cleanup_policy_decision_gate",
            "policy_resolved": ready,
            "awaiting_policy_decision_row_count": 0 if ready else 2,
            "blocked_row_count": 0 if ready else 2,
            "policy_change_requested_row_count": 0,
            "protected_payload_size_gb": 396.794,
        }
    }


def _completion_evidence(ready: bool = True) -> dict:
    return {
        "summary": {
            "status": "cleanup_execution_completion_evidence_ready" if ready else "blocked_cleanup_execution_completion_evidence",
            "completion_evidence_ready": ready,
            "blocked_row_count": 0 if ready else 2,
            "transition_cleanup_complete": ready,
            "ligand_heavy_cleanup_complete": ready,
            "ligand_deleted_count": 40 if ready else 0,
            "ligand_deleted_bytes": 6453908480 if ready else 0,
            "external_state_mutated": ready,
        }
    }


def test_cleanup_completion_gate_blocks_current_pre_execution_state() -> None:
    payload = mod.build_cleanup_completion_gate(
        approval_gate_packet=_approval_gate(False),
        postcheck_contract_packet=_postcheck(True),
        transition_cleanup_packet=_transition(False),
        ligand_cleanup_packet=_ligand(False),
        protected_policy_gate_packet=_protected_policy(False),
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_cleanup_completion_gate"
    assert summary["cleanup_complete"] is False
    assert summary["stage_count"] == 5
    assert summary["blocked_stage_count"] == 4
    assert summary["approval_ready"] is False
    assert summary["approval_authorized_row_count"] == 0
    assert summary["approval_awaiting_operator_approval_row_count"] == 5
    assert summary["approval_blocked_row_count"] == 5
    assert summary["postcheck_contract_ready"] is True
    assert summary["postcheck_row_count"] == 7
    assert summary["postcheck_blocked_row_count"] == 0
    assert summary["postcheck_global_refresh_command_count"] == 9
    assert summary["transition_cleanup_complete"] is False
    assert summary["transition_approval_gated_reclaim_size_gb"] == 43.206
    assert summary["ligand_heavy_cleanup_complete"] is False
    assert summary["ligand_heavy_candidate_size_gb"] == 6.011
    assert summary["protected_policy_resolved"] is False
    assert summary["delete_executed"] is False
    assert summary["external_state_mutated"] is False


def test_cleanup_completion_gate_uses_execution_completion_evidence() -> None:
    payload = mod.build_cleanup_completion_gate(
        approval_gate_packet=_approval_gate(True),
        postcheck_contract_packet=_postcheck(True),
        transition_cleanup_packet=_transition(False),
        ligand_cleanup_packet=_ligand(False),
        protected_policy_gate_packet=_protected_policy(True),
        completion_evidence_packet=_completion_evidence(True),
    )

    summary = payload["summary"]
    assert summary["status"] == "cleanup_completion_gate_ready"
    assert summary["cleanup_complete"] is True
    assert summary["completion_evidence_ready"] is True
    assert summary["transition_cleanup_complete"] is True
    assert summary["ligand_heavy_cleanup_complete"] is True
    assert summary["blocked_stage_count"] == 0


def test_cleanup_completion_gate_ready_when_all_cleanup_evidence_is_complete() -> None:
    payload = mod.build_cleanup_completion_gate(
        approval_gate_packet=_approval_gate(True),
        postcheck_contract_packet=_postcheck(True),
        transition_cleanup_packet=_transition(True),
        ligand_cleanup_packet=_ligand(True),
        protected_policy_gate_packet=_protected_policy(True),
    )

    assert payload["summary"]["status"] == "cleanup_completion_gate_ready"
    assert payload["summary"]["cleanup_complete"] is True
    assert payload["summary"]["blocked_stage_count"] == 0
    assert all(row["status"] == "ready" for row in payload["rows"])


def test_cleanup_completion_gate_blocks_when_postcheck_contract_is_not_ready() -> None:
    payload = mod.build_cleanup_completion_gate(
        approval_gate_packet=_approval_gate(True),
        postcheck_contract_packet=_postcheck(False),
        transition_cleanup_packet=_transition(True),
        ligand_cleanup_packet=_ligand(True),
        protected_policy_gate_packet=_protected_policy(True),
    )

    assert payload["summary"]["status"] == "blocked_cleanup_completion_gate"
    assert payload["summary"]["cleanup_complete"] is False
    assert payload["summary"]["postcheck_contract_ready"] is False
    assert payload["summary"]["blocked_stage_count"] == 1
    assert any(row["stage"] == "cleanup_postcheck_contract" and row["status"] == "blocked" for row in payload["rows"])


def test_cleanup_completion_gate_tool_writes_outputs(tmp_path: Path) -> None:
    approval_json = tmp_path / "approval.json"
    postcheck_json = tmp_path / "postcheck.json"
    transition_json = tmp_path / "transition.json"
    ligand_json = tmp_path / "ligand.json"
    protected_json = tmp_path / "protected.json"
    out_json = tmp_path / "completion.json"
    out_csv = tmp_path / "completion.csv"
    out_md = tmp_path / "completion.md"
    approval_json.write_text(json.dumps(_approval_gate(False)) + "\n", encoding="utf-8")
    postcheck_json.write_text(json.dumps(_postcheck(True)) + "\n", encoding="utf-8")
    transition_json.write_text(json.dumps(_transition(False)) + "\n", encoding="utf-8")
    ligand_json.write_text(json.dumps(_ligand(False)) + "\n", encoding="utf-8")
    protected_json.write_text(json.dumps(_protected_policy(False)) + "\n", encoding="utf-8")

    mod.main(
        [
            "--approval-gate-json",
            str(approval_json),
            "--postcheck-contract-json",
            str(postcheck_json),
            "--transition-cleanup-json",
            str(transition_json),
            "--ligand-cleanup-json",
            str(ligand_json),
            "--protected-policy-gate-json",
            str(protected_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "blocked_cleanup_completion_gate"
    assert out_csv.read_text(encoding="utf-8").startswith("stage,status,")
    assert "Cleanup Completion Gate" in out_md.read_text(encoding="utf-8")
