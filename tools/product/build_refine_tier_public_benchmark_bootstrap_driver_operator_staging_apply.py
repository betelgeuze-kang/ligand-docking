#!/usr/bin/env python3
"""Preview-only apply gate for R9 bootstrap-driver operator worksheet rows."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_refine_tier_public_benchmark_bootstrap_driver_operator_review_worksheet import (
    DEFAULT_OUT_CSV as DEFAULT_WORKSHEET_CSV,
    DEFAULT_OUT_JSON as DEFAULT_WORKSHEET_JSON,
)
from tools.product.build_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt import (
    APPROVAL_TOKEN,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "config/refine_tier_public_benchmark_bootstrap_driver_operator_staging_apply_current.json"
DEFAULT_OUT_CSV = "config/refine_tier_public_benchmark_bootstrap_driver_operator_staging_apply_current.csv"
DEFAULT_OUT_MD = "docs/refine_tier_public_benchmark_bootstrap_driver_operator_staging_apply_current.md"

PLACEHOLDER_PREFIXES = ("OPERATOR_FILL", "OPERATOR_CONFIRM")
ACCEPT_DECISIONS = {"accept", "accepted", "approve", "approved", "reviewed_accept"}
REQUIRED_COLUMNS = [
    "worksheet_id",
    "target_id",
    "pose_id",
    "work_order_id",
    "split",
    "metric_name",
    "review_surface",
    "metric_value_under_review",
    "method_under_review",
    "expected_metric_source_artifact",
    "expected_metric_source_artifact_present",
    "metric_source_artifact_sha256",
    "payload_validation_status",
    "input_artifacts",
    "input_artifact_sha256s",
    "input_artifact_sha256_verified",
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
    "approval_token_required",
]
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
    "R9 bootstrap-driver operator staging apply is preview-only. It validates the top-driver worksheet "
    "rows before any separate approved procedure may write missing candidate metric-source payloads or "
    "backfill existing payload receipt coverage. It does not write metric payload JSON, copy canonical "
    "receipts, promote canonical intake, change production scoring, run docking/MD, download, upload, "
    "email, delete, commit, push, or mutate external state."
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


def _float(value: Any) -> float | None:
    try:
        return float(_text(value))
    except (TypeError, ValueError):
        return None


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
    return (payload if isinstance(payload, dict) else {}), True


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _operator_pending_fields(row: dict[str, Any]) -> list[str]:
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


def _input_hashes_verified(row: dict[str, Any], *, root: Path) -> bool:
    artifacts = _split_semicolon(row.get("input_artifacts"))
    hashes = _split_semicolon(row.get("input_artifact_sha256s"))
    if not artifacts or len(artifacts) != len(hashes):
        return False
    for artifact, digest in zip(artifacts, hashes):
        if "::" in artifact:
            return False
        path = _resolve(artifact, root=root)
        if not path.is_file() or _sha256_file(path) != digest:
            return False
    return True


def _payload_schema_valid(row: dict[str, Any], *, root: Path) -> bool:
    artifact = _text(row.get("expected_metric_source_artifact"))
    if not artifact:
        return False
    path = _resolve(artifact, root=root)
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    expected_value = _float(row.get("metric_value_under_review"))
    payload_value = _float(payload.get("value"))
    if expected_value is None or payload_value is None or abs(expected_value - payload_value) > 1e-6:
        return False
    return bool(
        _text(payload.get("metric_name")) == _text(row.get("metric_name"))
        and _text(payload.get("target_id")).lower() == _text(row.get("target_id")).lower()
        and _text(payload.get("pose_id")) == _text(row.get("pose_id"))
        and _text(payload.get("method")) == _text(row.get("method_under_review"))
        and _bool(payload.get("license_ok")) is True
        and _int(payload.get("external_engine_calls")) == 0
        and _split_semicolon(row.get("input_artifacts")) == [str(item) for item in payload.get("input_artifacts", [])]
        and _split_semicolon(row.get("input_artifact_sha256s"))
        == [str(item) for item in payload.get("input_artifact_sha256s", [])]
    )


def _payload_preview(row: dict[str, Any]) -> str:
    value = _float(row.get("metric_value_under_review"))
    payload = {
        "metric_name": _text(row.get("metric_name")),
        "target_id": _text(row.get("target_id")),
        "pose_id": _text(row.get("pose_id")),
        "value": value if value is not None else _text(row.get("metric_value_under_review")),
        "method": _text(row.get("method_under_review")),
        "input_artifacts": _split_semicolon(row.get("input_artifacts")),
        "input_artifact_sha256s": _split_semicolon(row.get("input_artifact_sha256s")),
        "operator_id": _text(row.get("operator_id")),
        "reviewed_at_utc": _text(row.get("reviewed_at_utc")),
        "license_ok": True,
        "external_engine_calls": 0,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _row_report(row: dict[str, str], *, root: Path) -> dict[str, Any]:
    review_surface = _text(row.get("review_surface"))
    artifact = _text(row.get("expected_metric_source_artifact"))
    artifact_path = _resolve(artifact, root=root) if artifact else root / "__missing__"
    artifact_present = artifact_path.is_file() if artifact else False
    artifact_sha256 = _sha256_file(artifact_path) if artifact_present else ""
    input_hashes_verified = _bool(row.get("input_artifact_sha256_verified")) and _input_hashes_verified(row, root=root)
    operator_pending = _operator_pending_fields(row)
    payload_schema_valid = _payload_schema_valid(row, root=root) if artifact_present else False
    blockers: list[str] = []

    if any(_has_placeholder(row.get(field)) for field in MANUAL_FIELDS):
        blockers.append("operator_placeholders_unfilled")
    if operator_pending:
        blockers.append("operator_manual_fields_pending")
    if _float(row.get("metric_value_under_review")) is None:
        blockers.append("metric_value_under_review_invalid")
    if not _text(row.get("method_under_review")):
        blockers.append("method_under_review_missing")
    if not input_hashes_verified:
        blockers.append("input_artifact_sha256_verification_failed")
    if _text(row.get("approval_token_required")) != APPROVAL_TOKEN:
        blockers.append("approval_token_required_mismatch")

    if review_surface == "candidate_preview_payload_write_review":
        if artifact_present:
            blockers.append("candidate_metric_source_artifact_already_present")
    elif review_surface == "existing_payload_backfill_receipt_review":
        if not artifact_present:
            blockers.append("existing_metric_source_artifact_missing")
        if _text(row.get("payload_validation_status")) != "pass":
            blockers.append("existing_payload_validation_not_pass")
        if artifact_present and _text(row.get("metric_source_artifact_sha256")) != artifact_sha256:
            blockers.append("existing_metric_source_artifact_sha256_mismatch")
        if artifact_present and not payload_schema_valid:
            blockers.append("existing_payload_schema_revalidation_failed")
    else:
        blockers.append("unknown_review_surface")

    ready = not blockers
    return {
        "worksheet_id": _text(row.get("worksheet_id")),
        "target_id": _text(row.get("target_id")),
        "pose_id": _text(row.get("pose_id")),
        "work_order_id": _text(row.get("work_order_id")),
        "split": _text(row.get("split")),
        "metric_name": _text(row.get("metric_name")),
        "review_surface": review_surface,
        "row_status": "pass" if ready else "blocked",
        "blockers": ";".join(blockers),
        "operator_manual_pending_field_count": len(operator_pending),
        "operator_manual_pending_fields": ";".join(operator_pending),
        "input_artifact_sha256_verified": input_hashes_verified,
        "expected_metric_source_artifact": artifact,
        "expected_metric_source_artifact_present": artifact_present,
        "expected_metric_source_artifact_sha256": artifact_sha256,
        "existing_payload_schema_revalidated": payload_schema_valid,
        "metric_value_under_review": _text(row.get("metric_value_under_review")),
        "method_under_review": _text(row.get("method_under_review")),
        "candidate_payload_write_preview_ready": bool(
            ready and review_surface == "candidate_preview_payload_write_review"
        ),
        "existing_payload_receipt_backfill_preview_ready": bool(
            ready and review_surface == "existing_payload_backfill_receipt_review"
        ),
        "payload_preview_json": _payload_preview(row) if ready else "",
        "payload_write_allowed": False,
        "canonical_receipt_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "production_score_mutation_allowed": False,
        "external_state_mutated": False,
    }


def _most_common_blocker(rows: list[dict[str, Any]]) -> str:
    counter: Counter[str] = Counter()
    for row in rows:
        counter.update(part for part in _split_semicolon(row.get("blockers")) if part)
    return counter.most_common(1)[0][0] if counter else ""


def build_refine_tier_public_benchmark_bootstrap_driver_operator_staging_apply(
    *,
    worksheet_csv: str | Path = DEFAULT_WORKSHEET_CSV,
    worksheet_json: str | Path = DEFAULT_WORKSHEET_JSON,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    worksheet_rows, columns, worksheet_csv_present = _read_csv(worksheet_csv, root=root_path)
    worksheet_packet, worksheet_json_present = _read_json(worksheet_json, root=root_path)
    worksheet_summary = _summary(worksheet_packet)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in columns] if worksheet_csv_present else list(REQUIRED_COLUMNS)
    rows = [_row_report(row, root=root_path) for row in worksheet_rows] if not missing_columns else []
    blocked_rows = [row for row in rows if row["row_status"] != "pass"]
    pass_rows = [row for row in rows if row["row_status"] == "pass"]
    candidate_rows = [row for row in rows if row["review_surface"] == "candidate_preview_payload_write_review"]
    backfill_rows = [row for row in rows if row["review_surface"] == "existing_payload_backfill_receipt_review"]
    first_blocked = blocked_rows[0] if blocked_rows else {}

    blockers: list[str] = []
    if not worksheet_csv_present:
        blockers.append("worksheet_csv_missing")
    if missing_columns:
        blockers.append("worksheet_csv_missing_required_columns:" + ",".join(missing_columns))
    if not worksheet_rows:
        blockers.append("worksheet_rows_missing")
    if not worksheet_json_present:
        blockers.append("worksheet_json_missing")
    if worksheet_json_present and worksheet_summary.get("status") != "refine_tier_public_benchmark_bootstrap_driver_operator_review_worksheet_ready":
        blockers.append("worksheet_json_not_ready")
    if blocked_rows:
        blockers.append("blocked_worksheet_rows_present")

    ready = bool(worksheet_csv_present and worksheet_rows and not missing_columns and not blockers)
    summary = {
        "packet_type": "refine_tier_public_benchmark_bootstrap_driver_operator_staging_apply",
        "status": (
            "refine_tier_public_benchmark_bootstrap_driver_operator_staging_preview_ready"
            if ready
            else "blocked_refine_tier_public_benchmark_bootstrap_driver_operator_staging_apply"
        ),
        "worksheet_csv": _display(worksheet_csv, root=root_path),
        "worksheet_csv_present": worksheet_csv_present,
        "worksheet_json": _display(worksheet_json, root=root_path),
        "worksheet_json_present": worksheet_json_present,
        "worksheet_json_status": _text(worksheet_summary.get("status")),
        "worksheet_row_count": len(worksheet_rows),
        "worksheet_missing_required_column_count": len(missing_columns),
        "worksheet_missing_required_columns": missing_columns,
        "pass_row_count": len(pass_rows),
        "blocked_row_count": len(blocked_rows),
        "candidate_preview_row_count": len(candidate_rows),
        "candidate_payload_write_preview_ready_count": sum(
            1 for row in candidate_rows if row.get("candidate_payload_write_preview_ready") is True
        ),
        "existing_payload_backfill_row_count": len(backfill_rows),
        "existing_payload_receipt_backfill_preview_ready_count": sum(
            1 for row in backfill_rows if row.get("existing_payload_receipt_backfill_preview_ready") is True
        ),
        "input_artifact_sha256_verified_row_count": sum(
            1 for row in rows if row.get("input_artifact_sha256_verified") is True
        ),
        "expected_metric_source_artifact_present_row_count": sum(
            1 for row in rows if row.get("expected_metric_source_artifact_present") is True
        ),
        "existing_payload_schema_revalidated_row_count": sum(
            1 for row in backfill_rows if row.get("existing_payload_schema_revalidated") is True
        ),
        "operator_manual_pending_field_count": sum(
            _int(row.get("operator_manual_pending_field_count")) for row in rows
        ),
        "placeholder_row_count": sum(
            1
            for raw in worksheet_rows
            if any(_has_placeholder(raw.get(field)) for field in MANUAL_FIELDS)
        ),
        "approval_token_required": APPROVAL_TOKEN,
        "payload_write_preview_ready": ready,
        "payload_write_allowed": False,
        "canonical_receipt_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "production_score_mutation_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "first_blocked_worksheet_id": _text(first_blocked.get("worksheet_id")),
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_blocked_pose_id": _text(first_blocked.get("pose_id")),
        "first_blocked_metric_name": _text(first_blocked.get("metric_name")),
        "most_common_row_blocker": _most_common_blocker(blocked_rows),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Preview is ready. A separate operator-approved procedure must still materialize candidate "
            "payload JSON and/or copy backfill receipt coverage before canonical intake or claim gates can move."
            if ready
            else "Fill the six bootstrap-driver worksheet rows with accept decisions, true review flags, "
            f"operator/timestamp, license review, zero-external-engine evidence, and {APPROVAL_TOKEN}; "
            "then rerun this preview before any payload or canonical receipt write."
        ),
    }
    return {"summary": summary, "rows": rows, "required_columns": REQUIRED_COLUMNS}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# R9 Bootstrap Driver Operator Staging Apply Preview",
        "",
        f"- status: `{s['status']}`",
        f"- rows pass/blocked/total: `{s['pass_row_count']}/{s['blocked_row_count']}/{s['worksheet_row_count']}`",
        f"- candidate_payload_write_preview_ready_count: `{s['candidate_payload_write_preview_ready_count']}`",
        "- existing_payload_receipt_backfill_preview_ready_count: "
        f"`{s['existing_payload_receipt_backfill_preview_ready_count']}`",
        f"- input_artifact_sha256_verified_row_count: `{s['input_artifact_sha256_verified_row_count']}`",
        f"- existing_payload_schema_revalidated_row_count: `{s['existing_payload_schema_revalidated_row_count']}`",
        f"- operator_manual_pending_field_count: `{s['operator_manual_pending_field_count']}`",
        f"- placeholder_row_count: `{s['placeholder_row_count']}`",
        f"- approval_token_required: `{s['approval_token_required']}`",
        f"- payload_write_allowed: `{s['payload_write_allowed']}`",
        f"- canonical_receipt_write_allowed: `{s['canonical_receipt_write_allowed']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        f"- most_common_row_blocker: `{s['most_common_row_blocker']}`",
        "",
        "## Blockers",
    ]
    lines.extend(f"- `{blocker}`" for blocker in s["blockers"])
    if not s["blockers"]:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| worksheet | target | pose | metric | surface | status | blockers |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| `{row['worksheet_id']}` | `{row['target_id']}` | `{row['pose_id']}` | "
            f"`{row['metric_name']}` | `{row['review_surface']}` | `{row['row_status']}` | "
            f"`{row['blockers']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", s["next_required_step"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build preview-only R9 bootstrap-driver worksheet apply gate.")
    parser.add_argument("--worksheet-csv", default=DEFAULT_WORKSHEET_CSV)
    parser.add_argument("--worksheet-json", default=DEFAULT_WORKSHEET_JSON)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_refine_tier_public_benchmark_bootstrap_driver_operator_staging_apply(
        worksheet_csv=args.worksheet_csv,
        worksheet_json=args.worksheet_json,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
