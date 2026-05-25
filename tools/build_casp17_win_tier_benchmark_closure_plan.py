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

DEFAULT_THRESHOLD_JSON = "runs/casp17_win_tier_threshold_packet_current.json"
DEFAULT_HISTORICAL_WORKORDER_JSON = "runs/casp17_historical_input_workorder_packet_current.json"
DEFAULT_SIDECHAIN_NATIVE_JSON = "runs/casp17_sidechain_native_benchmark_packet_current.json"
DEFAULT_HISTORICAL_BENCHMARK_JSON = "runs/casp17_historical_benchmark_packet_current.json"
DEFAULT_REFINEMENT_ABLATION_JSON = "runs/casp17_refinement_ablation_packet_current.json"
DEFAULT_MODEL_SELECTION_CALIBRATION_JSON = "runs/casp17_model_selection_calibration_packet_current.json"
DEFAULT_OUT_JSON = "runs/casp17_win_tier_benchmark_closure_plan_current.json"
DEFAULT_OUT_CSV = "runs/casp17_win_tier_benchmark_closure_plan_current.csv"
DEFAULT_OUT_MD = "runs/casp17_win_tier_benchmark_closure_plan_current.md"
DEFAULT_OUT_TEMPLATE_CSV = "runs/casp17_win_tier_benchmark_operator_template_current.csv"

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

CORE_TEMPLATE_COLUMNS = [
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

CALIBRATION_COLUMNS = [
    "selected_model_rank",
    "best_model_rank",
    "selected_native_metric",
    "best_native_metric",
    "selected_score",
    "best_score",
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
        fieldnames = ["track", "status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _thresholds(threshold_payload: dict[str, Any]) -> dict[str, dict[str, float]]:
    thresholds = _summary(threshold_payload).get("thresholds")
    if isinstance(thresholds, dict):
        return {
            str(name): {
                "competitive": _float(values.get("competitive")) if isinstance(values, dict) else 0.0,
                "win": _float(values.get("win")) if isinstance(values, dict) else 0.0,
            }
            for name, values in thresholds.items()
        }
    return {}


def _ceil_threshold(thresholds: dict[str, dict[str, float]], metric: str, level: str) -> int:
    return int(math.ceil(_float(thresholds.get(metric, {}).get(level))))


def _template_row(scope: str, index: int) -> dict[str, str]:
    label = "MONOMER" if scope == "monomer" else "COMPLEX"
    target = f"REQUIRED_{label}_{index:03d}"
    row = {
        "benchmark_id": f"hist_{target}",
        "target_id": target,
        "scope": scope,
        "split": "historical",
        "prediction_pdb": f"runs/casp17_historical_benchmark_predictions_current/{target}_prediction.pdb",
        "native_pdb": f"runs/casp17_historical_benchmark_natives_current/{target}_native.pdb",
        "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
        "prediction_method": "REQUIRED_INTERNAL_METHOD",
        "prediction_created_at": "YYYY-MM-DD",
        "native_release_date": "YYYY-MM-DD",
        "prediction_generated_before_native_release": "REQUIRED_TRUE_CONFIRMATION",
        "public_template_or_native_used_for_prediction": "REQUIRED_FALSE_CONFIRMATION",
        "other_team_model_used": "REQUIRED_FALSE_CONFIRMATION",
        "post_release_information_used": "REQUIRED_FALSE_CONFIRMATION",
        "current_casp17_target": "REQUIRED_FALSE_CONFIRMATION",
        "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
        "selected_model_rank": "REQUIRED_1_TO_5",
        "best_model_rank": "REQUIRED_1_TO_5",
        "selected_native_metric": "REQUIRED_NATIVE_METRIC",
        "best_native_metric": "REQUIRED_ORACLE_METRIC",
        "selected_score": "REQUIRED_INTERNAL_SCORE",
        "best_score": "REQUIRED_ORACLE_SCORE",
    }
    for layer in ABLATION_LAYER_NAMES:
        row[f"{layer}_prediction_pdb"] = f"runs/casp17_historical_ablation_predictions_current/{layer}/{target}TS.pdb"
    return row


def _write_template_csv(path_like: str | Path, monomer_rows: int, complex_rows: int) -> str:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = CORE_TEMPLATE_COLUMNS + [f"{layer}_prediction_pdb" for layer in ABLATION_LAYER_NAMES] + CALIBRATION_COLUMNS
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for index in range(1, monomer_rows + 1):
            writer.writerow(_template_row("monomer", index))
        for index in range(1, complex_rows + 1):
            writer.writerow(_template_row("complex", index))
    return _artifact(path)


def _track_row(
    *,
    priority: int,
    track: str,
    current_count: int,
    competitive_required: int,
    win_required: int,
    evidence_status: str,
    blocker: str,
    next_action: str,
    extra_missing_files: int = 0,
) -> dict[str, Any]:
    competitive_missing = max(0, competitive_required - current_count)
    win_missing = max(0, win_required - current_count)
    return {
        "priority": priority,
        "track": track,
        "evidence_status": evidence_status or "missing",
        "current_count": current_count,
        "competitive_required_count": competitive_required,
        "competitive_missing_count": competitive_missing,
        "win_required_count": win_required,
        "win_missing_count": win_missing,
        "extra_missing_file_count": extra_missing_files,
        "closure_status": "pass" if win_missing == 0 and not blocker else "blocked_input",
        "blocker": blocker,
        "next_action": next_action,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    threshold_payload = _read_json(args.threshold_json)
    thresholds = _thresholds(threshold_payload)
    workorder = _summary(_read_json(args.historical_workorder_json))
    sidechain_native = _summary(_read_json(args.sidechain_native_json))
    historical = _summary(_read_json(args.historical_benchmark_json))
    ablation = _summary(_read_json(args.refinement_ablation_json))
    calibration = _summary(_read_json(args.model_selection_calibration_json))

    competitive_monomer = _ceil_threshold(thresholds, "historical_monomer_rows", "competitive")
    win_monomer = _ceil_threshold(thresholds, "historical_monomer_rows", "win")
    competitive_complex = _ceil_threshold(thresholds, "historical_complex_rows", "competitive")
    win_complex = _ceil_threshold(thresholds, "historical_complex_rows", "win")
    competitive_total = competitive_monomer + competitive_complex
    win_total = win_monomer + win_complex
    layer_count = len(ABLATION_LAYER_NAMES)

    current_monomer = _int(historical.get("monomer_benchmark_count"))
    current_complex = _int(historical.get("complex_benchmark_count"))
    current_total = current_monomer + current_complex
    sidechain_rows = _int(sidechain_native.get("benchmark_count"))
    ablation_groups = _int(ablation.get("ablation_group_count"))
    calibration_rows = _int(calibration.get("calibration_row_count"))

    missing_win_monomer = max(0, win_monomer - current_monomer)
    missing_win_complex = max(0, win_complex - current_complex)
    missing_win_total = missing_win_monomer + missing_win_complex
    template_csv = _write_template_csv(args.out_template_csv, missing_win_monomer, missing_win_complex)

    rows = [
        _track_row(
            priority=1,
            track="historical_monomer_native_accuracy",
            current_count=current_monomer,
            competitive_required=competitive_monomer,
            win_required=win_monomer,
            evidence_status=str(historical.get("historical_benchmark_status", "missing")),
            blocker="historical_monomer_rows_missing" if current_monomer < win_monomer else "",
            next_action="Add no-leak monomer historical prediction/native rows and pass sequence/chain/residue exactness.",
            extra_missing_files=max(0, win_monomer - current_monomer) * 2,
        ),
        _track_row(
            priority=2,
            track="historical_complex_interface_accuracy",
            current_count=current_complex,
            competitive_required=competitive_complex,
            win_required=win_complex,
            evidence_status=str(historical.get("historical_benchmark_status", "missing")),
            blocker="historical_complex_rows_missing" if current_complex < win_complex else "",
            next_action="Add no-leak complex historical prediction/native rows with stoichiometry, chains, and interface contacts.",
            extra_missing_files=max(0, win_complex - current_complex) * 2,
        ),
        _track_row(
            priority=3,
            track="sidechain_native_quality",
            current_count=sidechain_rows,
            competitive_required=competitive_total,
            win_required=win_total,
            evidence_status=str(sidechain_native.get("sidechain_native_benchmark_status", "missing")),
            blocker="sidechain_native_benchmark_missing_or_blocked" if sidechain_rows < win_total else "",
            next_action="Run sidechain-native benchmark on the same no-leak historical rows and satisfy lDDT/RMSD thresholds.",
            extra_missing_files=max(0, win_total - sidechain_rows) * 2,
        ),
        _track_row(
            priority=4,
            track="refinement_ablation_native_evidence",
            current_count=ablation_groups,
            competitive_required=competitive_total,
            win_required=win_total,
            evidence_status=str(ablation.get("refinement_ablation_status", "missing")),
            blocker="refinement_ablation_missing_or_blocked" if ablation_groups < win_total else "",
            next_action="Populate per-layer historical predictions and prove the final layer is no-worse/improved.",
            extra_missing_files=max(0, win_total - ablation_groups) * layer_count,
        ),
        _track_row(
            priority=5,
            track="model_selection_calibration",
            current_count=calibration_rows,
            competitive_required=competitive_total,
            win_required=win_total,
            evidence_status=str(calibration.get("calibration_status", "missing")),
            blocker="model_selection_calibration_missing_or_blocked" if calibration_rows < win_total else "",
            next_action="Fill selected-vs-oracle top-5 calibration rows and reduce MODEL 1 selection loss.",
            extra_missing_files=0,
        ),
    ]

    blocked_rows = [row for row in rows if row["closure_status"] != "pass"]
    summary = {
        "packet_type": "casp17_win_tier_benchmark_closure_plan",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "closure_plan_status": "ready",
        "benchmark_evidence_status": "pass" if not blocked_rows else "blocked_input",
        "threshold_json": _artifact(args.threshold_json),
        "historical_workorder_json": _artifact(args.historical_workorder_json),
        "sidechain_native_json": _artifact(args.sidechain_native_json),
        "historical_benchmark_json": _artifact(args.historical_benchmark_json),
        "refinement_ablation_json": _artifact(args.refinement_ablation_json),
        "model_selection_calibration_json": _artifact(args.model_selection_calibration_json),
        "competitive_required_monomer_rows": competitive_monomer,
        "competitive_required_complex_rows": competitive_complex,
        "competitive_required_total_rows": competitive_total,
        "win_required_monomer_rows": win_monomer,
        "win_required_complex_rows": win_complex,
        "win_required_total_rows": win_total,
        "current_monomer_rows": current_monomer,
        "current_complex_rows": current_complex,
        "current_total_rows": current_total,
        "missing_win_monomer_rows": missing_win_monomer,
        "missing_win_complex_rows": missing_win_complex,
        "missing_win_total_rows": missing_win_total,
        "required_core_prediction_files_for_win": missing_win_total,
        "required_native_files_for_win": missing_win_total,
        "required_ablation_layer_prediction_files_for_win": missing_win_total * layer_count,
        "required_calibration_rows_for_win": missing_win_total,
        "current_operator_workorder_count": _int(workorder.get("workorder_count")),
        "current_operator_missing_core_file_count": _int(workorder.get("missing_core_file_count")),
        "current_operator_missing_ablation_layer_count": _int(
            workorder.get("missing_ablation_layer_count") or workorder.get("missing_ablation_layer_file_count")
        ),
        "operator_template_csv": template_csv,
        "operator_template_row_count": missing_win_total,
        "operator_template_layer_count": layer_count,
        "first_blocked_track": str(blocked_rows[0]["track"] if blocked_rows else ""),
        "first_blocker": str(blocked_rows[0]["blocker"] if blocked_rows else ""),
        "claim_boundary": (
            "Local planning packet only. It expands the no-leak historical/native evidence needed for competitive and win-tier claims; "
            "it does not fetch native structures, clear provenance, score accuracy, use external predictors, or submit to CASP."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Win Tier Benchmark Closure Plan",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- closure_plan_status: `{summary['closure_plan_status']}`",
        f"- benchmark_evidence_status: `{summary['benchmark_evidence_status']}`",
        f"- competitive rows monomer/complex/total: `{summary['competitive_required_monomer_rows']}/{summary['competitive_required_complex_rows']}/{summary['competitive_required_total_rows']}`",
        f"- win rows monomer/complex/total: `{summary['win_required_monomer_rows']}/{summary['win_required_complex_rows']}/{summary['win_required_total_rows']}`",
        f"- current rows monomer/complex/total: `{summary['current_monomer_rows']}/{summary['current_complex_rows']}/{summary['current_total_rows']}`",
        f"- missing win rows monomer/complex/total: `{summary['missing_win_monomer_rows']}/{summary['missing_win_complex_rows']}/{summary['missing_win_total_rows']}`",
        f"- required core prediction/native files for win: `{summary['required_core_prediction_files_for_win']}/{summary['required_native_files_for_win']}`",
        f"- required ablation layer prediction files for win: `{summary['required_ablation_layer_prediction_files_for_win']}`",
        f"- required calibration rows for win: `{summary['required_calibration_rows_for_win']}`",
        f"- operator_template_csv: `{summary['operator_template_csv']}`",
        f"- first_blocked_track: `{summary['first_blocked_track'] or '-'}`",
        f"- first_blocker: `{summary['first_blocker'] or '-'}`",
        "",
        "## Tracks",
        "",
        "| priority | track | status | current | competitive required | competitive missing | win required | win missing | extra files | blocker |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority']} | `{row['track']}` | `{row['closure_status']}` | {row['current_count']} | "
            f"{row['competitive_required_count']} | {row['competitive_missing_count']} | "
            f"{row['win_required_count']} | {row['win_missing_count']} | {row['extra_missing_file_count']} | "
            f"`{row['blocker'] or '-'}` |"
        )
    lines.extend(
        [
            "",
            "## Operator Use",
            "",
            "1. Replace `REQUIRED_*` placeholders in the operator template with cleared non-current historical targets.",
            "2. Generate prediction PDBs only with the internal physics lane, before native release where applicable.",
            "3. Add local historical native PDBs only when provenance confirms no current-target or post-release leakage.",
            "4. Fill every ablation-layer PDB path before claiming final-layer no-worse/improvement evidence.",
            "5. Fill selected-vs-oracle top-5 calibration metrics after native scoring on cleared historical rows.",
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
    parser = argparse.ArgumentParser(description="Build a no-leak historical benchmark closure plan for CASP17 win-tier evidence.")
    parser.add_argument("--threshold-json", default=DEFAULT_THRESHOLD_JSON)
    parser.add_argument("--historical-workorder-json", default=DEFAULT_HISTORICAL_WORKORDER_JSON)
    parser.add_argument("--sidechain-native-json", default=DEFAULT_SIDECHAIN_NATIVE_JSON)
    parser.add_argument("--historical-benchmark-json", default=DEFAULT_HISTORICAL_BENCHMARK_JSON)
    parser.add_argument("--refinement-ablation-json", default=DEFAULT_REFINEMENT_ABLATION_JSON)
    parser.add_argument("--model-selection-calibration-json", default=DEFAULT_MODEL_SELECTION_CALIBRATION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-template-csv", default=DEFAULT_OUT_TEMPLATE_CSV)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
