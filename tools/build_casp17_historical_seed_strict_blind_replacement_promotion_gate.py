#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INTAKE_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_intake_current.json"
DEFAULT_EVIDENCE_IMPORT_GATE_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_evidence_import_gate_current.json"
)
DEFAULT_OPERATOR_VALUE_GATE_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_operator_value_gate_current.json"
)
DEFAULT_GATE_DIR = "casp17/historical_seed_strict_blind_replacement_promotion_gate"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_promotion_gate_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_strict_blind_replacement_promotion_gate_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_PROMOTION_GATE.md"

FILE_COMPLETE_STATUSES = {"already_applied", "applied"}
OPERATOR_COMPLETE_STATUSES = {"already_applied", "applied"}
ROW_COLUMNS = [
    "queue_rank",
    "required_benchmark_id",
    "required_target_id",
    "scope",
    "metric_profile",
    "promotion_status",
    "ready_for_competitive_proof",
    "intake_status",
    "intake_filled_field_count",
    "intake_missing_field_count",
    "file_action_count",
    "file_complete_count",
    "file_ready_apply_count",
    "file_awaiting_count",
    "file_blocked_count",
    "operator_action_count",
    "operator_complete_count",
    "operator_ready_apply_count",
    "operator_awaiting_count",
    "operator_blocked_count",
    "promotion_md",
    "blockers",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local CASP17 strict-blind replacement promotion gate only. It aggregates intake preflight, file evidence "
    "import, and operator-value gates to decide whether a replacement slot may enter competitive proof. It does "
    "not select replacement targets, approve no-leak provenance, compute CASP metrics, mutate benchmark CSVs, "
    "or submit to CASP."
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


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


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


def _safe_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_") or "unknown"


def _group_by_benchmark(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_text(row.get("required_benchmark_id"))].append(row)
    return grouped


def _count_status(rows: list[dict[str, Any]], key: str, statuses: set[str]) -> int:
    return sum(1 for row in rows if _text(row.get(key)) in statuses)


def _count_prefix(rows: list[dict[str, Any]], key: str, prefix: str) -> int:
    return sum(1 for row in rows if _text(row.get(key)).startswith(prefix))


def _file_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    file_rows = [row for row in rows if _text(row.get("field_kind")) == "file"]
    return {
        "action": len(file_rows),
        "complete": _count_status(file_rows, "import_status", FILE_COMPLETE_STATUSES),
        "ready_apply": _count_status(file_rows, "import_status", {"ready_to_apply"}),
        "awaiting": _count_prefix(file_rows, "import_status", "awaiting"),
        "blocked": _count_prefix(file_rows, "import_status", "blocked"),
    }


def _operator_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "action": len(rows),
        "complete": _count_status(rows, "gate_status", OPERATOR_COMPLETE_STATUSES),
        "ready_apply": _count_status(rows, "gate_status", {"ready_to_apply"}),
        "awaiting": _count_prefix(rows, "gate_status", "awaiting"),
        "blocked": _count_prefix(rows, "gate_status", "blocked"),
    }


def _status_and_blockers(
    intake_row: dict[str, Any],
    file_counts: dict[str, int],
    operator_counts: dict[str, int],
) -> tuple[str, list[str], str]:
    blockers: list[str] = []
    intake_status = _text(intake_row.get("preflight_status"))
    intake_missing = _int(intake_row.get("missing_field_count"))
    if file_counts["blocked"]:
        blockers.append(f"file_import_blocked:{file_counts['blocked']}")
    if operator_counts["blocked"]:
        blockers.append(f"operator_value_blocked:{operator_counts['blocked']}")
    if file_counts["awaiting"]:
        blockers.append(f"file_evidence_missing:{file_counts['awaiting']}")
    if operator_counts["awaiting"]:
        blockers.append(f"operator_values_missing:{operator_counts['awaiting']}")
    if file_counts["ready_apply"]:
        blockers.append(f"file_import_apply_required:{file_counts['ready_apply']}")
    if operator_counts["ready_apply"]:
        blockers.append(f"operator_value_apply_required:{operator_counts['ready_apply']}")
    if file_counts["action"] < 6:
        blockers.append(f"file_action_count_below_required:{file_counts['action']}")
    if operator_counts["action"] < 10:
        blockers.append(f"operator_action_count_below_required:{operator_counts['action']}")
    if intake_status != "ready_for_strict_blind_preflight":
        blockers.append(f"intake_status:{intake_status or 'missing'}")
    if intake_missing:
        blockers.append(f"intake_missing_fields:{intake_missing}")
    if not blockers:
        return "ready_for_competitive_proof", [], "promote this strict-blind replacement into competitive proof row fill"
    if file_counts["blocked"] or operator_counts["blocked"]:
        return "blocked_review_required", blockers, "repair blocked file/operator gate rows before promotion"
    if file_counts["awaiting"]:
        return "awaiting_file_evidence", blockers, "place required strict-blind evidence files, rerun dropzones/import gate"
    if operator_counts["awaiting"]:
        return "awaiting_operator_values", blockers, "fill replacement_operator_values.csv and rerun operator value gate"
    if file_counts["ready_apply"] or operator_counts["ready_apply"]:
        return "awaiting_apply", blockers, "apply ready file/operator values, then rerun intake preflight"
    return "awaiting_intake_preflight", blockers, "rerun strict-blind replacement intake preflight"


def _write_row_md(path: Path, row: dict[str, Any]) -> None:
    lines = [
        f"# {row['required_benchmark_id']} Promotion Gate",
        "",
        f"- status: `{row['promotion_status']}`",
        f"- ready_for_competitive_proof: `{row['ready_for_competitive_proof']}`",
        f"- required target: `{row['required_target_id']}`",
        f"- scope: `{row['scope']}`",
        f"- intake status: `{row['intake_status']}`",
        f"- intake filled/missing: `{row['intake_filled_field_count']}/{row['intake_missing_field_count']}`",
        f"- file actions complete/ready/awaiting/blocked: `{row['file_complete_count']}/{row['file_ready_apply_count']}/{row['file_awaiting_count']}/{row['file_blocked_count']}`",
        f"- operator actions complete/ready/awaiting/blocked: `{row['operator_complete_count']}/{row['operator_ready_apply_count']}/{row['operator_awaiting_count']}/{row['operator_blocked_count']}`",
        f"- blockers: `{row['blockers'] or '-'}`",
        f"- next action: {row['next_action'] or '-'}",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _promotion_row(
    intake_row: dict[str, Any],
    file_rows: list[dict[str, Any]],
    operator_rows: list[dict[str, Any]],
    gate_dir: str | Path,
) -> dict[str, Any]:
    file_counts = _file_counts(file_rows)
    operator_counts = _operator_counts(operator_rows)
    status, blockers, next_action = _status_and_blockers(intake_row, file_counts, operator_counts)
    queue_rank = _int(intake_row.get("queue_rank"))
    benchmark_id = _text(intake_row.get("required_benchmark_id"))
    folder = _resolve(gate_dir) / f"{queue_rank:02d}_{_safe_name(benchmark_id)}"
    md = folder / "PROMOTION_GATE.md"
    row = {
        "queue_rank": queue_rank,
        "required_benchmark_id": benchmark_id,
        "required_target_id": _text(intake_row.get("required_target_id")),
        "scope": _text(intake_row.get("scope")),
        "metric_profile": _text(intake_row.get("metric_profile")),
        "promotion_status": status,
        "ready_for_competitive_proof": "true" if status == "ready_for_competitive_proof" else "false",
        "intake_status": _text(intake_row.get("preflight_status")),
        "intake_filled_field_count": _int(intake_row.get("filled_field_count")),
        "intake_missing_field_count": _int(intake_row.get("missing_field_count")),
        "file_action_count": file_counts["action"],
        "file_complete_count": file_counts["complete"],
        "file_ready_apply_count": file_counts["ready_apply"],
        "file_awaiting_count": file_counts["awaiting"],
        "file_blocked_count": file_counts["blocked"],
        "operator_action_count": operator_counts["action"],
        "operator_complete_count": operator_counts["complete"],
        "operator_ready_apply_count": operator_counts["ready_apply"],
        "operator_awaiting_count": operator_counts["awaiting"],
        "operator_blocked_count": operator_counts["blocked"],
        "promotion_md": _artifact(md),
        "blockers": ",".join(blockers),
        "next_action": next_action,
    }
    _write_row_md(md, row)
    return row


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    intake_payload = _read_json(args.intake_json)
    evidence_payload = _read_json(args.evidence_import_gate_json)
    operator_payload = _read_json(args.operator_value_gate_json)
    intake_rows = _rows(intake_payload)
    file_by_benchmark = _group_by_benchmark(_rows(evidence_payload))
    operator_by_benchmark = _group_by_benchmark(_rows(operator_payload))
    input_blockers: list[str] = []
    if not _resolve(args.intake_json).exists():
        input_blockers.append("strict_blind_replacement_intake_json_missing")
    if not _resolve(args.evidence_import_gate_json).exists():
        input_blockers.append("strict_blind_replacement_evidence_import_gate_json_missing")
    if not _resolve(args.operator_value_gate_json).exists():
        input_blockers.append("strict_blind_replacement_operator_value_gate_json_missing")
    rows = [
        _promotion_row(
            row,
            file_by_benchmark.get(_text(row.get("required_benchmark_id")), []),
            operator_by_benchmark.get(_text(row.get("required_benchmark_id")), []),
            args.gate_dir,
        )
        for row in intake_rows
    ]
    summary = _build_summary(args, rows, input_blockers, intake_payload, evidence_payload, operator_payload)
    return {"summary": summary, "rows": rows}


def _build_summary(
    args: argparse.Namespace,
    rows: list[dict[str, Any]],
    input_blockers: list[str],
    intake_payload: dict[str, Any],
    evidence_payload: dict[str, Any],
    operator_payload: dict[str, Any],
) -> dict[str, Any]:
    by_status: dict[str, int] = defaultdict(int)
    for row in rows:
        by_status[_text(row.get("promotion_status"))] += 1
    first_open = next((row for row in rows if row.get("promotion_status") != "ready_for_competitive_proof"), {})
    first_open_status = _text(first_open.get("promotion_status"))
    summary = {
        "packet_type": "casp17_historical_seed_strict_blind_replacement_promotion_gate",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "strict_blind_replacement_promotion_gate_status": _overall_status(rows, input_blockers),
        "intake_json": _artifact(args.intake_json),
        "evidence_import_gate_json": _artifact(args.evidence_import_gate_json),
        "operator_value_gate_json": _artifact(args.operator_value_gate_json),
        "gate_dir": _artifact(args.gate_dir),
        "intake_status": _text(_summary(intake_payload).get("strict_blind_replacement_intake_status")),
        "evidence_import_gate_status": _text(
            _summary(evidence_payload).get("strict_blind_replacement_evidence_import_gate_status")
        ),
        "operator_value_gate_status": _text(
            _summary(operator_payload).get("strict_blind_replacement_operator_value_gate_status")
        ),
        "slot_count": len(rows),
        "ready_for_competitive_proof_count": by_status["ready_for_competitive_proof"],
        "awaiting_file_evidence_count": sum(1 for row in rows if _int(row.get("file_awaiting_count")) > 0),
        "awaiting_operator_values_count": sum(1 for row in rows if _int(row.get("operator_awaiting_count")) > 0),
        "awaiting_apply_count": sum(
            1
            for row in rows
            if _int(row.get("file_ready_apply_count")) > 0 or _int(row.get("operator_ready_apply_count")) > 0
        ),
        "awaiting_intake_preflight_count": sum(
            1 for row in rows if row.get("intake_status") != "ready_for_strict_blind_preflight"
        ),
        "blocked_review_count": sum(
            1
            for row in rows
            if _int(row.get("file_blocked_count")) > 0
            or _int(row.get("operator_blocked_count")) > 0
            or row.get("promotion_status") == "blocked_review_required"
        ),
        "intake_ready_count": sum(1 for row in rows if row.get("intake_status") == "ready_for_strict_blind_preflight"),
        "file_complete_slot_count": sum(1 for row in rows if _int(row.get("file_complete_count")) >= 6),
        "operator_complete_slot_count": sum(1 for row in rows if _int(row.get("operator_complete_count")) >= 10),
        "file_awaiting_action_count": sum(_int(row.get("file_awaiting_count")) for row in rows),
        "operator_awaiting_action_count": sum(_int(row.get("operator_awaiting_count")) for row in rows),
        "first_open_benchmark_id": _text(first_open.get("required_benchmark_id")),
        "first_open_status": first_open_status,
        "first_open_phase": _phase_for_status(first_open_status),
        "first_next_action": _text(first_open.get("next_action")) or "provide strict-blind replacement gate inputs",
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return summary


def _phase_for_status(status: str) -> str:
    return {
        "ready_for_competitive_proof": "competitive_proof",
        "awaiting_file_evidence": "file_evidence",
        "awaiting_operator_values": "operator_values",
        "awaiting_apply": "apply",
        "awaiting_intake_preflight": "intake_preflight",
        "blocked_review_required": "review",
    }.get(status, "input")


def _overall_status(rows: list[dict[str, Any]], input_blockers: list[str]) -> str:
    if input_blockers:
        return "blocked_missing_input"
    if not rows:
        return "blocked_missing_promotion_rows"
    if all(row.get("promotion_status") == "ready_for_competitive_proof" for row in rows):
        return "strict_blind_replacements_ready_for_competitive_proof"
    if any(row.get("promotion_status") == "blocked_review_required" for row in rows):
        return "blocked_review_required"
    return "awaiting_strict_blind_replacement_promotion"


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Strict-Blind Replacement Promotion Gate",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['strict_blind_replacement_promotion_gate_status']}`",
        f"- slots ready/total: `{summary['ready_for_competitive_proof_count']}/{summary['slot_count']}`",
        f"- awaiting file/operator/apply/intake: `{summary['awaiting_file_evidence_count']}/{summary['awaiting_operator_values_count']}/{summary['awaiting_apply_count']}/{summary['awaiting_intake_preflight_count']}`",
        f"- blocked review: `{summary['blocked_review_count']}`",
        f"- intake/file/operator complete slots: `{summary['intake_ready_count']}/{summary['file_complete_slot_count']}/{summary['operator_complete_slot_count']}`",
        f"- awaiting file/operator actions: `{summary['file_awaiting_action_count']}/{summary['operator_awaiting_action_count']}`",
        f"- first open: `{summary['first_open_benchmark_id'] or '-'}` `{summary['first_open_phase'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Promotion Rows",
        "",
        "| rank | benchmark | scope | status | ready | file complete/awaiting | operator complete/awaiting | blockers |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['queue_rank']} | `{row['required_benchmark_id']}` | `{row['scope']}` | "
            f"`{row['promotion_status']}` | `{row['ready_for_competitive_proof']}` | "
            f"{row['file_complete_count']}/{row['file_awaiting_count']} | "
            f"{row['operator_complete_count']}/{row['operator_awaiting_count']} | `{row['blockers']}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked_missing_promotion_rows` | false | 0/0 | 0/0 | provide inputs |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 strict-blind replacement promotion gate.")
    parser.add_argument("--intake-json", default=DEFAULT_INTAKE_JSON)
    parser.add_argument("--evidence-import-gate-json", default=DEFAULT_EVIDENCE_IMPORT_GATE_JSON)
    parser.add_argument("--operator-value-gate-json", default=DEFAULT_OPERATOR_VALUE_GATE_JSON)
    parser.add_argument("--gate-dir", default=DEFAULT_GATE_DIR)
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
