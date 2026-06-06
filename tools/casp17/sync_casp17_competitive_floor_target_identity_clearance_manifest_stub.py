#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WORKORDER_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_workorder_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_manifest_sync_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_manifest_sync_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_MANIFEST_SYNC.md"

PROVENANCE_TO_MANIFEST_COLUMNS = [
    "benchmark_id",
    "target_id",
    "scope",
    "split",
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
SYNC_COLUMNS = [
    "target_id",
    "sync_status",
    "provenance_status",
    "manifest_status",
    "provenance_template_csv",
    "manifest_stub_csv",
    "changed_field_count",
    "applied_field_count",
    "blockers",
    "next_action",
]
CLEAR_VALUES = {"cleared", "no_leak", "ready_for_row_fill", "internal_no_leak", "true", "yes"}
TRUE_VALUES = {"1", "true", "yes", "y"}
FALSE_VALUES = {"0", "false", "no", "n"}
CLAIM_BOUNDARY = (
    "Local competitive-floor target identity clearance manifest sync only. It copies already-cleared provenance "
    "fields into the matching per-target manifest stub when --apply is explicitly provided. It preserves "
    "prediction/native paths, does not fetch native structures, does not clear no-leak provenance, does not choose "
    "targets, does not score native accuracy, and does not submit to CASP."
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


def _contains_placeholder(value: Any) -> bool:
    text = _text(value)
    upper = text.upper()
    return not text or upper.startswith("REQUIRED") or "REQUIRED_" in upper or "YYYY-MM-DD" in upper


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


def _read_csv_one(path_like: str | Path) -> tuple[dict[str, str], list[str], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return {}, [], [f"{path.name}_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    blockers: list[str] = []
    if not fieldnames:
        blockers.append(f"{path.name}_header_missing")
    if not rows:
        blockers.append(f"{path.name}_empty")
    if len(rows) > 1:
        blockers.append(f"{path.name}_multiple_rows")
    return (rows[0] if rows else {}), fieldnames, blockers


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


def _provenance_blockers(row: dict[str, str], target_id: str, fieldnames: list[str]) -> list[str]:
    blockers: list[str] = []
    missing_columns = [column for column in PROVENANCE_TO_MANIFEST_COLUMNS if column not in fieldnames]
    if missing_columns:
        blockers.append("provenance_required_columns_missing:" + ",".join(missing_columns))
    if _text(row.get("target_id")).upper() != target_id:
        blockers.append("provenance_target_id_mismatch")
    for column in ["benchmark_id", "target_id", "scope", "split", "prediction_method"]:
        if _contains_placeholder(row.get(column)):
            blockers.append(f"{column}_required")
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


def _manifest_blockers(row: dict[str, str], target_id: str, fieldnames: list[str]) -> list[str]:
    blockers: list[str] = []
    missing_columns = [column for column in MANIFEST_COLUMNS if column not in fieldnames]
    if missing_columns:
        blockers.append("manifest_required_columns_missing:" + ",".join(missing_columns))
    if _text(row.get("target_id")).upper() != target_id:
        blockers.append("manifest_target_id_mismatch")
    for column in ["prediction_pdb", "native_pdb"]:
        if _contains_placeholder(row.get(column)):
            blockers.append(f"manifest_{column}_required")
    return blockers


def _next_action(status: str) -> str:
    if status == "ready_to_sync":
        return "review this plan, then rerun with --apply to copy cleared provenance fields into the manifest stub"
    if status == "synced":
        return "rerun the workorder audit and promotion plan"
    if status == "awaiting_provenance":
        return "complete the no-leak provenance template before syncing the manifest stub"
    return "resolve manifest/provenance sync blockers"


def _sync_row(workorder_row: dict[str, Any], apply: bool) -> dict[str, Any]:
    target_id = _text(workorder_row.get("target_id")).upper()
    provenance_path = _text(workorder_row.get("provenance_template_csv"))
    manifest_path = _text(workorder_row.get("manifest_stub_csv"))
    provenance, provenance_fields, provenance_file_blockers = _read_csv_one(provenance_path)
    manifest, manifest_fields, manifest_file_blockers = _read_csv_one(manifest_path)
    provenance_blockers = list(provenance_file_blockers)
    manifest_blockers = list(manifest_file_blockers)
    if not provenance_file_blockers:
        provenance_blockers.extend(_provenance_blockers(provenance, target_id, provenance_fields))
    if not manifest_file_blockers:
        manifest_blockers.extend(_manifest_blockers(manifest, target_id, manifest_fields))
    provenance_status = "ready" if not provenance_blockers else "blocked"
    manifest_status = "present" if not manifest_blockers else "blocked"
    blockers = [*provenance_blockers, *manifest_blockers]
    changed_fields = [
        column
        for column in PROVENANCE_TO_MANIFEST_COLUMNS
        if _text(provenance.get(column)) != _text(manifest.get(column))
    ]
    if blockers:
        status = "awaiting_provenance" if provenance_blockers and not manifest_file_blockers else "blocked"
    elif changed_fields:
        status = "ready_to_sync"
    else:
        status = "synced"
    applied_count = 0
    if apply and status == "ready_to_sync":
        updated = dict(manifest)
        for column in PROVENANCE_TO_MANIFEST_COLUMNS:
            updated[column] = _text(provenance.get(column))
        _write_csv(manifest_path, [updated], manifest_fields or MANIFEST_COLUMNS)
        applied_count = len(changed_fields)
        manifest_status = "synced"
        status = "synced"
    return {
        "target_id": target_id,
        "sync_status": status,
        "provenance_status": provenance_status,
        "manifest_status": manifest_status,
        "provenance_template_csv": provenance_path,
        "manifest_stub_csv": manifest_path,
        "changed_field_count": len(changed_fields),
        "applied_field_count": applied_count,
        "blockers": ",".join(dict.fromkeys(blockers)),
        "next_action": _next_action(status),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    workorder_payload = _read_json(args.workorder_json)
    workorder_summary = _summary(workorder_payload)
    rows = [_sync_row(row, args.apply) for row in _rows(workorder_payload)]
    by_status = Counter(_text(row.get("sync_status")) for row in rows)
    if not rows:
        sync_status = "missing_workorders"
    elif by_status["blocked"]:
        sync_status = "blocked"
    elif by_status["ready_to_sync"]:
        sync_status = "ready_to_sync"
    elif by_status["awaiting_provenance"]:
        sync_status = "awaiting_provenance"
    elif by_status["synced"] == len(rows):
        sync_status = "synced"
    else:
        sync_status = "blocked"
    first_open = next((row for row in rows if row["sync_status"] != "synced"), rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_competitive_floor_target_identity_clearance_manifest_sync",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "clearance_manifest_sync_status": sync_status,
        "apply_mode": "applied" if args.apply else "dry_run",
        "workorder_json": _artifact(args.workorder_json),
        "clearance_workorder_status": _text(workorder_summary.get("clearance_workorder_status")),
        "sync_row_count": len(rows),
        "ready_to_sync_count": by_status["ready_to_sync"],
        "awaiting_provenance_count": by_status["awaiting_provenance"],
        "blocked_count": by_status["blocked"],
        "synced_count": by_status["synced"],
        "changed_field_count": sum(_int(row.get("changed_field_count")) for row in rows),
        "applied_field_count": sum(_int(row.get("applied_field_count")) for row in rows),
        "first_open_target_id": _text(first_open.get("target_id")),
        "first_open_status": _text(first_open.get("sync_status")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Target Identity Clearance Manifest Sync",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- clearance_manifest_sync_status: `{summary['clearance_manifest_sync_status']}`",
        f"- apply_mode: `{summary['apply_mode']}`",
        f"- rows ready/awaiting/blocked/synced: `{summary['ready_to_sync_count']}/{summary['awaiting_provenance_count']}/{summary['blocked_count']}/{summary['synced_count']}`",
        f"- changed/applied fields: `{summary['changed_field_count']}/{summary['applied_field_count']}`",
        f"- first open: `{summary['first_open_target_id'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Sync Rows",
        "",
        "| target | status | provenance | manifest | changed | applied | blockers | next action |",
        "| --- | --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['sync_status']}` | `{row['provenance_status']}` | "
            f"`{row['manifest_status']}` | {row['changed_field_count']} | {row['applied_field_count']} | "
            f"`{row['blockers'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | `missing_workorders` | - | - | 0 | 0 | `workorders_missing` | rerun clearance workorder builder |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], SYNC_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync cleared CASP17 clearance provenance into manifest stubs.")
    parser.add_argument("--workorder-json", default=DEFAULT_WORKORDER_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
