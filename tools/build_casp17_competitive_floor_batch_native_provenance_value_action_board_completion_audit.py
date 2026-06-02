#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

from tools import build_casp17_competitive_floor_batch_native_provenance_value_action_board as board


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_VALUE_GATE_JSON = "casp17/casp17_competitive_floor_batch_native_provenance_value_gate_current.json"
DEFAULT_ACTION_BOARD_JSON = (
    "casp17/casp17_competitive_floor_batch_native_provenance_value_action_board_current.json"
)
DEFAULT_OUT_JSON = (
    "casp17/casp17_competitive_floor_batch_native_provenance_value_action_board_completion_audit_current.json"
)
DEFAULT_OUT_CSV = (
    "casp17/casp17_competitive_floor_batch_native_provenance_value_action_board_completion_audit_current.csv"
)
DEFAULT_OUT_MD = "casp17/CASP17_COMPETITIVE_FLOOR_BATCH_NATIVE_PROVENANCE_VALUE_ACTION_BOARD_COMPLETION_AUDIT.md"

ROW_COLUMNS = [
    "target_id",
    "target_name",
    "audit_status",
    "target_action_folder",
    "folder_present",
    "readme_present",
    "value_actions_present",
    "expected_action_count",
    "value_actions_csv_rows",
    "value_actions_row_mismatch",
    "board_action_json_rows",
    "coordinate_copy_count",
    "competitive_proof_eligible",
    "author_serialized",
    "blockers",
]
CLAIM_BOUNDARY = (
    "CASP17 competitive-floor batch native/provenance value action board completion audit only. It verifies the "
    "field-level operator action board files, target-named folders, action row counts, no-coordinate-copy hygiene, "
    "and proof boundary flags. It does not fill values, fetch native structures, clear no-leak provenance, compute "
    "native accuracy, serialize a CASP author code, or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    text = str(path_like or "").strip()
    if not text:
        return ""
    path = _resolve(text).resolve()
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


def _read_csv_rows(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _present(path_like: str | Path) -> int:
    return 1 if _resolve(path_like).is_file() else 0


def _folder_present(path_like: str | Path) -> int:
    return 1 if _resolve(path_like).is_dir() else 0


def _coordinate_file_count(path_like: str | Path) -> int:
    path = _resolve(path_like)
    if not path.exists():
        return 0
    return sum(1 for item in path.rglob("*") if item.is_file() and item.suffix.lower() in {".pdb", ".cif"})


def _gate_expected_counts(gate_rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in gate_rows:
        target_id = _text(row.get("target_id")).upper()
        counts[target_id] = len(board._blockers(row))
    return counts


def _board_rows_by_target(action_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_target: dict[str, list[dict[str, Any]]] = {}
    for row in action_rows:
        target_id = _text(row.get("target_id")).upper()
        if target_id:
            by_target.setdefault(target_id, []).append(row)
    return by_target


def _target_row(
    target_id: str,
    *,
    gate_row: dict[str, Any],
    action_rows: list[dict[str, Any]],
    expected_count: int,
    global_blockers: list[str],
) -> dict[str, Any]:
    first_action = action_rows[0] if action_rows else {}
    folder = _text(first_action.get("target_action_folder")) or board._target_folder(
        _text(first_action.get("out_dir")) or "", gate_row
    )
    blockers = list(global_blockers)
    folder_present = _folder_present(folder)
    readme_present = _present(_resolve(folder) / "README.md")
    value_actions_present = _present(_resolve(folder) / "value_actions.csv")
    csv_rows = _read_csv_rows(_resolve(folder) / "value_actions.csv") if value_actions_present else []
    board_action_json_rows = len(action_rows)
    csv_row_count = len(csv_rows)
    if not folder_present:
        blockers.append("target_action_folder_missing")
    if not readme_present:
        blockers.append("target_action_readme_missing")
    if not value_actions_present:
        blockers.append("target_value_actions_csv_missing")
    if board_action_json_rows != expected_count:
        blockers.append("board_action_json_row_mismatch")
    if csv_row_count != expected_count:
        blockers.append("target_value_actions_csv_row_mismatch")
    coordinate_count = _coordinate_file_count(folder)
    if coordinate_count:
        blockers.append("target_coordinate_copy_present")
    if any(_text(row.get("competitive_proof_eligible")).lower() != "false" for row in action_rows):
        blockers.append("competitive_proof_boundary_not_false")
    if any(_text(row.get("author_serialized")).lower() != "false" for row in action_rows):
        blockers.append("author_boundary_not_false")
    blockers = list(dict.fromkeys(blockers))
    return {
        "target_id": target_id,
        "target_name": _text(gate_row.get("target_name")) or _text(first_action.get("target_name")),
        "audit_status": "pass" if not blockers else "blocked",
        "target_action_folder": _artifact(folder),
        "folder_present": folder_present,
        "readme_present": readme_present,
        "value_actions_present": value_actions_present,
        "expected_action_count": expected_count,
        "value_actions_csv_rows": csv_row_count,
        "value_actions_row_mismatch": 0 if csv_row_count == expected_count else 1,
        "board_action_json_rows": board_action_json_rows,
        "coordinate_copy_count": coordinate_count,
        "competitive_proof_eligible": "false",
        "author_serialized": "false",
        "blockers": ",".join(blockers),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    gate_payload = _read_json(args.value_gate_json)
    action_board_payload = _read_json(args.action_board_json)
    gate_summary = _summary(gate_payload)
    action_board_summary = _summary(action_board_payload)
    gate_rows = _rows(gate_payload)
    action_rows = _rows(action_board_payload)
    expected_by_target = _gate_expected_counts(gate_rows)
    gate_by_target = {_text(row.get("target_id")).upper(): row for row in gate_rows if _text(row.get("target_id"))}
    action_by_target = _board_rows_by_target(action_rows)
    global_blockers: list[str] = []
    if not _resolve(args.value_gate_json).exists():
        global_blockers.append("value_gate_json_missing")
    if not _resolve(args.action_board_json).exists():
        global_blockers.append("value_action_board_json_missing")
    out_dir = _text(action_board_summary.get("out_dir"))
    if not out_dir:
        global_blockers.append("value_action_board_out_dir_missing")
    else:
        if not _folder_present(out_dir):
            global_blockers.append("value_action_board_out_dir_missing")
        if not _present(_resolve(out_dir) / "manifest.json"):
            global_blockers.append("value_action_board_manifest_missing")
    if _text(action_board_summary.get("value_gate_status")) != _text(
        gate_summary.get("batch_native_provenance_value_gate_status")
    ):
        global_blockers.append("value_gate_status_mismatch")
    if _int(action_board_summary.get("action_count")) != sum(expected_by_target.values()):
        global_blockers.append("value_action_board_action_count_mismatch")
    target_rows = [
        _target_row(
            target_id,
            gate_row=gate_by_target.get(target_id, {}),
            action_rows=action_by_target.get(target_id, []),
            expected_count=expected_by_target.get(target_id, 0),
            global_blockers=global_blockers,
        )
        for target_id in sorted(expected_by_target)
    ]
    blocked_rows = [row for row in target_rows if row["audit_status"] != "pass"]
    coordinate_count = _coordinate_file_count(out_dir) if out_dir else 0
    status = "casp17_competitive_floor_batch_native_provenance_value_action_board_completion_audit_pass"
    if blocked_rows or global_blockers or not target_rows:
        status = "casp17_competitive_floor_batch_native_provenance_value_action_board_completion_audit_blocked"
    first_blocked = blocked_rows[0] if blocked_rows else {}
    summary = {
        "packet_type": "casp17_competitive_floor_batch_native_provenance_value_action_board_completion_audit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "batch_native_provenance_value_action_board_completion_audit_status": status,
        "value_gate_json": _artifact(args.value_gate_json),
        "action_board_json": _artifact(args.action_board_json),
        "value_gate_status": _text(gate_summary.get("batch_native_provenance_value_gate_status")),
        "action_board_status": _text(
            action_board_summary.get("batch_native_provenance_value_action_board_status")
        ),
        "out_dir": _artifact(out_dir),
        "target_count": len(target_rows),
        "target_pass_count": len(target_rows) - len(blocked_rows),
        "target_blocked_count": len(blocked_rows),
        "action_expected_count": sum(expected_by_target.values()),
        "action_board_json_rows": len(action_rows),
        "action_json_row_mismatch_count": 0 if len(action_rows) == sum(expected_by_target.values()) else 1,
        "target_folder_present_count": sum(_int(row.get("folder_present")) for row in target_rows),
        "target_readme_present_count": sum(_int(row.get("readme_present")) for row in target_rows),
        "target_value_actions_present_count": sum(_int(row.get("value_actions_present")) for row in target_rows),
        "target_value_actions_expected_rows": sum(_int(row.get("expected_action_count")) for row in target_rows),
        "target_value_actions_csv_rows": sum(_int(row.get("value_actions_csv_rows")) for row in target_rows),
        "target_value_actions_row_mismatch_count": sum(
            _int(row.get("value_actions_row_mismatch")) for row in target_rows
        ),
        "coordinate_copy_count": coordinate_count,
        "target_coordinate_copy_count": sum(_int(row.get("coordinate_copy_count")) for row in target_rows),
        "competitive_proof_eligible_count": 0,
        "author_serialized_count": 0,
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_blocker": _text(first_blocked.get("blockers")).split(",")[0] if first_blocked else "",
        "input_blockers": ",".join(global_blockers),
        "next_action": "Fill the 36 operator values in the batch intake CSV, then rerun the value gate.",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": target_rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive Floor Batch Native/Provenance Value Action Board Completion Audit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['batch_native_provenance_value_action_board_completion_audit_status']}`",
        f"- targets pass/blocked/total: `{summary['target_pass_count']}/{summary['target_blocked_count']}/{summary['target_count']}`",
        f"- actions expected/json/mismatch: `{summary['action_expected_count']}/{summary['action_board_json_rows']}/{summary['action_json_row_mismatch_count']}`",
        f"- target files folder/readme/actions: `{summary['target_folder_present_count']}/{summary['target_readme_present_count']}/{summary['target_value_actions_present_count']}`",
        f"- target action rows expected/csv/mismatch: `{summary['target_value_actions_expected_rows']}/{summary['target_value_actions_csv_rows']}/{summary['target_value_actions_row_mismatch_count']}`",
        f"- coordinate copies board/target: `{summary['coordinate_copy_count']}/{summary['target_coordinate_copy_count']}`",
        f"- proof/author: `{summary['competitive_proof_eligible_count']}/{summary['author_serialized_count']}`",
        f"- first blocked: `{summary['first_blocked_target_id'] or '-'}` `{summary['first_blocker'] or '-'}`",
        "",
        "## Targets",
        "",
        "| target | status | files | rows | coordinates | blockers |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['audit_status']}` | "
            f"`{row['folder_present']}/{row['readme_present']}/{row['value_actions_present']}` | "
            f"`{row['expected_action_count']}/{row['value_actions_csv_rows']}/{row['value_actions_row_mismatch']}` | "
            f"`{row['coordinate_copy_count']}` | `{row['blockers'] or '-'}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit CASP17 batch native/provenance value action board completion."
    )
    parser.add_argument("--value-gate-json", default=DEFAULT_VALUE_GATE_JSON)
    parser.add_argument("--action-board-json", default=DEFAULT_ACTION_BOARD_JSON)
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
