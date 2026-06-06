#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INTAKE_JSON = "casp17/casp17_competitive_floor_evidence_intake_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_row_fill_patch_gate_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_row_fill_patch_gate_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_ROW_FILL_PATCH_GATE.md"

CLAIM_BOUNDARY = (
    "Local competitive-floor row_fill patch gate only. It dry-runs row_fill.csv updates from intake patch "
    "candidates and writes operator review artifacts; it does not mutate row_fill.csv, choose historical targets, "
    "clear no-leak provenance, score native accuracy, fetch native structures, run predictors, or submit to CASP."
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


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


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
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["dropzone_id", "template_column", "patch_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


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


def _row_fill_cache(intake_rows: list[dict[str, Any]]) -> dict[str, tuple[dict[str, str], list[str]]]:
    cache: dict[str, tuple[dict[str, str], list[str]]] = {}
    for row in intake_rows:
        row_fill = _text(row.get("source_row_fill_csv"))
        if row_fill and row_fill not in cache:
            rows, blockers = _read_csv(row_fill)
            cache[row_fill] = (rows[0] if rows else {}, blockers)
    return cache


def _batch_folder(row: dict[str, Any]) -> Path:
    row_fill = _text(row.get("source_row_fill_csv"))
    if row_fill:
        return _resolve(row_fill).parent
    patch_csv = _text(row.get("patch_candidate_csv"))
    if patch_csv:
        return _resolve(patch_csv).parent
    return ROOT / "casp17" / "competitive_floor_batch_current" / _text(row.get("dropzone_id"))


def _status_for(intake_row: dict[str, Any], row_fill_row: dict[str, str], row_fill_blockers: list[str]) -> tuple[str, str]:
    if row_fill_blockers:
        return "row_fill_blocked", ",".join(row_fill_blockers)
    column = _text(intake_row.get("template_column"))
    current = _text(row_fill_row.get(column)) or _text(intake_row.get("row_fill_value"))
    recommended = _text(intake_row.get("recommended_value"))
    intake_status = _text(intake_row.get("intake_status"))
    if intake_status == "patch_candidate":
        if _contains_placeholder(recommended):
            return "blocked_missing_recommended_value", "recommended_value_required"
        if _contains_placeholder(current):
            return "ready_to_patch", ""
        if current == recommended:
            return "already_applied", ""
        return "conflict_existing_value", "row_fill_value_differs_from_recommended_value"
    if intake_status in {"row_fill_file_present", "field_present_needs_worklist_rerun"}:
        return "already_filled", ""
    if intake_status == "ambiguous_file_candidates":
        return "blocked_ambiguous_candidates", "multiple_candidate_values"
    if intake_status in {"awaiting_dropzone_file", "awaiting_operator_value"}:
        return "awaiting_evidence", intake_status
    if intake_status == "row_fill_blocked":
        return "row_fill_blocked", "row_fill_blocked_by_intake"
    return "awaiting_evidence", intake_status or "intake_status_missing"


def _gate_row(intake_row: dict[str, Any], row_fill_row: dict[str, str], row_fill_blockers: list[str]) -> dict[str, Any]:
    status, blocker = _status_for(intake_row, row_fill_row, row_fill_blockers)
    batch_folder = _batch_folder(intake_row)
    dry_run_csv = batch_folder / "ROW_FILL_PATCH_DRY_RUN.csv"
    dry_run_md = batch_folder / "ROW_FILL_PATCH_DRY_RUN.md"
    column = _text(intake_row.get("template_column"))
    return {
        "dropzone_id": _text(intake_row.get("dropzone_id")),
        "action_rank": _int(intake_row.get("action_rank")),
        "operator_priority": _int(intake_row.get("operator_priority")),
        "row_rank": _int(intake_row.get("row_rank")),
        "benchmark_id": _text(intake_row.get("benchmark_id")),
        "target_id": _text(intake_row.get("target_id")),
        "scope": _text(intake_row.get("scope")),
        "evidence_class": _text(intake_row.get("evidence_class")),
        "template_column": column,
        "source_row_fill_csv": _text(intake_row.get("source_row_fill_csv")),
        "current_value": _text(row_fill_row.get(column)) or _text(intake_row.get("row_fill_value")),
        "recommended_value": _text(intake_row.get("recommended_value")),
        "intake_status": _text(intake_row.get("intake_status")),
        "patch_status": status,
        "blocker": blocker,
        "dry_run_csv": _artifact(dry_run_csv),
        "dry_run_md": _artifact(dry_run_md),
        "next_action": _next_action(status, column),
    }


def _next_action(status: str, column: str) -> str:
    if status == "ready_to_patch":
        return f"review recommended_value, then copy it into {column} in row_fill.csv and rerun status/worklist"
    if status == "already_applied":
        return "rerun row-fill status and worklist to close this action"
    if status == "already_filled":
        return "rerun row-fill status and worklist to validate the existing value"
    if status == "conflict_existing_value":
        return f"resolve the row_fill.csv {column} value versus the recommended_value before patching"
    if status == "blocked_ambiguous_candidates":
        return "reduce the candidate set to one cleared value or update row_fill.csv manually"
    if status == "row_fill_blocked":
        return "repair row_fill.csv before applying any patch candidates"
    if status == "blocked_missing_recommended_value":
        return "regenerate intake after placing evidence or clearing value-ledger fields"
    return "provide the missing cleared evidence, then rerun intake and this patch gate"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    intake_payload = _read_json(args.intake_json)
    intake_summary = _summary(intake_payload)
    intake_rows = _rows(intake_payload)
    row_cache = _row_fill_cache(intake_rows)
    gate_rows: list[dict[str, Any]] = []
    for row in intake_rows:
        row_fill = _text(row.get("source_row_fill_csv"))
        row_fill_row, blockers = row_cache.get(row_fill, ({}, ["row_fill_csv_missing"]))
        gate_rows.append(_gate_row(row, row_fill_row, blockers))
    by_status = defaultdict(int)
    row_ids: set[str] = set()
    rows_with_ready: set[str] = set()
    rows_with_blockers: set[str] = set()
    for row in gate_rows:
        status = str(row["patch_status"])
        by_status[status] += 1
        dropzone_id = str(row["dropzone_id"])
        if dropzone_id:
            row_ids.add(dropzone_id)
        if status == "ready_to_patch":
            rows_with_ready.add(dropzone_id)
        if status.startswith("blocked") or status in {"conflict_existing_value", "row_fill_blocked"}:
            rows_with_blockers.add(dropzone_id)
    first_open = next((row for row in gate_rows if row["patch_status"] != "already_applied"), gate_rows[0] if gate_rows else {})
    ready_row_count = len(rows_with_ready - rows_with_blockers)
    summary = {
        "packet_type": "casp17_competitive_floor_row_fill_patch_gate",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "patch_gate_status": _patch_gate_status(gate_rows, by_status),
        "intake_json": _artifact(args.intake_json),
        "intake_status": _text(intake_summary.get("intake_status")),
        "row_count": len(row_ids),
        "action_count": len(gate_rows),
        "ready_to_patch_count": by_status["ready_to_patch"],
        "ready_row_count": ready_row_count,
        "already_applied_count": by_status["already_applied"],
        "already_filled_count": by_status["already_filled"],
        "awaiting_evidence_count": by_status["awaiting_evidence"],
        "conflict_count": by_status["conflict_existing_value"],
        "blocked_count": (
            by_status["row_fill_blocked"]
            + by_status["blocked_ambiguous_candidates"]
            + by_status["blocked_missing_recommended_value"]
        ),
        "first_open_dropzone_id": _text(first_open.get("dropzone_id")),
        "first_open_column": _text(first_open.get("template_column")),
        "first_open_status": _text(first_open.get("patch_status")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": gate_rows}


def _patch_gate_status(rows: list[dict[str, Any]], by_status: dict[str, int]) -> str:
    if not rows:
        return "ready"
    if by_status["conflict_existing_value"] or by_status["row_fill_blocked"] or by_status["blocked_ambiguous_candidates"]:
        return "blocked"
    if by_status["ready_to_patch"]:
        return "ready_for_operator_patch"
    if by_status["awaiting_evidence"] or by_status["blocked_missing_recommended_value"]:
        return "awaiting_evidence"
    return "ready"


def _write_dry_runs(payload: dict[str, Any]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in payload["rows"]:
        grouped[_text(row.get("dropzone_id"))].append(row)
    for dropzone_id, rows in grouped.items():
        if not dropzone_id or not rows:
            continue
        rows.sort(key=lambda item: int(item["action_rank"]))
        dry_run_csv = _resolve(rows[0]["dry_run_csv"])
        dry_run_md = _resolve(rows[0]["dry_run_md"])
        _write_csv(dry_run_csv, rows)
        lines = [
            "# CASP17 Competitive-Floor Row Fill Patch Dry Run",
            "",
            f"- dropzone_id: `{dropzone_id}`",
            f"- row_fill_csv: `{rows[0]['source_row_fill_csv']}`",
            f"- dry_run_csv: `{_artifact(dry_run_csv)}`",
            f"- action count: `{len(rows)}`",
            "",
            "| rank | class | column | status | current | recommended | next action |",
            "| ---: | --- | --- | --- | --- | --- | --- |",
        ]
        for row in rows:
            lines.append(
                f"| {row['action_rank']} | `{row['evidence_class']}` | `{row['template_column']}` | "
                f"`{row['patch_status']}` | `{row['current_value'] or '-'}` | "
                f"`{row['recommended_value'] or '-'}` | {row['next_action']} |"
            )
        lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
        dry_run_md.parent.mkdir(parents=True, exist_ok=True)
        dry_run_md.write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Row Fill Patch Gate",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- patch_gate_status: `{summary['patch_gate_status']}`",
        f"- rows/actions: `{summary['row_count']}/{summary['action_count']}`",
        f"- ready_to_patch: `{summary['ready_to_patch_count']}` rows `{summary['ready_row_count']}`",
        f"- already applied/filled: `{summary['already_applied_count']}/{summary['already_filled_count']}`",
        f"- awaiting_evidence: `{summary['awaiting_evidence_count']}`",
        f"- conflicts/blocked: `{summary['conflict_count']}/{summary['blocked_count']}`",
        f"- first open: `{summary['first_open_dropzone_id'] or '-'}` `{summary['first_open_column'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Patch Gate Rows",
        "",
        "| rank | dropzone | class | column | status | current | recommended | next action |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['action_rank']} | `{row['dropzone_id']}` | `{row['evidence_class']}` | "
            f"`{row['template_column']}` | `{row['patch_status']}` | `{row['current_value'] or '-'}` | "
            f"`{row['recommended_value'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `ready` | - | - | - | - | no patch gate rows |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    if args.write_dry_runs:
        _write_dry_runs(payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-run row_fill.csv patch candidates from CASP17 evidence intake.")
    parser.add_argument("--intake-json", default=DEFAULT_INTAKE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--write-dry-runs", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
