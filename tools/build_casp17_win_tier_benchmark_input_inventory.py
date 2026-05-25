#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INPUT_SCAFFOLD_JSON = "runs/casp17_win_tier_benchmark_input_scaffold_current.json"
DEFAULT_OUT_JSON = "runs/casp17_win_tier_benchmark_input_inventory_current.json"
DEFAULT_OUT_CSV = "runs/casp17_win_tier_benchmark_input_inventory_current.csv"
DEFAULT_OUT_FILES_CSV = "runs/casp17_win_tier_benchmark_input_inventory_files_current.csv"
DEFAULT_OUT_MD = "runs/casp17_win_tier_benchmark_input_inventory_current.md"

TRUE_VALUES = {"1", "true", "yes", "y"}
FALSE_VALUES = {"0", "false", "no", "n"}
CLEAR_VALUES = {"no_leak", "cleared", "true", "yes", "internal_no_leak"}
DATE_COLUMNS = {"prediction_created_at", "native_release_date"}
FALSE_COLUMNS = {
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
    "current_casp17_target",
}
RANK_COLUMNS = {"selected_model_rank", "best_model_rank"}
NUMERIC_COLUMNS = {"selected_native_metric", "best_native_metric", "selected_score", "best_score"}


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


def _json_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], [f"{path.name}_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    blockers: list[str] = []
    if not fieldnames:
        blockers.append(f"{path.name}_header_missing")
    if not rows:
        blockers.append(f"{path.name}_empty")
    return rows, blockers


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["row_rank", "target_id", "inventory_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _is_placeholder(value: Any) -> bool:
    text = _text(value)
    upper = text.upper()
    return not text or upper.startswith("REQUIRED_") or "YYYY-MM-DD" in upper


def _date_ok(value: Any) -> bool:
    text = _text(value)
    if _is_placeholder(text):
        return False
    try:
        dt.date.fromisoformat(text[:10])
    except ValueError:
        return False
    return True


def _date_value(value: Any) -> dt.date | None:
    if not _date_ok(value):
        return None
    return dt.date.fromisoformat(_text(value)[:10])


def _numeric_ok(value: Any) -> bool:
    try:
        parsed = float(_text(value))
    except ValueError:
        return False
    return math.isfinite(parsed)


def _rank_ok(value: Any) -> bool:
    try:
        parsed = int(_text(value))
    except ValueError:
        return False
    return 1 <= parsed <= 5


def _pdb_counts(path: Path) -> tuple[int, int, str]:
    atom_count = 0
    ca_count = 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not (line.startswith("ATOM") or line.startswith("HETATM")):
                    continue
                atom_count += 1
                if line[12:16].strip() == "CA":
                    ca_count += 1
    except OSError as exc:
        return 0, 0, f"pdb_read_failed:{type(exc).__name__}"
    blockers: list[str] = []
    if atom_count <= 0:
        blockers.append("pdb_atom_records_missing")
    if ca_count <= 0:
        blockers.append("pdb_ca_records_missing")
    return atom_count, ca_count, ",".join(blockers)


def _file_row(row: dict[str, Any], required_file: dict[str, str]) -> dict[str, Any]:
    expected_path = _text(required_file.get("expected_path"))
    path = _resolve(expected_path) if expected_path else ROOT / "__missing__"
    exists = bool(expected_path and path.exists())
    size_bytes = path.stat().st_size if exists else 0
    atom_count = 0
    ca_count = 0
    blockers: list[str] = []
    if not expected_path:
        blockers.append("expected_path_missing")
    elif _is_placeholder(expected_path):
        blockers.append("expected_path_placeholder")
    if not exists:
        blockers.append("file_missing")
    elif size_bytes <= 0:
        blockers.append("file_empty")
    elif path.suffix.lower() == ".pdb":
        atom_count, ca_count, pdb_blocker = _pdb_counts(path)
        if pdb_blocker:
            blockers.append(pdb_blocker)
    return {
        "row_rank": row["row_rank"],
        "benchmark_id": row["benchmark_id"],
        "target_id": row["target_id"],
        "scope": row["scope"],
        "file_role": _text(required_file.get("file_role")),
        "template_column": _text(required_file.get("template_column")),
        "expected_path": expected_path,
        "exists": exists,
        "size_bytes": size_bytes,
        "pdb_atom_count": atom_count,
        "pdb_ca_count": ca_count,
        "file_status": "pass" if not blockers else "blocked",
        "blockers": ",".join(blockers),
    }


def _field_status(column: str, value: Any) -> tuple[str, str]:
    lower = _text(value).lower()
    if column in {"leakage_clearance", "operator_clearance"}:
        return ("pass", "") if lower in CLEAR_VALUES else ("blocked", f"{column}_requires_no_leak_clearance")
    if column == "prediction_method":
        return ("pass", "") if not _is_placeholder(value) else ("blocked", "prediction_method_required")
    if column in DATE_COLUMNS:
        return ("pass", "") if _date_ok(value) else ("blocked", f"{column}_requires_iso_date")
    if column == "prediction_generated_before_native_release":
        return ("pass", "") if lower in TRUE_VALUES else ("blocked", "prediction_before_native_release_confirmation_required")
    if column in FALSE_COLUMNS:
        return ("pass", "") if lower in FALSE_VALUES else ("blocked", f"{column}_must_be_false")
    if column in RANK_COLUMNS:
        return ("pass", "") if _rank_ok(value) else ("blocked", f"{column}_requires_rank_1_to_5")
    if column in NUMERIC_COLUMNS:
        return ("pass", "") if _numeric_ok(value) else ("blocked", f"{column}_requires_numeric")
    return ("pass", "") if not _is_placeholder(value) else ("blocked", f"{column}_required")


def _field_group_status(rows: list[dict[str, str]], columns: set[str] | None = None) -> tuple[str, int, str]:
    if not rows:
        return "blocked", 0, "template_csv_missing_or_empty"
    blockers: list[str] = []
    ready = 0
    row = rows[0]
    selected_columns = columns if columns is not None else set(row)
    for column in selected_columns:
        status, blocker = _field_status(column, row.get(column))
        if status == "pass":
            ready += 1
        elif blocker:
            blockers.append(blocker)
    pred = _date_value(row.get("prediction_created_at"))
    native = _date_value(row.get("native_release_date"))
    if pred and native and pred >= native:
        blockers.append("prediction_date_not_before_native_release")
    return ("pass" if not blockers else "blocked"), ready, ",".join(blockers)


def _inventory_row(scaffold_row: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    required_files, file_source_blockers = _read_csv(scaffold_row.get("required_files_csv", ""))
    provenance_rows, provenance_source_blockers = _read_csv(scaffold_row.get("provenance_template_csv", ""))
    calibration_rows, calibration_source_blockers = _read_csv(scaffold_row.get("calibration_template_csv", ""))
    file_rows = [_file_row(scaffold_row, row) for row in required_files]
    present_files = sum(1 for row in file_rows if row["file_status"] == "pass")
    prediction_files = [row for row in file_rows if row["file_role"] == "prediction_pdb"]
    native_files = [row for row in file_rows if row["file_role"] == "native_pdb"]
    ablation_files = [row for row in file_rows if row["file_role"].startswith("ablation_")]
    present_ablation = sum(1 for row in ablation_files if row["file_status"] == "pass")
    provenance_status, provenance_ready_count, provenance_blockers = _field_group_status(
        provenance_rows,
        {
            "leakage_clearance",
            "prediction_method",
            "prediction_created_at",
            "native_release_date",
            "prediction_generated_before_native_release",
            "public_template_or_native_used_for_prediction",
            "other_team_model_used",
            "post_release_information_used",
            "current_casp17_target",
            "operator_clearance",
        },
    )
    calibration_status, calibration_ready_count, calibration_blockers = _field_group_status(
        calibration_rows,
        {
            "selected_model_rank",
            "best_model_rank",
            "selected_native_metric",
            "best_native_metric",
            "selected_score",
            "best_score",
        },
    )
    blockers = []
    blockers.extend(file_source_blockers)
    blockers.extend(provenance_source_blockers)
    blockers.extend(calibration_source_blockers)
    if len(file_rows) != int(scaffold_row.get("required_file_count") or len(file_rows)):
        blockers.append("required_file_inventory_count_mismatch")
    missing_files = len(file_rows) - present_files
    if missing_files:
        blockers.append("required_files_missing")
    if provenance_status != "pass":
        blockers.append(provenance_blockers or "provenance_blocked")
    if calibration_status != "pass":
        blockers.append(calibration_blockers or "calibration_blocked")
    if _is_placeholder(scaffold_row.get("target_id")):
        blockers.append("placeholder_target_id")
    if _is_placeholder(scaffold_row.get("benchmark_id")):
        blockers.append("placeholder_benchmark_id")
    row = {
        "row_rank": scaffold_row["row_rank"],
        "benchmark_id": scaffold_row["benchmark_id"],
        "target_id": scaffold_row["target_id"],
        "scope": scaffold_row["scope"],
        "metric_profile": scaffold_row["metric_profile"],
        "inventory_status": "ready" if not blockers else "blocked",
        "required_file_count": len(file_rows),
        "present_file_count": present_files,
        "missing_file_count": missing_files,
        "prediction_file_present": bool(prediction_files and prediction_files[0]["file_status"] == "pass"),
        "native_file_present": bool(native_files and native_files[0]["file_status"] == "pass"),
        "ablation_layer_present_count": present_ablation,
        "ablation_layer_required_count": len(ablation_files),
        "provenance_status": provenance_status,
        "provenance_ready_field_count": provenance_ready_count,
        "calibration_status": calibration_status,
        "calibration_ready_field_count": calibration_ready_count,
        "row_dir": scaffold_row.get("row_dir", ""),
        "blockers": ",".join(item for item in blockers if item),
    }
    return row, file_rows


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Win-Tier Benchmark Input Inventory",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- inventory_status: `{summary['inventory_status']}`",
        f"- rows ready/blocked: `{summary['ready_row_count']}/{summary['blocked_row_count']}`",
        f"- files present/missing: `{summary['present_file_count']}/{summary['missing_file_count']}`",
        f"- prediction/native present: `{summary['present_prediction_file_count']}/{summary['present_native_file_count']}`",
        f"- ablation present/required: `{summary['present_ablation_layer_file_count']}/{summary['required_ablation_layer_file_count']}`",
        f"- provenance ready rows: `{summary['provenance_ready_row_count']}`",
        f"- calibration ready rows: `{summary['calibration_ready_row_count']}`",
        f"- files_csv: `{summary['files_csv']}`",
        "",
        "## Rows",
        "",
        "| rank | benchmark | target | scope | status | files | ablation | provenance | calibration | blockers |",
        "| ---: | --- | --- | --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['row_rank']} | `{row['benchmark_id']}` | `{row['target_id']}` | `{row['scope']}` | "
            f"`{row['inventory_status']}` | {row['present_file_count']}/{row['required_file_count']} | "
            f"{row['ablation_layer_present_count']}/{row['ablation_layer_required_count']} | "
            f"`{row['provenance_status']}` | `{row['calibration_status']}` | `{row['blockers'] or '-'}` |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    scaffold_payload = _read_json(args.input_scaffold_json)
    scaffold_summary = _summary(scaffold_payload)
    scaffold_rows = _json_rows(scaffold_payload)
    rows: list[dict[str, Any]] = []
    file_rows: list[dict[str, Any]] = []
    for scaffold_row in scaffold_rows:
        row, files = _inventory_row(scaffold_row)
        rows.append(row)
        file_rows.extend(files)
    ready_rows = [row for row in rows if row["inventory_status"] == "ready"]
    present_files = [row for row in file_rows if row["file_status"] == "pass"]
    prediction_files = [row for row in file_rows if row["file_role"] == "prediction_pdb" and row["file_status"] == "pass"]
    native_files = [row for row in file_rows if row["file_role"] == "native_pdb" and row["file_status"] == "pass"]
    ablation_files = [row for row in file_rows if row["file_role"].startswith("ablation_")]
    present_ablation = [row for row in ablation_files if row["file_status"] == "pass"]
    summary = {
        "packet_type": "casp17_win_tier_benchmark_input_inventory",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "inventory_status": "ready" if rows and len(ready_rows) == len(rows) else "blocked",
        "input_scaffold_json": _artifact(args.input_scaffold_json),
        "input_scaffold_status": _text(scaffold_summary.get("scaffold_status")),
        "row_count": len(rows),
        "ready_row_count": len(ready_rows),
        "blocked_row_count": len(rows) - len(ready_rows),
        "required_file_count": len(file_rows),
        "present_file_count": len(present_files),
        "missing_file_count": len(file_rows) - len(present_files),
        "present_prediction_file_count": len(prediction_files),
        "required_prediction_file_count": sum(1 for row in file_rows if row["file_role"] == "prediction_pdb"),
        "present_native_file_count": len(native_files),
        "required_native_file_count": sum(1 for row in file_rows if row["file_role"] == "native_pdb"),
        "present_ablation_layer_file_count": len(present_ablation),
        "required_ablation_layer_file_count": len(ablation_files),
        "provenance_ready_row_count": sum(1 for row in rows if row["provenance_status"] == "pass"),
        "calibration_ready_row_count": sum(1 for row in rows if row["calibration_status"] == "pass"),
        "files_csv": _artifact(args.out_files_csv),
        "claim_boundary": (
            "Local input inventory only. It checks row scaffold files, provenance placeholders, and calibration placeholders; "
            "it does not fetch natives, certify no-leak status, score accuracy, use external predictors, or submit to CASP."
        ),
    }
    return {"summary": summary, "rows": rows, "file_rows": file_rows}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inventory CASP17 win-tier benchmark scaffold inputs.")
    parser.add_argument("--input-scaffold-json", default=DEFAULT_INPUT_SCAFFOLD_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-files-csv", default=DEFAULT_OUT_FILES_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, {"summary": payload["summary"], "rows": payload["rows"]})
    _write_csv(args.out_csv, payload["rows"])
    _write_csv(args.out_files_csv, payload["file_rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
