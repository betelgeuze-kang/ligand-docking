#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_QUEUE_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_queue_current.json"
DEFAULT_DROPZONES_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_evidence_dropzones_current.json"
)
DEFAULT_OPERATOR_GATE_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_operator_value_gate_current.json"
)
DEFAULT_INTAKE_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_intake_current.json"
DEFAULT_FIRST_SLOT_CLOSURE_KIT_JSON = "casp17/casp17_strict_blind_first_slot_closure_kit_current.json"
DEFAULT_RUNWAY_DIR = "casp17/strict_blind_batch_closure_runway"
DEFAULT_OUT_JSON = "casp17/casp17_strict_blind_batch_closure_runway_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_strict_blind_batch_closure_runway_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_BATCH_CLOSURE_RUNWAY.md"

ROW_COLUMNS = [
    "runway_rank",
    "required_benchmark_id",
    "required_target_id",
    "scope",
    "slot_status",
    "first_blocking_stage",
    "first_blocker",
    "file_present_count",
    "file_missing_count",
    "operator_ready_count",
    "operator_open_count",
    "intake_filled_count",
    "intake_missing_count",
    "closure_artifact",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local CASP17 strict-blind batch closure runway only. It aggregates the 40 historical replacement slots into "
    "a fill order using existing queue, dropzone, operator-value, intake, and first-slot closure artifacts. It does "
    "not create evidence, copy files, mutate intake/operator CSVs, approve provenance, compute CASP metrics, push "
    "remotes, or submit to CASP."
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


def _safe_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_") or "unknown"


def _by_benchmark(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("required_benchmark_id")): row for row in rows}


def _operator_counts(operator_rows: list[dict[str, Any]], benchmark_id: str) -> tuple[int, int, int]:
    rows = [row for row in operator_rows if _text(row.get("required_benchmark_id")) == benchmark_id]
    ready_statuses = {"ready_to_apply", "already_applied", "applied"}
    ready = sum(1 for row in rows if _text(row.get("gate_status")) in ready_statuses)
    total = len(rows)
    return ready, max(total - ready, 0), total


def _slot_status(
    first_stage: str,
    file_missing: int,
    operator_open: int,
    intake_missing: int,
) -> str:
    if first_stage:
        return "blocked_first_slot_source_gate"
    if file_missing:
        return "blocked_evidence_files"
    if operator_open:
        return "blocked_operator_values"
    if intake_missing:
        return "blocked_intake_preflight"
    return "ready_for_strict_blind_promotion"


def _first_stage(
    *,
    is_first_slot: bool,
    first_closure: dict[str, Any],
    file_missing: int,
    operator_open: int,
    intake_missing: int,
) -> tuple[str, str, str]:
    if is_first_slot and _text(first_closure.get("first_slot_closure_kit_status")) != "first_slot_closure_ready_for_operator_apply":
        return (
            _text(first_closure.get("first_blocked_step")) or "internal_prediction_source_gate",
            _text(first_closure.get("first_blocker")) or "first_slot_closure_blocked",
            _text(first_closure.get("first_next_action")) or "finish first-slot internal prediction source gate",
        )
    if file_missing:
        return ("evidence_files", f"missing_files:{file_missing}", "place required strict-blind evidence files")
    if operator_open:
        return ("operator_values", f"open_operator_values:{operator_open}", "fill and clear replacement_operator_values.csv")
    if intake_missing:
        return ("intake_preflight", f"missing_intake_fields:{intake_missing}", "rerun intake preflight after files and values are filled")
    return ("", "", "promote this slot through strict-blind replacement gates")


def _build_rows(
    queue_rows: list[dict[str, Any]],
    dropzone_rows: list[dict[str, Any]],
    operator_rows: list[dict[str, Any]],
    intake_rows: list[dict[str, Any]],
    first_closure: dict[str, Any],
) -> list[dict[str, Any]]:
    dropzone_by_id = _by_benchmark(dropzone_rows)
    intake_by_id = _by_benchmark(intake_rows)
    first_benchmark = _text(first_closure.get("required_benchmark_id"))
    rows: list[dict[str, Any]] = []
    for queue in queue_rows:
        benchmark_id = _text(queue.get("required_benchmark_id"))
        dropzone = dropzone_by_id.get(benchmark_id, {})
        intake = intake_by_id.get(benchmark_id, {})
        operator_ready, operator_open, _ = _operator_counts(operator_rows, benchmark_id)
        file_present = _int(dropzone.get("file_present_count"))
        file_missing = _int(dropzone.get("file_missing_count"))
        intake_filled = _int(intake.get("filled_field_count"))
        intake_missing = _int(intake.get("missing_field_count"))
        stage, blocker, next_action = _first_stage(
            is_first_slot=bool(first_benchmark and benchmark_id == first_benchmark),
            first_closure=first_closure,
            file_missing=file_missing,
            operator_open=operator_open,
            intake_missing=intake_missing,
        )
        rows.append(
            {
                "runway_rank": _int(queue.get("queue_rank")),
                "required_benchmark_id": benchmark_id,
                "required_target_id": _text(queue.get("required_target_id")),
                "scope": _text(queue.get("scope")),
                "slot_status": _slot_status(stage if benchmark_id == first_benchmark else "", file_missing, operator_open, intake_missing),
                "first_blocking_stage": stage,
                "first_blocker": blocker,
                "file_present_count": file_present,
                "file_missing_count": file_missing,
                "operator_ready_count": operator_ready,
                "operator_open_count": operator_open,
                "intake_filled_count": intake_filled,
                "intake_missing_count": intake_missing,
                "closure_artifact": _text(first_closure.get("kit_folder")) if benchmark_id == first_benchmark else _text(queue.get("replacement_folder")),
                "next_action": next_action,
            }
        )
    return rows


def _input_blockers(args: argparse.Namespace) -> list[str]:
    blockers = []
    for name in [
        "queue_json",
        "dropzones_json",
        "operator_gate_json",
        "intake_json",
        "first_slot_closure_kit_json",
    ]:
        if not _resolve(getattr(args, name)).exists():
            blockers.append(f"{name}_missing")
    return blockers


def _runway_status(input_blockers: list[str], rows: list[dict[str, Any]]) -> str:
    if input_blockers:
        return "blocked_missing_inputs"
    if not rows:
        return "blocked_missing_slots"
    if all(row["slot_status"] == "ready_for_strict_blind_promotion" for row in rows):
        return "strict_blind_batch_ready_for_promotion"
    if any(row["first_blocking_stage"] == "internal_prediction_source_gate" for row in rows):
        return "blocked_on_first_slot_internal_prediction_source"
    return "blocked_on_batch_evidence_or_operator_values"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    queue_payload = _read_json(args.queue_json)
    dropzone_payload = _read_json(args.dropzones_json)
    operator_payload = _read_json(args.operator_gate_json)
    intake_payload = _read_json(args.intake_json)
    first_closure_payload = _read_json(args.first_slot_closure_kit_json)
    first_closure = _summary(first_closure_payload)
    input_blockers = _input_blockers(args)
    rows = _build_rows(
        _rows(queue_payload),
        _rows(dropzone_payload),
        _rows(operator_payload),
        _rows(intake_payload),
        first_closure,
    )
    first_blocked = next((row for row in rows if row["slot_status"] != "ready_for_strict_blind_promotion"), {})
    by_stage: dict[str, int] = {}
    for row in rows:
        by_stage[row["first_blocking_stage"] or "ready"] = by_stage.get(row["first_blocking_stage"] or "ready", 0) + 1
    summary = {
        "packet_type": "casp17_strict_blind_batch_closure_runway",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "batch_closure_runway_status": _runway_status(input_blockers, rows),
        "slot_count": len(rows),
        "ready_slot_count": sum(1 for row in rows if row["slot_status"] == "ready_for_strict_blind_promotion"),
        "blocked_slot_count": sum(1 for row in rows if row["slot_status"] != "ready_for_strict_blind_promotion"),
        "source_gate_blocked_count": by_stage.get("internal_prediction_source_gate", 0),
        "evidence_file_blocked_count": by_stage.get("evidence_files", 0),
        "operator_value_blocked_count": by_stage.get("operator_values", 0),
        "intake_preflight_blocked_count": by_stage.get("intake_preflight", 0),
        "file_present_count": sum(_int(row.get("file_present_count")) for row in rows),
        "file_missing_count": sum(_int(row.get("file_missing_count")) for row in rows),
        "operator_ready_count": sum(_int(row.get("operator_ready_count")) for row in rows),
        "operator_open_count": sum(_int(row.get("operator_open_count")) for row in rows),
        "intake_filled_count": sum(_int(row.get("intake_filled_count")) for row in rows),
        "intake_missing_count": sum(_int(row.get("intake_missing_count")) for row in rows),
        "first_blocked_rank": _int(first_blocked.get("runway_rank")),
        "first_blocked_benchmark_id": _text(first_blocked.get("required_benchmark_id")),
        "first_blocking_stage": _text(first_blocked.get("first_blocking_stage")),
        "first_blocker": _text(first_blocked.get("first_blocker")),
        "first_next_action": _text(first_blocked.get("next_action")),
        "runway_dir": _artifact(args.runway_dir),
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_runway_folder(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    folder = _resolve(args.runway_dir)
    folder.mkdir(parents=True, exist_ok=True)
    _write_csv(folder / "batch_closure_runway.csv", payload["rows"], ROW_COLUMNS)
    lines = [
        "# CASP17 Strict-Blind Batch Closure Runway",
        "",
        f"- status: `{summary['batch_closure_runway_status']}`",
        f"- slots ready/blocked/total: `{summary['ready_slot_count']}/{summary['blocked_slot_count']}/{summary['slot_count']}`",
        f"- blocked by source/evidence/operator/intake: `{summary['source_gate_blocked_count']}/{summary['evidence_file_blocked_count']}/{summary['operator_value_blocked_count']}/{summary['intake_preflight_blocked_count']}`",
        f"- files present/missing: `{summary['file_present_count']}/{summary['file_missing_count']}`",
        f"- operator values ready/open: `{summary['operator_ready_count']}/{summary['operator_open_count']}`",
        f"- first blocked: `{summary['first_blocked_rank']}` `{summary['first_blocked_benchmark_id']}` `{summary['first_blocking_stage']}` `{summary['first_blocker']}`",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    (folder / "BATCH_CLOSURE_RUNWAY.md").write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Strict-Blind Batch Closure Runway",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['batch_closure_runway_status']}`",
        f"- slots ready/blocked/total: `{summary['ready_slot_count']}/{summary['blocked_slot_count']}/{summary['slot_count']}`",
        f"- blocked by source/evidence/operator/intake: `{summary['source_gate_blocked_count']}/{summary['evidence_file_blocked_count']}/{summary['operator_value_blocked_count']}/{summary['intake_preflight_blocked_count']}`",
        f"- files present/missing: `{summary['file_present_count']}/{summary['file_missing_count']}`",
        f"- operator values ready/open: `{summary['operator_ready_count']}/{summary['operator_open_count']}`",
        f"- intake fields filled/missing: `{summary['intake_filled_count']}/{summary['intake_missing_count']}`",
        f"- first blocked: `{summary['first_blocked_rank']}` `{summary['first_blocked_benchmark_id']}` `{summary['first_blocking_stage']}` `{summary['first_blocker']}`",
        "",
        "## Runway",
        "",
        "| rank | benchmark | target | scope | status | first stage | files | operator | intake | next action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"][:80]:
        lines.append(
            f"| `{row['runway_rank']}` | `{row['required_benchmark_id']}` | `{row['required_target_id']}` | "
            f"`{row['scope']}` | `{row['slot_status']}` | `{row['first_blocking_stage'] or '-'}` | "
            f"`{row['file_present_count']}/{row['file_missing_count']}` | "
            f"`{row['operator_ready_count']}/{row['operator_open_count']}` | "
            f"`{row['intake_filled_count']}/{row['intake_missing_count']}` | {row['next_action']} |"
        )
    lines.extend(["", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    _write_runway_folder(args, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build strict-blind batch closure runway.")
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    parser.add_argument("--dropzones-json", default=DEFAULT_DROPZONES_JSON)
    parser.add_argument("--operator-gate-json", default=DEFAULT_OPERATOR_GATE_JSON)
    parser.add_argument("--intake-json", default=DEFAULT_INTAKE_JSON)
    parser.add_argument("--first-slot-closure-kit-json", default=DEFAULT_FIRST_SLOT_CLOSURE_KIT_JSON)
    parser.add_argument("--runway-dir", default=DEFAULT_RUNWAY_DIR)
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
