#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.ligand_scaleup_surface_helpers import (
    DEFAULT_LIGAND_SCALEUP_BENCHMARK_SUMMARY_JSON as LIGAND_SCALEUP_BENCHMARK_SUMMARY_JSON,
    DEFAULT_LIGAND_SCALEUP_SUITE_STATUS_JSON as LIGAND_SCALEUP_SUITE_STATUS_JSON,
    summarize_ligand_scaleup_blocker,
)
from tools.local_engine_surface_helpers import (
    DEFAULT_LOCAL_ENGINE_COMMERCIALIZATION_QUEUE_JSON,
    local_engine_summary_from_source,
    summarize_local_engine_commercialization_queue,
)
from tools.product.transporter_phase_helpers import infer_transporter_phase

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PRETEST_JSON = "runs/pretest_execution_readiness_current.json"
DEFAULT_PRETEST_HANDOFF_JSON = "runs/pretest_handoff_bundle_current.json"
DEFAULT_PRETEST_SEQUENCE_JSON = "runs/pretest_execution_sequence_note_current.json"
DEFAULT_PRETEST_COMMAND_CHECKLIST_JSON = "runs/pretest_command_checklist_current.json"
DEFAULT_PARTIAL_HANDOFF_JSON = "runs/partial_authoritative_family_handoff_current.json"
DEFAULT_TRANSPORTER_APPLY_DRAFT_JSON = "runs/transporter_apply_draft_status_current.json"
DEFAULT_CA2_CAPTURE_SHEET_JSON = "runs/ca2_negative_evidence_capture_sheet_current.json"
DEFAULT_CA2_CAPTURE_INTAKE_JSON = "runs/ca2_negative_evidence_capture_intake_current.json"
DEFAULT_CA2_COMMIT_PACKET_JSON = "runs/ca2_evidence_closure_commit_packet_current.json"
DEFAULT_PXR_CAPTURE_SHEET_JSON = "runs/pxr_unresolved_evidence_capture_sheet_current.json"
DEFAULT_PXR_CAPTURE_INTAKE_JSON = "runs/pxr_unresolved_evidence_capture_intake_current.json"
DEFAULT_PXR_COMMIT_PACKET_JSON = "runs/pxr_pending_resolution_commit_packet_current.json"
DEFAULT_PXR_BURNDOWN_JSON = "runs/pxr_pending_burndown_console_current.json"
DEFAULT_PXR_LITERATURE_OVERLAY_JSON = "runs/pxr_literature_candidate_overlay_current.json"
DEFAULT_PXR_CONFIRMATION_PACKET_JSON = "runs/pxr_exact_source_confirmation_packet_current.json"
DEFAULT_PXR_CONFLICT_RESOLVER_PACKET_JSON = "runs/pxr_conflict_resolver_packet_current.json"
DEFAULT_PXR_QUANTITATIVE_PROVENANCE_PACKET_JSON = "runs/pxr_quantitative_provenance_packet_current.json"
DEFAULT_TRANSPORTER_CAPTURE_INTAKE_JSON = "runs/transporter_blocker_capture_intake_current.json"
DEFAULT_AQP1_FIRST_SEED_ROW_PACKET_JSON = "runs/aqp1_first_seed_row_packet_current.json"
DEFAULT_AQP1_EXTERNAL_SEED_JSON = "runs/aqp1_external_evidence_seed_current.json"
DEFAULT_AQP1_QUANT_BIND_INTAKE_JSON = "runs/aqp1_quantitative_binding_capture_intake_current.json"
DEFAULT_AQP1_QUANTITATIVE_PROVENANCE_PACKET_JSON = "runs/aqp1_quantitative_provenance_packet_current.json"
DEFAULT_AQP1_FIRST_WAVE_SOURCE_CONFIRMATION_PACKET_JSON = "runs/aqp1_first_wave_source_confirmation_packet_current.json"
DEFAULT_AQP1_FIRST_WAVE_FOLLOW_ON_PACKET_JSON = "runs/aqp1_first_wave_follow_on_packet_current.json"
DEFAULT_AQP1_FIRST_WAVE_FOLLOW_ON_PACKET_MD = "runs/aqp1_first_wave_follow_on_packet_current.md"
DEFAULT_AQP1_FOLLOW_ON_BLOCKER_DECOMPOSITION_JSON = "runs/aqp1_follow_on_blocker_decomposition_current.json"
DEFAULT_AQP1_NEGATIVE_PRIMARY_PROBE_RESOLUTION_PACKET_JSON = "runs/aqp1_negative_primary_probe_resolution_packet_current.json"
DEFAULT_AQP1_NEGATIVE_PRIMARY_PROBE_RESOLUTION_PACKET_MD = "runs/aqp1_negative_primary_probe_resolution_packet_current.md"
DEFAULT_GLUT1_SECOND_WAVE_SOURCE_CONFIRMATION_PACKET_JSON = "runs/glut1_second_wave_source_confirmation_packet_current.json"
DEFAULT_GLUT1_SECOND_WAVE_SOURCE_CONFIRMATION_PACKET_MD = "runs/glut1_second_wave_source_confirmation_packet_current.md"
DEFAULT_MANUAL_BURNDOWN_JSON = "runs/family_manual_review_burndown_current.json"
DEFAULT_MANUAL_PRIORITY_QUEUE_JSON = "runs/family_manual_review_priority_queue_current.json"
DEFAULT_EVIDENCE_ACQUISITION_QUEUE_JSON = "runs/family_evidence_acquisition_queue_current.json"
DEFAULT_EVIDENCE_INVESTIGATOR_PACKET_JSON = "runs/family_evidence_investigator_packet_current.json"
DEFAULT_COMMERCIALIZATION_JSON = "runs/commercialization_readiness_current.json"
DEFAULT_COMMERCIALIZATION_GAP_JSON = "runs/commercialization_gap_burndown_current.json"
DEFAULT_LOCAL_ENGINE_QUEUE_JSON = DEFAULT_LOCAL_ENGINE_COMMERCIALIZATION_QUEUE_JSON
DEFAULT_LIGAND_SCALEUP_SUITE_STATUS_JSON = LIGAND_SCALEUP_SUITE_STATUS_JSON
DEFAULT_LIGAND_SCALEUP_BENCHMARK_SUMMARY_JSON = LIGAND_SCALEUP_BENCHMARK_SUMMARY_JSON
DEFAULT_OUT_JSON = "runs/execution_handoff_dashboard_current.json"
DEFAULT_OUT_CSV = "runs/execution_handoff_dashboard_current.csv"
DEFAULT_OUT_MD = "runs/execution_handoff_dashboard_current.md"


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


def _artifact_for(path: str, payload: dict[str, Any] | None) -> str:
    return path if payload else ""


def build_payload(
    pretest: dict[str, Any],
    pretest_handoff: dict[str, Any],
    pretest_sequence: dict[str, Any],
    pretest_command_checklist: dict[str, Any],
    partial_handoff: dict[str, Any],
    transporter_apply_draft: dict[str, Any],
    ca2_capture_intake: dict[str, Any],
    pxr_capture_intake: dict[str, Any],
    transporter_capture_intake: dict[str, Any],
    aqp1_first_seed_row_packet: dict[str, Any],
    aqp1_external_seed: dict[str, Any],
    manual_burndown: dict[str, Any],
    manual_priority_queue: dict[str, Any],
    evidence_acquisition_queue: dict[str, Any],
    evidence_investigator_packet: dict[str, Any],
    pxr_literature_overlay: dict[str, Any],
    pxr_confirmation_packet: dict[str, Any],
    pxr_quantitative_provenance_packet: dict[str, Any],
    commercialization: dict[str, Any],
    commercialization_gap: dict[str, Any],
    aqp1_quantitative_binding_capture_intake: dict[str, Any] | None = None,
    aqp1_quantitative_provenance_packet: dict[str, Any] | None = None,
    aqp1_first_wave_source_confirmation_packet: dict[str, Any] | None = None,
    ca2_capture_sheet: dict[str, Any] | None = None,
    ca2_commit_packet: dict[str, Any] | None = None,
    pxr_capture_sheet: dict[str, Any] | None = None,
    pxr_commit_packet: dict[str, Any] | None = None,
    pxr_burndown_console: dict[str, Any] | None = None,
    pxr_conflict_resolver_packet: dict[str, Any] | None = None,
    aqp1_first_wave_follow_on_packet: dict[str, Any] | None = None,
    aqp1_follow_on_blocker_decomposition: dict[str, Any] | None = None,
    aqp1_follow_on_source_confirmation_packet: dict[str, Any] | None = None,
    transporter_placeholder_burndown_queue: dict[str, Any] | None = None,
    aqp1_negative_primary_probe_resolution_packet: dict[str, Any] | None = None,
    glut1_second_wave_source_confirmation_packet: dict[str, Any] | None = None,
    ligand_scaleup_suite_status: dict[str, Any] | None = None,
    ligand_scaleup_benchmark_summary: dict[str, Any] | None = None,
    local_engine_commercialization_queue: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pretest_s = dict(pretest.get("summary", {}) or {})
    pretest_rows = list(pretest.get("rows", []) or [])
    pretest_handoff_s = dict(pretest_handoff.get("summary", {}) or {})
    pretest_sequence_s = dict(pretest_sequence.get("summary", {}) or {})
    pretest_checklist_s = dict(pretest_command_checklist.get("summary", {}) or {})
    partial_s = dict(partial_handoff.get("summary", {}) or {})
    transporter_s = dict(transporter_apply_draft.get("summary", {}) or {})
    ca2_capture_s = dict(ca2_capture_intake.get("summary", {}) or {})
    ca2_capture_sheet_s = dict((ca2_capture_sheet or {}).get("summary", {}) or {})
    ca2_commit_s = dict((ca2_commit_packet or {}).get("summary", {}) or {})
    pxr_capture_s = dict(pxr_capture_intake.get("summary", {}) or {})
    pxr_capture_sheet_s = dict((pxr_capture_sheet or {}).get("summary", {}) or {})
    pxr_commit_s = dict((pxr_commit_packet or {}).get("summary", {}) or {})
    pxr_burndown_s = dict((pxr_burndown_console or {}).get("summary", {}) or {})
    transporter_capture_s = dict(transporter_capture_intake.get("summary", {}) or {})
    aqp1_first_seed_s = dict((aqp1_first_seed_row_packet or {}).get("summary", {}) or {})
    aqp1_external_seed_s = dict((aqp1_external_seed or {}).get("summary", {}) or {})
    aqp1_quant_bind_s = dict((aqp1_quantitative_binding_capture_intake or {}).get("summary", {}) or {})
    aqp1_quant_prov_s = dict((aqp1_quantitative_provenance_packet or {}).get("summary", {}) or {})
    aqp1_first_wave_confirmation_s = dict((aqp1_first_wave_source_confirmation_packet or {}).get("summary", {}) or {})
    aqp1_first_wave_follow_on_s = dict((aqp1_first_wave_follow_on_packet or {}).get("summary", {}) or {})
    aqp1_follow_on_blocker_decomposition_s = dict((aqp1_follow_on_blocker_decomposition or {}).get("summary", {}) or {})
    aqp1_follow_on_source_confirmation_packet_s = dict(
        (aqp1_follow_on_source_confirmation_packet or {}).get("summary", {}) or {}
    )
    transporter_placeholder_burndown_queue_s = dict(
        (transporter_placeholder_burndown_queue or {}).get("summary", {}) or {}
    )
    aqp1_negative_primary_probe_resolution_s = dict(
        (aqp1_negative_primary_probe_resolution_packet or {}).get("summary", {}) or {}
    )
    glut1_second_wave_source_confirmation_packet_s = dict(
        (glut1_second_wave_source_confirmation_packet or {}).get("summary", {}) or {}
    )
    transporter_seed_rows = int(transporter_s.get("binder_slot_count", 0) or 0)
    transporter_placeholder_rows = int(transporter_s.get("placeholder_driven_rows", 0) or 0)
    transporter_phase = infer_transporter_phase(transporter_s)
    manual_s = dict(manual_burndown.get("summary", {}) or {})
    manual_priority_s = dict(manual_priority_queue.get("summary", {}) or {})
    evidence_acquisition_s = dict(evidence_acquisition_queue.get("summary", {}) or {})
    evidence_investigator_s = dict(evidence_investigator_packet.get("summary", {}) or {})
    pxr_literature_s = dict((pxr_literature_overlay or {}).get("summary", {}) or {})
    pxr_confirmation_s = dict((pxr_confirmation_packet or {}).get("summary", {}) or {})
    pxr_conflict_resolver_s = dict((pxr_conflict_resolver_packet or {}).get("summary", {}) or {})
    pxr_quantitative_s = dict((pxr_quantitative_provenance_packet or {}).get("summary", {}) or {})
    commercialization_s = dict(commercialization.get("summary", {}) or {})
    commercialization_gap_s = dict(commercialization_gap.get("summary", {}) or {})
    ligand_scaleup_summary = summarize_ligand_scaleup_blocker(
        ligand_scaleup_suite_status,
        ligand_scaleup_benchmark_summary,
    )
    local_engine_summary = summarize_local_engine_commercialization_queue(
        local_engine_commercialization_queue
    )
    if not local_engine_summary["local_engine_commercialization_queue_ready"]:
        local_engine_summary = local_engine_summary_from_source(commercialization_s)
    aqp1_quant_signal = (
        "exact_human_activity_present_leave_kcal_blank"
        if int(aqp1_quant_prov_s.get("exact_human_aqp1_activity_count", 0) or 0) > 0
        else "quantitative_binding_absent_leave_kcal_blank"
    )
    aqp1_quant_focus_ligand = str(aqp1_quant_prov_s.get("primary_focus_ligand", "") or "").strip()
    aqp1_first_wave_primary_focus_ligand = str(
        aqp1_first_wave_confirmation_s.get("primary_focus_ligand", "") or ""
    ).strip()
    aqp1_first_wave_exact_human_reference_ligand = str(
        aqp1_first_wave_confirmation_s.get("exact_human_reference_ligand", "") or ""
    ).strip()
    aqp1_first_wave_next_required_step = str(
        aqp1_first_wave_confirmation_s.get("next_required_step", "") or ""
    ).strip()
    aqp1_first_wave_follow_on_packet_ready = bool(aqp1_first_wave_follow_on_s)
    aqp1_first_wave_follow_on_packet_artifact = str(
        aqp1_first_wave_follow_on_s.get("follow_on_packet_artifact")
        or aqp1_first_wave_follow_on_s.get("packet_artifact")
        or (DEFAULT_AQP1_FIRST_WAVE_FOLLOW_ON_PACKET_JSON if aqp1_first_wave_follow_on_packet_ready else "")
    ).strip()
    aqp1_first_wave_follow_on_row_count = int(aqp1_first_wave_follow_on_s.get("row_count", 0) or 0)
    aqp1_first_wave_follow_on_primary_focus_ligand = str(
        aqp1_first_wave_follow_on_s.get("primary_focus_ligand", "") or ""
    ).strip()
    aqp1_follow_on_blocker_decomposition_ready = bool(aqp1_follow_on_blocker_decomposition_s)
    aqp1_follow_on_blocker_count = int(aqp1_follow_on_blocker_decomposition_s.get("blocker_row_count", 0) or 0)
    aqp1_follow_on_exact_human_nonbinding_count = int(
        aqp1_follow_on_blocker_decomposition_s.get("exact_human_nonbinding_count", 0) or 0
    )
    aqp1_follow_on_exact_target_pair_absent_count = int(
        aqp1_follow_on_blocker_decomposition_s.get("exact_target_pair_absent_count", 0) or 0
    )
    aqp1_follow_on_high_or_medium_potential_count = int(
        aqp1_follow_on_blocker_decomposition_s.get("high_or_medium_potential_count", 0) or 0
    )
    aqp1_follow_on_claim_safe_kcal_ready_count = int(
        aqp1_follow_on_blocker_decomposition_s.get("claim_safe_kcal_ready_count", 0) or 0
    )
    aqp1_follow_on_source_confirmation_primary_focus_ligand = str(
        aqp1_follow_on_blocker_decomposition_s.get("source_confirmation_primary_focus_ligand", "") or ""
    ).strip()
    aqp1_follow_on_exact_human_guardrail_ligand = str(
        aqp1_follow_on_blocker_decomposition_s.get("exact_human_guardrail_ligand", "") or ""
    ).strip()
    aqp1_follow_on_blocking_signal = str(
        aqp1_follow_on_blocker_decomposition_s.get("blocking_signal", "") or ""
    ).strip()
    aqp1_follow_on_next_required_step = str(
        aqp1_follow_on_blocker_decomposition_s.get("next_required_step", "") or ""
    ).strip()
    aqp1_follow_on_blocker_decomposition_artifact = str(
        aqp1_follow_on_blocker_decomposition_s.get("blocker_decomposition_artifact")
        or aqp1_follow_on_blocker_decomposition_s.get("packet_artifact")
        or (DEFAULT_AQP1_FOLLOW_ON_BLOCKER_DECOMPOSITION_JSON if aqp1_follow_on_blocker_decomposition_ready else "")
    ).strip()
    aqp1_follow_on_source_confirmation_packet_ready = bool(aqp1_follow_on_source_confirmation_packet_s)
    aqp1_follow_on_source_confirmation_packet_artifact = _artifact_for(
        "runs/aqp1_follow_on_source_confirmation_packet_current.md",
        aqp1_follow_on_source_confirmation_packet_s,
    )
    aqp1_follow_on_source_confirmation_packet_row_count = int(
        aqp1_follow_on_source_confirmation_packet_s.get("row_count", 0) or 0
    )
    aqp1_follow_on_source_confirmation_packet_primary_focus_ligand = str(
        aqp1_follow_on_source_confirmation_packet_s.get("primary_focus_ligand", "") or ""
    ).strip()
    aqp1_follow_on_source_confirmation_packet_exact_human_reference_ligand = str(
        aqp1_follow_on_source_confirmation_packet_s.get("exact_human_reference_ligand", "") or ""
    ).strip()
    transporter_placeholder_burndown_queue_ready = bool(transporter_placeholder_burndown_queue_s)
    transporter_placeholder_burndown_queue_artifact = _artifact_for(
        "runs/transporter_placeholder_burndown_queue_current.md",
        transporter_placeholder_burndown_queue_s,
    )
    transporter_placeholder_burndown_queue_row_count = int(
        transporter_placeholder_burndown_queue_s.get("row_count", 0) or 0
    )
    transporter_placeholder_burndown_queue_top_blocker_id = str(
        transporter_placeholder_burndown_queue_s.get("top_blocker_id", "") or ""
    ).strip()
    aqp1_negative_primary_probe_resolution_ready = bool(aqp1_negative_primary_probe_resolution_s)
    aqp1_negative_primary_probe_resolution_artifact = str(
        aqp1_negative_primary_probe_resolution_s.get("packet_artifact")
        or _artifact_for(
            DEFAULT_AQP1_NEGATIVE_PRIMARY_PROBE_RESOLUTION_PACKET_MD,
            aqp1_negative_primary_probe_resolution_s,
        )
    ).strip()
    aqp1_negative_primary_probe_resolution_row_count = int(
        aqp1_negative_primary_probe_resolution_s.get("row_count", 0) or 0
    )
    aqp1_negative_primary_probe_resolution_candidate = str(
        aqp1_negative_primary_probe_resolution_s.get("primary_probe_candidate", "") or ""
    ).strip()
    aqp1_negative_primary_probe_resolution_solvent_fallback_candidate = str(
        aqp1_negative_primary_probe_resolution_s.get("solvent_fallback_candidate", "") or ""
    ).strip()
    aqp1_negative_primary_probe_resolution_decision = str(
        aqp1_negative_primary_probe_resolution_s.get("resolution_decision", "") or ""
    ).strip()
    aqp1_negative_primary_probe_resolution_next_required_step = str(
        aqp1_negative_primary_probe_resolution_s.get("next_required_step", "") or ""
    ).strip()
    glut1_second_wave_source_confirmation_packet_ready = bool(glut1_second_wave_source_confirmation_packet_s)
    glut1_second_wave_source_confirmation_packet_artifact = str(
        glut1_second_wave_source_confirmation_packet_s.get("packet_artifact")
        or _artifact_for(
            DEFAULT_GLUT1_SECOND_WAVE_SOURCE_CONFIRMATION_PACKET_MD,
            glut1_second_wave_source_confirmation_packet_s,
        )
    ).strip()
    glut1_second_wave_source_confirmation_packet_row_count = int(
        glut1_second_wave_source_confirmation_packet_s.get("row_count", 0) or 0
    )
    glut1_second_wave_source_confirmation_packet_primary_focus_ligand = str(
        glut1_second_wave_source_confirmation_packet_s.get("primary_focus_ligand", "") or ""
    ).strip()
    glut1_second_wave_source_confirmation_packet_next_required_step = str(
        glut1_second_wave_source_confirmation_packet_s.get("next_required_step", "") or ""
    ).strip()
    glut1_second_wave_direct_quantitative_binding_count = int(
        glut1_second_wave_source_confirmation_packet_s.get("direct_quantitative_binding_count", 0) or 0
    )
    aqp1_first_wave_follow_on_exact_human_reference_ligand = str(
        aqp1_first_wave_follow_on_s.get(
            "exact_human_reference_ligand",
            aqp1_first_wave_exact_human_reference_ligand or aqp1_quant_focus_ligand,
        )
        or ""
    ).strip()
    aqp1_first_wave_follow_on_signal = str(
        aqp1_first_wave_follow_on_s.get("signal", aqp1_first_wave_follow_on_s.get("next_required_step", "")) or ""
    ).strip()
    aqp1_operator_provenance_note = (
        f"{aqp1_quant_focus_ligand} carries exact human AQP1 target-activity provenance, but replacement_reference_binding_kcal_mol stays blank until claim-safe quantitative binding is curated."
        if aqp1_quant_focus_ligand and int(aqp1_quant_prov_s.get("exact_human_aqp1_activity_count", 0) or 0) > 0
        else "Keep replacement_reference_binding_kcal_mol blank until exact human target activity or claim-safe quantitative binding is curated."
    )
    aqp1_first_wave_confirmation_note = (
        aqp1_first_wave_next_required_step
        if aqp1_first_wave_next_required_step
        else (
            f"Review {aqp1_first_wave_primary_focus_ligand} first as the AQP1 core_binder_01 exact-source scope packet, "
            f"keep {aqp1_first_wave_exact_human_reference_ligand or aqp1_quant_focus_ligand} as the exact-human-activity reference row, "
            "and leave replacement_reference_binding_kcal_mol blank."
            if aqp1_first_wave_primary_focus_ligand and (aqp1_first_wave_exact_human_reference_ligand or aqp1_quant_focus_ligand)
            else ""
        )
    )
    aqp1_first_wave_follow_on_note = (
        f"Follow the AQP1 first-wave follow-on packet next: {aqp1_first_wave_follow_on_signal}"
        if aqp1_first_wave_follow_on_signal
        else ""
    )
    aqp1_follow_on_blocker_note = (
        f"Follow the AQP1 follow-on blocker decomposition packet next: {aqp1_follow_on_next_required_step}"
        if aqp1_follow_on_next_required_step
        else ""
    )
    aqp1_follow_on_source_confirmation_note = (
        f"Keep {aqp1_follow_on_source_confirmation_packet_primary_focus_ligand} as the literature-backed follow-on exact-source row while "
        f"{aqp1_follow_on_source_confirmation_packet_exact_human_reference_ligand or aqp1_first_wave_exact_human_reference_ligand or 'AqB013'} "
        "stays the exact-human-activity guardrail."
        if aqp1_follow_on_source_confirmation_packet_primary_focus_ligand
        else ""
    )
    aqp1_negative_primary_probe_resolution_note = (
        f"Keep `{aqp1_negative_primary_probe_resolution_artifact or DEFAULT_AQP1_NEGATIVE_PRIMARY_PROBE_RESOLUTION_PACKET_MD}` "
        "open as the AQP1 negative primary-probe-resolution handoff. "
        + (
            aqp1_negative_primary_probe_resolution_next_required_step
            if aqp1_negative_primary_probe_resolution_next_required_step
            else (
                f"Keep {aqp1_negative_primary_probe_resolution_candidate or 'the current primary negative probe candidate'} "
                "review-only, preserve "
                f"{aqp1_negative_primary_probe_resolution_solvent_fallback_candidate or 'the solvent fallback candidate'} "
                "as solvent fallback only, and hold the lane at "
                f"{aqp1_negative_primary_probe_resolution_decision or 'keep_review_only_no_authoritative_negative_promotion'}."
            )
        )
        if aqp1_negative_primary_probe_resolution_ready
        else ""
    )
    transporter_placeholder_burndown_note = str(
        transporter_placeholder_burndown_queue_s.get("next_required_step", "") or ""
    ).strip()
    glut1_second_wave_source_confirmation_note = (
        f"Open `{glut1_second_wave_source_confirmation_packet_artifact or DEFAULT_GLUT1_SECOND_WAVE_SOURCE_CONFIRMATION_PACKET_MD}` "
        f"as the GLUT1 second-wave source-confirmation packet handoff, keep "
        f"{glut1_second_wave_source_confirmation_packet_primary_focus_ligand} as the lead, and keep direct quantitative binding "
        f"rows={glut1_second_wave_direct_quantitative_binding_count}."
        if glut1_second_wave_source_confirmation_packet_primary_focus_ligand
        else ""
    )
    aqp1_first_wave_dashboard_note = " ".join(
        part
        for part in (
            aqp1_first_wave_confirmation_note,
            aqp1_follow_on_source_confirmation_note,
            aqp1_follow_on_blocker_note,
            aqp1_first_wave_follow_on_note,
            aqp1_negative_primary_probe_resolution_note,
            transporter_placeholder_burndown_note,
            glut1_second_wave_source_confirmation_note,
        )
        if part
    )
    local_engine_queue_note = str(
        local_engine_summary.get("local_engine_commercialization_queue_blocker_note", "") or ""
    ).strip()
    local_engine_queue_next_required_step = str(
        local_engine_summary.get("local_engine_commercialization_queue_next_required_step", "") or ""
    ).strip()

    ready_now = [row for row in pretest_rows if row.get("pretest_ready") == "yes"]
    partial_now = [row for row in pretest_rows if row.get("pretest_ready") == "partial"]
    blocked_now = [row for row in pretest_rows if row.get("pretest_ready") == "no"]
    ca2_direct_conflict_count = int(
        ca2_capture_s.get(
            "direct_conflict_row_count",
            ca2_capture_sheet_s.get("direct_conflict_row_count", ca2_commit_s.get("conflict_review_row_count", 0)),
        )
        or 0
    )
    ca2_no_direct_negative_count = int(
        ca2_capture_s.get(
            "no_direct_negative_found_count",
            ca2_capture_sheet_s.get("no_direct_negative_found_count", ca2_commit_s.get("no_direct_negative_source_row_count", 0)),
        )
        or 0
    )
    ca2_source_linked_count = int(
        ca2_capture_s.get("source_linked_count", ca2_capture_sheet_s.get("source_linked_count", 0)) or 0
    )
    ca2_direct_negative_evidence_count = int(
        ca2_capture_s.get(
            "direct_negative_evidence_count",
            ca2_capture_sheet_s.get("direct_negative_evidence_count", 0),
        )
        or 0
    )
    ca2_closure_mode = str(
        ca2_capture_s.get("closure_mode", ca2_commit_s.get("closure_mode", "review_only_conflict_or_gap_only")) or ""
    )
    ca2_authoritative_negative_closure_allowed = bool(
        ca2_capture_s.get(
            "authoritative_negative_closure_allowed",
            ca2_commit_s.get("authoritative_negative_closure_allowed", False),
        )
    )
    ca2_remaining_blank_field = str(
        ca2_capture_s.get("remaining_blank_field", ca2_commit_s.get("remaining_blank_field", "replacement_reference_binding_kcal_mol"))
        or "replacement_reference_binding_kcal_mol"
    )
    ca2_next_required_step = str(
        ca2_commit_s.get("next_required_step", ca2_capture_s.get("next_required_step", ""))
    ).strip()

    pxr_signal = (
        f"review_only_{pxr_capture_sheet_s.get('review_only_candidate_count', 0)}"
        f"_deferred_{pxr_commit_s.get('must_remain_deferred_count', pxr_burndown_s.get('must_defer_count', 0))}"
        "_keep_human_support_explicit"
    )

    dashboard_rows: list[dict[str, Any]] = []
    for row in ready_now + partial_now + blocked_now:
        family = str(row.get("family", "") or "")
        lane = "run_now" if row.get("pretest_ready") == "yes" else ("prepare_next" if row.get("pretest_ready") == "partial" else "manual_review_only")
        extra_signal = ""
        if family == "transporter":
            extra_signal = (
                f"phase={transporter_phase}; "
                f"seed_rows={transporter_seed_rows}; "
                f"placeholder_rows={transporter_placeholder_rows}; "
                f"ready_apply={transporter_s.get('ready_for_apply_rows', 0)}; "
                f"capture_pending={transporter_capture_s.get('pending_capture_count', 0)}; "
                f"capture_sources={transporter_capture_s.get('source_linked_count', 0)}; "
                f"supportive={transporter_capture_s.get('supportive_target_specific_packet_evidence_count', 0)}; "
                f"aqp1_evidence={aqp1_first_seed_s.get('evidence_mode', 'functional_potency_staged_review_only')}; "
                f"aqp1_quantitative_binding={aqp1_first_seed_s.get('quantitative_binding_status', 'quantitative_binding_absent_claim_safe_kcal_missing')}; "
                f"aqp1_first_seed_unresolved={aqp1_first_seed_s.get('remaining_unresolved_fields', 'replacement_reference_binding_kcal_mol')}; "
                f"aqp1_direct_binding_candidates={aqp1_external_seed_s.get('direct_quantitative_binding_candidate_count', 0)}; "
                f"aqp1_qbind_sources={aqp1_quant_bind_s.get('source_linked_count', 0)}; "
                f"aqp1_qbind_review_only_gap={aqp1_quant_bind_s.get('captured_review_only_gap_count', 0)}; "
                f"aqp1_qbind_supportive={aqp1_quant_bind_s.get('supportive_direct_quantitative_binding_count', 0)}; "
                f"aqp1_qbind_kcal_ready={aqp1_quant_bind_s.get('kcal_overlay_ready_count', 0)}; "
                f"aqp1_qbind_signal={aqp1_quant_signal}; "
                f"aqp1_quantprov_rows={aqp1_quant_prov_s.get('row_count', 0)}; "
                f"aqp1_quantprov_pubchem_resolved={aqp1_quant_prov_s.get('pubchem_resolved_count', 0)}; "
                f"aqp1_quantprov_chembl_exact={aqp1_quant_prov_s.get('chembl_exact_match_count', 0)}; "
                f"aqp1_quantprov_exact_human_activity={aqp1_quant_prov_s.get('exact_human_aqp1_activity_count', 0)}; "
                f"aqp1_quantprov_focus={aqp1_quant_focus_ligand}; "
                f"aqp1_quantprov_signal={aqp1_quant_prov_s.get('signal', aqp1_quant_signal)}; "
                f"aqp1_first_wave_rows={aqp1_first_wave_confirmation_s.get('row_count', 0)}; "
                f"aqp1_first_wave_focus={aqp1_first_wave_primary_focus_ligand}; "
                f"aqp1_first_wave_exact_human_reference={aqp1_first_wave_exact_human_reference_ligand}; "
                f"aqp1_first_wave_pubchem_resolved={aqp1_first_wave_confirmation_s.get('pubchem_resolved_count', 0)}; "
                f"aqp1_first_wave_exact_pair_absent={aqp1_first_wave_confirmation_s.get('exact_pair_absent_count', 0)}; "
                f"aqp1_first_wave_exact_human_reference_count={aqp1_first_wave_confirmation_s.get('exact_human_activity_reference_count', 0)}; "
                f"aqp1_first_wave_claim_safe_kcal_ready={aqp1_first_wave_confirmation_s.get('claim_safe_kcal_ready_count', 0)}; "
                f"aqp1_first_wave_follow_on_rows={aqp1_first_wave_follow_on_row_count}; "
                f"aqp1_first_wave_follow_on_focus={aqp1_first_wave_follow_on_primary_focus_ligand}; "
                f"aqp1_first_wave_follow_on_reference={aqp1_first_wave_follow_on_exact_human_reference_ligand}; "
                f"aqp1_first_wave_follow_on_signal={aqp1_first_wave_follow_on_signal}; "
                f"aqp1_first_wave_follow_on_packet_artifact={aqp1_first_wave_follow_on_packet_artifact}; "
                f"aqp1_follow_on_blocker_decomposition_ready={aqp1_follow_on_blocker_decomposition_ready}; "
                f"aqp1_follow_on_blocker_count={aqp1_follow_on_blocker_count}; "
                f"aqp1_follow_on_exact_human_nonbinding_count={aqp1_follow_on_exact_human_nonbinding_count}; "
                f"aqp1_follow_on_exact_target_pair_absent_count={aqp1_follow_on_exact_target_pair_absent_count}; "
                f"aqp1_follow_on_high_or_medium_potential_count={aqp1_follow_on_high_or_medium_potential_count}; "
                f"aqp1_follow_on_claim_safe_kcal_ready_count={aqp1_follow_on_claim_safe_kcal_ready_count}; "
                f"aqp1_follow_on_source_confirmation_primary_focus_ligand={aqp1_follow_on_source_confirmation_primary_focus_ligand}; "
                f"aqp1_follow_on_exact_human_guardrail_ligand={aqp1_follow_on_exact_human_guardrail_ligand}; "
                f"aqp1_follow_on_blocking_signal={aqp1_follow_on_blocking_signal}; "
                f"aqp1_follow_on_next_required_step={aqp1_follow_on_next_required_step}; "
                f"aqp1_follow_on_blocker_decomposition_artifact={aqp1_follow_on_blocker_decomposition_artifact}; "
                f"aqp1_follow_on_source_confirmation_packet_ready={aqp1_follow_on_source_confirmation_packet_ready}; "
                f"aqp1_follow_on_source_confirmation_packet_artifact={aqp1_follow_on_source_confirmation_packet_artifact}; "
                f"transporter_placeholder_burndown_queue_ready={transporter_placeholder_burndown_queue_ready}; "
                f"transporter_placeholder_burndown_queue_artifact={transporter_placeholder_burndown_queue_artifact}; "
                f"aqp1_negative_primary_probe_resolution_ready={aqp1_negative_primary_probe_resolution_ready}; "
                f"aqp1_negative_primary_probe_resolution_artifact={aqp1_negative_primary_probe_resolution_artifact}; "
                f"aqp1_negative_primary_probe_resolution_row_count={aqp1_negative_primary_probe_resolution_row_count}; "
                f"aqp1_negative_primary_probe_resolution_candidate={aqp1_negative_primary_probe_resolution_candidate}; "
                f"aqp1_negative_primary_probe_resolution_solvent_fallback_candidate={aqp1_negative_primary_probe_resolution_solvent_fallback_candidate}; "
                f"aqp1_negative_primary_probe_resolution_decision={aqp1_negative_primary_probe_resolution_decision}; "
                f"glut1_second_wave_source_confirmation_packet_ready={glut1_second_wave_source_confirmation_packet_ready}; "
                f"glut1_second_wave_source_confirmation_packet_artifact={glut1_second_wave_source_confirmation_packet_artifact}; "
                f"glut1_second_wave_source_confirmation_packet_row_count={glut1_second_wave_source_confirmation_packet_row_count}; "
                f"glut1_second_wave_source_confirmation_packet_primary_focus_ligand={glut1_second_wave_source_confirmation_packet_primary_focus_ligand}; "
                f"glut1_second_wave_direct_quantitative_binding_count={glut1_second_wave_direct_quantitative_binding_count}"
                + (
                    f"; {local_engine_summary['local_engine_commercialization_queue_blocker_signal']}"
                    if local_engine_summary["local_engine_commercialization_queue_blocker_signal"]
                    else ""
                )
                + (
                    f"; {ligand_scaleup_summary['ligand_scaleup_blocker_signal']}"
                    if ligand_scaleup_summary["ligand_scaleup_blocker_signal"]
                    else ""
                )
            )
        elif family == "non_kinase_enzyme_ca2":
            extra_signal = (
                f"partial_handoff_rows={partial_s.get('handoff_row_count', 0)}; "
                f"review_only_total={partial_s.get('review_only_row_total', 0)}; "
                f"defer_total={partial_s.get('defer_row_total', 0)}; "
                f"closure_scope={ca2_closure_mode}; "
                f"source_linked={ca2_source_linked_count}; "
                f"direct_negative_evidence={ca2_direct_negative_evidence_count}; "
                f"direct_conflicts={ca2_direct_conflict_count}; "
                f"no_direct_negative={ca2_no_direct_negative_count}; "
                f"authoritative_negative_closure_allowed={ca2_authoritative_negative_closure_allowed}"
            )
        elif family == "nuclear_receptor_pxr":
            extra_signal = (
                f"unresolved_rows={pxr_capture_sheet_s.get('row_count', 0)}; "
                f"capture_pending={pxr_capture_s.get('pending_capture_count', 0)}; "
                f"capture_sources={pxr_capture_s.get('source_linked_count', 0)}; "
                f"supportive_human={pxr_capture_s.get('supportive_target_specific_human_count', 0)}; "
                f"review_only_candidate={pxr_capture_sheet_s.get('review_only_candidate_count', 0)}; "
                f"captured_conflict_or_gap={pxr_capture_s.get('captured_conflict_or_gap_count', 0)}; "
                f"confirm_now={pxr_commit_s.get('confirm_now_count', 0)}; "
                f"must_defer={pxr_commit_s.get('must_remain_deferred_count', pxr_burndown_s.get('must_defer_count', 0))}; "
                f"binder_gap={pxr_commit_s.get('binder_gap_count', 0)}; "
                f"today_open={pxr_burndown_s.get('today_open_now', '')}; "
                f"confirmation_focus={pxr_confirmation_s.get('row_count', 0)}; "
                f"conflict_resolver_focus={pxr_conflict_resolver_s.get('row_count', 0)}; "
                f"exact_dual_mode_conflicts={pxr_conflict_resolver_s.get('exact_human_dual_mode_conflict_count', 0)}; "
                f"qhts_conflicts={pxr_conflict_resolver_s.get('direct_human_qhts_conflict_count', 0)}; "
                f"nonhuman_boundary_contexts={pxr_conflict_resolver_s.get('nonhuman_boundary_context_count', 0)}; "
                f"queue_low_prob_conflicts={evidence_acquisition_s.get('low_probability_conflict_count', 0)}; "
                f"investigator_mode={evidence_investigator_s.get('focus_mode', '')}; "
                f"quant_gap_focus={pxr_quantitative_s.get('row_count', 0)}; "
                f"chembl_zero={pxr_quantitative_s.get('chembl_zero_activity_count', 0)}; "
                f"bindingdb_exact_gap={pxr_quantitative_s.get('bindingdb_exact_gap_count', 0)}; "
                f"signal={pxr_signal}"
            )
        elif family == "gpcr":
            extra_signal = f"endpoint_only={pretest_handoff_s.get('gpcr_ready_endpoint_only', False)}"
        elif family == "idp":
            extra_signal = (
                f"legacy_subset_basis={pretest_handoff_s.get('idp_subset_only', False)}; "
                f"commercial_pretest_ready={pretest_handoff_s.get('idp_commercial_pretest_ready', False)}; "
                f"wider_lane_admitted={pretest_handoff_s.get('idp_wider_shadow_safe_lane_admitted', False)}"
            )
        dashboard_rows.append(
            {
                "priority_lane": lane,
                "family": family,
                "runtime_scope_now": row.get("runtime_scope_now", ""),
                "commercialization_score": row.get("commercialization_score", ""),
                "current_state": (
                    "review_only_conflict_closure_in_progress"
                    if family == "non_kinase_enzyme_ca2"
                    else row.get("current_state", "")
                ),
                "primary_blocker": row.get("primary_blocker", ""),
                "extra_signal": extra_signal,
                "next_required_step": (
                    (
                        "Keep CA2 in review-only/conflict closure. "
                        f"{ca2_direct_conflict_count} rows have direct inhibitor conflict, "
                        f"{ca2_no_direct_negative_count} rows still lack a direct CA2-specific negative source, "
                        f"{ca2_remaining_blank_field} stays blank, and authoritative negative closure is "
                        f"{'allowed' if ca2_authoritative_negative_closure_allowed else 'not allowed'}."
                    )
                    if family == "non_kinase_enzyme_ca2"
                    else (
                        f"Use AQP1 core_binder_01 as the first non-placeholder synchronized candidate-row target. "
                        f"{aqp1_first_wave_dashboard_note or aqp1_operator_provenance_note}"
                        + (
                            f" {local_engine_queue_next_required_step}"
                            if local_engine_queue_next_required_step
                            else f" {local_engine_queue_note}"
                            if local_engine_queue_note
                            else ""
                        )
                        + (
                            f" {ligand_scaleup_summary['ligand_scaleup_next_required_step']}"
                            if ligand_scaleup_summary["ligand_scaleup_next_required_step"]
                            else ""
                        )
                    )
                    if family == "transporter"
                    else row.get("next_required_step", "")
                ),
            }
        )

    summary = {
        "family_count": len(pretest_rows),
        "run_now_count": len(ready_now),
        "prepare_next_count": len(partial_now),
        "manual_review_only_count": len(blocked_now),
        "core_commercial_lane_score": commercialization_s.get("core_commercial_lane_score", pretest_s.get("core_commercial_lane_score", "")),
        "all_category_expansion_score": commercialization_s.get("all_category_expansion_score", pretest_s.get("all_category_expansion_score", "")),
        "execution_sequence_ready": bool(pretest_sequence_s),
        "pretest_command_checklist_ready": bool(pretest_checklist_s),
        "pretest_command_check_count": pretest_checklist_s.get("check_count", 0),
        "partial_handoff_row_count": partial_s.get("handoff_row_count", 0),
        "ca2_closure_mode": ca2_closure_mode,
        "ca2_direct_conflict_row_count": ca2_direct_conflict_count,
        "ca2_no_direct_negative_source_row_count": ca2_no_direct_negative_count,
        "ca2_source_linked_count": ca2_source_linked_count,
        "ca2_direct_negative_evidence_count": ca2_direct_negative_evidence_count,
        "ca2_authoritative_negative_closure_allowed": ca2_authoritative_negative_closure_allowed,
        "ca2_remaining_blank_field": ca2_remaining_blank_field,
        "pxr_unresolved_row_count": pxr_capture_sheet_s.get("row_count", 0),
        "pxr_source_linked_count": pxr_capture_s.get("source_linked_count", 0),
        "pxr_supportive_target_specific_human_count": pxr_capture_s.get("supportive_target_specific_human_count", 0),
        "pxr_review_only_candidate_count": pxr_capture_sheet_s.get("review_only_candidate_count", 0),
        "pxr_captured_conflict_or_gap_count": pxr_capture_s.get("captured_conflict_or_gap_count", 0),
        "pxr_confirm_now_count": pxr_commit_s.get("confirm_now_count", 0),
        "pxr_must_defer_count": pxr_commit_s.get("must_remain_deferred_count", pxr_burndown_s.get("must_defer_count", 0)),
        "pxr_binder_gap_count": pxr_commit_s.get("binder_gap_count", 0),
        "pxr_today_open_now": pxr_burndown_s.get("today_open_now", ""),
        "pxr_signal": pxr_signal,
        "pxr_literature_overlay_ready": bool(pxr_literature_s),
        "pxr_literature_high_signal_row_count": pxr_literature_s.get("high_signal_row_count", 0),
        "pxr_literature_same_sentence_human_row_count": pxr_literature_s.get("same_sentence_human_row_count", 0),
        "pxr_literature_title_direct_nonhuman_row_count": pxr_literature_s.get("title_direct_nonhuman_row_count", 0),
        "pxr_literature_same_sentence_row_count": pxr_literature_s.get("same_sentence_row_count", 0),
        "pxr_literature_review_context_row_count": pxr_literature_s.get("review_context_row_count", 0),
        "pxr_literature_target_only_row_count": pxr_literature_s.get("target_only_row_count", 0),
        "pxr_literature_no_candidate_row_count": pxr_literature_s.get("no_candidate_row_count", 0),
        "pxr_confirmation_packet_ready": bool(pxr_confirmation_s),
        "pxr_confirmation_focus_count": pxr_confirmation_s.get("row_count", 0),
        "pxr_confirmation_supportive_binder_count": pxr_confirmation_s.get(
            "supportive_binder_confirmation_count", 0
        ),
        "pxr_confirmation_conflict_count": pxr_confirmation_s.get("conflict_confirmation_count", 0),
        "pxr_confirmation_primary_focus_ligand": pxr_confirmation_s.get("primary_focus_ligand", ""),
        "pxr_conflict_resolver_packet_ready": bool(pxr_conflict_resolver_s),
        "pxr_conflict_resolver_focus_count": pxr_conflict_resolver_s.get("row_count", 0),
        "pxr_conflict_resolver_primary_focus_ligand": pxr_conflict_resolver_s.get("primary_focus_ligand", ""),
        "pxr_conflict_resolver_pubchem_conflict_count": pxr_conflict_resolver_s.get("pubchem_conflict_count", 0),
        "pxr_conflict_resolver_title_direct_nonhuman_conflict_count": pxr_conflict_resolver_s.get(
            "title_direct_nonhuman_conflict_count", 0
        ),
        "pxr_conflict_resolver_exact_human_dual_mode_conflict_count": pxr_conflict_resolver_s.get(
            "exact_human_dual_mode_conflict_count", 0
        ),
        "pxr_conflict_resolver_direct_human_qhts_conflict_count": pxr_conflict_resolver_s.get(
            "direct_human_qhts_conflict_count", 0
        ),
        "pxr_conflict_resolver_nonhuman_boundary_context_count": pxr_conflict_resolver_s.get(
            "nonhuman_boundary_context_count", 0
        ),
        "pxr_quantitative_provenance_packet_ready": bool(pxr_quantitative_s),
        "pxr_quantitative_provenance_focus_count": pxr_quantitative_s.get("row_count", 0),
        "pxr_quantitative_provenance_primary_focus_ligand": pxr_quantitative_s.get("primary_focus_ligand", ""),
        "pxr_quantitative_provenance_chembl_zero_count": pxr_quantitative_s.get("chembl_zero_activity_count", 0),
        "pxr_quantitative_provenance_bindingdb_exact_gap_count": pxr_quantitative_s.get(
            "bindingdb_exact_gap_count", 0
        ),
        "pxr_quantitative_provenance_value_found_count": pxr_quantitative_s.get("quantitative_value_found_count", 0),
        "manual_burndown_pending_total": manual_s.get("pending_manual_count_total", 0),
        "manual_review_priority_queue_ready": bool(manual_priority_s),
        "manual_review_priority_queue_rows": manual_priority_s.get("queue_row_count", 0),
        "evidence_acquisition_queue_ready": bool(evidence_acquisition_s),
        "evidence_acquisition_queue_rows": evidence_acquisition_s.get("queue_row_count", 0),
        "evidence_acquisition_high_priority_count": evidence_acquisition_s.get("high_priority_count", 0),
        "evidence_acquisition_count_improving_candidate_count": evidence_acquisition_s.get(
            "count_improving_candidate_count", 0
        ),
        "evidence_acquisition_supportive_manual_confirmation_count": evidence_acquisition_s.get(
            "supportive_manual_confirmation_count", 0
        ),
        "evidence_acquisition_actionable_conflict_resolution_count": evidence_acquisition_s.get(
            "actionable_conflict_resolution_count", 0
        ),
        "evidence_acquisition_low_probability_conflict_count": evidence_acquisition_s.get(
            "low_probability_conflict_count", 0
        ),
        "evidence_investigator_packet_ready": bool(evidence_investigator_s),
        "evidence_investigator_focus_count": evidence_investigator_s.get("focus_row_count", 0),
        "evidence_investigator_focus_mode": evidence_investigator_s.get("focus_mode", ""),
        "evidence_investigator_primary_focus_ligand": evidence_investigator_s.get("primary_focus_ligand", ""),
        "evidence_investigator_low_probability_conflict_focus_count": evidence_investigator_s.get(
            "low_probability_conflict_focus_count", 0
        ),
        "evidence_investigator_rows_with_literature_candidates": evidence_investigator_s.get("rows_with_literature_candidates", 0),
        "evidence_investigator_rows_with_high_signal_literature_candidates": evidence_investigator_s.get(
            "rows_with_high_signal_literature_candidates", 0
        ),
        "commercialization_gap_ready": bool(commercialization_gap_s),
        "highest_gap_family": commercialization_gap_s.get("highest_gap_family", ""),
        **local_engine_summary,
        **ligand_scaleup_summary,
        "transporter_seed_row_count": transporter_seed_rows,
        "transporter_pending_manual_verdict_count": int(transporter_s.get("pending_manual_verdict_count", 0) or 0),
        "transporter_placeholder_driven_rows": transporter_placeholder_rows,
        "aqp1_first_seed_evidence_mode": aqp1_first_seed_s.get("evidence_mode", "functional_potency_staged_review_only"),
        "aqp1_first_seed_quantitative_binding_status": aqp1_first_seed_s.get(
            "quantitative_binding_status",
            "quantitative_binding_absent_claim_safe_kcal_missing",
        ),
        "aqp1_quantitative_binding_source_linked_count": aqp1_quant_bind_s.get("source_linked_count", 0),
        "aqp1_quantitative_binding_captured_review_only_gap_count": aqp1_quant_bind_s.get("captured_review_only_gap_count", 0),
        "aqp1_quantitative_binding_supportive_direct_count": aqp1_quant_bind_s.get("supportive_direct_quantitative_binding_count", 0),
        "aqp1_quantitative_binding_kcal_overlay_ready_count": aqp1_quant_bind_s.get("kcal_overlay_ready_count", 0),
        "aqp1_quantitative_binding_signal": aqp1_quant_signal,
        "aqp1_quantitative_provenance_packet_ready": bool(aqp1_quant_prov_s),
        "aqp1_quantitative_provenance_row_count": aqp1_quant_prov_s.get("row_count", 0),
        "aqp1_quantitative_provenance_pubchem_resolved_count": aqp1_quant_prov_s.get("pubchem_resolved_count", 0),
        "aqp1_quantitative_provenance_chembl_exact_match_count": aqp1_quant_prov_s.get("chembl_exact_match_count", 0),
        "aqp1_quantitative_provenance_exact_human_activity_count": aqp1_quant_prov_s.get(
            "exact_human_aqp1_activity_count", 0
        ),
        "aqp1_quantitative_provenance_primary_focus_ligand": aqp1_quant_focus_ligand,
        "aqp1_quantitative_provenance_signal": aqp1_quant_prov_s.get("signal", aqp1_quant_signal),
        "aqp1_first_wave_source_confirmation_packet_ready": bool(aqp1_first_wave_confirmation_s),
        "aqp1_first_wave_source_confirmation_row_count": aqp1_first_wave_confirmation_s.get("row_count", 0),
        "aqp1_first_wave_source_confirmation_primary_focus_ligand": aqp1_first_wave_primary_focus_ligand,
        "aqp1_first_wave_source_confirmation_exact_human_reference_ligand": aqp1_first_wave_exact_human_reference_ligand,
        "aqp1_first_wave_source_confirmation_pubchem_resolved_count": aqp1_first_wave_confirmation_s.get(
            "pubchem_resolved_count", 0
        ),
        "aqp1_first_wave_source_confirmation_exact_pair_absent_count": aqp1_first_wave_confirmation_s.get(
            "exact_pair_absent_count", 0
        ),
        "aqp1_first_wave_source_confirmation_exact_human_activity_reference_count": aqp1_first_wave_confirmation_s.get(
            "exact_human_activity_reference_count", 0
        ),
        "aqp1_first_wave_source_confirmation_claim_safe_kcal_ready_count": aqp1_first_wave_confirmation_s.get(
            "claim_safe_kcal_ready_count", 0
        ),
        "aqp1_follow_on_source_confirmation_packet_ready": aqp1_follow_on_source_confirmation_packet_ready,
        "aqp1_follow_on_source_confirmation_packet_artifact": aqp1_follow_on_source_confirmation_packet_artifact,
        "aqp1_follow_on_source_confirmation_packet_row_count": aqp1_follow_on_source_confirmation_packet_row_count,
        "aqp1_follow_on_source_confirmation_packet_primary_focus_ligand": aqp1_follow_on_source_confirmation_packet_primary_focus_ligand,
        "aqp1_follow_on_source_confirmation_packet_exact_human_reference_ligand": aqp1_follow_on_source_confirmation_packet_exact_human_reference_ligand,
        "transporter_placeholder_burndown_queue_ready": transporter_placeholder_burndown_queue_ready,
        "transporter_placeholder_burndown_queue_artifact": transporter_placeholder_burndown_queue_artifact,
        "transporter_placeholder_burndown_queue_row_count": transporter_placeholder_burndown_queue_row_count,
        "transporter_placeholder_burndown_queue_top_blocker_id": transporter_placeholder_burndown_queue_top_blocker_id,
        "aqp1_negative_primary_probe_resolution_ready": aqp1_negative_primary_probe_resolution_ready,
        "aqp1_negative_primary_probe_resolution_artifact": aqp1_negative_primary_probe_resolution_artifact,
        "aqp1_negative_primary_probe_resolution_row_count": aqp1_negative_primary_probe_resolution_row_count,
        "aqp1_negative_primary_probe_resolution_candidate": aqp1_negative_primary_probe_resolution_candidate,
        "aqp1_negative_primary_probe_resolution_solvent_fallback_candidate": aqp1_negative_primary_probe_resolution_solvent_fallback_candidate,
        "aqp1_negative_primary_probe_resolution_decision": aqp1_negative_primary_probe_resolution_decision,
        "aqp1_negative_primary_probe_resolution_next_required_step": aqp1_negative_primary_probe_resolution_next_required_step,
        "glut1_second_wave_source_confirmation_packet_ready": glut1_second_wave_source_confirmation_packet_ready,
        "glut1_second_wave_source_confirmation_packet_artifact": glut1_second_wave_source_confirmation_packet_artifact,
        "glut1_second_wave_source_confirmation_packet_row_count": glut1_second_wave_source_confirmation_packet_row_count,
        "glut1_second_wave_source_confirmation_packet_primary_focus_ligand": glut1_second_wave_source_confirmation_packet_primary_focus_ligand,
        "glut1_second_wave_source_confirmation_packet_next_required_step": glut1_second_wave_source_confirmation_packet_next_required_step,
        "glut1_second_wave_direct_quantitative_binding_count": glut1_second_wave_direct_quantitative_binding_count,
        "aqp1_first_wave_follow_on_packet_ready": aqp1_first_wave_follow_on_packet_ready,
        "aqp1_first_wave_follow_on_packet_artifact": aqp1_first_wave_follow_on_packet_artifact,
        "aqp1_first_wave_follow_on_row_count": aqp1_first_wave_follow_on_row_count,
        "aqp1_first_wave_follow_on_primary_focus_ligand": aqp1_first_wave_follow_on_primary_focus_ligand,
        "aqp1_first_wave_follow_on_exact_human_reference_ligand": aqp1_first_wave_follow_on_exact_human_reference_ligand,
        "aqp1_first_wave_follow_on_signal": aqp1_first_wave_follow_on_signal,
        "aqp1_follow_on_blocker_decomposition_ready": aqp1_follow_on_blocker_decomposition_ready,
        "aqp1_follow_on_blocker_count": aqp1_follow_on_blocker_count,
        "aqp1_follow_on_exact_human_nonbinding_count": aqp1_follow_on_exact_human_nonbinding_count,
        "aqp1_follow_on_exact_target_pair_absent_count": aqp1_follow_on_exact_target_pair_absent_count,
        "aqp1_follow_on_high_or_medium_potential_count": aqp1_follow_on_high_or_medium_potential_count,
        "aqp1_follow_on_claim_safe_kcal_ready_count": aqp1_follow_on_claim_safe_kcal_ready_count,
        "aqp1_follow_on_source_confirmation_primary_focus_ligand": aqp1_follow_on_source_confirmation_primary_focus_ligand,
        "aqp1_follow_on_exact_human_guardrail_ligand": aqp1_follow_on_exact_human_guardrail_ligand,
        "aqp1_follow_on_blocking_signal": aqp1_follow_on_blocking_signal,
        "aqp1_follow_on_next_required_step": aqp1_follow_on_next_required_step,
        "aqp1_follow_on_blocker_decomposition_artifact": aqp1_follow_on_blocker_decomposition_artifact,
        "aqp1_first_wave_source_confirmation_next_required_step": aqp1_first_wave_next_required_step,
        "aqp1_operator_provenance_note": aqp1_operator_provenance_note,
        "aqp1_first_seed_remaining_unresolved_fields": aqp1_first_seed_s.get(
            "remaining_unresolved_fields",
            "replacement_reference_binding_kcal_mol",
        ),
        "next_required_step": (
            f"Run only the four families already marked pretest-ready within their safe scope. Keep CA2 in review-only/conflict evidence-closure mode, keep PXR in evidence-closure mode, and keep transporter in seed-row blocker-closure mode. For AQP1, {aqp1_first_wave_dashboard_note or aqp1_operator_provenance_note}"
            + (
                f" {local_engine_queue_next_required_step}"
                if local_engine_queue_next_required_step
                else f" {local_engine_queue_note}"
                if local_engine_queue_note
                else ""
            )
            + (
                f" {ligand_scaleup_summary['ligand_scaleup_next_required_step']}"
                if ligand_scaleup_summary["ligand_scaleup_next_required_step"]
                else ""
            )
            if transporter_phase == "seed_row_blocker_closure"
            else "Run only the four families already marked pretest-ready within their safe scope. Keep CA2 in review-only/conflict evidence-closure mode, keep PXR in evidence-closure mode, and keep transporter in manual-review mode until manual verdicts and packet evidence mature."
            + (
                f" {local_engine_queue_next_required_step}"
                if local_engine_queue_next_required_step
                else f" {local_engine_queue_note}"
                if local_engine_queue_note
                else ""
            )
            + (
                f" {ligand_scaleup_summary['ligand_scaleup_next_required_step']}"
                if ligand_scaleup_summary["ligand_scaleup_next_required_step"]
                else ""
            )
        ),
    }
    return {"summary": summary, "rows": dashboard_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Execution Handoff Dashboard",
        "",
        f"- family_count: `{s['family_count']}`",
        f"- run_now_count: `{s['run_now_count']}`",
        f"- prepare_next_count: `{s['prepare_next_count']}`",
        f"- manual_review_only_count: `{s['manual_review_only_count']}`",
        f"- core_commercial_lane_score: `{s['core_commercial_lane_score']}`",
        f"- all_category_expansion_score: `{s['all_category_expansion_score']}`",
        f"- execution_sequence_ready: `{s['execution_sequence_ready']}`",
        f"- pretest_command_checklist_ready: `{s['pretest_command_checklist_ready']}`",
        f"- pretest_command_check_count: `{s['pretest_command_check_count']}`",
        f"- partial_handoff_row_count: `{s['partial_handoff_row_count']}`",
        f"- ca2_closure_mode: `{s['ca2_closure_mode']}`",
        f"- ca2_direct_conflict_row_count: `{s['ca2_direct_conflict_row_count']}`",
        f"- ca2_no_direct_negative_source_row_count: `{s['ca2_no_direct_negative_source_row_count']}`",
        f"- ca2_source_linked_count: `{s['ca2_source_linked_count']}`",
        f"- ca2_direct_negative_evidence_count: `{s['ca2_direct_negative_evidence_count']}`",
        f"- ca2_authoritative_negative_closure_allowed: `{s['ca2_authoritative_negative_closure_allowed']}`",
        f"- ca2_remaining_blank_field: `{s['ca2_remaining_blank_field']}`",
        f"- pxr_unresolved_row_count: `{s['pxr_unresolved_row_count']}`",
        f"- pxr_source_linked_count: `{s['pxr_source_linked_count']}`",
        f"- pxr_supportive_target_specific_human_count: `{s['pxr_supportive_target_specific_human_count']}`",
        f"- pxr_review_only_candidate_count: `{s['pxr_review_only_candidate_count']}`",
        f"- pxr_captured_conflict_or_gap_count: `{s['pxr_captured_conflict_or_gap_count']}`",
        f"- pxr_confirm_now_count: `{s['pxr_confirm_now_count']}`",
        f"- pxr_must_defer_count: `{s['pxr_must_defer_count']}`",
        f"- pxr_binder_gap_count: `{s['pxr_binder_gap_count']}`",
        f"- pxr_today_open_now: `{s['pxr_today_open_now']}`",
        f"- pxr_signal: `{s['pxr_signal']}`",
        f"- pxr_literature_overlay_ready: `{s['pxr_literature_overlay_ready']}`",
        f"- pxr_literature_high_signal_row_count: `{s['pxr_literature_high_signal_row_count']}`",
        f"- pxr_literature_same_sentence_human_row_count: `{s['pxr_literature_same_sentence_human_row_count']}`",
        f"- pxr_literature_title_direct_nonhuman_row_count: `{s['pxr_literature_title_direct_nonhuman_row_count']}`",
        f"- pxr_literature_same_sentence_row_count: `{s['pxr_literature_same_sentence_row_count']}`",
        f"- pxr_literature_review_context_row_count: `{s['pxr_literature_review_context_row_count']}`",
        f"- pxr_literature_target_only_row_count: `{s['pxr_literature_target_only_row_count']}`",
        f"- pxr_literature_no_candidate_row_count: `{s['pxr_literature_no_candidate_row_count']}`",
        f"- pxr_confirmation_packet_ready: `{s['pxr_confirmation_packet_ready']}`",
        f"- pxr_confirmation_focus_count: `{s['pxr_confirmation_focus_count']}`",
        f"- pxr_confirmation_supportive_binder_count: `{s['pxr_confirmation_supportive_binder_count']}`",
        f"- pxr_confirmation_conflict_count: `{s['pxr_confirmation_conflict_count']}`",
        f"- pxr_confirmation_primary_focus_ligand: `{s['pxr_confirmation_primary_focus_ligand']}`",
        f"- pxr_conflict_resolver_packet_ready: `{s['pxr_conflict_resolver_packet_ready']}`",
        f"- pxr_conflict_resolver_focus_count: `{s['pxr_conflict_resolver_focus_count']}`",
        f"- pxr_conflict_resolver_primary_focus_ligand: `{s['pxr_conflict_resolver_primary_focus_ligand']}`",
        f"- pxr_conflict_resolver_pubchem_conflict_count: `{s['pxr_conflict_resolver_pubchem_conflict_count']}`",
        f"- pxr_conflict_resolver_title_direct_nonhuman_conflict_count: `{s['pxr_conflict_resolver_title_direct_nonhuman_conflict_count']}`",
        f"- pxr_conflict_resolver_exact_human_dual_mode_conflict_count: `{s['pxr_conflict_resolver_exact_human_dual_mode_conflict_count']}`",
        f"- pxr_conflict_resolver_direct_human_qhts_conflict_count: `{s['pxr_conflict_resolver_direct_human_qhts_conflict_count']}`",
        f"- pxr_conflict_resolver_nonhuman_boundary_context_count: `{s['pxr_conflict_resolver_nonhuman_boundary_context_count']}`",
        f"- pxr_quantitative_provenance_packet_ready: `{s['pxr_quantitative_provenance_packet_ready']}`",
        f"- pxr_quantitative_provenance_focus_count: `{s['pxr_quantitative_provenance_focus_count']}`",
        f"- pxr_quantitative_provenance_primary_focus_ligand: `{s['pxr_quantitative_provenance_primary_focus_ligand']}`",
        f"- pxr_quantitative_provenance_chembl_zero_count: `{s['pxr_quantitative_provenance_chembl_zero_count']}`",
        f"- pxr_quantitative_provenance_bindingdb_exact_gap_count: `{s['pxr_quantitative_provenance_bindingdb_exact_gap_count']}`",
        f"- pxr_quantitative_provenance_value_found_count: `{s['pxr_quantitative_provenance_value_found_count']}`",
        f"- manual_burndown_pending_total: `{s['manual_burndown_pending_total']}`",
        f"- manual_review_priority_queue_ready: `{s['manual_review_priority_queue_ready']}`",
        f"- manual_review_priority_queue_rows: `{s['manual_review_priority_queue_rows']}`",
        f"- evidence_acquisition_queue_ready: `{s['evidence_acquisition_queue_ready']}`",
        f"- evidence_acquisition_queue_rows: `{s['evidence_acquisition_queue_rows']}`",
        f"- evidence_acquisition_high_priority_count: `{s['evidence_acquisition_high_priority_count']}`",
        f"- evidence_acquisition_count_improving_candidate_count: `{s['evidence_acquisition_count_improving_candidate_count']}`",
        f"- evidence_acquisition_supportive_manual_confirmation_count: `{s['evidence_acquisition_supportive_manual_confirmation_count']}`",
        f"- evidence_acquisition_actionable_conflict_resolution_count: `{s['evidence_acquisition_actionable_conflict_resolution_count']}`",
        f"- evidence_acquisition_low_probability_conflict_count: `{s['evidence_acquisition_low_probability_conflict_count']}`",
        f"- evidence_investigator_packet_ready: `{s['evidence_investigator_packet_ready']}`",
        f"- evidence_investigator_focus_count: `{s['evidence_investigator_focus_count']}`",
        f"- evidence_investigator_focus_mode: `{s['evidence_investigator_focus_mode']}`",
        f"- evidence_investigator_primary_focus_ligand: `{s['evidence_investigator_primary_focus_ligand']}`",
        f"- evidence_investigator_low_probability_conflict_focus_count: `{s['evidence_investigator_low_probability_conflict_focus_count']}`",
        f"- evidence_investigator_rows_with_literature_candidates: `{s['evidence_investigator_rows_with_literature_candidates']}`",
        f"- evidence_investigator_rows_with_high_signal_literature_candidates: `{s['evidence_investigator_rows_with_high_signal_literature_candidates']}`",
        f"- commercialization_gap_ready: `{s['commercialization_gap_ready']}`",
        f"- highest_gap_family: `{s['highest_gap_family']}`",
        f"- local_engine_commercialization_queue_ready: `{s['local_engine_commercialization_queue_ready']}`",
        f"- local_engine_commercialization_queue_artifact: `{s['local_engine_commercialization_queue_artifact']}`",
        f"- local_engine_commercialization_queue_top_priority_id: `{s['local_engine_commercialization_queue_top_priority_id']}`",
        f"- local_engine_commercialization_queue_top_priority_status: `{s['local_engine_commercialization_queue_top_priority_status']}`",
        f"- local_engine_commercialization_queue_blocked_count: `{s['local_engine_commercialization_queue_blocked_count']}`",
        f"- local_engine_commercialization_queue_nightly_gate_burndown_artifact: `{s['local_engine_commercialization_queue_nightly_gate_burndown_artifact']}`",
        f"- local_engine_commercialization_queue_nightly_gate_primary_metric: `{s['local_engine_commercialization_queue_nightly_gate_primary_metric']}`",
        f"- local_engine_commercialization_queue_nightly_gate_primary_delta: `{s['local_engine_commercialization_queue_nightly_gate_primary_delta']}`",
        f"- local_engine_commercialization_queue_blocker_note: `{s['local_engine_commercialization_queue_blocker_note']}`",
        f"- ligand_scaleup_blocker_ready: `{s['ligand_scaleup_blocker_ready']}`",
        f"- ligand_scaleup_blocked: `{s['ligand_scaleup_blocked']}`",
        f"- ligand_scaleup_blocker_note: `{s['ligand_scaleup_blocker_note']}`",
        f"- ligand_scaleup_next_required_step: `{s['ligand_scaleup_next_required_step']}`",
        f"- transporter_seed_row_count: `{s['transporter_seed_row_count']}`",
        f"- transporter_placeholder_driven_rows: `{s['transporter_placeholder_driven_rows']}`",
        f"- aqp1_first_seed_evidence_mode: `{s['aqp1_first_seed_evidence_mode']}`",
        f"- aqp1_first_seed_quantitative_binding_status: `{s['aqp1_first_seed_quantitative_binding_status']}`",
        f"- aqp1_quantitative_binding_source_linked_count: `{s['aqp1_quantitative_binding_source_linked_count']}`",
        f"- aqp1_quantitative_binding_captured_review_only_gap_count: `{s['aqp1_quantitative_binding_captured_review_only_gap_count']}`",
        f"- aqp1_quantitative_binding_supportive_direct_count: `{s['aqp1_quantitative_binding_supportive_direct_count']}`",
        f"- aqp1_quantitative_binding_kcal_overlay_ready_count: `{s['aqp1_quantitative_binding_kcal_overlay_ready_count']}`",
        f"- aqp1_quantitative_binding_signal: `{s['aqp1_quantitative_binding_signal']}`",
        f"- aqp1_quantitative_provenance_packet_ready: `{s['aqp1_quantitative_provenance_packet_ready']}`",
        f"- aqp1_quantitative_provenance_row_count: `{s['aqp1_quantitative_provenance_row_count']}`",
        f"- aqp1_quantitative_provenance_pubchem_resolved_count: `{s['aqp1_quantitative_provenance_pubchem_resolved_count']}`",
        f"- aqp1_quantitative_provenance_chembl_exact_match_count: `{s['aqp1_quantitative_provenance_chembl_exact_match_count']}`",
        f"- aqp1_quantitative_provenance_exact_human_activity_count: `{s['aqp1_quantitative_provenance_exact_human_activity_count']}`",
        f"- aqp1_quantitative_provenance_primary_focus_ligand: `{s['aqp1_quantitative_provenance_primary_focus_ligand']}`",
        f"- aqp1_quantitative_provenance_signal: `{s['aqp1_quantitative_provenance_signal']}`",
        f"- aqp1_first_wave_source_confirmation_packet_ready: `{s['aqp1_first_wave_source_confirmation_packet_ready']}`",
        f"- aqp1_first_wave_source_confirmation_row_count: `{s['aqp1_first_wave_source_confirmation_row_count']}`",
        f"- aqp1_first_wave_source_confirmation_primary_focus_ligand: `{s['aqp1_first_wave_source_confirmation_primary_focus_ligand']}`",
        f"- aqp1_first_wave_source_confirmation_exact_human_reference_ligand: `{s['aqp1_first_wave_source_confirmation_exact_human_reference_ligand']}`",
        f"- aqp1_first_wave_source_confirmation_pubchem_resolved_count: `{s['aqp1_first_wave_source_confirmation_pubchem_resolved_count']}`",
        f"- aqp1_first_wave_source_confirmation_exact_pair_absent_count: `{s['aqp1_first_wave_source_confirmation_exact_pair_absent_count']}`",
        f"- aqp1_first_wave_source_confirmation_exact_human_activity_reference_count: `{s['aqp1_first_wave_source_confirmation_exact_human_activity_reference_count']}`",
        f"- aqp1_first_wave_source_confirmation_claim_safe_kcal_ready_count: `{s['aqp1_first_wave_source_confirmation_claim_safe_kcal_ready_count']}`",
        f"- aqp1_follow_on_source_confirmation_packet_ready: `{s['aqp1_follow_on_source_confirmation_packet_ready']}`",
        f"- aqp1_follow_on_source_confirmation_packet_artifact: `{s['aqp1_follow_on_source_confirmation_packet_artifact']}`",
        f"- aqp1_follow_on_source_confirmation_packet_row_count: `{s['aqp1_follow_on_source_confirmation_packet_row_count']}`",
        f"- aqp1_follow_on_source_confirmation_packet_primary_focus_ligand: `{s['aqp1_follow_on_source_confirmation_packet_primary_focus_ligand']}`",
        f"- aqp1_follow_on_source_confirmation_packet_exact_human_reference_ligand: `{s['aqp1_follow_on_source_confirmation_packet_exact_human_reference_ligand']}`",
        f"- transporter_placeholder_burndown_queue_ready: `{s['transporter_placeholder_burndown_queue_ready']}`",
        f"- transporter_placeholder_burndown_queue_artifact: `{s['transporter_placeholder_burndown_queue_artifact']}`",
        f"- transporter_placeholder_burndown_queue_row_count: `{s['transporter_placeholder_burndown_queue_row_count']}`",
        f"- transporter_placeholder_burndown_queue_top_blocker_id: `{s['transporter_placeholder_burndown_queue_top_blocker_id']}`",
        f"- aqp1_negative_primary_probe_resolution_ready: `{s['aqp1_negative_primary_probe_resolution_ready']}`",
        f"- aqp1_negative_primary_probe_resolution_artifact: `{s['aqp1_negative_primary_probe_resolution_artifact']}`",
        f"- aqp1_negative_primary_probe_resolution_row_count: `{s['aqp1_negative_primary_probe_resolution_row_count']}`",
        f"- aqp1_negative_primary_probe_resolution_candidate: `{s['aqp1_negative_primary_probe_resolution_candidate']}`",
        f"- aqp1_negative_primary_probe_resolution_solvent_fallback_candidate: `{s['aqp1_negative_primary_probe_resolution_solvent_fallback_candidate']}`",
        f"- aqp1_negative_primary_probe_resolution_decision: `{s['aqp1_negative_primary_probe_resolution_decision']}`",
        f"- aqp1_negative_primary_probe_resolution_next_required_step: `{s['aqp1_negative_primary_probe_resolution_next_required_step']}`",
        f"- glut1_second_wave_source_confirmation_packet_ready: `{s['glut1_second_wave_source_confirmation_packet_ready']}`",
        f"- glut1_second_wave_source_confirmation_packet_artifact: `{s['glut1_second_wave_source_confirmation_packet_artifact']}`",
        f"- glut1_second_wave_source_confirmation_packet_row_count: `{s['glut1_second_wave_source_confirmation_packet_row_count']}`",
        f"- glut1_second_wave_source_confirmation_packet_primary_focus_ligand: `{s['glut1_second_wave_source_confirmation_packet_primary_focus_ligand']}`",
        f"- glut1_second_wave_source_confirmation_packet_next_required_step: `{s['glut1_second_wave_source_confirmation_packet_next_required_step']}`",
        f"- glut1_second_wave_direct_quantitative_binding_count: `{s['glut1_second_wave_direct_quantitative_binding_count']}`",
        f"- aqp1_first_wave_follow_on_packet_ready: `{s['aqp1_first_wave_follow_on_packet_ready']}`",
        f"- aqp1_first_wave_follow_on_packet_artifact: `{s['aqp1_first_wave_follow_on_packet_artifact']}`",
        f"- aqp1_first_wave_follow_on_row_count: `{s['aqp1_first_wave_follow_on_row_count']}`",
        f"- aqp1_first_wave_follow_on_primary_focus_ligand: `{s['aqp1_first_wave_follow_on_primary_focus_ligand']}`",
        f"- aqp1_first_wave_follow_on_exact_human_reference_ligand: `{s['aqp1_first_wave_follow_on_exact_human_reference_ligand']}`",
        f"- aqp1_first_wave_follow_on_signal: `{s['aqp1_first_wave_follow_on_signal']}`",
        f"- aqp1_follow_on_blocker_decomposition_ready: `{s['aqp1_follow_on_blocker_decomposition_ready']}`",
        f"- aqp1_follow_on_blocker_count: `{s['aqp1_follow_on_blocker_count']}`",
        f"- aqp1_follow_on_exact_human_nonbinding_count: `{s['aqp1_follow_on_exact_human_nonbinding_count']}`",
        f"- aqp1_follow_on_exact_target_pair_absent_count: `{s['aqp1_follow_on_exact_target_pair_absent_count']}`",
        f"- aqp1_follow_on_high_or_medium_potential_count: `{s['aqp1_follow_on_high_or_medium_potential_count']}`",
        f"- aqp1_follow_on_claim_safe_kcal_ready_count: `{s['aqp1_follow_on_claim_safe_kcal_ready_count']}`",
        f"- aqp1_follow_on_source_confirmation_primary_focus_ligand: `{s['aqp1_follow_on_source_confirmation_primary_focus_ligand']}`",
        f"- aqp1_follow_on_exact_human_guardrail_ligand: `{s['aqp1_follow_on_exact_human_guardrail_ligand']}`",
        f"- aqp1_follow_on_blocking_signal: `{s['aqp1_follow_on_blocking_signal']}`",
        f"- aqp1_follow_on_next_required_step: `{s['aqp1_follow_on_next_required_step']}`",
        f"- aqp1_follow_on_blocker_decomposition_artifact: `{s['aqp1_follow_on_blocker_decomposition_artifact']}`",
        f"- aqp1_first_wave_source_confirmation_next_required_step: `{s['aqp1_first_wave_source_confirmation_next_required_step']}`",
        f"- aqp1_operator_provenance_note: `{s['aqp1_operator_provenance_note']}`",
        f"- aqp1_first_seed_remaining_unresolved_fields: `{s['aqp1_first_seed_remaining_unresolved_fields']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Family Lanes",
        "",
        "| priority_lane | family | runtime_scope_now | commercialization_score | current_state | primary_blocker | extra_signal | next_required_step |",
        "| --- | --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['priority_lane']}` | `{row['family']}` | `{row['runtime_scope_now']}` | {row['commercialization_score']} | `{row['current_state']}` | `{row['primary_blocker']}` | `{row['extra_signal']}` | {row['next_required_step']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a single execution handoff dashboard across pretest-ready, partial-authoritative, and manual-review lanes.")
    parser.add_argument("--pretest-json", default=DEFAULT_PRETEST_JSON)
    parser.add_argument("--pretest-handoff-json", default=DEFAULT_PRETEST_HANDOFF_JSON)
    parser.add_argument("--pretest-sequence-json", default=DEFAULT_PRETEST_SEQUENCE_JSON)
    parser.add_argument("--pretest-command-checklist-json", default=DEFAULT_PRETEST_COMMAND_CHECKLIST_JSON)
    parser.add_argument("--partial-handoff-json", default=DEFAULT_PARTIAL_HANDOFF_JSON)
    parser.add_argument("--transporter-apply-draft-json", default=DEFAULT_TRANSPORTER_APPLY_DRAFT_JSON)
    parser.add_argument("--ca2-capture-sheet-json", default=DEFAULT_CA2_CAPTURE_SHEET_JSON)
    parser.add_argument("--ca2-capture-intake-json", default=DEFAULT_CA2_CAPTURE_INTAKE_JSON)
    parser.add_argument("--ca2-commit-packet-json", default=DEFAULT_CA2_COMMIT_PACKET_JSON)
    parser.add_argument("--pxr-capture-sheet-json", default=DEFAULT_PXR_CAPTURE_SHEET_JSON)
    parser.add_argument("--pxr-capture-intake-json", default=DEFAULT_PXR_CAPTURE_INTAKE_JSON)
    parser.add_argument("--pxr-commit-packet-json", default=DEFAULT_PXR_COMMIT_PACKET_JSON)
    parser.add_argument("--pxr-burndown-json", default=DEFAULT_PXR_BURNDOWN_JSON)
    parser.add_argument("--transporter-capture-intake-json", default=DEFAULT_TRANSPORTER_CAPTURE_INTAKE_JSON)
    parser.add_argument("--aqp1-first-seed-row-packet-json", default=DEFAULT_AQP1_FIRST_SEED_ROW_PACKET_JSON)
    parser.add_argument("--aqp1-external-seed-json", default=DEFAULT_AQP1_EXTERNAL_SEED_JSON)
    parser.add_argument("--aqp1-quantitative-binding-capture-intake-json", default=DEFAULT_AQP1_QUANT_BIND_INTAKE_JSON)
    parser.add_argument(
        "--aqp1-quantitative-provenance-packet-json",
        default=DEFAULT_AQP1_QUANTITATIVE_PROVENANCE_PACKET_JSON,
    )
    parser.add_argument(
        "--aqp1-first-wave-source-confirmation-packet-json",
        default=DEFAULT_AQP1_FIRST_WAVE_SOURCE_CONFIRMATION_PACKET_JSON,
    )
    parser.add_argument(
        "--aqp1-first-wave-follow-on-packet-json",
        default=DEFAULT_AQP1_FIRST_WAVE_FOLLOW_ON_PACKET_JSON,
    )
    parser.add_argument(
        "--aqp1-follow-on-blocker-decomposition-json",
        default=DEFAULT_AQP1_FOLLOW_ON_BLOCKER_DECOMPOSITION_JSON,
    )
    parser.add_argument(
        "--aqp1-follow-on-source-confirmation-packet-json",
        default="runs/aqp1_follow_on_source_confirmation_packet_current.json",
    )
    parser.add_argument(
        "--transporter-placeholder-burndown-queue-json",
        default="runs/transporter_placeholder_burndown_queue_current.json",
    )
    parser.add_argument(
        "--aqp1-negative-primary-probe-resolution-packet-json",
        default=DEFAULT_AQP1_NEGATIVE_PRIMARY_PROBE_RESOLUTION_PACKET_JSON,
    )
    parser.add_argument(
        "--glut1-second-wave-source-confirmation-packet-json",
        default=DEFAULT_GLUT1_SECOND_WAVE_SOURCE_CONFIRMATION_PACKET_JSON,
    )
    parser.add_argument("--manual-burndown-json", default=DEFAULT_MANUAL_BURNDOWN_JSON)
    parser.add_argument("--manual-priority-queue-json", default=DEFAULT_MANUAL_PRIORITY_QUEUE_JSON)
    parser.add_argument("--evidence-acquisition-queue-json", default=DEFAULT_EVIDENCE_ACQUISITION_QUEUE_JSON)
    parser.add_argument("--evidence-investigator-packet-json", default=DEFAULT_EVIDENCE_INVESTIGATOR_PACKET_JSON)
    parser.add_argument("--pxr-literature-overlay-json", default=DEFAULT_PXR_LITERATURE_OVERLAY_JSON)
    parser.add_argument("--pxr-confirmation-packet-json", default=DEFAULT_PXR_CONFIRMATION_PACKET_JSON)
    parser.add_argument("--pxr-conflict-resolver-packet-json", default=DEFAULT_PXR_CONFLICT_RESOLVER_PACKET_JSON)
    parser.add_argument(
        "--pxr-quantitative-provenance-packet-json",
        default=DEFAULT_PXR_QUANTITATIVE_PROVENANCE_PACKET_JSON,
    )
    parser.add_argument("--commercialization-json", default=DEFAULT_COMMERCIALIZATION_JSON)
    parser.add_argument("--commercialization-gap-json", default=DEFAULT_COMMERCIALIZATION_GAP_JSON)
    parser.add_argument(
        "--local-engine-commercialization-queue-json",
        default=DEFAULT_LOCAL_ENGINE_QUEUE_JSON,
    )
    parser.add_argument("--ligand-scaleup-suite-status-json", default=DEFAULT_LIGAND_SCALEUP_SUITE_STATUS_JSON)
    parser.add_argument(
        "--ligand-scaleup-benchmark-summary-json",
        default=DEFAULT_LIGAND_SCALEUP_BENCHMARK_SUMMARY_JSON,
    )
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.pretest_json),
        _load_json(args.pretest_handoff_json),
        _load_json(args.pretest_sequence_json),
        _load_json(args.pretest_command_checklist_json),
        _load_json(args.partial_handoff_json),
        _load_json(args.transporter_apply_draft_json),
        _maybe_load_json(args.ca2_capture_intake_json),
        _maybe_load_json(args.pxr_capture_intake_json),
        _maybe_load_json(args.transporter_capture_intake_json),
        _maybe_load_json(args.aqp1_first_seed_row_packet_json),
        _maybe_load_json(args.aqp1_external_seed_json),
        _load_json(args.manual_burndown_json),
        _load_json(args.manual_priority_queue_json),
        _maybe_load_json(args.evidence_acquisition_queue_json),
        _maybe_load_json(args.evidence_investigator_packet_json),
        _maybe_load_json(args.pxr_literature_overlay_json),
        _maybe_load_json(args.pxr_confirmation_packet_json),
        _maybe_load_json(args.pxr_quantitative_provenance_packet_json),
        _load_json(args.commercialization_json),
        _load_json(args.commercialization_gap_json),
        aqp1_quantitative_binding_capture_intake=_maybe_load_json(args.aqp1_quantitative_binding_capture_intake_json),
        aqp1_quantitative_provenance_packet=_maybe_load_json(args.aqp1_quantitative_provenance_packet_json),
        aqp1_first_wave_source_confirmation_packet=_maybe_load_json(args.aqp1_first_wave_source_confirmation_packet_json),
        aqp1_first_wave_follow_on_packet=_maybe_load_json(args.aqp1_first_wave_follow_on_packet_json),
        aqp1_follow_on_blocker_decomposition=_maybe_load_json(args.aqp1_follow_on_blocker_decomposition_json),
        aqp1_follow_on_source_confirmation_packet=_maybe_load_json(
            args.aqp1_follow_on_source_confirmation_packet_json
        ),
        transporter_placeholder_burndown_queue=_maybe_load_json(args.transporter_placeholder_burndown_queue_json),
        aqp1_negative_primary_probe_resolution_packet=_maybe_load_json(
            args.aqp1_negative_primary_probe_resolution_packet_json
        ),
        glut1_second_wave_source_confirmation_packet=_maybe_load_json(
            args.glut1_second_wave_source_confirmation_packet_json
        ),
        ca2_capture_sheet=_maybe_load_json(args.ca2_capture_sheet_json),
        ca2_commit_packet=_maybe_load_json(args.ca2_commit_packet_json),
        pxr_capture_sheet=_maybe_load_json(args.pxr_capture_sheet_json),
        pxr_commit_packet=_maybe_load_json(args.pxr_commit_packet_json),
        pxr_burndown_console=_maybe_load_json(args.pxr_burndown_json),
        pxr_conflict_resolver_packet=_maybe_load_json(args.pxr_conflict_resolver_packet_json),
        ligand_scaleup_suite_status=_maybe_load_json(args.ligand_scaleup_suite_status_json),
        ligand_scaleup_benchmark_summary=_maybe_load_json(args.ligand_scaleup_benchmark_summary_json),
        local_engine_commercialization_queue=_maybe_load_json(args.local_engine_commercialization_queue_json),
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
