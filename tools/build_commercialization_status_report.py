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
    if local_delivery_summary and delivery_ready:
        strengths.append(
            f"Local delivery verdict is `{delivery_verdict or 'delivery_ready'}` with "
            f"`p0={delivery_p0_count}` and `hard={delivery_hard_count}` blockers."
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
            f"Current commercialization boards show `placeholder_driven_rows={placeholder_rows}` and separate `reducible_now={reducible_now_rows}` from `evidence_blocked={evidence_blocked_rows}`, but that split is still transporter-specific rather than platform-wide.",
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
        "local_delivery_verdict": delivery_verdict,
        "local_delivery_p0_blocker_count": delivery_p0_count,
        "local_delivery_hard_blocker_count": delivery_hard_count,
        "local_delivery_status_line": delivery_status_line,
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
        "next_required_step": _text(local_engine_queue_summary.get("next_required_step"))
        or _text(rollup_summary.get("next_required_step"))
        or _text(gap_summary.get("next_required_step")),
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
        f"- local_delivery_verdict: `{s['local_delivery_verdict'] or '-'}`",
        f"- local_delivery_blockers: `p0={s['local_delivery_p0_blocker_count']}, hard={s['local_delivery_hard_blocker_count']}`",
        f"- local_delivery_status_line: `{s['local_delivery_status_line'] or '-'}`",
        f"- keep_green_trend_ready: `{s['keep_green_trend_ready']}`",
        f"- keep_green_trend_artifact: `{s['keep_green_trend_artifact'] or '-'}`",
        f"- keep_green_trend_status: `{s['keep_green_trend_status'] or '-'}`",
        f"- keep_green_trend_all_current_green: `{s['keep_green_trend_all_current_green']}`",
        f"- keep_green_trend_sufficient_repeated_history: `{s['keep_green_trend_sufficient_repeated_history']}`",
        f"- keep_green_trend_lane_counts: `current={s['keep_green_trend_current_green_lane_count']}/{s['keep_green_trend_lane_count']}, repeated={s['keep_green_trend_repeated_history_ready_lane_count']}/{s['keep_green_trend_lane_count']}, insufficient={s['keep_green_trend_insufficient_history_lane_count']}`",
        f"- keep_green_trend_nightly_recent_pass_streak: `{s['keep_green_trend_nightly_recent_pass_streak']}/{s['keep_green_trend_minimum_repeated_sample_count']}`",
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
    )
    _write_markdown(_resolve(args.out_md), payload)


if __name__ == "__main__":
    main()
