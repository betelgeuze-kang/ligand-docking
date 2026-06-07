#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_GPCR_DECISION_JSON = "runs/gpcr_residual_apply_decision_narrow_v2_current.json"
DEFAULT_GPCR_CHEMBL50_V3_DECISION_JSON = "runs/gpcr_residual_chembl50_v3_decision_current.json"
DEFAULT_GPCR_CHEMBL50_V4_DECISION_JSON = "runs/gpcr_residual_chembl50_v4_decision_current.json"
DEFAULT_GPCR_CHEMBL50_V4_APPLY_DECISION_JSON = "runs/gpcr_residual_chembl50_v4_apply_decision_current.json"
DEFAULT_GPCR_APPLY_SAFE_ENDPOINT_JSON = "runs/gpcr_apply_safe_endpoint_current.json"
DEFAULT_GLOBAL_TARGET_LIST_JSON = "runs/global_residual_correction_target_list_current.json"
DEFAULT_CASCADE_ENVELOPE_JSON = "runs/ligand_cascade_speedup_envelope_current.json"
DEFAULT_CA2_READINESS_JSON = "runs/ca2_packet_replacement_readiness_current.json"
DEFAULT_PXR_READINESS_JSON = "runs/pxr_packet_fill_readiness_current.json"
DEFAULT_CROSSFAMILY_SHADOW_SCAFFOLD_JSON = "runs/cross_family_locked_decoy_shadow_current.json"
DEFAULT_CROSSFAMILY_SHADOW_DECISION_JSON = "runs/cross_family_locked_decoy_shadow_decision_current.json"
DEFAULT_CA2_PENDING_DISPOSITION_JSON = "runs/ca2_pending_row_disposition_current.json"
DEFAULT_PXR_PENDING_DISPOSITION_JSON = "runs/pxr_pending_row_disposition_current.json"
DEFAULT_TRANSPORTER_READINESS_JSON = "runs/transporter_membrane_readiness_current.json"
DEFAULT_AQP1_P0_PLAN_JSON = "runs/aqp1_p0_packet_plan_current.json"
DEFAULT_AQP1_MANUAL_REVIEW_QUEUE_JSON = "runs/aqp1_manual_review_queue_current.json"
DEFAULT_AQP1_LOCAL_EVIDENCE_NOTE_JSON = "runs/aqp1_local_evidence_note_current.json"
DEFAULT_AQP1_EXTERNAL_EVIDENCE_SEED_JSON = "runs/aqp1_external_evidence_seed_current.json"
DEFAULT_AQP1_VERDICT_JSON = "runs/aqp1_candidate_verdict_sheet_current.json"
DEFAULT_GLUT1_LOCAL_EVIDENCE_NOTE_JSON = "runs/glut1_local_evidence_note_current.json"
DEFAULT_GLUT1_EXTERNAL_EVIDENCE_SEED_JSON = "runs/glut1_external_evidence_seed_current.json"
DEFAULT_GLUT1_VERDICT_JSON = "runs/glut1_candidate_verdict_sheet_current.json"
DEFAULT_BINDER_PROGRESS_JSON = "runs/transporter_binder_verdict_progress_current.json"
DEFAULT_BINDER_RUBRIC_JSON = "runs/transporter_binder_decision_rubric_current.json"
DEFAULT_BINDER_NOTE_TEMPLATES_JSON = "runs/transporter_manual_decision_note_templates_current.json"
DEFAULT_BINDER_PREFILL_PREVIEW_JSON = "runs/transporter_manual_verdict_prefill_preview_current.json"
DEFAULT_BINDER_PACKETS_JSON = "runs/transporter_manual_verdict_packets_current.json"
DEFAULT_AQP1_APPLY_DRAFT_JSON = "runs/aqp1_manual_verdict_apply_draft_current.json"
DEFAULT_GLUT1_APPLY_DRAFT_JSON = "runs/glut1_manual_verdict_apply_draft_current.json"
DEFAULT_AQP1_NEGATIVE_PACKET_JSON = "runs/aqp1_negative_review_handoff_packet_current.json"
DEFAULT_GLUT1_NEGATIVE_PACKET_JSON = "runs/glut1_negative_review_handoff_packet_current.json"
DEFAULT_TRANSPORTER_DASHBOARD_JSON = "runs/transporter_manual_review_dashboard_current.json"
DEFAULT_TRANSPORTER_SEED_ROW_BOARD_JSON = "runs/transporter_seed_row_promotion_board_current.json"
DEFAULT_TRANSPORTER_FIT_DONOR_POLICY_DECISION_JSON = "runs/transporter_fit_donor_policy_decision_current.json"
DEFAULT_TRANSPORTER_WAVE_DECISION_JSON = "runs/transporter_wave_decision_current.json"
DEFAULT_TRANSPORTER_DONOR_REOPEN_CHECKLIST_JSON = "runs/transporter_donor_policy_reopen_checklist_current.json"
DEFAULT_TRANSPORTER_REVIEWER_DAY_PLAN_JSON = "runs/transporter_reviewer_day_plan_current.json"
DEFAULT_TRANSPORTER_NEGATIVE_REVIEWER_DAY_PLAN_JSON = "runs/transporter_negative_reviewer_day_plan_current.json"
DEFAULT_IDP_PAGE4_SLICE_JSON = "runs/idp_page4_feature_state_v1_shadow_slice_current.json"
DEFAULT_IDP_TP53_SLICE_JSON = "runs/idp_tp53_feature_state_v1_shadow_slice_current.json"
DEFAULT_IDP_LITERATURE_SUMMARY_JSON = "runs/idp_feature_state_literature_anchor_summary_current.json"
DEFAULT_IDP_FEATURE_MASK_COMPARISON_JSON = "runs/idp_literature_anchor_feature_mask_comparison_current.json"
DEFAULT_IDP_SUBSET_DECISION_JSON = "runs/idp_feature_state_subset_decision_current.json"
DEFAULT_IDP_COMMERCIAL_PRETEST_JSON = "runs/idp_commercial_pretest_packet_current.json"
DEFAULT_IDP_COMMERCIAL_PRETEST_DECISION_JSON = "runs/idp_commercial_pretest_decision_current.json"
DEFAULT_IDP_BROADER_SHADOW_RESULT_JSON = "runs/idp_broader_shadow_result_current.json"
DEFAULT_IDP_BROADER_SHADOW_DECISION_JSON = "runs/idp_broader_shadow_decision_current.json"
DEFAULT_IDP_BROADER_PROMOTION_RESOLUTION_JSON = "runs/idp_broader_promotion_resolution_current.json"
DEFAULT_OUT_JSON = "runs/cross_family_residual_shadow_layer_current.json"
DEFAULT_OUT_CSV = "runs/cross_family_residual_shadow_layer_current.csv"
DEFAULT_OUT_MD = "runs/cross_family_residual_shadow_layer_current.md"


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


def _latest_cross_family_shadow_run() -> dict[str, Any]:
    return _latest_protocol_run("cross_family_locked_decoy_shadow_v1")


def _latest_protocol_run(protocol_id: str, set_spec_substr: str = "") -> dict[str, Any]:
    run_paths = sorted(
        glob.glob(str((ROOT / "runs/external_validation_blind_runs/external_validation_blind_runs_*").resolve())),
        key=os.path.getmtime,
        reverse=True,
    )
    for run_path in run_paths:
        state_path = Path(run_path) / "state.json"
        if not state_path.exists():
            continue
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if str(state.get("protocol_id", "")).strip() != protocol_id:
            continue
        if set_spec_substr and set_spec_substr not in str(state.get("set_spec_json", "")):
            continue
        status = str(state.get("status", "") or "")
        summary_path = Path(run_path) / "summary.json"
        if summary_path.exists():
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                summary = {}
            summary_status = str(summary.get("status", "") or "").strip()
            if summary_status:
                status = summary_status
        return {
            "run_root": str(Path(run_path).resolve()),
            "status": status,
        }
    return {"run_root": "", "status": ""}


def _enrich_payload_with_runtime_context(
    payload: dict[str, Any],
    aqp1_plan: dict[str, Any],
    aqp1_manual_review_queue: dict[str, Any] | None = None,
    aqp1_local_evidence_note: dict[str, Any] | None = None,
    aqp1_external_evidence_seed: dict[str, Any] | None = None,
    aqp1_verdict: dict[str, Any] | None = None,
    glut1_local_evidence_note: dict[str, Any] | None = None,
    glut1_external_evidence_seed: dict[str, Any] | None = None,
    glut1_verdict: dict[str, Any] | None = None,
    transporter_binder_progress: dict[str, Any] | None = None,
    transporter_binder_rubric: dict[str, Any] | None = None,
    transporter_binder_note_templates: dict[str, Any] | None = None,
    transporter_binder_prefill_preview: dict[str, Any] | None = None,
    transporter_binder_packets: dict[str, Any] | None = None,
    aqp1_apply_draft: dict[str, Any] | None = None,
    glut1_apply_draft: dict[str, Any] | None = None,
    aqp1_negative_packet: dict[str, Any] | None = None,
    glut1_negative_packet: dict[str, Any] | None = None,
    transporter_dashboard: dict[str, Any] | None = None,
    transporter_seed_row_board: dict[str, Any] | None = None,
    transporter_fit_donor_policy_decision: dict[str, Any] | None = None,
    transporter_wave_decision: dict[str, Any] | None = None,
    transporter_donor_reopen_checklist: dict[str, Any] | None = None,
    transporter_reviewer_day_plan: dict[str, Any] | None = None,
    transporter_negative_reviewer_day_plan: dict[str, Any] | None = None,
    gpcr_apply_safe_endpoint: dict[str, Any] | None = None,
    idp_commercial_pretest: dict[str, Any] | None = None,
    idp_commercial_pretest_decision: dict[str, Any] | None = None,
    idp_broader_shadow_result: dict[str, Any] | None = None,
    idp_broader_shadow_decision: dict[str, Any] | None = None,
    idp_broader_promotion_resolution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gpcr_v3_run = _latest_protocol_run(
        "gpcr_residual_locked_decoy_ab_shadow_only_v1",
        "gpcr_residual_chembl50_v3_locked_decoy_ab_current",
    )
    gpcr_v4_run = _latest_protocol_run(
        "gpcr_residual_locked_decoy_ab_shadow_only_v1",
        "gpcr_residual_chembl50_v4_locked_decoy_ab_current",
    )
    gpcr_v4_apply_run = _latest_protocol_run(
        "gpcr_residual_locked_decoy_ab_apply_v1",
        "gpcr_residual_chembl50_v4_apply_locked_decoy_ab_current",
    )
    gpcr_v3_decision = _maybe_load_json(DEFAULT_GPCR_CHEMBL50_V3_DECISION_JSON)
    gpcr_v4_decision = _maybe_load_json(DEFAULT_GPCR_CHEMBL50_V4_DECISION_JSON)
    gpcr_v4_apply_decision = _maybe_load_json(DEFAULT_GPCR_CHEMBL50_V4_APPLY_DECISION_JSON)
    gpcr_v3_decision_text = str(gpcr_v3_decision.get("decision", "") or "").strip()
    gpcr_v4_decision_text = str(gpcr_v4_decision.get("decision", "") or "").strip()
    gpcr_v4_apply_decision_text = str(gpcr_v4_apply_decision.get("decision", "") or "").strip()
    gpcr_v3_status = str(gpcr_v3_run.get("status", "") or "").strip().lower()
    gpcr_v4_status = str(gpcr_v4_run.get("status", "") or "").strip().lower()
    gpcr_v4_apply_status = str(gpcr_v4_apply_run.get("status", "") or "").strip().lower()
    gpcr_v3_running = gpcr_v3_status == "running"
    gpcr_v4_running = gpcr_v4_status == "running"
    gpcr_v4_apply_running = gpcr_v4_apply_status == "running"
    aqp1_summary = dict(aqp1_plan.get("summary", {}) or {})
    aqp1_next = aqp1_summary.get("next_priority_steps", []) or []
    aqp1_next_text = ", ".join(str(x) for x in aqp1_next[:3])
    aqp1_review_summary = dict((aqp1_manual_review_queue or {}).get("summary", {}) or {})
    aqp1_evidence_summary = dict((aqp1_local_evidence_note or {}).get("summary", {}) or {})
    aqp1_external_summary = dict((aqp1_external_evidence_seed or {}).get("summary", {}) or {})
    aqp1_verdict_summary = dict((aqp1_verdict or {}).get("summary", {}) or {})
    glut1_evidence_summary = dict((glut1_local_evidence_note or {}).get("summary", {}) or {})
    glut1_external_summary = dict((glut1_external_evidence_seed or {}).get("summary", {}) or {})
    glut1_verdict_summary = dict((glut1_verdict or {}).get("summary", {}) or {})
    transporter_binder_progress_summary = dict((transporter_binder_progress or {}).get("summary", {}) or {})
    transporter_binder_rubric_summary = dict((transporter_binder_rubric or {}).get("summary", {}) or {})
    transporter_binder_note_templates_summary = dict((transporter_binder_note_templates or {}).get("summary", {}) or {})
    transporter_binder_prefill_preview_summary = dict((transporter_binder_prefill_preview or {}).get("summary", {}) or {})
    transporter_binder_packets_summary = dict((transporter_binder_packets or {}).get("summary", {}) or {})
    aqp1_apply_draft_summary = dict((aqp1_apply_draft or {}).get("summary", {}) or {})
    glut1_apply_draft_summary = dict((glut1_apply_draft or {}).get("summary", {}) or {})
    aqp1_negative_packet_summary = dict((aqp1_negative_packet or {}).get("summary", {}) or {})
    glut1_negative_packet_summary = dict((glut1_negative_packet or {}).get("summary", {}) or {})
    transporter_dashboard_summary = dict((transporter_dashboard or {}).get("summary", {}) or {})
    transporter_seed_row_board_summary = dict((transporter_seed_row_board or {}).get("summary", {}) or {})
    transporter_donor_summary = dict((transporter_fit_donor_policy_decision or {}).get("summary", {}) or {})
    transporter_wave_summary = dict((transporter_wave_decision or {}).get("summary", {}) or {})
    transporter_donor_reopen_summary = dict((transporter_donor_reopen_checklist or {}).get("summary", {}) or {})
    transporter_reviewer_day_plan_summary = dict((transporter_reviewer_day_plan or {}).get("summary", {}) or {})
    transporter_negative_reviewer_day_plan_summary = dict((transporter_negative_reviewer_day_plan or {}).get("summary", {}) or {})
    gpcr_endpoint_summary = dict((gpcr_apply_safe_endpoint or {}).get("summary", {}) or {})
    idp_commercial_pretest_summary = dict((idp_commercial_pretest or {}).get("summary", {}) or {})
    idp_commercial_pretest_decision_summary = dict((idp_commercial_pretest_decision or {}).get("summary", {}) or {})
    idp_broader_shadow_result_summary = dict((idp_broader_shadow_result or {}).get("summary", {}) or {})
    idp_broader_shadow_decision_summary = dict((idp_broader_shadow_decision or {}).get("summary", {}) or {})
    idp_broader_promotion_resolution_summary = dict((idp_broader_promotion_resolution or {}).get("summary", {}) or {})
    idp_effective_decision_summary = idp_broader_promotion_resolution_summary or idp_broader_shadow_decision_summary or idp_commercial_pretest_decision_summary
    aqp1_review_only = aqp1_review_summary.get("review_only_negative_count")
    aqp1_defer = aqp1_review_summary.get("defer_binder_count")

    for row in payload.get("rows", []):
        if row.get("family") == "gpcr":
            base_signal = str(row.get("readiness_signal", "") or "")
            if gpcr_v3_status:
                row["readiness_signal"] = f"{base_signal}; chembl50_v3_shadow={gpcr_v3_status}"
            if gpcr_v3_decision_text:
                row["readiness_signal"] = f"{row['readiness_signal']}; chembl50_v3_decision={gpcr_v3_decision_text}"
            if gpcr_v4_status:
                row["readiness_signal"] = f"{row['readiness_signal']}; chembl50_v4_shadow={gpcr_v4_status}"
            if gpcr_v4_decision_text:
                row["readiness_signal"] = f"{row['readiness_signal']}; chembl50_v4_decision={gpcr_v4_decision_text}"
            if gpcr_v4_apply_status:
                row["readiness_signal"] = f"{row['readiness_signal']}; chembl50_v4_apply={gpcr_v4_apply_status}"
            if gpcr_v4_apply_decision_text:
                row["readiness_signal"] = f"{row['readiness_signal']}; chembl50_v4_apply_decision={gpcr_v4_apply_decision_text}"
            if gpcr_endpoint_summary:
                row["readiness_signal"] = (
                    f"{row['readiness_signal']}; "
                    f"apply_safe_endpoint={gpcr_endpoint_summary.get('endpoint_status', '')}"
                )
            if gpcr_v4_apply_running:
                row["current_state"] = "chembl50_v4_apply_running"
                row["next_required_step"] = (
                    "Finish the running chembl50_v4 locked-decoy apply slice, then compare it against baseline and v4 shadow before any router discussion."
                )
            elif gpcr_v4_apply_status == "completed" and gpcr_v4_apply_decision_text == "no_go_for_100k_router":
                if gpcr_endpoint_summary.get("endpoint_status") == "locked_decoy_apply_safe_router_blocked":
                    row["current_state"] = "chembl50_v4_apply_safe_endpoint_router_blocked"
                    row["next_required_step"] = str(
                        gpcr_endpoint_summary.get(
                            "next_required_step",
                            "Keep the 100k router blocked while treating chembl50_v4 apply as a locked-decoy apply-safe GPCR endpoint.",
                        )
                    )
                else:
                    row["current_state"] = "chembl50_v4_apply_completed_router_blocked"
                    row["next_required_step"] = (
                        "Keep the 100k router blocked. chembl50_v4 apply stayed pass-safe and improved EF1 on chembl50, but it still introduces a small PR regression versus baseline, so it is not ready for router promotion."
                    )
            elif gpcr_v4_apply_status == "completed" and gpcr_v4_apply_decision_text == "go_for_100k_router":
                row["current_state"] = "chembl50_v4_apply_completed_router_candidate"
                row["next_required_step"] = (
                    "chembl50_v4 apply completed without regressions; this is the first GPCR candidate eligible for a guarded 100k router trial."
                )
            elif gpcr_v4_running:
                row["current_state"] = "chembl50_v4_shadow_running"
                row["next_required_step"] = (
                    "Finish the running chembl50_v4 locked-decoy shadow slice, then compare it against v3 shadow/apply before any new GPCR apply or router promotion."
                )
            elif gpcr_v4_status == "completed" and gpcr_v4_decision_text == "go_for_locked_decoy_apply_trial":
                row["current_state"] = "chembl50_v4_shadow_completed_apply_candidate"
                row["next_required_step"] = (
                    "Use chembl50_v4 as the next locked-decoy apply trial candidate; it preserves gpcr_core_full at baseline while keeping a small chembl50 OOD PR gain. Keep 100k router promotion blocked."
                )
            elif gpcr_v3_running:
                row["current_state"] = "chembl50_v3_shadow_running"
                row["next_required_step"] = (
                    "Finish the running chembl50_v3 locked-decoy shadow slice, then compare it against narrow_v2 before any new GPCR apply or router promotion."
                )
            elif gpcr_v3_status == "completed" and gpcr_v3_decision_text == "go_for_locked_decoy_apply_trial":
                row["next_required_step"] = "Use chembl50_v3 as the next locked-decoy apply trial candidate; keep 100k router promotion blocked until apply-mode proves safe."
        elif row.get("family") == "transporter":
            base_signal = str(row.get("readiness_signal", "") or "")
            todo_count = aqp1_summary.get("todo_count")
            if todo_count is not None:
                row["readiness_signal"] = f"{base_signal}; aqp1_todo_count={todo_count}"
            if aqp1_review_only is not None and aqp1_defer is not None:
                row["readiness_signal"] = f"{row['readiness_signal']}; aqp1_review_only={aqp1_review_only}; aqp1_defer={aqp1_defer}"
                row["current_state"] = "draft_packet_review_in_progress"
            if aqp1_evidence_summary:
                row["readiness_signal"] = (
                    f"{row['readiness_signal']}; "
                    f"aqp1_local_binder_curated={aqp1_evidence_summary.get('local_target_specific_binder_evidence_curated', False)}; "
                    f"aqp1_local_negative_curated={aqp1_evidence_summary.get('local_quantitative_negative_evidence_curated', False)}; "
                    f"aqp1_fit_donor={aqp1_evidence_summary.get('temporary_fit_donor_target', '')}"
                )
                row["current_state"] = "draft_packet_review_local_evidence_blocked"
            if aqp1_external_summary:
                row["readiness_signal"] = (
                    f"{row['readiness_signal']}; "
                    f"aqp1_external_candidate_count={aqp1_external_summary.get('candidate_count', 0)}; "
                    f"aqp1_external_first_wave_candidate_count={aqp1_external_summary.get('draft_first_wave_candidate_count', 0)}; "
                    f"aqp1_external_status={aqp1_external_summary.get('endpoint_status', '')}"
                )
                row["current_state"] = "draft_packet_external_seeded_local_evidence_blocked"
            if aqp1_verdict_summary:
                row["readiness_signal"] = (
                    f"{row['readiness_signal']}; "
                    f"aqp1_keep_review_only={aqp1_verdict_summary.get('keep_review_only_count', 0)}; "
                    f"aqp1_caution_only={aqp1_verdict_summary.get('caution_only_count', 0)}; "
                    f"aqp1_defer={aqp1_verdict_summary.get('defer_count', 0)}"
                )
            if glut1_evidence_summary:
                row["readiness_signal"] = (
                    f"{row['readiness_signal']}; "
                    f"glut1_local_binder_curated={glut1_evidence_summary.get('local_target_specific_binder_evidence_curated', False)}; "
                    f"glut1_local_negative_curated={glut1_evidence_summary.get('local_quantitative_negative_evidence_curated', False)}; "
                    f"glut1_fit_donor={glut1_evidence_summary.get('temporary_fit_donor_target', '')}"
                )
            if glut1_external_summary:
                row["readiness_signal"] = (
                    f"{row['readiness_signal']}; "
                    f"glut1_external_candidate_count={glut1_external_summary.get('candidate_count', 0)}; "
                    f"glut1_external_second_wave_candidate_count={glut1_external_summary.get('draft_second_wave_candidate_count', 0)}; "
                    f"glut1_external_status={glut1_external_summary.get('endpoint_status', '')}"
                )
            if glut1_verdict_summary:
                row["readiness_signal"] = (
                    f"{row['readiness_signal']}; "
                    f"glut1_keep_review_only={glut1_verdict_summary.get('keep_review_only_count', 0)}; "
                    f"glut1_caution_only={glut1_verdict_summary.get('caution_only_count', 0)}; "
                    f"glut1_defer={glut1_verdict_summary.get('defer_count', 0)}"
                )
            if transporter_binder_progress_summary:
                row["readiness_signal"] = (
                    f"{row['readiness_signal']}; "
                    f"transporter_binder_pending={transporter_binder_progress_summary.get('pending_manual_verdict_count', 0)}; "
                    f"transporter_binder_done={transporter_binder_progress_summary.get('completed_manual_verdict_count', 0)}"
                )
            if transporter_binder_rubric_summary:
                row["readiness_signal"] = (
                    f"{row['readiness_signal']}; "
                    f"transporter_binder_rubric_ready={bool(transporter_binder_rubric_summary)}"
                )
            if transporter_binder_note_templates_summary:
                row["readiness_signal"] = (
                    f"{row['readiness_signal']}; "
                    f"transporter_binder_note_templates_ready={bool(transporter_binder_note_templates_summary)}; "
                    f"transporter_binder_note_template_count={transporter_binder_note_templates_summary.get('template_row_count', 0)}"
                )
            if transporter_binder_prefill_preview_summary:
                row["readiness_signal"] = (
                    f"{row['readiness_signal']}; "
                    f"transporter_binder_prefill_preview_ready={bool(transporter_binder_prefill_preview_summary)}; "
                    f"transporter_binder_prefill_preview_count={transporter_binder_prefill_preview_summary.get('preview_row_count', 0)}"
                )
            if transporter_binder_packets_summary:
                row["readiness_signal"] = (
                    f"{row['readiness_signal']}; "
                    f"transporter_binder_packets_ready={bool(transporter_binder_packets_summary)}; "
                    f"transporter_binder_packet_target_count={transporter_binder_packets_summary.get('target_count', 0)}"
                )
            if aqp1_apply_draft_summary or glut1_apply_draft_summary:
                row["readiness_signal"] = (
                    f"{row['readiness_signal']}; "
                    f"transporter_binder_apply_drafts_ready={bool(aqp1_apply_draft_summary or glut1_apply_draft_summary)}; "
                    f"transporter_binder_apply_draft_target_count="
                    f"{sum(1 for draft in (aqp1_apply_draft_summary, glut1_apply_draft_summary) if draft)}"
                )
            if aqp1_negative_packet_summary or glut1_negative_packet_summary:
                row["readiness_signal"] = (
                    f"{row['readiness_signal']}; "
                    f"transporter_negative_packets_ready={bool(aqp1_negative_packet_summary or glut1_negative_packet_summary)}; "
                    f"transporter_negative_packet_target_count="
                    f"{sum(1 for pkt in (aqp1_negative_packet_summary, glut1_negative_packet_summary) if pkt)}"
                )
            if transporter_donor_summary:
                row["readiness_signal"] = (
                    f"{row['readiness_signal']}; "
                    f"transporter_donor_policy={transporter_donor_summary.get('decision_status', '')}"
                )
            if transporter_wave_summary:
                row["readiness_signal"] = (
                    f"{row['readiness_signal']}; "
                    f"transporter_wave={transporter_wave_summary.get('decision_status', '')}"
                )
            if transporter_donor_reopen_summary:
                row["readiness_signal"] = (
                    f"{row['readiness_signal']}; "
                    f"transporter_donor_reopen_ready={transporter_donor_reopen_summary.get('reopen_ready', False)}"
                )
            if transporter_reviewer_day_plan_summary:
                row["readiness_signal"] = (
                    f"{row['readiness_signal']}; "
                    f"transporter_reviewer_day_plan_ready={bool(transporter_reviewer_day_plan_summary)}"
                )
            if transporter_negative_reviewer_day_plan_summary:
                row["readiness_signal"] = (
                    f"{row['readiness_signal']}; "
                    f"transporter_negative_day_plan_ready={bool(transporter_negative_reviewer_day_plan_summary)}"
                )
            if transporter_dashboard_summary:
                row["readiness_signal"] = (
                    f"{row['readiness_signal']}; "
                    f"transporter_current_phase={transporter_dashboard_summary.get('current_phase', '')}; "
                    f"transporter_seed_row_fill_safe_prefill_count={transporter_dashboard_summary.get('aqp1_seed_row_fill_safe_prefill_count', 0)}"
                )
                if transporter_dashboard_summary.get("binder_completed_manual_verdict_count", 0):
                    row["current_state"] = "manual_verdict_complete_blocker_closure_seed_row_promotion"
            if transporter_seed_row_board_summary:
                row["readiness_signal"] = (
                    f"{row['readiness_signal']}; "
                    f"transporter_today_seed_target={transporter_seed_row_board_summary.get('today_seed_target', '')}; "
                    f"transporter_seed_now_count={transporter_seed_row_board_summary.get('seed_now_count', 0)}"
                )
                row["next_required_step"] = (
                    "Keep transporter non-authoritative. "
                    + str(transporter_seed_row_board_summary.get("next_required_step", "") or row.get("next_required_step", ""))
                )
            if aqp1_next_text:
                row["next_required_step"] = (
                    "Keep transporter in scaffold mode; AQP1 stays first-wave and GLUT1 stays second-wave while both remain local-evidence blocked and the family donor policy stays temporarily pinned to EGFR for scaffold-only use. Use AQP1 external seeds as manual-review inputs only, then burn down AQP1 first: "
                    f"{aqp1_next_text}."
                )
                if transporter_seed_row_board_summary:
                    row["next_required_step"] = (
                        "Keep transporter non-authoritative. Use AQP1 core_binder_01 as the first seed-row promotion target, keep GLUT1 second-wave, and "
                        "do not revisit donor policy until placeholder-driven rows and blocker checks are reduced."
                    )
        elif row.get("family") == "idp" and idp_commercial_pretest_summary:
            row["current_state"] = (
                str(idp_effective_decision_summary.get("status", "")).strip()
                or "controlled_shadow_only_commercial_pretest_ready_broader_corrected_promotion_blocked"
            )
            row["readiness_signal"] = (
                f"{row['readiness_signal']}; "
                f"commercial_pretest_status={idp_effective_decision_summary.get('status', idp_commercial_pretest_summary.get('status', ''))}; "
                f"commercial_pretest_core={idp_commercial_pretest_summary.get('core_target_count', 0)}; "
                f"commercial_pretest_watchlist={idp_commercial_pretest_summary.get('watchlist_target_count', 0)}"
            )
            if idp_broader_shadow_result_summary:
                row["readiness_signal"] = (
                    f"{row['readiness_signal']}; "
                    f"broader_shadow_completed={idp_broader_shadow_result_summary.get('true_broader_shadow_completed', False)}; "
                    f"broader_shadow_passed={idp_broader_shadow_result_summary.get('true_broader_shadow_passed', False)}; "
                    f"page4_fold_pass={idp_broader_shadow_result_summary.get('page4_fold_pass', False)}; "
                    f"tau_k18_fold_pass={idp_broader_shadow_result_summary.get('tau_k18_fold_pass', False)}"
                )
            if idp_effective_decision_summary:
                row["readiness_signal"] = (
                    f"{row['readiness_signal']}; "
                    f"shadow_safe_retained={idp_effective_decision_summary.get('shadow_safe_retained', False)}; "
                    f"blocking_target={idp_effective_decision_summary.get('blocking_target', '')}; "
                    f"blocking_class={idp_effective_decision_summary.get('blocking_class', '')}"
                )
            if idp_commercial_pretest_decision_summary and not idp_effective_decision_summary:
                row["readiness_signal"] = (
                    f"{row['readiness_signal']}; "
                    f"shadow_safe_retained={idp_commercial_pretest_decision_summary.get('shadow_safe_retained', False)}; "
                    f"blocking_target={idp_commercial_pretest_decision_summary.get('blocking_target', '')}"
                )
            row["next_required_step"] = (
                str(idp_effective_decision_summary.get("next_required_step", "")).strip()
                or
                str(idp_commercial_pretest_decision_summary.get("next_required_step", "")).strip()
                or str(idp_commercial_pretest_summary.get("next_required_step", "")).strip()
                or row.get("next_required_step", "")
            )

    summary = dict(payload.get("summary", {}) or {})
    summary["gpcr_chembl50_v3_shadow_run_root"] = gpcr_v3_run.get("run_root", "")
    summary["gpcr_chembl50_v3_shadow_status"] = gpcr_v3_run.get("status", "")
    summary["gpcr_chembl50_v3_decision"] = gpcr_v3_decision_text
    summary["gpcr_chembl50_v4_shadow_run_root"] = gpcr_v4_run.get("run_root", "")
    summary["gpcr_chembl50_v4_shadow_status"] = gpcr_v4_run.get("status", "")
    summary["gpcr_chembl50_v4_decision"] = gpcr_v4_decision_text
    summary["gpcr_chembl50_v4_apply_run_root"] = gpcr_v4_apply_run.get("run_root", "")
    summary["gpcr_chembl50_v4_apply_status"] = gpcr_v4_apply_run.get("status", "")
    summary["gpcr_chembl50_v4_apply_decision"] = gpcr_v4_apply_decision_text
    if aqp1_summary:
        summary["aqp1_p0_todo_count"] = aqp1_summary.get("todo_count")
        summary["aqp1_next_priority_steps"] = aqp1_summary.get("next_priority_steps", [])
    if aqp1_review_summary:
        summary["aqp1_manual_review_only_count"] = aqp1_review_only
        summary["aqp1_manual_defer_count"] = aqp1_defer
    if aqp1_evidence_summary:
        summary["aqp1_local_evidence_status"] = aqp1_evidence_summary.get("endpoint_status", "")
        summary["aqp1_local_binder_curated"] = aqp1_evidence_summary.get("local_target_specific_binder_evidence_curated", False)
        summary["aqp1_local_negative_curated"] = aqp1_evidence_summary.get("local_quantitative_negative_evidence_curated", False)
    if aqp1_external_summary:
        summary["aqp1_external_candidate_count"] = aqp1_external_summary.get("candidate_count", 0)
        summary["aqp1_external_first_wave_candidate_count"] = aqp1_external_summary.get("draft_first_wave_candidate_count", 0)
        summary["aqp1_external_status"] = aqp1_external_summary.get("endpoint_status", "")
    if aqp1_verdict_summary:
        summary["aqp1_keep_review_only_count"] = aqp1_verdict_summary.get("keep_review_only_count", 0)
        summary["aqp1_caution_only_count"] = aqp1_verdict_summary.get("caution_only_count", 0)
        summary["aqp1_defer_count"] = aqp1_verdict_summary.get("defer_count", 0)
    if glut1_evidence_summary:
        summary["glut1_local_evidence_status"] = glut1_evidence_summary.get("endpoint_status", "")
        summary["glut1_local_binder_curated"] = glut1_evidence_summary.get("local_target_specific_binder_evidence_curated", False)
        summary["glut1_local_negative_curated"] = glut1_evidence_summary.get("local_quantitative_negative_evidence_curated", False)
    if glut1_external_summary:
        summary["glut1_external_candidate_count"] = glut1_external_summary.get("candidate_count", 0)
        summary["glut1_external_second_wave_candidate_count"] = glut1_external_summary.get("draft_second_wave_candidate_count", 0)
        summary["glut1_external_status"] = glut1_external_summary.get("endpoint_status", "")
    if glut1_verdict_summary:
        summary["glut1_keep_review_only_count"] = glut1_verdict_summary.get("keep_review_only_count", 0)
        summary["glut1_caution_only_count"] = glut1_verdict_summary.get("caution_only_count", 0)
        summary["glut1_defer_count"] = glut1_verdict_summary.get("defer_count", 0)
    if transporter_binder_progress_summary:
        summary["transporter_binder_pending_manual_verdict_count"] = transporter_binder_progress_summary.get("pending_manual_verdict_count", 0)
        summary["transporter_binder_completed_manual_verdict_count"] = transporter_binder_progress_summary.get("completed_manual_verdict_count", 0)
    if transporter_binder_rubric_summary:
        summary["transporter_binder_rubric_ready"] = bool(transporter_binder_rubric_summary)
    if transporter_binder_note_templates_summary:
        summary["transporter_binder_note_templates_ready"] = bool(transporter_binder_note_templates_summary)
        summary["transporter_binder_note_template_count"] = transporter_binder_note_templates_summary.get("template_row_count", 0)
    if transporter_binder_prefill_preview_summary:
        summary["transporter_binder_prefill_preview_ready"] = bool(transporter_binder_prefill_preview_summary)
        summary["transporter_binder_prefill_preview_count"] = transporter_binder_prefill_preview_summary.get("preview_row_count", 0)
    if transporter_binder_packets_summary:
        summary["transporter_binder_packets_ready"] = bool(transporter_binder_packets_summary)
        summary["transporter_binder_packet_target_count"] = transporter_binder_packets_summary.get("target_count", 0)
    if aqp1_apply_draft_summary or glut1_apply_draft_summary:
        summary["transporter_binder_apply_drafts_ready"] = bool(aqp1_apply_draft_summary or glut1_apply_draft_summary)
        summary["transporter_binder_apply_draft_target_count"] = sum(
            1 for draft in (aqp1_apply_draft_summary, glut1_apply_draft_summary) if draft
        )
        summary["transporter_binder_apply_draft_prefill_count"] = (
            aqp1_apply_draft_summary.get("draft_prefill_count", 0)
            + glut1_apply_draft_summary.get("draft_prefilled_count", 0)
        )
    if aqp1_negative_packet_summary or glut1_negative_packet_summary:
        summary["transporter_negative_packets_ready"] = bool(aqp1_negative_packet_summary or glut1_negative_packet_summary)
        summary["transporter_negative_packet_target_count"] = sum(
            1 for pkt in (aqp1_negative_packet_summary, glut1_negative_packet_summary) if pkt
        )
        summary["transporter_negative_slot_count_total"] = (
            aqp1_negative_packet_summary.get("negative_slot_count", 0)
            + glut1_negative_packet_summary.get("negative_slot_count", 0)
        )
    if transporter_donor_summary:
        summary["transporter_fit_donor_policy_status"] = transporter_donor_summary.get("decision_status", "")
    if transporter_wave_summary:
        summary["transporter_wave_decision_status"] = transporter_wave_summary.get("decision_status", "")
    if transporter_donor_reopen_summary:
        summary["transporter_donor_reopen_ready"] = transporter_donor_reopen_summary.get("reopen_ready", False)
        summary["transporter_donor_reopen_blocked_check_count"] = transporter_donor_reopen_summary.get("blocked_check_count", 0)
    if transporter_reviewer_day_plan_summary:
        summary["transporter_reviewer_day_plan_ready"] = bool(transporter_reviewer_day_plan_summary)
    if transporter_negative_reviewer_day_plan_summary:
        summary["transporter_negative_reviewer_day_plan_ready"] = bool(transporter_negative_reviewer_day_plan_summary)
        summary["transporter_negative_review_row_count"] = transporter_negative_reviewer_day_plan_summary.get("negative_slot_review_row_count", 0)
    if transporter_dashboard_summary:
        summary["transporter_current_phase"] = transporter_dashboard_summary.get("current_phase", "")
        summary["transporter_seed_row_fill_safe_prefill_count"] = transporter_dashboard_summary.get("aqp1_seed_row_fill_safe_prefill_count", 0)
    if transporter_seed_row_board_summary:
        summary["transporter_today_seed_target"] = transporter_seed_row_board_summary.get("today_seed_target", "")
        summary["transporter_seed_now_count"] = transporter_seed_row_board_summary.get("seed_now_count", 0)
    if gpcr_endpoint_summary:
        summary["gpcr_apply_safe_endpoint_status"] = gpcr_endpoint_summary.get("endpoint_status", "")
    if idp_commercial_pretest_summary:
        summary["idp_commercial_pretest_status"] = idp_effective_decision_summary.get("status", idp_commercial_pretest_summary.get("status", ""))
        summary["idp_commercial_pretest_core_target_count"] = idp_commercial_pretest_summary.get("core_target_count", 0)
        summary["idp_commercial_pretest_watchlist_target_count"] = idp_commercial_pretest_summary.get("watchlist_target_count", 0)
    if idp_broader_shadow_result_summary:
        summary["idp_true_broader_shadow_completed"] = idp_broader_shadow_result_summary.get("true_broader_shadow_completed", False)
        summary["idp_true_broader_shadow_passed"] = idp_broader_shadow_result_summary.get("true_broader_shadow_passed", False)
        summary["idp_page4_fold_pass"] = idp_broader_shadow_result_summary.get("page4_fold_pass", False)
        summary["idp_tau_k18_fold_pass"] = idp_broader_shadow_result_summary.get("tau_k18_fold_pass", False)
    if idp_effective_decision_summary:
        summary["idp_broader_shadow_decision"] = idp_effective_decision_summary.get("decision", "")
        summary["idp_broader_shadow_blocking_class"] = idp_effective_decision_summary.get("blocking_class", "")
        summary["idp_commercial_shadow_safe_retained"] = idp_effective_decision_summary.get("shadow_safe_retained", False)
        summary["idp_commercial_blocking_target"] = idp_effective_decision_summary.get("blocking_target", "")
    elif idp_commercial_pretest_decision_summary:
        summary["idp_commercial_shadow_safe_retained"] = idp_commercial_pretest_decision_summary.get("shadow_safe_retained", False)
        summary["idp_commercial_blocking_target"] = idp_commercial_pretest_decision_summary.get("blocking_target", "")
    payload["summary"] = summary
    return payload


def build_payload(
    gpcr_decision: dict[str, Any],
    global_target_list: dict[str, Any],
    cascade_envelope: dict[str, Any],
    ca2_readiness: dict[str, Any],
    pxr_readiness: dict[str, Any],
    crossfamily_shadow_scaffold: dict[str, Any],
    crossfamily_shadow_decision: dict[str, Any],
    ca2_pending_disposition: dict[str, Any],
    pxr_pending_disposition: dict[str, Any],
    transporter_readiness: dict[str, Any],
    idp_page4_slice: dict[str, Any],
    idp_tp53_slice: dict[str, Any],
    idp_literature_summary: dict[str, Any],
    idp_feature_mask_comparison: dict[str, Any],
    idp_subset_decision: dict[str, Any],
) -> dict[str, Any]:
    crossfamily_run = _latest_cross_family_shadow_run()
    crossfamily_status = str(crossfamily_run.get("status", "") or "").strip().lower()
    crossfamily_running = crossfamily_status == "running"
    crossfamily_completed = crossfamily_status == "completed"
    crossfamily_decision_summary = dict(crossfamily_shadow_decision.get("summary", {}) or {})
    crossfamily_decision = str(crossfamily_decision_summary.get("decision", "") or "")
    ca2_pending_summary = dict(ca2_pending_disposition.get("summary", {}) or {})
    pxr_pending_summary = dict(pxr_pending_disposition.get("summary", {}) or {})
    pxr_supportive_binder_review_count = sum(
        1
        for row in pxr_pending_disposition.get("rows", []) or []
        if str(row.get("promotion_blocker", "")).strip() == "activity_present_manual_confirmation_required"
    )
    pxr_confirmed_binder_quantitative_gap_count = sum(
        1
        for row in pxr_pending_disposition.get("rows", []) or []
        if str(row.get("promotion_blocker", "")).strip() == "quantitative_binding_value_or_activity_proxy_missing"
    )
    transporter_summary = dict(transporter_readiness.get("summary", {}) or {})
    idp_page4_summary = dict(idp_page4_slice.get("summary", {}) or {})
    idp_tp53_summary = dict(idp_tp53_slice.get("summary", {}) or {})
    idp_lit_summary = dict(idp_literature_summary.get("summary", {}) or {})
    idp_mask_cmp = dict(idp_feature_mask_comparison or {})
    idp_subset = dict((idp_subset_decision.get("summary", {}) if isinstance(idp_subset_decision.get("summary", {}), dict) else {}) or {})
    idp_default_mask = str(idp_subset.get("default_feature_mask", "") or "all")
    idp_default_ready = bool(idp_subset.get("literature_anchor_default_promotion", False))
    rows = [
        {
            "family": "gpcr",
            "current_state": "measured_shadow_and_apply_complete",
            "shadow_policy": "narrow_v2 shadow/apply proven claim-safe on locked-decoy equal-size slice",
            "routing_policy": "no_go_for_100k_router",
            "readiness_signal": gpcr_decision.get("decision", ""),
            "next_required_step": "Refine chembl50-friendly correction target before any 100k router promotion.",
        },
        {
            "family": "ion_channel",
            "current_state": (
                "locked_decoy_shadow_running"
                if crossfamily_running
                else "locked_decoy_shadow_ready"
            ),
            "shadow_policy": "family_noop_shadow_equal_size_locked_decoy",
            "routing_policy": "frozen baseline path with family token",
            "readiness_signal": (
                f"{str(crossfamily_run.get('status', '') or 'scaffold_ready')}"
                + (f"; decision={crossfamily_decision}" if crossfamily_decision else "")
            ),
            "next_required_step": (
                "Keep ion_channel in conservative noop shadow mode as a measured family while CA2/PXR authoritative rows continue to fill."
                if crossfamily_completed and crossfamily_decision == "keep_shadow_noop_contract_for_ion_kinase"
                else (
                    "Interpret the completed TRPV1 locked-decoy shadow deltas and keep ion_channel in conservative shadow mode until CA2/PXR mature."
                    if crossfamily_completed
                    else "Finish the current TRPV1 locked-decoy shadow run and confirm pass stability before any cross-family apply-mode step."
                )
            ),
        },
        {
            "family": "kinase",
            "current_state": (
                "locked_decoy_shadow_running"
                if crossfamily_running
                else "locked_decoy_shadow_ready"
            ),
            "shadow_policy": "family_noop_shadow_equal_size_locked_decoy",
            "routing_policy": "frozen baseline path with family token",
            "readiness_signal": (
                f"{str(crossfamily_run.get('status', '') or 'scaffold_ready')}"
                + (f"; decision={crossfamily_decision}" if crossfamily_decision else "")
            ),
            "next_required_step": (
                "Keep kinase in conservative noop shadow mode as a measured comparison family while CA2/PXR authoritative rows continue to fill."
                if crossfamily_completed and crossfamily_decision == "keep_shadow_noop_contract_for_ion_kinase"
                else (
                    "Interpret the completed kinase locked-decoy shadow deltas and keep kinase in conservative shadow mode as the comparison family."
                    if crossfamily_completed
                    else "Finish the current kinase locked-decoy shadow run and keep kinase in conservative shadow mode as a comparison family."
                )
            ),
        },
        {
            "family": "idp",
            "current_state": (
                "literature_anchor_default_mask_ready_broader_corrected_promotion_blocked"
                if idp_default_ready
                else "tau_k18_baseline_replay_safe_but_corrected_promotion_blocked"
            ),
            "shadow_policy": "feature_state_v1 with provisional-anchor abstain; rg_sasa_only default for literature-anchor subset; broader corrected-path promotion still blocked",
            "routing_policy": "no coordinate correction",
            "readiness_signal": (
                f"subset_decision={idp_subset.get('decision', '')}; "
                f"default_mask={idp_default_mask}; "
                f"cmp={idp_mask_cmp.get('decision', '')}; "
                f"page4_provisional={idp_page4_summary.get('provisional_anchor_row_count', '')}; "
                f"tp53_gate={idp_tp53_summary.get('would_change_gate_count', '')}"
            ),
            "next_required_step": "Use rg_sasa_only as the default literature-anchor shadow mask, keep broader corrected-path promotion blocked, and revisit full-IDP promotion only after provisional-anchor and corrected-path risks are reduced.",
        },
        {
            "family": "non_kinase_enzyme_ca2",
            "current_state": "binding_verification_in_progress",
            "shadow_policy": "future family token with abstention",
            "routing_policy": "blocked_until_authoritative_binding_rows_exist",
            "readiness_signal": (
                f"ready_rows={ca2_readiness.get('summary', {}).get('ready_row_count', '')}; "
                f"blocked_rows={ca2_readiness.get('summary', {}).get('blocked_row_count', '')}; "
                f"review_only_rows={ca2_pending_summary.get('review_only_rows', 0)}; "
                f"defer_rows={ca2_pending_summary.get('defer_rows', 0)}"
            ),
            "next_required_step": "Keep the remaining CA2 negative-like rows review-only, keep them out of authoritative apply, and only attach the CA2 family token after direct CA2-specific negative evidence closes those blockers.",
        },
        {
            "family": "nuclear_receptor_pxr",
            "current_state": "binding_verification_in_progress",
            "shadow_policy": "future family token with abstention",
            "routing_policy": "blocked_until_authoritative_binding_rows_exist",
            "readiness_signal": (
                f"ready_rows={pxr_readiness.get('summary', {}).get('ready_for_apply_row_count', '')}; "
                f"blocked_rows={pxr_readiness.get('summary', {}).get('blocked_row_count', '')}; "
                f"review_only_rows={pxr_pending_summary.get('review_only_rows', 0)}; "
                f"defer_rows={pxr_pending_summary.get('defer_rows', 0)}"
                + (
                    f"; supportive_manual_confirmation_rows={pxr_supportive_binder_review_count}"
                    if pxr_supportive_binder_review_count
                    else ""
                )
                + (
                    f"; confirmed_quantitative_gap_rows={pxr_confirmed_binder_quantitative_gap_count}"
                    if pxr_confirmed_binder_quantitative_gap_count
                    else ""
                )
            ),
            "next_required_step": (
                "Keep current review-only PXR negative-like rows frozen, keep bexarotene deferred as a literature-backed supportive binder pending manual confirmation, keep the remaining unresolved negatives deferred, and only expand the PXR family token when target-specific evidence is curated."
                if pxr_supportive_binder_review_count
                else "Keep current review-only PXR negative-like rows frozen, keep bexarotene deferred as a literature-confirmed human PXR binder with quantitative provenance still missing, keep the remaining unresolved negatives deferred, and only expand the PXR family token when target-specific evidence is curated."
                if pxr_confirmed_binder_quantitative_gap_count
                else "Keep current review-only PXR negative-like rows frozen, explicitly defer the remaining unresolved PXR rows, and only expand the PXR family token when target-specific evidence is curated."
            ),
        },
        {
            "family": "transporter",
            "current_state": "scaffold_only",
            "shadow_policy": "strongest abstention defaults",
            "routing_policy": "unsupported_shadow_family",
            "readiness_signal": (
                f"validate_only_ok={transporter_summary.get('validate_only_ok', False)}; "
                f"p0_open_count={transporter_summary.get('p0_open_count', '')}"
            ),
            "next_required_step": "Keep transporter in scaffold mode until CA2 and PXR prove the family-expansion workflow, while using the validate-only readiness panel to burn down AQP1/GLUT1 P0 blockers.",
        },
    ]
    return {
        "summary": {
            "family_count": len(rows),
            "mean_stage2_share_pct": cascade_envelope.get("summary", {}).get("mean_stage2_share_pct"),
            "gpcr_router_decision": gpcr_decision.get("decision", ""),
            "cross_family_shadow_candidate_spec_json": crossfamily_shadow_scaffold.get("candidate_spec_json", ""),
            "cross_family_shadow_run_root": crossfamily_run.get("run_root", ""),
            "cross_family_shadow_status": crossfamily_run.get("status", ""),
            "measured_failure_scopes": global_target_list.get("summary", {}).get("measured_failure_scopes", []),
            "measured_pass_scopes": global_target_list.get("summary", {}).get("measured_pass_scopes", []),
            "next_required_step": (
                "Keep ion/kinase as measured noop-shadow families, then extend authoritative CA2/PXR rows so the global cross-family shadow shell can carry GPCR/ion/kinase as measured families and CA2/PXR as abstaining expansion families."
                if crossfamily_completed and crossfamily_decision == "keep_shadow_noop_contract_for_ion_kinase"
                else (
                    "Interpret the completed ion/kinase locked-decoy shadow comparison, then extend authoritative CA2/PXR rows so the "
                    "global cross-family shadow shell can carry GPCR/ion/kinase as measured families and CA2/PXR as abstaining expansion families."
                    if crossfamily_completed
                    else "Finish the running ion/kinase locked-decoy shadow candidate, then extend authoritative CA2/PXR rows so the "
                    "global cross-family shadow shell can carry GPCR/ion/kinase as measured families and CA2/PXR as abstaining expansion families."
                )
            ),
        },
        "rows": rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Cross-Family Residual Shadow Layer",
        "",
        f"- family_count: `{payload['summary']['family_count']}`",
        f"- mean_stage2_share_pct: `{payload['summary']['mean_stage2_share_pct']}`",
        f"- gpcr_router_decision: `{payload['summary']['gpcr_router_decision']}`",
        f"- cross_family_shadow_status: `{payload['summary'].get('cross_family_shadow_status', '')}`",
        f"- cross_family_shadow_run_root: `{payload['summary'].get('cross_family_shadow_run_root', '')}`",
        "",
        "## Next Step",
        "",
        f"- {payload['summary']['next_required_step']}",
        "",
        "## Family Plan",
        "",
        "| family | current_state | shadow_policy | routing_policy | readiness_signal | next_required_step |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['family']} | {row['current_state']} | {row['shadow_policy']} | "
            f"{row['routing_policy']} | `{row['readiness_signal']}` | {row['next_required_step']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a current cross-family residual shadow layer plan from measured GPCR scale-up and family-expansion readiness.")
    parser.add_argument("--gpcr-decision-json", default=DEFAULT_GPCR_DECISION_JSON)
    parser.add_argument("--global-target-list-json", default=DEFAULT_GLOBAL_TARGET_LIST_JSON)
    parser.add_argument("--cascade-envelope-json", default=DEFAULT_CASCADE_ENVELOPE_JSON)
    parser.add_argument("--ca2-readiness-json", default=DEFAULT_CA2_READINESS_JSON)
    parser.add_argument("--pxr-readiness-json", default=DEFAULT_PXR_READINESS_JSON)
    parser.add_argument("--crossfamily-shadow-scaffold-json", default=DEFAULT_CROSSFAMILY_SHADOW_SCAFFOLD_JSON)
    parser.add_argument("--crossfamily-shadow-decision-json", default=DEFAULT_CROSSFAMILY_SHADOW_DECISION_JSON)
    parser.add_argument("--ca2-pending-disposition-json", default=DEFAULT_CA2_PENDING_DISPOSITION_JSON)
    parser.add_argument("--pxr-pending-disposition-json", default=DEFAULT_PXR_PENDING_DISPOSITION_JSON)
    parser.add_argument("--transporter-readiness-json", default=DEFAULT_TRANSPORTER_READINESS_JSON)
    parser.add_argument("--aqp1-p0-plan-json", default=DEFAULT_AQP1_P0_PLAN_JSON)
    parser.add_argument("--aqp1-manual-review-queue-json", default=DEFAULT_AQP1_MANUAL_REVIEW_QUEUE_JSON)
    parser.add_argument("--aqp1-local-evidence-note-json", default=DEFAULT_AQP1_LOCAL_EVIDENCE_NOTE_JSON)
    parser.add_argument("--aqp1-external-evidence-seed-json", default=DEFAULT_AQP1_EXTERNAL_EVIDENCE_SEED_JSON)
    parser.add_argument("--aqp1-verdict-json", default=DEFAULT_AQP1_VERDICT_JSON)
    parser.add_argument("--glut1-local-evidence-note-json", default=DEFAULT_GLUT1_LOCAL_EVIDENCE_NOTE_JSON)
    parser.add_argument("--glut1-external-evidence-seed-json", default=DEFAULT_GLUT1_EXTERNAL_EVIDENCE_SEED_JSON)
    parser.add_argument("--glut1-verdict-json", default=DEFAULT_GLUT1_VERDICT_JSON)
    parser.add_argument("--transporter-binder-progress-json", default=DEFAULT_BINDER_PROGRESS_JSON)
    parser.add_argument("--transporter-binder-rubric-json", default=DEFAULT_BINDER_RUBRIC_JSON)
    parser.add_argument("--transporter-binder-note-templates-json", default=DEFAULT_BINDER_NOTE_TEMPLATES_JSON)
    parser.add_argument("--transporter-binder-prefill-preview-json", default=DEFAULT_BINDER_PREFILL_PREVIEW_JSON)
    parser.add_argument("--transporter-binder-packets-json", default=DEFAULT_BINDER_PACKETS_JSON)
    parser.add_argument("--aqp1-apply-draft-json", default=DEFAULT_AQP1_APPLY_DRAFT_JSON)
    parser.add_argument("--glut1-apply-draft-json", default=DEFAULT_GLUT1_APPLY_DRAFT_JSON)
    parser.add_argument("--aqp1-negative-packet-json", default=DEFAULT_AQP1_NEGATIVE_PACKET_JSON)
    parser.add_argument("--glut1-negative-packet-json", default=DEFAULT_GLUT1_NEGATIVE_PACKET_JSON)
    parser.add_argument("--transporter-dashboard-json", default=DEFAULT_TRANSPORTER_DASHBOARD_JSON)
    parser.add_argument("--transporter-seed-row-board-json", default=DEFAULT_TRANSPORTER_SEED_ROW_BOARD_JSON)
    parser.add_argument("--transporter-fit-donor-policy-decision-json", default=DEFAULT_TRANSPORTER_FIT_DONOR_POLICY_DECISION_JSON)
    parser.add_argument("--transporter-wave-decision-json", default=DEFAULT_TRANSPORTER_WAVE_DECISION_JSON)
    parser.add_argument("--transporter-donor-reopen-checklist-json", default=DEFAULT_TRANSPORTER_DONOR_REOPEN_CHECKLIST_JSON)
    parser.add_argument("--transporter-reviewer-day-plan-json", default=DEFAULT_TRANSPORTER_REVIEWER_DAY_PLAN_JSON)
    parser.add_argument("--transporter-negative-reviewer-day-plan-json", default=DEFAULT_TRANSPORTER_NEGATIVE_REVIEWER_DAY_PLAN_JSON)
    parser.add_argument("--gpcr-apply-safe-endpoint-json", default=DEFAULT_GPCR_APPLY_SAFE_ENDPOINT_JSON)
    parser.add_argument("--idp-page4-slice-json", default=DEFAULT_IDP_PAGE4_SLICE_JSON)
    parser.add_argument("--idp-tp53-slice-json", default=DEFAULT_IDP_TP53_SLICE_JSON)
    parser.add_argument("--idp-literature-summary-json", default=DEFAULT_IDP_LITERATURE_SUMMARY_JSON)
    parser.add_argument("--idp-feature-mask-comparison-json", default=DEFAULT_IDP_FEATURE_MASK_COMPARISON_JSON)
    parser.add_argument("--idp-subset-decision-json", default=DEFAULT_IDP_SUBSET_DECISION_JSON)
    parser.add_argument("--idp-commercial-pretest-json", default=DEFAULT_IDP_COMMERCIAL_PRETEST_JSON)
    parser.add_argument("--idp-commercial-pretest-decision-json", default=DEFAULT_IDP_COMMERCIAL_PRETEST_DECISION_JSON)
    parser.add_argument("--idp-broader-shadow-result-json", default=DEFAULT_IDP_BROADER_SHADOW_RESULT_JSON)
    parser.add_argument("--idp-broader-shadow-decision-json", default=DEFAULT_IDP_BROADER_SHADOW_DECISION_JSON)
    parser.add_argument("--idp-broader-promotion-resolution-json", default=DEFAULT_IDP_BROADER_PROMOTION_RESOLUTION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.gpcr_decision_json),
        _load_json(args.global_target_list_json),
        _load_json(args.cascade_envelope_json),
        _load_json(args.ca2_readiness_json),
        _load_json(args.pxr_readiness_json),
        _load_json(args.crossfamily_shadow_scaffold_json),
        _load_json(args.crossfamily_shadow_decision_json),
        _load_json(args.ca2_pending_disposition_json),
        _load_json(args.pxr_pending_disposition_json),
        _load_json(args.transporter_readiness_json),
        _load_json(args.idp_page4_slice_json),
        _load_json(args.idp_tp53_slice_json),
        _load_json(args.idp_literature_summary_json),
        _load_json(args.idp_feature_mask_comparison_json),
        _load_json(args.idp_subset_decision_json),
    )
    payload = _enrich_payload_with_runtime_context(
        payload,
        _load_json(args.aqp1_p0_plan_json),
        _maybe_load_json(args.aqp1_manual_review_queue_json),
        _maybe_load_json(args.aqp1_local_evidence_note_json),
        _maybe_load_json(args.aqp1_external_evidence_seed_json),
        _maybe_load_json(args.aqp1_verdict_json),
        _maybe_load_json(args.glut1_local_evidence_note_json),
        _maybe_load_json(args.glut1_external_evidence_seed_json),
        _maybe_load_json(args.glut1_verdict_json),
        _maybe_load_json(args.transporter_binder_progress_json),
        _maybe_load_json(args.transporter_binder_rubric_json),
        _maybe_load_json(args.transporter_binder_note_templates_json),
        _maybe_load_json(args.transporter_binder_prefill_preview_json),
        _maybe_load_json(args.transporter_binder_packets_json),
        _maybe_load_json(args.aqp1_apply_draft_json),
        _maybe_load_json(args.glut1_apply_draft_json),
        _maybe_load_json(args.aqp1_negative_packet_json),
        _maybe_load_json(args.glut1_negative_packet_json),
        _maybe_load_json(args.transporter_dashboard_json),
        _maybe_load_json(args.transporter_seed_row_board_json),
        _maybe_load_json(args.transporter_fit_donor_policy_decision_json),
        _maybe_load_json(args.transporter_wave_decision_json),
        _maybe_load_json(args.transporter_donor_reopen_checklist_json),
        _maybe_load_json(args.transporter_reviewer_day_plan_json),
        _maybe_load_json(args.transporter_negative_reviewer_day_plan_json),
        _maybe_load_json(args.gpcr_apply_safe_endpoint_json),
        _maybe_load_json(args.idp_commercial_pretest_json),
        _maybe_load_json(args.idp_commercial_pretest_decision_json),
        _maybe_load_json(args.idp_broader_shadow_result_json),
        _maybe_load_json(args.idp_broader_shadow_decision_json),
        _maybe_load_json(args.idp_broader_promotion_resolution_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
