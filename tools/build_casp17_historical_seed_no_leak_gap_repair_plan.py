#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_NO_LEAK_DOSSIERS_JSON = "casp17/casp17_historical_seed_no_leak_provenance_dossiers_current.json"
DEFAULT_CHRONOLOGY_BOARD_JSON = "casp17/casp17_historical_seed_chronology_candidate_board_current.json"
DEFAULT_REPAIR_DIR = "casp17/historical_seed_no_leak_gap_repair_plan"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_no_leak_gap_repair_plan_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_no_leak_gap_repair_plan_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_NO_LEAK_GAP_REPAIR_PLAN.md"

NO_LEAK_FIELDS = [
    "no_leak_evidence_ref",
    "leakage_clearance",
    "operator_clearance",
    "operator",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
]

CHRONOLOGY_FIELDS = {
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
}
NEGATIVE_CONTROL_FIELDS = {
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
}
CLEARANCE_FIELDS = {"no_leak_evidence_ref", "leakage_clearance", "operator_clearance", "operator"}

ROW_COLUMNS = [
    "row_rank",
    "target_id",
    "benchmark_id",
    "scope",
    "repair_status",
    "repair_csv",
    "field_count",
    "operator_required_field_count",
    "weak_local_candidate_field_count",
    "authoritative_candidate_field_count",
    "chronology_field_count",
    "negative_control_field_count",
    "clearance_field_count",
    "mtime_risk",
    "next_action",
    "blockers",
]

FIELD_COLUMNS = [
    "target_id",
    "benchmark_id",
    "scope",
    "field_name",
    "field_group",
    "operator_required",
    "authoritative_candidate_value",
    "weak_local_candidate_value",
    "weak_local_candidate_source",
    "repair_status",
    "blockers",
    "notes",
]

CLAIM_BOUNDARY = (
    "Local CASP17 historical seed no-leak gap repair plan only. It decomposes operator-required no-leak "
    "provenance fields and surfaces weak local chronology hints for review. Path dates and file mtimes are "
    "not no-leak clearance authority. The packet does not mutate operator CSVs, approve leakage clearance, "
    "infer native release authority, fetch structures, run predictors, or submit to CASP."
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


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"true", "1", "yes", "y"}


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


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _safe_name(target_id: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in target_id).strip("_") or "unknown"


def _field_group(field_name: str) -> str:
    if field_name in CHRONOLOGY_FIELDS:
        return "chronology"
    if field_name in NEGATIVE_CONTROL_FIELDS:
        return "negative_control"
    if field_name in CLEARANCE_FIELDS:
        return "clearance"
    return "other"


def _weak_candidate(field_name: str, dossier_row: dict[str, Any], chronology_row: dict[str, Any]) -> tuple[str, str]:
    if field_name == "prediction_created_at":
        path_date = _text(chronology_row.get("prediction_path_date")) or _text(dossier_row.get("prediction_path_date"))
        mtime_date = _text(chronology_row.get("prediction_file_mtime_date")) or _text(
            dossier_row.get("prediction_file_mtime_date")
        )
        if path_date:
            return path_date, "prediction_path_date"
        if mtime_date:
            return mtime_date, "prediction_file_mtime"
    if field_name == "native_release_date":
        mtime_date = _text(chronology_row.get("native_file_mtime_date")) or _text(dossier_row.get("native_file_mtime_date"))
        if mtime_date:
            return mtime_date, "native_file_mtime_not_release_authority"
    return "", ""


def _field_row(
    field_name: str,
    dossier_row: dict[str, Any],
    chronology_row: dict[str, Any],
    target_id: str,
    benchmark_id: str,
    scope: str,
) -> dict[str, Any]:
    group = _field_group(field_name)
    weak_value, weak_source = _weak_candidate(field_name, dossier_row, chronology_row)
    blockers = ["operator_evidence_required"]
    if group == "chronology":
        blockers.append("authoritative_chronology_required")
    if group == "negative_control":
        blockers.append("operator_negative_control_required")
    if field_name in {"leakage_clearance", "operator_clearance"}:
        blockers.append("operator_clearance_required")
    if field_name == "no_leak_evidence_ref":
        blockers.append("independent_no_leak_evidence_ref_required")
    if weak_value:
        blockers.append("weak_local_candidate_not_clearance_authority")
    return {
        "target_id": target_id,
        "benchmark_id": benchmark_id,
        "scope": scope,
        "field_name": field_name,
        "field_group": group,
        "operator_required": True,
        "authoritative_candidate_value": "",
        "weak_local_candidate_value": weak_value,
        "weak_local_candidate_source": weak_source,
        "repair_status": "operator_evidence_required_with_weak_hint" if weak_value else "operator_evidence_required",
        "blockers": ",".join(dict.fromkeys(blockers)),
        "notes": "manual no-leak provenance field; do not auto-fill from local timestamps or path names",
    }


def _build_target_row(
    dossier_row: dict[str, Any],
    chronology_row: dict[str, Any],
    row_rank: int,
    repair_dir: str | Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    target_id = _text(dossier_row.get("target_id")).upper()
    benchmark_id = _text(dossier_row.get("benchmark_id"))
    scope = _text(dossier_row.get("scope"))
    field_rows = [
        _field_row(field, dossier_row, chronology_row, target_id, benchmark_id, scope) for field in NO_LEAK_FIELDS
    ]
    weak_count = sum(1 for row in field_rows if _text(row.get("weak_local_candidate_value")))
    mtime_risk = _bool(dossier_row.get("file_mtime_prediction_before_native")) is False or _text(
        chronology_row.get("file_mtime_prediction_before_native")
    ).lower() == "false"
    repair_csv = _resolve(repair_dir) / f"{row_rank:02d}_{_safe_name(target_id)}" / "no_leak_gap_repair_fields.csv"
    _write_csv(repair_csv, field_rows, FIELD_COLUMNS)
    blockers = ["operator_no_leak_evidence_required"]
    if mtime_risk:
        blockers.append("mtime_not_clearance_authority")
    status = "no_leak_gap_repair_required"
    summary_row = {
        "row_rank": row_rank,
        "target_id": target_id,
        "benchmark_id": benchmark_id,
        "scope": scope,
        "repair_status": status,
        "repair_csv": _artifact(repair_csv),
        "field_count": len(field_rows),
        "operator_required_field_count": len(field_rows),
        "weak_local_candidate_field_count": weak_count,
        "authoritative_candidate_field_count": 0,
        "chronology_field_count": sum(1 for row in field_rows if row["field_group"] == "chronology"),
        "negative_control_field_count": sum(1 for row in field_rows if row["field_group"] == "negative_control"),
        "clearance_field_count": sum(1 for row in field_rows if row["field_group"] == "clearance"),
        "mtime_risk": mtime_risk,
        "next_action": "attach independent no-leak evidence, authoritative dates, negative controls, and operator clearance",
        "blockers": ",".join(blockers),
    }
    return summary_row, field_rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    dossier_payload = _read_json(args.no_leak_dossiers_json)
    chronology_payload = _read_json(args.chronology_board_json)
    dossier_rows = _rows(dossier_payload)
    chronology_by_target = {_text(row.get("target_id")).upper(): row for row in _rows(chronology_payload)}
    rows: list[dict[str, Any]] = []
    repair_rows_by_target: dict[str, list[dict[str, Any]]] = {}
    for index, dossier_row in enumerate(dossier_rows, start=1):
        target_id = _text(dossier_row.get("target_id")).upper()
        summary_row, field_rows = _build_target_row(
            dossier_row,
            chronology_by_target.get(target_id, {}),
            index,
            args.repair_dir,
        )
        rows.append(summary_row)
        repair_rows_by_target[target_id] = field_rows
    input_blockers: list[str] = []
    if not _resolve(args.no_leak_dossiers_json).exists():
        input_blockers.append("no_leak_dossiers_json_missing")
    if not _resolve(args.chronology_board_json).exists():
        input_blockers.append("chronology_board_json_missing")
    if input_blockers:
        status = "blocked_missing_input"
    elif not rows:
        status = "blocked_missing_no_leak_rows"
    else:
        status = "no_leak_gap_repair_required"
    first_open = rows[0] if rows else {}
    summary = {
        "packet_type": "casp17_historical_seed_no_leak_gap_repair_plan",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "no_leak_gap_repair_status": status,
        "no_leak_dossiers_json": _artifact(args.no_leak_dossiers_json),
        "chronology_board_json": _artifact(args.chronology_board_json),
        "repair_dir": _artifact(args.repair_dir),
        "seed_row_count": len(rows),
        "repair_csv_count": sum(1 for row in rows if _text(row.get("repair_csv"))),
        "field_count": sum(_int(row.get("field_count")) for row in rows),
        "operator_required_field_count": sum(_int(row.get("operator_required_field_count")) for row in rows),
        "weak_local_candidate_field_count": sum(_int(row.get("weak_local_candidate_field_count")) for row in rows),
        "authoritative_candidate_field_count": sum(_int(row.get("authoritative_candidate_field_count")) for row in rows),
        "chronology_field_count": sum(_int(row.get("chronology_field_count")) for row in rows),
        "negative_control_field_count": sum(_int(row.get("negative_control_field_count")) for row in rows),
        "clearance_field_count": sum(_int(row.get("clearance_field_count")) for row in rows),
        "mtime_risk_row_count": sum(1 for row in rows if row.get("mtime_risk")),
        "first_open_target_id": _text(first_open.get("target_id")),
        "first_next_action": _text(first_open.get("next_action")) or "provide no-leak dossier rows",
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows, "repair_rows_by_target": repair_rows_by_target}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed No-Leak Gap Repair Plan",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- no_leak_gap_repair_status: `{summary['no_leak_gap_repair_status']}`",
        f"- seed rows/repair csvs: `{summary['seed_row_count']}/{summary['repair_csv_count']}`",
        f"- fields/operator-required/weak/authoritative: `{summary['field_count']}/{summary['operator_required_field_count']}/{summary['weak_local_candidate_field_count']}/{summary['authoritative_candidate_field_count']}`",
        f"- chronology/negative-control/clearance fields: `{summary['chronology_field_count']}/{summary['negative_control_field_count']}/{summary['clearance_field_count']}`",
        f"- mtime-risk rows: `{summary['mtime_risk_row_count']}`",
        f"- first open: `{summary['first_open_target_id'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Seed Rows",
        "",
        "| rank | target | scope | status | fields | weak | chronology | negative | clearance | mtime risk | csv | blockers |",
        "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['row_rank']} | `{row['target_id']}` | `{row['scope']}` | `{row['repair_status']}` | "
            f"{row['field_count']} | {row['weak_local_candidate_field_count']} | "
            f"{row['chronology_field_count']} | {row['negative_control_field_count']} | "
            f"{row['clearance_field_count']} | `{row['mtime_risk']}` | `{row['repair_csv']}` | "
            f"`{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked_missing_no_leak_rows` | 0 | 0 | 0 | 0 | 0 | - | - | provide inputs |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 historical seed no-leak gap repair plan.")
    parser.add_argument("--no-leak-dossiers-json", default=DEFAULT_NO_LEAK_DOSSIERS_JSON)
    parser.add_argument("--chronology-board-json", default=DEFAULT_CHRONOLOGY_BOARD_JSON)
    parser.add_argument("--repair-dir", default=DEFAULT_REPAIR_DIR)
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
