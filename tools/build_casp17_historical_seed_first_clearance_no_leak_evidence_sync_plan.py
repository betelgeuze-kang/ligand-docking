#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_REVIEW_GATE_JSON = "casp17/casp17_historical_seed_first_clearance_no_leak_evidence_review_gate_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_first_clearance_no_leak_evidence_sync_plan_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_first_clearance_no_leak_evidence_sync_plan_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_FIRST_CLEARANCE_NO_LEAK_EVIDENCE_SYNC_PLAN.md"

ACTION_COLUMNS = [
    "action_id",
    "action_status",
    "sync_mode",
    "target_id",
    "benchmark_id",
    "field_name",
    "destination_intake_csv",
    "current_operator_value",
    "current_operator_clearance",
    "current_evidence_ref",
    "source_operator_value",
    "source_operator_clearance",
    "source_operator_evidence_ref",
    "proposed_operator_value",
    "proposed_operator_clearance",
    "evidence_ref_handling",
    "blocker",
    "next_action",
]

CLAIM_BOUNDARY = (
    "Local CASP17 first-clearance no-leak evidence sync plan only. It maps reviewed operator "
    "evidence values into the first-clearance no-leak intake, using dry-run by default. It does not "
    "approve provenance, generate evidence, compute CASP metrics, mutate evidence stubs, push remotes, "
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
    if not str(path_like).strip():
        return []
    path = _resolve(path_like)
    if not path.is_file():
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


def _review_ready(summary: dict[str, Any]) -> bool:
    return _text(summary.get("first_clearance_no_leak_evidence_review_gate_status")) == (
        "first_clearance_no_leak_evidence_ready_for_operator_fill"
    )


def _intake_csv(review_summary: dict[str, Any]) -> str:
    packet_path = _text(review_summary.get("evidence_packet_json"))
    packet_payload = _read_json(packet_path)
    packet_summary = _summary(packet_payload)
    return _text(packet_summary.get("no_leak_operator_intake_csv"))


def _action_status(
    review_ready: bool,
    source_row: dict[str, Any],
    intake_row: dict[str, str] | None,
) -> tuple[str, str]:
    if not review_ready:
        return "blocked_review_gate_not_ready", _text(source_row.get("first_blocker")) or "review_gate_not_ready"
    if intake_row is None:
        return "blocked_destination_field_missing", "destination_field_missing"
    if _text(source_row.get("review_gate_status")) != "ready_for_no_leak_gate_operator_fill":
        return "blocked_source_field_not_ready", _text(source_row.get("first_blocker")) or "source_field_not_ready"
    if not _text(source_row.get("template_operator_value")):
        return "blocked_source_operator_value_missing", "source_operator_value_missing"
    if not _text(source_row.get("template_operator_clearance")):
        return "blocked_source_operator_clearance_missing", "source_operator_clearance_missing"
    return "ready_to_sync", ""


def _next_action(field_name: str, status: str, blocker: str) -> str:
    if status == "ready_to_sync":
        return f"copy reviewed operator_value and operator_clearance for {field_name} into no-leak intake"
    if status == "blocked_review_gate_not_ready":
        return "complete the no-leak evidence review gate before syncing into the intake"
    if status == "blocked_destination_field_missing":
        return f"restore {field_name} row in the no-leak operator intake"
    if blocker:
        return f"resolve {blocker} for {field_name} before sync"
    return f"repair {field_name} before sync"


def _build_rows(
    args: argparse.Namespace,
    review_summary: dict[str, Any],
    review_rows: list[dict[str, Any]],
    intake_csv: str,
    intake_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    intake_by_field = {_text(row.get("field_name")): row for row in intake_rows if _text(row.get("field_name"))}
    review_is_ready = _review_ready(review_summary)
    rows = []
    for index, source_row in enumerate(review_rows, start=1):
        field_name = _text(source_row.get("field_name"))
        intake_row = intake_by_field.get(field_name)
        action_status, blocker = _action_status(review_is_ready, source_row, intake_row)
        source_value = _text(source_row.get("template_operator_value"))
        source_clearance = _text(source_row.get("template_operator_clearance"))
        rows.append(
            {
                "action_id": f"first_no_leak_sync_{index:03d}",
                "action_status": action_status,
                "sync_mode": args.mode,
                "target_id": _text(review_summary.get("target_id")),
                "benchmark_id": _text(review_summary.get("benchmark_id")),
                "field_name": field_name,
                "destination_intake_csv": intake_csv,
                "current_operator_value": _text((intake_row or {}).get("operator_value")),
                "current_operator_clearance": _text((intake_row or {}).get("operator_clearance")),
                "current_evidence_ref": _text((intake_row or {}).get("evidence_ref")),
                "source_operator_value": source_value,
                "source_operator_clearance": source_clearance,
                "source_operator_evidence_ref": _text(source_row.get("template_operator_evidence_ref")),
                "proposed_operator_value": source_value,
                "proposed_operator_clearance": source_clearance,
                "evidence_ref_handling": "preserve_intake_evidence_ref_review_packet_holds_operator_evidence",
                "blocker": blocker,
                "next_action": _next_action(field_name, action_status, blocker),
            }
        )
    return rows


def _apply_sync(rows: list[dict[str, Any]]) -> int:
    ready_rows = [row for row in rows if row["action_status"] == "ready_to_sync"]
    if not ready_rows:
        return 0
    destination = _text(ready_rows[0].get("destination_intake_csv"))
    intake_rows = _read_csv(destination)
    if not intake_rows:
        return 0
    by_field = {_text(row.get("field_name")): row for row in intake_rows}
    applied = 0
    for action in ready_rows:
        intake_row = by_field.get(_text(action.get("field_name")))
        if not intake_row:
            continue
        intake_row["operator_value"] = _text(action.get("proposed_operator_value"))
        intake_row["operator_clearance"] = _text(action.get("proposed_operator_clearance"))
        action["action_status"] = "applied"
        applied += 1
    _write_csv(destination, intake_rows, list(intake_rows[0].keys()))
    return applied


def _status(input_blockers: list[str], rows: list[dict[str, Any]], mode: str, applied_count: int) -> str:
    if input_blockers:
        return "blocked_missing_inputs"
    if not rows:
        return "blocked_no_review_rows"
    if any(row["action_status"] == "blocked_review_gate_not_ready" for row in rows):
        return "awaiting_first_clearance_no_leak_evidence_review"
    if any(row["action_status"].startswith("blocked") for row in rows):
        return "blocked_first_clearance_no_leak_evidence_sync"
    if mode == "apply" and applied_count == len(rows):
        return "first_clearance_no_leak_evidence_sync_applied"
    if mode == "apply":
        return "first_clearance_no_leak_evidence_sync_partially_applied"
    return "first_clearance_no_leak_evidence_sync_ready_dry_run"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    review_path = _resolve(args.review_gate_json)
    review_payload = _read_json(review_path)
    review_summary = _summary(review_payload)
    review_rows = _rows(review_payload)
    intake_csv = _intake_csv(review_summary)
    intake_rows = _read_csv(intake_csv)
    input_blockers = []
    if not review_path.exists():
        input_blockers.append("review_gate_json_missing")
    if review_path.exists() and not intake_csv:
        input_blockers.append("no_leak_operator_intake_csv_missing")
    if intake_csv and not _resolve(intake_csv).is_file():
        input_blockers.append("no_leak_operator_intake_csv_not_found")
    rows = [] if input_blockers else _build_rows(args, review_summary, review_rows, intake_csv, intake_rows)
    applied_count = _apply_sync(rows) if args.mode == "apply" and not input_blockers else 0
    ready_count = sum(1 for row in rows if row["action_status"] == "ready_to_sync")
    blocked_count = sum(1 for row in rows if row["action_status"].startswith("blocked"))
    summary = {
        "packet_type": "casp17_historical_seed_first_clearance_no_leak_evidence_sync_plan",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "first_clearance_no_leak_evidence_sync_plan_status": _status(input_blockers, rows, args.mode, applied_count),
        "sync_mode": args.mode,
        "review_gate_json": _artifact(args.review_gate_json),
        "review_gate_status": _text(
            review_summary.get("first_clearance_no_leak_evidence_review_gate_status")
        ),
        "target_id": _text(review_summary.get("target_id")),
        "benchmark_id": _text(review_summary.get("benchmark_id")),
        "destination_intake_csv": _artifact(intake_csv),
        "action_count": len(rows),
        "ready_action_count": ready_count,
        "blocked_action_count": blocked_count,
        "applied_action_count": applied_count,
        "review_ready_field_count": len(
            [row for row in review_rows if _text(row.get("review_gate_status")) == "ready_for_no_leak_gate_operator_fill"]
        ),
        "review_blocked_field_count": len(
            [row for row in review_rows if _text(row.get("review_gate_status")) != "ready_for_no_leak_gate_operator_fill"]
        ),
        "first_action_id": _text(rows[0].get("action_id")) if rows else "",
        "first_blocked_field": _text(rows[0].get("field_name")) if rows and rows[0]["action_status"].startswith("blocked") else "",
        "first_blocker": _text(rows[0].get("blocker")) if rows else ",".join(input_blockers),
        "next_action": _text(rows[0].get("next_action")) if rows else "provide review gate and intake CSV inputs",
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed First Clearance No-Leak Evidence Sync Plan",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['first_clearance_no_leak_evidence_sync_plan_status']}`",
        f"- mode: `{summary['sync_mode']}`",
        f"- target/benchmark: `{summary['target_id']}` `{summary['benchmark_id']}`",
        f"- review gate: `{summary['review_gate_status'] or '-'}`",
        f"- actions ready/blocked/applied/total: `{summary['ready_action_count']}/{summary['blocked_action_count']}/{summary['applied_action_count']}/{summary['action_count']}`",
        f"- review ready/blocked fields: `{summary['review_ready_field_count']}/{summary['review_blocked_field_count']}`",
        f"- destination intake: `{summary['destination_intake_csv'] or '-'}`",
        f"- first blocker: `{summary['first_action_id'] or '-'}` `{summary['first_blocked_field'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Actions",
        "",
        "| action | status | field | source value | source clearance | current value | current clearance | blocker | next action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['action_id']}` | `{row['action_status']}` | `{row['field_name']}` | "
            f"`{row['source_operator_value'] or '-'}` | `{row['source_operator_clearance'] or '-'}` | "
            f"`{row['current_operator_value'] or '-'}` | `{row['current_operator_clearance'] or '-'}` | "
            f"`{row['blocker'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | - | - | - | - | - |")
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
        description="Build a dry-run/apply sync plan from reviewed no-leak evidence into the no-leak intake."
    )
    parser.add_argument("--review-gate-json", default=DEFAULT_REVIEW_GATE_JSON)
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
