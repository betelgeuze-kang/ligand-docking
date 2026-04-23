#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_LOCAL_EVIDENCE_NOTE_JSON = "runs/glut1_local_evidence_note_current.json"
DEFAULT_EXTERNAL_SEED_JSON = "runs/glut1_external_evidence_seed_current.json"
DEFAULT_MANUAL_REVIEW_QUEUE_JSON = "runs/glut1_manual_review_queue_current.json"
DEFAULT_CANDIDATE_VERDICT_JSON = "runs/glut1_candidate_verdict_sheet_current.json"
DEFAULT_PENDING_DISPOSITION_JSON = "runs/glut1_pending_row_disposition_current.json"
DEFAULT_BINDER_VERDICT_SHEET_JSON = "runs/glut1_binder_verdict_update_sheet_current.json"
DEFAULT_MANUAL_VERDICT_APPLY_DRAFT_JSON = "runs/glut1_manual_verdict_apply_draft_current.json"
DEFAULT_TRANSPORTER_DASHBOARD_JSON = "runs/transporter_manual_review_dashboard_current.json"
DEFAULT_OUT_JSON = "runs/glut1_manual_verdict_handoff_packet_current.json"
DEFAULT_OUT_CSV = "runs/glut1_manual_verdict_handoff_packet_current.csv"
DEFAULT_OUT_MD = "runs/glut1_manual_verdict_handoff_packet_current.md"


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
    local_evidence_note: dict[str, Any],
    external_seed: dict[str, Any],
    manual_review_queue: dict[str, Any],
    candidate_verdict: dict[str, Any],
    pending_disposition: dict[str, Any],
    binder_verdict_sheet: dict[str, Any],
    manual_verdict_apply_draft: dict[str, Any],
    transporter_dashboard: dict[str, Any],
) -> dict[str, Any]:
    dashboard_row = _glut1_target_row(transporter_dashboard)
    seed_by_step = _keyed(external_seed.get("rows", []) or [], "proposed_packet_step")
    verdict_by_step = _keyed(candidate_verdict.get("rows", []) or [], "proposed_packet_step")
    queue_by_step = _keyed(manual_review_queue.get("rows", []) or [], "packet_step")
    pending_by_step = _keyed(pending_disposition.get("rows", []) or [], "packet_step")
    draft_by_step = _keyed(manual_verdict_apply_draft.get("draft_rows", []) or [], "packet_step")

    binder_rows: list[dict[str, Any]] = []
    for row in binder_verdict_sheet.get("sheet_rows", []) or []:
        step = str(row.get("packet_step", "")).strip()
        seed = seed_by_step.get(step, {})
        verdict = verdict_by_step.get(step, {})
        queue = queue_by_step.get(step, {})
        pending = pending_by_step.get(step, {})
        draft = draft_by_step.get(step, {})
        binder_rows.append(
            {
                "row_type": "binder",
                "priority_rank": str(row.get("priority_rank", "")).strip(),
                "packet_step": step,
                "candidate_name": str(row.get("candidate_name", "")).strip(),
                "source_anchor": str(row.get("source_anchor", "")).strip(),
                "source_url": str(row.get("source_url", "")).strip(),
                "evidence_strength": str(row.get("evidence_strength", "")).strip(),
                "review_bucket": str(verdict.get("review_bucket", "")).strip() or str(queue.get("suggested_external_review_bucket", "")).strip(),
                "recommended_verdict": str(verdict.get("recommended_verdict", "")).strip() or str(row.get("current_recommended_verdict", "")).strip(),
                "draft_manual_verdict_update": str(draft.get("draft_manual_verdict_update", "")).strip(),
                "draft_manual_confidence_update": str(draft.get("draft_manual_confidence_update", "")).strip(),
                "draft_update_status": str(draft.get("draft_update_status", "")).strip(),
                "promotion_blocker": str(row.get("promotion_blocker", "")).strip() or str(queue.get("promotion_blocker", "")).strip() or str(pending.get("promotion_blocker", "")).strip(),
                "next_required_action": str(row.get("next_required_action", "")).strip() or str(queue.get("next_required_action", "")).strip() or str(pending.get("next_required_action", "")).strip(),
                "caution": str(seed.get("caution", "")).strip() or str(row.get("caution", "")).strip(),
            }
        )

    negative_rows: list[dict[str, Any]] = []
    for row in manual_review_queue.get("rows", []) or []:
        if str(row.get("replacement_is_binder", "")).strip() == "1":
            continue
        step = str(row.get("packet_step", "")).strip()
        pending = pending_by_step.get(step, {})
        negative_rows.append(
            {
                "row_type": "negative",
                "priority_rank": str(row.get("priority_rank", "")).strip(),
                "packet_step": step,
                "current_ligand_id": str(row.get("current_ligand_id", "")).strip(),
                "review_bucket": str(row.get("review_bucket", "")).strip() or str(pending.get("disposition", "")).strip(),
                "promotion_blocker": str(row.get("promotion_blocker", "")).strip() or str(pending.get("promotion_blocker", "")).strip(),
                "next_required_action": str(row.get("next_required_action", "")).strip() or str(pending.get("next_required_action", "")).strip(),
                "required_missing_fields": str(row.get("required_missing_fields", "")).strip(),
                "notes": str(row.get("notes", "")).strip(),
            }
        )

    summary = {
        "target_id": "GLUT1",
        "wave": "second_wave",
        "local_evidence_status": str(dashboard_row.get("local_evidence_status", "")).strip() or str(local_evidence_note.get("summary", {}).get("endpoint_status", "")).strip(),
        "binder_slot_count": len(binder_rows),
        "negative_slot_count": len(negative_rows),
        "external_candidate_count": int(external_seed.get("summary", {}).get("candidate_count", 0) or 0),
        "recommended_second_wave_candidate_count": int(external_seed.get("summary", {}).get("draft_second_wave_candidate_count", 0) or 0),
        "binder_pending_manual_verdict_count": int(binder_verdict_sheet.get("summary", {}).get("pending_manual_verdict_count", 0) or 0),
        "authoritative_manual_fields_touched_count": int(manual_verdict_apply_draft.get("summary", {}).get("authoritative_manual_fields_touched_count", 0) or 0),
        "placeholder_rows": int(dashboard_row.get("placeholder_rows", 0) or 0),
        "family_decision_status": str(transporter_dashboard.get("summary", {}).get("family_decision_status", "")).strip(),
        "scaffold_fit_donor_target": str(transporter_dashboard.get("summary", {}).get("scaffold_fit_donor_target", "")).strip(),
        "next_required_step": (
            str(dashboard_row.get("next_required_step", "")).strip()
            or str(manual_verdict_apply_draft.get("summary", {}).get("next_required_step", "")).strip()
            or "Keep GLUT1 manual-review only and finish reviewer-side verdict confirmation before any transporter packet promotion discussion."
        ),
    }
    handoff_rows = binder_rows + negative_rows
    return {"summary": summary, "binder_rows": binder_rows, "negative_rows": negative_rows, "handoff_rows": handoff_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# GLUT1 Manual Verdict Handoff Packet",
        "",
        f"- target_id: `{s['target_id']}`",
        f"- wave: `{s['wave']}`",
        f"- local_evidence_status: `{s['local_evidence_status']}`",
        f"- binder_slot_count: `{s['binder_slot_count']}`",
        f"- negative_slot_count: `{s['negative_slot_count']}`",
        f"- external_candidate_count: `{s['external_candidate_count']}`",
        f"- recommended_second_wave_candidate_count: `{s['recommended_second_wave_candidate_count']}`",
        f"- binder_pending_manual_verdict_count: `{s['binder_pending_manual_verdict_count']}`",
        f"- authoritative_manual_fields_touched_count: `{s['authoritative_manual_fields_touched_count']}`",
        f"- placeholder_rows: `{s['placeholder_rows']}`",
        f"- family_decision_status: `{s['family_decision_status']}`",
        f"- scaffold_fit_donor_target: `{s['scaffold_fit_donor_target']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Binder Rows",
        "",
        "| priority_rank | packet_step | candidate_name | source_anchor | evidence_strength | review_bucket | recommended_verdict | draft_manual_verdict_update | draft_update_status | promotion_blocker | next_required_action |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["binder_rows"]:
        lines.append(
            f"| {row['priority_rank']} | `{row['packet_step']}` | `{row['candidate_name']}` | "
            f"`{row['source_anchor']}` | `{row['evidence_strength']}` | `{row['review_bucket']}` | "
            f"`{row['recommended_verdict']}` | `{row['draft_manual_verdict_update']}` | "
            f"`{row['draft_update_status']}` | `{row['promotion_blocker']}` | `{row['next_required_action']}` |"
        )
    lines.extend(
        [
            "",
            "## Negative Rows",
            "",
            "| priority_rank | packet_step | current_ligand_id | review_bucket | promotion_blocker | next_required_action | required_missing_fields |",
            "| ---: | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["negative_rows"]:
        lines.append(
            f"| {row['priority_rank']} | `{row['packet_step']}` | `{row['current_ligand_id']}` | "
            f"`{row['review_bucket']}` | `{row['promotion_blocker']}` | `{row['next_required_action']}` | "
            f"`{row['required_missing_fields']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a GLUT1 reviewer handoff packet from the current GLUT1 review artifacts.")
    parser.add_argument("--local-evidence-note-json", default=DEFAULT_LOCAL_EVIDENCE_NOTE_JSON)
    parser.add_argument("--external-seed-json", default=DEFAULT_EXTERNAL_SEED_JSON)
    parser.add_argument("--manual-review-queue-json", default=DEFAULT_MANUAL_REVIEW_QUEUE_JSON)
    parser.add_argument("--candidate-verdict-json", default=DEFAULT_CANDIDATE_VERDICT_JSON)
    parser.add_argument("--pending-disposition-json", default=DEFAULT_PENDING_DISPOSITION_JSON)
    parser.add_argument("--binder-verdict-sheet-json", default=DEFAULT_BINDER_VERDICT_SHEET_JSON)
    parser.add_argument("--manual-verdict-apply-draft-json", default=DEFAULT_MANUAL_VERDICT_APPLY_DRAFT_JSON)
    parser.add_argument("--transporter-dashboard-json", default=DEFAULT_TRANSPORTER_DASHBOARD_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.local_evidence_note_json),
        _load_json(args.external_seed_json),
        _load_json(args.manual_review_queue_json),
        _load_json(args.candidate_verdict_json),
        _load_json(args.pending_disposition_json),
        _load_json(args.binder_verdict_sheet_json),
        _load_json(args.manual_verdict_apply_draft_json),
        _load_json(args.transporter_dashboard_json),
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
