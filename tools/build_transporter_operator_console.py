#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path


RUNS = Path("runs")

REVIEWER_DAY_PLAN_JSON = RUNS / "transporter_reviewer_day_plan_current.json"
APPLY_DRAFT_STATUS_JSON = RUNS / "transporter_apply_draft_status_current.json"
MANUAL_REVIEW_DASHBOARD_JSON = RUNS / "transporter_manual_review_dashboard_current.json"
AQP1_MANUAL_VERDICT_HANDOFF_JSON = RUNS / "aqp1_manual_verdict_handoff_packet_current.json"
GLUT1_MANUAL_VERDICT_HANDOFF_JSON = RUNS / "glut1_manual_verdict_handoff_packet_current.json"
GLUT1_SOURCE_CONFIRMATION_JSON = RUNS / "glut1_second_wave_source_confirmation_packet_current.json"
AQP1_FIRST_SEED_ROW_PACKET_JSON = RUNS / "aqp1_first_seed_row_packet_current.json"
AQP1_SEED_ROW_EXECUTION_PACKET_JSON = RUNS / "transporter_seed_row_execution_packet_current.json"
AQP1_SEED_ROW_FILL_DRAFT_JSON = RUNS / "aqp1_seed_row_fill_draft_current.json"
AQP1_SEED_ROW_SYNC_PREVIEW_JSON = RUNS / "aqp1_seed_row_sync_apply_preview_current.json"
AQP1_QUANTITATIVE_PROVENANCE_JSON = RUNS / "aqp1_quantitative_provenance_packet_current.json"
AQP1_SOURCE_CONFIRMATION_JSON = RUNS / "aqp1_first_wave_source_confirmation_packet_current.json"
AQP1_FOLLOW_ON_PACKET_JSON = RUNS / "aqp1_first_wave_follow_on_packet_current.json"
AQP1_FOLLOW_ON_BLOCKER_DECOMPOSITION_JSON = RUNS / "aqp1_follow_on_blocker_decomposition_current.json"
TRANSPORTER_NEGATIVE_TARGET_PACKETS_JSON = RUNS / "transporter_negative_evidence_target_packets_current.json"

OUT_JSON = RUNS / "transporter_operator_console_current.json"
OUT_CSV = RUNS / "transporter_operator_console_current.csv"
OUT_MD = RUNS / "transporter_operator_console_current.md"


def load_json(path: Path) -> dict:
    with path.open() as fh:
        return json.load(fh)


def maybe_load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open() as fh:
        return json.load(fh)


def _follow_on_blocker_decomposition_artifact(summary: dict) -> str:
    return str(
        summary.get("aqp1_follow_on_blocker_decomposition_artifact")
        or summary.get("follow_on_blocker_decomposition_artifact")
        or summary.get("blocker_decomposition_artifact")
        or summary.get("artifact_path")
        or summary.get("primary_artifact")
        or summary.get("packet_artifact")
        or ("runs/aqp1_follow_on_blocker_decomposition_current.md" if summary else "")
    ).strip()


def _aqp1_primary_probe_resolution_fields(payload: dict | None) -> dict[str, str | bool]:
    summary = dict((payload or {}).get("summary", {}) or {})
    artifact = str(summary.get("aqp1_negative_primary_probe_resolution_artifact", "") or "").strip()
    return {
        "ready": bool(artifact),
        "artifact": artifact,
        "candidate": str(summary.get("aqp1_negative_primary_probe_resolution_candidate", "") or "").strip(),
        "decision": str(summary.get("aqp1_negative_primary_probe_resolution_decision", "") or "").strip(),
        "solvent_fallback_candidate": str(
            summary.get("aqp1_negative_primary_probe_resolution_solvent_fallback_candidate", "") or ""
        ).strip(),
    }


def build_target_rows(
    aqp1_handoff: dict,
    glut1_handoff: dict,
    aqp1_first_seed_row_packet: dict,
    aqp1_seed_row_execution_packet: dict,
    aqp1_seed_row_fill_draft: dict,
    aqp1_seed_row_sync_preview: dict,
    aqp1_quantitative_provenance: dict,
    aqp1_source_confirmation: dict,
    aqp1_follow_on_packet: dict,
    aqp1_follow_on_blocker_decomposition: dict,
    glut1_source_confirmation: dict,
    negative_target_packets: dict | None = None,
) -> list[dict]:
    aqp1_summary = dict(aqp1_handoff.get("summary", {}) or {})
    glut1_summary = dict(glut1_handoff.get("summary", {}) or {})
    aqp1_seed_summary = dict(aqp1_first_seed_row_packet.get("summary", {}) or {})
    aqp1_seed_execution_summary = dict(aqp1_seed_row_execution_packet.get("summary", {}) or {})
    aqp1_seed_fill_summary = dict(aqp1_seed_row_fill_draft.get("summary", {}) or {})
    aqp1_seed_sync_summary = dict(aqp1_seed_row_sync_preview.get("summary", {}) or {})
    aqp1_quantitative_summary = dict(aqp1_quantitative_provenance.get("summary", {}) or {})
    aqp1_source_confirmation_summary = dict(aqp1_source_confirmation.get("summary", {}) or {})
    aqp1_follow_on_summary = dict(aqp1_follow_on_packet.get("summary", {}) or {})
    aqp1_follow_on_blocker_decomposition_summary = dict(
        aqp1_follow_on_blocker_decomposition.get("summary", {}) or {}
    )
    glut1_source_confirmation_summary = dict(glut1_source_confirmation.get("summary", {}) or {})
    aqp1_primary_probe_resolution = _aqp1_primary_probe_resolution_fields(negative_target_packets)
    aqp1_follow_on_blocker_decomposition_artifact = _follow_on_blocker_decomposition_artifact(
        aqp1_follow_on_blocker_decomposition_summary
    )
    aqp1_follow_on_blocker_decomposition_clause = (
        f", with `{aqp1_follow_on_blocker_decomposition_artifact}` open as the AQP1 follow-on blocker decomposition surface"
        if aqp1_follow_on_blocker_decomposition_artifact
        else ""
    )
    aqp1_primary_probe_resolution_clause = (
        ", and keep "
        f"`{aqp1_primary_probe_resolution['artifact']}` ready so "
        f"`{aqp1_primary_probe_resolution['candidate'] or 'sodium nitroprusside'}` stays review-only while "
        f"`{aqp1_primary_probe_resolution['solvent_fallback_candidate'] or 'dimethyl sulfoxide'}` remains solvent-only at decision "
        f"`{aqp1_primary_probe_resolution['decision'] or 'keep_review_only_no_authoritative_negative_promotion'}`"
        if aqp1_primary_probe_resolution["artifact"]
        else ""
    )
    aqp1_primary_probe_resolution_sentence = (
        f"{aqp1_primary_probe_resolution_clause}."
        if aqp1_primary_probe_resolution_clause
        else ""
    )
    use_seed_packet = int(aqp1_summary.get("pending_manual_verdict_count", 0) or 0) == 0 and bool(aqp1_seed_summary)
    use_seed_execution_packet = use_seed_packet and bool(aqp1_seed_execution_summary)
    use_seed_fill_draft = use_seed_packet and bool(aqp1_seed_fill_summary)
    use_seed_sync_preview = use_seed_fill_draft and bool(aqp1_seed_sync_summary)
    return [
        {
            "target": "aqp1",
            "wave": "first",
            "open_first": "runs/aqp1_first_seed_row_packet_current.md" if use_seed_packet else "runs/aqp1_manual_verdict_packet_current.md",
            "open_second": (
                "runs/transporter_seed_row_execution_packet_current.md"
                if use_seed_execution_packet
                else "runs/aqp1_seed_row_fill_draft_current.md"
                if use_seed_fill_draft
                else "runs/aqp1_negative_review_handoff_packet_current.md"
            ),
            "open_source_confirmation": "runs/aqp1_first_wave_source_confirmation_packet_current.md" if aqp1_source_confirmation_summary else "",
            "open_provenance": "runs/aqp1_quantitative_provenance_packet_current.md" if aqp1_quantitative_summary else "",
            "open_follow_on": "runs/aqp1_first_wave_follow_on_packet_current.md" if aqp1_follow_on_summary else "",
            "open_third": (
                "runs/aqp1_seed_row_fill_draft_current.md"
                if use_seed_execution_packet
                else
                "runs/aqp1_seed_row_sync_apply_preview_current.md"
                if use_seed_sync_preview
                else "runs/aqp1_negative_review_handoff_packet_current.md"
                if use_seed_fill_draft
                else "runs/aqp1_binder_confirmation_card_current.md"
            ),
            "open_fourth": (
                "runs/aqp1_seed_row_sync_apply_preview_current.md"
                if use_seed_execution_packet and use_seed_sync_preview
                else
                "runs/aqp1_negative_review_handoff_packet_current.md"
                if use_seed_sync_preview
                else "runs/aqp1_binder_confirmation_card_current.md"
                if use_seed_fill_draft
                else "runs/aqp1_manual_verdict_staging_sheet_current.md"
            ),
            "open_fifth": (
                "runs/aqp1_negative_review_handoff_packet_current.md"
                if use_seed_execution_packet and use_seed_sync_preview
                else "runs/aqp1_manual_verdict_staging_sheet_current.md"
                if use_seed_fill_draft
                else ""
            ),
            "candidate_count": aqp1_summary["binder_first_wave_count"],
            "pending_manual_verdict_count": aqp1_summary["pending_manual_verdict_count"],
            "review_bucket": "review_only_first_wave",
            "exact_human_activity_count": aqp1_quantitative_summary.get("exact_human_aqp1_activity_count", 0),
            "quantitative_provenance_primary_focus_ligand": aqp1_quantitative_summary.get("primary_focus_ligand", ""),
            "quantitative_provenance_signal": aqp1_quantitative_summary.get("signal", ""),
            "follow_on_row_count": aqp1_follow_on_summary.get("row_count", 0),
            "follow_on_targets": aqp1_follow_on_summary.get("follow_on_targets", ""),
            "aqp1_follow_on_blocker_decomposition_ready": bool(aqp1_follow_on_blocker_decomposition_artifact),
            "aqp1_follow_on_blocker_decomposition_artifact": aqp1_follow_on_blocker_decomposition_artifact,
            "aqp1_follow_on_blocker_decomposition_row_count": aqp1_follow_on_blocker_decomposition_summary.get(
                "blocker_row_count",
                0,
            ),
            "aqp1_follow_on_blocker_decomposition_follow_on_targets": aqp1_follow_on_blocker_decomposition_summary.get(
                "follow_on_targets",
                "",
            ),
            "aqp1_follow_on_blocker_decomposition_primary_focus_ligand": aqp1_follow_on_blocker_decomposition_summary.get(
                "primary_focus_ligand",
                "",
            ),
            "aqp1_follow_on_blocker_decomposition_exact_human_guardrail_ligand": aqp1_follow_on_blocker_decomposition_summary.get(
                "exact_human_guardrail_ligand",
                "",
            ),
            "aqp1_follow_on_blocker_decomposition_exact_human_nonbinding_count": aqp1_follow_on_blocker_decomposition_summary.get(
                "exact_human_nonbinding_count",
                0,
            ),
            "aqp1_follow_on_blocker_decomposition_exact_target_pair_absent_count": aqp1_follow_on_blocker_decomposition_summary.get(
                "exact_target_pair_absent_count",
                0,
            ),
            "aqp1_follow_on_blocker_decomposition_next_required_step": aqp1_follow_on_blocker_decomposition_summary.get(
                "next_required_step",
                "",
            ),
            "aqp1_negative_primary_probe_resolution_ready": aqp1_primary_probe_resolution["ready"],
            "aqp1_negative_primary_probe_resolution_artifact": aqp1_primary_probe_resolution["artifact"],
            "aqp1_negative_primary_probe_resolution_candidate": aqp1_primary_probe_resolution["candidate"],
            "aqp1_negative_primary_probe_resolution_decision": aqp1_primary_probe_resolution["decision"],
            "aqp1_negative_primary_probe_resolution_solvent_fallback_candidate": aqp1_primary_probe_resolution[
                "solvent_fallback_candidate"
            ],
            "operator_instruction": (
                "Start here today. Read the AQP1 first seed-row packet, use the execution packet to see the exact synchronized triple-edit contract, keep the AqB013 provenance lane visible, keep the AQP1 follow-on packet ready for core_binder_02/core_binder_03"
                f"{aqp1_follow_on_blocker_decomposition_clause}, and remember this row is functional-potency staged only with quantitative binding still absent. Then use the seed-row fill draft and sync preview before moving to negative review."
                f"{aqp1_primary_probe_resolution_sentence}"
                if use_seed_execution_packet and use_seed_sync_preview
                else
                "Start here today. Read the AQP1 first seed-row packet, keep the AqB013 provenance lane visible, keep the AQP1 follow-on packet ready for core_binder_02/core_binder_03"
                f"{aqp1_follow_on_blocker_decomposition_clause}, use the seed-row fill draft to stage only reviewer-safe fields, and keep quantitative binding absent while you confirm the exact synchronized-row draft in the sync/apply preview before moving to negative review and staging."
                f"{aqp1_primary_probe_resolution_sentence}"
                if use_seed_sync_preview
                else "Start here today. Read the AQP1 first seed-row packet, keep the AqB013 provenance lane visible, keep the AQP1 follow-on packet ready for core_binder_02/core_binder_03"
                f"{aqp1_follow_on_blocker_decomposition_clause}, then use the seed-row fill draft to stage only reviewer-safe fields before moving to negative review and staging."
                f"{aqp1_primary_probe_resolution_sentence}"
                if use_seed_fill_draft
                else "Start here today. Use the AQP1 first seed-row packet to reduce placeholder-driven rows, keep the AqB013 provenance lane visible, keep the AQP1 follow-on packet ready for core_binder_02/core_binder_03"
                f"{aqp1_follow_on_blocker_decomposition_clause}, then move to the AQP1 negative packet only after the first seed-row target is fully understood."
                f"{aqp1_primary_probe_resolution_sentence}"
                if use_seed_packet
                else "Start here today. Finish the AQP1 binder packet first, then move to the AQP1 negative packet only if the binder packet is exhausted."
            ),
        },
        {
            "target": "glut1",
            "wave": "second",
            "open_first": "runs/glut1_manual_verdict_packet_current.md",
            "open_second": "runs/glut1_negative_review_handoff_packet_current.md",
            "open_source_confirmation": (
                "runs/glut1_second_wave_source_confirmation_packet_current.md"
                if glut1_source_confirmation_summary
                else ""
            ),
            "open_provenance": "",
            "open_follow_on": "",
            "open_third": "runs/glut1_binder_confirmation_card_current.md",
            "open_fourth": "runs/glut1_manual_verdict_staging_sheet_current.md",
            "open_fifth": "",
            "candidate_count": glut1_summary["binder_slot_count"],
            "pending_manual_verdict_count": glut1_summary["binder_pending_manual_verdict_count"],
            "review_bucket": "review_only_second_wave",
            "glut1_second_wave_source_confirmation_ready": bool(glut1_source_confirmation_summary),
            "glut1_second_wave_source_confirmation_row_count": glut1_source_confirmation_summary.get("row_count", 0),
            "glut1_second_wave_source_confirmation_primary_focus_ligand": glut1_source_confirmation_summary.get(
                "primary_focus_ligand",
                "",
            ),
            "glut1_direct_quantitative_binding_count": glut1_source_confirmation_summary.get(
                "direct_quantitative_binding_count",
                0,
            ),
            "glut1_exact_target_pair_activity_count": glut1_source_confirmation_summary.get(
                "exact_target_pair_activity_count",
                0,
            ),
            "glut1_structured_pair_absent_count": glut1_source_confirmation_summary.get(
                "structured_pair_absent_count",
                0,
            ),
            "operator_instruction": (
                "Open only after AQP1 first-wave binder and negative packets are exhausted or time remains."
                + (
                    f" When widened, keep `runs/glut1_second_wave_source_confirmation_packet_current.md` open and start with "
                    f"{glut1_source_confirmation_summary.get('primary_focus_ligand', 'cytochalasin B')} as the direct quantitative GLUT1 binding lead, "
                    "then review WZB117 as the exact-target-pair functional inhibitor row and STF-31 as the review-only functional anchor."
                    if glut1_source_confirmation_summary
                    else ""
                )
            ),
        },
    ]


def build_summary(
    reviewer_day_plan: dict,
    apply_draft_status: dict,
    manual_review_dashboard: dict,
    aqp1_seed_row_execution_packet: dict,
    aqp1_seed_row_sync_preview: dict,
    aqp1_quantitative_provenance: dict,
    aqp1_follow_on_packet: dict,
    aqp1_follow_on_blocker_decomposition: dict,
    glut1_source_confirmation: dict,
    target_rows: list[dict],
) -> dict:
    aqp1_open_first = target_rows[0]["open_first"] if target_rows else "runs/aqp1_manual_verdict_packet_current.md"
    aqp1_open_source_confirmation = target_rows[0].get("open_source_confirmation", "") if target_rows else ""
    aqp1_open_provenance = target_rows[0].get("open_provenance", "") if target_rows else ""
    aqp1_open_follow_on = target_rows[0].get("open_follow_on", "") if target_rows else ""
    aqp1_follow_on_blocker_decomposition_summary = dict(
        aqp1_follow_on_blocker_decomposition.get("summary", {}) or {}
    )
    aqp1_open_follow_on_blocker_decomposition = _follow_on_blocker_decomposition_artifact(
        aqp1_follow_on_blocker_decomposition_summary
    )
    aqp1_seed_execution_summary = dict(aqp1_seed_row_execution_packet.get("summary", {}) or {})
    aqp1_seed_sync_summary = dict(aqp1_seed_row_sync_preview.get("summary", {}) or {})
    aqp1_quantitative_summary = dict(aqp1_quantitative_provenance.get("summary", {}) or {})
    aqp1_follow_on_summary = dict(aqp1_follow_on_packet.get("summary", {}) or {})
    glut1_source_confirmation_summary = dict((glut1_source_confirmation or {}).get("summary", {}) or {})
    glut1_open_source_confirmation = target_rows[1].get("open_source_confirmation", "") if len(target_rows) > 1 else ""
    aqp1_open_second = target_rows[0]["open_second"] if target_rows else ""
    aqp1_open_third = target_rows[0]["open_third"] if target_rows else ""
    aqp1_open_fourth = target_rows[0]["open_fourth"] if target_rows else ""
    aqp1_open_fifth = target_rows[0]["open_fifth"] if target_rows else ""
    aqp1_open_execution = "runs/transporter_seed_row_execution_packet_current.md" if aqp1_seed_execution_summary else ""
    aqp1_open_seed_fill = (
        aqp1_open_third if aqp1_open_second == aqp1_open_execution else aqp1_open_second
    )
    aqp1_open_sync_preview = (
        aqp1_open_fourth if aqp1_open_execution and aqp1_open_fourth == "runs/aqp1_seed_row_sync_apply_preview_current.md" else aqp1_open_third
    )
    aqp1_open_negative_review = (
        aqp1_open_fifth if aqp1_open_execution and aqp1_open_fifth == "runs/aqp1_negative_review_handoff_packet_current.md" else aqp1_open_fourth
    )
    aqp1_primary_probe_resolution_artifact = target_rows[0].get("aqp1_negative_primary_probe_resolution_artifact", "") if target_rows else ""
    aqp1_primary_probe_resolution_candidate = target_rows[0].get("aqp1_negative_primary_probe_resolution_candidate", "") if target_rows else ""
    aqp1_primary_probe_resolution_decision = target_rows[0].get("aqp1_negative_primary_probe_resolution_decision", "") if target_rows else ""
    aqp1_primary_probe_resolution_solvent_fallback_candidate = target_rows[0].get(
        "aqp1_negative_primary_probe_resolution_solvent_fallback_candidate",
        "",
    ) if target_rows else ""
    return {
        "target_count": len(target_rows),
        "aqp1_open_first": aqp1_open_first,
        "aqp1_open_second": aqp1_open_second,
        "aqp1_open_source_confirmation": aqp1_open_source_confirmation,
        "aqp1_open_provenance": aqp1_open_provenance,
        "aqp1_open_follow_on": aqp1_open_follow_on,
        "aqp1_open_follow_on_blocker_decomposition": aqp1_open_follow_on_blocker_decomposition,
        "aqp1_open_execution": aqp1_open_execution,
        "aqp1_open_seed_fill": aqp1_open_seed_fill,
        "aqp1_open_sync_preview": aqp1_open_sync_preview,
        "aqp1_open_negative_review": aqp1_open_negative_review,
        "glut1_open_first": "runs/glut1_manual_verdict_packet_current.md",
        "glut1_open_source_confirmation": glut1_open_source_confirmation,
        "aqp1_open_third": aqp1_open_third,
        "glut1_open_third": "runs/glut1_binder_confirmation_card_current.md",
        "aqp1_open_fourth": aqp1_open_fourth,
        "glut1_open_fourth": "runs/glut1_manual_verdict_staging_sheet_current.md",
        "aqp1_open_fifth": aqp1_open_fifth,
        "binder_pending_manual_verdict_count": apply_draft_status["summary"]["pending_manual_verdict_count"],
        "binder_note_template_count": apply_draft_status["summary"]["note_template_count"],
        "aqp1_ready_for_today": reviewer_day_plan["summary"]["aqp1_ready_for_today"],
        "glut1_ready_for_today": reviewer_day_plan["summary"]["glut1_ready_for_today"],
        "transporter_family_state": manual_review_dashboard["summary"]["family_decision_status"],
        "current_phase": manual_review_dashboard["summary"].get("current_phase", ""),
        "aqp1_seed_fill_ready": (
            aqp1_open_seed_fill == "runs/aqp1_seed_row_fill_draft_current.md"
        ),
        "aqp1_seed_fill_safe_prefill_count": manual_review_dashboard["summary"].get("aqp1_seed_row_fill_safe_prefill_count", 0),
        "aqp1_execution_packet_ready": bool(aqp1_seed_execution_summary),
        "aqp1_sync_preview_ready": (
            aqp1_open_sync_preview == "runs/aqp1_seed_row_sync_apply_preview_current.md"
        ),
        "aqp1_sync_preview_safe_staged_field_count": aqp1_seed_sync_summary.get(
            "safe_staged_field_count",
            manual_review_dashboard["summary"].get("aqp1_seed_row_sync_safe_staged_field_count", 0),
        ),
        "aqp1_exact_human_activity_count": aqp1_quantitative_summary.get("exact_human_aqp1_activity_count", 0),
        "aqp1_quantitative_provenance_primary_focus_ligand": aqp1_quantitative_summary.get("primary_focus_ligand", ""),
        "aqp1_quantitative_provenance_signal": aqp1_quantitative_summary.get("signal", ""),
        "glut1_second_wave_source_confirmation_ready": bool(glut1_source_confirmation_summary),
        "glut1_second_wave_source_confirmation_packet_artifact": (
            "runs/glut1_second_wave_source_confirmation_packet_current.md"
            if glut1_source_confirmation_summary
            else ""
        ),
        "glut1_second_wave_source_confirmation_row_count": glut1_source_confirmation_summary.get("row_count", 0),
        "glut1_second_wave_source_confirmation_primary_focus_ligand": glut1_source_confirmation_summary.get(
            "primary_focus_ligand",
            "",
        ),
        "glut1_direct_quantitative_binding_count": glut1_source_confirmation_summary.get(
            "direct_quantitative_binding_count",
            0,
        ),
        "glut1_exact_target_pair_activity_count": glut1_source_confirmation_summary.get(
            "exact_target_pair_activity_count",
            0,
        ),
        "glut1_structured_pair_absent_count": glut1_source_confirmation_summary.get(
            "structured_pair_absent_count",
            0,
        ),
        "aqp1_follow_on_packet_ready": bool(aqp1_follow_on_summary),
        "aqp1_follow_on_row_count": aqp1_follow_on_summary.get("row_count", 0),
        "aqp1_follow_on_targets": aqp1_follow_on_summary.get("follow_on_targets", ""),
        "aqp1_follow_on_blocker_decomposition_ready": bool(aqp1_open_follow_on_blocker_decomposition),
        "aqp1_follow_on_blocker_decomposition_artifact": aqp1_open_follow_on_blocker_decomposition,
        "aqp1_follow_on_blocker_decomposition_row_count": aqp1_follow_on_blocker_decomposition_summary.get(
            "blocker_row_count",
            0,
        ),
        "aqp1_follow_on_blocker_decomposition_follow_on_targets": aqp1_follow_on_blocker_decomposition_summary.get(
            "follow_on_targets",
            "",
        ),
        "aqp1_follow_on_blocker_decomposition_primary_focus_ligand": aqp1_follow_on_blocker_decomposition_summary.get(
            "primary_focus_ligand",
            "",
        ),
        "aqp1_follow_on_blocker_decomposition_exact_human_guardrail_ligand": aqp1_follow_on_blocker_decomposition_summary.get(
            "exact_human_guardrail_ligand",
            "",
        ),
        "aqp1_follow_on_blocker_decomposition_exact_human_nonbinding_count": aqp1_follow_on_blocker_decomposition_summary.get(
            "exact_human_nonbinding_count",
            0,
        ),
        "aqp1_follow_on_blocker_decomposition_exact_target_pair_absent_count": aqp1_follow_on_blocker_decomposition_summary.get(
            "exact_target_pair_absent_count",
            0,
        ),
        "aqp1_follow_on_blocker_decomposition_next_required_step": aqp1_follow_on_blocker_decomposition_summary.get(
            "next_required_step",
            "",
        ),
        "aqp1_negative_primary_probe_resolution_ready": bool(aqp1_primary_probe_resolution_artifact),
        "aqp1_negative_primary_probe_resolution_artifact": aqp1_primary_probe_resolution_artifact,
        "aqp1_negative_primary_probe_resolution_candidate": aqp1_primary_probe_resolution_candidate,
        "aqp1_negative_primary_probe_resolution_decision": aqp1_primary_probe_resolution_decision,
        "aqp1_negative_primary_probe_resolution_solvent_fallback_candidate": aqp1_primary_probe_resolution_solvent_fallback_candidate,
        "aqp1_evidence_mode": aqp1_seed_execution_summary.get("evidence_mode", "functional_potency_staged_review_only"),
        "aqp1_quantitative_binding_status": aqp1_seed_execution_summary.get(
            "quantitative_binding_status",
            "quantitative_binding_absent_claim_safe_kcal_missing",
        ),
        "aqp1_remaining_unresolved_fields": aqp1_seed_execution_summary.get(
            "remaining_unresolved_fields",
            "replacement_reference_binding_kcal_mol",
        ),
        "console_rule": (
            "Open AQP1 first, keep the AqB013 exact-human-activity provenance lane visible while working, use GLUT1 only as the second-wave fallback, and do not convert any transporter draft into authoritative apply today."
            + (
                f" When widened, keep {glut1_open_source_confirmation or 'the GLUT1 second-wave source-confirmation packet'} open and start with "
                f"{glut1_source_confirmation_summary.get('primary_focus_ligand', 'cytochalasin B')} as the direct quantitative GLUT1 binding lead while leaving replacement_reference_binding_kcal_mol blank."
                if glut1_source_confirmation_summary
                else ""
            )
        ),
    }


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_md(path: Path, summary: dict, rows: list[dict]) -> None:
    lines = [
        "# Transporter Operator Console",
        "",
        f"- target_count: `{summary['target_count']}`",
        f"- binder_pending_manual_verdict_count: `{summary['binder_pending_manual_verdict_count']}`",
        f"- binder_note_template_count: `{summary['binder_note_template_count']}`",
        f"- aqp1_ready_for_today: `{summary['aqp1_ready_for_today']}`",
        f"- glut1_ready_for_today: `{summary['glut1_ready_for_today']}`",
        f"- transporter_family_state: `{summary['transporter_family_state']}`",
        f"- current_phase: `{summary['current_phase']}`",
        f"- aqp1_open_source_confirmation: `{summary['aqp1_open_source_confirmation']}`",
        f"- aqp1_open_provenance: `{summary['aqp1_open_provenance']}`",
        f"- aqp1_open_follow_on: `{summary['aqp1_open_follow_on']}`",
        f"- aqp1_open_follow_on_blocker_decomposition: `{summary['aqp1_open_follow_on_blocker_decomposition']}`",
        f"- aqp1_execution_packet_ready: `{summary['aqp1_execution_packet_ready']}`",
        f"- aqp1_seed_fill_ready: `{summary['aqp1_seed_fill_ready']}`",
        f"- aqp1_seed_fill_safe_prefill_count: `{summary['aqp1_seed_fill_safe_prefill_count']}`",
        f"- aqp1_sync_preview_ready: `{summary['aqp1_sync_preview_ready']}`",
        f"- aqp1_sync_preview_safe_staged_field_count: `{summary['aqp1_sync_preview_safe_staged_field_count']}`",
        f"- aqp1_exact_human_activity_count: `{summary['aqp1_exact_human_activity_count']}`",
        f"- aqp1_quantitative_provenance_primary_focus_ligand: `{summary['aqp1_quantitative_provenance_primary_focus_ligand']}`",
        f"- aqp1_quantitative_provenance_signal: `{summary['aqp1_quantitative_provenance_signal']}`",
        f"- glut1_open_source_confirmation: `{summary['glut1_open_source_confirmation']}`",
        f"- glut1_second_wave_source_confirmation_ready: `{summary['glut1_second_wave_source_confirmation_ready']}`",
        f"- glut1_second_wave_source_confirmation_packet_artifact: `{summary['glut1_second_wave_source_confirmation_packet_artifact']}`",
        f"- glut1_second_wave_source_confirmation_row_count: `{summary['glut1_second_wave_source_confirmation_row_count']}`",
        f"- glut1_second_wave_source_confirmation_primary_focus_ligand: `{summary['glut1_second_wave_source_confirmation_primary_focus_ligand']}`",
        f"- glut1_direct_quantitative_binding_count: `{summary['glut1_direct_quantitative_binding_count']}`",
        f"- glut1_exact_target_pair_activity_count: `{summary['glut1_exact_target_pair_activity_count']}`",
        f"- glut1_structured_pair_absent_count: `{summary['glut1_structured_pair_absent_count']}`",
        f"- aqp1_follow_on_packet_ready: `{summary['aqp1_follow_on_packet_ready']}`",
        f"- aqp1_follow_on_row_count: `{summary['aqp1_follow_on_row_count']}`",
        f"- aqp1_follow_on_targets: `{summary['aqp1_follow_on_targets']}`",
        f"- aqp1_follow_on_blocker_decomposition_ready: `{summary['aqp1_follow_on_blocker_decomposition_ready']}`",
        f"- aqp1_follow_on_blocker_decomposition_artifact: `{summary['aqp1_follow_on_blocker_decomposition_artifact']}`",
        f"- aqp1_follow_on_blocker_decomposition_row_count: `{summary['aqp1_follow_on_blocker_decomposition_row_count']}`",
        f"- aqp1_follow_on_blocker_decomposition_follow_on_targets: `{summary['aqp1_follow_on_blocker_decomposition_follow_on_targets']}`",
        f"- aqp1_follow_on_blocker_decomposition_primary_focus_ligand: `{summary['aqp1_follow_on_blocker_decomposition_primary_focus_ligand']}`",
        f"- aqp1_follow_on_blocker_decomposition_exact_human_guardrail_ligand: `{summary['aqp1_follow_on_blocker_decomposition_exact_human_guardrail_ligand']}`",
        f"- aqp1_follow_on_blocker_decomposition_exact_human_nonbinding_count: `{summary['aqp1_follow_on_blocker_decomposition_exact_human_nonbinding_count']}`",
        f"- aqp1_follow_on_blocker_decomposition_exact_target_pair_absent_count: `{summary['aqp1_follow_on_blocker_decomposition_exact_target_pair_absent_count']}`",
        f"- aqp1_follow_on_blocker_decomposition_next_required_step: `{summary['aqp1_follow_on_blocker_decomposition_next_required_step']}`",
        f"- aqp1_negative_primary_probe_resolution_ready: `{summary['aqp1_negative_primary_probe_resolution_ready']}`",
        f"- aqp1_negative_primary_probe_resolution_artifact: `{summary['aqp1_negative_primary_probe_resolution_artifact']}`",
        f"- aqp1_negative_primary_probe_resolution_candidate: `{summary['aqp1_negative_primary_probe_resolution_candidate']}`",
        f"- aqp1_negative_primary_probe_resolution_decision: `{summary['aqp1_negative_primary_probe_resolution_decision']}`",
        f"- aqp1_negative_primary_probe_resolution_solvent_fallback_candidate: `{summary['aqp1_negative_primary_probe_resolution_solvent_fallback_candidate']}`",
        f"- aqp1_evidence_mode: `{summary['aqp1_evidence_mode']}`",
        f"- aqp1_quantitative_binding_status: `{summary['aqp1_quantitative_binding_status']}`",
        f"- aqp1_remaining_unresolved_fields: `{summary['aqp1_remaining_unresolved_fields']}`",
        "",
        "## Console Rule",
        "",
        f"- {summary['console_rule']}",
        f"- AQP1 first-wave seed work is functional potency staged only; claim-safe quantitative binding is still absent.",
        "",
        "## Open First",
        "",
        f"- `AQP1`: `{summary['aqp1_open_first']}`",
        f"- `AQP1 source confirmation`: `{summary['aqp1_open_source_confirmation']}`",
        f"- `AQP1 provenance`: `{summary['aqp1_open_provenance']}`",
        f"- `AQP1 follow-on`: `{summary['aqp1_open_follow_on']}`",
        f"- `AQP1 follow-on blocker decomposition`: `{summary['aqp1_open_follow_on_blocker_decomposition']}`",
        f"- `AQP1 execution packet`: `{summary['aqp1_open_execution']}`",
        f"- `AQP1 seed fill draft`: `{summary['aqp1_open_seed_fill']}`",
        f"- `AQP1 sync preview`: `{summary['aqp1_open_sync_preview']}`",
        f"- `AQP1 negative review`: `{summary['aqp1_open_negative_review']}`",
        f"- `GLUT1`: `{summary['glut1_open_first']}`",
        f"- `GLUT1 source confirmation`: `{summary['glut1_open_source_confirmation']}`",
        "",
        "## Target Order",
        "",
        "| target | wave | open first | open second | open source confirmation | open provenance | open follow on | open third | open fourth | open fifth | pending manual verdicts | operator instruction |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| `{target}` | `{wave}` | `{open_first}` | `{open_second}` | `{open_source_confirmation}` | `{open_provenance}` | `{open_follow_on}` | `{open_third}` | `{open_fourth}` | `{open_fifth}` | `{pending_manual_verdict_count}` | {operator_instruction} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## What To Do Today",
            "",
            "- Open `AQP1` first and, because the manual-verdict backlog is already cleared, use the first seed-row packet, the follow-on packet, the execution packet, the seed-row fill draft, and the sync preview before returning to negative review and the staging surface.",
            "- Keep the `AqB013` exact-human-activity provenance packet open as a guardrail and leave `replacement_reference_binding_kcal_mol` blank while reviewing AQP1 binder rows.",
            (
                f"- Keep `{summary['aqp1_negative_primary_probe_resolution_artifact']}` ready so `{summary['aqp1_negative_primary_probe_resolution_candidate'] or 'sodium nitroprusside'}` stays review-only and `{summary['aqp1_negative_primary_probe_resolution_solvent_fallback_candidate'] or 'dimethyl sulfoxide'}` stays solvent-only at decision `{summary['aqp1_negative_primary_probe_resolution_decision'] or 'keep_review_only_no_authoritative_negative_promotion'}`."
                if summary["aqp1_negative_primary_probe_resolution_artifact"]
                else "- Keep the AQP1 primary-probe resolution handoff ready if the negative-evidence packet surface is available."
            ),
            "- Open `GLUT1` only if AQP1 first-wave work is exhausted or if extra reviewer time remains.",
            "- When GLUT1 widens, keep the GLUT1 second-wave source-confirmation packet open and start with cytochalasin B before WZB117 and STF-31.",
            "- Keep transporter in reviewer-only mode; do not convert draft packets, note templates, or suggested verdicts into authoritative apply.",
        ]
    )
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    reviewer_day_plan = load_json(REVIEWER_DAY_PLAN_JSON)
    apply_draft_status = load_json(APPLY_DRAFT_STATUS_JSON)
    manual_review_dashboard = load_json(MANUAL_REVIEW_DASHBOARD_JSON)
    aqp1_handoff = load_json(AQP1_MANUAL_VERDICT_HANDOFF_JSON)
    glut1_handoff = load_json(GLUT1_MANUAL_VERDICT_HANDOFF_JSON)
    aqp1_first_seed_row_packet = load_json(AQP1_FIRST_SEED_ROW_PACKET_JSON)
    aqp1_seed_row_execution_packet = load_json(AQP1_SEED_ROW_EXECUTION_PACKET_JSON)
    aqp1_seed_row_fill_draft = load_json(AQP1_SEED_ROW_FILL_DRAFT_JSON)
    aqp1_seed_row_sync_preview = load_json(AQP1_SEED_ROW_SYNC_PREVIEW_JSON)
    aqp1_quantitative_provenance = load_json(AQP1_QUANTITATIVE_PROVENANCE_JSON)
    aqp1_source_confirmation = load_json(AQP1_SOURCE_CONFIRMATION_JSON)
    aqp1_follow_on_packet = maybe_load_json(AQP1_FOLLOW_ON_PACKET_JSON)
    aqp1_follow_on_blocker_decomposition = maybe_load_json(AQP1_FOLLOW_ON_BLOCKER_DECOMPOSITION_JSON)
    glut1_source_confirmation = maybe_load_json(GLUT1_SOURCE_CONFIRMATION_JSON)
    negative_target_packets = maybe_load_json(TRANSPORTER_NEGATIVE_TARGET_PACKETS_JSON)

    target_rows = build_target_rows(
        aqp1_handoff,
        glut1_handoff,
        aqp1_first_seed_row_packet,
        aqp1_seed_row_execution_packet,
        aqp1_seed_row_fill_draft,
        aqp1_seed_row_sync_preview,
        aqp1_quantitative_provenance,
        aqp1_source_confirmation,
        aqp1_follow_on_packet,
        aqp1_follow_on_blocker_decomposition,
        glut1_source_confirmation,
        negative_target_packets,
    )
    summary = build_summary(
        reviewer_day_plan,
        apply_draft_status,
        manual_review_dashboard,
        aqp1_seed_row_execution_packet,
        aqp1_seed_row_sync_preview,
        aqp1_quantitative_provenance,
        aqp1_follow_on_packet,
        aqp1_follow_on_blocker_decomposition,
        glut1_source_confirmation,
        target_rows,
    )
    payload = {"summary": summary, "target_rows": target_rows}

    write_json(OUT_JSON, payload)
    write_csv(OUT_CSV, target_rows)
    write_md(OUT_MD, summary, target_rows)


if __name__ == "__main__":
    main()
