#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PENDING_RESOLUTION_PACKET_JSON = "runs/pxr_pending_resolution_packet_current.json"
DEFAULT_PACKET_FILL_READINESS_JSON = "runs/pxr_packet_fill_readiness_current.json"
DEFAULT_NEXT_VERIFICATION_SLICE_JSON = "runs/pxr_next_verification_slice_current.json"
DEFAULT_OUT_JSON = "runs/pxr_evidence_closure_day_plan_current.json"
DEFAULT_OUT_CSV = "runs/pxr_evidence_closure_day_plan_current.csv"
DEFAULT_OUT_MD = "runs/pxr_evidence_closure_day_plan_current.md"


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


def _build_work_items(
    pending_resolution_packet: dict[str, Any],
    packet_fill_readiness: dict[str, Any],
    next_verification_slice: dict[str, Any],
) -> list[dict[str, Any]]:
    readiness_by_step = {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in packet_fill_readiness.get("readiness_rows", []) or []
        if str(row.get("packet_step", "")).strip()
    }

    items: list[dict[str, Any]] = []
    for row in pending_resolution_packet.get("rows", []) or []:
        step = str(row.get("packet_step", "")).strip()
        readiness = readiness_by_step.get(step, {})
        is_review_only = "review_only" in str(row.get("disposition", "")).strip()
        is_binder_gap = str(row.get("replacement_is_binder", "")).strip() == "1"
        supportive_binder_review = is_binder_gap and str(row.get("promotion_blocker", "")).strip() == "activity_present_manual_confirmation_required"
        confirmed_binder_quantitative_gap = is_binder_gap and str(row.get("promotion_blocker", "")).strip() == "quantitative_binding_value_or_activity_proxy_missing"
        plan_phase = "first_hour" if is_review_only else ("second_pass" if is_binder_gap else "same_day_followup")
        day_goal = (
            "confirm_review_only_negative_and_leave_quantitative_binding_blank"
            if is_review_only
            else (
                "manually_confirm_supportive_binder_or_keep_deferred"
                if supportive_binder_review
                else "curate_quantitative_binder_provenance_or_keep_deferred"
                if confirmed_binder_quantitative_gap
                else "resolve_target_specific_binder_gap_or_keep_deferred"
                if is_binder_gap
                else "resolve_non_binder_conflict_or_keep_deferred"
            )
        )
        items.append(
            {
                "plan_phase": plan_phase,
                "priority_rank": str(row.get("priority_rank", "")).strip(),
                "packet_step": step,
                "ligand": str(row.get("ligand", "")).strip(),
                "replacement_is_binder": str(row.get("replacement_is_binder", "")).strip(),
                "disposition": str(row.get("disposition", "")).strip(),
                "assay_type_honesty": str(row.get("assay_type_honesty", "")).strip(),
                "promotion_blocker": str(row.get("promotion_blocker", "")).strip(),
                "next_required_action": str(row.get("next_required_action", "")).strip(),
                "readiness_missing_fields": str(row.get("readiness_missing_fields", "")).strip() or str(readiness.get("required_missing_fields", "")).strip(),
                "day_goal": day_goal,
                "stop_if_unresolved": "yes" if not is_review_only else "no",
            }
        )
    return items


def _ligands(rows: list[dict[str, Any]], *, disposition_contains: str | None = None, day_goal: str | None = None) -> list[str]:
    out: list[str] = []
    for row in rows:
        if disposition_contains and disposition_contains not in str(row.get("disposition", "")).strip():
            continue
        if day_goal and str(row.get("day_goal", "")).strip() != day_goal:
            continue
        ligand = str(row.get("ligand", "")).strip()
        if ligand:
            out.append(ligand)
    return out


def build_payload(
    pending_resolution_packet: dict[str, Any],
    packet_fill_readiness: dict[str, Any],
    next_verification_slice: dict[str, Any],
) -> dict[str, Any]:
    rows = _build_work_items(pending_resolution_packet, packet_fill_readiness, next_verification_slice)
    first_hour_count = sum(1 for row in rows if row["plan_phase"] == "first_hour")
    second_pass_count = sum(1 for row in rows if row["plan_phase"] == "second_pass")
    followup_count = sum(1 for row in rows if row["plan_phase"] == "same_day_followup")
    supportive_binder_review_count = sum(
        1 for row in rows if row["day_goal"] == "manually_confirm_supportive_binder_or_keep_deferred"
    )
    confirmed_binder_quantitative_gap_count = sum(
        1 for row in rows if row["day_goal"] == "curate_quantitative_binder_provenance_or_keep_deferred"
    )
    review_only_ligands = ", ".join(_ligands(rows, disposition_contains="review_only")) or "none"
    deferred_conflict_ligands = ", ".join(
        _ligands(rows, day_goal="resolve_non_binder_conflict_or_keep_deferred")
    ) or "none"
    summary = {
        "family": "pxr",
        "target": str(pending_resolution_packet.get("summary", {}).get("target", "PXR_NR1I2_BLIND")).strip(),
        "work_item_count": len(rows),
        "first_hour_count": first_hour_count,
        "second_pass_count": second_pass_count,
        "same_day_followup_count": followup_count,
        "supportive_binder_review_count": supportive_binder_review_count,
        "confirmed_binder_quantitative_gap_count": confirmed_binder_quantitative_gap_count,
        "ready_for_apply_row_count": int(packet_fill_readiness.get("summary", {}).get("ready_for_apply_row_count", 0) or 0),
        "blocked_row_count": int(packet_fill_readiness.get("summary", {}).get("blocked_row_count", 0) or 0),
        "contains_binder_gap": bool(next_verification_slice.get("summary", {}).get("contains_binder_gap", False)),
        "policy_line": str(pending_resolution_packet.get("summary", {}).get("policy_line", "")).strip(),
        "next_required_step": (
            f"Start with review-only negatives ({review_only_ligands}), then work deferred non-binder conflicts ({deferred_conflict_ligands}), and keep literature-supported deferred binder rows pending manual confirmation."
            if supportive_binder_review_count
            else f"Start with review-only negatives ({review_only_ligands}), then work deferred non-binder conflicts ({deferred_conflict_ligands}), and keep literature-confirmed binder rows on the quantitative-provenance curation lane."
            if confirmed_binder_quantitative_gap_count
            else f"Start with review-only negatives ({review_only_ligands}), then work deferred non-binder conflicts ({deferred_conflict_ligands}), and leave remaining binder-gap rows deferred unless target-specific human PXR evidence is found."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# PXR Evidence Closure Day Plan",
        "",
        f"- family: `{s['family']}`",
        f"- target: `{s['target']}`",
        f"- work_item_count: `{s['work_item_count']}`",
        f"- first_hour_count: `{s['first_hour_count']}`",
        f"- second_pass_count: `{s['second_pass_count']}`",
        f"- same_day_followup_count: `{s['same_day_followup_count']}`",
        f"- supportive_binder_review_count: `{s['supportive_binder_review_count']}`",
        f"- confirmed_binder_quantitative_gap_count: `{s['confirmed_binder_quantitative_gap_count']}`",
        f"- ready_for_apply_row_count: `{s['ready_for_apply_row_count']}`",
        f"- blocked_row_count: `{s['blocked_row_count']}`",
        f"- contains_binder_gap: `{s['contains_binder_gap']}`",
        "",
        "## Policy Line",
        "",
        f"- {s['policy_line']}",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Work Items",
        "",
        "| plan_phase | priority_rank | packet_step | ligand | binder | disposition | assay_type_honesty | day_goal | stop_if_unresolved |",
        "| --- | ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['plan_phase']}` | {row['priority_rank']} | `{row['packet_step']}` | `{row['ligand']}` | "
            f"`{row['replacement_is_binder']}` | `{row['disposition']}` | `{row['assay_type_honesty']}` | "
            f"`{row['day_goal']}` | `{row['stop_if_unresolved']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a one-day operator plan for closing current PXR evidence gaps.")
    parser.add_argument("--pending-resolution-packet-json", default=DEFAULT_PENDING_RESOLUTION_PACKET_JSON)
    parser.add_argument("--packet-fill-readiness-json", default=DEFAULT_PACKET_FILL_READINESS_JSON)
    parser.add_argument("--next-verification-slice-json", default=DEFAULT_NEXT_VERIFICATION_SLICE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.pending_resolution_packet_json),
        _load_json(args.packet_fill_readiness_json),
        _load_json(args.next_verification_slice_json),
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
