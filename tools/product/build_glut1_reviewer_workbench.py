#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MANUAL_VERDICT_HANDOFF_JSON = "runs/glut1_manual_verdict_handoff_packet_current.json"
DEFAULT_NEGATIVE_REVIEW_HANDOFF_JSON = "runs/glut1_negative_review_handoff_packet_current.json"
DEFAULT_APPLY_DRAFT_JSON = "runs/glut1_manual_verdict_apply_draft_current.json"
DEFAULT_CANDIDATE_VERDICT_JSON = "runs/glut1_candidate_verdict_sheet_current.json"
DEFAULT_LOCAL_EVIDENCE_JSON = "runs/glut1_local_evidence_note_current.json"
DEFAULT_OUT_JSON = "runs/glut1_reviewer_workbench_current.json"
DEFAULT_OUT_CSV = "runs/glut1_reviewer_workbench_current.csv"
DEFAULT_OUT_MD = "runs/glut1_reviewer_workbench_current.md"


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


def _candidate_index(candidate_verdict_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("proposed_packet_step", "")).strip(): row
        for row in (candidate_verdict_payload.get("rows", []) or [])
        if str(row.get("proposed_packet_step", "")).strip()
    }


def build_payload(
    manual_verdict_handoff_payload: dict[str, Any],
    negative_review_handoff_payload: dict[str, Any],
    apply_draft_payload: dict[str, Any],
    candidate_verdict_payload: dict[str, Any],
    local_evidence_payload: dict[str, Any],
) -> dict[str, Any]:
    candidate_by_step = _candidate_index(candidate_verdict_payload)
    apply_draft_by_step = {
        str(row.get("packet_step", "")).strip(): row
        for row in (apply_draft_payload.get("draft_rows", []) or [])
        if str(row.get("packet_step", "")).strip()
    }

    rows: list[dict[str, Any]] = []

    for row in manual_verdict_handoff_payload.get("binder_rows", []) or []:
        packet_step = str(row.get("packet_step", "")).strip()
        draft = apply_draft_by_step.get(packet_step, {})
        rows.append(
            {
                "workbench_section": "binder_second_wave",
                "priority_rank": str(row.get("priority_rank", "")).strip(),
                "packet_step": packet_step,
                "label": str(row.get("candidate_name", "")).strip(),
                "current_focus": "Confirm second-wave review-only hold and add explicit manual note.",
                "recommended_verdict": str(row.get("recommended_verdict", "")).strip(),
                "draft_manual_verdict_update": str(draft.get("draft_manual_verdict_update", row.get("draft_manual_verdict_update", ""))).strip(),
                "draft_manual_confidence_update": str(draft.get("draft_manual_confidence_update", row.get("draft_manual_confidence_update", ""))).strip(),
                "anchor": str(row.get("source_anchor", "")).strip(),
                "evidence_strength": str(row.get("evidence_strength", "")).strip(),
                "next_action": str(row.get("next_required_action", "")).strip(),
                "blocker_or_constraint": str(row.get("promotion_blocker", "")).strip(),
            }
        )

    for row in negative_review_handoff_payload.get("negative_rows", []) or []:
        rows.append(
            {
                "workbench_section": "negative_slot_policy",
                "priority_rank": str(row.get("priority_rank", "")).strip(),
                "packet_step": str(row.get("packet_step", "")).strip(),
                "label": str(row.get("current_ligand_id", "")).strip(),
                "current_focus": "Keep review-only negative slot blocked and avoid proxy fills.",
                "recommended_verdict": "keep_review_only",
                "draft_manual_verdict_update": "",
                "draft_manual_confidence_update": "",
                "anchor": "",
                "evidence_strength": "",
                "next_action": str(row.get("next_required_action", row.get("verification_queue_action", ""))).strip(),
                "blocker_or_constraint": str(row.get("promotion_blocker", "")).strip(),
            }
        )

    for row in negative_review_handoff_payload.get("caution_signal_rows", []) or []:
        verdict = candidate_by_step.get(str(row.get("proposed_packet_step", "")).strip(), {})
        rows.append(
            {
                "workbench_section": "caution_or_defer_signal",
                "priority_rank": str(row.get("priority_rank", "")).strip(),
                "packet_step": str(row.get("proposed_packet_step", "")).strip(),
                "label": str(row.get("candidate_name", "")).strip(),
                "current_focus": "Keep caution/defer reference out of packet rows.",
                "recommended_verdict": str(row.get("recommended_verdict", verdict.get("recommended_verdict", ""))).strip(),
                "draft_manual_verdict_update": "",
                "draft_manual_confidence_update": "",
                "anchor": str(row.get("source_anchor", "")).strip(),
                "evidence_strength": "",
                "next_action": str(row.get("verification_queue_action", "")).strip(),
                "blocker_or_constraint": str(verdict.get("promotion_policy", "caution_only_not_for_authoritative_apply")).strip(),
            }
        )

    summary = {
        "target_id": str(manual_verdict_handoff_payload.get("summary", {}).get("target_id", "GLUT1")).strip(),
        "wave": str(manual_verdict_handoff_payload.get("summary", {}).get("wave", "second_wave")).strip(),
        "endpoint_status": str(manual_verdict_handoff_payload.get("summary", {}).get("local_evidence_status", "draft_only_local_evidence_blocked")).strip(),
        "authoritative_apply_allowed": False,
        "binder_second_wave_count": len(manual_verdict_handoff_payload.get("binder_rows", []) or []),
        "pending_manual_verdict_count": int(manual_verdict_handoff_payload.get("summary", {}).get("binder_pending_manual_verdict_count", 0) or 0),
        "negative_slot_count": int(negative_review_handoff_payload.get("summary", {}).get("negative_slot_count", 0) or 0),
        "caution_or_defer_reference_count": int(negative_review_handoff_payload.get("summary", {}).get("caution_signal_count", 0) or 0),
        "draft_prefill_count": int(apply_draft_payload.get("summary", {}).get("draft_prefilled_count", 0) or 0),
        "ready_for_reviewer_fill_count": len(manual_verdict_handoff_payload.get("binder_rows", []) or []),
        "candidate_count": int(candidate_verdict_payload.get("summary", {}).get("candidate_count", 0) or 0),
        "local_binder_curated": bool(local_evidence_payload.get("summary", {}).get("local_target_specific_binder_evidence_curated", False)),
        "local_negative_curated": bool(local_evidence_payload.get("summary", {}).get("local_quantitative_negative_evidence_curated", False)),
        "local_blocker_signal_count": len(local_evidence_payload.get("rows", []) or []),
        "today_focus": "Keep GLUT1 as second-wave only: review the three binder candidates, confirm the three negative slots stay review-only, and leave caution/defer references outside packet rows.",
        "next_required_step": str(manual_verdict_handoff_payload.get("summary", {}).get("next_required_step", "")).strip()
        or str(local_evidence_payload.get("summary", {}).get("next_required_step", "")).strip(),
    }
    checklist = [
        "Binder first: confirm cytochalasin B, WZB117, and STF-31 stay keep_review_only with explicit manual notes.",
        "Negative second: confirm all three non-binder slots stay review-only and receive no proxy quantitative fill.",
        "Caution references last: keep forskolin and gossypol out of authoritative packet rows.",
        "Stop if any step would require reopening donor policy or authoritative apply; that is out of scope for this workbench.",
    ]
    return {"summary": summary, "checklist": checklist, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# GLUT1 Reviewer Workbench",
        "",
        f"- target_id: `{s['target_id']}`",
        f"- wave: `{s['wave']}`",
        f"- endpoint_status: `{s['endpoint_status']}`",
        f"- authoritative_apply_allowed: `{s['authoritative_apply_allowed']}`",
        f"- binder_second_wave_count: `{s['binder_second_wave_count']}`",
        f"- pending_manual_verdict_count: `{s['pending_manual_verdict_count']}`",
        f"- negative_slot_count: `{s['negative_slot_count']}`",
        f"- caution_or_defer_reference_count: `{s['caution_or_defer_reference_count']}`",
        f"- draft_prefill_count: `{s['draft_prefill_count']}`",
        f"- ready_for_reviewer_fill_count: `{s['ready_for_reviewer_fill_count']}`",
        f"- candidate_count: `{s['candidate_count']}`",
        f"- local_binder_curated: `{s['local_binder_curated']}`",
        f"- local_negative_curated: `{s['local_negative_curated']}`",
        f"- local_blocker_signal_count: `{s['local_blocker_signal_count']}`",
        "",
        "## Today Focus",
        "",
        f"- {s['today_focus']}",
        "",
        "## Checklist",
        "",
    ]
    for item in payload["checklist"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Workbench Rows",
            "",
            "| workbench_section | priority_rank | packet_step | label | recommended_verdict | draft_manual_verdict_update | next_action |",
            "| --- | ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| `{row['workbench_section']}` | {row['priority_rank']} | `{row['packet_step']}` | `{row['label']}` | "
            f"`{row['recommended_verdict']}` | `{row['draft_manual_verdict_update']}` | `{row['next_action']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an operator-facing GLUT1 reviewer workbench from existing GLUT1 review artifacts.")
    parser.add_argument("--manual-verdict-handoff-json", default=DEFAULT_MANUAL_VERDICT_HANDOFF_JSON)
    parser.add_argument("--negative-review-handoff-json", default=DEFAULT_NEGATIVE_REVIEW_HANDOFF_JSON)
    parser.add_argument("--apply-draft-json", default=DEFAULT_APPLY_DRAFT_JSON)
    parser.add_argument("--candidate-verdict-json", default=DEFAULT_CANDIDATE_VERDICT_JSON)
    parser.add_argument("--local-evidence-json", default=DEFAULT_LOCAL_EVIDENCE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.manual_verdict_handoff_json),
        _load_json(args.negative_review_handoff_json),
        _load_json(args.apply_draft_json),
        _load_json(args.candidate_verdict_json),
        _load_json(args.local_evidence_json),
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
