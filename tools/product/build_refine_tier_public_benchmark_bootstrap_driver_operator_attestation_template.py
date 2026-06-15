#!/usr/bin/env python3
"""Build an operator-only attestation template for R9 bootstrap-driver rows."""
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
from tools.product.build_refine_tier_public_benchmark_bootstrap_driver_operator_machine_prefill_template import (
    DEFAULT_PREFILL_CSV,
)
from tools.product.build_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt import (
    APPROVAL_TOKEN,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "config/refine_tier_public_benchmark_bootstrap_driver_operator_attestation_template_current.json"
DEFAULT_OUT_CSV = "config/refine_tier_public_benchmark_bootstrap_driver_operator_attestation_template_current.csv"
DEFAULT_OUT_MD = "docs/refine_tier_public_benchmark_bootstrap_driver_operator_attestation_template_current.md"

OPERATOR_ONLY_FIELDS = [
    "operator_decision",
    "license_ok_reviewed",
    "operator_id",
    "reviewed_at_utc",
    "approval_token",
]
PLACEHOLDER_PREFIXES = ("OPERATOR_FILL", "OPERATOR_CONFIRM")
ACCEPT_DECISIONS = {"accept", "accepted", "approve", "approved", "reviewed_accept"}

CLAIM_BOUNDARY = (
    "R9 bootstrap-driver operator attestation template only extracts the remaining operator-only "
    "decision/license/operator identity/timestamp/approval fields from the machine-prefilled worksheet "
    "and pins each row to a prefill-row SHA-256 fingerprint. It does not edit the canonical worksheet, "
    "accept approvals, write metric payload JSON, copy canonical receipts, promote canonical intake, "
    "change production scoring, run docking/MD, download, upload, email, delete, commit, push, or mutate "
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


def _split_semicolon(value: Any) -> list[str]:
    return [part.strip() for part in _text(value).split(";") if part.strip()]


def _read_csv(path_like: str | Path, *, root: Path) -> tuple[list[dict[str, str]], list[str], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return [], [], False
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader], list(reader.fieldnames or []), True


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


def _row_fingerprint(row: dict[str, Any]) -> str:
    payload = {str(key): _text(value) for key, value in sorted(row.items())}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _operator_only_pending_fields(row: dict[str, Any]) -> list[str]:
    fields = _split_semicolon(row.get("operator_manual_pending_fields"))
    return [field for field in fields if field in OPERATOR_ONLY_FIELDS]


def _row_blockers(row: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    pending = _operator_only_pending_fields(row)
    if pending:
        blockers.append("operator_only_fields_pending")
    if any(_has_placeholder(row.get(field)) for field in OPERATOR_ONLY_FIELDS):
        blockers.append("operator_only_placeholders_unfilled")
    if _text(row.get("operator_decision")).lower() not in ACCEPT_DECISIONS:
        blockers.append("operator_decision_missing_or_not_accept")
    if _bool(row.get("license_ok_reviewed")) is not True:
        blockers.append("license_review_not_true")
    if not _text(row.get("operator_id")) or _has_placeholder(row.get("operator_id")):
        blockers.append("operator_id_missing")
    if not _reviewed_at_valid(row.get("reviewed_at_utc")):
        blockers.append("reviewed_at_utc_missing_or_invalid")
    if _text(row.get("approval_token")) != APPROVAL_TOKEN:
        blockers.append("approval_token_missing_or_invalid")
    return blockers


def _attestation_row(row: dict[str, str], index: int) -> dict[str, Any]:
    blockers = _row_blockers(row)
    pending = _operator_only_pending_fields(row)
    machine_prefilled_fields = [
        field
        for field in (
            "metric_value_reviewed",
            "method_reviewed",
            "input_artifacts_reviewed",
            "input_artifact_sha256s_reviewed",
            "expected_metric_source_artifact_reviewed",
            "payload_schema_reviewed",
        )
        if _bool(row.get(field)) is True
    ]
    return {
        "attestation_id": f"r9_bootstrap_driver_operator_attestation_{index:03d}",
        "worksheet_id": _text(row.get("worksheet_id")),
        "target_id": _text(row.get("target_id")),
        "pose_id": _text(row.get("pose_id")),
        "work_order_id": _text(row.get("work_order_id")),
        "split": _text(row.get("split")),
        "metric_name": _text(row.get("metric_name")),
        "review_surface": _text(row.get("review_surface")),
        "prefill_row_sha256": _row_fingerprint(row),
        "machine_prefilled_field_count": len(machine_prefilled_fields),
        "machine_prefilled_fields": ";".join(machine_prefilled_fields),
        "operator_only_field_count": len(OPERATOR_ONLY_FIELDS),
        "operator_only_fields": ";".join(OPERATOR_ONLY_FIELDS),
        "operator_only_pending_field_count": len(pending),
        "operator_only_pending_fields": ";".join(pending),
        "metric_value_under_review": _text(row.get("metric_value_under_review")),
        "method_under_review": _text(row.get("method_under_review")),
        "expected_metric_source_artifact": _text(row.get("expected_metric_source_artifact")),
        "expected_metric_source_artifact_present": _text(row.get("expected_metric_source_artifact_present")),
        "input_artifact_sha256_verified": _text(row.get("input_artifact_sha256_verified")),
        "operator_decision": _text(row.get("operator_decision")),
        "license_ok_reviewed": _text(row.get("license_ok_reviewed")),
        "operator_id": _text(row.get("operator_id")),
        "reviewed_at_utc": _text(row.get("reviewed_at_utc")),
        "approval_token": _text(row.get("approval_token")),
        "approval_token_required": APPROVAL_TOKEN,
        "operator_attestation": "OPERATOR_CONFIRM_MACHINE_PREFILL_AND_LICENSE_REVIEWED",
        "row_status": "pass" if not blockers else "blocked",
        "blockers": ";".join(blockers),
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
        counter.update(_split_semicolon(row.get("blockers")))
    return counter.most_common(1)[0][0] if counter else ""


def build_refine_tier_public_benchmark_bootstrap_driver_operator_attestation_template(
    *,
    prefill_csv: str | Path = DEFAULT_PREFILL_CSV,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    prefill_rows, prefill_columns, prefill_present = _read_csv(prefill_csv, root=root_path)
    rows = [_attestation_row(row, index) for index, row in enumerate(prefill_rows, start=1)]
    blocked_rows = [row for row in rows if row.get("row_status") != "pass"]
    pass_rows = [row for row in rows if row.get("row_status") == "pass"]
    duplicate_fingerprints = sorted(
        {
            _text(row.get("prefill_row_sha256"))
            for row in rows
            if _text(row.get("prefill_row_sha256"))
            and [other.get("prefill_row_sha256") for other in rows].count(row.get("prefill_row_sha256")) > 1
        }
    )

    blockers: list[str] = []
    if not prefill_present:
        blockers.append("prefill_csv_missing")
    if not prefill_rows:
        blockers.append("prefill_rows_missing")
    if duplicate_fingerprints:
        blockers.append("duplicate_prefill_row_fingerprints_present")

    summary = {
        "packet_type": "refine_tier_public_benchmark_bootstrap_driver_operator_attestation_template",
        "status": (
            "refine_tier_public_benchmark_bootstrap_driver_operator_attestation_template_ready"
            if prefill_present and prefill_rows and not blockers
            else "blocked_refine_tier_public_benchmark_bootstrap_driver_operator_attestation_template"
        ),
        "prefill_csv": _display(prefill_csv, root=root_path),
        "prefill_csv_present": prefill_present,
        "prefill_column_count": len(prefill_columns),
        "attestation_row_count": len(rows),
        "attestation_pass_row_count": len(pass_rows),
        "attestation_blocked_row_count": len(blocked_rows),
        "prefill_row_fingerprint_count": sum(1 for row in rows if _text(row.get("prefill_row_sha256"))),
        "duplicate_prefill_row_fingerprint_count": len(duplicate_fingerprints),
        "operator_only_field_count": len(OPERATOR_ONLY_FIELDS),
        "operator_only_total_field_count": len(rows) * len(OPERATOR_ONLY_FIELDS),
        "operator_only_pending_field_count": sum(_int(row.get("operator_only_pending_field_count")) for row in rows),
        "machine_prefilled_field_count": sum(_int(row.get("machine_prefilled_field_count")) for row in rows),
        "placeholder_row_count": sum(
            1 for row in rows if any(_has_placeholder(row.get(field)) for field in OPERATOR_ONLY_FIELDS)
        ),
        "approval_token_required": APPROVAL_TOKEN,
        "approval_ready": len(rows) > 0 and not blocked_rows,
        "canonical_worksheet_edited": False,
        "payload_write_allowed": False,
        "canonical_receipt_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "production_score_mutation_allowed": False,
        "external_state_mutated": False,
        "first_blocked_attestation_id": _text(blocked_rows[0].get("attestation_id")) if blocked_rows else "",
        "first_blocked_worksheet_id": _text(blocked_rows[0].get("worksheet_id")) if blocked_rows else "",
        "most_common_row_blocker": _most_common_blocker(blocked_rows),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Operator fills the six attestation rows with accept/reject, license review, operator identity, "
            "review timestamp, and the approval token; then merge back into the machine-prefilled candidate "
            "worksheet and rerun staging apply before any payload or receipt write."
        ),
    }
    return {"summary": summary, "rows": rows, "operator_only_fields": OPERATOR_ONLY_FIELDS}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# R9 Bootstrap Driver Operator Attestation Template",
        "",
        f"- status: `{s['status']}`",
        f"- attestation_row_count: `{s['attestation_row_count']}`",
        f"- attestation pass/blocked: `{s['attestation_pass_row_count']}/{s['attestation_blocked_row_count']}`",
        f"- operator_only_pending_field_count: `{s['operator_only_pending_field_count']}`",
        f"- machine_prefilled_field_count: `{s['machine_prefilled_field_count']}`",
        f"- prefill_row_fingerprint_count: `{s['prefill_row_fingerprint_count']}`",
        f"- approval_ready: `{s['approval_ready']}`",
        f"- approval_token_required: `{s['approval_token_required']}`",
        f"- payload_write_allowed: `{s['payload_write_allowed']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        f"- most_common_row_blocker: `{s['most_common_row_blocker']}`",
        "",
        "## Rows",
        "",
        "| attestation | target | pose | metric | status | pending | fingerprint |",
        "| --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['attestation_id']}` | `{row['target_id']}` | `{row['pose_id']}` | "
            f"`{row['metric_name']}` | `{row['row_status']}` | "
            f"`{row['operator_only_pending_field_count']}` | `{row['prefill_row_sha256']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", s["next_required_step"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build R9 bootstrap-driver operator-only attestation template.")
    parser.add_argument("--prefill-csv", default=DEFAULT_PREFILL_CSV)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_refine_tier_public_benchmark_bootstrap_driver_operator_attestation_template(
        prefill_csv=args.prefill_csv,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
