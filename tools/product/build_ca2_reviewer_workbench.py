#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PACKET_JSON = "runs/ca2_review_only_negative_packet_current.json"
DEFAULT_DAY_PLAN_JSON = "runs/ca2_evidence_closure_day_plan_current.json"
DEFAULT_OUT_JSON = "runs/ca2_reviewer_workbench_current.json"
DEFAULT_OUT_CSV = "runs/ca2_reviewer_workbench_current.csv"
DEFAULT_OUT_MD = "runs/ca2_reviewer_workbench_current.md"


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


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y"}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_payload(packet_payload: dict[str, Any], day_plan_payload: dict[str, Any]) -> dict[str, Any]:
    packet_rows = {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in packet_payload.get("rows", [])
        if str(row.get("packet_step", "")).strip()
    }

    workbench_rows: list[dict[str, Any]] = []
    for row in day_plan_payload.get("rows", []):
        packet_step = str(row.get("packet_step", "")).strip()
        packet_row = packet_rows.get(packet_step, {})
        today_focus = _as_bool(row.get("today_focus", False))
        workbench_rows.append(
            {
                "day_queue_rank": int(str(row.get("day_queue_rank", "999")) or "999"),
                "review_phase": "today_focus" if today_focus else "later_queue",
                "packet": str(row.get("packet", "")).strip(),
                "packet_step": packet_step,
                "ligand": str(row.get("ligand", "")).strip(),
                "operator_review_bucket": str(packet_row.get("operator_review_bucket", "")).strip(),
                "assay_type_honesty": str(packet_row.get("assay_type_honesty", "")).strip()
                or str(row.get("assay_type_honesty", "")).strip(),
                "promotion_blocker": str(packet_row.get("promotion_blocker", "")).strip(),
                "recommended_resolution": str(row.get("recommended_resolution", "")).strip(),
                "next_required_action": str(packet_row.get("next_required_action", "")).strip(),
                "current_missing_fields": str(packet_row.get("current_missing_fields", "")).strip(),
                "authoritative_apply_allowed_now": str(packet_row.get("authoritative_apply_allowed_now", "")).strip(),
                "operator_note_template": str(packet_row.get("operator_note_template", "")).strip(),
                "capture_status": str(packet_row.get("capture_status", "")).strip(),
                "evidence_scope": str(packet_row.get("evidence_scope", "")).strip(),
                "assay_context": str(packet_row.get("assay_context", "")).strip(),
                "source_title": str(packet_row.get("source_title", "")).strip(),
                "source_id": str(packet_row.get("source_id", "")).strip(),
                "source_url": str(packet_row.get("source_url", "")).strip(),
                "evidence_anchor": str(packet_row.get("evidence_anchor", "")).strip(),
                "manual_decision_note": str(packet_row.get("manual_decision_note", "")).strip(),
                "local_hint_count": int(str(packet_row.get("local_hint_count", "0")) or "0"),
                "local_exact_match_hint_count": int(str(packet_row.get("local_exact_match_hint_count", "0")) or "0"),
                "local_exact_match_candidate_ids": str(packet_row.get("local_exact_match_candidate_ids", "")).strip(),
                "local_exact_match_source_paths": str(packet_row.get("local_exact_match_source_paths", "")).strip(),
                "local_hint_next_move": str(packet_row.get("local_hint_next_move", "")).strip(),
                "blocker_action_summary": str(packet_row.get("blocker_action_summary", "")).strip(),
            }
        )
    workbench_rows.sort(key=lambda item: int(item["day_queue_rank"]))

    summary = {
        "family": str(day_plan_payload["summary"].get("family", "ca2")).strip(),
        "review_only_row_count": int(packet_payload["summary"].get("review_only_row_count", 0)),
        "today_focus_count": int(day_plan_payload["summary"].get("today_focus_count", 0)),
        "later_queue_count": int(day_plan_payload["summary"].get("later_queue_count", 0)),
        "high_conflict_row_count": int(packet_payload["summary"].get("high_conflict_row_count", 0)),
        "direct_conflict_row_count": int(packet_payload["summary"].get("direct_conflict_row_count", 0)),
        "no_direct_negative_found_count": int(packet_payload["summary"].get("no_direct_negative_found_count", 0)),
        "rows_with_cited_source": int(packet_payload["summary"].get("rows_with_cited_source", 0)),
        "rows_with_local_exact_match_hint": int(packet_payload["summary"].get("rows_with_local_exact_match_hint", 0)),
        "closure_mode": str(packet_payload["summary"].get("closure_mode", "review_only_conflict_closure")).strip(),
        "authoritative_negative_closure_allowed": bool(packet_payload["summary"].get("authoritative_negative_closure_allowed", False)),
        "most_common_missing_field": str(packet_payload["summary"].get("most_common_missing_field", "")).strip(),
        "ship_blocker": str(day_plan_payload["summary"].get("ship_blocker", "")).strip(),
        "selected_after_verified_top3": bool(day_plan_payload["summary"].get("selected_after_verified_top3", False)),
        "contains_only_core_rows": bool(day_plan_payload["summary"].get("contains_only_core_rows", False)),
        "workbench_ready": True,
        "day_goal": str(day_plan_payload["summary"].get("day_goal", "")).strip(),
        "next_required_step": (
            "Use this workbench as the single CA2 reviewer surface: cited source anchors and local repo hints are inline, "
            "the three core negatives stay first, OOD negatives stay parked, and all six rows remain review-only."
        ),
    }
    return {"summary": summary, "rows": workbench_rows}


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CA2 Reviewer Workbench",
        "",
        f"- family: `{summary['family']}`",
        f"- review_only_row_count: `{summary['review_only_row_count']}`",
        f"- today_focus_count: `{summary['today_focus_count']}`",
        f"- later_queue_count: `{summary['later_queue_count']}`",
        f"- high_conflict_row_count: `{summary['high_conflict_row_count']}`",
        f"- direct_conflict_row_count: `{summary['direct_conflict_row_count']}`",
        f"- no_direct_negative_found_count: `{summary['no_direct_negative_found_count']}`",
        f"- rows_with_cited_source: `{summary['rows_with_cited_source']}`",
        f"- rows_with_local_exact_match_hint: `{summary['rows_with_local_exact_match_hint']}`",
        f"- closure_mode: `{summary['closure_mode']}`",
        f"- authoritative_negative_closure_allowed: `{summary['authoritative_negative_closure_allowed']}`",
        f"- most_common_missing_field: `{summary['most_common_missing_field']}`",
        f"- ship_blocker: `{summary['ship_blocker']}`",
        f"- selected_after_verified_top3: `{summary['selected_after_verified_top3']}`",
        f"- contains_only_core_rows: `{summary['contains_only_core_rows']}`",
        f"- workbench_ready: `{summary['workbench_ready']}`",
        "",
        "## Day Goal",
        "",
        f"- {summary['day_goal']}",
        f"- {summary['next_required_step']}",
        "",
        "## Review Rows",
        "",
        "| day_queue_rank | review_phase | packet_step | ligand | operator_review_bucket | assay_type_honesty | promotion_blocker | next_required_action | authoritative_apply_allowed_now |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['day_queue_rank']} | `{row['review_phase']}` | `{row['packet_step']}` | `{row['ligand']}` | "
            f"`{row['operator_review_bucket']}` | `{row['assay_type_honesty']}` | `{row['promotion_blocker']}` | "
            f"`{row['next_required_action']}` | `{row['authoritative_apply_allowed_now']}` |"
        )
    lines.extend(["", "## Evidence Anchors", ""])
    for row in payload["rows"]:
        source_anchor = row["evidence_anchor"] or "no_curated_anchor"
        local_exact = row["local_exact_match_candidate_ids"] or "none"
        lines.append(
            f"- `{row['packet_step']}`: `{source_anchor}` | local_exact_match_candidates=`{local_exact}` | {row['blocker_action_summary']}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CA2 reviewer workbench from the negative packet and evidence-closure day plan.")
    parser.add_argument("--packet-json", default=DEFAULT_PACKET_JSON)
    parser.add_argument("--day-plan-json", default=DEFAULT_DAY_PLAN_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.packet_json), _load_json(args.day_plan_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_md(out_md, payload)


if __name__ == "__main__":
    main()
