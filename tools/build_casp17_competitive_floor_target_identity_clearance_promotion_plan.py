#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_AUDIT_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_workorder_audit_current.json"
DEFAULT_CURRENT_TARGET_CSV = "casp17/casp17_target_model_folders_current.csv"
DEFAULT_OUT_MANIFEST_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_promoted_manifest_candidate_current.csv"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_promotion_plan_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_promotion_plan_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_PROMOTION_PLAN.md"

MANIFEST_COLUMNS = [
    "benchmark_id",
    "target_id",
    "scope",
    "split",
    "prediction_pdb",
    "native_pdb",
    "leakage_clearance",
    "prediction_method",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
    "current_casp17_target",
    "operator_clearance",
]
PLAN_COLUMNS = [
    "target_id",
    "promotion_status",
    "audit_status",
    "manifest_stub_csv",
    "out_manifest_csv",
    "benchmark_id",
    "scope",
    "prediction_pdb",
    "native_pdb",
    "blockers",
    "next_action",
]
CLEAR_VALUES = {"cleared", "no_leak", "ready_for_row_fill", "internal_no_leak", "true", "yes"}
TRUE_VALUES = {"1", "true", "yes", "y"}
FALSE_VALUES = {"0", "false", "no", "n"}
CLAIM_BOUNDARY = (
    "Local competitive-floor clearance promotion plan only. It copies audit-passing manifest stubs into a "
    "candidate manifest CSV for operator review. It does not fetch native structures, clear provenance, choose "
    "targets, score native accuracy, mutate the active historical manifest, mutate identity intake files, or "
    "submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_manifest_stub(path_like: str | Path) -> tuple[dict[str, str], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return {}, ["manifest_stub_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    blockers: list[str] = []
    missing = [column for column in MANIFEST_COLUMNS if column not in fieldnames]
    if missing:
        blockers.append("manifest_required_columns_missing:" + ",".join(missing))
    if not rows:
        blockers.append("manifest_stub_empty")
    if len(rows) > 1:
        blockers.append("manifest_stub_multiple_rows")
    return (rows[0] if rows else {}), blockers


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _contains_placeholder(value: Any) -> bool:
    text = _text(value)
    upper = text.upper()
    return not text or upper.startswith("REQUIRED") or "REQUIRED_" in upper or "YYYY-MM-DD" in upper


def _date_or_none(value: Any) -> dt.date | None:
    text = _text(value)
    if not text:
        return None
    for candidate in (text[:10], text):
        try:
            return dt.date.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def _current_targets(path_like: str | Path) -> set[str]:
    return {_text(row.get("target_id")).upper() for row in _read_csv(path_like) if _text(row.get("target_id"))}


def _manifest_blockers(row: dict[str, str], current_targets: set[str], target_id: str) -> list[str]:
    blockers: list[str] = []
    if _text(row.get("target_id")).upper() != target_id:
        blockers.append("manifest_target_id_mismatch")
    if target_id in current_targets:
        blockers.append("current_casp17_target_not_allowed")
    for column in MANIFEST_COLUMNS:
        if _contains_placeholder(row.get(column)):
            blockers.append(f"{column}_required")
    if not _text(row.get("benchmark_id")).startswith("hist_"):
        blockers.append("benchmark_id_must_start_hist")
    if _text(row.get("scope")) not in {"monomer", "complex"}:
        blockers.append("scope_must_be_monomer_or_complex")
    for column in ["prediction_pdb", "native_pdb"]:
        value = _text(row.get(column))
        if value and not _resolve(value).exists():
            blockers.append(f"{column}_not_found")
    if _text(row.get("leakage_clearance")).lower() not in CLEAR_VALUES:
        blockers.append("leakage_clearance_required")
    if _text(row.get("operator_clearance")).lower() not in CLEAR_VALUES:
        blockers.append("operator_clearance_required")
    prediction_date = _date_or_none(row.get("prediction_created_at"))
    native_date = _date_or_none(row.get("native_release_date"))
    if prediction_date is None:
        blockers.append("prediction_created_at_required_iso_date")
    if native_date is None:
        blockers.append("native_release_date_required_iso_date")
    if prediction_date is not None and native_date is not None and prediction_date >= native_date:
        blockers.append("prediction_date_not_before_native_release")
    if _text(row.get("prediction_generated_before_native_release")).lower() not in TRUE_VALUES:
        blockers.append("prediction_generated_before_native_release_required")
    for column in [
        "public_template_or_native_used_for_prediction",
        "other_team_model_used",
        "post_release_information_used",
        "current_casp17_target",
    ]:
        if _text(row.get(column)).lower() not in FALSE_VALUES:
            blockers.append(f"{column}_must_be_false")
    return blockers


def _next_action(status: str) -> str:
    if status == "ready_for_operator_manifest_import":
        return "operator may review this candidate manifest row before importing it into the historical manifest candidate flow"
    if status == "blocked_by_audit":
        return "clear the native/provenance workorder audit before promotion"
    return "fix manifest stub blockers and rerun the promotion plan"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    audit_payload = _read_json(args.audit_json)
    audit_summary = _summary(audit_payload)
    current_targets = _current_targets(args.current_target_csv)
    rows: list[dict[str, Any]] = []
    promoted_manifest_rows: list[dict[str, str]] = []
    for audit in _rows(audit_payload):
        target_id = _text(audit.get("target_id")).upper()
        manifest_row: dict[str, str] = {}
        manifest_blockers: list[str] = []
        if _text(audit.get("audit_status")) != "pass":
            status = "blocked_by_audit"
            manifest_blockers = [token for token in _text(audit.get("blockers")).split(",") if token]
        else:
            manifest_row, manifest_blockers = _read_manifest_stub(audit.get("manifest_stub_csv"))
            manifest_blockers.extend(_manifest_blockers(manifest_row, current_targets, target_id))
            status = "ready_for_operator_manifest_import" if not manifest_blockers else "blocked_manifest_stub"
            if status == "ready_for_operator_manifest_import":
                promoted_manifest_rows.append({column: _text(manifest_row.get(column)) for column in MANIFEST_COLUMNS})
        rows.append(
            {
                "target_id": target_id,
                "promotion_status": status,
                "audit_status": _text(audit.get("audit_status")),
                "manifest_stub_csv": _text(audit.get("manifest_stub_csv")),
                "out_manifest_csv": _artifact(args.out_manifest_csv),
                "benchmark_id": _text(manifest_row.get("benchmark_id")),
                "scope": _text(manifest_row.get("scope")),
                "prediction_pdb": _text(manifest_row.get("prediction_pdb")),
                "native_pdb": _text(manifest_row.get("native_pdb")),
                "blockers": ",".join(dict.fromkeys(manifest_blockers)),
                "next_action": _next_action(status),
            }
        )
    _write_csv(args.out_manifest_csv, promoted_manifest_rows, MANIFEST_COLUMNS)
    by_status = Counter(_text(row.get("promotion_status")) for row in rows)
    first_blocked = next(
        (
            row
            for row in rows
            if _text(row.get("promotion_status")) != "ready_for_operator_manifest_import"
        ),
        rows[0] if rows else {},
    )
    ready_count = by_status["ready_for_operator_manifest_import"]
    if not rows:
        promotion_status = "missing_audit"
    elif ready_count == len(rows):
        promotion_status = "ready_for_operator_manifest_import"
    elif ready_count:
        promotion_status = "partial_ready_for_operator_manifest_import"
    elif by_status["blocked_by_audit"] == len(rows):
        promotion_status = "blocked_by_audit"
    elif by_status["blocked_manifest_stub"] == len(rows):
        promotion_status = "blocked_manifest_stub"
    else:
        promotion_status = "blocked"
    blocked_count = len(rows) - ready_count
    if "audit_pass_count" in audit_summary:
        audit_pass_count = _int(audit_summary.get("audit_pass_count"))
    else:
        audit_pass_count = sum(1 for row in rows if _text(row.get("audit_status")) == "pass")
    summary = {
        "packet_type": "casp17_competitive_floor_target_identity_clearance_promotion_plan",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "clearance_promotion_status": promotion_status,
        "audit_json": _artifact(args.audit_json),
        "audit_status": _text(audit_summary.get("clearance_workorder_audit_status")),
        "audit_pass_count": audit_pass_count,
        "current_target_csv": _artifact(args.current_target_csv),
        "out_manifest_csv": _artifact(args.out_manifest_csv),
        "promotion_row_count": len(rows),
        "promotion_target_count": len(rows),
        "ready_for_operator_manifest_import_count": ready_count,
        "manifest_ready_count": ready_count,
        "blocked_count": blocked_count,
        "blocked_by_audit_count": by_status["blocked_by_audit"],
        "blocked_manifest_stub_count": by_status["blocked_manifest_stub"],
        "promoted_manifest_count": len(promoted_manifest_rows),
        "promoted_manifest_row_count": len(promoted_manifest_rows),
        "first_open_target_id": _text(first_blocked.get("target_id")),
        "first_open_status": _text(first_blocked.get("promotion_status")),
        "first_open_next_action": _text(first_blocked.get("next_action")),
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_blocked_status": _text(first_blocked.get("promotion_status")),
        "first_blocked_next_action": _text(first_blocked.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows, "promoted_manifest_rows": promoted_manifest_rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Target Identity Clearance Promotion Plan",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- clearance_promotion_status: `{summary['clearance_promotion_status']}`",
        f"- audit_status: `{summary['audit_status'] or '-'}`",
        f"- promotion targets: `{summary['promotion_target_count']}`",
        f"- ready/blocked-audit/blocked-manifest: `{summary['ready_for_operator_manifest_import_count']}/{summary['blocked_by_audit_count']}/{summary['blocked_manifest_stub_count']}`",
        f"- promoted manifest rows: `{summary['promoted_manifest_row_count']}`",
        f"- out_manifest_csv: `{summary['out_manifest_csv']}`",
        f"- first blocked: `{summary['first_blocked_target_id'] or '-'}` `{summary['first_blocked_status'] or '-'}`",
        f"- next action: {summary['first_blocked_next_action'] or '-'}",
        "",
        "## Plan Rows",
        "",
        "| target | promotion | audit | manifest stub | blockers | next action |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['promotion_status']}` | `{row['audit_status'] or '-'}` | "
            f"`{row['manifest_stub_csv'] or '-'}` | `{row['blockers'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | `missing_audit` | - | - | `audit_rows_missing` | rerun workorder audit |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], PLAN_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 target identity clearance promotion plan.")
    parser.add_argument("--audit-json", default=DEFAULT_AUDIT_JSON)
    parser.add_argument("--current-target-csv", default=DEFAULT_CURRENT_TARGET_CSV)
    parser.add_argument("--out-manifest-csv", default=DEFAULT_OUT_MANIFEST_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
