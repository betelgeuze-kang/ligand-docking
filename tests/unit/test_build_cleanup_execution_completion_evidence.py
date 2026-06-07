from __future__ import annotations

import json
from pathlib import Path

from tools import build_cleanup_execution_completion_evidence as mod


def _approval_gate(tmp_path: Path) -> dict:
    return {
        "summary": {
            "status": "cleanup_execution_operator_approval_gate_ready",
            "authorized_row_count": 5,
        },
        "rows": [
            {
                "lane": "casp17_external_pool",
                "recommended_action": "externalize",
                "path": str(tmp_path / "casp17" / "massivefold_external_pool_intake"),
                "approval_gate_status": "authorized_for_operator_execution",
                "size_gb": 1.0,
            },
            {
                "lane": "legacy_runs_archive",
                "recommended_action": "archive",
                "path": str(tmp_path / "runs" / "archive"),
                "approval_gate_status": "authorized_for_operator_execution",
                "size_gb": 2.0,
            },
            {
                "lane": "build_output",
                "recommended_action": "delete_candidate",
                "path": str(tmp_path / "rust_engine" / "target"),
                "approval_gate_status": "authorized_for_operator_execution",
                "size_gb": 3.0,
            },
            {
                "lane": "local_environment",
                "recommended_action": "delete_candidate",
                "path": str(tmp_path / ".venv"),
                "approval_gate_status": "authorized_for_operator_execution",
                "size_gb": 4.0,
            },
            {
                "lane": "ligand_heavy_cleanup",
                "recommended_action": "delete_stale_stage2_trajectory_payloads_after_approval",
                "path": str(tmp_path / "runs" / "ligand_heavy_cleanup_execution_preflight_current.json"),
                "approval_gate_status": "authorized_for_operator_execution",
                "size_gb": 5.0,
            },
        ],
    }


def _execute_receipt() -> dict:
    return {
        "summary": {
            "status": "cleanup_executed",
            "planned_delete_count": 2,
            "deleted_count": 2,
            "planned_delete_bytes": 12,
            "deleted_bytes": 12,
        }
    }


def test_cleanup_execution_completion_evidence_ready(tmp_path: Path) -> None:
    external_root = tmp_path / "externalized"
    (external_root / "casp17_massivefold_external_pool_intake").mkdir(parents=True)
    (external_root / "runs_archive").mkdir(parents=True)

    payload = mod.build_cleanup_execution_completion_evidence(
        approval_gate_packet=_approval_gate(tmp_path),
        ligand_execute_packet=_execute_receipt(),
        externalized_root=external_root,
    )

    summary = payload["summary"]
    assert summary["status"] == "cleanup_execution_completion_evidence_ready"
    assert summary["transition_cleanup_complete"] is True
    assert summary["ligand_heavy_cleanup_complete"] is True
    assert summary["complete_row_count"] == 5
    assert summary["blocked_row_count"] == 0
    assert summary["authorized_reclaim_size_gb"] == 15.0
    assert all(row["completion_status"] == "complete" for row in payload["rows"])


def test_cleanup_execution_completion_evidence_blocks_missing_destination(tmp_path: Path) -> None:
    payload = mod.build_cleanup_execution_completion_evidence(
        approval_gate_packet=_approval_gate(tmp_path),
        ligand_execute_packet=_execute_receipt(),
        externalized_root=tmp_path / "externalized",
    )

    assert payload["summary"]["status"] == "blocked_cleanup_execution_completion_evidence"
    assert "externalized_destination_missing" in payload["summary"]["blockers"]
    assert payload["summary"]["transition_cleanup_complete"] is False


def test_cleanup_execution_completion_evidence_tool_writes_outputs(tmp_path: Path) -> None:
    external_root = tmp_path / "externalized"
    (external_root / "casp17_massivefold_external_pool_intake").mkdir(parents=True)
    (external_root / "runs_archive").mkdir(parents=True)
    approval_json = tmp_path / "approval.json"
    execute_json = tmp_path / "execute.json"
    out_json = tmp_path / "evidence.json"
    out_csv = tmp_path / "evidence.csv"
    out_md = tmp_path / "evidence.md"
    approval_json.write_text(json.dumps(_approval_gate(tmp_path)) + "\n", encoding="utf-8")
    execute_json.write_text(json.dumps(_execute_receipt()) + "\n", encoding="utf-8")

    mod.main(
        [
            "--approval-gate-json",
            str(approval_json),
            "--ligand-execute-json",
            str(execute_json),
            "--externalized-root",
            str(external_root),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "cleanup_execution_completion_evidence_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("lane,recommended_action,")
    assert "Cleanup Execution Completion Evidence" in out_md.read_text(encoding="utf-8")
