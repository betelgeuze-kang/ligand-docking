from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tools.gpcr_replay import build_gpcr_broad_claim_review_receipt as mod

ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_receipt(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=mod.REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _row(review_id: str, evidence_artifact: Path, evidence_status: str, provenance_kind: str) -> dict[str, str]:
    return {
        "review_id": review_id,
        "evidence_artifact": str(evidence_artifact),
        "evidence_status": evidence_status,
        "claim_ready": "true",
        "reviewer": "reviewer@example.test",
        "reviewed_at_utc": "2026-06-14T00:00:00Z",
        "provenance_kind": provenance_kind,
        "license_ok": "true",
        "external_engine_calls": "0",
        "approval_token": mod.APPROVAL_TOKEN,
        "operator_attestation": "reviewed_for_broad_gpcr_claim",
        "notes": "reviewed local evidence",
    }


def test_placeholder_receipt_blocks_broad_claim_review(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.csv"
    _write_receipt(
        receipt,
        [
            {
                "review_id": "target_heldout_broad_scope_review_not_approved",
                "evidence_artifact": "OPERATOR_FILL_LOCAL_TARGET_HELDOUT_BROAD_CLAIM_REVIEW_JSON",
                "evidence_status": "gpcr_target_heldout_broad_claim_review_ready",
                "claim_ready": "OPERATOR_CONFIRM_TRUE",
                "reviewer": "OPERATOR_FILL_REVIEWER",
                "reviewed_at_utc": "OPERATOR_FILL_REVIEWED_AT_UTC",
                "provenance_kind": "target_heldout_public_benchmark_review",
                "license_ok": "OPERATOR_CONFIRM_LICENSE_OK",
                "external_engine_calls": "0",
                "approval_token": "OPERATOR_FILL_APPROVAL_TOKEN",
                "operator_attestation": "OPERATOR_FILL_OPERATOR_ATTESTATION",
                "notes": "OPERATOR_FILL_NOTES",
            },
            {
                "review_id": "scorer_router_promotion_gate_not_approved",
                "evidence_artifact": "OPERATOR_FILL_LOCAL_SCORER_ROUTER_PROMOTION_GATE_JSON",
                "evidence_status": "gpcr_scorer_router_promotion_gate_ready",
                "claim_ready": "OPERATOR_CONFIRM_TRUE",
                "reviewer": "OPERATOR_FILL_REVIEWER",
                "reviewed_at_utc": "OPERATOR_FILL_REVIEWED_AT_UTC",
                "provenance_kind": "scorer_router_promotion_gate",
                "license_ok": "OPERATOR_CONFIRM_LICENSE_OK",
                "external_engine_calls": "0",
                "approval_token": "OPERATOR_FILL_APPROVAL_TOKEN",
                "operator_attestation": "OPERATOR_FILL_OPERATOR_ATTESTATION",
                "notes": "OPERATOR_FILL_NOTES",
            },
        ],
    )

    payload = mod.build_gpcr_broad_claim_review_receipt(receipt_csv=receipt, root=tmp_path)
    summary = payload["summary"]

    assert summary["status"] == "blocked_gpcr_broad_claim_review_receipt"
    assert summary["receipt_row_count"] == 2
    assert summary["blocked_row_count"] == 2
    assert summary["pass_row_count"] == 0
    assert summary["operator_review_surface_ready_count"] == 2
    assert summary["operator_review_surface_blocked_count"] == 0
    assert summary["evidence_artifact_present_count"] == 0
    assert summary["evidence_status_contract_present_count"] == 2
    assert summary["expected_true_fields_present_count"] == 2
    assert summary["external_engine_calls_zero_count"] == 2
    assert summary["receipt_manual_field_pending_count"] == 16
    assert summary["receipt_evidence_artifact_pending_count"] == 2
    assert summary["receipt_claim_ready_pending_count"] == 2
    assert summary["receipt_reviewer_pending_count"] == 2
    assert summary["receipt_reviewed_at_utc_pending_count"] == 2
    assert summary["receipt_license_ok_pending_count"] == 2
    assert summary["receipt_approval_token_pending_count"] == 2
    assert summary["receipt_operator_attestation_pending_count"] == 2
    assert summary["receipt_notes_pending_count"] == 2
    assert summary["target_heldout_broad_scope_review_approved"] is False
    assert summary["scorer_router_promotion_gate_approved"] is False
    assert summary["blockers"] == ["blocked_receipt_rows_present"]
    assert summary["first_blocked_review_id"] == "target_heldout_broad_scope_review_not_approved"


def test_review_receipt_passes_with_local_evidence_json(tmp_path: Path) -> None:
    target_evidence = tmp_path / "target_review.json"
    scorer_evidence = tmp_path / "scorer_gate.json"
    receipt = tmp_path / "receipt.csv"
    _write_json(
        target_evidence,
        {
            "summary": {
                "status": "gpcr_target_heldout_broad_claim_review_ready",
                "target_heldout_broad_scope_review_approved": True,
            }
        },
    )
    _write_json(
        scorer_evidence,
        {
            "summary": {
                "status": "gpcr_scorer_router_promotion_gate_ready",
                "scorer_router_promotion_gate_ready": True,
                "active_scorer_apply_allowed": True,
                "router_claim_allowed": True,
                "platform_claim_allowed": True,
            }
        },
    )
    _write_receipt(
        receipt,
        [
            _row(
                "target_heldout_broad_scope_review_not_approved",
                target_evidence,
                "gpcr_target_heldout_broad_claim_review_ready",
                "target_heldout_public_benchmark_review",
            ),
            _row(
                "scorer_router_promotion_gate_not_approved",
                scorer_evidence,
                "gpcr_scorer_router_promotion_gate_ready",
                "scorer_router_promotion_gate",
            ),
        ],
    )

    payload = mod.build_gpcr_broad_claim_review_receipt(receipt_csv=receipt, root=tmp_path)
    summary = payload["summary"]

    assert summary["status"] == "gpcr_broad_claim_review_receipt_ready"
    assert summary["broad_claim_review_receipt_ready"] is True
    assert summary["pass_row_count"] == 2
    assert summary["blocked_row_count"] == 0
    assert summary["operator_review_surface_ready_count"] == 2
    assert summary["operator_review_surface_blocked_count"] == 0
    assert summary["evidence_artifact_present_count"] == 2
    assert summary["evidence_status_contract_present_count"] == 2
    assert summary["expected_true_fields_present_count"] == 2
    assert summary["external_engine_calls_zero_count"] == 2
    assert summary["receipt_manual_field_pending_count"] == 0
    assert summary["target_heldout_broad_scope_review_approved"] is True
    assert summary["scorer_router_promotion_gate_approved"] is True


def test_cli_writes_receipt_outputs(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.csv"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"
    _write_receipt(
        receipt,
        [
            {
                column: "OPERATOR_FILL"
                for column in mod.REQUIRED_COLUMNS
            }
        ],
    )

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/gpcr_replay/build_gpcr_broad_claim_review_receipt.py"),
            "--receipt-csv",
            str(receipt),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
            "--root",
            str(tmp_path),
        ],
        check=True,
        cwd=ROOT,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "blocked_gpcr_broad_claim_review_receipt"
    assert out_csv.exists()
    assert "GPCR Broad Claim Review Receipt" in out_md.read_text(encoding="utf-8")
