from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_cleanup_execution_approval_gate as mod
from tools import build_cleanup_payload_manifest_lock as lock_mod


def _dossier() -> dict:
    return {
        "summary": {
            "status": "cleanup_execution_approval_dossier_ready",
            "approval_reclaim_size_gb": 39.01,
            "protected_payload_size_gb": 396.794,
        },
        "rows": [
            {
                "lane": "casp17_external_pool",
                "recommended_action": "externalize",
                "path": "casp17/pool",
                "approval_status": "approval_required",
                "approval_token_required": "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS",
                "size_gb": 32.36,
                "candidate_count": 1,
                "snapshot_fingerprint_sha256": "a" * 64,
            },
            {
                "lane": "build_output",
                "recommended_action": "delete_candidate",
                "path": "rust_engine/target",
                "approval_status": "approval_required",
                "approval_token_required": "APPROVE_DELETE_REGENERABLE_LOCAL_ARTIFACTS",
                "size_gb": 0.639,
                "candidate_count": 1,
            },
            {
                "lane": "protected_cleanup",
                "recommended_action": "keep_protected_until_explicit_policy_change",
                "path": "/mnt/recent_big",
                "approval_status": "policy_blocked_not_promoted",
                "size_gb": 396.794,
                "candidate_count": 1,
            },
        ],
    }


def _approval_row(
    *,
    lane: str,
    action: str,
    path: str,
    decision: str,
    token: str,
    payload_fingerprint: str = "",
) -> dict[str, str]:
    return {
        "lane": lane,
        "recommended_action": action,
        "path": path,
        "payload_fingerprint_sha256": payload_fingerprint,
        "operator_decision": decision,
        "operator_approval_token": token,
    }


def _lock() -> dict:
    return lock_mod.build_cleanup_payload_manifest_lock(dossier_packet=_dossier())


def _fingerprint(lock: dict, lane: str) -> str:
    return next(row["payload_fingerprint_sha256"] for row in lock["rows"] if row["lane"] == lane)


def test_cleanup_execution_approval_gate_blocks_missing_operator_csv() -> None:
    payload = mod.build_cleanup_execution_approval_gate(
        dossier_packet=_dossier(),
        operator_approval_rows=[],
        operator_approval_csv_present=False,
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_cleanup_execution_operator_approval_gate"
    assert summary["operator_approval_csv_present"] is False
    assert summary["awaiting_operator_approval_row_count"] == 2
    assert summary["authorized_row_count"] == 0
    assert "operator_approval_csv_missing" in summary["blockers"]
    assert "operator_decision_missing" in summary["blockers"]
    assert summary["execution_enabled"] is False
    assert summary["delete_executed"] is False
    assert summary["external_state_mutated"] is False


def test_cleanup_execution_approval_gate_authorizes_exact_token_and_skip() -> None:
    payload = mod.build_cleanup_execution_approval_gate(
        dossier_packet=_dossier(),
        operator_approval_rows=[
            _approval_row(
                lane="casp17_external_pool",
                action="externalize",
                path="casp17/pool",
                decision="approve",
                token="APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS",
            ),
            _approval_row(
                lane="build_output",
                action="delete_candidate",
                path="rust_engine/target",
                decision="skip",
                token="",
            ),
        ],
        operator_approval_csv_present=True,
    )

    summary = payload["summary"]
    assert summary["status"] == "cleanup_execution_operator_approval_gate_ready"
    assert summary["authorized_row_count"] == 1
    assert summary["skipped_row_count"] == 1
    assert summary["blocked_row_count"] == 0
    assert summary["authorized_reclaim_size_gb"] == 32.36
    casp17 = next(row for row in payload["rows"] if row["lane"] == "casp17_external_pool")
    assert casp17["approval_gate_status"] == "authorized_for_operator_execution"
    build = next(row for row in payload["rows"] if row["lane"] == "build_output")
    assert build["approval_gate_status"] == "skipped_by_operator"
    protected = next(row for row in payload["rows"] if row["lane"] == "protected_cleanup")
    assert protected["approval_gate_status"] == "policy_blocked_not_promoted"


def test_cleanup_execution_approval_gate_blocks_protected_approval_attempt() -> None:
    payload = mod.build_cleanup_execution_approval_gate(
        dossier_packet=_dossier(),
        operator_approval_rows=[
            _approval_row(
                lane="protected_cleanup",
                action="keep_protected_until_explicit_policy_change",
                path="/mnt/recent_big",
                decision="approve",
                token="APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS",
            )
        ],
        operator_approval_csv_present=True,
    )

    assert payload["summary"]["status"] == "blocked_cleanup_execution_operator_approval_gate"
    assert "protected_row_approval_attempted" in payload["summary"]["blockers"]
    protected = next(row for row in payload["rows"] if row["lane"] == "protected_cleanup")
    assert protected["approval_gate_status"] == "blocked_protected_row_attempted"
    assert protected["delete_executed"] is False
    assert protected["external_state_mutated"] is False


def test_cleanup_execution_approval_gate_requires_payload_fingerprint_when_lock_enabled() -> None:
    lock = _lock()
    payload = mod.build_cleanup_execution_approval_gate(
        dossier_packet=_dossier(),
        payload_lock_packet=lock,
        operator_approval_rows=[
            _approval_row(
                lane="casp17_external_pool",
                action="externalize",
                path="casp17/pool",
                decision="approve",
                token="APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS",
                payload_fingerprint="not-current",
            ),
            _approval_row(
                lane="build_output",
                action="delete_candidate",
                path="rust_engine/target",
                decision="skip",
                token="",
                payload_fingerprint=_fingerprint(lock, "build_output"),
            ),
        ],
        operator_approval_csv_present=True,
        payload_lock_required=True,
    )

    assert payload["summary"]["status"] == "blocked_cleanup_execution_operator_approval_gate"
    assert payload["summary"]["source_payload_lock_status"] == "cleanup_payload_manifest_lock_ready"
    assert payload["summary"]["payload_lock_required"] is True
    assert "operator_payload_fingerprint_mismatch" in payload["summary"]["blockers"]
    casp17 = next(row for row in payload["rows"] if row["lane"] == "casp17_external_pool")
    assert casp17["approval_gate_status"] == "blocked_before_execution"


def test_cleanup_execution_approval_gate_authorizes_with_payload_lock_fingerprint() -> None:
    lock = _lock()
    payload = mod.build_cleanup_execution_approval_gate(
        dossier_packet=_dossier(),
        payload_lock_packet=lock,
        operator_approval_rows=[
            _approval_row(
                lane="casp17_external_pool",
                action="externalize",
                path="casp17/pool",
                decision="approve",
                token="APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS",
                payload_fingerprint=_fingerprint(lock, "casp17_external_pool"),
            ),
            _approval_row(
                lane="build_output",
                action="delete_candidate",
                path="rust_engine/target",
                decision="skip",
                token="",
                payload_fingerprint=_fingerprint(lock, "build_output"),
            ),
        ],
        operator_approval_csv_present=True,
        payload_lock_required=True,
    )

    assert payload["summary"]["status"] == "cleanup_execution_operator_approval_gate_ready"
    assert payload["summary"]["authorized_row_count"] == 1
    assert payload["summary"]["blocked_row_count"] == 0


def test_cleanup_execution_approval_gate_tool_writes_outputs_and_template(tmp_path: Path) -> None:
    dossier_json = tmp_path / "dossier.json"
    payload_lock_json = tmp_path / "lock.json"
    approval_csv = tmp_path / "approval.csv"
    template_csv = tmp_path / "template.csv"
    out_json = tmp_path / "gate.json"
    out_csv = tmp_path / "gate.csv"
    out_md = tmp_path / "gate.md"
    dossier_json.write_text(json.dumps(_dossier()) + "\n", encoding="utf-8")
    lock = _lock()
    payload_lock_json.write_text(json.dumps(lock) + "\n", encoding="utf-8")
    with approval_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "lane",
                "recommended_action",
                "path",
                "payload_fingerprint_sha256",
                "operator_decision",
                "operator_approval_token",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerow(
            _approval_row(
                lane="casp17_external_pool",
                action="externalize",
                path="casp17/pool",
                decision="approve",
                token="APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS",
                payload_fingerprint=_fingerprint(lock, "casp17_external_pool"),
            )
        )
        writer.writerow(
            _approval_row(
                lane="build_output",
                action="delete_candidate",
                path="rust_engine/target",
                decision="skip",
                token="",
                payload_fingerprint=_fingerprint(lock, "build_output"),
            )
        )

    mod.main(
        [
            "--dossier-json",
            str(dossier_json),
            "--payload-lock-json",
            str(payload_lock_json),
            "--operator-approval-csv",
            str(approval_csv),
            "--template-csv",
            str(template_csv),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "cleanup_execution_operator_approval_gate_ready"
    assert template_csv.read_text(encoding="utf-8").startswith("lane,recommended_action,path,payload_fingerprint_sha256,")
    assert out_csv.read_text(encoding="utf-8").startswith("lane,recommended_action,path,")
    assert "Cleanup Execution Operator Approval Gate" in out_md.read_text(encoding="utf-8")
