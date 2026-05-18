#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_READINESS_JSON = "runs/ca2_packet_replacement_readiness_current.json"
DEFAULT_REVIEW_QUEUE_JSON = "runs/ca2_manual_review_queue_current.json"
DEFAULT_NEXT_SLICE_JSON = "runs/ca2_next_verification_slice_current.json"
DEFAULT_CAPTURE_INTAKE_JSON = "runs/ca2_negative_evidence_capture_intake_current.json"
DEFAULT_OUT_JSON = "runs/ca2_evidence_closure_day_plan_current.json"
DEFAULT_OUT_CSV = "runs/ca2_evidence_closure_day_plan_current.csv"
DEFAULT_OUT_MD = "runs/ca2_evidence_closure_day_plan_current.md"


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
    review_queue_payload: dict[str, Any],
    next_slice_payload: dict[str, Any],
    capture_intake_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    capture_intake_payload = capture_intake_payload or {}
    readiness = dict(readiness_payload.get("summary", {}) or {})
    review_summary = dict(review_queue_payload.get("summary", {}) or {})
    next_summary = dict(next_slice_payload.get("summary", {}) or {})
    next_rows = list(next_slice_payload.get("rows", []) or [])
    queue_rows = list(review_queue_payload.get("rows", []) or [])

    today_focus_steps = {
        str(row.get("packet_step", "")).strip()
        for row in next_rows
        if str(row.get("packet_step", "")).strip()
    }

    all_pending_rows: list[dict[str, Any]] = []
    for row in queue_rows:
        packet_step = str(row.get("packet_step", "")).strip()
        all_pending_rows.append(
            {
                "packet_step": packet_step,
                "ligand": str(row.get("replacement_ligand_id", "")).strip(),
                "packet": str(row.get("packet", "")).strip(),
                "priority_rank": int(str(row.get("priority_rank", "999")).strip() or 999),
                "assay_type_honesty": str(row.get("assay_type_honesty", "")).strip(),
                "recommended_resolution": str(row.get("recommended_resolution", "")).strip(),
                "today_focus": "yes" if packet_step in today_focus_steps else "no",
            }
        )

    all_pending_rows.sort(key=lambda row: (0 if row["today_focus"] == "yes" else 1, row["priority_rank"], row["packet_step"]))
    for idx, row in enumerate(all_pending_rows, start=1):
        row["day_queue_rank"] = idx

    today_focus_rows = [row for row in all_pending_rows if row["today_focus"] == "yes"]
    deferred_later_rows = [row for row in all_pending_rows if row["today_focus"] == "no"]

    summary = {
        "family": "ca2",
        "ready_row_count": int(readiness.get("ready_row_count", 0) or 0),
        "blocked_row_count": int(readiness.get("blocked_row_count", 0) or 0),
        "policy_fixed_pending_count": int(review_summary.get("policy_fixed_pending_count", 0) or 0),
        "today_focus_count": len(today_focus_rows),
        "later_queue_count": len(deferred_later_rows),
        "direct_conflict_row_count": int(capture_intake_payload.get("summary", {}).get("direct_conflict_row_count", 0) or 0),
        "no_direct_negative_found_count": int(capture_intake_payload.get("summary", {}).get("no_direct_negative_found_count", 0) or 0),
        "closure_mode": "review_only_conflict_closure",
        "authoritative_negative_closure_allowed": False,
        "most_common_missing_field": str(readiness.get("most_common_missing_field", "")).strip(),
        "day_goal": "Close the three core review-only negatives first, keep OOD negatives parked for later, and preserve the already-ready binder tranche unchanged.",
        "ship_blocker": "replacement_reference_binding_kcal_mol",
        "next_required_step": "Work top-down through the three core negative rows, record manual evidence notes, preserve review-only/conflict closure, and keep OOD negatives out of authoritative apply until direct CA2-specific negative evidence exists.",
        "selected_after_verified_top3": bool(next_summary.get("selected_after_verified_top3", False)),
        "contains_only_core_rows": bool(next_summary.get("contains_only_core_rows", False)),
    }
    return {
        "summary": summary,
        "today_focus_rows": today_focus_rows,
        "later_queue_rows": deferred_later_rows,
        "rows": all_pending_rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# CA2 Evidence Closure Day Plan",
        "",
        f"- family: `{s['family']}`",
        f"- ready_row_count: `{s['ready_row_count']}`",
        f"- blocked_row_count: `{s['blocked_row_count']}`",
        f"- policy_fixed_pending_count: `{s['policy_fixed_pending_count']}`",
        f"- today_focus_count: `{s['today_focus_count']}`",
        f"- later_queue_count: `{s['later_queue_count']}`",
        f"- direct_conflict_row_count: `{s['direct_conflict_row_count']}`",
        f"- no_direct_negative_found_count: `{s['no_direct_negative_found_count']}`",
        f"- closure_mode: `{s['closure_mode']}`",
        f"- authoritative_negative_closure_allowed: `{s['authoritative_negative_closure_allowed']}`",
        f"- most_common_missing_field: `{s['most_common_missing_field']}`",
        "",
        "## Day Goal",
        "",
        f"- {s['day_goal']}",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Today Focus",
        "",
        "| day_queue_rank | packet_step | ligand | assay_type_honesty | recommended_resolution |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for row in payload["today_focus_rows"]:
        lines.append(
            f"| {row['day_queue_rank']} | `{row['packet_step']}` | `{row['ligand']}` | "
            f"`{row['assay_type_honesty']}` | `{row['recommended_resolution']}` |"
        )
    lines.extend(
        [
            "",
            "## Later Queue",
            "",
            "| day_queue_rank | packet_step | ligand | packet | assay_type_honesty | recommended_resolution |",
            "| ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["later_queue_rows"]:
        lines.append(
            f"| {row['day_queue_rank']} | `{row['packet_step']}` | `{row['ligand']}` | `{row['packet']}` | "
            f"`{row['assay_type_honesty']}` | `{row['recommended_resolution']}` |"
        )
    lines.extend(
        [
            "",
            "## Closure Notes",
            "",
            f"- `selected_after_verified_top3 = {s['selected_after_verified_top3']}` keeps the day plan anchored on the three core negatives immediately after the verified top binder tranche.",
            f"- `contains_only_core_rows = {s['contains_only_core_rows']}` means the first pass should stay on core rows before reopening any OOD negative packet work.",
            f"- Shipping blocker remains `{s['ship_blocker']}` on all six negative rows, so the goal is evidence closure and policy stability, not forced quantitative promotion.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CA2 evidence-closure day plan from readiness and review artifacts.")
    parser.add_argument("--readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--review-queue-json", default=DEFAULT_REVIEW_QUEUE_JSON)
    parser.add_argument("--next-slice-json", default=DEFAULT_NEXT_SLICE_JSON)
    parser.add_argument("--capture-intake-json", default=DEFAULT_CAPTURE_INTAKE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.readiness_json),
        _load_json(args.review_queue_json),
        _load_json(args.next_slice_json),
        _load_json(args.capture_intake_json),
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
