#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_FULFILLMENT_GATE_JSON = "casp17/casp17_strict_blind_source_request_fulfillment_gate_current.json"
DEFAULT_SOURCE_GATE_OPERATOR_PACKET_JSON = (
    "casp17/casp17_strict_blind_source_gate_operator_packet_current.json"
)
DEFAULT_OUT_JSON = "casp17/casp17_strict_blind_source_request_operator_sync_plan_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_strict_blind_source_request_operator_sync_plan_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_SOURCE_REQUEST_OPERATOR_SYNC_PLAN.md"

ACTION_COLUMNS = [
    "action_id",
    "action_status",
    "sync_mode",
    "source_request_id",
    "candidate_target_id",
    "field_key",
    "source_template_csv",
    "destination_operator_csv",
    "source_value",
    "source_evidence_ref",
    "current_operator_value",
    "proposed_operator_value",
    "blocker",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local CASP17 strict-blind source-request operator sync plan only. It maps the first ready source request "
    "template into the source-gate operator CSV, with dry-run as the default mode. It does not approve provenance, "
    "copy prediction files, mutate source manifests, compute CASP metrics, push remotes, or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    if not str(path_like):
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


def _input_blockers(args: argparse.Namespace) -> list[str]:
    blockers = []
    for name in ["fulfillment_gate_json", "source_gate_operator_packet_json"]:
        if not _resolve(getattr(args, name)).exists():
            blockers.append(f"{name}_missing")
    return blockers


def _template_rows(template_csv: str) -> dict[str, dict[str, str]]:
    return {_text(row.get("field_key")): row for row in _read_csv_rows(template_csv) if _text(row.get("field_key"))}


def _ready_fulfillment_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if _text(row.get("ready_for_operator_packet")) == "True"
        and _text(row.get("request_kind")) != "candidate_replacement_required"
    ]


def _operator_csv(summary: dict[str, Any]) -> str:
    return _text(summary.get("operator_csv"))


def _operator_rows_by_field(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = _operator_rows(payload)
    if rows:
        return {_text(row.get("field_key")): row for row in rows if _text(row.get("field_key"))}
    operator_csv = _operator_csv(_summary(payload))
    return {_text(row.get("field_key")): row for row in _read_csv_rows(operator_csv) if _text(row.get("field_key"))}


def _blocker_row(args: argparse.Namespace, fulfillment_summary: dict[str, Any], operator_summary: dict[str, Any]) -> list[dict[str, Any]]:
    blocker = _text(fulfillment_summary.get("first_blocker")) or "source_request_fulfillment_not_ready"
    return [
        {
            "action_id": "source_request_sync_blocker_001",
            "action_status": "blocked_awaiting_source_request_fulfillment",
            "sync_mode": args.mode,
            "source_request_id": _text(fulfillment_summary.get("first_blocked_request_id")),
            "candidate_target_id": _text(fulfillment_summary.get("first_blocked_target_id")),
            "field_key": blocker,
            "source_template_csv": "",
            "destination_operator_csv": _operator_csv(operator_summary),
            "source_value": "",
            "source_evidence_ref": "",
            "current_operator_value": "",
            "proposed_operator_value": "",
            "blocker": blocker,
            "next_action": _text(fulfillment_summary.get("first_next_action")) or "complete source request fulfillment gate first",
        }
    ]


def _build_sync_rows(
    args: argparse.Namespace,
    selected: dict[str, Any],
    operator_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    template_csv = _text(selected.get("operator_template_csv"))
    template_by_field = _template_rows(template_csv)
    operator_summary = _summary(operator_payload)
    operator_by_field = _operator_rows_by_field(operator_payload)
    destination_csv = _operator_csv(operator_summary)
    rows: list[dict[str, Any]] = []
    for index, field_key in enumerate(operator_by_field, start=1):
        source_row = template_by_field.get(field_key, {})
        source_value = _text(source_row.get("operator_value"))
        source_evidence = _text(source_row.get("operator_evidence_ref"))
        current_value = _text(operator_by_field.get(field_key, {}).get("operator_value"))
        blocker = "" if source_value else f"{field_key}_source_value_missing"
        action_status = "ready_to_sync" if not blocker else "blocked_missing_source_value"
        rows.append(
            {
                "action_id": f"source_request_sync_{index:03d}",
                "action_status": action_status,
                "sync_mode": args.mode,
                "source_request_id": _text(selected.get("request_id")),
                "candidate_target_id": _text(selected.get("candidate_target_id")),
                "field_key": field_key,
                "source_template_csv": template_csv,
                "destination_operator_csv": destination_csv,
                "source_value": source_value,
                "source_evidence_ref": source_evidence,
                "current_operator_value": current_value,
                "proposed_operator_value": source_value,
                "blocker": blocker,
                "next_action": "apply value to source-gate operator CSV" if not blocker else "fill source template value first",
            }
        )
    return rows


def _apply_sync(rows: list[dict[str, Any]], operator_payload: dict[str, Any]) -> int:
    destination_csv = _operator_csv(_summary(operator_payload))
    if not destination_csv:
        return 0
    path = _resolve(destination_csv)
    existing_rows = _read_csv_rows(path)
    if not existing_rows:
        return 0
    by_field = {row.get("field_key", ""): row for row in existing_rows}
    applied = 0
    for action in rows:
        if action["action_status"] != "ready_to_sync":
            continue
        row = by_field.get(action["field_key"])
        if not row:
            continue
        row["operator_value"] = action["proposed_operator_value"]
        row["operator_evidence_ref"] = action["source_evidence_ref"]
        action["action_status"] = "applied"
        applied += 1
    _write_csv(path, existing_rows, list(existing_rows[0].keys()))
    return applied


def _status(input_blockers: list[str], rows: list[dict[str, Any]], mode: str, applied_count: int) -> str:
    if input_blockers:
        return "blocked_missing_inputs"
    if not rows or rows[0]["action_status"].startswith("blocked_awaiting"):
        return "awaiting_source_request_fulfillment"
    if any(row["action_status"].startswith("blocked") for row in rows):
        return "blocked_source_request_operator_sync"
    if mode == "apply" and applied_count == len(rows):
        return "source_request_operator_sync_applied"
    if mode == "apply":
        return "source_request_operator_sync_partially_applied"
    return "source_request_operator_sync_ready_dry_run"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    fulfillment_payload = _read_json(args.fulfillment_gate_json)
    operator_payload = _read_json(args.source_gate_operator_packet_json)
    fulfillment_summary = _summary(fulfillment_payload)
    operator_summary = _summary(operator_payload)
    input_blockers = _input_blockers(args)
    ready_rows = [] if input_blockers else _ready_fulfillment_rows(_rows(fulfillment_payload))
    selected = ready_rows[0] if ready_rows else {}
    if input_blockers:
        rows: list[dict[str, Any]] = []
    elif selected:
        rows = _build_sync_rows(args, selected, operator_payload)
    else:
        rows = _blocker_row(args, fulfillment_summary, operator_summary)
    applied_count = _apply_sync(rows, operator_payload) if args.mode == "apply" and selected else 0
    ready_actions = sum(1 for row in rows if row["action_status"] == "ready_to_sync")
    blocked_actions = sum(1 for row in rows if row["action_status"].startswith("blocked"))
    summary = {
        "packet_type": "casp17_strict_blind_source_request_operator_sync_plan",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_request_operator_sync_plan_status": _status(input_blockers, rows, args.mode, applied_count),
        "sync_mode": args.mode,
        "fulfillment_gate_status": _text(fulfillment_summary.get("source_request_fulfillment_gate_status")),
        "ready_request_count": _int(fulfillment_summary.get("ready_request_count")),
        "blocked_request_count": _int(fulfillment_summary.get("blocked_request_count")),
        "selected_request_id": _text(selected.get("request_id")),
        "selected_target_id": _text(selected.get("candidate_target_id")),
        "selected_template_csv": _text(selected.get("operator_template_csv")),
        "destination_operator_csv": _operator_csv(operator_summary),
        "sync_action_count": len(rows) if selected else 0,
        "ready_sync_action_count": ready_actions,
        "blocked_sync_action_count": blocked_actions,
        "applied_sync_action_count": applied_count,
        "first_action_id": _text(rows[0].get("action_id")) if rows else "",
        "first_blocker": _text(rows[0].get("blocker")) if rows else ",".join(input_blockers),
        "first_next_action": _text(rows[0].get("next_action")) if rows else "provide required input JSON files",
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Strict-Blind Source Request Operator Sync Plan",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['source_request_operator_sync_plan_status']}`",
        f"- mode: `{summary['sync_mode']}`",
        f"- fulfillment ready/blocked: `{summary['ready_request_count']}/{summary['blocked_request_count']}`",
        f"- selected request/target: `{summary['selected_request_id'] or '-'}` `{summary['selected_target_id'] or '-'}`",
        f"- actions ready/blocked/applied/total: `{summary['ready_sync_action_count']}/{summary['blocked_sync_action_count']}/{summary['applied_sync_action_count']}/{summary['sync_action_count']}`",
        f"- destination: `{summary['destination_operator_csv'] or '-'}`",
        f"- first blocker: `{summary['first_action_id'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Actions",
        "",
        "| action | status | request | field | source value | current | blocker | next action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['action_id']}` | `{row['action_status']}` | `{row['source_request_id'] or '-'}` | "
            f"`{row['field_key']}` | `{row['source_value'] or '-'}` | `{row['current_operator_value'] or '-'}` | "
            f"`{row['blocker'] or '-'}` | {row['next_action'] or '-'} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | - | - | - | - |")
    lines.extend(["", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ACTION_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 source-request to operator-packet sync plan.")
    parser.add_argument("--fulfillment-gate-json", default=DEFAULT_FULFILLMENT_GATE_JSON)
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
