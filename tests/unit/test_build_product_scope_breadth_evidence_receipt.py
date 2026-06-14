from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_product_scope_breadth_evidence_receipt as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=mod.REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _scope_checklist(path: Path) -> None:
    _write_json(
        path,
        {
            "summary": {
                "status": "product_scope_breadth_closure_checklist_ready",
                "blocker_class_counts": {blocker: 1 for blocker in mod.REQUIRED_SCOPE_BLOCKERS},
                "scope_breadth_ready": False,
            }
        },
    )


def test_product_scope_breadth_evidence_receipt_blocks_default_template() -> None:
    payload = mod.build_product_scope_breadth_evidence_receipt()
    summary = payload["summary"]

    assert summary["status"] == "blocked_product_scope_breadth_evidence_receipt"
    assert summary["full_scope_evidence_receipt_ready"] is False
    assert summary["receipt_row_count"] == 6
    assert summary["required_scope_blocker_count"] == 6
    assert summary["missing_required_scope_blocker_count"] == 0
    assert summary["blocked_row_count"] == 6
    assert summary["first_blocked_scope_blocker_id"] == "direct_binding_evidence_missing"
    assert summary["first_blocked_evidence_artifact"] == "OPERATOR_FILL_LOCAL_EVIDENCE_JSON"
    assert summary["first_blocked_expected_evidence_status"] == (
        "product_scope_transporter_direct_binding_evidence_ready"
    )
    assert summary["first_blocked_observed_evidence_status"] == "missing"
    assert summary["first_blocked_missing_true_fields"] == ["transporter_direct_binding_evidence_ready"]
    assert "operator_placeholders_unfilled" in summary["first_blocked_row_blockers"]
    assert summary["most_common_row_blocker"] == "operator_placeholders_unfilled"
    assert summary["evidence_status_contract_present_count"] == 6
    assert summary["expected_true_fields_present_count"] == 6
    assert summary["expected_quality_true_field_count"] == 4
    assert summary["expected_int_min_field_count"] == 4
    assert summary["expected_false_field_count"] == 4
    assert summary["provenance_kind_accepted_count"] == 6
    assert summary["external_state_mutated_false_count"] == 6
    assert summary["operator_attestation_accepted_count"] == 6
    assert summary["operator_review_surface_ready_count"] == 6
    assert summary["operator_review_surface_blocked_count"] == 0
    assert summary["receipt_manual_field_pending_count"] == 36
    assert summary["receipt_evidence_artifact_pending_count"] == 6
    assert summary["receipt_claim_ready_pending_count"] == 6
    assert summary["receipt_reviewer_pending_count"] == 6
    assert summary["receipt_reviewed_at_utc_pending_count"] == 6
    assert summary["receipt_license_ok_pending_count"] == 6
    assert summary["receipt_approval_token_pending_count"] == 6
    assert summary["external_state_mutated"] is False
    assert "blocked_receipt_rows_present" in summary["blockers"]
    assert all(row["row_status"] == "blocked" for row in payload["rows"])
    assert all("operator_placeholders_unfilled" in row["blockers"] for row in payload["rows"])
    assert all(row["operator_review_surface_ready"] is True for row in payload["rows"])
    assert all(row["operator_manual_pending_field_count"] == 6 for row in payload["rows"])


def test_product_scope_breadth_evidence_receipt_passes_verified_local_evidence(tmp_path: Path) -> None:
    receipt_csv = tmp_path / "config" / "receipt.csv"
    scope_checklist_json = tmp_path / "runs" / "scope_checklist.json"
    _scope_checklist(scope_checklist_json)
    rows: list[dict[str, object]] = []
    for scope_blocker_id in mod.REQUIRED_SCOPE_BLOCKERS:
        expected = mod.EXPECTED_EVIDENCE[scope_blocker_id]
        evidence_path = tmp_path / "runs" / f"{scope_blocker_id}.json"
        summary = {
            "status": expected["status"],
            **{field: True for field in expected["true_fields"]},
            **{field: True for field in expected.get("quality_true_fields", [])},
            **{
                field: minimum
                for field, minimum in (expected.get("int_min_fields") or {}).items()
            },
            **{field: False for field in expected.get("false_fields", [])},
        }
        if scope_blocker_id == "direct_binding_evidence_missing":
            summary["status"] = "aqp1_direct_binding_external_evidence_intake_ready"
            summary["product_scope_evidence_status"] = expected["status"]
        if scope_blocker_id == "exact_negative_quantitative_value_missing":
            summary["status"] = "aqp1_negative_evidence_intake_gate_ready"
            summary["product_scope_evidence_status"] = expected["status"]
        evidence_payload = {
            "summary": summary,
        }
        _write_json(evidence_path, evidence_payload)
        rows.append(
            {
                "scope_blocker_id": scope_blocker_id,
                "evidence_artifact": evidence_path.relative_to(tmp_path).as_posix(),
                "evidence_status": expected["status"],
                "claim_ready": "true",
                "reviewer": "operator-a",
                "reviewed_at_utc": "2026-06-12T00:00:00+00:00",
                "provenance_kind": "operator_curated_public",
                "license_ok": "true",
                "external_state_mutated": "false",
                "approval_token": mod.APPROVAL_TOKEN,
                "operator_attestation": "reviewed_for_scope_promotion",
                "notes": "unit-test evidence",
            }
        )
    _write_csv(receipt_csv, rows)

    payload = mod.build_product_scope_breadth_evidence_receipt(
        receipt_csv=receipt_csv.relative_to(tmp_path),
        scope_checklist_json=scope_checklist_json.relative_to(tmp_path),
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "product_scope_breadth_evidence_receipt_ready"
    assert summary["full_scope_evidence_receipt_ready"] is True
    assert summary["pass_row_count"] == 6
    assert summary["blocked_row_count"] == 0
    assert summary["first_blocked_scope_blocker_id"] == ""
    assert summary["first_blocked_row_blockers"] == []
    assert summary["most_common_row_blocker"] == ""
    assert summary["evidence_status_verified_count"] == 6
    assert summary["operator_review_surface_ready_count"] == 6
    assert summary["operator_review_surface_blocked_count"] == 0
    assert summary["receipt_manual_field_pending_count"] == 0
    assert summary["blockers"] == []
    assert all(row["operator_manual_pending_field_count"] == 0 for row in payload["rows"])


def test_product_scope_breadth_evidence_receipt_rejects_shallow_transporter_evidence(
    tmp_path: Path,
) -> None:
    receipt_csv = tmp_path / "config" / "receipt.csv"
    scope_checklist_json = tmp_path / "runs" / "scope_checklist.json"
    _scope_checklist(scope_checklist_json)
    rows: list[dict[str, object]] = []
    for scope_blocker_id in mod.REQUIRED_SCOPE_BLOCKERS:
        expected = mod.EXPECTED_EVIDENCE[scope_blocker_id]
        evidence_path = tmp_path / "runs" / f"{scope_blocker_id}.json"
        summary = {
            "status": expected["status"],
            **{field: True for field in expected["true_fields"]},
        }
        if scope_blocker_id != "direct_binding_evidence_missing":
            summary.update({field: True for field in expected.get("quality_true_fields", [])})
            summary.update(
                {
                    field: minimum
                    for field, minimum in (expected.get("int_min_fields") or {}).items()
                }
            )
            summary.update({field: False for field in expected.get("false_fields", [])})
        _write_json(evidence_path, {"summary": summary})
        rows.append(
            {
                "scope_blocker_id": scope_blocker_id,
                "evidence_artifact": evidence_path.relative_to(tmp_path).as_posix(),
                "evidence_status": expected["status"],
                "claim_ready": "true",
                "reviewer": "operator-a",
                "reviewed_at_utc": "2026-06-12T00:00:00+00:00",
                "provenance_kind": "operator_curated_public",
                "license_ok": "true",
                "external_state_mutated": "false",
                "approval_token": mod.APPROVAL_TOKEN,
                "operator_attestation": "reviewed_for_scope_promotion",
                "notes": "unit-test evidence",
            }
        )
    _write_csv(receipt_csv, rows)

    payload = mod.build_product_scope_breadth_evidence_receipt(
        receipt_csv=receipt_csv.relative_to(tmp_path),
        scope_checklist_json=scope_checklist_json.relative_to(tmp_path),
        root=tmp_path,
    )
    summary = payload["summary"]
    first_row = payload["rows"][0]

    assert summary["status"] == "blocked_product_scope_breadth_evidence_receipt"
    assert summary["full_scope_evidence_receipt_ready"] is False
    assert summary["pass_row_count"] == 5
    assert summary["blocked_row_count"] == 1
    assert summary["first_blocked_scope_blocker_id"] == "direct_binding_evidence_missing"
    assert summary["first_blocked_missing_true_fields"] == []
    assert (
        "evidence_quality_true_fields_missing:"
        "primary_source_direct_binding_evidence_ready,claim_safe_direct_binding_kcal_ready"
    ) in first_row["blockers"]
    assert (
        "evidence_int_min_fields_missing:"
        "claim_safe_direct_binding_row_count>=1,primary_source_verified_count>=1"
    ) in first_row["blockers"]
    assert (
        "evidence_false_fields_not_false:"
        "direct_binding_gap_open,functional_surrogate_promoted_to_kcal"
    ) in first_row["blockers"]
    assert first_row["operator_review_surface_ready"] is True
    assert first_row["operator_manual_pending_field_count"] == 0
    assert "blocked_receipt_rows_present" in summary["blockers"]


def test_product_scope_breadth_evidence_receipt_cli_writes_outputs(tmp_path: Path) -> None:
    out_json = tmp_path / "receipt.json"
    out_csv = tmp_path / "receipt.csv"
    out_md = tmp_path / "receipt.md"

    mod.main(["--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    assert out_json.is_file()
    assert out_csv.is_file()
    assert out_md.is_file()
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "blocked_product_scope_breadth_evidence_receipt"
