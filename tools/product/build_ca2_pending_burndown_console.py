#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_READINESS_JSON = "runs/ca2_packet_replacement_readiness_current.json"
DEFAULT_DRAFT_JSON = "runs/ca2_negative_reviewer_draft_packet_current.json"
DEFAULT_COMMIT_JSON = "runs/ca2_evidence_closure_commit_packet_current.json"
DEFAULT_OUT_JSON = "runs/ca2_pending_burndown_console_current.json"
DEFAULT_OUT_CSV = "runs/ca2_pending_burndown_console_current.csv"
DEFAULT_OUT_MD = "runs/ca2_pending_burndown_console_current.md"


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
    draft_payload: dict[str, Any],
    commit_payload: dict[str, Any],
) -> dict[str, Any]:
    readiness_s = dict(readiness_payload.get("summary", {}) or {})
    draft_s = dict(draft_payload.get("summary", {}) or {})
    commit_s = dict(commit_payload.get("summary", {}) or {})

    rows: list[dict[str, Any]] = []
    commit_rows = list(commit_payload.get("rows", []) or [])
    draft_rows = list(draft_payload.get("rows", []) or [])

    def _allowed(value: Any) -> str:
        token = str(value).strip().lower()
        return "yes" if token in {"1", "true", "yes"} else "no"

    for idx, row in enumerate(commit_rows, start=1):
        rows.append(
            {
                "console_rank": idx,
                "lane": "confirm_now",
                "priority_rank": idx,
                "packet_step": str(row.get("packet_step", "")).strip(),
                "ligand": str(row.get("ligand", "")).strip(),
                "action_surface": "commit_packet",
                "operator_action": str(row.get("next_required_action", "")).strip(),
                "allowed_now": _allowed(row.get("authoritative_apply_allowed_now", False)),
                "must_keep_blank": str(row.get("must_remain_blank_fields", "")).strip(),
                "key_note": str(row.get("draft_manual_decision_note", "")).strip(),
            }
        )

    start_rank = len(rows)
    for offset, row in enumerate(draft_rows, start=1):
        rows.append(
            {
                "console_rank": start_rank + offset,
                "lane": "review_only",
                "priority_rank": int(str(row.get("day_queue_rank", "999")).strip() or 999),
                "packet_step": str(row.get("packet_step", "")).strip(),
                "ligand": str(row.get("ligand", "")).strip(),
                "action_surface": "reviewer_draft",
                "operator_action": str(row.get("next_required_action", "")).strip(),
                "allowed_now": _allowed(row.get("authoritative_apply_allowed_now", "no")),
                "must_keep_blank": str(row.get("promotion_blocker", "")).strip(),
                "key_note": str(row.get("draft_manual_decision_note", "")).strip(),
            }
        )

    summary = {
        "family": "ca2",
        "ready_row_count": int(readiness_s.get("ready_row_count", 0) or 0),
        "blocked_row_count": int(readiness_s.get("blocked_row_count", 0) or 0),
        "confirm_now_row_count": int(commit_s.get("confirm_now_row_count", 0) or 0),
        "confirmed_commit_count": int(commit_s.get("confirmed_manual_commit_count", 0) or 0),
        "pending_commit_count": int(commit_s.get("pending_manual_commit_count", 0) or 0),
        "review_only_row_count": int(draft_s.get("draft_row_count", 0) or 0),
        "most_common_missing_field": str(readiness_s.get("most_common_missing_field", "")).strip(),
        "closure_mode": str(commit_s.get("closure_mode", "review_only_conflict_closure")).strip(),
        "review_only_conflict_or_gap_only": bool(commit_s.get("review_only_conflict_or_gap_only", True)),
        "direct_conflict_row_count": int(commit_s.get("conflict_review_row_count", 0) or 0),
        "no_direct_negative_source_row_count": int(commit_s.get("no_direct_negative_source_row_count", 0) or 0),
        "authoritative_negative_closure_allowed": bool(commit_s.get("authoritative_negative_closure_allowed", False)),
        "remaining_blank_field": str(commit_s.get("remaining_blank_field", "replacement_reference_binding_kcal_mol")).strip(),
        "next_required_step": "Use confirm-now rows to record reviewer-facing closure fields, but keep the lane in review-only/conflict closure: five rows are direct inhibitor conflicts, one row still lacks a direct CA2-specific negative source, and replacement_reference_binding_kcal_mol must stay blank.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# CA2 Pending Burndown Console",
        "",
        f"- family: `{s['family']}`",
        f"- ready_row_count: `{s['ready_row_count']}`",
        f"- blocked_row_count: `{s['blocked_row_count']}`",
        f"- confirm_now_row_count: `{s['confirm_now_row_count']}`",
        f"- confirmed_commit_count: `{s['confirmed_commit_count']}`",
        f"- pending_commit_count: `{s['pending_commit_count']}`",
        f"- review_only_row_count: `{s['review_only_row_count']}`",
        f"- most_common_missing_field: `{s['most_common_missing_field']}`",
        f"- closure_mode: `{s['closure_mode']}`",
        f"- review_only_conflict_or_gap_only: `{s['review_only_conflict_or_gap_only']}`",
        f"- direct_conflict_row_count: `{s['direct_conflict_row_count']}`",
        f"- no_direct_negative_source_row_count: `{s['no_direct_negative_source_row_count']}`",
        f"- authoritative_negative_closure_allowed: `{s['authoritative_negative_closure_allowed']}`",
        f"- remaining_blank_field: `{s['remaining_blank_field']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Console",
        "",
        "| console_rank | lane | packet_step | ligand | action_surface | operator_action | allowed_now | must_keep_blank |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['console_rank']} | `{row['lane']}` | `{row['packet_step']}` | `{row['ligand']}` | "
            f"`{row['action_surface']}` | `{row['operator_action']}` | `{row['allowed_now']}` | `{row['must_keep_blank']}` |"
        )
    lines.extend(["", "## Notes", ""])
    for row in payload["rows"]:
        lines.append(f"- `{row['packet_step']}`: {row['key_note']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CA2 pending burndown console across confirm-now and review-only rows.")
    parser.add_argument("--readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--draft-json", default=DEFAULT_DRAFT_JSON)
    parser.add_argument("--commit-json", default=DEFAULT_COMMIT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.readiness_json),
        _load_json(args.draft_json),
        _load_json(args.commit_json),
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
