#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ADJUDICATION_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_adjudication_packet_current.json"
DEFAULT_TARGET_WATCHLIST_CSV = "runs/casp17_target_watchlist_current.csv"
DEFAULT_CURRENT_TARGET_CSV = "casp17/casp17_target_model_folders_current.csv"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_replacement_queue_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_replacement_queue_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_QUEUE.md"

REPLACEMENT_COLUMNS = [
    "replace_target_id",
    "replace_target_name",
    "candidate_target_id",
    "candidate_target_name",
    "candidate_status",
    "candidate_rank",
    "candidate_type",
    "residues",
    "stoichiometry",
    "entry_date",
    "qa_expiration",
    "prediction_pdb",
    "ts_prediction_pdb",
    "raw_validation_json",
    "scorecard_json",
    "native_source_pdb_suggestion",
    "current_target_collision_ids",
    "blockers",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local CASP17 competitive-floor clearance replacement queue only. It ranks closed watchlist protein targets as "
    "possible replacements for collision-blocked clearance targets, while checking current-target name collisions "
    "and local prediction evidence. It does not choose a final replacement, fetch native structures, clear no-leak "
    "provenance, mutate clearance workorders/operator intake, score native accuracy, or submit to CASP."
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
        writer = csv.DictWriter(handle, fieldnames=REPLACEMENT_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _normalize_name(value: str) -> str:
    text = value.lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\bcomplex\b|\bchains?\b|\bprotein\b|\bcanceled\b|\bpreprint\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _target_name(row: dict[str, Any]) -> str:
    return _text(row.get("target_name") or row.get("description") or row.get("protein_name"))


def _existing(path_like: str | Path) -> str:
    path = _resolve(path_like)
    return _artifact(path) if path.exists() else ""


def _current_targets(path_like: str | Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in _read_csv(path_like):
        target_id = _text(row.get("target_id")).upper()
        name = _target_name(row)
        if target_id and name:
            out[target_id] = name
    return out


def _replacement_targets(adjudication_payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in _rows(adjudication_payload)
        if _text(row.get("replacement_required")).lower() == "true"
    ]


def _used_clearance_targets(adjudication_payload: dict[str, Any]) -> set[str]:
    return {_text(row.get("target_id")).upper() for row in _rows(adjudication_payload) if _text(row.get("target_id"))}


def _watchlist_candidates(path_like: str | Path) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for row in _read_csv(path_like):
        target_id = _text(row.get("target_id")).upper()
        if not target_id.startswith(("H", "T")):
            continue
        if _text(row.get("target_type")) != "Prot":
            continue
        if _text(row.get("deadline_class")) != "closed":
            continue
        candidates.append(row)
    return candidates


def _collision_ids(candidate_name: str, current_targets: dict[str, str]) -> list[str]:
    normalized = _normalize_name(candidate_name)
    if not normalized:
        return []
    return [
        target_id
        for target_id, current_name in sorted(current_targets.items())
        if normalized == _normalize_name(current_name)
    ]


def _candidate_artifacts(target_id: str) -> dict[str, str]:
    return {
        "prediction_pdb": _existing(f"runs/casp17_prediction_jobs_current/{target_id}/{target_id}_model_1.pdb"),
        "ts_prediction_pdb": _existing(f"runs/casp17_predictions_current/{target_id}TS.pdb"),
        "raw_validation_json": _existing(
            f"runs/casp17_internal_physics_raw_validations_current/{target_id}_raw_confidence_calibration.json"
        ),
        "scorecard_json": _existing(f"runs/casp17_internal_scorecards_current/{target_id}_internal_scorecard.json"),
    }


def _candidate_status(blockers: list[str]) -> tuple[str, str]:
    if not blockers:
        return (
            "candidate_ready_for_operator_clearance",
            "create replacement clearance workorder row, then run native candidate/no-leak operator intake",
        )
    if "current_target_name_collision" in blockers:
        return (
            "blocked_current_target_collision",
            "do not use this replacement candidate unless operator proves it is not current-target leakage",
        )
    if "local_prediction_missing" in blockers:
        return (
            "blocked_missing_local_prediction",
            "generate or locate local internal prediction/TS artifacts before using this replacement candidate",
        )
    return (
        "operator_source_repair_required",
        "repair missing local evidence before moving this candidate into clearance workorders",
    )


def _rank(row: dict[str, Any]) -> tuple[int, int, int, str]:
    status = _text(row.get("candidate_status"))
    status_rank = {
        "candidate_ready_for_operator_clearance": 0,
        "operator_source_repair_required": 1,
        "blocked_missing_local_prediction": 2,
        "blocked_current_target_collision": 3,
    }.get(status, 4)
    missing_count = len([blocker for blocker in _text(row.get("blockers")).split(",") if blocker])
    residues = _int(row.get("residues"))
    return (status_rank, missing_count, residues, _text(row.get("candidate_target_id")))


def _candidate_rows_for_target(
    replacement_target: dict[str, Any],
    *,
    candidates: list[dict[str, str]],
    current_targets: dict[str, str],
    used_targets: set[str],
    max_candidates: int,
) -> list[dict[str, Any]]:
    replace_id = _text(replacement_target.get("target_id")).upper()
    replace_name = _target_name(replacement_target)
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_id = _text(candidate.get("target_id")).upper()
        if candidate_id in used_targets:
            continue
        candidate_name = _target_name(candidate)
        collisions = _collision_ids(candidate_name, current_targets)
        artifacts = _candidate_artifacts(candidate_id)
        blockers: list[str] = []
        if collisions:
            blockers.append("current_target_name_collision")
        if not artifacts["prediction_pdb"] and not artifacts["ts_prediction_pdb"]:
            blockers.append("local_prediction_missing")
        if not artifacts["raw_validation_json"]:
            blockers.append("raw_validation_missing")
        if not artifacts["scorecard_json"]:
            blockers.append("scorecard_missing")
        status, next_action = _candidate_status(blockers)
        rows.append(
            {
                "replace_target_id": replace_id,
                "replace_target_name": replace_name,
                "candidate_target_id": candidate_id,
                "candidate_target_name": candidate_name,
                "candidate_status": status,
                "candidate_rank": 0,
                "candidate_type": _text(candidate.get("target_type")),
                "residues": _text(candidate.get("residues")),
                "stoichiometry": _text(candidate.get("stoichiometry")),
                "entry_date": _text(candidate.get("entry_date")),
                "qa_expiration": _text(candidate.get("qa_expiration")),
                "native_source_pdb_suggestion": f"casp17/native_candidate_downloads/{candidate_id}/{candidate_id}_native.pdb",
                "current_target_collision_ids": ";".join(collisions),
                "blockers": ",".join(dict.fromkeys(blockers)),
                "next_action": next_action,
                **artifacts,
            }
        )
    rows = sorted(rows, key=_rank)[:max_candidates]
    for index, row in enumerate(rows, start=1):
        row["candidate_rank"] = index
    if not rows:
        rows.append(
            {
                "replace_target_id": replace_id,
                "replace_target_name": replace_name,
                "candidate_target_id": "",
                "candidate_target_name": "",
                "candidate_status": "no_replacement_candidate_found",
                "candidate_rank": 1,
                "candidate_type": "",
                "residues": "",
                "stoichiometry": "",
                "entry_date": "",
                "qa_expiration": "",
                "prediction_pdb": "",
                "ts_prediction_pdb": "",
                "raw_validation_json": "",
                "scorecard_json": "",
                "native_source_pdb_suggestion": "",
                "current_target_collision_ids": "",
                "blockers": "replacement_candidate_missing",
                "next_action": "expand target discovery beyond local watchlist or repair source candidate inventory",
            }
        )
    return rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    adjudication_payload = _read_json(args.adjudication_json)
    replacement_targets = _replacement_targets(adjudication_payload)
    used_targets = _used_clearance_targets(adjudication_payload)
    current_targets = _current_targets(args.current_target_csv)
    candidates = _watchlist_candidates(args.target_watchlist_csv)
    rows: list[dict[str, Any]] = []
    for replacement_target in replacement_targets:
        rows.extend(
            _candidate_rows_for_target(
                replacement_target,
                candidates=candidates,
                current_targets=current_targets,
                used_targets=used_targets,
                max_candidates=max(1, args.max_candidates_per_target),
            )
        )
    statuses = [_text(row.get("candidate_status")) for row in rows]
    if not replacement_targets:
        replacement_status = "no_replacements_required"
    elif statuses.count("candidate_ready_for_operator_clearance"):
        replacement_status = "candidate_ready_for_operator_clearance"
    elif rows:
        replacement_status = "blocked_replacement_candidates"
    else:
        replacement_status = "no_replacement_candidate_found"
    first_open = next((row for row in rows if row["candidate_status"] != "candidate_ready_for_operator_clearance"), rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_competitive_floor_target_identity_clearance_replacement_queue",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "replacement_queue_status": replacement_status,
        "adjudication_json": _artifact(args.adjudication_json),
        "target_watchlist_csv": _artifact(args.target_watchlist_csv),
        "current_target_csv": _artifact(args.current_target_csv),
        "replacement_required_target_count": len(replacement_targets),
        "candidate_row_count": len(rows),
        "ready_candidate_count": statuses.count("candidate_ready_for_operator_clearance"),
        "blocked_missing_prediction_count": statuses.count("blocked_missing_local_prediction"),
        "blocked_current_collision_count": statuses.count("blocked_current_target_collision"),
        "operator_source_repair_required_count": statuses.count("operator_source_repair_required"),
        "no_candidate_count": statuses.count("no_replacement_candidate_found"),
        "first_open_replace_target_id": _text(first_open.get("replace_target_id")),
        "first_open_candidate_target_id": _text(first_open.get("candidate_target_id")),
        "first_open_status": _text(first_open.get("candidate_status")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Target Identity Clearance Replacement Queue",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- replacement_queue_status: `{summary['replacement_queue_status']}`",
        f"- replacement targets/candidate rows: `{summary['replacement_required_target_count']}/{summary['candidate_row_count']}`",
        f"- ready/missing-prediction/current-collision/source-repair/no-candidate: `{summary['ready_candidate_count']}/{summary['blocked_missing_prediction_count']}/{summary['blocked_current_collision_count']}/{summary['operator_source_repair_required_count']}/{summary['no_candidate_count']}`",
        f"- first open: `{summary['first_open_replace_target_id'] or '-'}` -> `{summary['first_open_candidate_target_id'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- first next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Replacement Candidates",
        "",
        "| replace | rank | candidate | status | prediction | validation | scorecard | blockers | next action |",
        "| --- | ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['replace_target_id']}` | {row['candidate_rank']} | `{row['candidate_target_id'] or '-'}` "
            f"{row['candidate_target_name'] or ''} | `{row['candidate_status']}` | "
            f"`{row['prediction_pdb'] or row['ts_prediction_pdb'] or '-'}` | "
            f"`{row['raw_validation_json'] or '-'}` | `{row['scorecard_json'] or '-'}` | "
            f"`{row['blockers'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | 0 | - | `no_replacements_required` | - | - | - | - | no replacement required |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 clearance replacement target queue.")
    parser.add_argument("--adjudication-json", default=DEFAULT_ADJUDICATION_JSON)
    parser.add_argument("--target-watchlist-csv", default=DEFAULT_TARGET_WATCHLIST_CSV)
    parser.add_argument("--current-target-csv", default=DEFAULT_CURRENT_TARGET_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--max-candidates-per-target", type=int, default=8)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
