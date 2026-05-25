#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_IDENTITY_CANDIDATE_JSON = "casp17/casp17_competitive_floor_identity_candidate_packet_current.json"
DEFAULT_OPERATOR_PREFLIGHT_CSV = "runs/casp17_win_tier_benchmark_operator_preflight_current.csv"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_identity_source_repair_plan_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_identity_source_repair_plan_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_IDENTITY_SOURCE_REPAIR_PLAN.md"

REPAIR_COLUMNS = [
    "repair_rank",
    "source_rank",
    "benchmark_id",
    "target_id",
    "scope",
    "repair_phase",
    "repair_status",
    "blocking_field_count",
    "blockers",
    "next_action",
]
TARGET_IDENTITY_BLOCKERS = {"placeholder_target_id", "target_id_missing", "current_casp17_target_not_allowed"}
CORE_FILE_BLOCKERS = {"prediction_pdb_not_found", "prediction_pdb_missing", "native_pdb_not_found", "native_pdb_missing"}
PROVENANCE_BLOCKERS = {
    "leakage_clearance_required",
    "prediction_method_required",
    "prediction_created_at_required_iso_date",
    "native_release_date_required_iso_date",
    "prediction_date_not_before_native_release",
    "prediction_generated_before_native_release_required",
    "public_template_or_native_used_for_prediction_must_be_false",
    "other_team_model_used_must_be_false",
    "post_release_information_used_must_be_false",
    "current_casp17_target_must_be_false",
    "operator_clearance_required",
}
ABLATION_BLOCKERS = {"ablation_layer_prediction_pdb_missing"}
CALIBRATION_BLOCKERS = {
    "selected_model_rank_required_1_to_5",
    "best_model_rank_required_1_to_5",
    "selected_native_metric_required_numeric",
    "best_native_metric_required_numeric",
    "selected_native_metric_exceeds_oracle_metric",
    "selected_score_required_numeric",
    "best_score_required_numeric",
}
PHASES = [
    ("target_identity", TARGET_IDENTITY_BLOCKERS),
    ("core_files", CORE_FILE_BLOCKERS),
    ("no_leak_provenance", PROVENANCE_BLOCKERS),
    ("ablation_files", ABLATION_BLOCKERS),
    ("calibration_values", CALIBRATION_BLOCKERS),
]
CLAIM_BOUNDARY = (
    "Local competitive-floor identity source repair plan only. It decomposes blocked historical/operator source "
    "candidate rows into operator repair phases before they can feed identity intake. It does not choose targets, "
    "clear no-leak provenance, fetch native structures, score native accuracy, run predictors, mutate row_fill.csv, "
    "edit operator templates, or submit to CASP."
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
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPAIR_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _split_blockers(value: Any) -> set[str]:
    return {token.strip() for token in _text(value).split(",") if token.strip()}


def _phase_next_action(phase: str) -> str:
    if phase == "target_identity":
        return "replace REQUIRED target/benchmark placeholders with a cleared non-current historical target identity"
    if phase == "core_files":
        return "provide local historical prediction_pdb and native_pdb source files for this target"
    if phase == "no_leak_provenance":
        return "fill no-leak provenance, dates, method, and true/false leakage confirmations"
    if phase == "ablation_files":
        return "provide all required local ablation-layer prediction PDBs after the target identity is cleared"
    if phase == "calibration_values":
        return "enter selected/best ranks, native metrics, and internal scores from cleared historical evidence"
    return "review this blocked source candidate"


def _repair_status(phase: str, blockers: set[str]) -> str:
    if not blockers:
        return "pass"
    if phase == "target_identity":
        return "awaiting_target_identity"
    if phase == "core_files":
        return "awaiting_core_files"
    if phase == "no_leak_provenance":
        return "awaiting_no_leak_provenance"
    if phase == "ablation_files":
        return "awaiting_ablation_files"
    if phase == "calibration_values":
        return "awaiting_calibration_values"
    return "awaiting_repair"


def _repair_rows(preflight_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    repair_rank = 0
    for source_rank, row in enumerate(preflight_rows, start=1):
        blockers = _split_blockers(row.get("blockers"))
        for phase, phase_blockers in PHASES:
            active = sorted(blockers & phase_blockers)
            if not active:
                continue
            repair_rank += 1
            rows.append(
                {
                    "repair_rank": repair_rank,
                    "source_rank": source_rank,
                    "benchmark_id": _text(row.get("benchmark_id")),
                    "target_id": _text(row.get("target_id")).upper(),
                    "scope": _text(row.get("scope")).lower(),
                    "repair_phase": phase,
                    "repair_status": _repair_status(phase, set(active)),
                    "blocking_field_count": len(active),
                    "blockers": ",".join(active),
                    "next_action": _phase_next_action(phase),
                }
            )
    return rows


def _plan_status(rows: list[dict[str, Any]], preflight_blockers: list[str]) -> str:
    if preflight_blockers:
        return "blocked_missing_preflight"
    if not rows:
        return "ready_for_identity_candidates"
    statuses = {_text(row.get("repair_status")) for row in rows}
    for status in [
        "awaiting_target_identity",
        "awaiting_core_files",
        "awaiting_no_leak_provenance",
        "awaiting_ablation_files",
        "awaiting_calibration_values",
    ]:
        if status in statuses:
            return status
    return "awaiting_repair"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    candidate_summary = _summary(_read_json(args.identity_candidate_json))
    preflight_rows, preflight_blockers = _read_csv(args.operator_preflight_csv)
    rows = _repair_rows(preflight_rows)
    by_status = Counter(_text(row.get("repair_status")) for row in rows)
    by_phase = Counter(_text(row.get("repair_phase")) for row in rows)
    blocked_source_ids = {_text(row.get("benchmark_id")) for row in preflight_rows if _text(row.get("operator_row_status")) != "ready"}
    first_open = next((row for row in rows if _text(row.get("repair_status")) != "pass"), rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_competitive_floor_identity_source_repair_plan",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_repair_status": _plan_status(rows, preflight_blockers),
        "identity_candidate_json": _artifact(args.identity_candidate_json),
        "operator_preflight_csv": _artifact(args.operator_preflight_csv),
        "operator_preflight_blockers": ",".join(preflight_blockers),
        "source_candidate_status": _text(candidate_summary.get("identity_candidate_status")),
        "source_candidate_count": _int(candidate_summary.get("source_candidate_count")),
        "source_ready_candidate_count": _int(candidate_summary.get("source_ready_candidate_count")),
        "source_blocked_candidate_count": _int(candidate_summary.get("source_blocked_candidate_count")),
        "preflight_row_count": len(preflight_rows),
        "blocked_source_row_count": len(blocked_source_ids),
        "repair_action_count": len(rows),
        "target_identity_action_count": by_phase["target_identity"],
        "core_file_action_count": by_phase["core_files"],
        "provenance_action_count": by_phase["no_leak_provenance"],
        "ablation_action_count": by_phase["ablation_files"],
        "calibration_action_count": by_phase["calibration_values"],
        "awaiting_target_identity_count": by_status["awaiting_target_identity"],
        "awaiting_core_files_count": by_status["awaiting_core_files"],
        "awaiting_no_leak_provenance_count": by_status["awaiting_no_leak_provenance"],
        "awaiting_ablation_files_count": by_status["awaiting_ablation_files"],
        "awaiting_calibration_values_count": by_status["awaiting_calibration_values"],
        "first_open_benchmark_id": _text(first_open.get("benchmark_id")),
        "first_open_target_id": _text(first_open.get("target_id")),
        "first_open_phase": _text(first_open.get("repair_phase")),
        "first_open_status": _text(first_open.get("repair_status")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Identity Source Repair Plan",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- source_repair_status: `{summary['source_repair_status']}`",
        f"- source candidates ready/blocked/total: `{summary['source_ready_candidate_count']}/{summary['source_blocked_candidate_count']}/{summary['source_candidate_count']}`",
        f"- preflight rows blocked/total: `{summary['blocked_source_row_count']}/{summary['preflight_row_count']}`",
        f"- repair actions: `{summary['repair_action_count']}`",
        f"- phase actions identity/core/provenance/ablation/calibration: `{summary['target_identity_action_count']}/{summary['core_file_action_count']}/{summary['provenance_action_count']}/{summary['ablation_action_count']}/{summary['calibration_action_count']}`",
        f"- first open: `{summary['first_open_benchmark_id'] or '-'}` `{summary['first_open_phase'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Repair Rows",
        "",
        "| rank | benchmark | target | scope | phase | status | blockers | next action |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['repair_rank']} | `{row['benchmark_id']}` | `{row['target_id']}` | `{row['scope']}` | "
            f"`{row['repair_phase']}` | `{row['repair_status']}` | `{row['blockers']}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | - | `ready_for_identity_candidates` | - | no repair rows |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 identity source repair plan from blocked candidates.")
    parser.add_argument("--identity-candidate-json", default=DEFAULT_IDENTITY_CANDIDATE_JSON)
    parser.add_argument("--operator-preflight-csv", default=DEFAULT_OPERATOR_PREFLIGHT_CSV)
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
