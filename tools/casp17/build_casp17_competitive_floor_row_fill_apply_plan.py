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

DEFAULT_PATCH_GATE_JSON = "casp17/casp17_competitive_floor_row_fill_patch_gate_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_row_fill_apply_plan_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_row_fill_apply_plan_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_ROW_FILL_APPLY_PLAN.md"

CLAIM_BOUNDARY = (
    "Local competitive-floor row_fill apply plan only. By default it writes review plans and does not mutate "
    "row_fill.csv. The optional --apply mode applies only ready_to_patch rows with non-placeholder recommendations "
    "and still does not choose targets, clear no-leak provenance, score native accuracy, fetch native structures, "
    "run predictors, or submit to CASP."
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


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], *, fieldnames: list[str] | None = None) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved = list(fieldnames or [])
    for row in rows:
        for key in row:
            if key not in resolved:
                resolved.append(key)
    if not resolved:
        resolved = ["dropzone_id", "template_column", "apply_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=resolved, extrasaction="ignore")
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


def _batch_folder(row: dict[str, Any]) -> Path:
    row_fill = _text(row.get("source_row_fill_csv"))
    if row_fill:
        return _resolve(row_fill).parent
    dry_run_csv = _text(row.get("dry_run_csv"))
    if dry_run_csv:
        return _resolve(dry_run_csv).parent
    return ROOT / "casp17" / "competitive_floor_batch_current" / _text(row.get("dropzone_id"))


def _apply_plan_paths(row: dict[str, Any]) -> tuple[Path, Path]:
    batch_folder = _batch_folder(row)
    return batch_folder / "ROW_FILL_APPLY_PLAN.csv", batch_folder / "ROW_FILL_APPLY_PLAN.md"


def _row_plan_status(row: dict[str, Any]) -> tuple[str, str]:
    patch_status = _text(row.get("patch_status"))
    recommended = _text(row.get("recommended_value"))
    if patch_status == "ready_to_patch":
        if _contains_placeholder(recommended):
            return "blocked_missing_recommended_value", "recommended_value_required"
        return "planned_patch", ""
    if patch_status in {"already_applied", "already_filled"}:
        return "no_op_already_filled", ""
    if patch_status == "conflict_existing_value":
        return "blocked_conflict", "row_fill_value_differs_from_recommended_value"
    if patch_status in {"row_fill_blocked", "blocked_ambiguous_candidates", "blocked_missing_recommended_value"}:
        return "blocked", patch_status
    return "awaiting_evidence", patch_status or "patch_status_missing"


def _plan_row(row: dict[str, Any]) -> dict[str, Any]:
    apply_status, blocker = _row_plan_status(row)
    plan_csv, plan_md = _apply_plan_paths(row)
    return {
        "dropzone_id": _text(row.get("dropzone_id")),
        "action_rank": _int(row.get("action_rank")),
        "operator_priority": _int(row.get("operator_priority")),
        "row_rank": _int(row.get("row_rank")),
        "benchmark_id": _text(row.get("benchmark_id")),
        "target_id": _text(row.get("target_id")),
        "scope": _text(row.get("scope")),
        "evidence_class": _text(row.get("evidence_class")),
        "template_column": _text(row.get("template_column")),
        "source_row_fill_csv": _text(row.get("source_row_fill_csv")),
        "current_value": _text(row.get("current_value")),
        "recommended_value": _text(row.get("recommended_value")),
        "patch_status": _text(row.get("patch_status")),
        "apply_status": apply_status,
        "blocker": blocker,
        "apply_plan_csv": _artifact(plan_csv),
        "apply_plan_md": _artifact(plan_md),
        "next_action": _next_action(apply_status, _text(row.get("template_column"))),
    }


def _next_action(status: str, column: str) -> str:
    if status == "planned_patch":
        return f"run this tool with --apply after review, then rerun row-fill status/worklist for {column}"
    if status == "no_op_already_filled":
        return "rerun row-fill status/worklist to close the already-filled value"
    if status == "blocked_conflict":
        return f"resolve the current {column} value before applying patches"
    if status == "blocked":
        return "resolve patch-gate blockers before applying"
    if status == "blocked_missing_recommended_value":
        return "regenerate intake and patch gate after evidence produces a concrete recommended value"
    return "wait for cleared evidence, then rerun intake and patch gate"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    gate_payload = _read_json(args.patch_gate_json)
    gate_summary = _summary(gate_payload)
    plan_rows = [_plan_row(row) for row in _rows(gate_payload)]
    applied_count = _apply_ready_rows(plan_rows) if args.apply else 0
    by_status = defaultdict(int)
    row_ids: set[str] = set()
    rows_with_plan: set[str] = set()
    rows_with_blockers: set[str] = set()
    for row in plan_rows:
        status = str(row["apply_status"])
        by_status[status] += 1
        dropzone_id = str(row["dropzone_id"])
        if dropzone_id:
            row_ids.add(dropzone_id)
        if status == "planned_patch":
            rows_with_plan.add(dropzone_id)
        if status.startswith("blocked"):
            rows_with_blockers.add(dropzone_id)
    first_open = next((row for row in plan_rows if row["apply_status"] != "no_op_already_filled"), plan_rows[0] if plan_rows else {})
    summary = {
        "packet_type": "casp17_competitive_floor_row_fill_apply_plan",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "apply_plan_status": _apply_plan_status(plan_rows, by_status),
        "patch_gate_json": _artifact(args.patch_gate_json),
        "patch_gate_status": _text(gate_summary.get("patch_gate_status")),
        "apply_mode": "applied" if args.apply else "dry_run",
        "row_count": len(row_ids),
        "action_count": len(plan_rows),
        "planned_patch_count": by_status["planned_patch"],
        "planned_row_count": len(rows_with_plan - rows_with_blockers),
        "applied_count": applied_count,
        "awaiting_evidence_count": by_status["awaiting_evidence"],
        "blocked_count": by_status["blocked"] + by_status["blocked_conflict"] + by_status["blocked_missing_recommended_value"],
        "already_filled_count": by_status["no_op_already_filled"],
        "first_open_dropzone_id": _text(first_open.get("dropzone_id")),
        "first_open_column": _text(first_open.get("template_column")),
        "first_open_status": _text(first_open.get("apply_status")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": plan_rows}


def _apply_plan_status(rows: list[dict[str, Any]], by_status: dict[str, int]) -> str:
    if not rows:
        return "ready"
    if by_status["blocked"] or by_status["blocked_conflict"] or by_status["blocked_missing_recommended_value"]:
        return "blocked"
    if by_status["planned_patch"]:
        return "ready_for_apply"
    if by_status["awaiting_evidence"]:
        return "awaiting_evidence"
    return "ready"


def _apply_ready_rows(plan_rows: list[dict[str, Any]]) -> int:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in plan_rows:
        if row["apply_status"] == "planned_patch":
            grouped[str(row["source_row_fill_csv"])].append(row)
    applied_count = 0
    for row_fill_csv, rows in grouped.items():
        csv_rows, fieldnames, blockers = _read_csv(row_fill_csv)
        if blockers or not csv_rows:
            continue
        row = csv_rows[0]
        for patch in rows:
            column = str(patch["template_column"])
            recommended = str(patch["recommended_value"])
            if column not in fieldnames or _contains_placeholder(recommended):
                continue
            current = _text(row.get(column))
            if _contains_placeholder(current):
                row[column] = recommended
                applied_count += 1
        _write_csv(row_fill_csv, csv_rows, fieldnames=fieldnames)
    return applied_count


def _write_apply_plans(payload: dict[str, Any]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in payload["rows"]:
        grouped[_text(row.get("dropzone_id"))].append(row)
    for dropzone_id, rows in grouped.items():
        if not dropzone_id or not rows:
            continue
        rows.sort(key=lambda row: int(row["action_rank"]))
        plan_csv = _resolve(rows[0]["apply_plan_csv"])
        plan_md = _resolve(rows[0]["apply_plan_md"])
        _write_csv(plan_csv, rows)
        lines = [
            "# CASP17 Competitive-Floor Row Fill Apply Plan",
            "",
            f"- dropzone_id: `{dropzone_id}`",
            f"- row_fill_csv: `{rows[0]['source_row_fill_csv']}`",
            f"- apply_plan_csv: `{_artifact(plan_csv)}`",
            f"- action count: `{len(rows)}`",
            "",
            "| rank | class | column | status | current | recommended | next action |",
            "| ---: | --- | --- | --- | --- | --- | --- |",
        ]
        for row in rows:
            lines.append(
                f"| {row['action_rank']} | `{row['evidence_class']}` | `{row['template_column']}` | "
                f"`{row['apply_status']}` | `{row['current_value'] or '-'}` | "
                f"`{row['recommended_value'] or '-'}` | {row['next_action']} |"
            )
        lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
        plan_md.parent.mkdir(parents=True, exist_ok=True)
        plan_md.write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Row Fill Apply Plan",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- apply_plan_status: `{summary['apply_plan_status']}`",
        f"- apply_mode: `{summary['apply_mode']}`",
        f"- rows/actions: `{summary['row_count']}/{summary['action_count']}`",
        f"- planned patches: `{summary['planned_patch_count']}` rows `{summary['planned_row_count']}`",
        f"- applied_count: `{summary['applied_count']}`",
        f"- awaiting/blocked/already-filled: `{summary['awaiting_evidence_count']}/{summary['blocked_count']}/{summary['already_filled_count']}`",
        f"- first open: `{summary['first_open_dropzone_id'] or '-'}` `{summary['first_open_column'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Apply Plan Rows",
        "",
        "| rank | dropzone | class | column | status | current | recommended | next action |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['action_rank']} | `{row['dropzone_id']}` | `{row['evidence_class']}` | "
            f"`{row['template_column']}` | `{row['apply_status']}` | `{row['current_value'] or '-'}` | "
            f"`{row['recommended_value'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `ready` | - | - | - | - | no apply-plan rows |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    if args.write_apply_plans:
        _write_apply_plans(payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build or apply CASP17 competitive-floor row_fill patch plans.")
    parser.add_argument("--patch-gate-json", default=DEFAULT_PATCH_GATE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--write-apply-plans", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
