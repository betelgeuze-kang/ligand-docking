#!/usr/bin/env python3
"""Fail-closed operator receipt for R9 statistical-support coordinate fetch approval."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight import (
    DEFAULT_OUT_JSON as DEFAULT_R4_PREFLIGHT_JSON,
    EXECUTE_COMMAND,
)
from tools.product.fetch_public_benchmark_native_structure import APPROVAL_TOKEN

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECEIPT_CSV = (
    "config/refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_current.csv"
)
DEFAULT_OUT_JSON = (
    "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_current.json"
)
DEFAULT_OUT_CSV = (
    "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_current.csv"
)
DEFAULT_OUT_MD = (
    "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_current.md"
)

PLACEHOLDER_PREFIXES = ("OPERATOR_FILL", "OPERATOR_CONFIRM")
REQUIRED_COLUMNS = [
    "r4_review_id",
    "target_id",
    "pose_id",
    "r4_preflight_row_sha256",
    "operator_decision",
    "coordinate_fetch_approved",
    "source_url_reviewed",
    "staging_destination_reviewed",
    "license_ok",
    "biological_assembly_reviewed",
    "execute_command_reviewed",
    "post_fetch_validation_required",
    "canonical_intake_promotion_allowed",
    "claim_promotion_allowed",
    "external_state_mutated",
    "reviewer",
    "reviewed_at_utc",
    "approval_token",
    "notes",
]
R4_FINGERPRINT_FIELDS = [
    "r4_review_id",
    "target_id",
    "pose_id",
    "source_url_primary",
    "staging_destination_path",
    "execute_command",
    "target",
    "action",
    "impact",
    "risk",
    "rollback",
    "verification",
]
R4_OPERATOR_REVIEW_SURFACE_FIELDS = [
    "source_url_primary",
    "staging_destination_path",
    "execute_command",
    "target",
    "action",
    "impact",
    "risk",
    "rollback",
    "verification",
]

CLAIM_BOUNDARY = (
    "R9 statistical-support coordinate fetch operator receipt only; it validates local operator approval "
    "for the public coordinate fetch R4 preflight rows before any execute-mode download can be treated as "
    "approved. It does not download coordinates, run docking or MD, compute metrics, write canonical intake, "
    "promote claims, upload, email, delete, commit, push, or mutate external state."
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
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


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


def _is_placeholder(value: Any) -> bool:
    return _text(value).startswith(PLACEHOLDER_PREFIXES)


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


def _r4_row_fingerprint(row: dict[str, Any]) -> str:
    payload = {
        field: (
            EXECUTE_COMMAND
            if field == "execute_command"
            else _text(row.get(field)).lower()
            if field == "target_id"
            else _text(row.get(field))
        )
        for field in R4_FINGERPRINT_FIELDS
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


def _manual_pending_fields(row: dict[str, Any]) -> list[str]:
    pending: list[str] = []
    if _text(row.get("operator_decision")) != "approve_coordinate_fetch":
        pending.append("operator_decision")
    if not _bool(row.get("coordinate_fetch_approved")):
        pending.append("coordinate_fetch_approved")
    if not _bool(row.get("source_url_reviewed")):
        pending.append("source_url_reviewed")
    if not _bool(row.get("staging_destination_reviewed")):
        pending.append("staging_destination_reviewed")
    if not _bool(row.get("license_ok")):
        pending.append("license_ok")
    if not _bool(row.get("biological_assembly_reviewed")):
        pending.append("biological_assembly_reviewed")
    if not _bool(row.get("execute_command_reviewed")):
        pending.append("execute_command_reviewed")
    if not _bool(row.get("post_fetch_validation_required")):
        pending.append("post_fetch_validation_required")
    if not _text(row.get("reviewer")) or _is_placeholder(row.get("reviewer")):
        pending.append("reviewer")
    if not _reviewed_at_valid(row.get("reviewed_at_utc")):
        pending.append("reviewed_at_utc")
    if _text(row.get("approval_token")) != APPROVAL_TOKEN:
        pending.append("approval_token")
    return pending


def _operator_review_surface_ready(row: dict[str, Any]) -> bool:
    return bool(
        row.get("r4_preflight_row_fingerprint_verified") is True
        and _text(row.get("r4_preflight_status")) == "ready_for_r4_operator_confirmation"
        and all(_text(row.get(field)) for field in R4_OPERATOR_REVIEW_SURFACE_FIELDS)
    )


def _receipt_row(
    row: dict[str, Any],
    *,
    r4_by_id: dict[str, dict[str, Any]],
    duplicate_review_ids: set[str],
) -> dict[str, Any]:
    review_id = _text(row.get("r4_review_id"))
    r4_row = r4_by_id.get(review_id, {})
    expected_fingerprint = _r4_row_fingerprint(r4_row) if r4_row else ""
    provided_fingerprint = _text(row.get("r4_preflight_row_sha256"))
    pending_fields = _manual_pending_fields(row)
    blockers: list[str] = []

    if not review_id or review_id not in r4_by_id:
        blockers.append("r4_review_id_missing_or_unrecognized")
    if review_id in duplicate_review_ids:
        blockers.append("duplicate_r4_review_id")
    if _has_placeholder(row):
        blockers.append("operator_placeholders_unfilled")
    if _text(row.get("target_id")).lower() != _text(r4_row.get("target_id")).lower():
        blockers.append("target_id_mismatch")
    if _text(row.get("pose_id")) != _text(r4_row.get("pose_id")):
        blockers.append("pose_id_mismatch")
    if not provided_fingerprint or provided_fingerprint != expected_fingerprint:
        blockers.append("r4_preflight_row_fingerprint_missing_or_mismatch")
    if _text(row.get("operator_decision")) != "approve_coordinate_fetch":
        blockers.append("operator_decision_not_approved")
    if _bool(row.get("coordinate_fetch_approved")) is not True:
        blockers.append("coordinate_fetch_approved_not_true")
    if _bool(row.get("source_url_reviewed")) is not True:
        blockers.append("source_url_reviewed_not_true")
    if _bool(row.get("staging_destination_reviewed")) is not True:
        blockers.append("staging_destination_reviewed_not_true")
    if _bool(row.get("license_ok")) is not True:
        blockers.append("license_not_ok")
    if _bool(row.get("biological_assembly_reviewed")) is not True:
        blockers.append("biological_assembly_reviewed_not_true")
    if _bool(row.get("execute_command_reviewed")) is not True:
        blockers.append("execute_command_reviewed_not_true")
    if _bool(row.get("post_fetch_validation_required")) is not True:
        blockers.append("post_fetch_validation_required_not_true")
    if _bool(row.get("canonical_intake_promotion_allowed")) is not False:
        blockers.append("canonical_intake_promotion_allowed_must_remain_false")
    if _bool(row.get("claim_promotion_allowed")) is not False:
        blockers.append("claim_promotion_allowed_must_remain_false")
    if _bool(row.get("external_state_mutated")) is not False:
        blockers.append("external_state_mutated_must_remain_false")
    if not _text(row.get("reviewer")):
        blockers.append("reviewer_missing")
    if not _reviewed_at_valid(row.get("reviewed_at_utc")):
        blockers.append("reviewed_at_utc_missing_or_invalid")
    if _text(row.get("approval_token")) != APPROVAL_TOKEN:
        blockers.append("approval_token_missing_or_invalid")

    return {
        **{column: row.get(column, "") for column in REQUIRED_COLUMNS},
        "row_status": "pass" if not blockers else "blocked",
        "blockers": ";".join(blockers),
        "source_url_primary": _text(r4_row.get("source_url_primary")),
        "staging_destination_path": _text(r4_row.get("staging_destination_path")),
        "execute_command": EXECUTE_COMMAND,
        "expected_r4_preflight_row_sha256": expected_fingerprint,
        "r4_preflight_row_fingerprint_verified": bool(
            provided_fingerprint and provided_fingerprint == expected_fingerprint
        ),
        "r4_preflight_status": _text(r4_row.get("r4_preflight_status")) or "missing",
        "coordinate_validation_status": _text(r4_row.get("coordinate_validation_status")) or "missing",
        "metric_materialization_status": _text(r4_row.get("metric_materialization_status")) or "missing",
        "target": _text(r4_row.get("target")),
        "action": _text(r4_row.get("action")),
        "impact": _text(r4_row.get("impact")),
        "risk": _text(r4_row.get("risk")),
        "rollback": _text(r4_row.get("rollback")),
        "verification": _text(r4_row.get("verification")),
        "operator_review_surface_ready": _operator_review_surface_ready(
            {
                **r4_row,
                "execute_command": EXECUTE_COMMAND,
                "r4_preflight_row_fingerprint_verified": bool(
                    provided_fingerprint and provided_fingerprint == expected_fingerprint
                ),
            }
        ),
        "operator_manual_pending_fields": ";".join(pending_fields),
        "operator_manual_pending_field_count": len(pending_fields),
        "download_executed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "external_state_mutated": False,
    }


def build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt(
    *,
    receipt_csv: str | Path = DEFAULT_RECEIPT_CSV,
    r4_preflight_json: str | Path = DEFAULT_R4_PREFLIGHT_JSON,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    r4_payload, r4_present = _read_json(r4_preflight_json, root=root_path)
    r4_summary = _summary(r4_payload)
    r4_rows = _rows(r4_payload)
    r4_by_id = {_text(row.get("r4_review_id")): row for row in r4_rows if _text(row.get("r4_review_id"))}

    raw_rows, columns, receipt_present = _read_csv(receipt_csv, root=root_path)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in columns] if receipt_present else list(REQUIRED_COLUMNS)
    review_ids = [_text(row.get("r4_review_id")) for row in raw_rows if _text(row.get("r4_review_id"))]
    duplicate_review_ids = sorted({review_id for review_id in review_ids if review_ids.count(review_id) > 1})
    missing_review_ids = [review_id for review_id in r4_by_id if review_id not in set(review_ids)]
    unexpected_review_ids = [review_id for review_id in review_ids if review_id not in r4_by_id]
    rows = [
        _receipt_row(
            row,
            r4_by_id=r4_by_id,
            duplicate_review_ids=set(duplicate_review_ids),
        )
        for row in raw_rows
    ]
    passed_rows = [row for row in rows if row["row_status"] == "pass"]
    blocked_rows = [row for row in rows if row["row_status"] != "pass"]
    first_blocked = blocked_rows[0] if blocked_rows else {}
    fingerprint_verified_rows = [
        row for row in rows if row.get("r4_preflight_row_fingerprint_verified") is True
    ]
    fingerprint_mismatch_rows = [
        row
        for row in rows
        if "r4_preflight_row_fingerprint_missing_or_mismatch" in _split_blockers(row.get("blockers"))
    ]
    operator_review_surface_ready_rows = [
        row for row in rows if row.get("operator_review_surface_ready") is True
    ]
    row_pending_fields = [set(_split_blockers(row.get("operator_manual_pending_fields"))) for row in rows]
    manual_pending_field_counts = {
        "operator_decision": sum(1 for fields in row_pending_fields if "operator_decision" in fields),
        "coordinate_fetch_approved": sum(
            1 for fields in row_pending_fields if "coordinate_fetch_approved" in fields
        ),
        "source_url_reviewed": sum(1 for fields in row_pending_fields if "source_url_reviewed" in fields),
        "staging_destination_reviewed": sum(
            1 for fields in row_pending_fields if "staging_destination_reviewed" in fields
        ),
        "license_ok": sum(1 for fields in row_pending_fields if "license_ok" in fields),
        "biological_assembly_reviewed": sum(
            1 for fields in row_pending_fields if "biological_assembly_reviewed" in fields
        ),
        "execute_command_reviewed": sum(
            1 for fields in row_pending_fields if "execute_command_reviewed" in fields
        ),
        "post_fetch_validation_required": sum(
            1 for fields in row_pending_fields if "post_fetch_validation_required" in fields
        ),
        "reviewer": sum(1 for fields in row_pending_fields if "reviewer" in fields),
        "reviewed_at_utc": sum(1 for fields in row_pending_fields if "reviewed_at_utc" in fields),
        "approval_token": sum(1 for fields in row_pending_fields if "approval_token" in fields),
    }

    blockers: list[str] = []
    if not r4_present:
        blockers.append("coordinate_fetch_r4_preflight_missing")
    if r4_summary.get("status") != "refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready":
        blockers.append("coordinate_fetch_r4_preflight_not_ready")
    if not receipt_present:
        blockers.append("receipt_csv_missing")
    if missing_columns:
        blockers.append("receipt_columns_missing:" + ",".join(missing_columns))
    if missing_review_ids:
        blockers.append("required_r4_review_receipts_missing")
    if unexpected_review_ids:
        blockers.append("unexpected_r4_review_receipts_present")
    if duplicate_review_ids:
        blockers.append("duplicate_r4_review_receipts_present")
    if blocked_rows:
        blockers.append("blocked_receipt_rows_present")

    ready = bool(
        r4_present
        and receipt_present
        and not blockers
        and len(passed_rows) == len(r4_by_id)
        and len(r4_by_id) > 0
    )
    summary = {
        "packet_type": "refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt",
        "status": (
            "refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready"
            if ready
            else "blocked_refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt"
        ),
        "operator_receipt_ready": ready,
        "receipt_csv": _display(receipt_csv, root=root_path),
        "receipt_csv_present": receipt_present,
        "receipt_row_count": len(raw_rows),
        "r4_preflight": _display(r4_preflight_json, root=root_path),
        "r4_preflight_present": r4_present,
        "r4_preflight_ready": bool(r4_summary.get("r4_preflight_ready") is True),
        "r4_preflight_status": _text(r4_summary.get("status")),
        "required_r4_review_count": len(r4_by_id),
        "missing_required_r4_review_count": len(missing_review_ids),
        "missing_required_r4_review_ids": missing_review_ids,
        "unexpected_r4_review_count": len(unexpected_review_ids),
        "unexpected_r4_review_ids": unexpected_review_ids,
        "duplicate_r4_review_id_count": len(duplicate_review_ids),
        "duplicate_r4_review_ids": duplicate_review_ids,
        "r4_preflight_row_fingerprint_required": True,
        "r4_preflight_row_fingerprint_verified_count": len(fingerprint_verified_rows),
        "r4_preflight_row_fingerprint_mismatch_count": len(fingerprint_mismatch_rows),
        "operator_review_surface_ready_count": len(operator_review_surface_ready_rows),
        "operator_review_surface_blocked_count": len(rows) - len(operator_review_surface_ready_rows),
        "source_url_present_count": sum(1 for row in rows if _text(row.get("source_url_primary"))),
        "staging_destination_path_present_count": sum(
            1 for row in rows if _text(row.get("staging_destination_path"))
        ),
        "execute_command_present_count": sum(1 for row in rows if _text(row.get("execute_command"))),
        "pass_row_count": len(passed_rows),
        "blocked_row_count": len(blocked_rows),
        "approved_fetch_count": sum(1 for row in passed_rows if _bool(row.get("coordinate_fetch_approved"))),
        "source_url_reviewed_count": sum(1 for row in passed_rows if _bool(row.get("source_url_reviewed"))),
        "license_ok_count": sum(1 for row in passed_rows if _bool(row.get("license_ok"))),
        "biological_assembly_reviewed_count": sum(
            1 for row in passed_rows if _bool(row.get("biological_assembly_reviewed"))
        ),
        "post_fetch_validation_required_count": sum(
            1 for row in passed_rows if _bool(row.get("post_fetch_validation_required"))
        ),
        "receipt_operator_decision_pending_count": manual_pending_field_counts["operator_decision"],
        "receipt_coordinate_fetch_approval_pending_count": manual_pending_field_counts[
            "coordinate_fetch_approved"
        ],
        "receipt_source_url_review_pending_count": manual_pending_field_counts["source_url_reviewed"],
        "receipt_staging_destination_review_pending_count": manual_pending_field_counts[
            "staging_destination_reviewed"
        ],
        "receipt_license_review_pending_count": manual_pending_field_counts["license_ok"],
        "receipt_biological_assembly_review_pending_count": manual_pending_field_counts[
            "biological_assembly_reviewed"
        ],
        "receipt_execute_command_review_pending_count": manual_pending_field_counts[
            "execute_command_reviewed"
        ],
        "receipt_post_fetch_validation_review_pending_count": manual_pending_field_counts[
            "post_fetch_validation_required"
        ],
        "receipt_reviewer_pending_count": manual_pending_field_counts["reviewer"],
        "receipt_reviewed_at_pending_count": manual_pending_field_counts["reviewed_at_utc"],
        "receipt_approval_token_pending_count": manual_pending_field_counts["approval_token"],
        "receipt_manual_field_pending_count": sum(
            _int(row.get("operator_manual_pending_field_count")) for row in rows
        ),
        "first_blocked_review_id": _text(first_blocked.get("r4_review_id")),
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_blocked_pose_id": _text(first_blocked.get("pose_id")),
        "first_blocked_row_blockers": _split_blockers(first_blocked.get("blockers")),
        "most_common_row_blocker": _most_common_blocker(blocked_rows),
        "approval_token_required": APPROVAL_TOKEN,
        "execute_command": EXECUTE_COMMAND,
        "authorized_for_external_download": ready,
        "download_executed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "external_state_mutated": False,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            f"Receipt ready; run `{EXECUTE_COMMAND}` only in an operator-approved execution context, "
            "then rebuild coordinate intake validation and metric source materialization readiness."
            if ready
            else f"Fill all {len(raw_rows)} coordinate-fetch receipt rows "
            f"(operator_review_surface_ready_count={len(operator_review_surface_ready_rows)}, "
            f"receipt_manual_field_pending_count="
            f"{sum(_int(row.get('operator_manual_pending_field_count')) for row in rows)}, "
            f"fingerprint_verified_count={len(fingerprint_verified_rows)}) with approve_coordinate_fetch, "
            f"reviewed source/license/assembly fields, reviewer, timestamp, and {APPROVAL_TOKEN}; "
            "keep claim and canonical intake promotion flags false."
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
        "# R9 Statistical Support Coordinate Fetch Operator Receipt",
        "",
        f"- status: `{summary['status']}`",
        f"- operator_receipt_ready: `{summary['operator_receipt_ready']}`",
        f"- rows pass/blocked/total: `{summary['pass_row_count']}/{summary['blocked_row_count']}/{summary['receipt_row_count']}`",
        f"- required_r4_review_count: `{summary['required_r4_review_count']}`",
        "- r4_preflight_row_fingerprint_verified/mismatch: "
        f"`{summary['r4_preflight_row_fingerprint_verified_count']}/"
        f"{summary['r4_preflight_row_fingerprint_mismatch_count']}`",
        "- operator_review_surface_ready/blocked: "
        f"`{summary['operator_review_surface_ready_count']}/"
        f"{summary['operator_review_surface_blocked_count']}`",
        f"- source_url_present_count: `{summary['source_url_present_count']}`",
        f"- staging_destination_path_present_count: `{summary['staging_destination_path_present_count']}`",
        f"- execute_command_present_count: `{summary['execute_command_present_count']}`",
        f"- receipt_manual_field_pending_count: `{summary['receipt_manual_field_pending_count']}`",
        f"- approval_token_required: `{summary['approval_token_required']}`",
        f"- authorized_for_external_download: `{summary['authorized_for_external_download']}`",
        f"- first_blocked_review_id: `{summary['first_blocked_review_id']}`",
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
            "| review | target | pose | status | blockers | source | destination |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| `{row['r4_review_id']}` | `{row['target_id']}` | `{row['pose_id']}` | "
            f"`{row['row_status']}` | `{row['blockers']}` | `{row['source_url_primary']}` | "
            f"`{row['staging_destination_path']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Build R9 statistical-support coordinate fetch operator receipt gate."
    )
    parser.add_argument("--receipt-csv", default=DEFAULT_RECEIPT_CSV)
    parser.add_argument("--r4-preflight-json", default=DEFAULT_R4_PREFLIGHT_JSON)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    root = Path(args.root)
    payload = build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt(
        receipt_csv=args.receipt_csv,
        r4_preflight_json=args.r4_preflight_json,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
