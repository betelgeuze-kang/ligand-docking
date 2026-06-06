#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WORKBENCH_JSON = "runs/pxr_reviewer_workbench_current.json"
DEFAULT_DAY_PLAN_JSON = "runs/pxr_evidence_closure_day_plan_current.json"
DEFAULT_PENDING_PACKET_JSON = "runs/pxr_pending_resolution_packet_current.json"
DEFAULT_OUT_JSON = "runs/pxr_pending_resolution_reviewer_draft_packet_current.json"
DEFAULT_OUT_CSV = "runs/pxr_pending_resolution_reviewer_draft_packet_current.csv"
DEFAULT_OUT_MD = "runs/pxr_pending_resolution_reviewer_draft_packet_current.md"


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


def _draft_note(row: dict[str, Any]) -> str:
    ligand = str(row.get("ligand", "")).strip()
    stance = str(row.get("operator_stance", "")).strip()
    honesty = str(row.get("assay_type_honesty", "")).strip()
    blocker = str(row.get("promotion_blocker", "")).strip()
    if blocker == "inactive_only_human_pxr_qhts_review_only":
        return (
            f"Treat {ligand} as a direct inactive-only human PXR qHTS row. "
            "Keep it review-only, record the inactive target-specific source cleanly, and do not convert it into a count-improving non-binder claim."
        )
    if stance == "review_only_negative":
        return (
            f"Treat {ligand} as a review-only negative-like PXR row. "
            f"Confirm the weak upper-bound signal without inventing a quantitative non-binder value."
        )
    if ligand == "acetaminophen":
        return (
            "Resolve whether acetaminophen stays deferred because proxy activity conflicts with a non-binder label. "
            "Only move it out of defer if local target-specific human PXR evidence clearly supports a safer classification."
        )
    if stance == "deferred_supportive_binder_review":
        if ligand == "bexarotene":
            return (
                "Treat bexarotene as the supportive human PXR binder row anchored by the PubChem qHTS proxy lane. "
                "Keep it deferred until manual confirmation establishes claim-safe target-specific binder evidence; accessible ChEMBL/BindingDB quantitative provenance is still absent."
            )
        return (
            f"Treat {ligand} as a literature-backed supportive human PXR binder row that still needs manual confirmation. "
            "Keep it deferred until the source is manually confirmed as claim-safe target-specific binder evidence."
        )
    if stance == "deferred_confirmed_binder_quantitative_gap":
        return (
            f"Treat {ligand} as a manually confirmed human PXR binder-support row. "
            "Keep it deferred until claim-safe quantitative activity or binding provenance is curated."
        )
    if ligand == "caffeine":
        return (
            "Keep caffeine in the unresolved non-binder conflict lane until local target-specific human PXR evidence appears. "
            "Do not upgrade it from defer based on generic absence-of-evidence arguments."
        )
    if ligand == "bexarotene":
        return (
            "Treat bexarotene as the supportive-binder manual-confirmation row. "
            "Only reopen it if exact human PXR target evidence upgrades the current proxy support cleanly."
        )
    return f"Review {ligand} under `{honesty}` and keep the current deferred/review-only policy unless stronger local evidence changes the classification."


def _stop_condition(row: dict[str, Any]) -> str:
    ligand = str(row.get("ligand", "")).strip()
    stance = str(row.get("operator_stance", "")).strip()
    blocker = str(row.get("promotion_blocker", "")).strip()
    if blocker == "inactive_only_human_pxr_qhts_review_only":
        return "Stop after documenting the inactive-only human PXR qHTS source; keep review-only and do not assign a quantitative non-binder value."
    if stance == "review_only_negative":
        return "Stop if the source does not improve on the current weak upper-bound signal; keep review-only and leave quantitative binding blank."
    if stance == "deferred_supportive_binder_review":
        return (
            "Stop if the supportive target-specific human PXR source cannot be manually confirmed as claim-safe binder evidence; "
            "keep deferred and do not fill binder fields."
        )
    if stance == "deferred_confirmed_binder_quantitative_gap":
        return (
            "Stop if the source remains qualitative-only or lacks claim-safe quantitative human PXR output; "
            "keep deferred and do not fill binder fields."
        )
    if ligand == "acetaminophen":
        return "Stop if evidence remains proxy-only or non-target-specific; keep deferred and do not relabel as a non-binder."
    if ligand == "caffeine":
        return "Stop if no local target-specific human PXR activity is found; keep deferred and do not auto-promote by absence of contradiction."
    if ligand == "bexarotene":
        return "Stop if no local target-specific human PXR binder evidence is found; keep deferred and do not fill binder fields."
    return "Stop if the new evidence does not reduce the current blocker cleanly; keep the row in its current policy bucket."


def _resolution_bias(row: dict[str, Any]) -> str:
    if str(row.get("operator_stance", "")).strip() == "review_only_negative":
        return "review_only"
    return "defer"


def _ligands(rows: list[dict[str, Any]], *, resolution_bias: str | None = None) -> list[str]:
    out: list[str] = []
    for row in rows:
        if resolution_bias and str(row.get("resolution_bias", "")).strip() != resolution_bias:
            continue
        ligand = str(row.get("ligand", "")).strip()
        if ligand:
            out.append(ligand)
    return out


def build_payload(
    workbench_payload: dict[str, Any],
    day_plan_payload: dict[str, Any],
    pending_packet_payload: dict[str, Any],
) -> dict[str, Any]:
    workbench_s = dict(workbench_payload.get("summary", {}) or {})
    day_plan_s = dict(day_plan_payload.get("summary", {}) or {})
    pending_s = dict(pending_packet_payload.get("summary", {}) or {})

    rows: list[dict[str, Any]] = []
    for row in workbench_payload.get("rows", []) or []:
        rows.append(
            {
                "draft_rank": 0,
                "plan_phase": str(row.get("plan_phase", "")).strip(),
                "priority_rank": int(str(row.get("priority_rank", "999")).strip() or 999),
                "packet_step": str(row.get("packet_step", "")).strip(),
                "ligand": str(row.get("ligand", "")).strip(),
                "binder": int(row.get("replacement_is_binder", 0) or 0),
                "operator_stance": str(row.get("operator_stance", "")).strip(),
                "assay_type_honesty": str(row.get("assay_type_honesty", "")).strip(),
                "promotion_blocker": str(row.get("promotion_blocker", "")).strip(),
                "next_required_action": str(row.get("next_required_action", "")).strip(),
                "resolution_bias": _resolution_bias(row),
                "draft_note": _draft_note(row),
                "explicit_stop_condition": _stop_condition(row),
            }
        )

    phase_order = {"first_hour": 0, "same_day_followup": 1, "second_pass": 2}
    rows.sort(key=lambda row: (phase_order.get(str(row["plan_phase"]), 9), int(row["priority_rank"]), str(row["packet_step"])))
    for idx, row in enumerate(rows, start=1):
        row["draft_rank"] = idx

    review_only_ligands = ", ".join(_ligands(rows, resolution_bias="review_only")) or "none"
    deferred_ligands = ", ".join(_ligands(rows, resolution_bias="defer")) or "none"

    summary = {
        "family": str(workbench_s.get("family", pending_s.get("family", "pxr"))).strip(),
        "target": str(workbench_s.get("target", day_plan_s.get("target", ""))).strip(),
        "reviewer_draft_row_count": len(rows),
        "review_only_row_count": int(workbench_s.get("review_only_row_count", pending_s.get("review_only_row_count", 0)) or 0),
        "defer_row_count": int(workbench_s.get("defer_row_count", pending_s.get("defer_row_count", 0)) or 0),
        "binder_gap_count": int(workbench_s.get("binder_gap_count", pending_s.get("binder_gap_count", 0)) or 0),
        "supportive_binder_review_count": int(workbench_s.get("supportive_binder_review_count", 0) or 0),
        "confirmed_binder_quantitative_gap_count": int(workbench_s.get("confirmed_binder_quantitative_gap_count", 0) or 0),
        "ready_for_apply_row_count": int(day_plan_s.get("ready_for_apply_row_count", pending_s.get("ready_for_apply_row_count", 0)) or 0),
        "blocked_row_count": int(day_plan_s.get("blocked_row_count", pending_s.get("blocked_row_count", 0)) or 0),
        "policy_line": str(workbench_s.get("policy_line", pending_s.get("policy_line", ""))).strip(),
        "next_required_step": (
            f"Use these reviewer-facing draft notes to keep review-only rows ({review_only_ligands}) documented, keep deferred rows ({deferred_ligands}) parked unless local target-specific human evidence reduces their blockers, and keep literature-supported binder rows deferred until manual confirmation is complete."
            if int(workbench_s.get("supportive_binder_review_count", 0) or 0)
            else f"Use these reviewer-facing draft notes to keep review-only rows ({review_only_ligands}) documented, keep deferred rows ({deferred_ligands}) parked unless local target-specific human evidence reduces their blockers, and keep literature-confirmed binder rows deferred until quantitative provenance is added."
            if int(workbench_s.get("confirmed_binder_quantitative_gap_count", 0) or 0)
            else f"Use these reviewer-facing draft notes to keep review-only rows ({review_only_ligands}) documented, keep deferred rows ({deferred_ligands}) parked unless local target-specific human evidence reduces their blockers, and leave remaining binder-gap rows deferred unless the gap closes cleanly."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# PXR Pending-Resolution Reviewer Draft Packet",
        "",
        f"- family: `{s['family']}`",
        f"- target: `{s['target']}`",
        f"- reviewer_draft_row_count: `{s['reviewer_draft_row_count']}`",
        f"- review_only_row_count: `{s['review_only_row_count']}`",
        f"- defer_row_count: `{s['defer_row_count']}`",
        f"- binder_gap_count: `{s['binder_gap_count']}`",
        f"- supportive_binder_review_count: `{s['supportive_binder_review_count']}`",
        f"- confirmed_binder_quantitative_gap_count: `{s['confirmed_binder_quantitative_gap_count']}`",
        f"- ready_for_apply_row_count: `{s['ready_for_apply_row_count']}`",
        f"- blocked_row_count: `{s['blocked_row_count']}`",
        "",
        "## Policy Line",
        "",
        f"- {s['policy_line']}",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Reviewer Draft Rows",
        "",
        "| draft_rank | plan_phase | priority_rank | packet_step | ligand | binder | resolution_bias | next_required_action | explicit_stop_condition |",
        "| ---: | --- | ---: | --- | --- | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['draft_rank']} | `{row['plan_phase']}` | {row['priority_rank']} | `{row['packet_step']}` | "
            f"`{row['ligand']}` | {row['binder']} | `{row['resolution_bias']}` | "
            f"`{row['next_required_action']}` | {row['explicit_stop_condition']} |"
        )
    lines.extend(
        [
            "",
            "## Draft Notes",
            "",
        ]
    )
    for row in payload["rows"]:
        lines.append(f"- `{row['ligand']}`: {row['draft_note']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a reviewer-facing draft packet for current unresolved PXR rows.")
    parser.add_argument("--workbench-json", default=DEFAULT_WORKBENCH_JSON)
    parser.add_argument("--day-plan-json", default=DEFAULT_DAY_PLAN_JSON)
    parser.add_argument("--pending-packet-json", default=DEFAULT_PENDING_PACKET_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.workbench_json),
        _load_json(args.day_plan_json),
        _load_json(args.pending_packet_json),
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
