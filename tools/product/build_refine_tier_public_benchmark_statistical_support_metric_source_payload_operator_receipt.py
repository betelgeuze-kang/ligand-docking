#!/usr/bin/env python3
"""Fail-closed operator receipt for R9 statistical-support metric source payloads."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_refine_tier_public_benchmark_statistical_support_metric_source_templates import (
    DEFAULT_OUT_JSON as DEFAULT_METRIC_SOURCE_TEMPLATES_JSON,
    REQUIRED_METRIC_SOURCE_PAYLOAD_FIELDS,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECEIPT_CSV = (
    "config/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.csv"
)
DEFAULT_OUT_JSON = (
    "runs/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.json"
)
DEFAULT_OUT_CSV = (
    "runs/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.csv"
)
DEFAULT_OUT_MD = (
    "runs/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.md"
)

PLACEHOLDER_PREFIXES = ("OPERATOR_FILL", "OPERATOR_CONFIRM")
APPROVAL_TOKEN = "APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS"
REQUIRED_COLUMNS = [
    "template_id",
    "target_id",
    "pose_id",
    "metric_name",
    "metric_source_template_row_sha256",
    "metric_value",
    "method",
    "input_artifacts_reviewed",
    "input_artifact_sha256s_reviewed",
    "metric_source_artifact_reviewed",
    "payload_schema_reviewed",
    "license_ok",
    "external_engine_calls",
    "operator_id",
    "reviewed_at_utc",
    "approval_token",
    "notes",
]
TEMPLATE_FINGERPRINT_FIELDS = [
    "template_id",
    "candidate_queue_id",
    "expansion_slot_id",
    "suggested_work_order_id",
    "target_id",
    "pose_id",
    "metric_name",
    "metric_source_artifact",
    "required_metric_input_artifacts",
    "required_metric_input_artifact_sha256s",
    "required_metric_source_payload_fields",
    "template_payload_json",
]

CLAIM_BOUNDARY = (
    "R9 statistical-support metric source payload operator receipt only; it validates local "
    "operator-reviewed DockQ, lDDT-PLI, and internal DeltaG payload rows against the current "
    "metric source templates before any payload can be treated as reviewed evidence. It does not "
    "download coordinates, run docking or MD, compute metrics, write metric payload JSON files, "
    "write canonical intake, promote claims, upload, email, delete, commit, push, or mutate "
    "external state."
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


def _float_valid(value: Any) -> bool:
    try:
        float(_text(value))
    except (TypeError, ValueError):
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


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [dict(row) for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _read_csv(path_like: str | Path, *, root: Path = ROOT) -> tuple[list[dict[str, str]], list[str], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return [], [], False
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader], list(reader.fieldnames or []), True


def _has_placeholder(row: dict[str, Any]) -> bool:
    return any(
        _text(value).startswith(PLACEHOLDER_PREFIXES)
        for key, value in row.items()
        if key != "notes"
    )


def _reviewed_at_valid(value: Any) -> bool:
    text = _text(value)
    if not text:
        return False
    try:
        dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _split_blockers(value: Any) -> list[str]:
    return [part for part in _text(value).split(";") if part]


def template_row_fingerprint(row: dict[str, Any]) -> str:
    payload = {
        field: _text(row.get(field)).lower() if field == "target_id" else _text(row.get(field))
        for field in TEMPLATE_FINGERPRINT_FIELDS
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _most_common_blocker(rows: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    first_seen: dict[str, int] = {}
    for row in rows:
        for blocker in _split_blockers(row.get("blockers")):
            if blocker not in first_seen:
                first_seen[blocker] = len(first_seen)
            counts[blocker] = counts.get(blocker, 0) + 1
    if not counts:
        return ""
    return sorted(counts.items(), key=lambda item: (-item[1], first_seen[item[0]]))[0][0]


def _receipt_row(
    row: dict[str, Any],
    *,
    template_by_id: dict[str, dict[str, Any]],
    duplicate_template_ids: set[str],
    root: Path,
) -> dict[str, Any]:
    template_id = _text(row.get("template_id"))
    template = template_by_id.get(template_id, {})
    expected_fingerprint = template_row_fingerprint(template) if template else ""
    provided_fingerprint = _text(row.get("metric_source_template_row_sha256"))
    blockers: list[str] = []

    if not template_id or template_id not in template_by_id:
        blockers.append("template_id_missing_or_unrecognized")
    if template_id in duplicate_template_ids:
        blockers.append("duplicate_template_id")
    if _has_placeholder(row):
        blockers.append("operator_placeholders_unfilled")
    if _text(row.get("target_id")).lower() != _text(template.get("target_id")).lower():
        blockers.append("target_id_mismatch")
    if _text(row.get("pose_id")) != _text(template.get("pose_id")):
        blockers.append("pose_id_mismatch")
    if _text(row.get("metric_name")) != _text(template.get("metric_name")):
        blockers.append("metric_name_mismatch")
    if not provided_fingerprint or provided_fingerprint != expected_fingerprint:
        blockers.append("metric_source_template_row_fingerprint_missing_or_mismatch")
    if _float_valid(row.get("metric_value")) is not True:
        blockers.append("metric_value_missing_or_invalid")
    if not _text(row.get("method")):
        blockers.append("method_missing")
    if _bool(row.get("input_artifacts_reviewed")) is not True:
        blockers.append("input_artifacts_reviewed_not_true")
    if _bool(row.get("input_artifact_sha256s_reviewed")) is not True:
        blockers.append("input_artifact_sha256s_reviewed_not_true")
    if _bool(row.get("metric_source_artifact_reviewed")) is not True:
        blockers.append("metric_source_artifact_reviewed_not_true")
    if _bool(row.get("payload_schema_reviewed")) is not True:
        blockers.append("payload_schema_reviewed_not_true")
    if _bool(row.get("license_ok")) is not True:
        blockers.append("license_not_ok")
    if _int(row.get("external_engine_calls")) != 0:
        blockers.append("external_engine_calls_must_be_zero")
    if not _text(row.get("operator_id")):
        blockers.append("operator_id_missing")
    if not _reviewed_at_valid(row.get("reviewed_at_utc")):
        blockers.append("reviewed_at_utc_missing_or_invalid")
    if _text(row.get("approval_token")) != APPROVAL_TOKEN:
        blockers.append("approval_token_missing_or_invalid")
    if _text(template.get("coordinate_validation_status")) != "pass":
        blockers.append("coordinate_validation_not_pass")
    if _bool(template.get("metric_source_payload_fill_ready")) is not True:
        blockers.append("metric_source_template_not_fill_ready")
    if _int(template.get("missing_required_metric_input_artifact_count")):
        blockers.append("required_metric_input_artifacts_missing")
    metric_source_artifact = _text(template.get("metric_source_artifact"))
    if metric_source_artifact and _resolve(metric_source_artifact, root=root).is_file():
        blockers.append("metric_source_artifact_already_present")

    return {
        **{column: row.get(column, "") for column in REQUIRED_COLUMNS},
        "row_status": "pass" if not blockers else "blocked",
        "blockers": ";".join(blockers),
        "expected_metric_source_template_row_sha256": expected_fingerprint,
        "metric_source_template_row_fingerprint_verified": bool(
            provided_fingerprint and provided_fingerprint == expected_fingerprint
        ),
        "candidate_queue_id": _text(template.get("candidate_queue_id")),
        "expansion_slot_id": _text(template.get("expansion_slot_id")),
        "suggested_work_order_id": _text(template.get("suggested_work_order_id")),
        "metric_source_artifact": metric_source_artifact,
        "required_metric_input_artifacts": _text(template.get("required_metric_input_artifacts")),
        "required_metric_input_artifact_sha256s": _text(
            template.get("required_metric_input_artifact_sha256s")
        ),
        "required_metric_source_payload_fields": ";".join(REQUIRED_METRIC_SOURCE_PAYLOAD_FIELDS),
        "coordinate_validation_status": _text(template.get("coordinate_validation_status")) or "missing",
        "metric_materialization_status": _text(template.get("metric_materialization_status")) or "missing",
        "metric_source_payload_fill_ready": _bool(template.get("metric_source_payload_fill_ready")),
        "template_status": _text(template.get("template_status")),
        "template_blockers": _text(template.get("template_blockers")),
        "payload_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "external_state_mutated": False,
    }


def build_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt(
    *,
    receipt_csv: str | Path = DEFAULT_RECEIPT_CSV,
    metric_source_templates_json: str | Path = DEFAULT_METRIC_SOURCE_TEMPLATES_JSON,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    template_payload, template_present = _read_json(metric_source_templates_json, root=root_path)
    template_summary = _summary(template_payload)
    template_rows = _rows(template_payload)
    template_by_id = {
        _text(row.get("template_id")): row for row in template_rows if _text(row.get("template_id"))
    }

    raw_rows, columns, receipt_present = _read_csv(receipt_csv, root=root_path)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in columns] if receipt_present else list(REQUIRED_COLUMNS)
    template_ids = [_text(row.get("template_id")) for row in raw_rows if _text(row.get("template_id"))]
    duplicate_template_ids = sorted({template_id for template_id in template_ids if template_ids.count(template_id) > 1})
    missing_template_ids = [template_id for template_id in template_by_id if template_id not in set(template_ids)]
    unexpected_template_ids = [template_id for template_id in template_ids if template_id not in template_by_id]
    rows = [
        _receipt_row(
            row,
            template_by_id=template_by_id,
            duplicate_template_ids=set(duplicate_template_ids),
            root=root_path,
        )
        for row in raw_rows
    ]
    passed_rows = [row for row in rows if row["row_status"] == "pass"]
    blocked_rows = [row for row in rows if row["row_status"] != "pass"]
    first_blocked = blocked_rows[0] if blocked_rows else {}
    fingerprint_verified_rows = [
        row for row in rows if row.get("metric_source_template_row_fingerprint_verified") is True
    ]
    fingerprint_mismatch_rows = [
        row
        for row in rows
        if "metric_source_template_row_fingerprint_missing_or_mismatch" in _split_blockers(row.get("blockers"))
    ]

    blockers: list[str] = []
    if not template_present:
        blockers.append("metric_source_templates_missing")
    if template_summary.get("status") != "refine_tier_public_benchmark_statistical_support_metric_source_templates_ready":
        blockers.append("metric_source_templates_not_ready")
    if not receipt_present:
        blockers.append("receipt_csv_missing")
    if missing_columns:
        blockers.append("receipt_columns_missing:" + ",".join(missing_columns))
    if missing_template_ids:
        blockers.append("required_metric_source_template_receipts_missing")
    if unexpected_template_ids:
        blockers.append("unexpected_metric_source_template_receipts_present")
    if duplicate_template_ids:
        blockers.append("duplicate_metric_source_template_receipts_present")
    if blocked_rows:
        blockers.append("blocked_receipt_rows_present")

    ready = bool(
        template_present
        and receipt_present
        and not blockers
        and len(passed_rows) == len(template_by_id)
        and len(template_by_id) > 0
    )
    summary = {
        "packet_type": "refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt",
        "status": (
            "refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready"
            if ready
            else "blocked_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt"
        ),
        "operator_receipt_ready": ready,
        "receipt_csv": _display(receipt_csv, root=root_path),
        "receipt_csv_present": receipt_present,
        "receipt_row_count": len(raw_rows),
        "metric_source_templates": _display(metric_source_templates_json, root=root_path),
        "metric_source_templates_present": template_present,
        "metric_source_templates_ready": bool(
            template_summary.get("status")
            == "refine_tier_public_benchmark_statistical_support_metric_source_templates_ready"
        ),
        "metric_source_templates_status": _text(template_summary.get("status")),
        "required_template_count": len(template_by_id),
        "missing_required_template_count": len(missing_template_ids),
        "missing_required_template_ids": missing_template_ids,
        "unexpected_template_count": len(unexpected_template_ids),
        "unexpected_template_ids": unexpected_template_ids,
        "duplicate_template_id_count": len(duplicate_template_ids),
        "duplicate_template_ids": duplicate_template_ids,
        "metric_source_template_row_fingerprint_required": True,
        "metric_source_template_row_fingerprint_verified_count": len(fingerprint_verified_rows),
        "metric_source_template_row_fingerprint_mismatch_count": len(fingerprint_mismatch_rows),
        "pass_row_count": len(passed_rows),
        "blocked_row_count": len(blocked_rows),
        "approved_payload_count": len(passed_rows),
        "template_fill_ready_row_count": sum(
            1 for row in rows if row.get("metric_source_payload_fill_ready") is True
        ),
        "coordinate_validation_pass_payload_row_count": sum(
            1 for row in rows if row.get("coordinate_validation_status") == "pass"
        ),
        "coordinate_validation_blocked_payload_row_count": sum(
            1 for row in rows if row.get("coordinate_validation_status") != "pass"
        ),
        "payload_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "external_state_mutated": False,
        "approval_token_required": APPROVAL_TOKEN,
        "first_blocked_template_id": _text(first_blocked.get("template_id")),
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_blocked_pose_id": _text(first_blocked.get("pose_id")),
        "first_blocked_metric_name": _text(first_blocked.get("metric_name")),
        "first_blocked_row_blockers": _split_blockers(first_blocked.get("blockers")),
        "most_common_row_blocker": _most_common_blocker(blocked_rows),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Receipt ready; only then write reviewed metric source payload JSON files and rerun "
            "materialization, canonical intake, and bootstrap support gates."
            if ready
            else "After the 17 coordinate candidates pass validation, fill all 51 metric-source payload "
            f"receipt rows with numeric reviewed values, matching template fingerprints, method/operator/"
            f"timestamp, license_ok=true, external_engine_calls=0, and {APPROVAL_TOKEN}."
        ),
    }
    return {"summary": summary, "rows": rows, "required_columns": REQUIRED_COLUMNS}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    summary = payload["summary"]
    lines = [
        "# R9 Statistical Support Metric Source Payload Operator Receipt",
        "",
        f"- status: `{summary['status']}`",
        f"- operator_receipt_ready: `{summary['operator_receipt_ready']}`",
        f"- rows pass/blocked/total: `{summary['pass_row_count']}/{summary['blocked_row_count']}/{summary['receipt_row_count']}`",
        f"- required_template_count: `{summary['required_template_count']}`",
        "- template_fingerprint_verified/mismatch: "
        f"`{summary['metric_source_template_row_fingerprint_verified_count']}/"
        f"{summary['metric_source_template_row_fingerprint_mismatch_count']}`",
        f"- coordinate_validation_pass_payload_row_count: `{summary['coordinate_validation_pass_payload_row_count']}`",
        f"- approval_token_required: `{summary['approval_token_required']}`",
        f"- first_blocked_template_id: `{summary['first_blocked_template_id']}`",
        f"- most_common_row_blocker: `{summary['most_common_row_blocker']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        "",
        "## Blockers",
    ]
    lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    if not summary["blockers"]:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| template | target | pose | metric | status | blockers | artifact |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| `{row['template_id']}` | `{row['target_id']}` | `{row['pose_id']}` | "
            f"`{row['metric_name']}` | `{row['row_status']}` | `{row['blockers']}` | "
            f"`{row['metric_source_artifact']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Build R9 statistical-support metric source payload operator receipt gate."
    )
    parser.add_argument("--receipt-csv", default=DEFAULT_RECEIPT_CSV)
    parser.add_argument("--metric-source-templates-json", default=DEFAULT_METRIC_SOURCE_TEMPLATES_JSON)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    root = Path(args.root)
    payload = build_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt(
        receipt_csv=args.receipt_csv,
        metric_source_templates_json=args.metric_source_templates_json,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
