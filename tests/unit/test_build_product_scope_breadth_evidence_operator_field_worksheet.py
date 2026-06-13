from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_product_scope_breadth_evidence_operator_field_worksheet as mod
from tools.product.build_product_scope_breadth_evidence_receipt import (
    APPROVAL_TOKEN,
    EXPECTED_EVIDENCE,
    REQUIRED_COLUMNS,
    REQUIRED_SCOPE_BLOCKERS,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


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


def _receipt_packet(*, ready: bool = False) -> dict:
    rows = []
    for row in _receipt_rows(filled=ready):
        rows.append(
            {
                **row,
                "row_status": "pass" if ready else "blocked",
                "observed_evidence_status": row["evidence_status"] if ready else "missing",
                "missing_true_fields": "" if ready else "transporter_direct_binding_evidence_ready",
            }
        )
    return {
        "summary": {
            "status": (
                "product_scope_breadth_evidence_receipt_ready"
                if ready
                else "blocked_product_scope_breadth_evidence_receipt"
            ),
            "full_scope_evidence_receipt_ready": ready,
            "first_blocked_scope_blocker_id": (
                "" if ready else "direct_binding_evidence_missing"
            ),
            "external_state_mutated": False,
        },
        "rows": rows,
    }


def _priority_packet(*, ready: bool = False) -> dict:
    return {
        "summary": {
            "status": "product_scope_breadth_evidence_priority_packet_ready",
            "priority_packet_ready": True,
            "open_item_count": 0 if ready else 15,
            "scientific_evidence_request_count": 0 if ready else 11,
            "local_crosscheck_candidate_count": 0 if ready else 11,
            "review_only_keep_blocked_count": 0 if ready else 1,
            "top_item_id": "" if ready else "AQP1.core_binder_01",
            "top_bucket": (
                "" if ready else "local_crosscheck_review_present_but_exact_quant_required"
            ),
            "top_domain": "" if ready else "transporter",
            "top_target_id": "" if ready else "AQP1",
            "top_required_evidence_type": (
                "" if ready else "exact_transporter_target_pair_quantitative_binder_kcal"
            ),
            "top_review_template_artifact": (
                "" if ready else "runs/transporter_manual_review_intake_template_current.json"
            ),
            "top_apply_gate_artifact": (
                "" if ready else "runs/transporter_binder_promotion_gate_current.json"
            ),
            "top_next_step": (
                "" if ready else "Review local crosscheck files, capture exact evidence if present."
            ),
            "external_state_mutated": False,
        }
    }


def _scope_checklist(*, ready: bool = False) -> dict:
    return {
        "summary": {
            "status": (
                "product_scope_breadth_closure_checklist_ready"
                if ready
                else "blocked_product_scope_breadth_closure_checklist"
            ),
            "scope_breadth_ready": ready,
            "blocker_classes": [] if ready else list(REQUIRED_SCOPE_BLOCKERS),
            "manual_review_subcheck_count": 0 if ready else 39,
            "ready_for_apply_count": 6 if ready else 0,
            "external_state_mutated": False,
        }
    }


def _write_sources(tmp_path: Path, *, filled: bool = False) -> None:
    _write_csv(tmp_path / mod.DEFAULT_RECEIPT_CSV, _receipt_rows(filled=filled), REQUIRED_COLUMNS)
    _write_json(tmp_path / mod.DEFAULT_RECEIPT_JSON, _receipt_packet(ready=filled))
    _write_json(tmp_path / mod.DEFAULT_PRIORITY_PACKET_JSON, _priority_packet(ready=filled))
    _write_json(tmp_path / mod.DEFAULT_SCOPE_CHECKLIST_JSON, _scope_checklist(ready=filled))


def test_product_scope_breadth_evidence_operator_field_worksheet_flags_pending_fields(
    tmp_path: Path,
) -> None:
    _write_sources(tmp_path, filled=False)

    payload = mod.build_product_scope_breadth_evidence_operator_field_worksheet(root=tmp_path)
    summary = payload["summary"]

    assert summary["status"] == "product_scope_breadth_evidence_operator_field_worksheet_ready"
    assert summary["field_worksheet_ready"] is True
    assert summary["operator_fill_complete"] is False
    assert summary["receipt_row_count"] == 6
    assert summary["receipt_field_row_count"] == 72
    assert summary["required_receipt_field_count"] == 66
    assert summary["operator_fill_pending_field_count"] == 36
    assert summary["invalid_field_count"] == 0
    assert summary["top_blocker_id"] == "direct_binding_evidence_missing"
    assert summary["top_blocker_field_count"] == 12
    assert summary["top_blocker_pending_field_count"] == 6
    assert summary["top_item_id"] == "AQP1.core_binder_01"
    assert summary["top_bucket"] == "local_crosscheck_review_present_but_exact_quant_required"
    assert summary["priority_open_item_count"] == 15
    assert summary["priority_scientific_evidence_request_count"] == 11
    assert summary["priority_local_crosscheck_candidate_count"] == 11
    assert summary["priority_review_only_keep_blocked_count"] == 1
    assert summary["scope_checklist_manual_review_subcheck_count"] == 39
    assert summary["claim_promoted"] is False
    assert summary["external_state_mutated"] is False


def test_product_scope_breadth_evidence_operator_field_worksheet_can_be_fill_complete(
    tmp_path: Path,
) -> None:
    _write_sources(tmp_path, filled=True)

    payload = mod.build_product_scope_breadth_evidence_operator_field_worksheet(root=tmp_path)
    summary = payload["summary"]

    assert summary["field_worksheet_ready"] is True
    assert summary["operator_fill_complete"] is True
    assert summary["operator_fill_pending_field_count"] == 0
    assert summary["invalid_field_count"] == 0
    assert all(row["operator_input_required"] is False for row in payload["rows"])


def test_product_scope_breadth_evidence_operator_field_worksheet_blocks_missing_sources(
    tmp_path: Path,
) -> None:
    payload = mod.build_product_scope_breadth_evidence_operator_field_worksheet(root=tmp_path)
    summary = payload["summary"]

    assert summary["status"] == "blocked_product_scope_breadth_evidence_operator_field_worksheet"
    assert summary["field_worksheet_ready"] is False
    assert "receipt_csv_missing" in summary["blockers"]
    assert "receipt_artifact_missing" in summary["blockers"]
    assert "priority_packet_artifact_missing" in summary["blockers"]
    assert "scope_checklist_artifact_missing" in summary["blockers"]
