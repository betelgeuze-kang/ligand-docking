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


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WORKORDER_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_workorder_current.json"
DEFAULT_OPERATOR_INTAKE_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_operator_intake_current.json"
DEFAULT_NATIVE_CANDIDATE_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_native_candidate_packet_current.json"
)
DEFAULT_OUT_DIR = "casp17/competitive_floor_target_identity_clearance_adjudication"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_adjudication_packet_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_adjudication_packet_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_ADJUDICATION.md"

ADJUDICATION_COLUMNS = [
    "target_id",
    "target_name",
    "adjudication_status",
    "operator_intake_status",
    "candidate_row_count",
    "operator_review_candidate_count",
    "blocked_collision_count",
    "blocked_public_date_count",
    "no_candidate_count",
    "search_prepared_count",
    "replacement_required",
    "manual_native_search_required",
    "safe_to_apply_operator_intake",
    "adjudication_md",
    "blockers",
    "next_action",
]
REVIEW_STATUSES = {"operator_review_required", "review_only_relaxed_match"}
CLAIM_BOUNDARY = (
    "Local CASP17 competitive-floor clearance adjudication only. It consolidates operator-intake and native-candidate "
    "risk signals into target-level next actions. It does not clear no-leak provenance, assert native identity, copy "
    "native files, score native accuracy, mutate operator intake, choose final targets, or submit to CASP."
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


def _slug(value: str, fallback: str = "target") -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("._")
    return slug or fallback


def _target_name(row: dict[str, Any]) -> str:
    return _text(row.get("target_name") or row.get("description") or row.get("protein_name"))


def _group_by_target(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        target_id = _text(row.get("target_id")).upper()
        if target_id:
            grouped[target_id].append(row)
    return grouped


def _operator_intake_by_target(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("target_id")).upper(): row
        for row in _rows(payload)
        if _text(row.get("target_id"))
    }


def _candidate_counts(candidate_rows: list[dict[str, Any]]) -> dict[str, int]:
    statuses = [_text(row.get("candidate_status")) for row in candidate_rows]
    blockers = ",".join(_text(row.get("blockers")) for row in candidate_rows)
    return {
        "candidate_row_count": len(candidate_rows),
        "operator_review_candidate_count": sum(1 for status in statuses if status in REVIEW_STATUSES),
        "blocked_collision_count": sum(1 for status in statuses if status == "blocked_current_target_collision"),
        "blocked_public_date_count": blockers.count("candidate_public_before_target_entry"),
        "no_candidate_count": statuses.count("no_rcsb_candidate_found"),
        "search_prepared_count": statuses.count("search_prepared"),
    }


def _decision(
    *,
    intake_status: str,
    counts: dict[str, int],
) -> tuple[str, list[str], str, str, str]:
    if intake_status == "applied":
        return (
            "operator_intake_applied",
            [],
            "false",
            "false",
            "rerun clearance audit, manifest sync, and promotion",
        )
    if intake_status == "ready_to_apply":
        return (
            "operator_intake_ready_to_apply",
            [],
            "false",
            "false",
            "review operator intake report, then run the clearance cycle with --apply-operator-intake",
        )
    if counts["operator_review_candidate_count"]:
        return (
            "native_candidate_operator_review_required",
            ["operator_no_leak_review_required"],
            "false",
            "false",
            "inspect candidate structure/entity metadata, then create independent no-leak evidence before intake",
        )
    if counts["blocked_collision_count"]:
        return (
            "blocked_current_target_collision",
            ["current_target_collision_blocks_native_candidate"],
            "true",
            "false",
            "replace this clearance target or provide independent operator proof that the candidate is not current-target leakage",
        )
    if counts["no_candidate_count"]:
        return (
            "manual_native_search_required",
            ["rcsb_candidate_missing"],
            "false",
            "true",
            "broaden manual native search, then document local no-leak evidence before intake",
        )
    if counts["search_prepared_count"]:
        return (
            "native_candidate_fetch_required",
            ["native_candidate_search_not_run"],
            "false",
            "true",
            "run native candidate packet with --fetch-rcsb",
        )
    return (
        "awaiting_operator_intake",
        ["operator_intake_required"],
        "false",
        "false",
        "fill native_source_pdb, no_leak_evidence_ref, operator, dates, and provenance controls",
    )


def _write_target_md(
    out_dir: Path,
    row: dict[str, Any],
    candidate_rows: list[dict[str, Any]],
) -> str:
    target_id = _text(row.get("target_id"))
    target_name = _text(row.get("target_name"))
    target_folder = out_dir / f"{target_id}_{_slug(target_name, fallback=target_id)}"
    target_folder.mkdir(parents=True, exist_ok=True)
    path = target_folder / "ADJUDICATION.md"
    lines = [
        f"# {target_id} Clearance Adjudication",
        "",
        f"- target_name: {target_name or '-'}",
        f"- adjudication_status: `{row['adjudication_status']}`",
        f"- operator_intake_status: `{row['operator_intake_status'] or '-'}`",
        f"- replacement_required: `{row['replacement_required']}`",
        f"- manual_native_search_required: `{row['manual_native_search_required']}`",
        f"- safe_to_apply_operator_intake: `{row['safe_to_apply_operator_intake']}`",
        f"- blockers: `{row['blockers'] or '-'}`",
        f"- next_action: {row['next_action'] or '-'}",
        "",
        "## Candidate Signals",
        "",
        "| status | query | pdb | release | collisions | blockers |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for candidate in candidate_rows:
        lines.append(
            f"| `{candidate.get('candidate_status', '')}` | `{candidate.get('query_label', '')}` "
            f"`{candidate.get('query_text', '')}` | `{candidate.get('pdb_id') or '-'}` | "
            f"`{candidate.get('initial_release_date') or '-'}` | `{candidate.get('current_target_collision_ids') or '-'}` | "
            f"`{candidate.get('blockers') or '-'}` |"
        )
    if not candidate_rows:
        lines.append("| - | - | - | - | - | `native_candidate_rows_missing` |")
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    return _artifact(path)


def _adjudicate_row(
    workorder_row: dict[str, Any],
    *,
    intake_by_target: dict[str, dict[str, Any]],
    candidate_by_target: dict[str, list[dict[str, Any]]],
    out_dir: Path,
) -> dict[str, Any]:
    target_id = _text(workorder_row.get("target_id")).upper()
    target_name = _target_name(workorder_row)
    intake_status = _text(intake_by_target.get(target_id, {}).get("intake_status"))
    candidate_rows = candidate_by_target.get(target_id, [])
    counts = _candidate_counts(candidate_rows)
    status, blockers, replacement_required, manual_required, next_action = _decision(
        intake_status=intake_status,
        counts=counts,
    )
    safe_to_apply = "true" if status == "operator_intake_ready_to_apply" else "false"
    row = {
        "target_id": target_id,
        "target_name": target_name,
        "adjudication_status": status,
        "operator_intake_status": intake_status,
        **counts,
        "replacement_required": replacement_required,
        "manual_native_search_required": manual_required,
        "safe_to_apply_operator_intake": safe_to_apply,
        "adjudication_md": "",
        "blockers": ",".join(dict.fromkeys(blockers)),
        "next_action": next_action,
    }
    row["adjudication_md"] = _write_target_md(out_dir, row, candidate_rows)
    return row


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    workorder_payload = _read_json(args.workorder_json)
    operator_intake_payload = _read_json(args.operator_intake_json)
    native_candidate_payload = _read_json(args.native_candidate_json)
    intake_by_target = _operator_intake_by_target(operator_intake_payload)
    candidate_by_target = _group_by_target(_rows(native_candidate_payload))
    out_dir = _resolve(args.out_dir)
    rows = [
        _adjudicate_row(
            workorder_row,
            intake_by_target=intake_by_target,
            candidate_by_target=candidate_by_target,
            out_dir=out_dir,
        )
        for workorder_row in _rows(workorder_payload)
    ]
    statuses = [_text(row.get("adjudication_status")) for row in rows]
    if not rows:
        adjudication_status = "missing_workorders"
    elif "operator_intake_ready_to_apply" in statuses:
        adjudication_status = "operator_intake_ready_to_apply"
    elif "native_candidate_operator_review_required" in statuses:
        adjudication_status = "operator_review_required"
    elif any(status.startswith("blocked_") for status in statuses):
        adjudication_status = "blocked_candidate_risk"
    elif "manual_native_search_required" in statuses:
        adjudication_status = "manual_native_search_required"
    elif "native_candidate_fetch_required" in statuses:
        adjudication_status = "native_candidate_fetch_required"
    elif all(status == "operator_intake_applied" for status in statuses):
        adjudication_status = "operator_intake_applied"
    else:
        adjudication_status = "awaiting_operator_intake"
    first_open = next(
        (row for row in rows if row["adjudication_status"] not in {"operator_intake_applied"}),
        rows[0] if rows else {},
    )
    summary = {
        "packet_type": "casp17_competitive_floor_target_identity_clearance_adjudication_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "adjudication_packet_status": adjudication_status,
        "workorder_json": _artifact(args.workorder_json),
        "operator_intake_json": _artifact(args.operator_intake_json),
        "native_candidate_json": _artifact(args.native_candidate_json),
        "native_candidate_status": _text(_summary(native_candidate_payload).get("native_candidate_packet_status")),
        "out_dir": _artifact(args.out_dir),
        "target_count": len(rows),
        "operator_intake_ready_count": statuses.count("operator_intake_ready_to_apply"),
        "operator_intake_applied_count": statuses.count("operator_intake_applied"),
        "operator_review_required_count": statuses.count("native_candidate_operator_review_required"),
        "blocked_current_target_collision_count": statuses.count("blocked_current_target_collision"),
        "manual_native_search_required_count": statuses.count("manual_native_search_required"),
        "native_candidate_fetch_required_count": statuses.count("native_candidate_fetch_required"),
        "replacement_required_count": sum(1 for row in rows if row["replacement_required"] == "true"),
        "safe_to_apply_operator_intake_count": sum(1 for row in rows if row["safe_to_apply_operator_intake"] == "true"),
        "adjudication_md_count": sum(1 for row in rows if row["adjudication_md"]),
        "first_open_target_id": _text(first_open.get("target_id")),
        "first_open_status": _text(first_open.get("adjudication_status")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Target Identity Clearance Adjudication",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- adjudication_packet_status: `{summary['adjudication_packet_status']}`",
        f"- targets: `{summary['target_count']}`",
        f"- ready/applied/operator-review/collision/manual/fetch: `{summary['operator_intake_ready_count']}/{summary['operator_intake_applied_count']}/{summary['operator_review_required_count']}/{summary['blocked_current_target_collision_count']}/{summary['manual_native_search_required_count']}/{summary['native_candidate_fetch_required_count']}`",
        f"- replacement_required/safe_to_apply/md: `{summary['replacement_required_count']}/{summary['safe_to_apply_operator_intake_count']}/{summary['adjudication_md_count']}`",
        f"- first open: `{summary['first_open_target_id'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- first next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Target Decisions",
        "",
        "| target | status | intake | candidates | collision | manual | replacement | next action |",
        "| --- | --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['adjudication_status']}` | `{row['operator_intake_status'] or '-'}` | "
            f"{row['candidate_row_count']} | {row['blocked_collision_count']} | `{row['manual_native_search_required']}` | "
            f"`{row['replacement_required']}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | `missing_workorders` | - | 0 | 0 | `false` | `false` | rebuild clearance workorders |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ADJUDICATION_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 target identity clearance adjudication packet.")
    parser.add_argument("--workorder-json", default=DEFAULT_WORKORDER_JSON)
    parser.add_argument("--operator-intake-json", default=DEFAULT_OPERATOR_INTAKE_JSON)
    parser.add_argument("--native-candidate-json", default=DEFAULT_NATIVE_CANDIDATE_JSON)
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
