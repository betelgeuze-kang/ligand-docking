#!/usr/bin/env python3
"""Fail-closed receipt gate for full-scope breadth evidence."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECEIPT_CSV = "config/product_scope_breadth_evidence_receipt_current.csv"
DEFAULT_SCOPE_CHECKLIST_JSON = "runs/product_scope_breadth_closure_checklist_current.json"
DEFAULT_OUT_JSON = "runs/product_scope_breadth_evidence_receipt_current.json"
DEFAULT_OUT_CSV = "runs/product_scope_breadth_evidence_receipt_current.csv"
DEFAULT_OUT_MD = "runs/product_scope_breadth_evidence_receipt_current.md"
APPROVAL_TOKEN = "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT"

CLAIM_BOUNDARY = (
    "Product scope breadth evidence receipt only; it validates local operator-provided evidence packets for "
    "the full-scope/transporter claim blockers. It does not acquire evidence, edit product scope, apply "
    "review rows, run docking, promote claims, upload, email, delete, or mutate external state."
)

REQUIRED_SCOPE_BLOCKERS = [
    "direct_binding_evidence_missing",
    "exact_negative_quantitative_value_missing",
    "manual_identity_scaffold_confirmation_required",
    "scientific_domain_gate_not_ready",
    "allowed_scope_family_count_too_narrow",
    "explicit_general_platform_flag_missing",
]

REQUIRED_COLUMNS = [
    "scope_blocker_id",
    "evidence_artifact",
    "evidence_status",
    "claim_ready",
    "reviewer",
    "reviewed_at_utc",
    "provenance_kind",
    "license_ok",
    "external_state_mutated",
    "approval_token",
    "operator_attestation",
    "notes",
]

ALLOWED_PROVENANCE_KINDS = {
    "transporter_public_binding_evidence",
    "transporter_manual_review_packet",
    "scope_breadth_closure_gate",
    "domain_gate_evidence",
    "product_claim_boundary_decision",
    "operator_curated_public",
}

EXPECTED_EVIDENCE = {
    "direct_binding_evidence_missing": {
        "status": "product_scope_transporter_direct_binding_evidence_ready",
        "true_fields": ["transporter_direct_binding_evidence_ready"],
    },
    "exact_negative_quantitative_value_missing": {
        "status": "product_scope_transporter_negative_quantitative_evidence_ready",
        "true_fields": ["transporter_negative_quantitative_evidence_ready"],
    },
    "manual_identity_scaffold_confirmation_required": {
        "status": "product_scope_transporter_identity_scaffold_review_ready",
        "true_fields": ["transporter_identity_scaffold_review_ready"],
    },
    "scientific_domain_gate_not_ready": {
        "status": "product_scope_scientific_domain_gate_ready",
        "true_fields": ["scientific_domain_gate_ready"],
    },
    "allowed_scope_family_count_too_narrow": {
        "status": "product_scope_family_floor_ready",
        "true_fields": ["scope_family_floor_ready"],
    },
    "explicit_general_platform_flag_missing": {
        "status": "product_scope_general_platform_claim_gate_ready",
        "true_fields": ["general_platform_claim_gate_ready"],
    },
}

PLACEHOLDER_PREFIXES = ("OPERATOR_FILL", "OPERATOR_CONFIRM")


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _read_csv(path_like: str | Path, *, root: Path = ROOT) -> tuple[list[dict[str, Any]], list[str], bool]:
    path = _resolve(path_like, root=root)
    if not path.exists():
        return [], [], False
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader], list(reader.fieldnames or []), True


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
    if packet.get("status"):
        return packet
    return {}


def _has_placeholder(row: dict[str, Any]) -> bool:
    return any(_text(value).startswith(PLACEHOLDER_PREFIXES) for value in row.values())


def _reviewed_at_valid(value: Any) -> bool:
    text = _text(value)
    if not text:
        return False
    try:
        dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _current_scope_blocker_classes(path_like: str | Path, *, root: Path = ROOT) -> tuple[set[str], dict[str, Any], bool]:
    packet, present = _read_json(path_like, root=root)
    summary = _summary(packet)
    counts = summary.get("blocker_class_counts")
    if isinstance(counts, dict):
        return {str(key) for key, value in counts.items() if int(value or 0) > 0}, summary, present
    classes = summary.get("blocker_classes")
    if isinstance(classes, list):
        return {str(item) for item in classes if str(item)}, summary, present
    return set(), summary, present


def _row_status(
    row: dict[str, Any],
    *,
    duplicate_scope_blocker_ids: set[str],
    current_scope_blockers: set[str],
    root: Path = ROOT,
) -> dict[str, Any]:
    scope_blocker_id = _text(row.get("scope_blocker_id"))
    expected = EXPECTED_EVIDENCE.get(scope_blocker_id, {})
    evidence_artifact = _text(row.get("evidence_artifact"))
    evidence_packet, evidence_present = _read_json(evidence_artifact, root=root) if evidence_artifact else ({}, False)
    evidence_summary = _summary(evidence_packet)
    expected_status = _text(expected.get("status"))
    expected_true_fields = [str(field) for field in expected.get("true_fields", [])]
    missing_true_fields = [field for field in expected_true_fields if evidence_summary.get(field) is not True]
    blockers: list[str] = []

    if scope_blocker_id not in REQUIRED_SCOPE_BLOCKERS:
        blockers.append("scope_blocker_id_missing_or_unrecognized")
    if scope_blocker_id in duplicate_scope_blocker_ids:
        blockers.append("duplicate_scope_blocker_id")
    if current_scope_blockers and scope_blocker_id not in current_scope_blockers:
        blockers.append("scope_blocker_not_in_current_closure_checklist")
    if _has_placeholder(row):
        blockers.append("operator_placeholders_unfilled")
    if not evidence_artifact:
        blockers.append("evidence_artifact_missing")
    elif not evidence_present:
        blockers.append("evidence_artifact_not_found")
    elif not evidence_summary:
        blockers.append("evidence_json_unreadable_or_missing_status")
    if evidence_summary and expected_status and _text(evidence_summary.get("status")) != expected_status:
        blockers.append("evidence_status_mismatch")
    if missing_true_fields:
        blockers.append("evidence_true_fields_missing:" + ",".join(missing_true_fields))
    if _text(row.get("evidence_status")) != expected_status:
        blockers.append("receipt_evidence_status_mismatch")
    if _bool(row.get("claim_ready")) is not True:
        blockers.append("claim_ready_not_true")
    if not _text(row.get("reviewer")):
        blockers.append("reviewer_missing")
    if not _reviewed_at_valid(row.get("reviewed_at_utc")):
        blockers.append("reviewed_at_utc_missing_or_invalid")
    if _text(row.get("provenance_kind")) not in ALLOWED_PROVENANCE_KINDS:
        blockers.append("provenance_kind_unaccepted")
    if _bool(row.get("license_ok")) is not True:
        blockers.append("license_not_ok")
    if _bool(row.get("external_state_mutated")) is not False:
        blockers.append("external_state_mutated_present")
    if _text(row.get("approval_token")) != APPROVAL_TOKEN:
        blockers.append("approval_token_missing_or_invalid")
    if _text(row.get("operator_attestation")) != "reviewed_for_scope_promotion":
        blockers.append("operator_attestation_missing_or_unaccepted")

    return {
        **{column: row.get(column, "") for column in REQUIRED_COLUMNS},
        "row_status": "pass" if not blockers else "blocked",
        "blockers": ";".join(blockers),
        "expected_evidence_status": expected_status,
        "expected_true_fields": ";".join(expected_true_fields),
        "missing_true_fields": ";".join(missing_true_fields),
        "evidence_artifact_present": evidence_present,
        "observed_evidence_status": _text(evidence_summary.get("status")) or "missing",
        "external_state_mutated": False,
    }


def build_product_scope_breadth_evidence_receipt(
    *,
    receipt_csv: str | Path = DEFAULT_RECEIPT_CSV,
    scope_checklist_json: str | Path = DEFAULT_SCOPE_CHECKLIST_JSON,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    raw_rows, columns, present = _read_csv(receipt_csv, root=root_path)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in columns] if present else list(REQUIRED_COLUMNS)
    scope_blocker_ids = [_text(row.get("scope_blocker_id")) for row in raw_rows if _text(row.get("scope_blocker_id"))]
    duplicate_scope_blocker_ids = sorted(
        {blocker_id for blocker_id in scope_blocker_ids if scope_blocker_ids.count(blocker_id) > 1}
    )
    current_scope_blockers, scope_checklist, scope_checklist_present = _current_scope_blocker_classes(
        scope_checklist_json,
        root=root_path,
    )
    rows = [
        _row_status(
            row,
            duplicate_scope_blocker_ids=set(duplicate_scope_blocker_ids),
            current_scope_blockers=current_scope_blockers,
            root=root_path,
        )
        for row in raw_rows
    ]
    passed_rows = [row for row in rows if row["row_status"] == "pass"]
    blocked_rows = [row for row in rows if row["row_status"] != "pass"]
    row_ids = {_text(row.get("scope_blocker_id")) for row in raw_rows}
    missing_required_scope_blockers = [blocker for blocker in REQUIRED_SCOPE_BLOCKERS if blocker not in row_ids]

    blockers: list[str] = []
    if not present:
        blockers.append("receipt_csv_missing")
    if missing_columns:
        blockers.append("receipt_columns_missing:" + ",".join(missing_columns))
    if missing_required_scope_blockers:
        blockers.append("required_scope_blocker_receipts_missing")
    if duplicate_scope_blocker_ids:
        blockers.append("duplicate_scope_blocker_receipts_present")
    if current_scope_blockers and not set(REQUIRED_SCOPE_BLOCKERS).issubset(current_scope_blockers):
        blockers.append("scope_checklist_missing_required_blockers")
    if blocked_rows:
        blockers.append("blocked_receipt_rows_present")

    ready = bool(present and not blockers and len(passed_rows) == len(REQUIRED_SCOPE_BLOCKERS))
    summary = {
        "packet_type": "product_scope_breadth_evidence_receipt",
        "status": "product_scope_breadth_evidence_receipt_ready" if ready else "blocked_product_scope_breadth_evidence_receipt",
        "full_scope_evidence_receipt_ready": ready,
        "receipt_csv": str(receipt_csv),
        "receipt_csv_present": present,
        "receipt_row_count": len(raw_rows),
        "required_scope_blocker_count": len(REQUIRED_SCOPE_BLOCKERS),
        "required_scope_blockers": list(REQUIRED_SCOPE_BLOCKERS),
        "missing_required_scope_blocker_count": len(missing_required_scope_blockers),
        "missing_required_scope_blockers": missing_required_scope_blockers,
        "duplicate_scope_blocker_id_count": len(duplicate_scope_blocker_ids),
        "duplicate_scope_blocker_ids": duplicate_scope_blocker_ids,
        "pass_row_count": len(passed_rows),
        "blocked_row_count": len(blocked_rows),
        "evidence_artifact_present_count": sum(1 for row in rows if row["evidence_artifact_present"]),
        "evidence_status_verified_count": sum(
            1
            for row in passed_rows
            if row["observed_evidence_status"] == row["expected_evidence_status"]
        ),
        "scope_checklist_json": str(scope_checklist_json),
        "scope_checklist_present": scope_checklist_present,
        "scope_checklist_status": _text(scope_checklist.get("status")),
        "scope_checklist_scope_breadth_ready": bool(scope_checklist.get("scope_breadth_ready") is True),
        "current_scope_blocker_count": len(current_scope_blockers),
        "current_scope_blockers": sorted(current_scope_blockers),
        "approval_token_required": APPROVAL_TOKEN,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "All full-scope evidence receipts are locally verified; rerun scope-breadth, goal audit, release bundle, and source-of-truth gates before considering any widened product claims."
            if ready
            else "Replace placeholder receipt rows with local evidence JSON paths, reviewed provenance, license flags, no external mutation, and APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT."
        ),
    }
    return {"summary": summary, "rows": rows, "required_columns": REQUIRED_COLUMNS}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    summary = payload["summary"]
    lines = [
        "# Product Scope Breadth Evidence Receipt",
        "",
        f"- status: `{summary['status']}`",
        f"- full_scope_evidence_receipt_ready: `{summary['full_scope_evidence_receipt_ready']}`",
        f"- rows pass/total: `{summary['pass_row_count']}/{summary['receipt_row_count']}`",
        f"- blocked_row_count: `{summary['blocked_row_count']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        f"- approval_token_required: `{summary['approval_token_required']}`",
        "",
        "## Blockers",
    ]
    lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    if not summary["blockers"]:
        lines.append("- none")
    lines.extend(["", "## Rows", "", "| scope blocker | status | observed evidence | blockers |", "| --- | --- | --- | --- |"])
    for row in payload["rows"]:
        lines.append(
            f"| `{row['scope_blocker_id']}` | `{row['row_status']}` | "
            f"`{row['observed_evidence_status']}` | `{row['blockers']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build product scope-breadth evidence receipt gate.")
    parser.add_argument("--receipt-csv", default=DEFAULT_RECEIPT_CSV)
    parser.add_argument("--scope-checklist-json", default=DEFAULT_SCOPE_CHECKLIST_JSON)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    root = Path(args.root)
    payload = build_product_scope_breadth_evidence_receipt(
        receipt_csv=args.receipt_csv,
        scope_checklist_json=args.scope_checklist_json,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_markdown(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
