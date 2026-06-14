from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_product_scope_breadth_evidence_operator_staging_apply as mod
from tools.product.build_product_scope_breadth_evidence_receipt import (
    APPROVAL_TOKEN,
    EXPECTED_EVIDENCE,
    REQUIRED_COLUMNS,
    REQUIRED_SCOPE_BLOCKERS,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in REQUIRED_COLUMNS})


def _receipt_rows(*, filled: bool = False) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for scope_blocker_id in REQUIRED_SCOPE_BLOCKERS:
        expected = EXPECTED_EVIDENCE[scope_blocker_id]
        row = {
            "scope_blocker_id": scope_blocker_id,
            "evidence_artifact": "OPERATOR_FILL_LOCAL_EVIDENCE_JSON",
            "evidence_status": str(expected["status"]),
            "claim_ready": "OPERATOR_CONFIRM_TRUE",
            "reviewer": "OPERATOR_FILL_REVIEWER",
            "reviewed_at_utc": "OPERATOR_FILL_REVIEWED_AT_UTC",
            "provenance_kind": "operator_curated_public",
            "license_ok": "OPERATOR_CONFIRM_TRUE",
            "external_state_mutated": "false",
            "approval_token": "OPERATOR_FILL_APPROVAL_TOKEN",
            "operator_attestation": "reviewed_for_scope_promotion",
            "notes": "pending",
        }
        if filled:
            row.update(
                {
                    "evidence_artifact": f"runs/evidence/{scope_blocker_id}.json",
                    "claim_ready": "true",
                    "reviewer": "operator",
                    "reviewed_at_utc": "2026-06-13T00:00:00Z",
                    "license_ok": "true",
                    "approval_token": APPROVAL_TOKEN,
                }
            )
        rows.append(row)
    return rows


def _write_evidence_packets(root: Path) -> None:
    for scope_blocker_id, expected in EXPECTED_EVIDENCE.items():
        summary = {"status": expected["status"]}
        for field in expected["true_fields"]:
            summary[str(field)] = True
        for field in expected.get("quality_true_fields", []):
            summary[str(field)] = True
        for field, minimum in (expected.get("int_min_fields") or {}).items():
            summary[str(field)] = minimum
        for field in expected.get("false_fields", []):
            summary[str(field)] = False
        _write_json(root / f"runs/evidence/{scope_blocker_id}.json", {"summary": summary})


def _write_scope_checklist(root: Path) -> None:
    _write_json(
        root / mod.DEFAULT_SCOPE_CHECKLIST_JSON,
        {
            "summary": {
                "status": "blocked_product_scope_breadth_closure_checklist",
                "scope_breadth_ready": False,
                "blocker_classes": list(REQUIRED_SCOPE_BLOCKERS),
                "manual_review_subcheck_count": 39,
            }
        },
    )


def _write_field_worksheet(root: Path, *, pending_field_count: int = 36) -> None:
    _write_json(
        root / mod.DEFAULT_FIELD_WORKSHEET_JSON,
        {
            "summary": {
                "status": "product_scope_breadth_evidence_operator_field_worksheet_ready",
                "operator_fill_pending_field_count": pending_field_count,
                "top_blocker_id": "direct_binding_evidence_missing",
                "top_item_id": "AQP1.core_binder_01",
                "top_bucket": "local_crosscheck_review_present_but_exact_quant_required",
            }
        },
    )


def test_scope_breadth_operator_staging_apply_blocks_placeholder_receipt(
    tmp_path: Path,
) -> None:
    _write_csv(tmp_path / mod.DEFAULT_STAGING_RECEIPT_CSV, _receipt_rows(filled=False))
    _write_scope_checklist(tmp_path)
    _write_field_worksheet(tmp_path, pending_field_count=36)

    payload = mod.build_product_scope_breadth_evidence_operator_staging_apply(root=tmp_path)
    summary = payload["summary"]

    assert summary["status"] == "blocked_product_scope_breadth_evidence_operator_staging_apply"
    assert summary["candidate_receipt_ready"] is False
    assert summary["candidate_receipt_status"] == "blocked_product_scope_breadth_evidence_receipt"
    assert summary["candidate_pass_row_count"] == 0
    assert summary["candidate_blocked_row_count"] == 6
    assert summary["staging_placeholder_row_count"] == 6
    assert summary["candidate_first_blocked_scope_blocker_id"] == "direct_binding_evidence_missing"
    assert summary["candidate_most_common_row_blocker"] == "operator_placeholders_unfilled"
    assert summary["field_worksheet_pending_field_count"] == 36
    assert summary["live_copy_allowed"] is False
    assert summary["canonical_receipt_written"] is False
    assert summary["claim_promoted"] is False
    assert summary["external_state_mutated"] is False
    assert "candidate_receipt_not_ready" in summary["blockers"]


def test_scope_breadth_operator_staging_apply_writes_candidate_when_receipt_passes(
    tmp_path: Path,
) -> None:
    _write_csv(tmp_path / mod.DEFAULT_STAGING_RECEIPT_CSV, _receipt_rows(filled=True))
    _write_evidence_packets(tmp_path)
    _write_scope_checklist(tmp_path)
    _write_field_worksheet(tmp_path, pending_field_count=0)

    payload = mod.build_product_scope_breadth_evidence_operator_staging_apply(root=tmp_path)
    summary = payload["summary"]

    assert summary["status"] == "product_scope_breadth_evidence_operator_staging_preview_ready"
    assert summary["candidate_receipt_ready"] is True
    assert summary["candidate_pass_row_count"] == 6
    assert summary["candidate_blocked_row_count"] == 0
    assert summary["candidate_receipt_written"] is True
    assert summary["live_copy_allowed"] is False
    assert summary["canonical_receipt_written"] is False
    assert (tmp_path / mod.DEFAULT_CANDIDATE_RECEIPT_CSV).is_file()


def test_scope_breadth_operator_staging_apply_live_copy_requires_approval_token(
    tmp_path: Path,
) -> None:
    staging_csv = tmp_path / "runs/staging_scope_receipt.csv"
    live_csv = tmp_path / mod.DEFAULT_LIVE_RECEIPT_CSV
    _write_csv(staging_csv, _receipt_rows(filled=True))
    _write_csv(live_csv, _receipt_rows(filled=False))
    _write_evidence_packets(tmp_path)
    _write_scope_checklist(tmp_path)
    _write_field_worksheet(tmp_path, pending_field_count=0)

    blocked = mod.build_product_scope_breadth_evidence_operator_staging_apply(
        staging_csv=staging_csv,
        live_receipt_csv=live_csv,
        mode="live_apply",
        write_canonical_receipt=True,
        root=tmp_path,
    )["summary"]
    assert blocked["canonical_receipt_written"] is False
    assert blocked["approval_token_accepted"] is False
    assert "write_canonical_receipt_approval_token_missing_or_invalid" in blocked["blockers"]

    applied = mod.build_product_scope_breadth_evidence_operator_staging_apply(
        staging_csv=staging_csv,
        live_receipt_csv=live_csv,
        mode="live_apply",
        write_canonical_receipt=True,
        approval_token=APPROVAL_TOKEN,
        root=tmp_path,
    )["summary"]
    assert applied["status"] == "product_scope_breadth_evidence_receipt_canonical_written"
    assert applied["canonical_receipt_written"] is True
    assert applied["approval_token_accepted"] is True
    with live_csv.open("r", encoding="utf-8", newline="") as handle:
        live_rows = list(csv.DictReader(handle))
    assert live_rows[0]["evidence_artifact"] == "runs/evidence/direct_binding_evidence_missing.json"
