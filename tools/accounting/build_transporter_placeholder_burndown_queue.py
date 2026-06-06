#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

RUNS = Path("runs")

DEFAULT_BLOCKER_JSON = RUNS / "transporter_authoritative_apply_blocker_decomposition_current.json"
DEFAULT_APPLY_STATUS_JSON = RUNS / "transporter_apply_draft_status_current.json"
DEFAULT_QUEUE_JSON = RUNS / "transporter_seed_row_promotion_board_current.json"
DEFAULT_AQP1_FOLLOW_ON_SOURCE_CONFIRMATION_JSON = RUNS / "aqp1_follow_on_source_confirmation_packet_current.json"
DEFAULT_GLUT1_SECOND_WAVE_SOURCE_CONFIRMATION_JSON = RUNS / "glut1_second_wave_source_confirmation_packet_current.json"
DEFAULT_NEGATIVE_APPLY_GATE_JSON = RUNS / "transporter_negative_authoritative_apply_gate_current.json"
DEFAULT_OUT_JSON = RUNS / "transporter_placeholder_burndown_queue_current.json"
DEFAULT_OUT_CSV = RUNS / "transporter_placeholder_burndown_queue_current.csv"
DEFAULT_OUT_MD = RUNS / "transporter_placeholder_burndown_queue_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (Path(__file__).resolve().parents[1] / path).resolve()


def _load_json(path_like: str | Path) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "pass", "passed"}
    return bool(value)


def _rows_by_step(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    payload = payload or {}
    return {
        _text(row.get("packet_step")): dict(row)
        for row in payload.get("rows", []) or []
        if _text(row.get("packet_step"))
    }


def _apply_rows_by_slot(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("slot_queue_id")): dict(row)
        for row in (payload or {}).get("rows", []) or []
        if _text(row.get("slot_queue_id"))
    }


def _artifacts_ready(*artifact_paths: str) -> bool:
    cleaned = [_text(path) for path in artifact_paths if _text(path)]
    return bool(cleaned) and all(_resolve(path).exists() for path in cleaned)


def _queue_order(row: dict[str, Any]) -> tuple[int, int, str]:
    target_id = _text(row.get("target_id")).upper()
    row_kind = _text(row.get("row_kind")).lower()
    if row_kind == "negative":
        return (2, 0 if target_id == "AQP1" else 1, _text(row.get("packet_step")))
    target_order = 0 if target_id == "AQP1" else 1 if target_id == "GLUT1" else 9
    return (target_order, 0, _text(row.get("packet_step")))


def _burndown_class(
    target_id: str,
    row_kind: str,
    seed_packet_artifact: str,
    fill_draft_artifact: str,
    sync_preview_artifact: str,
) -> str:
    if target_id.upper() == "AQP1" and row_kind == "binder":
        return "staged_non_authoritative"
    if target_id.upper() == "GLUT1" and row_kind == "binder" and _artifacts_ready(
        seed_packet_artifact,
        fill_draft_artifact,
        sync_preview_artifact,
    ):
        return "staged_non_authoritative"
    return "placeholder_driven"


def _burndown_phase(target_id: str, row_kind: str) -> str:
    if target_id.upper() == "AQP1" and row_kind == "binder":
        return "first_wave_seed_row_promotion"
    if target_id.upper() == "AQP1" and row_kind == "negative":
        return "first_wave_negative_review"
    if target_id.upper() == "GLUT1" and row_kind == "binder":
        return "second_wave_seed_row_promotion"
    return "second_wave_negative_review"


def _reduction_track(target_id: str, row_kind: str, seed_packet_artifact: str, fill_draft_artifact: str, sync_preview_artifact: str) -> str:
    if target_id.upper() == "AQP1" and row_kind == "binder":
        return "already_staged"
    if target_id.upper() == "GLUT1" and row_kind == "binder":
        if not _artifacts_ready(seed_packet_artifact, fill_draft_artifact, sync_preview_artifact):
            return "glut1_staging_surface_missing"
        return "glut1_staged"
    if row_kind == "negative":
        return "negative_evidence_missing"
    return "other"


def _reduction_potential(reduction_track: str) -> str:
    if reduction_track == "glut1_staging_surface_missing":
        return "reducible_now"
    if reduction_track == "negative_evidence_missing":
        return "requires_new_negative_evidence"
    if reduction_track == "negative_evidence_curated":
        return "already_counted_elsewhere"
    if reduction_track in {"already_staged", "glut1_staged"}:
        return "already_counted_elsewhere"
    return "unknown"


def _source_artifact(row: dict[str, Any], follow_on_ready: bool, glut1_second_wave_ready: bool) -> str:
    target_id = _text(row.get("target_id")).upper()
    packet_step = _text(row.get("packet_step"))
    row_kind = _text(row.get("row_kind")).lower()
    if row_kind == "negative":
        return "runs/transporter_negative_reviewer_day_plan_current.md"
    for field in ("seed_packet_artifact", "fill_draft_artifact", "sync_preview_artifact"):
        value = _text(row.get(field))
        if value and _resolve(value).exists():
            return value
    if target_id == "AQP1" and packet_step in {"core_binder_02", "core_binder_03"} and follow_on_ready:
        return "runs/aqp1_follow_on_source_confirmation_packet_current.md"
    if target_id == "GLUT1" and row_kind == "binder" and glut1_second_wave_ready:
        return "runs/glut1_second_wave_source_confirmation_packet_current.md"
    return "runs/transporter_seed_row_promotion_board_current.md"


def _burndown_action(target_id: str, row_kind: str, packet_step: str, next_required_action: str) -> str:
    if target_id.upper() == "AQP1" and row_kind == "binder":
        return (
            f"Keep {packet_step} staged as the first-wave AQP1 seed-row lane, preserve the AqB013 "
            "exact-human-activity provenance signal, and keep replacement_reference_binding_kcal_mol blank."
        )
    if target_id.upper() == "GLUT1" and row_kind == "binder":
        return (
            f"Queue {packet_step} as the second-wave GLUT1 binder lane only after the AQP1 rows are cleared, "
            "and keep transporter donor policy frozen."
        )
    if target_id.upper() == "AQP1" and row_kind == "negative":
        return "Keep AQP1 negative slots review-only until all AQP1 and GLUT1 binder placeholder lanes are parked."
    if target_id.upper() == "GLUT1" and row_kind == "negative":
        return "Keep GLUT1 negative slots review-only and leave them last in the burndown order."
    return next_required_action


def _target_queue_order(target_id: str) -> int:
    if target_id.upper() == "AQP1":
        return 0
    if target_id.upper() == "GLUT1":
        return 1
    return 9


def build_payload(
    blocker_payload: dict[str, Any],
    apply_status_payload: dict[str, Any],
    queue_payload: dict[str, Any],
    aqp1_follow_on_source_confirmation_payload: dict[str, Any] | None = None,
    glut1_second_wave_source_confirmation_payload: dict[str, Any] | None = None,
    negative_apply_gate_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blocker_summary = dict(blocker_payload.get("summary", {}) or {})
    apply_summary = dict(apply_status_payload.get("summary", {}) or {})
    queue_summary = dict(queue_payload.get("summary", {}) or {})
    follow_on_source_summary = dict((aqp1_follow_on_source_confirmation_payload or {}).get("summary", {}) or {})
    glut1_second_wave_summary = dict((glut1_second_wave_source_confirmation_payload or {}).get("summary", {}) or {})
    follow_on_source_ready = bool(follow_on_source_summary)
    glut1_second_wave_ready = bool(glut1_second_wave_summary)
    glut1_second_wave_by_step = _rows_by_step(glut1_second_wave_source_confirmation_payload)
    negative_apply_by_slot = _apply_rows_by_slot(negative_apply_gate_payload)

    apply_target_rows = {
        _text(row.get("target_id")).upper(): dict(row)
        for row in (apply_status_payload.get("target_rows", []) or [])
        if _text(row.get("target_id"))
    }
    queue_blocker_signal = _text(blocker_summary.get("top_blocker_signal")) or _text(apply_summary.get("top_blocker_signal"))
    if not queue_blocker_signal:
        queue_blocker_signal = (
            f"placeholder_driven_rows={_int(apply_summary.get('placeholder_driven_rows'))}; "
            f"staged_non_authoritative_rows={_int(apply_summary.get('staged_non_authoritative_rows'))}; "
            f"ready_for_apply_rows={_int(apply_summary.get('ready_for_apply_rows'))}"
        )

    queue_rows: list[dict[str, Any]] = []
    for row in sorted(list(queue_payload.get("rows", []) or []), key=_queue_order):
        target_id = _text(row.get("target_id"))
        row_kind = _text(row.get("row_kind")).lower()
        packet_step = _text(row.get("packet_step"))
        queue_id = f"{target_id}__{packet_step}"
        negative_apply_allowed = _bool(
            negative_apply_by_slot.get(queue_id, {}).get("authoritative_negative_apply_allowed")
        )
        burndown_class = _burndown_class(
            target_id,
            row_kind,
            _text(row.get("seed_packet_artifact")),
            _text(row.get("fill_draft_artifact")),
            _text(row.get("sync_preview_artifact")),
        )
        reduction_track = _reduction_track(
            target_id,
            row_kind,
            _text(row.get("seed_packet_artifact")),
            _text(row.get("fill_draft_artifact")),
            _text(row.get("sync_preview_artifact")),
        )
        if row_kind == "negative" and negative_apply_allowed:
            burndown_class = "evidence_curated"
            reduction_track = "negative_evidence_curated"
        glut1_source_row = glut1_second_wave_by_step.get(packet_step, {}) if target_id.upper() == "GLUT1" else {}
        queue_rank = len(queue_rows) + 1
        queue_rows.append(
            {
                "queue_rank": queue_rank,
                "queue_id": queue_id,
                "priority_rank": _int(row.get("priority_rank")),
                "target_id": target_id,
                "wave": _text(row.get("wave")),
                "queue_lane": "today_first" if target_id.upper() == "AQP1" else "today_second",
                "packet_step": packet_step,
                "row_kind": row_kind,
                "promotion_class": _text(row.get("promotion_class")),
                "burndown_phase": _burndown_phase(target_id, row_kind),
                "burndown_class": burndown_class,
                "candidate_name": _text(glut1_source_row.get("candidate_name")) or _text(row.get("candidate_name")),
                "source_anchor": _text(glut1_source_row.get("source_anchor")) or _text(row.get("source_anchor")),
                "source_url": _text(glut1_source_row.get("source_url")) or _text(row.get("source_url")),
                "review_bucket": _text(row.get("review_bucket")),
                "promotion_blocker": _text(glut1_source_row.get("promotion_blocker")) or _text(row.get("promotion_blocker")),
                "source_next_required_action": _text(glut1_source_row.get("next_required_action")) or _text(row.get("next_required_action")),
                "burndown_action": _burndown_action(
                    target_id,
                    row_kind,
                    packet_step,
                    _text(row.get("next_required_action")),
                ),
                "required_seed_fields": _text(row.get("required_seed_fields")),
                "seed_packet_artifact": _text(row.get("seed_packet_artifact")),
                "fill_draft_artifact": _text(row.get("fill_draft_artifact")),
                "sync_preview_artifact": _text(row.get("sync_preview_artifact")),
                "reduction_track": reduction_track,
                "negative_apply_gate_artifact": "runs/transporter_negative_authoritative_apply_gate_current.md",
                "authoritative_negative_apply_allowed": negative_apply_allowed,
                "queue_artifact": "runs/transporter_seed_row_promotion_board_current.md",
                "apply_artifact": "runs/transporter_apply_draft_status_current.md",
                "blocker_artifact": "runs/transporter_authoritative_apply_blocker_decomposition_current.md",
                "source_artifact": _source_artifact(row, follow_on_source_ready, glut1_second_wave_ready),
                "blocker_link": queue_blocker_signal,
            }
        )
        queue_rows[-1]["reduction_potential"] = _reduction_potential(queue_rows[-1]["reduction_track"])

    target_rows: list[dict[str, Any]] = []
    for target_id in ("AQP1", "GLUT1"):
        ordered_rows = [row for row in queue_rows if row["target_id"].upper() == target_id]
        apply_row = apply_target_rows.get(target_id, {})
        queue_start_rank = ordered_rows[0]["queue_rank"] if ordered_rows else 0
        queue_end_rank = ordered_rows[-1]["queue_rank"] if ordered_rows else 0
        exact_human_activity_count = 0
        quantitative_focus_ligand = ""
        quantitative_signal = ""
        if target_id == "AQP1":
            exact_human_activity_count = _int(
                apply_row.get("exact_human_activity_count", apply_summary.get("aqp1_exact_human_activity_count", 0))
            )
            quantitative_focus_ligand = _text(
                apply_row.get(
                    "quantitative_provenance_focus_ligand",
                    apply_summary.get("aqp1_quantitative_provenance_focus_ligand", ""),
                )
            )
            quantitative_signal = _text(
                apply_row.get(
                    "quantitative_provenance_signal",
                    apply_summary.get("aqp1_quantitative_provenance_signal", ""),
                )
            )

        target_rows.append(
            {
                "target_id": target_id,
                "wave_priority": "today_first" if target_id == "AQP1" else "today_second",
                "queue_start_rank": queue_start_rank,
                "queue_end_rank": queue_end_rank,
                "queue_row_count": len(ordered_rows),
                "staged_non_authoritative_rows": sum(
                    1 for row in ordered_rows if row["burndown_class"] == "staged_non_authoritative"
                ),
                "placeholder_driven_rows": sum(
                    1 for row in ordered_rows if row["burndown_class"] == "placeholder_driven"
                ),
                "first_packet_step": ordered_rows[0]["packet_step"] if ordered_rows else "",
                "last_packet_step": ordered_rows[-1]["packet_step"] if ordered_rows else "",
                "exact_human_activity_count": exact_human_activity_count,
                "quantitative_provenance_focus_ligand": quantitative_focus_ligand,
                "quantitative_provenance_signal": quantitative_signal,
                "next_required_step": (
                    "Stage the three AQP1 binder rows first, keep the exact-human-activity provenance lane visible, "
                    "then move to GLUT1 binder rows; keep AQP1 negative slots parked until the binder lanes are exhausted."
                    if target_id == "AQP1"
                    else (
                        "Keep GLUT1 second-wave only after AQP1 binders are parked; use the GLUT1 second-wave source-confirmation packet "
                        "for core_binder_01 through core_binder_03 before any negative slots."
                        if glut1_second_wave_ready
                        else "Keep GLUT1 second-wave only after AQP1 binders are parked; burn down GLUT1 binder placeholders before any negative slots."
                    )
                ),
                "queue_artifact": "runs/transporter_seed_row_promotion_board_current.md",
                "apply_artifact": "runs/transporter_apply_draft_status_current.md",
                "blocker_artifact": "runs/transporter_authoritative_apply_blocker_decomposition_current.md",
            }
        )

    reducible_now_rows = [
        row for row in queue_rows if row["burndown_class"] == "placeholder_driven" and row["reduction_potential"] == "reducible_now"
    ]
    evidence_blocked_rows = [
        row
        for row in queue_rows
        if row["burndown_class"] == "placeholder_driven" and row["reduction_potential"] != "reducible_now"
    ]
    negative_evidence_missing_rows = [row for row in queue_rows if row["reduction_track"] == "negative_evidence_missing"]
    immediate_reduction_target = "GLUT1 binder staging surfaces" if reducible_now_rows else ""
    immediate_reduction_target_queue_start = min((row["queue_rank"] for row in reducible_now_rows), default=0)
    immediate_reduction_target_queue_end = max((row["queue_rank"] for row in reducible_now_rows), default=0)
    current_placeholder_rows = sum(1 for row in queue_rows if row["burndown_class"] == "placeholder_driven")
    current_staged_rows = sum(1 for row in queue_rows if row["burndown_class"] == "staged_non_authoritative")
    current_apply_ready_rows = sum(1 for row in queue_rows if row["authoritative_negative_apply_allowed"])
    current_blocker_signal = (
        f"placeholder_driven_rows={current_placeholder_rows}; "
        f"staged_non_authoritative_rows={current_staged_rows}; "
        f"ready_for_apply_rows={current_apply_ready_rows}"
    )
    placeholder_status_sentence = (
        "All transporter negative placeholder rows are evidence-curated by the authoritative apply gate."
        if not current_placeholder_rows and current_apply_ready_rows
        else (
            f"The first reducible-now slice is {immediate_reduction_target} covering queue ranks "
            f"{immediate_reduction_target_queue_start}-{immediate_reduction_target_queue_end} for a potential "
            f"{len(reducible_now_rows)}-row reduction."
            if reducible_now_rows
            else "The reducible-now GLUT1 staging slice is already parked, so the remaining placeholder-driven rows are evidence-blocked negative slots."
        )
    )

    summary = {
        "family": "transporter",
        "target_count": len(target_rows),
        "queue_row_count": len(queue_rows),
        "row_count": len(queue_rows),
        "seed_row_count": _int(queue_summary.get("aqp1_seed_surface_count") or 3),
        "binder_row_count": sum(1 for row in queue_rows if row["row_kind"] == "binder"),
        "negative_row_count": sum(1 for row in queue_rows if row["row_kind"] == "negative"),
        "staged_non_authoritative_rows": current_staged_rows,
        "placeholder_driven_rows": current_placeholder_rows,
        "transporter_staged_non_authoritative_rows": sum(
            1 for row in queue_rows if row["burndown_class"] == "staged_non_authoritative"
        ),
        "transporter_placeholder_driven_rows": sum(1 for row in queue_rows if row["burndown_class"] == "placeholder_driven"),
        "reducible_now_placeholder_rows": len(reducible_now_rows),
        "evidence_blocked_placeholder_rows": len(evidence_blocked_rows),
        "glut1_staging_surface_missing_rows": sum(
            1 for row in queue_rows if row["reduction_track"] == "glut1_staging_surface_missing"
        ),
        "negative_evidence_missing_rows": len(negative_evidence_missing_rows),
        "immediate_reduction_target": immediate_reduction_target,
        "immediate_reduction_target_queue_start": immediate_reduction_target_queue_start,
        "immediate_reduction_target_queue_end": immediate_reduction_target_queue_end,
        "immediate_reduction_delta_if_completed": len(reducible_now_rows),
        "ready_for_apply_rows": current_apply_ready_rows or _int(apply_summary.get("ready_for_apply_rows")),
        "top_blocker_id": _text(blocker_summary.get("top_blocker_id")) or "placeholder_packet_rows",
        "top_blocker_signal": current_blocker_signal,
        "first_wave_target": _text(queue_summary.get("first_wave_target")) or "AQP1",
        "second_wave_target": _text(queue_summary.get("second_wave_target")) or "GLUT1",
        "today_first_target": _text(queue_summary.get("first_wave_target")) or "AQP1",
        "today_second_target": _text(queue_summary.get("second_wave_target")) or "GLUT1",
        "today_seed_target": _text(queue_summary.get("today_seed_target")) or "AQP1 core_binder_01",
        "aqp1_seed_surface_count": _int(queue_summary.get("aqp1_seed_surface_count") or 3),
        "glut1_seed_surface_count": _int(queue_summary.get("glut1_seed_surface_count") or 3),
        "aqp1_exact_human_activity_count": _int(apply_summary.get("aqp1_exact_human_activity_count")),
        "aqp1_quantitative_provenance_focus_ligand": _text(apply_summary.get("aqp1_quantitative_provenance_focus_ligand")),
        "aqp1_quantitative_provenance_signal": _text(apply_summary.get("aqp1_quantitative_provenance_signal")),
        "aqp1_follow_on_source_confirmation_row_count": _int(follow_on_source_summary.get("row_count")),
        "aqp1_follow_on_source_confirmation_primary_focus_ligand": _text(
            follow_on_source_summary.get("primary_focus_ligand")
        ),
        "aqp1_follow_on_exact_human_guardrail_ligand": _text(
            follow_on_source_summary.get("exact_human_guardrail_ligand")
        ),
        "glut1_second_wave_source_confirmation_ready": glut1_second_wave_ready,
        "glut1_second_wave_source_confirmation_artifact": (
            "runs/glut1_second_wave_source_confirmation_packet_current.md" if glut1_second_wave_ready else ""
        ),
        "glut1_second_wave_source_confirmation_row_count": _int(glut1_second_wave_summary.get("row_count")),
        "glut1_second_wave_source_confirmation_primary_focus_ligand": _text(
            glut1_second_wave_summary.get("primary_focus_ligand")
        ),
        "glut1_second_wave_direct_quantitative_binding_count": _int(
            glut1_second_wave_summary.get("direct_quantitative_binding_count")
        ),
        "top_queue_id": _text(queue_rows[0].get("queue_id")) if queue_rows else "",
        "queue_order_signal": (
            "AQP1 binder seed rows, then GLUT1 binder rows, then AQP1 negative slots, then GLUT1 negative slots"
        ),
        "next_required_step": (
            "Burn down transporter rows in queue order: AQP1 core_binder_01 through core_binder_03 first, "
            "then GLUT1 core_binder_01 through core_binder_03, then AQP1 core_non_binder_01 through core_non_binder_03, "
            "then GLUT1 core_non_binder_01 through core_non_binder_03. Keep AqB013 as the exact-human-activity provenance lane, "
            f"treat {_text(follow_on_source_summary.get('primary_focus_ligand')) or 'AqB011'} as the literature-backed follow-on exact-source row, "
            f"treat {_text(glut1_second_wave_summary.get('primary_focus_ligand')) or 'cytochalasin B'} as the GLUT1 second-wave source-confirmation lead, "
            "leave replacement_reference_binding_kcal_mol blank, and do not reopen donor policy until the placeholder-driven rows are reduced. "
            + placeholder_status_sentence
        ),
    }
    return {"summary": summary, "target_rows": target_rows, "rows": queue_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Transporter Placeholder Burndown Queue",
        "",
        f"- family: `{s['family']}`",
        f"- target_count: `{s['target_count']}`",
        f"- queue_row_count: `{s['queue_row_count']}`",
        f"- staged_non_authoritative_rows: `{s['staged_non_authoritative_rows']}`",
        f"- placeholder_driven_rows: `{s['placeholder_driven_rows']}`",
        f"- reducible_now_placeholder_rows: `{s['reducible_now_placeholder_rows']}`",
        f"- evidence_blocked_placeholder_rows: `{s['evidence_blocked_placeholder_rows']}`",
        f"- glut1_staging_surface_missing_rows: `{s['glut1_staging_surface_missing_rows']}`",
        f"- negative_evidence_missing_rows: `{s['negative_evidence_missing_rows']}`",
        f"- immediate_reduction_target: `{s['immediate_reduction_target'] or '-'}`",
        f"- immediate_reduction_target_queue_start: `{s['immediate_reduction_target_queue_start']}`",
        f"- immediate_reduction_target_queue_end: `{s['immediate_reduction_target_queue_end']}`",
        f"- immediate_reduction_delta_if_completed: `{s['immediate_reduction_delta_if_completed']}`",
        f"- ready_for_apply_rows: `{s['ready_for_apply_rows']}`",
        f"- top_blocker_id: `{s['top_blocker_id']}`",
        f"- top_blocker_signal: `{s['top_blocker_signal']}`",
        f"- first_wave_target: `{s['first_wave_target']}`",
        f"- second_wave_target: `{s['second_wave_target']}`",
        f"- today_seed_target: `{s['today_seed_target']}`",
        f"- aqp1_seed_surface_count: `{s['aqp1_seed_surface_count']}`",
        f"- glut1_seed_surface_count: `{s['glut1_seed_surface_count']}`",
        f"- aqp1_exact_human_activity_count: `{s['aqp1_exact_human_activity_count']}`",
        f"- aqp1_quantitative_provenance_focus_ligand: `{s['aqp1_quantitative_provenance_focus_ligand'] or '-'}`",
        f"- aqp1_quantitative_provenance_signal: `{s['aqp1_quantitative_provenance_signal'] or '-'}`",
        f"- aqp1_follow_on_source_confirmation_row_count: `{s['aqp1_follow_on_source_confirmation_row_count']}`",
        f"- aqp1_follow_on_source_confirmation_primary_focus_ligand: `{s['aqp1_follow_on_source_confirmation_primary_focus_ligand'] or '-'}`",
        f"- aqp1_follow_on_exact_human_guardrail_ligand: `{s['aqp1_follow_on_exact_human_guardrail_ligand'] or '-'}`",
        f"- glut1_second_wave_source_confirmation_ready: `{s['glut1_second_wave_source_confirmation_ready']}`",
        f"- glut1_second_wave_source_confirmation_row_count: `{s['glut1_second_wave_source_confirmation_row_count']}`",
        f"- glut1_second_wave_source_confirmation_primary_focus_ligand: `{s['glut1_second_wave_source_confirmation_primary_focus_ligand'] or '-'}`",
        f"- glut1_second_wave_direct_quantitative_binding_count: `{s['glut1_second_wave_direct_quantitative_binding_count']}`",
        f"- top_queue_id: `{s['top_queue_id']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Target Burndown",
        "",
        "| target_id | wave_priority | queue_start_rank | queue_end_rank | queue_row_count | staged_non_authoritative_rows | placeholder_driven_rows | first_packet_step | last_packet_step | next_required_step |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["target_rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['wave_priority']}` | {row['queue_start_rank']} | {row['queue_end_rank']} | {row['queue_row_count']} | "
            f"{row['staged_non_authoritative_rows']} | {row['placeholder_driven_rows']} | `{row['first_packet_step']}` | `{row['last_packet_step']}` | "
            f"{row['next_required_step']} |"
        )
    lines.extend(
        [
            "",
            "## Queue",
            "",
            "| queue_rank | queue_id | target_id | wave | packet_step | row_kind | burndown_class | reduction_track | reduction_potential | candidate_name | source_artifact | burndown_action |",
            "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| {row['queue_rank']} | `{row['queue_id']}` | `{row['target_id']}` | `{row['wave']}` | `{row['packet_step']}` | "
            f"`{row['row_kind']}` | `{row['burndown_class']}` | `{row['reduction_track']}` | `{row['reduction_potential']}` | "
            f"`{row['candidate_name']}` | `{row['source_artifact']}` | `{row['burndown_action']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the transporter placeholder burndown queue from blocker/apply/queue artifacts.")
    parser.add_argument("--blocker-json", default=str(DEFAULT_BLOCKER_JSON))
    parser.add_argument("--apply-status-json", default=str(DEFAULT_APPLY_STATUS_JSON))
    parser.add_argument("--queue-json", default=str(DEFAULT_QUEUE_JSON))
    parser.add_argument(
        "--aqp1-follow-on-source-confirmation-json",
        default=str(DEFAULT_AQP1_FOLLOW_ON_SOURCE_CONFIRMATION_JSON),
    )
    parser.add_argument(
        "--glut1-second-wave-source-confirmation-json",
        default=str(DEFAULT_GLUT1_SECOND_WAVE_SOURCE_CONFIRMATION_JSON),
    )
    parser.add_argument("--negative-apply-gate-json", default=str(DEFAULT_NEGATIVE_APPLY_GATE_JSON))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    follow_on_source_confirmation_path = _resolve(args.aqp1_follow_on_source_confirmation_json)
    glut1_second_wave_source_confirmation_path = _resolve(args.glut1_second_wave_source_confirmation_json)
    negative_apply_gate_path = _resolve(args.negative_apply_gate_json)
    payload = build_payload(
        _load_json(args.blocker_json),
        _load_json(args.apply_status_json),
        _load_json(args.queue_json),
        _load_json(follow_on_source_confirmation_path) if follow_on_source_confirmation_path.exists() else None,
        _load_json(glut1_second_wave_source_confirmation_path)
        if glut1_second_wave_source_confirmation_path.exists()
        else None,
        _load_json(negative_apply_gate_path) if negative_apply_gate_path.exists() else None,
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
