#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_FIRST_SLOT_KIT_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_kit_current.json"
)
DEFAULT_SOURCE_GATE_JSON = "casp17/casp17_strict_blind_internal_prediction_source_gate_current.json"
DEFAULT_APPLY_PLAN_JSON = "casp17/casp17_strict_blind_internal_prediction_source_apply_plan_current.json"
DEFAULT_EVIDENCE_DROPZONES_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_evidence_dropzones_current.json"
)
DEFAULT_OPERATOR_GATE_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_operator_value_gate_current.json"
)
DEFAULT_INTAKE_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_intake_current.json"
DEFAULT_KIT_DIR = "casp17/strict_blind_first_slot_closure_kit"
DEFAULT_OUT_JSON = "casp17/casp17_strict_blind_first_slot_closure_kit_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_strict_blind_first_slot_closure_kit_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_FIRST_SLOT_CLOSURE_KIT.md"

ROW_COLUMNS = [
    "step_id",
    "step_order",
    "step_status",
    "ready_count",
    "blocked_count",
    "total_count",
    "artifact",
    "first_blocker",
    "next_action",
]
FILL_COLUMNS = [
    "fill_id",
    "fill_kind",
    "field_name",
    "source_or_template",
    "destination",
    "current_status",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local CASP17 first-slot closure kit only. It gathers existing source gate, apply-plan, evidence-dropzone, "
    "operator-value, and intake-preflight blockers for the first strict-blind historical slot. It does not create "
    "or copy evidence files, mutate intake/operator CSVs, approve provenance, compute CASP metrics, push remotes, "
    "or submit to CASP."
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


def _read_csv_rows(path_like: str | Path) -> list[dict[str, str]]:
    if not _text(path_like):
        return []
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
    for name in [
        "first_slot_kit_json",
        "source_gate_json",
        "apply_plan_json",
        "evidence_dropzones_json",
        "operator_gate_json",
        "intake_json",
    ]:
        if not _resolve(getattr(args, name)).exists():
            blockers.append(f"{name}_missing")
    return blockers


def _first_row(rows: list[dict[str, Any]], benchmark_id: str) -> dict[str, Any]:
    for row in rows:
        if _text(row.get("required_benchmark_id")) == benchmark_id:
            return row
    return rows[0] if rows else {}


def _step(
    step_id: str,
    order: int,
    status: str,
    ready: int,
    blocked: int,
    total: int,
    artifact: str,
    first_blocker: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "step_order": order,
        "step_status": status or "missing",
        "ready_count": ready,
        "blocked_count": blocked,
        "total_count": total,
        "artifact": artifact,
        "first_blocker": first_blocker,
        "next_action": next_action,
    }


def _fill_rows(dropzone_row: dict[str, Any], operator_values_csv: str, apply_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    fills: list[dict[str, str]] = []
    patch_rows = _read_csv_rows(_text(dropzone_row.get("patch_preview_csv")))
    for index, row in enumerate(patch_rows, start=1):
        fills.append(
            {
                "fill_id": f"first_slot_fill_{index:03d}",
                "fill_kind": _text(row.get("field_kind")),
                "field_name": _text(row.get("field_name")),
                "source_or_template": _text(row.get("source_path")) or operator_values_csv,
                "destination": _text(row.get("destination_intake_csv")),
                "current_status": _text(row.get("source_status")),
                "next_action": _text(row.get("operator_action")),
            }
        )
    base = len(fills)
    for offset, row in enumerate(apply_rows, start=1):
        fills.append(
            {
                "fill_id": f"apply_plan_action_{offset:03d}",
                "fill_kind": _text(row.get("action_type")),
                "field_name": _text(row.get("field_name")),
                "source_or_template": _text(row.get("source_value")),
                "destination": _text(row.get("destination")),
                "current_status": _text(row.get("action_status")),
                "next_action": _text(row.get("next_action")),
            }
        )
    return fills


def _operator_step_counts(operator_rows: list[dict[str, Any]], benchmark_id: str) -> tuple[int, int, int]:
    rows = [row for row in operator_rows if _text(row.get("required_benchmark_id")) == benchmark_id]
    ready_statuses = {"ready_to_apply", "already_applied", "applied"}
    ready = sum(1 for row in rows if _text(row.get("gate_status")) in ready_statuses)
    total = len(rows)
    return ready, max(total - ready, 0), total


def _closure_status(input_blockers: list[str], rows: list[dict[str, Any]]) -> str:
    if input_blockers:
        return "blocked_missing_inputs"
    if any(row["blocked_count"] for row in rows):
        first = next(row for row in rows if row["blocked_count"])
        return f"blocked_on_{first['step_id']}"
    return "first_slot_closure_ready_for_operator_apply"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    first_slot_payload = _read_json(args.first_slot_kit_json)
    source_gate_payload = _read_json(args.source_gate_json)
    apply_plan_payload = _read_json(args.apply_plan_json)
    dropzones_payload = _read_json(args.evidence_dropzones_json)
    operator_gate_payload = _read_json(args.operator_gate_json)
    intake_payload = _read_json(args.intake_json)
    first_slot = _summary(first_slot_payload)
    source_gate = _summary(source_gate_payload)
    apply_plan = _summary(apply_plan_payload)
    operator_gate = _summary(operator_gate_payload)
    benchmark_id = _text(first_slot.get("required_benchmark_id") or source_gate.get("required_benchmark_id"))
    dropzone_row = _first_row(_rows(dropzones_payload), benchmark_id)
    intake_row = _first_row(_rows(intake_payload), benchmark_id)
    operator_values_csv = _text(_first_row(_rows(operator_gate_payload), benchmark_id).get("operator_values_csv"))
    operator_ready, operator_blocked, operator_total = _operator_step_counts(_rows(operator_gate_payload), benchmark_id)
    input_blockers = _input_blockers(args)
    steps = [
        _step(
            "internal_prediction_source_gate",
            1,
            _text(source_gate.get("internal_prediction_source_gate_status")),
            _int(source_gate.get("pass_count")),
            _int(source_gate.get("blocked_count")),
            _int(source_gate.get("check_count")),
            args.source_gate_json,
            _text(source_gate.get("first_blocker")),
            _text(source_gate.get("first_next_action")),
        ),
        _step(
            "internal_prediction_apply_plan",
            2,
            _text(apply_plan.get("internal_prediction_source_apply_plan_status")),
            _int(apply_plan.get("ready_action_count")),
            _int(apply_plan.get("blocked_action_count")),
            _int(apply_plan.get("action_count")),
            args.apply_plan_json,
            _text(apply_plan.get("first_blocker")),
            _text(apply_plan.get("first_next_action")),
        ),
        _step(
            "first_slot_evidence_files",
            3,
            _text(dropzone_row.get("dropzone_status")),
            _int(dropzone_row.get("file_present_count")),
            _int(dropzone_row.get("file_missing_count")),
            _int(dropzone_row.get("file_required_count")),
            _text(dropzone_row.get("dropzone_folder")),
            _text(dropzone_row.get("blockers")),
            _text(dropzone_row.get("next_action")),
        ),
        _step(
            "first_slot_operator_values",
            4,
            _text(operator_gate.get("strict_blind_replacement_operator_value_gate_status")),
            operator_ready,
            operator_blocked,
            operator_total,
            operator_values_csv,
            _text(operator_gate.get("first_open_field")),
            _text(operator_gate.get("first_next_action")),
        ),
        _step(
            "first_slot_intake_preflight",
            5,
            _text(intake_row.get("preflight_status")),
            _int(intake_row.get("filled_field_count")),
            _int(intake_row.get("missing_field_count")),
            _int(intake_row.get("required_field_count")),
            _text(intake_row.get("intake_csv")),
            _text(intake_row.get("blockers")),
            _text(intake_row.get("next_action")),
        ),
    ]
    fill_rows = _fill_rows(dropzone_row, operator_values_csv, _rows(apply_plan_payload))
    first_blocked = next((row for row in steps if _int(row["blocked_count"]) > 0), {})
    summary = {
        "packet_type": "casp17_strict_blind_first_slot_closure_kit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "first_slot_closure_kit_status": _closure_status(input_blockers, steps),
        "required_benchmark_id": benchmark_id,
        "required_target_id": _text(first_slot.get("required_target_id") or source_gate.get("required_target_id")),
        "required_scope": _text(first_slot.get("scope") or source_gate.get("required_scope")),
        "step_count": len(steps),
        "step_ready_count": sum(1 for row in steps if _int(row["blocked_count"]) == 0 and _int(row["total_count"]) > 0),
        "step_blocked_count": sum(1 for row in steps if _int(row["blocked_count"]) > 0),
        "fill_item_count": len(fill_rows),
        "file_fill_count": sum(1 for row in fill_rows if row["fill_kind"] in {"file", "file_copy", "supplemental_evidence"}),
        "operator_fill_count": sum(1 for row in fill_rows if row["fill_kind"] == "operator_value"),
        "source_gate_status": _text(source_gate.get("internal_prediction_source_gate_status")),
        "apply_plan_status": _text(apply_plan.get("internal_prediction_source_apply_plan_status")),
        "dropzone_status": _text(dropzone_row.get("dropzone_status")),
        "operator_gate_status": _text(operator_gate.get("strict_blind_replacement_operator_value_gate_status")),
        "intake_preflight_status": _text(intake_row.get("preflight_status")),
        "first_blocked_step": _text(first_blocked.get("step_id")),
        "first_blocker": _text(first_blocked.get("first_blocker")),
        "first_next_action": _text(first_blocked.get("next_action")),
        "kit_folder": _artifact(_resolve(args.kit_dir) / (benchmark_id or "hist_REQUIRED_MONOMER_001")),
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": steps, "fill_rows": fill_rows}


def _write_kit_folder(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    folder = _resolve(args.kit_dir) / (summary["required_benchmark_id"] or "hist_REQUIRED_MONOMER_001")
    folder.mkdir(parents=True, exist_ok=True)
    _write_csv(folder / "closure_steps.csv", payload["rows"], ROW_COLUMNS)
    _write_csv(folder / "fill_order.csv", payload["fill_rows"], FILL_COLUMNS)
    lines = [
        "# CASP17 Strict-Blind First Slot Closure Kit",
        "",
        f"- status: `{summary['first_slot_closure_kit_status']}`",
        f"- required benchmark/target/scope: `{summary['required_benchmark_id']}` `{summary['required_target_id']}` `{summary['required_scope']}`",
        f"- steps ready/blocked/total: `{summary['step_ready_count']}/{summary['step_blocked_count']}/{summary['step_count']}`",
        f"- fill items file/operator/total: `{summary['file_fill_count']}/{summary['operator_fill_count']}/{summary['fill_item_count']}`",
        f"- first blocker: `{summary['first_blocked_step'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    (folder / "FIRST_SLOT_CLOSURE_KIT.md").write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Strict-Blind First Slot Closure Kit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['first_slot_closure_kit_status']}`",
        f"- required benchmark/target/scope: `{summary['required_benchmark_id']}` `{summary['required_target_id']}` `{summary['required_scope']}`",
        f"- steps ready/blocked/total: `{summary['step_ready_count']}/{summary['step_blocked_count']}/{summary['step_count']}`",
        f"- fill items file/operator/total: `{summary['file_fill_count']}/{summary['operator_fill_count']}/{summary['fill_item_count']}`",
        f"- source/apply/dropzone/operator/intake: `{summary['source_gate_status']}` `{summary['apply_plan_status']}` `{summary['dropzone_status']}` `{summary['operator_gate_status']}` `{summary['intake_preflight_status']}`",
        f"- first blocker: `{summary['first_blocked_step'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- kit folder: `{summary['kit_folder']}`",
        "",
        "## Steps",
        "",
        "| step | status | ready/blocked/total | artifact | first blocker | next action |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['step_id']}` | `{row['step_status']}` | `{row['ready_count']}/{row['blocked_count']}/{row['total_count']}` | "
            f"`{row['artifact']}` | `{row['first_blocker'] or '-'}` | {row['next_action'] or '-'} |"
        )
    lines.extend(["", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    _write_kit_folder(args, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build strict-blind first-slot closure kit.")
    parser.add_argument("--first-slot-kit-json", default=DEFAULT_FIRST_SLOT_KIT_JSON)
    parser.add_argument("--source-gate-json", default=DEFAULT_SOURCE_GATE_JSON)
    parser.add_argument("--apply-plan-json", default=DEFAULT_APPLY_PLAN_JSON)
    parser.add_argument("--evidence-dropzones-json", default=DEFAULT_EVIDENCE_DROPZONES_JSON)
    parser.add_argument("--operator-gate-json", default=DEFAULT_OPERATOR_GATE_JSON)
    parser.add_argument("--intake-json", default=DEFAULT_INTAKE_JSON)
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
