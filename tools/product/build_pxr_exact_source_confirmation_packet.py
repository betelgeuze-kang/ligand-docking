#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CAPTURE_SHEET_JSON = "runs/pxr_unresolved_evidence_capture_sheet_current.json"
DEFAULT_INVESTIGATOR_PACKET_JSON = "runs/family_evidence_investigator_packet_current.json"
DEFAULT_LITERATURE_OVERLAY_JSON = "runs/pxr_literature_candidate_overlay_current.json"
DEFAULT_COMMIT_PACKET_JSON = "runs/pxr_pending_resolution_commit_packet_current.json"
DEFAULT_OUT_JSON = "runs/pxr_exact_source_confirmation_packet_current.json"
DEFAULT_OUT_CSV = "runs/pxr_exact_source_confirmation_packet_current.csv"
DEFAULT_OUT_MD = "runs/pxr_exact_source_confirmation_packet_current.md"


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


def _rows_by_step(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    payload = payload or {}
    return {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in payload.get("rows", []) or []
        if str(row.get("packet_step", "")).strip()
    }


def _focus_metadata(payload: dict[str, Any] | None) -> dict[str, dict[str, int]]:
    payload = payload or {}
    out: dict[str, dict[str, int]] = {}
    for row in payload.get("rows", []) or []:
        step = str(row.get("packet_step", "")).strip()
        if not step:
            continue
        out[step] = {
            "focus_rank": int(row.get("focus_rank", 0) or 0),
            "queue_rank": int(row.get("queue_rank", 0) or 0),
        }
    return out


def _capture_name(row: dict[str, Any]) -> str:
    return str(row.get("ligand", "")).strip() or str(row.get("replacement_ligand_id", "")).strip()


def _confirmation_scope(capture_row: dict[str, Any], literature_row: dict[str, Any]) -> str:
    blocker = str(capture_row.get("manual_promotion_blocker", "")).strip()
    signal = str(literature_row.get("best_candidate_signal", "")).strip()
    if blocker == "activity_present_manual_confirmation_required":
        return "supportive_binder_manual_confirmation"
    if signal == "title_direct_nonhuman_candidate":
        return "nonhuman_or_conflict_confirmation"
    return "exact_source_review"


def _acceptance_gate(scope: str) -> str:
    if scope == "supportive_binder_manual_confirmation":
        return (
            "Accept only if the cited source explicitly ties the ligand to human NR1I2/PXR/SXR target activity or binding in a target-specific assay context."
        )
    if scope == "nonhuman_or_conflict_confirmation":
        return (
            "Accept only if a source resolves the current conflict with human NR1I2/PXR target-specific evidence; otherwise keep the row deferred."
        )
    return "Accept only exact human NR1I2/PXR target-specific evidence with unambiguous ligand identity and assay context."


def _rejection_gate(scope: str) -> str:
    if scope == "supportive_binder_manual_confirmation":
        return "Reject mechanism-only rexinoid context, indirect CYP3A induction, or non-human-only support that does not cleanly confirm a human PXR binder row."
    if scope == "nonhuman_or_conflict_confirmation":
        return "Reject mice/preclinical-only mechanistic papers, proxy-only CYP3A responses, and any source that does not reduce the existing human PXR conflict."
    return "Reject review-like, non-target-specific, and non-human-only sources."


def _capture_instruction(scope: str) -> str:
    if scope == "supportive_binder_manual_confirmation":
        return "If confirmed, update the PXR capture sheet manual fields and keep binder-facing quantitative fields blank until claim-safe provenance is explicit."
    if scope == "nonhuman_or_conflict_confirmation":
        return "If not resolved, leave the current defer bucket unchanged and do not downgrade the row into a non-binder."
    return "Update the capture sheet only if the source clearly changes the current policy bucket."


def build_payload(
    capture_sheet_payload: dict[str, Any],
    investigator_packet_payload: dict[str, Any],
    literature_overlay_payload: dict[str, Any],
    commit_packet_payload: dict[str, Any],
) -> dict[str, Any]:
    capture_by_step = _rows_by_step(capture_sheet_payload)
    focus_by_step = _focus_metadata(investigator_packet_payload)
    literature_by_step = _rows_by_step(literature_overlay_payload)
    commit_by_step = _rows_by_step(commit_packet_payload)

    candidate_steps: set[str] = set()
    for step, capture_row in capture_by_step.items():
        blocker = str(capture_row.get("manual_promotion_blocker", "")).strip()
        if blocker != "activity_present_manual_confirmation_required":
            continue
        candidate_steps.add(step)

    rows: list[dict[str, Any]] = []
    for step in candidate_steps:
        capture_row = capture_by_step.get(step, {})
        literature_row = literature_by_step.get(step, {})
        blocker = str(capture_row.get("manual_promotion_blocker", "")).strip()
        status = str(literature_row.get("candidate_status", "")).strip()
        scope = _confirmation_scope(capture_row, literature_row)
        focus_meta = focus_by_step.get(step, {})
        rows.append(
            {
                "confirmation_rank": 0,
                "focus_rank": int(focus_meta.get("focus_rank", 0) or 0),
                "queue_rank": int(focus_meta.get("queue_rank", 0) or 0),
                "priority_rank": int(str(capture_row.get("priority_rank", "999")).strip() or 999),
                "packet_step": step,
                "ligand": _capture_name(capture_row),
                "confirmation_scope": scope,
                "capture_status": str(capture_row.get("capture_status", "")).strip(),
                "policy_bucket": str(capture_row.get("policy_bucket", "")).strip(),
                "manual_assay_type_honesty": str(capture_row.get("manual_assay_type_honesty", "")).strip(),
                "manual_promotion_blocker": blocker,
                "current_source_title": str(capture_row.get("source_title", "")).strip(),
                "current_source_url": str(capture_row.get("source_url", "")).strip(),
                "current_source_note": str(capture_row.get("source_note", "")).strip(),
                "literature_candidate_status": status,
                "best_candidate_pmid": str(literature_row.get("best_candidate_pmid", "")).strip(),
                "best_candidate_title": str(literature_row.get("best_candidate_title", "")).strip(),
                "best_candidate_url": str(literature_row.get("best_candidate_url", "")).strip(),
                "best_candidate_signal": str(literature_row.get("best_candidate_signal", "")).strip(),
                "best_candidate_mentions_human": str(literature_row.get("best_candidate_mentions_human", "")).strip(),
                "best_candidate_mentions_nonhuman": str(literature_row.get("best_candidate_mentions_nonhuman", "")).strip(),
                "best_candidate_review_like": str(literature_row.get("best_candidate_review_like", "")).strip(),
                "acceptance_gate": _acceptance_gate(scope),
                "rejection_gate": _rejection_gate(scope),
                "capture_instruction": _capture_instruction(scope),
                "current_commit_note": str(commit_by_step.get(step, {}).get("commit_note", "")).strip(),
            }
        )

    scope_order = {
        "supportive_binder_manual_confirmation": 0,
        "nonhuman_or_conflict_confirmation": 1,
        "exact_source_review": 2,
    }
    rows.sort(
        key=lambda row: (
            scope_order.get(str(row.get("confirmation_scope", "")), 9),
            int(row["focus_rank"] or 999) if int(row["focus_rank"] or 0) > 0 else 999,
            int(row["queue_rank"] or 999) if int(row["queue_rank"] or 0) > 0 else 999,
            int(row["priority_rank"] or 999),
            str(row["packet_step"]),
        )
    )
    for idx, row in enumerate(rows, start=1):
        row["confirmation_rank"] = idx

    summary = {
        "row_count": len(rows),
        "supportive_binder_confirmation_count": sum(
            1 for row in rows if row["confirmation_scope"] == "supportive_binder_manual_confirmation"
        ),
        "conflict_confirmation_count": sum(
            1 for row in rows if row["confirmation_scope"] == "nonhuman_or_conflict_confirmation"
        ),
        "title_direct_nonhuman_count": sum(
            1 for row in rows if row["best_candidate_signal"] == "title_direct_nonhuman_candidate"
        ),
        "primary_focus_ligand": str(rows[0].get("ligand", "")).strip() if rows else "",
        "next_required_step": (
            "Review supportive binder confirmation first, then treat title-direct non-human conflict papers as manual review only unless exact human PXR target evidence appears."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# PXR Exact-Source Confirmation Packet",
        "",
        f"- row_count: `{s['row_count']}`",
        f"- supportive_binder_confirmation_count: `{s['supportive_binder_confirmation_count']}`",
        f"- conflict_confirmation_count: `{s['conflict_confirmation_count']}`",
        f"- title_direct_nonhuman_count: `{s['title_direct_nonhuman_count']}`",
        f"- primary_focus_ligand: `{s['primary_focus_ligand']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Rows",
        "",
        "| confirmation_rank | ligand | packet_step | confirmation_scope | best_candidate_signal |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['confirmation_rank']} | `{row['ligand']}` | `{row['packet_step']}` | `{row['confirmation_scope']}` | `{row['best_candidate_signal'] or '-'}` |"
        )
    lines.extend(["", "## Reviewer Gates", ""])
    for row in payload["rows"]:
        lines.append(f"- `{row['ligand']}` accept: {row['acceptance_gate']}")
        lines.append(f"- `{row['ligand']}` reject: {row['rejection_gate']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a reviewer-facing exact-source confirmation packet for PXR manual-confirmation rows.")
    parser.add_argument("--capture-sheet-json", default=DEFAULT_CAPTURE_SHEET_JSON)
    parser.add_argument("--investigator-packet-json", default=DEFAULT_INVESTIGATOR_PACKET_JSON)
    parser.add_argument("--literature-overlay-json", default=DEFAULT_LITERATURE_OVERLAY_JSON)
    parser.add_argument("--commit-packet-json", default=DEFAULT_COMMIT_PACKET_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.capture_sheet_json),
        _load_json(args.investigator_packet_json),
        _load_json(args.literature_overlay_json),
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
