#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CHECKLIST_JSON = "runs/transporter_donor_policy_reopen_checklist_current.json"
DEFAULT_DASHBOARD_JSON = "runs/transporter_manual_review_dashboard_current.json"
DEFAULT_BINDER_DAY_PLAN_JSON = "runs/transporter_reviewer_day_plan_current.json"
DEFAULT_NEGATIVE_DAY_PLAN_JSON = "runs/transporter_negative_reviewer_day_plan_current.json"
DEFAULT_OUT_JSON = "runs/transporter_donor_policy_blocker_packet_current.json"
DEFAULT_OUT_CSV = "runs/transporter_donor_policy_blocker_packet_current.csv"
DEFAULT_OUT_MD = "runs/transporter_donor_policy_blocker_packet_current.md"


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


def _binder_focus_lookup(day_plan_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("target_id", "")).strip(): dict(row)
        for row in day_plan_payload.get("review_rows", [])
        if str(row.get("target_id", "")).strip()
    }


def _negative_focus_lookup(day_plan_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in day_plan_payload.get("target_rows", []):
        target_id = str(row.get("target_id", "")).strip()
        if target_id:
            lookup[target_id] = dict(row)
    return lookup


def build_payload(
    *,
    checklist_payload: dict[str, Any],
    dashboard_payload: dict[str, Any],
    binder_day_plan_payload: dict[str, Any],
    negative_day_plan_payload: dict[str, Any],
) -> dict[str, Any]:
    binder_pending_manual_verdict_count = int(
        dashboard_payload.get("summary", {}).get("binder_pending_manual_verdict_count", 0) or 0
    )
    binder_completed_manual_verdict_count = int(
        dashboard_payload.get("summary", {}).get("binder_completed_manual_verdict_count", 0) or 0
    )
    binder_seed_row_count = int(
        dashboard_payload.get("summary", {}).get("binder_seed_row_count", 0) or 0
    )
    placeholder_row_count_total = int(
        dashboard_payload.get("summary", {}).get("placeholder_row_count_total", 0) or 0
    )
    binder_focus = _binder_focus_lookup(binder_day_plan_payload)
    negative_focus = _negative_focus_lookup(negative_day_plan_payload)
    dashboard_targets = {
        str(row.get("target_id", "")).strip(): dict(row)
        for row in dashboard_payload.get("target_rows", [])
        if str(row.get("target_id", "")).strip()
    }

    blocker_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(checklist_payload.get("rows", []), start=1):
        check_id = str(row.get("check_id", "")).strip()
        blocker_scope = "family"
        if check_id == "candidate_has_non_placeholder_packet_row":
            blocker_scope = "binder_day_plan"
            unblock_today = (
                "finish binder manual verdicts and reduce placeholder-driven rows"
                if binder_pending_manual_verdict_count > 0
                else "reduce placeholder-driven rows and advance the first non-authoritative seed-row sync path"
            )
        elif check_id == "p0_scaffold_open_count_zero":
            blocker_scope = "target_packet_backlog"
            unblock_today = "burn down AQP1 first, then GLUT1 scaffold-open tasks"
        else:
            blocker_scope = "negative_review_and_promotion_gate"
            unblock_today = "negative review stays review-only; do not treat reviewed negatives as authoritative apply"
        blocker_rows.append(
            {
                "priority_rank": idx,
                "check_id": check_id,
                "status": str(row.get("status", "")).strip(),
                "current_value": str(row.get("current_value", "")).strip(),
                "ready_when": str(row.get("ready_when", "")).strip(),
                "blocker_scope": blocker_scope,
                "unblock_today_action": unblock_today,
            }
        )

    target_rows: list[dict[str, Any]] = []
    for target_id in ["AQP1", "GLUT1"]:
        dash = dashboard_targets.get(target_id, {})
        binder = binder_focus.get(target_id, {})
        negative = negative_focus.get(target_id, {})
        target_rows.append(
            {
                "target_id": target_id,
                "binder_wave_priority": str(binder.get("wave_priority", "")).strip(),
                "binder_pending_manual_verdict_count": int(dash.get("binder_pending_manual_verdict_count", 0) or 0),
                "negative_slot_count": int(dash.get("negative_slot_count", 0) or 0),
                "placeholder_rows": int(dash.get("placeholder_rows", 0) or 0),
                "binder_first_candidate": str(binder.get("first_candidate", "")).strip(),
                "negative_wave_priority": str(negative.get("wave_priority", "")).strip(),
                "local_evidence_status": str(dash.get("local_evidence_status", "")).strip(),
                "target_blocker_line": str(dash.get("next_required_step", "")).strip(),
            }
        )

    summary = {
        "decision_status": str(checklist_payload["summary"].get("decision_status", "")).strip(),
        "scaffold_fit_donor_target": str(checklist_payload["summary"].get("scaffold_fit_donor_target", "")).strip(),
        "reopen_ready": bool(checklist_payload["summary"].get("reopen_ready", False)),
        "blocked_check_count": int(checklist_payload["summary"].get("blocked_check_count", 0)),
        "ready_check_count": int(checklist_payload["summary"].get("ready_check_count", 0)),
        "target_count": int(dashboard_payload["summary"].get("target_count", 0)),
        "current_phase": (
            "manual_verdict_burndown"
            if binder_pending_manual_verdict_count > 0
            else "blocker_closure_seed_row_promotion"
        ),
        "binder_seed_row_count": binder_seed_row_count,
        "binder_pending_manual_verdict_count": binder_pending_manual_verdict_count,
        "binder_completed_manual_verdict_count": binder_completed_manual_verdict_count,
        "negative_slot_count_total": int(dashboard_payload["summary"].get("negative_slot_count_total", 0)),
        "negative_review_row_count": int(dashboard_payload["summary"].get("negative_review_row_count", 0)),
        "placeholder_row_count_total": placeholder_row_count_total,
        "today_first_binder_target": "AQP1",
        "today_second_binder_target": "GLUT1",
        "blocker_packet_ready": True,
        "next_required_step": (
            "Use this packet as the single donor-policy blocker view: finish binder manual verdict work first, treat negative review as review-only only, and keep donor-policy reopen blocked until at least one transporter binder row is no longer placeholder-driven."
            if binder_pending_manual_verdict_count > 0
            else "Use this packet as the single donor-policy blocker view during seed-row blocker closure: keep negative review non-authoritative, reduce placeholder-driven packet rows, and do not reopen donor policy until at least one transporter binder row is no longer placeholder-driven."
        ),
    }
    return {
        "summary": summary,
        "blocker_rows": blocker_rows,
        "target_rows": target_rows,
    }


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Transporter Donor Policy Blocker Packet",
        "",
        f"- decision_status: `{summary['decision_status']}`",
        f"- scaffold_fit_donor_target: `{summary['scaffold_fit_donor_target']}`",
        f"- reopen_ready: `{summary['reopen_ready']}`",
        f"- blocked_check_count: `{summary['blocked_check_count']}`",
        f"- ready_check_count: `{summary['ready_check_count']}`",
        f"- target_count: `{summary['target_count']}`",
        f"- current_phase: `{summary['current_phase']}`",
        f"- binder_seed_row_count: `{summary['binder_seed_row_count']}`",
        f"- binder_pending_manual_verdict_count: `{summary['binder_pending_manual_verdict_count']}`",
        f"- binder_completed_manual_verdict_count: `{summary['binder_completed_manual_verdict_count']}`",
        f"- negative_slot_count_total: `{summary['negative_slot_count_total']}`",
        f"- negative_review_row_count: `{summary['negative_review_row_count']}`",
        f"- placeholder_row_count_total: `{summary['placeholder_row_count_total']}`",
        f"- blocker_packet_ready: `{summary['blocker_packet_ready']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Blocker Checks",
        "",
        "| priority_rank | check_id | status | current_value | blocker_scope | unblock_today_action | ready_when |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["blocker_rows"]:
        lines.append(
            f"| {row['priority_rank']} | `{row['check_id']}` | `{row['status']}` | `{row['current_value']}` | "
            f"`{row['blocker_scope']}` | {row['unblock_today_action']} | {row['ready_when']} |"
        )
    lines.extend(
        [
            "",
            "## Target Blocker Context",
            "",
            "| target_id | binder_wave_priority | binder_pending_manual_verdict_count | negative_slot_count | placeholder_rows | binder_first_candidate | negative_wave_priority | local_evidence_status |",
            "| --- | --- | ---: | ---: | ---: | --- | --- | --- |",
        ]
    )
    for row in payload["target_rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['binder_wave_priority']}` | {row['binder_pending_manual_verdict_count']} | "
            f"{row['negative_slot_count']} | {row['placeholder_rows']} | `{row['binder_first_candidate']}` | `{row['negative_wave_priority']}` | `{row['local_evidence_status']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a single blocker packet for transporter donor-policy reopen status.")
    parser.add_argument("--checklist-json", default=DEFAULT_CHECKLIST_JSON)
    parser.add_argument("--dashboard-json", default=DEFAULT_DASHBOARD_JSON)
    parser.add_argument("--binder-day-plan-json", default=DEFAULT_BINDER_DAY_PLAN_JSON)
    parser.add_argument("--negative-day-plan-json", default=DEFAULT_NEGATIVE_DAY_PLAN_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        checklist_payload=_load_json(args.checklist_json),
        dashboard_payload=_load_json(args.dashboard_json),
        binder_day_plan_payload=_load_json(args.binder_day_plan_json),
        negative_day_plan_payload=_load_json(args.negative_day_plan_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["blocker_rows"])
    _write_md(out_md, payload)


if __name__ == "__main__":
    main()
