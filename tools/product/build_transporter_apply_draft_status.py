#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_AQP1_BINDER_SHEET_JSON = "runs/aqp1_binder_verdict_update_sheet_current.json"
DEFAULT_GLUT1_BINDER_SHEET_JSON = "runs/glut1_binder_verdict_update_sheet_current.json"
DEFAULT_NOTE_TEMPLATES_JSON = "runs/transporter_manual_decision_note_templates_current.json"
DEFAULT_AQP1_PACKET_JSON = "runs/aqp1_packet_replacement_workbook_current.json"
DEFAULT_GLUT1_PACKET_JSON = "runs/glut1_packet_replacement_workbook_current.json"
DEFAULT_AQP1_QUEUE_JSON = "runs/aqp1_packet_fill_queue_current.json"
DEFAULT_GLUT1_QUEUE_JSON = "runs/glut1_packet_fill_queue_current.json"
DEFAULT_AQP1_QUANTITATIVE_PROVENANCE_JSON = "runs/aqp1_quantitative_provenance_packet_current.json"
DEFAULT_GLUT1_SOURCE_CONFIRMATION_JSON = "runs/glut1_second_wave_source_confirmation_packet_current.json"
DEFAULT_SEED_BOARD_JSON = "runs/transporter_seed_row_promotion_board_current.json"
DEFAULT_NEGATIVE_APPLY_GATE_JSON = "runs/transporter_negative_authoritative_apply_gate_current.json"
DEFAULT_OUT_JSON = "runs/transporter_apply_draft_status_current.json"
DEFAULT_OUT_CSV = "runs/transporter_apply_draft_status_current.csv"
DEFAULT_OUT_MD = "runs/transporter_apply_draft_status_current.md"


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


def _row_has_non_placeholder_stage(row: dict[str, Any]) -> bool:
    for field in (
        "replacement_ligand_id",
        "replacement_reference_binding_kcal_mol",
        "replacement_source",
        "replacement_smiles",
        "replacement_scaffold",
    ):
        if str(row.get(field, "")).strip():
            return True
    return False


def _glut1_staged_steps(seed_board_payload: dict[str, Any] | None) -> set[str]:
    if not seed_board_payload:
        return set()
    ready_steps: set[str] = set()
    for row in seed_board_payload.get("rows", []) or []:
        if str(row.get("target_id", "")).strip() != "GLUT1":
            continue
        if str(row.get("row_kind", "")).strip() != "binder":
            continue
        artifact_paths = [
            str(row.get("seed_packet_artifact", "")).strip(),
            str(row.get("fill_draft_artifact", "")).strip(),
            str(row.get("sync_preview_artifact", "")).strip(),
        ]
        if artifact_paths and all(path and _resolve(path).exists() for path in artifact_paths):
            ready_steps.add(str(row.get("packet_step", "")).strip())
    return ready_steps


def _negative_apply_allowed_steps(
    negative_apply_gate_payload: dict[str, Any] | None,
    target_id: str,
) -> set[str]:
    if not negative_apply_gate_payload:
        return set()
    out: set[str] = set()
    for row in negative_apply_gate_payload.get("rows", []) or []:
        if str(row.get("target_id", "")).strip() != target_id:
            continue
        if str(row.get("authoritative_negative_apply_allowed", "")).strip().lower() not in {
            "1",
            "true",
            "yes",
        } and not bool(row.get("authoritative_negative_apply_allowed", False)):
            continue
        packet_step = str(row.get("packet_step", "")).strip()
        if packet_step:
            out.add(packet_step)
    return out


def _append_step(base: str, addition: str) -> str:
    base_text = str(base or "").strip()
    addition_text = str(addition or "").strip()
    if base_text and addition_text:
        return f"{base_text} {addition_text}"
    return base_text or addition_text


def _target_summary(
    target_id: str,
    binder_sheet: dict[str, Any],
    note_templates: dict[str, Any],
    packet_workbook: dict[str, Any],
    packet_queue: dict[str, Any],
    quantitative_provenance_packet: dict[str, Any] | None = None,
    glut1_source_confirmation_packet: dict[str, Any] | None = None,
    seed_board_payload: dict[str, Any] | None = None,
    negative_apply_gate_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    binder_summary = dict(binder_sheet.get("summary", {}) or {})
    packet_summary = dict(packet_workbook.get("summary", {}) or {})
    queue_summary = dict(packet_queue.get("summary", {}) or {})
    provenance_summary = dict((quantitative_provenance_packet or {}).get("summary", {}) or {})
    glut1_source_confirmation_summary = dict((glut1_source_confirmation_packet or {}).get("summary", {}) or {})
    template_rows = [
        row for row in note_templates.get("rows", []) or []
        if str(row.get("target_id", "")).strip() == target_id
    ]
    exact_human_activity_count = (
        int(provenance_summary.get("exact_human_aqp1_activity_count", 0) or 0)
        if target_id == "AQP1"
        else 0
    )
    quantitative_provenance_focus_ligand = (
        str(provenance_summary.get("primary_focus_ligand", "")).strip()
        if target_id == "AQP1"
        else ""
    )
    quantitative_provenance_signal = (
        str(provenance_summary.get("signal", "")).strip()
        if target_id == "AQP1"
        else ""
    )
    second_wave_source_confirmation_ready = target_id == "GLUT1" and bool(glut1_source_confirmation_summary)
    second_wave_source_confirmation_packet_artifact = (
        "runs/glut1_second_wave_source_confirmation_packet_current.md"
        if second_wave_source_confirmation_ready
        else ""
    )
    second_wave_source_confirmation_row_count = (
        int(glut1_source_confirmation_summary.get("row_count", 0) or 0)
        if target_id == "GLUT1"
        else 0
    )
    second_wave_source_confirmation_primary_focus_ligand = (
        str(glut1_source_confirmation_summary.get("primary_focus_ligand", "")).strip()
        if target_id == "GLUT1"
        else ""
    )
    direct_quantitative_binding_count = (
        int(glut1_source_confirmation_summary.get("direct_quantitative_binding_count", 0) or 0)
        if target_id == "GLUT1"
        else 0
    )
    exact_target_pair_activity_count = (
        int(glut1_source_confirmation_summary.get("exact_target_pair_activity_count", 0) or 0)
        if target_id == "GLUT1"
        else 0
    )
    structured_pair_absent_count = (
        int(glut1_source_confirmation_summary.get("structured_pair_absent_count", 0) or 0)
        if target_id == "GLUT1"
        else 0
    )
    next_required_step = (
        str(binder_summary.get("next_required_step", "")).strip()
        or str(packet_summary.get("next_required_step", "")).strip()
        or str(queue_summary.get("next_required_step", "")).strip()
    )
    if target_id == "AQP1" and exact_human_activity_count > 0:
        next_required_step = _append_step(
            next_required_step,
            "Carry the exact-human-activity provenance lane forward, but keep "
            "replacement_reference_binding_kcal_mol blank.",
        )
    if target_id == "GLUT1" and second_wave_source_confirmation_ready:
        next_required_step = _append_step(
            next_required_step,
            (
                f"Keep {second_wave_source_confirmation_primary_focus_ligand or 'cytochalasin B'} as the GLUT1 "
                "second-wave source-confirmation lead with "
                f"direct_quantitative_binding_count={direct_quantitative_binding_count}, "
                f"exact_target_pair_activity_count={exact_target_pair_activity_count}, and "
                f"structured_pair_absent_count={structured_pair_absent_count}, and leave "
                "replacement_reference_binding_kcal_mol blank."
            ),
        )

    glut1_seed_steps = _glut1_staged_steps(seed_board_payload) if target_id == "GLUT1" else set()
    negative_apply_steps = _negative_apply_allowed_steps(negative_apply_gate_payload, target_id)
    ready_for_apply_rows = 0
    staged_non_authoritative_rows = 0
    placeholder_driven_rows = 0
    authoritative_negative_apply_rows = 0
    for row in packet_workbook.get("workbook_rows", []) or []:
        packet_step = str(row.get("packet_step", "")).strip()
        row_ready = str(row.get("row_ready_for_apply", "")).strip().lower() == "yes"
        row_staged = _row_has_non_placeholder_stage(row)
        glut1_surface_staged = target_id == "GLUT1" and packet_step in glut1_seed_steps
        authoritative_negative_ready = packet_step in negative_apply_steps
        if row_ready:
            ready_for_apply_rows += 1
        elif authoritative_negative_ready:
            ready_for_apply_rows += 1
            authoritative_negative_apply_rows += 1
        elif row_staged or glut1_surface_staged:
            staged_non_authoritative_rows += 1
        elif str(row.get("placeholder_sources", "")).strip():
            placeholder_driven_rows += 1

    return {
        "target_id": target_id,
        "binder_slot_count": int(binder_summary.get("binder_slot_count", 0) or 0),
        "binder_seed_row_count": int(binder_summary.get("binder_slot_count", 0) or 0),
        "pending_manual_verdict_count": int(binder_summary.get("pending_manual_verdict_count", 0) or 0),
        "completed_manual_verdict_count": int(binder_summary.get("completed_manual_verdict_count", 0) or 0),
        "suggested_prefill_count": int(binder_summary.get("suggested_prefill_count", 0) or 0),
        "note_template_count": len(template_rows),
        "packet_queue_count": int(queue_summary.get("queue_count", 0) or 0),
        "packet_binder_slots": int(queue_summary.get("binder_slots", 0) or 0),
        "packet_non_binder_slots": int(queue_summary.get("non_binder_slots", 0) or 0),
        "packet_workbook_row_count": int(packet_summary.get("workbook_row_count", 0) or 0),
        "ready_seed_row_count": int(packet_summary.get("ready_seed_row_count", 0) or 0),
        "ready_for_apply_rows": ready_for_apply_rows,
        "staged_non_authoritative_rows": staged_non_authoritative_rows,
        "placeholder_driven_rows": placeholder_driven_rows,
        "authoritative_negative_apply_rows": authoritative_negative_apply_rows,
        "seed_surface_artifact_count": len(glut1_seed_steps) if target_id == "GLUT1" else 0,
        "second_wave_source_confirmation_ready": second_wave_source_confirmation_ready,
        "second_wave_source_confirmation_packet_artifact": second_wave_source_confirmation_packet_artifact,
        "second_wave_source_confirmation_row_count": second_wave_source_confirmation_row_count,
        "second_wave_source_confirmation_primary_focus_ligand": second_wave_source_confirmation_primary_focus_ligand,
        "direct_quantitative_binding_count": direct_quantitative_binding_count,
        "exact_target_pair_activity_count": exact_target_pair_activity_count,
        "structured_pair_absent_count": structured_pair_absent_count,
        "exact_human_activity_count": exact_human_activity_count,
        "quantitative_provenance_focus_ligand": quantitative_provenance_focus_ligand,
        "quantitative_provenance_signal": quantitative_provenance_signal,
        "draft_apply_status": "manual_verdict_pending" if int(binder_summary.get("pending_manual_verdict_count", 0) or 0) > 0 else "seed_row_promotion_blocked",
        "next_required_step": next_required_step,
    }


def build_payload(
    aqp1_binder_sheet: dict[str, Any],
    glut1_binder_sheet: dict[str, Any],
    note_templates: dict[str, Any],
    aqp1_packet_workbook: dict[str, Any],
    glut1_packet_workbook: dict[str, Any],
    aqp1_packet_queue: dict[str, Any],
    glut1_packet_queue: dict[str, Any],
    aqp1_quantitative_provenance_packet: dict[str, Any] | None = None,
    glut1_source_confirmation_packet: dict[str, Any] | None = None,
    seed_board_payload: dict[str, Any] | None = None,
    negative_apply_gate_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = [
        _target_summary(
            "AQP1",
            aqp1_binder_sheet,
            note_templates,
            aqp1_packet_workbook,
            aqp1_packet_queue,
            quantitative_provenance_packet=aqp1_quantitative_provenance_packet,
            seed_board_payload=seed_board_payload,
            negative_apply_gate_payload=negative_apply_gate_payload,
        ),
        _target_summary(
            "GLUT1",
            glut1_binder_sheet,
            note_templates,
            glut1_packet_workbook,
            glut1_packet_queue,
            glut1_source_confirmation_packet=glut1_source_confirmation_packet,
            seed_board_payload=seed_board_payload,
            negative_apply_gate_payload=negative_apply_gate_payload,
        ),
    ]
    aqp1_row = next((row for row in rows if row["target_id"] == "AQP1"), {})
    glut1_row = next((row for row in rows if row["target_id"] == "GLUT1"), {})
    pending_manual_verdict_count = sum(row["pending_manual_verdict_count"] for row in rows)
    current_phase = (
        "manual_verdict_burndown"
        if pending_manual_verdict_count > 0
        else "blocker_closure_seed_row_promotion"
    )
    next_required_step = (
        "Use this board to track transporter draft-apply preparation only. Manual verdicts are still pending, so do not stage seed-row promotion yet."
        if pending_manual_verdict_count > 0
        else "Use this board to track transporter seed-row promotion readiness only. Manual verdicts and note templates are ready, but authoritative apply remains blocked while the remaining packet rows stay placeholder-driven."
    )
    if pending_manual_verdict_count == 0 and int(aqp1_row.get("exact_human_activity_count", 0) or 0) > 0:
        next_required_step = _append_step(
            next_required_step,
            "For AQP1, carry the exact-human-activity provenance lane forward without filling replacement_reference_binding_kcal_mol.",
        )
    if pending_manual_verdict_count == 0 and bool(glut1_row.get("second_wave_source_confirmation_ready", False)):
        next_required_step = _append_step(
            next_required_step,
            (
                f"For GLUT1, keep {str(glut1_row.get('second_wave_source_confirmation_primary_focus_ligand', '')).strip() or 'cytochalasin B'} "
                "as the second-wave source-confirmation lead with "
                f"direct_quantitative_binding_count={int(glut1_row.get('direct_quantitative_binding_count', 0) or 0)}, "
                f"exact_target_pair_activity_count={int(glut1_row.get('exact_target_pair_activity_count', 0) or 0)}, and "
                f"structured_pair_absent_count={int(glut1_row.get('structured_pair_absent_count', 0) or 0)}, and leave "
                "replacement_reference_binding_kcal_mol blank."
            ),
        )
    summary = {
        "target_count": len(rows),
        "current_phase": current_phase,
        "binder_slot_count": sum(row["binder_slot_count"] for row in rows),
        "binder_seed_row_count": sum(row["binder_seed_row_count"] for row in rows),
        "pending_manual_verdict_count": pending_manual_verdict_count,
        "completed_manual_verdict_count": sum(row["completed_manual_verdict_count"] for row in rows),
        "suggested_prefill_count": sum(row["suggested_prefill_count"] for row in rows),
        "note_template_count": sum(row["note_template_count"] for row in rows),
        "packet_queue_count": sum(row["packet_queue_count"] for row in rows),
        "packet_workbook_row_count": sum(row["packet_workbook_row_count"] for row in rows),
        "ready_for_apply_rows": sum(row["ready_for_apply_rows"] for row in rows),
        "staged_non_authoritative_rows": sum(row["staged_non_authoritative_rows"] for row in rows),
        "placeholder_driven_rows": sum(row["placeholder_driven_rows"] for row in rows),
        "authoritative_negative_apply_rows": sum(row["authoritative_negative_apply_rows"] for row in rows),
        "aqp1_exact_human_activity_count": int(aqp1_row.get("exact_human_activity_count", 0) or 0),
        "aqp1_quantitative_provenance_focus_ligand": str(aqp1_row.get("quantitative_provenance_focus_ligand", "")).strip(),
        "aqp1_quantitative_provenance_signal": str(aqp1_row.get("quantitative_provenance_signal", "")).strip(),
        "glut1_second_wave_source_confirmation_ready": bool(
            glut1_row.get("second_wave_source_confirmation_ready", False)
        ),
        "glut1_second_wave_source_confirmation_packet_artifact": str(
            glut1_row.get("second_wave_source_confirmation_packet_artifact", "")
        ).strip(),
        "glut1_second_wave_source_confirmation_row_count": int(
            glut1_row.get("second_wave_source_confirmation_row_count", 0) or 0
        ),
        "glut1_second_wave_source_confirmation_primary_focus_ligand": str(
            glut1_row.get("second_wave_source_confirmation_primary_focus_ligand", "")
        ).strip(),
        "glut1_direct_quantitative_binding_count": int(glut1_row.get("direct_quantitative_binding_count", 0) or 0),
        "glut1_exact_target_pair_activity_count": int(glut1_row.get("exact_target_pair_activity_count", 0) or 0),
        "glut1_structured_pair_absent_count": int(glut1_row.get("structured_pair_absent_count", 0) or 0),
        "next_required_step": next_required_step,
    }
    if pending_manual_verdict_count == 0 and summary["placeholder_driven_rows"] == 0:
        summary["next_required_step"] = (
            "Use this board to track transporter seed-row promotion readiness only. Manual verdicts and note templates are ready, "
            "negative placeholders are closed by the authoritative negative apply gate, and remaining promotion work is donor-policy "
            "reopen plus claim-safe binder-row promotion."
        )
        if int(aqp1_row.get("exact_human_activity_count", 0) or 0) > 0:
            summary["next_required_step"] = _append_step(
                summary["next_required_step"],
                "For AQP1, carry the exact-human-activity provenance lane forward without filling replacement_reference_binding_kcal_mol.",
            )
        if bool(glut1_row.get("second_wave_source_confirmation_ready", False)):
            summary["next_required_step"] = _append_step(
                summary["next_required_step"],
                (
                    f"For GLUT1, keep {str(glut1_row.get('second_wave_source_confirmation_primary_focus_ligand', '')).strip() or 'cytochalasin B'} "
                    "as the second-wave source-confirmation lead while binder rows remain non-authoritative."
                ),
            )
    return {"summary": summary, "target_rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Transporter Apply Draft Status",
        "",
        f"- target_count: `{s['target_count']}`",
        f"- current_phase: `{s['current_phase']}`",
        f"- binder_slot_count: `{s['binder_slot_count']}`",
        f"- binder_seed_row_count: `{s['binder_seed_row_count']}`",
        f"- pending_manual_verdict_count: `{s['pending_manual_verdict_count']}`",
        f"- completed_manual_verdict_count: `{s['completed_manual_verdict_count']}`",
        f"- suggested_prefill_count: `{s['suggested_prefill_count']}`",
        f"- note_template_count: `{s['note_template_count']}`",
        f"- packet_queue_count: `{s['packet_queue_count']}`",
        f"- packet_workbook_row_count: `{s['packet_workbook_row_count']}`",
        f"- ready_for_apply_rows: `{s['ready_for_apply_rows']}`",
        f"- staged_non_authoritative_rows: `{s['staged_non_authoritative_rows']}`",
        f"- placeholder_driven_rows: `{s['placeholder_driven_rows']}`",
        f"- authoritative_negative_apply_rows: `{s['authoritative_negative_apply_rows']}`",
        f"- aqp1_exact_human_activity_count: `{s['aqp1_exact_human_activity_count']}`",
        f"- aqp1_quantitative_provenance_focus_ligand: `{s['aqp1_quantitative_provenance_focus_ligand'] or '-'}`",
        f"- aqp1_quantitative_provenance_signal: `{s['aqp1_quantitative_provenance_signal'] or '-'}`",
        f"- glut1_second_wave_source_confirmation_ready: `{s['glut1_second_wave_source_confirmation_ready']}`",
        f"- glut1_second_wave_source_confirmation_packet_artifact: `{s['glut1_second_wave_source_confirmation_packet_artifact'] or '-'}`",
        f"- glut1_second_wave_source_confirmation_row_count: `{s['glut1_second_wave_source_confirmation_row_count']}`",
        f"- glut1_second_wave_source_confirmation_primary_focus_ligand: `{s['glut1_second_wave_source_confirmation_primary_focus_ligand'] or '-'}`",
        f"- glut1_direct_quantitative_binding_count: `{s['glut1_direct_quantitative_binding_count']}`",
        f"- glut1_exact_target_pair_activity_count: `{s['glut1_exact_target_pair_activity_count']}`",
        f"- glut1_structured_pair_absent_count: `{s['glut1_structured_pair_absent_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Target Seed-Row Status",
        "",
        "| target_id | draft_apply_status | binder_slot_count | binder_seed_row_count | pending_manual_verdict_count | suggested_prefill_count | note_template_count | packet_queue_count | packet_workbook_row_count | ready_for_apply_rows | staged_non_authoritative_rows | placeholder_driven_rows | authoritative_negative_apply_rows | second_wave_source_confirmation_ready | second_wave_source_confirmation_row_count | second_wave_source_confirmation_primary_focus_ligand | direct_quantitative_binding_count | exact_target_pair_activity_count | structured_pair_absent_count | exact_human_activity_count | quantitative_provenance_signal | next_required_step |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["target_rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['draft_apply_status']}` | {row['binder_slot_count']} | {row['binder_seed_row_count']} | {row['pending_manual_verdict_count']} | "
            f"{row['suggested_prefill_count']} | {row['note_template_count']} | {row['packet_queue_count']} | {row['packet_workbook_row_count']} | "
            f"{row['ready_for_apply_rows']} | {row['staged_non_authoritative_rows']} | {row['placeholder_driven_rows']} | "
            f"{row['authoritative_negative_apply_rows']} | "
            f"`{row['second_wave_source_confirmation_ready']}` | {row['second_wave_source_confirmation_row_count']} | "
            f"`{row['second_wave_source_confirmation_primary_focus_ligand'] or '-'}` | {row['direct_quantitative_binding_count']} | "
            f"{row['exact_target_pair_activity_count']} | {row['structured_pair_absent_count']} | {row['exact_human_activity_count']} | "
            f"`{row['quantitative_provenance_signal'] or '-'}` | {row['next_required_step']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a transporter apply-draft status board for AQP1 and GLUT1.")
    parser.add_argument("--aqp1-binder-sheet-json", default=DEFAULT_AQP1_BINDER_SHEET_JSON)
    parser.add_argument("--glut1-binder-sheet-json", default=DEFAULT_GLUT1_BINDER_SHEET_JSON)
    parser.add_argument("--note-templates-json", default=DEFAULT_NOTE_TEMPLATES_JSON)
    parser.add_argument("--aqp1-packet-json", default=DEFAULT_AQP1_PACKET_JSON)
    parser.add_argument("--glut1-packet-json", default=DEFAULT_GLUT1_PACKET_JSON)
    parser.add_argument("--aqp1-queue-json", default=DEFAULT_AQP1_QUEUE_JSON)
    parser.add_argument("--glut1-queue-json", default=DEFAULT_GLUT1_QUEUE_JSON)
    parser.add_argument("--aqp1-quantitative-provenance-json", default=DEFAULT_AQP1_QUANTITATIVE_PROVENANCE_JSON)
    parser.add_argument("--glut1-source-confirmation-json", default=DEFAULT_GLUT1_SOURCE_CONFIRMATION_JSON)
    parser.add_argument("--seed-board-json", default=DEFAULT_SEED_BOARD_JSON)
    parser.add_argument("--negative-apply-gate-json", default=DEFAULT_NEGATIVE_APPLY_GATE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.aqp1_binder_sheet_json),
        _load_json(args.glut1_binder_sheet_json),
        _load_json(args.note_templates_json),
        _load_json(args.aqp1_packet_json),
        _load_json(args.glut1_packet_json),
        _load_json(args.aqp1_queue_json),
        _load_json(args.glut1_queue_json),
        _load_json(args.aqp1_quantitative_provenance_json),
        _load_json(args.glut1_source_confirmation_json),
        _load_json(args.seed_board_json),
        _load_json(args.negative_apply_gate_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["target_rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
