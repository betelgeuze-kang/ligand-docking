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

DEFAULT_BATCH_JSON = "casp17/casp17_competitive_floor_batch_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_row_fill_status_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_row_fill_status_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_ROW_FILL_STATUS.md"

PROVENANCE_COLUMNS = [
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
]
ABLATION_LAYER_NAMES = [
    "recursive",
    "scored",
    "sidechain_scaffold",
    "sidechain_repacked",
    "sidechain_completed",
    "steric_relaxed",
    "rotamer_minimized",
    "polar_refined",
    "forcefield_minimized",
    "statistical_rotamer",
]
ABLATION_COLUMNS = [f"{layer}_prediction_pdb" for layer in ABLATION_LAYER_NAMES]
CALIBRATION_COLUMNS = [
    "selected_model_rank",
    "best_model_rank",
    "selected_native_metric",
    "best_native_metric",
    "selected_score",
    "best_score",
]
REQUIRED_COLUMNS = (
    ["benchmark_id", "target_id", "scope", "split", "prediction_pdb", "native_pdb"]
    + PROVENANCE_COLUMNS
    + ABLATION_COLUMNS
    + CALIBRATION_COLUMNS
)

CLEAR_VALUES = {"no_leak", "cleared", "true", "yes", "internal_no_leak"}
TRUE_VALUES = {"1", "true", "yes", "y"}
FALSE_VALUES = {"0", "false", "no", "n"}
CLAIM_BOUNDARY = (
    "Local row-fill status packet only. It audits operator-filled competitive-floor row_fill.csv files and local "
    "file paths; it does not fetch natives, clear provenance, score native accuracy, use external predictors, or submit to CASP."
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
        return int(float(str(value).strip()))
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
    missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    if missing:
        blockers.append("required_columns_missing:" + ",".join(missing))
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
        fieldnames = ["operator_priority", "row_fill_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _contains_placeholder(value: Any) -> bool:
    text = _text(value)
    upper = text.upper()
    return not text or upper.startswith("REQUIRED") or "REQUIRED_" in upper or "YYYY-MM-DD" in upper


def _date_or_none(value: Any) -> dt.date | None:
    text = _text(value)
    if _contains_placeholder(text):
        return None
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def _float_or_none(value: Any) -> float | None:
    try:
        parsed = float(_text(value))
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _rank_ok(value: Any) -> bool:
    try:
        parsed = int(_text(value))
    except ValueError:
        return False
    return 1 <= parsed <= 5


def _local_path_ok(value: Any) -> tuple[bool, str]:
    text = _text(value)
    if _contains_placeholder(text):
        return False, "placeholder_path"
    if not _resolve(text).is_file():
        return False, "file_not_found"
    return True, ""


def _field_blockers(row: dict[str, str]) -> tuple[list[str], int, int, int, int]:
    blockers: list[str] = []
    missing_required = 0
    placeholder_fields = 0
    missing_files = 0
    for column in REQUIRED_COLUMNS:
        value = _text(row.get(column))
        if not value:
            missing_required += 1
            blockers.append(f"{column}_missing")
        elif _contains_placeholder(value):
            placeholder_fields += 1
            blockers.append(f"{column}_placeholder")

    for column in ["prediction_pdb", "native_pdb"] + ABLATION_COLUMNS:
        ok, blocker = _local_path_ok(row.get(column))
        if not ok:
            missing_files += 1
            blockers.append(f"{column}_{blocker}")

    provenance_blockers = 0
    if _text(row.get("leakage_clearance")).lower() not in CLEAR_VALUES:
        provenance_blockers += 1
        blockers.append("leakage_clearance_requires_no_leak_clearance")
    if _contains_placeholder(row.get("prediction_method")):
        provenance_blockers += 1
        blockers.append("prediction_method_required")
    prediction_date = _date_or_none(row.get("prediction_created_at"))
    native_date = _date_or_none(row.get("native_release_date"))
    if prediction_date is None:
        provenance_blockers += 1
        blockers.append("prediction_created_at_requires_iso_date")
    if native_date is None:
        provenance_blockers += 1
        blockers.append("native_release_date_requires_iso_date")
    if prediction_date and native_date and prediction_date >= native_date:
        provenance_blockers += 1
        blockers.append("prediction_date_not_before_native_release")
    if _text(row.get("prediction_generated_before_native_release")).lower() not in TRUE_VALUES:
        provenance_blockers += 1
        blockers.append("prediction_before_native_release_confirmation_required")
    for column in [
        "public_template_or_native_used_for_prediction",
        "other_team_model_used",
        "post_release_information_used",
        "current_casp17_target",
    ]:
        if _text(row.get(column)).lower() not in FALSE_VALUES:
            provenance_blockers += 1
            blockers.append(f"{column}_must_be_false")
    if _text(row.get("operator_clearance")).lower() not in CLEAR_VALUES:
        provenance_blockers += 1
        blockers.append("operator_clearance_requires_no_leak_clearance")

    calibration_blockers = 0
    if not _rank_ok(row.get("selected_model_rank")):
        calibration_blockers += 1
        blockers.append("selected_model_rank_requires_rank_1_to_5")
    if not _rank_ok(row.get("best_model_rank")):
        calibration_blockers += 1
        blockers.append("best_model_rank_requires_rank_1_to_5")
    selected_native = _float_or_none(row.get("selected_native_metric"))
    best_native = _float_or_none(row.get("best_native_metric"))
    if selected_native is None:
        calibration_blockers += 1
        blockers.append("selected_native_metric_requires_numeric")
    if best_native is None:
        calibration_blockers += 1
        blockers.append("best_native_metric_requires_numeric")
    if selected_native is not None and best_native is not None and selected_native > best_native + 1e-9:
        calibration_blockers += 1
        blockers.append("selected_native_metric_exceeds_oracle_metric")
    if _float_or_none(row.get("selected_score")) is None:
        calibration_blockers += 1
        blockers.append("selected_score_requires_numeric")
    if _float_or_none(row.get("best_score")) is None:
        calibration_blockers += 1
        blockers.append("best_score_requires_numeric")
    return sorted(set(blockers)), missing_required, placeholder_fields, missing_files, provenance_blockers + calibration_blockers


def _status_row(batch_row: dict[str, Any]) -> dict[str, Any]:
    batch_folder = _resolve(batch_row.get("batch_folder", ""))
    row_fill_template = batch_folder / "row_fill_template.csv"
    row_fill = batch_folder / "row_fill.csv"
    source_rows, source_blockers = _read_csv(row_fill)
    row = source_rows[0] if source_rows else {}
    blockers = list(source_blockers)
    missing_required = len(REQUIRED_COLUMNS)
    placeholder_fields = 0
    missing_files = 12
    semantic_blockers = 0
    if row:
        field_blockers, missing_required, placeholder_fields, missing_files, semantic_blockers = _field_blockers(row)
        blockers.extend(field_blockers)
    else:
        blockers.append("row_fill_csv_not_filled")
    blockers = sorted(set(blocker for blocker in blockers if blocker))
    status = "ready_for_operator_template" if row and not blockers else "awaiting_row_fill"
    if row and blockers:
        status = "blocked"
    next_action = (
        "copy row_fill_template.csv to row_fill.csv and replace placeholders"
        if not row_fill.exists()
        else "resolve row_fill.csv blockers and rerun operator-template/preflight"
    )
    return {
        "operator_priority": _int(batch_row.get("operator_priority")),
        "row_rank": _int(batch_row.get("row_rank")),
        "benchmark_id": _text(row.get("benchmark_id")) or _text(batch_row.get("benchmark_id")),
        "target_id": _text(row.get("target_id")) or _text(batch_row.get("target_id")),
        "scope": _text(row.get("scope")) or _text(batch_row.get("scope")),
        "row_fill_status": status,
        "batch_folder": _artifact(batch_folder),
        "row_fill_template_csv": _artifact(row_fill_template),
        "row_fill_csv": _artifact(row_fill),
        "row_fill_exists": row_fill.exists(),
        "missing_required_field_count": missing_required,
        "placeholder_field_count": placeholder_fields,
        "missing_local_file_count": missing_files,
        "semantic_blocker_count": semantic_blockers,
        "blockers": ",".join(blockers),
        "next_action": next_action,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    batch_payload = _read_json(args.batch_json)
    batch_summary = _summary(batch_payload)
    rows = [_status_row(row) for row in _rows(batch_payload)]
    filled_rows = [row for row in rows if row["row_fill_exists"]]
    ready_rows = [row for row in rows if row["row_fill_status"] == "ready_for_operator_template"]
    first_open = next((row for row in rows if row["row_fill_status"] != "ready_for_operator_template"), {})
    template_count = sum(1 for row in rows if _resolve(row["row_fill_template_csv"]).is_file())
    summary = {
        "packet_type": "casp17_competitive_floor_row_fill_status",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "row_fill_status": "ready_for_operator_template" if rows and len(ready_rows) == len(rows) else "awaiting_fill",
        "batch_json": _artifact(args.batch_json),
        "batch_status": _text(batch_summary.get("batch_status")),
        "row_count": len(rows),
        "row_fill_template_count": template_count,
        "row_fill_filled_count": len(filled_rows),
        "ready_for_operator_template_count": len(ready_rows),
        "blocked_or_awaiting_count": len(rows) - len(ready_rows),
        "missing_required_field_count": sum(int(row["missing_required_field_count"]) for row in rows),
        "placeholder_field_count": sum(int(row["placeholder_field_count"]) for row in rows),
        "missing_local_file_count": sum(int(row["missing_local_file_count"]) for row in rows),
        "semantic_blocker_count": sum(int(row["semantic_blocker_count"]) for row in rows),
        "first_open_row_fill_csv": first_open.get("row_fill_csv", ""),
        "first_open_template_csv": first_open.get("row_fill_template_csv", ""),
        "first_open_next_action": first_open.get("next_action", ""),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Row Fill Status",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- row_fill_status: `{summary['row_fill_status']}`",
        f"- templates/filled/ready/total: `{summary['row_fill_template_count']}/{summary['row_fill_filled_count']}/{summary['ready_for_operator_template_count']}/{summary['row_count']}`",
        f"- missing fields/placeholders/local-files/semantic blockers: `{summary['missing_required_field_count']}/{summary['placeholder_field_count']}/{summary['missing_local_file_count']}/{summary['semantic_blocker_count']}`",
        f"- first open row_fill_csv: `{summary['first_open_row_fill_csv'] or '-'}`",
        f"- first open template_csv: `{summary['first_open_template_csv'] or '-'}`",
        f"- first open next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Rows",
        "",
        "| priority | benchmark | target | scope | status | filled | missing fields | placeholders | missing files | blockers | next action |",
        "| ---: | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['operator_priority']} | `{row['benchmark_id']}` | `{row['target_id']}` | `{row['scope']}` | "
            f"`{row['row_fill_status']}` | `{row['row_fill_exists']}` | {row['missing_required_field_count']} | "
            f"{row['placeholder_field_count']} | {row['missing_local_file_count']} | `{row['blockers'] or '-'}` | "
            f"{row['next_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit competitive-floor row_fill.csv completion state.")
    parser.add_argument("--batch-json", default=DEFAULT_BATCH_JSON)
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
