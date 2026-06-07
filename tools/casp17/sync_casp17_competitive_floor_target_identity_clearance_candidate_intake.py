#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CANDIDATE_INTAKE_CSV = (
    "casp17/casp17_competitive_floor_identity_intake_bundle_candidate_from_clearance_current.csv"
)
DEFAULT_LIVE_INTAKE_CSV = "casp17/casp17_competitive_floor_identity_intake_bundle_current.csv"
DEFAULT_CURRENT_TARGET_CSV = "casp17/casp17_target_model_folders_current.csv"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_candidate_intake_sync_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_candidate_intake_sync_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_CANDIDATE_INTAKE_SYNC.md"

REQUIRED_FIELDS = ["proposed_benchmark_id", "proposed_target_id", "evidence_ref", "operator_clearance"]
SYNC_FIELDS = REQUIRED_FIELDS + ["identity_status", "missing_field_count", "blockers", "next_action"]
SYNC_COLUMNS = [
    "dropzone_id",
    "scope",
    "sync_status",
    "candidate_status",
    "live_identity_status",
    "proposed_benchmark_id",
    "proposed_target_id",
    "evidence_ref",
    "operator_clearance",
    "missing_field_count",
    "applied_field_count",
    "blockers",
    "next_action",
]
CLEAR_VALUES = {"ready_for_row_fill", "cleared", "no_leak", "internal_no_leak", "true", "yes"}
CLAIM_BOUNDARY = (
    "Local competitive-floor target identity clearance candidate-intake sync only. It copies operator-reviewed "
    "candidate intake rows into the live identity intake CSV only when --apply is explicitly provided. It does not "
    "choose targets, clear provenance, fetch native structures, score native accuracy, mutate the identity unlock "
    "kit, import evidence, run predictors, or submit to CASP."
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


def _contains_placeholder(value: Any) -> bool:
    text = _text(value)
    upper = text.upper()
    return not text or upper.startswith("REQUIRED") or "REQUIRED_" in upper or "YYYY-MM-DD" in upper


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], [], [f"{path.name}_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    blockers: list[str] = []
    if not fieldnames:
        blockers.append(f"{path.name}_header_missing")
    if not rows:
        blockers.append(f"{path.name}_empty")
    return rows, fieldnames, blockers


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


def _by_dropzone(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {_text(row.get("dropzone_id")): row for row in rows if _text(row.get("dropzone_id"))}


def _current_targets(path_like: str | Path) -> set[str]:
    rows, _fields, blockers = _read_csv(path_like)
    if blockers:
        return set()
    return {_text(row.get("target_id")).upper() for row in rows if _text(row.get("target_id"))}


def _live_slot_open(row: dict[str, str]) -> bool:
    return all(_contains_placeholder(row.get(field)) for field in REQUIRED_FIELDS[:2])


def _candidate_has_values(row: dict[str, str]) -> bool:
    return any(not _contains_placeholder(row.get(field)) for field in REQUIRED_FIELDS)


def _row_blockers(
    candidate: dict[str, str],
    live: dict[str, str],
    current_targets: set[str],
    duplicate_targets: set[str],
) -> list[str]:
    blockers: list[str] = []
    target_id = _text(candidate.get("proposed_target_id")).upper()
    benchmark_id = _text(candidate.get("proposed_benchmark_id"))
    if not live:
        blockers.append("live_intake_row_missing")
    if _text(candidate.get("identity_status")) != "staged_for_operator_review":
        blockers.append("candidate_status_not_staged_for_operator_review")
    if live and _text(candidate.get("scope")) != _text(live.get("scope")):
        blockers.append("candidate_live_scope_mismatch")
    for field in REQUIRED_FIELDS:
        if _contains_placeholder(candidate.get(field)):
            blockers.append(f"{field}_required")
    if benchmark_id and not benchmark_id.startswith("hist_"):
        blockers.append("proposed_benchmark_id_must_start_hist")
    if target_id in current_targets:
        blockers.append("proposed_target_id_is_current_casp17_target")
    if target_id in duplicate_targets:
        blockers.append("proposed_target_id_duplicate")
    if _text(candidate.get("operator_clearance")).lower() not in CLEAR_VALUES:
        blockers.append("operator_clearance_required")
    if live and not _live_slot_open(live):
        blockers.append("live_intake_slot_not_empty")
    return blockers


def _next_action(status: str) -> str:
    if status == "ready_to_apply":
        return "review candidate intake row, then rerun with --apply to copy it into the live identity intake bundle"
    if status == "applied":
        return "rerun identity intake sync and identity cycle"
    if status == "waiting_on_staged_identity":
        return "wait for clearance intake staging to produce staged_for_operator_review rows"
    return "resolve candidate intake sync blockers before applying"


def _build_rows(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[str], list[str]]:
    candidate_rows, _candidate_fields, candidate_blockers = _read_csv(args.candidate_intake_csv)
    live_rows, live_fields, live_blockers = _read_csv(args.live_intake_csv)
    live_by_id = _by_dropzone(live_rows)
    current_targets = _current_targets(args.current_target_csv)
    staged_targets = [
        _text(row.get("proposed_target_id")).upper()
        for row in candidate_rows
        if _text(row.get("identity_status")) == "staged_for_operator_review"
        and not _contains_placeholder(row.get("proposed_target_id"))
    ]
    counts = Counter(staged_targets)
    duplicate_targets = {target for target, count in counts.items() if count > 1}
    rows: list[dict[str, Any]] = []
    for candidate in candidate_rows:
        dropzone_id = _text(candidate.get("dropzone_id"))
        live = live_by_id.get(dropzone_id, {})
        if not _candidate_has_values(candidate):
            status = "waiting_on_staged_identity"
            blockers = ["candidate_identity_values_missing"]
            applied = 0
        else:
            blockers = _row_blockers(candidate, live, current_targets, duplicate_targets)
            status = "ready_to_apply" if not blockers else "blocked"
            applied = 0
        rows.append(
            {
                "dropzone_id": dropzone_id,
                "scope": _text(candidate.get("scope") or live.get("scope")),
                "sync_status": status,
                "candidate_status": _text(candidate.get("identity_status")),
                "live_identity_status": _text(live.get("identity_status")),
                "proposed_benchmark_id": _text(candidate.get("proposed_benchmark_id")),
                "proposed_target_id": _text(candidate.get("proposed_target_id")).upper(),
                "evidence_ref": _text(candidate.get("evidence_ref")),
                "operator_clearance": _text(candidate.get("operator_clearance")),
                "missing_field_count": sum(1 for field in REQUIRED_FIELDS if _contains_placeholder(candidate.get(field))),
                "applied_field_count": applied,
                "blockers": ",".join(dict.fromkeys(blockers)),
                "next_action": _next_action(status),
            }
        )
    return rows, live_rows, live_fields, [*candidate_blockers, *live_blockers]


def _apply_rows(args: argparse.Namespace, rows: list[dict[str, Any]], live_rows: list[dict[str, str]], live_fields: list[str]) -> int:
    ready_by_id = {row["dropzone_id"]: row for row in rows if row["sync_status"] == "ready_to_apply"}
    applied = 0
    for live in live_rows:
        dropzone_id = _text(live.get("dropzone_id"))
        candidate = ready_by_id.get(dropzone_id)
        if not candidate:
            continue
        for field in REQUIRED_FIELDS:
            live[field] = _text(candidate.get(field))
        live["identity_status"] = "staged_for_operator_review"
        live["missing_field_count"] = "0"
        live["blockers"] = ""
        live["next_action"] = "review identity values, then run identity intake sync"
        applied += len(SYNC_FIELDS)
    if applied:
        _write_csv(args.live_intake_csv, live_rows, live_fields)
    return applied


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    rows, live_rows, live_fields, input_blockers = _build_rows(args)
    applied_count = _apply_rows(args, rows, live_rows, live_fields) if args.apply else 0
    if applied_count:
        for row in rows:
            if row["sync_status"] == "ready_to_apply":
                row["sync_status"] = "applied"
                row["applied_field_count"] = len(SYNC_FIELDS)
                row["next_action"] = _next_action("applied")
    by_status = Counter(_text(row.get("sync_status")) for row in rows)
    if input_blockers:
        sync_status = "missing_inputs"
    elif by_status["blocked"]:
        sync_status = "blocked"
    elif by_status["ready_to_apply"] and not args.apply:
        sync_status = "ready_to_apply"
    elif by_status["applied"]:
        sync_status = "applied"
    elif by_status["waiting_on_staged_identity"]:
        sync_status = "waiting_on_staged_identity"
    else:
        sync_status = "waiting_on_staged_identity"
    first_open = next((row for row in rows if row["sync_status"] != "applied"), rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_competitive_floor_target_identity_clearance_candidate_intake_sync",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "candidate_intake_sync_status": sync_status,
        "apply_mode": "applied" if args.apply else "dry_run",
        "candidate_intake_csv": _artifact(args.candidate_intake_csv),
        "live_intake_csv": _artifact(args.live_intake_csv),
        "current_target_csv": _artifact(args.current_target_csv),
        "sync_row_count": len(rows),
        "ready_to_apply_count": by_status["ready_to_apply"],
        "waiting_on_staged_identity_count": by_status["waiting_on_staged_identity"],
        "blocked_count": by_status["blocked"],
        "applied_row_count": by_status["applied"],
        "applied_field_count": applied_count,
        "first_open_dropzone_id": _text(first_open.get("dropzone_id")),
        "first_open_status": _text(first_open.get("sync_status")),
        "first_open_next_action": _text(first_open.get("next_action")) or _next_action("waiting_on_staged_identity"),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Target Identity Clearance Candidate Intake Sync",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- candidate_intake_sync_status: `{summary['candidate_intake_sync_status']}`",
        f"- apply_mode: `{summary['apply_mode']}`",
        f"- rows ready/waiting/blocked/applied: `{summary['ready_to_apply_count']}/{summary['waiting_on_staged_identity_count']}/{summary['blocked_count']}/{summary['applied_row_count']}`",
        f"- applied fields: `{summary['applied_field_count']}`",
        f"- first open: `{summary['first_open_dropzone_id'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Sync Rows",
        "",
        "| dropzone | scope | status | candidate status | live status | benchmark | target | blockers | next action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['dropzone_id']}` | `{row['scope']}` | `{row['sync_status']}` | "
            f"`{row['candidate_status'] or '-'}` | `{row['live_identity_status'] or '-'}` | "
            f"`{row['proposed_benchmark_id'] or '-'}` | `{row['proposed_target_id'] or '-'}` | "
            f"`{row['blockers'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `waiting_on_staged_identity` | - | - | - | - | `candidate_rows_missing` | rerun clearance intake staging |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], SYNC_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync cleared candidate identity intake rows into live intake.")
    parser.add_argument("--candidate-intake-csv", default=DEFAULT_CANDIDATE_INTAKE_CSV)
    parser.add_argument("--live-intake-csv", default=DEFAULT_LIVE_INTAKE_CSV)
    parser.add_argument("--current-target-csv", default=DEFAULT_CURRENT_TARGET_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
