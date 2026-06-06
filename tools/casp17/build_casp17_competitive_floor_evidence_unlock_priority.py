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

DEFAULT_IMPORT_JSON = "casp17/casp17_competitive_floor_evidence_import_current.json"
DEFAULT_IMPORT_CSV = "casp17/casp17_competitive_floor_evidence_import_current.csv"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_evidence_unlock_priority_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_evidence_unlock_priority_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_EVIDENCE_UNLOCK_PRIORITY.md"

DONE_STATUSES = {"already_imported", "copied_to_dropzone", "ledger_updated"}
READY_STATUSES = {"ready_to_copy", "ready_to_update_ledger"}
FILE_CLASSES = {"core_file", "ablation_file"}
PHASES = [
    ("identity_unlock", 1, "fill benchmark_id and target_id values first; target_id unlocks canonical file recommendations"),
    ("file_sources", 2, "place/import prediction, native, and ablation PDB source files after target_id is known"),
    ("provenance_clearance", 3, "fill no-leak provenance confirmations and dates"),
    ("calibration_values", 4, "fill ranks, native metrics, and internal scores"),
]
CLAIM_BOUNDARY = (
    "Local competitive-floor evidence unlock priority only. It ranks existing import rows so operators fill "
    "target identity before file source paths and downstream values. It does not choose targets, clear provenance, "
    "fetch native structures, score native accuracy, run predictors, mutate row_fill.csv, or submit to CASP."
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


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["dropzone_id", "phase", "unlock_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _rows_from_import(args: argparse.Namespace) -> list[dict[str, Any]]:
    payload = _read_json(args.import_json)
    rows = payload.get("rows")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return _read_csv(args.import_csv)


def _status(row: dict[str, Any]) -> str:
    status = _text(row.get("import_status"))
    if status:
        return status
    return "awaiting_import_file" if _text(row.get("import_kind")) == "file" else "awaiting_import_value"


def _is_done(row: dict[str, Any]) -> bool:
    return _status(row) in DONE_STATUSES


def _is_ready(row: dict[str, Any]) -> bool:
    return _status(row) in READY_STATUSES


def _phase_for(row: dict[str, Any]) -> str:
    evidence_class = _text(row.get("evidence_class"))
    column = _text(row.get("template_column"))
    if evidence_class == "target_identity" or column in {"benchmark_id", "target_id"}:
        return "identity_unlock"
    if evidence_class in FILE_CLASSES or _text(row.get("import_kind")) == "file":
        return "file_sources"
    if evidence_class == "provenance":
        return "provenance_clearance"
    if evidence_class == "calibration":
        return "calibration_values"
    return "provenance_clearance"


def _phase_meta(phase: str) -> tuple[int, str]:
    for name, order, next_action in PHASES:
        if name == phase:
            return order, next_action
    return 99, "review this import row"


def _phase_row(dropzone_id: str, phase: str, rows: list[dict[str, Any]], all_rows: list[dict[str, Any]]) -> dict[str, Any]:
    order, next_action = _phase_meta(phase)
    action_count = len(rows)
    done_count = sum(1 for row in rows if _is_done(row))
    ready_count = sum(1 for row in rows if _is_ready(row))
    open_count = max(0, action_count - done_count)
    target_id_rows = [
        row
        for row in all_rows
        if _text(row.get("dropzone_id")) == dropzone_id and _text(row.get("template_column")) == "target_id"
    ]
    target_id_done = bool(target_id_rows and all(_is_done(row) for row in target_id_rows))
    file_rows = [
        row
        for row in all_rows
        if _text(row.get("dropzone_id")) == dropzone_id and _phase_for(row) == "file_sources"
    ]
    file_actions = len(file_rows)
    if phase == "identity_unlock" and not target_id_done:
        downstream_blocked_file_actions = file_actions
        downstream_unlocked_file_actions = 0
    elif phase == "identity_unlock":
        downstream_blocked_file_actions = 0
        downstream_unlocked_file_actions = file_actions
    else:
        downstream_blocked_file_actions = 0
        downstream_unlocked_file_actions = 0
    unlock_status = "complete" if open_count == 0 else ("ready_for_apply" if ready_count else "awaiting_import")
    first_open = next((row for row in rows if not _is_done(row)), rows[0] if rows else {})
    return {
        "dropzone_id": dropzone_id,
        "phase_order": order,
        "phase": phase,
        "unlock_status": unlock_status,
        "action_count": action_count,
        "done_count": done_count,
        "ready_count": ready_count,
        "open_count": open_count,
        "target_id_done": target_id_done,
        "file_actions_in_row": file_actions,
        "downstream_unlocked_file_actions": downstream_unlocked_file_actions,
        "downstream_blocked_file_actions": downstream_blocked_file_actions,
        "first_open_column": _text(first_open.get("template_column")),
        "first_open_status": _status(first_open) if first_open else "",
        "next_action": next_action,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    import_rows = _rows_from_import(args)
    grouped_by_dropzone: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in import_rows:
        grouped_by_dropzone[_text(row.get("dropzone_id"))].append(row)
    phase_rows: list[dict[str, Any]] = []
    for dropzone_id in sorted(grouped_by_dropzone):
        if not dropzone_id:
            continue
        rows = grouped_by_dropzone[dropzone_id]
        by_phase: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_phase[_phase_for(row)].append(row)
        for phase, _order, _next_action in PHASES:
            phase_rows.append(_phase_row(dropzone_id, phase, by_phase.get(phase, []), import_rows))
    phase_rows.sort(key=lambda row: (int(row["phase_order"]), int(str(row["dropzone_id"]).split("_")[1] or 0), row["dropzone_id"]))
    by_phase_count = Counter(row["phase"] for row in phase_rows)
    identity_open = sum(row["open_count"] for row in phase_rows if row["phase"] == "identity_unlock")
    target_id_open = sum(
        1
        for dropzone_id, rows in grouped_by_dropzone.items()
        if dropzone_id
        and any(_text(row.get("template_column")) == "target_id" and not _is_done(row) for row in rows)
    )
    downstream_blocked = sum(row["downstream_blocked_file_actions"] for row in phase_rows)
    first_open = next((row for row in phase_rows if row["open_count"]), phase_rows[0] if phase_rows else {})
    row_ids = {dropzone_id for dropzone_id in grouped_by_dropzone if dropzone_id}
    summary = {
        "packet_type": "casp17_competitive_floor_evidence_unlock_priority",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "unlock_status": "ready" if phase_rows and not identity_open and not downstream_blocked else "identity_unlock_required",
        "import_json": _artifact(args.import_json),
        "import_csv": _artifact(args.import_csv),
        "row_count": len(row_ids),
        "phase_row_count": len(phase_rows),
        "identity_phase_count": by_phase_count["identity_unlock"],
        "file_phase_count": by_phase_count["file_sources"],
        "provenance_phase_count": by_phase_count["provenance_clearance"],
        "calibration_phase_count": by_phase_count["calibration_values"],
        "identity_open_action_count": identity_open,
        "target_id_open_count": target_id_open,
        "file_actions_waiting_on_identity_count": downstream_blocked,
        "first_open_dropzone_id": _text(first_open.get("dropzone_id")),
        "first_open_phase": _text(first_open.get("phase")),
        "first_open_column": _text(first_open.get("first_open_column")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": phase_rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Evidence Unlock Priority",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- unlock_status: `{summary['unlock_status']}`",
        f"- rows/phases: `{summary['row_count']}/{summary['phase_row_count']}`",
        f"- identity open actions: `{summary['identity_open_action_count']}`",
        f"- target_id still open: `{summary['target_id_open_count']}`",
        f"- file actions waiting on identity: `{summary['file_actions_waiting_on_identity_count']}`",
        f"- first open: `{summary['first_open_dropzone_id'] or '-'}` `{summary['first_open_phase'] or '-'}` `{summary['first_open_column'] or '-'}`",
        f"- next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Phase Rows",
        "",
        "| order | dropzone | phase | status | open | ready | done | downstream files blocked | first column | next action |",
        "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['phase_order']} | `{row['dropzone_id']}` | `{row['phase']}` | `{row['unlock_status']}` | "
            f"{row['open_count']} | {row['ready_count']} | {row['done_count']} | "
            f"{row['downstream_blocked_file_actions']} | `{row['first_open_column'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `ready` | `ready` | 0 | 0 | 0 | 0 | - | no import rows |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rank CASP17 competitive-floor evidence imports by unlock priority.")
    parser.add_argument("--import-json", default=DEFAULT_IMPORT_JSON)
    parser.add_argument("--import-csv", default=DEFAULT_IMPORT_CSV)
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
