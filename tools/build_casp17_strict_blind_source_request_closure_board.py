#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SOURCE_REQUEST_PACKET_JSON = "casp17/casp17_strict_blind_source_gate_source_request_packet_current.json"
DEFAULT_FULFILLMENT_GATE_JSON = "casp17/casp17_strict_blind_source_request_fulfillment_gate_current.json"
DEFAULT_OPERATOR_FILL_WORKLIST_JSON = "casp17/casp17_strict_blind_source_request_operator_fill_worklist_current.json"
DEFAULT_OPERATOR_SYNC_PLAN_JSON = "casp17/casp17_strict_blind_source_request_operator_sync_plan_current.json"
DEFAULT_SOURCE_GATE_OPERATOR_PACKET_JSON = "casp17/casp17_strict_blind_source_gate_operator_packet_current.json"
DEFAULT_INTERNAL_SOURCE_GATE_JSON = "casp17/casp17_strict_blind_internal_prediction_source_gate_current.json"
DEFAULT_INTERNAL_APPLY_PLAN_JSON = "casp17/casp17_strict_blind_internal_prediction_source_apply_plan_current.json"
DEFAULT_FIRST_SLOT_CLOSURE_KIT_JSON = "casp17/casp17_strict_blind_first_slot_closure_kit_current.json"
DEFAULT_BATCH_RUNWAY_JSON = "casp17/casp17_strict_blind_batch_closure_runway_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_strict_blind_source_request_closure_board_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_strict_blind_source_request_closure_board_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_SOURCE_REQUEST_CLOSURE_BOARD.md"

ROW_COLUMNS = [
    "stage_order",
    "stage_id",
    "label",
    "source_status",
    "stage_status",
    "ready_count",
    "blocked_count",
    "total_count",
    "artifact_path",
    "first_blocker",
    "next_action",
]

CLAIM_BOUNDARY = (
    "Local CASP17 strict-blind source-request closure board only. It aggregates the first-slot "
    "pre-native internal prediction source request, fulfillment, operator fill, sync, source gate, "
    "apply-plan, first-slot closure, and batch runway statuses. It does not fill operator values, "
    "copy prediction files, approve provenance, compute CASP metrics, push remotes, or submit to CASP."
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


def _stage(
    order: int,
    stage_id: str,
    label: str,
    source_status: str,
    ready: bool,
    ready_count: int,
    blocked_count: int,
    total_count: int,
    artifact_path: str,
    first_blocker: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "stage_order": order,
        "stage_id": stage_id,
        "label": label,
        "source_status": source_status,
        "stage_status": "stage_ready" if ready else "stage_blocked",
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "total_count": total_count,
        "artifact_path": _artifact(artifact_path),
        "first_blocker": first_blocker,
        "next_action": next_action,
    }


def _all_ready(ready: int, total: int) -> bool:
    return total > 0 and ready >= total


def _build_rows(args: argparse.Namespace, summaries: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    requests = summaries["requests"]
    fulfillment = summaries["fulfillment"]
    fill = summaries["fill"]
    sync = summaries["sync"]
    operator = summaries["operator"]
    gate = summaries["gate"]
    apply = summaries["apply"]
    first_slot = summaries["first_slot"]
    batch = summaries["batch"]
    request_count = _int(requests.get("request_count"))
    template_ready = _int(requests.get("operator_template_ready_count"))
    fulfillment_ready = _int(fulfillment.get("ready_request_count"))
    fulfillment_total = _int(fulfillment.get("request_count"))
    fill_ready = _int(fill.get("field_ready_count"))
    fill_total = _int(fill.get("field_action_count"))
    sync_ready = _int(sync.get("ready_sync_action_count"))
    sync_total = _int(sync.get("sync_action_count"))
    operator_ready = _int(operator.get("operator_ready_count"))
    operator_total = _int(operator.get("operator_ready_count")) + _int(operator.get("operator_awaiting_count"))
    gate_pass = _int(gate.get("pass_count"))
    gate_total = _int(gate.get("check_count"))
    apply_ready = _int(apply.get("ready_action_count"))
    apply_total = _int(apply.get("action_count"))
    first_slot_ready = _int(first_slot.get("step_ready_count"))
    first_slot_total = _int(first_slot.get("step_count"))
    batch_ready = _int(batch.get("ready_slot_count"))
    batch_total = _int(batch.get("slot_count"))
    return [
        _stage(
            1,
            "source_request_packet",
            "Acquire or replace pre-native internal prediction source requests",
            _text(requests.get("source_request_packet_status")),
            _all_ready(template_ready, request_count),
            template_ready,
            _int(requests.get("operator_template_awaiting_count")),
            request_count,
            args.source_request_packet_json,
            _text(requests.get("first_request_blocker")) or _text(requests.get("first_missing_operator_field")),
            _text(requests.get("first_next_action")),
        ),
        _stage(
            2,
            "source_request_fulfillment_gate",
            "Validate source request operator values and evidence",
            _text(fulfillment.get("source_request_fulfillment_gate_status")),
            fulfillment_ready > 0 and fulfillment_ready >= fulfillment_total,
            fulfillment_ready,
            _int(fulfillment.get("blocked_request_count")),
            fulfillment_total,
            args.fulfillment_gate_json,
            _text(fulfillment.get("first_blocker")),
            _text(fulfillment.get("first_next_action")),
        ),
        _stage(
            3,
            "source_request_operator_fill_worklist",
            "Fill source request operator template fields",
            _text(fill.get("source_request_operator_fill_worklist_status")),
            _all_ready(fill_ready, fill_total),
            fill_ready,
            _int(fill.get("operator_value_missing_count")),
            fill_total,
            args.operator_fill_worklist_json,
            _text(fill.get("first_blocker")),
            _text(fill.get("first_next_action")),
        ),
        _stage(
            4,
            "source_request_operator_sync_plan",
            "Sync ready source request values into source-gate operator packet",
            _text(sync.get("source_request_operator_sync_plan_status")),
            _text(sync.get("source_request_operator_sync_plan_status")) in {
                "source_request_operator_sync_ready_dry_run",
                "source_request_operator_sync_applied",
            },
            sync_ready,
            _int(sync.get("blocked_sync_action_count")),
            sync_total,
            args.operator_sync_plan_json,
            _text(sync.get("first_blocker")),
            _text(sync.get("first_next_action")),
        ),
        _stage(
            5,
            "source_gate_operator_packet",
            "Complete first-slot source-gate operator packet",
            _text(operator.get("source_gate_operator_packet_status")),
            _all_ready(operator_ready, operator_total),
            operator_ready,
            _int(operator.get("operator_awaiting_count")),
            operator_total,
            args.source_gate_operator_packet_json,
            _text(operator.get("first_field_key")) + ":" + _text(operator.get("first_operator_status")),
            _text(operator.get("first_next_action")),
        ),
        _stage(
            6,
            "internal_prediction_source_gate",
            "Validate internal pre-native prediction source manifest and PDB",
            _text(gate.get("internal_prediction_source_gate_status")),
            _all_ready(gate_pass, gate_total),
            gate_pass,
            _int(gate.get("blocked_count")),
            gate_total,
            args.internal_source_gate_json,
            _text(gate.get("first_blocker")),
            _text(gate.get("first_next_action")),
        ),
        _stage(
            7,
            "internal_prediction_source_apply_plan",
            "Copy verified internal prediction PDB into first-slot dropzone",
            _text(apply.get("internal_prediction_source_apply_plan_status")),
            _text(apply.get("internal_prediction_source_apply_plan_status")) in {
                "internal_prediction_source_apply_ready_dry_run",
                "internal_prediction_source_apply_applied",
            },
            apply_ready,
            _int(apply.get("blocked_action_count")),
            apply_total,
            args.internal_apply_plan_json,
            _text(apply.get("first_blocker")),
            _text(apply.get("first_next_action")),
        ),
        _stage(
            8,
            "first_slot_closure_kit",
            "Close first strict-blind historical slot",
            _text(first_slot.get("first_slot_closure_kit_status")),
            _all_ready(first_slot_ready, first_slot_total),
            first_slot_ready,
            _int(first_slot.get("step_blocked_count")),
            first_slot_total,
            args.first_slot_closure_kit_json,
            _text(first_slot.get("first_blocker")),
            _text(first_slot.get("first_next_action")),
        ),
        _stage(
            9,
            "batch_closure_runway",
            "Propagate first-slot closure into 40-slot strict-blind runway",
            _text(batch.get("batch_closure_runway_status")),
            _all_ready(batch_ready, batch_total),
            batch_ready,
            _int(batch.get("blocked_slot_count")),
            batch_total,
            args.batch_runway_json,
            _text(batch.get("first_blocker")),
            _text(batch.get("first_next_action")),
        ),
    ]


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    paths = [
        ("source_request_packet", args.source_request_packet_json),
        ("fulfillment_gate", args.fulfillment_gate_json),
        ("operator_fill_worklist", args.operator_fill_worklist_json),
        ("operator_sync_plan", args.operator_sync_plan_json),
        ("source_gate_operator_packet", args.source_gate_operator_packet_json),
        ("internal_source_gate", args.internal_source_gate_json),
        ("internal_apply_plan", args.internal_apply_plan_json),
        ("first_slot_closure_kit", args.first_slot_closure_kit_json),
        ("batch_runway", args.batch_runway_json),
    ]
    input_blockers = [f"{name}_json_missing" for name, path in paths if not _resolve(path).exists()]
    payloads = {
        "requests": _read_json(args.source_request_packet_json),
        "fulfillment": _read_json(args.fulfillment_gate_json),
        "fill": _read_json(args.operator_fill_worklist_json),
        "sync": _read_json(args.operator_sync_plan_json),
        "operator": _read_json(args.source_gate_operator_packet_json),
        "gate": _read_json(args.internal_source_gate_json),
        "apply": _read_json(args.internal_apply_plan_json),
        "first_slot": _read_json(args.first_slot_closure_kit_json),
        "batch": _read_json(args.batch_runway_json),
    }
    summaries = {key: _summary(payload) for key, payload in payloads.items()}
    rows = [] if input_blockers else _build_rows(args, summaries)
    ready_rows = [row for row in rows if row["stage_status"] == "stage_ready"]
    blocked_rows = [row for row in rows if row["stage_status"] != "stage_ready"]
    first_blocked = blocked_rows[0] if blocked_rows else {}
    status = "strict_blind_source_request_closure_ready_for_first_slot"
    if input_blockers:
        status = "blocked_missing_inputs"
    elif blocked_rows:
        status = "awaiting_strict_blind_source_request_closure"
    summary = {
        "packet_type": "casp17_strict_blind_source_request_closure_board",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "strict_blind_source_request_closure_board_status": status,
        "required_benchmark_id": _text(summaries["requests"].get("required_benchmark_id"))
        or _text(summaries["gate"].get("required_benchmark_id")),
        "required_target_id": _text(summaries["requests"].get("required_target_id"))
        or _text(summaries["gate"].get("required_target_id")),
        "required_scope": _text(summaries["requests"].get("required_scope"))
        or _text(summaries["gate"].get("required_scope")),
        "stage_count": len(rows),
        "ready_stage_count": len(ready_rows),
        "blocked_stage_count": len(blocked_rows),
        "first_blocked_stage_id": _text(first_blocked.get("stage_id")),
        "first_blocked_stage_status": _text(first_blocked.get("source_status")),
        "first_blocker": _text(first_blocked.get("first_blocker")),
        "next_action": _text(first_blocked.get("next_action")) if blocked_rows else "close first strict-blind slot",
        "source_request_status": _text(summaries["requests"].get("source_request_packet_status")),
        "fulfillment_gate_status": _text(summaries["fulfillment"].get("source_request_fulfillment_gate_status")),
        "operator_fill_worklist_status": _text(
            summaries["fill"].get("source_request_operator_fill_worklist_status")
        ),
        "operator_sync_plan_status": _text(summaries["sync"].get("source_request_operator_sync_plan_status")),
        "source_gate_operator_packet_status": _text(summaries["operator"].get("source_gate_operator_packet_status")),
        "internal_prediction_source_gate_status": _text(
            summaries["gate"].get("internal_prediction_source_gate_status")
        ),
        "internal_prediction_apply_plan_status": _text(
            summaries["apply"].get("internal_prediction_source_apply_plan_status")
        ),
        "first_slot_closure_kit_status": _text(summaries["first_slot"].get("first_slot_closure_kit_status")),
        "batch_closure_runway_status": _text(summaries["batch"].get("batch_closure_runway_status")),
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Strict-Blind Source Request Closure Board",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['strict_blind_source_request_closure_board_status']}`",
        f"- required benchmark/target/scope: `{summary['required_benchmark_id']}` `{summary['required_target_id']}` `{summary['required_scope']}`",
        f"- stages ready/blocked/total: `{summary['ready_stage_count']}/{summary['blocked_stage_count']}/{summary['stage_count']}`",
        f"- first blocked: `{summary['first_blocked_stage_id'] or '-'}` `{summary['first_blocked_stage_status'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- next action: {summary['next_action'] or '-'}",
        "",
        "## Stages",
        "",
        "| order | stage | status | ready | blocked | total | first blocker | next action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['stage_order']}` | `{row['stage_id']}` | `{row['source_status']}` | "
            f"`{row['ready_count']}` | `{row['blocked_count']}` | `{row['total_count']}` | "
            f"`{row['first_blocker'] or '-'}` | {row['next_action'] or '-'} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | - | - | - | missing input artifacts |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 strict-blind source-request closure board.")
    parser.add_argument("--source-request-packet-json", default=DEFAULT_SOURCE_REQUEST_PACKET_JSON)
    parser.add_argument("--fulfillment-gate-json", default=DEFAULT_FULFILLMENT_GATE_JSON)
    parser.add_argument("--operator-fill-worklist-json", default=DEFAULT_OPERATOR_FILL_WORKLIST_JSON)
    parser.add_argument("--operator-sync-plan-json", default=DEFAULT_OPERATOR_SYNC_PLAN_JSON)
    parser.add_argument("--source-gate-operator-packet-json", default=DEFAULT_SOURCE_GATE_OPERATOR_PACKET_JSON)
    parser.add_argument("--internal-source-gate-json", default=DEFAULT_INTERNAL_SOURCE_GATE_JSON)
    parser.add_argument("--internal-apply-plan-json", default=DEFAULT_INTERNAL_APPLY_PLAN_JSON)
    parser.add_argument("--first-slot-closure-kit-json", default=DEFAULT_FIRST_SLOT_CLOSURE_KIT_JSON)
    parser.add_argument("--batch-runway-json", default=DEFAULT_BATCH_RUNWAY_JSON)
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
