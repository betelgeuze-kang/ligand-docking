#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_REVIEW_PACKET_JSON = "runs/ca2_review_only_negative_packet_current.json"
DEFAULT_READINESS_JSON = "runs/ca2_packet_replacement_readiness_current.json"
DEFAULT_NEXT_SLICE_JSON = "runs/ca2_next_verification_slice_current.json"
DEFAULT_NEGATIVE_POLICY_JSON = "runs/family_negative_policy_summary_current.json"
DEFAULT_OUT_JSON = "runs/ca2_negative_review_day_plan_current.json"
DEFAULT_OUT_CSV = "runs/ca2_negative_review_day_plan_current.csv"
DEFAULT_OUT_MD = "runs/ca2_negative_review_day_plan_current.md"


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


def _ca2_policy_row(policy_payload: dict[str, Any]) -> dict[str, Any]:
    for row in policy_payload.get("rows", []) or []:
        if str(row.get("family", "")).strip() == "ca2":
            return row
    return {}


def build_payload(
    review_packet_payload: dict[str, Any],
    readiness_payload: dict[str, Any],
    next_slice_payload: dict[str, Any],
    negative_policy_payload: dict[str, Any],
) -> dict[str, Any]:
    readiness_rows = readiness_payload.get("workbook_rows", []) or []
    blocked_core = [
        row
        for row in readiness_rows
        if str(row.get("packet", "")).strip() == "core" and str(row.get("row_ready_for_apply", "")).strip() == "no"
    ]
    blocked_ood = [
        row
        for row in readiness_rows
        if str(row.get("packet", "")).strip() == "ood" and str(row.get("row_ready_for_apply", "")).strip() == "no"
    ]
    ca2_policy = _ca2_policy_row(negative_policy_payload)

    rows: list[dict[str, Any]] = []
    for row in review_packet_payload.get("rows", []) or []:
        priority_rank = int(row.get("priority_rank", 999))
        review_bucket = str(row.get("operator_review_bucket", "")).strip()
        if priority_rank <= 6:
            day_block = "morning_core_review"
        else:
            day_block = "afternoon_ood_review"
        if review_bucket == "conflict_review":
            day_block = "first_conflict_check"
        rows.append(
            {
                "day_block": day_block,
                "priority_rank": str(row.get("priority_rank", "")).strip(),
                "packet": str(row.get("packet", "")).strip(),
                "packet_step": str(row.get("packet_step", "")).strip(),
                "replacement_ligand_id": str(row.get("replacement_ligand_id", "")).strip(),
                "operator_review_bucket": review_bucket,
                "assay_type_honesty": str(row.get("assay_type_honesty", "")).strip(),
                "promotion_blocker": str(row.get("promotion_blocker", "")).strip(),
                "next_required_action": str(row.get("next_required_action", "")).strip(),
                "operator_goal": str(row.get("operator_goal", "")).strip(),
                "stop_if_found": "direct_ca2_specific_negative_evidence" if review_bucket == "standard_review" else "weak_or_conflicting_activity_signal",
                "operator_note_template": str(row.get("operator_note_template", "")).strip(),
            }
        )

    summary = {
        "family": "ca2",
        "review_only_row_count": int(review_packet_payload.get("summary", {}).get("review_only_row_count", 0) or 0),
        "core_review_only_count": int(review_packet_payload.get("summary", {}).get("core_review_only_count", 0) or 0),
        "ood_review_only_count": int(review_packet_payload.get("summary", {}).get("ood_review_only_count", 0) or 0),
        "high_conflict_row_count": int(review_packet_payload.get("summary", {}).get("high_conflict_row_count", 0) or 0),
        "direct_conflict_row_count": int(review_packet_payload.get("summary", {}).get("direct_conflict_row_count", 0) or 0),
        "no_direct_negative_found_count": int(review_packet_payload.get("summary", {}).get("no_direct_negative_found_count", 0) or 0),
        "closure_mode": str(review_packet_payload.get("summary", {}).get("closure_mode", "review_only_conflict_closure")).strip(),
        "authoritative_negative_closure_allowed": False,
        "readiness_blocked_row_count": int(readiness_payload.get("summary", {}).get("blocked_row_count", 0) or 0),
        "blocked_core_count": len(blocked_core),
        "blocked_ood_count": len(blocked_ood),
        "policy_review_only_negative_count": int(ca2_policy.get("review_only_negative_count", 0) or 0),
        "policy_defer_count": int(ca2_policy.get("defer_count", 0) or 0),
        "authoritative_apply_allowed": False,
        "next_required_step": "Work the direct-conflict rows first, keep metformin as the no-direct-source row, and finish the three OOD review-only negatives without injecting proxy values or promoting any CA2 negative-like row to authoritative apply.",
    }
    checklist = [
        "Treat this as review-only/conflict closure, not authoritative negative closure.",
        "Start with the direct-conflict rows first and keep metformin separate as the no-direct-source row.",
        "Keep all CA2 negative-like rows review-only; no proxy ΔG or hard non-binder value should be injected.",
        "Only change course if direct CA2-specific negative evidence is curated; otherwise end the day with the workbook still authoritative-blocked for these six rows.",
    ]
    phase_notes = [
        {
            "phase": "first_conflict_check",
            "goal": "Resolve whether acetaminophen stays review-only because of weak/conflicting CA2 activity.",
        },
        {
            "phase": "morning_core_review",
            "goal": "Review the remaining core negative-like rows without promoting them.",
        },
        {
            "phase": "afternoon_ood_review",
            "goal": "Finish the three OOD negative-like rows with the same review-only policy.",
        },
    ]
    return {"summary": summary, "checklist": checklist, "phase_notes": phase_notes, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# CA2 Negative Review Day Plan",
        "",
        f"- family: `{s['family']}`",
        f"- review_only_row_count: `{s['review_only_row_count']}`",
        f"- core_review_only_count: `{s['core_review_only_count']}`",
        f"- ood_review_only_count: `{s['ood_review_only_count']}`",
        f"- high_conflict_row_count: `{s['high_conflict_row_count']}`",
        f"- direct_conflict_row_count: `{s['direct_conflict_row_count']}`",
        f"- no_direct_negative_found_count: `{s['no_direct_negative_found_count']}`",
        f"- closure_mode: `{s['closure_mode']}`",
        f"- authoritative_negative_closure_allowed: `{s['authoritative_negative_closure_allowed']}`",
        f"- readiness_blocked_row_count: `{s['readiness_blocked_row_count']}`",
        f"- blocked_core_count: `{s['blocked_core_count']}`",
        f"- blocked_ood_count: `{s['blocked_ood_count']}`",
        f"- policy_review_only_negative_count: `{s['policy_review_only_negative_count']}`",
        f"- policy_defer_count: `{s['policy_defer_count']}`",
        f"- authoritative_apply_allowed: `{s['authoritative_apply_allowed']}`",
        "",
        "## Day Checklist",
        "",
    ]
    for item in payload["checklist"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Phase Notes", ""])
    for item in payload["phase_notes"]:
        lines.append(f"- `{item['phase']}`: {item['goal']}")
    lines.extend(
        [
            "",
            "## Review Blocks",
            "",
            "| day_block | priority_rank | packet_step | replacement_ligand_id | operator_review_bucket | next_required_action | stop_if_found |",
            "| --- | ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| `{row['day_block']}` | {row['priority_rank']} | `{row['packet_step']}` | `{row['replacement_ligand_id']}` | "
            f"`{row['operator_review_bucket']}` | `{row['next_required_action']}` | `{row['stop_if_found']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CA2 negative-review day plan from existing review-only packet and readiness artifacts.")
    parser.add_argument("--review-packet-json", default=DEFAULT_REVIEW_PACKET_JSON)
    parser.add_argument("--readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--next-slice-json", default=DEFAULT_NEXT_SLICE_JSON)
    parser.add_argument("--negative-policy-json", default=DEFAULT_NEGATIVE_POLICY_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.review_packet_json),
        _load_json(args.readiness_json),
        _load_json(args.next_slice_json),
        _load_json(args.negative_policy_json),
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
