#!/usr/bin/env python3
"""Validate operator-filled refine-tier benchmark work orders before intake apply."""
from __future__ import annotations

import argparse
import csv
import json
import tempfile
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_refine_tier_public_benchmark_readiness import (
    CLAIM_BOUNDARY,
    DEFAULT_INPUT_CSV,
    DEFAULT_OUT_WORK_ORDER_CSV,
    REQUIRED_COLUMNS,
    REFINE_TIER_PUBLIC_BENCHMARK_INTAKE_APPROVAL_TOKEN,
    WORK_ORDER_COLUMNS,
    build_refine_tier_public_benchmark_readiness,
    _row_status,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/refine_tier_public_benchmark_work_order_apply_current.json"
DEFAULT_OUT_CSV = "runs/refine_tier_public_benchmark_intake_candidate_current.csv"
DEFAULT_OUT_MD = "runs/refine_tier_public_benchmark_work_order_apply_current.md"
DEFAULT_READINESS_COMMAND = "python3 tools/product/build_refine_tier_public_benchmark_readiness.py"
DEFAULT_WRITE_INTAKE_COMMAND = (
    "python3 tools/product/apply_refine_tier_public_benchmark_work_order.py "
    f"--write-intake --approval-token {REFINE_TIER_PUBLIC_BENCHMARK_INTAKE_APPROVAL_TOKEN}"
)

PLACEHOLDER_PREFIXES = ("OPERATOR_FILL", "OPERATOR_CONFIRM")


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, Any]], list[str], bool]:
    path = _resolve(path_like)
    if not path.exists():
        return [], [], False
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return [dict(row) for row in reader], list(reader.fieldnames or []), True


def _text(value: Any) -> str:
    return str(value or "").strip()


def _has_placeholder(row: dict[str, Any]) -> bool:
    return any(_text(value).startswith(PLACEHOLDER_PREFIXES) for value in row.values())


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _intake_row_from_work_order(row: dict[str, Any]) -> dict[str, Any]:
    return {column: row.get(column, "") for column in REQUIRED_COLUMNS}


def apply_refine_tier_public_benchmark_work_order(
    *,
    work_order_csv: str | Path = DEFAULT_OUT_WORK_ORDER_CSV,
    out_csv: str | Path = DEFAULT_OUT_CSV,
    target_intake_csv: str | Path = DEFAULT_INPUT_CSV,
    write_intake: bool = False,
    approval_token: str = "",
    max_pose_rmsd_a: float = 2.5,
    min_dockq: float = 0.23,
    min_lddt_pli: float = 0.5,
) -> dict[str, Any]:
    rows, columns, present = _read_csv(work_order_csv)
    missing_work_order_columns = [column for column in WORK_ORDER_COLUMNS if column not in columns] if present else list(WORK_ORDER_COLUMNS)
    intake_rows: list[dict[str, Any]] = []
    row_reports: list[dict[str, Any]] = []
    target_intake_text = str(target_intake_csv)
    benchmark_ids = [_text(row.get("benchmark_id")) for row in rows if _text(row.get("benchmark_id"))]
    duplicate_benchmark_ids = sorted({benchmark_id for benchmark_id in benchmark_ids if benchmark_ids.count(benchmark_id) > 1})

    for idx, row in enumerate(rows):
        intake_row = _intake_row_from_work_order(row)
        placeholder_present = _has_placeholder(intake_row)
        status = _row_status(
            intake_row,
            max_pose_rmsd_a=max_pose_rmsd_a,
            min_dockq=min_dockq,
            min_lddt_pli=min_lddt_pli,
        )
        blockers: list[str] = []
        if placeholder_present:
            blockers.append("operator_placeholders_unfilled")
        if _text(row.get("target_input_csv")) and _text(row.get("target_input_csv")) != target_intake_text:
            blockers.append("target_input_csv_mismatch")
        if _text(row.get("operator_action")) != "append_validated_public_benchmark_row":
            blockers.append("operator_action_unaccepted")
        if _bool(row.get("external_state_mutated")):
            blockers.append("external_state_mutation_declared")
        if _text(row.get("benchmark_id")) in duplicate_benchmark_ids:
            blockers.append("duplicate_benchmark_id")
        if status["blockers"]:
            blockers.extend(str(status["blockers"]).split(";"))
        row_report = {
            "row_index": idx + 1,
            "work_order_id": row.get("work_order_id", ""),
            "row_status": "pass" if not blockers else "blocked",
            "blockers": ";".join(blocker for blocker in blockers if blocker),
            "placeholder_present": placeholder_present,
            "target_input_csv": row.get("target_input_csv", ""),
            **intake_row,
        }
        row_reports.append(row_report)
        if not blockers:
            intake_rows.append(intake_row)

    blockers: list[str] = []
    if not present:
        blockers.append("work_order_csv_missing")
    if missing_work_order_columns:
        blockers.append("work_order_columns_missing:" + ",".join(missing_work_order_columns))
    if not rows:
        blockers.append("work_order_rows_missing")
    blocked_rows = [row for row in row_reports if row["row_status"] != "pass"]
    if blocked_rows:
        blockers.append("blocked_work_order_rows_present")

    candidate_readiness_summary: dict[str, Any] = {}
    if present and rows and not blockers:
        with tempfile.TemporaryDirectory(prefix="refine_tier_public_benchmark_apply_") as tmpdir:
            tmp_csv = Path(tmpdir) / "candidate.csv"
            write_csv_rows(tmp_csv, intake_rows)
            candidate_readiness_summary = build_refine_tier_public_benchmark_readiness(input_csv=tmp_csv)["summary"]
        if not bool(candidate_readiness_summary.get("claim_grade_public_benchmark_ready")):
            blockers.append("candidate_readiness_gate_not_ready")
    approval_token_present = bool(_text(approval_token))
    approval_token_accepted = _text(approval_token) == REFINE_TIER_PUBLIC_BENCHMARK_INTAKE_APPROVAL_TOKEN
    if write_intake and not approval_token_accepted:
        blockers.append("write_intake_approval_token_missing_or_invalid")
    if write_intake and blockers:
        blockers.append("write_intake_blocked_until_work_order_rows_pass")

    ready = bool(present and rows and not blockers)
    candidate_path = _resolve(out_csv)
    candidate_written = False
    intake_written = False
    if ready:
        write_csv_rows(candidate_path, intake_rows)
        candidate_written = True
        if write_intake:
            write_csv_rows(_resolve(target_intake_csv), intake_rows)
            intake_written = True
    if intake_written:
        next_required_step = "Rerun the refine-tier public benchmark readiness builder against the updated tracked intake CSV."
    elif ready:
        next_required_step = "Review the candidate intake CSV, then rerun the apply tool with --write-intake to update the tracked intake CSV."
    elif "candidate_readiness_gate_not_ready" in blockers:
        next_required_step = "Add enough valid fit and holdout/test public benchmark rows for the aggregate readiness gate, then rerun the apply tool."
    elif "write_intake_approval_token_missing_or_invalid" in blockers and not blocked_rows:
        next_required_step = "Rerun the apply tool with the required approval token after candidate readiness is green."
    else:
        next_required_step = "Fill or repair blocked work-order rows, then rerun the apply tool before touching the tracked intake CSV."

    summary = {
        "packet_type": "refine_tier_public_benchmark_work_order_apply",
        "status": (
            "refine_tier_public_benchmark_intake_written"
            if intake_written
            else "refine_tier_public_benchmark_work_order_apply_ready"
            if ready
            else "blocked_refine_tier_public_benchmark_work_order_apply"
        ),
        "apply_ready": ready,
        "work_order_csv": str(work_order_csv),
        "work_order_csv_present": present,
        "work_order_row_count": len(rows),
        "duplicate_benchmark_ids": duplicate_benchmark_ids,
        "duplicate_benchmark_id_count": len(duplicate_benchmark_ids),
        "candidate_intake_csv": str(out_csv),
        "candidate_intake_written": candidate_written,
        "aggregate_readiness_required": True,
        "candidate_readiness_checked": bool(candidate_readiness_summary),
        "candidate_readiness_status": candidate_readiness_summary.get("status", ""),
        "candidate_claim_grade_public_benchmark_ready": bool(
            candidate_readiness_summary.get("claim_grade_public_benchmark_ready", False)
        ),
        "candidate_readiness_blockers": candidate_readiness_summary.get("blockers", []),
        "target_intake_csv": str(target_intake_csv),
        "write_intake_requested": bool(write_intake),
        "approval_token_required": REFINE_TIER_PUBLIC_BENCHMARK_INTAKE_APPROVAL_TOKEN if write_intake else "",
        "approval_token_present": approval_token_present,
        "approval_token_accepted": approval_token_accepted if write_intake else False,
        "intake_written": intake_written,
        "valid_intake_row_count": len(intake_rows),
        "blocked_row_count": len(blocked_rows),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "readiness_command": DEFAULT_READINESS_COMMAND,
        "write_intake_command": DEFAULT_WRITE_INTAKE_COMMAND,
        "next_required_step": next_required_step,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {
        "summary": summary,
        "rows": row_reports,
        "intake_rows": intake_rows,
        "required_columns": REQUIRED_COLUMNS,
        "work_order_columns": WORK_ORDER_COLUMNS,
    }


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Refine Tier Public Benchmark Work Order Apply",
        "",
        f"- status: `{summary['status']}`",
        f"- apply_ready: `{summary['apply_ready']}`",
        f"- work-order rows: `{summary['work_order_row_count']}`",
        f"- valid intake rows: `{summary['valid_intake_row_count']}`",
        f"- blocked rows: `{summary['blocked_row_count']}`",
        f"- candidate_intake_written: `{summary['candidate_intake_written']}`",
        f"- candidate_readiness_checked: `{summary['candidate_readiness_checked']}`",
        f"- candidate_readiness_status: `{summary['candidate_readiness_status']}`",
        f"- intake_written: `{summary['intake_written']}`",
        f"- approval_token_required: `{summary['approval_token_required']}`",
        f"- approval_token_accepted: `{summary['approval_token_accepted']}`",
        f"- blockers: `{summary['blocker_count']}`",
        f"- next_required_step: `{summary['next_required_step']}`",
        "",
        "## Blockers",
    ]
    lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    if not summary["blockers"]:
        lines.append("- none")
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Validate and optionally apply refine-tier public benchmark work-order rows.")
    parser.add_argument("--work-order-csv", default=DEFAULT_OUT_WORK_ORDER_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--target-intake-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--write-intake", action="store_true")
    parser.add_argument("--approval-token", default="")
    args = parser.parse_args(argv)
    payload = apply_refine_tier_public_benchmark_work_order(
        work_order_csv=args.work_order_csv,
        out_csv=args.out_csv,
        target_intake_csv=args.target_intake_csv,
        write_intake=bool(args.write_intake),
        approval_token=args.approval_token,
    )
    _write_json(args.out_json, payload)
    if payload["summary"]["apply_ready"] and not payload["summary"]["candidate_intake_written"]:
        write_csv_rows(_resolve(args.out_csv), payload["intake_rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
