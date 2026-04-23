#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.transporter_phase_helpers import aqp1_follow_on_seed_steps

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_APPLY_DRAFT_STATUS_JSON = "runs/transporter_apply_draft_status_current.json"
DEFAULT_NOTE_TEMPLATES_JSON = "runs/transporter_manual_decision_note_templates_current.json"
DEFAULT_AQP1_REVIEW_BRIEF_JSON = "runs/aqp1_binder_review_brief_current.json"
DEFAULT_PXR_REVIEW_PACKET_JSON = "runs/pxr_review_packet_current.json"
DEFAULT_TRANSPORTER_SEED_ROW_BOARD_JSON = "runs/transporter_seed_row_promotion_board_current.json"
DEFAULT_NEGATIVE_TARGET_PACKETS_JSON = "runs/transporter_negative_evidence_target_packets_current.json"
DEFAULT_OUT_JSON = "runs/transporter_reviewer_day_plan_current.json"
DEFAULT_OUT_CSV = "runs/transporter_reviewer_day_plan_current.csv"
DEFAULT_OUT_MD = "runs/transporter_reviewer_day_plan_current.md"


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


def _maybe_load_json(path_like: str) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
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


def _template_rows_for_target(note_templates: dict[str, Any], target_id: str) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in note_templates.get("rows", []) or []
        if str(row.get("target_id", "")).strip() == target_id
    ]


def _aqp1_primary_probe_resolution_handoff(summary: dict[str, Any]) -> str:
    artifact = str(summary.get("aqp1_negative_primary_probe_resolution_artifact", "") or "").strip()
    if not artifact:
        return ""
    candidate = (
        str(summary.get("aqp1_negative_primary_probe_resolution_candidate", "") or "").strip()
        or "sodium nitroprusside"
    )
    fallback = (
        str(summary.get("aqp1_negative_primary_probe_resolution_solvent_fallback_candidate", "") or "").strip()
        or "dimethyl sulfoxide"
    )
    decision = (
        str(summary.get("aqp1_negative_primary_probe_resolution_decision", "") or "").strip()
        or "keep_review_only_no_authoritative_negative_promotion"
    )
    return (
        f" Keep `{artifact}` ready as the AQP1 primary-probe resolution handoff: leave `{candidate}` review-only, "
        f"keep `{fallback}` solvent-only, and preserve decision `{decision}`."
    )


def build_payload(
    apply_draft_status: dict[str, Any],
    note_templates: dict[str, Any],
    aqp1_review_brief: dict[str, Any],
    pxr_review_packet: dict[str, Any],
    transporter_seed_row_board: dict[str, Any],
    negative_target_packets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target_rows = list(apply_draft_status.get("target_rows", []) or [])
    aqp1_templates = _template_rows_for_target(note_templates, "AQP1")
    glut1_templates = _template_rows_for_target(note_templates, "GLUT1")
    aqp1_follow_on_steps = aqp1_follow_on_seed_steps(transporter_seed_row_board)
    aqp1_follow_on_text = ", ".join(aqp1_follow_on_steps)
    apply_summary = dict(apply_draft_status.get("summary", {}) or {})
    negative_target_packets_summary = dict((negative_target_packets or {}).get("summary", {}) or {})
    aqp1_primary_probe_resolution_handoff = _aqp1_primary_probe_resolution_handoff(negative_target_packets_summary)

    review_rows = []
    for row in target_rows:
        target_id = str(row.get("target_id", "")).strip()
        template_rows = aqp1_templates if target_id == "AQP1" else glut1_templates
        first_candidate = str(template_rows[0].get("candidate_name", "")).strip() if template_rows else ""
        first_packet_step = str(template_rows[0].get("packet_step", "")).strip() if template_rows else ""
        pending_count = int(row.get("pending_manual_verdict_count", 0) or 0)
        review_rows.append(
            {
                "target_id": target_id,
                "wave_priority": "today_first" if target_id == "AQP1" else "today_second",
                "draft_apply_status": str(row.get("draft_apply_status", "")).strip(),
                "pending_manual_verdict_count": pending_count,
                "note_template_count": int(row.get("note_template_count", 0) or 0),
                "placeholder_driven_rows": int(row.get("placeholder_driven_rows", 0) or 0),
                "exact_human_activity_count": int(row.get("exact_human_activity_count", 0) or 0),
                "quantitative_provenance_focus_ligand": str(row.get("quantitative_provenance_focus_ligand", "")).strip(),
                "quantitative_provenance_signal": str(row.get("quantitative_provenance_signal", "")).strip(),
                "today_focus": (
                    (
                        "Fill the 3 AQP1 binder manual verdict fields using the AQP1 brief and note templates."
                        if pending_count > 0
                        else (
                            "AQP1 binder verdict staging is already complete. Start with core_binder_01 via the first seed-row packet, keep the AqB013 exact-human-activity provenance lane visible, then continue "
                            f"{aqp1_follow_on_text} through the seed-row promotion board while keeping every row non-authoritative and leaving replacement_reference_binding_kcal_mol blank."
                            + aqp1_primary_probe_resolution_handoff
                            if aqp1_follow_on_steps
                            else "AQP1 binder verdict staging is already complete. Use AQP1 first for blocker closure, keep the AqB013 exact-human-activity provenance lane visible, and keep every row non-authoritative."
                            + aqp1_primary_probe_resolution_handoff
                        )
                    )
                    if target_id == "AQP1"
                    else (
                        "Only start GLUT1 after AQP1; reuse the same verdict pattern without changing transporter policy."
                        if pending_count > 0
                        else "GLUT1 binder verdict staging is already complete. Keep GLUT1 as second-wave blocker closure only."
                    )
                ),
                "first_candidate": first_candidate,
                "first_packet_step": first_packet_step,
                "start_artifact": (
                    "runs/aqp1_binder_review_brief_current.md"
                    if target_id == "AQP1" and pending_count > 0
                    else "runs/aqp1_first_seed_row_packet_current.md"
                    if target_id == "AQP1"
                    else "runs/transporter_manual_decision_note_templates_current.md"
                    if pending_count > 0
                    else "runs/glut1_manual_verdict_packet_current.md"
                ),
                "completion_rule": (
                    "Do not mark complete until manual_verdict_update, manual_confidence_update, and manual_decision_note are all filled for the target's 3 binder rows."
                    if pending_count > 0
                    else "Treat binder verdict staging as complete; continue only with blocker closure and keep authoritative apply blocked."
                ),
            }
        )

    overall_pending = int(apply_draft_status.get("summary", {}).get("pending_manual_verdict_count", 0) or 0)
    summary = {
        "target_count": len(review_rows),
        "pending_manual_verdict_count": overall_pending,
        "note_template_count": int(note_templates.get("summary", {}).get("template_row_count", 0) or 0),
        "aqp1_ready_for_today": bool(aqp1_review_brief.get("summary", {}).get("ready_for_reviewer_fill_count", 0)),
        "glut1_ready_for_today": len(glut1_templates) == 3,
        "aqp1_follow_on_seed_count": len(aqp1_follow_on_steps),
        "aqp1_exact_human_activity_count": int(apply_summary.get("aqp1_exact_human_activity_count", 0) or 0),
        "aqp1_quantitative_provenance_focus_ligand": str(
            apply_summary.get("aqp1_quantitative_provenance_focus_ligand", "")
        ).strip(),
        "aqp1_quantitative_provenance_signal": str(
            apply_summary.get("aqp1_quantitative_provenance_signal", "")
        ).strip(),
        "aqp1_negative_primary_probe_resolution_ready": bool(
            negative_target_packets_summary.get("aqp1_negative_primary_probe_resolution_artifact", "")
        ),
        "aqp1_negative_primary_probe_resolution_artifact": str(
            negative_target_packets_summary.get("aqp1_negative_primary_probe_resolution_artifact", "")
        ).strip(),
        "aqp1_negative_primary_probe_resolution_candidate": str(
            negative_target_packets_summary.get("aqp1_negative_primary_probe_resolution_candidate", "")
        ).strip(),
        "aqp1_negative_primary_probe_resolution_decision": str(
            negative_target_packets_summary.get("aqp1_negative_primary_probe_resolution_decision", "")
        ).strip(),
        "aqp1_negative_primary_probe_resolution_solvent_fallback_candidate": str(
            negative_target_packets_summary.get("aqp1_negative_primary_probe_resolution_solvent_fallback_candidate", "")
        ).strip(),
        "supporting_non_transporter_packet": "runs/pxr_review_packet_current.md",
        "supporting_non_transporter_packet_reason": "Use the PXR review packet as a compact checklist style reference for reviewer phrasing and operator flow only; do not mix transporter and PXR classifications.",
        "day_goal": (
            "Complete AQP1 binder manual verdicts first, then open GLUT1 binder manual verdicts if time remains. Do not promote any transporter packet row today."
            if overall_pending > 0
            else "Binder-verdict backlog is cleared. Use today for transporter authoritative-apply blocker closure while keeping all transporter rows non-authoritative, carry AqB013 as the exact-human-activity provenance lane, and keep replacement_reference_binding_kcal_mol blank."
            + aqp1_primary_probe_resolution_handoff
        ),
        "next_required_step": (
            "Treat today as a reviewer-only burn-down day: fill manual verdict fields, keep note templates alongside entries, and leave authoritative transporter apply blocked."
            if overall_pending > 0
            else "Treat today as a blocker-closure day: keep transporter binder decisions as reviewer-state only, work packet evidence closure, keep AqB013 visible as the exact-human-activity provenance lane, and leave authoritative apply blocked."
            + aqp1_primary_probe_resolution_handoff
        ),
    }
    return {"summary": summary, "review_rows": review_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Transporter Reviewer Day Plan",
        "",
        f"- target_count: `{s['target_count']}`",
        f"- pending_manual_verdict_count: `{s['pending_manual_verdict_count']}`",
        f"- note_template_count: `{s['note_template_count']}`",
        f"- aqp1_ready_for_today: `{s['aqp1_ready_for_today']}`",
        f"- glut1_ready_for_today: `{s['glut1_ready_for_today']}`",
        f"- aqp1_follow_on_seed_count: `{s['aqp1_follow_on_seed_count']}`",
        f"- aqp1_exact_human_activity_count: `{s['aqp1_exact_human_activity_count']}`",
        f"- aqp1_quantitative_provenance_focus_ligand: `{s['aqp1_quantitative_provenance_focus_ligand']}`",
        f"- aqp1_quantitative_provenance_signal: `{s['aqp1_quantitative_provenance_signal']}`",
        f"- aqp1_negative_primary_probe_resolution_ready: `{s['aqp1_negative_primary_probe_resolution_ready']}`",
        f"- aqp1_negative_primary_probe_resolution_artifact: `{s['aqp1_negative_primary_probe_resolution_artifact']}`",
        f"- aqp1_negative_primary_probe_resolution_candidate: `{s['aqp1_negative_primary_probe_resolution_candidate']}`",
        f"- aqp1_negative_primary_probe_resolution_decision: `{s['aqp1_negative_primary_probe_resolution_decision']}`",
        f"- aqp1_negative_primary_probe_resolution_solvent_fallback_candidate: `{s['aqp1_negative_primary_probe_resolution_solvent_fallback_candidate']}`",
        f"- supporting_non_transporter_packet: `{s['supporting_non_transporter_packet']}`",
        "",
        "## Day Goal",
        "",
        f"- {s['day_goal']}",
        f"- {s['next_required_step']}",
        "",
        "## Review Order",
        "",
        "| target_id | wave_priority | draft_apply_status | pending_manual_verdict_count | note_template_count | exact_human_activity_count | quantitative_provenance_focus_ligand | first_candidate | first_packet_step | start_artifact |",
        "| --- | --- | --- | ---: | ---: | ---: | --- | --- | --- | --- |",
    ]
    for row in payload["review_rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['wave_priority']}` | `{row['draft_apply_status']}` | {row['pending_manual_verdict_count']} | {row['note_template_count']} | {row['exact_human_activity_count']} | "
            f"`{row['quantitative_provenance_focus_ligand']}` | `{row['first_candidate']}` | `{row['first_packet_step']}` | `{row['start_artifact']}` |"
        )
        lines.append("")
        lines.append(f"- Today focus for `{row['target_id']}`: {row['today_focus']}")
        lines.append(f"- Completion rule: {row['completion_rule']}")
        lines.append("")
    lines.extend(
        [
            "## Reference Style Packet",
            "",
            f"- `{s['supporting_non_transporter_packet']}`",
            f"- {s['supporting_non_transporter_packet_reason']}",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a same-day transporter reviewer checklist from apply-draft status and handoff packets.")
    parser.add_argument("--apply-draft-status-json", default=DEFAULT_APPLY_DRAFT_STATUS_JSON)
    parser.add_argument("--note-templates-json", default=DEFAULT_NOTE_TEMPLATES_JSON)
    parser.add_argument("--aqp1-review-brief-json", default=DEFAULT_AQP1_REVIEW_BRIEF_JSON)
    parser.add_argument("--pxr-review-packet-json", default=DEFAULT_PXR_REVIEW_PACKET_JSON)
    parser.add_argument("--transporter-seed-row-board-json", default=DEFAULT_TRANSPORTER_SEED_ROW_BOARD_JSON)
    parser.add_argument("--negative-target-packets-json", default=DEFAULT_NEGATIVE_TARGET_PACKETS_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.apply_draft_status_json),
        _load_json(args.note_templates_json),
        _load_json(args.aqp1_review_brief_json),
        _load_json(args.pxr_review_packet_json),
        _load_json(args.transporter_seed_row_board_json),
        _maybe_load_json(args.negative_target_packets_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["review_rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
