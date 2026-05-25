#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_EXECUTION_BOARD_JSON = "casp17/casp17_competitive_floor_execution_board_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_readiness_gate_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_readiness_gate_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_READINESS_GATE.md"

GATE_COLUMNS = [
    "gate_id",
    "gate_order",
    "gate_status",
    "ready_count",
    "blocked_count",
    "total_count",
    "first_blocker",
    "next_action",
]
DONE_STATUSES = {"ready_for_review", "ready_for_intake"}
CLAIM_BOUNDARY = (
    "Local competitive-floor readiness gate only. It evaluates row-level execution-board evidence to decide "
    "whether identity, file-source, value-entry, and evidence-import stages are ready to advance. It does not "
    "choose targets, clear no-leak provenance, fetch native structures, score native accuracy, run predictors, "
    "mutate row_fill.csv, apply imports, or submit to CASP."
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
        resolved = GATE_COLUMNS
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=resolved, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _first_row(rows: list[dict[str, Any]], predicate) -> dict[str, Any]:
    return next((row for row in rows if predicate(row)), rows[0] if rows else {})


def _gate_row(
    gate_id: str,
    gate_order: int,
    gate_status: str,
    ready_count: int,
    blocked_count: int,
    total_count: int,
    first_blocker: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "gate_order": gate_order,
        "gate_status": gate_status,
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "total_count": total_count,
        "first_blocker": first_blocker,
        "next_action": next_action,
    }


def _identity_gate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    blocked_rows = [
        row
        for row in rows
        if _text(row.get("row_execution_status")) in {"awaiting_identity", "blocked_identity"}
        or _text(row.get("identity_status")) != "ready_for_import"
    ]
    first = _first_row(rows, lambda row: row in blocked_rows)
    return _gate_row(
        "identity_gate",
        1,
        "pass" if total and not blocked_rows else "awaiting_identity",
        total - len(blocked_rows),
        len(blocked_rows),
        total,
        _text(first.get("identity_blockers")) or _text(first.get("row_execution_status")),
        _text(first.get("next_action")) or "fill proposed benchmark/target identity values",
    )


def _identity_apply_gate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    blocked_rows = [row for row in rows if _int(row.get("value_ready_from_identity_kit_count"))]
    first = _first_row(rows, lambda row: row in blocked_rows)
    return _gate_row(
        "identity_apply_gate",
        2,
        "pass" if total and not blocked_rows else "ready_for_identity_apply",
        total - len(blocked_rows),
        len(blocked_rows),
        total,
        "ready_from_identity_kit" if blocked_rows else "",
        _text(first.get("next_action")) or "apply cleared identity values into the import CSV",
    )


def _file_source_gate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = sum(_int(row.get("file_action_count")) for row in rows)
    blocked = sum(
        _int(row.get("file_waiting_on_identity_count"))
        + _int(row.get("file_awaiting_source_path_count"))
        + _int(row.get("file_blocked_count"))
        for row in rows
    )
    ready = sum(
        _int(row.get("file_ready_for_import_count")) + _int(row.get("file_already_imported_count"))
        for row in rows
    )
    first = _first_row(
        rows,
        lambda row: (
            _int(row.get("file_waiting_on_identity_count"))
            + _int(row.get("file_awaiting_source_path_count"))
            + _int(row.get("file_blocked_count"))
        )
        > 0,
    )
    if blocked:
        status = "waiting_on_identity" if _int(first.get("file_waiting_on_identity_count")) else "awaiting_file_sources"
    else:
        status = "pass" if total and ready == total else "awaiting_file_sources"
    return _gate_row(
        "file_source_gate",
        3,
        status,
        ready,
        blocked,
        total,
        _text(first.get("row_execution_status")),
        _text(first.get("next_action")) or "provide cleared historical PDB source paths",
    )


def _value_entry_gate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = sum(_int(row.get("value_action_count")) for row in rows)
    blocked = sum(
        _int(row.get("value_waiting_on_identity_count"))
        + _int(row.get("value_ready_from_identity_kit_count"))
        + _int(row.get("value_awaiting_value_count"))
        + _int(row.get("value_awaiting_clearance_count"))
        + _int(row.get("value_awaiting_ref_count"))
        + _int(row.get("value_blocked_count"))
        for row in rows
    )
    ready = sum(_int(row.get("value_ready_for_import_count")) for row in rows)
    first = _first_row(
        rows,
        lambda row: (
            _int(row.get("value_waiting_on_identity_count"))
            + _int(row.get("value_ready_from_identity_kit_count"))
            + _int(row.get("value_awaiting_value_count"))
            + _int(row.get("value_awaiting_clearance_count"))
            + _int(row.get("value_awaiting_ref_count"))
            + _int(row.get("value_blocked_count"))
        )
        > 0,
    )
    if blocked:
        status = "waiting_on_identity" if _int(first.get("value_waiting_on_identity_count")) else "awaiting_values"
    else:
        status = "pass" if total and ready == total else "awaiting_values"
    return _gate_row(
        "value_entry_gate",
        4,
        status,
        ready,
        blocked,
        total,
        _text(first.get("row_execution_status")),
        _text(first.get("next_action")) or "fill cleared provenance and calibration values",
    )


def _evidence_import_gate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    ready_rows = [
        row
        for row in rows
        if _text(row.get("row_execution_status")) in {"ready_for_evidence_import", "ready_for_review", "ready_for_intake"}
    ]
    blocked_rows = [row for row in rows if row not in ready_rows]
    first = _first_row(rows, lambda row: row in blocked_rows)
    return _gate_row(
        "evidence_import_gate",
        5,
        "pass" if total and not blocked_rows else _text(first.get("row_execution_status")) or "awaiting_evidence",
        len(ready_rows),
        len(blocked_rows),
        total,
        _text(first.get("row_execution_status")),
        _text(first.get("next_action")) or "resolve row execution blockers before evidence import",
    )


def _competitive_floor_gate(rows: list[dict[str, Any]], gate_rows: list[dict[str, Any]]) -> dict[str, Any]:
    passing = all(row["gate_status"] == "pass" for row in gate_rows)
    first_blocked = next((row for row in gate_rows if row["gate_status"] != "pass"), gate_rows[0] if gate_rows else {})
    return _gate_row(
        "competitive_floor_gate",
        6,
        "ready_for_competitive_floor" if passing and rows else _text(first_blocked.get("gate_status")) or "missing",
        len(rows) if passing else 0,
        0 if passing else 1,
        len(rows),
        _text(first_blocked.get("gate_id")),
        _text(first_blocked.get("next_action")) or "resolve upstream gates before competitive-floor promotion",
    )


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    board_payload = _read_json(args.execution_board_json)
    board_summary = _summary(board_payload)
    rows = _rows(board_payload)
    gate_rows = [
        _identity_gate(rows),
        _identity_apply_gate(rows),
        _file_source_gate(rows),
        _value_entry_gate(rows),
        _evidence_import_gate(rows),
    ]
    gate_rows.append(_competitive_floor_gate(rows, gate_rows))
    pass_statuses = {"pass", "ready_for_competitive_floor"}
    first_blocked = next((row for row in gate_rows if row["gate_status"] not in pass_statuses), gate_rows[0] if gate_rows else {})
    pass_count = sum(1 for row in gate_rows if row["gate_status"] in pass_statuses)
    summary = {
        "packet_type": "casp17_competitive_floor_readiness_gate",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "readiness_gate_status": _text(first_blocked.get("gate_status")) if pass_count < len(gate_rows) else "ready_for_competitive_floor",
        "execution_board_json": _artifact(args.execution_board_json),
        "execution_board_status": _text(board_summary.get("execution_board_status")),
        "gate_count": len(gate_rows),
        "pass_count": pass_count,
        "blocked_gate_count": len(gate_rows) - pass_count,
        "row_count": len(rows),
        "first_blocked_gate_id": _text(first_blocked.get("gate_id")) if pass_count < len(gate_rows) else "",
        "first_blocked_status": _text(first_blocked.get("gate_status")) if pass_count < len(gate_rows) else "",
        "first_blocked_next_action": _text(first_blocked.get("next_action")) if pass_count < len(gate_rows) else "",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": gate_rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Readiness Gate",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- readiness_gate_status: `{summary['readiness_gate_status']}`",
        f"- execution_board_status: `{summary['execution_board_status'] or '-'}`",
        f"- gates pass/blocked: `{summary['pass_count']}/{summary['blocked_gate_count']}`",
        f"- rows: `{summary['row_count']}`",
        f"- first blocked gate: `{summary['first_blocked_gate_id'] or '-'}` `{summary['first_blocked_status'] or '-'}`",
        f"- next action: {summary['first_blocked_next_action'] or '-'}",
        "",
        "## Gate Rows",
        "",
        "| order | gate | status | ready | blocked | total | blocker | next action |",
        "| ---: | --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['gate_order']} | `{row['gate_id']}` | `{row['gate_status']}` | "
            f"{row['ready_count']} | {row['blocked_count']} | {row['total_count']} | "
            f"`{row['first_blocker'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `ready` | 0 | 0 | 0 | - | no gate rows |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], fieldnames=GATE_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the CASP17 competitive-floor readiness gate.")
    parser.add_argument("--execution-board-json", default=DEFAULT_EXECUTION_BOARD_JSON)
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
