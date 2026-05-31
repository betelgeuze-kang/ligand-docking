#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_LANE_DECISION_JSON = "casp17/casp17_historical_seed_lane_decision_packet_current.json"
DEFAULT_BENCHMARK_SCAFFOLD_CSV = "runs/casp17_win_tier_benchmark_input_scaffold_current.csv"
DEFAULT_QUEUE_DIR = "casp17/historical_seed_strict_blind_replacement_queue"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_queue_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_strict_blind_replacement_queue_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_QUEUE.md"

REQUIREMENT_FIELDS = [
    "replacement_target_id",
    "replacement_benchmark_id",
    "target_identity_non_current_historical",
    "prediction_pdb",
    "native_pdb",
    "native_authority_ref",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "no_leak_evidence_ref",
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
    "ablation_manifest_ref",
    "calibration_values_ref",
    "operator_clearance",
]

ROW_COLUMNS = [
    "queue_rank",
    "scaffold_row_rank",
    "required_benchmark_id",
    "required_target_id",
    "scope",
    "metric_profile",
    "replacement_queue_status",
    "strict_blind_replacement_required",
    "current_seed_competitive_allowed_count",
    "current_seed_retrospective_count",
    "current_seed_authority_required_count",
    "requirement_field_count",
    "replacement_folder",
    "requirements_csv",
    "next_action",
    "blockers",
]

FIELD_COLUMNS = [
    "required_benchmark_id",
    "required_target_id",
    "scope",
    "metric_profile",
    "field_name",
    "required_policy",
    "operator_value",
    "evidence_ref",
    "operator_clearance",
    "notes",
]

CLAIM_BOUNDARY = (
    "Local CASP17 historical strict-blind replacement queue only. It expands the post-native/authority-blocked "
    "seed lane decision into per-benchmark replacement requirements for the 40-row win-tier scaffold. It does "
    "not select replacement targets, clear no-leak provenance, mutate benchmark/operator CSVs, fetch structures, "
    "compute official CASP metrics, or submit to CASP."
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
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"true", "1", "yes", "y"}


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


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


def _safe_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_") or "unknown"


def _requirement_rows(scaffold_row: dict[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for field in REQUIREMENT_FIELDS:
        if field in {
            "prediction_generated_before_native_release",
            "target_identity_non_current_historical",
        }:
            policy = "operator_confirmed_true"
        elif field in {
            "public_template_or_native_used_for_prediction",
            "other_team_model_used",
            "post_release_information_used",
        }:
            policy = "operator_confirmed_false"
        elif field in {"prediction_created_at", "native_release_date"}:
            policy = "authoritative_iso_date"
        elif field.endswith("_pdb"):
            policy = "existing_coordinate_valid_pdb"
        elif field == "operator_clearance":
            policy = "operator_cleared"
        else:
            policy = "operator_supplied_authoritative_evidence"
        rows.append(
            {
                "required_benchmark_id": _text(scaffold_row.get("benchmark_id")),
                "required_target_id": _text(scaffold_row.get("target_id")),
                "scope": _text(scaffold_row.get("scope")),
                "metric_profile": _text(scaffold_row.get("metric_profile")),
                "field_name": field,
                "required_policy": policy,
                "operator_value": "",
                "evidence_ref": "",
                "operator_clearance": "",
                "notes": "required before this scaffold slot can accept a strict-blind historical replacement",
            }
        )
    return rows


def _write_row_md(path: Path, row: dict[str, Any]) -> None:
    lines = [
        f"# {row['required_benchmark_id']} Strict-Blind Replacement",
        "",
        f"- status: `{row['replacement_queue_status']}`",
        f"- required target: `{row['required_target_id']}`",
        f"- scope: `{row['scope']}`",
        f"- metric profile: `{row['metric_profile']}`",
        f"- requirement fields: `{row['requirement_field_count']}`",
        f"- current seed competitive allowed: `{row['current_seed_competitive_allowed_count']}`",
        f"- current seed retrospective only: `{row['current_seed_retrospective_count']}`",
        f"- current seed authority required: `{row['current_seed_authority_required_count']}`",
        f"- requirements csv: `{row['requirements_csv']}`",
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


def _build_queue_row(
    queue_rank: int,
    scaffold_row: dict[str, str],
    queue_dir: str | Path,
    lane_summary: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    benchmark_id = _text(scaffold_row.get("benchmark_id"))
    target_id = _text(scaffold_row.get("target_id"))
    folder = _resolve(queue_dir) / f"{queue_rank:02d}_{_safe_name(benchmark_id or target_id)}"
    requirement_rows = _requirement_rows(scaffold_row)
    requirements_csv = folder / "strict_blind_replacement_requirements.csv"
    _write_csv(requirements_csv, requirement_rows, FIELD_COLUMNS)
    competitive_allowed = _int(lane_summary.get("competitive_proof_allowed_count"))
    retrospective = _int(lane_summary.get("retrospective_calibration_review_count"))
    authority_required = _int(lane_summary.get("authority_or_replacement_required_count"))
    row = {
        "queue_rank": queue_rank,
        "scaffold_row_rank": _int(scaffold_row.get("row_rank")),
        "required_benchmark_id": benchmark_id,
        "required_target_id": target_id,
        "scope": _text(scaffold_row.get("scope")),
        "metric_profile": _text(scaffold_row.get("metric_profile")),
        "replacement_queue_status": "awaiting_strict_blind_replacement",
        "strict_blind_replacement_required": True,
        "current_seed_competitive_allowed_count": competitive_allowed,
        "current_seed_retrospective_count": retrospective,
        "current_seed_authority_required_count": authority_required,
        "requirement_field_count": len(requirement_rows),
        "replacement_folder": _artifact(folder),
        "requirements_csv": _artifact(requirements_csv),
        "next_action": (
            "select a non-current historical target with pre-native internal prediction, authoritative native, "
            "no-leak evidence, ablation layers, calibration values, and operator clearance"
        ),
        "blockers": "strict_blind_replacement_identity_required,core_files_required,no_leak_required,ablation_required,calibration_required",
    }
    _write_row_md(folder / "REPLACEMENT_REQUIREMENTS.md", row)
    return row, requirement_rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    lane_payload = _read_json(args.lane_decision_json)
    lane_summary = _summary(lane_payload)
    scaffold_rows = _read_csv(args.benchmark_scaffold_csv)
    rows: list[dict[str, Any]] = []
    requirement_rows_by_slot: dict[str, list[dict[str, Any]]] = {}
    for index, scaffold_row in enumerate(scaffold_rows, start=1):
        row, requirements = _build_queue_row(index, scaffold_row, args.queue_dir, lane_summary)
        rows.append(row)
        requirement_rows_by_slot[row["required_benchmark_id"]] = requirements
    input_blockers: list[str] = []
    if not _resolve(args.lane_decision_json).exists():
        input_blockers.append("lane_decision_json_missing")
    if not _resolve(args.benchmark_scaffold_csv).exists():
        input_blockers.append("benchmark_scaffold_csv_missing")
    replacement_required = sum(1 for row in rows if _bool(row.get("strict_blind_replacement_required")))
    if input_blockers:
        status = "blocked_missing_input"
    elif not rows:
        status = "blocked_missing_scaffold_rows"
    elif replacement_required:
        status = "strict_blind_replacement_queue_open"
    else:
        status = "strict_blind_replacement_queue_ready"
    first_open = rows[0] if rows else {}
    summary = {
        "packet_type": "casp17_historical_seed_strict_blind_replacement_queue",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "strict_blind_replacement_queue_status": status,
        "lane_decision_json": _artifact(args.lane_decision_json),
        "benchmark_scaffold_csv": _artifact(args.benchmark_scaffold_csv),
        "queue_dir": _artifact(args.queue_dir),
        "scaffold_slot_count": len(rows),
        "monomer_slot_count": sum(1 for row in rows if row.get("scope") == "monomer"),
        "complex_slot_count": sum(1 for row in rows if row.get("scope") == "complex"),
        "strict_blind_replacement_required_count": replacement_required,
        "strict_blind_ready_slot_count": 0,
        "competitive_proof_allowed_slot_count": 0,
        "requirement_field_count": sum(_int(row.get("requirement_field_count")) for row in rows),
        "current_seed_count": _int(lane_summary.get("seed_row_count")),
        "current_seed_strict_blind_count": _int(lane_summary.get("strict_blind_eligible_count")),
        "current_seed_retrospective_count": _int(lane_summary.get("retrospective_calibration_review_count")),
        "current_seed_authority_required_count": _int(lane_summary.get("authority_or_replacement_required_count")),
        "current_seed_competitive_allowed_count": _int(lane_summary.get("competitive_proof_allowed_count")),
        "first_open_benchmark_id": _text(first_open.get("required_benchmark_id")),
        "first_next_action": _text(first_open.get("next_action")) or "provide benchmark scaffold rows",
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows, "requirement_rows_by_slot": requirement_rows_by_slot}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Strict-Blind Replacement Queue",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['strict_blind_replacement_queue_status']}`",
        f"- scaffold slots: `{summary['scaffold_slot_count']}`",
        f"- monomer/complex slots: `{summary['monomer_slot_count']}/{summary['complex_slot_count']}`",
        f"- replacement-required/ready/competitive: `{summary['strict_blind_replacement_required_count']}/{summary['strict_blind_ready_slot_count']}/{summary['competitive_proof_allowed_slot_count']}`",
        f"- current seed strict/retrospective/authority/competitive: `{summary['current_seed_strict_blind_count']}/{summary['current_seed_retrospective_count']}/{summary['current_seed_authority_required_count']}/{summary['current_seed_competitive_allowed_count']}`",
        f"- requirement fields: `{summary['requirement_field_count']}`",
        f"- first open: `{summary['first_open_benchmark_id'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Queue Rows",
        "",
        "| rank | benchmark | scope | metric profile | status | fields | requirements | blockers |",
        "| ---: | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['queue_rank']} | `{row['required_benchmark_id']}` | `{row['scope']}` | "
            f"`{row['metric_profile']}` | `{row['replacement_queue_status']}` | "
            f"{row['requirement_field_count']} | `{row['requirements_csv']}` | `{row['blockers']}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | `blocked_missing_scaffold_rows` | 0 | - | provide inputs |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 strict-blind historical replacement queue.")
    parser.add_argument("--lane-decision-json", default=DEFAULT_LANE_DECISION_JSON)
    parser.add_argument("--benchmark-scaffold-csv", default=DEFAULT_BENCHMARK_SCAFFOLD_CSV)
    parser.add_argument("--queue-dir", default=DEFAULT_QUEUE_DIR)
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
