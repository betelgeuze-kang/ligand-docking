#!/usr/bin/env python3
"""Field-level worksheet for full-scope breadth evidence receipt intake."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_product_scope_breadth_evidence_receipt import (
    ALLOWED_PROVENANCE_KINDS,
    APPROVAL_TOKEN,
    DEFAULT_OUT_JSON as DEFAULT_RECEIPT_JSON,
    DEFAULT_RECEIPT_CSV,
    DEFAULT_SCOPE_CHECKLIST_JSON,
    EXPECTED_EVIDENCE,
    PLACEHOLDER_PREFIXES,
    REQUIRED_COLUMNS,
    REQUIRED_SCOPE_BLOCKERS,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PRIORITY_PACKET_JSON = "runs/product_scope_breadth_evidence_priority_packet_current.json"
DEFAULT_OUT_JSON = "runs/product_scope_breadth_evidence_operator_field_worksheet_current.json"
DEFAULT_OUT_CSV = "runs/product_scope_breadth_evidence_operator_field_worksheet_current.csv"
DEFAULT_OUT_MD = "runs/product_scope_breadth_evidence_operator_field_worksheet_current.md"

OPTIONAL_FIELDS = {"notes"}
TRUE_FIELDS = {"claim_ready", "license_ok"}
TIMESTAMP_FIELDS = {"reviewed_at_utc"}

CLAIM_BOUNDARY = (
    "Product scope breadth evidence operator field worksheet only; it expands the R8 full-scope "
    "evidence receipt into field-level operator inputs and attaches the current scope-priority context. "
    "It does not acquire evidence, edit product scope, apply review rows, run docking, promote claims, "
    "upload, email, delete, commit, push, or mutate external state."
)

FIELD_ACTIONS = {
    "scope_blocker_id": "Keep one of the six required R8 scope blocker ids.",
    "evidence_artifact": "Replace the placeholder with a local reviewed evidence JSON path.",
    "evidence_status": "Keep the expected evidence status for the scope blocker row.",
    "claim_ready": "Confirm true only after the matching evidence packet is locally reviewed.",
    "reviewer": "Record the human/operator reviewer.",
    "reviewed_at_utc": "Record an ISO-8601 UTC review timestamp.",
    "provenance_kind": "Keep an accepted provenance kind for the evidence lane.",
    "license_ok": "Confirm true only after public/source license review.",
    "external_state_mutated": "Keep false; this path must not mutate external state.",
    "approval_token": f"Use {APPROVAL_TOKEN} only after the R8 scope evidence review is approved.",
    "operator_attestation": "Keep reviewed_for_scope_promotion.",
    "notes": "Record caveats without changing claim state.",
}


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display_path(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root)
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool_text(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _has_placeholder(value: Any) -> bool:
    text = _text(value)
    return not text or any(text.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES)


def _is_iso_timestamp(value: Any) -> bool:
    text = _text(value)
    if not text:
        return False
    try:
        dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return (payload if isinstance(payload, dict) else {}), True


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    if isinstance(summary, dict):
        return summary
    return packet if packet.get("status") else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in packet.get("rows") or [] if isinstance(row, dict)]


def _read_csv(
    path_like: str | Path,
    *,
    root: Path = ROOT,
    required_columns: list[str] | None = None,
) -> tuple[list[dict[str, str]], list[str], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return [], list(required_columns or []), False
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    missing_columns = [column for column in (required_columns or []) if column not in fieldnames]
    return rows, missing_columns, True


def _expected_value(field_name: str, scope_blocker_id: str) -> str:
    expected = EXPECTED_EVIDENCE.get(scope_blocker_id, {})
    if field_name == "scope_blocker_id":
        return "one required R8 scope blocker id"
    if field_name == "evidence_artifact":
        return "local reviewed evidence JSON"
    if field_name == "evidence_status":
        return _text(expected.get("status"))
    if field_name in TRUE_FIELDS:
        return "true"
    if field_name == "reviewer":
        return "non-empty operator reviewer"
    if field_name == "reviewed_at_utc":
        return "ISO-8601 UTC timestamp"
    if field_name == "provenance_kind":
        return ",".join(sorted(ALLOWED_PROVENANCE_KINDS))
    if field_name == "external_state_mutated":
        return "false"
    if field_name == "approval_token":
        return APPROVAL_TOKEN
    if field_name == "operator_attestation":
        return "reviewed_for_scope_promotion"
    return ""


def _gate_id(field_name: str, scope_blocker_id: str) -> str:
    if field_name in {"evidence_artifact", "evidence_status", "claim_ready"}:
        return scope_blocker_id
    if field_name in {"reviewer", "reviewed_at_utc", "approval_token", "operator_attestation"}:
        return "operator_review"
    if field_name in {"license_ok", "provenance_kind"}:
        return "provenance_license_review"
    if field_name == "external_state_mutated":
        return "external_state_guard"
    return ""


def _field_status(field_name: str, value: Any, scope_blocker_id: str) -> tuple[str, str]:
    text = _text(value)
    if _has_placeholder(value):
        if field_name in OPTIONAL_FIELDS:
            return "informational", ""
        return "operator_fill_pending", "operator_placeholder_or_empty"
    if field_name == "scope_blocker_id":
        return (
            ("ready", "")
            if text in REQUIRED_SCOPE_BLOCKERS
            else ("invalid", "scope_blocker_id_missing_or_unrecognized")
        )
    if field_name == "evidence_status":
        expected = _text(EXPECTED_EVIDENCE.get(scope_blocker_id, {}).get("status"))
        return ("ready", "") if text == expected else ("invalid", "receipt_evidence_status_mismatch")
    if field_name in TRUE_FIELDS:
        return ("ready", "") if _bool_text(value) else ("invalid", f"{field_name}_not_true")
    if field_name in TIMESTAMP_FIELDS:
        return ("ready", "") if _is_iso_timestamp(value) else ("invalid", "reviewed_at_utc_missing_or_invalid")
    if field_name == "provenance_kind":
        return ("ready", "") if text in ALLOWED_PROVENANCE_KINDS else ("invalid", "provenance_kind_unaccepted")
    if field_name == "external_state_mutated":
        return ("ready", "") if _bool_text(value) is False else ("invalid", "external_state_mutated_present")
    if field_name == "approval_token":
        return ("ready", "") if text == APPROVAL_TOKEN else ("invalid", "approval_token_missing_or_invalid")
    if field_name == "operator_attestation":
        return (
            ("ready", "")
            if text == "reviewed_for_scope_promotion"
            else ("invalid", "operator_attestation_missing_or_unaccepted")
        )
    if field_name in OPTIONAL_FIELDS:
        return "informational", ""
    return ("ready", "") if text else ("operator_fill_pending", "operator_placeholder_or_empty")


def _field_row(
    field_name: str,
    *,
    row_index: int,
    column_present: bool,
    receipt_row: dict[str, str],
    receipt_report_row: dict[str, Any],
    priority_summary: dict[str, Any],
) -> dict[str, Any]:
    scope_blocker_id = _text(receipt_row.get("scope_blocker_id"))
    value = receipt_row.get(field_name, "")
    status, blocker = (
        _field_status(field_name, value, scope_blocker_id)
        if column_present
        else ("missing_column", "receipt_column_missing")
    )
    expected = EXPECTED_EVIDENCE.get(scope_blocker_id, {})
    expected_true_fields = ";".join(str(field) for field in expected.get("true_fields", []))
    return {
        "worksheet_section": "scope_breadth_evidence_receipt",
        "source_row_id": scope_blocker_id or f"receipt_row_{row_index}",
        "source_row_index": row_index,
        "field_name": field_name,
        "gate_id": _gate_id(field_name, scope_blocker_id),
        "receipt_column_present": column_present,
        "required_for_operator_receipt": field_name not in OPTIONAL_FIELDS,
        "top_blocker_field": scope_blocker_id == _text(priority_summary.get("top_scope_blocker_id")),
        "current_value": _text(value),
        "observed_source_value": _text(receipt_report_row.get("observed_evidence_status")),
        "expected_value_hint": _expected_value(field_name, scope_blocker_id),
        "expected_true_fields": expected_true_fields,
        "field_status": status,
        "blocker": blocker,
        "operator_input_required": status == "operator_fill_pending",
        "top_item_id": _text(priority_summary.get("top_item_id")),
        "top_bucket": _text(priority_summary.get("top_bucket")),
        "top_required_evidence_type": _text(priority_summary.get("top_required_evidence_type")),
        "operator_action": FIELD_ACTIONS.get(field_name, ""),
        "claim_promoted": False,
        "external_state_mutated": False,
    }


def build_product_scope_breadth_evidence_operator_field_worksheet(
    *,
    receipt_csv: str | Path = DEFAULT_RECEIPT_CSV,
    receipt_json: str | Path = DEFAULT_RECEIPT_JSON,
    priority_packet_json: str | Path = DEFAULT_PRIORITY_PACKET_JSON,
    scope_checklist_json: str | Path = DEFAULT_SCOPE_CHECKLIST_JSON,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    receipt_rows, receipt_missing_columns, receipt_csv_present = _read_csv(
        receipt_csv,
        root=root_path,
        required_columns=REQUIRED_COLUMNS,
    )
    receipt_packet, receipt_artifact_present = _read_json(receipt_json, root=root_path)
    priority_packet, priority_artifact_present = _read_json(priority_packet_json, root=root_path)
    scope_checklist_packet, scope_checklist_artifact_present = _read_json(
        scope_checklist_json,
        root=root_path,
    )
    receipt_summary = _summary(receipt_packet)
    priority_summary = _summary(priority_packet)
    scope_checklist_summary = _summary(scope_checklist_packet)
    receipt_report_by_blocker = {
        _text(row.get("scope_blocker_id")): row for row in _rows(receipt_packet)
    }
    worksheet_rows = [
        _field_row(
            field_name,
            row_index=row_index,
            column_present=field_name not in receipt_missing_columns,
            receipt_row=receipt_row,
            receipt_report_row=receipt_report_by_blocker.get(_text(receipt_row.get("scope_blocker_id")), {}),
            priority_summary=priority_summary,
        )
        for row_index, receipt_row in enumerate(receipt_rows, start=1)
        for field_name in REQUIRED_COLUMNS
    ]
    pending_rows = [row for row in worksheet_rows if row["field_status"] == "operator_fill_pending"]
    invalid_rows = [row for row in worksheet_rows if row["field_status"] in {"invalid", "missing_column"}]
    top_blocker_id = _text(receipt_summary.get("first_blocked_scope_blocker_id"))
    top_blocker_rows = [
        row for row in worksheet_rows if row.get("source_row_id") == top_blocker_id
    ]
    top_blocker_pending_rows = [
        row for row in top_blocker_rows if row["field_status"] == "operator_fill_pending"
    ]
    source_blockers: list[str] = []
    if not receipt_csv_present:
        source_blockers.append("receipt_csv_missing")
    if receipt_missing_columns:
        source_blockers.append("receipt_columns_missing")
    if not receipt_rows:
        source_blockers.append("receipt_rows_missing")
    if not receipt_artifact_present:
        source_blockers.append("receipt_artifact_missing")
    if not priority_artifact_present:
        source_blockers.append("priority_packet_artifact_missing")
    if not scope_checklist_artifact_present:
        source_blockers.append("scope_checklist_artifact_missing")
    worksheet_ready = not source_blockers
    operator_fill_complete = worksheet_ready and not pending_rows and not invalid_rows
    summary = {
        "packet_type": "product_scope_breadth_evidence_operator_field_worksheet",
        "status": (
            "product_scope_breadth_evidence_operator_field_worksheet_ready"
            if worksheet_ready
            else "blocked_product_scope_breadth_evidence_operator_field_worksheet"
        ),
        "field_worksheet_ready": worksheet_ready,
        "operator_fill_complete": operator_fill_complete,
        "receipt_csv": _display_path(receipt_csv, root=root_path),
        "receipt_artifact": _display_path(receipt_json, root=root_path),
        "receipt_status": _text(receipt_summary.get("status")),
        "receipt_ready": bool(receipt_summary.get("full_scope_evidence_receipt_ready") is True),
        "priority_packet_artifact": _display_path(priority_packet_json, root=root_path),
        "priority_packet_status": _text(priority_summary.get("status")),
        "priority_packet_ready": bool(priority_summary.get("priority_packet_ready") is True),
        "scope_checklist_artifact": _display_path(scope_checklist_json, root=root_path),
        "scope_checklist_status": _text(scope_checklist_summary.get("status")),
        "scope_breadth_ready": bool(scope_checklist_summary.get("scope_breadth_ready") is True),
        "receipt_csv_present": receipt_csv_present,
        "receipt_artifact_present": receipt_artifact_present,
        "priority_packet_artifact_present": priority_artifact_present,
        "scope_checklist_artifact_present": scope_checklist_artifact_present,
        "receipt_row_count": len(receipt_rows),
        "receipt_field_row_count": len(worksheet_rows),
        "required_receipt_field_count": len(
            [row for row in worksheet_rows if row["required_for_operator_receipt"]]
        ),
        "operator_fill_pending_field_count": len(pending_rows),
        "invalid_field_count": len(invalid_rows),
        "ready_field_count": len([row for row in worksheet_rows if row["field_status"] == "ready"]),
        "informational_field_count": len(
            [row for row in worksheet_rows if row["field_status"] == "informational"]
        ),
        "top_blocker_id": top_blocker_id,
        "top_blocker_field_count": len(top_blocker_rows),
        "top_blocker_pending_field_count": len(top_blocker_pending_rows),
        "pending_field_names": [f"{row['source_row_id']}:{row['field_name']}" for row in pending_rows],
        "invalid_field_names": [f"{row['source_row_id']}:{row['field_name']}" for row in invalid_rows],
        "top_item_id": _text(priority_summary.get("top_item_id")),
        "top_bucket": _text(priority_summary.get("top_bucket")),
        "top_domain": _text(priority_summary.get("top_domain")),
        "top_target_id": _text(priority_summary.get("top_target_id")),
        "top_required_evidence_type": _text(priority_summary.get("top_required_evidence_type")),
        "top_review_template_artifact": _text(priority_summary.get("top_review_template_artifact")),
        "top_apply_gate_artifact": _text(priority_summary.get("top_apply_gate_artifact")),
        "top_next_step": _text(priority_summary.get("top_next_step")),
        "priority_open_item_count": int(priority_summary.get("open_item_count") or 0),
        "priority_scientific_evidence_request_count": int(
            priority_summary.get("scientific_evidence_request_count") or 0
        ),
        "priority_local_crosscheck_candidate_count": int(
            priority_summary.get("local_crosscheck_candidate_count") or 0
        ),
        "priority_review_only_keep_blocked_count": int(
            priority_summary.get("review_only_keep_blocked_count") or 0
        ),
        "scope_checklist_blocker_class_count": len(scope_checklist_summary.get("blocker_classes") or []),
        "scope_checklist_manual_review_subcheck_count": int(
            scope_checklist_summary.get("manual_review_subcheck_count") or 0
        ),
        "scope_checklist_ready_for_apply_count": int(
            scope_checklist_summary.get("ready_for_apply_count") or 0
        ),
        "approval_token_required": APPROVAL_TOKEN,
        "claim_promotion_allowed": False,
        "claim_promoted": False,
        "external_state_mutated": False,
        "blocker_count": len(source_blockers),
        "blockers": source_blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Operator fields are complete; rerun scope receipt, scope closure, goal audit, and release gates "
            "before any full-scope claim promotion."
            if operator_fill_complete
            else "Fill the R8 scope-breadth evidence receipt fields, starting with the first blocked scope "
            "receipt row and top evidence-priority item, then rerun scope receipt and full-commercial matrix."
        ),
        "source_artifacts": [
            str(receipt_csv),
            str(receipt_json),
            str(priority_packet_json),
            str(scope_checklist_json),
        ],
    }
    return {"summary": summary, "rows": worksheet_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    summary = payload["summary"]
    lines = [
        "# Product Scope Breadth Evidence Operator Field Worksheet",
        "",
        f"- status: `{summary['status']}`",
        f"- field_worksheet_ready: `{summary['field_worksheet_ready']}`",
        f"- operator_fill_complete: `{summary['operator_fill_complete']}`",
        f"- operator_fill_pending_field_count: `{summary['operator_fill_pending_field_count']}`",
        f"- top_blocker_id: `{summary['top_blocker_id']}`",
        f"- top_blocker_pending_field_count: `{summary['top_blocker_pending_field_count']}`",
        f"- top_item_id: `{summary['top_item_id']}`",
        f"- top_bucket: `{summary['top_bucket']}`",
        f"- approval_token_required: `{summary['approval_token_required']}`",
        "",
        "## Rows",
        "",
        "| section | source row | field | gate | status | current | expected | action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['worksheet_section']}` | `{row['source_row_id']}` | `{row['field_name']}` | "
            f"`{row['gate_id']}` | `{row['field_status']}` | `{row['current_value']}` | "
            f"`{row['expected_value_hint']}` | `{row['operator_action']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build field-level worksheet for product scope-breadth evidence receipt."
    )
    parser.add_argument("--receipt-csv", default=DEFAULT_RECEIPT_CSV)
    parser.add_argument("--receipt-json", default=DEFAULT_RECEIPT_JSON)
    parser.add_argument("--priority-packet-json", default=DEFAULT_PRIORITY_PACKET_JSON)
    parser.add_argument("--scope-checklist-json", default=DEFAULT_SCOPE_CHECKLIST_JSON)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_product_scope_breadth_evidence_operator_field_worksheet(
        receipt_csv=args.receipt_csv,
        receipt_json=args.receipt_json,
        priority_packet_json=args.priority_packet_json,
        scope_checklist_json=args.scope_checklist_json,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_markdown(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
