#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_IDENTITY_KIT_JSON = "casp17/casp17_competitive_floor_identity_unlock_kit_current.json"
DEFAULT_FILE_SOURCE_PLAN_JSON = "casp17/casp17_competitive_floor_file_source_plan_current.json"
DEFAULT_VALUE_ENTRY_PLAN_JSON = "casp17/casp17_competitive_floor_value_entry_plan_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_execution_board_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_execution_board_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_EXECUTION_BOARD.md"

BOARD_COLUMNS = [
    "dropzone_id",
    "operator_priority",
    "row_rank",
    "scope",
    "row_execution_status",
    "identity_status",
    "identity_blockers",
    "proposed_target_id",
    "file_action_count",
    "file_waiting_on_identity_count",
    "file_awaiting_source_path_count",
    "file_ready_for_import_count",
    "file_already_imported_count",
    "file_blocked_count",
    "value_action_count",
    "value_waiting_on_identity_count",
    "value_ready_from_identity_kit_count",
    "value_awaiting_value_count",
    "value_awaiting_clearance_count",
    "value_awaiting_ref_count",
    "value_ready_for_import_count",
    "value_blocked_count",
    "ready_action_count",
    "blocked_action_count",
    "next_action",
    "claim_boundary",
]
CLAIM_BOUNDARY = (
    "Local competitive-floor execution board only. It aggregates existing identity, file-source, and value-entry "
    "plans into row-level next actions. It does not choose targets, clear no-leak provenance, fetch native "
    "structures, score native accuracy, run predictors, mutate row_fill.csv, apply imports, or submit to CASP."
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


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], *, fieldnames: list[str] | None = None) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved = list(fieldnames or [])
    for row in rows:
        for key in row:
            if key not in resolved:
                resolved.append(key)
    if not resolved:
        resolved = BOARD_COLUMNS
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=resolved, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _group(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        dropzone_id = _text(row.get("dropzone_id"))
        if dropzone_id:
            grouped[dropzone_id].append(row)
    return grouped


def _status_counts(rows: list[dict[str, Any]], key: str) -> Counter[str]:
    return Counter(_text(row.get(key)) for row in rows)


def _row_execution_status(identity_status: str, file_counts: Counter[str], value_counts: Counter[str]) -> str:
    if identity_status == "blocked_identity":
        return "blocked_identity"
    if identity_status != "ready_for_import":
        return "awaiting_identity"
    if file_counts["blocked_identity"] or value_counts["blocked_identity"]:
        return "blocked_identity"
    if any(status.startswith("blocked") for status in file_counts if status):
        return "blocked_file_source"
    if any(status.startswith("blocked") for status in value_counts if status):
        return "blocked_value"
    if value_counts["ready_from_identity_kit"]:
        return "ready_for_identity_apply"
    if file_counts["awaiting_source_path"]:
        return "awaiting_file_sources"
    if value_counts["awaiting_value"] or value_counts["awaiting_clearance"] or value_counts["awaiting_evidence_ref"]:
        return "awaiting_values"
    if file_counts["ready_for_import"] or value_counts["ready_for_import"]:
        return "ready_for_evidence_import"
    if file_counts["already_imported"] and value_counts["ready_for_import"] == 0:
        return "ready_for_intake"
    return "ready_for_review"


def _next_action(status: str, identity: dict[str, Any], files: list[dict[str, Any]], values: list[dict[str, Any]]) -> str:
    if status in {"awaiting_identity", "blocked_identity"}:
        return _text(identity.get("next_action")) or "fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance"
    for row in values + files:
        if status == "ready_for_identity_apply" and _text(row.get("value_entry_status")) == "ready_from_identity_kit":
            return _text(row.get("next_action"))
        if status == "awaiting_file_sources" and _text(row.get("file_source_status")) == "awaiting_source_path":
            return _text(row.get("next_action"))
        if status == "awaiting_values" and _text(row.get("value_entry_status")).startswith("awaiting_"):
            return _text(row.get("next_action"))
        if status == "blocked_file_source" and _text(row.get("file_source_status")).startswith("blocked"):
            return _text(row.get("next_action"))
        if status == "blocked_value" and _text(row.get("value_entry_status")).startswith("blocked"):
            return _text(row.get("next_action"))
        if status == "ready_for_evidence_import" and (
            _text(row.get("file_source_status")) == "ready_for_import"
            or _text(row.get("value_entry_status")) == "ready_for_import"
        ):
            return _text(row.get("next_action"))
    return "review this row's competitive-floor evidence state"


def _sort_key(row: dict[str, Any]) -> tuple[int, str]:
    return _int(row.get("operator_priority")) or _int(row.get("row_rank")), _text(row.get("dropzone_id"))


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    identity_payload = _read_json(args.identity_kit_json)
    file_payload = _read_json(args.file_source_plan_json)
    value_payload = _read_json(args.value_entry_plan_json)
    identity_rows = _rows(identity_payload)
    file_rows = _rows(file_payload)
    value_rows = _rows(value_payload)
    file_by_dropzone = _group(file_rows)
    value_by_dropzone = _group(value_rows)
    dropzone_ids = sorted(
        {
            _text(row.get("dropzone_id"))
            for row in identity_rows + file_rows + value_rows
            if _text(row.get("dropzone_id"))
        }
    )
    identity_by_dropzone = {_text(row.get("dropzone_id")): row for row in identity_rows if _text(row.get("dropzone_id"))}
    board_rows: list[dict[str, Any]] = []
    for dropzone_id in dropzone_ids:
        identity = identity_by_dropzone.get(dropzone_id, {"dropzone_id": dropzone_id})
        files = file_by_dropzone.get(dropzone_id, [])
        values = value_by_dropzone.get(dropzone_id, [])
        file_counts = _status_counts(files, "file_source_status")
        value_counts = _status_counts(values, "value_entry_status")
        identity_status = _text(identity.get("identity_status")) or "missing_identity"
        status = _row_execution_status(identity_status, file_counts, value_counts)
        ready_count = (
            file_counts["ready_for_import"]
            + file_counts["already_imported"]
            + value_counts["ready_from_identity_kit"]
            + value_counts["ready_for_import"]
        )
        blocked_count = (
            file_counts["waiting_on_identity"]
            + file_counts["awaiting_source_path"]
            + value_counts["waiting_on_identity"]
            + value_counts["awaiting_value"]
            + value_counts["awaiting_clearance"]
            + value_counts["awaiting_evidence_ref"]
            + sum(count for key, count in file_counts.items() if key.startswith("blocked"))
            + sum(count for key, count in value_counts.items() if key.startswith("blocked"))
        )
        board_rows.append(
            {
                "dropzone_id": dropzone_id,
                "operator_priority": _int(identity.get("operator_priority")),
                "row_rank": _int(identity.get("row_rank")),
                "scope": _text(identity.get("scope")),
                "row_execution_status": status,
                "identity_status": identity_status,
                "identity_blockers": _text(identity.get("blockers")),
                "proposed_target_id": _text(identity.get("proposed_target_id")),
                "file_action_count": len(files),
                "file_waiting_on_identity_count": file_counts["waiting_on_identity"],
                "file_awaiting_source_path_count": file_counts["awaiting_source_path"],
                "file_ready_for_import_count": file_counts["ready_for_import"],
                "file_already_imported_count": file_counts["already_imported"],
                "file_blocked_count": sum(count for key, count in file_counts.items() if key.startswith("blocked")),
                "value_action_count": len(values),
                "value_waiting_on_identity_count": value_counts["waiting_on_identity"],
                "value_ready_from_identity_kit_count": value_counts["ready_from_identity_kit"],
                "value_awaiting_value_count": value_counts["awaiting_value"],
                "value_awaiting_clearance_count": value_counts["awaiting_clearance"],
                "value_awaiting_ref_count": value_counts["awaiting_evidence_ref"],
                "value_ready_for_import_count": value_counts["ready_for_import"],
                "value_blocked_count": sum(count for key, count in value_counts.items() if key.startswith("blocked")),
                "ready_action_count": ready_count,
                "blocked_action_count": blocked_count,
                "next_action": _next_action(status, identity, files, values),
                "claim_boundary": CLAIM_BOUNDARY,
            }
        )
    board_rows.sort(key=_sort_key)
    by_status = Counter(str(row["row_execution_status"]) for row in board_rows)
    first_open = next((row for row in board_rows if row["row_execution_status"] != "ready_for_review"), board_rows[0] if board_rows else {})
    if not board_rows:
        board_status = "ready"
    elif by_status["blocked_identity"] or by_status["blocked_file_source"] or by_status["blocked_value"]:
        board_status = "blocked"
    elif by_status["awaiting_identity"]:
        board_status = "awaiting_identity"
    elif by_status["ready_for_identity_apply"]:
        board_status = "ready_for_identity_apply"
    elif by_status["awaiting_file_sources"]:
        board_status = "awaiting_file_sources"
    elif by_status["awaiting_values"]:
        board_status = "awaiting_values"
    elif by_status["ready_for_evidence_import"]:
        board_status = "ready_for_evidence_import"
    else:
        board_status = "ready_for_review"
    summary = {
        "packet_type": "casp17_competitive_floor_execution_board",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "execution_board_status": board_status,
        "identity_kit_json": _artifact(args.identity_kit_json),
        "file_source_plan_json": _artifact(args.file_source_plan_json),
        "value_entry_plan_json": _artifact(args.value_entry_plan_json),
        "row_count": len(board_rows),
        "awaiting_identity_row_count": by_status["awaiting_identity"],
        "ready_for_identity_apply_row_count": by_status["ready_for_identity_apply"],
        "awaiting_file_source_row_count": by_status["awaiting_file_sources"],
        "awaiting_value_row_count": by_status["awaiting_values"],
        "ready_for_evidence_import_row_count": by_status["ready_for_evidence_import"],
        "blocked_row_count": by_status["blocked_identity"] + by_status["blocked_file_source"] + by_status["blocked_value"],
        "total_file_action_count": sum(_int(row.get("file_action_count")) for row in board_rows),
        "total_value_action_count": sum(_int(row.get("value_action_count")) for row in board_rows),
        "total_ready_action_count": sum(_int(row.get("ready_action_count")) for row in board_rows),
        "total_blocked_action_count": sum(_int(row.get("blocked_action_count")) for row in board_rows),
        "first_open_dropzone_id": _text(first_open.get("dropzone_id")),
        "first_open_status": _text(first_open.get("row_execution_status")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "identity_kit_status": _text(_summary(identity_payload).get("identity_unlock_status")),
        "file_source_plan_status": _text(_summary(file_payload).get("file_source_status")),
        "value_entry_plan_status": _text(_summary(value_payload).get("value_entry_status")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": board_rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Execution Board",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- execution_board_status: `{summary['execution_board_status']}`",
        f"- rows: `{summary['row_count']}`",
        f"- row states identity/apply/file/value/import/blocked: `{summary['awaiting_identity_row_count']}/{summary['ready_for_identity_apply_row_count']}/{summary['awaiting_file_source_row_count']}/{summary['awaiting_value_row_count']}/{summary['ready_for_evidence_import_row_count']}/{summary['blocked_row_count']}`",
        f"- file/value actions: `{summary['total_file_action_count']}/{summary['total_value_action_count']}`",
        f"- ready/blocked actions: `{summary['total_ready_action_count']}/{summary['total_blocked_action_count']}`",
        f"- source statuses identity/file/value: `{summary['identity_kit_status'] or '-'}` `{summary['file_source_plan_status'] or '-'}` `{summary['value_entry_plan_status'] or '-'}`",
        f"- first open: `{summary['first_open_dropzone_id'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Row Board",
        "",
        "| priority | dropzone | status | identity | target | files wait/source/ready/blocked | values wait/apply/await/ready/blocked | next action |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        value_awaiting = (
            _int(row["value_awaiting_value_count"])
            + _int(row["value_awaiting_clearance_count"])
            + _int(row["value_awaiting_ref_count"])
        )
        lines.append(
            f"| {row['operator_priority']} | `{row['dropzone_id']}` | `{row['row_execution_status']}` | "
            f"`{row['identity_status']}` | `{row['proposed_target_id'] or '-'}` | "
            f"`{row['file_waiting_on_identity_count']}/{row['file_awaiting_source_path_count']}/{row['file_ready_for_import_count']}/{row['file_blocked_count']}` | "
            f"`{row['value_waiting_on_identity_count']}/{row['value_ready_from_identity_kit_count']}/{value_awaiting}/{row['value_ready_for_import_count']}/{row['value_blocked_count']}` | "
            f"{row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `ready` | - | - | `0/0/0/0` | `0/0/0/0/0` | no execution rows |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], fieldnames=BOARD_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a row-level CASP17 competitive-floor execution board.")
    parser.add_argument("--identity-kit-json", default=DEFAULT_IDENTITY_KIT_JSON)
    parser.add_argument("--file-source-plan-json", default=DEFAULT_FILE_SOURCE_PLAN_JSON)
    parser.add_argument("--value-entry-plan-json", default=DEFAULT_VALUE_ENTRY_PLAN_JSON)
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
