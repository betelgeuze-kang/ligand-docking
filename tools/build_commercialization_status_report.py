#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_COMMERCIALIZATION_JSON = "runs/commercialization_readiness_current.json"
DEFAULT_GAP_JSON = "runs/commercialization_gap_burndown_current.json"
DEFAULT_ROLLUP_JSON = "runs/family_expansion_status_rollup_current.json"
DEFAULT_PLACEHOLDER_JSON = "runs/transporter_placeholder_burndown_queue_current.json"
DEFAULT_NEGATIVE_QUEUE_JSON = "runs/transporter_negative_evidence_closure_queue_current.json"
DEFAULT_NEGATIVE_TARGET_PACKETS_JSON = "runs/transporter_negative_evidence_target_packets_current.json"
DEFAULT_LOCAL_ENGINE_QUEUE_JSON = "runs/local_engine_commercialization_queue_current.json"
DEFAULT_LOCAL_DELIVERY_VERDICT_JSON = "runs/local_delivery_verdict_gate_current.json"
DEFAULT_KEEP_GREEN_TREND_JSON = "runs/keep_green_regression_trend_packet_current.json"
DEFAULT_PLATFORM_GAP_TAXONOMY_JSON = "runs/platform_gap_taxonomy_packet_current.json"
DEFAULT_EXTERNAL_EVIDENCE_CROSSCHECK_JSON = "runs/transporter_external_evidence_crosscheck_current.json"
DEFAULT_NEGATIVE_CANDIDATE_HARVEST_JSON = "runs/transporter_negative_candidate_harvest_current.json"
DEFAULT_NEGATIVE_CANDIDATE_CURATION_QUEUE_JSON = "runs/transporter_negative_candidate_curation_queue_current.json"
DEFAULT_AQP1_NEGATIVE_EVIDENCE_GAP_MATRIX_JSON = "runs/aqp1_negative_evidence_gap_matrix_current.json"
DEFAULT_AQP1_NEGATIVE_EVIDENCE_REQUEST_JSON = "runs/aqp1_negative_evidence_request_packet_current.json"
DEFAULT_AQP1_NEGATIVE_EVIDENCE_INTAKE_GATE_JSON = "runs/aqp1_negative_evidence_intake_gate_current.json"
DEFAULT_ACCURACY_PARITY_SCORECARD_JSON = "runs/accuracy_parity_scorecard_current.json"
DEFAULT_GPCR_A1_ACCURACY_REPAIR_QUEUE_JSON = "runs/gpcr_a1_accuracy_repair_queue_current.json"
DEFAULT_GPCR_A1_INDEPENDENT_REPEAT_PACKET_JSON = "runs/gpcr_a1_independent_repeat_packet_current.json"
DEFAULT_OUT_MD = "commercialization_status_report.md"


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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _family_list(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return _text(value)


def _find_family_row(rows: list[dict[str, Any]], family: str) -> dict[str, Any]:
    for row in rows:
        if _text(row.get("family")) == family:
            return dict(row)
    return {}


def build_payload(
    commercialization_payload: dict[str, Any],
    gap_payload: dict[str, Any],
    rollup_payload: dict[str, Any],
    placeholder_payload: dict[str, Any],
    negative_queue_payload: dict[str, Any] | None = None,
    negative_target_packets_payload: dict[str, Any] | None = None,
    local_engine_queue_payload: dict[str, Any] | None = None,
    local_delivery_verdict_payload: dict[str, Any] | None = None,
    keep_green_trend_payload: dict[str, Any] | None = None,
    platform_gap_taxonomy_payload: dict[str, Any] | None = None,
    external_evidence_crosscheck_payload: dict[str, Any] | None = None,
    negative_candidate_harvest_payload: dict[str, Any] | None = None,
    negative_candidate_curation_queue_payload: dict[str, Any] | None = None,
    aqp1_negative_evidence_gap_matrix_payload: dict[str, Any] | None = None,
    aqp1_negative_evidence_request_payload: dict[str, Any] | None = None,
    aqp1_negative_evidence_intake_gate_payload: dict[str, Any] | None = None,
    accuracy_parity_scorecard_payload: dict[str, Any] | None = None,
    gpcr_a1_accuracy_repair_queue_payload: dict[str, Any] | None = None,
    gpcr_a1_independent_repeat_packet_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    commercialization_summary = dict(commercialization_payload.get("summary", {}) or {})
    gap_summary = dict(gap_payload.get("summary", {}) or {})
    rollup_summary = dict(rollup_payload.get("summary", {}) or {})
    placeholder_summary = dict(placeholder_payload.get("summary", {}) or {})
    negative_queue_summary = dict((negative_queue_payload or {}).get("summary", {}) or {})
    negative_target_packets_summary = dict((negative_target_packets_payload or {}).get("summary", {}) or {})
    local_engine_queue_summary = dict((local_engine_queue_payload or {}).get("summary", {}) or {})
    local_delivery_summary = dict((local_delivery_verdict_payload or {}).get("summary", {}) or {})
    keep_green_trend_summary = dict((keep_green_trend_payload or {}).get("summary", {}) or {})
    platform_gap_taxonomy_summary = dict((platform_gap_taxonomy_payload or {}).get("summary", {}) or {})
    external_evidence_summary = dict((external_evidence_crosscheck_payload or {}).get("summary", {}) or {})
    negative_candidate_harvest_summary = dict((negative_candidate_harvest_payload or {}).get("summary", {}) or {})
    negative_candidate_curation_queue_summary = dict(
        (negative_candidate_curation_queue_payload or {}).get("summary", {}) or {}
    )
    aqp1_negative_evidence_gap_matrix_summary = dict(
        (aqp1_negative_evidence_gap_matrix_payload or {}).get("summary", {}) or {}
    )
    aqp1_negative_evidence_request_summary = dict(
        (aqp1_negative_evidence_request_payload or {}).get("summary", {}) or {}
    )
    aqp1_negative_evidence_intake_gate_summary = dict(
        (aqp1_negative_evidence_intake_gate_payload or {}).get("summary", {}) or {}
    )
    accuracy_parity_summary = dict((accuracy_parity_scorecard_payload or {}).get("summary", {}) or {})
    gpcr_a1_summary = dict((gpcr_a1_accuracy_repair_queue_payload or {}).get("summary", {}) or {})
    gpcr_a1_repeat_summary = dict((gpcr_a1_independent_repeat_packet_payload or {}).get("summary", {}) or {})
    transporter_row = _find_family_row(list(commercialization_payload.get("rows", []) or []), "transporter")

    strongest_ready_families = _family_list(commercialization_summary.get("strongest_ready_families")) or "kinase, ion_channel, gpcr"
    top_blocker_family = _text(gap_summary.get("highest_gap_family")) or _text(rollup_summary.get("highest_gap_family")) or "transporter"
    placeholder_rows = int(placeholder_summary.get("placeholder_driven_rows", gap_summary.get("transporter_placeholder_driven_rows", 0)) or 0)
    reducible_now_rows = int(placeholder_summary.get("reducible_now_placeholder_rows", 0) or 0)
    evidence_blocked_rows = int(placeholder_summary.get("evidence_blocked_placeholder_rows", 0) or 0)
    negative_queue_top_source_context_artifact = _text(negative_queue_summary.get("top_source_context_artifact"))
    negative_queue_top_source_context_role = _text(negative_queue_summary.get("top_source_context_role"))
    negative_queue_aqp1_focus_ligand = _text(negative_queue_summary.get("aqp1_source_context_focus_ligand"))
    negative_queue_aqp1_direct_negative_count = int(
        negative_queue_summary.get("aqp1_source_context_direct_negative_quantitative_row_found_count", 0) or 0
    )
    negative_queue_aqp1_authoritative_apply_count = int(
        negative_queue_summary.get("aqp1_source_context_authoritative_negative_apply_allowed_count", 0) or 0
    )
    negative_queue_glut1_handoff_artifact = _text(negative_queue_summary.get("glut1_negative_handoff_artifact"))
    immediate_target = _text(placeholder_summary.get("immediate_reduction_target"))
    immediate_queue_start = int(placeholder_summary.get("immediate_reduction_target_queue_start", 0) or 0)
    immediate_queue_end = int(placeholder_summary.get("immediate_reduction_target_queue_end", 0) or 0)
    immediate_delta = int(placeholder_summary.get("immediate_reduction_delta_if_completed", 0) or 0)
    if reducible_now_rows == 0:
        immediate_target = ""
        immediate_queue_start = 0
        immediate_queue_end = 0
        immediate_delta = 0
    follow_on_lane = _text(commercialization_summary.get("aqp1_first_wave_follow_on_lane_label")) or "core_binder_02/03"
    aqp1_focus = _text(commercialization_summary.get("aqp1_first_wave_primary_focus_ligand")) or "bacopaside II"
    aqp1_guardrail = _text(commercialization_summary.get("aqp1_exact_human_reference_ligand")) or "AqB013"
    glut1_focus = _text(commercialization_summary.get("glut1_second_wave_source_confirmation_packet_primary_focus_ligand")) or "cytochalasin B"
    local_only_mode = True
    engine_top_priority_id = _text(local_engine_queue_summary.get("top_priority_id"))
    engine_top_priority_status = _text(local_engine_queue_summary.get("top_priority_status"))
    engine_queue_clear = bool(local_engine_queue_summary.get("queue_clear", False))
    engine_blocked_count = int(local_engine_queue_summary.get("blocked_count", 0) or 0)
    engine_partial_count = int(local_engine_queue_summary.get("partial_count", 0) or 0)
    engine_keep_green_count = int(local_engine_queue_summary.get("keep_green_count", 0) or 0)
    engine_parked_count = int(local_engine_queue_summary.get("parked_science_blocker_count", 0) or 0)
    delivery_ready = bool(local_delivery_summary.get("delivery_ready", False))
    delivery_verdict = _text(local_delivery_summary.get("verdict"))
    delivery_p0_count = int(local_delivery_summary.get("p0_blocker_count", 0) or 0)
    delivery_hard_count = int(local_delivery_summary.get("hard_blocker_count", 0) or 0)
    delivery_status_line = _text(local_delivery_summary.get("status_line"))
    local_delivery_queue_mismatch = bool(local_delivery_summary and delivery_ready and not engine_queue_clear)
    effective_delivery_ready = bool(
        delivery_ready
        and delivery_verdict == "delivery_ready"
        and delivery_p0_count == 0
        and delivery_hard_count == 0
        and engine_queue_clear
    )
    effective_delivery_status_line = (
        delivery_status_line
        if effective_delivery_ready
        else (
            "blocked: local delivery verdict is stale or inconsistent with the active local-engine queue; "
            "regenerate local_delivery_verdict after clearing the queue."
            if local_delivery_queue_mismatch
            else delivery_status_line
        )
    )
    engine_nightly_status_line = _text(local_engine_queue_summary.get("nightly_status_line"))
    engine_nightly_gate_artifact = _text(local_engine_queue_summary.get("nightly_gate_burndown_artifact"))
    engine_nightly_gate_metric = _text(local_engine_queue_summary.get("nightly_gate_primary_metric"))
    engine_nightly_gate_value = _text(local_engine_queue_summary.get("nightly_gate_primary_value"))
    engine_nightly_gate_threshold = _text(local_engine_queue_summary.get("nightly_gate_primary_threshold"))
    engine_nightly_gate_delta = _text(local_engine_queue_summary.get("nightly_gate_primary_delta"))
    engine_nightly_tuning_artifact = _text(local_engine_queue_summary.get("nightly_stage6_tuning_artifact"))
    engine_nightly_tuning_focus = _text(local_engine_queue_summary.get("nightly_stage6_tuning_primary_focus_row_key"))
    engine_nightly_followup_artifact = _text(local_engine_queue_summary.get("nightly_stage6_followup_artifact"))
    engine_nightly_followup_focus = _text(local_engine_queue_summary.get("nightly_stage6_followup_primary_focus_row_key"))
    engine_nightly_sweep_artifact = _text(local_engine_queue_summary.get("nightly_stage6_sweep_artifact"))
    engine_nightly_sweep_focus = _text(local_engine_queue_summary.get("nightly_stage6_sweep_primary_focus_row_key"))
    engine_nightly_sweep_preset = _text(local_engine_queue_summary.get("nightly_stage6_sweep_primary_preset_id"))
    engine_nightly_probe_artifact = _text(local_engine_queue_summary.get("nightly_stage6_probe_artifact"))
    engine_nightly_probe_focus = _text(local_engine_queue_summary.get("nightly_stage6_probe_primary_focus_row_key"))
    engine_nightly_probe_pass = bool(local_engine_queue_summary.get("nightly_stage6_probe_projected_gate_pass", False))
    engine_nightly_promotion_artifact = _text(local_engine_queue_summary.get("nightly_stage6_promotion_artifact"))
    engine_nightly_promotion_focus = _text(local_engine_queue_summary.get("nightly_stage6_promotion_primary_focus_row_key"))
    engine_nightly_promotion_pass = bool(local_engine_queue_summary.get("nightly_stage6_promotion_projected_gate_pass", False))
    engine_nightly_realization_artifact = _text(local_engine_queue_summary.get("nightly_stage6_realization_artifact"))
    engine_nightly_realization_focus = _text(local_engine_queue_summary.get("nightly_stage6_realization_primary_focus_row_key"))
    engine_nightly_realization_preset = _text(local_engine_queue_summary.get("nightly_stage6_realization_primary_preset_id"))
    engine_nightly_realization_pass = bool(local_engine_queue_summary.get("nightly_stage6_realization_gate_pass", False))
    engine_nightly_rescored_artifact = _text(local_engine_queue_summary.get("nightly_stage6_rescored_gate_artifact"))
    engine_nightly_rescored_focus = _text(local_engine_queue_summary.get("nightly_stage6_rescored_gate_primary_focus_row_key"))
    engine_nightly_rescored_preset = _text(local_engine_queue_summary.get("nightly_stage6_rescored_gate_primary_preset_id"))
    engine_nightly_rescored_pass = bool(local_engine_queue_summary.get("nightly_stage6_rescored_gate_pass", False))
    engine_nightly_downstream_artifact = _text(local_engine_queue_summary.get("nightly_stage6_downstream_rerun_artifact"))
    engine_nightly_downstream_focus = _text(local_engine_queue_summary.get("nightly_stage6_downstream_rerun_primary_focus_row_key"))
    engine_nightly_downstream_preset = _text(local_engine_queue_summary.get("nightly_stage6_downstream_rerun_primary_preset_id"))
    engine_nightly_downstream_target_subset = _text(local_engine_queue_summary.get("nightly_stage6_downstream_rerun_target_subset"))
    engine_nightly_downstream_profile_artifact = _text(
        local_engine_queue_summary.get("nightly_stage6_downstream_rerun_profile_json_artifact")
    )
    engine_nightly_downstream_dry_run_status_artifact = _text(
        local_engine_queue_summary.get("nightly_stage6_downstream_rerun_dry_run_status_artifact")
    )
    engine_nightly_downstream_dry_run_validated = bool(
        local_engine_queue_summary.get("nightly_stage6_downstream_rerun_dry_run_validated", False)
    )
    engine_nightly_downstream_payload_pass = bool(
        local_engine_queue_summary.get("nightly_stage6_downstream_rerun_payload_pass", False)
    )
    engine_nightly_execute_artifact = _text(local_engine_queue_summary.get("nightly_stage6_execute_artifact"))
    engine_nightly_execute_focus = _text(local_engine_queue_summary.get("nightly_stage6_execute_primary_focus_row_key"))
    engine_nightly_execute_preset = _text(local_engine_queue_summary.get("nightly_stage6_execute_primary_preset_id"))
    engine_nightly_execute_target_subset = _text(local_engine_queue_summary.get("nightly_stage6_execute_target_subset"))
    engine_nightly_execute_status_artifact = _text(
        local_engine_queue_summary.get("nightly_stage6_execute_status_json_artifact")
    )
    engine_nightly_execute_summary_artifact = _text(
        local_engine_queue_summary.get("nightly_stage6_execute_pipeline_summary_json_artifact")
    )
    engine_nightly_execute_gate_mean = _text(
        local_engine_queue_summary.get("nightly_stage6_execute_gate_mean_min_distance_A")
    )
    engine_nightly_execute_gate_pass = bool(
        local_engine_queue_summary.get("nightly_stage6_execute_gate_pass", False)
    )
    engine_nightly_execute_payload_pass = bool(
        local_engine_queue_summary.get("nightly_stage6_execute_payload_pass", False)
    )
    engine_nightly_execute_matches_rescored_gate = bool(
        local_engine_queue_summary.get("nightly_stage6_execute_matches_rescored_gate", False)
    )
    engine_viewer_status = _text(local_engine_queue_summary.get("viewer_status"))
    engine_viewer_status_line = _text(local_engine_queue_summary.get("viewer_status_line"))
    engine_viewer_keep_green = engine_viewer_status == "keep_green"
    engine_wetlab_status = _text(local_engine_queue_summary.get("wetlab_status"))
    engine_wetlab_status_line = _text(local_engine_queue_summary.get("wetlab_status_line"))
    engine_wetlab_allatom_artifact = _text(
        local_engine_queue_summary.get("wetlab_selected_allatom_gate_burndown_artifact")
    )
    engine_wetlab_allatom_target_id = _text(
        local_engine_queue_summary.get("wetlab_selected_allatom_target_id")
    )
    engine_wetlab_allatom_focus_artifact = _text(
        local_engine_queue_summary.get("wetlab_selected_allatom_focus_artifact")
    )
    engine_wetlab_allatom_primary_code = _text(
        local_engine_queue_summary.get("wetlab_selected_allatom_primary_burndown_code")
    )
    engine_wetlab_allatom_primary_metric = _text(
        local_engine_queue_summary.get("wetlab_selected_allatom_primary_burndown_metric")
    )
    engine_wetlab_allatom_primary_value = _text(
        local_engine_queue_summary.get("wetlab_selected_allatom_primary_burndown_value")
    )
    engine_wetlab_allatom_primary_threshold = _text(
        local_engine_queue_summary.get("wetlab_selected_allatom_primary_burndown_threshold")
    )
    engine_wetlab_allatom_primary_delta = _text(
        local_engine_queue_summary.get("wetlab_selected_allatom_primary_burndown_delta")
    )
    engine_wetlab_allatom_hard_block_count = int(
        local_engine_queue_summary.get("wetlab_selected_allatom_hard_block_count", 0) or 0
    )
    engine_wetlab_allatom_semi_hard_block_count = int(
        local_engine_queue_summary.get("wetlab_selected_allatom_semi_hard_block_count", 0) or 0
    )
    keep_green_trend_artifact = _text(keep_green_trend_summary.get("packet_artifact"))
    keep_green_trend_status = _text(keep_green_trend_summary.get("commercial_trend_status"))
    keep_green_trend_all_current_green = bool(keep_green_trend_summary.get("all_current_green", False))
    keep_green_trend_sufficient_history = bool(keep_green_trend_summary.get("sufficient_repeated_history", False))
    keep_green_trend_current_green_count = int(keep_green_trend_summary.get("current_green_lane_count", 0) or 0)
    keep_green_trend_lane_count = int(keep_green_trend_summary.get("lane_count", 0) or 0)
    keep_green_trend_ready_count = int(keep_green_trend_summary.get("repeated_history_ready_lane_count", 0) or 0)
    keep_green_trend_insufficient_count = int(keep_green_trend_summary.get("insufficient_history_lane_count", 0) or 0)
    keep_green_trend_min_samples = int(keep_green_trend_summary.get("minimum_repeated_sample_count", 0) or 0)
    keep_green_trend_nightly_streak = int(keep_green_trend_summary.get("nightly_recent_pass_streak", 0) or 0)
    platform_gap_taxonomy_artifact = _text(platform_gap_taxonomy_summary.get("packet_artifact"))
    platform_gap_taxonomy_top_gap = _text(platform_gap_taxonomy_summary.get("top_expansion_gap_id"))
    platform_gap_taxonomy_top_class = _text(platform_gap_taxonomy_summary.get("top_expansion_gap_class"))
    platform_gap_taxonomy_current_blockers = int(
        platform_gap_taxonomy_summary.get("current_delivery_blocker_count", 0) or 0
    )
    platform_gap_taxonomy_expansion_blockers = int(
        platform_gap_taxonomy_summary.get("expansion_blocker_count", 0) or 0
    )
    platform_gap_taxonomy_non_transporter_count = int(
        platform_gap_taxonomy_summary.get("non_transporter_gap_count", 0) or 0
    )
    platform_gap_taxonomy_split_resolved = bool(
        platform_gap_taxonomy_summary.get("transporter_specific_split_resolved", False)
    )
    platform_gap_taxonomy_scaleup_status = _text(
        platform_gap_taxonomy_summary.get("ligand_scaleup_claim_safe_status")
    )
    platform_accounting_closed = bool(platform_gap_taxonomy_summary.get("platform_accounting_closed", False)) or (
        bool(platform_gap_taxonomy_summary)
        and platform_gap_taxonomy_current_blockers == 0
        and platform_gap_taxonomy_expansion_blockers == 0
    )
    tracked_gap_accounting_closed = bool(gap_summary.get("tracked_gap_accounting_closed", False))
    gap_active_blocked_count = int(gap_summary.get("blocked_count", 0) or 0)
    gap_raw_blocked_bucket_count = int(gap_summary.get("raw_blocked_bucket_count", gap_active_blocked_count) or 0)
    gap_parked_or_review_only_blocked_count = int(
        gap_summary.get("parked_or_review_only_blocked_count", 0) or 0
    )
    family_accounting_closed = bool(rollup_summary.get("all_tracked_family_accounting_closed", False))
    transporter_negative_accounting_closed = bool(
        gap_summary.get("transporter_placeholder_accounting_closed", False)
        or rollup_summary.get("transporter_negative_accounting_closed", False)
        or negative_queue_summary.get("negative_evidence_closure_allowed", False)
    )
    aqp1_functional_kcal_surrogate_closure_allowed = bool(
        platform_gap_taxonomy_summary.get(
            "aqp1_functional_kcal_surrogate_closure_allowed",
            gap_summary.get(
                "aqp1_functional_kcal_surrogate_closure_allowed",
                rollup_summary.get("aqp1_functional_kcal_surrogate_closure_allowed", False),
            ),
        )
    )
    aqp1_functional_kcal_surrogate_ready_count = int(
        platform_gap_taxonomy_summary.get(
            "aqp1_functional_kcal_surrogate_ready_count",
            gap_summary.get(
                "aqp1_functional_kcal_surrogate_ready_count",
                rollup_summary.get("aqp1_functional_kcal_surrogate_ready_count", 0),
            ),
        )
        or 0
    )
    aqp1_direct_binding_gap_still_open = bool(
        platform_gap_taxonomy_summary.get(
            "aqp1_direct_binding_gap_still_open",
            gap_summary.get("aqp1_direct_binding_gap_still_open", rollup_summary.get("aqp1_direct_binding_gap_still_open", False)),
        )
    )
    ca2_pxr_review_policy_closure_allowed = bool(
        platform_gap_taxonomy_summary.get("ca2_pxr_review_policy_closure_allowed", False)
    )
    ca2_pxr_review_only_policy_locked_row_count = int(
        platform_gap_taxonomy_summary.get("ca2_pxr_review_only_policy_locked_row_count", 0) or 0
    )
    all_tracked_commercialization_accounting_closed = (
        engine_queue_clear
        and keep_green_trend_sufficient_history
        and platform_accounting_closed
        and tracked_gap_accounting_closed
        and family_accounting_closed
        and transporter_negative_accounting_closed
        and aqp1_functional_kcal_surrogate_closure_allowed
        and ca2_pxr_review_policy_closure_allowed
    )
    if all_tracked_commercialization_accounting_closed:
        top_blocker_family = "none_tracked_commercialization_gap"
    accuracy_parity_ready = bool(accuracy_parity_summary)
    accuracy_parity_status = _text(accuracy_parity_summary.get("status"))
    accuracy_parity_allowed = bool(accuracy_parity_summary.get("overall_commercial_tool_accuracy_parity_allowed", False))
    accuracy_parity_pass_count = int(accuracy_parity_summary.get("pass_row_count", 0) or 0)
    accuracy_parity_restricted_count = int(accuracy_parity_summary.get("restricted_pass_row_count", 0) or 0)
    accuracy_parity_blocked_count = int(accuracy_parity_summary.get("blocked_row_count", 0) or 0)
    accuracy_parity_missing_count = int(accuracy_parity_summary.get("missing_row_count", 0) or 0)
    accuracy_parity_top_blockers = [
        _text(item) for item in accuracy_parity_summary.get("top_blockers", []) if _text(item)
    ]
    accuracy_parity_top_blockers_text = ", ".join(accuracy_parity_top_blockers[:4]) or "-"
    accuracy_parity_next_step = _text(accuracy_parity_summary.get("next_required_step"))
    gpcr_a1_ready = bool(gpcr_a1_summary)
    gpcr_a1_status = _text(gpcr_a1_summary.get("status"))
    gpcr_a1_top_repair = _text(gpcr_a1_summary.get("top_priority_repair_id"))
    gpcr_a1_top_target = _text(gpcr_a1_summary.get("top_priority_target"))
    gpcr_a1_top_blocker_group = _text(gpcr_a1_summary.get("top_priority_blocker_group"))
    gpcr_a1_open_rows = int(gpcr_a1_summary.get("open_queue_row_count", 0) or 0)
    gpcr_a1_guarded_100k_allowed = bool(gpcr_a1_summary.get("guarded_100k_rerun_allowed_now", False))
    gpcr_a1_next_step = _text(gpcr_a1_summary.get("next_required_step"))
    gpcr_a1_repeat_ready = bool(gpcr_a1_repeat_summary.get("independent_repeat_ready", False))
    gpcr_a1_repeat_status = _text(gpcr_a1_repeat_summary.get("status"))
    gpcr_a1_repeat_completed = bool(gpcr_a1_repeat_summary.get("independent_repeat_completed", False))
    gpcr_a1_repeat_result_passed = bool(gpcr_a1_repeat_summary.get("independent_repeat_result_passed", False)) or (
        "passed" in gpcr_a1_repeat_status
    )
    gpcr_a1_repeat_claim_locked = "claim_locked" in gpcr_a1_repeat_status or (
        bool(gpcr_a1_repeat_summary) and not bool(gpcr_a1_repeat_summary.get("claim_promotion_allowed", True))
    )
    gpcr_a1_repeat_result_state = (
        "passed_claim_locked"
        if gpcr_a1_repeat_result_passed and gpcr_a1_repeat_claim_locked
        else "passed"
        if gpcr_a1_repeat_result_passed
        else "ready_to_run"
        if gpcr_a1_repeat_ready
        else "blocked_or_not_ready"
        if gpcr_a1_repeat_summary
        else "missing"
    )
    gpcr_a1_repeat_tag = _text(gpcr_a1_repeat_summary.get("repeat_tag"))
    gpcr_a1_repeat_validate_command = _text(gpcr_a1_repeat_summary.get("validate_command"))
    gpcr_a1_repeat_run_command = _text(gpcr_a1_repeat_summary.get("run_command"))
    gpcr_a1_repeat_blocker_count = int(gpcr_a1_repeat_summary.get("blocker_count", 0) or 0)
    post_goal_accuracy_parity_active = (
        all_tracked_commercialization_accounting_closed and accuracy_parity_ready and not accuracy_parity_allowed
    )
    external_crosscheck_ready = bool(external_evidence_summary.get("crosscheck_ready", False))
    external_crosscheck_artifact = "runs/transporter_external_evidence_crosscheck_current.md"
    external_crosscheck_skill_family = _text(external_evidence_summary.get("skill_family"))
    external_crosscheck_skill_source_count = int(external_evidence_summary.get("skill_source_count", 0) or 0)
    external_crosscheck_target_count = int(external_evidence_summary.get("target_count", 0) or 0)
    external_crosscheck_row_count = int(external_evidence_summary.get("row_count", 0) or 0)
    external_crosscheck_aqp1_uniprot = _text(external_evidence_summary.get("aqp1_uniprot_accession"))
    external_crosscheck_glut1_uniprot = _text(external_evidence_summary.get("glut1_uniprot_accession"))
    external_crosscheck_aqp1_chembl = _text(external_evidence_summary.get("aqp1_chembl_target_id"))
    external_crosscheck_glut1_chembl = _text(external_evidence_summary.get("glut1_chembl_target_id"))
    external_crosscheck_rcsb_glut1_entry = _text(external_evidence_summary.get("rcsb_glut1_entry"))
    external_crosscheck_aqp1_bindingdb_count = int(
        external_evidence_summary.get("aqp1_bindingdb_affinity_count", 0) or 0
    )
    external_crosscheck_glut1_bindingdb_count = int(
        external_evidence_summary.get("glut1_bindingdb_affinity_count", 0) or 0
    )
    external_crosscheck_glut1_positive_exact_count = int(
        external_evidence_summary.get("glut1_positive_exact_activity_count", 0) or 0
    )
    external_crosscheck_direct_negative_count = int(
        external_evidence_summary.get("direct_negative_quantitative_row_found_count", 0) or 0
    )
    external_crosscheck_authoritative_apply_count = int(
        external_evidence_summary.get("authoritative_negative_apply_allowed_count", 0) or 0
    )
    external_crosscheck_negative_closure_allowed = bool(
        external_evidence_summary.get("negative_evidence_closure_allowed", False)
    )
    external_crosscheck_current_decision = _text(external_evidence_summary.get("current_decision"))
    external_crosscheck_next_required_step = _text(external_evidence_summary.get("next_required_step"))
    negative_candidate_harvest_ready = bool(
        negative_candidate_harvest_summary.get("candidate_harvest_ready", False)
    )
    negative_candidate_harvest_artifact = _text(
        negative_candidate_harvest_summary.get("packet_artifact")
    ) or "runs/transporter_negative_candidate_harvest_current.md"
    negative_candidate_harvest_status = _text(negative_candidate_harvest_summary.get("candidate_harvest_status"))
    negative_candidate_harvest_row_count = int(negative_candidate_harvest_summary.get("row_count", 0) or 0)
    negative_candidate_harvest_aqp1_review_count = int(
        negative_candidate_harvest_summary.get("aqp1_candidate_review_row_count", 0) or 0
    )
    negative_candidate_harvest_glut1_review_count = int(
        negative_candidate_harvest_summary.get("glut1_candidate_review_row_count", 0) or 0
    )
    negative_candidate_harvest_aqp1_quant_count = int(
        negative_candidate_harvest_summary.get("aqp1_quantitative_lower_bound_candidate_count", 0) or 0
    )
    negative_candidate_harvest_glut1_quant_count = int(
        negative_candidate_harvest_summary.get("glut1_quantitative_lower_bound_candidate_count", 0) or 0
    )
    negative_candidate_harvest_aqp1_cover_count = int(
        negative_candidate_harvest_summary.get("potential_aqp1_negative_slot_cover_count", 0) or 0
    )
    negative_candidate_harvest_glut1_cover_count = int(
        negative_candidate_harvest_summary.get("potential_glut1_negative_slot_cover_count", 0) or 0
    )
    negative_candidate_harvest_unreviewed_quant_count = int(
        negative_candidate_harvest_summary.get("unreviewed_direct_negative_quantitative_candidate_count", 0) or 0
    )
    negative_candidate_harvest_apply_count = int(
        negative_candidate_harvest_summary.get("authoritative_negative_apply_allowed_count", 0) or 0
    )
    negative_candidate_harvest_closure_allowed = bool(
        negative_candidate_harvest_summary.get("negative_evidence_closure_allowed", False)
    )
    negative_candidate_curation_queue_ready = bool(
        negative_candidate_curation_queue_summary.get("curation_queue_ready", False)
    )
    negative_candidate_curation_queue_artifact = _text(
        negative_candidate_curation_queue_summary.get("packet_artifact")
    ) or "runs/transporter_negative_candidate_curation_queue_current.md"
    negative_candidate_curation_queue_target_id = _text(
        negative_candidate_curation_queue_summary.get("target_id")
    )
    negative_candidate_curation_queue_status = _text(
        negative_candidate_curation_queue_summary.get("queue_status")
    )
    negative_candidate_curation_queue_source_artifact = _text(
        negative_candidate_curation_queue_summary.get("source_harvest_artifact")
    )
    negative_candidate_curation_queue_candidate_count = int(
        negative_candidate_curation_queue_summary.get("available_quantitative_lower_bound_candidate_count", 0) or 0
    )
    negative_candidate_curation_queue_slot_count = int(
        negative_candidate_curation_queue_summary.get("target_negative_slot_count", 0) or 0
    )
    negative_candidate_curation_queue_row_count = int(
        negative_candidate_curation_queue_summary.get("queue_row_count", 0) or 0
    )
    negative_candidate_curation_queue_slot_cover_count = int(
        negative_candidate_curation_queue_summary.get("slot_cover_ready_count", 0) or 0
    )
    negative_candidate_curation_queue_unused_count = int(
        negative_candidate_curation_queue_summary.get("unused_candidate_count", 0) or 0
    )
    negative_candidate_curation_queue_aqp1_blocker_open = bool(
        negative_candidate_curation_queue_summary.get("aqp1_first_blocker_open", False)
    )
    negative_candidate_curation_queue_apply_allowed = bool(
        negative_candidate_curation_queue_summary.get("candidate_apply_allowed", False)
    )
    negative_candidate_curation_queue_authoritative_apply_count = int(
        negative_candidate_curation_queue_summary.get("authoritative_negative_apply_allowed_count", 0) or 0
    )
    negative_candidate_curation_queue_closure_allowed = bool(
        negative_candidate_curation_queue_summary.get("negative_evidence_closure_allowed", False)
    )
    negative_candidate_curation_queue_claim_promotion_allowed = bool(
        negative_candidate_curation_queue_summary.get("claim_promotion_allowed", False)
    )
    aqp1_negative_gap_matrix_ready = bool(
        aqp1_negative_evidence_gap_matrix_summary.get("gap_matrix_ready", False)
    )
    aqp1_negative_gap_matrix_artifact = _text(
        aqp1_negative_evidence_gap_matrix_summary.get("packet_artifact")
    ) or "runs/aqp1_negative_evidence_gap_matrix_current.md"
    aqp1_negative_gap_matrix_status = _text(
        aqp1_negative_evidence_gap_matrix_summary.get("gap_status")
    )
    aqp1_negative_gap_matrix_target_accession = _text(
        aqp1_negative_evidence_gap_matrix_summary.get("target_uniprot_accession")
    )
    aqp1_negative_gap_matrix_target_chembl = _text(
        aqp1_negative_evidence_gap_matrix_summary.get("target_chembl_id")
    )
    aqp1_negative_gap_matrix_slot_count = int(
        aqp1_negative_evidence_gap_matrix_summary.get("negative_slot_count", 0) or 0
    )
    aqp1_negative_gap_matrix_route_count = int(
        aqp1_negative_evidence_gap_matrix_summary.get("evidence_route_count", 0) or 0
    )
    aqp1_negative_gap_matrix_blocked_route_count = int(
        aqp1_negative_evidence_gap_matrix_summary.get("blocked_route_count", 0) or 0
    )
    aqp1_negative_gap_matrix_review_context_route_count = int(
        aqp1_negative_evidence_gap_matrix_summary.get("review_context_route_count", 0) or 0
    )
    aqp1_negative_gap_matrix_direct_negative_count = int(
        aqp1_negative_evidence_gap_matrix_summary.get("direct_negative_quantitative_row_found_count", 0) or 0
    )
    aqp1_negative_gap_matrix_apply_count = int(
        aqp1_negative_evidence_gap_matrix_summary.get("authoritative_negative_apply_allowed_count", 0) or 0
    )
    aqp1_negative_gap_matrix_slot_cover_ready_count = int(
        aqp1_negative_evidence_gap_matrix_summary.get("negative_slot_cover_ready_count", 0) or 0
    )
    aqp1_negative_gap_matrix_slot_cover_missing_count = int(
        aqp1_negative_evidence_gap_matrix_summary.get("negative_slot_cover_missing_count", 0) or 0
    )
    aqp1_negative_gap_matrix_claim_promotion_allowed = bool(
        aqp1_negative_evidence_gap_matrix_summary.get("claim_promotion_allowed", False)
    )
    aqp1_negative_gap_matrix_commercialization_blocker = _text(
        aqp1_negative_evidence_gap_matrix_summary.get("commercialization_blocker")
    )
    aqp1_negative_evidence_request_ready = bool(
        aqp1_negative_evidence_request_summary.get("evidence_request_ready", False)
    )
    aqp1_negative_evidence_request_artifact = _text(
        aqp1_negative_evidence_request_summary.get("packet_artifact")
    ) or "runs/aqp1_negative_evidence_request_packet_current.md"
    aqp1_negative_evidence_request_source_gap_artifact = _text(
        aqp1_negative_evidence_request_summary.get("source_gap_matrix_artifact")
    )
    aqp1_negative_evidence_request_status = _text(
        aqp1_negative_evidence_request_summary.get("request_status")
    )
    aqp1_negative_evidence_request_mode = _text(
        aqp1_negative_evidence_request_summary.get("request_mode")
    )
    aqp1_negative_evidence_request_row_count = int(
        aqp1_negative_evidence_request_summary.get("request_row_count", 0) or 0
    )
    aqp1_negative_evidence_request_required_row_count = int(
        aqp1_negative_evidence_request_summary.get("required_assignable_negative_row_count", 0) or 0
    )
    aqp1_negative_evidence_request_current_direct_count = int(
        aqp1_negative_evidence_request_summary.get("current_direct_negative_quantitative_row_found_count", 0) or 0
    )
    aqp1_negative_evidence_request_slot_cover_ready_count = int(
        aqp1_negative_evidence_request_summary.get("negative_slot_cover_ready_count", 0) or 0
    )
    aqp1_negative_evidence_request_slot_cover_missing_count = int(
        aqp1_negative_evidence_request_summary.get("negative_slot_cover_missing_count", 0) or 0
    )
    aqp1_negative_evidence_request_blocked_route_count = int(
        aqp1_negative_evidence_request_summary.get("blocked_gap_route_count", 0) or 0
    )
    aqp1_negative_evidence_request_public_exhausted = bool(
        aqp1_negative_evidence_request_summary.get("public_reinterpretation_exhausted", False)
    )
    aqp1_negative_evidence_request_internal_or_primary_required = bool(
        aqp1_negative_evidence_request_summary.get("internal_wetlab_or_primary_source_required", False)
    )
    aqp1_negative_evidence_request_apply_count = int(
        aqp1_negative_evidence_request_summary.get("authoritative_negative_apply_allowed_count", 0) or 0
    )
    aqp1_negative_evidence_request_closure_allowed = bool(
        aqp1_negative_evidence_request_summary.get("negative_evidence_closure_allowed", False)
    )
    aqp1_negative_evidence_request_claim_promotion_allowed = bool(
        aqp1_negative_evidence_request_summary.get("claim_promotion_allowed", False)
    )
    aqp1_negative_evidence_intake_gate_ready = bool(
        aqp1_negative_evidence_intake_gate_summary.get("intake_gate_ready", False)
    )
    aqp1_negative_evidence_intake_gate_artifact = _text(
        aqp1_negative_evidence_intake_gate_summary.get("packet_artifact")
    ) or "runs/aqp1_negative_evidence_intake_gate_current.md"
    aqp1_negative_evidence_intake_gate_request_artifact = _text(
        aqp1_negative_evidence_intake_gate_summary.get("request_artifact")
    )
    aqp1_negative_evidence_intake_gate_template_artifact = _text(
        aqp1_negative_evidence_intake_gate_summary.get("template_csv_artifact")
    )
    aqp1_negative_evidence_intake_gate_intake_artifact = _text(
        aqp1_negative_evidence_intake_gate_summary.get("intake_csv_artifact")
    )
    aqp1_negative_evidence_intake_gate_status = _text(
        aqp1_negative_evidence_intake_gate_summary.get("intake_status")
    )
    aqp1_negative_evidence_intake_gate_row_count = int(
        aqp1_negative_evidence_intake_gate_summary.get("intake_row_count", 0) or 0
    )
    aqp1_negative_evidence_intake_gate_row_with_data_count = int(
        aqp1_negative_evidence_intake_gate_summary.get("intake_row_with_data_count", 0) or 0
    )
    aqp1_negative_evidence_intake_gate_valid_row_count = int(
        aqp1_negative_evidence_intake_gate_summary.get("valid_intake_row_count", 0) or 0
    )
    aqp1_negative_evidence_intake_gate_required_row_count = int(
        aqp1_negative_evidence_intake_gate_summary.get("required_assignable_negative_row_count", 0) or 0
    )
    aqp1_negative_evidence_intake_gate_missing_row_count = int(
        aqp1_negative_evidence_intake_gate_summary.get("missing_valid_intake_row_count", 0) or 0
    )
    aqp1_negative_evidence_intake_gate_error_row_count = int(
        aqp1_negative_evidence_intake_gate_summary.get("validation_error_row_count", 0) or 0
    )
    aqp1_negative_evidence_intake_gate_review_ready_count = int(
        aqp1_negative_evidence_intake_gate_summary.get("review_ready_row_count", 0) or 0
    )
    aqp1_negative_evidence_intake_gate_complete = bool(
        aqp1_negative_evidence_intake_gate_summary.get("intake_gate_complete", False)
    )
    aqp1_negative_evidence_intake_gate_split_update_required = bool(
        aqp1_negative_evidence_intake_gate_summary.get("split_reference_meta_update_required", False)
    )
    aqp1_negative_evidence_intake_gate_apply_count = int(
        aqp1_negative_evidence_intake_gate_summary.get("authoritative_negative_apply_allowed_count", 0) or 0
    )
    aqp1_negative_evidence_intake_gate_closure_allowed = bool(
        aqp1_negative_evidence_intake_gate_summary.get("negative_evidence_closure_allowed", False)
    )
    aqp1_negative_evidence_intake_gate_claim_promotion_allowed = bool(
        aqp1_negative_evidence_intake_gate_summary.get("claim_promotion_allowed", False)
    )

    strengths = [
        f"Commercial core is still strongest in `{strongest_ready_families}`.",
        f"`core_commercial_lane_score={commercialization_summary.get('core_commercial_lane_score', 0)}` and `all_category_expansion_score={commercialization_summary.get('all_category_expansion_score', 0)}` remain unchanged.",
        f"The top expansion blocker is still `{top_blocker_family}`.",
    ]
    if local_engine_queue_summary:
        if engine_queue_clear:
            strengths.append(
                "For local-only commercialization, the engine queue is clear for the scoped delivery lane: "
                f"`blocked={engine_blocked_count}`, `partial={engine_partial_count}`, "
                f"`keep_green={engine_keep_green_count}`, `parked_science={engine_parked_count}`."
            )
        else:
            strengths.append(
                "For local-only commercialization, the new engine queue now makes the operating blockers explicit: "
                f"`blocked={engine_blocked_count}`, `partial={engine_partial_count}`, `parked_science={engine_parked_count}`."
            )
    if local_delivery_summary and effective_delivery_ready:
        strengths.append(
            f"Local delivery verdict is `{delivery_verdict or 'delivery_ready'}` with "
            f"`p0={delivery_p0_count}` and `hard={delivery_hard_count}` blockers."
        )
    if external_crosscheck_ready:
        strengths.append(
            "Life Science Research external crosscheck is attached for transporter evidence: "
            f"`sources={external_crosscheck_skill_source_count}`, `targets={external_crosscheck_target_count}`, "
            f"`rows={external_crosscheck_row_count}`, direct negative rows=`{external_crosscheck_direct_negative_count}`."
        )
    if negative_candidate_harvest_ready:
        strengths.append(
            "ChEMBL target-level transporter negative-candidate harvest is attached: "
            f"`rows={negative_candidate_harvest_row_count}`, unreviewed quantitative lower-bound candidates="
            f"`{negative_candidate_harvest_unreviewed_quant_count}`, apply-allowed="
            f"`{negative_candidate_harvest_apply_count}`."
        )
    if negative_candidate_curation_queue_ready:
        strengths.append(
            "GLUT1 negative-candidate curation queue is attached as pre-apply evidence work: "
            f"`rows={negative_candidate_curation_queue_row_count}/{negative_candidate_curation_queue_slot_count}`, "
            f"candidate apply allowed=`{negative_candidate_curation_queue_apply_allowed}`, "
            f"claim promotion=`{negative_candidate_curation_queue_claim_promotion_allowed}`."
        )
    if aqp1_negative_gap_matrix_ready:
        strengths.append(
            "AQP1 negative-evidence gap matrix is attached: "
            f"`routes={aqp1_negative_gap_matrix_route_count}`, blocked routes="
            f"`{aqp1_negative_gap_matrix_blocked_route_count}`, direct negative rows="
            f"`{aqp1_negative_gap_matrix_direct_negative_count}`, slot cover="
            f"`{aqp1_negative_gap_matrix_slot_cover_ready_count}/{aqp1_negative_gap_matrix_slot_count}`."
        )
    if aqp1_negative_evidence_request_ready:
        strengths.append(
            "AQP1 exact-evidence request packet is attached: "
            f"`requests={aqp1_negative_evidence_request_row_count}`, required assignable rows="
            f"`{aqp1_negative_evidence_request_required_row_count}`, current direct rows="
            f"`{aqp1_negative_evidence_request_current_direct_count}`, closure allowed="
            f"`{aqp1_negative_evidence_request_closure_allowed}`."
        )
    if aqp1_negative_evidence_intake_gate_ready:
        strengths.append(
            "AQP1 negative-evidence intake gate is attached: "
            f"`valid={aqp1_negative_evidence_intake_gate_valid_row_count}/"
            f"{aqp1_negative_evidence_intake_gate_required_row_count}`, data rows="
            f"`{aqp1_negative_evidence_intake_gate_row_with_data_count}`, gate complete="
            f"`{aqp1_negative_evidence_intake_gate_complete}`, closure allowed="
            f"`{aqp1_negative_evidence_intake_gate_closure_allowed}`."
        )
    if reducible_now_rows > 0:
        immediate_priority = [
            f"Reduce transporter placeholder-driven rows from `{placeholder_rows}` by attacking the first reducible-now slice: `{immediate_target}`.",
            f"That slice covers queue ranks `{immediate_queue_start}-{immediate_queue_end}` and can remove `{immediate_delta}` placeholder rows without needing new external negative evidence.",
            f"Keep `{aqp1_focus}` as the AQP1 first-wave scope, `{aqp1_guardrail}` as the exact-human-activity guardrail, and `{glut1_focus}` as the GLUT1 second-wave lead while this reduction happens.",
        ]
        transporter_gap_line = (
            "GLUT1 binder rows already have source-confirmation context, but they still lack staged seed-row surfaces, "
            "so they remain placeholder-driven instead of moving into a staged non-authoritative lane."
        )
        transporter_fix_line = (
            f"First, build the missing GLUT1 staging surfaces for queue ranks `{immediate_queue_start}-{immediate_queue_end}` "
            f"so `{immediate_delta}` rows can move out of the placeholder bucket."
        )
    else:
        immediate_priority = [
            f"The first reducible-now GLUT1 staging slice is already closed, leaving transporter placeholder-driven rows at `{placeholder_rows}`.",
            f"The remaining `{evidence_blocked_rows}` placeholder rows are evidence-blocked and now require direct negative evidence rather than more staging surfaces.",
            f"Keep `{aqp1_focus}` as the AQP1 first-wave scope, `{aqp1_guardrail}` as the exact-human-activity guardrail, and `{glut1_focus}` as the parked GLUT1 second-wave lead while transporter negatives stay frozen.",
        ]
        if local_engine_queue_summary:
            engine_priority: list[str] = []
            if engine_queue_clear:
                engine_priority.append(
                    "Use `runs/local_engine_commercialization_queue_current.md` as the keep-green board: "
                    f"the scoped local queue is clear, and `{engine_top_priority_id or 'transporter_science_blocker'}` is "
                    f"`{engine_top_priority_status or 'parked'}` outside the delivery-ready claim."
                )
                if local_delivery_summary:
                    engine_priority.append(
                        f"Local delivery verdict is `{delivery_verdict or '-'}` with "
                        f"`p0={delivery_p0_count}` and `hard={delivery_hard_count}` blockers; "
                        f"{delivery_status_line or 'keep the restricted local scope explicit.'}"
                    )
                if engine_nightly_status_line:
                    engine_priority.append(f"Nightly status line: `{engine_nightly_status_line}`.")
                if engine_nightly_gate_artifact:
                    engine_priority.append(
                        "Keep "
                        f"`{engine_nightly_gate_artifact}` "
                        "as the nightly gate regression artifact; the latest canonical top-level reentry is green, so this is now "
                        "keep-green evidence rather than an active tuning surface."
                    )
                if engine_nightly_execute_artifact and engine_nightly_execute_payload_pass and engine_nightly_execute_gate_pass:
                    engine_priority.append(
                        "Keep "
                        f"`{engine_nightly_execute_artifact}` "
                        "as supporting execute proof: target subset "
                        f"`{engine_nightly_execute_target_subset or '-'}` already passes at "
                        f"`{engine_nightly_execute_gate_mean or '-'}`"
                        + (
                            ", matching the rescored gate closely."
                            if engine_nightly_execute_matches_rescored_gate
                            else "."
                        )
                    )
                if engine_viewer_status_line:
                    engine_priority.append(f"Viewer keep-green line: `{engine_viewer_status_line}`.")
                if engine_wetlab_status_line:
                    engine_priority.append(f"Wetlab keep-green line: `{engine_wetlab_status_line}`.")
                if engine_wetlab_allatom_artifact:
                    engine_priority.append(
                        "Keep "
                        f"`{engine_wetlab_allatom_artifact}` "
                        "as selected all-atom regression evidence for "
                        f"`{engine_wetlab_allatom_target_id or 'selected_allatom'}`: "
                        f"`{engine_wetlab_allatom_primary_metric or 'mean_min_distance_A'}={engine_wetlab_allatom_primary_value or '-'}` "
                        f"versus `{engine_wetlab_allatom_primary_threshold or '-'}`, with "
                        f"`hard={engine_wetlab_allatom_hard_block_count}` and "
                        f"`semi_hard={engine_wetlab_allatom_semi_hard_block_count}`."
                    )
                if keep_green_trend_artifact:
                    engine_priority.append(
                        "Keep "
                        f"`{keep_green_trend_artifact}` "
                        "as the repeated keep-green trend packet: "
                        f"`{keep_green_trend_current_green_count}/{keep_green_trend_lane_count}` lanes are currently green, "
                        f"`{keep_green_trend_ready_count}/{keep_green_trend_lane_count}` have sufficient repeated history, "
                        f"and nightly streak is `{keep_green_trend_nightly_streak}/{keep_green_trend_min_samples}`."
                    )
                if platform_gap_taxonomy_artifact:
                    engine_priority.append(
                        "Use "
                        f"`{platform_gap_taxonomy_artifact}` "
                        "as the platform-wide gap taxonomy: current delivery blockers="
                        f"`{platform_gap_taxonomy_current_blockers}`, expansion blockers="
                        f"`{platform_gap_taxonomy_expansion_blockers}`, top expansion gap="
                        f"`{platform_gap_taxonomy_top_gap or '-'}` (`{platform_gap_taxonomy_top_class or '-'}`), "
                        f"and scale-up status=`{platform_gap_taxonomy_scaleup_status or '-'}`."
                    )
                immediate_priority = engine_priority + immediate_priority
            else:
                engine_priority.append(
                    "Use `runs/local_engine_commercialization_queue_current.md` as the top local-only queue: "
                    f"`{engine_top_priority_id or 'nightly_reliability'}` is the first blocker and its current state is "
                    f"`{engine_top_priority_status or 'blocked'}`."
                )
                engine_priority.append(
                    (
                        "Burn down engine blockers before reopening science-mining work: `nightly reliability -> wetlab execution readiness`, "
                        "while keeping the mesh-backed viewer proof green, refresh reproducibility green, and transporter evidence parked."
                        if engine_viewer_keep_green
                        else "Burn down engine blockers before reopening science-mining work: `nightly reliability -> viewer usability -> wetlab execution readiness`, "
                        "while keeping refresh reproducibility green and transporter evidence parked."
                    )
                )
                immediate_priority = engine_priority + immediate_priority
            if (not engine_queue_clear) and engine_nightly_status_line:
                immediate_priority.insert(2, f"Nightly status line: `{engine_nightly_status_line}`.")
            if (not engine_queue_clear) and engine_nightly_gate_artifact:
                immediate_priority.insert(
                    3,
                    "Use "
                    f"`{engine_nightly_gate_artifact}` "
                    "as the nightly gate burndown packet: tune "
                    f"`{engine_nightly_gate_metric or 'mean_min_distance_A'}` "
                    f"from `{engine_nightly_gate_value or '-'}` toward `{engine_nightly_gate_threshold or '-'}` "
                    f"(delta `{engine_nightly_gate_delta or '-'}`) while keeping stage2 recovered.",
                )
            if (not engine_queue_clear) and engine_nightly_tuning_artifact:
                immediate_priority.insert(
                    4,
                    "Keep "
                    f"`{engine_nightly_tuning_artifact}` "
                    "open as the exact culprit-band packet: the nightly gate is currently touching the full unique band, and the first tuning focus row is "
                    f"`{engine_nightly_tuning_focus or '-'}`.",
                )
            if (not engine_queue_clear) and engine_nightly_followup_artifact:
                immediate_priority.insert(
                    5,
                    "Keep "
                    f"`{engine_nightly_followup_artifact}` "
                    "open as the row-level retry/closure packet: the first execution focus row is "
                    f"`{engine_nightly_followup_focus or '-'}`.",
                )
            if (not engine_queue_clear) and engine_nightly_probe_artifact and engine_nightly_probe_pass:
                immediate_priority.insert(
                    6,
                    "Keep "
                    f"`{engine_nightly_probe_artifact}` "
                    "open as the measured stage6 re-entry target: the current probe focus row is "
                    f"`{engine_nightly_probe_focus or '-'}` and the projected gate already passes once nightly returns to stage6.",
                )
            if (not engine_queue_clear) and engine_nightly_promotion_artifact and engine_nightly_promotion_pass:
                immediate_priority.insert(
                    7,
                    "Keep "
                    f"`{engine_nightly_promotion_artifact}` "
                    "open as the canonical retry-lane promotion packet: "
                    f"`{engine_nightly_promotion_focus or '-'}` is the first replacement row, even if the latest nightly still needs upstream re-entry.",
                )
            if (not engine_queue_clear) and engine_nightly_realization_artifact and engine_nightly_realization_pass:
                immediate_priority.insert(
                    8,
                    "Keep "
                    f"`{engine_nightly_realization_artifact}` "
                    "open as the measured realization packet: "
                    f"`{engine_nightly_realization_focus or '-'}` leads the canonical uncapped retry lane with preset "
                    f"`{engine_nightly_realization_preset or '-'}`.",
                )
            if (not engine_queue_clear) and engine_nightly_rescored_artifact and engine_nightly_rescored_pass:
                immediate_priority.insert(
                    9,
                    "Keep "
                    f"`{engine_nightly_rescored_artifact}` "
                    "open as the post-apply rescored gate packet: "
                    f"`{engine_nightly_rescored_focus or '-'}` is the first locked replacement row with preset "
                    f"`{engine_nightly_rescored_preset or '-'}`, so the next move is the downstream nightly rerun.",
                )
            if (not engine_queue_clear) and engine_nightly_downstream_artifact:
                immediate_priority.insert(
                    10,
                    "Keep "
                    f"`{engine_nightly_downstream_artifact}` "
                    "open as the exact downstream nightly rerun handoff: target subset "
                    f"`{engine_nightly_downstream_target_subset or '-'}` with focus row "
                    f"`{engine_nightly_downstream_focus or '-'}` and preset "
                    f"`{engine_nightly_downstream_preset or '-'}`; "
                    + (
                        "the dry-run seam is already validated, so the next move is the non-dry-run smoke rerun."
                        if engine_nightly_downstream_dry_run_validated
                        else "run the generated dry-run seam first before executing the rerun."
                    ),
                )
            if (
                (not engine_queue_clear)
                and engine_nightly_execute_artifact
                and engine_nightly_execute_payload_pass
                and engine_nightly_execute_gate_pass
            ):
                immediate_priority.insert(
                    11,
                    "Keep "
                    f"`{engine_nightly_execute_artifact}` "
                    "open as the measured non-dry-run smoke proof: target subset "
                    f"`{engine_nightly_execute_target_subset or '-'}` with focus row "
                    f"`{engine_nightly_execute_focus or '-'}` and preset "
                    f"`{engine_nightly_execute_preset or '-'}` already passes at "
                    f"`{engine_nightly_execute_gate_mean or '-'}`"
                    + (
                        ", matching the rescored gate closely."
                        if engine_nightly_execute_matches_rescored_gate
                        else "."
                    ),
                )
            if (not engine_queue_clear) and engine_viewer_status_line:
                immediate_priority.insert(12, f"Viewer status line: `{engine_viewer_status_line}`.")
            if (not engine_queue_clear) and engine_wetlab_status_line:
                immediate_priority.insert(13, f"Wetlab status line: `{engine_wetlab_status_line}`.")
            if (not engine_queue_clear) and engine_wetlab_allatom_artifact:
                immediate_priority.insert(
                    14,
                    "Keep "
                    f"`{engine_wetlab_allatom_artifact}` "
                    "open as the exact wetlab blocker surface: "
                    f"`{engine_wetlab_allatom_primary_code or 'recompute_mean_min_distance_A'}` is first for "
                    f"`{engine_wetlab_allatom_target_id or 'selected_allatom'}` at "
                    f"`{engine_wetlab_allatom_primary_metric or 'mean_min_distance_A'}={engine_wetlab_allatom_primary_value or '-'}` "
                    f"versus `{engine_wetlab_allatom_primary_threshold or '-'}` "
                    f"(delta `{engine_wetlab_allatom_primary_delta or '-'}`), with "
                    f"`hard={engine_wetlab_allatom_hard_block_count}` and "
                    f"`semi_hard={engine_wetlab_allatom_semi_hard_block_count}` still open.",
                )
        if negative_queue_summary:
            context_clause = (
                f" Use `{negative_queue_top_source_context_artifact}` as the top source context "
                f"(`{negative_queue_top_source_context_role}`; AQP1 direct negative rows="
                f"`{negative_queue_aqp1_direct_negative_count}`, authoritative apply="
                f"`{negative_queue_aqp1_authoritative_apply_count}`)."
                if negative_queue_top_source_context_artifact
                else ""
            )
            glut1_clause = (
                f" Keep `{negative_queue_glut1_handoff_artifact}` ready for the GLUT1 follow-on negative handoff."
                if negative_queue_glut1_handoff_artifact
                else ""
            )
            immediate_priority.append(
                f"Use `runs/transporter_negative_evidence_closure_queue_current.md` as the live queue: `{_text(negative_queue_summary.get('top_target_id'))} {_text(negative_queue_summary.get('top_packet_step'))}` is first."
                + context_clause
                + glut1_clause
            )
        if negative_target_packets_summary:
            immediate_priority.append(
                "Use `runs/transporter_negative_evidence_target_packets_current.md` as the target-level handoff: "
                f"`{_text(negative_target_packets_summary.get('top_target_id'))}` is first for queue ranks "
                f"`{negative_target_packets_summary.get('top_queue_rank_start', 0)}-{negative_target_packets_summary.get('top_queue_rank_end', 0)}`, "
                "then move to the GLUT1 packet."
            )
            if _text(negative_target_packets_summary.get("aqp1_slot_closure_artifact")):
                immediate_priority.append(
                    "Use "
                    f"`{_text(negative_target_packets_summary.get('aqp1_slot_closure_artifact'))}` "
                    "as the slot-level AQP1 closure packet: "
                    f"`{_text(negative_target_packets_summary.get('aqp1_slot_closure_top_packet_step')) or 'core_non_binder_01'}` "
                    "is the first review-only slot to park."
                )
            if _text(negative_target_packets_summary.get("aqp1_negative_confirmation_artifact")):
                immediate_priority.append(
                    "Use "
                    f"`{_text(negative_target_packets_summary.get('aqp1_negative_confirmation_artifact'))}` "
                    "as the AQP1 negative confirmation packet: keep the decision at "
                    f"`{_text(negative_target_packets_summary.get('aqp1_negative_confirmation_decision'))}` "
                    "with PMID "
                    f"`{_text(negative_target_packets_summary.get('aqp1_negative_confirmation_primary_anchor_pmid'))}` "
                    "as the exact-source anchor and PMID "
                    f"`{_text(negative_target_packets_summary.get('aqp1_negative_confirmation_boundary_positive_pmid'))}` "
                    "as boundary-only context."
                )
            if _text(negative_target_packets_summary.get("aqp1_negative_slot_resolution_artifact")):
                immediate_priority.append(
                    "Use "
                    f"`{_text(negative_target_packets_summary.get('aqp1_negative_slot_resolution_artifact'))}` "
                    "as the slot-level AQP1 resolution handoff: start from "
                    f"`{_text(negative_target_packets_summary.get('aqp1_negative_slot_resolution_top_packet_step'))}` "
                    "and keep PMID "
                    f"`{_text(negative_target_packets_summary.get('aqp1_negative_slot_resolution_primary_anchor_pmid'))}` "
                    "as the first slot anchor."
                )
            if _text(negative_target_packets_summary.get("aqp1_negative_candidate_frontier_artifact")):
                immediate_priority.append(
                    "Use "
                    f"`{_text(negative_target_packets_summary.get('aqp1_negative_candidate_frontier_artifact'))}` "
                    "as the AQP1 negative frontier packet: keep "
                    f"`{_text(negative_target_packets_summary.get('aqp1_negative_candidate_frontier_primary_frontier_candidate'))}` "
                    "as the first extra exact-source frontier candidate and treat all frontier rows as review-only."
                )
            if _text(negative_target_packets_summary.get("aqp1_negative_frontier_resolution_artifact")):
                immediate_priority.append(
                    "Use "
                    f"`{_text(negative_target_packets_summary.get('aqp1_negative_frontier_resolution_artifact'))}` "
                    "as the AQP1 negative frontier-resolution handoff: keep "
                    f"`{_text(negative_target_packets_summary.get('aqp1_negative_frontier_resolution_primary_frontier_candidate'))}` "
                    "as the first indirect-context frontier row and park "
                    f"`{_text(negative_target_packets_summary.get('aqp1_negative_frontier_resolution_solvent_fallback_candidate'))}` "
                    "as solvent-only fallback."
                )
            if _text(negative_target_packets_summary.get("aqp1_negative_primary_probe_artifact")):
                immediate_priority.append(
                    "Use "
                    f"`{_text(negative_target_packets_summary.get('aqp1_negative_primary_probe_artifact'))}` "
                    "as the AQP1 primary negative-probe handoff: keep "
                    f"`{_text(negative_target_packets_summary.get('aqp1_negative_primary_probe_candidate'))}` "
                    "first, anchored to PMID "
                    f"`{_text(negative_target_packets_summary.get('aqp1_negative_primary_probe_source_anchor_pmid'))}`."
                )
            if _text(negative_target_packets_summary.get("aqp1_negative_primary_probe_resolution_artifact")):
                immediate_priority.append(
                    "Use "
                    f"`{_text(negative_target_packets_summary.get('aqp1_negative_primary_probe_resolution_artifact'))}` "
                    "as the AQP1 primary-probe resolution handoff: keep "
                    f"`{_text(negative_target_packets_summary.get('aqp1_negative_primary_probe_resolution_candidate'))}` "
                    "review-only, preserve "
                    f"`{_text(negative_target_packets_summary.get('aqp1_negative_primary_probe_resolution_solvent_fallback_candidate'))}` "
                    "as solvent fallback only, and hold the lane at decision "
                    f"`{_text(negative_target_packets_summary.get('aqp1_negative_primary_probe_resolution_decision'))}`."
                )
            if _text(negative_target_packets_summary.get("aqp1_negative_direct_evidence_audit_artifact")):
                immediate_priority.append(
                    "Use "
                    f"`{_text(negative_target_packets_summary.get('aqp1_negative_direct_evidence_audit_artifact'))}` "
                    "as the AQP1 direct-evidence audit: PubMed exact ligand/target hits="
                    f"`{negative_target_packets_summary.get('aqp1_negative_direct_evidence_audit_pubmed_exact_ligand_target_hit_count', 0)}`, "
                    "ChEMBL exact target-pair rows="
                    f"`{negative_target_packets_summary.get('aqp1_negative_direct_evidence_audit_chembl_exact_target_pair_activity_count', 0)}`, "
                    "direct negative rows="
                    f"`{negative_target_packets_summary.get('aqp1_negative_direct_evidence_audit_direct_negative_quantitative_row_found_count', 0)}`, "
                    "so keep the lane at "
                    f"`{_text(negative_target_packets_summary.get('aqp1_negative_direct_evidence_audit_decision'))}`."
                )
            if _text(negative_target_packets_summary.get("aqp1_negative_acquisition_artifact")):
                immediate_priority.append(
                    "Use "
                    f"`{_text(negative_target_packets_summary.get('aqp1_negative_acquisition_artifact'))}` "
                    "as the AQP1 negative evidence acquisition packet: start from "
                    f"`{_text(negative_target_packets_summary.get('aqp1_negative_acquisition_primary_query_label'))}` "
                    "and open the primary PubMed anchor first."
                )
            if _text(negative_target_packets_summary.get("glut1_negative_direct_evidence_audit_artifact")):
                immediate_priority.append(
                    "Use "
                    f"`{_text(negative_target_packets_summary.get('glut1_negative_direct_evidence_audit_artifact'))}` "
                    "as the GLUT1 negative direct-evidence audit: placeholder negative slots="
                    f"`{negative_target_packets_summary.get('glut1_negative_direct_evidence_audit_placeholder_negative_candidate_count', 0)}`, "
                    "positive/binder context rows="
                    f"`{negative_target_packets_summary.get('glut1_negative_direct_evidence_audit_source_context_positive_or_binder_candidate_count', 0)}`, "
                    "direct negative rows="
                    f"`{negative_target_packets_summary.get('glut1_negative_direct_evidence_audit_direct_negative_quantitative_row_found_count', 0)}`, "
                    "so keep GLUT1 at "
                    f"`{_text(negative_target_packets_summary.get('glut1_negative_direct_evidence_audit_decision'))}`."
                )
        if external_crosscheck_ready:
            immediate_priority.append(
                f"Use `{external_crosscheck_artifact}` as the skill-backed external evidence crosscheck: "
                f"AQP1 `{external_crosscheck_aqp1_uniprot}/{external_crosscheck_aqp1_chembl}` and "
                f"GLUT1 `{external_crosscheck_glut1_uniprot}/{external_crosscheck_glut1_chembl}` are mapped, "
                f"GLUT1 structure support includes `{external_crosscheck_rcsb_glut1_entry or '-'}`, "
                f"BindingDB affinities are AQP1=`{external_crosscheck_aqp1_bindingdb_count}` / "
                f"GLUT1=`{external_crosscheck_glut1_bindingdb_count}`, "
                f"GLUT1 positive exact ChEMBL activity rows=`{external_crosscheck_glut1_positive_exact_count}`, "
                f"direct negative rows=`{external_crosscheck_direct_negative_count}`, authoritative apply="
                f"`{external_crosscheck_authoritative_apply_count}`, so decision stays "
                f"`{external_crosscheck_current_decision or 'keep_transporter_negative_slots_review_only'}`."
            )
        if negative_candidate_harvest_ready:
            immediate_priority.append(
                f"Use `{negative_candidate_harvest_artifact}` as the candidate harvest board: "
                f"AQP1 review rows=`{negative_candidate_harvest_aqp1_review_count}` with quantitative lower-bound candidates="
                f"`{negative_candidate_harvest_aqp1_quant_count}`, while GLUT1 review rows="
                f"`{negative_candidate_harvest_glut1_review_count}` include "
                f"`{negative_candidate_harvest_glut1_quant_count}` ChEMBL lower-bound candidates covering up to "
                f"`{negative_candidate_harvest_glut1_cover_count}` GLUT1 negative slots. Prepare GLUT1 curation in parallel, "
                "but keep AQP1 first in the strict closure order and keep all harvested rows unapplied."
            )
        if negative_candidate_curation_queue_ready:
            immediate_priority.append(
                f"Use `{negative_candidate_curation_queue_artifact}` as the GLUT1 pre-apply curation queue: "
                f"`{negative_candidate_curation_queue_row_count}` rows cover "
                f"`{negative_candidate_curation_queue_slot_cover_count}/{negative_candidate_curation_queue_slot_count}` "
                f"GLUT1 negative slots from `{negative_candidate_curation_queue_candidate_count}` ChEMBL lower-bound candidates. "
                f"AQP1-first blocker open=`{negative_candidate_curation_queue_aqp1_blocker_open}`, "
                f"candidate apply allowed=`{negative_candidate_curation_queue_apply_allowed}`, so this is curation prework only."
            )
        if aqp1_negative_gap_matrix_ready:
            immediate_priority.append(
                f"Use `{aqp1_negative_gap_matrix_artifact}` as the AQP1 blocker matrix: "
                f"`{aqp1_negative_gap_matrix_blocked_route_count}/{aqp1_negative_gap_matrix_route_count}` evidence routes remain blocked, "
                f"direct quantitative negative rows=`{aqp1_negative_gap_matrix_direct_negative_count}`, "
                f"AQP1 slot cover=`{aqp1_negative_gap_matrix_slot_cover_ready_count}/{aqp1_negative_gap_matrix_slot_count}`. "
                "Do not reinterpret review-only literature context as negative evidence; acquire or curate exact target-pair quantitative rows."
            )
        if aqp1_negative_evidence_request_ready:
            immediate_priority.append(
                f"Use `{aqp1_negative_evidence_request_artifact}` as the AQP1 exact-evidence acquisition request: "
                f"`{aqp1_negative_evidence_request_row_count}` request rows require "
                f"`{aqp1_negative_evidence_request_required_row_count}` assignable quantitative negative rows; "
                f"current direct rows=`{aqp1_negative_evidence_request_current_direct_count}`, missing="
                f"`{aqp1_negative_evidence_request_slot_cover_missing_count}`, public reinterpretation exhausted="
                f"`{aqp1_negative_evidence_request_public_exhausted}`."
            )
        if aqp1_negative_evidence_intake_gate_ready:
            immediate_priority.append(
                f"Use `{aqp1_negative_evidence_intake_gate_artifact}` as the AQP1 evidence intake gate: "
                f"fill `{aqp1_negative_evidence_intake_gate_template_artifact or 'runs/aqp1_negative_evidence_intake_template_current.csv'}` "
                f"and rerun the gate until valid rows reach "
                f"`{aqp1_negative_evidence_intake_gate_valid_row_count}/"
                f"{aqp1_negative_evidence_intake_gate_required_row_count}`; current status="
                f"`{aqp1_negative_evidence_intake_gate_status or 'awaiting_exact_aqp1_quantitative_negative_evidence_rows'}`."
            )
        transporter_gap_line = (
            "GLUT1 binder rows are now staged as non-authoritative second-wave surfaces, so the remaining transporter gap is no longer staging but evidence-blocked negative closure."
        )
        transporter_fix_line = (
            "First, leave GLUT1 staged binder rows parked, and move transporter effort to the remaining evidence-blocked negative rows instead of reopening second-wave staging work."
        )
    if engine_queue_clear:
        report_gaps = [
            "The local delivery verdict is green only for the restricted local scope; transporter negative-evidence mining remains parked outside that claim.",
            (
                "Nightly, viewer, wetlab, and refresh lanes are now keep-green surfaces, and the trend packet is attached, but repeated-history sufficiency is not complete."
                if keep_green_trend_artifact and not keep_green_trend_sufficient_history
                else "Nightly, viewer, wetlab, and refresh lanes are now keep-green surfaces, but they still need trend history across repeated canonical runs."
            ),
            (
                "The platform-wide taxonomy now separates restricted-delivery blockers from expansion blockers, so transporter placeholder counts are no longer the only commercialization split."
                if platform_gap_taxonomy_split_resolved
                else f"Current commercialization boards show `placeholder_driven_rows={placeholder_rows}` and separate `reducible_now={reducible_now_rows}` from `evidence_blocked={evidence_blocked_rows}`, but that split is still transporter-specific rather than platform-wide."
            ),
            transporter_gap_line,
        ]
        fix_plan = [
            "First, keep the local engine queue green with recurrent canonical nightly, viewer, wetlab, and refresh regression checks before broadening the delivery claim.",
            transporter_fix_line,
            f"Third, keep the AQP1 follow-on lane `{follow_on_lane}` parked behind `{aqp1_focus}` while `{aqp1_guardrail}` stays the provenance guardrail and `replacement_reference_binding_kcal_mol` remains blank.",
            "Fourth, leave all transporter negative rows outside the delivery-ready scope until direct negative evidence is curated.",
        ]
    else:
        report_gaps = [
            "A canonical `commercialization_status_report.md` now exists, but it still overweights transporter burndown versus broader local-run commercialization gaps.",
            f"Current commercialization boards show `placeholder_driven_rows={placeholder_rows}` and separate `reducible_now={reducible_now_rows}` from `evidence_blocked={evidence_blocked_rows}`, but that split is still transporter-specific rather than platform-wide.",
            (
                "For local-only operation, the canonical report now surfaces nightly reliability and wetlab validation as active blockers while viewer usability has moved into keep-green regression coverage, but it still needs clearer closure metrics and trend history for those lanes."
                if engine_viewer_keep_green
                else "For local-only operation, the canonical report now surfaces nightly reliability, wetlab validation, and viewer usability as first-class blockers, but it still needs clearer closure metrics and trend history for those lanes."
            ),
            transporter_gap_line,
        ]
        if local_engine_queue_summary:
            report_gaps.insert(
                0,
                (
                    "The repo now has a local-engine commercialization queue, but the older family-first wording still understates the fact that "
                    "`nightly reliability` and `wetlab execution readiness` block local commercial trust sooner than another round of transporter evidence mining, while `viewer usability` now sits in keep-green regression coverage."
                    if engine_viewer_keep_green
                    else "The repo now has a local-engine commercialization queue, but the older family-first wording still understates the fact that "
                    "`nightly reliability`, `viewer usability`, and `wetlab execution readiness` block local commercial trust sooner than another round of transporter evidence mining."
                ),
            )
        fix_plan = [
            (
                "First, promote the local engine queue to the top of the commercialization board and burn down `nightly reliability` and `wetlab execution readiness` while keeping the viewer proof green before reopening low-yield evidence mining."
                if engine_viewer_keep_green
                else "First, promote the local engine queue to the top of the commercialization board and burn down `nightly reliability`, `viewer usability`, and `wetlab execution readiness` before reopening low-yield evidence mining."
            ),
            transporter_fix_line,
            f"Third, keep the AQP1 follow-on lane `{follow_on_lane}` parked behind `{aqp1_focus}` while `{aqp1_guardrail}` stays the provenance guardrail and `replacement_reference_binding_kcal_mol` remains blank.",
            "Fourth, leave all transporter negative rows in the evidence-blocked bucket until direct negative evidence is curated; do not mix them with already-staged GLUT1 binder work.",
        ]
    if external_crosscheck_ready:
        report_gaps.append(
            "External life-science database crosscheck now confirms the transporter negative lane remains evidence-blocked: "
            f"closure_allowed=`{external_crosscheck_negative_closure_allowed}`, direct negative rows="
            f"`{external_crosscheck_direct_negative_count}`, authoritative apply rows="
            f"`{external_crosscheck_authoritative_apply_count}`."
        )
        fix_plan.append(
            "Before any transporter negative promotion, refresh the external crosscheck and require exact target-pair quantitative negative evidence; "
            f"current decision is `{external_crosscheck_current_decision or 'keep_transporter_negative_slots_review_only'}`."
        )
    if negative_candidate_harvest_ready:
        report_gaps.append(
            "The target-level ChEMBL harvest changes the work shape but not the claim boundary: "
            f"GLUT1 has `{negative_candidate_harvest_glut1_quant_count}` unreviewed lower-bound candidates, "
            f"but AQP1 has `{negative_candidate_harvest_aqp1_quant_count}` and closure_allowed="
            f"`{negative_candidate_harvest_closure_allowed}`."
        )
        fix_plan.append(
            "Curate harvested GLUT1 lower-bound candidates into molecule/source/split/reference/meta packets as prework, "
            "while preserving the AQP1-first order and keeping `authoritative_negative_apply_allowed=false` until reviewer approval."
        )
    if negative_candidate_curation_queue_ready:
        report_gaps.append(
            "The GLUT1 curation queue now covers the second-wave negative slots, but it is explicitly pre-apply: "
            f"queue_status=`{negative_candidate_curation_queue_status}`, apply_allowed="
            f"`{negative_candidate_curation_queue_apply_allowed}`, and AQP1-first blocker open="
            f"`{negative_candidate_curation_queue_aqp1_blocker_open}`."
        )
        fix_plan.append(
            "Review the GLUT1 curation queue row by row for molecule identity, ChEMBL document provenance, assay semantics, "
            "split assignment, and reference/meta packet updates; keep claim promotion false until AQP1 negative closure is solved."
        )
    if aqp1_negative_gap_matrix_ready:
        report_gaps.append(
            "AQP1 is now decomposed by evidence route, and the blocker is explicit: "
            f"status=`{aqp1_negative_gap_matrix_status}`, slot cover="
            f"`{aqp1_negative_gap_matrix_slot_cover_ready_count}/{aqp1_negative_gap_matrix_slot_count}`, "
            f"missing=`{aqp1_negative_gap_matrix_slot_cover_missing_count}`, claim promotion="
            f"`{aqp1_negative_gap_matrix_claim_promotion_allowed}`."
        )
        fix_plan.append(
            "For AQP1, stop spending cycles on reinterpretation-only sources: the next acceptable closure is an exact human AQP1 "
            "target-pair quantitative weak/no-effect row with molecule identity, assay context, units, primary source, split assignment, "
            "and reference/meta packet updates."
        )
    if aqp1_negative_evidence_request_ready:
        report_gaps.append(
            "AQP1 now has an acquisition-ready exact-evidence request packet, but it still has no claim-safe rows: "
            f"request_status=`{aqp1_negative_evidence_request_status}`, required rows="
            f"`{aqp1_negative_evidence_request_required_row_count}`, direct rows="
            f"`{aqp1_negative_evidence_request_current_direct_count}`, closure_allowed="
            f"`{aqp1_negative_evidence_request_closure_allowed}`."
        )
        fix_plan.append(
            "Execute the AQP1 evidence request through public primary-source curation or an internal/CRO assay; only rows matching the "
            "request schema should enter split/reference/meta updates, and all other context stays review-only."
        )
    if aqp1_negative_evidence_intake_gate_ready:
        report_gaps.append(
            "AQP1 now has a row-level intake validator, but the current gate is still below the evidence threshold: "
            f"status=`{aqp1_negative_evidence_intake_gate_status}`, valid rows="
            f"`{aqp1_negative_evidence_intake_gate_valid_row_count}/"
            f"{aqp1_negative_evidence_intake_gate_required_row_count}`, missing="
            f"`{aqp1_negative_evidence_intake_gate_missing_row_count}`, validation error rows="
            f"`{aqp1_negative_evidence_intake_gate_error_row_count}`, apply allowed="
            f"`{aqp1_negative_evidence_intake_gate_apply_count}`."
        )
        fix_plan.append(
            "Use the AQP1 intake template as the only admissible entry point for new weak/no-effect rows; the gate must pass before "
            "split/reference/meta review, and authoritative negative apply remains false until that review is complete."
        )
    if all_tracked_commercialization_accounting_closed:
        strengths = [
            f"Tracked commercialization accounting is closed: local engine queue clear=`{engine_queue_clear}`, "
            f"platform blockers=`{platform_gap_taxonomy_current_blockers}/{platform_gap_taxonomy_expansion_blockers}`, "
            f"and repeated keep-green history=`{keep_green_trend_ready_count}/{keep_green_trend_lane_count}`.",
            f"Latest canonical GPU/HIP smoke reruns are green, with nightly pass streak "
            f"`{keep_green_trend_nightly_streak}/{keep_green_trend_min_samples}` and local queue top priority "
            f"`{engine_top_priority_id or '-'}`=`{engine_top_priority_status or '-'}`.",
            f"Transporter negative placeholders are closed for accounting; AQP1 has "
            f"`{aqp1_functional_kcal_surrogate_ready_count}` functional IC50-derived kcal surrogate rows, while direct-binding kcal remains no-claim.",
            f"CA2/PXR review-only policy is closed with `{ca2_pxr_review_only_policy_locked_row_count}` locked rows and no promotion path.",
        ]
        if accuracy_parity_ready:
            strengths.append(
                "Post-goal commercial-tool accuracy parity is now tracked separately: "
                f"status=`{accuracy_parity_status or '-'}`, allowed=`{accuracy_parity_allowed}`, "
                f"rows pass/restricted/blocked/missing="
                f"`{accuracy_parity_pass_count}/{accuracy_parity_restricted_count}/"
                f"{accuracy_parity_blocked_count}/{accuracy_parity_missing_count}`."
            )
        immediate_priority = [
            "Keep the closed accounting state green with recurring canonical nightly, viewer, wetlab, refresh, and platform taxonomy regeneration.",
            "Do not widen wording from functional surrogate/review-only evidence into direct binding, unattended decision-making, or broad platform claims.",
            "Treat future AQP1/GLUT1 direct-binding kcal evidence, larger ligand-scale suites, and non-local deployment hardening as new expansion work rather than blockers on the current /goal accounting closure.",
        ]
        if post_goal_accuracy_parity_active:
            immediate_priority.insert(
                1,
                "Open the post-goal accuracy-parity lane from `runs/accuracy_parity_scorecard_current.md`: "
                f"`{accuracy_parity_status}` with top blockers `{accuracy_parity_top_blockers_text}`.",
            )
            if gpcr_a1_ready:
                if gpcr_a1_open_rows == 0:
                    immediate_priority.insert(
                        2,
                        "`runs/gpcr_a1_accuracy_repair_queue_current.md` is cleared but claim-locked: "
                        f"`{gpcr_a1_top_repair or '-'}` metrics passed for `{gpcr_a1_top_target or '-'}`; "
                        "the next A1 move is an independent repeat before any router or commercial parity promotion.",
                    )
                    if gpcr_a1_repeat_ready:
                        immediate_priority.insert(
                            3,
                            "`runs/gpcr_a1_independent_repeat_packet_current.md` is ready: run its validate command first, "
                            f"then launch repeat tag `{gpcr_a1_repeat_tag or '-'}` if validation stays green.",
                        )
                else:
                    immediate_priority.insert(
                        2,
                        "Use `runs/gpcr_a1_accuracy_repair_queue_current.md` as the first repair board: "
                        f"`{gpcr_a1_top_repair or '-'}` for `{gpcr_a1_top_target or '-'}` "
                        f"(`{gpcr_a1_top_blocker_group or '-'}`), guarded 100k rerun allowed="
                        f"`{gpcr_a1_guarded_100k_allowed}`.",
                    )
        report_gaps = [
            "No tracked current-delivery or platform-expansion blocker remains open in the refreshed accounting artifacts.",
            "Residual science caveat: AQP1 kcal values are functional IC50-derived surrogates, not direct binding free energies.",
            "Residual policy caveat: CA2/PXR rows stay review-only or locked unless a separate authoritative promotion review is opened.",
        ]
        if post_goal_accuracy_parity_active:
            report_gaps.append(
                "Post-goal broad commercial-tool accuracy parity remains blocked outside the closed `/goal` accounting scope: "
                f"`{accuracy_parity_blocked_count}` blocked rows and `{accuracy_parity_restricted_count}` restricted-pass rows."
            )
        fix_plan = [
            "Keep `runs/platform_gap_taxonomy_packet_current.md`, `runs/local_engine_commercialization_queue_current.md`, and `runs/keep_green_regression_trend_packet_current.md` as the closure gates.",
            "Preserve `replacement_reference_binding_kcal_mol` blanks for transporter rows unless direct target-specific binding evidence is curated.",
            "Continue regression-only monitoring; open a new scoped work item for any broader Schrodinger/Galaxy/OpenMM-grade accuracy benchmark expansion.",
        ]
        if post_goal_accuracy_parity_active:
            fix_plan.append(
                gpcr_a1_next_step
                or accuracy_parity_next_step
                or "Repair the first accuracy-parity blocker and regenerate the scorecard before any broad commercial-tool claim."
            )
    artifacts = [
        "runs/local_delivery_verdict_gate_current.md",
        "runs/local_engine_commercialization_queue_current.md",
        engine_nightly_gate_artifact or "runs/nightly_gate_burndown_packet_current.md",
        engine_nightly_tuning_artifact or "runs/nightly_stage6_tuning_packet_current.md",
        engine_nightly_followup_artifact or "runs/nightly_stage6_followup_retry_packet_current.md",
        engine_nightly_sweep_artifact or "runs/nightly_stage6_tuning_sweep_packet_current.md",
        engine_nightly_probe_artifact or "runs/nightly_stage6_probe_result_packet_current.md",
        engine_nightly_promotion_artifact or "runs/nightly_stage6_probe_promotion_packet_current.md",
        engine_nightly_realization_artifact or "runs/nightly_stage6_realization_packet_current.md",
        engine_nightly_rescored_artifact or "runs/nightly_stage6_rescored_gate_packet_current.md",
        engine_nightly_downstream_artifact or "runs/nightly_stage6_downstream_rerun_packet_current.md",
        engine_nightly_execute_artifact or "runs/nightly_stage6_execute_result_packet_current.md",
        keep_green_trend_artifact or "runs/keep_green_regression_trend_packet_current.md",
        platform_gap_taxonomy_artifact or "runs/platform_gap_taxonomy_packet_current.md",
        "runs/wetlab_execution_readiness_queue_current.md",
        engine_wetlab_allatom_artifact or "runs/wetlab_selected_allatom_gate_burndown_packet_current.md",
        "runs/commercialization_readiness_current.md",
        "runs/commercialization_gap_burndown_current.md",
        "runs/family_expansion_status_rollup_current.json",
        "runs/transporter_placeholder_burndown_queue_current.md",
        "runs/transporter_negative_evidence_closure_queue_current.md",
        "runs/transporter_negative_evidence_target_packets_current.md",
        _text(negative_target_packets_summary.get("aqp1_slot_closure_artifact")) or "runs/aqp1_negative_slot_closure_packet_current.md",
        _text(negative_target_packets_summary.get("aqp1_negative_confirmation_artifact")) or "runs/aqp1_negative_evidence_confirmation_packet_current.md",
        _text(negative_target_packets_summary.get("aqp1_negative_slot_resolution_artifact")) or "runs/aqp1_negative_slot_resolution_packet_current.md",
        _text(negative_target_packets_summary.get("aqp1_negative_candidate_frontier_artifact")) or "runs/aqp1_negative_candidate_frontier_packet_current.md",
        _text(negative_target_packets_summary.get("aqp1_negative_frontier_resolution_artifact")) or "runs/aqp1_negative_frontier_resolution_packet_current.md",
        _text(negative_target_packets_summary.get("aqp1_negative_primary_probe_artifact")) or "runs/aqp1_negative_primary_probe_packet_current.md",
        _text(negative_target_packets_summary.get("aqp1_negative_primary_probe_resolution_artifact")) or "runs/aqp1_negative_primary_probe_resolution_packet_current.md",
        _text(negative_target_packets_summary.get("aqp1_negative_direct_evidence_audit_artifact")) or "runs/aqp1_negative_direct_evidence_audit_packet_current.md",
        _text(negative_target_packets_summary.get("aqp1_negative_acquisition_artifact")) or "runs/aqp1_negative_evidence_acquisition_packet_current.md",
        _text(negative_target_packets_summary.get("glut1_negative_direct_evidence_audit_artifact")) or "runs/glut1_negative_direct_evidence_audit_packet_current.md",
        external_crosscheck_artifact,
        aqp1_negative_gap_matrix_artifact,
        aqp1_negative_evidence_request_artifact,
        aqp1_negative_evidence_intake_gate_artifact,
        aqp1_negative_evidence_intake_gate_template_artifact or "runs/aqp1_negative_evidence_intake_template_current.csv",
        negative_candidate_harvest_artifact,
        negative_candidate_curation_queue_artifact,
        "runs/accuracy_parity_scorecard_current.md",
        "runs/gpcr_a1_accuracy_repair_queue_current.md",
        "runs/gpcr_a1_independent_repeat_packet_current.md",
        "runs/glut1_second_wave_source_confirmation_packet_current.md",
        "runs/glut1_second_wave_seed_row_packet_current.md",
    ]
    if engine_nightly_downstream_profile_artifact:
        artifacts.append(engine_nightly_downstream_profile_artifact)
    if engine_nightly_downstream_dry_run_status_artifact:
        artifacts.append(engine_nightly_downstream_dry_run_status_artifact)
    if engine_nightly_execute_status_artifact:
        artifacts.append(engine_nightly_execute_status_artifact)
    if engine_nightly_execute_summary_artifact:
        artifacts.append(engine_nightly_execute_summary_artifact)

    summary = {
        "top_blocker_family": top_blocker_family,
        "core_commercial_lane_score": commercialization_summary.get("core_commercial_lane_score", 0),
        "all_category_expansion_score": commercialization_summary.get("all_category_expansion_score", 0),
        "strongest_ready_families": strongest_ready_families,
        "transporter_placeholder_driven_rows": placeholder_rows,
        "reducible_now_placeholder_rows": reducible_now_rows,
        "evidence_blocked_placeholder_rows": evidence_blocked_rows,
        "immediate_reduction_target": immediate_target,
        "immediate_reduction_target_queue_start": immediate_queue_start,
        "immediate_reduction_target_queue_end": immediate_queue_end,
        "immediate_reduction_delta_if_completed": immediate_delta,
        "transporter_primary_blocker": _text(transporter_row.get("primary_blocker")),
        "transporter_claim_safe_scope": _text(transporter_row.get("claim_safe_scope")),
        "local_only_mode": local_only_mode,
        "all_tracked_commercialization_accounting_closed": all_tracked_commercialization_accounting_closed,
        "tracked_gap_accounting_closed": tracked_gap_accounting_closed,
        "gap_active_blocked_count": gap_active_blocked_count,
        "gap_raw_blocked_bucket_count": gap_raw_blocked_bucket_count,
        "gap_parked_or_review_only_blocked_count": gap_parked_or_review_only_blocked_count,
        "family_accounting_closed": family_accounting_closed,
        "platform_accounting_closed": platform_accounting_closed,
        "transporter_negative_accounting_closed": transporter_negative_accounting_closed,
        "aqp1_functional_kcal_surrogate_closure_allowed": aqp1_functional_kcal_surrogate_closure_allowed,
        "aqp1_functional_kcal_surrogate_ready_count": aqp1_functional_kcal_surrogate_ready_count,
        "aqp1_direct_binding_gap_still_open": aqp1_direct_binding_gap_still_open,
        "ca2_pxr_review_policy_closure_allowed": ca2_pxr_review_policy_closure_allowed,
        "ca2_pxr_review_only_policy_locked_row_count": ca2_pxr_review_only_policy_locked_row_count,
        "post_goal_accuracy_parity_active": post_goal_accuracy_parity_active,
        "accuracy_parity_scorecard_ready": accuracy_parity_ready,
        "accuracy_parity_status": accuracy_parity_status,
        "accuracy_parity_overall_commercial_tool_accuracy_parity_allowed": accuracy_parity_allowed,
        "accuracy_parity_pass_row_count": accuracy_parity_pass_count,
        "accuracy_parity_restricted_pass_row_count": accuracy_parity_restricted_count,
        "accuracy_parity_blocked_row_count": accuracy_parity_blocked_count,
        "accuracy_parity_missing_row_count": accuracy_parity_missing_count,
        "accuracy_parity_broad_accuracy_estimate_pct": _text(
            accuracy_parity_summary.get("current_broad_accuracy_parity_estimate_pct")
        ),
        "accuracy_parity_broad_commercial_platform_estimate_pct": _text(
            accuracy_parity_summary.get("current_broad_commercial_platform_estimate_pct")
        ),
        "accuracy_parity_top_blockers": accuracy_parity_top_blockers,
        "gpcr_a1_accuracy_repair_queue_ready": gpcr_a1_ready,
        "gpcr_a1_accuracy_repair_queue_status": gpcr_a1_status,
        "gpcr_a1_accuracy_repair_queue_top_priority_repair_id": gpcr_a1_top_repair,
        "gpcr_a1_accuracy_repair_queue_top_priority_target": gpcr_a1_top_target,
        "gpcr_a1_accuracy_repair_queue_top_priority_blocker_group": gpcr_a1_top_blocker_group,
        "gpcr_a1_accuracy_repair_queue_open_queue_row_count": gpcr_a1_open_rows,
        "gpcr_a1_accuracy_repair_queue_guarded_100k_rerun_allowed_now": gpcr_a1_guarded_100k_allowed,
        "gpcr_a1_independent_repeat_packet_ready": bool(gpcr_a1_repeat_summary),
        "gpcr_a1_independent_repeat_status": gpcr_a1_repeat_status,
        "gpcr_a1_independent_repeat_ready": gpcr_a1_repeat_ready,
        "gpcr_a1_independent_repeat_completed": gpcr_a1_repeat_completed,
        "gpcr_a1_independent_repeat_result_passed": gpcr_a1_repeat_result_passed,
        "gpcr_a1_independent_repeat_claim_locked": gpcr_a1_repeat_claim_locked,
        "gpcr_a1_independent_repeat_result_state": gpcr_a1_repeat_result_state,
        "gpcr_a1_independent_repeat_blocker_count": gpcr_a1_repeat_blocker_count,
        "gpcr_a1_independent_repeat_tag": gpcr_a1_repeat_tag,
        "gpcr_a1_independent_repeat_validate_command": gpcr_a1_repeat_validate_command,
        "gpcr_a1_independent_repeat_run_command": gpcr_a1_repeat_run_command,
        "negative_evidence_queue_ready": bool(negative_queue_summary),
        "negative_evidence_queue_top_target_id": _text(negative_queue_summary.get("top_target_id")),
        "negative_evidence_queue_top_packet_step": _text(negative_queue_summary.get("top_packet_step")),
        "negative_evidence_queue_top_source_context_artifact": negative_queue_top_source_context_artifact,
        "negative_evidence_queue_top_source_context_role": negative_queue_top_source_context_role,
        "negative_evidence_queue_aqp1_source_context_focus_ligand": negative_queue_aqp1_focus_ligand,
        "negative_evidence_queue_aqp1_direct_negative_quantitative_row_found_count": negative_queue_aqp1_direct_negative_count,
        "negative_evidence_queue_aqp1_authoritative_negative_apply_allowed_count": negative_queue_aqp1_authoritative_apply_count,
        "negative_evidence_queue_glut1_negative_handoff_artifact": negative_queue_glut1_handoff_artifact,
        "negative_target_packets_ready": bool(negative_target_packets_summary),
        "negative_target_packets_top_target_id": _text(negative_target_packets_summary.get("top_target_id")),
        "negative_target_packets_top_queue_rank_start": negative_target_packets_summary.get("top_queue_rank_start", 0),
        "negative_target_packets_top_queue_rank_end": negative_target_packets_summary.get("top_queue_rank_end", 0),
        "negative_target_packets_aqp1_direct_evidence_audit_artifact": _text(
            negative_target_packets_summary.get("aqp1_negative_direct_evidence_audit_artifact")
        ),
        "negative_target_packets_aqp1_direct_evidence_audit_pubmed_exact_ligand_target_hit_count": negative_target_packets_summary.get(
            "aqp1_negative_direct_evidence_audit_pubmed_exact_ligand_target_hit_count", 0
        ),
        "negative_target_packets_aqp1_direct_evidence_audit_chembl_exact_target_pair_activity_count": negative_target_packets_summary.get(
            "aqp1_negative_direct_evidence_audit_chembl_exact_target_pair_activity_count", 0
        ),
        "negative_target_packets_aqp1_direct_evidence_audit_direct_negative_quantitative_row_found_count": negative_target_packets_summary.get(
            "aqp1_negative_direct_evidence_audit_direct_negative_quantitative_row_found_count", 0
        ),
        "negative_target_packets_aqp1_direct_evidence_audit_decision": _text(
            negative_target_packets_summary.get("aqp1_negative_direct_evidence_audit_decision")
        ),
        "negative_target_packets_glut1_direct_evidence_audit_artifact": _text(
            negative_target_packets_summary.get("glut1_negative_direct_evidence_audit_artifact")
        ),
        "negative_target_packets_glut1_direct_evidence_audit_placeholder_negative_candidate_count": negative_target_packets_summary.get(
            "glut1_negative_direct_evidence_audit_placeholder_negative_candidate_count", 0
        ),
        "negative_target_packets_glut1_direct_evidence_audit_source_context_positive_or_binder_candidate_count": negative_target_packets_summary.get(
            "glut1_negative_direct_evidence_audit_source_context_positive_or_binder_candidate_count", 0
        ),
        "negative_target_packets_glut1_direct_evidence_audit_direct_negative_quantitative_row_found_count": negative_target_packets_summary.get(
            "glut1_negative_direct_evidence_audit_direct_negative_quantitative_row_found_count", 0
        ),
        "negative_target_packets_glut1_direct_evidence_audit_decision": _text(
            negative_target_packets_summary.get("glut1_negative_direct_evidence_audit_decision")
        ),
        "local_engine_queue_ready": bool(local_engine_queue_summary),
        "local_engine_queue_clear": engine_queue_clear,
        "local_engine_queue_top_priority_id": engine_top_priority_id,
        "local_engine_queue_top_priority_status": engine_top_priority_status,
        "local_engine_queue_blocked_count": engine_blocked_count,
        "local_engine_queue_partial_count": engine_partial_count,
        "local_engine_queue_keep_green_count": engine_keep_green_count,
        "local_engine_queue_parked_science_blocker_count": engine_parked_count,
        "local_delivery_ready": delivery_ready,
        "effective_delivery_ready": effective_delivery_ready,
        "local_delivery_queue_mismatch": local_delivery_queue_mismatch,
        "local_delivery_verdict": delivery_verdict,
        "local_delivery_p0_blocker_count": delivery_p0_count,
        "local_delivery_hard_blocker_count": delivery_hard_count,
        "local_delivery_status_line": delivery_status_line,
        "effective_delivery_status_line": effective_delivery_status_line,
        "keep_green_trend_ready": bool(keep_green_trend_summary),
        "keep_green_trend_artifact": keep_green_trend_artifact,
        "keep_green_trend_status": keep_green_trend_status,
        "keep_green_trend_all_current_green": keep_green_trend_all_current_green,
        "keep_green_trend_sufficient_repeated_history": keep_green_trend_sufficient_history,
        "keep_green_trend_current_green_lane_count": keep_green_trend_current_green_count,
        "keep_green_trend_lane_count": keep_green_trend_lane_count,
        "keep_green_trend_repeated_history_ready_lane_count": keep_green_trend_ready_count,
        "keep_green_trend_insufficient_history_lane_count": keep_green_trend_insufficient_count,
        "keep_green_trend_minimum_repeated_sample_count": keep_green_trend_min_samples,
        "keep_green_trend_nightly_recent_pass_streak": keep_green_trend_nightly_streak,
        "platform_gap_taxonomy_ready": bool(platform_gap_taxonomy_summary),
        "platform_gap_taxonomy_accounting_closed": platform_accounting_closed,
        "platform_gap_taxonomy_artifact": platform_gap_taxonomy_artifact,
        "platform_gap_taxonomy_current_delivery_blocker_count": platform_gap_taxonomy_current_blockers,
        "platform_gap_taxonomy_expansion_blocker_count": platform_gap_taxonomy_expansion_blockers,
        "platform_gap_taxonomy_non_transporter_gap_count": platform_gap_taxonomy_non_transporter_count,
        "platform_gap_taxonomy_transporter_specific_split_resolved": platform_gap_taxonomy_split_resolved,
        "platform_gap_taxonomy_top_expansion_gap_id": platform_gap_taxonomy_top_gap,
        "platform_gap_taxonomy_top_expansion_gap_class": platform_gap_taxonomy_top_class,
        "platform_gap_taxonomy_ligand_scaleup_claim_safe_status": platform_gap_taxonomy_scaleup_status,
        "external_evidence_crosscheck_ready": external_crosscheck_ready,
        "external_evidence_crosscheck_artifact": external_crosscheck_artifact if external_crosscheck_ready else "",
        "external_evidence_crosscheck_skill_family": external_crosscheck_skill_family,
        "external_evidence_crosscheck_skill_source_count": external_crosscheck_skill_source_count,
        "external_evidence_crosscheck_target_count": external_crosscheck_target_count,
        "external_evidence_crosscheck_row_count": external_crosscheck_row_count,
        "external_evidence_crosscheck_aqp1_uniprot_accession": external_crosscheck_aqp1_uniprot,
        "external_evidence_crosscheck_glut1_uniprot_accession": external_crosscheck_glut1_uniprot,
        "external_evidence_crosscheck_aqp1_chembl_target_id": external_crosscheck_aqp1_chembl,
        "external_evidence_crosscheck_glut1_chembl_target_id": external_crosscheck_glut1_chembl,
        "external_evidence_crosscheck_rcsb_glut1_entry": external_crosscheck_rcsb_glut1_entry,
        "external_evidence_crosscheck_aqp1_bindingdb_affinity_count": external_crosscheck_aqp1_bindingdb_count,
        "external_evidence_crosscheck_glut1_bindingdb_affinity_count": external_crosscheck_glut1_bindingdb_count,
        "external_evidence_crosscheck_glut1_positive_exact_activity_count": external_crosscheck_glut1_positive_exact_count,
        "external_evidence_crosscheck_direct_negative_quantitative_row_found_count": external_crosscheck_direct_negative_count,
        "external_evidence_crosscheck_authoritative_negative_apply_allowed_count": external_crosscheck_authoritative_apply_count,
        "external_evidence_crosscheck_negative_evidence_closure_allowed": external_crosscheck_negative_closure_allowed,
        "external_evidence_crosscheck_current_decision": external_crosscheck_current_decision,
        "external_evidence_crosscheck_next_required_step": external_crosscheck_next_required_step,
        "negative_candidate_harvest_ready": negative_candidate_harvest_ready,
        "negative_candidate_harvest_artifact": negative_candidate_harvest_artifact if negative_candidate_harvest_ready else "",
        "negative_candidate_harvest_status": (
            "archived_preclosure_candidate_harvest_not_current_blocker"
            if all_tracked_commercialization_accounting_closed
            else negative_candidate_harvest_status
        ),
        "negative_candidate_harvest_row_count": negative_candidate_harvest_row_count,
        "negative_candidate_harvest_aqp1_candidate_review_row_count": negative_candidate_harvest_aqp1_review_count,
        "negative_candidate_harvest_glut1_candidate_review_row_count": negative_candidate_harvest_glut1_review_count,
        "negative_candidate_harvest_aqp1_quantitative_lower_bound_candidate_count": negative_candidate_harvest_aqp1_quant_count,
        "negative_candidate_harvest_glut1_quantitative_lower_bound_candidate_count": negative_candidate_harvest_glut1_quant_count,
        "negative_candidate_harvest_potential_aqp1_negative_slot_cover_count": negative_candidate_harvest_aqp1_cover_count,
        "negative_candidate_harvest_potential_glut1_negative_slot_cover_count": negative_candidate_harvest_glut1_cover_count,
        "negative_candidate_harvest_unreviewed_direct_negative_quantitative_candidate_count": negative_candidate_harvest_unreviewed_quant_count,
        "negative_candidate_harvest_authoritative_negative_apply_allowed_count": negative_candidate_harvest_apply_count,
        "negative_candidate_harvest_negative_evidence_closure_allowed": negative_candidate_harvest_closure_allowed,
        "negative_candidate_curation_queue_ready": negative_candidate_curation_queue_ready,
        "negative_candidate_curation_queue_artifact": (
            negative_candidate_curation_queue_artifact if negative_candidate_curation_queue_ready else ""
        ),
        "negative_candidate_curation_queue_target_id": negative_candidate_curation_queue_target_id,
        "negative_candidate_curation_queue_status": (
            "archived_preclosure_curation_queue_not_current_blocker"
            if all_tracked_commercialization_accounting_closed
            else negative_candidate_curation_queue_status
        ),
        "negative_candidate_curation_queue_source_harvest_artifact": negative_candidate_curation_queue_source_artifact,
        "negative_candidate_curation_queue_available_quantitative_lower_bound_candidate_count": negative_candidate_curation_queue_candidate_count,
        "negative_candidate_curation_queue_target_negative_slot_count": negative_candidate_curation_queue_slot_count,
        "negative_candidate_curation_queue_row_count": negative_candidate_curation_queue_row_count,
        "negative_candidate_curation_queue_slot_cover_ready_count": negative_candidate_curation_queue_slot_cover_count,
        "negative_candidate_curation_queue_unused_candidate_count": negative_candidate_curation_queue_unused_count,
        "negative_candidate_curation_queue_aqp1_first_blocker_open": (
            False
            if all_tracked_commercialization_accounting_closed
            else negative_candidate_curation_queue_aqp1_blocker_open
        ),
        "negative_candidate_curation_queue_candidate_apply_allowed": negative_candidate_curation_queue_apply_allowed,
        "negative_candidate_curation_queue_authoritative_negative_apply_allowed_count": negative_candidate_curation_queue_authoritative_apply_count,
        "negative_candidate_curation_queue_negative_evidence_closure_allowed": negative_candidate_curation_queue_closure_allowed,
        "negative_candidate_curation_queue_claim_promotion_allowed": negative_candidate_curation_queue_claim_promotion_allowed,
        "aqp1_negative_evidence_gap_matrix_ready": aqp1_negative_gap_matrix_ready,
        "aqp1_negative_evidence_gap_matrix_artifact": (
            aqp1_negative_gap_matrix_artifact if aqp1_negative_gap_matrix_ready else ""
        ),
        "aqp1_negative_evidence_gap_matrix_status": aqp1_negative_gap_matrix_status,
        "aqp1_negative_evidence_gap_matrix_target_uniprot_accession": aqp1_negative_gap_matrix_target_accession,
        "aqp1_negative_evidence_gap_matrix_target_chembl_id": aqp1_negative_gap_matrix_target_chembl,
        "aqp1_negative_evidence_gap_matrix_negative_slot_count": aqp1_negative_gap_matrix_slot_count,
        "aqp1_negative_evidence_gap_matrix_evidence_route_count": aqp1_negative_gap_matrix_route_count,
        "aqp1_negative_evidence_gap_matrix_blocked_route_count": aqp1_negative_gap_matrix_blocked_route_count,
        "aqp1_negative_evidence_gap_matrix_review_context_route_count": aqp1_negative_gap_matrix_review_context_route_count,
        "aqp1_negative_evidence_gap_matrix_direct_negative_quantitative_row_found_count": aqp1_negative_gap_matrix_direct_negative_count,
        "aqp1_negative_evidence_gap_matrix_authoritative_negative_apply_allowed_count": aqp1_negative_gap_matrix_apply_count,
        "aqp1_negative_evidence_gap_matrix_negative_slot_cover_ready_count": aqp1_negative_gap_matrix_slot_cover_ready_count,
        "aqp1_negative_evidence_gap_matrix_negative_slot_cover_missing_count": aqp1_negative_gap_matrix_slot_cover_missing_count,
        "aqp1_negative_evidence_gap_matrix_claim_promotion_allowed": aqp1_negative_gap_matrix_claim_promotion_allowed,
        "aqp1_negative_evidence_gap_matrix_commercialization_blocker": aqp1_negative_gap_matrix_commercialization_blocker,
        "aqp1_negative_evidence_request_ready": aqp1_negative_evidence_request_ready,
        "aqp1_negative_evidence_request_artifact": (
            aqp1_negative_evidence_request_artifact if aqp1_negative_evidence_request_ready else ""
        ),
        "aqp1_negative_evidence_request_source_gap_matrix_artifact": aqp1_negative_evidence_request_source_gap_artifact,
        "aqp1_negative_evidence_request_status": aqp1_negative_evidence_request_status,
        "aqp1_negative_evidence_request_mode": aqp1_negative_evidence_request_mode,
        "aqp1_negative_evidence_request_row_count": aqp1_negative_evidence_request_row_count,
        "aqp1_negative_evidence_request_required_assignable_negative_row_count": aqp1_negative_evidence_request_required_row_count,
        "aqp1_negative_evidence_request_current_direct_negative_quantitative_row_found_count": aqp1_negative_evidence_request_current_direct_count,
        "aqp1_negative_evidence_request_negative_slot_cover_ready_count": aqp1_negative_evidence_request_slot_cover_ready_count,
        "aqp1_negative_evidence_request_negative_slot_cover_missing_count": aqp1_negative_evidence_request_slot_cover_missing_count,
        "aqp1_negative_evidence_request_blocked_gap_route_count": aqp1_negative_evidence_request_blocked_route_count,
        "aqp1_negative_evidence_request_public_reinterpretation_exhausted": aqp1_negative_evidence_request_public_exhausted,
        "aqp1_negative_evidence_request_internal_wetlab_or_primary_source_required": aqp1_negative_evidence_request_internal_or_primary_required,
        "aqp1_negative_evidence_request_authoritative_negative_apply_allowed_count": aqp1_negative_evidence_request_apply_count,
        "aqp1_negative_evidence_request_negative_evidence_closure_allowed": aqp1_negative_evidence_request_closure_allowed,
        "aqp1_negative_evidence_request_claim_promotion_allowed": aqp1_negative_evidence_request_claim_promotion_allowed,
        "aqp1_negative_evidence_intake_gate_ready": aqp1_negative_evidence_intake_gate_ready,
        "aqp1_negative_evidence_intake_gate_artifact": (
            aqp1_negative_evidence_intake_gate_artifact if aqp1_negative_evidence_intake_gate_ready else ""
        ),
        "aqp1_negative_evidence_intake_gate_request_artifact": aqp1_negative_evidence_intake_gate_request_artifact,
        "aqp1_negative_evidence_intake_gate_template_artifact": aqp1_negative_evidence_intake_gate_template_artifact,
        "aqp1_negative_evidence_intake_gate_intake_artifact": aqp1_negative_evidence_intake_gate_intake_artifact,
        "aqp1_negative_evidence_intake_gate_status": aqp1_negative_evidence_intake_gate_status,
        "aqp1_negative_evidence_intake_gate_row_count": aqp1_negative_evidence_intake_gate_row_count,
        "aqp1_negative_evidence_intake_gate_row_with_data_count": aqp1_negative_evidence_intake_gate_row_with_data_count,
        "aqp1_negative_evidence_intake_gate_valid_intake_row_count": aqp1_negative_evidence_intake_gate_valid_row_count,
        "aqp1_negative_evidence_intake_gate_required_assignable_negative_row_count": aqp1_negative_evidence_intake_gate_required_row_count,
        "aqp1_negative_evidence_intake_gate_missing_valid_intake_row_count": aqp1_negative_evidence_intake_gate_missing_row_count,
        "aqp1_negative_evidence_intake_gate_validation_error_row_count": aqp1_negative_evidence_intake_gate_error_row_count,
        "aqp1_negative_evidence_intake_gate_review_ready_row_count": aqp1_negative_evidence_intake_gate_review_ready_count,
        "aqp1_negative_evidence_intake_gate_complete": aqp1_negative_evidence_intake_gate_complete,
        "aqp1_negative_evidence_intake_gate_split_reference_meta_update_required": aqp1_negative_evidence_intake_gate_split_update_required,
        "aqp1_negative_evidence_intake_gate_authoritative_negative_apply_allowed_count": aqp1_negative_evidence_intake_gate_apply_count,
        "aqp1_negative_evidence_intake_gate_negative_evidence_closure_allowed": aqp1_negative_evidence_intake_gate_closure_allowed,
        "aqp1_negative_evidence_intake_gate_claim_promotion_allowed": aqp1_negative_evidence_intake_gate_claim_promotion_allowed,
        "local_engine_queue_nightly_gate_artifact": engine_nightly_gate_artifact,
        "local_engine_queue_nightly_status_line": engine_nightly_status_line,
        "local_engine_queue_nightly_tuning_artifact": engine_nightly_tuning_artifact,
        "local_engine_queue_nightly_tuning_focus_row_key": engine_nightly_tuning_focus,
        "local_engine_queue_nightly_followup_artifact": engine_nightly_followup_artifact,
        "local_engine_queue_nightly_followup_focus_row_key": engine_nightly_followup_focus,
        "local_engine_queue_nightly_sweep_artifact": engine_nightly_sweep_artifact,
        "local_engine_queue_nightly_sweep_focus_row_key": engine_nightly_sweep_focus,
        "local_engine_queue_nightly_sweep_primary_preset_id": engine_nightly_sweep_preset,
        "local_engine_queue_nightly_probe_artifact": engine_nightly_probe_artifact,
        "local_engine_queue_nightly_probe_focus_row_key": engine_nightly_probe_focus,
        "local_engine_queue_nightly_probe_projected_gate_pass": engine_nightly_probe_pass,
        "local_engine_queue_nightly_promotion_artifact": engine_nightly_promotion_artifact,
        "local_engine_queue_nightly_promotion_focus_row_key": engine_nightly_promotion_focus,
        "local_engine_queue_nightly_promotion_projected_gate_pass": engine_nightly_promotion_pass,
        "local_engine_queue_nightly_realization_artifact": engine_nightly_realization_artifact,
        "local_engine_queue_nightly_realization_focus_row_key": engine_nightly_realization_focus,
        "local_engine_queue_nightly_realization_primary_preset_id": engine_nightly_realization_preset,
        "local_engine_queue_nightly_realization_gate_pass": engine_nightly_realization_pass,
        "local_engine_queue_nightly_rescored_gate_artifact": engine_nightly_rescored_artifact,
        "local_engine_queue_nightly_rescored_gate_focus_row_key": engine_nightly_rescored_focus,
        "local_engine_queue_nightly_rescored_gate_primary_preset_id": engine_nightly_rescored_preset,
        "local_engine_queue_nightly_rescored_gate_pass": engine_nightly_rescored_pass,
        "local_engine_queue_nightly_downstream_rerun_artifact": engine_nightly_downstream_artifact,
        "local_engine_queue_nightly_downstream_rerun_focus_row_key": engine_nightly_downstream_focus,
        "local_engine_queue_nightly_downstream_rerun_primary_preset_id": engine_nightly_downstream_preset,
        "local_engine_queue_nightly_downstream_rerun_target_subset": engine_nightly_downstream_target_subset,
        "local_engine_queue_nightly_downstream_rerun_profile_json_artifact": engine_nightly_downstream_profile_artifact,
        "local_engine_queue_nightly_downstream_rerun_dry_run_status_artifact": engine_nightly_downstream_dry_run_status_artifact,
        "local_engine_queue_nightly_downstream_rerun_dry_run_validated": engine_nightly_downstream_dry_run_validated,
        "local_engine_queue_nightly_downstream_rerun_payload_pass": engine_nightly_downstream_payload_pass,
        "local_engine_queue_nightly_execute_artifact": engine_nightly_execute_artifact,
        "local_engine_queue_nightly_execute_focus_row_key": engine_nightly_execute_focus,
        "local_engine_queue_nightly_execute_primary_preset_id": engine_nightly_execute_preset,
        "local_engine_queue_nightly_execute_target_subset": engine_nightly_execute_target_subset,
        "local_engine_queue_nightly_execute_status_json_artifact": engine_nightly_execute_status_artifact,
        "local_engine_queue_nightly_execute_pipeline_summary_json_artifact": engine_nightly_execute_summary_artifact,
        "local_engine_queue_nightly_execute_gate_mean_min_distance_A": engine_nightly_execute_gate_mean,
        "local_engine_queue_nightly_execute_gate_pass": engine_nightly_execute_gate_pass,
        "local_engine_queue_nightly_execute_payload_pass": engine_nightly_execute_payload_pass,
        "local_engine_queue_nightly_execute_matches_rescored_gate": engine_nightly_execute_matches_rescored_gate,
        "local_engine_queue_viewer_status_line": engine_viewer_status_line,
        "local_engine_queue_wetlab_status_line": engine_wetlab_status_line,
        "local_engine_queue_wetlab_selected_allatom_gate_burndown_artifact": engine_wetlab_allatom_artifact,
        "local_engine_queue_wetlab_selected_allatom_target_id": engine_wetlab_allatom_target_id,
        "local_engine_queue_wetlab_selected_allatom_focus_artifact": engine_wetlab_allatom_focus_artifact,
        "local_engine_queue_wetlab_selected_allatom_primary_burndown_code": engine_wetlab_allatom_primary_code,
        "local_engine_queue_wetlab_selected_allatom_primary_burndown_metric": engine_wetlab_allatom_primary_metric,
        "local_engine_queue_wetlab_selected_allatom_primary_burndown_value": engine_wetlab_allatom_primary_value,
        "local_engine_queue_wetlab_selected_allatom_primary_burndown_threshold": engine_wetlab_allatom_primary_threshold,
        "local_engine_queue_wetlab_selected_allatom_primary_burndown_delta": engine_wetlab_allatom_primary_delta,
        "local_engine_queue_wetlab_selected_allatom_hard_block_count": engine_wetlab_allatom_hard_block_count,
        "local_engine_queue_wetlab_selected_allatom_semi_hard_block_count": engine_wetlab_allatom_semi_hard_block_count,
        "next_required_step": (
            (
                "All tracked commercialization accounting blockers are closed; next scoped work is post-goal commercial-tool accuracy parity."
                if post_goal_accuracy_parity_active
                else "All tracked commercialization accounting blockers are closed; keep guardrails and regression evidence attached."
            )
            if all_tracked_commercialization_accounting_closed
            else _text(local_engine_queue_summary.get("next_required_step"))
            or _text(rollup_summary.get("next_required_step"))
            or _text(gap_summary.get("next_required_step"))
        ),
        "strengths": strengths,
        "immediate_priority": immediate_priority,
        "report_gaps": report_gaps,
        "fix_plan": fix_plan,
        "artifacts": artifacts,
    }
    return {"summary": summary}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Commercialization Status Report",
        "",
        "## Snapshot",
        "",
        f"- top_blocker_family: `{s['top_blocker_family']}`",
        f"- core_commercial_lane_score: `{s['core_commercial_lane_score']}`",
        f"- all_category_expansion_score: `{s['all_category_expansion_score']}`",
        f"- strongest_ready_families: `{s['strongest_ready_families']}`",
        f"- local_only_mode: `{s['local_only_mode']}`",
        f"- all_tracked_commercialization_accounting_closed: `{s['all_tracked_commercialization_accounting_closed']}`",
        f"- tracked_gap_accounting_closed: `{s['tracked_gap_accounting_closed']}`",
        f"- gap_active_blocked_count: `{s['gap_active_blocked_count']}`",
        f"- gap_raw_blocked_bucket_count: `{s['gap_raw_blocked_bucket_count']}`",
        f"- gap_parked_or_review_only_blocked_count: `{s['gap_parked_or_review_only_blocked_count']}`",
        f"- family_accounting_closed: `{s['family_accounting_closed']}`",
        f"- platform_accounting_closed: `{s['platform_accounting_closed']}`",
        f"- transporter_negative_accounting_closed: `{s['transporter_negative_accounting_closed']}`",
        f"- aqp1_functional_kcal_surrogate_closure_allowed: `{s['aqp1_functional_kcal_surrogate_closure_allowed']}`",
        f"- aqp1_functional_kcal_surrogate_ready_count: `{s['aqp1_functional_kcal_surrogate_ready_count']}`",
        f"- aqp1_direct_binding_gap_still_open: `{s['aqp1_direct_binding_gap_still_open']}`",
        f"- ca2_pxr_review_policy_closure_allowed: `{s['ca2_pxr_review_policy_closure_allowed']}`",
        f"- ca2_pxr_review_only_policy_locked_row_count: `{s['ca2_pxr_review_only_policy_locked_row_count']}`",
        f"- post_goal_accuracy_parity_active: `{s['post_goal_accuracy_parity_active']}`",
        f"- accuracy_parity_scorecard_ready: `{s['accuracy_parity_scorecard_ready']}`",
        f"- accuracy_parity_status: `{s['accuracy_parity_status'] or '-'}`",
        f"- accuracy_parity_allowed: `{s['accuracy_parity_overall_commercial_tool_accuracy_parity_allowed']}`",
        f"- accuracy_parity_rows: `pass={s['accuracy_parity_pass_row_count']}, restricted={s['accuracy_parity_restricted_pass_row_count']}, blocked={s['accuracy_parity_blocked_row_count']}, missing={s['accuracy_parity_missing_row_count']}`",
        f"- accuracy_parity_estimates: `broad_accuracy={s['accuracy_parity_broad_accuracy_estimate_pct'] or '-'}, broad_commercial_platform={s['accuracy_parity_broad_commercial_platform_estimate_pct'] or '-'}`",
        f"- accuracy_parity_top_blockers: `{', '.join(s['accuracy_parity_top_blockers'][:4]) or '-'}`",
        f"- gpcr_a1_accuracy_repair_queue_ready: `{s['gpcr_a1_accuracy_repair_queue_ready']}`",
        f"- gpcr_a1_accuracy_repair_queue_status: `{s['gpcr_a1_accuracy_repair_queue_status'] or '-'}`",
        f"- gpcr_a1_accuracy_repair_queue_top_priority: `{s['gpcr_a1_accuracy_repair_queue_top_priority_repair_id'] or '-'} ({s['gpcr_a1_accuracy_repair_queue_top_priority_target'] or '-'})`",
        f"- gpcr_a1_accuracy_repair_queue_open_rows: `{s['gpcr_a1_accuracy_repair_queue_open_queue_row_count']}`",
        f"- gpcr_a1_accuracy_repair_queue_guarded_100k_rerun_allowed_now: `{s['gpcr_a1_accuracy_repair_queue_guarded_100k_rerun_allowed_now']}`",
        f"- gpcr_a1_independent_repeat_packet_ready: `{s['gpcr_a1_independent_repeat_packet_ready']}`",
        f"- gpcr_a1_independent_repeat_status: `{s['gpcr_a1_independent_repeat_status'] or '-'}`",
        f"- gpcr_a1_independent_repeat_ready_to_run: `{s['gpcr_a1_independent_repeat_ready']}`",
        f"- gpcr_a1_independent_repeat_completed: `{s['gpcr_a1_independent_repeat_completed']}`",
        f"- gpcr_a1_independent_repeat_result_passed: `{s['gpcr_a1_independent_repeat_result_passed']}`",
        f"- gpcr_a1_independent_repeat_claim_locked: `{s['gpcr_a1_independent_repeat_claim_locked']}`",
        f"- gpcr_a1_independent_repeat_result_state: `{s['gpcr_a1_independent_repeat_result_state']}`",
        f"- gpcr_a1_independent_repeat_blocker_count: `{s['gpcr_a1_independent_repeat_blocker_count']}`",
        f"- gpcr_a1_independent_repeat_tag: `{s['gpcr_a1_independent_repeat_tag'] or '-'}`",
        f"- transporter_placeholder_driven_rows: `{s['transporter_placeholder_driven_rows']}`",
        f"- reducible_now_placeholder_rows: `{s['reducible_now_placeholder_rows']}`",
        f"- evidence_blocked_placeholder_rows: `{s['evidence_blocked_placeholder_rows']}`",
        f"- immediate_reduction_target: `{s['immediate_reduction_target'] or '-'}`",
        f"- immediate_reduction_target_queue_range: `{s['immediate_reduction_target_queue_start']}-{s['immediate_reduction_target_queue_end']}`",
        f"- immediate_reduction_delta_if_completed: `{s['immediate_reduction_delta_if_completed']}`",
        f"- negative_evidence_queue_ready: `{s['negative_evidence_queue_ready']}`",
        f"- negative_evidence_queue_top: `{s['negative_evidence_queue_top_target_id']} {s['negative_evidence_queue_top_packet_step']}`",
        f"- negative_evidence_queue_top_source_context_artifact: `{s['negative_evidence_queue_top_source_context_artifact'] or '-'}`",
        f"- negative_evidence_queue_top_source_context_role: `{s['negative_evidence_queue_top_source_context_role'] or '-'}`",
        f"- negative_evidence_queue_aqp1_source_context_focus_ligand: `{s['negative_evidence_queue_aqp1_source_context_focus_ligand'] or '-'}`",
        f"- negative_evidence_queue_aqp1_direct_negative_quantitative_row_found_count: `{s['negative_evidence_queue_aqp1_direct_negative_quantitative_row_found_count']}`",
        f"- negative_evidence_queue_aqp1_authoritative_negative_apply_allowed_count: `{s['negative_evidence_queue_aqp1_authoritative_negative_apply_allowed_count']}`",
        f"- negative_evidence_queue_glut1_negative_handoff_artifact: `{s['negative_evidence_queue_glut1_negative_handoff_artifact'] or '-'}`",
        f"- negative_target_packets_ready: `{s['negative_target_packets_ready']}`",
        f"- negative_target_packets_top_queue: `{s['negative_target_packets_top_target_id']} {s['negative_target_packets_top_queue_rank_start']}-{s['negative_target_packets_top_queue_rank_end']}`",
        f"- negative_target_packets_aqp1_direct_evidence_audit_artifact: `{s['negative_target_packets_aqp1_direct_evidence_audit_artifact'] or '-'}`",
        f"- negative_target_packets_aqp1_direct_evidence_audit_pubmed_exact_ligand_target_hit_count: `{s['negative_target_packets_aqp1_direct_evidence_audit_pubmed_exact_ligand_target_hit_count']}`",
        f"- negative_target_packets_aqp1_direct_evidence_audit_chembl_exact_target_pair_activity_count: `{s['negative_target_packets_aqp1_direct_evidence_audit_chembl_exact_target_pair_activity_count']}`",
        f"- negative_target_packets_aqp1_direct_evidence_audit_direct_negative_quantitative_row_found_count: `{s['negative_target_packets_aqp1_direct_evidence_audit_direct_negative_quantitative_row_found_count']}`",
        f"- negative_target_packets_aqp1_direct_evidence_audit_decision: `{s['negative_target_packets_aqp1_direct_evidence_audit_decision'] or '-'}`",
        f"- negative_target_packets_glut1_direct_evidence_audit_artifact: `{s['negative_target_packets_glut1_direct_evidence_audit_artifact'] or '-'}`",
        f"- negative_target_packets_glut1_direct_evidence_audit_placeholder_negative_candidate_count: `{s['negative_target_packets_glut1_direct_evidence_audit_placeholder_negative_candidate_count']}`",
        f"- negative_target_packets_glut1_direct_evidence_audit_source_context_positive_or_binder_candidate_count: `{s['negative_target_packets_glut1_direct_evidence_audit_source_context_positive_or_binder_candidate_count']}`",
        f"- negative_target_packets_glut1_direct_evidence_audit_direct_negative_quantitative_row_found_count: `{s['negative_target_packets_glut1_direct_evidence_audit_direct_negative_quantitative_row_found_count']}`",
        f"- negative_target_packets_glut1_direct_evidence_audit_decision: `{s['negative_target_packets_glut1_direct_evidence_audit_decision'] or '-'}`",
        f"- local_engine_queue_ready: `{s['local_engine_queue_ready']}`",
        f"- local_engine_queue_clear: `{s['local_engine_queue_clear']}`",
        f"- local_engine_queue_top_priority: `{s['local_engine_queue_top_priority_id'] or '-'} ({s['local_engine_queue_top_priority_status'] or '-'})`",
        f"- local_engine_queue_blocked_count: `{s['local_engine_queue_blocked_count']}`",
        f"- local_engine_queue_partial_count: `{s['local_engine_queue_partial_count']}`",
        f"- local_engine_queue_keep_green_count: `{s['local_engine_queue_keep_green_count']}`",
        f"- local_engine_queue_parked_science_blocker_count: `{s['local_engine_queue_parked_science_blocker_count']}`",
        f"- local_delivery_ready: `{s['local_delivery_ready']}`",
        f"- effective_delivery_ready: `{s['effective_delivery_ready']}`",
        f"- local_delivery_queue_mismatch: `{s['local_delivery_queue_mismatch']}`",
        f"- local_delivery_verdict: `{s['local_delivery_verdict'] or '-'}`",
        f"- local_delivery_blockers: `p0={s['local_delivery_p0_blocker_count']}, hard={s['local_delivery_hard_blocker_count']}`",
        f"- local_delivery_status_line: `{s['local_delivery_status_line'] or '-'}`",
        f"- effective_delivery_status_line: `{s['effective_delivery_status_line'] or '-'}`",
        f"- keep_green_trend_ready: `{s['keep_green_trend_ready']}`",
        f"- keep_green_trend_artifact: `{s['keep_green_trend_artifact'] or '-'}`",
        f"- keep_green_trend_status: `{s['keep_green_trend_status'] or '-'}`",
        f"- keep_green_trend_all_current_green: `{s['keep_green_trend_all_current_green']}`",
        f"- keep_green_trend_sufficient_repeated_history: `{s['keep_green_trend_sufficient_repeated_history']}`",
        f"- keep_green_trend_lane_counts: `current={s['keep_green_trend_current_green_lane_count']}/{s['keep_green_trend_lane_count']}, repeated={s['keep_green_trend_repeated_history_ready_lane_count']}/{s['keep_green_trend_lane_count']}, insufficient={s['keep_green_trend_insufficient_history_lane_count']}`",
        f"- keep_green_trend_nightly_recent_pass_streak: `{s['keep_green_trend_nightly_recent_pass_streak']}/{s['keep_green_trend_minimum_repeated_sample_count']}`",
        f"- platform_gap_taxonomy_ready: `{s['platform_gap_taxonomy_ready']}`",
        f"- platform_gap_taxonomy_accounting_closed: `{s['platform_gap_taxonomy_accounting_closed']}`",
        f"- platform_gap_taxonomy_artifact: `{s['platform_gap_taxonomy_artifact'] or '-'}`",
        f"- platform_gap_taxonomy_current_delivery_blocker_count: `{s['platform_gap_taxonomy_current_delivery_blocker_count']}`",
        f"- platform_gap_taxonomy_expansion_blocker_count: `{s['platform_gap_taxonomy_expansion_blocker_count']}`",
        f"- platform_gap_taxonomy_non_transporter_gap_count: `{s['platform_gap_taxonomy_non_transporter_gap_count']}`",
        f"- platform_gap_taxonomy_transporter_specific_split_resolved: `{s['platform_gap_taxonomy_transporter_specific_split_resolved']}`",
        f"- platform_gap_taxonomy_top_expansion_gap: `{s['platform_gap_taxonomy_top_expansion_gap_id'] or '-'} ({s['platform_gap_taxonomy_top_expansion_gap_class'] or '-'})`",
        f"- platform_gap_taxonomy_ligand_scaleup_claim_safe_status: `{s['platform_gap_taxonomy_ligand_scaleup_claim_safe_status'] or '-'}`",
        f"- external_evidence_crosscheck_ready: `{s['external_evidence_crosscheck_ready']}`",
        f"- external_evidence_crosscheck_artifact: `{s['external_evidence_crosscheck_artifact'] or '-'}`",
        f"- external_evidence_crosscheck_skill_family: `{s['external_evidence_crosscheck_skill_family'] or '-'}`",
        f"- external_evidence_crosscheck_skill_source_count: `{s['external_evidence_crosscheck_skill_source_count']}`",
        f"- external_evidence_crosscheck_target_count: `{s['external_evidence_crosscheck_target_count']}`",
        f"- external_evidence_crosscheck_row_count: `{s['external_evidence_crosscheck_row_count']}`",
        f"- external_evidence_crosscheck_accessions: `AQP1={s['external_evidence_crosscheck_aqp1_uniprot_accession'] or '-'}, GLUT1={s['external_evidence_crosscheck_glut1_uniprot_accession'] or '-'}`",
        f"- external_evidence_crosscheck_chembl_targets: `AQP1={s['external_evidence_crosscheck_aqp1_chembl_target_id'] or '-'}, GLUT1={s['external_evidence_crosscheck_glut1_chembl_target_id'] or '-'}`",
        f"- external_evidence_crosscheck_rcsb_glut1_entry: `{s['external_evidence_crosscheck_rcsb_glut1_entry'] or '-'}`",
        f"- external_evidence_crosscheck_bindingdb_affinity_counts: `AQP1={s['external_evidence_crosscheck_aqp1_bindingdb_affinity_count']}, GLUT1={s['external_evidence_crosscheck_glut1_bindingdb_affinity_count']}`",
        f"- external_evidence_crosscheck_glut1_positive_exact_activity_count: `{s['external_evidence_crosscheck_glut1_positive_exact_activity_count']}`",
        f"- external_evidence_crosscheck_direct_negative_quantitative_row_found_count: `{s['external_evidence_crosscheck_direct_negative_quantitative_row_found_count']}`",
        f"- external_evidence_crosscheck_authoritative_negative_apply_allowed_count: `{s['external_evidence_crosscheck_authoritative_negative_apply_allowed_count']}`",
        f"- external_evidence_crosscheck_negative_evidence_closure_allowed: `{s['external_evidence_crosscheck_negative_evidence_closure_allowed']}`",
        f"- external_evidence_crosscheck_current_decision: `{s['external_evidence_crosscheck_current_decision'] or '-'}`",
        f"- negative_candidate_harvest_ready: `{s['negative_candidate_harvest_ready']}`",
        f"- negative_candidate_harvest_artifact: `{s['negative_candidate_harvest_artifact'] or '-'}`",
        f"- negative_candidate_harvest_status: `{s['negative_candidate_harvest_status'] or '-'}`",
        f"- negative_candidate_harvest_row_count: `{s['negative_candidate_harvest_row_count']}`",
        f"- negative_candidate_harvest_review_rows: `AQP1={s['negative_candidate_harvest_aqp1_candidate_review_row_count']}, GLUT1={s['negative_candidate_harvest_glut1_candidate_review_row_count']}`",
        f"- negative_candidate_harvest_quantitative_lower_bound_candidates: `AQP1={s['negative_candidate_harvest_aqp1_quantitative_lower_bound_candidate_count']}, GLUT1={s['negative_candidate_harvest_glut1_quantitative_lower_bound_candidate_count']}`",
        f"- negative_candidate_harvest_potential_slot_cover: `AQP1={s['negative_candidate_harvest_potential_aqp1_negative_slot_cover_count']}, GLUT1={s['negative_candidate_harvest_potential_glut1_negative_slot_cover_count']}`",
        f"- negative_candidate_harvest_unreviewed_direct_negative_quantitative_candidate_count: `{s['negative_candidate_harvest_unreviewed_direct_negative_quantitative_candidate_count']}`",
        f"- negative_candidate_harvest_authoritative_negative_apply_allowed_count: `{s['negative_candidate_harvest_authoritative_negative_apply_allowed_count']}`",
        f"- negative_candidate_harvest_negative_evidence_closure_allowed: `{s['negative_candidate_harvest_negative_evidence_closure_allowed']}`",
        f"- negative_candidate_curation_queue_ready: `{s['negative_candidate_curation_queue_ready']}`",
        f"- negative_candidate_curation_queue_artifact: `{s['negative_candidate_curation_queue_artifact'] or '-'}`",
        f"- negative_candidate_curation_queue_target_id: `{s['negative_candidate_curation_queue_target_id'] or '-'}`",
        f"- negative_candidate_curation_queue_status: `{s['negative_candidate_curation_queue_status'] or '-'}`",
        f"- negative_candidate_curation_queue_source_harvest_artifact: `{s['negative_candidate_curation_queue_source_harvest_artifact'] or '-'}`",
        f"- negative_candidate_curation_queue_available_quantitative_lower_bound_candidate_count: `{s['negative_candidate_curation_queue_available_quantitative_lower_bound_candidate_count']}`",
        f"- negative_candidate_curation_queue_slot_cover: `{s['negative_candidate_curation_queue_slot_cover_ready_count']}/{s['negative_candidate_curation_queue_target_negative_slot_count']}`",
        f"- negative_candidate_curation_queue_unused_candidate_count: `{s['negative_candidate_curation_queue_unused_candidate_count']}`",
        f"- negative_candidate_curation_queue_aqp1_first_blocker_open: `{s['negative_candidate_curation_queue_aqp1_first_blocker_open']}`",
        f"- negative_candidate_curation_queue_candidate_apply_allowed: `{s['negative_candidate_curation_queue_candidate_apply_allowed']}`",
        f"- negative_candidate_curation_queue_authoritative_negative_apply_allowed_count: `{s['negative_candidate_curation_queue_authoritative_negative_apply_allowed_count']}`",
        f"- negative_candidate_curation_queue_negative_evidence_closure_allowed: `{s['negative_candidate_curation_queue_negative_evidence_closure_allowed']}`",
        f"- negative_candidate_curation_queue_claim_promotion_allowed: `{s['negative_candidate_curation_queue_claim_promotion_allowed']}`",
        f"- aqp1_negative_evidence_gap_matrix_ready: `{s['aqp1_negative_evidence_gap_matrix_ready']}`",
        f"- aqp1_negative_evidence_gap_matrix_artifact: `{s['aqp1_negative_evidence_gap_matrix_artifact'] or '-'}`",
        f"- aqp1_negative_evidence_gap_matrix_status: `{s['aqp1_negative_evidence_gap_matrix_status'] or '-'}`",
        f"- aqp1_negative_evidence_gap_matrix_target_ids: `UniProt={s['aqp1_negative_evidence_gap_matrix_target_uniprot_accession'] or '-'}, ChEMBL={s['aqp1_negative_evidence_gap_matrix_target_chembl_id'] or '-'}`",
        f"- aqp1_negative_evidence_gap_matrix_routes: `blocked={s['aqp1_negative_evidence_gap_matrix_blocked_route_count']}/{s['aqp1_negative_evidence_gap_matrix_evidence_route_count']}, review_context={s['aqp1_negative_evidence_gap_matrix_review_context_route_count']}`",
        f"- aqp1_negative_evidence_gap_matrix_direct_negative_quantitative_row_found_count: `{s['aqp1_negative_evidence_gap_matrix_direct_negative_quantitative_row_found_count']}`",
        f"- aqp1_negative_evidence_gap_matrix_authoritative_negative_apply_allowed_count: `{s['aqp1_negative_evidence_gap_matrix_authoritative_negative_apply_allowed_count']}`",
        f"- aqp1_negative_evidence_gap_matrix_slot_cover: `{s['aqp1_negative_evidence_gap_matrix_negative_slot_cover_ready_count']}/{s['aqp1_negative_evidence_gap_matrix_negative_slot_count']}`",
        f"- aqp1_negative_evidence_gap_matrix_negative_slot_cover_missing_count: `{s['aqp1_negative_evidence_gap_matrix_negative_slot_cover_missing_count']}`",
        f"- aqp1_negative_evidence_gap_matrix_claim_promotion_allowed: `{s['aqp1_negative_evidence_gap_matrix_claim_promotion_allowed']}`",
        f"- aqp1_negative_evidence_gap_matrix_commercialization_blocker: `{s['aqp1_negative_evidence_gap_matrix_commercialization_blocker'] or '-'}`",
        f"- aqp1_negative_evidence_request_ready: `{s['aqp1_negative_evidence_request_ready']}`",
        f"- aqp1_negative_evidence_request_artifact: `{s['aqp1_negative_evidence_request_artifact'] or '-'}`",
        f"- aqp1_negative_evidence_request_source_gap_matrix_artifact: `{s['aqp1_negative_evidence_request_source_gap_matrix_artifact'] or '-'}`",
        f"- aqp1_negative_evidence_request_status: `{s['aqp1_negative_evidence_request_status'] or '-'}`",
        f"- aqp1_negative_evidence_request_mode: `{s['aqp1_negative_evidence_request_mode'] or '-'}`",
        f"- aqp1_negative_evidence_request_rows: `{s['aqp1_negative_evidence_request_row_count']}/{s['aqp1_negative_evidence_request_required_assignable_negative_row_count']}`",
        f"- aqp1_negative_evidence_request_current_direct_negative_quantitative_row_found_count: `{s['aqp1_negative_evidence_request_current_direct_negative_quantitative_row_found_count']}`",
        f"- aqp1_negative_evidence_request_slot_cover: `{s['aqp1_negative_evidence_request_negative_slot_cover_ready_count']}/{s['aqp1_negative_evidence_request_required_assignable_negative_row_count']}`",
        f"- aqp1_negative_evidence_request_negative_slot_cover_missing_count: `{s['aqp1_negative_evidence_request_negative_slot_cover_missing_count']}`",
        f"- aqp1_negative_evidence_request_blocked_gap_route_count: `{s['aqp1_negative_evidence_request_blocked_gap_route_count']}`",
        f"- aqp1_negative_evidence_request_public_reinterpretation_exhausted: `{s['aqp1_negative_evidence_request_public_reinterpretation_exhausted']}`",
        f"- aqp1_negative_evidence_request_internal_wetlab_or_primary_source_required: `{s['aqp1_negative_evidence_request_internal_wetlab_or_primary_source_required']}`",
        f"- aqp1_negative_evidence_request_authoritative_negative_apply_allowed_count: `{s['aqp1_negative_evidence_request_authoritative_negative_apply_allowed_count']}`",
        f"- aqp1_negative_evidence_request_negative_evidence_closure_allowed: `{s['aqp1_negative_evidence_request_negative_evidence_closure_allowed']}`",
        f"- aqp1_negative_evidence_request_claim_promotion_allowed: `{s['aqp1_negative_evidence_request_claim_promotion_allowed']}`",
        f"- aqp1_negative_evidence_intake_gate_ready: `{s['aqp1_negative_evidence_intake_gate_ready']}`",
        f"- aqp1_negative_evidence_intake_gate_artifact: `{s['aqp1_negative_evidence_intake_gate_artifact'] or '-'}`",
        f"- aqp1_negative_evidence_intake_gate_request_artifact: `{s['aqp1_negative_evidence_intake_gate_request_artifact'] or '-'}`",
        f"- aqp1_negative_evidence_intake_gate_template_artifact: `{s['aqp1_negative_evidence_intake_gate_template_artifact'] or '-'}`",
        f"- aqp1_negative_evidence_intake_gate_intake_artifact: `{s['aqp1_negative_evidence_intake_gate_intake_artifact'] or '-'}`",
        f"- aqp1_negative_evidence_intake_gate_status: `{s['aqp1_negative_evidence_intake_gate_status'] or '-'}`",
        f"- aqp1_negative_evidence_intake_gate_rows: `valid={s['aqp1_negative_evidence_intake_gate_valid_intake_row_count']}/{s['aqp1_negative_evidence_intake_gate_required_assignable_negative_row_count']}, data={s['aqp1_negative_evidence_intake_gate_row_with_data_count']}, total={s['aqp1_negative_evidence_intake_gate_row_count']}`",
        f"- aqp1_negative_evidence_intake_gate_missing_valid_intake_row_count: `{s['aqp1_negative_evidence_intake_gate_missing_valid_intake_row_count']}`",
        f"- aqp1_negative_evidence_intake_gate_validation_error_row_count: `{s['aqp1_negative_evidence_intake_gate_validation_error_row_count']}`",
        f"- aqp1_negative_evidence_intake_gate_review_ready_row_count: `{s['aqp1_negative_evidence_intake_gate_review_ready_row_count']}`",
        f"- aqp1_negative_evidence_intake_gate_complete: `{s['aqp1_negative_evidence_intake_gate_complete']}`",
        f"- aqp1_negative_evidence_intake_gate_split_reference_meta_update_required: `{s['aqp1_negative_evidence_intake_gate_split_reference_meta_update_required']}`",
        f"- aqp1_negative_evidence_intake_gate_authoritative_negative_apply_allowed_count: `{s['aqp1_negative_evidence_intake_gate_authoritative_negative_apply_allowed_count']}`",
        f"- aqp1_negative_evidence_intake_gate_negative_evidence_closure_allowed: `{s['aqp1_negative_evidence_intake_gate_negative_evidence_closure_allowed']}`",
        f"- aqp1_negative_evidence_intake_gate_claim_promotion_allowed: `{s['aqp1_negative_evidence_intake_gate_claim_promotion_allowed']}`",
        f"- local_engine_queue_nightly_gate_artifact: `{s['local_engine_queue_nightly_gate_artifact'] or '-'}`",
        f"- local_engine_queue_nightly_status_line: `{s['local_engine_queue_nightly_status_line'] or '-'}`",
        f"- local_engine_queue_nightly_tuning_artifact: `{s['local_engine_queue_nightly_tuning_artifact'] or '-'}`",
        f"- local_engine_queue_nightly_tuning_focus_row_key: `{s['local_engine_queue_nightly_tuning_focus_row_key'] or '-'}`",
        f"- local_engine_queue_nightly_followup_artifact: `{s['local_engine_queue_nightly_followup_artifact'] or '-'}`",
        f"- local_engine_queue_nightly_followup_focus_row_key: `{s['local_engine_queue_nightly_followup_focus_row_key'] or '-'}`",
        f"- local_engine_queue_nightly_sweep_artifact: `{s['local_engine_queue_nightly_sweep_artifact'] or '-'}`",
        f"- local_engine_queue_nightly_sweep_focus_row_key: `{s['local_engine_queue_nightly_sweep_focus_row_key'] or '-'}`",
        f"- local_engine_queue_nightly_sweep_primary_preset_id: `{s['local_engine_queue_nightly_sweep_primary_preset_id'] or '-'}`",
        f"- local_engine_queue_nightly_probe_artifact: `{s['local_engine_queue_nightly_probe_artifact'] or '-'}`",
        f"- local_engine_queue_nightly_probe_focus_row_key: `{s['local_engine_queue_nightly_probe_focus_row_key'] or '-'}`",
        f"- local_engine_queue_nightly_probe_projected_gate_pass: `{s['local_engine_queue_nightly_probe_projected_gate_pass']}`",
        f"- local_engine_queue_nightly_promotion_artifact: `{s['local_engine_queue_nightly_promotion_artifact'] or '-'}`",
        f"- local_engine_queue_nightly_promotion_focus_row_key: `{s['local_engine_queue_nightly_promotion_focus_row_key'] or '-'}`",
        f"- local_engine_queue_nightly_promotion_projected_gate_pass: `{s['local_engine_queue_nightly_promotion_projected_gate_pass']}`",
        f"- local_engine_queue_nightly_realization_artifact: `{s['local_engine_queue_nightly_realization_artifact'] or '-'}`",
        f"- local_engine_queue_nightly_realization_focus_row_key: `{s['local_engine_queue_nightly_realization_focus_row_key'] or '-'}`",
        f"- local_engine_queue_nightly_realization_primary_preset_id: `{s['local_engine_queue_nightly_realization_primary_preset_id'] or '-'}`",
        f"- local_engine_queue_nightly_realization_gate_pass: `{s['local_engine_queue_nightly_realization_gate_pass']}`",
        f"- local_engine_queue_nightly_rescored_gate_artifact: `{s['local_engine_queue_nightly_rescored_gate_artifact'] or '-'}`",
        f"- local_engine_queue_nightly_rescored_gate_focus_row_key: `{s['local_engine_queue_nightly_rescored_gate_focus_row_key'] or '-'}`",
        f"- local_engine_queue_nightly_rescored_gate_primary_preset_id: `{s['local_engine_queue_nightly_rescored_gate_primary_preset_id'] or '-'}`",
        f"- local_engine_queue_nightly_rescored_gate_pass: `{s['local_engine_queue_nightly_rescored_gate_pass']}`",
        f"- local_engine_queue_nightly_downstream_rerun_artifact: `{s['local_engine_queue_nightly_downstream_rerun_artifact'] or '-'}`",
        f"- local_engine_queue_nightly_downstream_rerun_focus_row_key: `{s['local_engine_queue_nightly_downstream_rerun_focus_row_key'] or '-'}`",
        f"- local_engine_queue_nightly_downstream_rerun_primary_preset_id: `{s['local_engine_queue_nightly_downstream_rerun_primary_preset_id'] or '-'}`",
        f"- local_engine_queue_nightly_downstream_rerun_target_subset: `{s['local_engine_queue_nightly_downstream_rerun_target_subset'] or '-'}`",
        f"- local_engine_queue_nightly_downstream_rerun_profile_json_artifact: `{s['local_engine_queue_nightly_downstream_rerun_profile_json_artifact'] or '-'}`",
        f"- local_engine_queue_nightly_downstream_rerun_dry_run_status_artifact: `{s['local_engine_queue_nightly_downstream_rerun_dry_run_status_artifact'] or '-'}`",
        f"- local_engine_queue_nightly_downstream_rerun_dry_run_validated: `{s['local_engine_queue_nightly_downstream_rerun_dry_run_validated']}`",
        f"- local_engine_queue_nightly_downstream_rerun_payload_pass: `{s['local_engine_queue_nightly_downstream_rerun_payload_pass']}`",
        f"- local_engine_queue_nightly_execute_artifact: `{s['local_engine_queue_nightly_execute_artifact'] or '-'}`",
        f"- local_engine_queue_nightly_execute_focus_row_key: `{s['local_engine_queue_nightly_execute_focus_row_key'] or '-'}`",
        f"- local_engine_queue_nightly_execute_primary_preset_id: `{s['local_engine_queue_nightly_execute_primary_preset_id'] or '-'}`",
        f"- local_engine_queue_nightly_execute_target_subset: `{s['local_engine_queue_nightly_execute_target_subset'] or '-'}`",
        f"- local_engine_queue_nightly_execute_status_json_artifact: `{s['local_engine_queue_nightly_execute_status_json_artifact'] or '-'}`",
        f"- local_engine_queue_nightly_execute_pipeline_summary_json_artifact: `{s['local_engine_queue_nightly_execute_pipeline_summary_json_artifact'] or '-'}`",
        f"- local_engine_queue_nightly_execute_gate_mean_min_distance_A: `{s['local_engine_queue_nightly_execute_gate_mean_min_distance_A'] or '-'}`",
        f"- local_engine_queue_nightly_execute_gate_pass: `{s['local_engine_queue_nightly_execute_gate_pass']}`",
        f"- local_engine_queue_nightly_execute_payload_pass: `{s['local_engine_queue_nightly_execute_payload_pass']}`",
        f"- local_engine_queue_nightly_execute_matches_rescored_gate: `{s['local_engine_queue_nightly_execute_matches_rescored_gate']}`",
        f"- local_engine_queue_viewer_status_line: `{s['local_engine_queue_viewer_status_line'] or '-'}`",
        f"- local_engine_queue_wetlab_status_line: `{s['local_engine_queue_wetlab_status_line'] or '-'}`",
        f"- local_engine_queue_wetlab_selected_allatom_gate_burndown_artifact: `{s['local_engine_queue_wetlab_selected_allatom_gate_burndown_artifact'] or '-'}`",
        f"- local_engine_queue_wetlab_selected_allatom_target_id: `{s['local_engine_queue_wetlab_selected_allatom_target_id'] or '-'}`",
        f"- local_engine_queue_wetlab_selected_allatom_focus_artifact: `{s['local_engine_queue_wetlab_selected_allatom_focus_artifact'] or '-'}`",
        f"- local_engine_queue_wetlab_selected_allatom_primary_burndown_code: `{s['local_engine_queue_wetlab_selected_allatom_primary_burndown_code'] or '-'}`",
        f"- local_engine_queue_wetlab_selected_allatom_primary_burndown_metric: `{s['local_engine_queue_wetlab_selected_allatom_primary_burndown_metric'] or '-'}`",
        f"- local_engine_queue_wetlab_selected_allatom_primary_burndown_value: `{s['local_engine_queue_wetlab_selected_allatom_primary_burndown_value'] or '-'}`",
        f"- local_engine_queue_wetlab_selected_allatom_primary_burndown_threshold: `{s['local_engine_queue_wetlab_selected_allatom_primary_burndown_threshold'] or '-'}`",
        f"- local_engine_queue_wetlab_selected_allatom_primary_burndown_delta: `{s['local_engine_queue_wetlab_selected_allatom_primary_burndown_delta'] or '-'}`",
        f"- local_engine_queue_wetlab_selected_allatom_hard_block_count: `{s['local_engine_queue_wetlab_selected_allatom_hard_block_count']}`",
        f"- local_engine_queue_wetlab_selected_allatom_semi_hard_block_count: `{s['local_engine_queue_wetlab_selected_allatom_semi_hard_block_count']}`",
        "",
        "## Current State",
        "",
    ]
    for item in s["strengths"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Immediate Priority", ""])
    for item in s["immediate_priority"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Missing Pieces", ""])
    for item in s["report_gaps"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Fix Plan", ""])
    for item in s["fix_plan"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", "", "## Source Artifacts", ""])
    for item in s["artifacts"]:
        lines.append(f"- `{item}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a canonical commercialization status report from current commercialization artifacts.")
    parser.add_argument("--commercialization-json", default=DEFAULT_COMMERCIALIZATION_JSON)
    parser.add_argument("--gap-json", default=DEFAULT_GAP_JSON)
    parser.add_argument("--rollup-json", default=DEFAULT_ROLLUP_JSON)
    parser.add_argument("--placeholder-json", default=DEFAULT_PLACEHOLDER_JSON)
    parser.add_argument("--negative-queue-json", default=DEFAULT_NEGATIVE_QUEUE_JSON)
    parser.add_argument("--negative-target-packets-json", default=DEFAULT_NEGATIVE_TARGET_PACKETS_JSON)
    parser.add_argument("--local-engine-queue-json", default=DEFAULT_LOCAL_ENGINE_QUEUE_JSON)
    parser.add_argument("--local-delivery-verdict-json", default=DEFAULT_LOCAL_DELIVERY_VERDICT_JSON)
    parser.add_argument("--keep-green-trend-json", default=DEFAULT_KEEP_GREEN_TREND_JSON)
    parser.add_argument("--platform-gap-taxonomy-json", default=DEFAULT_PLATFORM_GAP_TAXONOMY_JSON)
    parser.add_argument("--external-evidence-crosscheck-json", default=DEFAULT_EXTERNAL_EVIDENCE_CROSSCHECK_JSON)
    parser.add_argument("--negative-candidate-harvest-json", default=DEFAULT_NEGATIVE_CANDIDATE_HARVEST_JSON)
    parser.add_argument("--negative-candidate-curation-queue-json", default=DEFAULT_NEGATIVE_CANDIDATE_CURATION_QUEUE_JSON)
    parser.add_argument("--aqp1-negative-evidence-gap-matrix-json", default=DEFAULT_AQP1_NEGATIVE_EVIDENCE_GAP_MATRIX_JSON)
    parser.add_argument("--aqp1-negative-evidence-request-json", default=DEFAULT_AQP1_NEGATIVE_EVIDENCE_REQUEST_JSON)
    parser.add_argument("--aqp1-negative-evidence-intake-gate-json", default=DEFAULT_AQP1_NEGATIVE_EVIDENCE_INTAKE_GATE_JSON)
    parser.add_argument("--accuracy-parity-scorecard-json", default=DEFAULT_ACCURACY_PARITY_SCORECARD_JSON)
    parser.add_argument("--gpcr-a1-accuracy-repair-queue-json", default=DEFAULT_GPCR_A1_ACCURACY_REPAIR_QUEUE_JSON)
    parser.add_argument("--gpcr-a1-independent-repeat-packet-json", default=DEFAULT_GPCR_A1_INDEPENDENT_REPEAT_PACKET_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.commercialization_json),
        _load_json(args.gap_json),
        _load_json(args.rollup_json),
        _load_json(args.placeholder_json),
        _load_json(args.negative_queue_json),
        _load_json(args.negative_target_packets_json),
        _load_json(args.local_engine_queue_json),
        _load_json(args.local_delivery_verdict_json),
        _load_json(args.keep_green_trend_json),
        _load_json(args.platform_gap_taxonomy_json),
        _load_json(args.external_evidence_crosscheck_json),
        _load_json(args.negative_candidate_harvest_json),
        _load_json(args.negative_candidate_curation_queue_json),
        _load_json(args.aqp1_negative_evidence_gap_matrix_json),
        _load_json(args.aqp1_negative_evidence_request_json),
        _load_json(args.aqp1_negative_evidence_intake_gate_json),
        _load_json(args.accuracy_parity_scorecard_json),
        _load_json(args.gpcr_a1_accuracy_repair_queue_json),
        _load_json(args.gpcr_a1_independent_repeat_packet_json),
    )
    _write_markdown(_resolve(args.out_md), payload)


if __name__ == "__main__":
    main()
