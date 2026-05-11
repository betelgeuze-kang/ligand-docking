#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_MANUAL_REVIEW_QUEUE_JSON = "runs/glut1_manual_review_queue_current.json"
DEFAULT_PENDING_DISPOSITION_JSON = "runs/glut1_pending_row_disposition_current.json"
DEFAULT_LOCAL_EVIDENCE_NOTE_JSON = "runs/glut1_local_evidence_note_current.json"
DEFAULT_CANDIDATE_VERDICT_JSON = "runs/glut1_candidate_verdict_sheet_current.json"
DEFAULT_NEXT_VERIFICATION_SLICE_JSON = "runs/glut1_next_verification_slice_current.json"
DEFAULT_TRANSPORTER_DASHBOARD_JSON = "runs/transporter_manual_review_dashboard_current.json"
DEFAULT_SOURCE_CONFIRMATION_JSON = "runs/glut1_second_wave_source_confirmation_packet_current.json"
DEFAULT_OUT_JSON = "runs/glut1_negative_review_handoff_packet_current.json"
DEFAULT_OUT_CSV = "runs/glut1_negative_review_handoff_packet_current.csv"
DEFAULT_OUT_MD = "runs/glut1_negative_review_handoff_packet_current.md"


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


def _glut1_target_row(dashboard_payload: dict[str, Any]) -> dict[str, Any]:
    for row in dashboard_payload.get("target_rows", []) or []:
        if str(row.get("target_id", "")).strip() == "GLUT1":
            return dict(row)
    return {}


def _keyed(rows: list[dict[str, Any]], key_name: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get(key_name, "")).strip()
        if key:
            out[key] = dict(row)
    return out


def build_payload(
    manual_review_queue: dict[str, Any],
    pending_disposition: dict[str, Any],
    local_evidence_note: dict[str, Any],
    candidate_verdict: dict[str, Any],
    next_verification_slice: dict[str, Any],
    transporter_dashboard: dict[str, Any],
    source_confirmation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dashboard_row = _glut1_target_row(transporter_dashboard)
    source_summary = dict((source_confirmation or {}).get("summary", {}) or {})
    pending_by_step = _keyed(pending_disposition.get("rows", []) or [], "packet_step")
    slice_by_step = _keyed(next_verification_slice.get("rows", []) or [], "packet_step")
    source_context_artifact = (
        str(source_summary.get("packet_artifact", "")).strip()
        or "runs/glut1_second_wave_source_confirmation_packet_current.md"
    )
    source_context_primary_focus_ligand = str(source_summary.get("primary_focus_ligand", "")).strip()
    source_context_direct_quantitative_binding_count = int(
        source_summary.get("direct_quantitative_binding_count", 0) or 0
    )
    source_context_exact_target_pair_activity_count = int(
        source_summary.get("exact_target_pair_activity_count", 0) or 0
    )
    source_context_claim_safe_kcal_ready_count = int(source_summary.get("claim_safe_kcal_ready_count", 0) or 0)

    negative_rows: list[dict[str, Any]] = []
    for row in manual_review_queue.get("rows", []) or []:
        if str(row.get("replacement_is_binder", "")).strip() != "0":
            continue
        step = str(row.get("packet_step", "")).strip()
        disposition = pending_by_step.get(step, {})
        slice_row = slice_by_step.get(step, {})
        negative_rows.append(
            {
                "row_type": "negative_review",
                "priority_rank": str(row.get("priority_rank", "")).strip(),
                "packet_step": step,
                "current_ligand_id": str(row.get("current_ligand_id", "")).strip(),
                "review_bucket": str(row.get("review_bucket", "")).strip() or str(disposition.get("disposition", "")).strip(),
                "promotion_blocker": str(row.get("promotion_blocker", "")).strip() or str(disposition.get("promotion_blocker", "")).strip(),
                "next_required_action": str(row.get("next_required_action", "")).strip() or str(disposition.get("next_required_action", "")).strip(),
                "required_missing_fields": str(row.get("required_missing_fields", "")).strip(),
                "verification_queue_action": str(slice_row.get("next_action", "")).strip(),
                "source_context_artifact": source_context_artifact,
                "source_context_primary_focus_ligand": source_context_primary_focus_ligand,
                "source_context_role": "positive_or_binder_context_not_negative_evidence",
                "source_context_direct_quantitative_binding_count": source_context_direct_quantitative_binding_count,
                "source_context_exact_target_pair_activity_count": source_context_exact_target_pair_activity_count,
                "source_context_claim_safe_kcal_ready_count": source_context_claim_safe_kcal_ready_count,
                "authoritative_negative_apply_allowed": False,
                "notes": str(row.get("notes", "")).strip(),
            }
        )

    caution_signal_rows: list[dict[str, Any]] = []
    for row in candidate_verdict.get("rows", []) or []:
        step = str(row.get("proposed_packet_step", "")).strip()
        review_bucket = str(row.get("review_bucket", "")).strip()
        verdict = str(row.get("recommended_verdict", "")).strip()
        if step != "caution_only" and review_bucket not in {"review_only_tool_reference", "defer_polypharmacology"}:
            continue
        slice_row = slice_by_step.get(step, {})
        caution_signal_rows.append(
            {
                "row_type": "caution_signal",
                "priority_rank": str(len(caution_signal_rows) + 1),
                "candidate_name": str(row.get("candidate_name", "")).strip(),
                "proposed_packet_step": step,
                "review_bucket": review_bucket,
                "recommended_verdict": verdict,
                "source_anchor": str(row.get("source_anchor", "")).strip(),
                "caution": str(row.get("caution", "")).strip(),
                "verification_queue_action": str(slice_row.get("next_action", "")).strip(),
                "source_context_role": "caution_signal_not_negative_evidence",
                "authoritative_negative_apply_allowed": False,
            }
        )

    summary = {
        "target_id": "GLUT1",
        "packet_artifact": "runs/glut1_negative_review_handoff_packet_current.md",
        "local_evidence_status": str(dashboard_row.get("local_evidence_status", "")).strip() or str(local_evidence_note.get("summary", {}).get("endpoint_status", "")).strip(),
        "local_quantitative_negative_evidence_curated": bool(local_evidence_note.get("summary", {}).get("local_quantitative_negative_evidence_curated", False)),
        "negative_slot_count": len(negative_rows),
        "caution_signal_count": len(caution_signal_rows),
        "placeholder_rows": int(dashboard_row.get("placeholder_rows", 0) or 0),
        "negative_review_only_rows": int(dashboard_row.get("negative_review_only_rows", 0) or 0),
        "source_context_artifact": source_context_artifact,
        "source_context_primary_focus_ligand": source_context_primary_focus_ligand,
        "source_context_direct_quantitative_binding_count": source_context_direct_quantitative_binding_count,
        "source_context_exact_target_pair_activity_count": source_context_exact_target_pair_activity_count,
        "source_context_claim_safe_kcal_ready_count": source_context_claim_safe_kcal_ready_count,
        "source_context_negative_evidence_row_count": 0,
        "authoritative_negative_apply_allowed": False,
        "family_decision_status": str(transporter_dashboard.get("summary", {}).get("family_decision_status", "")).strip(),
        "scaffold_fit_donor_target": str(transporter_dashboard.get("summary", {}).get("scaffold_fit_donor_target", "")).strip(),
        "next_required_step": (
            "Keep GLUT1 non-binder rows review-only, keep caution-only tool/polypharmacology signals out of authoritative apply, "
            "and do not inject proxy negative values while local quantitative negative evidence remains uncurated."
        ),
    }
    return {
        "summary": summary,
        "negative_rows": negative_rows,
        "caution_signal_rows": caution_signal_rows,
        "handoff_rows": negative_rows + caution_signal_rows,
        "rows": negative_rows + caution_signal_rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# GLUT1 Negative Review Handoff Packet",
        "",
        f"- target_id: `{s['target_id']}`",
        f"- packet_artifact: `{s['packet_artifact']}`",
        f"- local_evidence_status: `{s['local_evidence_status']}`",
        f"- local_quantitative_negative_evidence_curated: `{s['local_quantitative_negative_evidence_curated']}`",
        f"- negative_slot_count: `{s['negative_slot_count']}`",
        f"- caution_signal_count: `{s['caution_signal_count']}`",
        f"- placeholder_rows: `{s['placeholder_rows']}`",
        f"- negative_review_only_rows: `{s['negative_review_only_rows']}`",
        f"- source_context_artifact: `{s['source_context_artifact']}`",
        f"- source_context_primary_focus_ligand: `{s['source_context_primary_focus_ligand']}`",
        f"- source_context_direct_quantitative_binding_count: `{s['source_context_direct_quantitative_binding_count']}`",
        f"- source_context_exact_target_pair_activity_count: `{s['source_context_exact_target_pair_activity_count']}`",
        f"- source_context_claim_safe_kcal_ready_count: `{s['source_context_claim_safe_kcal_ready_count']}`",
        f"- source_context_negative_evidence_row_count: `{s['source_context_negative_evidence_row_count']}`",
        f"- authoritative_negative_apply_allowed: `{s['authoritative_negative_apply_allowed']}`",
        f"- family_decision_status: `{s['family_decision_status']}`",
        f"- scaffold_fit_donor_target: `{s['scaffold_fit_donor_target']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Negative Rows",
        "",
        "| priority_rank | packet_step | current_ligand_id | review_bucket | promotion_blocker | source_context_role | next_required_action | verification_queue_action | required_missing_fields |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["negative_rows"]:
        lines.append(
            f"| {row['priority_rank']} | `{row['packet_step']}` | `{row['current_ligand_id']}` | "
            f"`{row['review_bucket']}` | `{row['promotion_blocker']}` | `{row['source_context_role']}` | "
            f"`{row['next_required_action']}` | "
            f"`{row['verification_queue_action']}` | `{row['required_missing_fields']}` |"
        )
    lines.extend(
        [
            "",
            "## Caution Signals",
            "",
            "| priority_rank | candidate_name | proposed_packet_step | review_bucket | recommended_verdict | source_anchor | verification_queue_action |",
            "| ---: | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["caution_signal_rows"]:
        lines.append(
            f"| {row['priority_rank']} | `{row['candidate_name']}` | `{row['proposed_packet_step']}` | "
            f"`{row['review_bucket']}` | `{row['recommended_verdict']}` | `{row['source_anchor']}` | "
            f"`{row['verification_queue_action']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a GLUT1 negative-review handoff packet from current GLUT1 non-binder and caution artifacts.")
    parser.add_argument("--manual-review-queue-json", default=DEFAULT_MANUAL_REVIEW_QUEUE_JSON)
    parser.add_argument("--pending-disposition-json", default=DEFAULT_PENDING_DISPOSITION_JSON)
    parser.add_argument("--local-evidence-note-json", default=DEFAULT_LOCAL_EVIDENCE_NOTE_JSON)
    parser.add_argument("--candidate-verdict-json", default=DEFAULT_CANDIDATE_VERDICT_JSON)
    parser.add_argument("--next-verification-slice-json", default=DEFAULT_NEXT_VERIFICATION_SLICE_JSON)
    parser.add_argument("--transporter-dashboard-json", default=DEFAULT_TRANSPORTER_DASHBOARD_JSON)
    parser.add_argument("--source-confirmation-json", default=DEFAULT_SOURCE_CONFIRMATION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.manual_review_queue_json),
        _load_json(args.pending_disposition_json),
        _load_json(args.local_evidence_note_json),
        _load_json(args.candidate_verdict_json),
        _load_json(args.next_verification_slice_json),
        _load_json(args.transporter_dashboard_json),
        _load_json(args.source_confirmation_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["handoff_rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
