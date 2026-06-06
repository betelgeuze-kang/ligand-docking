#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CA2_COMMIT_JSON = "runs/ca2_evidence_closure_commit_packet_current.json"
DEFAULT_PXR_COMMIT_JSON = "runs/pxr_pending_resolution_commit_packet_current.json"
DEFAULT_OUT_JSON = "runs/partial_authoritative_commit_launchboard_current.json"
DEFAULT_OUT_CSV = "runs/partial_authoritative_commit_launchboard_current.csv"
DEFAULT_OUT_MD = "runs/partial_authoritative_commit_launchboard_current.md"


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
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _first_label(rows: list[dict[str, Any]], key: str) -> str:
    if not rows:
        return ""
    return str(rows[0].get(key, "")).strip()


def _pxr_finish_line(summary: dict[str, Any]) -> str:
    supportive_binder_review_count = int(summary.get("supportive_binder_review_count", 0) or 0)
    confirmed_binder_quantitative_gap_count = int(summary.get("confirmed_binder_quantitative_gap_count", 0) or 0)
    if supportive_binder_review_count > 0:
        return (
            "Confirm the current review-only PXR rows, keep unresolved conflict negatives deferred, "
            "and keep literature-backed supportive binder rows like bexarotene deferred pending manual confirmation."
        )
    if confirmed_binder_quantitative_gap_count > 0:
        return (
            "Confirm the current review-only PXR rows, keep unresolved conflict negatives deferred, "
            "and keep bexarotene deferred on the literature-confirmed quantitative-provenance gap lane."
        )
    return "Confirm the current review-only PXR rows and leave the remaining deferred PXR rows parked until blocker-reducing evidence is curated."


def _pxr_stop_condition(summary: dict[str, Any]) -> str:
    supportive_binder_review_count = int(summary.get("supportive_binder_review_count", 0) or 0)
    confirmed_binder_quantitative_gap_count = int(summary.get("confirmed_binder_quantitative_gap_count", 0) or 0)
    if supportive_binder_review_count > 0:
        return (
            "Stop if evidence remains proxy-only or non-target-specific, or if a supportive binder source cannot be "
            "manually confirmed as claim-safe; keep deferred rows deferred and do not fill binder/non-binder quantitative fields."
        )
    if confirmed_binder_quantitative_gap_count > 0:
        return (
            "Stop if evidence remains qualitative-only or lacks claim-safe quantitative provenance; "
            "keep deferred rows deferred and do not fill binder/non-binder quantitative fields."
        )
    return "Stop if evidence remains proxy-only or non-target-specific; keep deferred rows deferred and do not fill binder/non-binder quantitative fields."


def _next_required_step(pxr_summary: dict[str, Any]) -> str:
    supportive_binder_review_count = int(pxr_summary.get("supportive_binder_review_count", 0) or 0)
    confirmed_binder_quantitative_gap_count = int(pxr_summary.get("confirmed_binder_quantitative_gap_count", 0) or 0)
    if supportive_binder_review_count > 0:
        pxr_clause = (
            "then move to the PXR commit packet, stop after ibuprofen is confirmed, keep unresolved negatives deferred, "
            "and leave literature-backed supportive binder rows deferred until manual confirmation is complete."
        )
    elif confirmed_binder_quantitative_gap_count > 0:
        pxr_clause = (
            "then move to the PXR commit packet, stop after ibuprofen is confirmed, keep unresolved negatives deferred, "
            "and leave literature-confirmed binder rows deferred until quantitative provenance is explicit."
        )
    else:
        pxr_clause = (
            "then move to the PXR commit packet and stop after ibuprofen is confirmed and the remaining rows are explicitly left deferred."
        )
    return (
        "Open the CA2 commit packet first, treat it as review-only/conflict closure rather than authoritative negative closure, "
        "record the 3 core CA2 confirmations immediately, leave the 3 OOD CA2 rows explicitly parked as later-queue review items, "
        f"{pxr_clause}"
    )


def build_payload(
    ca2_commit: dict[str, Any],
    pxr_commit: dict[str, Any],
) -> dict[str, Any]:
    ca2_rows = list(ca2_commit.get("rows", []) or [])
    pxr_rows = list(pxr_commit.get("rows", []) or [])
    ca2_summary = dict(ca2_commit.get("summary", {}) or {})
    pxr_summary = dict(pxr_commit.get("summary", {}) or {})

    stage_rows = [
        {
            "stage_order": 1,
            "family": "ca2",
            "open_packet": "runs/ca2_evidence_closure_commit_packet_current.md",
            "start_label": _first_label(ca2_rows, "ligand"),
            "commit_row_count": int(ca2_summary.get("commit_row_count", 0) or 0),
            "confirm_now_count": int(ca2_summary.get("confirm_now_row_count", 0) or 0),
            "must_remain_deferred_count": 0,
            "closure_mode": "review_only_conflict_closure",
            "direct_conflict_row_count": int(ca2_summary.get("conflict_review_row_count", 0) or 0),
            "no_direct_negative_source_row_count": int(ca2_summary.get("no_direct_negative_source_row_count", 0) or 0),
            "finish_line": "Confirm all 6 CA2 review-only negative rows, but treat the lane as review-only/conflict closure: 5 rows are direct inhibitor conflicts, 1 row has no direct CA2-specific negative source, the 3 core rows go first, and the 3 OOD rows stay explicitly parked as later-queue items.",
            "stop_condition": "Stop if any row would require `replacement_reference_binding_kcal_mol` or if anyone tries to reinterpret CA2 as authoritative negative closure; keep the field blank and do not broaden into authoritative apply.",
            "open_after_exhausted": "runs/pxr_pending_resolution_commit_packet_current.md",
        },
        {
            "stage_order": 2,
            "family": "pxr",
            "open_packet": "runs/pxr_pending_resolution_commit_packet_current.md",
            "start_label": _first_label(pxr_rows, "ligand"),
            "commit_row_count": int(pxr_summary.get("commit_row_count", 0) or 0),
            "confirm_now_count": int(pxr_summary.get("confirm_now_count", 0) or 0),
            "must_remain_deferred_count": int(pxr_summary.get("must_remain_deferred_count", 0) or 0),
            "finish_line": _pxr_finish_line(pxr_summary),
            "stop_condition": _pxr_stop_condition(pxr_summary),
            "open_after_exhausted": "",
        },
    ]

    summary = {
        "family_count": 2,
        "launch_stage_count": len(stage_rows),
        "today_open_now": stage_rows[0]["open_packet"],
        "today_open_now_label": stage_rows[0]["start_label"],
        "ca2_closure_mode": stage_rows[0].get("closure_mode", ""),
        "ca2_direct_conflict_row_count": stage_rows[0].get("direct_conflict_row_count", 0),
        "ca2_no_direct_negative_source_row_count": stage_rows[0].get("no_direct_negative_source_row_count", 0),
        "ca2_authoritative_negative_closure_allowed": False,
        "ca2_remaining_blank_field": "replacement_reference_binding_kcal_mol",
        "next_open_after_current": stage_rows[0]["open_after_exhausted"],
        "total_commit_row_count": sum(int(row["commit_row_count"]) for row in stage_rows),
        "total_confirm_now_count": sum(int(row["confirm_now_count"]) for row in stage_rows),
        "total_must_remain_deferred_count": sum(int(row["must_remain_deferred_count"]) for row in stage_rows),
        "next_required_step": _next_required_step(pxr_summary),
    }
    checklist = [
        f"Open `{summary['today_open_now']}` first.",
        f"Start at `{summary['today_open_now_label']}`.",
        "Do not fill quantitative binding fields for CA2 negative-like rows.",
        "Do not convert deferred PXR rows into review-only or authoritative apply without new target-specific human evidence.",
        f"After CA2 is exhausted, open `{summary['next_open_after_current']}`.",
    ]
    return {"summary": summary, "checklist": checklist, "rows": stage_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Partial-Authoritative Commit Launchboard",
        "",
        f"- family_count: `{s['family_count']}`",
        f"- launch_stage_count: `{s['launch_stage_count']}`",
        f"- total_commit_row_count: `{s['total_commit_row_count']}`",
        f"- total_confirm_now_count: `{s['total_confirm_now_count']}`",
        f"- total_must_remain_deferred_count: `{s['total_must_remain_deferred_count']}`",
        f"- ca2_closure_mode: `{s['ca2_closure_mode']}`",
        f"- ca2_direct_conflict_row_count: `{s['ca2_direct_conflict_row_count']}`",
        f"- ca2_no_direct_negative_source_row_count: `{s['ca2_no_direct_negative_source_row_count']}`",
        f"- ca2_authoritative_negative_closure_allowed: `{s['ca2_authoritative_negative_closure_allowed']}`",
        f"- ca2_remaining_blank_field: `{s['ca2_remaining_blank_field']}`",
        "",
        "## Open Now",
        "",
        f"- Packet: `{s['today_open_now']}`",
        f"- Start label: `{s['today_open_now_label']}`",
        f"- Next packet after current: `{s['next_open_after_current']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Checklist",
        "",
    ]
    for item in payload["checklist"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Strict Opening Order",
            "",
            "| stage_order | family | open_packet | start_label | commit_row_count | confirm_now_count | must_remain_deferred_count | finish_line | stop_condition | open_after_exhausted |",
            "| ---: | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| {row['stage_order']} | `{row['family']}` | `{row['open_packet']}` | `{row['start_label']}` | "
            f"{row['commit_row_count']} | {row['confirm_now_count']} | {row['must_remain_deferred_count']} | "
            f"{row['finish_line']} | {row['stop_condition']} | `{row['open_after_exhausted']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a strict commit-order launchboard for CA2/PXR partial-authoritative work.")
    parser.add_argument("--ca2-commit-json", default=DEFAULT_CA2_COMMIT_JSON)
    parser.add_argument("--pxr-commit-json", default=DEFAULT_PXR_COMMIT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.ca2_commit_json),
        _load_json(args.pxr_commit_json),
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
