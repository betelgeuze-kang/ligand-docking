#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_IDENTITY_CANDIDATE_JSON = "casp17/casp17_competitive_floor_identity_candidate_packet_current.json"
DEFAULT_IDENTITY_SOURCE_REPAIR_CSV = "casp17/casp17_competitive_floor_identity_source_repair_plan_current.csv"
DEFAULT_IDENTITY_UNLOCK_KIT_JSON = "casp17/casp17_competitive_floor_identity_unlock_kit_current.json"
DEFAULT_TARGET_CLEARANCE_CYCLE_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_cycle_current.json"
DEFAULT_REPLACEMENT_DECISION_PREFLIGHT_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_replacement_decision_preflight_current.json"
)
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_unblock_map_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_unblock_map_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_UNBLOCK_MAP.md"

PHASE_ORDER = [
    "target_identity",
    "core_files",
    "no_leak_provenance",
    "ablation_files",
    "calibration_values",
]

ROW_COLUMNS = [
    "operator_priority",
    "dropzone_id",
    "scope",
    "current_benchmark_id",
    "current_target_id",
    "identity_candidate_status",
    "target_identity_status",
    "core_files_status",
    "no_leak_provenance_status",
    "ablation_files_status",
    "calibration_values_status",
    "blocking_field_count",
    "blocking_phase_count",
    "first_blocking_phase",
    "first_blockers",
    "next_unblock_action",
]

CLAIM_BOUNDARY = (
    "Local CASP17 competitive-floor unblock map only. It condenses existing identity-candidate, source-repair, "
    "unlock-kit, clearance-cycle, and replacement-decision packets into a minimal next-action map for the first "
    "15 historical benchmark rows. It does not choose historical targets, fetch native structures, clear no-leak "
    "provenance, mutate row_fill files, score native accuracy, run predictors, or submit to CASP."
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
        return [dict(row) for row in csv.DictReader(handle)]


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _phase_map(repair_rows: list[dict[str, str]]) -> dict[int, dict[str, dict[str, str]]]:
    by_rank: dict[int, dict[str, dict[str, str]]] = defaultdict(dict)
    for row in repair_rows:
        source_rank = _int(row.get("source_rank"))
        phase = _text(row.get("repair_phase"))
        if source_rank and phase:
            by_rank[source_rank][phase] = row
    return dict(by_rank)


def _phase_status(phases: dict[str, dict[str, str]], phase: str) -> str:
    row = phases.get(phase, {})
    return _text(row.get("repair_status")) or "missing"


def _first_blocking_phase(phases: dict[str, dict[str, str]]) -> tuple[str, str, str]:
    for phase in PHASE_ORDER:
        row = phases.get(phase, {})
        status = _text(row.get("repair_status"))
        if status and not status.startswith("ready") and status != "pass":
            return phase, _text(row.get("blockers")), _text(row.get("next_action"))
    return "", "", ""


def _row(candidate_row: dict[str, Any], phases: dict[str, dict[str, str]], *, source_candidate_count: int) -> dict[str, Any]:
    phase, blockers, action = _first_blocking_phase(phases)
    if not action:
        candidate_status = _text(candidate_row.get("candidate_status"))
        if candidate_status == "ready_for_intake":
            action = "sync this cleared identity candidate into the identity unlock kit"
        elif source_candidate_count == 0:
            action = "seed the historical benchmark manifest with cleared non-CASP17 target identities"
        else:
            action = "repair blocked source candidates until one no-leak historical target is ready"
    blocking_fields = sum(_int(row.get("blocking_field_count")) for row in phases.values())
    blocking_phase_count = sum(
        1
        for row in phases.values()
        if _text(row.get("repair_status")) and not _text(row.get("repair_status")).startswith("ready")
    )
    return {
        "operator_priority": _int(candidate_row.get("operator_priority")),
        "dropzone_id": _text(candidate_row.get("dropzone_id")),
        "scope": _text(candidate_row.get("scope")),
        "current_benchmark_id": _text(candidate_row.get("current_benchmark_id")),
        "current_target_id": _text(candidate_row.get("current_target_id")),
        "identity_candidate_status": _text(candidate_row.get("candidate_status")),
        "target_identity_status": _phase_status(phases, "target_identity"),
        "core_files_status": _phase_status(phases, "core_files"),
        "no_leak_provenance_status": _phase_status(phases, "no_leak_provenance"),
        "ablation_files_status": _phase_status(phases, "ablation_files"),
        "calibration_values_status": _phase_status(phases, "calibration_values"),
        "blocking_field_count": blocking_fields,
        "blocking_phase_count": blocking_phase_count,
        "first_blocking_phase": phase,
        "first_blockers": blockers,
        "next_unblock_action": action,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    candidate_payload = _read_json(args.identity_candidate_json)
    candidate_summary = _summary(candidate_payload)
    candidate_rows = _rows(candidate_payload)
    repair_rows = _read_csv(args.identity_source_repair_csv)
    phases_by_rank = _phase_map(repair_rows)
    unlock_summary = _summary(_read_json(args.identity_unlock_kit_json))
    clearance_cycle_summary = _summary(_read_json(args.target_clearance_cycle_json))
    replacement_decision_summary = _summary(_read_json(args.replacement_decision_preflight_json))
    source_candidate_count = _int(candidate_summary.get("source_candidate_count"))

    rows = [
        _row(candidate_row, phases_by_rank.get(index, {}), source_candidate_count=source_candidate_count)
        for index, candidate_row in enumerate(candidate_rows, start=1)
    ]
    status_counts = Counter(_text(row.get("identity_candidate_status")) for row in rows)
    phase_status_counts = Counter()
    for row in rows:
        for phase in PHASE_ORDER:
            phase_status_counts[_text(row.get(f"{phase}_status"))] += 1
    first_open = next((row for row in rows if _text(row.get("identity_candidate_status")) != "ready_for_intake"), rows[0] if rows else {})
    if rows and status_counts["ready_for_intake"] == len(rows):
        unblock_status = "identity_ready_for_sync"
    elif source_candidate_count == 0:
        unblock_status = "awaiting_historical_manifest_seed"
    elif status_counts["ready_for_intake"]:
        unblock_status = "partial_identity_candidates_ready"
    else:
        unblock_status = "awaiting_candidate_source_repair"

    phase_open_counts = {
        phase: sum(1 for row in rows if _text(row.get(f"{phase}_status")) not in {"ready", "pass", ""})
        for phase in PHASE_ORDER
    }
    summary = {
        "packet_type": "casp17_competitive_floor_unblock_map",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "unblock_map_status": unblock_status,
        "identity_candidate_json": _artifact(args.identity_candidate_json),
        "identity_source_repair_csv": _artifact(args.identity_source_repair_csv),
        "identity_unlock_kit_json": _artifact(args.identity_unlock_kit_json),
        "target_clearance_cycle_json": _artifact(args.target_clearance_cycle_json),
        "replacement_decision_preflight_json": _artifact(args.replacement_decision_preflight_json),
        "row_count": len(rows),
        "monomer_count": sum(1 for row in rows if row["scope"] == "monomer"),
        "complex_count": sum(1 for row in rows if row["scope"] == "complex"),
        "ready_for_intake_count": status_counts["ready_for_intake"],
        "awaiting_candidate_source_count": status_counts["awaiting_candidate_source"],
        "source_candidate_count": source_candidate_count,
        "source_ready_candidate_count": _int(candidate_summary.get("source_ready_candidate_count")),
        "source_blocked_candidate_count": _int(candidate_summary.get("source_blocked_candidate_count")),
        "phase_open_counts": phase_open_counts,
        "blocking_field_count": sum(_int(row.get("blocking_field_count")) for row in rows),
        "blocking_phase_count": sum(_int(row.get("blocking_phase_count")) for row in rows),
        "identity_unlock_status": _text(unlock_summary.get("identity_unlock_status")),
        "target_clearance_cycle_status": _text(
            clearance_cycle_summary.get("cycle_status") or clearance_cycle_summary.get("clearance_cycle_status")
        ),
        "replacement_decision_preflight_status": _text(replacement_decision_summary.get("decision_preflight_status")),
        "first_open_dropzone_id": _text(first_open.get("dropzone_id")),
        "first_open_phase": _text(first_open.get("first_blocking_phase")),
        "first_open_blockers": _text(first_open.get("first_blockers")),
        "first_open_next_action": _text(first_open.get("next_unblock_action")),
        "claim_boundary": CLAIM_BOUNDARY,
        "phase_status_counts": dict(phase_status_counts),
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    phase_open = summary["phase_open_counts"]
    lines = [
        "# CASP17 Competitive-Floor Unblock Map",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- unblock_map_status: `{summary['unblock_map_status']}`",
        f"- rows monomer/complex/total: `{summary['monomer_count']}/{summary['complex_count']}/{summary['row_count']}`",
        f"- identity ready/awaiting: `{summary['ready_for_intake_count']}/{summary['awaiting_candidate_source_count']}`",
        f"- source candidates ready/blocked/total: `{summary['source_ready_candidate_count']}/{summary['source_blocked_candidate_count']}/{summary['source_candidate_count']}`",
        f"- open phases target/core/provenance/ablation/calibration: `{phase_open['target_identity']}/{phase_open['core_files']}/{phase_open['no_leak_provenance']}/{phase_open['ablation_files']}/{phase_open['calibration_values']}`",
        f"- blocking fields/phases: `{summary['blocking_field_count']}/{summary['blocking_phase_count']}`",
        f"- identity unlock / clearance cycle / replacement decision: `{summary['identity_unlock_status'] or '-'}` / `{summary['target_clearance_cycle_status'] or '-'}` / `{summary['replacement_decision_preflight_status'] or '-'}`",
        f"- first open: `{summary['first_open_dropzone_id'] or '-'}` `{summary['first_open_phase'] or '-'}`",
        f"- next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Rows",
        "",
        "| priority | dropzone | scope | identity | first phase | blockers | next action |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['operator_priority']} | `{row['dropzone_id']}` | `{row['scope']}` | "
            f"`{row['identity_candidate_status']}` | `{row['first_blocking_phase'] or '-'}` | "
            f"`{row['first_blockers'] or '-'}` | {row['next_unblock_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `missing` | - | - | regenerate identity candidate packet |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 competitive-floor unblock map.")
    parser.add_argument("--identity-candidate-json", default=DEFAULT_IDENTITY_CANDIDATE_JSON)
    parser.add_argument("--identity-source-repair-csv", default=DEFAULT_IDENTITY_SOURCE_REPAIR_CSV)
    parser.add_argument("--identity-unlock-kit-json", default=DEFAULT_IDENTITY_UNLOCK_KIT_JSON)
    parser.add_argument("--target-clearance-cycle-json", default=DEFAULT_TARGET_CLEARANCE_CYCLE_JSON)
    parser.add_argument("--replacement-decision-preflight-json", default=DEFAULT_REPLACEMENT_DECISION_PREFLIGHT_JSON)
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
