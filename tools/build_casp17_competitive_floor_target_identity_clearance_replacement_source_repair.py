#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_REPLACEMENT_QUEUE_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_replacement_queue_current.json"
DEFAULT_TARGET_WATCHLIST_CSV = "runs/casp17_target_watchlist_current.csv"
DEFAULT_OUT_DIR = "casp17/competitive_floor_target_identity_clearance_replacement_source_repair"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_replacement_source_repair_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_replacement_source_repair_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_SOURCE_REPAIR.md"

SOURCE_REPAIR_COLUMNS = [
    "candidate_target_id",
    "candidate_target_name",
    "source_repair_status",
    "replace_target_ids",
    "candidate_queue_statuses",
    "cancellation_date",
    "lane_recommendation",
    "recommended_action",
    "fasta_path",
    "prediction_pdb",
    "ts_prediction_pdb",
    "raw_validation_json",
    "scorecard_json",
    "predictor_command",
    "validation_command",
    "scorecard_command",
    "source_repair_md",
    "blockers",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local CASP17 competitive-floor replacement source repair only. It decomposes replacement candidates into "
    "sequence, prediction, validation, scorecard, cancellation, and collision blockers before they can be considered "
    "for clearance. It does not invent sequences, fetch native structures, clear no-leak provenance, mutate "
    "workorders/operator intake, score native accuracy, choose final replacements, or submit to CASP."
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


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SOURCE_REPAIR_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _slug(value: str, fallback: str = "candidate") -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("._")
    return slug or fallback


def _first_existing(paths: list[str | Path]) -> str:
    for path_like in paths:
        text = _text(path_like)
        if not text:
            continue
        path = _resolve(text)
        if path.exists():
            return _artifact(path)
    return ""


def _watchlist_by_target(path_like: str | Path) -> dict[str, dict[str, str]]:
    return {
        _text(row.get("target_id")).upper(): row
        for row in _read_csv(path_like)
        if _text(row.get("target_id"))
    }


def _candidate_groups(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        candidate_id = _text(row.get("candidate_target_id")).upper()
        if candidate_id:
            grouped[candidate_id].append(row)
    return grouped


def _fasta_path(candidate_id: str) -> str:
    return _first_existing(
        [
            f"casp17/replacement_source_fasta/{candidate_id}.fasta",
            f"runs/casp17_replacement_sequences_current/{candidate_id}.fasta",
            f"runs/casp17_sequences_current/{candidate_id}.fasta",
        ]
    )


def _candidate_artifacts(candidate_id: str, rows: list[dict[str, Any]]) -> dict[str, str]:
    first = rows[0] if rows else {}
    return {
        "fasta_path": _fasta_path(candidate_id),
        "prediction_pdb": _first_existing(
            [
                _text(first.get("prediction_pdb")),
                f"runs/casp17_prediction_jobs_current/{candidate_id}/{candidate_id}_model_1.pdb",
            ]
        ),
        "ts_prediction_pdb": _first_existing(
            [
                _text(first.get("ts_prediction_pdb")),
                f"runs/casp17_predictions_current/{candidate_id}TS.pdb",
            ]
        ),
        "raw_validation_json": _first_existing(
            [
                _text(first.get("raw_validation_json")),
                f"runs/casp17_internal_physics_raw_validations_current/{candidate_id}_raw_confidence_calibration.json",
            ]
        ),
        "scorecard_json": _first_existing(
            [
                _text(first.get("scorecard_json")),
                f"runs/casp17_internal_scorecards_current/{candidate_id}_internal_scorecard.json",
            ]
        ),
    }


def _commands(candidate_id: str, artifacts: dict[str, str]) -> tuple[str, str, str]:
    fasta = artifacts["fasta_path"] or f"casp17/replacement_source_fasta/{candidate_id}.fasta"
    prediction = artifacts["prediction_pdb"] or f"runs/casp17_prediction_jobs_current/{candidate_id}/{candidate_id}_model_1.pdb"
    runtime = f"runs/casp17_prediction_jobs_current/{candidate_id}/backend_runtime.json"
    metrics = f"runs/casp17_prediction_jobs_current/{candidate_id}/internal_physics_metrics.json"
    predictor_command = (
        "python3 tools/run_casp17_internal_physics_baseline_predictor.py "
        f"--target-id {candidate_id} --fasta {fasta} "
        f"--out-dir runs/casp17_prediction_jobs_current/{candidate_id} "
        f"--raw-pdb {prediction} --runtime-json {runtime} --metrics-json {metrics} "
        "--quality-preset casp17_quality --ranked-raw-count 5 --emit-backbone-atoms"
        f" --out-json runs/casp17_prediction_jobs_current/{candidate_id}/{candidate_id}_predictor.json"
        f" --out-csv runs/casp17_prediction_jobs_current/{candidate_id}/{candidate_id}_predictor.csv"
        f" --out-md runs/casp17_prediction_jobs_current/{candidate_id}/{candidate_id}_predictor.md"
    )
    validation_command = (
        "python3 tools/validate_casp17_backend_contract.py "
        f"--target-id {candidate_id} --sequence-path {fasta} --raw-pdb {prediction} "
        f"--runtime-json {runtime} --backend-kind internal_physics --require-gpu "
        f"--out-json runs/casp17_internal_physics_raw_validations_current/{candidate_id}_backend_contract.json "
        f"--out-csv runs/casp17_internal_physics_raw_validations_current/{candidate_id}_backend_contract.csv "
        f"--out-md runs/casp17_internal_physics_raw_validations_current/{candidate_id}_backend_contract.md"
    )
    scorecard_command = (
        "python3 tools/build_casp17_competitive_floor_target_identity_clearance_replacement_scorecard.py "
        "--source-repair-json casp17/casp17_competitive_floor_target_identity_clearance_replacement_source_repair_current.json "
        "--out-dir runs/casp17_internal_scorecards_current "
        "--out-json casp17/casp17_competitive_floor_target_identity_clearance_replacement_scorecard_current.json "
        "--out-csv casp17/casp17_competitive_floor_target_identity_clearance_replacement_scorecard_current.csv "
        "--out-md casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_SCORECARD.md"
    )
    return predictor_command, validation_command, scorecard_command


def _status_and_blockers(
    rows: list[dict[str, Any]],
    *,
    watchlist_row: dict[str, str],
    artifacts: dict[str, str],
) -> tuple[str, list[str], str]:
    blockers: list[str] = []
    lane_recommendation = _text(watchlist_row.get("lane_recommendation"))
    recommended_action = _text(watchlist_row.get("recommended_action"))
    if (
        _text(watchlist_row.get("cancellation_date"))
        or lane_recommendation == "out_of_scope_cancelled"
        or recommended_action == "ignore_for_selected_lanes"
    ):
        blockers.append("target_cancelled")
    if any("current_target_name_collision" in _text(row.get("blockers")) for row in rows):
        blockers.append("current_target_name_collision")
    if not artifacts["fasta_path"]:
        blockers.append("fasta_missing")
    if not artifacts["prediction_pdb"] and not artifacts["ts_prediction_pdb"]:
        blockers.append("local_prediction_missing")
    if not artifacts["raw_validation_json"]:
        blockers.append("raw_validation_missing")
    if not artifacts["scorecard_json"]:
        blockers.append("scorecard_missing")
    if "target_cancelled" in blockers:
        return "blocked_cancelled_target", blockers, "exclude this replacement unless an operator explicitly reopens the canceled target rationale"
    if "current_target_name_collision" in blockers:
        return "blocked_current_target_collision", blockers, "choose a non-colliding replacement target or prove no current-target leakage"
    if "local_prediction_missing" in blockers:
        if "fasta_missing" in blockers:
            return "awaiting_sequence", blockers, "provide reviewed FASTA before local prediction can be generated"
        return "ready_for_prediction_run", blockers, "run the internal physics predictor command for this candidate"
    if "raw_validation_missing" in blockers or "scorecard_missing" in blockers:
        return "ready_for_validation_scorecard", blockers, "run validation and scorecard generation for this candidate"
    return "source_ready", [], "move this replacement candidate into operator clearance review"


def _write_candidate_md(out_dir: Path, row: dict[str, Any]) -> str:
    folder = out_dir / f"{row['candidate_target_id']}_{_slug(row['candidate_target_name'], fallback=row['candidate_target_id'])}"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "SOURCE_REPAIR.md"
    lines = [
        f"# {row['candidate_target_id']} Replacement Source Repair",
        "",
        f"- candidate_name: {row['candidate_target_name'] or '-'}",
        f"- source_repair_status: `{row['source_repair_status']}`",
        f"- replace_target_ids: `{row['replace_target_ids']}`",
        f"- cancellation_date: `{row['cancellation_date'] or '-'}`",
        f"- lane_recommendation: `{row['lane_recommendation'] or '-'}`",
        f"- recommended_action: `{row['recommended_action'] or '-'}`",
        f"- fasta_path: `{row['fasta_path'] or '-'}`",
        f"- prediction_pdb: `{row['prediction_pdb'] or row['ts_prediction_pdb'] or '-'}`",
        f"- raw_validation_json: `{row['raw_validation_json'] or '-'}`",
        f"- scorecard_json: `{row['scorecard_json'] or '-'}`",
        f"- blockers: `{row['blockers'] or '-'}`",
        f"- next_action: {row['next_action']}",
        "",
        "## Commands",
        "",
        f"- predictor: `{row['predictor_command']}`",
        f"- validation: `{row['validation_command']}`",
        f"- scorecard: `{row['scorecard_command']}`",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return _artifact(path)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    replacement_payload = _read_json(args.replacement_queue_json)
    replacement_summary = _summary(replacement_payload)
    watchlist = _watchlist_by_target(args.target_watchlist_csv)
    grouped = _candidate_groups(_rows(replacement_payload))
    out_dir = _resolve(args.out_dir)
    rows: list[dict[str, Any]] = []
    for candidate_id, candidate_rows in sorted(grouped.items()):
        first = candidate_rows[0]
        artifacts = _candidate_artifacts(candidate_id, candidate_rows)
        watchlist_row = watchlist.get(candidate_id, {})
        status, blockers, next_action = _status_and_blockers(
            candidate_rows,
            watchlist_row=watchlist_row,
            artifacts=artifacts,
        )
        predictor_command, validation_command, scorecard_command = _commands(candidate_id, artifacts)
        row = {
            "candidate_target_id": candidate_id,
            "candidate_target_name": _text(first.get("candidate_target_name")),
            "source_repair_status": status,
            "replace_target_ids": ";".join(sorted({_text(row.get("replace_target_id")) for row in candidate_rows if _text(row.get("replace_target_id"))})),
            "candidate_queue_statuses": ";".join(sorted({_text(row.get("candidate_status")) for row in candidate_rows if _text(row.get("candidate_status"))})),
            "cancellation_date": _text(watchlist_row.get("cancellation_date")),
            "lane_recommendation": _text(watchlist_row.get("lane_recommendation")),
            "recommended_action": _text(watchlist_row.get("recommended_action")),
            **artifacts,
            "predictor_command": predictor_command,
            "validation_command": validation_command,
            "scorecard_command": scorecard_command,
            "source_repair_md": "",
            "blockers": ",".join(dict.fromkeys(blockers)),
            "next_action": next_action,
        }
        row["source_repair_md"] = _write_candidate_md(out_dir, row)
        rows.append(row)
    statuses = [_text(row.get("source_repair_status")) for row in rows]
    if not rows:
        source_repair_status = "no_replacement_candidates"
    elif "source_ready" in statuses:
        source_repair_status = "source_ready"
    elif "ready_for_prediction_run" in statuses:
        source_repair_status = "ready_for_prediction_run"
    elif "ready_for_validation_scorecard" in statuses:
        source_repair_status = "ready_for_validation_scorecard"
    elif "awaiting_sequence" in statuses:
        source_repair_status = "awaiting_sequence"
    else:
        source_repair_status = "blocked_source_candidates"
    first_open = next((row for row in rows if row["source_repair_status"] != "source_ready"), rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_competitive_floor_target_identity_clearance_replacement_source_repair",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "replacement_source_repair_status": source_repair_status,
        "replacement_queue_json": _artifact(args.replacement_queue_json),
        "replacement_queue_status": _text(replacement_summary.get("replacement_queue_status")),
        "target_watchlist_csv": _artifact(args.target_watchlist_csv),
        "out_dir": _artifact(args.out_dir),
        "candidate_count": len(rows),
        "source_ready_count": statuses.count("source_ready"),
        "ready_for_prediction_count": statuses.count("ready_for_prediction_run"),
        "ready_for_validation_scorecard_count": statuses.count("ready_for_validation_scorecard"),
        "awaiting_sequence_count": statuses.count("awaiting_sequence"),
        "blocked_cancelled_count": statuses.count("blocked_cancelled_target"),
        "blocked_current_collision_count": statuses.count("blocked_current_target_collision"),
        "source_repair_md_count": sum(1 for row in rows if row["source_repair_md"]),
        "first_open_candidate_target_id": _text(first_open.get("candidate_target_id")),
        "first_open_status": _text(first_open.get("source_repair_status")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Target Identity Clearance Replacement Source Repair",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- replacement_source_repair_status: `{summary['replacement_source_repair_status']}`",
        f"- candidates: `{summary['candidate_count']}`",
        f"- source-ready/predict/validate/sequence/cancelled/collision: `{summary['source_ready_count']}/{summary['ready_for_prediction_count']}/{summary['ready_for_validation_scorecard_count']}/{summary['awaiting_sequence_count']}/{summary['blocked_cancelled_count']}/{summary['blocked_current_collision_count']}`",
        f"- source repair docs: `{summary['source_repair_md_count']}`",
        f"- first open: `{summary['first_open_candidate_target_id'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- first next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Candidate Repair Rows",
        "",
        "| candidate | status | replace | fasta | prediction | validation | scorecard | blockers | next action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['candidate_target_id']}` | `{row['source_repair_status']}` | `{row['replace_target_ids']}` | "
            f"`{row['fasta_path'] or '-'}` | `{row['prediction_pdb'] or row['ts_prediction_pdb'] or '-'}` | "
            f"`{row['raw_validation_json'] or '-'}` | `{row['scorecard_json'] or '-'}` | "
            f"`{row['blockers'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | `no_replacement_candidates` | - | - | - | - | - | - | no replacement candidates queued |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 replacement source repair packet.")
    parser.add_argument("--replacement-queue-json", default=DEFAULT_REPLACEMENT_QUEUE_JSON)
    parser.add_argument("--target-watchlist-csv", default=DEFAULT_TARGET_WATCHLIST_CSV)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
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
