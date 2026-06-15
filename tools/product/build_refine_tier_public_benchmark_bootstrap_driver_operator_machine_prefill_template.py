#!/usr/bin/env python3
"""Build a machine-supported prefill template for R9 bootstrap-driver operator rows."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_refine_tier_public_benchmark_bootstrap_driver_operator_field_triage import (
    DEFAULT_OUT_JSON as DEFAULT_FIELD_TRIAGE_JSON,
    MACHINE_SUPPORTED_REVIEW_FIELDS,
    OPERATOR_ONLY_FIELDS,
)
from tools.product.build_refine_tier_public_benchmark_bootstrap_driver_operator_review_worksheet import (
    DEFAULT_OUT_CSV as DEFAULT_WORKSHEET_CSV,
)
from tools.product.build_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt import (
    APPROVAL_TOKEN,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PREFILL_CSV = (
    "config/refine_tier_public_benchmark_bootstrap_driver_operator_machine_prefill_template_current.csv"
)
DEFAULT_OUT_JSON = "config/refine_tier_public_benchmark_bootstrap_driver_operator_machine_prefill_template_current.json"
DEFAULT_OUT_MD = "docs/refine_tier_public_benchmark_bootstrap_driver_operator_machine_prefill_template_current.md"

PLACEHOLDER_PREFIXES = ("OPERATOR_FILL", "OPERATOR_CONFIRM")
ACCEPT_DECISIONS = {"accept", "accepted", "approve", "approved", "reviewed_accept"}
MANUAL_FIELDS = [
    "operator_decision",
    "metric_value_reviewed",
    "method_reviewed",
    "input_artifacts_reviewed",
    "input_artifact_sha256s_reviewed",
    "expected_metric_source_artifact_reviewed",
    "payload_schema_reviewed",
    "license_ok_reviewed",
    "operator_id",
    "reviewed_at_utc",
    "approval_token",
]

CLAIM_BOUNDARY = (
    "R9 bootstrap-driver operator machine prefill template only creates a separate candidate worksheet "
    "CSV where machine-supported review-confirmation fields are prefilled from current local evidence. "
    "It leaves operator decision, license review, operator identity, timestamp, and approval token as "
    "operator-only placeholders. It does not edit the canonical worksheet, mark operator approval, write "
    "metric payload JSON, copy canonical receipts, promote canonical intake, change production scoring, "
    "run docking/MD, download, upload, email, delete, commit, push, or mutate external state."
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


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _split_semicolon(value: Any) -> list[str]:
    return [part.strip() for part in _text(value).split(";") if part.strip()]


def _read_csv(path_like: str | Path, *, root: Path) -> tuple[list[dict[str, str]], list[str], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return [], [], False
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader], list(reader.fieldnames or []), True


def _read_json(path_like: str | Path, *, root: Path) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return payload if isinstance(payload, dict) else {}, True


def _has_placeholder(value: Any) -> bool:
    return _text(value).startswith(PLACEHOLDER_PREFIXES)


def _reviewed_at_valid(value: Any) -> bool:
    text = _text(value)
    if not text or _has_placeholder(text):
        return False
    try:
        dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _remaining_pending_fields(row: dict[str, Any]) -> list[str]:
    pending: list[str] = []
    if _text(row.get("operator_decision")).lower() not in ACCEPT_DECISIONS:
        pending.append("operator_decision")
    for field in (
        "metric_value_reviewed",
        "method_reviewed",
        "input_artifacts_reviewed",
        "input_artifact_sha256s_reviewed",
        "expected_metric_source_artifact_reviewed",
        "payload_schema_reviewed",
        "license_ok_reviewed",
    ):
        if _bool(row.get(field)) is not True:
            pending.append(field)
    if not _text(row.get("operator_id")) or _has_placeholder(row.get("operator_id")):
        pending.append("operator_id")
    if not _reviewed_at_valid(row.get("reviewed_at_utc")):
        pending.append("reviewed_at_utc")
    if _text(row.get("approval_token")) != APPROVAL_TOKEN:
        pending.append("approval_token")
    return pending


def _worksheet_key(row: dict[str, Any]) -> str:
    return _text(row.get("worksheet_id"))


def _triage_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [dict(row) for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _prefill_row(row: dict[str, str], triage: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    prefilled = dict(row)
    machine_gap_fields = _split_semicolon(triage.get("machine_gap_pending_fields"))
    if machine_gap_fields:
        return prefilled, []
    fields_to_prefill = [
        field
        for field in _split_semicolon(triage.get("machine_supported_pending_fields"))
        if field in MACHINE_SUPPORTED_REVIEW_FIELDS
    ]
    for field in fields_to_prefill:
        prefilled[field] = "true"
    prefilled["operator_manual_pending_fields"] = ";".join(_remaining_pending_fields(prefilled))
    prefilled["operator_manual_pending_field_count"] = str(len(_remaining_pending_fields(prefilled)))
    return prefilled, fields_to_prefill


def build_refine_tier_public_benchmark_bootstrap_driver_operator_machine_prefill_template(
    *,
    worksheet_csv: str | Path = DEFAULT_WORKSHEET_CSV,
    field_triage_json: str | Path = DEFAULT_FIELD_TRIAGE_JSON,
    prefill_csv: str | Path = DEFAULT_PREFILL_CSV,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    worksheet_rows, worksheet_columns, worksheet_present = _read_csv(worksheet_csv, root=root_path)
    triage_payload, triage_present = _read_json(field_triage_json, root=root_path)
    triage_summary = triage_payload.get("summary") if isinstance(triage_payload.get("summary"), dict) else {}
    triage_by_id = {_worksheet_key(row): row for row in _triage_rows(triage_payload) if _worksheet_key(row)}

    prefilled_rows: list[dict[str, str]] = []
    report_rows: list[dict[str, Any]] = []
    for row in worksheet_rows:
        triage = triage_by_id.get(_worksheet_key(row), {})
        prefilled, fields = _prefill_row(row, triage)
        remaining = _remaining_pending_fields(prefilled)
        operator_only_remaining = [field for field in remaining if field in OPERATOR_ONLY_FIELDS]
        machine_remaining = [field for field in remaining if field in MACHINE_SUPPORTED_REVIEW_FIELDS]
        unclassified_remaining = [
            field for field in remaining if field not in OPERATOR_ONLY_FIELDS and field not in MACHINE_SUPPORTED_REVIEW_FIELDS
        ]
        prefilled_rows.append(prefilled)
        report_rows.append(
            {
                "worksheet_id": _worksheet_key(row),
                "target_id": _text(row.get("target_id")),
                "pose_id": _text(row.get("pose_id")),
                "work_order_id": _text(row.get("work_order_id")),
                "split": _text(row.get("split")),
                "metric_name": _text(row.get("metric_name")),
                "review_surface": _text(row.get("review_surface")),
                "machine_prefilled_field_count": len(fields),
                "machine_prefilled_fields": ";".join(fields),
                "operator_only_remaining_field_count": len(operator_only_remaining),
                "operator_only_remaining_fields": ";".join(operator_only_remaining),
                "machine_remaining_field_count": len(machine_remaining),
                "machine_remaining_fields": ";".join(machine_remaining),
                "unclassified_remaining_field_count": len(unclassified_remaining),
                "unclassified_remaining_fields": ";".join(unclassified_remaining),
                "remaining_pending_field_count": len(remaining),
                "remaining_pending_fields": ";".join(remaining),
                "prefill_template_row_status": "blocked_operator_only_fields_remaining" if remaining else "ready",
                "payload_write_allowed": False,
                "canonical_receipt_write_allowed": False,
                "canonical_intake_promotion_allowed": False,
                "claim_promotion_allowed": False,
                "external_state_mutated": False,
            }
        )

    missing_triage_ids = [
        _worksheet_key(row) for row in worksheet_rows if _worksheet_key(row) and _worksheet_key(row) not in triage_by_id
    ]
    machine_prefill_count = sum(_int(row.get("machine_prefilled_field_count")) for row in report_rows)
    remaining_count = sum(_int(row.get("remaining_pending_field_count")) for row in report_rows)
    operator_only_remaining_count = sum(_int(row.get("operator_only_remaining_field_count")) for row in report_rows)
    machine_remaining_count = sum(_int(row.get("machine_remaining_field_count")) for row in report_rows)
    unclassified_remaining_count = sum(_int(row.get("unclassified_remaining_field_count")) for row in report_rows)

    blockers: list[str] = []
    if not worksheet_present:
        blockers.append("worksheet_csv_missing")
    if not triage_present:
        blockers.append("field_triage_json_missing")
    if triage_present and _text(triage_summary.get("status")) != "refine_tier_public_benchmark_bootstrap_driver_operator_field_triage_ready":
        blockers.append("field_triage_not_ready")
    if missing_triage_ids:
        blockers.append("field_triage_rows_missing_for_worksheet_ids")
    if machine_remaining_count:
        blockers.append("machine_supported_fields_not_prefilled")
    if unclassified_remaining_count:
        blockers.append("unclassified_fields_remaining")

    summary = {
        "packet_type": "refine_tier_public_benchmark_bootstrap_driver_operator_machine_prefill_template",
        "status": (
            "refine_tier_public_benchmark_bootstrap_driver_operator_machine_prefill_template_ready"
            if worksheet_present and triage_present and report_rows and not blockers
            else "blocked_refine_tier_public_benchmark_bootstrap_driver_operator_machine_prefill_template"
        ),
        "worksheet_csv": _display(worksheet_csv, root=root_path),
        "worksheet_csv_present": worksheet_present,
        "worksheet_column_count": len(worksheet_columns),
        "field_triage_json": _display(field_triage_json, root=root_path),
        "field_triage_json_present": triage_present,
        "field_triage_status": _text(triage_summary.get("status")),
        "prefill_csv": _display(prefill_csv, root=root_path),
        "prefill_row_count": len(prefilled_rows),
        "machine_supported_prefilled_field_count": machine_prefill_count,
        "remaining_pending_field_count": remaining_count,
        "operator_only_remaining_field_count": operator_only_remaining_count,
        "machine_remaining_field_count": machine_remaining_count,
        "unclassified_remaining_field_count": unclassified_remaining_count,
        "remaining_placeholder_row_count": sum(1 for row in prefilled_rows if any(_has_placeholder(row.get(field)) for field in MANUAL_FIELDS)),
        "approval_token_required": APPROVAL_TOKEN,
        "canonical_worksheet_edited": False,
        "payload_write_allowed": False,
        "canonical_receipt_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "production_score_mutation_allowed": False,
        "external_state_mutated": False,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use the prefilled candidate worksheet for operator review only: record accept/reject, license_ok, "
            "operator_id, reviewed_at_utc, and the approval token, then rerun the staging apply preview before "
            "any payload or canonical receipt write."
        ),
    }
    return {"summary": summary, "rows": report_rows, "prefilled_rows": prefilled_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# R9 Bootstrap Driver Operator Machine Prefill Template",
        "",
        f"- status: `{s['status']}`",
        f"- prefill_row_count: `{s['prefill_row_count']}`",
        f"- machine_supported_prefilled_field_count: `{s['machine_supported_prefilled_field_count']}`",
        f"- remaining_pending_field_count: `{s['remaining_pending_field_count']}`",
        f"- operator_only_remaining_field_count: `{s['operator_only_remaining_field_count']}`",
        f"- machine_remaining_field_count: `{s['machine_remaining_field_count']}`",
        f"- unclassified_remaining_field_count: `{s['unclassified_remaining_field_count']}`",
        f"- remaining_placeholder_row_count: `{s['remaining_placeholder_row_count']}`",
        f"- approval_token_required: `{s['approval_token_required']}`",
        f"- canonical_worksheet_edited: `{s['canonical_worksheet_edited']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        "",
        "## Rows",
        "",
        "| worksheet | target | pose | metric | prefilled | remaining | operator-only remaining |",
        "| --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['worksheet_id']}` | `{row['target_id']}` | `{row['pose_id']}` | "
            f"`{row['metric_name']}` | `{row['machine_prefilled_field_count']}` | "
            f"`{row['remaining_pending_field_count']}` | `{row['operator_only_remaining_field_count']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", s["next_required_step"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build R9 bootstrap-driver machine-supported prefill template.")
    parser.add_argument("--worksheet-csv", default=DEFAULT_WORKSHEET_CSV)
    parser.add_argument("--field-triage-json", default=DEFAULT_FIELD_TRIAGE_JSON)
    parser.add_argument("--prefill-csv", default=DEFAULT_PREFILL_CSV)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_refine_tier_public_benchmark_bootstrap_driver_operator_machine_prefill_template(
        worksheet_csv=args.worksheet_csv,
        field_triage_json=args.field_triage_json,
        prefill_csv=args.prefill_csv,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.prefill_csv, root=root), payload["prefilled_rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
