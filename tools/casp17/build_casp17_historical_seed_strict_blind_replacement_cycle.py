#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_QUEUE_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_queue_current.json"
DEFAULT_INTAKE_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_intake_current.json"
DEFAULT_DROPZONES_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_evidence_dropzones_current.json"
DEFAULT_QUALITY_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_evidence_quality_audit_current.json"
DEFAULT_IMPORT_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_evidence_import_gate_current.json"
DEFAULT_OPERATOR_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_operator_value_gate_current.json"
DEFAULT_OPERATOR_ACTION_BOARD_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_operator_action_board_current.json"
)
DEFAULT_PROMOTION_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_promotion_gate_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_cycle_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_strict_blind_replacement_cycle_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_CYCLE.md"

ROW_COLUMNS = [
    "stage",
    "status",
    "path",
    "ready_count",
    "awaiting_count",
    "blocked_count",
    "total_count",
    "first_open_benchmark_id",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local CASP17 strict-blind replacement cycle only. It aggregates the replacement queue, intake preflight, "
    "evidence dropzones, evidence quality audit, evidence import gate, operator-value gate, operator action board, "
    "and promotion gate into one fail-closed progress surface. It does not select replacement targets, create "
    "evidence, approve no-leak provenance, mutate intake CSVs, compute CASP metrics, or submit to CASP."
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


def _stage_row(
    stage: str,
    status: str,
    path_like: str | Path,
    *,
    ready: int,
    awaiting: int,
    blocked: int,
    total: int,
    first_open: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": status or "missing",
        "path": _artifact(path_like),
        "ready_count": ready,
        "awaiting_count": awaiting,
        "blocked_count": blocked,
        "total_count": total,
        "first_open_benchmark_id": first_open,
        "next_action": next_action,
    }


def _input_blockers(args: argparse.Namespace) -> list[str]:
    blockers = []
    for name in [
        "queue_json",
        "intake_json",
        "dropzones_json",
        "quality_json",
        "import_json",
        "operator_json",
        "operator_action_board_json",
        "promotion_json",
    ]:
        if not _resolve(getattr(args, name)).exists():
            blockers.append(f"{name}_missing")
    return blockers


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    queue_summary = _summary(_read_json(args.queue_json))
    intake_summary = _summary(_read_json(args.intake_json))
    dropzone_summary = _summary(_read_json(args.dropzones_json))
    quality_summary = _summary(_read_json(args.quality_json))
    import_summary = _summary(_read_json(args.import_json))
    operator_summary = _summary(_read_json(args.operator_json))
    operator_action_board_summary = _summary(_read_json(args.operator_action_board_json))
    promotion_summary = _summary(_read_json(args.promotion_json))
    blockers = _input_blockers(args)
    rows = _stage_rows(
        args,
        queue_summary,
        intake_summary,
        dropzone_summary,
        quality_summary,
        import_summary,
        operator_summary,
        operator_action_board_summary,
        promotion_summary,
    )
    summary = _build_summary(
        args,
        rows,
        blockers,
        queue_summary,
        intake_summary,
        dropzone_summary,
        quality_summary,
        import_summary,
        operator_summary,
        operator_action_board_summary,
        promotion_summary,
    )
    return {"summary": summary, "rows": rows}


def _stage_rows(
    args: argparse.Namespace,
    queue: dict[str, Any],
    intake: dict[str, Any],
    dropzone: dict[str, Any],
    quality: dict[str, Any],
    import_gate: dict[str, Any],
    operator_gate: dict[str, Any],
    operator_action_board: dict[str, Any],
    promotion: dict[str, Any],
) -> list[dict[str, Any]]:
    queue_total = _int(queue.get("scaffold_slot_count"))
    queue_ready = _int(queue.get("strict_blind_ready_slot_count"))
    intake_total = _int(intake.get("intake_slot_count"))
    dropzone_total = _int(dropzone.get("dropzone_count"))
    quality_total = _int(quality.get("slot_count"))
    import_total = _int(import_gate.get("action_count"))
    operator_total = _int(operator_gate.get("action_count"))
    operator_action_board_total = _int(operator_action_board.get("action_count"))
    promotion_total = _int(promotion.get("slot_count"))
    import_ready = (
        _int(import_gate.get("ready_for_apply_count"))
        + _int(import_gate.get("applied_count"))
        + _int(import_gate.get("already_applied_count"))
    )
    operator_ready = (
        _int(operator_gate.get("ready_for_apply_count"))
        + _int(operator_gate.get("applied_count"))
        + _int(operator_gate.get("already_applied_count"))
    )
    operator_action_board_ready = (
        _int(operator_action_board.get("ready_for_apply_count"))
        + _int(operator_action_board.get("applied_count"))
        + _int(operator_action_board.get("already_applied_count"))
    )
    promotion_ready = _int(promotion.get("ready_for_competitive_proof_count"))
    return [
        _stage_row(
            "queue",
            _text(queue.get("strict_blind_replacement_queue_status")),
            args.queue_json,
            ready=queue_ready,
            awaiting=max(queue_total - queue_ready, 0),
            blocked=0,
            total=queue_total,
            first_open=_text(queue.get("first_open_benchmark_id")),
            next_action=_text(queue.get("first_next_action")),
        ),
        _stage_row(
            "intake",
            _text(intake.get("strict_blind_replacement_intake_status")),
            args.intake_json,
            ready=_int(intake.get("ready_for_preflight_count")),
            awaiting=_int(intake.get("blocked_or_awaiting_count")),
            blocked=0,
            total=intake_total,
            first_open=_text(intake.get("first_open_benchmark_id")),
            next_action=_text(intake.get("first_next_action")),
        ),
        _stage_row(
            "evidence_dropzones",
            _text(dropzone.get("strict_blind_replacement_evidence_dropzone_status")),
            args.dropzones_json,
            ready=_int(dropzone.get("ready_for_intake_patch_count")),
            awaiting=_int(dropzone.get("awaiting_file_count")),
            blocked=0,
            total=dropzone_total,
            first_open=_text(dropzone.get("first_open_benchmark_id")),
            next_action=_text(dropzone.get("first_next_action")),
        ),
        _stage_row(
            "evidence_quality",
            _text(quality.get("strict_blind_replacement_evidence_quality_audit_status")),
            args.quality_json,
            ready=_int(quality.get("ready_for_quality_review_count")),
            awaiting=_int(quality.get("awaiting_evidence_files_count")),
            blocked=_int(quality.get("blocked_evidence_quality_count")),
            total=quality_total,
            first_open=_text(quality.get("first_open_benchmark_id")),
            next_action=_text(quality.get("first_next_action")),
        ),
        _stage_row(
            "evidence_import",
            _text(import_gate.get("strict_blind_replacement_evidence_import_gate_status")),
            args.import_json,
            ready=import_ready,
            awaiting=(
                _int(import_gate.get("awaiting_file_count"))
                + _int(import_gate.get("awaiting_operator_value_count"))
            ),
            blocked=_int(import_gate.get("blocked_count")),
            total=import_total,
            first_open=_text(import_gate.get("first_open_benchmark_id")),
            next_action=_text(import_gate.get("first_next_action")),
        ),
        _stage_row(
            "operator_values",
            _text(operator_gate.get("strict_blind_replacement_operator_value_gate_status")),
            args.operator_json,
            ready=operator_ready,
            awaiting=(
                _int(operator_gate.get("awaiting_operator_value_count"))
                + _int(operator_gate.get("awaiting_evidence_ref_count"))
                + _int(operator_gate.get("awaiting_operator_clearance_count"))
            ),
            blocked=_int(operator_gate.get("blocked_count")),
            total=operator_total,
            first_open=_text(operator_gate.get("first_open_benchmark_id")),
            next_action=_text(operator_gate.get("first_next_action")),
        ),
        _stage_row(
            "operator_action_board",
            _text(operator_action_board.get("strict_blind_replacement_operator_action_board_status")),
            args.operator_action_board_json,
            ready=operator_action_board_ready,
            awaiting=_int(operator_action_board.get("open_operator_value_count")),
            blocked=_int(operator_action_board.get("blocked_count")),
            total=operator_action_board_total,
            first_open=_text(operator_action_board.get("first_open_benchmark_id")),
            next_action=_text(operator_action_board.get("first_next_action")),
        ),
        _stage_row(
            "promotion",
            _text(promotion.get("strict_blind_replacement_promotion_gate_status")),
            args.promotion_json,
            ready=promotion_ready,
            awaiting=max(promotion_total - promotion_ready - _int(promotion.get("blocked_review_count")), 0),
            blocked=_int(promotion.get("blocked_review_count")),
            total=promotion_total,
            first_open=_text(promotion.get("first_open_benchmark_id")),
            next_action=_text(promotion.get("first_next_action")),
        ),
    ]


def _build_summary(
    args: argparse.Namespace,
    rows: list[dict[str, Any]],
    input_blockers: list[str],
    queue: dict[str, Any],
    intake: dict[str, Any],
    dropzone: dict[str, Any],
    quality: dict[str, Any],
    import_gate: dict[str, Any],
    operator_gate: dict[str, Any],
    operator_action_board: dict[str, Any],
    promotion: dict[str, Any],
) -> dict[str, Any]:
    cycle_status, first_stage = _cycle_status(
        input_blockers,
        dropzone,
        quality,
        import_gate,
        operator_gate,
        operator_action_board,
        intake,
        promotion,
    )
    first_row = next((row for row in rows if row["stage"] == first_stage), {})
    return {
        "packet_type": "casp17_historical_seed_strict_blind_replacement_cycle",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "strict_blind_replacement_cycle_status": cycle_status,
        "slot_count": _int(promotion.get("slot_count")) or _int(quality.get("slot_count")) or _int(intake.get("intake_slot_count")),
        "queue_slot_count": _int(queue.get("scaffold_slot_count")),
        "intake_ready_count": _int(intake.get("ready_for_preflight_count")),
        "intake_missing_field_count": _int(intake.get("missing_field_count")),
        "dropzone_ready_count": _int(dropzone.get("ready_for_intake_patch_count")),
        "evidence_file_present_count": _int(dropzone.get("file_present_count")),
        "evidence_file_missing_count": _int(dropzone.get("file_missing_count")),
        "quality_ready_count": _int(quality.get("ready_for_quality_review_count")),
        "quality_awaiting_count": _int(quality.get("awaiting_evidence_files_count")),
        "quality_blocked_count": _int(quality.get("blocked_evidence_quality_count")),
        "quality_pdb_valid_slot_count": _int(quality.get("pdb_valid_slot_count")),
        "quality_prediction_native_distinct_count": _int(quality.get("prediction_native_distinct_count")),
        "import_ready_count": (
            _int(import_gate.get("ready_for_apply_count"))
            + _int(import_gate.get("applied_count"))
            + _int(import_gate.get("already_applied_count"))
        ),
        "import_awaiting_file_count": _int(import_gate.get("awaiting_file_count")),
        "import_awaiting_operator_count": _int(import_gate.get("awaiting_operator_value_count")),
        "operator_ready_count": (
            _int(operator_gate.get("ready_for_apply_count"))
            + _int(operator_gate.get("applied_count"))
            + _int(operator_gate.get("already_applied_count"))
        ),
        "operator_awaiting_value_count": _int(operator_gate.get("awaiting_operator_value_count")),
        "operator_action_board_ready_count": (
            _int(operator_action_board.get("ready_for_apply_count"))
            + _int(operator_action_board.get("applied_count"))
            + _int(operator_action_board.get("already_applied_count"))
        ),
        "operator_action_board_action_count": _int(operator_action_board.get("action_count")),
        "operator_action_board_open_value_count": _int(operator_action_board.get("open_operator_value_count")),
        "operator_action_board_open_evidence_count": _int(operator_action_board.get("open_evidence_ref_count")),
        "operator_action_board_open_clearance_count": _int(operator_action_board.get("open_operator_clearance_count")),
        "promotion_ready_count": _int(promotion.get("ready_for_competitive_proof_count")),
        "promotion_awaiting_file_count": _int(promotion.get("awaiting_file_evidence_count")),
        "promotion_awaiting_operator_count": _int(promotion.get("awaiting_operator_values_count")),
        "promotion_awaiting_intake_count": _int(promotion.get("awaiting_intake_preflight_count")),
        "first_blocking_stage": first_stage,
        "first_open_benchmark_id": _text(first_row.get("first_open_benchmark_id")),
        "first_next_action": _text(first_row.get("next_action")) or "provide strict-blind replacement cycle inputs",
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _cycle_status(
    input_blockers: list[str],
    dropzone: dict[str, Any],
    quality: dict[str, Any],
    import_gate: dict[str, Any],
    operator_gate: dict[str, Any],
    operator_action_board: dict[str, Any],
    intake: dict[str, Any],
    promotion: dict[str, Any],
) -> tuple[str, str]:
    if input_blockers:
        return "blocked_missing_input", "queue"
    promotion_total = _int(promotion.get("slot_count"))
    promotion_ready = _int(promotion.get("ready_for_competitive_proof_count"))
    if promotion_total and promotion_ready == promotion_total:
        return "strict_blind_replacements_ready_for_competitive_proof", "promotion"
    if _int(quality.get("blocked_evidence_quality_count")):
        return "blocked_evidence_quality", "evidence_quality"
    if _int(dropzone.get("file_missing_count")):
        return "awaiting_evidence_files", "evidence_dropzones"
    if _int(quality.get("awaiting_evidence_files_count")):
        return "awaiting_evidence_quality_files", "evidence_quality"
    if _int(import_gate.get("awaiting_file_count")):
        return "awaiting_evidence_import", "evidence_import"
    if _int(operator_gate.get("awaiting_operator_value_count")):
        return "awaiting_operator_values", "operator_values"
    if _int(operator_action_board.get("open_operator_value_count")):
        return "awaiting_operator_action_board", "operator_action_board"
    if _int(intake.get("blocked_or_awaiting_count")):
        return "awaiting_intake_preflight", "intake"
    return "awaiting_strict_blind_promotion", "promotion"


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Strict-Blind Replacement Cycle",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['strict_blind_replacement_cycle_status']}`",
        f"- slots promotion-ready/total: `{summary['promotion_ready_count']}/{summary['slot_count']}`",
        f"- evidence files present/missing: `{summary['evidence_file_present_count']}/{summary['evidence_file_missing_count']}`",
        f"- quality ready/awaiting/blocked: `{summary['quality_ready_count']}/{summary['quality_awaiting_count']}/{summary['quality_blocked_count']}`",
        f"- import ready/awaiting-file/awaiting-operator: `{summary['import_ready_count']}/{summary['import_awaiting_file_count']}/{summary['import_awaiting_operator_count']}`",
        f"- operator ready/awaiting-value: `{summary['operator_ready_count']}/{summary['operator_awaiting_value_count']}`",
        f"- operator action board ready/open-value/open-evidence/open-clearance: `{summary['operator_action_board_ready_count']}/{summary['operator_action_board_open_value_count']}/{summary['operator_action_board_open_evidence_count']}/{summary['operator_action_board_open_clearance_count']}`",
        f"- first blocking stage: `{summary['first_blocking_stage'] or '-'}`",
        f"- first open: `{summary['first_open_benchmark_id'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Stages",
        "",
        "| stage | status | ready | awaiting | blocked | total | first open | next action |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['stage']}` | `{row['status']}` | {row['ready_count']} | {row['awaiting_count']} | "
            f"{row['blocked_count']} | {row['total_count']} | `{row['first_open_benchmark_id'] or '-'}` | "
            f"{row['next_action'] or '-'} |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 strict-blind replacement cycle summary.")
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    parser.add_argument("--intake-json", default=DEFAULT_INTAKE_JSON)
    parser.add_argument("--dropzones-json", default=DEFAULT_DROPZONES_JSON)
    parser.add_argument("--quality-json", default=DEFAULT_QUALITY_JSON)
    parser.add_argument("--import-json", default=DEFAULT_IMPORT_JSON)
    parser.add_argument("--operator-json", default=DEFAULT_OPERATOR_JSON)
    parser.add_argument("--operator-action-board-json", default=DEFAULT_OPERATOR_ACTION_BOARD_JSON)
    parser.add_argument("--promotion-json", default=DEFAULT_PROMOTION_JSON)
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
