#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_QUICKSTART_JSON = "runs/partial_authoritative_quickstart_packet_current.json"
DEFAULT_CA2_WORKBENCH_JSON = "runs/ca2_reviewer_workbench_current.json"
DEFAULT_PXR_WORKBENCH_JSON = "runs/pxr_reviewer_workbench_current.json"
DEFAULT_CA2_DAY_PLAN_JSON = "runs/ca2_evidence_closure_day_plan_current.json"
DEFAULT_PXR_DAY_PLAN_JSON = "runs/pxr_evidence_closure_day_plan_current.json"
DEFAULT_CA2_PENDING_JSON = "runs/ca2_manual_review_queue_current.json"
DEFAULT_PXR_PENDING_JSON = "runs/pxr_pending_resolution_packet_current.json"
DEFAULT_COMMIT_LAUNCHBOARD_JSON = "runs/partial_authoritative_commit_launchboard_current.json"
DEFAULT_OUT_JSON = "runs/partial_authoritative_reviewer_console_current.json"
DEFAULT_OUT_CSV = "runs/partial_authoritative_reviewer_console_current.csv"
DEFAULT_OUT_MD = "runs/partial_authoritative_reviewer_console_current.md"


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


def _family_map(rows: list[dict[str, Any]], key: str = "family") -> dict[str, dict[str, Any]]:
    return {
        str(row.get(key, "")).strip().lower(): dict(row)
        for row in rows
        if str(row.get(key, "")).strip()
    }


def _review_rows_from_ca2(workbench: dict[str, Any], pending: dict[str, Any]) -> list[dict[str, Any]]:
    pending_rows = {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in pending.get("rows", []) or []
    }
    rows: list[dict[str, Any]] = []
    for row in workbench.get("rows", []) or []:
        step = str(row.get("packet_step", "")).strip()
        pend = pending_rows.get(step, {})
        rows.append(
            {
                "family": "ca2",
                "review_rank": row.get("day_queue_rank", ""),
                "review_phase": str(row.get("review_phase", "")).strip(),
                "packet_step": step,
                "ligand": str(row.get("ligand", "")).strip(),
                "review_bucket": str(row.get("operator_review_bucket", "")).strip(),
                "next_required_action": str(row.get("next_required_action", "")).strip(),
                "recommended_resolution": str(row.get("recommended_resolution", "")).strip(),
                "promotion_blocker": str(row.get("promotion_blocker", "")).strip(),
                "authoritative_apply_allowed_now": str(row.get("authoritative_apply_allowed_now", "")).strip(),
                "review_reason": str(pend.get("notes", "")).strip() or str(row.get("operator_note_template", "")).strip(),
            }
        )
    return rows


def _review_rows_from_pxr(workbench: dict[str, Any], pending: dict[str, Any]) -> list[dict[str, Any]]:
    pending_rows = {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in pending.get("rows", []) or []
    }
    rows: list[dict[str, Any]] = []
    for row in workbench.get("rows", []) or []:
        step = str(row.get("packet_step", "")).strip()
        pend = pending_rows.get(step, {})
        rows.append(
            {
                "family": "pxr",
                "review_rank": row.get("priority_rank", ""),
                "review_phase": str(row.get("plan_phase", "")).strip(),
                "packet_step": step,
                "ligand": str(row.get("ligand", "")).strip(),
                "review_bucket": str(row.get("operator_stance", "")).strip(),
                "next_required_action": str(row.get("next_required_action", "")).strip(),
                "recommended_resolution": str(pend.get("disposition", "")).strip() or str(row.get("disposition", "")).strip(),
                "promotion_blocker": str(row.get("promotion_blocker", "")).strip(),
                "authoritative_apply_allowed_now": str(row.get("ready_for_authoritative_apply", "")).strip(),
                "review_reason": str(pend.get("review_reason", "")).strip() or str(row.get("day_goal", "")).strip(),
            }
        )
    return rows


def build_payload(
    quickstart: dict[str, Any],
    ca2_workbench: dict[str, Any],
    pxr_workbench: dict[str, Any],
    ca2_day_plan: dict[str, Any],
    pxr_day_plan: dict[str, Any],
    ca2_pending: dict[str, Any],
    pxr_pending: dict[str, Any],
    commit_launchboard: dict[str, Any],
) -> dict[str, Any]:
    family_rows = _family_map(quickstart.get("family_rows", []) or [])
    ca2_quick = family_rows.get("ca2", {})
    pxr_quick = family_rows.get("pxr", {})
    commit_launchboard_s = dict(commit_launchboard.get("summary", {}) or {})

    reviewer_rows = _review_rows_from_ca2(ca2_workbench, ca2_pending) + _review_rows_from_pxr(pxr_workbench, pxr_pending)

    summary = {
        "family_count": 2,
        "reviewer_row_count": len(reviewer_rows),
        "ca2_today_focus_count": int((ca2_day_plan.get("summary", {}) or {}).get("today_focus_count", 0) or 0),
        "ca2_closure_mode": str((ca2_workbench.get("summary", {}) or {}).get("closure_mode", "review_only_conflict_closure")).strip(),
        "ca2_direct_conflict_row_count": int((ca2_workbench.get("summary", {}) or {}).get("direct_conflict_row_count", 0) or 0),
        "ca2_no_direct_negative_found_count": int((ca2_workbench.get("summary", {}) or {}).get("no_direct_negative_found_count", 0) or 0),
        "ca2_authoritative_negative_closure_allowed": bool((ca2_workbench.get("summary", {}) or {}).get("authoritative_negative_closure_allowed", False)),
        "pxr_first_hour_count": int((pxr_day_plan.get("summary", {}) or {}).get("first_hour_count", 0) or 0),
        "ca2_review_only_row_count": int((ca2_workbench.get("summary", {}) or {}).get("review_only_row_count", 0) or 0),
        "pxr_review_only_row_count": int((pxr_workbench.get("summary", {}) or {}).get("review_only_row_count", 0) or 0),
        "pxr_defer_row_count": int((pxr_workbench.get("summary", {}) or {}).get("defer_row_count", 0) or 0),
        "after_review_artifact": "runs/partial_authoritative_commit_launchboard_current.md",
        "after_review_open_now": commit_launchboard_s.get("today_open_now", ""),
        "next_required_step": "Use this reviewer console after the quickstart packet. Review CA2 core negatives first, keep CA2 in review-only/conflict closure because five rows are direct conflicts and one row lacks a direct negative source, then triage PXR review-only and deferred rows without broadening either family beyond partial-authoritative scope. After reviewer triage, open the partial-authoritative commit launchboard.",
    }

    family_console_rows = [
        {
            "family": "ca2",
            "safe_scope_now": str(ca2_quick.get("safe_scope_now", "")).strip(),
            "ready_rows": ca2_quick.get("ready_rows", 0),
            "blocked_rows": ca2_quick.get("blocked_rows", 0),
            "review_focus": "today_core_review_only_negatives",
            "closure_mode": str((ca2_workbench.get("summary", {}) or {}).get("closure_mode", "review_only_conflict_closure")).strip(),
            "direct_conflict_row_count": int((ca2_workbench.get("summary", {}) or {}).get("direct_conflict_row_count", 0) or 0),
            "no_direct_negative_found_count": int((ca2_workbench.get("summary", {}) or {}).get("no_direct_negative_found_count", 0) or 0),
            "authoritative_negative_closure_allowed": bool((ca2_workbench.get("summary", {}) or {}).get("authoritative_negative_closure_allowed", False)),
            "artifact_check_command": str(ca2_quick.get("artifact_check_command", "")).strip(),
            "guardrail_check_command": str(ca2_quick.get("guardrail_check_command", "")).strip(),
            "reviewer_note": str(ca2_quick.get("operator_note", "")).strip(),
        },
        {
            "family": "pxr",
            "safe_scope_now": str(pxr_quick.get("safe_scope_now", "")).strip(),
            "ready_rows": pxr_quick.get("ready_rows", 0),
            "blocked_rows": pxr_quick.get("blocked_rows", 0),
            "review_focus": "review_only_then_defer_triage",
            "artifact_check_command": str(pxr_quick.get("artifact_check_command", "")).strip(),
            "guardrail_check_command": str(pxr_quick.get("guardrail_check_command", "")).strip(),
            "reviewer_note": str(pxr_quick.get("operator_note", "")).strip(),
        },
    ]

    return {"summary": summary, "family_rows": family_console_rows, "reviewer_rows": reviewer_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Partial-Authoritative Reviewer Console",
        "",
        f"- family_count: `{s['family_count']}`",
        f"- reviewer_row_count: `{s['reviewer_row_count']}`",
        f"- ca2_today_focus_count: `{s['ca2_today_focus_count']}`",
        f"- ca2_closure_mode: `{s['ca2_closure_mode']}`",
        f"- ca2_direct_conflict_row_count: `{s['ca2_direct_conflict_row_count']}`",
        f"- ca2_no_direct_negative_found_count: `{s['ca2_no_direct_negative_found_count']}`",
        f"- ca2_authoritative_negative_closure_allowed: `{s['ca2_authoritative_negative_closure_allowed']}`",
        f"- pxr_first_hour_count: `{s['pxr_first_hour_count']}`",
        f"- ca2_review_only_row_count: `{s['ca2_review_only_row_count']}`",
        f"- pxr_review_only_row_count: `{s['pxr_review_only_row_count']}`",
        f"- pxr_defer_row_count: `{s['pxr_defer_row_count']}`",
        f"- after_review_artifact: `{s['after_review_artifact']}`",
        f"- after_review_open_now: `{s['after_review_open_now']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Family Reviewer Surface",
        "",
        "| family | safe_scope_now | ready_rows | blocked_rows | review_focus | closure_mode | artifact_check_command | guardrail_check_command |",
        "| --- | --- | ---: | ---: | --- | --- | --- | --- |",
    ]
    for row in payload["family_rows"]:
        lines.append(
            f"| `{row['family']}` | `{row['safe_scope_now']}` | {row['ready_rows']} | {row['blocked_rows']} | "
            f"`{row['review_focus']}` | `{row.get('closure_mode','')}` | `{row['artifact_check_command']}` | `{row['guardrail_check_command']}` |"
        )
    lines.extend(["", "## Reviewer Rows", "", "| family | rank | phase | packet_step | ligand | next_required_action | recommended_resolution | promotion_blocker |", "| --- | ---: | --- | --- | --- | --- | --- | --- |"])
    for row in payload["reviewer_rows"]:
        lines.append(
            f"| `{row['family']}` | {row['review_rank']} | `{row['review_phase']}` | `{row['packet_step']}` | `{row['ligand']}` | "
            f"`{row['next_required_action']}` | `{row['recommended_resolution']}` | `{row['promotion_blocker']}` |"
        )
    lines.extend(["", "## Reviewer Notes", ""])
    for row in payload["reviewer_rows"]:
        lines.append(f"- `{row['family']}::{row['packet_step']}`: {row['review_reason']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a reviewer-facing CA2/PXR partial-authoritative console.")
    parser.add_argument("--quickstart-json", default=DEFAULT_QUICKSTART_JSON)
    parser.add_argument("--ca2-workbench-json", default=DEFAULT_CA2_WORKBENCH_JSON)
    parser.add_argument("--pxr-workbench-json", default=DEFAULT_PXR_WORKBENCH_JSON)
    parser.add_argument("--ca2-day-plan-json", default=DEFAULT_CA2_DAY_PLAN_JSON)
    parser.add_argument("--pxr-day-plan-json", default=DEFAULT_PXR_DAY_PLAN_JSON)
    parser.add_argument("--ca2-pending-json", default=DEFAULT_CA2_PENDING_JSON)
    parser.add_argument("--pxr-pending-json", default=DEFAULT_PXR_PENDING_JSON)
    parser.add_argument("--commit-launchboard-json", default=DEFAULT_COMMIT_LAUNCHBOARD_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.quickstart_json),
        _load_json(args.ca2_workbench_json),
        _load_json(args.pxr_workbench_json),
        _load_json(args.ca2_day_plan_json),
        _load_json(args.pxr_day_plan_json),
        _load_json(args.ca2_pending_json),
        _load_json(args.pxr_pending_json),
        _load_json(args.commit_launchboard_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["reviewer_rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
