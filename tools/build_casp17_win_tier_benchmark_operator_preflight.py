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

DEFAULT_OPERATOR_TEMPLATE_CSV = "runs/casp17_win_tier_benchmark_operator_template_current.csv"
DEFAULT_TARGET_WATCHLIST_JSON = "runs/casp17_target_watchlist_current.json"
DEFAULT_OUT_JSON = "runs/casp17_win_tier_benchmark_operator_preflight_current.json"
DEFAULT_OUT_CSV = "runs/casp17_win_tier_benchmark_operator_preflight_current.csv"
DEFAULT_OUT_MD = "runs/casp17_win_tier_benchmark_operator_preflight_current.md"

REQUIRED_CORE_COLUMNS = [
    "benchmark_id",
    "target_id",
    "scope",
    "split",
    "prediction_pdb",
    "native_pdb",
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

LEAKAGE_CLEAR_VALUES = {"no_leak", "cleared", "true", "yes", "internal_no_leak"}
TRUE_VALUES = {"1", "true", "yes", "y"}
FALSE_VALUES = {"0", "false", "no", "n"}


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


def _date_or_none(value: Any) -> dt.date | None:
    text = _text(value)
    if not text:
        return None
    for candidate in (text[:10], text):
        try:
            return dt.date.fromisoformat(candidate)
        except ValueError:
            continue
    return None


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


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], ["operator_template_csv_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    required = REQUIRED_CORE_COLUMNS + ABLATION_COLUMNS + CALIBRATION_COLUMNS
    missing = [column for column in required if column not in fieldnames]
    blockers = [f"required_columns_missing:{','.join(missing)}"] if missing else []
    if not rows:
        blockers.append("operator_template_csv_empty")
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
        fieldnames = ["benchmark_id", "operator_row_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _current_open_targets(watchlist: dict[str, Any]) -> set[str]:
    rows = watchlist.get("rows")
    if not isinstance(rows, list):
        return set()
    current: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        target_id = _text(row.get("target_id")).upper()
        if target_id and row.get("human_open") is True:
            current.add(target_id)
    return current


def _path_exists(path_text: str) -> bool:
    return bool(path_text and _resolve(path_text).exists())


def _evaluate_calibration(row: dict[str, str]) -> list[str]:
    blockers: list[str] = []
    selected_rank = _int_or_none(row.get("selected_model_rank"))
    best_rank = _int_or_none(row.get("best_model_rank"))
    if selected_rank is None or selected_rank < 1 or selected_rank > 5:
        blockers.append("selected_model_rank_required_1_to_5")
    if best_rank is None or best_rank < 1 or best_rank > 5:
        blockers.append("best_model_rank_required_1_to_5")
    selected_native = _float_or_none(row.get("selected_native_metric"))
    best_native = _float_or_none(row.get("best_native_metric"))
    if selected_native is None:
        blockers.append("selected_native_metric_required_numeric")
    if best_native is None:
        blockers.append("best_native_metric_required_numeric")
    if selected_native is not None and best_native is not None and selected_native > best_native + 1e-9:
        blockers.append("selected_native_metric_exceeds_oracle_metric")
    if _float_or_none(row.get("selected_score")) is None:
        blockers.append("selected_score_required_numeric")
    if _float_or_none(row.get("best_score")) is None:
        blockers.append("best_score_required_numeric")
    return blockers


def _evaluate_row(
    row: dict[str, str],
    *,
    rank: int,
    current_targets: set[str],
    duplicate_benchmark_ids: set[str],
    duplicate_target_ids: set[str],
) -> dict[str, Any]:
    benchmark_id = _text(row.get("benchmark_id"))
    target_id = _text(row.get("target_id")).upper()
    scope = _text(row.get("scope")).lower()
    blockers: list[str] = []

    if not benchmark_id:
        blockers.append("benchmark_id_missing")
    if benchmark_id in duplicate_benchmark_ids:
        blockers.append("duplicate_benchmark_id")
    if not target_id:
        blockers.append("target_id_missing")
    if target_id in duplicate_target_ids:
        blockers.append("duplicate_target_id")
    if target_id.startswith("REQUIRED_"):
        blockers.append("placeholder_target_id")
    if target_id in current_targets:
        blockers.append("current_casp17_target_not_allowed")
    if scope not in {"monomer", "complex"}:
        blockers.append("scope_not_monomer_or_complex")

    prediction_pdb = _text(row.get("prediction_pdb"))
    native_pdb = _text(row.get("native_pdb"))
    if not prediction_pdb:
        blockers.append("prediction_pdb_missing")
    elif not _path_exists(prediction_pdb):
        blockers.append("prediction_pdb_not_found")
    if not native_pdb:
        blockers.append("native_pdb_missing")
    elif not _path_exists(native_pdb):
        blockers.append("native_pdb_not_found")

    if _text(row.get("leakage_clearance")).lower() not in LEAKAGE_CLEAR_VALUES:
        blockers.append("leakage_clearance_required")
    if not _text(row.get("prediction_method")):
        blockers.append("prediction_method_required")
    prediction_created_at = _date_or_none(row.get("prediction_created_at"))
    native_release_date = _date_or_none(row.get("native_release_date"))
    if prediction_created_at is None:
        blockers.append("prediction_created_at_required_iso_date")
    if native_release_date is None:
        blockers.append("native_release_date_required_iso_date")
    if prediction_created_at is not None and native_release_date is not None and prediction_created_at >= native_release_date:
        blockers.append("prediction_date_not_before_native_release")
    if _text(row.get("prediction_generated_before_native_release")).lower() not in TRUE_VALUES:
        blockers.append("prediction_generated_before_native_release_required")
    for column in [
        "public_template_or_native_used_for_prediction",
        "other_team_model_used",
        "post_release_information_used",
        "current_casp17_target",
    ]:
        if _text(row.get(column)).lower() not in FALSE_VALUES:
            blockers.append(f"{column}_must_be_false")
    if _text(row.get("operator_clearance")).lower() not in LEAKAGE_CLEAR_VALUES:
        blockers.append("operator_clearance_required")

    missing_layers: list[str] = []
    for column in ABLATION_COLUMNS:
        path_text = _text(row.get(column))
        if not path_text:
            missing_layers.append(column.replace("_prediction_pdb", ""))
        elif not _path_exists(path_text):
            missing_layers.append(column.replace("_prediction_pdb", ""))

    calibration_blockers = _evaluate_calibration(row)
    blockers.extend(calibration_blockers)

    core_blockers = [
        blocker
        for blocker in blockers
        if blocker
        not in set(calibration_blockers)
        and not blocker.endswith("_layer_prediction_pdb_missing")
    ]
    core_ready = not core_blockers and bool(prediction_pdb and native_pdb)
    ablation_ready = core_ready and not missing_layers
    calibration_ready = core_ready and not calibration_blockers
    operator_ready = core_ready and ablation_ready and calibration_ready
    return {
        "row_rank": rank,
        "benchmark_id": benchmark_id,
        "target_id": target_id,
        "scope": scope,
        "operator_row_status": "ready" if operator_ready else "blocked",
        "core_ready": bool(core_ready),
        "ablation_ready": bool(ablation_ready),
        "calibration_ready": bool(calibration_ready),
        "prediction_pdb_exists": _path_exists(prediction_pdb),
        "native_pdb_exists": _path_exists(native_pdb),
        "ablation_layer_present_count": len(ABLATION_COLUMNS) - len(missing_layers),
        "ablation_layer_required_count": len(ABLATION_COLUMNS),
        "missing_ablation_layers": ",".join(missing_layers),
        "calibration_blockers": ",".join(sorted(set(calibration_blockers))),
        "blockers": ",".join(sorted(set(blockers + (["ablation_layer_prediction_pdb_missing"] if missing_layers else [])))),
    }


def _duplicate_values(rows: list[dict[str, str]], column: str) -> set[str]:
    seen: set[str] = set()
    duplicate: set[str] = set()
    for row in rows:
        value = _text(row.get(column)).upper() if column == "target_id" else _text(row.get(column))
        if not value:
            continue
        if value in seen:
            duplicate.add(value)
        seen.add(value)
    return duplicate


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    source_rows, source_blockers = _read_csv(args.operator_template_csv)
    current_targets = _current_open_targets(_read_json(args.target_watchlist_json))
    duplicate_benchmark_ids = _duplicate_values(source_rows, "benchmark_id")
    duplicate_target_ids = _duplicate_values(source_rows, "target_id")
    rows = [
        _evaluate_row(
            row,
            rank=index,
            current_targets=current_targets,
            duplicate_benchmark_ids=duplicate_benchmark_ids,
            duplicate_target_ids=duplicate_target_ids,
        )
        for index, row in enumerate(source_rows, start=1)
    ]
    ready_rows = [row for row in rows if row["operator_row_status"] == "ready"]
    monomer_ready = sum(1 for row in ready_rows if row["scope"] == "monomer")
    complex_ready = sum(1 for row in ready_rows if row["scope"] == "complex")
    threshold_blockers: list[str] = []
    if len(ready_rows) < args.min_ready_total:
        threshold_blockers.append("ready_total_below_threshold")
    if monomer_ready < args.min_ready_monomer:
        threshold_blockers.append("ready_monomer_below_threshold")
    if complex_ready < args.min_ready_complex:
        threshold_blockers.append("ready_complex_below_threshold")
    blocked_rows = [row for row in rows if row["operator_row_status"] != "ready"]
    first_blocked = blocked_rows[0] if blocked_rows else {}
    summary = {
        "packet_type": "casp17_win_tier_benchmark_operator_preflight",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "operator_preflight_status": "pass" if rows and not source_blockers and not blocked_rows and not threshold_blockers else "blocked",
        "operator_template_csv": _artifact(args.operator_template_csv),
        "target_watchlist_json": _artifact(args.target_watchlist_json),
        "row_count": len(rows),
        "ready_count": len(ready_rows),
        "blocked_count": len(blocked_rows),
        "ready_monomer_count": monomer_ready,
        "ready_complex_count": complex_ready,
        "min_ready_total": int(args.min_ready_total),
        "min_ready_monomer": int(args.min_ready_monomer),
        "min_ready_complex": int(args.min_ready_complex),
        "missing_prediction_count": sum(1 for row in rows if not row["prediction_pdb_exists"]),
        "missing_native_count": sum(1 for row in rows if not row["native_pdb_exists"]),
        "missing_ablation_layer_file_count": sum(
            len([layer for layer in row["missing_ablation_layers"].split(",") if layer]) for row in rows
        ),
        "calibration_blocked_count": sum(1 for row in rows if row["calibration_blockers"]),
        "provenance_or_core_blocked_count": sum(
            1
            for row in rows
            if any(
                token in row["blockers"]
                for token in [
                    "placeholder_target_id",
                    "leakage_clearance_required",
                    "prediction_method_required",
                    "prediction_created_at_required_iso_date",
                    "native_release_date_required_iso_date",
                    "operator_clearance_required",
                    "current_casp17_target_not_allowed",
                ]
            )
        ),
        "duplicate_benchmark_id_count": len(duplicate_benchmark_ids),
        "duplicate_target_id_count": len(duplicate_target_ids),
        "source_blockers": ",".join(source_blockers),
        "threshold_blockers": ",".join(threshold_blockers),
        "first_blocked_benchmark_id": str(first_blocked.get("benchmark_id", "")),
        "first_blocked_blockers": str(first_blocked.get("blockers", "")),
        "claim_boundary": (
            "Local operator-template preflight only. It checks no-leak historical benchmark intake fields, local files, "
            "ablation paths, and calibration fields; it does not fetch natives, clear provenance, score accuracy, use external predictors, or submit to CASP."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Win Tier Benchmark Operator Preflight",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- operator_preflight_status: `{summary['operator_preflight_status']}`",
        f"- rows ready/blocked: `{summary['ready_count']}/{summary['blocked_count']}`",
        f"- ready monomer/complex: `{summary['ready_monomer_count']}/{summary['ready_complex_count']}`",
        f"- required total/monomer/complex: `{summary['min_ready_total']}/{summary['min_ready_monomer']}/{summary['min_ready_complex']}`",
        f"- missing prediction/native/layer files: `{summary['missing_prediction_count']}/{summary['missing_native_count']}/{summary['missing_ablation_layer_file_count']}`",
        f"- calibration_blocked_count: `{summary['calibration_blocked_count']}`",
        f"- provenance_or_core_blocked_count: `{summary['provenance_or_core_blocked_count']}`",
        f"- threshold_blockers: `{summary['threshold_blockers'] or '-'}`",
        f"- first_blocked: `{summary['first_blocked_benchmark_id'] or '-'}`",
        "",
        "## Rows",
        "",
        "| rank | benchmark | target | scope | status | core | ablation | calibration | layers | blockers |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['row_rank']} | `{row['benchmark_id']}` | `{row['target_id']}` | `{row['scope']}` | "
            f"`{row['operator_row_status']}` | `{row['core_ready']}` | `{row['ablation_ready']}` | "
            f"`{row['calibration_ready']}` | {row['ablation_layer_present_count']}/{row['ablation_layer_required_count']} | "
            f"`{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| 0 | - | - | - | `blocked` | `False` | `False` | `False` | 0/0 | no rows |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight the expanded CASP17 win-tier benchmark operator template.")
    parser.add_argument("--operator-template-csv", default=DEFAULT_OPERATOR_TEMPLATE_CSV)
    parser.add_argument("--target-watchlist-json", default=DEFAULT_TARGET_WATCHLIST_JSON)
    parser.add_argument("--min-ready-total", type=int, default=40)
    parser.add_argument("--min-ready-monomer", type=int, default=25)
    parser.add_argument("--min-ready-complex", type=int, default=15)
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
    if payload["summary"]["operator_preflight_status"] != "pass":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
