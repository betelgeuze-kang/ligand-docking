#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CANDIDATE_BOARD_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_local_candidate_board_current.json"
)
DEFAULT_FEASIBILITY_BOARD_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_current.json"
)
DEFAULT_ROUTE_DIR = "casp17/historical_seed_strict_blind_replacement_first_slot_source_route_board"
DEFAULT_OUT_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_source_route_board_current.json"
)
DEFAULT_OUT_CSV = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_source_route_board_current.csv"
)
DEFAULT_OUT_MD = (
    "casp17/CASP17_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_FIRST_SLOT_SOURCE_ROUTE_BOARD.md"
)

ROW_COLUMNS = [
    "route_id",
    "target_id",
    "scope",
    "required_scope",
    "in_first_slot_scope",
    "candidate_status",
    "route_status",
    "allowed_for_first_slot",
    "prediction_created_at",
    "native_release_date",
    "post_native_action_count",
    "external_required_action_count",
    "source_required_action_count",
    "evidence_required_action_count",
    "date_required_action_count",
    "primary_blocked_action_count",
    "first_blocker",
    "route_folder",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local CASP17 first-slot source-route board only. It decides whether local candidates can be routed toward the "
    "first required strict-blind monomer slot, or must be replaced/sourced from an external pre-native prediction "
    "archive. It does not fetch sources, create evidence, approve candidates, compute metrics, or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    if not str(path_like):
        return ""
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


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _safe_name(index: int, target_id: str) -> str:
    return f"{index:02d}_{target_id.lower().replace('/', '_').replace(' ', '_')}"


def _route_folder(route_dir: str | Path, index: int, target_id: str) -> Path:
    return _resolve(route_dir) / _safe_name(index, target_id)


def _count(rows: list[dict[str, Any]], status: str) -> int:
    return sum(1 for row in rows if _text(row.get("feasibility_status")) == status)


def _first(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return rows[0] if rows else {}


def _route_status(candidate: dict[str, Any], feasibility_rows: list[dict[str, Any]], required_scope: str) -> tuple[str, str, str]:
    scope = _text(candidate.get("scope"))
    in_scope = str(scope == required_scope)
    if scope != required_scope:
        return (
            "out_of_scope_context_only_for_first_slot",
            "False",
            "do not promote to this monomer slot; keep as complex-lane context after source authority is repaired",
        )
    if any(_text(row.get("next_route")) == "source_external_pre_native_prediction_or_replace_candidate" for row in feasibility_rows):
        return (
            "in_scope_current_candidate_disqualified_post_native",
            "False",
            "source a pre-native prediction archive for this monomer or replace with a strict-blind monomer candidate",
        )
    if any(_text(row.get("feasibility_status")) == "repairable_current_prediction_pre_native" for row in feasibility_rows):
        return (
            "in_scope_pre_native_candidate_needs_primary_repairs",
            "False",
            "complete chronology, no-leak, ablation, calibration, and operator clearance before promotion",
        )
    if any(_text(row.get("feasibility_status")).startswith("repairable") for row in feasibility_rows):
        return (
            "in_scope_operator_repair_required",
            "False",
            "complete remaining source/evidence repairs and rerun feasibility before promotion",
        )
    return (
        "in_scope_no_actionable_route",
        "False",
        "replace this candidate with a strict-blind monomer candidate carrying pre-native prediction evidence",
    )


def _build_rows(candidate_rows: list[dict[str, Any]], feasibility_rows: list[dict[str, Any]], required_scope: str, route_dir: str | Path) -> list[dict[str, Any]]:
    feasibility_by_target: dict[str, list[dict[str, Any]]] = {}
    for row in feasibility_rows:
        feasibility_by_target.setdefault(_text(row.get("target_id")), []).append(row)

    rows: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidate_rows, start=1):
        target_id = _text(candidate.get("target_id"))
        target_feasibility_rows = feasibility_by_target.get(target_id, [])
        route_status, allowed, next_action = _route_status(candidate, target_feasibility_rows, required_scope)
        first = _first(target_feasibility_rows)
        folder = _route_folder(route_dir, index, target_id)
        rows.append(
            {
                "route_id": f"first_slot_source_route_{index:03d}",
                "target_id": target_id,
                "scope": _text(candidate.get("scope")),
                "required_scope": required_scope,
                "in_first_slot_scope": str(_text(candidate.get("scope")) == required_scope),
                "candidate_status": _text(candidate.get("candidate_status")),
                "route_status": route_status,
                "allowed_for_first_slot": allowed,
                "prediction_created_at": _text(candidate.get("prediction_created_at")),
                "native_release_date": _text(candidate.get("native_release_date")),
                "post_native_action_count": _count(target_feasibility_rows, "not_repairable_with_current_prediction"),
                "external_required_action_count": sum(
                    1
                    for row in target_feasibility_rows
                    if _text(row.get("next_route")) == "source_external_pre_native_prediction_or_replace_candidate"
                ),
                "source_required_action_count": _count(target_feasibility_rows, "repairable_operator_source_required"),
                "evidence_required_action_count": _count(target_feasibility_rows, "repairable_operator_evidence_required"),
                "date_required_action_count": _count(target_feasibility_rows, "needs_chronology_date_evidence"),
                "primary_blocked_action_count": _count(target_feasibility_rows, "blocked_by_primary_repairs"),
                "first_blocker": _text(first.get("blocker")),
                "route_folder": _artifact(folder),
                "next_action": next_action,
            }
        )
    return rows


def _overall_status(rows: list[dict[str, Any]], input_blockers: list[str]) -> str:
    if input_blockers:
        return "blocked_missing_input"
    in_scope_rows = [row for row in rows if row["in_first_slot_scope"] == "True"]
    if any(row["allowed_for_first_slot"] == "True" for row in in_scope_rows):
        return "first_slot_source_route_ready"
    if any(row["route_status"] == "in_scope_current_candidate_disqualified_post_native" for row in in_scope_rows):
        return "first_slot_requires_pre_native_monomer_source_or_replacement"
    if in_scope_rows:
        return "first_slot_requires_operator_repairs_or_replacement"
    return "first_slot_no_in_scope_candidates"


def _build_summary(
    args: argparse.Namespace,
    rows: list[dict[str, Any]],
    candidate_payload: dict[str, Any],
    feasibility_payload: dict[str, Any],
    input_blockers: list[str],
) -> dict[str, Any]:
    in_scope = [row for row in rows if row["in_first_slot_scope"] == "True"]
    out_scope = [row for row in rows if row["in_first_slot_scope"] != "True"]
    external = [row for row in in_scope if row["route_status"] == "in_scope_current_candidate_disqualified_post_native"]
    first_external = _first(external)
    first_out_scope = _first(out_scope)
    return {
        "packet_type": "casp17_historical_seed_strict_blind_replacement_first_slot_source_route_board",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "strict_blind_replacement_first_slot_source_route_board_status": _overall_status(rows, input_blockers),
        "candidate_board_json": _artifact(args.candidate_board_json),
        "feasibility_board_json": _artifact(args.feasibility_board_json),
        "candidate_board_status": _text(
            _summary(candidate_payload).get("strict_blind_replacement_first_slot_local_candidate_board_status")
        ),
        "feasibility_board_status": _text(
            _summary(feasibility_payload).get("strict_blind_replacement_first_slot_repair_feasibility_board_status")
        ),
        "required_benchmark_id": _text(_summary(candidate_payload).get("required_benchmark_id")),
        "required_target_id": _text(_summary(candidate_payload).get("required_target_id")),
        "required_scope": _text(_summary(candidate_payload).get("scope")) or "monomer",
        "route_count": len(rows),
        "in_scope_route_count": len(in_scope),
        "out_of_scope_route_count": len(out_scope),
        "allowed_for_first_slot_count": sum(1 for row in in_scope if row["allowed_for_first_slot"] == "True"),
        "in_scope_external_required_count": len(external),
        "in_scope_post_native_action_count": sum(_int(row["post_native_action_count"]) for row in in_scope),
        "in_scope_external_action_count": sum(_int(row["external_required_action_count"]) for row in in_scope),
        "out_of_scope_source_required_count": sum(1 for row in out_scope if _int(row["source_required_action_count"]) > 0),
        "out_of_scope_date_required_count": sum(1 for row in out_scope if _int(row["date_required_action_count"]) > 0),
        "first_external_route_id": _text(first_external.get("route_id")),
        "first_external_target_id": _text(first_external.get("target_id")),
        "first_external_prediction_created_at": _text(first_external.get("prediction_created_at")),
        "first_external_native_release_date": _text(first_external.get("native_release_date")),
        "first_external_next_action": _text(first_external.get("next_action")),
        "first_out_of_scope_target_id": _text(first_out_scope.get("target_id")),
        "route_dir": _artifact(args.route_dir),
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    candidate_payload = _read_json(args.candidate_board_json)
    feasibility_payload = _read_json(args.feasibility_board_json)
    input_blockers = []
    if not _resolve(args.candidate_board_json).exists():
        input_blockers.append("first_slot_local_candidate_board_json_missing")
    if not _resolve(args.feasibility_board_json).exists():
        input_blockers.append("first_slot_repair_feasibility_board_json_missing")
    required_scope = _text(_summary(candidate_payload).get("scope")) or "monomer"
    rows = _build_rows(_rows(candidate_payload), _rows(feasibility_payload), required_scope, args.route_dir)
    summary = _build_summary(args, rows, candidate_payload, feasibility_payload, input_blockers)
    return {"summary": summary, "rows": rows}


def _write_route_md(row: dict[str, Any]) -> None:
    lines = [
        f"# {row['target_id']} First-Slot Source Route",
        "",
        f"- route: `{row['route_id']}`",
        f"- status: `{row['route_status']}`",
        f"- scope/required: `{row['scope'] or '-'}` `{row['required_scope'] or '-'}`",
        f"- allowed for first slot: `{row['allowed_for_first_slot']}`",
        f"- prediction/native dates: `{row['prediction_created_at'] or '-'}` `{row['native_release_date'] or '-'}`",
        f"- external/source/evidence/date/primary actions: `{row['external_required_action_count']}/{row['source_required_action_count']}/{row['evidence_required_action_count']}/{row['date_required_action_count']}/{row['primary_blocked_action_count']}`",
        f"- next action: {row['next_action']}",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    folder = _resolve(row["route_folder"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SOURCE_ROUTE.md").write_text("\n".join(lines), encoding="utf-8")
    _write_csv(folder / "source_route.csv", [row], ROW_COLUMNS)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Strict-Blind Replacement First Slot Source Route Board",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['strict_blind_replacement_first_slot_source_route_board_status']}`",
        f"- required benchmark/target/scope: `{summary['required_benchmark_id'] or '-'}` `{summary['required_target_id'] or '-'}` `{summary['required_scope'] or '-'}`",
        f"- routes in-scope/out-of-scope/total: `{summary['in_scope_route_count']}/{summary['out_of_scope_route_count']}/{summary['route_count']}`",
        f"- allowed for first slot: `{summary['allowed_for_first_slot_count']}`",
        f"- in-scope external targets/actions: `{summary['in_scope_external_required_count']}/{summary['in_scope_external_action_count']}`",
        f"- out-of-scope source/date repair targets: `{summary['out_of_scope_source_required_count']}/{summary['out_of_scope_date_required_count']}`",
        f"- first external target: `{summary['first_external_target_id'] or '-'}` prediction/native `{summary['first_external_prediction_created_at'] or '-'}` `{summary['first_external_native_release_date'] or '-'}`",
        f"- next action: {summary['first_external_next_action'] or '-'}",
        "",
        "## Routes",
        "",
        "| route | target | scope | status | allowed | prediction | native | next action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['route_id']}` | `{row['target_id']}` | `{row['scope']}` | `{row['route_status']}` | "
            f"`{row['allowed_for_first_slot']}` | `{row['prediction_created_at'] or '-'}` | "
            f"`{row['native_release_date'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `clear` | - | - | - | rerun local candidate board |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    for row in payload["rows"]:
        _write_route_md(row)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build first-slot source route board.")
    parser.add_argument("--candidate-board-json", default=DEFAULT_CANDIDATE_BOARD_JSON)
    parser.add_argument("--feasibility-board-json", default=DEFAULT_FEASIBILITY_BOARD_JSON)
    parser.add_argument("--route-dir", default=DEFAULT_ROUTE_DIR)
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
