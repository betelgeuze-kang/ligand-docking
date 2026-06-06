#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_EVIDENCE_ACTION_BOARD_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_evidence_action_board_current.json"
)
DEFAULT_OPERATOR_ACTION_BOARD_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_operator_action_board_current.json"
)
DEFAULT_CYCLE_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_cycle_current.json"
DEFAULT_KIT_DIR = "casp17/historical_seed_strict_blind_replacement_first_slot_kit"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_kit_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_kit_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_FIRST_SLOT_KIT.md"

ROW_COLUMNS = [
    "action_group",
    "action_id",
    "queue_rank",
    "required_benchmark_id",
    "required_target_id",
    "scope",
    "field_name",
    "action_status",
    "value_present",
    "evidence_ref_present",
    "operator_clearance_present",
    "source_path",
    "operator_values_csv",
    "destination_intake_csv",
    "verify_command",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local CASP17 first-slot strict-blind replacement kit only. It narrows the current first open replacement "
    "slot into the evidence files and operator values that must be supplied before quality, import, and promotion "
    "gates can move. It does not create evidence, select targets, approve no-leak provenance, compute CASP "
    "metrics, mutate intake CSVs, or submit to CASP."
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


def _benchmark_id(args: argparse.Namespace, cycle: dict[str, Any], evidence: dict[str, Any], operator: dict[str, Any]) -> str:
    return (
        _text(args.required_benchmark_id)
        or _text(_summary(cycle).get("first_open_benchmark_id"))
        or _text(_summary(evidence).get("first_open_benchmark_id"))
        or _text(_summary(operator).get("first_open_benchmark_id"))
    )


def _evidence_status_done(status: str) -> bool:
    return status == "ready_for_quality_audit"


def _operator_status_done(status: str) -> bool:
    return status in {"ready_to_apply", "already_applied", "applied"}


def _evidence_checklist_rows(evidence_rows: list[dict[str, Any]], benchmark_id: str) -> list[dict[str, Any]]:
    rows = []
    for row in evidence_rows:
        if _text(row.get("required_benchmark_id")) != benchmark_id:
            continue
        rows.append(
            {
                "action_group": "evidence_file",
                "action_id": _text(row.get("action_id")),
                "queue_rank": _int(row.get("queue_rank")),
                "required_benchmark_id": benchmark_id,
                "required_target_id": _text(row.get("required_target_id")),
                "scope": _text(row.get("scope")),
                "field_name": _text(row.get("field_name")),
                "action_status": _text(row.get("action_status")),
                "value_present": "true" if _evidence_status_done(_text(row.get("action_status"))) else "false",
                "evidence_ref_present": "false",
                "operator_clearance_present": "false",
                "source_path": _text(row.get("source_path")),
                "operator_values_csv": "",
                "destination_intake_csv": "",
                "verify_command": _text(row.get("verify_command")),
                "next_action": _text(row.get("next_action")),
            }
        )
    return rows


def _operator_checklist_rows(operator_rows: list[dict[str, Any]], benchmark_id: str) -> list[dict[str, Any]]:
    rows = []
    for row in operator_rows:
        if _text(row.get("required_benchmark_id")) != benchmark_id:
            continue
        rows.append(
            {
                "action_group": "operator_value",
                "action_id": _text(row.get("action_id")),
                "queue_rank": _int(row.get("queue_rank")),
                "required_benchmark_id": benchmark_id,
                "required_target_id": "",
                "scope": "",
                "field_name": _text(row.get("field_name")),
                "action_status": _text(row.get("action_status")),
                "value_present": _text(row.get("operator_value_present")),
                "evidence_ref_present": _text(row.get("evidence_ref_present")),
                "operator_clearance_present": _text(row.get("operator_clearance_present")),
                "source_path": "",
                "operator_values_csv": _text(row.get("operator_values_csv")),
                "destination_intake_csv": _text(row.get("destination_intake_csv")),
                "verify_command": _text(row.get("verify_command")),
                "next_action": _text(row.get("next_action")),
            }
        )
    return rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    evidence_payload = _read_json(args.evidence_action_board_json)
    operator_payload = _read_json(args.operator_action_board_json)
    cycle_payload = _read_json(args.cycle_json)
    input_blockers = []
    if not _resolve(args.evidence_action_board_json).exists():
        input_blockers.append("strict_blind_replacement_evidence_action_board_json_missing")
    if not _resolve(args.operator_action_board_json).exists():
        input_blockers.append("strict_blind_replacement_operator_action_board_json_missing")
    if not _resolve(args.cycle_json).exists():
        input_blockers.append("strict_blind_replacement_cycle_json_missing")
    benchmark_id = _benchmark_id(args, cycle_payload, evidence_payload, operator_payload)
    evidence_rows = _evidence_checklist_rows(_rows(evidence_payload), benchmark_id)
    operator_rows = _operator_checklist_rows(_rows(operator_payload), benchmark_id)
    rows = evidence_rows + operator_rows
    summary = _build_summary(args, rows, input_blockers, benchmark_id, evidence_payload, operator_payload, cycle_payload)
    return {"summary": summary, "rows": rows}


def _build_summary(
    args: argparse.Namespace,
    rows: list[dict[str, Any]],
    input_blockers: list[str],
    benchmark_id: str,
    evidence_payload: dict[str, Any],
    operator_payload: dict[str, Any],
    cycle_payload: dict[str, Any],
) -> dict[str, Any]:
    evidence_rows = [row for row in rows if row["action_group"] == "evidence_file"]
    operator_rows = [row for row in rows if row["action_group"] == "operator_value"]
    evidence_open = [row for row in evidence_rows if not _evidence_status_done(row["action_status"])]
    operator_open = [row for row in operator_rows if not _operator_status_done(row["action_status"])]
    first_open = (evidence_open or operator_open or rows or [{}])[0]
    target_id = next((_text(row.get("required_target_id")) for row in evidence_rows if _text(row.get("required_target_id"))), "")
    scope = next((_text(row.get("scope")) for row in evidence_rows if _text(row.get("scope"))), "")
    kit_folder = _artifact(_kit_folder(args.kit_dir, benchmark_id))
    summary = {
        "packet_type": "casp17_historical_seed_strict_blind_replacement_first_slot_kit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "strict_blind_replacement_first_slot_kit_status": _overall_status(
            input_blockers,
            benchmark_id,
            evidence_rows,
            operator_rows,
        ),
        "required_benchmark_id": benchmark_id,
        "required_target_id": target_id,
        "scope": scope,
        "cycle_status": _text(_summary(cycle_payload).get("strict_blind_replacement_cycle_status")),
        "cycle_first_stage": _text(_summary(cycle_payload).get("first_blocking_stage")),
        "evidence_action_board_status": _text(
            _summary(evidence_payload).get("strict_blind_replacement_evidence_action_board_status")
        ),
        "operator_action_board_status": _text(
            _summary(operator_payload).get("strict_blind_replacement_operator_action_board_status")
        ),
        "evidence_action_count": len(evidence_rows),
        "evidence_ready_count": len(evidence_rows) - len(evidence_open),
        "evidence_open_count": len(evidence_open),
        "evidence_blocked_count": sum(1 for row in evidence_rows if row["action_status"].startswith("blocked")),
        "operator_action_count": len(operator_rows),
        "operator_ready_count": len(operator_rows) - len(operator_open),
        "operator_open_count": len(operator_open),
        "operator_open_value_count": sum(1 for row in operator_rows if row["value_present"] == "false"),
        "operator_open_evidence_count": sum(1 for row in operator_rows if row["evidence_ref_present"] == "false"),
        "operator_open_clearance_count": sum(1 for row in operator_rows if row["operator_clearance_present"] == "false"),
        "operator_blocked_count": sum(1 for row in operator_rows if row["action_status"].startswith("blocked")),
        "first_open_action_group": _text(first_open.get("action_group")),
        "first_open_action_id": _text(first_open.get("action_id")),
        "first_open_field": _text(first_open.get("field_name")),
        "first_open_status": _text(first_open.get("action_status")),
        "first_next_action": _text(first_open.get("next_action")) or "provide first strict-blind replacement slot inputs",
        "kit_folder": kit_folder,
        "kit_md": _artifact(_kit_folder(args.kit_dir, benchmark_id) / "FIRST_SLOT_KIT.md") if benchmark_id else "",
        "evidence_actions_csv": _artifact(_kit_folder(args.kit_dir, benchmark_id) / "first_slot_evidence_actions.csv")
        if benchmark_id
        else "",
        "operator_actions_csv": _artifact(_kit_folder(args.kit_dir, benchmark_id) / "first_slot_operator_actions.csv")
        if benchmark_id
        else "",
        "combined_checklist_csv": _artifact(_kit_folder(args.kit_dir, benchmark_id) / "first_slot_combined_checklist.csv")
        if benchmark_id
        else "",
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return summary


def _overall_status(
    input_blockers: list[str],
    benchmark_id: str,
    evidence_rows: list[dict[str, Any]],
    operator_rows: list[dict[str, Any]],
) -> str:
    if input_blockers:
        return "blocked_missing_input"
    if not benchmark_id or not evidence_rows or not operator_rows:
        return "blocked_missing_first_slot_actions"
    if any(row["action_status"].startswith("blocked") for row in evidence_rows):
        return "blocked_first_slot_evidence_review"
    if any(row["action_status"].startswith("blocked") for row in operator_rows):
        return "blocked_first_slot_operator_review"
    if any(not _evidence_status_done(row["action_status"]) for row in evidence_rows):
        return "awaiting_first_slot_evidence_files"
    if any(not _operator_status_done(row["action_status"]) for row in operator_rows):
        return "awaiting_first_slot_operator_values"
    return "first_slot_ready_for_import_gate"


def _kit_folder(kit_dir: str | Path, benchmark_id: str) -> Path:
    safe = benchmark_id.replace("/", "_").replace(" ", "_")
    return _resolve(kit_dir) / safe


def _write_md(path_like: str | Path, payload: dict[str, Any], *, title: str) -> None:
    summary = payload["summary"]
    lines = [
        f"# {title}",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['strict_blind_replacement_first_slot_kit_status']}`",
        f"- benchmark/target/scope: `{summary['required_benchmark_id'] or '-'}` `{summary['required_target_id'] or '-'}` `{summary['scope'] or '-'}`",
        f"- evidence ready/open/blocked/total: `{summary['evidence_ready_count']}/{summary['evidence_open_count']}/{summary['evidence_blocked_count']}/{summary['evidence_action_count']}`",
        f"- operator ready/open/blocked/total: `{summary['operator_ready_count']}/{summary['operator_open_count']}/{summary['operator_blocked_count']}/{summary['operator_action_count']}`",
        f"- operator open value/evidence/clearance: `{summary['operator_open_value_count']}/{summary['operator_open_evidence_count']}/{summary['operator_open_clearance_count']}`",
        f"- cycle: `{summary['cycle_status'] or '-'}` first stage `{summary['cycle_first_stage'] or '-'}`",
        f"- kit folder: `{summary['kit_folder'] or '-'}`",
        f"- first open: `{summary['first_open_action_group'] or '-'}` `{summary['first_open_action_id'] or '-'}` `{summary['first_open_field'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Checklist",
        "",
        "| group | action | field | status | source/operator file | next action |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        source = row["source_path"] or row["operator_values_csv"] or row["destination_intake_csv"] or "-"
        lines.append(
            f"| `{row['action_group']}` | `{row['action_id']}` | `{row['field_name']}` | "
            f"`{row['action_status']}` | `{source}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked_missing_first_slot_actions` | - | regenerate action boards |")
    lines.extend(["", "## Verification", ""])
    verify_commands = sorted({row["verify_command"] for row in payload["rows"] if row.get("verify_command")})
    for command in verify_commands:
        lines.append(f"- `{command}`")
    if not verify_commands:
        lines.append("- regenerate strict-blind action boards")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    evidence_rows = [row for row in payload["rows"] if row["action_group"] == "evidence_file"]
    operator_rows = [row for row in payload["rows"] if row["action_group"] == "operator_value"]
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload, title="CASP17 Historical Seed Strict-Blind Replacement First Slot Kit")
    if summary.get("required_benchmark_id"):
        folder = _kit_folder(args.kit_dir, summary["required_benchmark_id"])
        _write_csv(folder / "first_slot_evidence_actions.csv", evidence_rows, ROW_COLUMNS)
        _write_csv(folder / "first_slot_operator_actions.csv", operator_rows, ROW_COLUMNS)
        _write_csv(folder / "first_slot_combined_checklist.csv", payload["rows"], ROW_COLUMNS)
        _write_md(folder / "FIRST_SLOT_KIT.md", payload, title=f"{summary['required_benchmark_id']} First Slot Kit")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 strict-blind first-slot execution kit.")
    parser.add_argument("--evidence-action-board-json", default=DEFAULT_EVIDENCE_ACTION_BOARD_JSON)
    parser.add_argument("--operator-action-board-json", default=DEFAULT_OPERATOR_ACTION_BOARD_JSON)
    parser.add_argument("--cycle-json", default=DEFAULT_CYCLE_JSON)
    parser.add_argument("--required-benchmark-id", default="")
    parser.add_argument("--kit-dir", default=DEFAULT_KIT_DIR)
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
