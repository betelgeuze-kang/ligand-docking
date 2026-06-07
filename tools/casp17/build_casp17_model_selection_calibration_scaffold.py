#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_HISTORICAL_BENCHMARK_JSON = "runs/casp17_historical_benchmark_packet_current.json"
DEFAULT_EXISTING_CALIBRATION_CSV = "runs/casp17_model_selection_calibration_current.csv"
DEFAULT_OUT_JSON = "runs/casp17_model_selection_calibration_scaffold_current.json"
DEFAULT_OUT_CSV = "runs/casp17_model_selection_calibration_scaffold_current.csv"
DEFAULT_OUT_MD = "runs/casp17_model_selection_calibration_scaffold_current.md"

LEAKAGE_CLEAR_VALUES = {"no_leak", "cleared", "true", "yes", "internal_no_leak"}
REQUIRED_COLUMNS = [
    "benchmark_id",
    "scope",
    "selected_model_rank",
    "best_model_rank",
    "selected_native_metric",
    "best_native_metric",
    "selected_score",
    "best_score",
    "leakage_clearance",
]


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


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], ["existing_calibration_csv_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    blockers = [f"required_columns_missing:{','.join(missing)}"] if missing else []
    if not rows:
        blockers.append("existing_calibration_csv_empty")
    return rows, blockers


def _float_or_none(value: Any) -> float | None:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for key in REQUIRED_COLUMNS + ["calibration_ready_status", "blockers", "source"]:
        if key not in fieldnames:
            fieldnames.append(key)
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _base_row(source: str, benchmark_id: str, scope: str) -> dict[str, Any]:
    return {
        "benchmark_id": benchmark_id,
        "scope": scope,
        "selected_model_rank": "",
        "best_model_rank": "",
        "selected_native_metric": "",
        "best_native_metric": "",
        "selected_score": "",
        "best_score": "",
        "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
        "source": source,
    }


def _placeholder_rows() -> list[dict[str, Any]]:
    return [
        _with_status(_base_row("placeholder_required_inputs", "hist_REQUIRED_MONOMER", "monomer")),
        _with_status(_base_row("placeholder_required_inputs", "hist_REQUIRED_COMPLEX", "complex")),
    ]


def _row_from_historical(row: dict[str, Any]) -> dict[str, Any]:
    benchmark_id = _text(row.get("benchmark_id")) or _text(row.get("target_id")) or "unknown"
    scope = _text(row.get("scope")).lower() or "monomer"
    scaffold = _base_row("historical_benchmark_row", benchmark_id, scope)
    scaffold["leakage_clearance"] = _text(row.get("leakage_clearance")) or "REQUIRED_NO_LEAK_CLEARANCE"
    return _with_status(scaffold)


def _row_from_existing(row: dict[str, str]) -> dict[str, Any]:
    normalized = {column: _text(row.get(column)) for column in REQUIRED_COLUMNS}
    normalized["source"] = "existing_calibration_csv"
    return _with_status(normalized)


def _with_status(row: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    if not _text(row.get("benchmark_id")):
        blockers.append("benchmark_id_missing")
    scope = _text(row.get("scope")).lower()
    row["scope"] = scope
    if scope not in {"monomer", "complex"}:
        blockers.append("scope_not_monomer_or_complex")
    leakage = _text(row.get("leakage_clearance")).lower()
    if leakage not in LEAKAGE_CLEAR_VALUES:
        blockers.append("leakage_clearance_required")
    selected_rank = _int_or_none(row.get("selected_model_rank"))
    best_rank = _int_or_none(row.get("best_model_rank"))
    if selected_rank is None or selected_rank < 1 or selected_rank > 5:
        blockers.append("selected_model_rank_required_1_to_5")
    if best_rank is None or best_rank < 1 or best_rank > 5:
        blockers.append("best_model_rank_required_1_to_5")
    for column in ["selected_native_metric", "best_native_metric", "selected_score", "best_score"]:
        if _float_or_none(row.get(column)) is None:
            blockers.append(f"{column}_required_numeric")
    row["calibration_ready_status"] = "ready" if not blockers else "blocked"
    row["blockers"] = ",".join(blockers)
    return row


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    historical_payload = _read_json(args.historical_benchmark_json)
    historical_summary = _summary(historical_payload)
    existing_rows, existing_blockers = _read_csv(args.existing_calibration_csv)
    source_mode = "existing_calibration_csv"
    rows = [_row_from_existing(row) for row in existing_rows]
    if not rows:
        historical_rows = [
            row for row in _rows(historical_payload) if _text(row.get("benchmark_status")).lower() == "pass"
        ]
        if historical_rows:
            rows = [_row_from_historical(row) for row in historical_rows]
            source_mode = "historical_benchmark_rows"
        else:
            rows = _placeholder_rows()
            source_mode = "placeholder_required_inputs"
    ready_count = sum(1 for row in rows if row["calibration_ready_status"] == "ready")
    blocked_count = len(rows) - ready_count
    monomer_count = sum(1 for row in rows if row.get("scope") == "monomer")
    complex_count = sum(1 for row in rows if row.get("scope") == "complex")
    summary = {
        "packet_type": "casp17_model_selection_calibration_scaffold",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "historical_benchmark_json": _artifact(args.historical_benchmark_json),
        "existing_calibration_csv": _artifact(args.existing_calibration_csv),
        "source_mode": source_mode,
        "historical_benchmark_status": historical_summary.get("historical_benchmark_status", "missing"),
        "historical_benchmark_count": int(historical_summary.get("benchmark_count", 0) or 0),
        "candidate_count": len(rows),
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "monomer_candidate_count": monomer_count,
        "complex_candidate_count": complex_count,
        "existing_csv_blockers": ",".join(existing_blockers),
        "scaffold_status": "ready" if rows and blocked_count == 0 else "blocked",
        "required_calibration_columns": ",".join(REQUIRED_COLUMNS),
        "claim_boundary": "Local model-selection calibration scaffold only; it does not fetch natives, compute oracle metrics, clear leakage, or submit to CASP.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Model Selection Calibration Scaffold",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- scaffold_status: `{summary['scaffold_status']}`",
        f"- source_mode: `{summary['source_mode']}`",
        f"- historical_benchmark_status: `{summary['historical_benchmark_status']}`",
        f"- ready/blocked: `{summary['ready_count']}/{summary['blocked_count']}`",
        f"- monomer/complex candidates: `{summary['monomer_candidate_count']}/{summary['complex_candidate_count']}`",
        f"- existing_csv_blockers: `{summary['existing_csv_blockers'] or '-'}`",
        "",
        "## Required Calibration Columns",
        "",
        f"`{summary['required_calibration_columns']}`",
        "",
        "## Checklist",
        "",
        "| benchmark | scope | ready | selected/best rank | selected/best native metric | selected/best score | leakage | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['benchmark_id']}` | `{row['scope']}` | `{row['calibration_ready_status']}` | "
            f"`{row['selected_model_rank'] or '-'}/{row['best_model_rank'] or '-'}` | "
            f"`{row['selected_native_metric'] or '-'}/{row['best_native_metric'] or '-'}` | "
            f"`{row['selected_score'] or '-'}/{row['best_score'] or '-'}` | `{row['leakage_clearance']}` | {row['blockers'] or '-'} |"
        )
    lines.extend(
        [
            "",
            "## Use",
            "",
            "Only rows with `calibration_ready_status=ready` should be copied into `runs/casp17_model_selection_calibration_current.csv`.",
            "Rows must come from no-leak historical top-5 predictions with oracle native metrics; do not use current CASP17 target natives or post-release structures.",
            "",
            "## Claim Boundary",
            "",
            str(summary["claim_boundary"]),
            "",
        ]
    )
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a fail-closed CASP17 model-selection calibration CSV scaffold/checklist.")
    parser.add_argument("--historical-benchmark-json", default=DEFAULT_HISTORICAL_BENCHMARK_JSON)
    parser.add_argument("--existing-calibration-csv", default=DEFAULT_EXISTING_CALIBRATION_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
