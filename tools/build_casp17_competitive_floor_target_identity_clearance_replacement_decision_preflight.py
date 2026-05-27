#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DECISION_BUNDLE_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_replacement_decision_bundle_current.json"
)
DEFAULT_OUT_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_replacement_decision_preflight_current.json"
)
DEFAULT_OUT_CSV = (
    "casp17/casp17_competitive_floor_target_identity_clearance_replacement_decision_preflight_current.csv"
)
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_DECISION_PREFLIGHT.md"

NEW_UNIQUE_REQUIRED = [
    "proposed_candidate_target_id",
    "proposed_candidate_name",
    "closed_protein_target",
    "current_target_collision_checked",
    "cancellation_checked",
    "local_prediction_pdb",
    "raw_validation_json",
    "scorecard_json",
    "no_leak_evidence_ref",
    "operator_clearance",
    "operator",
]
DUPLICATE_EXCEPTION_REQUIRED = [
    "allow_duplicate_reuse",
    "no_leak_evidence_ref",
    "operator_clearance",
    "operator",
    "approval_date",
    "rationale",
]
TRUE_VALUES = {"true", "yes", "y", "1", "approved", "clear"}
TARGET_ID_RE = re.compile(r"^[A-Z][0-9]{4,}[A-Za-z0-9_.-]*$")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
CLAIM_BOUNDARY = (
    "Local CASP17 replacement decision preflight only. It validates whether a filled replacement decision bundle "
    "contains either a safe new unique candidate path or an explicit duplicate-reuse exception. It does not choose "
    "targets, approve exceptions, fetch native structures, clear no-leak provenance, mutate replacement workorders, "
    "score native accuracy, or submit to CASP."
)

PREFLIGHT_COLUMNS = [
    "replace_target_id",
    "replace_target_name",
    "decision_status",
    "preflight_status",
    "new_unique_status",
    "duplicate_exception_status",
    "ready_branch",
    "new_unique_candidate_target_id",
    "duplicate_candidate_target_id",
    "new_unique_blockers",
    "duplicate_exception_blockers",
    "next_action",
    "decision_folder",
    "new_unique_candidate_intake_csv",
    "duplicate_reuse_exception_csv",
    "decision_md",
]


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


def _read_csv_rows(path_like: str | Path) -> list[dict[str, str]]:
    path_value = _text(path_like)
    if not path_value:
        return []
    path = _resolve(path_value)
    if not path.is_file():
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except OSError:
        return []


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PREFLIGHT_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _is_placeholder(value: Any) -> bool:
    text = _text(value)
    return not text or "REQUIRED" in text or "YYYY-MM-DD" in text


def _is_true(value: Any) -> bool:
    return _text(value).lower() in TRUE_VALUES


def _path_present(path_like: Any) -> bool:
    value = _text(path_like)
    return bool(value) and not _is_placeholder(value) and _resolve(value).is_file()


def _first_row(path_like: str | Path) -> dict[str, str]:
    rows = _read_csv_rows(path_like)
    return rows[0] if rows else {}


def _new_unique_blockers(row: dict[str, str]) -> list[str]:
    blockers: list[str] = []
    if not row:
        return ["new_unique_candidate_intake_missing"]
    for key in NEW_UNIQUE_REQUIRED:
        if _is_placeholder(row.get(key)):
            blockers.append(f"{key}_required")
    target_id = _text(row.get("proposed_candidate_target_id")).upper()
    if target_id and not _is_placeholder(target_id) and not TARGET_ID_RE.match(target_id):
        blockers.append("proposed_candidate_target_id_invalid")
    for key in ("closed_protein_target", "current_target_collision_checked", "cancellation_checked"):
        if not _is_placeholder(row.get(key)) and not _is_true(row.get(key)):
            blockers.append(f"{key}_must_be_true")
    for key in ("local_prediction_pdb", "raw_validation_json", "scorecard_json"):
        if not _path_present(row.get(key)):
            blockers.append(f"{key}_not_found")
    return list(dict.fromkeys(blockers))


def _duplicate_exception_blockers(row: dict[str, str]) -> list[str]:
    blockers: list[str] = []
    if not row:
        return ["duplicate_reuse_exception_missing"]
    for key in DUPLICATE_EXCEPTION_REQUIRED:
        if _is_placeholder(row.get(key)):
            blockers.append(f"{key}_required")
    if not _is_placeholder(row.get("allow_duplicate_reuse")) and not _is_true(row.get("allow_duplicate_reuse")):
        blockers.append("allow_duplicate_reuse_must_be_true")
    approval_date = _text(row.get("approval_date"))
    if approval_date and not _is_placeholder(approval_date) and not DATE_RE.match(approval_date):
        blockers.append("approval_date_invalid")
    if _is_placeholder(row.get("duplicate_candidate_target_id")):
        blockers.append("duplicate_candidate_target_id_required")
    return list(dict.fromkeys(blockers))


def _status(blockers: list[str], ready_status: str) -> str:
    return ready_status if not blockers else "awaiting_operator_input"


def _preflight_status(new_unique_status: str, duplicate_status: str) -> tuple[str, str, str]:
    new_ready = new_unique_status == "ready_new_unique_candidate"
    duplicate_ready = duplicate_status == "ready_duplicate_reuse_exception"
    if new_ready and duplicate_ready:
        return ("blocked_conflicting_decisions", "conflict", "choose exactly one decision branch")
    if new_ready:
        return (
            "ready_new_unique_candidate",
            "new_unique",
            "rerun replacement queue/workorders with the approved unique candidate input",
        )
    if duplicate_ready:
        return (
            "ready_duplicate_reuse_exception",
            "duplicate_reuse_exception",
            "rerun replacement workorders with explicit duplicate reuse exception attached",
        )
    return (
        "awaiting_operator_decision",
        "",
        "fill either the new unique candidate intake or the duplicate reuse exception, then rerun this preflight",
    )


def _build_row(decision_row: dict[str, Any]) -> dict[str, Any]:
    new_unique_csv = _text(decision_row.get("new_unique_candidate_intake_csv"))
    duplicate_exception_csv = _text(decision_row.get("duplicate_reuse_exception_csv"))
    new_unique_row = _first_row(new_unique_csv)
    duplicate_row = _first_row(duplicate_exception_csv)
    new_unique_blockers = _new_unique_blockers(new_unique_row)
    duplicate_blockers = _duplicate_exception_blockers(duplicate_row)
    new_unique_status = _status(new_unique_blockers, "ready_new_unique_candidate")
    duplicate_status = _status(duplicate_blockers, "ready_duplicate_reuse_exception")
    preflight_status, ready_branch, next_action = _preflight_status(new_unique_status, duplicate_status)
    return {
        "replace_target_id": _text(decision_row.get("replace_target_id")),
        "replace_target_name": _text(decision_row.get("replace_target_name")),
        "decision_status": _text(decision_row.get("decision_status")),
        "preflight_status": preflight_status,
        "new_unique_status": new_unique_status,
        "duplicate_exception_status": duplicate_status,
        "ready_branch": ready_branch,
        "new_unique_candidate_target_id": _text(new_unique_row.get("proposed_candidate_target_id")),
        "duplicate_candidate_target_id": _text(duplicate_row.get("duplicate_candidate_target_id")),
        "new_unique_blockers": ",".join(new_unique_blockers),
        "duplicate_exception_blockers": ",".join(duplicate_blockers),
        "next_action": next_action,
        "decision_folder": _text(decision_row.get("decision_folder")),
        "new_unique_candidate_intake_csv": new_unique_csv,
        "duplicate_reuse_exception_csv": duplicate_exception_csv,
        "decision_md": _text(decision_row.get("decision_md")),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    decision_payload = _read_json(args.decision_bundle_json)
    decision_rows = _rows(decision_payload)
    rows = [_build_row(row) for row in decision_rows]
    ready_new_unique = sum(1 for row in rows if row["preflight_status"] == "ready_new_unique_candidate")
    ready_duplicate = sum(1 for row in rows if row["preflight_status"] == "ready_duplicate_reuse_exception")
    conflict_count = sum(1 for row in rows if row["preflight_status"] == "blocked_conflicting_decisions")
    awaiting_count = sum(1 for row in rows if row["preflight_status"] == "awaiting_operator_decision")
    if not rows:
        preflight_status = "no_decisions"
    elif conflict_count:
        preflight_status = "blocked_conflicting_decisions"
    elif ready_new_unique or ready_duplicate:
        preflight_status = "ready"
    else:
        preflight_status = "awaiting_operator_decision"
    first_open = next(
        (row for row in rows if row["preflight_status"] in {"awaiting_operator_decision", "blocked_conflicting_decisions"}),
        rows[0] if rows else {},
    )
    summary = {
        "packet_type": "casp17_competitive_floor_target_identity_clearance_replacement_decision_preflight",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision_preflight_status": preflight_status,
        "decision_bundle_json": _artifact(args.decision_bundle_json),
        "decision_bundle_status": _text(_summary(decision_payload).get("decision_bundle_status")),
        "decision_row_count": len(rows),
        "ready_new_unique_count": ready_new_unique,
        "ready_duplicate_exception_count": ready_duplicate,
        "awaiting_operator_decision_count": awaiting_count,
        "conflict_count": conflict_count,
        "new_unique_blocker_count": sum(1 for row in rows if row["new_unique_blockers"]),
        "duplicate_exception_blocker_count": sum(1 for row in rows if row["duplicate_exception_blockers"]),
        "first_open_replace_target_id": _text(first_open.get("replace_target_id")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Replacement Decision Preflight",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- decision_preflight_status: `{summary['decision_preflight_status']}`",
        f"- decision_bundle_status: `{summary['decision_bundle_status'] or '-'}`",
        f"- decisions ready-new/ready-duplicate/awaiting/conflict/total: `{summary['ready_new_unique_count']}/{summary['ready_duplicate_exception_count']}/{summary['awaiting_operator_decision_count']}/{summary['conflict_count']}/{summary['decision_row_count']}`",
        f"- blocker rows new-unique/duplicate-exception: `{summary['new_unique_blocker_count']}/{summary['duplicate_exception_blocker_count']}`",
        f"- first open: `{summary['first_open_replace_target_id'] or '-'}`",
        f"- first next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Preflight Rows",
        "",
        "| replace | preflight | new unique | duplicate exception | ready branch | next action | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        blockers = ";".join(
            blocker
            for blocker in (row["new_unique_blockers"], row["duplicate_exception_blockers"])
            if blocker
        )
        lines.append(
            f"| `{row['replace_target_id']}` | `{row['preflight_status']}` | `{row['new_unique_status']}` | "
            f"`{row['duplicate_exception_status']}` | `{row['ready_branch'] or '-'}` | {row['next_action']} | "
            f"`{blockers or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | `no_decisions` | - | - | - | no replacement decision rows | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight CASP17 replacement decision bundle inputs.")
    parser.add_argument("--decision-bundle-json", default=DEFAULT_DECISION_BUNDLE_JSON)
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
