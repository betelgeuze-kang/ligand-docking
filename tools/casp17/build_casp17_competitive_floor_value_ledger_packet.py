#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DROPZONE_JSON = "casp17/casp17_competitive_floor_evidence_dropzone_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_value_ledger_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_value_ledger_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_VALUE_LEDGER.md"

FILE_CLASSES = {"core_file", "ablation_file"}
LEDGER_COLUMNS = [
    "template_column",
    "evidence_class",
    "current_value",
    "proposed_value",
    "evidence_ref",
    "operator_clearance",
    "ledger_status",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local competitive-floor value ledger only. It creates per-row ledgers for target identity, provenance, and "
    "calibration fields; it does not choose historical targets, clear no-leak provenance, score native accuracy, "
    "fetch native structures, run predictors, mutate row_fill.csv, or submit to CASP."
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


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


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
        resolved = ["template_column", "ledger_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=resolved, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], [f"{path.name}_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    blockers: list[str] = []
    if not fieldnames:
        blockers.append(f"{path.name}_header_missing")
    if not rows:
        blockers.append(f"{path.name}_empty")
    missing = [column for column in LEDGER_COLUMNS if column not in fieldnames]
    if missing:
        blockers.append("ledger_columns_missing:" + ",".join(missing))
    return rows, blockers


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


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


def _batch_folder(action: dict[str, Any]) -> Path:
    row_fill_csv = _text(action.get("source_row_fill_csv"))
    if row_fill_csv:
        return _resolve(row_fill_csv).parent
    dropzone_folder = _text(action.get("dropzone_folder"))
    if dropzone_folder:
        return _resolve(dropzone_folder).parent
    return ROOT / "casp17" / "competitive_floor_batch_current" / _text(action.get("dropzone_id"))


def _ledger_path(action: dict[str, Any]) -> Path:
    return _batch_folder(action) / "FIELD_VALUE_LEDGER.csv"


def _guide_path(action: dict[str, Any]) -> Path:
    return _batch_folder(action) / "FIELD_VALUE_LEDGER.md"


def _seed_row(action: dict[str, Any]) -> dict[str, Any]:
    column = _text(action.get("template_column"))
    return {
        "template_column": column,
        "evidence_class": _text(action.get("evidence_class")),
        "current_value": _text(action.get("current_value")),
        "proposed_value": "",
        "evidence_ref": "",
        "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
        "ledger_status": "awaiting_value",
        "next_action": _next_action_for(column, _text(action.get("evidence_class"))),
    }


def _next_action_for(column: str, evidence_class: str) -> str:
    if evidence_class == "target_identity":
        return f"enter the cleared historical {column} and cite the local target-selection evidence"
    if evidence_class == "provenance":
        return f"enter {column} only after no-leak evidence supports the value"
    if evidence_class == "calibration":
        return f"enter {column} from the local historical scoring/calibration packet"
    return f"enter {column} only when the local evidence is cleared"


def _ledger_rows_for_action(action: dict[str, Any]) -> tuple[list[dict[str, str]], list[str]]:
    rows, blockers = _read_csv(_ledger_path(action))
    return rows, blockers


def _audit_action(action: dict[str, Any]) -> dict[str, Any]:
    path = _ledger_path(action)
    guide = _guide_path(action)
    rows, blockers = _ledger_rows_for_action(action)
    column = _text(action.get("template_column"))
    matching = [row for row in rows if _text(row.get("template_column")) == column]
    row = matching[0] if matching else {}
    proposed = _text(row.get("proposed_value"))
    clearance = _text(row.get("operator_clearance")).lower()
    evidence_ref = _text(row.get("evidence_ref"))
    ledger_status = _text(row.get("ledger_status")) or "awaiting_value"
    action_status = "awaiting_value"
    action_blockers: list[str] = []
    if blockers:
        action_status = "ledger_blocked"
        action_blockers.extend(blockers)
    elif not matching:
        action_status = "ledger_row_missing"
        action_blockers.append("ledger_row_missing")
    elif _contains_placeholder(proposed):
        action_status = "awaiting_value"
        action_blockers.append("proposed_value_required")
    elif clearance not in {"ready_for_row_fill", "cleared", "no_leak", "internal_no_leak"}:
        action_status = "awaiting_clearance"
        action_blockers.append("operator_clearance_required")
    elif not evidence_ref:
        action_status = "awaiting_evidence_ref"
        action_blockers.append("evidence_ref_required")
    else:
        action_status = "ready_for_intake"
    return {
        "dropzone_id": _text(action.get("dropzone_id")),
        "action_rank": _int(action.get("action_rank")),
        "operator_priority": _int(action.get("operator_priority")),
        "row_rank": _int(action.get("row_rank")),
        "benchmark_id": _text(action.get("benchmark_id")),
        "target_id": _text(action.get("target_id")),
        "scope": _text(action.get("scope")),
        "evidence_class": _text(action.get("evidence_class")),
        "template_column": column,
        "source_row_fill_csv": _text(action.get("source_row_fill_csv")),
        "value_ledger_csv": _artifact(path),
        "value_ledger_md": _artifact(guide),
        "proposed_value": proposed,
        "evidence_ref": evidence_ref,
        "operator_clearance": _text(row.get("operator_clearance")),
        "ledger_status": ledger_status,
        "value_ledger_action_status": action_status,
        "blockers": ",".join(action_blockers),
        "next_action": _text(row.get("next_action")) or _next_action_for(column, _text(action.get("evidence_class"))),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    dropzone_payload = _read_json(args.dropzone_json)
    dropzone_summary = _summary(dropzone_payload)
    actions = [
        action
        for action in _rows(dropzone_payload)
        if _text(action.get("evidence_class")) not in FILE_CLASSES
    ]
    audit_rows = [_audit_action(action) for action in actions]
    by_status = defaultdict(int)
    by_class = defaultdict(int)
    ledgers = {row["value_ledger_csv"] for row in audit_rows if row["value_ledger_csv"]}
    for row in audit_rows:
        by_status[str(row["value_ledger_action_status"])] += 1
        by_class[str(row["evidence_class"])] += 1
    first_open = next((row for row in audit_rows if row["value_ledger_action_status"] != "ready_for_intake"), audit_rows[0] if audit_rows else {})
    summary = {
        "packet_type": "casp17_competitive_floor_value_ledger",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "value_ledger_status": "ready_for_intake" if audit_rows and by_status["ready_for_intake"] == len(audit_rows) else "awaiting_values",
        "dropzone_json": _artifact(args.dropzone_json),
        "dropzone_status": _text(dropzone_summary.get("dropzone_status")),
        "ledger_count": len(ledgers),
        "action_count": len(audit_rows),
        "target_identity_count": by_class["target_identity"],
        "provenance_count": by_class["provenance"],
        "calibration_count": by_class["calibration"],
        "ready_for_intake_count": by_status["ready_for_intake"],
        "awaiting_value_count": by_status["awaiting_value"],
        "awaiting_clearance_count": by_status["awaiting_clearance"],
        "awaiting_evidence_ref_count": by_status["awaiting_evidence_ref"],
        "blocked_count": by_status["ledger_blocked"] + by_status["ledger_row_missing"],
        "first_open_dropzone_id": _text(first_open.get("dropzone_id")),
        "first_open_column": _text(first_open.get("template_column")),
        "first_open_status": _text(first_open.get("value_ledger_action_status")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": audit_rows}


def _write_ledger_files(payload: dict[str, Any], dropzone_payload: dict[str, Any]) -> None:
    grouped_actions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for action in _rows(dropzone_payload):
        if _text(action.get("evidence_class")) not in FILE_CLASSES:
            grouped_actions[_artifact(_ledger_path(action))].append(action)
    for ledger_artifact, actions in grouped_actions.items():
        ledger_path = _resolve(ledger_artifact)
        guide_path = _guide_path(actions[0])
        existing_rows, blockers = _read_csv(ledger_path)
        existing_by_column = {
            _text(row.get("template_column")): row
            for row in existing_rows
            if _text(row.get("template_column"))
        }
        seeded_rows: list[dict[str, Any]] = []
        for action in actions:
            column = _text(action.get("template_column"))
            seeded = _seed_row(action)
            if column in existing_by_column and not blockers:
                existing = existing_by_column[column]
                seeded.update({key: _text(existing.get(key)) for key in LEDGER_COLUMNS if key in existing})
            seeded_rows.append(seeded)
        _write_csv(ledger_path, seeded_rows, fieldnames=LEDGER_COLUMNS)
        lines = [
            "# CASP17 Competitive-Floor Field Value Ledger",
            "",
            f"- value_ledger_csv: `{_artifact(ledger_path)}`",
            f"- row_fill_csv: `{_text(actions[0].get('source_row_fill_csv'))}`",
            f"- action count: `{len(seeded_rows)}`",
            "",
            "| column | class | proposed value | clearance | evidence ref | status | next action |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for row in seeded_rows:
            lines.append(
                f"| `{row['template_column']}` | `{row['evidence_class']}` | `{row['proposed_value'] or '-'}` | "
                f"`{row['operator_clearance'] or '-'}` | `{row['evidence_ref'] or '-'}` | `{row['ledger_status']}` | {row['next_action']} |"
            )
        lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
        guide_path.parent.mkdir(parents=True, exist_ok=True)
        guide_path.write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Value Ledger",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- value_ledger_status: `{summary['value_ledger_status']}`",
        f"- ledgers/actions: `{summary['ledger_count']}/{summary['action_count']}`",
        f"- target/provenance/calibration actions: `{summary['target_identity_count']}/{summary['provenance_count']}/{summary['calibration_count']}`",
        f"- ready_for_intake: `{summary['ready_for_intake_count']}`",
        f"- awaiting value/clearance/evidence-ref: `{summary['awaiting_value_count']}/{summary['awaiting_clearance_count']}/{summary['awaiting_evidence_ref_count']}`",
        f"- first open: `{summary['first_open_dropzone_id'] or '-'}` `{summary['first_open_column'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Ledger Rows",
        "",
        "| rank | dropzone | class | column | status | proposed | clearance | evidence ref | next action |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['action_rank']} | `{row['dropzone_id']}` | `{row['evidence_class']}` | "
            f"`{row['template_column']}` | `{row['value_ledger_action_status']}` | "
            f"`{row['proposed_value'] or '-'}` | `{row['operator_clearance'] or '-'}` | "
            f"`{row['evidence_ref'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `ready` | - | - | - | - | - | no value-ledger rows |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    dropzone_payload = _read_json(args.dropzone_json)
    if args.write_ledgers:
        _write_ledger_files(payload, dropzone_payload)
        payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and audit per-row value ledgers for competitive-floor row_fill fields.")
    parser.add_argument("--dropzone-json", default=DEFAULT_DROPZONE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--write-ledgers", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
