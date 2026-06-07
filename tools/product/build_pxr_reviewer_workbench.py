#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PENDING_RESOLUTION_PACKET_JSON = "runs/pxr_pending_resolution_packet_current.json"
DEFAULT_EVIDENCE_CLOSURE_DAY_PLAN_JSON = "runs/pxr_evidence_closure_day_plan_current.json"
DEFAULT_OUT_JSON = "runs/pxr_reviewer_workbench_current.json"
DEFAULT_OUT_CSV = "runs/pxr_reviewer_workbench_current.csv"
DEFAULT_OUT_MD = "runs/pxr_reviewer_workbench_current.md"


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


def _keyed(rows: list[dict[str, Any]], key_name: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get(key_name, "")).strip()
        if key:
            out[key] = dict(row)
    return out


def _ligands(rows: list[dict[str, Any]], *, operator_stance: str | None = None) -> list[str]:
    selected = []
    for row in rows:
        if operator_stance and str(row.get("operator_stance", "")).strip() != operator_stance:
            continue
        ligand = str(row.get("ligand", "")).strip()
        if ligand:
            selected.append(ligand)
    return selected


def build_payload(
    pending_resolution_packet: dict[str, Any],
    evidence_closure_day_plan: dict[str, Any],
) -> dict[str, Any]:
    day_plan_by_step = _keyed(evidence_closure_day_plan.get("rows", []) or [], "packet_step")
    rows: list[dict[str, Any]] = []
    for row in pending_resolution_packet.get("rows", []) or []:
        step = str(row.get("packet_step", "")).strip()
        plan = day_plan_by_step.get(step, {})
        promotion_blocker = str(row.get("promotion_blocker", "")).strip()
        if "review_only" in str(row.get("disposition", "")).strip():
            operator_stance = "review_only_negative"
        elif str(row.get("replacement_is_binder", "")).strip() == "1" and promotion_blocker == "quantitative_binding_value_or_activity_proxy_missing":
            operator_stance = "deferred_confirmed_binder_quantitative_gap"
        elif str(row.get("replacement_is_binder", "")).strip() == "1" and promotion_blocker == "activity_present_manual_confirmation_required":
            operator_stance = "deferred_supportive_binder_review"
        elif str(row.get("replacement_is_binder", "")).strip() == "1":
            operator_stance = "deferred_binder_gap"
        else:
            operator_stance = "deferred_non_binder_conflict"
        rows.append(
            {
                "priority_rank": str(row.get("priority_rank", "")).strip(),
                "packet_step": step,
                "ligand": str(row.get("ligand", "")).strip(),
                "replacement_is_binder": str(row.get("replacement_is_binder", "")).strip(),
                "disposition": str(row.get("disposition", "")).strip(),
                "assay_type_honesty": str(row.get("assay_type_honesty", "")).strip(),
                "verification_status": str(row.get("verification_status", "")).strip(),
                "promotion_blocker": str(row.get("promotion_blocker", "")).strip(),
                "readiness_missing_fields": str(row.get("readiness_missing_fields", "")).strip(),
                "ready_for_authoritative_apply": str(row.get("ready_for_authoritative_apply", "")).strip(),
                "plan_phase": str(plan.get("plan_phase", "")).strip(),
                "day_goal": str(plan.get("day_goal", "")).strip(),
                "next_required_action": str(plan.get("next_required_action", "")).strip() or str(row.get("next_required_action", "")).strip(),
                "stop_if_unresolved": str(plan.get("stop_if_unresolved", "")).strip(),
                "operator_stance": operator_stance,
            }
        )

    supportive_binder_review_count = sum(1 for row in rows if row["operator_stance"] == "deferred_supportive_binder_review")
    confirmed_binder_quantitative_gap_count = sum(
        1 for row in rows if row["operator_stance"] == "deferred_confirmed_binder_quantitative_gap"
    )
    review_only_ligands = ", ".join(_ligands(rows, operator_stance="review_only_negative")) or "none"
    deferred_conflict_ligands = ", ".join(_ligands(rows, operator_stance="deferred_non_binder_conflict")) or "none"
    summary = {
        "family": str(pending_resolution_packet.get("summary", {}).get("family", "pxr")).strip(),
        "target": str(pending_resolution_packet.get("summary", {}).get("target", "PXR_NR1I2_BLIND")).strip(),
        "workbench_row_count": len(rows),
        "first_hour_count": sum(1 for row in rows if row["plan_phase"] == "first_hour"),
        "second_pass_count": sum(1 for row in rows if row["plan_phase"] == "second_pass"),
        "same_day_followup_count": sum(1 for row in rows if row["plan_phase"] == "same_day_followup"),
        "review_only_row_count": int(pending_resolution_packet.get("summary", {}).get("review_only_row_count", 0) or 0),
        "defer_row_count": int(pending_resolution_packet.get("summary", {}).get("defer_row_count", 0) or 0),
        "binder_gap_count": int(pending_resolution_packet.get("summary", {}).get("binder_gap_count", 0) or 0),
        "supportive_binder_review_count": supportive_binder_review_count,
        "confirmed_binder_quantitative_gap_count": confirmed_binder_quantitative_gap_count,
        "policy_line": str(pending_resolution_packet.get("summary", {}).get("policy_line", "")).strip(),
        "next_required_step": (
            f"Start with review-only negatives ({review_only_ligands}), then work deferred non-binder conflicts ({deferred_conflict_ligands}), and keep literature-supported deferred binder rows pending manual confirmation."
            if supportive_binder_review_count
            else f"Start with review-only negatives ({review_only_ligands}), then work deferred non-binder conflicts ({deferred_conflict_ligands}), and keep literature-confirmed binder rows on the quantitative-provenance gap lane."
            if confirmed_binder_quantitative_gap_count
            else str(evidence_closure_day_plan.get("summary", {}).get("next_required_step", "")).strip()
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# PXR Reviewer Workbench",
        "",
        f"- family: `{s['family']}`",
        f"- target: `{s['target']}`",
        f"- workbench_row_count: `{s['workbench_row_count']}`",
        f"- first_hour_count: `{s['first_hour_count']}`",
        f"- second_pass_count: `{s['second_pass_count']}`",
        f"- same_day_followup_count: `{s['same_day_followup_count']}`",
        f"- review_only_row_count: `{s['review_only_row_count']}`",
        f"- defer_row_count: `{s['defer_row_count']}`",
        f"- binder_gap_count: `{s['binder_gap_count']}`",
        f"- supportive_binder_review_count: `{s['supportive_binder_review_count']}`",
        f"- confirmed_binder_quantitative_gap_count: `{s['confirmed_binder_quantitative_gap_count']}`",
        "",
        "## Policy Line",
        "",
        f"- {s['policy_line']}",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Workbench Rows",
        "",
        "| plan_phase | priority_rank | packet_step | ligand | operator_stance | assay_type_honesty | day_goal | next_required_action | stop_if_unresolved |",
        "| --- | ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['plan_phase']}` | {row['priority_rank']} | `{row['packet_step']}` | `{row['ligand']}` | "
            f"`{row['operator_stance']}` | `{row['assay_type_honesty']}` | `{row['day_goal']}` | "
            f"`{row['next_required_action']}` | `{row['stop_if_unresolved']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a reviewer workbench by combining the PXR pending-resolution packet and day plan.")
    parser.add_argument("--pending-resolution-packet-json", default=DEFAULT_PENDING_RESOLUTION_PACKET_JSON)
    parser.add_argument("--evidence-closure-day-plan-json", default=DEFAULT_EVIDENCE_CLOSURE_DAY_PLAN_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.pending_resolution_packet_json),
        _load_json(args.evidence_closure_day_plan_json),
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
