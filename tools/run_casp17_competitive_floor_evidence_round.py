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

from tools import build_casp17_competitive_floor_evidence_import_packet as evidence_import
from tools import build_casp17_competitive_floor_evidence_intake_packet as evidence_intake
from tools import build_casp17_competitive_floor_row_fill_apply_plan as apply_plan
from tools import build_casp17_competitive_floor_row_fill_patch_gate as patch_gate
from tools import build_casp17_competitive_floor_value_ledger_packet as value_ledger


DEFAULT_DROPZONE_JSON = "casp17/casp17_competitive_floor_evidence_dropzone_current.json"
DEFAULT_IMPORT_CSV = "casp17/casp17_competitive_floor_evidence_import_current.csv"
DEFAULT_IMPORT_JSON = "casp17/casp17_competitive_floor_evidence_import_current.json"
DEFAULT_IMPORT_AUDIT_CSV = "casp17/casp17_competitive_floor_evidence_import_audit_current.csv"
DEFAULT_IMPORT_MD = "casp17/COMPETITIVE_FLOOR_EVIDENCE_IMPORT.md"
DEFAULT_VALUE_LEDGER_JSON = "casp17/casp17_competitive_floor_value_ledger_current.json"
DEFAULT_VALUE_LEDGER_CSV = "casp17/casp17_competitive_floor_value_ledger_current.csv"
DEFAULT_VALUE_LEDGER_MD = "casp17/COMPETITIVE_FLOOR_VALUE_LEDGER.md"
DEFAULT_INTAKE_JSON = "casp17/casp17_competitive_floor_evidence_intake_current.json"
DEFAULT_INTAKE_CSV = "casp17/casp17_competitive_floor_evidence_intake_current.csv"
DEFAULT_INTAKE_MD = "casp17/COMPETITIVE_FLOOR_EVIDENCE_INTAKE.md"
DEFAULT_PATCH_GATE_JSON = "casp17/casp17_competitive_floor_row_fill_patch_gate_current.json"
DEFAULT_PATCH_GATE_CSV = "casp17/casp17_competitive_floor_row_fill_patch_gate_current.csv"
DEFAULT_PATCH_GATE_MD = "casp17/COMPETITIVE_FLOOR_ROW_FILL_PATCH_GATE.md"
DEFAULT_APPLY_PLAN_JSON = "casp17/casp17_competitive_floor_row_fill_apply_plan_current.json"
DEFAULT_APPLY_PLAN_CSV = "casp17/casp17_competitive_floor_row_fill_apply_plan_current.csv"
DEFAULT_APPLY_PLAN_MD = "casp17/COMPETITIVE_FLOOR_ROW_FILL_APPLY_PLAN.md"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_evidence_round_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_evidence_round_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_EVIDENCE_ROUND.md"

CLAIM_BOUNDARY = (
    "Local competitive-floor evidence round only. It runs the local evidence import, value-ledger audit, "
    "evidence intake, row_fill patch gate, and row_fill apply-plan in order. It does not choose targets, "
    "clear no-leak provenance, fetch native structures, score native accuracy, run predictors, submit to CASP, "
    "or mutate row_fill.csv unless --apply-row-fill is explicitly provided."
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
        fieldnames = ["stage", "status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _run_import(args: argparse.Namespace) -> dict[str, Any]:
    argv = [
        "--dropzone-json",
        args.dropzone_json,
        "--import-csv",
        args.import_csv,
        "--out-json",
        args.import_json,
        "--out-csv",
        args.import_audit_csv,
        "--out-md",
        args.import_md,
    ]
    if args.apply_import:
        argv.append("--apply")
    if args.overwrite_import:
        argv.append("--overwrite")
    packet_args = evidence_import.parse_args(argv)
    payload = evidence_import.build_payload(packet_args)
    evidence_import.write_outputs(packet_args, payload)
    return payload


def _run_value_ledger(args: argparse.Namespace) -> dict[str, Any]:
    packet_args = value_ledger.parse_args(
        [
            "--dropzone-json",
            args.dropzone_json,
            "--out-json",
            args.value_ledger_json,
            "--out-csv",
            args.value_ledger_csv,
            "--out-md",
            args.value_ledger_md,
        ]
    )
    payload = value_ledger.build_payload(packet_args)
    value_ledger.write_outputs(packet_args, payload)
    return payload


def _run_intake(args: argparse.Namespace) -> dict[str, Any]:
    packet_args = evidence_intake.parse_args(
        [
            "--dropzone-json",
            args.dropzone_json,
            "--out-json",
            args.intake_json,
            "--out-csv",
            args.intake_csv,
            "--out-md",
            args.intake_md,
        ]
    )
    payload = evidence_intake.build_payload(packet_args)
    evidence_intake.write_outputs(packet_args, payload)
    return payload


def _run_patch_gate(args: argparse.Namespace) -> dict[str, Any]:
    packet_args = patch_gate.parse_args(
        [
            "--intake-json",
            args.intake_json,
            "--out-json",
            args.patch_gate_json,
            "--out-csv",
            args.patch_gate_csv,
            "--out-md",
            args.patch_gate_md,
        ]
    )
    payload = patch_gate.build_payload(packet_args)
    patch_gate.write_outputs(packet_args, payload)
    return payload


def _run_apply_plan(args: argparse.Namespace) -> dict[str, Any]:
    argv = [
        "--patch-gate-json",
        args.patch_gate_json,
        "--out-json",
        args.apply_plan_json,
        "--out-csv",
        args.apply_plan_csv,
        "--out-md",
        args.apply_plan_md,
    ]
    if args.apply_row_fill:
        argv.append("--apply")
    packet_args = apply_plan.parse_args(argv)
    payload = apply_plan.build_payload(packet_args)
    apply_plan.write_outputs(packet_args, payload)
    return payload


def _stage_row(stage: str, status: str, path_like: str, summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": status,
        "path": _artifact(path_like),
        "action_count": _int(summary.get("action_count")),
        "ready_count": _int(summary.get("ready_for_apply_count"))
        + _int(summary.get("ready_for_intake_count"))
        + _int(summary.get("patch_candidate_count"))
        + _int(summary.get("ready_to_patch_count"))
        + _int(summary.get("planned_patch_count")),
        "awaiting_count": _int(summary.get("awaiting_import_file_count"))
        + _int(summary.get("awaiting_import_value_count"))
        + _int(summary.get("awaiting_dropzone_file_count"))
        + _int(summary.get("awaiting_operator_value_count"))
        + _int(summary.get("awaiting_evidence_count")),
        "blocked_count": _int(summary.get("blocked_count")),
        "applied_count": _int(summary.get("applied_count")),
        "next_action": _text(summary.get("first_open_next_action")),
    }


def _round_status(import_summary: dict[str, Any], apply_summary: dict[str, Any]) -> str:
    if _text(import_summary.get("import_status")) == "blocked":
        return "blocked_import"
    if _int(import_summary.get("ready_for_apply_count")) and _text(import_summary.get("apply_mode")) != "applied":
        return "ready_for_import_apply"
    if _text(apply_summary.get("apply_plan_status")) == "blocked" and _int(
        apply_summary.get("planned_patch_count")
    ):
        return "ready_for_partial_row_fill_apply"
    if _text(apply_summary.get("apply_plan_status")) == "blocked":
        return "blocked_row_fill_apply"
    if _text(apply_summary.get("apply_plan_status")) == "ready_for_apply":
        return "ready_for_row_fill_apply"
    if _int(import_summary.get("awaiting_import_file_count")) or _int(import_summary.get("awaiting_import_value_count")):
        return "awaiting_import"
    if _text(apply_summary.get("apply_plan_status")) == "awaiting_evidence":
        return "awaiting_evidence"
    return "ready"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    import_payload = _run_import(args)
    value_payload = _run_value_ledger(args)
    intake_payload = _run_intake(args)
    gate_payload = _run_patch_gate(args)
    apply_payload = _run_apply_plan(args)

    import_summary = _summary(import_payload)
    value_summary = _summary(value_payload)
    intake_summary = _summary(intake_payload)
    gate_summary = _summary(gate_payload)
    apply_summary = _summary(apply_payload)
    rows = [
        _stage_row("evidence_import", _text(import_summary.get("import_status")), args.import_json, import_summary),
        _stage_row("value_ledger", _text(value_summary.get("value_ledger_status")), args.value_ledger_json, value_summary),
        _stage_row("evidence_intake", _text(intake_summary.get("intake_status")), args.intake_json, intake_summary),
        _stage_row("row_fill_patch_gate", _text(gate_summary.get("patch_gate_status")), args.patch_gate_json, gate_summary),
        _stage_row("row_fill_apply_plan", _text(apply_summary.get("apply_plan_status")), args.apply_plan_json, apply_summary),
    ]
    summary = {
        "packet_type": "casp17_competitive_floor_evidence_round",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "round_status": _round_status(import_summary, apply_summary),
        "apply_import": bool(args.apply_import),
        "apply_row_fill": bool(args.apply_row_fill),
        "dropzone_json": _artifact(args.dropzone_json),
        "import_csv": _artifact(args.import_csv),
        "stage_count": len(rows),
        "import_status": _text(import_summary.get("import_status")),
        "import_ready_for_apply_count": _int(import_summary.get("ready_for_apply_count")),
        "import_applied_count": _int(import_summary.get("applied_count")),
        "import_awaiting_file_count": _int(import_summary.get("awaiting_import_file_count")),
        "import_awaiting_value_count": _int(import_summary.get("awaiting_import_value_count")),
        "intake_status": _text(intake_summary.get("intake_status")),
        "intake_patch_candidate_count": _int(intake_summary.get("patch_candidate_count")),
        "patch_gate_status": _text(gate_summary.get("patch_gate_status")),
        "patch_gate_ready_to_patch_count": _int(gate_summary.get("ready_to_patch_count")),
        "apply_plan_status": _text(apply_summary.get("apply_plan_status")),
        "apply_plan_planned_patch_count": _int(apply_summary.get("planned_patch_count")),
        "apply_plan_applied_count": _int(apply_summary.get("applied_count")),
        "first_next_action": next((row["next_action"] for row in rows if row["next_action"]), ""),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Evidence Round",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- round_status: `{summary['round_status']}`",
        f"- apply_import/apply_row_fill: `{summary['apply_import']}/{summary['apply_row_fill']}`",
        f"- import ready/applied/awaiting files/awaiting values: `{summary['import_ready_for_apply_count']}/{summary['import_applied_count']}/{summary['import_awaiting_file_count']}/{summary['import_awaiting_value_count']}`",
        f"- intake patch candidates: `{summary['intake_patch_candidate_count']}`",
        f"- patch gate ready: `{summary['patch_gate_ready_to_patch_count']}`",
        f"- apply-plan planned/applied: `{summary['apply_plan_planned_patch_count']}/{summary['apply_plan_applied_count']}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Stages",
        "",
        "| stage | status | ready | awaiting | blocked | applied | path | next action |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['stage']}` | `{row['status'] or '-'}` | {row['ready_count']} | {row['awaiting_count']} | "
            f"{row['blocked_count']} | {row['applied_count']} | `{row['path']}` | {row['next_action'] or '-'} |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a local CASP17 competitive-floor evidence round.")
    parser.add_argument("--dropzone-json", default=DEFAULT_DROPZONE_JSON)
    parser.add_argument("--import-csv", default=DEFAULT_IMPORT_CSV)
    parser.add_argument("--import-json", default=DEFAULT_IMPORT_JSON)
    parser.add_argument("--import-audit-csv", default=DEFAULT_IMPORT_AUDIT_CSV)
    parser.add_argument("--import-md", default=DEFAULT_IMPORT_MD)
    parser.add_argument("--value-ledger-json", default=DEFAULT_VALUE_LEDGER_JSON)
    parser.add_argument("--value-ledger-csv", default=DEFAULT_VALUE_LEDGER_CSV)
    parser.add_argument("--value-ledger-md", default=DEFAULT_VALUE_LEDGER_MD)
    parser.add_argument("--intake-json", default=DEFAULT_INTAKE_JSON)
    parser.add_argument("--intake-csv", default=DEFAULT_INTAKE_CSV)
    parser.add_argument("--intake-md", default=DEFAULT_INTAKE_MD)
    parser.add_argument("--patch-gate-json", default=DEFAULT_PATCH_GATE_JSON)
    parser.add_argument("--patch-gate-csv", default=DEFAULT_PATCH_GATE_CSV)
    parser.add_argument("--patch-gate-md", default=DEFAULT_PATCH_GATE_MD)
    parser.add_argument("--apply-plan-json", default=DEFAULT_APPLY_PLAN_JSON)
    parser.add_argument("--apply-plan-csv", default=DEFAULT_APPLY_PLAN_CSV)
    parser.add_argument("--apply-plan-md", default=DEFAULT_APPLY_PLAN_MD)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--apply-import", action="store_true")
    parser.add_argument("--overwrite-import", action="store_true")
    parser.add_argument("--apply-row-fill", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
