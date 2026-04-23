#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.transporter_phase_helpers import aqp1_follow_on_seed_steps

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OPERATOR_CONSOLE_JSON = "runs/transporter_operator_console_current.json"
DEFAULT_REVIEWER_DAY_PLAN_JSON = "runs/transporter_reviewer_day_plan_current.json"
DEFAULT_NEGATIVE_REVIEWER_DAY_PLAN_JSON = "runs/transporter_negative_reviewer_day_plan_current.json"
DEFAULT_MANUAL_VERDICT_PACKETS_JSON = "runs/transporter_manual_verdict_packets_current.json"
DEFAULT_AQP1_FIRST_SEED_ROW_PACKET_JSON = "runs/aqp1_first_seed_row_packet_current.json"
DEFAULT_AQP1_SEED_ROW_EXECUTION_PACKET_JSON = "runs/transporter_seed_row_execution_packet_current.json"
DEFAULT_AQP1_SEED_ROW_SYNC_PREVIEW_JSON = "runs/aqp1_seed_row_sync_apply_preview_current.json"
DEFAULT_TRANSPORTER_SEED_ROW_BOARD_JSON = "runs/transporter_seed_row_promotion_board_current.json"
DEFAULT_OUT_JSON = "runs/transporter_reviewer_day2_console_current.json"
DEFAULT_OUT_CSV = "runs/transporter_reviewer_day2_console_current.csv"
DEFAULT_OUT_MD = "runs/transporter_reviewer_day2_console_current.md"


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


def _packet_lookup(manual_verdict_packets: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for packet in manual_verdict_packets.get("target_packets", []) or []:
        key = str(packet.get("target_id", "")).strip()
        if key:
            out[key] = dict(packet)
    return out


def build_payload(
    operator_console: dict[str, Any],
    reviewer_day_plan: dict[str, Any],
    negative_reviewer_day_plan: dict[str, Any],
    manual_verdict_packets: dict[str, Any],
    aqp1_first_seed_row_packet: dict[str, Any],
    aqp1_seed_row_execution_packet: dict[str, Any],
    aqp1_seed_row_sync_preview: dict[str, Any],
    transporter_seed_row_board: dict[str, Any],
) -> dict[str, Any]:
    operator_summary = dict(operator_console.get("summary", {}) or {})
    binder_plan_by_target = _keyed(reviewer_day_plan.get("review_rows", []) or [], "target_id")
    negative_plan_by_target = _keyed(negative_reviewer_day_plan.get("target_rows", []) or [], "target_id")
    packet_by_target = _packet_lookup(manual_verdict_packets)
    aqp1_seed_summary = dict((aqp1_first_seed_row_packet or {}).get("summary", {}) or {})
    aqp1_execution_summary = dict((aqp1_seed_row_execution_packet or {}).get("summary", {}) or {})
    aqp1_sync_summary = dict((aqp1_seed_row_sync_preview or {}).get("summary", {}) or {})
    aqp1_follow_on_steps = aqp1_follow_on_seed_steps(transporter_seed_row_board)
    binder_pending_manual_verdict_count = int(operator_summary.get("binder_pending_manual_verdict_count", 0) or 0)
    aqp1_primary_probe_resolution_artifact = str(
        operator_summary.get("aqp1_negative_primary_probe_resolution_artifact", "") or ""
    ).strip()
    aqp1_primary_probe_resolution_candidate = str(
        operator_summary.get("aqp1_negative_primary_probe_resolution_candidate", "") or ""
    ).strip()
    aqp1_primary_probe_resolution_decision = str(
        operator_summary.get("aqp1_negative_primary_probe_resolution_decision", "") or ""
    ).strip()
    aqp1_primary_probe_resolution_solvent_fallback_candidate = str(
        operator_summary.get("aqp1_negative_primary_probe_resolution_solvent_fallback_candidate", "") or ""
    ).strip()
    aqp1_primary_probe_resolution_handoff = (
        f" Keep {aqp1_primary_probe_resolution_artifact} ready so "
        f"{aqp1_primary_probe_resolution_candidate or 'sodium nitroprusside'} stays review-only while "
        f"{aqp1_primary_probe_resolution_solvent_fallback_candidate or 'dimethyl sulfoxide'} stays solvent-only at decision "
        f"{aqp1_primary_probe_resolution_decision or 'keep_review_only_no_authoritative_negative_promotion'}."
        if aqp1_primary_probe_resolution_artifact
        else ""
    )

    if binder_pending_manual_verdict_count == 0 and aqp1_seed_summary and aqp1_execution_summary and aqp1_sync_summary:
        stage_specs = [
            ("AQP1", "seed_row_packet", "runs/aqp1_first_seed_row_packet_current.md"),
            ("AQP1", "seed_row_execution", "runs/transporter_seed_row_execution_packet_current.md"),
            ("AQP1", "seed_row_sync_preview", "runs/aqp1_seed_row_sync_apply_preview_current.md"),
            ("AQP1", "negative_review", "runs/aqp1_negative_review_handoff_packet_current.md"),
            ("GLUT1", "binder_review", "runs/glut1_manual_verdict_packet_current.md"),
            ("GLUT1", "negative_review", "runs/glut1_negative_review_handoff_packet_current.md"),
        ]
    else:
        stage_specs = [
            ("AQP1", "binder_review", "runs/aqp1_manual_verdict_packet_current.md"),
            ("AQP1", "negative_review", "runs/aqp1_negative_review_handoff_packet_current.md"),
            ("GLUT1", "binder_review", "runs/glut1_manual_verdict_packet_current.md"),
            ("GLUT1", "negative_review", "runs/glut1_negative_review_handoff_packet_current.md"),
        ]

    rows: list[dict[str, Any]] = []
    for idx, (target, review_mode, artifact_path) in enumerate(stage_specs, start=1):
        binder_plan = binder_plan_by_target.get(target, {})
        neg_plan = negative_plan_by_target.get(target, {})
        packet = packet_by_target.get(target, {})
        if review_mode == "binder_review":
            pending_count = int(packet.get("pending_manual_verdict_count", 0) or 0)
            start_label = str(binder_plan.get("first_candidate", "")).strip()
            exhaustion_rule = str(binder_plan.get("completion_rule", "")).strip() or f"Exhaust this packet only after all {pending_count} binder verdict rows are explicitly filled."
            current_focus = str(binder_plan.get("today_focus", "")).strip()
            if target == "GLUT1" and operator_summary.get("glut1_second_wave_source_confirmation_ready"):
                current_focus = (
                    (current_focus + " ") if current_focus else ""
                ) + (
                    f"Keep {operator_summary.get('glut1_open_source_confirmation', 'runs/glut1_second_wave_source_confirmation_packet_current.md')} open, "
                    f"start from {operator_summary.get('glut1_second_wave_source_confirmation_primary_focus_ligand', 'cytochalasin B')}, "
                    "and treat WZB117/STF-31 as downstream second-wave review-only rows."
                )
        elif review_mode == "seed_row_packet":
            pending_count = 1
            start_label = str(aqp1_seed_summary.get("candidate_name", "")).strip()
            follow_on_note = (
                f" Then continue {', '.join(aqp1_follow_on_steps)} through the seed-row promotion board."
                if aqp1_follow_on_steps
                else ""
            )
            exhaustion_rule = (
                "Exhaust this packet only after the first AQP1 seed-row target, blockers, and reviewer-safe copy fields are all understood."
                + follow_on_note
            )
            current_focus = "Use the first seed-row packet to lock the AQP1 candidate, blocker, and safe-copy plan before staging, and keep the AqB013 exact-human-activity provenance lane visible."
        elif review_mode == "seed_row_execution":
            pending_count = int(aqp1_execution_summary.get("safe_staged_field_count", 0) or 1)
            start_label = str(aqp1_execution_summary.get("candidate_name", aqp1_seed_summary.get("candidate_name", ""))).strip()
            follow_on_note = (
                f" Keep row-02/03 follow-ons ({', '.join(aqp1_follow_on_steps)}) behind this row-01 execution packet."
                if aqp1_follow_on_steps
                else ""
            )
            exhaustion_rule = (
                "Exhaust this execution packet only after the exact synchronized triple-edit contract is understood and the row-01 staged field selection is confirmed."
                + follow_on_note
            )
            current_focus = "Use the execution packet to confirm the exact synchronized triple-edit contract, keep AqB013 provenance visible, and keep replacement_reference_binding_kcal_mol blank before opening the sync preview."
        elif review_mode == "seed_row_sync_preview":
            pending_count = int(aqp1_sync_summary.get("safe_staged_field_count", 0) or 0)
            start_label = str(aqp1_sync_summary.get("candidate_name", aqp1_seed_summary.get("candidate_name", ""))).strip()
            exhaustion_rule = "Exhaust this preview only after the exact synchronized-row draft state is understood and only the safe staged field remains selected."
            current_focus = "Confirm the non-authoritative synchronized-row stage, keep AqB013 provenance visible, and keep replacement_reference_binding_kcal_mol blank before moving to AQP1 negative review."
        else:
            pending_count = int(neg_plan.get("negative_slot_count", 0) or 0)
            start_label = f"{target} negative slots"
            caution_refs = sum(
                1
                for row in negative_reviewer_day_plan.get("review_rows", []) or []
                if str(row.get("target_id", "")).strip() == target
                and "caution" in str(row.get("review_phase", "")).strip()
            )
            exhaustion_rule = (
                f"Exhaust this packet after reviewing {pending_count} negative slots"
                + (f" and consulting {caution_refs} caution/defer reference rows." if caution_refs else ".")
            )
            current_focus = str(neg_plan.get("next_required_step", "")).strip()
            if target == "AQP1" and aqp1_primary_probe_resolution_handoff:
                current_focus = f"{current_focus}{aqp1_primary_probe_resolution_handoff}".strip()
        next_artifact = stage_specs[idx][2] if idx < len(stage_specs) else ""
        rows.append(
            {
                "stage_order": idx,
                "target_id": target,
                "review_mode": review_mode,
                "open_packet": artifact_path,
                "start_label": start_label,
                "pending_count": pending_count,
                "current_focus": current_focus,
                "exhaustion_rule": exhaustion_rule,
                "open_after_exhausted": next_artifact or "stop_reviewer_day2_console",
            }
        )

    summary = {
        "stage_count": len(rows),
        "today_first_target": str(negative_reviewer_day_plan.get("summary", {}).get("today_first_target", "")).strip() or "AQP1",
        "today_second_target": str(negative_reviewer_day_plan.get("summary", {}).get("today_second_target", "")).strip() or "GLUT1",
        "binder_pending_manual_verdict_count": binder_pending_manual_verdict_count,
        "negative_slot_count_total": int(negative_reviewer_day_plan.get("summary", {}).get("negative_slot_count_total", 0) or 0),
        "aqp1_follow_on_seed_targets": ", ".join(aqp1_follow_on_steps),
        "console_rule": str(operator_summary.get("console_rule", "")).strip(),
        "aqp1_negative_primary_probe_resolution_ready": bool(aqp1_primary_probe_resolution_artifact),
        "aqp1_negative_primary_probe_resolution_artifact": aqp1_primary_probe_resolution_artifact,
        "aqp1_negative_primary_probe_resolution_candidate": aqp1_primary_probe_resolution_candidate,
        "aqp1_negative_primary_probe_resolution_decision": aqp1_primary_probe_resolution_decision,
        "aqp1_negative_primary_probe_resolution_solvent_fallback_candidate": aqp1_primary_probe_resolution_solvent_fallback_candidate,
        "glut1_open_source_confirmation": str(operator_summary.get("glut1_open_source_confirmation", "")).strip(),
        "glut1_second_wave_source_confirmation_ready": bool(
            operator_summary.get("glut1_second_wave_source_confirmation_ready", False)
        ),
        "glut1_second_wave_source_confirmation_primary_focus_ligand": str(
            operator_summary.get("glut1_second_wave_source_confirmation_primary_focus_ligand", "") or ""
        ).strip(),
        "glut1_direct_quantitative_binding_count": int(
            operator_summary.get("glut1_direct_quantitative_binding_count", 0) or 0
        ),
        "glut1_exact_target_pair_activity_count": int(
            operator_summary.get("glut1_exact_target_pair_activity_count", 0) or 0
        ),
        "glut1_structured_pair_absent_count": int(
            operator_summary.get("glut1_structured_pair_absent_count", 0) or 0
        ),
        "day_goal": str(reviewer_day_plan.get("summary", {}).get("day_goal", "")).strip(),
        "negative_day_goal": str(negative_reviewer_day_plan.get("summary", {}).get("day_goal", "")).strip(),
        "next_required_step": (
            "Open packets strictly in stage order. Only move to the next packet when the current packet's exhaustion rule is satisfied."
            + aqp1_primary_probe_resolution_handoff
            + (
                f" When GLUT1 opens, keep {operator_summary.get('glut1_open_source_confirmation', 'runs/glut1_second_wave_source_confirmation_packet_current.md')} open and start with "
                f"{operator_summary.get('glut1_second_wave_source_confirmation_primary_focus_ligand', 'cytochalasin B')}."
                if operator_summary.get("glut1_second_wave_source_confirmation_ready")
                else ""
            )
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Transporter Reviewer Day-2 Console",
        "",
        f"- stage_count: `{s['stage_count']}`",
        f"- today_first_target: `{s['today_first_target']}`",
        f"- today_second_target: `{s['today_second_target']}`",
        f"- binder_pending_manual_verdict_count: `{s['binder_pending_manual_verdict_count']}`",
        f"- negative_slot_count_total: `{s['negative_slot_count_total']}`",
        f"- aqp1_follow_on_seed_targets: `{s['aqp1_follow_on_seed_targets']}`",
        f"- aqp1_negative_primary_probe_resolution_ready: `{s['aqp1_negative_primary_probe_resolution_ready']}`",
        f"- aqp1_negative_primary_probe_resolution_artifact: `{s['aqp1_negative_primary_probe_resolution_artifact']}`",
        f"- aqp1_negative_primary_probe_resolution_candidate: `{s['aqp1_negative_primary_probe_resolution_candidate']}`",
        f"- aqp1_negative_primary_probe_resolution_decision: `{s['aqp1_negative_primary_probe_resolution_decision']}`",
        f"- aqp1_negative_primary_probe_resolution_solvent_fallback_candidate: `{s['aqp1_negative_primary_probe_resolution_solvent_fallback_candidate']}`",
        f"- glut1_open_source_confirmation: `{s['glut1_open_source_confirmation']}`",
        f"- glut1_second_wave_source_confirmation_ready: `{s['glut1_second_wave_source_confirmation_ready']}`",
        f"- glut1_second_wave_source_confirmation_primary_focus_ligand: `{s['glut1_second_wave_source_confirmation_primary_focus_ligand']}`",
        f"- glut1_direct_quantitative_binding_count: `{s['glut1_direct_quantitative_binding_count']}`",
        f"- glut1_exact_target_pair_activity_count: `{s['glut1_exact_target_pair_activity_count']}`",
        f"- glut1_structured_pair_absent_count: `{s['glut1_structured_pair_absent_count']}`",
        "",
        "## Console Rule",
        "",
        f"- {s['console_rule']}",
        "",
        "## Day Goals",
        "",
        f"- Binder day goal: {s['day_goal']}",
        f"- Negative day goal: {s['negative_day_goal']}",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Stage Chain",
        "",
        "| stage_order | target_id | review_mode | open_packet | pending_count | start_label | open_after_exhausted |",
        "| ---: | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['stage_order']} | `{row['target_id']}` | `{row['review_mode']}` | "
            f"`{row['open_packet']}` | {row['pending_count']} | `{row['start_label']}` | "
            f"`{row['open_after_exhausted']}` |"
        )
    lines.extend(
        [
            "",
            "## Exhaustion Rules",
            "",
            "| stage_order | target_id | review_mode | exhaustion_rule |",
            "| ---: | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| {row['stage_order']} | `{row['target_id']}` | `{row['review_mode']}` | {row['exhaustion_rule']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a day-2 transporter reviewer console that sequences detailed AQP1/GLUT1 packets.")
    parser.add_argument("--operator-console-json", default=DEFAULT_OPERATOR_CONSOLE_JSON)
    parser.add_argument("--reviewer-day-plan-json", default=DEFAULT_REVIEWER_DAY_PLAN_JSON)
    parser.add_argument("--negative-reviewer-day-plan-json", default=DEFAULT_NEGATIVE_REVIEWER_DAY_PLAN_JSON)
    parser.add_argument("--manual-verdict-packets-json", default=DEFAULT_MANUAL_VERDICT_PACKETS_JSON)
    parser.add_argument("--aqp1-first-seed-row-packet-json", default=DEFAULT_AQP1_FIRST_SEED_ROW_PACKET_JSON)
    parser.add_argument("--aqp1-seed-row-execution-packet-json", default=DEFAULT_AQP1_SEED_ROW_EXECUTION_PACKET_JSON)
    parser.add_argument("--aqp1-seed-row-sync-preview-json", default=DEFAULT_AQP1_SEED_ROW_SYNC_PREVIEW_JSON)
    parser.add_argument("--transporter-seed-row-board-json", default=DEFAULT_TRANSPORTER_SEED_ROW_BOARD_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.operator_console_json),
        _load_json(args.reviewer_day_plan_json),
        _load_json(args.negative_reviewer_day_plan_json),
        _load_json(args.manual_verdict_packets_json),
        _load_json(args.aqp1_first_seed_row_packet_json),
        _load_json(args.aqp1_seed_row_execution_packet_json),
        _load_json(args.aqp1_seed_row_sync_preview_json),
        _load_json(args.transporter_seed_row_board_json),
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
