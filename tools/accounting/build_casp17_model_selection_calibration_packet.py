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

DEFAULT_SCORE_RECORD_JSON = "runs/casp17_internal_score_record_packet_current.json"
DEFAULT_RANKED_DEPTH_JSON = "runs/casp17_ranked_model_depth_packet_current.json"
DEFAULT_HISTORICAL_BENCHMARK_JSON = "runs/casp17_historical_benchmark_packet_current.json"
DEFAULT_CALIBRATION_CSV = "runs/casp17_model_selection_calibration_current.csv"
DEFAULT_OUT_JSON = "runs/casp17_model_selection_calibration_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_model_selection_calibration_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_model_selection_calibration_packet_current.md"

LEAKAGE_CLEAR_VALUES = {"no_leak", "cleared", "true", "yes", "internal_no_leak"}
REQUIRED_CALIBRATION_COLUMNS = [
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


def _float_or_none(value: Any) -> float | None:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _int_or_none(value: Any) -> int | None:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed


def _read_calibration_rows(path_like: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], ["calibration_csv_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    missing = [column for column in REQUIRED_CALIBRATION_COLUMNS if column not in fieldnames]
    blockers = [f"required_columns_missing:{','.join(missing)}"] if missing else []
    if not rows:
        blockers.append("calibration_csv_empty")
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
        fieldnames = ["calibration_dimension"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _dimension_row(
    dimension: str,
    status: str,
    current_evidence: str,
    requirement: str,
    blockers: list[str],
    next_action: str,
) -> dict[str, Any]:
    return {
        "calibration_dimension": dimension,
        "status": status,
        "current_evidence": current_evidence,
        "requirement": requirement,
        "blockers": ",".join(blockers),
        "next_action": next_action,
    }


def _calibration_row(row: dict[str, str], *, max_selection_loss: float) -> dict[str, Any]:
    benchmark_id = _text(row.get("benchmark_id")) or "unknown"
    scope = _text(row.get("scope")).lower() or "unknown"
    selected_rank = _int_or_none(row.get("selected_model_rank"))
    best_rank = _int_or_none(row.get("best_model_rank"))
    selected_metric = _float_or_none(row.get("selected_native_metric"))
    best_metric = _float_or_none(row.get("best_native_metric"))
    selected_score = _float_or_none(row.get("selected_score"))
    best_score = _float_or_none(row.get("best_score"))
    leakage = _text(row.get("leakage_clearance")).lower()
    blockers: list[str] = []
    if leakage not in LEAKAGE_CLEAR_VALUES:
        blockers.append("leakage_clearance_missing_or_not_clear")
    if scope not in {"monomer", "complex"}:
        blockers.append("scope_not_monomer_or_complex")
    if selected_rank is None or selected_rank < 1 or selected_rank > 5:
        blockers.append("selected_model_rank_invalid")
    if best_rank is None or best_rank < 1 or best_rank > 5:
        blockers.append("best_model_rank_invalid")
    for key, value in {
        "selected_native_metric": selected_metric,
        "best_native_metric": best_metric,
        "selected_score": selected_score,
        "best_score": best_score,
    }.items():
        if value is None:
            blockers.append(f"{key}_missing_or_invalid")
    selection_loss = 0.0
    score_order_agrees = False
    if selected_metric is not None and best_metric is not None:
        selection_loss = max(0.0, best_metric - selected_metric)
        if selection_loss > max_selection_loss:
            blockers.append("selection_loss_above_threshold")
    if selected_score is not None and best_score is not None:
        score_order_agrees = selected_score >= best_score or selected_rank == best_rank
        if not score_order_agrees:
            blockers.append("score_order_disagrees_with_native_best")
    return {
        "benchmark_id": benchmark_id,
        "scope": scope,
        "selected_model_rank": selected_rank or 0,
        "best_model_rank": best_rank or 0,
        "selected_native_metric": round(selected_metric or 0.0, 6),
        "best_native_metric": round(best_metric or 0.0, 6),
        "selection_loss": round(selection_loss, 6),
        "selected_score": round(selected_score or 0.0, 6),
        "best_score": round(best_score or 0.0, 6),
        "score_order_agrees": score_order_agrees,
        "calibration_row_status": "pass" if not blockers else "blocked",
        "blockers": ",".join(sorted(set(blockers))),
    }


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    score_summary = _summary(_read_json(args.score_record_json))
    ranked_summary = _summary(_read_json(args.ranked_depth_json))
    historical_summary = _summary(_read_json(args.historical_benchmark_json))
    raw_calibration_rows, calibration_csv_blockers = _read_calibration_rows(args.calibration_csv)
    calibration_rows = [
        _calibration_row(row, max_selection_loss=float(args.max_selection_loss)) for row in raw_calibration_rows
    ]

    target_count = int(score_summary.get("target_count", ranked_summary.get("target_count", 0)) or 0)
    score_records_pass = (
        score_summary.get("score_record_status") == "pass"
        and int(score_summary.get("score_record_count", -1)) == target_count
        and target_count > 0
    )
    multichain_count = int(score_summary.get("multichain_target_count", 0) or 0)
    qscore_records_pass = int(score_summary.get("qscore_multichain_count", -1)) == multichain_count
    ranked_depth_pass = (
        ranked_summary.get("ranked_depth_status") == "pass"
        and int(ranked_summary.get("pass_count", -1)) == target_count
        and int(ranked_summary.get("candidate_gate_pass_count", 0) or 0) >= target_count * 5
        and target_count > 0
    )
    benchmark_count = int(historical_summary.get("benchmark_count", 0) or 0)
    benchmark_exact_pass = (
        historical_summary.get("historical_benchmark_status") == "pass"
        and benchmark_count > 0
        and int(historical_summary.get("sequence_exact_match_count", -1)) == benchmark_count
        and int(historical_summary.get("chain_exact_match_count", -1)) == benchmark_count
    )
    row_pass_count = sum(1 for row in calibration_rows if row["calibration_row_status"] == "pass")
    monomer_pass_count = sum(
        1 for row in calibration_rows if row["calibration_row_status"] == "pass" and row["scope"] == "monomer"
    )
    complex_pass_count = sum(
        1 for row in calibration_rows if row["calibration_row_status"] == "pass" and row["scope"] == "complex"
    )
    calibration_rows_pass = (
        not calibration_csv_blockers
        and len(calibration_rows) >= int(args.min_calibration_rows)
        and row_pass_count == len(calibration_rows)
        and monomer_pass_count >= int(args.min_monomer_rows)
        and complex_pass_count >= int(args.min_complex_rows)
    )

    losses = [float(row["selection_loss"]) for row in calibration_rows if row["calibration_row_status"] == "pass"]
    exact_top1 = sum(
        1
        for row in calibration_rows
        if row["calibration_row_status"] == "pass" and row["selected_model_rank"] == row["best_model_rank"]
    )
    score_order_agree_count = sum(
        1 for row in calibration_rows if row["calibration_row_status"] == "pass" and row["score_order_agrees"] is True
    )

    rows = [
        _dimension_row(
            "score_record_coverage",
            "pass" if score_records_pass else "blocked",
            f"SCORE records={score_summary.get('score_record_count', 0)}/{target_count}",
            "Every current target has an explicit SCORE record before calibration is attempted.",
            [] if score_records_pass else ["score_record_coverage_incomplete"],
            "Regenerate internal SCORE records for every current target.",
        ),
        _dimension_row(
            "qscore_record_coverage",
            "pass" if qscore_records_pass else "blocked",
            f"QSCORE records={score_summary.get('qscore_multichain_count', 0)}/{multichain_count}",
            "Every current multichain target has explicit interface QSCORE records.",
            [] if qscore_records_pass else ["qscore_record_coverage_incomplete"],
            "Regenerate QSCORE records for multichain targets and inspect interface extraction.",
        ),
        _dimension_row(
            "ranked_candidate_depth",
            "pass" if ranked_depth_pass else "blocked",
            f"ranked_depth={ranked_summary.get('pass_count', 0)}/{target_count}; candidate gates={ranked_summary.get('candidate_gate_pass_count', 0)}/{ranked_summary.get('candidate_gate_total_count', 0)}",
            "Every current target has five gated ranked candidates, enabling top-1 versus best-of-5 calibration.",
            [] if ranked_depth_pass else ["ranked_candidate_depth_incomplete"],
            "Regenerate ranked top-5 candidates and candidate gates for every current target.",
        ),
        _dimension_row(
            "historical_native_benchmark_exactness",
            "pass" if benchmark_exact_pass else "blocked",
            f"historical_status={historical_summary.get('historical_benchmark_status', 'missing')}; benchmarks={benchmark_count}; sequence_exact={historical_summary.get('sequence_exact_match_count', 0)}/{benchmark_count}; chain_exact={historical_summary.get('chain_exact_match_count', 0)}/{benchmark_count}",
            "No-leak historical benchmark rows are chain/residue exact and native-scored before calibration is trusted.",
            [] if benchmark_exact_pass else ["historical_native_benchmark_exactness_missing"],
            "Populate the no-leak historical benchmark manifest with chain/residue-exact local prediction/native pairs.",
        ),
        _dimension_row(
            "calibration_rows",
            "pass" if calibration_rows_pass else "blocked",
            f"calibration rows pass={row_pass_count}/{len(calibration_rows)}; monomer={monomer_pass_count}; complex={complex_pass_count}; csv_blockers={','.join(calibration_csv_blockers) or '-'}",
            "A no-leak calibration CSV records selected-vs-oracle model ranks, native metrics, and SCORE ordering.",
            []
            if calibration_rows_pass
            else [*calibration_csv_blockers, "calibration_rows_below_threshold_or_blocked"],
            "Generate the calibration CSV from historical top-5 predictions after the benchmark manifest is ready.",
        ),
    ]
    calibration_status = (
        "pass"
        if score_records_pass and qscore_records_pass and ranked_depth_pass and benchmark_exact_pass and calibration_rows_pass
        else "blocked"
    )
    summary = {
        "packet_type": "casp17_model_selection_calibration_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "score_record_json": _artifact(args.score_record_json),
        "ranked_depth_json": _artifact(args.ranked_depth_json),
        "historical_benchmark_json": _artifact(args.historical_benchmark_json),
        "calibration_csv": _artifact(args.calibration_csv),
        "target_count": target_count,
        "score_record_coverage_status": "pass" if score_records_pass else "blocked",
        "qscore_record_coverage_status": "pass" if qscore_records_pass else "blocked",
        "ranked_candidate_depth_status": "pass" if ranked_depth_pass else "blocked",
        "historical_exactness_status": "pass" if benchmark_exact_pass else "blocked",
        "calibration_rows_status": "pass" if calibration_rows_pass else "blocked",
        "calibration_status": calibration_status,
        "calibration_row_count": len(calibration_rows),
        "calibration_pass_count": row_pass_count,
        "monomer_calibration_pass_count": monomer_pass_count,
        "complex_calibration_pass_count": complex_pass_count,
        "top1_selected_best_count": exact_top1,
        "score_order_agree_count": score_order_agree_count,
        "mean_selection_loss": _mean(losses),
        "max_selection_loss": max(losses) if losses else 0.0,
        "thresholds": {
            "min_calibration_rows": int(args.min_calibration_rows),
            "min_monomer_rows": int(args.min_monomer_rows),
            "min_complex_rows": int(args.min_complex_rows),
            "max_selection_loss": float(args.max_selection_loss),
        },
        "claim_boundary": "Internal model-selection calibration readiness only; not official CASP accuracy evidence, not current-target native evidence, and not portal submission.",
    }
    return {"summary": summary, "rows": rows, "calibration_rows": calibration_rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Model Selection Calibration Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- calibration_status: `{summary['calibration_status']}`",
        f"- target_count: `{summary['target_count']}`",
        f"- score/qscore/ranked/historical/calibration: `{summary['score_record_coverage_status']}/{summary['qscore_record_coverage_status']}/{summary['ranked_candidate_depth_status']}/{summary['historical_exactness_status']}/{summary['calibration_rows_status']}`",
        f"- calibration rows pass/count: `{summary['calibration_pass_count']}/{summary['calibration_row_count']}`",
        f"- top1 selected best: `{summary['top1_selected_best_count']}`",
        f"- score-order agree: `{summary['score_order_agree_count']}`",
        f"- mean/max selection loss: `{summary['mean_selection_loss']}/{summary['max_selection_loss']}`",
        "",
        "## Dimensions",
        "",
        "| dimension | status | evidence | blockers | next action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['calibration_dimension']}` | `{row['status']}` | {row['current_evidence']} | {row['blockers'] or '-'} | {row['next_action']} |"
        )
    lines.extend(
        [
            "",
            "## Calibration CSV Contract",
            "",
            "`" + ",".join(REQUIRED_CALIBRATION_COLUMNS) + "`",
            "",
            "Rows must be no-leak historical rows. `selected_native_metric` and `best_native_metric` should use the same native proxy metric within each scope, such as TM/GDT/lDDT for monomers or interface/DockQ-like proxy for complexes.",
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
    parser = argparse.ArgumentParser(description="Build a fail-closed CASP17 SCORE/QSCORE/model-selection calibration packet.")
    parser.add_argument("--score-record-json", default=DEFAULT_SCORE_RECORD_JSON)
    parser.add_argument("--ranked-depth-json", default=DEFAULT_RANKED_DEPTH_JSON)
    parser.add_argument("--historical-benchmark-json", default=DEFAULT_HISTORICAL_BENCHMARK_JSON)
    parser.add_argument("--calibration-csv", default=DEFAULT_CALIBRATION_CSV)
    parser.add_argument("--min-calibration-rows", type=int, default=2)
    parser.add_argument("--min-monomer-rows", type=int, default=1)
    parser.add_argument("--min-complex-rows", type=int, default=1)
    parser.add_argument("--max-selection-loss", type=float, default=0.03)
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
