#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AQP1_NOTE_JSON = "runs/aqp1_local_evidence_note_current.json"
DEFAULT_AQP1_QUEUE_JSON = "runs/aqp1_manual_review_queue_current.json"
DEFAULT_AQP1_PLAN_JSON = "runs/aqp1_p0_packet_plan_current.json"
DEFAULT_AQP1_EXTERNAL_SEED_JSON = "runs/aqp1_external_evidence_seed_current.json"
DEFAULT_AQP1_VERDICT_JSON = "runs/aqp1_candidate_verdict_sheet_current.json"
DEFAULT_GLUT1_NOTE_JSON = "runs/glut1_local_evidence_note_current.json"
DEFAULT_GLUT1_QUEUE_JSON = "runs/glut1_manual_review_queue_current.json"
DEFAULT_GLUT1_PENDING_JSON = "runs/glut1_pending_row_disposition_current.json"
DEFAULT_GLUT1_EXTERNAL_SEED_JSON = "runs/glut1_external_evidence_seed_current.json"
DEFAULT_GLUT1_VERDICT_JSON = "runs/glut1_candidate_verdict_sheet_current.json"
DEFAULT_AQP1_BINDER_SHEET_JSON = "runs/aqp1_binder_verdict_update_sheet_current.json"
DEFAULT_GLUT1_BINDER_SHEET_JSON = "runs/glut1_binder_verdict_update_sheet_current.json"
DEFAULT_AQP1_DRAFT_PACKET_JSON = "runs/aqp1_manual_verdict_draft_packet_current.json"
DEFAULT_GLUT1_DRAFT_PACKET_JSON = "runs/glut1_manual_verdict_draft_packet_current.json"
DEFAULT_AQP1_COMMIT_PACKET_JSON = "runs/aqp1_manual_verdict_commit_packet_current.json"
DEFAULT_GLUT1_COMMIT_PACKET_JSON = "runs/glut1_manual_verdict_commit_packet_current.json"
DEFAULT_AQP1_CONFIRMATION_CARD_JSON = "runs/aqp1_binder_confirmation_card_current.json"
DEFAULT_GLUT1_CONFIRMATION_CARD_JSON = "runs/glut1_binder_confirmation_card_current.json"
DEFAULT_AQP1_STAGING_SHEET_JSON = "runs/aqp1_manual_verdict_staging_sheet_current.json"
DEFAULT_GLUT1_STAGING_SHEET_JSON = "runs/glut1_manual_verdict_staging_sheet_current.json"
DEFAULT_AQP1_APPLY_DRAFT_JSON = "runs/aqp1_manual_verdict_apply_draft_current.json"
DEFAULT_GLUT1_APPLY_DRAFT_JSON = "runs/glut1_manual_verdict_apply_draft_current.json"
DEFAULT_AQP1_SEED_ROW_FILL_DRAFT_JSON = "runs/aqp1_seed_row_fill_draft_current.json"
DEFAULT_AQP1_SEED_ROW_SYNC_PREVIEW_JSON = "runs/aqp1_seed_row_sync_apply_preview_current.json"
DEFAULT_AQP1_QUANTITATIVE_PROVENANCE_JSON = "runs/aqp1_quantitative_provenance_packet_current.json"
DEFAULT_GLUT1_SOURCE_CONFIRMATION_JSON = "runs/glut1_second_wave_source_confirmation_packet_current.json"
DEFAULT_AQP1_NEGATIVE_PACKET_JSON = "runs/aqp1_negative_review_handoff_packet_current.json"
DEFAULT_GLUT1_NEGATIVE_PACKET_JSON = "runs/glut1_negative_review_handoff_packet_current.json"
DEFAULT_BINDER_PROGRESS_JSON = "runs/transporter_binder_verdict_progress_current.json"
DEFAULT_BINDER_RUBRIC_JSON = "runs/transporter_binder_decision_rubric_current.json"
DEFAULT_BINDER_NOTE_TEMPLATES_JSON = "runs/transporter_manual_decision_note_templates_current.json"
DEFAULT_BINDER_PREFILL_PREVIEW_JSON = "runs/transporter_manual_verdict_prefill_preview_current.json"
DEFAULT_BINDER_PACKETS_JSON = "runs/transporter_manual_verdict_packets_current.json"
DEFAULT_BINDER_CONFIRMATION_CONSOLE_JSON = "runs/transporter_manual_verdict_confirmation_console_current.json"
DEFAULT_OPERATOR_CONSOLE_JSON = "runs/transporter_operator_console_current.json"
DEFAULT_LAUNCHBOARD_JSON = "runs/transporter_manual_review_launchboard_current.json"
DEFAULT_TRANSPORTER_APPLY_STATUS_JSON = "runs/transporter_apply_draft_status_current.json"
DEFAULT_REVIEWER_DAY_PLAN_JSON = "runs/transporter_reviewer_day_plan_current.json"
DEFAULT_REVIEWER_DAY2_CONSOLE_JSON = "runs/transporter_reviewer_day2_console_current.json"
DEFAULT_NEGATIVE_REVIEWER_DAY_PLAN_JSON = "runs/transporter_negative_reviewer_day_plan_current.json"
DEFAULT_NEGATIVE_TARGET_PACKETS_JSON = "runs/transporter_negative_evidence_target_packets_current.json"
DEFAULT_DONOR_POLICY_JSON = "runs/transporter_fit_donor_policy_decision_current.json"
DEFAULT_READINESS_JSON = "runs/transporter_membrane_readiness_current.json"
DEFAULT_OUT_JSON = "runs/transporter_manual_review_dashboard_current.json"
DEFAULT_OUT_CSV = "runs/transporter_manual_review_dashboard_current.csv"
DEFAULT_OUT_MD = "runs/transporter_manual_review_dashboard_current.md"


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
    aqp1_note: dict[str, Any],
    aqp1_queue: dict[str, Any],
    aqp1_plan: dict[str, Any],
    aqp1_external_seed: dict[str, Any] | None,
    aqp1_verdict: dict[str, Any] | None,
    glut1_note: dict[str, Any],
    glut1_queue: dict[str, Any],
    glut1_pending: dict[str, Any],
    glut1_external_seed: dict[str, Any] | None,
    glut1_verdict: dict[str, Any] | None,
    aqp1_binder_sheet: dict[str, Any] | None,
    glut1_binder_sheet: dict[str, Any] | None,
    aqp1_draft_packet: dict[str, Any] | None,
    glut1_draft_packet: dict[str, Any] | None,
    aqp1_commit_packet: dict[str, Any] | None,
    glut1_commit_packet: dict[str, Any] | None,
    aqp1_confirmation_card: dict[str, Any] | None,
    glut1_confirmation_card: dict[str, Any] | None,
    aqp1_staging_sheet: dict[str, Any] | None,
    glut1_staging_sheet: dict[str, Any] | None,
    aqp1_apply_draft: dict[str, Any] | None,
    glut1_apply_draft: dict[str, Any] | None,
    aqp1_quantitative_provenance: dict[str, Any] | None,
    aqp1_negative_packet: dict[str, Any] | None,
    glut1_negative_packet: dict[str, Any] | None,
    binder_progress: dict[str, Any] | None,
    binder_rubric: dict[str, Any] | None,
    binder_note_templates: dict[str, Any] | None,
    binder_prefill_preview: dict[str, Any] | None,
    binder_packets: dict[str, Any] | None,
    binder_confirmation_console: dict[str, Any] | None,
    operator_console: dict[str, Any] | None,
    launchboard: dict[str, Any] | None,
    transporter_apply_status: dict[str, Any] | None,
    reviewer_day_plan: dict[str, Any] | None,
    reviewer_day2_console: dict[str, Any] | None,
    negative_reviewer_day_plan: dict[str, Any] | None,
    donor_policy: dict[str, Any],
    readiness: dict[str, Any],
    aqp1_seed_row_fill_draft: dict[str, Any] | None = None,
    aqp1_seed_row_sync_preview: dict[str, Any] | None = None,
    glut1_source_confirmation: dict[str, Any] | None = None,
    negative_target_packets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    aqp1_s = dict(aqp1_note.get("summary", {}) or {})
    aqp1_q = dict(aqp1_queue.get("summary", {}) or {})
    aqp1_p = dict(aqp1_plan.get("summary", {}) or {})
    aqp1_x = dict((aqp1_external_seed or {}).get("summary", {}) or {})
    aqp1_v = dict((aqp1_verdict or {}).get("summary", {}) or {})
    glut1_s = dict(glut1_note.get("summary", {}) or {})
    glut1_q = dict(glut1_queue.get("summary", {}) or {})
    glut1_p = dict(glut1_pending.get("summary", {}) or {})
    glut1_x = dict((glut1_external_seed or {}).get("summary", {}) or {})
    glut1_v = dict((glut1_verdict or {}).get("summary", {}) or {})
    aqp1_b = dict((aqp1_binder_sheet or {}).get("summary", {}) or {})
    glut1_b = dict((glut1_binder_sheet or {}).get("summary", {}) or {})
    aqp1_draft_s = dict((aqp1_draft_packet or {}).get("summary", {}) or {})
    glut1_draft_s = dict((glut1_draft_packet or {}).get("summary", {}) or {})
    aqp1_commit_s = dict((aqp1_commit_packet or {}).get("summary", {}) or {})
    glut1_commit_s = dict((glut1_commit_packet or {}).get("summary", {}) or {})
    aqp1_confirmation_s = dict((aqp1_confirmation_card or {}).get("summary", {}) or {})
    glut1_confirmation_s = dict((glut1_confirmation_card or {}).get("summary", {}) or {})
    aqp1_staging_s = dict((aqp1_staging_sheet or {}).get("summary", {}) or {})
    glut1_staging_s = dict((glut1_staging_sheet or {}).get("summary", {}) or {})
    aqp1_apply_s = dict((aqp1_apply_draft or {}).get("summary", {}) or {})
    glut1_apply_s = dict((glut1_apply_draft or {}).get("summary", {}) or {})
    aqp1_quantitative_s = dict((aqp1_quantitative_provenance or {}).get("summary", {}) or {})
    glut1_source_confirmation_s = dict((glut1_source_confirmation or {}).get("summary", {}) or {})
    aqp1_seed_fill_s = dict((aqp1_seed_row_fill_draft or {}).get("summary", {}) or {})
    aqp1_seed_sync_s = dict((aqp1_seed_row_sync_preview or {}).get("summary", {}) or {})
    aqp1_negative_s = dict((aqp1_negative_packet or {}).get("summary", {}) or {})
    glut1_negative_s = dict((glut1_negative_packet or {}).get("summary", {}) or {})
    binder_progress_s = dict((binder_progress or {}).get("summary", {}) or {})
    binder_rubric_s = dict((binder_rubric or {}).get("summary", {}) or {})
    binder_note_templates_s = dict((binder_note_templates or {}).get("summary", {}) or {})
    binder_prefill_preview_s = dict((binder_prefill_preview or {}).get("summary", {}) or {})
    binder_packets_s = dict((binder_packets or {}).get("summary", {}) or {})
    binder_confirmation_console_s = dict((binder_confirmation_console or {}).get("summary", {}) or {})
    operator_console_s = dict((operator_console or {}).get("summary", {}) or {})
    launchboard_s = dict((launchboard or {}).get("summary", {}) or {})
    transporter_apply_status_s = dict((transporter_apply_status or {}).get("summary", {}) or {})
    transporter_apply_status_by_target = {
        str(row.get("target_id", "")).strip(): dict(row)
        for row in (transporter_apply_status or {}).get("target_rows", []) or []
        if str(row.get("target_id", "")).strip()
    }
    reviewer_day_plan_s = dict((reviewer_day_plan or {}).get("summary", {}) or {})
    reviewer_day2_console_s = dict((reviewer_day2_console or {}).get("summary", {}) or {})
    negative_reviewer_day_plan_s = dict((negative_reviewer_day_plan or {}).get("summary", {}) or {})
    negative_target_packets_s = dict((negative_target_packets or {}).get("summary", {}) or {})
    packet_by_target = {
        str(packet.get("target_id", "")).strip(): dict(packet)
        for packet in (binder_packets or {}).get("target_packets", []) or []
        if str(packet.get("target_id", "")).strip()
    }
    donor_s = dict(donor_policy.get("summary", {}) or {})
    readiness_s = dict(readiness.get("summary", {}) or {})
    aqp1_primary_probe_resolution_handoff = _aqp1_primary_probe_resolution_handoff(negative_target_packets_s)
    aqp1_primary_probe_resolution_artifact = str(
        negative_target_packets_s.get("aqp1_negative_primary_probe_resolution_artifact", "") or ""
    ).strip()
    aqp1_primary_probe_resolution_candidate = str(
        negative_target_packets_s.get("aqp1_negative_primary_probe_resolution_candidate", "") or ""
    ).strip()
    aqp1_primary_probe_resolution_decision = str(
        negative_target_packets_s.get("aqp1_negative_primary_probe_resolution_decision", "") or ""
    ).strip()
    aqp1_primary_probe_resolution_solvent_fallback_candidate = str(
        negative_target_packets_s.get("aqp1_negative_primary_probe_resolution_solvent_fallback_candidate", "") or ""
    ).strip()
    aqp1_apply_status_row = transporter_apply_status_by_target.get("AQP1", {})
    glut1_apply_status_row = transporter_apply_status_by_target.get("GLUT1", {})
    aqp1_placeholder_rows = max(
        0,
        int(
            aqp1_apply_status_row.get(
                "placeholder_driven_rows",
                aqp1_s.get("placeholder_reference_count", aqp1_q.get("placeholder_reference_count", 0)),
            )
            or 0
        ),
    )
    glut1_placeholder_rows = max(
        0,
        int(
            glut1_apply_status_row.get(
                "placeholder_driven_rows",
                glut1_s.get("placeholder_reference_count", glut1_q.get("placeholder_reference_count", 0)),
            )
            or 0
        ),
    )

    target_rows = [
        {
            "target_id": "AQP1",
            "local_evidence_status": aqp1_s.get("endpoint_status", ""),
            "evidence_mode": aqp1_x.get("endpoint_status", "external_seed_ready_direct_binding_absent"),
            "quantitative_binding_status": "quantitative_binding_absent_claim_safe_kcal_missing",
            "remaining_seed_unresolved_fields": "replacement_reference_binding_kcal_mol",
            "exact_human_activity_count": aqp1_quantitative_s.get("exact_human_aqp1_activity_count", 0),
            "quantitative_provenance_primary_focus_ligand": aqp1_quantitative_s.get("primary_focus_ligand", ""),
            "quantitative_provenance_signal": aqp1_quantitative_s.get("signal", ""),
            "placeholder_rows": aqp1_placeholder_rows,
            "binder_defer_rows": aqp1_s.get("manual_defer_binder_count", aqp1_q.get("defer_binder_count", "")),
            "negative_review_only_rows": aqp1_s.get("manual_review_only_negative_count", aqp1_q.get("review_only_negative_count", "")),
            "p0_todo_count": aqp1_s.get("aqp1_p0_todo_count", aqp1_p.get("todo_count", "")),
            "external_candidate_count": aqp1_x.get("candidate_count", ""),
            "external_first_wave_candidate_count": aqp1_x.get("draft_first_wave_candidate_count", ""),
            "keep_review_only_count": aqp1_v.get("keep_review_only_count", ""),
            "caution_only_count": aqp1_v.get("caution_only_count", ""),
            "defer_count": aqp1_v.get("defer_count", ""),
            "binder_pending_manual_verdict_count": aqp1_b.get("pending_manual_verdict_count", ""),
            "binder_note_template_count": binder_note_templates_s.get("aqp1_template_count", ""),
            "binder_prefill_preview_count": binder_prefill_preview_s.get("aqp1_preview_count", ""),
            "binder_draft_packet_ready": bool(aqp1_draft_s),
            "binder_draft_packet_count": aqp1_draft_s.get("row_count", ""),
            "binder_commit_packet_ready": bool(aqp1_commit_s),
            "binder_commit_packet_count": aqp1_commit_s.get("row_count", ""),
            "binder_staging_sheet_ready": bool(aqp1_staging_s),
            "binder_staging_sheet_count": aqp1_staging_s.get("row_count", ""),
            "binder_apply_draft_ready": bool(aqp1_apply_s),
            "binder_apply_draft_prefill_count": aqp1_apply_s.get("draft_prefill_count", ""),
            "binder_apply_draft_pending_count": aqp1_apply_s.get("pending_manual_verdict_count", ""),
            "binder_apply_draft_staged_non_authoritative_count": aqp1_apply_status_row.get(
                "staged_non_authoritative_rows",
                aqp1_apply_s.get("staged_non_authoritative_rows", 0),
            ),
            "seed_row_fill_draft_ready": bool(aqp1_seed_fill_s),
            "seed_row_fill_safe_prefill_count": aqp1_seed_fill_s.get("safe_prefill_field_count", 0),
            "seed_row_sync_preview_ready": bool(aqp1_seed_sync_s),
            "seed_row_sync_safe_staged_field_count": aqp1_seed_sync_s.get("safe_staged_field_count", 0),
            "negative_packet_ready": bool(aqp1_negative_s),
            "negative_slot_count": aqp1_negative_s.get("negative_slot_count", ""),
            "binder_packet_ready": bool(packet_by_target.get("AQP1")),
            "aqp1_negative_primary_probe_resolution_ready": bool(aqp1_primary_probe_resolution_artifact),
            "aqp1_negative_primary_probe_resolution_artifact": aqp1_primary_probe_resolution_artifact,
            "aqp1_negative_primary_probe_resolution_candidate": aqp1_primary_probe_resolution_candidate,
            "aqp1_negative_primary_probe_resolution_decision": aqp1_primary_probe_resolution_decision,
            "aqp1_negative_primary_probe_resolution_solvent_fallback_candidate": aqp1_primary_probe_resolution_solvent_fallback_candidate,
            "next_required_step": (
                "Keep AQP1 authoritative apply blocked. Review bacopaside II, AqB013, and AqB011 as draft functional candidates only, carry AqB013 as the exact-human-activity provenance lane, and leave replacement_reference_binding_kcal_mol blank because direct claim-safe quantitative binding is still absent."
                + aqp1_primary_probe_resolution_handoff
            ),
        },
        {
            "target_id": "GLUT1",
            "local_evidence_status": glut1_s.get("endpoint_status", ""),
            "second_wave_source_confirmation_ready": bool(glut1_source_confirmation_s),
            "second_wave_source_confirmation_primary_focus_ligand": glut1_source_confirmation_s.get(
                "primary_focus_ligand",
                "",
            ),
            "direct_quantitative_binding_count": glut1_source_confirmation_s.get(
                "direct_quantitative_binding_count",
                0,
            ),
            "exact_target_pair_activity_count": glut1_source_confirmation_s.get(
                "exact_target_pair_activity_count",
                0,
            ),
            "structured_pair_absent_count": glut1_source_confirmation_s.get(
                "structured_pair_absent_count",
                0,
            ),
            "exact_human_activity_count": 0,
            "quantitative_provenance_primary_focus_ligand": "",
            "quantitative_provenance_signal": "",
            "placeholder_rows": glut1_placeholder_rows,
            "binder_defer_rows": glut1_s.get("manual_defer_binder_count", glut1_p.get("defer_rows", "")),
            "negative_review_only_rows": glut1_s.get("manual_review_only_negative_count", glut1_p.get("review_only_rows", "")),
            "p0_todo_count": "",
            "external_candidate_count": glut1_x.get("candidate_count", ""),
            "external_first_wave_candidate_count": glut1_x.get("draft_second_wave_candidate_count", ""),
            "keep_review_only_count": glut1_v.get("keep_review_only_count", ""),
            "caution_only_count": glut1_v.get("caution_only_count", ""),
            "defer_count": glut1_v.get("defer_count", ""),
            "binder_pending_manual_verdict_count": glut1_b.get("pending_manual_verdict_count", ""),
            "binder_note_template_count": binder_note_templates_s.get("glut1_template_count", ""),
            "binder_prefill_preview_count": binder_prefill_preview_s.get("glut1_preview_count", ""),
            "binder_draft_packet_ready": bool(glut1_draft_s),
            "binder_draft_packet_count": glut1_draft_s.get("binder_slot_count", ""),
            "binder_commit_packet_ready": bool(glut1_commit_s),
            "binder_commit_packet_count": glut1_commit_s.get("binder_slot_count", ""),
            "binder_staging_sheet_ready": bool(glut1_staging_s),
            "binder_staging_sheet_count": glut1_staging_s.get("row_count", ""),
            "binder_apply_draft_ready": bool(glut1_apply_s),
            "binder_apply_draft_prefill_count": glut1_apply_s.get("draft_prefilled_count", ""),
            "binder_apply_draft_pending_count": glut1_apply_s.get("pending_reviewer_action_count", ""),
            "binder_apply_draft_staged_non_authoritative_count": glut1_apply_status_row.get(
                "staged_non_authoritative_rows",
                glut1_apply_s.get("staged_non_authoritative_rows", 0),
            ),
            "seed_row_fill_draft_ready": False,
            "seed_row_fill_safe_prefill_count": 0,
            "seed_row_sync_preview_ready": False,
            "seed_row_sync_safe_staged_field_count": 0,
            "negative_packet_ready": bool(glut1_negative_s),
            "negative_slot_count": glut1_negative_s.get("negative_slot_count", ""),
            "binder_packet_ready": bool(packet_by_target.get("GLUT1")),
            "next_required_step": (
                glut1_source_confirmation_s.get("next_required_step")
                or glut1_x.get("next_required_step", glut1_s.get("next_required_step", glut1_p.get("next_required_step", "")))
            ),
        },
    ]

    binder_pending_manual_verdict_count = binder_progress_s.get("pending_manual_verdict_count", 0)
    summary = {
        "target_count": len(target_rows),
        "family_decision_status": donor_s.get("decision_status", ""),
        "scaffold_fit_donor_target": donor_s.get("scaffold_fit_donor_target", ""),
        "current_phase": (
            "manual_verdict_burndown"
            if int(binder_pending_manual_verdict_count or 0) > 0
            else "blocker_closure_seed_row_promotion"
        ),
        "transporter_p0_open_count": readiness_s.get("p0_open_count", ""),
        "aqp1_external_candidate_count": aqp1_x.get("candidate_count", 0),
        "aqp1_external_first_wave_candidate_count": aqp1_x.get("draft_first_wave_candidate_count", 0),
        "aqp1_direct_quantitative_binding_candidate_count": aqp1_x.get("direct_quantitative_binding_candidate_count", 0),
        "aqp1_quantitative_binding_status": "quantitative_binding_absent_claim_safe_kcal_missing",
        "aqp1_remaining_seed_unresolved_fields": "replacement_reference_binding_kcal_mol",
        "aqp1_exact_human_activity_count": aqp1_quantitative_s.get("exact_human_aqp1_activity_count", 0),
        "aqp1_quantitative_provenance_row_count": aqp1_quantitative_s.get("row_count", 0),
        "aqp1_quantitative_provenance_primary_focus_ligand": aqp1_quantitative_s.get("primary_focus_ligand", ""),
        "aqp1_quantitative_provenance_signal": aqp1_quantitative_s.get("signal", ""),
        "aqp1_keep_review_only_count": aqp1_v.get("keep_review_only_count", 0),
        "aqp1_caution_only_count": aqp1_v.get("caution_only_count", 0),
        "aqp1_defer_count": aqp1_v.get("defer_count", 0),
        "glut1_external_candidate_count": glut1_x.get("candidate_count", 0),
        "glut1_external_second_wave_candidate_count": glut1_x.get("draft_second_wave_candidate_count", 0),
        "glut1_second_wave_source_confirmation_ready": bool(glut1_source_confirmation_s),
        "glut1_second_wave_source_confirmation_packet_artifact": (
            "runs/glut1_second_wave_source_confirmation_packet_current.md"
            if glut1_source_confirmation_s
            else ""
        ),
        "glut1_second_wave_source_confirmation_row_count": glut1_source_confirmation_s.get("row_count", 0),
        "glut1_second_wave_source_confirmation_primary_focus_ligand": glut1_source_confirmation_s.get(
            "primary_focus_ligand",
            "",
        ),
        "glut1_direct_quantitative_binding_count": glut1_source_confirmation_s.get(
            "direct_quantitative_binding_count",
            0,
        ),
        "glut1_exact_target_pair_activity_count": glut1_source_confirmation_s.get(
            "exact_target_pair_activity_count",
            0,
        ),
        "glut1_structured_pair_absent_count": glut1_source_confirmation_s.get(
            "structured_pair_absent_count",
            0,
        ),
        "glut1_keep_review_only_count": glut1_v.get("keep_review_only_count", 0),
        "glut1_caution_only_count": glut1_v.get("caution_only_count", 0),
        "glut1_defer_count": glut1_v.get("defer_count", 0),
        "binder_seed_row_count": binder_packets_s.get(
            "total_binder_slots",
            aqp1_draft_s.get("row_count", 0) + glut1_draft_s.get("binder_slot_count", 0),
        ),
        "binder_pending_manual_verdict_count": binder_pending_manual_verdict_count,
        "binder_completed_manual_verdict_count": binder_progress_s.get("completed_manual_verdict_count", 0),
        "binder_rubric_ready": bool(binder_rubric_s),
        "binder_note_template_ready": bool(binder_note_templates_s),
        "binder_note_template_count": binder_note_templates_s.get("template_row_count", 0),
        "binder_prefill_preview_ready": bool(binder_prefill_preview_s),
        "binder_prefill_preview_count": binder_prefill_preview_s.get("preview_row_count", 0),
        "binder_draft_packets_ready": bool(aqp1_draft_s or glut1_draft_s),
        "binder_draft_packet_target_count": sum(1 for draft in (aqp1_draft_s, glut1_draft_s) if draft),
        "binder_draft_packet_row_count": aqp1_draft_s.get("row_count", 0) + glut1_draft_s.get("binder_slot_count", 0),
        "binder_commit_packets_ready": bool(aqp1_commit_s or glut1_commit_s),
        "binder_commit_packet_target_count": sum(1 for packet in (aqp1_commit_s, glut1_commit_s) if packet),
        "binder_commit_packet_row_count": aqp1_commit_s.get("row_count", 0) + glut1_commit_s.get("binder_slot_count", 0),
        "binder_confirmation_cards_ready": bool(aqp1_confirmation_s or glut1_confirmation_s),
        "binder_confirmation_card_target_count": sum(1 for card in (aqp1_confirmation_s, glut1_confirmation_s) if card),
        "binder_confirmation_card_row_count": aqp1_confirmation_s.get("row_count", 0) + glut1_confirmation_s.get("row_count", 0),
        "binder_staging_sheets_ready": bool(aqp1_staging_s or glut1_staging_s),
        "binder_staging_sheet_target_count": sum(1 for sheet in (aqp1_staging_s, glut1_staging_s) if sheet),
        "binder_staging_sheet_row_count": aqp1_staging_s.get("row_count", 0) + glut1_staging_s.get("row_count", 0),
        "binder_apply_drafts_ready": bool(aqp1_apply_s or glut1_apply_s),
        "binder_apply_draft_target_count": sum(1 for draft in (aqp1_apply_s, glut1_apply_s) if draft),
        "binder_apply_draft_prefill_count": aqp1_apply_s.get("draft_prefill_count", 0) + glut1_apply_s.get("draft_prefilled_count", 0),
        "binder_apply_draft_pending_count": aqp1_apply_s.get("pending_manual_verdict_count", 0) + glut1_apply_s.get("pending_reviewer_action_count", 0),
        "binder_apply_draft_staged_non_authoritative_count": transporter_apply_status_s.get(
            "staged_non_authoritative_rows",
            aqp1_apply_s.get("staged_non_authoritative_rows", 0) + glut1_apply_s.get("staged_non_authoritative_rows", 0),
        ),
        "seed_row_fill_drafts_ready": bool(aqp1_seed_fill_s),
        "seed_row_fill_draft_target_count": 1 if aqp1_seed_fill_s else 0,
        "aqp1_seed_row_fill_safe_prefill_count": aqp1_seed_fill_s.get("safe_prefill_field_count", 0),
        "seed_row_sync_preview_ready": bool(aqp1_seed_sync_s),
        "seed_row_sync_preview_target_count": 1 if aqp1_seed_sync_s else 0,
        "aqp1_seed_row_sync_safe_staged_field_count": aqp1_seed_sync_s.get("safe_staged_field_count", 0),
        "negative_packets_ready": bool(aqp1_negative_s or glut1_negative_s),
        "negative_packet_target_count": sum(1 for pkt in (aqp1_negative_s, glut1_negative_s) if pkt),
        "negative_slot_count_total": aqp1_negative_s.get("negative_slot_count", 0) + glut1_negative_s.get("negative_slot_count", 0),
        "binder_packets_ready": bool(binder_packets_s),
        "binder_packet_target_count": binder_packets_s.get("target_count", 0),
        "binder_confirmation_console_ready": bool(binder_confirmation_console_s),
        "binder_confirmation_target_count": binder_confirmation_console_s.get("target_count", 0),
        "binder_confirmation_row_count": binder_confirmation_console_s.get("row_count", 0),
        "operator_console_ready": bool(operator_console_s),
        "operator_console_target_count": operator_console_s.get("target_count", 0),
        "launchboard_ready": bool(launchboard_s),
        "launchboard_today_open_now": launchboard_s.get("today_open_now", ""),
        "reviewer_day_plan_ready": bool(reviewer_day_plan_s),
        "reviewer_day2_console_ready": bool(reviewer_day2_console_s),
        "reviewer_day2_stage_count": reviewer_day2_console_s.get("stage_count", 0),
        "negative_reviewer_day_plan_ready": bool(negative_reviewer_day_plan_s),
        "negative_review_row_count": negative_reviewer_day_plan_s.get("negative_slot_review_row_count", negative_reviewer_day_plan_s.get("negative_review_row_count", 0)),
        "negative_caution_reference_count": negative_reviewer_day_plan_s.get("caution_reference_row_count", negative_reviewer_day_plan_s.get("caution_reference_count", 0)),
        "aqp1_negative_primary_probe_resolution_ready": bool(aqp1_primary_probe_resolution_artifact),
        "aqp1_negative_primary_probe_resolution_artifact": aqp1_primary_probe_resolution_artifact,
        "aqp1_negative_primary_probe_resolution_candidate": aqp1_primary_probe_resolution_candidate,
        "aqp1_negative_primary_probe_resolution_decision": aqp1_primary_probe_resolution_decision,
        "aqp1_negative_primary_probe_resolution_solvent_fallback_candidate": aqp1_primary_probe_resolution_solvent_fallback_candidate,
        "targets_local_evidence_blocked": sum(1 for row in target_rows if row["local_evidence_status"] == "draft_only_local_evidence_blocked"),
        "targets_with_placeholder_rows": sum(1 for row in target_rows if row["placeholder_rows"]),
        "placeholder_row_count_total": transporter_apply_status_s.get(
            "placeholder_driven_rows",
            sum(int(row["placeholder_rows"] or 0) for row in target_rows),
        ),
        "next_required_step": (
            "Keep transporter family in draft/manual-review mode. Finish AQP1 first, keep GLUT1 staged behind it, use AQP1 external seeds only as manual-review inputs, and do not revisit family-level donor policy until at least one transporter ligand packet is no longer placeholder-driven."
            if int(binder_pending_manual_verdict_count or 0) > 0
            else (
                "Manual-verdict closure is complete. Keep transporter non-authoritative, use AQP1 first for blocker closure and seed-row promotion, keep GLUT1 second-wave, and do not revisit donor policy until placeholder-driven packet rows and donor-policy blockers are reduced. "
                "AQP1 binder evidence is currently functional potency only, carry AqB013 as the exact-human-activity provenance lane, and keep replacement_reference_binding_kcal_mol blank until claim-safe quantitative binding is curated."
                + aqp1_primary_probe_resolution_handoff
                + (
                    f" When GLUT1 opens, keep cytochalasin B as the second-wave source-confirmation lead via runs/glut1_second_wave_source_confirmation_packet_current.md; "
                    "WZB117 stays an exact-target-pair functional row and STF-31 stays review-only with structured-pair caveats."
                    if glut1_source_confirmation_s
                    else ""
                )
            )
        ),
    }
    return {"summary": summary, "target_rows": target_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Transporter Manual Review Dashboard",
        "",
        f"- target_count: `{s['target_count']}`",
        f"- family_decision_status: `{s['family_decision_status']}`",
        f"- scaffold_fit_donor_target: `{s['scaffold_fit_donor_target']}`",
        f"- current_phase: `{s['current_phase']}`",
        f"- transporter_p0_open_count: `{s['transporter_p0_open_count']}`",
        f"- aqp1_external_candidate_count: `{s['aqp1_external_candidate_count']}`",
        f"- aqp1_external_first_wave_candidate_count: `{s['aqp1_external_first_wave_candidate_count']}`",
        f"- aqp1_direct_quantitative_binding_candidate_count: `{s['aqp1_direct_quantitative_binding_candidate_count']}`",
        f"- aqp1_quantitative_binding_status: `{s['aqp1_quantitative_binding_status']}`",
        f"- aqp1_remaining_seed_unresolved_fields: `{s['aqp1_remaining_seed_unresolved_fields']}`",
        f"- aqp1_exact_human_activity_count: `{s['aqp1_exact_human_activity_count']}`",
        f"- aqp1_quantitative_provenance_row_count: `{s['aqp1_quantitative_provenance_row_count']}`",
        f"- aqp1_quantitative_provenance_primary_focus_ligand: `{s['aqp1_quantitative_provenance_primary_focus_ligand']}`",
        f"- aqp1_quantitative_provenance_signal: `{s['aqp1_quantitative_provenance_signal']}`",
        f"- aqp1_keep_review_only_count: `{s['aqp1_keep_review_only_count']}`",
        f"- aqp1_caution_only_count: `{s['aqp1_caution_only_count']}`",
        f"- aqp1_defer_count: `{s['aqp1_defer_count']}`",
        f"- glut1_external_candidate_count: `{s['glut1_external_candidate_count']}`",
        f"- glut1_external_second_wave_candidate_count: `{s['glut1_external_second_wave_candidate_count']}`",
        f"- glut1_second_wave_source_confirmation_ready: `{s['glut1_second_wave_source_confirmation_ready']}`",
        f"- glut1_second_wave_source_confirmation_packet_artifact: `{s['glut1_second_wave_source_confirmation_packet_artifact']}`",
        f"- glut1_second_wave_source_confirmation_row_count: `{s['glut1_second_wave_source_confirmation_row_count']}`",
        f"- glut1_second_wave_source_confirmation_primary_focus_ligand: `{s['glut1_second_wave_source_confirmation_primary_focus_ligand']}`",
        f"- glut1_direct_quantitative_binding_count: `{s['glut1_direct_quantitative_binding_count']}`",
        f"- glut1_exact_target_pair_activity_count: `{s['glut1_exact_target_pair_activity_count']}`",
        f"- glut1_structured_pair_absent_count: `{s['glut1_structured_pair_absent_count']}`",
        f"- glut1_keep_review_only_count: `{s['glut1_keep_review_only_count']}`",
        f"- glut1_caution_only_count: `{s['glut1_caution_only_count']}`",
        f"- glut1_defer_count: `{s['glut1_defer_count']}`",
        f"- binder_seed_row_count: `{s['binder_seed_row_count']}`",
        f"- binder_pending_manual_verdict_count: `{s['binder_pending_manual_verdict_count']}`",
        f"- binder_completed_manual_verdict_count: `{s['binder_completed_manual_verdict_count']}`",
        f"- binder_rubric_ready: `{s['binder_rubric_ready']}`",
        f"- binder_note_template_ready: `{s['binder_note_template_ready']}`",
        f"- binder_note_template_count: `{s['binder_note_template_count']}`",
        f"- binder_prefill_preview_ready: `{s['binder_prefill_preview_ready']}`",
        f"- binder_prefill_preview_count: `{s['binder_prefill_preview_count']}`",
        f"- binder_draft_packets_ready: `{s['binder_draft_packets_ready']}`",
        f"- binder_draft_packet_target_count: `{s['binder_draft_packet_target_count']}`",
        f"- binder_draft_packet_row_count: `{s['binder_draft_packet_row_count']}`",
        f"- binder_commit_packets_ready: `{s['binder_commit_packets_ready']}`",
        f"- binder_commit_packet_target_count: `{s['binder_commit_packet_target_count']}`",
        f"- binder_commit_packet_row_count: `{s['binder_commit_packet_row_count']}`",
        f"- binder_confirmation_cards_ready: `{s['binder_confirmation_cards_ready']}`",
        f"- binder_confirmation_card_target_count: `{s['binder_confirmation_card_target_count']}`",
        f"- binder_confirmation_card_row_count: `{s['binder_confirmation_card_row_count']}`",
        f"- binder_staging_sheets_ready: `{s['binder_staging_sheets_ready']}`",
        f"- binder_staging_sheet_target_count: `{s['binder_staging_sheet_target_count']}`",
        f"- binder_staging_sheet_row_count: `{s['binder_staging_sheet_row_count']}`",
        f"- binder_apply_drafts_ready: `{s['binder_apply_drafts_ready']}`",
        f"- binder_apply_draft_target_count: `{s['binder_apply_draft_target_count']}`",
        f"- binder_apply_draft_prefill_count: `{s['binder_apply_draft_prefill_count']}`",
        f"- binder_apply_draft_pending_count: `{s['binder_apply_draft_pending_count']}`",
        f"- binder_apply_draft_staged_non_authoritative_count: `{s['binder_apply_draft_staged_non_authoritative_count']}`",
        f"- seed_row_fill_drafts_ready: `{s['seed_row_fill_drafts_ready']}`",
        f"- seed_row_fill_draft_target_count: `{s['seed_row_fill_draft_target_count']}`",
        f"- aqp1_seed_row_fill_safe_prefill_count: `{s['aqp1_seed_row_fill_safe_prefill_count']}`",
        f"- seed_row_sync_preview_ready: `{s['seed_row_sync_preview_ready']}`",
        f"- seed_row_sync_preview_target_count: `{s['seed_row_sync_preview_target_count']}`",
        f"- aqp1_seed_row_sync_safe_staged_field_count: `{s['aqp1_seed_row_sync_safe_staged_field_count']}`",
        f"- negative_packets_ready: `{s['negative_packets_ready']}`",
        f"- negative_packet_target_count: `{s['negative_packet_target_count']}`",
        f"- negative_slot_count_total: `{s['negative_slot_count_total']}`",
        f"- binder_packets_ready: `{s['binder_packets_ready']}`",
        f"- binder_packet_target_count: `{s['binder_packet_target_count']}`",
        f"- binder_confirmation_console_ready: `{s['binder_confirmation_console_ready']}`",
        f"- binder_confirmation_target_count: `{s['binder_confirmation_target_count']}`",
        f"- binder_confirmation_row_count: `{s['binder_confirmation_row_count']}`",
        f"- operator_console_ready: `{s['operator_console_ready']}`",
        f"- operator_console_target_count: `{s['operator_console_target_count']}`",
        f"- launchboard_ready: `{s['launchboard_ready']}`",
        f"- launchboard_today_open_now: `{s['launchboard_today_open_now']}`",
        f"- reviewer_day_plan_ready: `{s['reviewer_day_plan_ready']}`",
        f"- reviewer_day2_console_ready: `{s['reviewer_day2_console_ready']}`",
        f"- reviewer_day2_stage_count: `{s['reviewer_day2_stage_count']}`",
        f"- negative_reviewer_day_plan_ready: `{s['negative_reviewer_day_plan_ready']}`",
        f"- negative_review_row_count: `{s['negative_review_row_count']}`",
        f"- negative_caution_reference_count: `{s['negative_caution_reference_count']}`",
        f"- aqp1_negative_primary_probe_resolution_ready: `{s['aqp1_negative_primary_probe_resolution_ready']}`",
        f"- aqp1_negative_primary_probe_resolution_artifact: `{s['aqp1_negative_primary_probe_resolution_artifact']}`",
        f"- aqp1_negative_primary_probe_resolution_candidate: `{s['aqp1_negative_primary_probe_resolution_candidate']}`",
        f"- aqp1_negative_primary_probe_resolution_decision: `{s['aqp1_negative_primary_probe_resolution_decision']}`",
        f"- aqp1_negative_primary_probe_resolution_solvent_fallback_candidate: `{s['aqp1_negative_primary_probe_resolution_solvent_fallback_candidate']}`",
        f"- targets_local_evidence_blocked: `{s['targets_local_evidence_blocked']}`",
        f"- targets_with_placeholder_rows: `{s['targets_with_placeholder_rows']}`",
        f"- placeholder_row_count_total: `{s['placeholder_row_count_total']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Targets",
        "",
        "| target_id | local_evidence_status | evidence_mode | quantitative_binding_status | remaining_seed_unresolved_fields | exact_human_activity_count | quantitative_provenance_primary_focus_ligand | quantitative_provenance_signal | placeholder_rows | binder_defer_rows | negative_review_only_rows | external_candidate_count | keep_review_only_count | caution_only_count | defer_count | binder_pending_manual_verdict_count | binder_note_template_count | binder_prefill_preview_count | binder_draft_packet_ready | binder_draft_packet_count | binder_commit_packet_ready | binder_commit_packet_count | binder_staging_sheet_ready | binder_staging_sheet_count | binder_apply_draft_ready | binder_apply_draft_prefill_count | binder_apply_draft_staged_non_authoritative_count | seed_row_fill_draft_ready | seed_row_fill_safe_prefill_count | seed_row_sync_preview_ready | seed_row_sync_safe_staged_field_count | negative_packet_ready | negative_slot_count | binder_packet_ready | p0_todo_count | next_required_step |",
        "| --- | --- | --- | --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- | ---: | --- | ---: | --- | ---: | ---: | --- | ---: | --- | ---: | --- | ---: | --- | ---: | --- |",
    ]
    for row in payload["target_rows"]:
        lines.append(
            f"| {row['target_id']} | `{row['local_evidence_status']}` | `{row.get('evidence_mode', '')}` | `{row.get('quantitative_binding_status', '')}` | `{row.get('remaining_seed_unresolved_fields', '')}` | {row.get('exact_human_activity_count', 0)} | `{row.get('quantitative_provenance_primary_focus_ligand', '')}` | `{row.get('quantitative_provenance_signal', '')}` | {row['placeholder_rows']} | {row['binder_defer_rows']} | {row['negative_review_only_rows']} | {row['external_candidate_count']} | {row['keep_review_only_count']} | {row['caution_only_count']} | {row['defer_count']} | {row['binder_pending_manual_verdict_count']} | {row['binder_note_template_count']} | {row['binder_prefill_preview_count']} | `{row['binder_draft_packet_ready']}` | {row['binder_draft_packet_count']} | `{row['binder_commit_packet_ready']}` | {row['binder_commit_packet_count']} | `{row['binder_staging_sheet_ready']}` | {row['binder_staging_sheet_count']} | `{row['binder_apply_draft_ready']}` | {row['binder_apply_draft_prefill_count']} | {row['binder_apply_draft_staged_non_authoritative_count']} | `{row['seed_row_fill_draft_ready']}` | {row['seed_row_fill_safe_prefill_count']} | `{row['seed_row_sync_preview_ready']}` | {row['seed_row_sync_safe_staged_field_count']} | `{row['negative_packet_ready']}` | {row['negative_slot_count']} | `{row['binder_packet_ready']}` | {row['p0_todo_count']} | {row['next_required_step']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a transporter manual-review dashboard across AQP1 and GLUT1 draft scaffolds.")
    parser.add_argument("--aqp1-note-json", default=DEFAULT_AQP1_NOTE_JSON)
    parser.add_argument("--aqp1-queue-json", default=DEFAULT_AQP1_QUEUE_JSON)
    parser.add_argument("--aqp1-plan-json", default=DEFAULT_AQP1_PLAN_JSON)
    parser.add_argument("--aqp1-external-seed-json", default=DEFAULT_AQP1_EXTERNAL_SEED_JSON)
    parser.add_argument("--aqp1-verdict-json", default=DEFAULT_AQP1_VERDICT_JSON)
    parser.add_argument("--glut1-note-json", default=DEFAULT_GLUT1_NOTE_JSON)
    parser.add_argument("--glut1-queue-json", default=DEFAULT_GLUT1_QUEUE_JSON)
    parser.add_argument("--glut1-pending-json", default=DEFAULT_GLUT1_PENDING_JSON)
    parser.add_argument("--glut1-external-seed-json", default=DEFAULT_GLUT1_EXTERNAL_SEED_JSON)
    parser.add_argument("--glut1-verdict-json", default=DEFAULT_GLUT1_VERDICT_JSON)
    parser.add_argument("--aqp1-binder-sheet-json", default=DEFAULT_AQP1_BINDER_SHEET_JSON)
    parser.add_argument("--glut1-binder-sheet-json", default=DEFAULT_GLUT1_BINDER_SHEET_JSON)
    parser.add_argument("--aqp1-draft-packet-json", default=DEFAULT_AQP1_DRAFT_PACKET_JSON)
    parser.add_argument("--glut1-draft-packet-json", default=DEFAULT_GLUT1_DRAFT_PACKET_JSON)
    parser.add_argument("--aqp1-commit-packet-json", default=DEFAULT_AQP1_COMMIT_PACKET_JSON)
    parser.add_argument("--glut1-commit-packet-json", default=DEFAULT_GLUT1_COMMIT_PACKET_JSON)
    parser.add_argument("--aqp1-confirmation-card-json", default=DEFAULT_AQP1_CONFIRMATION_CARD_JSON)
    parser.add_argument("--glut1-confirmation-card-json", default=DEFAULT_GLUT1_CONFIRMATION_CARD_JSON)
    parser.add_argument("--aqp1-staging-sheet-json", default=DEFAULT_AQP1_STAGING_SHEET_JSON)
    parser.add_argument("--glut1-staging-sheet-json", default=DEFAULT_GLUT1_STAGING_SHEET_JSON)
    parser.add_argument("--aqp1-apply-draft-json", default=DEFAULT_AQP1_APPLY_DRAFT_JSON)
    parser.add_argument("--glut1-apply-draft-json", default=DEFAULT_GLUT1_APPLY_DRAFT_JSON)
    parser.add_argument("--aqp1-seed-row-fill-draft-json", default=DEFAULT_AQP1_SEED_ROW_FILL_DRAFT_JSON)
    parser.add_argument("--aqp1-quantitative-provenance-json", default=DEFAULT_AQP1_QUANTITATIVE_PROVENANCE_JSON)
    parser.add_argument("--glut1-source-confirmation-json", default=DEFAULT_GLUT1_SOURCE_CONFIRMATION_JSON)
    parser.add_argument("--aqp1-negative-packet-json", default=DEFAULT_AQP1_NEGATIVE_PACKET_JSON)
    parser.add_argument("--glut1-negative-packet-json", default=DEFAULT_GLUT1_NEGATIVE_PACKET_JSON)
    parser.add_argument("--binder-progress-json", default=DEFAULT_BINDER_PROGRESS_JSON)
    parser.add_argument("--binder-rubric-json", default=DEFAULT_BINDER_RUBRIC_JSON)
    parser.add_argument("--binder-note-templates-json", default=DEFAULT_BINDER_NOTE_TEMPLATES_JSON)
    parser.add_argument("--binder-prefill-preview-json", default=DEFAULT_BINDER_PREFILL_PREVIEW_JSON)
    parser.add_argument("--binder-packets-json", default=DEFAULT_BINDER_PACKETS_JSON)
    parser.add_argument("--binder-confirmation-console-json", default=DEFAULT_BINDER_CONFIRMATION_CONSOLE_JSON)
    parser.add_argument("--operator-console-json", default=DEFAULT_OPERATOR_CONSOLE_JSON)
    parser.add_argument("--launchboard-json", default=DEFAULT_LAUNCHBOARD_JSON)
    parser.add_argument("--transporter-apply-status-json", default=DEFAULT_TRANSPORTER_APPLY_STATUS_JSON)
    parser.add_argument("--reviewer-day-plan-json", default=DEFAULT_REVIEWER_DAY_PLAN_JSON)
    parser.add_argument("--reviewer-day2-console-json", default=DEFAULT_REVIEWER_DAY2_CONSOLE_JSON)
    parser.add_argument("--negative-reviewer-day-plan-json", default=DEFAULT_NEGATIVE_REVIEWER_DAY_PLAN_JSON)
    parser.add_argument("--negative-target-packets-json", default=DEFAULT_NEGATIVE_TARGET_PACKETS_JSON)
    parser.add_argument("--donor-policy-json", default=DEFAULT_DONOR_POLICY_JSON)
    parser.add_argument("--readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--aqp1-seed-row-sync-preview-json", default=DEFAULT_AQP1_SEED_ROW_SYNC_PREVIEW_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.aqp1_note_json),
        _load_json(args.aqp1_queue_json),
        _load_json(args.aqp1_plan_json),
        _load_json(args.aqp1_external_seed_json),
        _load_json(args.aqp1_verdict_json),
        _load_json(args.glut1_note_json),
        _load_json(args.glut1_queue_json),
        _load_json(args.glut1_pending_json),
        _load_json(args.glut1_external_seed_json),
        _load_json(args.glut1_verdict_json),
        _load_json(args.aqp1_binder_sheet_json),
        _load_json(args.glut1_binder_sheet_json),
        _load_json(args.aqp1_draft_packet_json),
        _load_json(args.glut1_draft_packet_json),
        _load_json(args.aqp1_commit_packet_json),
        _load_json(args.glut1_commit_packet_json),
        _load_json(args.aqp1_confirmation_card_json),
        _load_json(args.glut1_confirmation_card_json),
        _load_json(args.aqp1_staging_sheet_json),
        _load_json(args.glut1_staging_sheet_json),
        _load_json(args.aqp1_apply_draft_json),
        _load_json(args.glut1_apply_draft_json),
        _load_json(args.aqp1_quantitative_provenance_json),
        _load_json(args.aqp1_negative_packet_json),
        _load_json(args.glut1_negative_packet_json),
        _load_json(args.binder_progress_json),
        _load_json(args.binder_rubric_json),
        _load_json(args.binder_note_templates_json),
        _load_json(args.binder_prefill_preview_json),
        _load_json(args.binder_packets_json),
        _load_json(args.binder_confirmation_console_json),
        _load_json(args.operator_console_json),
        _load_json(args.launchboard_json),
        _load_json(args.transporter_apply_status_json),
        _load_json(args.reviewer_day_plan_json),
        _load_json(args.reviewer_day2_console_json),
        _load_json(args.negative_reviewer_day_plan_json),
        _load_json(args.donor_policy_json),
        _load_json(args.readiness_json),
        _load_json(args.aqp1_seed_row_fill_draft_json),
        _load_json(args.aqp1_seed_row_sync_preview_json),
        _load_json(args.glut1_source_confirmation_json),
        _maybe_load_json(args.negative_target_packets_json),
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
