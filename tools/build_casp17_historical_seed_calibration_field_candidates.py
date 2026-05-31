#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OPERATOR_CLEARANCE_CSV = "runs/casp17_historical_identity_seed_operator_clearance_current.csv"
DEFAULT_CALIBRATION_LEDGER_JSON = "casp17/casp17_historical_seed_calibration_candidate_ledgers_current.json"
DEFAULT_FIELD_DIR = "casp17/historical_seed_calibration_field_candidates"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_calibration_field_candidates_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_calibration_field_candidates_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_CALIBRATION_FIELD_CANDIDATES.md"

FIELD_MAP = [
    ("selected_model_rank", "selected_model_rank_candidate"),
    ("best_model_rank", "best_model_rank_candidate"),
    ("selected_native_metric", "selected_native_metric_candidate"),
    ("best_native_metric", "best_native_metric_candidate"),
    ("selected_score", "selected_score_candidate"),
    ("best_score", "best_score_candidate"),
]

ROW_COLUMNS = [
    "row_rank",
    "target_id",
    "benchmark_id",
    "scope",
    "field_candidate_status",
    "field_candidate_csv",
    "field_count",
    "proposed_field_count",
    "already_matching_field_count",
    "conflict_field_count",
    "blocked_field_count",
    "next_action",
    "blockers",
]

FIELD_COLUMNS = [
    "target_id",
    "benchmark_id",
    "scope",
    "field_name",
    "current_value",
    "proposed_value",
    "evidence_source",
    "candidate_status",
    "blockers",
    "notes",
]

CLAIM_BOUNDARY = (
    "Local CASP17 historical seed calibration field candidates only. This packet proposes values from already-built "
    "calibration ledgers for operator review. It does not mutate operator CSVs, clear no-leak provenance, prove "
    "historical eligibility, compute official CASP metrics, fetch structures, run predictors, or submit to CASP."
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


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], [f"{_artifact(path)}_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    blockers: list[str] = []
    if not fields:
        blockers.append(f"{_artifact(path)}_header_missing")
    return rows, blockers


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


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


def _safe_name(target_id: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in target_id).strip("_") or "unknown"


def _placeholder(value: Any) -> bool:
    text = _text(value)
    return not text or text.upper().startswith("REQUIRED")


def _proposal_ready(value: Any) -> bool:
    text = _text(value)
    return bool(text) and not text.upper().startswith("REQUIRES")


def _ledger_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _candidate_status(current_value: str, proposed_value: str) -> tuple[str, str]:
    if not _proposal_ready(proposed_value):
        return "blocked", "proposed_value_missing"
    if _placeholder(current_value):
        return "proposed", ""
    if current_value == proposed_value:
        return "already_matching", ""
    return "conflict", "existing_value_differs_from_candidate"


def _build_field_rows(operator_row: dict[str, str], ledger_row: dict[str, Any]) -> list[dict[str, Any]]:
    field_rows: list[dict[str, Any]] = []
    for field_name, candidate_name in FIELD_MAP:
        current_value = _text(operator_row.get(field_name))
        proposed_value = _text(ledger_row.get(candidate_name))
        status, blocker = _candidate_status(current_value, proposed_value)
        field_rows.append(
            {
                "target_id": _text(ledger_row.get("target_id")).upper(),
                "benchmark_id": _text(ledger_row.get("benchmark_id")),
                "scope": _text(ledger_row.get("scope")),
                "field_name": field_name,
                "current_value": current_value,
                "proposed_value": proposed_value,
                "evidence_source": _text(ledger_row.get("candidate_ledger_csv")),
                "candidate_status": status,
                "blockers": blocker,
                "notes": "operator review candidate; apply only after no-leak/provenance clearance",
            }
        )
    return field_rows


def _build_target_row(
    operator_row: dict[str, str],
    ledger_row: dict[str, Any],
    row_rank: int,
    field_dir: str | Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    target_id = _text(ledger_row.get("target_id")).upper()
    field_rows = _build_field_rows(operator_row, ledger_row)
    proposed_count = sum(1 for row in field_rows if row["candidate_status"] == "proposed")
    matching_count = sum(1 for row in field_rows if row["candidate_status"] == "already_matching")
    conflict_count = sum(1 for row in field_rows if row["candidate_status"] == "conflict")
    blocked_count = sum(1 for row in field_rows if row["candidate_status"] == "blocked")
    blockers: list[str] = []
    if conflict_count:
        blockers.append("existing_calibration_value_conflict")
    if blocked_count:
        blockers.append("calibration_candidate_value_missing")
    ready = proposed_count + matching_count == len(FIELD_MAP) and not conflict_count and not blocked_count
    status = "calibration_field_candidates_ready_for_operator_apply" if ready else "blocked_calibration_field_candidates"
    field_csv = _resolve(field_dir) / f"{row_rank:02d}_{_safe_name(target_id)}" / "calibration_field_candidates.csv"
    _write_csv(field_csv, field_rows, FIELD_COLUMNS)
    summary_row = {
        "row_rank": row_rank,
        "target_id": target_id,
        "benchmark_id": _text(ledger_row.get("benchmark_id")),
        "scope": _text(ledger_row.get("scope")),
        "field_candidate_status": status,
        "field_candidate_csv": _artifact(field_csv),
        "field_count": len(FIELD_MAP),
        "proposed_field_count": proposed_count,
        "already_matching_field_count": matching_count,
        "conflict_field_count": conflict_count,
        "blocked_field_count": blocked_count,
        "next_action": (
            "operator may apply calibration field candidates after no-leak provenance clearance"
            if ready
            else "repair calibration candidate values or resolve existing operator value conflicts"
        ),
        "blockers": ",".join(dict.fromkeys(blockers)),
    }
    return summary_row, field_rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    operator_rows, operator_blockers = _read_csv(args.operator_clearance_csv)
    ledger_payload = _read_json(args.calibration_ledger_json)
    ledger_rows = _ledger_rows(ledger_payload)
    operator_by_target = {_text(row.get("target_id")).upper(): row for row in operator_rows}
    rows: list[dict[str, Any]] = []
    field_rows_by_target: dict[str, list[dict[str, Any]]] = {}
    for index, ledger_row in enumerate(ledger_rows, start=1):
        target_id = _text(ledger_row.get("target_id")).upper()
        operator_row = operator_by_target.get(target_id, {})
        summary_row, field_rows = _build_target_row(operator_row, ledger_row, index, args.field_dir)
        rows.append(summary_row)
        field_rows_by_target[target_id] = field_rows
    input_blockers = operator_blockers
    if not _resolve(args.calibration_ledger_json).exists():
        status = "blocked_missing_calibration_ledger"
    elif input_blockers:
        status = "blocked_missing_operator_csv"
    elif not rows:
        status = "blocked_missing_ledger_rows"
    elif any(row["field_candidate_status"] != "calibration_field_candidates_ready_for_operator_apply" for row in rows):
        status = "blocked_calibration_field_candidates"
    else:
        status = "calibration_field_candidates_ready_for_operator_apply"
    first_open = next(
        (row for row in rows if row["field_candidate_status"] != "calibration_field_candidates_ready_for_operator_apply"),
        rows[0] if rows else {},
    )
    summary = {
        "packet_type": "casp17_historical_seed_calibration_field_candidates",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "calibration_field_candidate_status": status,
        "operator_clearance_csv": _artifact(args.operator_clearance_csv),
        "calibration_ledger_json": _artifact(args.calibration_ledger_json),
        "field_dir": _artifact(args.field_dir),
        "seed_row_count": len(rows),
        "field_candidate_count": sum(_int(row.get("field_count")) for row in rows),
        "proposed_field_count": sum(_int(row.get("proposed_field_count")) for row in rows),
        "already_matching_field_count": sum(_int(row.get("already_matching_field_count")) for row in rows),
        "conflict_field_count": sum(_int(row.get("conflict_field_count")) for row in rows),
        "blocked_field_count": sum(_int(row.get("blocked_field_count")) for row in rows),
        "ready_to_apply_row_count": sum(
            1 for row in rows if row["field_candidate_status"] == "calibration_field_candidates_ready_for_operator_apply"
        ),
        "blocked_row_count": sum(
            1 for row in rows if row["field_candidate_status"] != "calibration_field_candidates_ready_for_operator_apply"
        ),
        "first_open_target_id": _text(first_open.get("target_id")),
        "first_next_action": _text(first_open.get("next_action")) or "provide operator CSV and calibration ledger rows",
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows, "field_rows_by_target": field_rows_by_target}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Calibration Field Candidates",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- calibration_field_candidate_status: `{summary['calibration_field_candidate_status']}`",
        f"- seed rows/fields/proposed/already: `{summary['seed_row_count']}/{summary['field_candidate_count']}/{summary['proposed_field_count']}/{summary['already_matching_field_count']}`",
        f"- ready rows/blocked rows/conflicts/blocked fields: `{summary['ready_to_apply_row_count']}/{summary['blocked_row_count']}/{summary['conflict_field_count']}/{summary['blocked_field_count']}`",
        f"- first open: `{summary['first_open_target_id'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Seed Rows",
        "",
        "| rank | target | scope | status | fields | proposed | matching | conflict | blocked | csv | blockers |",
        "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['row_rank']} | `{row['target_id']}` | `{row['scope']}` | `{row['field_candidate_status']}` | "
            f"{row['field_count']} | {row['proposed_field_count']} | {row['already_matching_field_count']} | "
            f"{row['conflict_field_count']} | {row['blocked_field_count']} | `{row['field_candidate_csv']}` | "
            f"`{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked_missing_ledger_rows` | 0 | 0 | 0 | 0 | 0 | - | provide inputs |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 historical seed calibration field candidates.")
    parser.add_argument("--operator-clearance-csv", default=DEFAULT_OPERATOR_CLEARANCE_CSV)
    parser.add_argument("--calibration-ledger-json", default=DEFAULT_CALIBRATION_LEDGER_JSON)
    parser.add_argument("--field-dir", default=DEFAULT_FIELD_DIR)
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
