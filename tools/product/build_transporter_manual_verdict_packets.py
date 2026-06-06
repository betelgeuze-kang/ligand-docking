#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_AQP1_BINDER_SHEET_JSON = "runs/aqp1_binder_verdict_update_sheet_current.json"
DEFAULT_GLUT1_BINDER_SHEET_JSON = "runs/glut1_binder_verdict_update_sheet_current.json"
DEFAULT_NOTE_TEMPLATES_JSON = "runs/transporter_manual_decision_note_templates_current.json"
DEFAULT_OUT_JSON = "runs/transporter_manual_verdict_packets_current.json"
DEFAULT_OUT_MD = "runs/transporter_manual_verdict_packets_current.md"
DEFAULT_AQP1_OUT_MD = "runs/aqp1_manual_verdict_packet_current.md"
DEFAULT_GLUT1_OUT_MD = "runs/glut1_manual_verdict_packet_current.md"
GLUT1_SOURCE_CONFIRMATION_PACKET_MD = "runs/glut1_second_wave_source_confirmation_packet_current.md"
GLUT1_SOURCE_CONFIRMATION_LEAD = "cytochalasin B"
GLUT1_SOURCE_CONFIRMATION_EXACT_TARGET_PAIR_FUNCTIONAL_LIGAND = "WZB117"
GLUT1_SOURCE_CONFIRMATION_STRUCTURED_PAIR_CAVEAT_LIGAND = "STF-31"


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


def _group_templates(note_payload: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in note_payload.get("rows", []) or []:
        key = (str(row.get("target_id", "")).strip(), str(row.get("packet_step", "")).strip())
        grouped[key] = dict(row)
    return grouped


def _glut1_source_confirmation_handoff(packet_step: str) -> dict[str, str]:
    lane_by_step = {
        "core_binder_01": (
            "lead",
            f"Keep {GLUT1_SOURCE_CONFIRMATION_LEAD} as the review-only GLUT1 second-wave source-confirmation lead.",
        ),
        "core_binder_02": (
            "exact-target-pair functional lane",
            "Keep WZB117 as the review-only exact-target-pair functional lane in the GLUT1 source-confirmation handoff.",
        ),
        "core_binder_03": (
            "structured-pair caveat",
            "Keep STF-31 as the review-only structured-pair caveat in the GLUT1 source-confirmation handoff.",
        ),
    }
    lane, review_note = lane_by_step.get(
        packet_step,
        (
            "review-only handoff context",
            "Keep this GLUT1 row inside the review-only source-confirmation handoff until a reviewer confirms stronger transporter-specific evidence.",
        ),
    )
    return {
        "source_confirmation_packet_artifact": GLUT1_SOURCE_CONFIRMATION_PACKET_MD,
        "source_confirmation_handoff_lane": lane,
        "source_confirmation_review_note": review_note,
    }


def _build_target_rows(target_id: str, sheet_payload: dict[str, Any], note_lookup: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in sheet_payload.get("sheet_rows", []) or []:
        packet_step = str(row.get("packet_step", "")).strip()
        note_row = note_lookup.get((target_id, packet_step), {})
        source_confirmation = (
            _glut1_source_confirmation_handoff(packet_step)
            if target_id == "GLUT1"
            else {
                "source_confirmation_packet_artifact": "",
                "source_confirmation_handoff_lane": "",
                "source_confirmation_review_note": "",
            }
        )
        rows.append(
            {
                "target_id": target_id,
                "priority_rank": str(row.get("priority_rank", "")).strip(),
                "packet_step": packet_step,
                "candidate_name": str(row.get("candidate_name", "")).strip(),
                "source_anchor": str(row.get("source_anchor", "")).strip(),
                "suggested_manual_verdict": str(row.get("suggested_manual_verdict", "")).strip(),
                "suggested_manual_confidence_update": str(row.get("suggested_manual_confidence_update", "")).strip(),
                "promotion_blocker": str(row.get("promotion_blocker", "")).strip(),
                "next_required_action": str(row.get("next_required_action", "")).strip(),
                "manual_decision_note_template": str(note_row.get("manual_decision_note_template", "")).strip()
                or str(row.get("suggested_manual_decision_note", "")).strip(),
                "update_status": str(row.get("update_status", "")).strip(),
                "source_confirmation_packet_artifact": source_confirmation["source_confirmation_packet_artifact"],
                "source_confirmation_handoff_lane": source_confirmation["source_confirmation_handoff_lane"],
                "source_confirmation_review_note": source_confirmation["source_confirmation_review_note"],
            }
        )
    return rows


def build_payload(aqp1_sheet: dict[str, Any], glut1_sheet: dict[str, Any], note_templates: dict[str, Any]) -> dict[str, Any]:
    note_lookup = _group_templates(note_templates)
    aqp1_rows = _build_target_rows("AQP1", aqp1_sheet, note_lookup)
    glut1_rows = _build_target_rows("GLUT1", glut1_sheet, note_lookup)
    target_packets = [
        {
            "target_id": "AQP1",
            "wave": "first_wave",
            "row_count": len(aqp1_rows),
            "pending_manual_verdict_count": sum(1 for row in aqp1_rows if row["update_status"] == "pending_manual_verdict"),
            "rows": aqp1_rows,
            "source_confirmation_packet_artifact": "",
            "source_confirmation_primary_focus_ligand": "",
            "source_confirmation_exact_target_pair_functional_ligand": "",
            "source_confirmation_structured_pair_caveat_ligand": "",
            "next_required_step": "Start with bacopaside II, AqB013, and AqB011. Keep all three review-only until stronger transporter-specific review packet evidence is confirmed.",
        },
        {
            "target_id": "GLUT1",
            "wave": "second_wave",
            "row_count": len(glut1_rows),
            "pending_manual_verdict_count": sum(1 for row in glut1_rows if row["update_status"] == "pending_manual_verdict"),
            "rows": glut1_rows,
            "source_confirmation_packet_artifact": GLUT1_SOURCE_CONFIRMATION_PACKET_MD,
            "source_confirmation_primary_focus_ligand": GLUT1_SOURCE_CONFIRMATION_LEAD,
            "source_confirmation_exact_target_pair_functional_ligand": GLUT1_SOURCE_CONFIRMATION_EXACT_TARGET_PAIR_FUNCTIONAL_LIGAND,
            "source_confirmation_structured_pair_caveat_ligand": GLUT1_SOURCE_CONFIRMATION_STRUCTURED_PAIR_CAVEAT_LIGAND,
            "next_required_step": (
                f"Keep GLUT1 behind AQP1. When GLUT1 opens, keep `{GLUT1_SOURCE_CONFIRMATION_PACKET_MD}` open and treat "
                f"{GLUT1_SOURCE_CONFIRMATION_LEAD} as the review-only lead, "
                f"{GLUT1_SOURCE_CONFIRMATION_EXACT_TARGET_PAIR_FUNCTIONAL_LIGAND} as the review-only exact-target-pair functional lane, "
                f"and {GLUT1_SOURCE_CONFIRMATION_STRUCTURED_PAIR_CAVEAT_LIGAND} as the review-only structured-pair caveat."
            ),
        },
    ]
    summary = {
        "target_count": len(target_packets),
        "total_binder_slots": len(aqp1_rows) + len(glut1_rows),
        "pending_manual_verdict_count": sum(packet["pending_manual_verdict_count"] for packet in target_packets),
        "glut1_second_wave_source_confirmation_packet_artifact": GLUT1_SOURCE_CONFIRMATION_PACKET_MD if glut1_rows else "",
        "glut1_second_wave_source_confirmation_primary_focus_ligand": GLUT1_SOURCE_CONFIRMATION_LEAD if glut1_rows else "",
        "glut1_second_wave_source_confirmation_exact_target_pair_functional_ligand": (
            GLUT1_SOURCE_CONFIRMATION_EXACT_TARGET_PAIR_FUNCTIONAL_LIGAND if glut1_rows else ""
        ),
        "glut1_second_wave_source_confirmation_structured_pair_caveat_ligand": (
            GLUT1_SOURCE_CONFIRMATION_STRUCTURED_PAIR_CAVEAT_LIGAND if glut1_rows else ""
        ),
        "next_required_step": (
            "Use the per-target packets as the operator-facing review-only surface. Keep all manual_verdict_update fields explicit and do not auto-promote from suggested text. "
            f"When GLUT1 opens, keep `{GLUT1_SOURCE_CONFIRMATION_PACKET_MD}` open with "
            f"{GLUT1_SOURCE_CONFIRMATION_LEAD} as the lead, "
            f"{GLUT1_SOURCE_CONFIRMATION_EXACT_TARGET_PAIR_FUNCTIONAL_LIGAND} as the exact-target-pair functional lane, "
            f"and {GLUT1_SOURCE_CONFIRMATION_STRUCTURED_PAIR_CAVEAT_LIGAND} as the structured-pair caveat."
        ),
    }
    return {"summary": summary, "target_packets": target_packets}


def _write_target_markdown(path: Path, packet: dict[str, Any]) -> None:
    lines = [
        f"# {packet['target_id']} Manual Verdict Packet",
        "",
        f"- wave: `{packet['wave']}`",
        f"- row_count: `{packet['row_count']}`",
        f"- pending_manual_verdict_count: `{packet['pending_manual_verdict_count']}`",
    ]
    if packet.get("source_confirmation_packet_artifact"):
        lines.extend(
            [
                f"- source_confirmation_packet_artifact: `{packet['source_confirmation_packet_artifact']}`",
                f"- source_confirmation_primary_focus_ligand: `{packet['source_confirmation_primary_focus_ligand']}`",
                f"- source_confirmation_exact_target_pair_functional_ligand: `{packet['source_confirmation_exact_target_pair_functional_ligand']}`",
                f"- source_confirmation_structured_pair_caveat_ligand: `{packet['source_confirmation_structured_pair_caveat_ligand']}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Next Step",
            "",
            f"- {packet['next_required_step']}",
            "",
            "## Rows",
            "",
            "| priority_rank | packet_step | candidate_name | suggested_manual_verdict | suggested_manual_confidence_update | promotion_blocker | source_confirmation_handoff_lane | manual_decision_note_template |",
            "| ---: | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in packet["rows"]:
        lines.append(
            f"| {row['priority_rank']} | `{row['packet_step']}` | `{row['candidate_name']}` | "
            f"`{row['suggested_manual_verdict']}` | `{row['suggested_manual_confidence_update']}` | "
            f"`{row['promotion_blocker']}` | `{row['source_confirmation_handoff_lane'] or '-'}` | "
            f"{row['manual_decision_note_template']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Transporter Manual Verdict Packets",
        "",
        f"- target_count: `{s['target_count']}`",
        f"- total_binder_slots: `{s['total_binder_slots']}`",
        f"- pending_manual_verdict_count: `{s['pending_manual_verdict_count']}`",
    ]
    if s.get("glut1_second_wave_source_confirmation_packet_artifact"):
        lines.extend(
            [
                f"- glut1_second_wave_source_confirmation_packet_artifact: `{s['glut1_second_wave_source_confirmation_packet_artifact']}`",
                f"- glut1_second_wave_source_confirmation_primary_focus_ligand: `{s['glut1_second_wave_source_confirmation_primary_focus_ligand']}`",
                f"- glut1_second_wave_source_confirmation_exact_target_pair_functional_ligand: `{s['glut1_second_wave_source_confirmation_exact_target_pair_functional_ligand']}`",
                f"- glut1_second_wave_source_confirmation_structured_pair_caveat_ligand: `{s['glut1_second_wave_source_confirmation_structured_pair_caveat_ligand']}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Next Step",
            "",
            f"- {s['next_required_step']}",
            "",
            "## Targets",
            "",
            "| target_id | wave | row_count | pending_manual_verdict_count | source_confirmation_packet_artifact | next_required_step |",
            "| --- | --- | ---: | ---: | --- | --- |",
        ]
    )
    for packet in payload["target_packets"]:
        lines.append(
            f"| `{packet['target_id']}` | `{packet['wave']}` | {packet['row_count']} | {packet['pending_manual_verdict_count']} | "
            f"`{packet.get('source_confirmation_packet_artifact') or '-'}` | {packet['next_required_step']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build operator-facing manual verdict packets for AQP1 and GLUT1 binder review.")
    parser.add_argument("--aqp1-binder-sheet-json", default=DEFAULT_AQP1_BINDER_SHEET_JSON)
    parser.add_argument("--glut1-binder-sheet-json", default=DEFAULT_GLUT1_BINDER_SHEET_JSON)
    parser.add_argument("--note-templates-json", default=DEFAULT_NOTE_TEMPLATES_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--aqp1-out-md", default=DEFAULT_AQP1_OUT_MD)
    parser.add_argument("--glut1-out-md", default=DEFAULT_GLUT1_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.aqp1_binder_sheet_json),
        _load_json(args.glut1_binder_sheet_json),
        _load_json(args.note_templates_json),
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    aqp1_out_md = _resolve(args.aqp1_out_md)
    glut1_out_md = _resolve(args.glut1_out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)
    packet_by_target = {packet["target_id"]: packet for packet in payload["target_packets"]}
    _write_target_markdown(aqp1_out_md, packet_by_target["AQP1"])
    _write_target_markdown(glut1_out_md, packet_by_target["GLUT1"])


if __name__ == "__main__":
    main()
