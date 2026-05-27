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

DEFAULT_OPERATOR_CLEARANCE_CSV = "runs/casp17_historical_identity_seed_operator_clearance_current.csv"
DEFAULT_SEED_MANIFEST_CSV = "runs/casp17_historical_benchmark_manifest_seed_current.csv"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_chronology_candidate_board_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_chronology_candidate_board_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_CHRONOLOGY_CANDIDATE_BOARD.md"

TRUE_VALUES = {"true", "yes", "1", "y"}
PLACEHOLDER_TOKENS = ("REQUIRED", "YYYY-MM-DD")
DATE_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")
ROW_COLUMNS = [
    "row_rank",
    "target_id",
    "benchmark_id",
    "chronology_status",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "prediction_path_date",
    "prediction_file_mtime_date",
    "native_file_mtime_date",
    "path_date_present",
    "file_mtime_present",
    "file_mtime_prediction_before_native",
    "next_action",
    "blockers",
]
CLAIM_BOUNDARY = (
    "Local CASP17 historical seed chronology candidate board only. It separates operator-entered chronology "
    "from weak local path/mtime candidates. File mtimes and path dates are not treated as no-leak chronology "
    "clearance. The board does not mutate operator CSVs, infer native release dates, fetch native structures, "
    "score native accuracy, or submit to CASP."
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


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _date_or_none(value: Any) -> dt.date | None:
    text = _text(value)
    if not text or any(token in text.upper() for token in PLACEHOLDER_TOKENS):
        return None
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        return None


def _path_date(value: Any) -> str:
    match = DATE_RE.search(_text(value))
    return match.group(1) if match else ""


def _mtime_date(value: Any) -> str:
    path = _resolve(_text(value))
    if not path.is_file():
        return ""
    return dt.datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()


def _row_status(row: dict[str, str]) -> dict[str, Any]:
    prediction_date = _date_or_none(row.get("prediction_created_at"))
    native_date = _date_or_none(row.get("native_release_date"))
    before_flag = _text(row.get("prediction_generated_before_native_release")).lower()
    prediction_path_date = _path_date(row.get("prediction_pdb"))
    prediction_mtime_date = _mtime_date(row.get("prediction_pdb"))
    native_mtime_date = _mtime_date(row.get("native_pdb"))
    mtime_order: bool | str = ""
    if prediction_mtime_date and native_mtime_date:
        mtime_order = prediction_mtime_date < native_mtime_date
    blockers: list[str] = []
    if prediction_date is None:
        blockers.append("prediction_created_at_requires_operator_evidence")
    if native_date is None:
        blockers.append("native_release_date_requires_operator_evidence")
    if before_flag not in TRUE_VALUES:
        blockers.append("prediction_generated_before_native_release_requires_operator_evidence")
    if prediction_date is not None and native_date is not None and prediction_date >= native_date:
        blockers.append("operator_chronology_date_order_conflict")
    if mtime_order is False:
        blockers.append("file_mtime_not_before_native_mtime")
    if not prediction_path_date:
        blockers.append("prediction_path_date_candidate_missing")
    if not prediction_mtime_date or not native_mtime_date:
        blockers.append("file_mtime_candidate_missing")
    if (
        prediction_date is not None
        and native_date is not None
        and prediction_date < native_date
        and before_flag in TRUE_VALUES
    ):
        status = "operator_chronology_ready" if "file_mtime_not_before_native_mtime" not in blockers else "operator_ready_mtime_warning"
    elif "operator_chronology_date_order_conflict" in blockers:
        status = "blocked_chronology_conflict"
    else:
        status = "operator_evidence_required"
    if status.startswith("operator_chronology_ready"):
        next_action = "keep chronology evidence attached and continue no-leak provenance review"
    elif status == "operator_ready_mtime_warning":
        next_action = "review local mtime warning but keep operator chronology evidence as authority"
    elif status == "blocked_chronology_conflict":
        next_action = "repair prediction/native date order before any cleared manifest promotion"
    else:
        next_action = "fill prediction_created_at, native_release_date, and before-native confirmation from operator evidence"
    return {
        "chronology_status": status,
        "prediction_created_at": _text(row.get("prediction_created_at")),
        "native_release_date": _text(row.get("native_release_date")),
        "prediction_generated_before_native_release": _text(row.get("prediction_generated_before_native_release")),
        "prediction_path_date": prediction_path_date,
        "prediction_file_mtime_date": prediction_mtime_date,
        "native_file_mtime_date": native_mtime_date,
        "path_date_present": bool(prediction_path_date),
        "file_mtime_present": bool(prediction_mtime_date and native_mtime_date),
        "file_mtime_prediction_before_native": mtime_order,
        "next_action": next_action,
        "blockers": ",".join(blockers),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    operator_rows, _operator_fields = _read_csv(args.operator_clearance_csv)
    seed_rows, _seed_fields = _read_csv(args.seed_manifest_csv)
    seed_by_target = {_text(row.get("target_id")).upper(): row for row in seed_rows}
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(operator_rows, start=1):
        target_id = _text(row.get("target_id")).upper()
        merged = dict(seed_by_target.get(target_id, {}))
        merged.update(row)
        report = {
            "row_rank": index,
            "target_id": target_id,
            "benchmark_id": _text(merged.get("benchmark_id")),
        }
        report.update(_row_status(merged))
        rows.append(report)
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["chronology_status"]] = status_counts.get(row["chronology_status"], 0) + 1
    conflict_count = status_counts.get("blocked_chronology_conflict", 0)
    if not rows:
        status = "missing_operator_rows"
    elif conflict_count:
        status = "blocked_chronology_conflict"
    elif status_counts.get("operator_evidence_required", 0):
        status = "operator_evidence_required"
    else:
        status = "operator_chronology_ready"
    first_open = next((row for row in rows if row["chronology_status"] != "operator_chronology_ready"), rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_historical_seed_chronology_candidate_board",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "chronology_board_status": status,
        "operator_clearance_csv": _artifact(args.operator_clearance_csv),
        "seed_manifest_csv": _artifact(args.seed_manifest_csv),
        "row_count": len(rows),
        "operator_chronology_ready_count": status_counts.get("operator_chronology_ready", 0),
        "operator_ready_mtime_warning_count": status_counts.get("operator_ready_mtime_warning", 0),
        "operator_evidence_required_count": status_counts.get("operator_evidence_required", 0),
        "blocked_chronology_conflict_count": conflict_count,
        "prediction_path_date_count": sum(1 for row in rows if row["path_date_present"]),
        "file_mtime_candidate_count": sum(1 for row in rows if row["file_mtime_present"]),
        "file_mtime_order_risk_count": sum(1 for row in rows if row["file_mtime_prediction_before_native"] is False),
        "first_open_target_id": _text(first_open.get("target_id")),
        "first_next_action": _text(first_open.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Chronology Candidate Board",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- chronology_board_status: `{summary['chronology_board_status']}`",
        f"- rows ready/warning/evidence-required/conflict/total: `{summary['operator_chronology_ready_count']}/{summary['operator_ready_mtime_warning_count']}/{summary['operator_evidence_required_count']}/{summary['blocked_chronology_conflict_count']}/{summary['row_count']}`",
        f"- path-date candidates: `{summary['prediction_path_date_count']}`",
        f"- file-mtime candidates/order-risk: `{summary['file_mtime_candidate_count']}/{summary['file_mtime_order_risk_count']}`",
        f"- first open: `{summary['first_open_target_id'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Rows",
        "",
        "| rank | target | status | operator pred/native | path date | mtime pred/native | mtime order | next action | blockers |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['row_rank']} | `{row['target_id']}` | `{row['chronology_status']}` | "
            f"`{row['prediction_created_at'] or '-'}`/`{row['native_release_date'] or '-'}` | "
            f"`{row['prediction_path_date'] or '-'}` | "
            f"`{row['prediction_file_mtime_date'] or '-'}`/`{row['native_file_mtime_date'] or '-'}` | "
            f"`{row['file_mtime_prediction_before_native']}` | {row['next_action']} | `{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `missing_operator_rows` | - | - | - | - | provide operator CSV | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 historical seed chronology candidate board.")
    parser.add_argument("--operator-clearance-csv", default=DEFAULT_OPERATOR_CLEARANCE_CSV)
    parser.add_argument("--seed-manifest-csv", default=DEFAULT_SEED_MANIFEST_CSV)
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
