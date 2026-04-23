#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DASHBOARD_JSON = "runs/transporter_manual_review_dashboard_current.json"
DEFAULT_LOCAL_EVIDENCE_JSON = "runs/aqp1_local_evidence_note_current.json"
DEFAULT_EVIDENCE_LEDGER_JSON = "runs/aqp1_candidate_evidence_ledger_current.json"
DEFAULT_CANDIDATE_VERDICT_JSON = "runs/aqp1_candidate_verdict_sheet_current.json"
DEFAULT_BINDER_SHEET_JSON = "runs/aqp1_binder_verdict_update_sheet_current.json"
DEFAULT_APPLY_DRAFT_JSON = "runs/aqp1_manual_verdict_apply_draft_current.json"
DEFAULT_MANUAL_QUEUE_JSON = "runs/aqp1_manual_review_queue_current.json"
DEFAULT_NEXT_SLICE_JSON = "runs/aqp1_next_verification_slice_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_manual_verdict_handoff_packet_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_manual_verdict_handoff_packet_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_manual_verdict_handoff_packet_current.md"


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


def _aqp1_target_row(dashboard_payload: dict[str, Any]) -> dict[str, Any]:
    for row in dashboard_payload.get("target_rows", []) or []:
        if str(row.get("target_id", "")).strip() == "AQP1":
            return row
    return {}


def _index_by(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = str(row.get(key, "")).strip()
        if value:
            out[value] = row
    return out


def build_payload(
    dashboard_payload: dict[str, Any],
    local_evidence_payload: dict[str, Any],
    evidence_ledger_payload: dict[str, Any],
    candidate_verdict_payload: dict[str, Any],
    binder_sheet_payload: dict[str, Any],
    apply_draft_payload: dict[str, Any],
    manual_queue_payload: dict[str, Any],
    next_slice_payload: dict[str, Any],
) -> dict[str, Any]:
    target_row = _aqp1_target_row(dashboard_payload)
    ledger_by_name = _index_by(evidence_ledger_payload.get("rows", []) or [], "candidate_name")
    verdict_by_name = _index_by(candidate_verdict_payload.get("rows", []) or [], "candidate_name")
    draft_by_name = _index_by(apply_draft_payload.get("rows", []) or [], "candidate_name")
    queue_by_step = _index_by(manual_queue_payload.get("rows", []) or [], "packet_step")
    slice_by_step = _index_by(next_slice_payload.get("rows", []) or [], "packet_step")

    handoff_rows: list[dict[str, Any]] = []

    for sheet_row in binder_sheet_payload.get("sheet_rows", []) or []:
        candidate_name = str(sheet_row.get("candidate_name", "")).strip()
        packet_step = str(sheet_row.get("packet_step", "")).strip()
        ledger = ledger_by_name.get(candidate_name, {})
        verdict = verdict_by_name.get(candidate_name, {})
        draft = draft_by_name.get(candidate_name, {})
        queue_row = queue_by_step.get(packet_step, {})
        slice_row = slice_by_step.get(packet_step, {})
        handoff_rows.append(
            {
                "section": "binder_first_wave",
                "priority_rank": str(sheet_row.get("priority_rank", "")).strip(),
                "packet_step": packet_step,
                "candidate_name": candidate_name,
                "anchor": str(sheet_row.get("source_anchor", "")).strip(),
                "review_bucket": str(verdict.get("review_bucket", sheet_row.get("current_review_bucket", ""))).strip(),
                "recommended_verdict": str(verdict.get("recommended_verdict", sheet_row.get("current_recommended_verdict", ""))).strip(),
                "draft_manual_verdict_update": str(draft.get("draft_manual_verdict_update", "")).strip(),
                "draft_manual_confidence_update": str(draft.get("draft_manual_confidence_update", "")).strip(),
                "evidence_strength": str(sheet_row.get("evidence_strength", "")).strip(),
                "mechanism_bucket": str(ledger.get("mechanism_bucket", "")).strip(),
                "assay_surface": str(ledger.get("assay_surface", "")).strip(),
                "potency_or_signal": str(sheet_row.get("potency_or_signal", "")).strip(),
                "promotion_blocker": str(sheet_row.get("promotion_blocker", "")).strip(),
                "next_action": str(slice_row.get("next_action", sheet_row.get("next_required_action", ""))).strip(),
                "reviewer_checklist": str(draft.get("reviewer_checklist", "")).strip(),
                "caution": str(sheet_row.get("caution", "")).strip(),
            }
        )

    for verdict_row in candidate_verdict_payload.get("rows", []) or []:
        packet_step = str(verdict_row.get("proposed_packet_step", "")).strip()
        if packet_step.startswith("core_binder_"):
            continue
        candidate_name = str(verdict_row.get("candidate_name", "")).strip()
        ledger = ledger_by_name.get(candidate_name, {})
        slice_row = slice_by_step.get(packet_step, {})
        handoff_rows.append(
            {
                "section": "caution_or_defer_reference",
                "priority_rank": "",
                "packet_step": packet_step,
                "candidate_name": candidate_name,
                "anchor": str(verdict_row.get("source_anchor", "")).strip(),
                "review_bucket": str(verdict_row.get("review_bucket", "")).strip(),
                "recommended_verdict": str(verdict_row.get("recommended_verdict", "")).strip(),
                "draft_manual_verdict_update": "",
                "draft_manual_confidence_update": str(ledger.get("confidence", "")).strip(),
                "evidence_strength": str(ledger.get("confidence", "")).strip(),
                "mechanism_bucket": str(ledger.get("mechanism_bucket", "")).strip(),
                "assay_surface": str(ledger.get("assay_surface", "")).strip(),
                "potency_or_signal": str(ledger.get("potency_or_signal", "")).strip(),
                "promotion_blocker": str(verdict_row.get("promotion_policy", "")).strip(),
                "next_action": str(slice_row.get("next_action", "review_primary_source_and_decide_keep_review_only_or_defer")).strip(),
                "reviewer_checklist": "confirm_reference_only;do_not_promote;record_if_defer_is_final",
                "caution": str(verdict_row.get("caution", "")).strip(),
            }
        )

    for queue_row in manual_queue_payload.get("rows", []) or []:
        packet_step = str(queue_row.get("packet_step", "")).strip()
        if not packet_step.startswith("core_non_binder_"):
            continue
        handoff_rows.append(
            {
                "section": "negative_slot_policy",
                "priority_rank": str(queue_row.get("priority_rank", "")).strip(),
                "packet_step": packet_step,
                "candidate_name": str(queue_row.get("current_ligand_id", "")).strip(),
                "anchor": "",
                "review_bucket": str(queue_row.get("review_bucket", "")).strip(),
                "recommended_verdict": "keep_review_only",
                "draft_manual_verdict_update": "",
                "draft_manual_confidence_update": "",
                "evidence_strength": "",
                "mechanism_bucket": "",
                "assay_surface": "",
                "potency_or_signal": "",
                "promotion_blocker": str(queue_row.get("promotion_blocker", "")).strip(),
                "next_action": str(queue_row.get("next_required_action", "")).strip(),
                "reviewer_checklist": "confirm_negative_review_only;do_not_inject_proxy_value",
                "caution": str(queue_row.get("notes", "")).strip(),
            }
        )

    binder_sheet_summary = dict(binder_sheet_payload.get("summary", {}) or {})

    summary = {
        "target_id": "AQP1",
        "endpoint_status": str(local_evidence_payload.get("summary", {}).get("endpoint_status", "")).strip(),
        "local_evidence_status": str(target_row.get("local_evidence_status", "")).strip(),
        "authoritative_apply_allowed": False,
        "binder_first_wave_count": sum(1 for row in handoff_rows if row["section"] == "binder_first_wave"),
        "caution_or_defer_reference_count": sum(1 for row in handoff_rows if row["section"] == "caution_or_defer_reference"),
        "negative_slot_policy_count": sum(1 for row in handoff_rows if row["section"] == "negative_slot_policy"),
        "pending_manual_verdict_count": int(
            binder_sheet_summary.get("pending_manual_verdict_count", target_row.get("binder_pending_manual_verdict_count", 0)) or 0
        ),
        "placeholder_rows": int(target_row.get("placeholder_rows", 0) or 0),
        "p0_todo_count": int(target_row.get("p0_todo_count", 0) or 0),
        "fit_donor_target": str(local_evidence_payload.get("summary", {}).get("temporary_fit_donor_target", "")).strip(),
        "next_required_step": str(target_row.get("next_required_step", "")).strip()
        or str(local_evidence_payload.get("summary", {}).get("next_required_step", "")).strip(),
    }

    checklist = [
        "Confirm the three first-wave binder anchors remain review-only and do not cross into authoritative apply.",
        "Keep tetraethylammonium and acetazolamide in caution/defer reference territory only.",
        "Leave all three negative slots review-only; do not inject proxy non-binder values.",
        "Do not reopen transporter donor policy while AQP1 remains placeholder-driven and local binder evidence is uncurated.",
    ]
    return {"summary": summary, "checklist": checklist, "rows": handoff_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Manual Verdict Handoff Packet",
        "",
        f"- target_id: `{s['target_id']}`",
        f"- endpoint_status: `{s['endpoint_status']}`",
        f"- local_evidence_status: `{s['local_evidence_status']}`",
        f"- authoritative_apply_allowed: `{s['authoritative_apply_allowed']}`",
        f"- binder_first_wave_count: `{s['binder_first_wave_count']}`",
        f"- caution_or_defer_reference_count: `{s['caution_or_defer_reference_count']}`",
        f"- negative_slot_policy_count: `{s['negative_slot_policy_count']}`",
        f"- pending_manual_verdict_count: `{s['pending_manual_verdict_count']}`",
        f"- placeholder_rows: `{s['placeholder_rows']}`",
        f"- p0_todo_count: `{s['p0_todo_count']}`",
        f"- fit_donor_target: `{s['fit_donor_target']}`",
        "",
        "## Reviewer Checklist",
        "",
    ]
    for item in payload["checklist"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Handoff Rows",
            "",
            "| section | priority_rank | packet_step | candidate_name | recommended_verdict | draft_manual_verdict_update | anchor | next_action |",
            "| --- | ---: | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| `{row['section']}` | {row['priority_rank']} | `{row['packet_step']}` | `{row['candidate_name']}` | "
            f"`{row['recommended_verdict']}` | `{row['draft_manual_verdict_update']}` | `{row['anchor']}` | `{row['next_action']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an AQP1 reviewer handoff packet consolidating current AQP1 draft/manual-review artifacts.")
    parser.add_argument("--dashboard-json", default=DEFAULT_DASHBOARD_JSON)
    parser.add_argument("--local-evidence-json", default=DEFAULT_LOCAL_EVIDENCE_JSON)
    parser.add_argument("--evidence-ledger-json", default=DEFAULT_EVIDENCE_LEDGER_JSON)
    parser.add_argument("--candidate-verdict-json", default=DEFAULT_CANDIDATE_VERDICT_JSON)
    parser.add_argument("--binder-sheet-json", default=DEFAULT_BINDER_SHEET_JSON)
    parser.add_argument("--apply-draft-json", default=DEFAULT_APPLY_DRAFT_JSON)
    parser.add_argument("--manual-queue-json", default=DEFAULT_MANUAL_QUEUE_JSON)
    parser.add_argument("--next-slice-json", default=DEFAULT_NEXT_SLICE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.dashboard_json),
        _load_json(args.local_evidence_json),
        _load_json(args.evidence_ledger_json),
        _load_json(args.candidate_verdict_json),
        _load_json(args.binder_sheet_json),
        _load_json(args.apply_draft_json),
        _load_json(args.manual_queue_json),
        _load_json(args.next_slice_json),
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
