#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_READINESS_JSON = "runs/pxr_packet_fill_readiness_current.json"
DEFAULT_DRAFT_PACKET_JSON = "runs/pxr_pending_resolution_reviewer_draft_packet_current.json"
DEFAULT_COMMIT_PACKET_JSON = "runs/pxr_pending_resolution_commit_packet_current.json"
DEFAULT_OUT_JSON = "runs/pxr_pending_burndown_console_current.json"
DEFAULT_OUT_CSV = "runs/pxr_pending_burndown_console_current.csv"
DEFAULT_OUT_MD = "runs/pxr_pending_burndown_console_current.md"


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
    readiness_payload: dict[str, Any],
    draft_packet_payload: dict[str, Any],
    commit_packet_payload: dict[str, Any],
) -> dict[str, Any]:
    readiness_s = dict(readiness_payload.get("summary", {}) or {})
    draft_s = dict(draft_packet_payload.get("summary", {}) or {})
    commit_s = dict(commit_packet_payload.get("summary", {}) or {})

    draft_by_step = {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in draft_packet_payload.get("rows", []) or []
        if str(row.get("packet_step", "")).strip()
    }

    rows: list[dict[str, Any]] = []
    for row in commit_packet_payload.get("rows", []) or []:
        packet_step = str(row.get("packet_step", "")).strip()
        draft_row = draft_by_step.get(packet_step, {})
        commit_class = str(row.get("commit_class", "")).strip() or "must_remain_deferred"
        lane = "confirm_now" if commit_class == "confirm_now" else "must_defer"
        rows.append(
            {
                "display_rank": 0,
                "lane": lane,
                "commit_rank": int(row.get("commit_rank", 0) or 0),
                "priority_rank": int(row.get("priority_rank", 999) or 999),
                "plan_phase": str(row.get("plan_phase", "")).strip(),
                "packet_step": packet_step,
                "ligand": str(row.get("ligand", "")).strip(),
                "binder": int(row.get("binder", 0) or 0),
                "resolution_bias": str(row.get("resolution_bias", "")).strip(),
                "next_required_action": str(draft_row.get("next_required_action", "")).strip(),
                "promotion_blocker": str(draft_row.get("promotion_blocker", "")).strip(),
                "draft_note": str(draft_row.get("draft_note", "")).strip(),
                "commit_note": str(row.get("commit_note", "")).strip(),
                "stop_condition": str(row.get("stop_condition", "")).strip(),
            }
        )

    lane_order = {"confirm_now": 0, "must_defer": 1}
    phase_order = {"first_hour": 0, "same_day_followup": 1, "second_pass": 2}
    rows.sort(
        key=lambda row: (
            lane_order.get(str(row["lane"]), 9),
            phase_order.get(str(row["plan_phase"]), 9),
            int(row["priority_rank"]),
            str(row["packet_step"]),
        )
    )
    for idx, row in enumerate(rows, start=1):
        row["display_rank"] = idx

    confirm_now_rows = [row for row in rows if row["lane"] == "confirm_now"]
    must_defer_rows = [row for row in rows if row["lane"] == "must_defer"]
    confirm_now_ligands = ", ".join(str(row.get("ligand", "")).strip() for row in confirm_now_rows if str(row.get("ligand", "")).strip()) or "none"
    must_defer_ligands = ", ".join(str(row.get("ligand", "")).strip() for row in must_defer_rows if str(row.get("ligand", "")).strip()) or "none"

    summary = {
        "family": str(commit_s.get("family", draft_s.get("family", "pxr"))).strip(),
        "target": str(commit_s.get("target", readiness_payload.get("target", ""))).strip(),
        "row_count": len(rows),
        "confirm_now_count": len(confirm_now_rows),
        "must_defer_count": len(must_defer_rows),
        "confirmed_commit_count": int(commit_s.get("confirmed_manual_commit_count", 0) or 0),
        "pending_commit_count": int(commit_s.get("pending_manual_commit_count", 0) or 0),
        "review_only_row_count": int(commit_s.get("review_only_row_count", draft_s.get("review_only_row_count", 0)) or 0),
        "defer_row_count": int(commit_s.get("defer_row_count", draft_s.get("defer_row_count", 0)) or 0),
        "binder_gap_count": int(commit_s.get("binder_gap_count", draft_s.get("binder_gap_count", 0)) or 0),
        "supportive_binder_review_count": int(commit_s.get("supportive_binder_review_count", draft_s.get("supportive_binder_review_count", 0)) or 0),
        "confirmed_binder_quantitative_gap_count": int(
            commit_s.get(
                "confirmed_binder_quantitative_gap_count",
                draft_s.get("confirmed_binder_quantitative_gap_count", 0),
            )
            or 0
        ),
        "ready_for_apply_row_count": int(readiness_s.get("ready_for_apply_row_count", commit_s.get("ready_for_apply_row_count", 0)) or 0),
        "blocked_row_count": int(readiness_s.get("blocked_row_count", commit_s.get("blocked_row_count", 0)) or 0),
        "policy_line": str(commit_s.get("policy_line", draft_s.get("policy_line", ""))).strip(),
        "today_open_now": confirm_now_ligands,
        "after_confirm_keep_deferred": must_defer_ligands,
        "next_required_step": (
            f"Confirm review-only rows now ({confirm_now_ligands}), then leave deferred rows ({must_defer_ligands}) parked until local target-specific human PXR evidence reduces their blockers, and keep literature-supported binder rows deferred until manual confirmation is complete."
            if int(commit_s.get("supportive_binder_review_count", draft_s.get("supportive_binder_review_count", 0)) or 0)
            else f"Confirm review-only rows now ({confirm_now_ligands}), then leave deferred rows ({must_defer_ligands}) parked until local target-specific human PXR evidence reduces their blockers, and keep literature-confirmed binder rows deferred until quantitative provenance is added."
            if int(
                commit_s.get(
                    "confirmed_binder_quantitative_gap_count",
                    draft_s.get("confirmed_binder_quantitative_gap_count", 0),
                )
                or 0
            )
            else f"Confirm review-only rows now ({confirm_now_ligands}), then leave deferred rows ({must_defer_ligands}) parked until local target-specific human PXR evidence reduces their blockers."
        ),
    }
    return {
        "summary": summary,
        "rows": rows,
        "confirm_now_rows": confirm_now_rows,
        "must_defer_rows": must_defer_rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# PXR Pending Burndown Console",
        "",
        f"- family: `{s['family']}`",
        f"- target: `{s['target']}`",
        f"- row_count: `{s['row_count']}`",
        f"- confirm_now_count: `{s['confirm_now_count']}`",
        f"- must_defer_count: `{s['must_defer_count']}`",
        f"- confirmed_commit_count: `{s['confirmed_commit_count']}`",
        f"- pending_commit_count: `{s['pending_commit_count']}`",
        f"- review_only_row_count: `{s['review_only_row_count']}`",
        f"- defer_row_count: `{s['defer_row_count']}`",
        f"- binder_gap_count: `{s['binder_gap_count']}`",
        f"- supportive_binder_review_count: `{s['supportive_binder_review_count']}`",
        f"- confirmed_binder_quantitative_gap_count: `{s['confirmed_binder_quantitative_gap_count']}`",
        f"- ready_for_apply_row_count: `{s['ready_for_apply_row_count']}`",
        f"- blocked_row_count: `{s['blocked_row_count']}`",
        "",
        "## Open Now",
        "",
        f"- Confirm now: `{s['today_open_now']}`",
        f"- Keep deferred after confirm: `{s['after_confirm_keep_deferred']}`",
        "",
        "## Policy Line",
        "",
        f"- {s['policy_line']}",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Confirm Now",
        "",
        "| display_rank | ligand | packet_step | next_required_action | commit_note | stop_condition |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["confirm_now_rows"]:
        lines.append(
            f"| {row['display_rank']} | `{row['ligand']}` | `{row['packet_step']}` | "
            f"`{row['next_required_action']}` | {row['commit_note']} | {row['stop_condition']} |"
        )
    lines.extend(
        [
            "",
            "## Must Defer",
            "",
            "| display_rank | ligand | packet_step | promotion_blocker | commit_note | stop_condition |",
            "| ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["must_defer_rows"]:
        lines.append(
            f"| {row['display_rank']} | `{row['ligand']}` | `{row['packet_step']}` | "
            f"`{row['promotion_blocker']}` | {row['commit_note']} | {row['stop_condition']} |"
        )
    lines.extend(["", "## Full Queue", "", "| display_rank | lane | ligand | packet_step | resolution_bias | plan_phase | priority_rank |", "| ---: | --- | --- | --- | --- | --- | ---: |"])
    for row in payload["rows"]:
        lines.append(
            f"| {row['display_rank']} | `{row['lane']}` | `{row['ligand']}` | `{row['packet_step']}` | "
            f"`{row['resolution_bias']}` | `{row['plan_phase']}` | {row['priority_rank']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a one-screen PXR pending burndown console for confirm-now versus must-defer.")
    parser.add_argument("--readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--draft-packet-json", default=DEFAULT_DRAFT_PACKET_JSON)
    parser.add_argument("--commit-packet-json", default=DEFAULT_COMMIT_PACKET_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.readiness_json),
        _load_json(args.draft_packet_json),
        _load_json(args.commit_packet_json),
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
