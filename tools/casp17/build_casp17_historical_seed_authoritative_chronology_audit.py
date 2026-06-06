#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_NATIVE_AUTHORITY_AUDIT_JSON = "casp17/casp17_historical_seed_native_authority_audit_current.json"
DEFAULT_CHRONOLOGY_BOARD_JSON = "casp17/casp17_historical_seed_chronology_candidate_board_current.json"
DEFAULT_AUDIT_DIR = "casp17/historical_seed_authoritative_chronology_audit"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_authoritative_chronology_audit_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_authoritative_chronology_audit_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_AUTHORITATIVE_CHRONOLOGY_AUDIT.md"

MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

ROW_COLUMNS = [
    "row_rank",
    "target_id",
    "benchmark_id",
    "scope",
    "chronology_authority_status",
    "prediction_created_candidate",
    "prediction_candidate_source",
    "native_authority_date",
    "native_authority_source",
    "native_authority_ref",
    "native_authority_status",
    "prediction_after_native_authority",
    "prediction_before_or_on_native_authority",
    "audit_folder",
    "next_action",
    "blockers",
]

CLAIM_BOUNDARY = (
    "Local CASP17 historical seed authoritative chronology audit only. It compares local/internal "
    "prediction-date candidates with native-authority dates parsed from already-audited native evidence. "
    "It does not clear no-leak provenance, certify a prediction was blind, approve use of public native "
    "structures/templates, mutate operator clearance CSVs, compute official CASP metrics, or submit to CASP."
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


def _parse_iso_date(value: str) -> dt.date | None:
    text = _text(value)
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        return None


def _parse_pdb_header_date(header: str) -> str:
    match = re.search(r"\b(\d{2})-([A-Z]{3})-(\d{2})\b", header.upper())
    if not match:
        return ""
    day_text, month_text, year_text = match.groups()
    month = MONTHS.get(month_text)
    if month is None:
        return ""
    year_two = int(year_text)
    year = 1900 + year_two if year_two >= 70 else 2000 + year_two
    try:
        return dt.date(year, month, int(day_text)).isoformat()
    except ValueError:
        return ""


def _prediction_path_date(path_text: str) -> str:
    match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", path_text)
    return match.group(1) if match else ""


def _prediction_candidate(native_row: dict[str, Any], chronology_row: dict[str, Any]) -> tuple[str, str]:
    chronology_date = _text(chronology_row.get("prediction_path_date"))
    if chronology_date:
        return chronology_date, "chronology_board_prediction_path_date"
    path_date = _prediction_path_date(_text(native_row.get("prediction_pdb")))
    if path_date:
        return path_date, "prediction_pdb_path_date"
    mtime_date = _text(chronology_row.get("prediction_file_mtime_date"))
    if mtime_date:
        return mtime_date, "chronology_board_prediction_file_mtime"
    return "", ""


def _row_status(
    prediction_date: str,
    native_date: str,
    native_authority_status: str,
) -> tuple[str, bool, bool, list[str], str]:
    blockers: list[str] = []
    prediction_after_native = False
    prediction_before_or_on_native = False
    if native_authority_status != "authority_pass":
        blockers.append("native_authority_not_pass")
    if not native_date:
        blockers.append("authoritative_native_date_missing")
    if not prediction_date:
        blockers.append("prediction_date_candidate_missing")
    prediction_dt = _parse_iso_date(prediction_date)
    native_dt = _parse_iso_date(native_date)
    if prediction_date and prediction_dt is None:
        blockers.append("prediction_date_candidate_invalid")
    if native_date and native_dt is None:
        blockers.append("native_authority_date_invalid")
    if prediction_dt and native_dt:
        prediction_after_native = prediction_dt > native_dt
        prediction_before_or_on_native = prediction_dt <= native_dt
        if prediction_after_native:
            blockers.append("prediction_not_before_authoritative_native_date")
            status = "post_native_prediction_chronology_blocked"
            next_action = (
                "replace with a pre-native blind prediction artifact, or keep this row in a separate "
                "post-native retrospective lane with explicit no-template evidence"
            )
            return status, prediction_after_native, prediction_before_or_on_native, blockers, next_action
    if blockers:
        status = "operator_authoritative_chronology_evidence_required"
        next_action = "attach missing authority dates and independent prediction chronology evidence"
    else:
        status = "chronology_candidate_before_native_review"
        next_action = "operator must still verify no-leak provenance and negative leakage controls"
    return status, prediction_after_native, prediction_before_or_on_native, blockers, next_action


def _write_row_md(path: Path, row: dict[str, Any]) -> None:
    lines = [
        f"# {row['target_id']} Authoritative Chronology Audit",
        "",
        f"- status: `{row['chronology_authority_status']}`",
        f"- benchmark: `{row['benchmark_id']}`",
        f"- scope: `{row['scope']}`",
        f"- prediction candidate: `{row['prediction_created_candidate'] or '-'}` `{row['prediction_candidate_source'] or '-'}`",
        f"- native authority date: `{row['native_authority_date'] or '-'}` `{row['native_authority_source'] or '-'}`",
        f"- native authority: `{row['native_authority_status']}` `{row['native_authority_ref'] or '-'}`",
        f"- prediction after native authority: `{row['prediction_after_native_authority']}`",
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


def _build_row(
    row_rank: int,
    native_row: dict[str, Any],
    chronology_row: dict[str, Any],
    audit_dir: str | Path,
) -> dict[str, Any]:
    target_id = _text(native_row.get("target_id")).upper()
    benchmark_id = _text(native_row.get("benchmark_id"))
    scope = _text(native_row.get("scope"))
    native_authority_status = _text(native_row.get("native_authority_status"))
    native_authority_ref = _text(native_row.get("native_authority_ref"))
    prediction_date, prediction_source = _prediction_candidate(native_row, chronology_row)
    native_date = _parse_pdb_header_date(_text(native_row.get("native_header")))
    native_source = f"pdb_header_date:{native_authority_ref}" if native_date and native_authority_ref else ""
    status, after_native, before_or_on_native, blockers, next_action = _row_status(
        prediction_date,
        native_date,
        native_authority_status,
    )
    folder = _resolve(audit_dir) / f"{row_rank:02d}_{_safe_name(target_id)}"
    out = {
        "row_rank": row_rank,
        "target_id": target_id,
        "benchmark_id": benchmark_id,
        "scope": scope,
        "chronology_authority_status": status,
        "prediction_created_candidate": prediction_date,
        "prediction_candidate_source": prediction_source,
        "native_authority_date": native_date,
        "native_authority_source": native_source,
        "native_authority_ref": native_authority_ref,
        "native_authority_status": native_authority_status,
        "prediction_after_native_authority": after_native,
        "prediction_before_or_on_native_authority": before_or_on_native,
        "audit_folder": _artifact(folder),
        "next_action": next_action,
        "blockers": ",".join(dict.fromkeys(blockers)),
    }
    _write_row_md(folder / "AUTHORITATIVE_CHRONOLOGY.md", out)
    _write_csv(folder / "authoritative_chronology.csv", [out], ROW_COLUMNS)
    return out


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    native_payload = _read_json(args.native_authority_audit_json)
    chronology_payload = _read_json(args.chronology_board_json)
    chronology_by_target = {_text(row.get("target_id")).upper(): row for row in _rows(chronology_payload)}
    rows = [
        _build_row(index, native_row, chronology_by_target.get(_text(native_row.get("target_id")).upper(), {}), args.audit_dir)
        for index, native_row in enumerate(_rows(native_payload), start=1)
    ]
    input_blockers: list[str] = []
    if not _resolve(args.native_authority_audit_json).exists():
        input_blockers.append("native_authority_audit_json_missing")
    if not _resolve(args.chronology_board_json).exists():
        input_blockers.append("chronology_board_json_missing")
    post_native_count = sum(1 for row in rows if row["chronology_authority_status"] == "post_native_prediction_chronology_blocked")
    evidence_required_count = sum(
        1 for row in rows if row["chronology_authority_status"] == "operator_authoritative_chronology_evidence_required"
    )
    before_native_count = sum(1 for row in rows if row["chronology_authority_status"] == "chronology_candidate_before_native_review")
    first_blocked = next(
        (row for row in rows if row["chronology_authority_status"] != "chronology_candidate_before_native_review"),
        rows[0] if rows else {},
    )
    if input_blockers:
        status = "blocked_missing_input"
    elif post_native_count:
        status = "post_native_prediction_chronology_blocked"
    elif evidence_required_count:
        status = "operator_authoritative_chronology_evidence_required"
    elif rows:
        status = "chronology_candidate_before_native_review"
    else:
        status = "blocked_missing_rows"
    summary = {
        "packet_type": "casp17_historical_seed_authoritative_chronology_audit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "authoritative_chronology_audit_status": status,
        "native_authority_audit_json": _artifact(args.native_authority_audit_json),
        "chronology_board_json": _artifact(args.chronology_board_json),
        "audit_dir": _artifact(args.audit_dir),
        "seed_row_count": len(rows),
        "native_authority_date_count": sum(1 for row in rows if _text(row.get("native_authority_date"))),
        "prediction_date_candidate_count": sum(1 for row in rows if _text(row.get("prediction_created_candidate"))),
        "before_native_candidate_count": before_native_count,
        "post_native_blocked_count": post_native_count,
        "evidence_required_count": evidence_required_count,
        "native_authority_not_pass_count": sum(1 for row in rows if row["native_authority_status"] != "authority_pass"),
        "missing_native_authority_date_count": sum(1 for row in rows if not _text(row.get("native_authority_date"))),
        "missing_prediction_date_count": sum(1 for row in rows if not _text(row.get("prediction_created_candidate"))),
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_next_action": _text(first_blocked.get("next_action")) or "provide native and prediction chronology inputs",
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Authoritative Chronology Audit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['authoritative_chronology_audit_status']}`",
        f"- seed rows: `{summary['seed_row_count']}`",
        f"- native authority dates / prediction date candidates: `{summary['native_authority_date_count']}/{summary['prediction_date_candidate_count']}`",
        f"- before-native / post-native-blocked / evidence-required: `{summary['before_native_candidate_count']}/{summary['post_native_blocked_count']}/{summary['evidence_required_count']}`",
        f"- native authority not-pass / missing native date / missing prediction date: `{summary['native_authority_not_pass_count']}/{summary['missing_native_authority_date_count']}/{summary['missing_prediction_date_count']}`",
        f"- first blocked: `{summary['first_blocked_target_id'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Seed Rows",
        "",
        "| rank | target | scope | status | prediction | native authority date | after native | blockers |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['row_rank']} | `{row['target_id']}` | `{row['scope']}` | "
            f"`{row['chronology_authority_status']}` | `{row['prediction_created_candidate'] or '-'}` | "
            f"`{row['native_authority_date'] or '-'}` | `{row['prediction_after_native_authority']}` | "
            f"`{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked_missing_rows` | - | - | - | provide inputs |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 historical seed authoritative chronology audit.")
    parser.add_argument("--native-authority-audit-json", default=DEFAULT_NATIVE_AUTHORITY_AUDIT_JSON)
    parser.add_argument("--chronology-board-json", default=DEFAULT_CHRONOLOGY_BOARD_JSON)
    parser.add_argument("--audit-dir", default=DEFAULT_AUDIT_DIR)
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
