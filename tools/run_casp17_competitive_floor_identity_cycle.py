#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import build_casp17_competitive_floor_execution_board as execution_board
from tools import build_casp17_competitive_floor_file_source_plan as file_source_plan
from tools import build_casp17_competitive_floor_readiness_gate as readiness_gate
from tools import build_casp17_competitive_floor_value_entry_plan as value_entry_plan
from tools import build_casp17_workbench_index as workbench_index
from tools import run_casp17_competitive_floor_identity_unlock_round as identity_round
from tools import sync_casp17_competitive_floor_identity_intake as identity_sync


DEFAULT_INTAKE_CSV = "casp17/casp17_competitive_floor_identity_intake_bundle_current.csv"
DEFAULT_IDENTITY_SYNC_JSON = "casp17/casp17_competitive_floor_identity_intake_sync_current.json"
DEFAULT_IDENTITY_SYNC_CSV = "casp17/casp17_competitive_floor_identity_intake_sync_current.csv"
DEFAULT_IDENTITY_SYNC_MD = "casp17/COMPETITIVE_FLOOR_IDENTITY_INTAKE_SYNC.md"
DEFAULT_DROPZONE_JSON = "casp17/casp17_competitive_floor_evidence_dropzone_current.json"
DEFAULT_IMPORT_CSV = "casp17/casp17_competitive_floor_evidence_import_current.csv"
DEFAULT_IMPORT_JSON = "casp17/casp17_competitive_floor_evidence_import_current.json"
DEFAULT_IMPORT_AUDIT_CSV = "casp17/casp17_competitive_floor_evidence_import_audit_current.csv"
DEFAULT_IMPORT_MD = "casp17/COMPETITIVE_FLOOR_EVIDENCE_IMPORT.md"
DEFAULT_CURRENT_TARGET_CSV = "casp17/casp17_target_model_folders_current.csv"
DEFAULT_IDENTITY_KIT_JSON = "casp17/casp17_competitive_floor_identity_unlock_kit_current.json"
DEFAULT_IDENTITY_KIT_CSV = "casp17/casp17_competitive_floor_identity_unlock_kit_current.csv"
DEFAULT_IDENTITY_KIT_MD = "casp17/COMPETITIVE_FLOOR_IDENTITY_UNLOCK_KIT.md"
DEFAULT_UNLOCK_PRIORITY_JSON = "casp17/casp17_competitive_floor_evidence_unlock_priority_current.json"
DEFAULT_UNLOCK_PRIORITY_CSV = "casp17/casp17_competitive_floor_evidence_unlock_priority_current.csv"
DEFAULT_UNLOCK_PRIORITY_MD = "casp17/COMPETITIVE_FLOOR_EVIDENCE_UNLOCK_PRIORITY.md"
DEFAULT_IDENTITY_ROUND_JSON = "casp17/casp17_competitive_floor_identity_unlock_round_current.json"
DEFAULT_IDENTITY_ROUND_CSV = "casp17/casp17_competitive_floor_identity_unlock_round_current.csv"
DEFAULT_IDENTITY_ROUND_MD = "casp17/COMPETITIVE_FLOOR_IDENTITY_UNLOCK_ROUND.md"
DEFAULT_FILE_SOURCE_PLAN_JSON = "casp17/casp17_competitive_floor_file_source_plan_current.json"
DEFAULT_FILE_SOURCE_PLAN_CSV = "casp17/casp17_competitive_floor_file_source_plan_current.csv"
DEFAULT_FILE_SOURCE_PLAN_MD = "casp17/COMPETITIVE_FLOOR_FILE_SOURCE_PLAN.md"
DEFAULT_VALUE_ENTRY_PLAN_JSON = "casp17/casp17_competitive_floor_value_entry_plan_current.json"
DEFAULT_VALUE_ENTRY_PLAN_CSV = "casp17/casp17_competitive_floor_value_entry_plan_current.csv"
DEFAULT_VALUE_ENTRY_PLAN_MD = "casp17/COMPETITIVE_FLOOR_VALUE_ENTRY_PLAN.md"
DEFAULT_EXECUTION_BOARD_JSON = "casp17/casp17_competitive_floor_execution_board_current.json"
DEFAULT_EXECUTION_BOARD_CSV = "casp17/casp17_competitive_floor_execution_board_current.csv"
DEFAULT_EXECUTION_BOARD_MD = "casp17/COMPETITIVE_FLOOR_EXECUTION_BOARD.md"
DEFAULT_READINESS_GATE_JSON = "casp17/casp17_competitive_floor_readiness_gate_current.json"
DEFAULT_READINESS_GATE_CSV = "casp17/casp17_competitive_floor_readiness_gate_current.csv"
DEFAULT_READINESS_GATE_MD = "casp17/COMPETITIVE_FLOOR_READINESS_GATE.md"
DEFAULT_WORKBENCH_JSON = "casp17/casp17_workbench_index_current.json"
DEFAULT_WORKBENCH_CSV = "casp17/casp17_workbench_index_current.csv"
DEFAULT_WORKBENCH_MD = "casp17/WORKBENCH.md"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_identity_cycle_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_identity_cycle_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_IDENTITY_CYCLE.md"

CYCLE_COLUMNS = [
    "stage",
    "status",
    "path",
    "ready_count",
    "awaiting_count",
    "blocked_count",
    "total_count",
    "next_action",
]
READY_STATUSES = {
    "complete",
    "identity_unlocked_continue_file_sources",
    "pass",
    "ready",
    "ready_for_competitive_floor",
    "ready_for_evidence_import",
    "ready_for_operator_fill",
    "ready_for_review",
    "synced",
}
CLAIM_BOUNDARY = (
    "Local CASP17 competitive-floor identity cycle only. It chains the existing identity intake sync, identity "
    "unlock round, identity-aware file/value plans, execution board, readiness gate, and workbench refresh. It "
    "does not choose targets, clear no-leak provenance, fetch native structures, score native accuracy, run "
    "predictors, mutate row_fill.csv directly, copy evidence files unless downstream apply flags are explicitly "
    "provided, or submit to CASP."
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


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CYCLE_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Identity Cycle",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- identity_cycle_status: `{summary['identity_cycle_status']}`",
        f"- apply_sync/apply_identity/apply_import: `{summary['apply_sync']}/{summary['apply_identity']}/{summary['apply_import']}`",
        f"- stages ready/blocked/total: `{summary['ready_stage_count']}/{summary['blocked_stage_count']}/{summary['stage_count']}`",
        f"- sync status: `{summary['sync_status']}` rows synced/ready/awaiting/blocked `{summary['sync_synced_count']}/{summary['sync_ready_to_sync_count']}/{summary['sync_awaiting_count']}/{summary['sync_blocked_count']}` missing fields `{summary['sync_missing_field_count']}` applied `{summary['sync_applied_count']}`",
        f"- identity round: `{summary['identity_round_status']}` ready/awaiting/blocked `{summary['identity_ready_for_import_count']}/{summary['identity_awaiting_count']}/{summary['identity_blocked_count']}`",
        f"- file/value plans: `{summary['file_source_plan_status']}`/`{summary['value_entry_plan_status']}`",
        f"- execution/readiness/workbench: `{summary['execution_board_status']}`/`{summary['readiness_gate_status']}`/`{summary['workbench_status'] or '-'}`",
        f"- first next action: {summary['first_next_action'] or '-'}",
        "",
        "## Cycle Stages",
        "",
        "| stage | status | ready | awaiting | blocked | total | path | next action |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['stage']}` | `{row['status']}` | {row['ready_count']} | {row['awaiting_count']} | "
            f"{row['blocked_count']} | {row['total_count']} | `{row['path']}` | {row['next_action'] or '-'} |"
        )
    if not payload["rows"]:
        lines.append("| - | `ready` | 0 | 0 | 0 | 0 | - | no cycle stages |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _run_identity_sync(args: argparse.Namespace) -> dict[str, Any]:
    argv = [
        "--intake-csv",
        args.intake_csv,
        "--kit-csv",
        args.identity_kit_csv,
        "--out-json",
        args.identity_sync_json,
        "--out-csv",
        args.identity_sync_csv,
        "--out-md",
        args.identity_sync_md,
    ]
    if args.apply_sync:
        argv.append("--apply")
    sync_args = identity_sync.parse_args(argv)
    payload = identity_sync.build_payload(sync_args)
    identity_sync.write_outputs(sync_args, payload)
    return payload


def _run_identity_round(args: argparse.Namespace) -> dict[str, Any]:
    argv = [
        "--dropzone-json",
        args.dropzone_json,
        "--import-csv",
        args.import_csv,
        "--import-json",
        args.import_json,
        "--import-audit-csv",
        args.import_audit_csv,
        "--import-md",
        args.import_md,
        "--current-target-csv",
        args.current_target_csv,
        "--identity-kit-json",
        args.identity_kit_json,
        "--identity-kit-csv",
        args.identity_kit_csv,
        "--identity-kit-md",
        args.identity_kit_md,
        "--unlock-priority-json",
        args.unlock_priority_json,
        "--unlock-priority-csv",
        args.unlock_priority_csv,
        "--unlock-priority-md",
        args.unlock_priority_md,
        "--out-json",
        args.identity_round_json,
        "--out-csv",
        args.identity_round_csv,
        "--out-md",
        args.identity_round_md,
    ]
    if args.apply_identity:
        argv.append("--apply-identity")
    if args.apply_import:
        argv.append("--apply-import")
    round_args = identity_round.parse_args(argv)
    payload = identity_round.build_payload(round_args)
    identity_round.write_outputs(round_args, payload)
    return payload


def _run_file_source_plan(args: argparse.Namespace) -> dict[str, Any]:
    plan_args = file_source_plan.parse_args(
        [
            "--import-csv",
            args.import_csv,
            "--identity-kit-json",
            args.identity_kit_json,
            "--identity-kit-csv",
            args.identity_kit_csv,
            "--current-target-csv",
            args.current_target_csv,
            "--out-json",
            args.file_source_plan_json,
            "--out-csv",
            args.file_source_plan_csv,
            "--out-md",
            args.file_source_plan_md,
        ]
    )
    payload = file_source_plan.build_payload(plan_args)
    file_source_plan.write_outputs(plan_args, payload)
    return payload


def _run_value_entry_plan(args: argparse.Namespace) -> dict[str, Any]:
    plan_args = value_entry_plan.parse_args(
        [
            "--import-csv",
            args.import_csv,
            "--identity-kit-json",
            args.identity_kit_json,
            "--identity-kit-csv",
            args.identity_kit_csv,
            "--out-json",
            args.value_entry_plan_json,
            "--out-csv",
            args.value_entry_plan_csv,
            "--out-md",
            args.value_entry_plan_md,
        ]
    )
    payload = value_entry_plan.build_payload(plan_args)
    value_entry_plan.write_outputs(plan_args, payload)
    return payload


def _run_execution_board(args: argparse.Namespace) -> dict[str, Any]:
    board_args = execution_board.parse_args(
        [
            "--identity-kit-json",
            args.identity_kit_json,
            "--file-source-plan-json",
            args.file_source_plan_json,
            "--value-entry-plan-json",
            args.value_entry_plan_json,
            "--out-json",
            args.execution_board_json,
            "--out-csv",
            args.execution_board_csv,
            "--out-md",
            args.execution_board_md,
        ]
    )
    payload = execution_board.build_payload(board_args)
    execution_board.write_outputs(board_args, payload)
    return payload


def _run_readiness_gate(args: argparse.Namespace) -> dict[str, Any]:
    gate_args = readiness_gate.parse_args(
        [
            "--execution-board-json",
            args.execution_board_json,
            "--out-json",
            args.readiness_gate_json,
            "--out-csv",
            args.readiness_gate_csv,
            "--out-md",
            args.readiness_gate_md,
        ]
    )
    payload = readiness_gate.build_payload(gate_args)
    readiness_gate.write_outputs(gate_args, payload)
    return payload


def _run_workbench(args: argparse.Namespace) -> dict[str, Any]:
    workbench_args = workbench_index.parse_args(
        [
            "--competitive-identity-cycle-json",
            args.out_json,
            "--out-json",
            args.workbench_json,
            "--out-csv",
            args.workbench_csv,
            "--out-md",
            args.workbench_md,
        ]
    )
    payload = workbench_index.build_payload(workbench_args)
    workbench_index._write_json(workbench_args.out_json, payload)
    workbench_index._write_csv(workbench_args.out_csv, payload["rows"])
    workbench_index._write_md(workbench_args.out_md, payload)
    return payload


def _stage_row(
    stage: str,
    status: str,
    path_like: str,
    *,
    ready: int,
    awaiting: int = 0,
    blocked: int = 0,
    total: int = 0,
    next_action: str = "",
) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": status or "missing",
        "path": _artifact(path_like),
        "ready_count": ready,
        "awaiting_count": awaiting,
        "blocked_count": blocked,
        "total_count": total,
        "next_action": next_action,
    }


def _first_next_action(rows: list[dict[str, Any]]) -> str:
    for row in rows:
        if _text(row.get("status")) not in READY_STATUSES:
            return _text(row.get("next_action"))
    return _text(rows[0].get("next_action")) if rows else ""


def _cycle_status(args: argparse.Namespace, summaries: dict[str, dict[str, Any]]) -> str:
    sync_status = _text(summaries["sync"].get("identity_intake_sync_status"))
    if sync_status == "blocked":
        return "blocked"
    if sync_status == "awaiting_intake":
        return "awaiting_intake"
    if sync_status == "ready_to_sync" and not args.apply_sync:
        return "ready_to_sync"
    round_status = _text(summaries["identity_round"].get("identity_round_status"))
    if round_status in {
        "blocked_identity",
        "awaiting_identity",
        "ready_for_identity_apply",
        "ready_for_identity_import_apply",
    }:
        return round_status
    gate_status = _text(summaries["readiness_gate"].get("readiness_gate_status"))
    if gate_status:
        return gate_status
    return (
        _text(summaries["execution_board"].get("execution_board_status"))
        or _text(summaries["file_source_plan"].get("file_source_status"))
        or _text(summaries["value_entry_plan"].get("value_entry_status"))
        or "missing"
    )


def _build_cycle_payload(
    args: argparse.Namespace,
    payloads: dict[str, dict[str, Any]],
    *,
    workbench_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summaries = {name: _summary(payload) for name, payload in payloads.items()}
    workbench_summary = _summary(workbench_payload or {})
    rows = [
        _stage_row(
            "identity_sync",
            _text(summaries["sync"].get("identity_intake_sync_status")),
            args.identity_sync_json,
            ready=(
                _int(summaries["sync"].get("synced_count"))
                + _int(summaries["sync"].get("ready_to_sync_count"))
            ),
            awaiting=_int(summaries["sync"].get("awaiting_intake_count")),
            blocked=_int(summaries["sync"].get("blocked_count")),
            total=_int(summaries["sync"].get("row_count")),
            next_action=_text(summaries["sync"].get("first_open_next_action")),
        ),
        _stage_row(
            "identity_round",
            _text(summaries["identity_round"].get("identity_round_status")),
            args.identity_round_json,
            ready=(
                _int(summaries["identity_round"].get("identity_ready_for_import_count"))
                + _int(summaries["identity_round"].get("import_ready_for_apply_count"))
            ),
            awaiting=_int(summaries["identity_round"].get("identity_awaiting_count")),
            blocked=(
                _int(summaries["identity_round"].get("identity_blocked_count"))
                + _int(summaries["identity_round"].get("target_id_open_count"))
            ),
            total=_int(summaries["identity_round"].get("row_count")),
            next_action=_text(summaries["identity_round"].get("first_next_action")),
        ),
        _stage_row(
            "file_source_plan",
            _text(summaries["file_source_plan"].get("file_source_status")),
            args.file_source_plan_json,
            ready=(
                _int(summaries["file_source_plan"].get("ready_for_import_count"))
                + _int(summaries["file_source_plan"].get("already_imported_count"))
            ),
            awaiting=(
                _int(summaries["file_source_plan"].get("waiting_on_identity_count"))
                + _int(summaries["file_source_plan"].get("awaiting_source_path_count"))
            ),
            blocked=(
                _int(summaries["file_source_plan"].get("identity_blocked_file_count"))
                + _int(summaries["file_source_plan"].get("blocked_file_source_count"))
            ),
            total=_int(summaries["file_source_plan"].get("file_action_count")),
            next_action=_text(summaries["file_source_plan"].get("first_open_next_action")),
        ),
        _stage_row(
            "value_entry_plan",
            _text(summaries["value_entry_plan"].get("value_entry_status")),
            args.value_entry_plan_json,
            ready=(
                _int(summaries["value_entry_plan"].get("ready_from_identity_kit_count"))
                + _int(summaries["value_entry_plan"].get("ready_for_import_count"))
            ),
            awaiting=(
                _int(summaries["value_entry_plan"].get("waiting_on_identity_count"))
                + _int(summaries["value_entry_plan"].get("awaiting_value_count"))
                + _int(summaries["value_entry_plan"].get("awaiting_clearance_count"))
                + _int(summaries["value_entry_plan"].get("awaiting_evidence_ref_count"))
            ),
            blocked=_int(summaries["value_entry_plan"].get("blocked_value_count")),
            total=_int(summaries["value_entry_plan"].get("value_action_count")),
            next_action=_text(summaries["value_entry_plan"].get("first_open_next_action")),
        ),
        _stage_row(
            "execution_board",
            _text(summaries["execution_board"].get("execution_board_status")),
            args.execution_board_json,
            ready=_int(summaries["execution_board"].get("total_ready_action_count")),
            awaiting=(
                _int(summaries["execution_board"].get("awaiting_identity_row_count"))
                + _int(summaries["execution_board"].get("ready_for_identity_apply_row_count"))
                + _int(summaries["execution_board"].get("awaiting_file_source_row_count"))
                + _int(summaries["execution_board"].get("awaiting_value_row_count"))
                + _int(summaries["execution_board"].get("ready_for_evidence_import_row_count"))
            ),
            blocked=_int(summaries["execution_board"].get("blocked_row_count")),
            total=_int(summaries["execution_board"].get("row_count")),
            next_action=_text(summaries["execution_board"].get("first_open_next_action")),
        ),
        _stage_row(
            "readiness_gate",
            _text(summaries["readiness_gate"].get("readiness_gate_status")),
            args.readiness_gate_json,
            ready=_int(summaries["readiness_gate"].get("pass_count")),
            blocked=_int(summaries["readiness_gate"].get("blocked_gate_count")),
            total=_int(summaries["readiness_gate"].get("gate_count")),
            next_action=_text(summaries["readiness_gate"].get("first_blocked_next_action")),
        ),
    ]
    if workbench_payload is not None:
        rows.append(
            _stage_row(
                "workbench",
                _text(workbench_summary.get("workbench_status")),
                args.workbench_json,
                ready=_int(workbench_summary.get("target_model_ready_count")),
                blocked=max(
                    0,
                    _int(workbench_summary.get("target_model_count"))
                    - _int(workbench_summary.get("target_model_ready_count")),
                ),
                total=_int(workbench_summary.get("target_model_count")),
                next_action=_text(workbench_summary.get("first_operator_fill_action")),
            )
        )
    ready_stage_count = sum(1 for row in rows if _text(row.get("status")) in READY_STATUSES)
    blocked_stage_count = len(rows) - ready_stage_count
    summary = {
        "packet_type": "casp17_competitive_floor_identity_cycle",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "identity_cycle_status": _cycle_status(args, summaries),
        "apply_sync": bool(args.apply_sync),
        "apply_identity": bool(args.apply_identity),
        "apply_import": bool(args.apply_import),
        "stage_count": len(rows),
        "ready_stage_count": ready_stage_count,
        "blocked_stage_count": blocked_stage_count,
        "sync_status": _text(summaries["sync"].get("identity_intake_sync_status")),
        "sync_synced_count": _int(summaries["sync"].get("synced_count")),
        "sync_ready_to_sync_count": _int(summaries["sync"].get("ready_to_sync_count")),
        "sync_awaiting_count": _int(summaries["sync"].get("awaiting_intake_count")),
        "sync_blocked_count": _int(summaries["sync"].get("blocked_count")),
        "sync_missing_field_count": _int(summaries["sync"].get("missing_field_count")),
        "sync_applied_count": _int(summaries["sync"].get("applied_sync_count")),
        "identity_round_status": _text(summaries["identity_round"].get("identity_round_status")),
        "identity_ready_for_import_count": _int(summaries["identity_round"].get("identity_ready_for_import_count")),
        "identity_awaiting_count": _int(summaries["identity_round"].get("identity_awaiting_count")),
        "identity_blocked_count": _int(summaries["identity_round"].get("identity_blocked_count")),
        "identity_import_ready_for_apply_count": _int(summaries["identity_round"].get("import_ready_for_apply_count")),
        "identity_import_applied_count": _int(summaries["identity_round"].get("import_applied_count")),
        "file_source_plan_status": _text(summaries["file_source_plan"].get("file_source_status")),
        "file_source_action_count": _int(summaries["file_source_plan"].get("file_action_count")),
        "file_source_waiting_on_identity_count": _int(
            summaries["file_source_plan"].get("waiting_on_identity_count")
        ),
        "value_entry_plan_status": _text(summaries["value_entry_plan"].get("value_entry_status")),
        "value_entry_action_count": _int(summaries["value_entry_plan"].get("value_action_count")),
        "value_entry_waiting_on_identity_count": _int(summaries["value_entry_plan"].get("waiting_on_identity_count")),
        "execution_board_status": _text(summaries["execution_board"].get("execution_board_status")),
        "execution_board_row_count": _int(summaries["execution_board"].get("row_count")),
        "readiness_gate_status": _text(summaries["readiness_gate"].get("readiness_gate_status")),
        "readiness_gate_pass_count": _int(summaries["readiness_gate"].get("pass_count")),
        "readiness_gate_blocked_count": _int(summaries["readiness_gate"].get("blocked_gate_count")),
        "readiness_gate_first_blocked_gate_id": _text(summaries["readiness_gate"].get("first_blocked_gate_id")),
        "workbench_status": _text(workbench_summary.get("workbench_status")),
        "first_next_action": _first_next_action(rows),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    payloads = {
        "sync": _run_identity_sync(args),
        "identity_round": _run_identity_round(args),
        "file_source_plan": _run_file_source_plan(args),
        "value_entry_plan": _run_value_entry_plan(args),
        "execution_board": _run_execution_board(args),
        "readiness_gate": _run_readiness_gate(args),
    }
    payload = _build_cycle_payload(args, payloads)
    write_outputs(args, payload)
    workbench_payload = _run_workbench(args)
    return _build_cycle_payload(args, payloads, workbench_payload=workbench_payload)


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the CASP17 competitive-floor identity progression cycle.")
    parser.add_argument("--intake-csv", default=DEFAULT_INTAKE_CSV)
    parser.add_argument("--identity-sync-json", default=DEFAULT_IDENTITY_SYNC_JSON)
    parser.add_argument("--identity-sync-csv", default=DEFAULT_IDENTITY_SYNC_CSV)
    parser.add_argument("--identity-sync-md", default=DEFAULT_IDENTITY_SYNC_MD)
    parser.add_argument("--dropzone-json", default=DEFAULT_DROPZONE_JSON)
    parser.add_argument("--import-csv", default=DEFAULT_IMPORT_CSV)
    parser.add_argument("--import-json", default=DEFAULT_IMPORT_JSON)
    parser.add_argument("--import-audit-csv", default=DEFAULT_IMPORT_AUDIT_CSV)
    parser.add_argument("--import-md", default=DEFAULT_IMPORT_MD)
    parser.add_argument("--current-target-csv", default=DEFAULT_CURRENT_TARGET_CSV)
    parser.add_argument("--identity-kit-json", default=DEFAULT_IDENTITY_KIT_JSON)
    parser.add_argument("--identity-kit-csv", default=DEFAULT_IDENTITY_KIT_CSV)
    parser.add_argument("--identity-kit-md", default=DEFAULT_IDENTITY_KIT_MD)
    parser.add_argument("--unlock-priority-json", default=DEFAULT_UNLOCK_PRIORITY_JSON)
    parser.add_argument("--unlock-priority-csv", default=DEFAULT_UNLOCK_PRIORITY_CSV)
    parser.add_argument("--unlock-priority-md", default=DEFAULT_UNLOCK_PRIORITY_MD)
    parser.add_argument("--identity-round-json", default=DEFAULT_IDENTITY_ROUND_JSON)
    parser.add_argument("--identity-round-csv", default=DEFAULT_IDENTITY_ROUND_CSV)
    parser.add_argument("--identity-round-md", default=DEFAULT_IDENTITY_ROUND_MD)
    parser.add_argument("--file-source-plan-json", default=DEFAULT_FILE_SOURCE_PLAN_JSON)
    parser.add_argument("--file-source-plan-csv", default=DEFAULT_FILE_SOURCE_PLAN_CSV)
    parser.add_argument("--file-source-plan-md", default=DEFAULT_FILE_SOURCE_PLAN_MD)
    parser.add_argument("--value-entry-plan-json", default=DEFAULT_VALUE_ENTRY_PLAN_JSON)
    parser.add_argument("--value-entry-plan-csv", default=DEFAULT_VALUE_ENTRY_PLAN_CSV)
    parser.add_argument("--value-entry-plan-md", default=DEFAULT_VALUE_ENTRY_PLAN_MD)
    parser.add_argument("--execution-board-json", default=DEFAULT_EXECUTION_BOARD_JSON)
    parser.add_argument("--execution-board-csv", default=DEFAULT_EXECUTION_BOARD_CSV)
    parser.add_argument("--execution-board-md", default=DEFAULT_EXECUTION_BOARD_MD)
    parser.add_argument("--readiness-gate-json", default=DEFAULT_READINESS_GATE_JSON)
    parser.add_argument("--readiness-gate-csv", default=DEFAULT_READINESS_GATE_CSV)
    parser.add_argument("--readiness-gate-md", default=DEFAULT_READINESS_GATE_MD)
    parser.add_argument("--workbench-json", default=DEFAULT_WORKBENCH_JSON)
    parser.add_argument("--workbench-csv", default=DEFAULT_WORKBENCH_CSV)
    parser.add_argument("--workbench-md", default=DEFAULT_WORKBENCH_MD)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--apply-sync", action="store_true")
    parser.add_argument("--apply-identity", action="store_true")
    parser.add_argument("--apply-import", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
