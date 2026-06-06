#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_EXECUTION_HANDOFF_JSON = "runs/execution_handoff_dashboard_current.json"
DEFAULT_RUN_NOW_SAFE_COMMAND_JSON = "runs/run_now_safe_command_packet_current.json"
DEFAULT_SEQUENCE_JSON = "runs/pretest_execution_sequence_note_current.json"
DEFAULT_PARTIAL_HANDOFF_JSON = "runs/partial_authoritative_family_handoff_current.json"
DEFAULT_PARTIAL_REVIEWER_CONSOLE_JSON = "runs/partial_authoritative_reviewer_console_current.json"
DEFAULT_PARTIAL_COMMIT_LAUNCHBOARD_JSON = "runs/partial_authoritative_commit_launchboard_current.json"
DEFAULT_PRIORITY_QUEUE_JSON = "runs/family_manual_review_priority_queue_current.json"
DEFAULT_TRANSPORTER_DAY_PLAN_JSON = "runs/transporter_reviewer_day_plan_current.json"
DEFAULT_TRANSPORTER_OPERATOR_CONSOLE_JSON = "runs/transporter_operator_console_current.json"
DEFAULT_TRANSPORTER_LAUNCHBOARD_JSON = "runs/transporter_manual_review_launchboard_current.json"
DEFAULT_OUT_JSON = "runs/operator_evidence_closure_console_current.json"
DEFAULT_OUT_CSV = "runs/operator_evidence_closure_console_current.csv"
DEFAULT_OUT_MD = "runs/operator_evidence_closure_console_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_payload(
    execution_handoff: dict[str, Any],
    run_now_safe_command: dict[str, Any],
    sequence_note: dict[str, Any],
    partial_handoff: dict[str, Any],
    partial_reviewer_console: dict[str, Any],
    partial_commit_launchboard: dict[str, Any],
    priority_queue: dict[str, Any],
    transporter_day_plan: dict[str, Any],
    transporter_operator_console: dict[str, Any],
    transporter_launchboard: dict[str, Any],
) -> dict[str, Any]:
    exec_s = dict(execution_handoff.get("summary", {}) or {})
    exec_rows = list(execution_handoff.get("rows", []) or [])
    run_now_safe_rows = list(run_now_safe_command.get("rows", []) or [])
    partial_s = dict(partial_handoff.get("summary", {}) or {})
    partial_families = {
        str(row.get("family", "")).strip().lower(): dict(row)
        for row in partial_handoff.get("families", []) or []
        if str(row.get("family", "")).strip()
    }
    ca2_partial = partial_families.get("ca2", {})
    partial_reviewer_s = dict(partial_reviewer_console.get("summary", {}) or {})
    partial_commit_s = dict(partial_commit_launchboard.get("summary", {}) or {})
    partial_rows = list(partial_reviewer_console.get("reviewer_rows", []) or [])
    queue_s = dict(priority_queue.get("summary", {}) or {})
    queue_rows = list(priority_queue.get("rows", []) or [])
    transporter_s = dict(transporter_day_plan.get("summary", {}) or {})
    transporter_rows = list(transporter_operator_console.get("target_rows", []) or [])
    transporter_launchboard_s = dict(transporter_launchboard.get("summary", {}) or {})
    transporter_first_wave_target = str(transporter_launchboard_s.get("first_wave_target", "") or "").strip().lower()
    transporter_phase = str(transporter_launchboard_s.get("current_phase", "") or "").strip()

    run_now_rows = [row for row in exec_rows if row.get("priority_lane") == "run_now"]
    prep_rows = [row for row in exec_rows if row.get("priority_lane") == "prepare_next"]
    manual_rows = [row for row in exec_rows if row.get("priority_lane") == "manual_review_only"]
    run_now_safe_map = {str(row.get("family", "")): dict(row) for row in run_now_safe_rows}

    console_rows: list[dict[str, Any]] = []
    for row in run_now_rows:
        family = str(row.get("family", "") or "")
        safe_row = run_now_safe_map.get(family, {})
        focus = safe_row.get("safe_scope_now", row.get("runtime_scope_now", ""))
        next_action = safe_row.get("primary_handoff_note", row.get("next_required_step", ""))
        if family == "idp":
            focus = row.get("runtime_scope_now", focus)
            next_action = row.get("next_required_step", next_action)
        console_rows.append(
            {
                "console_lane": "run_now",
                "item_id": family,
                "family": family,
                "focus": focus,
                "next_action": next_action,
            }
        )
    for row in partial_rows[:7]:
        console_rows.append(
            {
                "console_lane": "partial_closure",
                "item_id": row.get("packet_step", ""),
                "family": row.get("family", ""),
                "focus": row.get("ligand", ""),
                "next_action": row.get("next_required_action", ""),
            }
        )
    console_rows.append(
        {
            "console_lane": "partial_commit",
            "item_id": "ca2_then_pxr",
            "family": "partial_authoritative",
            "focus": partial_commit_s.get("today_open_now", "runs/partial_authoritative_commit_launchboard_current.md"),
            "next_action": partial_commit_s.get("next_required_step", "Open the partial-authoritative commit launchboard after reviewer triage."),
        }
    )
    for row in queue_rows[:6]:
        console_rows.append(
            {
                "console_lane": "manual_queue",
                "item_id": row.get("item_id", ""),
                "family": row.get("family", ""),
                "focus": row.get("candidate_or_ligand", ""),
                "next_action": row.get("recommended_action", ""),
            }
        )
    for row in transporter_rows:
        target = str(row.get("target", "") or "").strip().lower()
        use_launchboard = bool(transporter_first_wave_target) and target == transporter_first_wave_target
        console_rows.append(
            {
                "console_lane": "transporter_today",
                "item_id": row.get("target", ""),
                "family": "transporter",
                "focus": transporter_launchboard_s.get("today_open_now", row.get("open_first", "")) if use_launchboard else row.get("open_first", ""),
                "next_action": transporter_launchboard_s.get("today_finish_line", row.get("operator_instruction", "")) if use_launchboard else row.get("operator_instruction", ""),
            }
        )

    summary = {
        "run_now_count": len(run_now_rows),
        "prepare_next_count": len(prep_rows),
        "manual_review_only_count": len(manual_rows),
        "partial_handoff_row_count": partial_reviewer_s.get("reviewer_row_count", partial_s.get("handoff_row_count", 0)),
        "ca2_closure_mode": str(ca2_partial.get("closure_scope", "review_only_conflict_or_gap_only")).strip(),
        "ca2_direct_conflict_row_count": int(ca2_partial.get("direct_conflict_rows", 0) or 0),
        "ca2_no_direct_negative_source_row_count": int(ca2_partial.get("no_direct_negative_source_rows", 0) or 0),
        "partial_commit_ready": bool(partial_commit_s),
        "manual_queue_row_count": queue_s.get("queue_row_count", 0),
        "transporter_today_target_count": transporter_launchboard_s.get("target_count", transporter_operator_console.get("summary", {}).get("target_count", transporter_s.get("target_count", 0))),
        "transporter_pending_manual_verdict_count": transporter_s.get("pending_manual_verdict_count", 0),
        "transporter_current_phase": transporter_phase,
        "console_row_count": len(console_rows),
        "next_required_step": (
            "Use this console top-down: stay inside run-now safe scopes, keep CA2 on review-only/conflict closure rather than authoritative negative closure, keep PXR on evidence closure, then work transporter blocker closure with AQP1 first and GLUT1 second."
            if int(transporter_s.get("pending_manual_verdict_count", 0) or 0) == 0
            else "Use this console top-down: stay inside run-now safe scopes, keep CA2 on review-only/conflict closure rather than authoritative negative closure, keep PXR on evidence closure, then work the manual queue with AQP1 first and GLUT1 second."
        ),
    }
    return {"summary": summary, "rows": console_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Operator Evidence Closure Console",
        "",
        f"- run_now_count: `{s['run_now_count']}`",
        f"- prepare_next_count: `{s['prepare_next_count']}`",
        f"- manual_review_only_count: `{s['manual_review_only_count']}`",
        f"- partial_handoff_row_count: `{s['partial_handoff_row_count']}`",
        f"- ca2_closure_mode: `{s['ca2_closure_mode']}`",
        f"- ca2_direct_conflict_row_count: `{s['ca2_direct_conflict_row_count']}`",
        f"- ca2_no_direct_negative_source_row_count: `{s['ca2_no_direct_negative_source_row_count']}`",
        f"- manual_queue_row_count: `{s['manual_queue_row_count']}`",
        f"- transporter_today_target_count: `{s['transporter_today_target_count']}`",
        f"- transporter_pending_manual_verdict_count: `{s['transporter_pending_manual_verdict_count']}`",
        f"- transporter_current_phase: `{s['transporter_current_phase']}`",
        f"- console_row_count: `{s['console_row_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Console",
        "",
        "| console_lane | item_id | family | focus | next_action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['console_lane']}` | `{row['item_id']}` | `{row['family']}` | `{row['focus']}` | {row['next_action']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an operator console across run-now, partial-closure, and manual-review lanes.")
    parser.add_argument("--execution-handoff-json", default=DEFAULT_EXECUTION_HANDOFF_JSON)
    parser.add_argument("--run-now-safe-command-json", default=DEFAULT_RUN_NOW_SAFE_COMMAND_JSON)
    parser.add_argument("--sequence-json", default=DEFAULT_SEQUENCE_JSON)
    parser.add_argument("--partial-handoff-json", default=DEFAULT_PARTIAL_HANDOFF_JSON)
    parser.add_argument("--partial-reviewer-console-json", default=DEFAULT_PARTIAL_REVIEWER_CONSOLE_JSON)
    parser.add_argument("--partial-commit-launchboard-json", default=DEFAULT_PARTIAL_COMMIT_LAUNCHBOARD_JSON)
    parser.add_argument("--priority-queue-json", default=DEFAULT_PRIORITY_QUEUE_JSON)
    parser.add_argument("--transporter-day-plan-json", default=DEFAULT_TRANSPORTER_DAY_PLAN_JSON)
    parser.add_argument("--transporter-operator-console-json", default=DEFAULT_TRANSPORTER_OPERATOR_CONSOLE_JSON)
    parser.add_argument("--transporter-launchboard-json", default=DEFAULT_TRANSPORTER_LAUNCHBOARD_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.execution_handoff_json),
        _load_json(args.run_now_safe_command_json),
        _load_json(args.sequence_json),
        _load_json(args.partial_handoff_json),
        _load_json(args.partial_reviewer_console_json),
        _load_json(args.partial_commit_launchboard_json),
        _load_json(args.priority_queue_json),
        _load_json(args.transporter_day_plan_json),
        _load_json(args.transporter_operator_console_json),
        _load_json(args.transporter_launchboard_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
