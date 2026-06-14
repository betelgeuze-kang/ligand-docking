#!/usr/bin/env python3
"""Refresh the R9 metric-source payload receipt CSV against current templates."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.product.build_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt import (
    DEFAULT_RECEIPT_CSV,
    REQUIRED_COLUMNS,
    template_row_fingerprint,
)
from tools.product.build_refine_tier_public_benchmark_statistical_support_metric_source_templates import (
    DEFAULT_OUT_JSON as DEFAULT_METRIC_SOURCE_TEMPLATES_JSON,
)

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_NOTES = "Review metric source payload after coordinate validation passes."
PLACEHOLDER_REVIEW_FIELDS = {
    "metric_value": "OPERATOR_FILL_NUMERIC_METRIC_VALUE",
    "method": "OPERATOR_FILL_METHOD_OR_TOOL",
    "input_artifacts_reviewed": "OPERATOR_CONFIRM_TRUE",
    "input_artifact_sha256s_reviewed": "OPERATOR_CONFIRM_TRUE",
    "metric_source_artifact_reviewed": "OPERATOR_CONFIRM_TRUE",
    "payload_schema_reviewed": "OPERATOR_CONFIRM_TRUE",
    "license_ok": "OPERATOR_CONFIRM_TRUE",
    "external_engine_calls": "0",
    "operator_id": "OPERATOR_FILL_OPERATOR_ID",
    "reviewed_at_utc": "OPERATOR_FILL_REVIEWED_AT_UTC",
    "approval_token": "OPERATOR_FILL_APPROVAL_TOKEN",
    "notes": DEFAULT_NOTES,
}

CLAIM_BOUNDARY = (
    "R9 statistical-support metric source payload receipt CSV refresh only; it rewrites the local "
    "operator worksheet so template IDs and template fingerprints match the current metric source "
    "templates. It does not fill numeric metric values, approve receipts, write metric payload JSON "
    "files, promote canonical intake or claims, upload, email, delete, commit, push, or mutate external "
    "state."
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root)
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return (payload if isinstance(payload, dict) else {}), True


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [dict(row) for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _read_csv(path_like: str | Path, *, root: Path = ROOT) -> tuple[list[dict[str, str]], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return [], False
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)], True


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows([{column: row.get(column, "") for column in REQUIRED_COLUMNS} for row in rows])


def _review_value(existing: dict[str, str], field: str, *, preserve_existing_review: bool) -> str:
    if preserve_existing_review and _text(existing.get(field)):
        return _text(existing.get(field))
    return PLACEHOLDER_REVIEW_FIELDS[field]


def _receipt_row(
    template: dict[str, Any],
    *,
    existing_by_template_id: dict[str, dict[str, str]],
) -> tuple[dict[str, str], bool]:
    template_id = _text(template.get("template_id"))
    existing = existing_by_template_id.get(template_id, {})
    current_fingerprint = template_row_fingerprint(template)
    previous_fingerprint = _text(existing.get("metric_source_template_row_sha256"))
    preserve_existing_review = bool(previous_fingerprint and previous_fingerprint == current_fingerprint)
    row = {
        "template_id": template_id,
        "target_id": _text(template.get("target_id")),
        "pose_id": _text(template.get("pose_id")),
        "metric_name": _text(template.get("metric_name")),
        "metric_source_template_row_sha256": current_fingerprint,
    }
    for field in PLACEHOLDER_REVIEW_FIELDS:
        row[field] = _review_value(existing, field, preserve_existing_review=preserve_existing_review)
    return row, preserve_existing_review


def refresh_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_csv(
    *,
    metric_source_templates_json: str | Path = DEFAULT_METRIC_SOURCE_TEMPLATES_JSON,
    receipt_csv: str | Path = DEFAULT_RECEIPT_CSV,
    out_csv: str | Path | None = None,
    write: bool = False,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    out_csv = receipt_csv if out_csv is None else out_csv
    template_payload, template_present = _read_json(metric_source_templates_json, root=root_path)
    template_summary = _summary(template_payload)
    template_rows = _rows(template_payload)
    existing_rows, existing_present = _read_csv(receipt_csv, root=root_path)
    existing_by_template_id = {
        _text(row.get("template_id")): row for row in existing_rows if _text(row.get("template_id"))
    }

    rows: list[dict[str, str]] = []
    preserved_review_count = 0
    for template in template_rows:
        row, preserved = _receipt_row(template, existing_by_template_id=existing_by_template_id)
        rows.append(row)
        if preserved:
            preserved_review_count += 1

    if write:
        _write_csv(out_csv, rows, root=root_path)

    current_ids = {_text(row.get("template_id")) for row in template_rows if _text(row.get("template_id"))}
    existing_ids = set(existing_by_template_id)
    summary = {
        "packet_type": "refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_csv_refresh",
        "status": (
            "refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_csv_refreshed"
            if write
            else "refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_csv_preview"
        ),
        "write_executed": write,
        "metric_source_templates": _display(metric_source_templates_json, root=root_path),
        "metric_source_templates_present": template_present,
        "metric_source_templates_ready": bool(
            template_summary.get("status")
            == "refine_tier_public_benchmark_statistical_support_metric_source_templates_ready"
        ),
        "receipt_csv": _display(receipt_csv, root=root_path),
        "receipt_csv_present_before": existing_present,
        "out_csv": _display(out_csv, root=root_path),
        "template_row_count": len(template_rows),
        "refreshed_receipt_row_count": len(rows),
        "preserved_existing_review_row_count": preserved_review_count,
        "reset_review_row_count": len(rows) - preserved_review_count,
        "dropped_stale_receipt_row_count": len(existing_ids - current_ids),
        "missing_existing_receipt_row_count": len(current_ids - existing_ids),
        "numeric_metric_value_filled_count": 0,
        "approval_token_filled_count": 0,
        "payload_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows, "required_columns": REQUIRED_COLUMNS}


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(
        description="Refresh R9 statistical-support metric source payload receipt CSV fingerprints."
    )
    parser.add_argument("--metric-source-templates-json", default=DEFAULT_METRIC_SOURCE_TEMPLATES_JSON)
    parser.add_argument("--receipt-csv", default=DEFAULT_RECEIPT_CSV)
    parser.add_argument("--out-csv", default=None)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    payload = (
        refresh_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_csv(
            metric_source_templates_json=args.metric_source_templates_json,
            receipt_csv=args.receipt_csv,
            out_csv=args.out_csv,
            write=args.write,
            root=args.root,
        )
    )
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
