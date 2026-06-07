#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_AQP1_PACKET_JSON = "runs/aqp1_negative_review_handoff_packet_current.json"
DEFAULT_GLUT1_PACKET_JSON = "runs/glut1_negative_review_handoff_packet_current.json"
DEFAULT_GLUT1_SOURCE_CONFIRMATION_JSON = "runs/glut1_second_wave_source_confirmation_packet_current.json"
DEFAULT_DASHBOARD_JSON = "runs/transporter_manual_review_dashboard_current.json"
DEFAULT_DAY_PLAN_JSON = "runs/transporter_reviewer_day_plan_current.json"
DEFAULT_OUT_JSON = "runs/transporter_negative_reviewer_day_plan_current.json"
DEFAULT_OUT_CSV = "runs/transporter_negative_reviewer_day_plan_current.csv"
DEFAULT_OUT_MD = "runs/transporter_negative_reviewer_day_plan_current.md"
GLUT1_SOURCE_CONFIRMATION_PACKET_MD = "runs/glut1_second_wave_source_confirmation_packet_current.md"
GLUT1_SOURCE_CONFIRMATION_LEAD = "cytochalasin B"


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


def _append_sentence(base: str, addition: str) -> str:
    base = base.strip()
    addition = addition.strip()
    if not base:
        return addition
    if base[-1] in ".!?":
        return f"{base} {addition}"
    return f"{base}. {addition}"


def _glut1_source_confirmation_context(source_confirmation_packet: dict[str, Any] | None) -> dict[str, Any]:
    summary = dict((source_confirmation_packet or {}).get("summary", {}) or {})
    return {
        "packet_artifact": str(summary.get("packet_artifact", GLUT1_SOURCE_CONFIRMATION_PACKET_MD) or GLUT1_SOURCE_CONFIRMATION_PACKET_MD).strip(),
        "primary_focus_ligand": str(summary.get("primary_focus_ligand", GLUT1_SOURCE_CONFIRMATION_LEAD) or GLUT1_SOURCE_CONFIRMATION_LEAD).strip(),
        "row_count": int(summary.get("row_count", 0) or 0),
        "direct_quantitative_binding_count": int(summary.get("direct_quantitative_binding_count", 0) or 0),
        "exact_target_pair_activity_count": int(summary.get("exact_target_pair_activity_count", 0) or 0),
        "structured_pair_absent_count": int(summary.get("structured_pair_absent_count", 0) or 0),
    }


def _glut1_packet_scope_label(source_confirmation: dict[str, Any]) -> str:
    row_count = int(source_confirmation.get("row_count", 0) or 0)
    return f"a {row_count}-row handoff context" if row_count > 0 else "handoff context"


def _normalize_aqp1_rows(packet: dict[str, Any], wave_priority: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in packet.get("rows", []):
        section = str(row.get("section", "")).strip()
        if section == "negative_slot_policy":
            review_phase = "negative_slots_first"
            candidate = str(row.get("label", "")).strip()
        elif section == "caution_or_defer_signal":
            review_phase = "caution_references_second"
            candidate = str(row.get("label", "")).strip()
        else:
            review_phase = "blocker_reference_only"
            candidate = str(row.get("label", "")).strip()
        rows.append(
            {
                "target_id": "AQP1",
                "wave_priority": wave_priority,
                "review_phase": review_phase,
                "row_type": section or "unknown",
                "priority_rank": int(str(row.get("priority_rank", "999")) or "999"),
                "packet_step": str(row.get("packet_step", "")).strip(),
                "candidate_or_label": candidate,
                "review_bucket": str(row.get("review_bucket", "")).strip(),
                "recommended_resolution": str(row.get("recommended_resolution", "")).strip(),
                "promotion_blocker": str(row.get("promotion_blocker", "")).strip(),
                "source_confirmation_packet_artifact": "",
                "source_confirmation_packet_primary_focus_ligand": "",
                "source_confirmation_packet_row_count": 0,
                "next_required_action": str(row.get("next_action", "")).strip(),
            }
        )
    return rows


def _normalize_glut1_rows(
    packet: dict[str, Any],
    wave_priority: str,
    source_confirmation: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    packet_artifact = str(source_confirmation.get("packet_artifact", "")).strip()
    packet_focus = str(source_confirmation.get("primary_focus_ligand", "")).strip()
    packet_row_count = int(source_confirmation.get("row_count", 0) or 0)
    for row in packet.get("negative_rows", []):
        rows.append(
            {
                "target_id": "GLUT1",
                "wave_priority": wave_priority,
                "review_phase": "negative_slots_first",
                "row_type": str(row.get("row_type", "negative_slot_policy")).strip(),
                "priority_rank": int(str(row.get("priority_rank", "999")) or "999"),
                "packet_step": str(row.get("packet_step", "")).strip(),
                "candidate_or_label": str(row.get("current_ligand_id", "")).strip(),
                "review_bucket": str(row.get("review_bucket", "")).strip(),
                "recommended_resolution": "keep_review_only_until_negative_evidence_is_curated",
                "promotion_blocker": str(row.get("promotion_blocker", "")).strip(),
                "source_confirmation_packet_artifact": packet_artifact,
                "source_confirmation_packet_primary_focus_ligand": packet_focus,
                "source_confirmation_packet_row_count": packet_row_count,
                "next_required_action": str(row.get("next_required_action", "")).strip(),
            }
        )
    for row in packet.get("caution_signal_rows", []):
        rows.append(
            {
                "target_id": "GLUT1",
                "wave_priority": wave_priority,
                "review_phase": "caution_references_second",
                "row_type": str(row.get("row_type", "caution_signal")).strip(),
                "priority_rank": int(str(row.get("priority_rank", "999")) or "999"),
                "packet_step": str(row.get("proposed_packet_step", "")).strip(),
                "candidate_or_label": str(row.get("candidate_name", "")).strip(),
                "review_bucket": str(row.get("review_bucket", "")).strip(),
                "recommended_resolution": str(row.get("recommended_verdict", "")).strip(),
                "promotion_blocker": "caution_only_not_for_authoritative_apply",
                "source_confirmation_packet_artifact": packet_artifact,
                "source_confirmation_packet_primary_focus_ligand": packet_focus,
                "source_confirmation_packet_row_count": packet_row_count,
                "next_required_action": str(row.get("verification_queue_action", "")).strip(),
            }
        )
    return rows


def _wave_priority_lookup(day_plan: dict[str, Any]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for row in day_plan.get("review_rows", []):
        target_id = str(row.get("target_id", "")).strip()
        if target_id:
            lookup[target_id] = str(row.get("wave_priority", "")).strip()
    return lookup


def _target_next_required_step(target_id: str, row: dict[str, Any], source_confirmation: dict[str, Any]) -> str:
    base_step = str(row.get("next_required_step", "")).strip()
    if target_id != "GLUT1":
        return base_step
    packet_artifact = str(source_confirmation.get("packet_artifact", GLUT1_SOURCE_CONFIRMATION_PACKET_MD) or GLUT1_SOURCE_CONFIRMATION_PACKET_MD).strip()
    packet_focus = str(source_confirmation.get("primary_focus_ligand", GLUT1_SOURCE_CONFIRMATION_LEAD) or GLUT1_SOURCE_CONFIRMATION_LEAD).strip()
    handoff_step = (
        f"Open `{packet_artifact}` as {_glut1_packet_scope_label(source_confirmation)}, keep {packet_focus} as the GLUT1 second-wave lead, "
        "keep WZB117 in the exact-target-pair functional lane, keep STF-31 in the structured-pair caveat lane, "
        "and do not treat that packet as negative-slot promotion, proxy non-binder evidence, or authoritative apply."
    )
    return _append_sentence(base_step, handoff_step)


def build_payload(
    *,
    aqp1_packet_payload: dict[str, Any],
    glut1_packet_payload: dict[str, Any],
    dashboard_payload: dict[str, Any],
    day_plan_payload: dict[str, Any],
    glut1_source_confirmation_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    wave_lookup = _wave_priority_lookup(day_plan_payload)
    glut1_source_confirmation = _glut1_source_confirmation_context(glut1_source_confirmation_payload)
    aqp1_rows = _normalize_aqp1_rows(aqp1_packet_payload, wave_lookup.get("AQP1", "today_first"))
    glut1_rows = _normalize_glut1_rows(
        glut1_packet_payload,
        wave_lookup.get("GLUT1", "today_second"),
        glut1_source_confirmation,
    )
    rows = aqp1_rows + glut1_rows
    phase_order = {"negative_slots_first": 0, "caution_references_second": 1, "blocker_reference_only": 2}
    wave_order = {"today_first": 0, "today_second": 1}
    rows.sort(key=lambda row: (wave_order.get(row["wave_priority"], 9), phase_order.get(row["review_phase"], 9), row["priority_rank"]))

    dashboard_rows = {str(row.get("target_id", "")).strip(): row for row in dashboard_payload.get("target_rows", [])}
    target_rows = []
    for target_id in ["AQP1", "GLUT1"]:
        row = dashboard_rows.get(target_id, {})
        target_rows.append(
            {
                "target_id": target_id,
                "wave_priority": wave_lookup.get(target_id, ""),
                "negative_slot_count": int(row.get("negative_slot_count", 0) or 0),
                "negative_packet_ready": bool(row.get("negative_packet_ready", False)),
                "local_evidence_status": str(row.get("local_evidence_status", "")).strip(),
                "placeholder_rows": int(row.get("placeholder_rows", 0) or 0),
                "second_wave_source_confirmation_packet_artifact": (
                    glut1_source_confirmation["packet_artifact"] if target_id == "GLUT1" else ""
                ),
                "second_wave_source_confirmation_primary_focus_ligand": (
                    glut1_source_confirmation["primary_focus_ligand"] if target_id == "GLUT1" else ""
                ),
                "second_wave_source_confirmation_row_count": (
                    glut1_source_confirmation["row_count"] if target_id == "GLUT1" else 0
                ),
                "next_required_step": _target_next_required_step(target_id, row, glut1_source_confirmation),
            }
        )

    summary = {
        "target_count": 2,
        "today_first_target": "AQP1",
        "today_second_target": "GLUT1",
        "negative_packet_target_count": int(dashboard_payload["summary"].get("negative_packet_target_count", 0)),
        "negative_slot_count_total": int(dashboard_payload["summary"].get("negative_slot_count_total", 0)),
        "negative_slot_review_row_count": sum(1 for row in rows if row["review_phase"] == "negative_slots_first"),
        "caution_reference_row_count": sum(1 for row in rows if row["review_phase"] == "caution_references_second"),
        "blocker_reference_row_count": sum(1 for row in rows if row["review_phase"] == "blocker_reference_only"),
        "glut1_second_wave_source_confirmation_packet_artifact": glut1_source_confirmation["packet_artifact"],
        "glut1_second_wave_source_confirmation_row_count": glut1_source_confirmation["row_count"],
        "glut1_second_wave_source_confirmation_primary_focus_ligand": glut1_source_confirmation["primary_focus_ligand"],
        "glut1_direct_quantitative_binding_count": glut1_source_confirmation["direct_quantitative_binding_count"],
        "glut1_exact_target_pair_activity_count": glut1_source_confirmation["exact_target_pair_activity_count"],
        "glut1_structured_pair_absent_count": glut1_source_confirmation["structured_pair_absent_count"],
        "negative_day_plan_ready": True,
        "day_goal": (
            "Burn down transporter negative review in AQP1 first, then GLUT1. Keep all negative slots review-only, "
            "treat caution rows as references only, and use the GLUT1 second-wave source-confirmation packet as "
            "cytochalasin B-led context only. WZB117 stays exact-target-pair functional, STF-31 stays under a structured-pair caveat, "
            "and none of it is proxy quantitative non-binder evidence or authoritative apply."
        ),
        "next_required_step": (
            "Work through negative-slot rows first for AQP1, then GLUT1; only consult caution rows after slot review. "
            f"When GLUT1 comes up, open `{glut1_source_confirmation['packet_artifact']}` as {_glut1_packet_scope_label(glut1_source_confirmation)}, "
            f"keep {glut1_source_confirmation['primary_focus_ligand']} as the second-wave lead, keep WZB117 in the exact-target-pair functional lane, "
            "keep STF-31 in the structured-pair caveat lane, and keep donor-policy / authoritative-apply discussions out of this day plan."
        ),
    }
    return {"summary": summary, "target_rows": target_rows, "review_rows": rows}


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Transporter Negative Reviewer Day Plan",
        "",
        f"- target_count: `{summary['target_count']}`",
        f"- today_first_target: `{summary['today_first_target']}`",
        f"- today_second_target: `{summary['today_second_target']}`",
        f"- negative_packet_target_count: `{summary['negative_packet_target_count']}`",
        f"- negative_slot_count_total: `{summary['negative_slot_count_total']}`",
        f"- negative_slot_review_row_count: `{summary['negative_slot_review_row_count']}`",
        f"- caution_reference_row_count: `{summary['caution_reference_row_count']}`",
        f"- blocker_reference_row_count: `{summary['blocker_reference_row_count']}`",
        f"- glut1_second_wave_source_confirmation_packet_artifact: `{summary['glut1_second_wave_source_confirmation_packet_artifact']}`",
        f"- glut1_second_wave_source_confirmation_row_count: `{summary['glut1_second_wave_source_confirmation_row_count']}`",
        f"- glut1_second_wave_source_confirmation_primary_focus_ligand: `{summary['glut1_second_wave_source_confirmation_primary_focus_ligand']}`",
        f"- glut1_direct_quantitative_binding_count: `{summary['glut1_direct_quantitative_binding_count']}`",
        f"- glut1_exact_target_pair_activity_count: `{summary['glut1_exact_target_pair_activity_count']}`",
        f"- glut1_structured_pair_absent_count: `{summary['glut1_structured_pair_absent_count']}`",
        f"- negative_day_plan_ready: `{summary['negative_day_plan_ready']}`",
        "",
        "## Day Goal",
        "",
        f"- {summary['day_goal']}",
        f"- {summary['next_required_step']}",
        "",
        "## Target Order",
        "",
        "| target_id | wave_priority | negative_slot_count | negative_packet_ready | local_evidence_status | placeholder_rows | second_wave_source_confirmation_packet_artifact | second_wave_source_confirmation_primary_focus_ligand | second_wave_source_confirmation_row_count |",
        "| --- | --- | ---: | --- | --- | ---: | --- | --- | ---: |",
    ]
    for row in payload["target_rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['wave_priority']}` | {row['negative_slot_count']} | `{row['negative_packet_ready']}` | "
            f"`{row['local_evidence_status']}` | {row['placeholder_rows']} | `{row['second_wave_source_confirmation_packet_artifact']}` | "
            f"`{row['second_wave_source_confirmation_primary_focus_ligand']}` | {row['second_wave_source_confirmation_row_count']} |"
        )
    lines.extend(
        [
            "",
            "## Review Rows",
            "",
            "| target_id | wave_priority | review_phase | priority_rank | packet_step | candidate_or_label | review_bucket | source_confirmation_packet_artifact | source_confirmation_packet_primary_focus_ligand | source_confirmation_packet_row_count | next_required_action |",
            "| --- | --- | --- | ---: | --- | --- | --- | --- | --- | ---: | --- |",
        ]
    )
    for row in payload["review_rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['wave_priority']}` | `{row['review_phase']}` | {row['priority_rank']} | "
            f"`{row['packet_step']}` | `{row['candidate_or_label']}` | `{row['review_bucket']}` | `{row['source_confirmation_packet_artifact']}` | "
            f"`{row['source_confirmation_packet_primary_focus_ligand']}` | {row['source_confirmation_packet_row_count']} | `{row['next_required_action']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a transporter negative-review day plan for AQP1 and GLUT1.")
    parser.add_argument("--aqp1-packet-json", default=DEFAULT_AQP1_PACKET_JSON)
    parser.add_argument("--glut1-packet-json", default=DEFAULT_GLUT1_PACKET_JSON)
    parser.add_argument("--glut1-source-confirmation-json", default=DEFAULT_GLUT1_SOURCE_CONFIRMATION_JSON)
    parser.add_argument("--dashboard-json", default=DEFAULT_DASHBOARD_JSON)
    parser.add_argument("--day-plan-json", default=DEFAULT_DAY_PLAN_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        aqp1_packet_payload=_load_json(args.aqp1_packet_json),
        glut1_packet_payload=_load_json(args.glut1_packet_json),
        glut1_source_confirmation_payload=_load_json(args.glut1_source_confirmation_json),
        dashboard_payload=_load_json(args.dashboard_json),
        day_plan_payload=_load_json(args.day_plan_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["review_rows"])
    _write_md(out_md, payload)


if __name__ == "__main__":
    main()
