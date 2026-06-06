#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WIN_RUBRIC_JSON = "runs/casp17_win_readiness_rubric_packet_current.json"
DEFAULT_ACTION_QUEUE_JSON = "runs/casp17_win_tier_action_queue_packet_current.json"
DEFAULT_HISTORICAL_INPUT_WORKORDER_JSON = "runs/casp17_historical_input_workorder_packet_current.json"
DEFAULT_STRUCTURE_IMAGE_QUALITY_JSON = "runs/casp17_structure_image_quality_packet_current.json"
DEFAULT_DATA_BUNDLE_JSON = "casp17/casp17_data_bundle_manifest_current.json"
DEFAULT_WIN_TIER_THRESHOLD_JSON = "runs/casp17_win_tier_threshold_packet_current.json"
DEFAULT_BENCHMARK_CLOSURE_PLAN_JSON = "runs/casp17_win_tier_benchmark_closure_plan_current.json"
DEFAULT_BENCHMARK_OPERATOR_PREFLIGHT_JSON = "runs/casp17_win_tier_benchmark_operator_preflight_current.json"
DEFAULT_BENCHMARK_OPERATOR_IMPORT_JSON = "runs/casp17_win_tier_benchmark_operator_import_packet_current.json"
DEFAULT_OUT_JSON = "runs/casp17_win_gap_closure_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_win_gap_closure_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_win_gap_closure_packet_current.md"

LEVEL_ORDER = [
    ("submission_level_status", "submission_floor"),
    ("review_quality_status", "review_quality"),
    ("competitive_floor_status", "competitive_floor"),
    ("win_tier_level_status", "win_tier"),
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


def _text(value: Any) -> str:
    return str(value or "").strip()


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
        fieldnames = ["priority", "dimension", "closure_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _action_for_dimension(dimension: str, actions: list[dict[str, Any]]) -> dict[str, Any]:
    for row in actions:
        related = _text(row.get("related_dimension"))
        if dimension and dimension in related.split(";"):
            return row
    for row in actions:
        if dimension and dimension in _text(row.get("related_dimension")):
            return row
    return {}


def _level_statuses(win_summary: dict[str, Any]) -> dict[str, str]:
    return {level: _text(win_summary.get(key)) or "missing" for key, level in LEVEL_ORDER}


def _current_proven_level(level_statuses: dict[str, str]) -> str:
    current = "none"
    for _key, level in LEVEL_ORDER:
        if level_statuses.get(level) == "pass":
            current = level
            continue
        break
    return current


def _next_unclosed_level(level_statuses: dict[str, str]) -> str:
    for _key, level in LEVEL_ORDER:
        if level_statuses.get(level) != "pass":
            return level
    return "complete"


def _closure_status(readiness_status: str, action_status: str) -> str:
    if readiness_status == "pass":
        return "closed"
    if action_status.startswith("blocked"):
        return "blocked_input"
    if action_status.startswith("ready"):
        return "ready_to_execute"
    if readiness_status == "partial":
        return "needs_evidence"
    return "blocked_input"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    win_payload = _read_json(args.win_rubric_json)
    action_payload = _read_json(args.action_queue_json)
    workorder = _summary(_read_json(args.historical_input_workorder_json))
    image_quality = _summary(_read_json(args.structure_image_quality_json))
    data_bundle = _summary(_read_json(args.data_bundle_json))
    thresholds = _summary(_read_json(args.win_tier_threshold_json))
    benchmark_plan = _summary(_read_json(args.benchmark_closure_plan_json))
    operator_preflight = _summary(_read_json(args.benchmark_operator_preflight_json))
    operator_import = _summary(_read_json(args.benchmark_operator_import_json))

    win_summary = _summary(win_payload)
    action_summary = _summary(action_payload)
    win_rows = _rows(win_payload)
    action_rows = _rows(action_payload)
    level_statuses = _level_statuses(win_summary)

    rows: list[dict[str, Any]] = []
    for row in sorted(win_rows, key=lambda item: int(item.get("priority") or 999)):
        dimension = _text(row.get("dimension"))
        readiness_status = _text(row.get("status")) or "missing"
        action = {} if readiness_status == "pass" else _action_for_dimension(dimension, action_rows)
        action_status = _text(action.get("status")) or ("pass" if readiness_status == "pass" else "missing_action")
        rows.append(
            {
                "priority": int(row.get("priority") or 999),
                "level": _text(row.get("level")),
                "dimension": dimension,
                "closure_status": _closure_status(readiness_status, action_status),
                "readiness_status": readiness_status,
                "action_id": _text(action.get("action_id")),
                "action_status": action_status,
                "blockers": _text(action.get("blockers")) or ("-" if readiness_status == "pass" else "action_missing"),
                "required_level": _text(row.get("required_level")),
                "current_evidence": _text(row.get("current_evidence")),
                "inputs_needed": _text(action.get("inputs_needed")),
                "command": _text(action.get("command")),
                "done_when": _text(action.get("done_when")),
                "evidence_artifacts": _text(row.get("evidence_artifacts")) or _text(action.get("evidence_artifacts")),
            }
        )

    not_closed = [row for row in rows if row["closure_status"] != "closed"]
    win_rows_not_closed = [row for row in rows if row["level"] == "win_tier" and row["closure_status"] != "closed"]
    blocked_input = [row for row in rows if row["closure_status"] == "blocked_input"]
    first_open = not_closed[0] if not_closed else {}
    first_operator_input = next((row for row in rows if row.get("action_id") == "historical_benchmark_inputs"), first_open)

    summary = {
        "packet_type": "casp17_win_gap_closure_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "closure_status": "pass" if not not_closed else "blocked_input" if blocked_input else "ready_to_execute",
        "current_proven_level": _current_proven_level(level_statuses),
        "next_unclosed_level": _next_unclosed_level(level_statuses),
        "submission_level_status": level_statuses.get("submission_floor", "missing"),
        "review_quality_status": level_statuses.get("review_quality", "missing"),
        "competitive_floor_status": level_statuses.get("competitive_floor", "missing"),
        "win_tier_level_status": level_statuses.get("win_tier", "missing"),
        "target_count": int(win_summary.get("target_count") or action_summary.get("target_count") or 0),
        "requirement_count": len(rows),
        "closed_count": sum(1 for row in rows if row["closure_status"] == "closed"),
        "not_closed_count": len(not_closed),
        "blocked_input_count": len(blocked_input),
        "win_tier_not_closed_count": len(win_rows_not_closed),
        "first_open_dimension": _text(first_open.get("dimension")),
        "first_open_action_id": _text(first_open.get("action_id")),
        "first_open_blockers": _text(first_open.get("blockers")),
        "first_operator_input_dimension": _text(first_operator_input.get("dimension")),
        "first_operator_input_action_id": _text(first_operator_input.get("action_id")),
        "first_operator_input_blockers": _text(first_operator_input.get("blockers")),
        "historical_input_workorder_status": _text(workorder.get("workorder_status")),
        "historical_input_workorder_count": int(workorder.get("workorder_count") or 0),
        "historical_core_workorder_count": int(workorder.get("core_input_workorder_count") or 0),
        "historical_missing_core_file_count": int(workorder.get("missing_core_file_count") or 0),
        "historical_missing_ablation_layer_file_count": int(
            workorder.get("missing_ablation_layer_file_count") or workorder.get("missing_ablation_layer_count") or 0
        ),
        "operator_template_csv": _text(workorder.get("operator_template_csv")),
        "image_quality_status": _text(image_quality.get("image_quality_status")),
        "image_pass_count": int(image_quality.get("pass_count") or 0),
        "image_count": int(image_quality.get("image_count") or 0),
        "presentation_plate_pass_count": int(image_quality.get("presentation_plate_pass_count") or 0),
        "presentation_plate_count": int(image_quality.get("presentation_plate_count") or 0),
        "data_bundle_status": _text(data_bundle.get("bundle_status")),
        "data_bundle_artifact_count": int(data_bundle.get("artifact_count") or 0),
        "threshold_packet_status": _text(thresholds.get("threshold_packet_status")),
        "threshold_count": int(thresholds.get("threshold_count") or 0),
        "threshold_pass_count": int(thresholds.get("pass_count") or 0),
        "threshold_partial_count": int(thresholds.get("partial_count") or 0),
        "threshold_blocked_count": int(thresholds.get("blocked_count") or 0),
        "threshold_first_blocked_dimension": _text(thresholds.get("first_blocked_dimension")),
        "threshold_first_blocked_metric": _text(thresholds.get("first_blocked_metric")),
        "threshold_first_blocked_blocker": _text(thresholds.get("first_blocked_blocker")),
        "benchmark_closure_plan_status": _text(benchmark_plan.get("closure_plan_status")),
        "benchmark_evidence_status": _text(benchmark_plan.get("benchmark_evidence_status")),
        "benchmark_win_required_total_rows": int(benchmark_plan.get("win_required_total_rows") or 0),
        "benchmark_missing_win_total_rows": int(benchmark_plan.get("missing_win_total_rows") or 0),
        "benchmark_required_core_prediction_files_for_win": int(
            benchmark_plan.get("required_core_prediction_files_for_win") or 0
        ),
        "benchmark_required_native_files_for_win": int(benchmark_plan.get("required_native_files_for_win") or 0),
        "benchmark_required_ablation_layer_prediction_files_for_win": int(
            benchmark_plan.get("required_ablation_layer_prediction_files_for_win") or 0
        ),
        "benchmark_required_calibration_rows_for_win": int(benchmark_plan.get("required_calibration_rows_for_win") or 0),
        "benchmark_operator_template_csv": _text(benchmark_plan.get("operator_template_csv")),
        "benchmark_operator_preflight_status": _text(operator_preflight.get("operator_preflight_status")),
        "benchmark_operator_ready_count": int(operator_preflight.get("ready_count") or 0),
        "benchmark_operator_blocked_count": int(operator_preflight.get("blocked_count") or 0),
        "benchmark_operator_missing_prediction_count": int(operator_preflight.get("missing_prediction_count") or 0),
        "benchmark_operator_missing_native_count": int(operator_preflight.get("missing_native_count") or 0),
        "benchmark_operator_missing_ablation_layer_file_count": int(
            operator_preflight.get("missing_ablation_layer_file_count") or 0
        ),
        "benchmark_operator_calibration_blocked_count": int(operator_preflight.get("calibration_blocked_count") or 0),
        "benchmark_operator_threshold_blockers": _text(operator_preflight.get("threshold_blockers")),
        "benchmark_operator_import_status": _text(operator_import.get("import_status")),
        "benchmark_import_historical_manifest_candidate_csv": _text(
            operator_import.get("historical_manifest_candidate_csv")
        ),
        "benchmark_import_historical_manifest_candidate_row_count": int(
            operator_import.get("historical_manifest_candidate_row_count") or 0
        ),
        "benchmark_import_calibration_candidate_csv": _text(
            operator_import.get("model_selection_calibration_candidate_csv")
        ),
        "benchmark_import_calibration_candidate_row_count": int(
            operator_import.get("model_selection_calibration_candidate_row_count") or 0
        ),
        "benchmark_operator_import_blockers": _text(operator_import.get("blockers")),
        "win_rubric_json": _artifact(args.win_rubric_json),
        "action_queue_json": _artifact(args.action_queue_json),
        "historical_input_workorder_json": _artifact(args.historical_input_workorder_json),
        "structure_image_quality_json": _artifact(args.structure_image_quality_json),
        "data_bundle_json": _artifact(args.data_bundle_json),
        "win_tier_threshold_json": _artifact(args.win_tier_threshold_json),
        "benchmark_closure_plan_json": _artifact(args.benchmark_closure_plan_json),
        "benchmark_operator_preflight_json": _artifact(args.benchmark_operator_preflight_json),
        "benchmark_operator_import_json": _artifact(args.benchmark_operator_import_json),
        "claim_boundary": (
            "Internal closure packet only. It converts current local gate evidence into next actions and operational "
            "win-tier targets; it does not fetch natives, prove current-target accuracy, use external predictors, or submit to CASP."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Win Gap Closure Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- closure_status: `{summary['closure_status']}`",
        f"- current_proven_level: `{summary['current_proven_level']}`",
        f"- next_unclosed_level: `{summary['next_unclosed_level']}`",
        f"- submission/review/competitive/win: `{summary['submission_level_status']}/{summary['review_quality_status']}/{summary['competitive_floor_status']}/{summary['win_tier_level_status']}`",
        f"- first_open_dimension: `{summary['first_open_dimension'] or '-'}`",
        f"- first_open_action: `{summary['first_open_action_id'] or '-'}`",
        f"- first_open_blockers: `{summary['first_open_blockers'] or '-'}`",
        f"- first_operator_input_action: `{summary['first_operator_input_action_id'] or '-'}`",
        f"- first_operator_input_blockers: `{summary['first_operator_input_blockers'] or '-'}`",
        f"- historical_workorders: `{summary['historical_input_workorder_count']}`",
        f"- historical_missing_core_files: `{summary['historical_missing_core_file_count']}`",
        f"- historical_missing_ablation_layer_files: `{summary['historical_missing_ablation_layer_file_count']}`",
        f"- image_quality: `{summary['image_quality_status']}` `{summary['image_pass_count']}/{summary['image_count']}`",
        f"- presentation_plates: `{summary['presentation_plate_pass_count']}/{summary['presentation_plate_count']}`",
        f"- data_bundle: `{summary['data_bundle_status']}` artifacts `{summary['data_bundle_artifact_count']}`",
        f"- thresholds: `{summary['threshold_packet_status'] or '-'}` pass/partial/blocked `{summary['threshold_pass_count']}/{summary['threshold_partial_count']}/{summary['threshold_blocked_count']}`",
        f"- first_threshold_gap: `{summary['threshold_first_blocked_dimension'] or '-'}` / `{summary['threshold_first_blocked_metric'] or '-'}`",
        f"- first_threshold_blocker: `{summary['threshold_first_blocked_blocker'] or '-'}`",
        f"- benchmark_closure_plan: `{summary['benchmark_closure_plan_status'] or '-'}` evidence `{summary['benchmark_evidence_status'] or '-'}`",
        f"- benchmark_missing_win_rows: `{summary['benchmark_missing_win_total_rows']}/{summary['benchmark_win_required_total_rows']}`",
        f"- benchmark_required_prediction/native/ablation/calibration: `{summary['benchmark_required_core_prediction_files_for_win']}/{summary['benchmark_required_native_files_for_win']}/{summary['benchmark_required_ablation_layer_prediction_files_for_win']}/{summary['benchmark_required_calibration_rows_for_win']}`",
        f"- benchmark_operator_preflight: `{summary['benchmark_operator_preflight_status'] or '-'}` ready/blocked `{summary['benchmark_operator_ready_count']}/{summary['benchmark_operator_blocked_count']}`",
        f"- benchmark_operator_missing_prediction/native/ablation/calibration: `{summary['benchmark_operator_missing_prediction_count']}/{summary['benchmark_operator_missing_native_count']}/{summary['benchmark_operator_missing_ablation_layer_file_count']}/{summary['benchmark_operator_calibration_blocked_count']}`",
        f"- benchmark_operator_import: `{summary['benchmark_operator_import_status'] or '-'}` historical/calibration rows `{summary['benchmark_import_historical_manifest_candidate_row_count']}/{summary['benchmark_import_calibration_candidate_row_count']}`",
        f"- benchmark_operator_import_blockers: `{summary['benchmark_operator_import_blockers'] or '-'}`",
        "",
        "## Operational Interpretation",
        "",
        "- `submission_floor` means local CASP TS formatting, validation, scoring, and fail-closed submission gates are green.",
        "- `review_quality` means every current target also has human-reviewable molecular images and image-quality smoke.",
        "- `competitive_floor` requires all-atom/sidechain quality plus no-leak sidechain-native evidence, not just internal geometry.",
        "- `win_tier` requires no-leak historical native evidence for monomers, complexes/interfaces, refinement ablation, and model-selection calibration.",
        "",
        "## Closure Rows",
        "",
        "| priority | level | dimension | closure | gate | action | blockers | needed input |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority']} | `{row['level']}` | `{row['dimension']}` | `{row['closure_status']}` | "
            f"`{row['readiness_status']}` | `{row['action_id'] or '-'}` | `{row['blockers'] or '-'}` | "
            f"{row['inputs_needed'] or '-'} |"
        )
    if not payload["rows"]:
        lines.append("| 0 | - | - | `blocked_input` | - | - | missing win rubric | - |")
    lines.extend(
        [
            "",
            "## First Open Command",
            "",
            "```bash",
            next((row["command"] for row in payload["rows"] if row["closure_status"] != "closed" and row["command"]), "# no open command"),
            "```",
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
    parser = argparse.ArgumentParser(description="Build a CASP17 closure packet from submission floor to win-tier evidence gaps.")
    parser.add_argument("--win-rubric-json", default=DEFAULT_WIN_RUBRIC_JSON)
    parser.add_argument("--action-queue-json", default=DEFAULT_ACTION_QUEUE_JSON)
    parser.add_argument("--historical-input-workorder-json", default=DEFAULT_HISTORICAL_INPUT_WORKORDER_JSON)
    parser.add_argument("--structure-image-quality-json", default=DEFAULT_STRUCTURE_IMAGE_QUALITY_JSON)
    parser.add_argument("--data-bundle-json", default=DEFAULT_DATA_BUNDLE_JSON)
    parser.add_argument("--win-tier-threshold-json", default=DEFAULT_WIN_TIER_THRESHOLD_JSON)
    parser.add_argument("--benchmark-closure-plan-json", default=DEFAULT_BENCHMARK_CLOSURE_PLAN_JSON)
    parser.add_argument("--benchmark-operator-preflight-json", default=DEFAULT_BENCHMARK_OPERATOR_PREFLIGHT_JSON)
    parser.add_argument("--benchmark-operator-import-json", default=DEFAULT_BENCHMARK_OPERATOR_IMPORT_JSON)
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
