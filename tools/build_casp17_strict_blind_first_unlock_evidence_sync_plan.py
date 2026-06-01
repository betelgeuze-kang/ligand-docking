#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_REVIEW_GATE_JSON = "casp17/casp17_strict_blind_first_unlock_evidence_review_gate_current.json"
DEFAULT_SOURCE_GATE_OPERATOR_PACKET_JSON = (
    "casp17/casp17_strict_blind_source_gate_operator_packet_current.json"
)
DEFAULT_OUT_JSON = "casp17/casp17_strict_blind_first_unlock_evidence_sync_plan_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_strict_blind_first_unlock_evidence_sync_plan_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_FIRST_UNLOCK_EVIDENCE_SYNC_PLAN.md"

ACTION_COLUMNS = [
    "action_id",
    "action_status",
    "sync_mode",
    "request_id",
    "candidate_target_id",
    "field_key",
    "review_gate_status",
    "destination_operator_csv",
    "destination_field_present",
    "source_operator_value",
    "source_operator_evidence_ref",
    "source_operator_clearance",
    "source_operator_id",
    "current_operator_value",
    "current_operator_evidence_ref",
    "proposed_operator_value",
    "proposed_operator_evidence_ref",
    "blocker",
    "next_action",
]

CLAIM_BOUNDARY = (
    "Local CASP17 strict-blind first-unlock evidence sync plan only. It maps reviewed first-unlock "
    "operator evidence into the source-gate operator CSV, using dry-run by default. It does not approve "
    "provenance, copy prediction files, mutate source manifests, compute CASP metrics, push remotes, "
    "or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: Any) -> str:
    if path_like is None or not str(path_like).strip():
        return ""
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
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


def _operator_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("operator_rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _read_csv_rows(path_like: str | Path) -> list[dict[str, str]]:
    if not _text(path_like):
        return []
    path = _resolve(path_like)
    if not path.exists() or not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


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


def _operator_csv(summary: dict[str, Any]) -> str:
    return _text(summary.get("operator_csv"))


def _operator_rows_by_field(payload: dict[str, Any], operator_csv: str) -> dict[str, dict[str, Any]]:
    csv_rows = _read_csv_rows(operator_csv)
    rows: list[dict[str, Any]] = csv_rows if csv_rows else _operator_rows(payload)
    return {_text(row.get("field_key")): row for row in rows if _text(row.get("field_key"))}


def _input_blockers(args: argparse.Namespace, operator_csv: str) -> list[str]:
    blockers = []
    if not _resolve(args.review_gate_json).exists():
        blockers.append("review_gate_json_missing")
    if not _resolve(args.source_gate_operator_packet_json).exists():
        blockers.append("source_gate_operator_packet_json_missing")
    if _resolve(args.source_gate_operator_packet_json).exists() and not operator_csv:
        blockers.append("source_gate_operator_csv_missing")
    if operator_csv and not _resolve(operator_csv).is_file():
        blockers.append("source_gate_operator_csv_not_found")
    return blockers


def _review_gate_ready(summary: dict[str, Any]) -> bool:
    return _text(summary.get("first_unlock_evidence_review_gate_status")) == (
        "first_unlock_evidence_ready_for_source_gate_sync"
    )


def _action_status(
    review_gate_ready: bool,
    source_row: dict[str, Any],
    destination_row: dict[str, Any] | None,
) -> tuple[str, str]:
    if not review_gate_ready:
        return "blocked_review_gate_not_ready", _text(source_row.get("first_blocker")) or "review_gate_not_ready"
    if destination_row is None:
        return "blocked_destination_field_missing", "destination_field_missing"
    if _text(source_row.get("review_gate_status")) != "field_ready_for_source_gate_sync":
        return "blocked_review_field_not_ready", _text(source_row.get("first_blocker")) or "review_field_not_ready"
    if not _text(source_row.get("template_operator_value")):
        return "blocked_source_operator_value_missing", "source_operator_value_missing"
    if not _text(source_row.get("template_operator_evidence_ref")):
        return "blocked_source_operator_evidence_ref_missing", "source_operator_evidence_ref_missing"
    if not _text(source_row.get("template_operator_clearance")):
        return "blocked_source_operator_clearance_missing", "source_operator_clearance_missing"
    if not _text(source_row.get("template_operator_id")):
        return "blocked_source_operator_id_missing", "source_operator_id_missing"
    return "ready_to_sync", ""


def _next_action(field_key: str, status: str, blocker: str) -> str:
    if status == "ready_to_sync":
        return f"copy reviewed first-unlock value and evidence ref for {field_key} into source-gate operator CSV"
    if status == "blocked_review_gate_not_ready":
        return "complete first-unlock evidence review before syncing into the source gate"
    if status == "blocked_destination_field_missing":
        return f"restore {field_key} row in the source-gate operator CSV"
    if blocker:
        return f"resolve {blocker} for {field_key} before source-gate sync"
    return f"repair {field_key} before source-gate sync"


def _build_rows(
    args: argparse.Namespace,
    review_summary: dict[str, Any],
    review_rows: list[dict[str, Any]],
    operator_payload: dict[str, Any],
    operator_csv: str,
) -> list[dict[str, Any]]:
    destination_by_field = _operator_rows_by_field(operator_payload, operator_csv)
    review_is_ready = _review_gate_ready(review_summary)
    rows = []
    for index, source_row in enumerate(review_rows, start=1):
        field_key = _text(source_row.get("field_key"))
        destination_row = destination_by_field.get(field_key)
        action_status, blocker = _action_status(review_is_ready, source_row, destination_row)
        source_value = _text(source_row.get("template_operator_value"))
        source_evidence = _text(source_row.get("template_operator_evidence_ref"))
        rows.append(
            {
                "action_id": f"first_unlock_evidence_sync_{index:03d}",
                "action_status": action_status,
                "sync_mode": args.mode,
                "request_id": _text(review_summary.get("request_id")),
                "candidate_target_id": _text(review_summary.get("candidate_target_id")),
                "field_key": field_key,
                "review_gate_status": _text(source_row.get("review_gate_status")),
                "destination_operator_csv": operator_csv,
                "destination_field_present": "true" if destination_row is not None else "false",
                "source_operator_value": source_value,
                "source_operator_evidence_ref": source_evidence,
                "source_operator_clearance": _text(source_row.get("template_operator_clearance")),
                "source_operator_id": _text(source_row.get("template_operator_id")),
                "current_operator_value": _text((destination_row or {}).get("operator_value")),
                "current_operator_evidence_ref": _text((destination_row or {}).get("operator_evidence_ref")),
                "proposed_operator_value": source_value,
                "proposed_operator_evidence_ref": source_evidence,
                "blocker": blocker,
                "next_action": _next_action(field_key, action_status, blocker),
            }
        )
    return rows


def _apply_sync(rows: list[dict[str, Any]], operator_csv: str) -> int:
    ready_rows = [row for row in rows if row["action_status"] == "ready_to_sync"]
    if not ready_rows or not operator_csv:
        return 0
    existing_rows = _read_csv_rows(operator_csv)
    if not existing_rows:
        return 0
    by_field = {_text(row.get("field_key")): row for row in existing_rows}
    applied = 0
    for action in ready_rows:
        destination = by_field.get(_text(action.get("field_key")))
        if not destination:
            continue
        destination["operator_value"] = _text(action.get("proposed_operator_value"))
        destination["operator_evidence_ref"] = _text(action.get("proposed_operator_evidence_ref"))
        if "operator_clearance" in destination:
            destination["operator_clearance"] = _text(action.get("source_operator_clearance"))
        if "operator_id" in destination:
            destination["operator_id"] = _text(action.get("source_operator_id"))
        action["action_status"] = "applied"
        applied += 1
    _write_csv(operator_csv, existing_rows, list(existing_rows[0].keys()))
    return applied


def _status(input_blockers: list[str], rows: list[dict[str, Any]], mode: str, applied_count: int) -> str:
    if input_blockers:
        return "blocked_missing_inputs"
    if not rows:
        return "blocked_no_review_rows"
    if any(row["action_status"] == "blocked_review_gate_not_ready" for row in rows):
        return "awaiting_first_unlock_evidence_review"
    if any(row["action_status"].startswith("blocked") for row in rows):
        return "blocked_first_unlock_evidence_sync"
    if mode == "apply" and applied_count == len(rows):
        return "first_unlock_evidence_sync_applied"
    if mode == "apply":
        return "first_unlock_evidence_sync_partially_applied"
    return "first_unlock_evidence_sync_ready_dry_run"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    review_payload = _read_json(args.review_gate_json)
    operator_payload = _read_json(args.source_gate_operator_packet_json)
    review_summary = _summary(review_payload)
    operator_summary = _summary(operator_payload)
    review_rows = _rows(review_payload)
    operator_csv = _operator_csv(operator_summary)
    input_blockers = _input_blockers(args, operator_csv)
    rows = [] if input_blockers else _build_rows(args, review_summary, review_rows, operator_payload, operator_csv)
    applied_count = _apply_sync(rows, operator_csv) if args.mode == "apply" and not input_blockers else 0
    ready_count = sum(1 for row in rows if row["action_status"] == "ready_to_sync")
    blocked_count = sum(1 for row in rows if row["action_status"].startswith("blocked"))
    first_blocked = next((row for row in rows if row["action_status"].startswith("blocked")), rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_strict_blind_first_unlock_evidence_sync_plan",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "first_unlock_evidence_sync_plan_status": _status(input_blockers, rows, args.mode, applied_count),
        "sync_mode": args.mode,
        "review_gate_json": _artifact(args.review_gate_json),
        "source_gate_operator_packet_json": _artifact(args.source_gate_operator_packet_json),
        "review_gate_status": _text(review_summary.get("first_unlock_evidence_review_gate_status")),
        "request_id": _text(review_summary.get("request_id")),
        "candidate_target_id": _text(review_summary.get("candidate_target_id")),
        "destination_operator_csv": _artifact(operator_csv),
        "action_count": len(rows),
        "ready_action_count": ready_count,
        "blocked_action_count": blocked_count,
        "applied_action_count": applied_count,
        "review_ready_field_count": _int(review_summary.get("ready_field_count")),
        "review_blocked_field_count": _int(review_summary.get("blocked_field_count")),
        "first_action_id": _text(first_blocked.get("action_id")),
        "first_blocked_field": _text(first_blocked.get("field_key"))
        if _text(first_blocked.get("action_status")).startswith("blocked")
        else "",
        "first_blocker": _text(first_blocked.get("blocker")) if rows else ",".join(input_blockers),
        "first_next_action": _text(first_blocked.get("next_action")) if rows else "provide required input JSON files",
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Strict-Blind First Unlock Evidence Sync Plan",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['first_unlock_evidence_sync_plan_status']}`",
        f"- mode: `{summary['sync_mode']}`",
        f"- review gate: `{summary['review_gate_status'] or '-'}`",
        f"- request/target: `{summary['request_id'] or '-'}` `{summary['candidate_target_id'] or '-'}`",
        f"- actions ready/blocked/applied/total: `{summary['ready_action_count']}/{summary['blocked_action_count']}/{summary['applied_action_count']}/{summary['action_count']}`",
        f"- review ready/blocked fields: `{summary['review_ready_field_count']}/{summary['review_blocked_field_count']}`",
        f"- destination: `{summary['destination_operator_csv'] or '-'}`",
        f"- first blocker: `{summary['first_action_id'] or '-'}` `{summary['first_blocked_field'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Actions",
        "",
        "| action | status | field | source value | current value | blocker | next action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['action_id']}` | `{row['action_status']}` | `{row['field_key']}` | "
            f"`{row['source_operator_value'] or '-'}` | `{row['current_operator_value'] or '-'}` | "
            f"`{row['blocker'] or '-'}` | {row['next_action'] or '-'} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | - | - | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ACTION_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build CASP17 first-unlock evidence to source-gate operator sync plan."
    )
    parser.add_argument("--review-gate-json", default=DEFAULT_REVIEW_GATE_JSON)
    parser.add_argument("--source-gate-operator-packet-json", default=DEFAULT_SOURCE_GATE_OPERATOR_PACKET_JSON)
    parser.add_argument("--mode", choices=["dry_run", "apply"], default="dry_run")
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
