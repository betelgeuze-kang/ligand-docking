#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WORKBENCH_JSON = "runs/pxr_reviewer_workbench_current.json"
DEFAULT_PENDING_PACKET_JSON = "runs/pxr_pending_resolution_packet_current.json"
DEFAULT_DRAFT_PACKET_JSON = "runs/pxr_pending_resolution_reviewer_draft_packet_current.json"
DEFAULT_DAY_PLAN_JSON = "runs/pxr_evidence_closure_day_plan_current.json"
DEFAULT_OUT_JSON = "runs/pxr_pending_resolution_commit_packet_current.json"
DEFAULT_OUT_CSV = "runs/pxr_pending_resolution_commit_packet_current.csv"
DEFAULT_OUT_MD = "runs/pxr_pending_resolution_commit_packet_current.md"


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


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _existing_by_step(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    return {
        str(row.get("packet_step", "")).strip(): row
        for row in _read_csv(path)
        if str(row.get("packet_step", "")).strip()
    }


def _commit_decision(row: dict[str, Any], existing: dict[str, str] | None = None) -> tuple[str, str]:
    existing = existing or {}
    ligand = str(row.get("ligand", "")).strip()
    bias = str(row.get("resolution_bias", "")).strip()
    manual_blocker = str(existing.get("manual_promotion_blocker", "")).strip()
    manual_honesty = str(existing.get("manual_assay_type_honesty", "")).strip()
    capture_status = str(existing.get("capture_status", "")).strip()
    manual_class = str(existing.get("manual_commit_class", "")).strip()
    manual_override_note = str(existing.get("manual_commit_class_override", "")).strip()
    if manual_blocker == "inactive_only_human_pxr_qhts_review_only" or manual_honesty == "inactive_only_human_pxr_qhts_review_only":
        return (
            "confirm_now",
            "Confirm as a review-only inactive-only human PXR qHTS row, keep quantitative binding blank, and do not promote it into an authoritative non-binder claim.",
        )
    if capture_status and capture_status != "pending_capture" and manual_class:
        return (
            manual_class,
            manual_override_note
            or (
                "Confirm as review-only negative-like row, keep quantitative binding blank, and keep out of authoritative apply."
                if manual_class == "confirm_now"
                else "Keep current deferred/review-only state unless the blocker is explicitly reduced by local target-specific human evidence."
            ),
        )
    if ligand == "ibuprofen" and bias == "review_only":
        return (
            "confirm_now",
            "Confirm as review-only negative-like row, keep quantitative binding blank, and keep out of authoritative apply.",
        )
    if manual_blocker == "activity_present_manual_confirmation_required" or "manual_confirmation_required" in manual_honesty:
        return (
            "must_remain_deferred",
            "Keep deferred as a literature-backed supportive human PXR binder row until manual confirmation upgrades it to claim-safe binder evidence.",
        )
    if manual_blocker == "quantitative_binding_value_or_activity_proxy_missing" or manual_honesty == "literature_confirmed_target_specific_human_pxr_binder_quantitative_value_missing":
        return (
            "must_remain_deferred",
            "Manual review confirmed human PXR/SXR binder-modulator support for bexarotene from PMID 18544536, but claim-safe quantitative provenance is still missing; keep deferred and leave binder fields blank.",
        )
    if ligand == "acetaminophen":
        return (
            "must_remain_deferred",
            "Keep deferred unless local target-specific human PXR evidence resolves the current proxy conflict cleanly.",
        )
    if ligand == "caffeine":
        return (
            "must_remain_deferred",
            "Keep deferred until local target-specific human PXR evidence exists; absence of evidence is not enough to relabel.",
        )
    if ligand == "bexarotene":
        return (
            "must_remain_deferred",
            "Keep deferred until target-specific human PXR quantitative provenance closes the binder-gap row cleanly.",
        )
    return ("must_remain_deferred", "Keep current deferred/review-only state unless the blocker is explicitly reduced by local target-specific human evidence.")


def _default_commit_status(*, commit_class: str, resolution_bias: str) -> str:
    if commit_class == "confirm_now" or resolution_bias == "review_only":
        return "confirmed_review_only"
    return "confirmed_defer"


def _ligands(rows: list[dict[str, Any]], *, commit_class: str | None = None) -> list[str]:
    out: list[str] = []
    for row in rows:
        if commit_class and str(row.get("commit_class", "")).strip() != commit_class:
            continue
        ligand = str(row.get("ligand", "")).strip()
        if ligand:
            out.append(ligand)
    return out


def build_payload(
    workbench_payload: dict[str, Any],
    pending_packet_payload: dict[str, Any],
    draft_packet_payload: dict[str, Any],
    day_plan_payload: dict[str, Any],
    existing_sheet: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    existing_sheet = existing_sheet or {}
    workbench_s = dict(workbench_payload.get("summary", {}) or {})
    pending_s = dict(pending_packet_payload.get("summary", {}) or {})
    draft_s = dict(draft_packet_payload.get("summary", {}) or {})
    day_s = dict(day_plan_payload.get("summary", {}) or {})

    rows: list[dict[str, Any]] = []
    for row in draft_packet_payload.get("rows", []) or []:
        step = str(row.get("packet_step", "")).strip()
        existing = existing_sheet.get(step, {})
        commit_class, commit_note = _commit_decision(row, existing)
        rows.append(
            {
                "commit_rank": 0,
                "plan_phase": str(row.get("plan_phase", "")).strip(),
                "priority_rank": int(str(row.get("priority_rank", "999")).strip() or 999),
                "packet_step": step,
                "ligand": str(row.get("ligand", "")).strip(),
                "binder": int(row.get("binder", 0) or 0),
                "resolution_bias": str(row.get("resolution_bias", "")).strip(),
                "commit_class": commit_class,
                "commit_note": commit_note,
                "stop_condition": str(row.get("explicit_stop_condition", "")).strip(),
                "staged_commit_class": commit_class,
                "staged_resolution_bias": str(row.get("resolution_bias", "")).strip(),
                "staged_assay_type_honesty": str(row.get("assay_type_honesty", "")).strip(),
                "staged_promotion_blocker": str(row.get("promotion_blocker", "")).strip(),
                "staged_next_required_action": str(row.get("next_required_action", "")).strip(),
                "staged_commit_note": commit_note,
                "manual_commit_class": str(existing.get("manual_commit_class", "")).strip(),
                "manual_resolution_bias": str(existing.get("manual_resolution_bias", "")).strip(),
                "manual_assay_type_honesty": str(existing.get("manual_assay_type_honesty", "")).strip(),
                "manual_promotion_blocker": str(existing.get("manual_promotion_blocker", "")).strip(),
                "manual_next_required_action": str(existing.get("manual_next_required_action", "")).strip(),
                "manual_commit_note": str(existing.get("manual_commit_note", "")).strip(),
                "commit_status": str(existing.get("commit_status", _default_commit_status(commit_class=commit_class, resolution_bias=str(row.get("resolution_bias", "")).strip()))).strip(),
            }
        )

    phase_order = {"first_hour": 0, "same_day_followup": 1, "second_pass": 2}
    rows.sort(key=lambda row: (phase_order.get(str(row["plan_phase"]), 9), int(row["priority_rank"]), str(row["packet_step"])))
    for idx, row in enumerate(rows, start=1):
        row["commit_rank"] = idx

    confirm_now_ligands = ", ".join(_ligands(rows, commit_class="confirm_now")) or "none"
    must_defer_ligands = ", ".join(_ligands(rows, commit_class="must_remain_deferred")) or "none"

    summary = {
        "family": str(draft_s.get("family", pending_s.get("family", workbench_s.get("family", "pxr")))).strip(),
        "target": str(draft_s.get("target", pending_s.get("target", day_s.get("target", "")))).strip(),
        "commit_row_count": len(rows),
        "confirm_now_count": sum(1 for row in rows if row["commit_class"] == "confirm_now"),
        "must_remain_deferred_count": sum(1 for row in rows if row["commit_class"] == "must_remain_deferred"),
        "review_only_row_count": int(pending_s.get("review_only_row_count", workbench_s.get("review_only_row_count", 0)) or 0),
        "defer_row_count": int(pending_s.get("defer_row_count", workbench_s.get("defer_row_count", 0)) or 0),
        "binder_gap_count": int(pending_s.get("binder_gap_count", workbench_s.get("binder_gap_count", 0)) or 0),
        "supportive_binder_review_count": int(pending_s.get("supportive_binder_review_count", workbench_s.get("supportive_binder_review_count", 0)) or 0),
        "confirmed_binder_quantitative_gap_count": int(
            pending_s.get(
                "confirmed_binder_quantitative_gap_count",
                workbench_s.get("confirmed_binder_quantitative_gap_count", 0),
            )
            or 0
        ),
        "ready_for_apply_row_count": int(day_s.get("ready_for_apply_row_count", pending_s.get("ready_for_apply_row_count", 0)) or 0),
        "blocked_row_count": int(day_s.get("blocked_row_count", pending_s.get("blocked_row_count", 0)) or 0),
        "pending_manual_commit_count": sum(1 for row in rows if row["commit_status"] == "pending_manual_commit"),
        "confirmed_manual_commit_count": sum(1 for row in rows if row["commit_status"] != "pending_manual_commit"),
        "policy_line": str(pending_s.get("policy_line", workbench_s.get("policy_line", ""))).strip(),
        "next_required_step": (
            f"Commit review-only rows now ({confirm_now_ligands}), keep deferred rows ({must_defer_ligands}) parked until local target-specific human evidence reduces their blockers, and keep supportive binder rows deferred until manual confirmation is complete."
            if int(pending_s.get("supportive_binder_review_count", workbench_s.get("supportive_binder_review_count", 0)) or 0)
            else f"Commit review-only rows now ({confirm_now_ligands}), keep deferred rows ({must_defer_ligands}) parked until local target-specific human evidence reduces their blockers, and keep literature-confirmed binder rows deferred until quantitative provenance is added."
            if int(
                pending_s.get(
                    "confirmed_binder_quantitative_gap_count",
                    workbench_s.get("confirmed_binder_quantitative_gap_count", 0),
                )
                or 0
            )
            else f"Commit review-only rows now ({confirm_now_ligands}), and keep deferred rows ({must_defer_ligands}) parked until local target-specific human evidence reduces their blockers."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# PXR Pending-Resolution Commit Packet",
        "",
        f"- family: `{s['family']}`",
        f"- target: `{s['target']}`",
        f"- commit_row_count: `{s['commit_row_count']}`",
        f"- confirm_now_count: `{s['confirm_now_count']}`",
        f"- must_remain_deferred_count: `{s['must_remain_deferred_count']}`",
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
        "## Commit Rows",
        "",
        "| commit_rank | plan_phase | priority_rank | packet_step | ligand | binder | commit_class | commit_note |",
        "| ---: | --- | ---: | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['commit_rank']} | `{row['plan_phase']}` | {row['priority_rank']} | `{row['packet_step']}` | "
            f"`{row['ligand']}` | {row['binder']} | `{row['commit_class']}` | {row['commit_note']} |"
        )
    lines.extend(
        [
            "",
            "## Stop Conditions",
            "",
        ]
    )
    for row in payload["rows"]:
        lines.append(f"- `{row['ligand']}`: {row['stop_condition']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a PXR pending-resolution commit packet after the reviewer draft packet.")
    parser.add_argument("--workbench-json", default=DEFAULT_WORKBENCH_JSON)
    parser.add_argument("--pending-packet-json", default=DEFAULT_PENDING_PACKET_JSON)
    parser.add_argument("--draft-packet-json", default=DEFAULT_DRAFT_PACKET_JSON)
    parser.add_argument("--day-plan-json", default=DEFAULT_DAY_PLAN_JSON)
    parser.add_argument("--existing-sheet-csv", default="")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_csv = _resolve(args.out_csv)
    payload = build_payload(
        _load_json(args.workbench_json),
        _load_json(args.pending_packet_json),
        _load_json(args.draft_packet_json),
        _load_json(args.day_plan_json),
        existing_sheet=_existing_by_step(_resolve(args.existing_sheet_csv)) if str(args.existing_sheet_csv).strip() else _existing_by_step(out_csv),
    )

    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
