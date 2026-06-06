#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import json
import re
from pathlib import Path
from typing import Any

try:
    import tools.wetlab_selected_allatom_canonical as selected_allatom_canonical_mod
except ImportError:
    class _SelectedAllatomCanonicalFallback:
        @staticmethod
        def resolve_selected_allatom_canonical(**kwargs):
            raise NotImplementedError("selected_allatom canonical resolver is not available")

    selected_allatom_canonical_mod = _SelectedAllatomCanonicalFallback()
from tools.wetlab_selected_allatom_visual import (
    resolve_selected_allatom_visual_bundle,
    selected_allatom_visual_surface_fields,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_BLUEPRINT_JSON = "runs/wetlab_wave1_campaign_blueprint_current.json"
DEFAULT_BRIEF_MATRIX_JSON = "runs/wetlab_wave1_target_brief_matrix_current.json"
DEFAULT_COMPANION_JSON = "runs/wetlab_validation_companion_panels_current.json"
DEFAULT_OUTREACH_JSON = "runs/wetlab_partner_outreach_tracks_current.json"
DEFAULT_RAIL_PACKET_INDEX_JSON = "runs/wetlab_wave1_rail_packet_index_current.json"
DEFAULT_SCHEMA_JSON = "runs/wetlab_one_page_brief_schema_current.json"
DEFAULT_DOMAIN_GENERATION_SCHEMA_JSON = "runs/wetlab_domain_generation_schema_current.json"
DEFAULT_PARTNER_EXPORT_SCHEMA_JSON = "runs/wetlab_partner_export_schema_current.json"
DEFAULT_PRIORITY3_RENDER_SPLIT_JSON = "runs/wetlab_priority3_target_render_split_current.json"
DEFAULT_MPRO_RENDER_SUITE_JSON = "runs/sarscov2_mpro_render_suite_current.json"
DEFAULT_CAIX_RENDER_SUITE_JSON = "runs/caix_render_suite_current.json"
DEFAULT_TCRUZI_PDE_RENDER_SUITE_JSON = "runs/tcruzi_pde_render_suite_current.json"
DEFAULT_PREP_ARTIFACT_LANE_JSON = "runs/wetlab_prep_artifact_lane_current.json"
DEFAULT_PRIORITY3_RUN_QUEUE_JSON = "runs/wetlab_priority3_protein_run_queue_current.json"
DEFAULT_MPRO_LAUNCH_PACKET_JSON = "runs/sarscov2_mpro_launch_packet_current.json"
DEFAULT_CAIX_LAUNCH_PACKET_JSON = "runs/caix_launch_packet_current.json"
DEFAULT_TCRUZI_PDE_LAUNCH_PACKET_JSON = "runs/tcruzi_pde_launch_packet_current.json"
DEFAULT_MPRO_RUN_RECORD_JSON = "runs/sarscov2_mpro_run_record_current.json"
DEFAULT_CAIX_RUN_RECORD_JSON = "runs/caix_run_record_current.json"
DEFAULT_TCRUZI_PDE_RUN_RECORD_JSON = "runs/tcruzi_pde_run_record_current.json"
DEFAULT_MPRO_RUN_STATUS_JSON = "runs/sarscov2_mpro_run_status_current.json"
DEFAULT_CAIX_RESULT_REVIEW_JSON = "runs/caix_result_review_current.json"
DEFAULT_TCRUZI_PDE_RESULT_REVIEW_JSON = "runs/tcruzi_pde_result_review_current.json"
DEFAULT_PRIORITY3_RUNTIME_EVENT_JSON = "runs/wetlab_priority3_runtime_event_current.json"
DEFAULT_PRIORITY3_RUNTIME_RUNBOOK_JSON = "runs/wetlab_priority3_runtime_runbook_current.json"
DEFAULT_NEXT3_RUN_QUEUE_JSON = "runs/wetlab_next3_protein_run_queue_current.json"
DEFAULT_NEXT3_CHAIN_STACK_JSON = "runs/wetlab_next3_chain_stack_current.json"
DEFAULT_NEXT3_RUNTIME_EVENT_JSON = "runs/wetlab_next3_runtime_event_current.json"
DEFAULT_NEXT3_RUNTIME_RUNBOOK_JSON = "runs/wetlab_next3_runtime_runbook_current.json"
DEFAULT_NEXT3_EXECUTION_CONSOLE_JSON = "runs/wetlab_next3_execution_console_current.json"
DEFAULT_FINAL2_RUN_QUEUE_JSON = "runs/wetlab_final2_protein_run_queue_current.json"
DEFAULT_FINAL2_CHAIN_STACK_JSON = "runs/wetlab_final2_chain_stack_current.json"
DEFAULT_FINAL2_RUNTIME_EVENT_JSON = "runs/wetlab_final2_runtime_event_current.json"
DEFAULT_FINAL2_RUNTIME_RUNBOOK_JSON = "runs/wetlab_final2_runtime_runbook_current.json"
DEFAULT_FINAL2_EXECUTION_CONSOLE_JSON = "runs/wetlab_final2_execution_console_current.json"
DEFAULT_WAVE2_RUN_QUEUE_JSON = "runs/wetlab_wave2_protein_run_queue_current.json"
DEFAULT_WAVE2_CHAIN_STACK_JSON = "runs/wetlab_wave2_chain_stack_current.json"
DEFAULT_WAVE2_RUNTIME_EVENT_JSON = "runs/wetlab_wave2_runtime_event_current.json"
DEFAULT_WAVE2_RUNTIME_RUNBOOK_JSON = "runs/wetlab_wave2_runtime_runbook_current.json"
DEFAULT_WAVE2_EXECUTION_CONSOLE_JSON = "runs/wetlab_wave2_execution_console_current.json"
DEFAULT_MASTER_QUEUE_JSON = "runs/wetlab_master_execution_queue_current.json"
DEFAULT_MASTER_RUNTIME_RUNBOOK_JSON = "runs/wetlab_master_runtime_runbook_current.json"
DEFAULT_MASTER_EXECUTION_CONSOLE_JSON = "runs/wetlab_master_execution_console_current.json"
DEFAULT_MASTER_TERMINAL_REVIEW_JSON = "runs/wetlab_master_terminal_review_current.json"
DEFAULT_OUTBOUND_EXECUTION_PRIORITY_BOARD_JSON = "runs/wetlab_outbound_execution_priority_board_current.json"
DEFAULT_FINAL_CAMPAIGN_SUMMARY_JSON = "runs/wetlab_final_campaign_summary_current.json"
DEFAULT_PARTNER_SEND_ROUND_JSON = "runs/wetlab_partner_send_round_current.json"
DEFAULT_MASTER_HANDOFF_DASHBOARD_JSON = "runs/wetlab_master_handoff_dashboard_current.json"
DEFAULT_DATA_QUALITY_ASSESSMENT_JSON = "runs/wetlab_data_quality_assessment_current.json"
DEFAULT_BROAD_SCREEN_LIBRARY_SPEC_JSON = "runs/wetlab_broad_screen_library_spec_current.json"
DEFAULT_BROAD_SCREEN_QUEUE_JSON = "runs/wetlab_broad_screen_queue_current.json"
DEFAULT_BROAD_SCREEN_BRIDGE_JSON = "runs/wetlab_broad_screen_bridge_current.json"
DEFAULT_BROAD_SCREEN_COMPOUND_UNIVERSE_JSON = "runs/wetlab_broad_screen_compound_universe_current.json"
DEFAULT_BROAD_SCREEN_BULK_RESULTS_JSON = "runs/wetlab_broad_screen_bulk_results_current.json"
DEFAULT_BROAD_SCREEN_REPURPOSING_AUTOFILL_JSON = "runs/wetlab_broad_screen_repurposing_autofill_current.json"
DEFAULT_BROAD_SCREEN_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_BROAD_SCREEN_RUNTIME_RUNBOOK_JSON = "runs/wetlab_broad_screen_runtime_runbook_current.json"
DEFAULT_BROAD_SCREEN_BULK_RESULT_SOURCE_SCHEMA_JSON = "runs/wetlab_broad_screen_bulk_result_source_schema_current.json"
DEFAULT_BROAD_SCREEN_BULK_RESULT_ROW_EXAMPLES_JSON = "runs/wetlab_broad_screen_bulk_result_row_examples_current.json"
DEFAULT_BROAD_SCREEN_TARGET_RERANK_JSON = "runs/wetlab_broad_screen_target_rerank_current.json"
DEFAULT_BROAD_SCREEN_STABILITY_SCORE_JSON = "runs/wetlab_broad_screen_stability_score_current.json"
DEFAULT_BROAD_SCREEN_ANTITARGET_QUEUE_JSON = "runs/wetlab_broad_screen_antitarget_queue_current.json"
DEFAULT_BROAD_SCREEN_ANTITARGET_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_antitarget_execution_queue_current.json"
DEFAULT_BROAD_SCREEN_PRIMARY_WATCH_STATE_JSON = "runs/wetlab_broad_screen_primary_watcher_current.json"
DEFAULT_BROAD_SCREEN_PRIMARY_WATCH_JSON = "runs/wetlab_broad_screen_primary_watcher_current.json"
LEGACY_BROAD_SCREEN_PRIMARY_WATCH_STATE_JSON = "runs/wetlab_broad_screen_primary_watch_state_current.json"
LEGACY_BROAD_SCREEN_PRIMARY_WATCH_JSON = "runs/wetlab_broad_screen_primary_watch_action_current.json"
DEFAULT_BROAD_SCREEN_ANTITARGET_WATCH_STATE_JSON = "runs/wetlab_broad_screen_antitarget_watcher_state_current.json"
DEFAULT_BROAD_SCREEN_ANTITARGET_WATCH_JSON = "runs/wetlab_broad_screen_antitarget_watcher_current.json"
DEFAULT_BROAD_SCREEN_PRIMARY_WATCH_LOOP_PID = "runs/wetlab_broad_screen_primary_watch_loop.pid"
DEFAULT_BROAD_SCREEN_ANTITARGET_WATCHER_LOOP_PID = "runs/wetlab_broad_screen_antitarget_watcher_loop.pid"
DEFAULT_BROAD_SCREEN_ACTUAL_APPEND_JSON = "runs/wetlab_broad_screen_actual_append_current.json"
DEFAULT_BROAD_SCREEN_NEXT_TARGET_EXTENSION_JSON = "runs/wetlab_broad_screen_next_target_extension_current.json"
DEFAULT_BROAD_SCREEN_THROUGHPUT_BRIDGE_JSON = "runs/wetlab_broad_screen_throughput_bridge_current.json"
DEFAULT_BROAD_SCREEN_PRIMARY_RETRY_PRESET_JSON = "runs/wetlab_primary_retry_preset_surface_current.json"
DEFAULT_BROAD_SCREEN_PRIMARY_HOLD_GUARD_JSON = "runs/wetlab_primary_hold_guard_surface_current.json"
DEFAULT_BROAD_SCREEN_CURRENT_RESULTS_INDEX_JSON = "runs/wetlab_current_results_index_current.json"
DEFAULT_BROAD_SCREEN_MONITOR_SEMANTICS_JSON = "runs/wetlab_monitor_semantics_current.json"
DEFAULT_BROAD_SCREEN_RETRY_HANDOFF_SUMMARY_JSON = "runs/wetlab_retry_handoff_summary_current.json"
DEFAULT_BROAD_SCREEN_SELECTED_ALLATOM_VISUAL_BUNDLE_JSON = "runs/selected_allatom_visual_bundle_current.json"
DEFAULT_BROAD_SCREEN_DPRE1_BRANCH_REVIEW_SURFACE_JSON = "runs/wetlab_dpre1_branch_review_surface_current.json"
DEFAULT_BROAD_SCREEN_STK17B_MANUAL_RETRY_LANE_JSON = "runs/wetlab_stk17b_manual_retry_lane_current.json"
DEFAULT_BROAD_SCREEN_STK17B_EXPLORATORY_RETRY_LANE_JSON = "runs/wetlab_stk17b_exploratory_retry_lane_current.json"
DEFAULT_BROAD_SCREEN_STK17B_EXPLORATORY_FOLLOWUP_LANE_JSON = "runs/wetlab_stk17b_exploratory_followup_lane_current.json"
DEFAULT_BROAD_SCREEN_STK17B_FOLLOWUP_REVIEW_SURFACE_JSON = "runs/wetlab_stk17b_followup_review_surface_current.json"
DEFAULT_BROAD_SCREEN_PLPRO_MANUAL_RETRY_LANE_JSON = "runs/wetlab_plpro_manual_retry_lane_current.json"
DEFAULT_BROAD_SCREEN_MAPPING_FIX_RETRY_SUPPORT_JSON = "runs/wetlab_mapping_fix_retry_support_current.json"
DEFAULT_BROAD_SCREEN_STAGE1_MAPPING_FIX_LANES_JSON = "runs/wetlab_stage1_mapping_fix_lanes_current.json"
DEFAULT_BROAD_SCREEN_MAPPING_FIX_RETRY_POLICY_TEMPLATES_JSON = "runs/wetlab_mapping_fix_retry_policy_templates_current.json"
DEFAULT_BROAD_SCREEN_HARD_TARGET_RESCUE_LANE_JSON = "runs/wetlab_hard_target_rescue_lane_current.json"
DEFAULT_BROAD_SCREEN_RESCUE_ANCHOR_ARTIFACTS_JSON = "runs/wetlab_rescue_anchor_artifacts_current.json"
DEFAULT_BROAD_SCREEN_RESCUE_THREE_BEAD_CANDIDATES_JSON = "runs/wetlab_rescue_three_bead_candidates_current.json"
DEFAULT_BROAD_SCREEN_TCRUZI_PDE_PROMOTED_TOP4_REVIEW_PACKET_JSON = "runs/wetlab_tcruzi_pde_promoted_top4_review_packet_current.json"
DEFAULT_BROAD_SCREEN_TCRUZI_PDE_RESCUE_ONLY_BRANCH_SUMMARY_JSON = "runs/wetlab_tcruzi_pde_rescue_only_branch_summary_current.json"
DEFAULT_BROAD_SCREEN_KINASE_RETRY_POLICY_TEMPLATES_JSON = "runs/wetlab_kinase_retry_policy_templates_current.json"
DEFAULT_BROAD_SCREEN_TARGET_RETRY_POLICY_TEMPLATES_JSON = "runs/wetlab_target_retry_policy_templates_current.json"
DEFAULT_BROAD_SCREEN_DENGUE_STAGE6_TUNING_SURFACE_JSON = "runs/wetlab_dengue_ns2b_ns3_protease_stage6_tuning_surface_current.json"
DEFAULT_BROAD_SCREEN_DENGUE_EXPLORATORY_RETRY_LANE_JSON = "runs/wetlab_dengue_ns2b_ns3_protease_exploratory_retry_lane_current.json"
DEFAULT_BROAD_SCREEN_LBDHODH_STAGE6_TUNING_SURFACE_JSON = "runs/wetlab_lbdhodh_stage6_tuning_surface_current.json"
DEFAULT_BROAD_SCREEN_LBDHODH_EXPLORATORY_RETRY_LANE_JSON = "runs/wetlab_lbdhodh_exploratory_retry_lane_current.json"
DEFAULT_BROAD_SCREEN_LBDHODH_GATE51_VALIDATION_REVIEW_SURFACE_JSON = "runs/wetlab_lbdhodh_gate51_validation_review_surface_current.json"
DEFAULT_QUEUE_JSON = "runs/wetlab_wave1_packet_queue_current.json"
DEFAULT_ONE_PAGE_BRIEFS_JSON = "runs/wetlab_wave1_one_page_briefs_current.json"
DEFAULT_BRIEF_INDEX_JSON = "runs/wetlab_wave1_target_brief_index_current.json"
DEFAULT_FILL_QUEUE_JSON = "runs/wetlab_wave1_brief_fill_queue_current.json"
DEFAULT_FIRST_CONTACT_JSON = "runs/wetlab_first_contact_brief_bundle_current.json"
DEFAULT_PRIORITY3_FILL_MAP_JSON = "runs/wetlab_priority3_repurposing_fill_map_current.json"
DEFAULT_PRIORITY3_NOVELTY_FILL_MAP_JSON = "runs/wetlab_priority3_novelty_fill_map_current.json"
DEFAULT_NEXT3_FILL_MAP_JSON = "runs/wetlab_next3_repurposing_fill_map_current.json"
DEFAULT_NEXT3_NOVELTY_FILL_MAP_JSON = "runs/wetlab_next3_novelty_fill_map_current.json"
DEFAULT_MPRO_VENDOR_COST_CHECK_JSON = "runs/wetlab_mpro_vendor_cost_check_current.json"
DEFAULT_FIRST_CONTACT_EXPORT_JSON = "runs/wetlab_partner_first_contact_export_bundle_current.json"
DEFAULT_CLEANUP_MANIFEST_JSON = "runs/runs_cleanup_batch2_manifest_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_partnering_stack_current.json"
DEFAULT_OUT_MD = "runs/wetlab_partnering_stack_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    root_path = (ROOT / path).resolve()
    if root_path.exists():
        return root_path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return root_path


def _resolve_output(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _maybe_load_json(path_like: str) -> dict[str, Any] | None:
    path = _resolve(path_like)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _pid_snapshot(path_like: str) -> dict[str, Any]:
    path = _resolve(path_like)
    snapshot = {
        "pid_path": str(path),
        "pid": 0,
        "pid_alive": False,
        "pid_state": "missing",
    }
    if not path.exists():
        return snapshot
    try:
        pid = int(path.read_text(encoding="utf-8").strip() or 0)
    except Exception:
        snapshot["pid_state"] = "invalid"
        return snapshot
    snapshot["pid"] = pid
    if pid <= 0:
        snapshot["pid_state"] = "invalid"
        return snapshot
    try:
        os.kill(pid, 0)
    except OSError:
        snapshot["pid_state"] = "stale"
        return snapshot
    snapshot["pid_alive"] = True
    snapshot["pid_state"] = "alive"
    return snapshot


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _text(*values: Any, default: str = "") -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return default


def _joined(*parts: Any) -> str:
    rendered: list[str] = []
    for part in parts:
        if part is None or part == "":
            continue
        if isinstance(part, (list, tuple, set)):
            text = ", ".join(str(item).strip() for item in part if str(item or "").strip())
        else:
            text = str(part).strip()
        if text:
            rendered.append(text)
    return " ".join(rendered)


def _safe_bool(*values: Any, default: bool | None = None) -> bool | None:
    for value in values:
        if isinstance(value, bool):
            return value
        if value in {"", None}:
            continue
        if isinstance(value, (int, float)):
            return bool(value)
        text = str(value).strip().lower()
        if text in {"1", "true", "t", "yes", "y", "ready", "pass", "passed"}:
            return True
        if text in {"0", "false", "f", "no", "n", "fail", "failed"}:
            return False
    return default


def _safe_int(*values: Any, default: int = 0) -> int:
    for value in values:
        try:
            if value in {"", None}:
                continue
            return int(value)
        except Exception:
            continue
    return default


def _resolve_bool(*values: Any, default: bool = False) -> bool:
    for value in values:
        parsed = _safe_bool(value)
        if parsed is not None:
            return parsed
    return default


def _has_value(summary: dict[str, Any], key: str) -> bool:
    if key not in summary:
        return False
    value = summary.get(key)
    return value is not None and value != ""


def _summary_matches_selected_allatom_focus(
    summary: dict[str, Any],
    *,
    selected_target_id: str,
    selected_surface_label: str,
) -> bool:
    target_id = _text(summary.get("selected_allatom_target_id"), summary.get("target_id"))
    surface_label = _text(
        summary.get("selected_allatom_surface_label"),
        summary.get("surface_label"),
    )
    return bool(
        target_id
        and surface_label
        and target_id == _text(selected_target_id)
        and surface_label == _text(selected_surface_label)
    )


def _selected_allatom_review_packet_metric_from_sources(
    summaries: tuple[dict[str, Any], ...],
    *,
    selected_target_id: str,
    selected_surface_label: str,
    metric_key: str,
) -> tuple[bool, float, str]:
    selected_metric_key = f"selected_allatom_{metric_key}"
    selected_source_key = f"{selected_metric_key}_source"
    for summary in summaries:
        if not summary or not _summary_matches_selected_allatom_focus(
            summary,
            selected_target_id=selected_target_id,
            selected_surface_label=selected_surface_label,
        ):
            continue
        source = _text(summary.get(selected_source_key), summary.get(f"{metric_key}_source"))
        if not source or "review_packet" not in source:
            continue
        if _has_value(summary, selected_metric_key):
            return True, _safe_float(summary.get(selected_metric_key)) or 0.0, source
        if _has_value(summary, metric_key):
            return True, _safe_float(summary.get(metric_key)) or 0.0, source
    return False, 0.0, ""


def _resolve_reported_bool(
    summaries: tuple[dict[str, Any], ...],
    *,
    reported_keys: tuple[str, ...] = (),
    value_keys: tuple[str, ...],
) -> tuple[bool, bool]:
    for summary in summaries:
        if not summary:
            continue
        for reported_key in reported_keys:
            if _has_value(summary, reported_key):
                reported = _resolve_bool(summary.get(reported_key), default=False)
                if not reported:
                    return False, False
                for value_key in value_keys:
                    if _has_value(summary, value_key):
                        return True, _resolve_bool(summary.get(value_key), default=False)
                return True, False
        for value_key in value_keys:
            if _has_value(summary, value_key):
                return True, _resolve_bool(summary.get(value_key), default=False)
    return False, False


def _safe_float(value: Any) -> float | None:
    if value in {"", None}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolve_reported_float(
    summaries: tuple[dict[str, Any], ...],
    *,
    value_keys: tuple[str, ...],
) -> tuple[bool, float]:
    for summary in summaries:
        if not summary:
            continue
        for value_key in value_keys:
            if _has_value(summary, value_key):
                return True, _safe_float(summary.get(value_key)) or 0.0
    return False, 0.0


def _resolve_text_from_summaries(
    summaries: tuple[dict[str, Any], ...],
    *,
    value_keys: tuple[str, ...],
    default: str = "",
) -> str:
    for summary in summaries:
        if not summary:
            continue
        for value_key in value_keys:
            if _has_value(summary, value_key):
                return str(summary.get(value_key, "")).strip()
    return default


def _safe_str_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item or "").strip()]
    text = str(value or "").strip()
    if not text:
        return []
    if ";" in text:
        parts = text.split(";")
    elif "," in text:
        parts = text.split(",")
    else:
        parts = [text]
    return [part.strip() for part in parts if part.strip()]


def _infer_selected_allatom_translation_shortlist_fallback(*texts: Any) -> dict[str, Any]:
    joined = " ".join(_text(text) for text in texts if _text(text))
    if not joined:
        return {"reported": False}
    translation_match = re.search(r"translation_gate=([A-Za-z0-9_]+)", joined)
    shortlist_match = re.search(r"shortlist_tier=([A-Za-z0-9_]+)", joined)
    lane_match = re.search(r"recommended_next_expensive_lane=([A-Za-z0-9_]+)", joined)
    if not any((translation_match, shortlist_match, lane_match)):
        return {"reported": False}
    return {
        "reported": True,
        "translation_gate_version": "three_bead_to_allatom_translation_v1",
        "translation_gate_focus_status": translation_match.group(1) if translation_match else "",
        "translation_gate_focus_score": None,
        "translation_gate_focus_reason": "",
        "focus_shortlist_tier": shortlist_match.group(1) if shortlist_match else "",
        "recommended_next_expensive_lane": lane_match.group(1) if lane_match else "",
        "recommended_next_expensive_lane_reason": "",
        "provenance_mode": "inferred_from_partial_upstream",
    }


def _selected_allatom_effective_blocking_order(
    *,
    hard_block_present: bool,
    claim_requirement_mode: str,
    claim_requirement_status: str,
    translation_status: str,
    commercial_hard_gate_reported_v2: bool,
    commercial_hard_gate_pass_v2: bool,
) -> str:
    if hard_block_present:
        return "hard_block_first"
    if claim_requirement_mode == "semi_hard" and claim_requirement_status == "blocked":
        return "claim_block_first"
    if commercial_hard_gate_reported_v2 and not commercial_hard_gate_pass_v2:
        return "commercial_block_first"
    if translation_status and translation_status not in {"ready", "pass", "passed"}:
        return "translation_guidance_first"
    return "ready"


def _selected_allatom_effective_primary_blocking_domain(
    *,
    hard_block_present: bool,
    commercial_hard_gate_reported_v2: bool,
    commercial_hard_gate_pass_v2: bool,
    translation_status: str,
    claim_requirement_mode: str,
    claim_requirement_status: str,
) -> str:
    if hard_block_present:
        if commercial_hard_gate_reported_v2 and not commercial_hard_gate_pass_v2:
            return "commercial_v2"
        if translation_status:
            return "translation_v2"
    if claim_requirement_mode == "semi_hard" and claim_requirement_status == "blocked":
        return "claim_equivalence"
    if translation_status and translation_status not in {"ready", "pass", "passed"}:
        return "translation_v2"
    if commercial_hard_gate_reported_v2 and not commercial_hard_gate_pass_v2:
        return "commercial_v2"
    return "none"


def _selected_allatom_action_recipe_codes(action_list: list[dict[str, Any]], required_calculations: list[str]) -> list[str]:
    codes: list[str] = []
    for calculation in required_calculations:
        text = _text(calculation)
        if text and text not in codes:
            codes.append(text)
    for item in action_list:
        for key in ("calc_action", "action"):
            text = _text(item.get(key))
            if text and text not in codes:
                codes.append(text)
    return codes


def _selected_allatom_action_recipe_rows(action_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(item) for item in action_list]


def _selected_allatom_canonical_surface(
    *,
    review_packet_summary: dict[str, Any] | None,
    retry_handoff_summary: dict[str, Any] | None,
    current_results_index_summary: dict[str, Any] | None,
    monitor_semantics_summary: dict[str, Any] | None,
    master_handoff_dashboard_summary: dict[str, Any] | None,
    final_campaign_summary: dict[str, Any] | None,
    partnering_stack_summary: dict[str, Any] | None,
    selected_allatom_sources: tuple[dict[str, Any], ...],
    selected_allatom_next_required_step: str,
    selected_allatom_focus_available: bool,
    selected_allatom_final_gate_reported: bool,
    selected_allatom_final_gate_pass: bool,
    selected_allatom_claim_gate_reported: bool,
    selected_allatom_claim_gate_available: bool,
    selected_allatom_claim_ready_reported: bool,
    selected_allatom_claim_ready_for_allatom: bool,
    selected_allatom_wetlab_gate_reported: bool,
    selected_allatom_wetlab_gate_pass: bool,
    selected_allatom_commercial_reported_v2: bool,
    selected_allatom_commercial_hard_gate_reported_v2: bool,
    selected_allatom_commercial_hard_gate_pass_v2: bool,
    selected_allatom_commercial_soft_score_v2: float,
    selected_allatom_commercial_confidence_score_v2: float,
    selected_allatom_commercial_overall_score_v2: float,
    selected_allatom_commercial_risk_bucket_v2: str,
    selected_allatom_commercial_decision_class_v2: str,
    selected_allatom_commercial_primary_upgrade_actions_v2: list[str],
    selected_allatom_commercial_human_summary_v2: str,
    selected_allatom_translation_gate_version: str,
    selected_allatom_translation_gate_focus_status: str,
    selected_allatom_translation_gate_focus_score: float,
    selected_allatom_translation_gate_focus_reason: str,
    selected_allatom_focus_shortlist_tier: str,
    selected_allatom_recommended_next_expensive_lane: str,
    selected_allatom_recommended_next_expensive_lane_reason: str,
    selected_allatom_best_mean_min_distance_A: float,
    selected_allatom_promoted_candidate_count: int,
    selected_allatom_under_2p5_candidate_count: int,
    selected_allatom_near_candidate_count: int,
) -> dict[str, Any]:
    helper_result: dict[str, Any] = {}
    try:
        helper_result = selected_allatom_canonical_mod.resolve_selected_allatom_canonical(
            review_packet_summary=review_packet_summary,
            retry_handoff_summary=retry_handoff_summary,
            current_results_index_summary=current_results_index_summary,
            monitor_semantics_summary=monitor_semantics_summary,
            master_handoff_dashboard_summary=master_handoff_dashboard_summary,
            final_campaign_summary=final_campaign_summary,
            partnering_stack_summary=partnering_stack_summary,
            next_required_step=selected_allatom_next_required_step,
        )
    except NotImplementedError:
        helper_result = {}
    except Exception:
        helper_result = {}

    summaries = tuple(
        summary
        for summary in (
            review_packet_summary,
            retry_handoff_summary,
            current_results_index_summary,
            monitor_semantics_summary,
            master_handoff_dashboard_summary,
            final_campaign_summary,
            partnering_stack_summary,
        )
        if summary
    )

    claim_requirement_mode = _resolve_text_from_summaries(
        summaries,
        value_keys=(
            "selected_allatom_claim_requirement_mode",
            "claim_gate_requirement_mode",
            "raw_claim_requirement_mode",
        ),
    )
    if not claim_requirement_mode:
        claim_requirement_mode = "semi_hard" if selected_allatom_claim_gate_reported or selected_allatom_claim_ready_reported else "not_applicable"

    claim_requirement_provenance = _resolve_text_from_summaries(
        summaries,
        value_keys=(
            "selected_allatom_claim_requirement_provenance",
            "claim_gate_requirement_provenance",
            "raw_claim_requirement_provenance",
        ),
        default="inferred_from_claim_gate_availability",
    )
    claim_required_for_final_wetlab = _resolve_bool(
        _resolve_text_from_summaries(
            summaries,
            value_keys=(
                "selected_allatom_claim_required_for_final_wetlab",
                "claim_gate_required_for_final_wetlab",
                "raw_claim_required_for_final_wetlab",
            ),
        ),
        default=claim_requirement_mode == "semi_hard",
    )
    claim_required_for_commercial_readiness = _resolve_bool(
        _resolve_text_from_summaries(
            summaries,
            value_keys=(
                "selected_allatom_claim_required_for_commercial_readiness",
                "claim_gate_required_for_commercial_readiness",
                "raw_claim_required_for_commercial_readiness",
            ),
        ),
        default=claim_requirement_mode == "semi_hard",
    )
    claim_requirement_reason = _resolve_text_from_summaries(
        summaries,
        value_keys=(
            "selected_allatom_claim_requirement_reason",
            "claim_gate_requirement_reason",
            "raw_claim_requirement_reason",
        ),
    )
    if not claim_requirement_reason:
        if claim_requirement_mode == "semi_hard":
            claim_requirement_reason = "claim/equivalence gate is required before final wetlab release."
        else:
            claim_requirement_reason = "claim/equivalence gate is not applicable for this focus."

    effective_actionability_status = _resolve_text_from_summaries(
        summaries,
        value_keys=(
            "selected_allatom_effective_actionability_status",
            "selected_allatom_actionability_status",
            "effective_actionability_status",
        ),
    )
    claim_requirement_mode_effective = _resolve_text_from_summaries(
        summaries,
        value_keys=(
            "selected_allatom_effective_actionability_claim_requirement_mode",
            "selected_allatom_actionability_claim_requirement_mode",
            "effective_actionability_claim_requirement_mode",
        ),
    )
    hard_block_present = bool(
        str(selected_allatom_translation_gate_focus_status).strip().lower() in {"fail", "blocked"}
        or (
            selected_allatom_commercial_hard_gate_reported_v2
            and not selected_allatom_commercial_hard_gate_pass_v2
        )
    )
    if not claim_requirement_mode_effective:
        claim_requirement_mode_effective = (
            "semi_hard" if claim_required_for_final_wetlab and not hard_block_present else "not_applicable"
        )
    claim_requirement_status_effective = _resolve_text_from_summaries(
        summaries,
        value_keys=(
            "selected_allatom_effective_actionability_claim_requirement_status",
            "selected_allatom_actionability_claim_requirement_status",
            "effective_actionability_claim_requirement_status",
        ),
    )
    if not claim_requirement_status_effective:
        if claim_requirement_mode_effective == "semi_hard":
            claim_requirement_status_effective = "satisfied" if selected_allatom_claim_ready_for_allatom else "blocked"
        else:
            claim_requirement_status_effective = "not_applicable"
    claim_requirement_reason_effective = _resolve_text_from_summaries(
        summaries,
        value_keys=(
            "selected_allatom_effective_actionability_claim_requirement_reason",
            "selected_allatom_actionability_claim_requirement_reason",
            "effective_actionability_claim_requirement_reason",
        ),
    )
    if not claim_requirement_reason_effective:
        if claim_requirement_mode_effective == "semi_hard" and selected_allatom_claim_ready_for_allatom:
            claim_requirement_reason_effective = "claim/equivalence gate is satisfied."
        elif claim_requirement_mode_effective == "semi_hard":
            claim_requirement_reason_effective = "claim/equivalence gate is semi-hard and blocked."
        elif hard_block_present and claim_requirement_mode == "semi_hard":
            claim_requirement_reason_effective = "claim/equivalence gate is deferred until the hard block is resolved."
        else:
            claim_requirement_reason_effective = "claim/equivalence gate is not applicable."

    translation_status = _text(selected_allatom_translation_gate_focus_status)
    recommended_lane = _text(selected_allatom_recommended_next_expensive_lane)
    recommended_lane_reason = _text(selected_allatom_recommended_next_expensive_lane_reason)
    effective_next_expensive_lane = _resolve_text_from_summaries(
        summaries,
        value_keys=(
            "selected_allatom_effective_actionability_next_expensive_lane",
            "selected_allatom_actionability_next_expensive_lane",
            "effective_actionability_next_expensive_lane",
        ),
        default=recommended_lane,
    )
    effective_next_expensive_lane_reason = _resolve_text_from_summaries(
        summaries,
        value_keys=(
            "selected_allatom_effective_actionability_next_expensive_lane_reason",
            "selected_allatom_actionability_next_expensive_lane_reason",
            "effective_actionability_next_expensive_lane_reason",
        ),
        default=recommended_lane_reason,
    )

    effective_required_calculations = _resolve_list_from_summaries(
        summaries,
        value_keys=(
            "selected_allatom_effective_actionability_required_calculations",
            "selected_allatom_actionability_required_calculations",
            "effective_actionability_required_calculations",
        ),
    )
    if not effective_required_calculations:
        if translation_status and translation_status not in {"ready", "pass", "passed"}:
            effective_required_calculations.append("recompute_mean_min_distance_A")
        if claim_requirement_mode_effective == "semi_hard" and selected_allatom_claim_ready_for_allatom is False:
            effective_required_calculations.append("resolve_claim_equivalence_gate")
    effective_required_calculations = list(dict.fromkeys(effective_required_calculations))

    effective_action_list = _resolve_list_from_summaries(
        summaries,
        value_keys=(
            "selected_allatom_effective_actionability_action_list",
            "selected_allatom_actionability_action_list",
            "effective_actionability_action_list",
        ),
    )
    if not effective_action_list:
        effective_action_list = []
        if effective_required_calculations:
            for calculation in effective_required_calculations:
                effective_action_list.append(
                    {
                        "severity": "hard" if calculation.startswith("recompute_") else "semi_hard",
                        "action": calculation,
                        "status": "required",
                    }
                )
        if effective_next_expensive_lane:
            effective_action_list.append(
                {
                    "severity": "soft",
                    "action": "defer_expensive_lane" if effective_next_expensive_lane == "defer_expensive_lane" else "enter_expensive_lane",
                    "status": "deferred" if effective_next_expensive_lane == "defer_expensive_lane" else "queued",
                    "lane": effective_next_expensive_lane,
                }
            )

    effective_action_list_text = _resolve_text_from_summaries(
        summaries,
        value_keys=(
            "selected_allatom_effective_actionability_action_list_text",
            "selected_allatom_actionability_action_list_text",
            "effective_actionability_action_list_text",
        ),
    )
    if not effective_action_list_text:
        effective_action_list_text = " | ".join(
            f"{item.get('severity', 'soft')}:{item.get('action', '')}[{item.get('status', '')}]"
            + (f" lane={item.get('lane')}" if item.get("lane") else "")
            for item in effective_action_list
            if _text(item.get("action"))
        )

    effective_blocking_order = _resolve_text_from_summaries(
        summaries,
        value_keys=(
            "selected_allatom_effective_blocking_order",
            "effective_blocking_order",
            "selected_allatom_actionability_blocking_order",
        ),
    )
    if not effective_blocking_order:
        effective_blocking_order = _selected_allatom_effective_blocking_order(
            hard_block_present=hard_block_present,
            claim_requirement_mode=claim_requirement_mode_effective,
            claim_requirement_status=claim_requirement_status_effective,
            translation_status=translation_status,
            commercial_hard_gate_reported_v2=selected_allatom_commercial_hard_gate_reported_v2,
            commercial_hard_gate_pass_v2=selected_allatom_commercial_hard_gate_pass_v2,
        )

    effective_primary_blocking_domain = _resolve_text_from_summaries(
        summaries,
        value_keys=(
            "selected_allatom_effective_primary_blocking_domain",
            "effective_primary_blocking_domain",
            "selected_allatom_actionability_primary_blocking_domain",
        ),
    )
    if not effective_primary_blocking_domain:
        effective_primary_blocking_domain = _selected_allatom_effective_primary_blocking_domain(
            hard_block_present=hard_block_present,
            commercial_hard_gate_reported_v2=selected_allatom_commercial_hard_gate_reported_v2,
            commercial_hard_gate_pass_v2=selected_allatom_commercial_hard_gate_pass_v2,
            translation_status=translation_status,
            claim_requirement_mode=claim_requirement_mode_effective,
            claim_requirement_status=claim_requirement_status_effective,
        )

    action_recipe_codes = _resolve_list_from_summaries(
        summaries,
        value_keys=(
            "selected_allatom_action_recipe_codes",
            "action_recipe_codes",
        ),
    )
    if not action_recipe_codes:
        action_recipe_codes = _selected_allatom_action_recipe_codes(effective_action_list, effective_required_calculations)

    action_recipe_rows = _resolve_list_from_summaries(
        summaries,
        value_keys=(
            "selected_allatom_action_recipe_rows",
            "action_recipe_rows",
        ),
    )
    if not action_recipe_rows:
        action_recipe_rows = _selected_allatom_action_recipe_rows(effective_action_list)

    raw_claim_requirement_reason = claim_requirement_reason
    raw_claim_required_for_final_wetlab = bool(claim_required_for_final_wetlab)
    raw_claim_required_for_commercial_readiness = bool(claim_required_for_commercial_readiness)

    effective_actionability_status = _resolve_text_from_summaries(
        summaries,
        value_keys=(
            "selected_allatom_effective_actionability_status",
            "selected_allatom_actionability_status",
            "effective_actionability_status",
        ),
    )
    if not effective_actionability_status:
        if not selected_allatom_final_gate_reported:
            effective_actionability_status = "not_reported"
        elif selected_allatom_final_gate_pass:
            effective_actionability_status = "ready"
        elif hard_block_present:
            effective_actionability_status = "hard_blocked"
        elif claim_requirement_mode_effective == "semi_hard" and not selected_allatom_claim_ready_for_allatom:
            effective_actionability_status = "semi_hard_blocked"
        elif effective_next_expensive_lane or selected_allatom_focus_shortlist_tier:
            effective_actionability_status = "soft_guided"
        else:
            effective_actionability_status = "blocked"
    if effective_actionability_status == "ready":
        effective_required_calculations = []
    effective_actionability_required_calculations_text = ", ".join(effective_required_calculations)

    action_recipe_rollup_text = _joined(action_recipe_codes, effective_action_list_text)
    human_summary = _joined(
        f"Raw claim requirement {claim_requirement_mode} ({claim_requirement_provenance})",
        f"required final wetlab {raw_claim_required_for_final_wetlab}",
        f"required commercial readiness {raw_claim_required_for_commercial_readiness}",
        f"reason {raw_claim_requirement_reason}",
        f"effective actionability {effective_actionability_status}",
        f"claim mode {claim_requirement_mode_effective}:{claim_requirement_status_effective}",
        f"blocking order {effective_blocking_order}",
        f"primary domain {effective_primary_blocking_domain}",
        f"action recipe {action_recipe_rollup_text}" if action_recipe_rollup_text else "",
    )
    commercial_schema_version_v2_default = _text(helper_result.get("commercial_schema_version_v2", ""))

    def _helper_text(key: str, default: str = "") -> str:
        return _text(helper_result.get(key, ""), default)

    def _helper_bool(key: str, default: bool = False) -> bool:
        return _resolve_bool(helper_result.get(key), default=default)

    def _helper_float(key: str, default: float = 0.0) -> float:
        parsed = _safe_float(helper_result.get(key))
        return default if parsed is None else parsed

    def _helper_list(key: str, default: list[Any] | None = None) -> list[Any]:
        value = helper_result.get(key)
        if isinstance(value, (list, tuple, set)):
            return list(value)
        if value in {"", None}:
            return list(default or [])
        return _safe_str_list(value)

    return {
        "commercial_schema_version_v2": _helper_text("commercial_schema_version_v2", commercial_schema_version_v2_default)
        or _resolve_text_from_summaries(
            summaries,
            value_keys=("commercial_schema_version_v2", "selected_allatom_commercial_schema_version_v2"),
            default=commercial_schema_version_v2_default,
        ),
        "commercial_overall_score_v2": _helper_float(
            "commercial_overall_score_v2",
            selected_allatom_commercial_overall_score_v2,
        ),
        "commercial_risk_bucket_v2": _helper_text("commercial_risk_bucket_v2", selected_allatom_commercial_risk_bucket_v2)
        or _resolve_text_from_summaries(
            summaries,
            value_keys=("commercial_risk_bucket_v2", "selected_allatom_commercial_risk_bucket_v2"),
            default=selected_allatom_commercial_risk_bucket_v2,
        ),
        "commercial_decision_class_v2": _helper_text("commercial_decision_class_v2", selected_allatom_commercial_decision_class_v2)
        or _resolve_text_from_summaries(
            summaries,
            value_keys=("commercial_decision_class_v2", "selected_allatom_commercial_decision_class_v2"),
            default=selected_allatom_commercial_decision_class_v2,
        ),
        "commercial_primary_upgrade_actions_v2": _helper_list(
            "commercial_primary_upgrade_actions_v2",
            selected_allatom_commercial_primary_upgrade_actions_v2,
        )
        or _resolve_list_from_summaries(
            summaries,
            value_keys=("commercial_primary_upgrade_actions_v2", "selected_allatom_commercial_primary_upgrade_actions_v2"),
        )
        or list(selected_allatom_commercial_primary_upgrade_actions_v2),
        "translation_gate_version": _helper_text("translation_gate_version", selected_allatom_translation_gate_version)
        or _resolve_text_from_summaries(
            summaries,
            value_keys=("translation_gate_version", "selected_allatom_translation_gate_version"),
            default=selected_allatom_translation_gate_version,
        ),
        "translation_gate_focus_status": _helper_text("translation_gate_focus_status", selected_allatom_translation_gate_focus_status)
        or _resolve_text_from_summaries(
            summaries,
            value_keys=("translation_gate_focus_status", "selected_allatom_translation_gate_focus_status"),
            default=selected_allatom_translation_gate_focus_status,
        ),
        "translation_gate_focus_score": _helper_float(
            "translation_gate_focus_score",
            selected_allatom_translation_gate_focus_score,
        ),
        "translation_gate_focus_reason": _helper_text("translation_gate_focus_reason", selected_allatom_translation_gate_focus_reason)
        or _resolve_text_from_summaries(
            summaries,
            value_keys=("translation_gate_focus_reason", "selected_allatom_translation_gate_focus_reason"),
            default=selected_allatom_translation_gate_focus_reason,
        ),
        "focus_shortlist_tier": _helper_text("focus_shortlist_tier", selected_allatom_focus_shortlist_tier)
        or _resolve_text_from_summaries(
            summaries,
            value_keys=("focus_shortlist_tier", "selected_allatom_focus_shortlist_tier"),
            default=selected_allatom_focus_shortlist_tier,
        ),
        "recommended_next_expensive_lane": _helper_text("recommended_next_expensive_lane", selected_allatom_recommended_next_expensive_lane)
        or _resolve_text_from_summaries(
            summaries,
            value_keys=("recommended_next_expensive_lane", "selected_allatom_recommended_next_expensive_lane"),
            default=selected_allatom_recommended_next_expensive_lane,
        ),
        "recommended_next_expensive_lane_reason": _helper_text(
            "recommended_next_expensive_lane_reason",
            selected_allatom_recommended_next_expensive_lane_reason,
        )
        or _resolve_text_from_summaries(
            summaries,
            value_keys=("recommended_next_expensive_lane_reason", "selected_allatom_recommended_next_expensive_lane_reason"),
            default=selected_allatom_recommended_next_expensive_lane_reason,
        ),
        "raw_claim_requirement_mode": _helper_text("raw_claim_requirement_mode", claim_requirement_mode),
        "raw_claim_requirement_provenance": _helper_text("raw_claim_requirement_provenance", claim_requirement_provenance),
        "raw_claim_required_for_final_wetlab": _helper_bool(
            "raw_claim_required_for_final_wetlab",
            raw_claim_required_for_final_wetlab,
        ),
        "raw_claim_required_for_commercial_readiness": _helper_bool(
            "raw_claim_required_for_commercial_readiness",
            raw_claim_required_for_commercial_readiness,
        ),
        "raw_claim_requirement_reason": _helper_text("raw_claim_requirement_reason", raw_claim_requirement_reason),
        "effective_actionability_status": _helper_text("effective_actionability_status", effective_actionability_status),
        "effective_actionability_claim_requirement_mode": _helper_text(
            "effective_actionability_claim_requirement_mode",
            claim_requirement_mode_effective,
        ),
        "effective_actionability_claim_requirement_status": _helper_text(
            "effective_actionability_claim_requirement_status",
            claim_requirement_status_effective,
        ),
        "effective_actionability_claim_requirement_reason": _helper_text(
            "effective_actionability_claim_requirement_reason",
            claim_requirement_reason_effective,
        ),
        "effective_actionability_next_expensive_lane": _helper_text(
            "effective_actionability_next_expensive_lane",
            effective_next_expensive_lane,
        ),
        "effective_actionability_next_expensive_lane_reason": _helper_text(
            "effective_actionability_next_expensive_lane_reason",
            effective_next_expensive_lane_reason,
        ),
        "effective_actionability_required_calculations": _helper_list(
            "effective_actionability_required_calculations",
            effective_required_calculations,
        )
        if effective_actionability_status != "ready"
        else list(effective_required_calculations),
        "effective_actionability_required_calculations_text": (
            _helper_text(
                "effective_actionability_required_calculations_text",
                effective_actionability_required_calculations_text,
            )
            if effective_actionability_status != "ready"
            else effective_actionability_required_calculations_text
        ),
        "effective_actionability_action_list": _helper_list(
            "effective_actionability_action_list",
            effective_action_list,
        ),
        "effective_actionability_action_list_text": _helper_text(
            "effective_actionability_action_list_text",
            effective_action_list_text,
        ),
        "effective_blocking_order": _helper_text("effective_blocking_order", effective_blocking_order),
        "effective_primary_blocking_domain": _helper_text(
            "effective_primary_blocking_domain",
            effective_primary_blocking_domain,
        ),
        "action_recipe_codes": _helper_list("action_recipe_codes", action_recipe_codes),
        "action_recipe_rows": _helper_list("action_recipe_rows", action_recipe_rows),
        "action_recipe_rollup_text": _helper_text("action_recipe_rollup_text", action_recipe_rollup_text),
        "translation_provenance_mode": _helper_text(
            "translation_provenance_mode",
            "source_driven" if _text(selected_allatom_translation_gate_version) or _text(selected_allatom_translation_gate_focus_status) else "not_reported",
        )
        or _resolve_text_from_summaries(
            summaries,
            value_keys=("translation_provenance_mode", "selected_allatom_translation_provenance_mode"),
            default="source_driven" if _text(selected_allatom_translation_gate_version) or _text(selected_allatom_translation_gate_focus_status) else "not_reported",
        ),
        "commercial_provenance_mode_v2": _helper_text(
            "commercial_provenance_mode_v2",
            "source_driven" if selected_allatom_commercial_reported_v2 else "not_reported",
        )
        or _resolve_text_from_summaries(
            summaries,
            value_keys=("commercial_provenance_mode_v2", "selected_allatom_commercial_provenance_mode_v2"),
            default="source_driven" if selected_allatom_commercial_reported_v2 else "not_reported",
        ),
        "hybrid_policy": _helper_text(
            "hybrid_policy",
            "canonical_scores_source_only__translation_shortlist_labeled_fallback",
        )
        or _resolve_text_from_summaries(
            summaries,
            value_keys=("hybrid_policy", "selected_allatom_hybrid_policy"),
            default="canonical_scores_source_only__translation_shortlist_labeled_fallback",
        ),
        "human_summary": human_summary,
    }


def _resolve_list_from_summaries(
    summaries: tuple[dict[str, Any], ...],
    *,
    value_keys: tuple[str, ...],
) -> list[str]:
    for summary in summaries:
        if not summary:
            continue
        for value_key in value_keys:
            if _has_value(summary, value_key):
                values = _safe_str_list(summary.get(value_key))
                if values:
                    return values
    return []


def _normalize_selected_allatom_semantics(raw_value: Any, *, focus_available: bool, final_gate_reported: bool) -> str:
    text = str(raw_value or "").strip()
    if text in {"explicit_split_gate_fields", "operator_review_and_final_gate"}:
        return "explicit_split_gate_fields"
    if text:
        return text
    if final_gate_reported:
        return "explicit_split_gate_fields"
    if focus_available:
        return "selected_focus_without_reported_final_gate"
    return "not_selected"


def _selected_allatom_focus_label(target_id: str, surface_label: str) -> str:
    if target_id and surface_label:
        return f"{target_id} / {surface_label}"
    return target_id or surface_label or "not_selected"


def _selected_allatom_review_rollup(reported: bool, ready: bool) -> str:
    if not reported:
        return "operator review not reported"
    return "operator review ready" if ready else "operator review blocked"


def _selected_allatom_final_gate_rollup(reported: bool, passed: bool) -> str:
    if not reported:
        return "final gate not reported"
    return "final gate passed" if passed else "final gate blocked"


def _selected_allatom_wetlab_gate_rollup(reported: bool, passed: bool) -> str:
    if not reported:
        return "wetlab gate not reported"
    return "wetlab gate passed" if passed else "wetlab gate blocked"


def _selected_allatom_claim_rollup(
    claim_gate_reported: bool,
    claim_gate_available: bool,
    claim_ready_reported: bool,
    claim_ready_for_allatom: bool,
) -> str:
    if claim_ready_reported and claim_ready_for_allatom:
        return "claim ready"
    if claim_gate_reported and claim_gate_available:
        return "claim gate available"
    if claim_gate_reported or claim_ready_reported:
        return "claim unavailable"
    return "claim not reported"


def _selected_allatom_semantics_rollup(semantics: str) -> str:
    return {
        "explicit_split_gate_fields": "explicit split-gate fields",
        "legacy_review_packet_fallback": "legacy review-packet fallback",
        "selected_focus_without_reported_final_gate": "selected focus without reported final gate",
        "not_selected": "not selected",
    }.get(semantics, semantics or "not selected")


def _selected_allatom_human_rollups(
    *,
    focus_available: bool,
    target_id: str,
    surface_label: str,
    operator_review_reported: bool,
    operator_review_ready: bool,
    wetlab_gate_reported: bool,
    wetlab_gate_pass: bool,
    final_gate_reported: bool,
    final_gate_pass: bool,
    claim_gate_reported: bool,
    claim_gate_available: bool,
    claim_ready_reported: bool,
    claim_ready_for_allatom: bool,
    semantics: str,
    best_compound_name: str,
    best_compound_name_human_readable: str,
    best_compound_name_resolution: str,
    best_mean_min_distance_A: float,
    promoted_candidate_count: int,
    under_2p5_candidate_count: int,
    near_candidate_count: int,
    commercial_reported: bool,
    commercial_hard_gate_reported: bool,
    commercial_hard_gate_pass: bool,
    commercial_overall_score_v1: float,
    commercial_risk_bucket_v1: str,
    commercial_decision_class_v1: str,
    commercial_primary_upgrade_actions_v1: list[str],
    commercial_schema_version_v2: str,
    commercial_reported_v2: bool,
    commercial_hard_gate_reported_v2: bool,
    commercial_hard_gate_pass_v2: bool,
    commercial_soft_score_v2: float,
    commercial_confidence_score_v2: float,
    commercial_overall_score_v2: float,
    commercial_risk_bucket_v2: str,
    commercial_decision_class_v2: str,
    commercial_primary_upgrade_actions_v2: list[str],
    commercial_human_summary_v2: str,
    commercial_provenance_mode_v2: str,
    translation_gate_version: str,
    translation_gate_focus_status: str,
    translation_gate_focus_score: float,
    translation_gate_focus_reason: str,
    focus_shortlist_tier: str,
    recommended_next_expensive_lane: str,
    recommended_next_expensive_lane_reason: str,
    translation_provenance_mode: str,
) -> dict[str, str]:
    if not focus_available:
        return {
            "focus_label": "not_selected",
            "gate_rollup": "selected all-atom focus not available",
            "gate_detail_rollup": "wetlab gate not reported | semantics=not selected",
            "commercial_rollup": "commercial v1 not reported",
            "commercial_detail_rollup": "commercial v1 not reported",
            "commercial_summary": "Commercial-grade v1 is not yet reported for the selected all-atom focus.",
            "commercial_rollup_v2": "commercial v2 not reported",
            "commercial_detail_rollup_v2": "commercial v2 not reported",
            "commercial_summary_v2": "Commercial-grade v2 is not yet reported for the selected all-atom focus.",
            "translation_rollup": "translation gate not reported",
            "translation_summary": "Translation-gate and stronger-physics shortlist signals are not yet reported for the selected all-atom focus.",
            "human_summary": "No selected all-atom focus is currently reported.",
        }
    focus_label = _selected_allatom_focus_label(target_id, surface_label)
    review_rollup = _selected_allatom_review_rollup(operator_review_reported, operator_review_ready)
    final_gate_rollup = _selected_allatom_final_gate_rollup(final_gate_reported, final_gate_pass)
    claim_rollup = _selected_allatom_claim_rollup(
        claim_gate_reported,
        claim_gate_available,
        claim_ready_reported,
        claim_ready_for_allatom,
    )
    wetlab_gate_rollup = _selected_allatom_wetlab_gate_rollup(wetlab_gate_reported, wetlab_gate_pass)
    semantics_rollup = _selected_allatom_semantics_rollup(semantics)
    best_compound = _text(
        best_compound_name_human_readable,
        best_compound_name if best_compound_name_resolution != "cache_placeholder" else "",
    )
    detail_parts: list[str] = []
    if best_compound:
        detail_parts.append(f"best compound {best_compound}")
    if best_mean_min_distance_A > 0:
        detail_parts.append(f"best mean min distance {best_mean_min_distance_A:.3f}A")
    if promoted_candidate_count or under_2p5_candidate_count or near_candidate_count:
        detail_parts.append(
            "candidate bands "
            f"promoted={promoted_candidate_count}, strict<2.5A={under_2p5_candidate_count}, near<3.0A={near_candidate_count}"
        )
    detail_rollup = f"{wetlab_gate_rollup} | semantics={semantics_rollup}"
    if detail_parts:
        detail_rollup += " | " + " | ".join(detail_parts)
    if commercial_reported:
        action_text = ", ".join(commercial_primary_upgrade_actions_v1) if commercial_primary_upgrade_actions_v1 else "none"
        commercial_rollup = (
            f"commercial overall {commercial_overall_score_v1:.1f}"
            f" | risk {commercial_risk_bucket_v1 or 'unreported'}"
            f" | decision {commercial_decision_class_v1 or 'unreported'}"
        )
        commercial_detail_rollup = (
            f"commercial hard gate {'passed' if commercial_hard_gate_pass else 'blocked'}"
            if commercial_hard_gate_reported
            else "commercial hard gate not reported"
        )
        commercial_detail_rollup += f" | primary upgrades {action_text}"
        commercial_sentence = (
            f" Commercial-grade v1: overall {commercial_overall_score_v1:.1f},"
            f" risk {commercial_risk_bucket_v1 or 'unreported'},"
            f" decision {commercial_decision_class_v1 or 'unreported'},"
            f" primary upgrades {action_text}."
        )
    else:
        commercial_rollup = "commercial v1 not reported"
        commercial_detail_rollup = "commercial v1 not reported"
        commercial_sentence = " Commercial-grade v1 is not yet reported for this focus."
    if commercial_reported_v2:
        action_text_v2 = (
            ", ".join(commercial_primary_upgrade_actions_v2)
            if commercial_primary_upgrade_actions_v2
            else "none"
        )
        commercial_v2_provenance_suffix = (
            f" | provenance {commercial_provenance_mode_v2}"
            if commercial_provenance_mode_v2 and commercial_provenance_mode_v2 != "source_driven"
            else ""
        )
        commercial_rollup_v2 = (
            f"commercial v2 overall {commercial_overall_score_v2:.1f}"
            f" | risk {commercial_risk_bucket_v2 or 'unreported'}"
            f" | decision {commercial_decision_class_v2 or 'unreported'}"
            f"{commercial_v2_provenance_suffix}"
        )
        commercial_detail_rollup_v2 = (
            f"commercial v2 hard gate {'passed' if commercial_hard_gate_pass_v2 else 'blocked'}"
            if commercial_hard_gate_reported_v2
            else "commercial v2 hard gate not reported"
        )
        commercial_detail_rollup_v2 += (
            f" | soft {commercial_soft_score_v2:.1f}"
            f" | confidence {commercial_confidence_score_v2:.1f}"
            f" | primary upgrades {action_text_v2}"
        )
        commercial_sentence_v2 = (
            commercial_human_summary_v2.strip()
            if commercial_human_summary_v2.strip()
            else (
                f"Commercial-grade v2 ({commercial_schema_version_v2 or 'schema unreported'}): "
                f"overall {commercial_overall_score_v2:.1f},"
                f" soft {commercial_soft_score_v2:.1f},"
                f" confidence {commercial_confidence_score_v2:.1f},"
                f" risk {commercial_risk_bucket_v2 or 'unreported'},"
                f" decision {commercial_decision_class_v2 or 'unreported'},"
                f" primary upgrades {action_text_v2}."
            )
        )
        if commercial_provenance_mode_v2 and commercial_provenance_mode_v2 != "source_driven":
            commercial_sentence_v2 = (
                f"{commercial_sentence_v2.rstrip('.')} "
                f"[provenance: {commercial_provenance_mode_v2}]."
            )
    else:
        commercial_rollup_v2 = "commercial v2 not reported"
        commercial_detail_rollup_v2 = "commercial v2 not reported"
        commercial_sentence_v2 = "Commercial-grade v2 is not yet reported for this focus."
    translation_status = translation_gate_focus_status or "not reported"
    translation_reported = bool(
        translation_gate_version
        or translation_gate_focus_status
        or translation_gate_focus_score > 0
        or translation_gate_focus_reason
        or focus_shortlist_tier
        or recommended_next_expensive_lane
        or recommended_next_expensive_lane_reason
    )
    translation_rollup = (
        f"translation {translation_status}"
        if translation_reported
        else "translation gate not reported"
    )
    translation_detail_parts: list[str] = []
    if translation_gate_focus_score > 0:
        translation_detail_parts.append(f"score {translation_gate_focus_score:.1f}")
    if focus_shortlist_tier:
        translation_detail_parts.append(f"shortlist tier {focus_shortlist_tier}")
    if recommended_next_expensive_lane:
        translation_detail_parts.append(f"next lane {recommended_next_expensive_lane}")
    if translation_provenance_mode and translation_provenance_mode != "source_driven":
        translation_detail_parts.append(f"provenance {translation_provenance_mode}")
    if translation_detail_parts:
        translation_rollup += " | " + " | ".join(translation_detail_parts)
    if translation_reported:
        translation_prefix = (
            "Translation/shortlist fallback (inferred from partial upstream"
            if translation_provenance_mode == "inferred_from_partial_upstream"
            else "Translation gate"
        )
        translation_prefix += (
            f"; {translation_gate_version or 'schema unreported'})"
            if translation_provenance_mode == "inferred_from_partial_upstream"
            else f" ({translation_gate_version or 'schema unreported'})"
        )
        translation_sentence = (
            f"{translation_prefix}: "
            f"status {translation_status}"
            + (f", score {translation_gate_focus_score:.1f}" if translation_gate_focus_score > 0 else "")
            + (f", shortlist tier {focus_shortlist_tier}" if focus_shortlist_tier else "")
            + (
                f", recommended stronger-physics lane {recommended_next_expensive_lane}"
                if recommended_next_expensive_lane
                else ""
            )
            + (
                f", rationale {translation_gate_focus_reason}"
                if translation_gate_focus_reason
                else ""
            )
            + (
                f", lane rationale {recommended_next_expensive_lane_reason}"
                if recommended_next_expensive_lane_reason
                else ""
            )
            + "."
        )
    else:
        translation_sentence = (
            "Translation-gate and stronger-physics shortlist signals are not yet reported for this focus."
        )
    return {
        "focus_label": focus_label,
        "gate_rollup": f"{review_rollup} | {final_gate_rollup} | {claim_rollup}",
        "gate_detail_rollup": detail_rollup,
        "commercial_rollup": commercial_rollup,
        "commercial_detail_rollup": commercial_detail_rollup,
        "commercial_summary": commercial_sentence.strip(),
        "commercial_rollup_v2": commercial_rollup_v2,
        "commercial_detail_rollup_v2": commercial_detail_rollup_v2,
        "commercial_summary_v2": commercial_sentence_v2.strip(),
        "translation_rollup": translation_rollup,
        "translation_summary": translation_sentence.strip(),
        "human_summary": (
            f"Selected all-atom focus {focus_label}: {review_rollup}, {final_gate_rollup}, {claim_rollup}. "
            f"{wetlab_gate_rollup}. Semantics: {semantics_rollup}."
            + (f" Details: {'; '.join(detail_parts)}." if detail_parts else "")
            + f" {commercial_sentence.strip()}"
            + f" {commercial_sentence_v2.strip()}"
            + f" {translation_sentence.strip()}"
        ),
    }


def _primary_watch_ready(summary: dict[str, Any]) -> bool:
    status = str(summary.get("status", "")).strip()
    return status in {
        "wetlab_broad_screen_primary_watcher_ready",
        "wetlab_broad_screen_primary_watch_state_ready",
        "wetlab_broad_screen_primary_watch_action_ready",
    }


def _primary_watch_next_required_step(*summaries: dict[str, Any]) -> str:
    for summary in summaries:
        text = str(summary.get("next_required_step", "")).strip()
        if text:
            return text
    return ""


def _normalize_antitarget_watch_step(text: str, antitarget_execution_summary: dict[str, Any]) -> str:
    status = str(antitarget_execution_summary.get("first_actionable_queue_status", "")).strip()
    if (
        "counterscreen state aligned with the active lane" in text
        and "running" in status
        and "supervision_only" not in status
    ):
        return "Run the anti-target watcher again or leave it in loop mode to keep compute-attached counterscreen state aligned with active compute state."
    return text


def _manual_retry_step_from_lane(lane_payload: dict[str, Any]) -> str:
    summary = _summary(lane_payload)
    lane_label = str(summary.get("followup_lane_label", "") or summary.get("lane_label", "")).strip()
    status = str(summary.get("status", "")).strip()
    selectable = bool(summary.get("ready_for_manual_retry", False)) or (
        lane_label == "exploratory_gate4.5_followup" and status.startswith("wetlab_stk17b_exploratory_followup_lane_")
    )
    if not selectable:
        return ""
    explicit_next_step = str(summary.get("next_required_step", "")).strip()
    if explicit_next_step:
        return explicit_next_step
    target_id = str(summary.get("target_id", "")).strip()
    shard_id = str(summary.get("shard_id", "")).strip()
    selected_kind = str(summary.get("selected_command_kind", "")).strip()
    followup_shards = str(summary.get("followup_shard_ids", "")).strip()
    label = (
        "exploratory follow-up gate4.5 manual retry runner"
        if "followup" in lane_label
        else
        "exploratory gate4.5 manual retry runner"
        if "gate45" in selected_kind
        else "tuned gate55 manual retry runner"
        if "gate55" in selected_kind
        else "manual retry runner"
    )
    if "followup" in lane_label:
        freeze_clause = (
            f"keep auto-start hard-frozen after the gate4.5 success and review follow-up shards {followup_shards} separately before reopening."
            if followup_shards
            else "keep auto-start hard-frozen after the gate4.5 success and review the follow-up shards separately before reopening."
        )
    else:
        freeze_clause = "keep auto-start blocked until the guarded retry either lands a clean summary or is held again."
    if target_id and shard_id:
        return f"Run the {target_id} {label} for {shard_id}; {freeze_clause}"
    if target_id:
        return f"Run the {target_id} {label}; {freeze_clause}"
    return ""


def _manual_retry_next_step(
    retry_handoff_summary: dict[str, Any],
    stk17b_exploratory_followup_lane: dict[str, Any],
    stk17b_manual_retry_lane: dict[str, Any],
    stk17b_exploratory_retry_lane: dict[str, Any],
    plpro_manual_retry_lane: dict[str, Any],
    lbdhodh_exploratory_retry_lane: dict[str, Any],
    fallback: str = "",
) -> str:
    retry_summary = _summary(retry_handoff_summary)
    selected_lane_label = str(retry_summary.get("selected_manual_retry_lane_label", "")).strip()
    selected_target = str(retry_summary.get("selected_manual_retry_target_id", "")).strip()
    selected_shard = str(retry_summary.get("selected_manual_retry_shard_id", "")).strip()
    selected_kind = str(retry_summary.get("selected_manual_retry_selected_command_kind", "")).strip()
    focus_target = str(retry_summary.get("manual_retry_focus_target_id", "")).strip()
    for lane_payload in (
        stk17b_exploratory_followup_lane,
        stk17b_exploratory_retry_lane,
        stk17b_manual_retry_lane,
        plpro_manual_retry_lane,
        lbdhodh_exploratory_retry_lane,
    ):
        summary = _summary(lane_payload)
        lane_label = str(summary.get("followup_lane_label", "") or summary.get("lane_label", "")).strip()
        status = str(summary.get("status", "")).strip()
        selectable = bool(summary.get("ready_for_manual_retry", False)) or (
            lane_label == "exploratory_gate4.5_followup" and status.startswith("wetlab_stk17b_exploratory_followup_lane_")
        ) or (
            status.startswith("wetlab_lbdhodh_exploratory_retry_lane_")
            and str(summary.get("queue_status", "")).strip() == "running"
            and bool(str(summary.get("next_required_step", "")).strip())
        )
        if not selectable:
            continue
        if selected_lane_label and lane_label != selected_lane_label:
            continue
        if selected_target and str(summary.get("target_id", "")).strip() != selected_target:
            continue
        if selected_shard and _lane_shard_display(summary) != selected_shard:
            continue
        if selected_kind and str(summary.get("selected_command_kind", "")).strip() != selected_kind:
            continue
        lane_step = _manual_retry_step_from_lane(lane_payload)
        if lane_step:
            return lane_step
    for lane_payload in (
        stk17b_exploratory_followup_lane,
        stk17b_exploratory_retry_lane,
        stk17b_manual_retry_lane,
        plpro_manual_retry_lane,
        lbdhodh_exploratory_retry_lane,
    ):
        summary = _summary(lane_payload)
        if focus_target and str(summary.get("target_id", "")).strip() == focus_target:
            lane_step = _manual_retry_step_from_lane(lane_payload)
            if lane_step:
                return lane_step
    for lane_payload in (
        stk17b_exploratory_followup_lane,
        stk17b_exploratory_retry_lane,
        stk17b_manual_retry_lane,
        plpro_manual_retry_lane,
        lbdhodh_exploratory_retry_lane,
    ):
        lane_step = _manual_retry_step_from_lane(lane_payload)
        if lane_step:
            return lane_step
    return fallback


def _rescue_next_required_step(
    tcruzi_pde_rescue_only_branch_summary: dict[str, Any] | None,
    tcruzi_pde_promoted_top4_review_packet: dict[str, Any] | None,
    hard_target_rescue_lane: dict[str, Any] | None,
    rescue_anchor_artifacts: dict[str, Any] | None,
    rescue_three_bead_candidates: dict[str, Any] | None,
) -> str:
    branch_summary = _summary(tcruzi_pde_rescue_only_branch_summary)
    if (
        str(branch_summary.get("status", "")).strip() == "wetlab_tcruzi_pde_rescue_only_branch_summary_ready"
        and str(branch_summary.get("target_id", "")).strip() == "T. cruzi PDE"
    ):
        explicit = str(branch_summary.get("next_required_step", "")).strip()
        if explicit:
            return explicit
    review_packet = _summary(tcruzi_pde_promoted_top4_review_packet)
    if (
        str(review_packet.get("status", "")).strip() == "wetlab_tcruzi_pde_promoted_top4_review_packet_ready"
        and str(review_packet.get("target_id", "")).strip() == "T. cruzi PDE"
    ):
        explicit = str(review_packet.get("next_required_step", "")).strip()
        if explicit:
            return explicit
    for payload, status_name, label in (
        (hard_target_rescue_lane, "wetlab_hard_target_rescue_lane_ready", "hard-target rescue lane"),
        (rescue_anchor_artifacts, "wetlab_rescue_anchor_artifacts_ready", "rescue anchors"),
        (rescue_three_bead_candidates, "wetlab_rescue_three_bead_candidates_ready", "3-bead rescue"),
    ):
        summary = _summary(payload)
        if str(summary.get("status", "")).strip() != status_name:
            continue
        explicit = str(summary.get("next_required_step", "")).strip()
        if explicit:
            return explicit
        target_id = str(summary.get("target_id", "")).strip()
        shard_id = str(summary.get("shard_id", "")).strip()
        if label == "hard-target rescue lane":
            if target_id and shard_id:
                return f"Run the hard-target rescue lane for {target_id} {shard_id}; keep the default lane closed."
            if target_id:
                return f"Run the hard-target rescue lane for {target_id}; keep the default lane closed."
        elif label == "rescue anchors":
            if target_id:
                return f"Review rescue anchors for {target_id}; keep the default lane closed."
        elif label == "3-bead rescue" and target_id:
            return f"Review 3-bead rescue candidates for {target_id}; keep the default lane closed."
    return ""


def _stk17b_followup_review_next_step(review_surface_payload: dict[str, Any] | None) -> str:
    summary = _summary(review_surface_payload)
    if str(summary.get("target_id", "")).strip() != "STK17B (DRAK2)":
        return ""
    if not str(summary.get("decision", "")).strip():
        return ""
    return str(summary.get("next_required_step", "")).strip()


def _dengue_stage6_summary(
    execution_queue: dict[str, Any] | None,
    dengue_stage6_tuning_surface: dict[str, Any] | None,
    dengue_exploratory_retry_lane: dict[str, Any] | None,
) -> dict[str, Any]:
    queue = _summary(execution_queue)
    tuning = _summary(dengue_stage6_tuning_surface)
    lane = _summary(dengue_exploratory_retry_lane)
    tuning_ready = str(tuning.get("status", "")).strip() == "wetlab_dengue_ns2b_ns3_protease_stage6_tuning_surface_ready"
    lane_ready = str(lane.get("status", "")).strip() == "wetlab_dengue_ns2b_ns3_protease_exploratory_retry_lane_ready"
    if not tuning_ready and not lane_ready:
        return {}
    queue_target_id = str(queue.get("first_actionable_target_id", "")).strip()
    queue_shard_id = str(queue.get("first_actionable_shard_id", "")).strip()
    queue_next_required_step = str(queue.get("next_required_step", "")).strip()
    queue_status = str(queue.get("first_actionable_queue_status", "")).strip()
    queue_priority = queue_target_id == "Dengue NS2B-NS3 protease" and bool(queue_shard_id)
    target_id = str(
        queue_target_id if queue_priority else lane.get("target_id", "") or tuning.get("target_id", "") or "Dengue NS2B-NS3 protease"
    ).strip()
    threshold = float(tuning.get("recommended_observed_threshold_A", 0.0) or 0.0)
    command_kind = str(lane.get("selected_command_kind", "") or tuning.get("immediately_runnable_command_kind", "") or "").strip()
    lane_label = str(lane.get("lane_label", "")).strip()
    shard_id = str(queue_shard_id if queue_priority else lane.get("shard_id", "") or tuning.get("next_retry_shard_id", "")).strip()
    next_required_step = str(
        queue_next_required_step if queue_priority else lane.get("next_required_step", "") or tuning.get("next_required_step", "") or ""
    ).strip()
    source_priority = "execution_queue" if queue_priority else "exploratory_lane" if lane_ready else "tuning_surface"
    return {
        "status": str(queue_status if queue_priority else lane.get("status", "") or tuning.get("status", "") or "missing").strip(),
        "source_priority": source_priority,
        "target_id": target_id,
        "tuning_ready": tuning_ready,
        "recommended_threshold_A": threshold,
        "immediately_runnable_command_kind": str(tuning.get("immediately_runnable_command_kind", "")).strip(),
        "retry_lane_ready": lane_ready,
        "ready_for_manual_retry": bool(lane.get("ready_for_manual_retry", False)),
        "shard_id": shard_id,
        "selected_command_kind": command_kind,
        "lane_label": lane_label,
        "next_required_step": next_required_step or (
            "Promote Dengue NS2B-NS3 protease stage6 tuned retry, keep the default lane closed, and reserve any future Dengue reopen for an explicit new review."
            if tuning_ready
            else ""
        ),
    }


def _lane_shard_display(summary: dict[str, Any]) -> str:
    lane_label = str(summary.get("followup_lane_label", "") or summary.get("lane_label", "")).strip()
    if lane_label == "exploratory_gate4.5_followup":
        return str(summary.get("shard_id", "")).strip() or str(summary.get("followup_shard_ids", "")).strip()
    return str(summary.get("shard_id", "")).strip()


def _exploratory_freeze_snapshot(
    exploratory_summary: dict[str, Any],
    *primary_watch_summaries: dict[str, Any],
) -> dict[str, Any]:
    target_id = str(exploratory_summary.get("target_id", "")).strip()
    if str(exploratory_summary.get("hard_freeze_state", "")).strip():
        followup_shards_text = str(exploratory_summary.get("followup_shard_ids", "")).strip()
        followup_shard_count = len([part for part in followup_shards_text.split(";") if str(part).strip()])
        hold_streak = int(
            exploratory_summary.get("guard_hold_streak", 0)
            or exploratory_summary.get("hold_streak", 0)
            or followup_shard_count
            or 0
        )
        hold_limit = int(
            exploratory_summary.get("guard_limit", 0)
            or exploratory_summary.get("hold_limit", 0)
            or followup_shard_count
            or 0
        )
        next_required_step = str(exploratory_summary.get("next_required_step", "")).strip()
        return {
            "state": str(exploratory_summary.get("hard_freeze_state", "")).strip(),
            "target_id": target_id,
            "hold_streak": hold_streak,
            "hold_limit": hold_limit,
            "freeze_note": str(exploratory_summary.get("freeze_note", "")).strip() or next_required_step,
            "next_required_step": next_required_step,
        }
    for summary in primary_watch_summaries:
        blocked_target_id = str(summary.get("guard_blocked_target_id", "")).strip()
        if target_id and blocked_target_id and blocked_target_id == target_id:
            return {
                "state": "guard_blocked_from_primary_watch",
                "target_id": blocked_target_id,
                "hold_streak": int(summary.get("guard_hold_streak", 0) or 0),
                "hold_limit": int(summary.get("guard_hold_limit", 0) or 0),
                "freeze_note": str(summary.get("guard_note", "")).strip(),
                "next_required_step": str(summary.get("next_required_step", "")).strip(),
            }
    if bool(exploratory_summary.get("guard_active", False)):
        return {
            "state": "guard_active_from_exploratory_lane",
            "target_id": target_id,
            "hold_streak": int(exploratory_summary.get("guard_hold_streak", 0) or 0),
            "hold_limit": int(exploratory_summary.get("guard_limit", 0) or 0),
            "freeze_note": str(exploratory_summary.get("freeze_note", "")).strip(),
            "next_required_step": str(exploratory_summary.get("next_required_step", "")).strip(),
        }
    return {
        "state": "",
        "target_id": "",
        "hold_streak": 0,
        "hold_limit": 0,
        "freeze_note": "",
        "next_required_step": "",
    }


def build_payload(
    portfolio: dict[str, Any],
    blueprint: dict[str, Any],
    brief_matrix: dict[str, Any],
    companion: dict[str, Any],
    outreach: dict[str, Any],
    rail_packet_index: dict[str, Any],
    schema: dict[str, Any],
    queue: dict[str, Any],
    one_page_briefs: dict[str, Any],
    brief_index: dict[str, Any],
    fill_queue: dict[str, Any],
    first_contact: dict[str, Any],
    priority3_fill_map: dict[str, Any],
    priority3_novelty_fill_map: dict[str, Any],
    next3_fill_map: dict[str, Any] | None,
    next3_novelty_fill_map: dict[str, Any] | None,
    mpro_vendor_cost_check: dict[str, Any],
    first_contact_export_bundle: dict[str, Any] | None,
    cleanup_manifest: dict[str, Any] | None,
    domain_generation_schema: dict[str, Any] | None = None,
    partner_export_schema: dict[str, Any] | None = None,
    priority3_render_split: dict[str, Any] | None = None,
    mpro_render_suite: dict[str, Any] | None = None,
    caix_render_suite: dict[str, Any] | None = None,
    tcruzi_pde_render_suite: dict[str, Any] | None = None,
    prep_artifact_lane: dict[str, Any] | None = None,
    priority3_run_queue: dict[str, Any] | None = None,
    mpro_launch_packet: dict[str, Any] | None = None,
    caix_launch_packet: dict[str, Any] | None = None,
    tcruzi_pde_launch_packet: dict[str, Any] | None = None,
    mpro_run_record: dict[str, Any] | None = None,
    caix_run_record: dict[str, Any] | None = None,
    tcruzi_pde_run_record: dict[str, Any] | None = None,
    mpro_run_status: dict[str, Any] | None = None,
    caix_result_review: dict[str, Any] | None = None,
    tcruzi_pde_result_review: dict[str, Any] | None = None,
    priority3_runtime_event: dict[str, Any] | None = None,
    priority3_runtime_runbook: dict[str, Any] | None = None,
    next3_run_queue: dict[str, Any] | None = None,
    next3_chain_stack: dict[str, Any] | None = None,
    next3_runtime_event: dict[str, Any] | None = None,
    next3_runtime_runbook: dict[str, Any] | None = None,
    next3_execution_console: dict[str, Any] | None = None,
    final2_run_queue: dict[str, Any] | None = None,
    final2_chain_stack: dict[str, Any] | None = None,
    final2_runtime_event: dict[str, Any] | None = None,
    final2_runtime_runbook: dict[str, Any] | None = None,
    final2_execution_console: dict[str, Any] | None = None,
    wave2_run_queue: dict[str, Any] | None = None,
    wave2_chain_stack: dict[str, Any] | None = None,
    wave2_runtime_event: dict[str, Any] | None = None,
    wave2_runtime_runbook: dict[str, Any] | None = None,
    wave2_execution_console: dict[str, Any] | None = None,
    master_queue: dict[str, Any] | None = None,
    master_runtime_runbook: dict[str, Any] | None = None,
    master_execution_console: dict[str, Any] | None = None,
    master_terminal_review: dict[str, Any] | None = None,
    outbound_execution_priority_board: dict[str, Any] | None = None,
    final_campaign_summary: dict[str, Any] | None = None,
    partner_send_round: dict[str, Any] | None = None,
    master_handoff_dashboard: dict[str, Any] | None = None,
    data_quality_assessment: dict[str, Any] | None = None,
    broad_screen_library_spec: dict[str, Any] | None = None,
    broad_screen_queue: dict[str, Any] | None = None,
    broad_screen_bridge: dict[str, Any] | None = None,
    broad_screen_compound_universe: dict[str, Any] | None = None,
    broad_screen_bulk_results: dict[str, Any] | None = None,
    broad_screen_repurposing_autofill: dict[str, Any] | None = None,
    broad_screen_execution_queue: dict[str, Any] | None = None,
    broad_screen_runtime_runbook: dict[str, Any] | None = None,
    broad_screen_bulk_result_source_schema: dict[str, Any] | None = None,
    broad_screen_bulk_result_row_examples: dict[str, Any] | None = None,
    broad_screen_target_rerank: dict[str, Any] | None = None,
    broad_screen_stability_score: dict[str, Any] | None = None,
    broad_screen_antitarget_queue: dict[str, Any] | None = None,
    broad_screen_antitarget_execution_queue: dict[str, Any] | None = None,
    broad_screen_primary_watch_state: dict[str, Any] | None = None,
    broad_screen_primary_watch: dict[str, Any] | None = None,
    broad_screen_antitarget_watch_state: dict[str, Any] | None = None,
    broad_screen_antitarget_watch: dict[str, Any] | None = None,
    broad_screen_actual_append: dict[str, Any] | None = None,
    broad_screen_next_target_extension: dict[str, Any] | None = None,
    broad_screen_throughput_bridge: dict[str, Any] | None = None,
    broad_screen_primary_retry_preset: dict[str, Any] | None = None,
    broad_screen_primary_hold_guard: dict[str, Any] | None = None,
    broad_screen_current_results_index: dict[str, Any] | None = None,
    broad_screen_monitor_semantics: dict[str, Any] | None = None,
    broad_screen_retry_handoff_summary: dict[str, Any] | None = None,
    broad_screen_dpre1_branch_review_surface: dict[str, Any] | None = None,
    broad_screen_stk17b_manual_retry_lane: dict[str, Any] | None = None,
    broad_screen_stk17b_exploratory_retry_lane: dict[str, Any] | None = None,
    broad_screen_stk17b_exploratory_followup_lane: dict[str, Any] | None = None,
    broad_screen_stk17b_followup_review_surface: dict[str, Any] | None = None,
    broad_screen_plpro_manual_retry_lane: dict[str, Any] | None = None,
    broad_screen_mapping_fix_retry_support: dict[str, Any] | None = None,
    broad_screen_stage1_mapping_fix_lanes: dict[str, Any] | None = None,
    broad_screen_mapping_fix_retry_policy_templates: dict[str, Any] | None = None,
    broad_screen_hard_target_rescue_lane: dict[str, Any] | None = None,
    broad_screen_rescue_anchor_artifacts: dict[str, Any] | None = None,
    broad_screen_rescue_three_bead_candidates: dict[str, Any] | None = None,
    broad_screen_tcruzi_pde_promoted_top4_review_packet: dict[str, Any] | None = None,
    broad_screen_tcruzi_pde_rescue_only_branch_summary: dict[str, Any] | None = None,
    broad_screen_kinase_retry_policy_templates: dict[str, Any] | None = None,
    broad_screen_target_retry_policy_templates: dict[str, Any] | None = None,
    broad_screen_dengue_stage6_tuning_surface: dict[str, Any] | None = None,
    broad_screen_dengue_exploratory_retry_lane: dict[str, Any] | None = None,
    broad_screen_lbdhodh_stage6_tuning_surface: dict[str, Any] | None = None,
    broad_screen_lbdhodh_exploratory_retry_lane: dict[str, Any] | None = None,
    broad_screen_lbdhodh_gate51_validation_review_surface: dict[str, Any] | None = None,
    broad_screen_selected_allatom_visual_bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ps = dict(portfolio.get("summary", {}) or {})
    bs = dict(blueprint.get("summary", {}) or {})
    ms = dict(brief_matrix.get("summary", {}) or {})
    cs = dict(companion.get("summary", {}) or {})
    os = dict(outreach.get("summary", {}) or {})
    rs = dict(rail_packet_index.get("summary", {}) or {})
    ss = dict(schema.get("summary", {}) or {})
    dgs = dict((domain_generation_schema or {}).get("summary", {}) or {})
    pes = dict((partner_export_schema or {}).get("summary", {}) or {})
    prs = dict((priority3_render_split or {}).get("summary", {}) or {})
    mrs = dict((mpro_render_suite or {}).get("summary", {}) or {})
    crs = dict((caix_render_suite or {}).get("summary", {}) or {})
    trs = dict((tcruzi_pde_render_suite or {}).get("summary", {}) or {})
    pals = dict((prep_artifact_lane or {}).get("summary", {}) or {})
    pqs = dict((priority3_run_queue or {}).get("summary", {}) or {})
    mls = dict((mpro_launch_packet or {}).get("summary", {}) or {})
    cls = dict((caix_launch_packet or {}).get("summary", {}) or {})
    tls = dict((tcruzi_pde_launch_packet or {}).get("summary", {}) or {})
    mrrs = dict((mpro_run_record or {}).get("summary", {}) or {})
    crrs2 = dict((caix_run_record or {}).get("summary", {}) or {})
    trrrs = dict((tcruzi_pde_run_record or {}).get("summary", {}) or {})
    mps = dict((mpro_run_status or {}).get("summary", {}) or {})
    crrs = dict((caix_result_review or {}).get("summary", {}) or {})
    trrs = dict((tcruzi_pde_result_review or {}).get("summary", {}) or {})
    pres = dict((priority3_runtime_event or {}).get("summary", {}) or {})
    prbs = dict((priority3_runtime_runbook or {}).get("summary", {}) or {})
    nxqs = dict((next3_run_queue or {}).get("summary", {}) or {})
    nxcs = dict((next3_chain_stack or {}).get("summary", {}) or {})
    nxes = dict((next3_runtime_event or {}).get("summary", {}) or {})
    nxrs = dict((next3_runtime_runbook or {}).get("summary", {}) or {})
    nxcons = dict((next3_execution_console or {}).get("summary", {}) or {})
    f2qs = dict((final2_run_queue or {}).get("summary", {}) or {})
    f2cs = dict((final2_chain_stack or {}).get("summary", {}) or {})
    f2es = dict((final2_runtime_event or {}).get("summary", {}) or {})
    f2rs = dict((final2_runtime_runbook or {}).get("summary", {}) or {})
    f2cons = dict((final2_execution_console or {}).get("summary", {}) or {})
    w2qs = dict((wave2_run_queue or {}).get("summary", {}) or {})
    w2cs = dict((wave2_chain_stack or {}).get("summary", {}) or {})
    w2es = dict((wave2_runtime_event or {}).get("summary", {}) or {})
    w2rs = dict((wave2_runtime_runbook or {}).get("summary", {}) or {})
    w2cons = dict((wave2_execution_console or {}).get("summary", {}) or {})
    mqs2 = dict((master_queue or {}).get("summary", {}) or {})
    mrs2 = dict((master_runtime_runbook or {}).get("summary", {}) or {})
    mcons2 = dict((master_execution_console or {}).get("summary", {}) or {})
    mtrs = dict((master_terminal_review or {}).get("summary", {}) or {})
    oebs = dict((outbound_execution_priority_board or {}).get("summary", {}) or {})
    fcss = dict((final_campaign_summary or {}).get("summary", {}) or {})
    psrs = dict((partner_send_round or {}).get("summary", {}) or {})
    mhds = dict((master_handoff_dashboard or {}).get("summary", {}) or {})
    dqas = dict((data_quality_assessment or {}).get("summary", {}) or {})
    bsls = dict((broad_screen_library_spec or {}).get("summary", {}) or {})
    bsqs = dict((broad_screen_queue or {}).get("summary", {}) or {})
    bsbs = dict((broad_screen_bridge or {}).get("summary", {}) or {})
    bscus = dict((broad_screen_compound_universe or {}).get("summary", {}) or {})
    bsbus = dict((broad_screen_bulk_results or {}).get("summary", {}) or {})
    bsrafs = dict((broad_screen_repurposing_autofill or {}).get("summary", {}) or {})
    bseqs = dict((broad_screen_execution_queue or {}).get("summary", {}) or {})
    bsrrs = dict((broad_screen_runtime_runbook or {}).get("summary", {}) or {})
    bsscs = dict((broad_screen_bulk_result_source_schema or {}).get("summary", {}) or {})
    bsbres = dict((broad_screen_bulk_result_row_examples or {}).get("summary", {}) or {})
    bstrs = dict((broad_screen_target_rerank or {}).get("summary", {}) or {})
    bssts = dict((broad_screen_stability_score or {}).get("summary", {}) or {})
    bsats = dict((broad_screen_antitarget_queue or {}).get("summary", {}) or {})
    bsaeqs = dict((broad_screen_antitarget_execution_queue or {}).get("summary", {}) or {})
    bspwss = dict((broad_screen_primary_watch_state or {}).get("summary", {}) or {})
    bspws = dict((broad_screen_primary_watch or {}).get("summary", {}) or {})
    bsawss = dict((broad_screen_antitarget_watch_state or {}).get("summary", {}) or {})
    bsaws = dict((broad_screen_antitarget_watch or {}).get("summary", {}) or {})
    bspwlp = _pid_snapshot(DEFAULT_BROAD_SCREEN_PRIMARY_WATCH_LOOP_PID)
    bsawlp = _pid_snapshot(DEFAULT_BROAD_SCREEN_ANTITARGET_WATCHER_LOOP_PID)
    bsaas = dict((broad_screen_actual_append or {}).get("summary", {}) or {})
    bsnxs = dict((broad_screen_next_target_extension or {}).get("summary", {}) or {})
    bstbs = dict((broad_screen_throughput_bridge or {}).get("summary", {}) or {})
    bsrps = dict((broad_screen_primary_retry_preset or {}).get("summary", {}) or {})
    bshgs = dict((broad_screen_primary_hold_guard or {}).get("summary", {}) or {})
    bcris = dict((broad_screen_current_results_index or {}).get("summary", {}) or {})
    bsmss = dict((broad_screen_monitor_semantics or {}).get("summary", {}) or {})
    bsrhs = dict((broad_screen_retry_handoff_summary or {}).get("summary", {}) or {})
    selected_allatom_visual = resolve_selected_allatom_visual_bundle(
        broad_screen_selected_allatom_visual_bundle,
        summary_sources=[bcris, bsmss, fcss, mhds, bsrhs],
    )
    selected_allatom_visual_fields = selected_allatom_visual_surface_fields(
        selected_allatom_visual
    )
    bdr1 = dict((broad_screen_dpre1_branch_review_surface or {}).get("summary", {}) or {})
    bssmls = dict((broad_screen_stk17b_manual_retry_lane or {}).get("summary", {}) or {})
    bsserls = dict((broad_screen_stk17b_exploratory_retry_lane or {}).get("summary", {}) or {})
    bssefls = dict((broad_screen_stk17b_exploratory_followup_lane or {}).get("summary", {}) or {})
    bssfrs = dict((broad_screen_stk17b_followup_review_surface or {}).get("summary", {}) or {})
    bspmls = dict((broad_screen_plpro_manual_retry_lane or {}).get("summary", {}) or {})
    bsmfrs = dict((broad_screen_mapping_fix_retry_support or {}).get("summary", {}) or {})
    bssmfl = dict((broad_screen_stage1_mapping_fix_lanes or {}).get("summary", {}) or {})
    bsmfrpts = dict((broad_screen_mapping_fix_retry_policy_templates or {}).get("summary", {}) or {})
    bshrls = dict((broad_screen_hard_target_rescue_lane or {}).get("summary", {}) or {})
    bsresas = dict((broad_screen_rescue_anchor_artifacts or {}).get("summary", {}) or {})
    bsr3bs = dict((broad_screen_rescue_three_bead_candidates or {}).get("summary", {}) or {})
    bstprps = dict((broad_screen_tcruzi_pde_promoted_top4_review_packet or {}).get("summary", {}) or {})
    bstcrbs = dict((broad_screen_tcruzi_pde_rescue_only_branch_summary or {}).get("summary", {}) or {})
    bskrts = dict((broad_screen_kinase_retry_policy_templates or {}).get("summary", {}) or {})
    bstrpts = dict((broad_screen_target_retry_policy_templates or {}).get("summary", {}) or {})
    bdgts = dict((broad_screen_dengue_stage6_tuning_surface or {}).get("summary", {}) or {})
    bdgrs = dict((broad_screen_dengue_exploratory_retry_lane or {}).get("summary", {}) or {})
    bslts = dict((broad_screen_lbdhodh_stage6_tuning_surface or {}).get("summary", {}) or {})
    bsldrs = dict((broad_screen_lbdhodh_exploratory_retry_lane or {}).get("summary", {}) or {})
    bslvrs = dict((broad_screen_lbdhodh_gate51_validation_review_surface or {}).get("summary", {}) or {})
    dengue_stage6_summary = _dengue_stage6_summary(
        broad_screen_execution_queue,
        broad_screen_dengue_stage6_tuning_surface,
        broad_screen_dengue_exploratory_retry_lane,
    )
    dengue_stage6_next_required_step = str(
        dengue_stage6_summary.get("next_required_step", "")
        or bdgrs.get("next_required_step", "")
        or bdgts.get("next_required_step", "")
    ).strip()
    rescue_next_required_step = _rescue_next_required_step(
        broad_screen_tcruzi_pde_rescue_only_branch_summary,
        broad_screen_tcruzi_pde_promoted_top4_review_packet,
        broad_screen_hard_target_rescue_lane,
        broad_screen_rescue_anchor_artifacts,
        broad_screen_rescue_three_bead_candidates,
    )
    pde_top4_review_packet_ready = _resolve_bool(
        bsrhs.get("tcruzi_pde_promoted_top4_review_packet_ready"),
        fcss.get("broad_screen_tcruzi_pde_promoted_top4_review_packet_ready"),
        str(bstprps.get("status", "")).strip() == "wetlab_tcruzi_pde_promoted_top4_review_packet_ready",
        default=False,
    )
    pde_top4_packet_ready_for_operator_review = _resolve_bool(
        bsrhs.get("tcruzi_pde_promoted_top4_review_packet_ready_for_operator_review"),
        fcss.get("broad_screen_tcruzi_pde_promoted_top4_packet_ready_for_operator_review"),
        bstprps.get("packet_ready_for_operator_review"),
        bstprps.get("packet_ready"),
        pde_top4_review_packet_ready,
        fcss.get("broad_screen_tcruzi_pde_promoted_top4_packet_ready"),
        default=pde_top4_review_packet_ready,
    )
    pde_top4_wetlab_final_gate_pass = _resolve_bool(
        bsrhs.get("tcruzi_pde_promoted_top4_review_packet_final_gate_pass"),
        bsrhs.get("tcruzi_pde_promoted_top4_wetlab_final_gate_pass"),
        fcss.get("broad_screen_tcruzi_pde_promoted_top4_wetlab_final_gate_pass"),
        bstprps.get("wetlab_final_gate_pass"),
        bstprps.get("wetlab_gate_pass"),
        default=pde_top4_packet_ready_for_operator_review,
    )
    pde_top4_claim_gate_available = _resolve_bool(
        bsrhs.get("tcruzi_pde_promoted_top4_review_packet_claim_gate_available"),
        bsrhs.get("tcruzi_pde_promoted_top4_claim_gate_available"),
        fcss.get("broad_screen_tcruzi_pde_promoted_top4_claim_gate_available"),
        bstprps.get("claim_gate_available"),
        default=False,
    )
    pde_top4_claim_ready_for_allatom = _resolve_bool(
        bsrhs.get("tcruzi_pde_promoted_top4_review_packet_claim_ready_for_allatom"),
        bsrhs.get("tcruzi_pde_promoted_top4_claim_ready_for_allatom"),
        fcss.get("broad_screen_tcruzi_pde_promoted_top4_claim_ready_for_allatom"),
        bstprps.get("claim_ready_for_allatom"),
        default=False,
    )
    pde_rescue_only_branch_summary_ready = _resolve_bool(
        bsrhs.get("tcruzi_pde_rescue_only_branch_summary_ready"),
        fcss.get("broad_screen_tcruzi_pde_rescue_only_branch_summary_ready"),
        str(bstcrbs.get("status", "")).strip() == "wetlab_tcruzi_pde_rescue_only_branch_summary_ready",
        default=False,
    )
    pde_branch_review_packet_ready_for_operator_review = _resolve_bool(
        bsrhs.get("tcruzi_pde_rescue_only_branch_review_packet_ready_for_operator_review"),
        fcss.get("broad_screen_tcruzi_pde_rescue_only_branch_review_packet_ready_for_operator_review"),
        bstcrbs.get("review_packet_ready_for_operator_review"),
        bstcrbs.get("packet_ready_for_operator_review"),
        bstcrbs.get("review_packet_ready"),
        bstcrbs.get("promoted_top4_packet_ready"),
        pde_top4_packet_ready_for_operator_review,
        default=pde_top4_packet_ready_for_operator_review,
    )
    pde_branch_review_packet_final_gate_pass = _resolve_bool(
        bsrhs.get("tcruzi_pde_rescue_only_branch_review_packet_final_gate_pass"),
        fcss.get("broad_screen_tcruzi_pde_rescue_only_branch_review_packet_final_gate_pass"),
        bstcrbs.get("review_packet_final_gate_pass"),
        bstcrbs.get("wetlab_final_gate_pass"),
        bstcrbs.get("review_packet_wetlab_gate_pass"),
        bstcrbs.get("wetlab_gate_pass"),
        default=pde_top4_wetlab_final_gate_pass,
    )
    pde_branch_review_packet_claim_gate_available = _resolve_bool(
        bsrhs.get("tcruzi_pde_rescue_only_branch_review_packet_claim_gate_available"),
        fcss.get("broad_screen_tcruzi_pde_rescue_only_branch_review_packet_claim_gate_available"),
        bstcrbs.get("review_packet_claim_gate_available"),
        bstcrbs.get("claim_gate_available"),
        default=pde_top4_claim_gate_available,
    )
    pde_branch_review_packet_claim_ready_for_allatom = _resolve_bool(
        bsrhs.get("tcruzi_pde_rescue_only_branch_review_packet_claim_ready_for_allatom"),
        fcss.get("broad_screen_tcruzi_pde_rescue_only_branch_review_packet_claim_ready_for_allatom"),
        bstcrbs.get("review_packet_claim_ready_for_allatom"),
        bstcrbs.get("claim_ready_for_allatom"),
        default=pde_top4_claim_ready_for_allatom,
    )
    pde_branch_ready_for_final_wetlab = _resolve_bool(
        bsrhs.get("tcruzi_pde_rescue_only_branch_ready_for_final_wetlab"),
        fcss.get("broad_screen_tcruzi_pde_rescue_only_branch_ready_for_final_wetlab"),
        bstcrbs.get("branch_ready_for_final_wetlab"),
        bool(bstcrbs.get("branch_to_rescue_only", False)) and pde_branch_review_packet_final_gate_pass,
        default=bool(bstcrbs.get("branch_to_rescue_only", False)) and pde_branch_review_packet_final_gate_pass,
    )
    pde_operator_packet_ready_for_operator_review = _resolve_bool(
        bsrhs.get("selected_rescue_branch_operator_packet_ready_for_operator_review"),
        bsrhs.get("tcruzi_pde_rescue_operator_packet_ready_for_operator_review"),
        fcss.get("selected_rescue_branch_operator_packet_ready_for_operator_review"),
        fcss.get("broad_screen_tcruzi_pde_rescue_operator_packet_ready_for_operator_review"),
        bstcrbs.get("operator_packet_ready_for_operator_review"),
        bsrhs.get("selected_rescue_branch_operator_packet_ready"),
        bsrhs.get("tcruzi_pde_rescue_operator_packet_ready"),
        fcss.get("selected_rescue_branch_operator_packet_ready"),
        fcss.get("broad_screen_tcruzi_pde_rescue_operator_packet_ready"),
        bstcrbs.get("operator_packet_ready"),
        default=False,
    )
    pde_operator_packet_final_gate_pass = _resolve_bool(
        bsrhs.get("selected_rescue_branch_operator_packet_final_gate_pass"),
        bsrhs.get("tcruzi_pde_rescue_operator_packet_final_gate_pass"),
        fcss.get("selected_rescue_branch_operator_packet_final_gate_pass"),
        fcss.get("broad_screen_tcruzi_pde_rescue_operator_packet_final_gate_pass"),
        bstcrbs.get("operator_packet_final_gate_pass"),
        default=pde_operator_packet_ready_for_operator_review,
    )
    pde_operator_packet_claim_gate_available = _resolve_bool(
        bsrhs.get("selected_rescue_branch_operator_packet_claim_gate_available"),
        bsrhs.get("tcruzi_pde_rescue_operator_packet_claim_gate_available"),
        fcss.get("selected_rescue_branch_operator_packet_claim_gate_available"),
        fcss.get("broad_screen_tcruzi_pde_rescue_operator_packet_claim_gate_available"),
        bstcrbs.get("operator_packet_claim_gate_available"),
        default=False,
    )
    pde_operator_packet_claim_ready_for_allatom = _resolve_bool(
        bsrhs.get("selected_rescue_branch_operator_packet_claim_ready_for_allatom"),
        bsrhs.get("tcruzi_pde_rescue_operator_packet_claim_ready_for_allatom"),
        fcss.get("selected_rescue_branch_operator_packet_claim_ready_for_allatom"),
        fcss.get("broad_screen_tcruzi_pde_rescue_operator_packet_claim_ready_for_allatom"),
        bstcrbs.get("operator_packet_claim_ready_for_allatom"),
        default=False,
    )
    pde_operator_packet_scope = str(
        bsrhs.get("selected_rescue_branch_operator_packet_scope")
        or bsrhs.get("tcruzi_pde_rescue_operator_packet_scope")
        or fcss.get("selected_rescue_branch_operator_packet_scope")
        or fcss.get("broad_screen_tcruzi_pde_rescue_operator_packet_scope")
        or bstcrbs.get("operator_packet_scope")
        or ""
    ).strip()
    selected_allatom_sources = (bcris, fcss, mhds, bsrhs, bsmss)
    selected_allatom_focus_available = bool(
        _text(
            bsrhs.get("selected_allatom_target_id", ""),
            fcss.get("selected_allatom_target_id", ""),
            mhds.get("selected_allatom_target_id", ""),
            bcris.get("selected_allatom_target_id", ""),
            bsmss.get("selected_allatom_target_id", ""),
            bsrhs.get("selected_allatom_surface_label", ""),
            fcss.get("selected_allatom_surface_label", ""),
            mhds.get("selected_allatom_surface_label", ""),
            bcris.get("selected_allatom_surface_label", ""),
            bsmss.get("selected_allatom_surface_label", ""),
        )
    )
    (
        selected_allatom_operator_review_reported,
        selected_allatom_operator_review_ready,
    ) = _resolve_reported_bool(
        selected_allatom_sources,
        reported_keys=("selected_allatom_operator_review_ready_reported",),
        value_keys=(
            "selected_allatom_packet_ready_for_operator_review",
            "selected_allatom_operator_review_ready",
            "selected_allatom_packet_ready",
        ),
    )
    (
        selected_allatom_wetlab_gate_reported,
        selected_allatom_wetlab_gate_pass,
    ) = _resolve_reported_bool(
        (bcris, fcss, mhds, bsrhs, bsmss),
        reported_keys=("selected_allatom_wetlab_gate_reported",),
        value_keys=(
            "selected_allatom_wetlab_gate_pass",
            "selected_allatom_gate_pass",
        ),
    )
    (
        selected_allatom_final_gate_reported,
        selected_allatom_final_gate_pass,
    ) = _resolve_reported_bool(
        (bcris, fcss, mhds, bsrhs, bsmss),
        reported_keys=("selected_allatom_final_gate_reported",),
        value_keys=(
            "selected_allatom_wetlab_final_gate_pass",
            "selected_allatom_final_gate_pass",
        ),
    )
    (
        selected_allatom_claim_gate_reported,
        selected_allatom_claim_gate_available,
    ) = _resolve_reported_bool(
        selected_allatom_sources,
        reported_keys=("selected_allatom_claim_gate_available_reported",),
        value_keys=("selected_allatom_claim_gate_available",),
    )
    (
        selected_allatom_claim_ready_reported,
        selected_allatom_claim_ready_for_allatom,
    ) = _resolve_reported_bool(
        selected_allatom_sources,
        reported_keys=("selected_allatom_claim_ready_for_allatom_reported",),
        value_keys=("selected_allatom_claim_ready_for_allatom",),
    )
    selected_allatom_readiness_semantics = _normalize_selected_allatom_semantics(
        _text(
            bsrhs.get("selected_allatom_readiness_semantics", ""),
            fcss.get("selected_allatom_readiness_semantics", ""),
            mhds.get("selected_allatom_readiness_semantics", ""),
        ),
        focus_available=selected_allatom_focus_available,
        final_gate_reported=selected_allatom_final_gate_reported,
    )
    selected_allatom_target_id = _text(
        bsrhs.get("selected_allatom_target_id", ""),
        fcss.get("selected_allatom_target_id", ""),
        mhds.get("selected_allatom_target_id", ""),
        bcris.get("selected_allatom_target_id", ""),
        bsmss.get("selected_allatom_target_id", ""),
    )
    selected_allatom_surface_label = _text(
        bsrhs.get("selected_allatom_surface_label", ""),
        fcss.get("selected_allatom_surface_label", ""),
        mhds.get("selected_allatom_surface_label", ""),
        bcris.get("selected_allatom_surface_label", ""),
        bsmss.get("selected_allatom_surface_label", ""),
    )
    selected_allatom_best_compound_name = _text(
        bsrhs.get("selected_allatom_best_compound_name", ""),
        fcss.get("selected_allatom_best_compound_name", ""),
        mhds.get("selected_allatom_best_compound_name", ""),
        bcris.get("selected_allatom_best_compound_name", ""),
    )
    selected_allatom_best_compound_name_human_readable = _text(
        bsrhs.get("selected_allatom_best_compound_name_human_readable", ""),
        fcss.get("selected_allatom_best_compound_name_human_readable", ""),
        mhds.get("selected_allatom_best_compound_name_human_readable", ""),
        bcris.get("selected_allatom_best_compound_name_human_readable", ""),
    )
    selected_allatom_best_compound_name_resolution = _text(
        bsrhs.get("selected_allatom_best_compound_name_resolution", ""),
        fcss.get("selected_allatom_best_compound_name_resolution", ""),
        mhds.get("selected_allatom_best_compound_name_resolution", ""),
        bcris.get("selected_allatom_best_compound_name_resolution", ""),
        default="unresolved",
    )
    (
        selected_allatom_review_packet_distance_reported,
        selected_allatom_review_packet_distance_A,
        selected_allatom_best_mean_min_distance_A_source,
    ) = _selected_allatom_review_packet_metric_from_sources(
        selected_allatom_sources,
        selected_target_id=selected_allatom_target_id,
        selected_surface_label=selected_allatom_surface_label,
        metric_key="best_mean_min_distance_A",
    )
    if selected_allatom_review_packet_distance_reported:
        selected_allatom_best_mean_min_distance_A = selected_allatom_review_packet_distance_A
    else:
        selected_allatom_best_mean_min_distance_A = 0.0
        selected_allatom_best_mean_min_distance_A_source = ""
        for summary in (bsrhs, fcss, mhds, bcris):
            if _has_value(summary, "selected_allatom_best_mean_min_distance_A"):
                selected_allatom_best_mean_min_distance_A = (
                    _safe_float(summary.get("selected_allatom_best_mean_min_distance_A"))
                    or 0.0
                )
                selected_allatom_best_mean_min_distance_A_source = _text(
                    summary.get("selected_allatom_best_mean_min_distance_A_source")
                )
                break
    selected_allatom_promoted_candidate_count = int(
        _text(
            bsrhs.get("selected_allatom_promoted_candidate_count", ""),
            fcss.get("selected_allatom_promoted_candidate_count", ""),
            mhds.get("selected_allatom_promoted_candidate_count", ""),
            bcris.get("selected_allatom_promoted_candidate_count", ""),
            default="0",
        )
        or 0
    )
    selected_allatom_under_2p5_candidate_count = int(
        _text(
            bsrhs.get("selected_allatom_under_2p5_candidate_count", ""),
            fcss.get("selected_allatom_under_2p5_candidate_count", ""),
            mhds.get("selected_allatom_under_2p5_candidate_count", ""),
            bcris.get("selected_allatom_under_2p5_candidate_count", ""),
            default="0",
        )
        or 0
    )
    selected_allatom_near_candidate_count = int(
        _text(
            bsrhs.get("selected_allatom_near_candidate_count", ""),
            fcss.get("selected_allatom_near_candidate_count", ""),
            mhds.get("selected_allatom_near_candidate_count", ""),
            bcris.get("selected_allatom_near_candidate_count", ""),
            default="0",
        )
        or 0
    )
    selected_allatom_next_required_step = _resolve_text_from_summaries(
        selected_allatom_sources,
        value_keys=("selected_allatom_next_required_step",),
    )
    (
        selected_allatom_commercial_reported,
        selected_allatom_commercial_overall_score_v1,
    ) = _resolve_reported_float(
        selected_allatom_sources,
        value_keys=(
            "selected_allatom_commercial_overall_score_v1",
            "commercial_overall_score_v1",
        ),
    )
    selected_allatom_commercial_schema_version = _resolve_text_from_summaries(
        selected_allatom_sources,
        value_keys=(
            "selected_allatom_commercial_schema_version",
            "commercial_schema_version",
        ),
    )
    (
        selected_allatom_commercial_hard_gate_reported,
        selected_allatom_commercial_hard_gate_pass_v1,
    ) = _resolve_reported_bool(
        selected_allatom_sources,
        value_keys=(
            "selected_allatom_commercial_hard_gate_pass_v1",
            "commercial_hard_gate_pass_v1",
        ),
    )
    selected_allatom_commercial_risk_bucket_v1 = _resolve_text_from_summaries(
        selected_allatom_sources,
        value_keys=(
            "selected_allatom_commercial_risk_bucket_v1",
            "commercial_risk_bucket_v1",
        ),
    )
    selected_allatom_commercial_decision_class_v1 = _resolve_text_from_summaries(
        selected_allatom_sources,
        value_keys=(
            "selected_allatom_commercial_decision_class_v1",
            "commercial_decision_class_v1",
        ),
    )
    selected_allatom_commercial_primary_upgrade_actions_v1 = _resolve_list_from_summaries(
        selected_allatom_sources,
        value_keys=(
            "selected_allatom_commercial_primary_upgrade_actions_v1",
            "commercial_primary_upgrade_actions_v1",
        ),
    )
    selected_allatom_commercial_schema_version_v2 = _resolve_text_from_summaries(
        selected_allatom_sources,
        value_keys=(
            "selected_allatom_commercial_schema_version_v2",
            "commercial_schema_version_v2",
        ),
    )
    (
        selected_allatom_commercial_reported_v2,
        selected_allatom_commercial_overall_score_v2,
    ) = _resolve_reported_float(
        selected_allatom_sources,
        value_keys=(
            "selected_allatom_commercial_overall_score_v2",
            "commercial_overall_score_v2",
        ),
    )
    (
        selected_allatom_commercial_hard_gate_reported_v2,
        selected_allatom_commercial_hard_gate_pass_v2,
    ) = _resolve_reported_bool(
        selected_allatom_sources,
        value_keys=(
            "selected_allatom_commercial_hard_gate_pass_v2",
            "commercial_hard_gate_pass_v2",
        ),
    )
    (
        selected_allatom_commercial_soft_reported_v2,
        selected_allatom_commercial_soft_score_v2,
    ) = _resolve_reported_float(
        selected_allatom_sources,
        value_keys=(
            "selected_allatom_commercial_soft_score_v2",
            "commercial_soft_score_v2",
        ),
    )
    (
        selected_allatom_commercial_confidence_reported_v2,
        selected_allatom_commercial_confidence_score_v2,
    ) = _resolve_reported_float(
        selected_allatom_sources,
        value_keys=(
            "selected_allatom_commercial_confidence_score_v2",
            "commercial_confidence_score_v2",
        ),
    )
    selected_allatom_commercial_reported_v2 = bool(
        selected_allatom_commercial_reported_v2
        or selected_allatom_commercial_soft_reported_v2
        or selected_allatom_commercial_confidence_reported_v2
        or bool(selected_allatom_commercial_schema_version_v2)
    )
    selected_allatom_commercial_risk_bucket_v2 = _resolve_text_from_summaries(
        selected_allatom_sources,
        value_keys=(
            "selected_allatom_commercial_risk_bucket_v2",
            "commercial_risk_bucket_v2",
        ),
    )
    selected_allatom_commercial_decision_class_v2 = _resolve_text_from_summaries(
        selected_allatom_sources,
        value_keys=(
            "selected_allatom_commercial_decision_class_v2",
            "commercial_decision_class_v2",
        ),
    )
    selected_allatom_commercial_primary_upgrade_actions_v2 = _resolve_list_from_summaries(
        selected_allatom_sources,
        value_keys=(
            "selected_allatom_commercial_primary_upgrade_actions_v2",
            "commercial_primary_upgrade_actions_v2",
        ),
    )
    selected_allatom_commercial_human_summary_v2 = _resolve_text_from_summaries(
        selected_allatom_sources,
        value_keys=(
            "selected_allatom_commercial_human_summary_v2",
            "commercial_human_summary_v2",
        ),
    )
    selected_allatom_commercial_provenance_mode_v2 = (
        "source_driven" if selected_allatom_commercial_reported_v2 else "not_reported"
    )
    selected_allatom_translation_reported = any(
        _has_value(summary, key)
        for summary, key in (
            (bsrhs, "selected_allatom_translation_gate_version"),
            (bsrhs, "selected_allatom_translation_gate_focus_status"),
            (bsrhs, "selected_allatom_translation_gate_focus_score"),
            (bsrhs, "selected_allatom_translation_gate_focus_reason"),
            (bsrhs, "selected_allatom_focus_shortlist_tier"),
            (bsrhs, "selected_allatom_recommended_next_expensive_lane"),
            (bsrhs, "selected_allatom_recommended_next_expensive_lane_reason"),
            (fcss, "selected_allatom_translation_gate_version"),
            (fcss, "selected_allatom_translation_gate_focus_status"),
            (fcss, "selected_allatom_translation_gate_focus_score"),
            (fcss, "selected_allatom_translation_gate_focus_reason"),
            (fcss, "selected_allatom_focus_shortlist_tier"),
            (fcss, "selected_allatom_recommended_next_expensive_lane"),
            (fcss, "selected_allatom_recommended_next_expensive_lane_reason"),
            (mhds, "selected_allatom_translation_gate_version"),
            (mhds, "selected_allatom_translation_gate_focus_status"),
            (mhds, "selected_allatom_translation_gate_focus_score"),
            (mhds, "selected_allatom_translation_gate_focus_reason"),
            (mhds, "selected_allatom_focus_shortlist_tier"),
            (mhds, "selected_allatom_recommended_next_expensive_lane"),
            (mhds, "selected_allatom_recommended_next_expensive_lane_reason"),
            (bcris, "selected_allatom_translation_gate_version"),
            (bcris, "selected_allatom_translation_gate_focus_status"),
            (bcris, "selected_allatom_translation_gate_focus_score"),
            (bcris, "selected_allatom_translation_gate_focus_reason"),
            (bcris, "selected_allatom_focus_shortlist_tier"),
            (bcris, "selected_allatom_recommended_next_expensive_lane"),
            (bcris, "selected_allatom_recommended_next_expensive_lane_reason"),
            (bsmss, "selected_allatom_translation_gate_version"),
            (bsmss, "selected_allatom_translation_gate_focus_status"),
            (bsmss, "selected_allatom_translation_gate_focus_score"),
            (bsmss, "selected_allatom_translation_gate_focus_reason"),
            (bsmss, "selected_allatom_focus_shortlist_tier"),
            (bsmss, "selected_allatom_recommended_next_expensive_lane"),
            (bsmss, "selected_allatom_recommended_next_expensive_lane_reason"),
        )
    )
    selected_allatom_translation_gate_version = _resolve_text_from_summaries(
        selected_allatom_sources,
        value_keys=(
            "selected_allatom_translation_gate_version",
            "translation_gate_version",
        ),
    )
    selected_allatom_translation_gate_focus_status = _resolve_text_from_summaries(
        selected_allatom_sources,
        value_keys=(
            "selected_allatom_translation_gate_focus_status",
            "translation_gate_focus_status",
        ),
    )
    (
        _selected_allatom_translation_gate_focus_score_reported,
        selected_allatom_translation_gate_focus_score,
    ) = _resolve_reported_float(
        selected_allatom_sources,
        value_keys=(
            "selected_allatom_translation_gate_focus_score",
            "translation_gate_focus_score",
        ),
    )
    selected_allatom_translation_gate_focus_reason = _resolve_text_from_summaries(
        selected_allatom_sources,
        value_keys=(
            "selected_allatom_translation_gate_focus_reason",
            "translation_gate_focus_reason",
        ),
    )
    selected_allatom_focus_shortlist_tier = _resolve_text_from_summaries(
        selected_allatom_sources,
        value_keys=(
            "selected_allatom_focus_shortlist_tier",
            "focus_shortlist_tier",
        ),
    )
    selected_allatom_recommended_next_expensive_lane = _resolve_text_from_summaries(
        selected_allatom_sources,
        value_keys=(
            "selected_allatom_recommended_next_expensive_lane",
            "recommended_next_expensive_lane",
        ),
    )
    selected_allatom_recommended_next_expensive_lane_reason = _resolve_text_from_summaries(
        selected_allatom_sources,
        value_keys=(
            "selected_allatom_recommended_next_expensive_lane_reason",
            "recommended_next_expensive_lane_reason",
        ),
    )
    selected_allatom_translation_provenance_mode = (
        "source_driven" if selected_allatom_translation_reported else "not_reported"
    )
    if not selected_allatom_translation_reported:
        translation_fallback = _infer_selected_allatom_translation_shortlist_fallback(
            selected_allatom_next_required_step,
        )
        if translation_fallback.get("reported", False):
            selected_allatom_translation_gate_version = _text(
                selected_allatom_translation_gate_version,
                translation_fallback.get("translation_gate_version", ""),
            )
            selected_allatom_translation_gate_focus_status = _text(
                selected_allatom_translation_gate_focus_status,
                translation_fallback.get("translation_gate_focus_status", ""),
            )
            selected_allatom_translation_gate_focus_reason = _text(
                selected_allatom_translation_gate_focus_reason,
                translation_fallback.get("translation_gate_focus_reason", ""),
            )
            selected_allatom_focus_shortlist_tier = _text(
                selected_allatom_focus_shortlist_tier,
                translation_fallback.get("focus_shortlist_tier", ""),
            )
            selected_allatom_recommended_next_expensive_lane = _text(
                selected_allatom_recommended_next_expensive_lane,
                translation_fallback.get("recommended_next_expensive_lane", ""),
            )
            selected_allatom_recommended_next_expensive_lane_reason = _text(
                selected_allatom_recommended_next_expensive_lane_reason,
                translation_fallback.get("recommended_next_expensive_lane_reason", ""),
            )
            selected_allatom_translation_provenance_mode = str(
                translation_fallback.get("provenance_mode", "inferred_from_partial_upstream")
            ).strip() or "inferred_from_partial_upstream"
    selected_allatom_rollups = _selected_allatom_human_rollups(
        focus_available=selected_allatom_focus_available,
        target_id=selected_allatom_target_id,
        surface_label=selected_allatom_surface_label,
        operator_review_reported=selected_allatom_operator_review_reported,
        operator_review_ready=selected_allatom_operator_review_ready,
        wetlab_gate_reported=selected_allatom_wetlab_gate_reported,
        wetlab_gate_pass=selected_allatom_wetlab_gate_pass,
        final_gate_reported=selected_allatom_final_gate_reported,
        final_gate_pass=selected_allatom_final_gate_pass,
        claim_gate_reported=selected_allatom_claim_gate_reported,
        claim_gate_available=selected_allatom_claim_gate_available,
        claim_ready_reported=selected_allatom_claim_ready_reported,
        claim_ready_for_allatom=selected_allatom_claim_ready_for_allatom,
        semantics=selected_allatom_readiness_semantics,
        best_compound_name=selected_allatom_best_compound_name,
        best_compound_name_human_readable=selected_allatom_best_compound_name_human_readable,
        best_compound_name_resolution=selected_allatom_best_compound_name_resolution,
        best_mean_min_distance_A=selected_allatom_best_mean_min_distance_A,
        promoted_candidate_count=selected_allatom_promoted_candidate_count,
        under_2p5_candidate_count=selected_allatom_under_2p5_candidate_count,
        near_candidate_count=selected_allatom_near_candidate_count,
        commercial_reported=selected_allatom_commercial_reported,
        commercial_hard_gate_reported=selected_allatom_commercial_hard_gate_reported,
        commercial_hard_gate_pass=selected_allatom_commercial_hard_gate_pass_v1,
        commercial_overall_score_v1=selected_allatom_commercial_overall_score_v1,
        commercial_risk_bucket_v1=selected_allatom_commercial_risk_bucket_v1,
        commercial_decision_class_v1=selected_allatom_commercial_decision_class_v1,
        commercial_primary_upgrade_actions_v1=selected_allatom_commercial_primary_upgrade_actions_v1,
        commercial_schema_version_v2=selected_allatom_commercial_schema_version_v2,
        commercial_reported_v2=selected_allatom_commercial_reported_v2,
        commercial_hard_gate_reported_v2=selected_allatom_commercial_hard_gate_reported_v2,
        commercial_hard_gate_pass_v2=selected_allatom_commercial_hard_gate_pass_v2,
        commercial_soft_score_v2=selected_allatom_commercial_soft_score_v2,
        commercial_confidence_score_v2=selected_allatom_commercial_confidence_score_v2,
        commercial_overall_score_v2=selected_allatom_commercial_overall_score_v2,
        commercial_risk_bucket_v2=selected_allatom_commercial_risk_bucket_v2,
        commercial_decision_class_v2=selected_allatom_commercial_decision_class_v2,
        commercial_primary_upgrade_actions_v2=selected_allatom_commercial_primary_upgrade_actions_v2,
        commercial_human_summary_v2=selected_allatom_commercial_human_summary_v2,
        commercial_provenance_mode_v2=selected_allatom_commercial_provenance_mode_v2,
        translation_gate_version=selected_allatom_translation_gate_version,
        translation_gate_focus_status=selected_allatom_translation_gate_focus_status,
        translation_gate_focus_score=selected_allatom_translation_gate_focus_score,
        translation_gate_focus_reason=selected_allatom_translation_gate_focus_reason,
        focus_shortlist_tier=selected_allatom_focus_shortlist_tier,
        recommended_next_expensive_lane=selected_allatom_recommended_next_expensive_lane,
        recommended_next_expensive_lane_reason=selected_allatom_recommended_next_expensive_lane_reason,
        translation_provenance_mode=selected_allatom_translation_provenance_mode,
    )
    selected_allatom_canonical_view = _selected_allatom_canonical_surface(
        review_packet_summary=bsrhs,
        retry_handoff_summary=bsrhs,
        current_results_index_summary=bcris,
        monitor_semantics_summary=bsmss,
        master_handoff_dashboard_summary=mhds,
        final_campaign_summary=fcss,
        partnering_stack_summary=None,
        selected_allatom_sources=selected_allatom_sources,
        selected_allatom_next_required_step=selected_allatom_next_required_step,
        selected_allatom_focus_available=selected_allatom_focus_available,
        selected_allatom_final_gate_reported=selected_allatom_final_gate_reported,
        selected_allatom_final_gate_pass=selected_allatom_final_gate_pass,
        selected_allatom_claim_gate_reported=selected_allatom_claim_gate_reported,
        selected_allatom_claim_gate_available=selected_allatom_claim_gate_available,
        selected_allatom_claim_ready_reported=selected_allatom_claim_ready_reported,
        selected_allatom_claim_ready_for_allatom=selected_allatom_claim_ready_for_allatom,
        selected_allatom_wetlab_gate_reported=selected_allatom_wetlab_gate_reported,
        selected_allatom_wetlab_gate_pass=selected_allatom_wetlab_gate_pass,
        selected_allatom_commercial_reported_v2=selected_allatom_commercial_reported_v2,
        selected_allatom_commercial_hard_gate_reported_v2=selected_allatom_commercial_hard_gate_reported_v2,
        selected_allatom_commercial_hard_gate_pass_v2=selected_allatom_commercial_hard_gate_pass_v2,
        selected_allatom_commercial_soft_score_v2=selected_allatom_commercial_soft_score_v2,
        selected_allatom_commercial_confidence_score_v2=selected_allatom_commercial_confidence_score_v2,
        selected_allatom_commercial_overall_score_v2=selected_allatom_commercial_overall_score_v2,
        selected_allatom_commercial_risk_bucket_v2=selected_allatom_commercial_risk_bucket_v2,
        selected_allatom_commercial_decision_class_v2=selected_allatom_commercial_decision_class_v2,
        selected_allatom_commercial_primary_upgrade_actions_v2=selected_allatom_commercial_primary_upgrade_actions_v2,
        selected_allatom_commercial_human_summary_v2=selected_allatom_commercial_human_summary_v2,
        selected_allatom_translation_gate_version=selected_allatom_translation_gate_version,
        selected_allatom_translation_gate_focus_status=selected_allatom_translation_gate_focus_status,
        selected_allatom_translation_gate_focus_score=selected_allatom_translation_gate_focus_score,
        selected_allatom_translation_gate_focus_reason=selected_allatom_translation_gate_focus_reason,
        selected_allatom_focus_shortlist_tier=selected_allatom_focus_shortlist_tier,
        selected_allatom_recommended_next_expensive_lane=selected_allatom_recommended_next_expensive_lane,
        selected_allatom_recommended_next_expensive_lane_reason=selected_allatom_recommended_next_expensive_lane_reason,
        selected_allatom_best_mean_min_distance_A=selected_allatom_best_mean_min_distance_A,
        selected_allatom_promoted_candidate_count=selected_allatom_promoted_candidate_count,
        selected_allatom_under_2p5_candidate_count=selected_allatom_under_2p5_candidate_count,
        selected_allatom_near_candidate_count=selected_allatom_near_candidate_count,
    )
    if (
        selected_allatom_wetlab_gate_pass
        and selected_allatom_final_gate_pass
        and selected_allatom_claim_ready_for_allatom
    ):
        translation_status = _text(
            selected_allatom_canonical_view.get("translation_gate_focus_status"),
            selected_allatom_translation_gate_focus_status,
            default="not reported",
        )
        lane = _text(
            selected_allatom_canonical_view.get("recommended_next_expensive_lane"),
            selected_allatom_recommended_next_expensive_lane,
        )
        lane_phrase = "expensive lane deferred" if lane == "defer_expensive_lane" else f"next expensive lane `{lane}`"
        selected_allatom_next_required_step = (
            "Selected all-atom delivery P0 is green; broader/default wetlab lane remains closed; "
            f"translation gate remains {translation_status}; {lane_phrase}."
        )
    selected_allatom_rollups["human_summary"] = _joined(
        selected_allatom_rollups["human_summary"],
        selected_allatom_canonical_view.get("human_summary", ""),
    )
    exploratory_freeze = _exploratory_freeze_snapshot(bssefls or bsserls, bspws, bspwss)
    primary_watch_loop_attached = bool(bspwlp.get("pid_alive", False))
    primary_watch_loop_liveness = (
        "attached"
        if primary_watch_loop_attached
        else "stale"
        if str(bspwlp.get("pid_state", "")).strip() == "stale"
        else "detached"
    )
    primary_watch_loop_fallback_mode = (
        "compute-attached"
        if primary_watch_loop_attached
        else "stale-recovery"
        if primary_watch_loop_liveness == "stale"
        else "manual-restart"
    )
    antitarget_watch_loop_attached = bool(bsawlp.get("pid_alive", False))
    antitarget_watch_loop_liveness = (
        "attached"
        if antitarget_watch_loop_attached
        else "stale"
        if str(bsawlp.get("pid_state", "")).strip() == "stale"
        else "detached"
    )
    antitarget_watch_loop_fallback_mode = (
        "supervision-only"
        if antitarget_watch_loop_attached and bool(bsawss.get("supervision_only", bsaws.get("supervision_only", False)))
        else "compute-attached"
        if antitarget_watch_loop_attached
        else "stale-recovery"
        if antitarget_watch_loop_liveness == "stale"
        else "manual-restart"
    )
    master_active_stack_level = str(mcons2.get("active_stack_level", mqs2.get("active_stack_level", ""))).strip()
    master_active_target_id = str(mcons2.get("active_target_id", mqs2.get("active_target_id", ""))).strip()
    master_active_target_queue_status = str(mcons2.get("active_target_queue_status", mqs2.get("active_target_queue_status", ""))).strip()
    master_active_target_execution_state = str(mcons2.get("active_target_execution_state", mqs2.get("active_target_execution_state", ""))).strip()
    master_stack_gate_states = dict(mcons2.get("stack_gate_states", {}) or mqs2.get("stack_gate_states", {}) or {})
    master_lbdhodh_blockers = dict(mcons2.get("lbdhodh_blockers", {}) or f2cs.get("lbdhodh_blockers", {}) or mqs2.get("lbdhodh_blockers", {}) or {})
    master_wave2_release_gate_status = str(
        mcons2.get("wave2_release_gate_status", mqs2.get("wave2_release_gate_status", trrs.get("wave2_release_gate_status", "")))
    ).strip()
    master_wave2_release_blocked = bool(
        mcons2.get("wave2_release_blocked", mqs2.get("wave2_release_blocked", trrs.get("wave2_release_blocked", True)))
    )
    master_wave2_ready = bool(mcons2.get("wave2_ready", mqs2.get("wave2_ready", not master_wave2_release_blocked)))
    master_wave2_queue_status = str(
        mcons2.get(
            "wave2_queue_status",
            mqs2.get("wave2_queue_status", "ready_after_previous_review" if master_wave2_ready else "blocked_on_previous_review"),
        )
    ).strip()
    qs = dict(queue.get("summary", {}) or {})
    ws = dict(one_page_briefs.get("summary", {}) or {})
    bis = dict(brief_index.get("summary", {}) or {})
    fs = dict(fill_queue.get("summary", {}) or {})
    cs2 = dict(first_contact.get("summary", {}) or {})
    p3s = dict(priority3_fill_map.get("summary", {}) or {})
    n3s = dict(priority3_novelty_fill_map.get("summary", {}) or {})
    nxs = dict((next3_fill_map or {}).get("summary", {}) or {})
    nns = dict((next3_novelty_fill_map or {}).get("summary", {}) or {})
    mvs = dict(mpro_vendor_cost_check.get("summary", {}) or {})
    exs = dict((first_contact_export_bundle or {}).get("summary", {}) or {})
    cms = dict((cleanup_manifest or {}).get("summary", {}) or {})
    mpro_run_record_ready = bool(
        str(mrrs.get("artifact_kind", "")).strip() == "run_record"
        and str(mrrs.get("target_id", "")).strip() == "SARS-CoV-2 Mpro"
    )
    caix_run_record_ready = bool(
        str(crrs2.get("artifact_kind", "")).strip() == "run_record"
        and str(crrs2.get("target_id", "")).strip() == "CA IX"
    )
    tcruzi_pde_run_record_ready = bool(
        str(trrrs.get("artifact_kind", "")).strip() == "run_record"
        and str(trrrs.get("target_id", "")).strip() == "T. cruzi PDE"
    )

    return {
        "summary": {
            "status": "wetlab_partnering_stack_ready",
            "artifact_kind": "wetlab_partnering_stack",
            "artifact_schema_version": "wetlab_partnering_stack.v1",
            "artifact_completeness": "full_partnering_stack",
            "portfolio_target_count": int(ps.get("total_target_count", 0) or 0),
            "wave1_target_count": int(bs.get("wave1_target_count", 0) or 0),
            "brief_matrix_count": int(ms.get("row_count", 0) or 0),
            "companion_panel_count": int(cs.get("row_count", 0) or 0),
            "outreach_track_count": int(os.get("track_count", 0) or 0),
            "rail_packet_index_ready": bool(rs.get("status") == "wetlab_wave1_rail_packet_index_ready"),
            "brief_schema_ready": bool(ss.get("status") == "wetlab_one_page_brief_schema_ready"),
            "domain_generation_schema_ready": bool(dgs.get("status") == "wetlab_domain_generation_schema_ready"),
            "partner_export_schema_ready": bool(pes.get("status") == "wetlab_partner_export_schema_ready"),
            "priority3_render_split_ready": bool(prs.get("status") == "wetlab_priority3_target_render_split_ready"),
            "sarscov2_mpro_render_suite_ready": bool(mrs.get("status") == "sarscov2_mpro_render_suite_ready"),
            "caix_render_suite_ready": bool(crs.get("status") == "caix_render_suite_ready"),
            "tcruzi_pde_render_suite_ready": bool(trs.get("status") == "tcruzi_pde_render_suite_ready"),
            "priority3_target_overlay_ready_count": sum(
                1
                for ready in (
                    mrs.get("status") == "sarscov2_mpro_render_suite_ready",
                    crs.get("status") == "caix_render_suite_ready",
                    trs.get("status") == "tcruzi_pde_render_suite_ready",
                )
                if ready
            ),
            "prep_artifact_lane_ready": bool(pals.get("status") == "wetlab_prep_artifact_lane_ready"),
            "priority3_run_queue_ready": bool(pqs.get("status") == "wetlab_priority3_protein_run_queue_ready"),
            "mpro_launch_packet_ready": bool(mls.get("status") == "sarscov2_mpro_launch_packet_ready"),
            "caix_launch_packet_ready": bool(cls.get("status") == "caix_launch_packet_ready"),
            "tcruzi_pde_launch_packet_ready": bool(tls.get("status") == "tcruzi_pde_launch_packet_ready"),
            "priority3_launch_packet_ready_count": sum(
                1
                for ready in (
                    mls.get("status") == "sarscov2_mpro_launch_packet_ready",
                    cls.get("status") == "caix_launch_packet_ready",
                    tls.get("status") == "tcruzi_pde_launch_packet_ready",
                )
                if ready
            ),
            "mpro_run_record_ready": mpro_run_record_ready,
            "caix_run_record_ready": caix_run_record_ready,
            "tcruzi_pde_run_record_ready": tcruzi_pde_run_record_ready,
            "priority3_run_record_ready_count": sum(
                1
                for ready in (
                    mpro_run_record_ready,
                    caix_run_record_ready,
                    tcruzi_pde_run_record_ready,
                )
                if ready
            ),
            "mpro_run_status_ready": bool(str(mps.get("status", "")).strip() == "sarscov2_mpro_run_status_ready"),
            "caix_result_review_ready": bool(str(crrs.get("status", "")).strip() == "caix_result_review_ready"),
            "tcruzi_pde_result_review_ready": bool(str(trrs.get("status", "")).strip() == "tcruzi_pde_result_review_ready"),
            "priority3_runtime_event_ready": bool(str(pres.get("status", "")).strip() == "wetlab_priority3_runtime_event_applied"),
            "priority3_runtime_runbook_ready": bool(str(prbs.get("status", "")).strip() == "wetlab_priority3_runtime_runbook_ready"),
            "next3_run_queue_ready": bool(str(nxqs.get("status", "")).strip() == "wetlab_next3_protein_run_queue_ready"),
            "next3_chain_stack_ready": bool(str(nxcs.get("status", "")).strip() == "wetlab_next3_chain_stack_ready"),
            "next3_runtime_event_ready": bool(str(nxes.get("status", "")).strip() == "wetlab_next3_runtime_event_applied"),
            "next3_runtime_runbook_ready": bool(str(nxrs.get("status", "")).strip() == "wetlab_next3_runtime_runbook_ready"),
            "next3_execution_console_ready": bool(str(nxcons.get("status", "")).strip() == "wetlab_next3_execution_console_ready"),
            "final2_run_queue_ready": bool(str(f2qs.get("status", "")).strip() == "wetlab_final2_protein_run_queue_ready"),
            "final2_chain_stack_ready": bool(str(f2cs.get("status", "")).strip() == "wetlab_final2_chain_stack_ready"),
            "final2_runtime_event_ready": bool(str(f2es.get("status", "")).strip() == "wetlab_final2_runtime_event_applied"),
            "final2_runtime_runbook_ready": bool(str(f2rs.get("status", "")).strip() == "wetlab_final2_runtime_runbook_ready"),
            "final2_execution_console_ready": bool(str(f2cons.get("status", "")).strip() == "wetlab_final2_execution_console_ready"),
            "wave2_run_queue_ready": bool(str(w2qs.get("status", "")).strip() == "wetlab_wave2_protein_run_queue_ready"),
            "wave2_chain_stack_ready": bool(str(w2cs.get("status", "")).strip() == "wetlab_wave2_chain_stack_ready"),
            "wave2_runtime_event_ready": bool(str(w2es.get("status", "")).strip() == "wetlab_wave2_runtime_event_applied"),
            "wave2_runtime_runbook_ready": bool(str(w2rs.get("status", "")).strip() == "wetlab_wave2_runtime_runbook_ready"),
            "wave2_execution_console_ready": bool(str(w2cons.get("status", "")).strip() == "wetlab_wave2_execution_console_ready"),
            "master_queue_ready": bool(str(mqs2.get("status", "")).strip() == "wetlab_master_execution_queue_ready"),
            "master_runtime_runbook_ready": bool(str(mrs2.get("status", "")).strip() == "wetlab_master_runtime_runbook_ready"),
            "master_execution_console_ready": bool(str(mcons2.get("status", "")).strip() == "wetlab_master_execution_console_ready"),
            "master_terminal_review_ready": bool(str(mtrs.get("status", "")).strip() == "wetlab_master_terminal_review_ready"),
            "outbound_execution_priority_board_ready": bool(
                str(oebs.get("status", "")).strip() == "wetlab_outbound_execution_priority_board_ready"
            ),
            "final_campaign_summary_ready": bool(str(fcss.get("status", "")).strip() == "wetlab_final_campaign_summary_ready"),
            "partner_send_round_ready": bool(str(psrs.get("status", "")).strip() == "wetlab_partner_send_round_ready"),
            "master_handoff_dashboard_ready": bool(str(mhds.get("status", "")).strip() == "wetlab_master_handoff_dashboard_ready"),
            "data_quality_assessment_ready": bool(str(dqas.get("status", "")).strip() == "wetlab_data_quality_assessment_ready"),
            "broad_screen_library_spec_ready": bool(
                str(bsls.get("status", "")).strip() == "wetlab_broad_screen_library_spec_ready"
            ),
            "broad_screen_queue_ready": bool(str(bsqs.get("status", "")).strip() == "wetlab_broad_screen_queue_ready"),
            "broad_screen_bridge_ready": bool(str(bsbs.get("status", "")).strip() == "wetlab_broad_screen_bridge_ready"),
            "broad_screen_compound_universe_ready": bool(
                str(bscus.get("status", "")).strip() == "wetlab_broad_screen_compound_universe_ready"
            ),
            "broad_screen_bulk_results_ready": bool(
                str(bsbus.get("status", "")).strip() == "wetlab_broad_screen_bulk_results_ready"
            ),
            "broad_screen_repurposing_autofill_ready": bool(
                str(bsrafs.get("status", "")).strip() == "wetlab_broad_screen_repurposing_autofill_ready"
            ),
            "broad_screen_execution_queue_ready": bool(
                str(bseqs.get("status", "")).strip() == "wetlab_broad_screen_execution_queue_ready"
            ),
            "broad_screen_runtime_runbook_ready": bool(
                str(bsrrs.get("status", "")).strip() == "wetlab_broad_screen_runtime_runbook_ready"
            ),
            "broad_screen_bulk_result_source_schema_ready": bool(
                str(bsscs.get("status", "")).strip() == "wetlab_broad_screen_bulk_result_source_schema_ready"
            ),
            "broad_screen_bulk_result_row_examples_ready": bool(
                str(bsbres.get("status", "")).strip() == "wetlab_broad_screen_bulk_result_row_examples_ready"
            ),
            "broad_screen_target_rerank_ready": bool(
                str(bstrs.get("status", "")).strip() == "wetlab_broad_screen_target_rerank_ready"
            ),
            "broad_screen_stability_score_ready": bool(
                str(bssts.get("status", "")).strip() == "wetlab_broad_screen_stability_score_ready"
            ),
            "broad_screen_antitarget_queue_ready": bool(
                str(bsats.get("status", "")).strip() == "wetlab_broad_screen_antitarget_queue_ready"
            ),
            "broad_screen_antitarget_execution_queue_ready": bool(
                str(bsaeqs.get("status", "")).strip() == "wetlab_broad_screen_antitarget_execution_queue_ready"
            ),
            "broad_screen_primary_watch_state_ready": bool(
                _primary_watch_ready(bspwss) or _primary_watch_ready(bspws)
            ),
            "broad_screen_primary_watch_ready": bool(
                _primary_watch_ready(bspws) or _primary_watch_ready(bspwss)
            ),
            "broad_screen_primary_watch_next_required_step": _primary_watch_next_required_step(bspws, bspwss),
            "broad_screen_primary_watch_loop_pid": int(bspwlp.get("pid", 0) or 0),
            "broad_screen_primary_watch_loop_attached": primary_watch_loop_attached,
            "broad_screen_primary_watch_liveness": primary_watch_loop_liveness,
            "broad_screen_primary_watch_fallback_mode": primary_watch_loop_fallback_mode,
            "broad_screen_primary_watch_exploratory_success_freeze_target_id": str(
                bspws.get("exploratory_success_freeze_target_id", "") or bspwss.get("exploratory_success_freeze_target_id", "")
            ).strip(),
            "broad_screen_primary_watch_exploratory_success_freeze_shard_id": str(
                bspws.get("exploratory_success_freeze_shard_id", "") or bspwss.get("exploratory_success_freeze_shard_id", "")
            ).strip(),
            "broad_screen_antitarget_watch_state_ready": bool(
                str(bsawss.get("status", "")).strip() == "wetlab_broad_screen_antitarget_watcher_state_ready"
            ),
            "broad_screen_antitarget_watch_ready": bool(
                str(bsaws.get("status", "")).strip() == "wetlab_broad_screen_antitarget_watcher_ready"
            ),
            "broad_screen_antitarget_watch_next_required_step": _normalize_antitarget_watch_step(
                str(bsaws.get("next_required_step", "") or bsawss.get("next_required_step", "")).strip(),
                bsaeqs,
            ),
            "broad_screen_antitarget_watch_loop_pid": int(bsawlp.get("pid", 0) or 0),
            "broad_screen_antitarget_watch_loop_attached": antitarget_watch_loop_attached,
            "broad_screen_antitarget_watch_liveness": antitarget_watch_loop_liveness,
            "broad_screen_antitarget_watch_fallback_mode": antitarget_watch_loop_fallback_mode,
            "broad_screen_actual_append_ready": bool(
                str(bsaas.get("status", "")).strip().startswith("wetlab_broad_screen_actual_append_")
            ),
            "broad_screen_append_batch_pending_entry_count": int(bsaas.get("queued_pending_entry_count", 0) or 0),
            "broad_screen_next_target_extension_ready": bool(
                str(bsnxs.get("status", "")).strip() == "wetlab_broad_screen_next_target_extension_ready"
            ),
            "broad_screen_throughput_bridge_ready": bool(
                str(bstbs.get("status", "")).strip() == "wetlab_broad_screen_throughput_bridge_ready"
            ),
            "broad_screen_throughput_target_id": str(bstbs.get("target_id", "")).strip(),
            "broad_screen_throughput_shard_id": str(bstbs.get("shard_id", "")).strip(),
            "broad_screen_throughput_execute_ready": bool(bstbs.get("throughput_execute_ready", False)),
            "broad_screen_primary_retry_preset_ready": bool(
                str(bsrps.get("status", "")).strip() == "wetlab_primary_retry_preset_surface_ready"
            ),
            "broad_screen_primary_retry_guard_blocked_target_count": int(
                bsrps.get("guard_blocked_target_count", 0) or 0
            ),
            "broad_screen_primary_hold_guard_ready": bool(
                str(bshgs.get("status", "")).strip() == "wetlab_primary_hold_guard_surface_ready"
            ),
            "broad_screen_primary_hold_guard_triggered_target_count": int(
                bshgs.get("triggered_target_count", 0) or 0
            ),
            "broad_screen_current_results_index_ready": bool(
                str(bcris.get("status", "")).strip() == "wetlab_current_results_index_ready"
            ),
            "broad_screen_current_results_group_count": int(bcris.get("group_count", 0) or 0),
            "broad_screen_monitor_semantics_ready": bool(
                str(bsmss.get("status", "")).strip() == "wetlab_monitor_semantics_ready"
            ),
            "broad_screen_monitor_guard_active": bool(bsmss.get("guard_active", False)),
            "broad_screen_retry_handoff_summary_ready": bool(
                str(bsrhs.get("status", "")).strip() == "wetlab_retry_handoff_summary_ready"
            ),
            "broad_screen_retry_handoff_manual_retry_decision_count": int(
                bsrhs.get("manual_retry_decision_count", 0) or 0
            ),
            "broad_screen_retry_handoff_focus_target_id": str(
                bsrhs.get(
                    "selected_rescue_review_target_id",
                    bsrhs.get(
                        "selected_validated_target_id",
                        bslvrs.get("target_id", "") if bool(bslvrs.get("gate51_validated", False)) else bsrhs.get("manual_retry_focus_target_id", ""),
                    ),
                )
            ).strip(),
            "broad_screen_dpre1_branch_review_ready": bool(
                str(bdr1.get("status", "")).strip() == "wetlab_dpre1_branch_review_surface_ready"
            ),
            "broad_screen_dpre1_branch_review_target_id": str(bdr1.get("target_id", "")).strip(),
            "broad_screen_dpre1_branch_review_branch_label": str(bdr1.get("branch_label", "")).strip(),
            "broad_screen_dpre1_branch_review_branch_state": str(bdr1.get("branch_state", "")).strip(),
            "broad_screen_dpre1_branch_review_source_priority": str(bdr1.get("source_priority", "")).strip(),
            "broad_screen_dpre1_branch_review_decision_source_priority": str(
                bdr1.get("decision_source_priority", "")
            ).strip(),
            "broad_screen_dpre1_branch_review_result_review_status": str(
                bdr1.get("result_review_status", "")
            ).strip(),
            "broad_screen_dpre1_branch_review_result_summary_status": str(
                bdr1.get("result_summary_status", "")
            ).strip(),
            "broad_screen_dpre1_branch_review_launch_packet_status": str(
                bdr1.get("launch_packet_status", "")
            ).strip(),
            "broad_screen_dpre1_branch_review_stage6_tuning_surface_ready": bool(
                bdr1.get("stage6_tuning_surface_ready", False)
            ),
            "broad_screen_dpre1_branch_review_stage6_tuning_source_priority": str(
                bdr1.get("stage6_tuning_source_priority", "")
            ).strip(),
            "broad_screen_dpre1_branch_review_stage6_tuning_recommended_threshold_A": float(
                bdr1.get("stage6_tuning_recommended_threshold_A", 0.0) or 0.0
            ),
            "broad_screen_dpre1_branch_review_stage6_tuning_immediately_runnable_command_kind": str(
                bdr1.get("stage6_tuning_immediately_runnable_command_kind", "")
            ).strip(),
            "broad_screen_dpre1_branch_review_exploratory_retry_lane_ready": bool(
                bdr1.get("exploratory_retry_lane_ready", False)
            ),
            "broad_screen_dpre1_branch_review_exploratory_source_priority": str(
                bdr1.get("exploratory_source_priority", "")
            ).strip(),
            "broad_screen_dpre1_branch_review_exploratory_retry_lane_label": str(
                bdr1.get("exploratory_retry_lane_label", "")
            ).strip(),
            "broad_screen_dpre1_branch_review_exploratory_retry_selected_command_kind": str(
                bdr1.get("exploratory_retry_selected_command_kind", "")
            ).strip(),
            "broad_screen_dpre1_branch_review_exploratory_retry_selected_threshold_A": float(
                bdr1.get("exploratory_retry_selected_threshold_A", 0.0) or 0.0
            ),
            "broad_screen_dpre1_branch_review_successor_target": str(bdr1.get("successor_target", "")).strip(),
            "broad_screen_dpre1_branch_review_successor_gate_state": str(
                bdr1.get("successor_gate_state", "")
            ).strip(),
            "broad_screen_dpre1_branch_review_next_required_step": str(
                bdr1.get("next_required_step", "")
            ).strip(),
            "broad_screen_lbdhodh_stage6_tuning_surface_ready": bool(
                str(bslts.get("status", "")).strip() == "wetlab_lbdhodh_stage6_tuning_surface_ready"
            ),
            "broad_screen_lbdhodh_stage6_recommended_threshold_A": float(
                bslts.get("recommended_observed_threshold_A", 0.0) or 0.0
            ),
            "broad_screen_lbdhodh_stage6_immediately_runnable_command_kind": str(
                bslts.get("immediately_runnable_command_kind", "")
            ).strip(),
            "broad_screen_lbdhodh_gate51_validation_review_surface_ready": bool(
                str(bslvrs.get("status", "")).strip() == "wetlab_lbdhodh_gate51_validation_review_surface_ready"
            ),
            "broad_screen_lbdhodh_gate51_validated": bool(bslvrs.get("gate51_validated", False)),
            "broad_screen_lbdhodh_gate51_validation_decision": str(bslvrs.get("decision", "")).strip(),
            "broad_screen_lbdhodh_gate51_validation_default_lane_reopen_allowed": bool(
                bslvrs.get("default_lane_reopen_allowed", False)
            ),
            "broad_screen_lbdhodh_gate51_validation_branch_to_gate51_only": bool(
                bslvrs.get("branch_to_gate51_only", False)
            ),
            "broad_screen_lbdhodh_gate51_validation_success_count": int(
                bslvrs.get("gate51_validation_success_count", 0) or 0
            ),
            "broad_screen_lbdhodh_gate51_validation_row_count": int(
                bslvrs.get("gate51_validation_row_count", 0) or 0
            ),
            "broad_screen_lbdhodh_gate51_validation_validated_command_kind": str(
                bslvrs.get("validated_command_kind", "")
            ).strip(),
            "broad_screen_lbdhodh_gate51_validation_validated_threshold_A": float(
                bslvrs.get("validated_threshold_A", 0.0) or 0.0
            ),
            "broad_screen_lbdhodh_gate51_validation_next_required_step": str(
                bslvrs.get("next_required_step", "")
            ).strip(),
            "selected_validated_target_id": str(
                bsrhs.get("selected_validated_target_id", bslvrs.get("target_id", ""))
            ).strip(),
            "selected_validated_surface_label": str(
                bsrhs.get(
                    "selected_validated_surface_label",
                    "gate5.1_validation_review" if bool(bslvrs.get("gate51_validated", False)) else "",
                )
            ).strip(),
            "selected_validated_selected_command_kind": str(
                bsrhs.get("selected_validated_selected_command_kind", bslvrs.get("validated_command_kind", ""))
            ).strip(),
            "selected_validated_threshold_A": float(
                bsrhs.get("selected_validated_threshold_A", bslvrs.get("validated_threshold_A", 0.0)) or 0.0
            ),
            "selected_validated_next_required_step": str(
                bsrhs.get("selected_validated_next_required_step", bslvrs.get("next_required_step", ""))
            ).strip(),
            "selected_krs1_branch_review_target_id": str(
                bsrhs.get("selected_krs1_branch_review_target_id", "")
            ).strip(),
            "selected_krs1_branch_review_branch_label": str(
                bsrhs.get("selected_krs1_branch_review_branch_label", "")
            ).strip(),
            "selected_krs1_branch_review_branch_state": str(
                bsrhs.get("selected_krs1_branch_review_branch_state", "")
            ).strip(),
            "selected_krs1_branch_review_selected_command_kind": str(
                bsrhs.get("selected_krs1_branch_review_selected_command_kind", "")
            ).strip(),
            "selected_krs1_branch_review_selected_threshold_A": float(
                bsrhs.get("selected_krs1_branch_review_selected_threshold_A", 0.0) or 0.0
            ),
            "selected_krs1_branch_review_next_required_step": str(
                bsrhs.get("selected_krs1_branch_review_next_required_step", "")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_review_surface_ready": bool(
                bsrhs.get("tcruzi_pde_rescue_review_surface_ready", False)
            ),
            "broad_screen_tcruzi_pde_rescue_review_target_id": str(
                bsrhs.get("tcruzi_pde_rescue_review_target_id")
                or bsrhs.get("selected_rescue_review_target_id", "")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_review_decision": str(
                bsrhs.get("tcruzi_pde_rescue_review_decision", "")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_review_default_lane_reopen_allowed": bool(
                bsrhs.get("tcruzi_pde_rescue_review_default_lane_reopen_allowed", False)
            ),
            "broad_screen_tcruzi_pde_rescue_review_branch_to_rescue_only": bool(
                bsrhs.get("tcruzi_pde_rescue_review_branch_to_rescue_only", False)
            ),
            "broad_screen_tcruzi_pde_rescue_review_promoted_candidate_count": int(
                bsrhs.get("tcruzi_pde_rescue_review_promoted_candidate_count", 0) or 0
            ),
            "broad_screen_tcruzi_pde_rescue_review_under_2p5_candidate_count": int(
                bsrhs.get("tcruzi_pde_rescue_review_under_2p5_candidate_count", 0) or 0
            ),
            "broad_screen_tcruzi_pde_rescue_review_selected_command_kind": str(
                bsrhs.get("tcruzi_pde_rescue_review_selected_command_kind")
                or bsrhs.get("selected_rescue_review_selected_command_kind", "")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_review_selected_threshold_A": float(
                bsrhs.get("tcruzi_pde_rescue_review_selected_threshold_A", 0.0) or 0.0
            ),
            "broad_screen_tcruzi_pde_rescue_review_next_required_step": str(
                bsrhs.get("tcruzi_pde_rescue_review_next_required_step")
                or bsrhs.get("selected_rescue_review_next_required_step", "")
            ).strip(),
            "broad_screen_tcruzi_pde_promoted_top4_review_packet_ready": bool(
                pde_top4_review_packet_ready
            ),
            "broad_screen_tcruzi_pde_promoted_top4_packet_ready_for_operator_review": pde_top4_packet_ready_for_operator_review,
            "broad_screen_tcruzi_pde_promoted_top4_wetlab_final_gate_pass": pde_top4_wetlab_final_gate_pass,
            "broad_screen_tcruzi_pde_promoted_top4_claim_gate_available": pde_top4_claim_gate_available,
            "broad_screen_tcruzi_pde_promoted_top4_claim_ready_for_allatom": pde_top4_claim_ready_for_allatom,
            "broad_screen_tcruzi_pde_promoted_top4_review_packet_target_id": str(
                bsrhs.get("tcruzi_pde_promoted_top4_review_packet_target_id", "")
                or fcss.get("broad_screen_tcruzi_pde_promoted_top4_target_id", "")
                or bstprps.get("target_id", "")
            ).strip(),
            "broad_screen_tcruzi_pde_promoted_top4_review_packet_shard_id": str(
                bsrhs.get("tcruzi_pde_promoted_top4_review_packet_shard_id", "")
                or fcss.get("broad_screen_tcruzi_pde_promoted_top4_shard_id", "")
                or bstprps.get("shard_id", "")
            ).strip(),
            "broad_screen_tcruzi_pde_promoted_top4_review_packet_selected_command_kind": str(
                bsrhs.get("tcruzi_pde_promoted_top4_review_packet_selected_command_kind", "")
                or fcss.get("broad_screen_tcruzi_pde_promoted_top4_selected_command_kind", "")
                or bstprps.get("selected_command_kind", "")
            ).strip(),
            "broad_screen_tcruzi_pde_promoted_top4_review_packet_strict_threshold_A": float(
                bsrhs.get("tcruzi_pde_promoted_top4_review_packet_strict_threshold_A", 0.0)
                or fcss.get("broad_screen_tcruzi_pde_promoted_top4_strict_threshold_A", 0.0)
                or bstprps.get("strict_threshold_A", 0.0)
                or 0.0
            ),
            "broad_screen_tcruzi_pde_promoted_top4_review_packet_promoted_candidate_count": int(
                bsrhs.get("tcruzi_pde_promoted_top4_review_packet_promoted_candidate_count", 0) or 0
            ),
            "broad_screen_tcruzi_pde_promoted_top4_review_packet_under_2p5_candidate_count": int(
                bsrhs.get("tcruzi_pde_promoted_top4_review_packet_under_2p5_candidate_count", 0) or 0
            ),
            "broad_screen_tcruzi_pde_promoted_top4_review_packet_near_candidate_count": int(
                bsrhs.get("tcruzi_pde_promoted_top4_review_packet_near_candidate_count", 0) or 0
            ),
            "broad_screen_tcruzi_pde_promoted_top4_review_packet_best_ligand_id": str(
                bsrhs.get("tcruzi_pde_promoted_top4_review_packet_best_ligand_id", "")
            ).strip(),
            "broad_screen_tcruzi_pde_promoted_top4_review_packet_best_compound_name": str(
                bsrhs.get("tcruzi_pde_promoted_top4_review_packet_best_compound_name", "")
            ).strip(),
            "broad_screen_tcruzi_pde_promoted_top4_review_packet_best_compound_name_human_readable": str(
                bsrhs.get("tcruzi_pde_promoted_top4_review_packet_best_compound_name_human_readable", "")
            ).strip(),
            "broad_screen_tcruzi_pde_promoted_top4_review_packet_best_compound_name_resolution": str(
                bsrhs.get("tcruzi_pde_promoted_top4_review_packet_best_compound_name_resolution", "")
            ).strip(),
            "broad_screen_tcruzi_pde_promoted_top4_review_packet_best_mean_min_distance_A": float(
                bsrhs.get("tcruzi_pde_promoted_top4_review_packet_best_mean_min_distance_A", 0.0) or 0.0
            ),
            "broad_screen_tcruzi_pde_promoted_top4_review_packet_next_required_step": str(
                bsrhs.get("tcruzi_pde_promoted_top4_review_packet_next_required_step", "")
                or fcss.get("broad_screen_tcruzi_pde_promoted_top4_next_required_step", "")
                or bstprps.get("next_required_step", "")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_only_branch_summary_ready": bool(
                pde_rescue_only_branch_summary_ready
            ),
            "broad_screen_tcruzi_pde_rescue_only_branch_review_packet_ready_for_operator_review": pde_branch_review_packet_ready_for_operator_review,
            "broad_screen_tcruzi_pde_rescue_only_branch_review_packet_final_gate_pass": pde_branch_review_packet_final_gate_pass,
            "broad_screen_tcruzi_pde_rescue_only_branch_review_packet_claim_gate_available": pde_branch_review_packet_claim_gate_available,
            "broad_screen_tcruzi_pde_rescue_only_branch_review_packet_claim_ready_for_allatom": pde_branch_review_packet_claim_ready_for_allatom,
            "broad_screen_tcruzi_pde_rescue_only_branch_ready_for_final_wetlab": pde_branch_ready_for_final_wetlab,
            "broad_screen_tcruzi_pde_rescue_only_branch_target_id": str(
                bsrhs.get("tcruzi_pde_rescue_only_branch_target_id", "")
                or fcss.get("broad_screen_tcruzi_pde_rescue_only_branch_target_id", "")
                or bstcrbs.get("target_id", "")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_only_branch_shard_id": str(
                bsrhs.get("tcruzi_pde_rescue_only_branch_shard_id", "")
                or fcss.get("broad_screen_tcruzi_pde_rescue_only_branch_shard_id", "")
                or bstcrbs.get("shard_id", "")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_only_branch_label": str(
                bsrhs.get("tcruzi_pde_rescue_only_branch_label", "")
                or fcss.get("broad_screen_tcruzi_pde_rescue_only_branch_label", "")
                or bstcrbs.get("branch_label", "")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_only_branch_state": str(
                bsrhs.get("tcruzi_pde_rescue_only_branch_state", "")
                or fcss.get("broad_screen_tcruzi_pde_rescue_only_branch_state", "")
                or bstcrbs.get("branch_state", "")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_only_branch_default_lane_reopen_allowed": bool(
                bsrhs.get("tcruzi_pde_rescue_only_branch_default_lane_reopen_allowed", False)
            ),
            "broad_screen_tcruzi_pde_rescue_only_branch_branch_to_rescue_only": bool(
                bsrhs.get("tcruzi_pde_rescue_only_branch_branch_to_rescue_only", False)
            ),
            "broad_screen_tcruzi_pde_rescue_only_branch_selected_command_kind": str(
                bsrhs.get("tcruzi_pde_rescue_only_branch_selected_command_kind", "")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_only_branch_selected_threshold_A": float(
                bsrhs.get("tcruzi_pde_rescue_only_branch_selected_threshold_A", 0.0) or 0.0
            ),
            "broad_screen_tcruzi_pde_rescue_only_branch_promoted_candidate_count": int(
                bsrhs.get("tcruzi_pde_rescue_only_branch_promoted_candidate_count", 0) or 0
            ),
            "broad_screen_tcruzi_pde_rescue_only_branch_under_2p5_candidate_count": int(
                bsrhs.get("tcruzi_pde_rescue_only_branch_under_2p5_candidate_count", 0) or 0
            ),
            "broad_screen_tcruzi_pde_rescue_only_branch_next_required_step": str(
                bsrhs.get("tcruzi_pde_rescue_only_branch_next_required_step", "")
            ).strip(),
            "selected_rescue_review_target_id": str(
                bsrhs.get("selected_rescue_review_target_id", "")
            ).strip(),
            "selected_rescue_review_surface_label": str(
                bsrhs.get("selected_rescue_review_surface_label", "")
            ).strip(),
            "selected_rescue_review_selected_command_kind": str(
                bsrhs.get("selected_rescue_review_selected_command_kind", "")
            ).strip(),
            "selected_rescue_review_best_compound_name": str(
                bsrhs.get("selected_rescue_review_best_compound_name", "")
            ).strip(),
            "selected_rescue_review_best_compound_name_human_readable": str(
                bsrhs.get("selected_rescue_review_best_compound_name_human_readable", "")
            ).strip(),
            "selected_rescue_review_best_compound_name_resolution": str(
                bsrhs.get("selected_rescue_review_best_compound_name_resolution", "")
            ).strip(),
            "selected_rescue_review_strict_threshold_A": float(
                bsrhs.get("selected_rescue_review_strict_threshold_A", 0.0) or 0.0
            ),
            "selected_rescue_review_near_threshold_A": float(
                bsrhs.get("selected_rescue_review_near_threshold_A", 0.0) or 0.0
            ),
            "selected_rescue_review_promoted_candidate_count": int(
                bsrhs.get("selected_rescue_review_promoted_candidate_count", 0) or 0
            ),
            "selected_rescue_review_under_2p5_candidate_count": int(
                bsrhs.get("selected_rescue_review_under_2p5_candidate_count", 0) or 0
            ),
            "selected_rescue_review_next_required_step": str(
                bsrhs.get("selected_rescue_review_next_required_step", "")
            ).strip(),
            "selected_rescue_branch_target_id": str(
                bsrhs.get("selected_rescue_branch_target_id", "")
            ).strip(),
            "selected_rescue_branch_surface_label": str(
                bsrhs.get("selected_rescue_branch_surface_label", "")
            ).strip(),
            "selected_rescue_branch_selected_command_kind": str(
                bsrhs.get("selected_rescue_branch_selected_command_kind", "")
            ).strip(),
            "selected_rescue_branch_best_compound_name": str(
                bsrhs.get("selected_rescue_branch_best_compound_name", "")
            ).strip(),
            "selected_rescue_branch_best_compound_name_human_readable": str(
                bsrhs.get("selected_rescue_branch_best_compound_name_human_readable", "")
            ).strip(),
            "selected_rescue_branch_best_compound_name_resolution": str(
                bsrhs.get("selected_rescue_branch_best_compound_name_resolution", "")
            ).strip(),
            "selected_rescue_branch_selected_threshold_A": float(
                bsrhs.get("selected_rescue_branch_selected_threshold_A", 0.0) or 0.0
            ),
            "selected_rescue_branch_promoted_candidate_count": int(
                bsrhs.get("selected_rescue_branch_promoted_candidate_count", 0) or 0
            ),
            "selected_rescue_branch_under_2p5_candidate_count": int(
                bsrhs.get("selected_rescue_branch_under_2p5_candidate_count", 0) or 0
            ),
            "selected_rescue_branch_ready_for_final_wetlab": pde_branch_ready_for_final_wetlab,
            "broad_screen_tcruzi_pde_rescue_operator_packet_ready_for_operator_review": pde_operator_packet_ready_for_operator_review,
            "broad_screen_tcruzi_pde_rescue_operator_packet_final_gate_pass": pde_operator_packet_final_gate_pass,
            "broad_screen_tcruzi_pde_rescue_operator_packet_claim_gate_available": pde_operator_packet_claim_gate_available,
            "broad_screen_tcruzi_pde_rescue_operator_packet_claim_ready_for_allatom": pde_operator_packet_claim_ready_for_allatom,
            "selected_rescue_branch_operator_packet_ready": bool(
                pde_operator_packet_ready_for_operator_review
            ),
            "selected_rescue_branch_operator_packet_ready_for_operator_review": pde_operator_packet_ready_for_operator_review,
            "selected_rescue_branch_operator_packet_final_gate_pass": pde_operator_packet_final_gate_pass,
            "selected_rescue_branch_operator_packet_claim_gate_available": pde_operator_packet_claim_gate_available,
            "selected_rescue_branch_operator_packet_claim_ready_for_allatom": pde_operator_packet_claim_ready_for_allatom,
            "selected_rescue_branch_operator_packet_scope": str(
                pde_operator_packet_scope
            ).strip(),
            "tcruzi_pde_rescue_only_branch_summary_best_compound_name": str(
                bsrhs.get("tcruzi_pde_rescue_only_branch_summary_best_compound_name", "")
            ).strip(),
            "tcruzi_pde_rescue_only_branch_summary_best_compound_name_human_readable": str(
                bsrhs.get("tcruzi_pde_rescue_only_branch_summary_best_compound_name_human_readable", "")
            ).strip(),
            "tcruzi_pde_rescue_only_branch_summary_best_compound_name_resolution": str(
                bsrhs.get("tcruzi_pde_rescue_only_branch_summary_best_compound_name_resolution", "")
            ).strip(),
            "broad_screen_rescue_only_branch_templates_ready": bool(
                bsrhs.get("rescue_only_branch_templates_ready", False)
            ),
            "broad_screen_rescue_only_branch_template_target_count": int(
                bsrhs.get("rescue_only_branch_template_target_count", 0) or 0
            ),
            "broad_screen_rescue_only_branch_focus_target_id": str(
                bsrhs.get("rescue_only_branch_focus_target_id", "")
            ).strip(),
            "broad_screen_rescue_only_branch_focus_template_label": str(
                bsrhs.get("rescue_only_branch_focus_template_label", "")
            ).strip(),
            "broad_screen_rescue_only_branch_focus_surface_label": str(
                bsrhs.get("rescue_only_branch_focus_surface_label", "")
            ).strip(),
            "broad_screen_rescue_only_branch_focus_selected_command_kind": str(
                bsrhs.get("rescue_only_branch_focus_selected_command_kind", "")
            ).strip(),
            "broad_screen_rescue_only_branch_focus_selected_threshold_A": float(
                bsrhs.get("rescue_only_branch_focus_selected_threshold_A", 0.0) or 0.0
            ),
            "selected_rescue_branch_next_required_step": str(
                bsrhs.get("selected_rescue_branch_next_required_step", "")
            ).strip(),
            "broad_screen_allatom_family_ready": bool(
                bsrhs.get("allatom_family_ready", False)
            ),
            "broad_screen_allatom_family_target_count": int(
                bsrhs.get("allatom_family_target_count", 0) or 0
            ),
            "broad_screen_allatom_family_surface_count": int(
                bsrhs.get("allatom_family_surface_count", 0) or 0
            ),
            "broad_screen_allatom_family_focus_target_id": str(
                bsrhs.get("allatom_family_focus_target_id", "")
            ).strip(),
            "broad_screen_allatom_family_focus_surface_label": str(
                bsrhs.get("allatom_family_focus_surface_label", "")
            ).strip(),
            "selected_allatom_target_id": selected_allatom_target_id,
            "selected_allatom_surface_label": selected_allatom_surface_label,
            "selected_allatom_selected_command_kind": str(
                bsrhs.get("selected_allatom_selected_command_kind", "")
            ).strip(),
            "selected_allatom_selected_threshold_A": float(
                bsrhs.get("selected_allatom_selected_threshold_A", 0.0) or 0.0
            ),
            "selected_allatom_packet_scope": str(
                bsrhs.get("selected_allatom_packet_scope", "")
            ).strip(),
            "selected_allatom_focus_available": selected_allatom_focus_available,
            "selected_allatom_operator_review_ready_reported": selected_allatom_operator_review_reported,
            "selected_allatom_operator_review_ready": selected_allatom_operator_review_ready,
            "selected_allatom_wetlab_gate_reported": selected_allatom_wetlab_gate_reported,
            "selected_allatom_wetlab_gate_pass": selected_allatom_wetlab_gate_pass,
            "selected_allatom_final_gate_reported": selected_allatom_final_gate_reported,
            "selected_allatom_final_gate_pass": selected_allatom_final_gate_pass,
            "selected_allatom_final_wetlab_ready": selected_allatom_final_gate_pass,
            "selected_allatom_claim_gate_available_reported": selected_allatom_claim_gate_reported,
            "selected_allatom_claim_gate_available": selected_allatom_claim_gate_available,
            "selected_allatom_claim_ready_for_allatom_reported": selected_allatom_claim_ready_reported,
            "selected_allatom_claim_ready_for_allatom": selected_allatom_claim_ready_for_allatom,
            "selected_allatom_readiness_semantics": selected_allatom_readiness_semantics,
            "selected_allatom_raw_claim_requirement_mode": str(
                selected_allatom_canonical_view.get("raw_claim_requirement_mode", "")
            ).strip(),
            "selected_allatom_raw_claim_requirement_provenance": str(
                selected_allatom_canonical_view.get("raw_claim_requirement_provenance", "")
            ).strip(),
            "selected_allatom_raw_claim_required_for_final_wetlab": bool(
                selected_allatom_canonical_view.get("raw_claim_required_for_final_wetlab", False)
            ),
            "selected_allatom_raw_claim_required_for_commercial_readiness": bool(
                selected_allatom_canonical_view.get("raw_claim_required_for_commercial_readiness", False)
            ),
            "selected_allatom_raw_claim_requirement_reason": str(
                selected_allatom_canonical_view.get("raw_claim_requirement_reason", "")
            ).strip(),
            "selected_allatom_effective_actionability_status": str(
                selected_allatom_canonical_view.get("effective_actionability_status", "")
            ).strip(),
            "selected_allatom_effective_actionability_claim_requirement_mode": str(
                selected_allatom_canonical_view.get("effective_actionability_claim_requirement_mode", "")
            ).strip(),
            "selected_allatom_effective_actionability_claim_requirement_status": str(
                selected_allatom_canonical_view.get("effective_actionability_claim_requirement_status", "")
            ).strip(),
            "selected_allatom_effective_actionability_claim_requirement_reason": str(
                selected_allatom_canonical_view.get("effective_actionability_claim_requirement_reason", "")
            ).strip(),
            "selected_allatom_effective_actionability_next_expensive_lane": str(
                selected_allatom_canonical_view.get("effective_actionability_next_expensive_lane", "")
            ).strip(),
            "selected_allatom_effective_actionability_next_expensive_lane_reason": str(
                selected_allatom_canonical_view.get("effective_actionability_next_expensive_lane_reason", "")
            ).strip(),
            "selected_allatom_effective_actionability_required_calculations": list(
                selected_allatom_canonical_view.get("effective_actionability_required_calculations", [])
            ),
            "selected_allatom_effective_actionability_required_calculations_text": str(
                selected_allatom_canonical_view.get("effective_actionability_required_calculations_text", "")
            ).strip(),
            "selected_allatom_effective_actionability_action_list": list(
                selected_allatom_canonical_view.get("effective_actionability_action_list", [])
            ),
            "selected_allatom_effective_actionability_action_list_text": str(
                selected_allatom_canonical_view.get("effective_actionability_action_list_text", "")
            ).strip(),
            "selected_allatom_actionability_required_calculations": list(
                selected_allatom_canonical_view.get("effective_actionability_required_calculations", [])
            ),
            "selected_allatom_actionability_required_calculations_text": str(
                selected_allatom_canonical_view.get("effective_actionability_required_calculations_text", "")
            ).strip(),
            "selected_allatom_actionability_action_list": list(
                selected_allatom_canonical_view.get("effective_actionability_action_list", [])
            ),
            "selected_allatom_actionability_action_list_text": str(
                selected_allatom_canonical_view.get("effective_actionability_action_list_text", "")
            ).strip(),
            "selected_allatom_effective_blocking_order": str(
                selected_allatom_canonical_view.get("effective_blocking_order", "")
            ).strip(),
            "selected_allatom_effective_primary_blocking_domain": str(
                selected_allatom_canonical_view.get("effective_primary_blocking_domain", "")
            ).strip(),
            "selected_allatom_action_recipe_codes": list(
                selected_allatom_canonical_view.get("action_recipe_codes", [])
            ),
            "selected_allatom_action_recipe_rows": list(
                selected_allatom_canonical_view.get("action_recipe_rows", [])
            ),
            "selected_allatom_action_recipe_rollup_text": str(
                selected_allatom_canonical_view.get("action_recipe_rollup_text", "")
            ).strip(),
            **selected_allatom_visual_fields,
            "selected_allatom_focus_label": selected_allatom_rollups["focus_label"],
            "selected_allatom_gate_rollup": selected_allatom_rollups["gate_rollup"],
            "selected_allatom_gate_detail_rollup": selected_allatom_rollups["gate_detail_rollup"],
            "selected_allatom_commercial_rollup": selected_allatom_rollups["commercial_rollup"],
            "selected_allatom_commercial_detail_rollup": selected_allatom_rollups["commercial_detail_rollup"],
            "selected_allatom_commercial_summary": selected_allatom_rollups["commercial_summary"],
            "selected_allatom_commercial_rollup_v2": selected_allatom_rollups["commercial_rollup_v2"],
            "selected_allatom_commercial_detail_rollup_v2": selected_allatom_rollups["commercial_detail_rollup_v2"],
            "selected_allatom_commercial_summary_v2": selected_allatom_rollups["commercial_summary_v2"],
            "selected_allatom_translation_rollup": selected_allatom_rollups["translation_rollup"],
            "selected_allatom_translation_summary": selected_allatom_rollups["translation_summary"],
            "selected_allatom_claim_actionability_split_summary": " | ".join(
                part
                for part in (
                    f"raw claim {str(selected_allatom_canonical_view.get('raw_claim_requirement_mode', '')).strip()}"
                    if str(selected_allatom_canonical_view.get("raw_claim_requirement_mode", "")).strip()
                    else "",
                    "required for final wetlab"
                    if bool(
                        selected_allatom_canonical_view.get(
                            "raw_claim_required_for_final_wetlab",
                            False,
                        )
                    )
                    else "",
                    "required for commercial readiness"
                    if bool(
                        selected_allatom_canonical_view.get(
                            "raw_claim_required_for_commercial_readiness",
                            False,
                        )
                    )
                    else "",
                    f"effective actionability {str(selected_allatom_canonical_view.get('effective_actionability_status', '')).strip()}"
                    if str(selected_allatom_canonical_view.get("effective_actionability_status", "")).strip()
                    else "",
                    f"effective claim {str(selected_allatom_canonical_view.get('effective_actionability_claim_requirement_mode', '')).strip()}:{str(selected_allatom_canonical_view.get('effective_actionability_claim_requirement_status', '')).strip()}"
                    if str(
                        selected_allatom_canonical_view.get(
                            "effective_actionability_claim_requirement_mode",
                            "",
                        )
                    ).strip()
                    else "",
                    f"blocking order {str(selected_allatom_canonical_view.get('effective_blocking_order', '')).strip()}"
                    if str(selected_allatom_canonical_view.get("effective_blocking_order", "")).strip()
                    else "",
                    f"domain {str(selected_allatom_canonical_view.get('effective_primary_blocking_domain', '')).strip()}"
                    if str(
                        selected_allatom_canonical_view.get(
                            "effective_primary_blocking_domain",
                            "",
                        )
                    ).strip()
                    else "",
                    f"recipe {str(selected_allatom_canonical_view.get('action_recipe_rollup_text', '')).strip()}"
                    if str(selected_allatom_canonical_view.get("action_recipe_rollup_text", "")).strip()
                    else "",
                )
                if part
            ),
            "selected_allatom_human_summary": selected_allatom_rollups["human_summary"],
            "selected_allatom_best_compound_name": selected_allatom_best_compound_name,
            "selected_allatom_best_compound_name_human_readable": selected_allatom_best_compound_name_human_readable,
            "selected_allatom_best_compound_name_resolution": selected_allatom_best_compound_name_resolution,
            "selected_allatom_best_mean_min_distance_A": selected_allatom_best_mean_min_distance_A,
            "selected_allatom_best_mean_min_distance_A_source": selected_allatom_best_mean_min_distance_A_source,
            "selected_allatom_promoted_candidate_count": selected_allatom_promoted_candidate_count,
            "selected_allatom_under_2p5_candidate_count": selected_allatom_under_2p5_candidate_count,
            "selected_allatom_near_candidate_count": selected_allatom_near_candidate_count,
            "selected_allatom_commercial_schema_version": selected_allatom_commercial_schema_version,
            "selected_allatom_commercial_schema_version_v2": selected_allatom_commercial_schema_version_v2,
            "selected_allatom_commercial_provenance_mode_v2": str(
                selected_allatom_canonical_view.get(
                    "commercial_provenance_mode_v2", selected_allatom_commercial_provenance_mode_v2
                )
            ).strip(),
            "selected_allatom_translation_provenance_mode": str(
                selected_allatom_canonical_view.get(
                    "translation_provenance_mode", selected_allatom_translation_provenance_mode
                )
            ).strip(),
            "selected_allatom_hybrid_policy": str(
                selected_allatom_canonical_view.get(
                    "hybrid_policy",
                    "canonical_scores_source_only__translation_shortlist_labeled_fallback",
                )
            ).strip(),
            "selected_allatom_commercial_reported": selected_allatom_commercial_reported,
            "selected_allatom_commercial_hard_gate_reported": selected_allatom_commercial_hard_gate_reported,
            "selected_allatom_commercial_hard_gate_pass_v1": selected_allatom_commercial_hard_gate_pass_v1,
            "selected_allatom_commercial_overall_score_v1": selected_allatom_commercial_overall_score_v1,
            "selected_allatom_commercial_risk_bucket_v1": selected_allatom_commercial_risk_bucket_v1,
            "selected_allatom_commercial_decision_class_v1": selected_allatom_commercial_decision_class_v1,
            "selected_allatom_commercial_primary_upgrade_actions_v1": list(
                selected_allatom_commercial_primary_upgrade_actions_v1
            ),
            "selected_allatom_commercial_hard_gate_pass_v2": selected_allatom_commercial_hard_gate_pass_v2,
            "selected_allatom_commercial_soft_score_v2": selected_allatom_commercial_soft_score_v2,
            "selected_allatom_commercial_confidence_score_v2": selected_allatom_commercial_confidence_score_v2,
            "selected_allatom_commercial_overall_score_v2": selected_allatom_commercial_overall_score_v2,
            "selected_allatom_commercial_risk_bucket_v2": selected_allatom_commercial_risk_bucket_v2,
            "selected_allatom_commercial_decision_class_v2": selected_allatom_commercial_decision_class_v2,
            "selected_allatom_commercial_primary_upgrade_actions_v2": list(
                selected_allatom_commercial_primary_upgrade_actions_v2
            ),
            "selected_allatom_commercial_human_summary_v2": _text(
                selected_allatom_commercial_human_summary_v2,
                selected_allatom_rollups["commercial_summary_v2"],
            ),
            "selected_allatom_translation_gate_version": selected_allatom_translation_gate_version,
            "selected_allatom_translation_gate_focus_status": selected_allatom_translation_gate_focus_status,
            "selected_allatom_translation_gate_focus_score": selected_allatom_translation_gate_focus_score,
            "selected_allatom_translation_gate_focus_reason": selected_allatom_translation_gate_focus_reason,
            "selected_allatom_focus_shortlist_tier": selected_allatom_focus_shortlist_tier,
            "selected_allatom_recommended_next_expensive_lane": selected_allatom_recommended_next_expensive_lane,
            "selected_allatom_recommended_next_expensive_lane_reason": selected_allatom_recommended_next_expensive_lane_reason,
            "selected_allatom_next_required_step": selected_allatom_next_required_step,
            "broad_screen_lbdhodh_retry_lane_ready": bool(
                str(bsldrs.get("status", "")).strip() == "wetlab_lbdhodh_exploratory_retry_lane_ready"
            ),
            "broad_screen_lbdhodh_retry_ready_for_manual_retry": bool(
                bsldrs.get("ready_for_manual_retry", False)
            ),
            "broad_screen_lbdhodh_retry_target_id": str(bsldrs.get("target_id", "")).strip(),
            "broad_screen_lbdhodh_retry_shard_id": str(bsldrs.get("shard_id", "")).strip(),
            "broad_screen_lbdhodh_retry_selected_command_kind": str(
                bsldrs.get("selected_command_kind", "")
            ).strip(),
            "broad_screen_lbdhodh_retry_lane_label": str(bsldrs.get("lane_label", "")).strip(),
            "broad_screen_dengue_stage6_tuning_surface_ready": bool(
                str(bdgts.get("status", "")).strip() == "wetlab_dengue_ns2b_ns3_protease_stage6_tuning_surface_ready"
            ),
            "broad_screen_dengue_stage6_recommended_threshold_A": float(
                bdgts.get("recommended_observed_threshold_A", 0.0) or 0.0
            ),
            "broad_screen_dengue_stage6_immediately_runnable_command_kind": str(
                bdgts.get("immediately_runnable_command_kind", "")
            ).strip(),
            "broad_screen_dengue_stage6_retry_lane_ready": bool(
                str(bdgrs.get("status", "")).strip() == "wetlab_dengue_ns2b_ns3_protease_exploratory_retry_lane_ready"
            ),
            "broad_screen_dengue_stage6_retry_ready_for_manual_retry": bool(
                bdgrs.get("ready_for_manual_retry", False)
            ),
            "broad_screen_dengue_stage6_retry_source_priority": str(
                dengue_stage6_summary.get("source_priority", "")
            ).strip(),
            "broad_screen_dengue_stage6_retry_target_id": str(
                dengue_stage6_summary.get("target_id", bdgrs.get("target_id", bdgts.get("target_id", "")))
            ).strip(),
            "broad_screen_dengue_stage6_retry_shard_id": str(
                dengue_stage6_summary.get("shard_id", bdgrs.get("shard_id", ""))
            ).strip(),
            "broad_screen_dengue_stage6_retry_selected_command_kind": str(
                dengue_stage6_summary.get(
                    "selected_command_kind", bdgrs.get("selected_command_kind", bdgts.get("immediately_runnable_command_kind", ""))
                )
            ).strip(),
            "broad_screen_dengue_stage6_retry_lane_label": str(
                dengue_stage6_summary.get("lane_label", bdgrs.get("lane_label", "dengue_stage6_tuned_retry"))
            ).strip(),
            "broad_screen_dengue_stage6_retry_next_required_step": str(
                dengue_stage6_summary.get("next_required_step", bdgrs.get("next_required_step", bdgts.get("next_required_step", "")))
            ).strip(),
            "broad_screen_stk17b_manual_retry_lane_ready": bool(
                str(bssmls.get("status", "")).strip() == "wetlab_stk17b_manual_retry_lane_ready"
            ),
            "broad_screen_stk17b_manual_retry_ready_for_manual_retry": bool(
                bssmls.get("ready_for_manual_retry", False)
            ),
            "broad_screen_stk17b_manual_retry_target_id": str(bssmls.get("target_id", "")).strip(),
            "broad_screen_stk17b_manual_retry_shard_id": str(bssmls.get("shard_id", "")).strip(),
            "broad_screen_stk17b_manual_retry_selected_command_kind": str(
                bssmls.get("selected_command_kind", "")
            ).strip(),
            "broad_screen_stk17b_exploratory_followup_lane_ready": bool(
                str(bssefls.get("status", "")).strip() == "wetlab_stk17b_exploratory_followup_lane_ready"
            ),
            "broad_screen_stk17b_exploratory_followup_ready_for_manual_retry": bool(
                bssefls.get("ready_for_manual_retry", False)
            ),
            "broad_screen_stk17b_exploratory_followup_target_id": str(bssefls.get("target_id", "")).strip(),
            "broad_screen_stk17b_exploratory_followup_shard_id": _lane_shard_display(bssefls),
            "broad_screen_stk17b_exploratory_followup_selected_command_kind": str(
                bssefls.get("selected_command_kind", "")
            ).strip(),
            "broad_screen_stk17b_exploratory_followup_lane_label": str(
                bssefls.get("followup_lane_label", bssefls.get("lane_label", ""))
            ).strip(),
            "broad_screen_stk17b_exploratory_followup_freeze_state": str(
                bssefls.get("hard_freeze_state", bssefls.get("freeze_state", ""))
            ).strip(),
            "broad_screen_stk17b_exploratory_followup_freeze_note": str(
                bssefls.get("freeze_note", "")
            ).strip(),
            "broad_screen_stk17b_exploratory_followup_followup_shard_ids": str(
                bssefls.get("followup_shard_ids", "")
            ).strip(),
            "broad_screen_stk17b_followup_review_surface_ready": bool(
                str(bssfrs.get("status", "")).strip() == "wetlab_stk17b_followup_review_surface_ready"
            ),
            "broad_screen_stk17b_followup_review_decision": str(bssfrs.get("decision", "")).strip(),
            "broad_screen_stk17b_followup_review_decision_rationale": str(
                bssfrs.get("decision_rationale", "")
            ).strip(),
            "broad_screen_stk17b_followup_review_default_lane_reopen_allowed": bool(
                bssfrs.get("default_lane_reopen_allowed", False)
            ),
            "broad_screen_stk17b_followup_review_branch_to_gate45_only": bool(
                bssfrs.get("branch_to_gate45_only", False)
            ),
            "broad_screen_stk17b_followup_review_next_required_step": str(
                bssfrs.get("next_required_step", "")
            ).strip(),
            "broad_screen_stk17b_exploratory_retry_lane_ready": bool(
                str(bsserls.get("status", "")).strip() == "wetlab_stk17b_exploratory_retry_lane_ready"
            ),
            "broad_screen_stk17b_exploratory_retry_ready_for_manual_retry": bool(
                bsserls.get("ready_for_manual_retry", False)
            ),
            "broad_screen_stk17b_exploratory_retry_target_id": str(bsserls.get("target_id", "")).strip(),
            "broad_screen_stk17b_exploratory_retry_shard_id": str(bsserls.get("shard_id", "")).strip(),
            "broad_screen_stk17b_exploratory_retry_selected_command_kind": str(
                bsserls.get("selected_command_kind", "")
            ).strip(),
            "broad_screen_stk17b_exploratory_retry_selected_threshold_A": float(
                bsserls.get("selected_threshold_A", 0.0) or 0.0
            ),
            "broad_screen_stk17b_exploratory_freeze_state": str(exploratory_freeze.get("state", "")).strip(),
            "broad_screen_stk17b_exploratory_freeze_target_id": str(
                exploratory_freeze.get("target_id", "")
            ).strip(),
            "broad_screen_stk17b_exploratory_freeze_hold_streak": int(
                exploratory_freeze.get("hold_streak", 0) or 0
            ),
            "broad_screen_stk17b_exploratory_freeze_hold_limit": int(
                exploratory_freeze.get("hold_limit", 0) or 0
            ),
            "broad_screen_stk17b_exploratory_freeze_note": str(
                exploratory_freeze.get("freeze_note", "")
            ).strip(),
            "broad_screen_stk17b_exploratory_freeze_next_required_step": str(
                exploratory_freeze.get("next_required_step", "")
            ).strip(),
            "broad_screen_plpro_manual_retry_lane_ready": bool(
                str(bspmls.get("status", "")).strip() == "wetlab_plpro_manual_retry_lane_ready"
            ),
            "broad_screen_plpro_manual_retry_ready_for_manual_retry": bool(
                bspmls.get("ready_for_manual_retry", False)
            ),
            "broad_screen_plpro_manual_retry_target_id": str(bspmls.get("target_id", "")).strip(),
            "broad_screen_plpro_manual_retry_shard_id": str(bspmls.get("shard_id", "")).strip(),
            "broad_screen_plpro_manual_retry_selected_command_kind": str(
                bspmls.get("selected_command_kind", "")
            ).strip(),
            "broad_screen_mapping_fix_retry_support_ready": bool(
                str(bsmfrs.get("status", "")).strip() == "wetlab_mapping_fix_retry_support_ready"
            ),
            "broad_screen_mapping_fix_retry_ready_target_count": int(
                bsmfrs.get("ready_target_count", 0) or 0
            ),
            "broad_screen_mapping_fix_retry_ready_targets": str(
                bsmfrs.get("ready_targets", "")
            ).strip(),
            "broad_screen_stage1_mapping_fix_lanes_ready": bool(
                str(bssmfl.get("status", "")).strip() == "wetlab_stage1_mapping_fix_lanes_ready"
            ),
            "broad_screen_stage1_mapping_fix_ready_target_count": int(
                bssmfl.get("ready_target_count", 0) or 0
            ),
            "broad_screen_stage1_mapping_fix_ready_targets": str(
                bssmfl.get("ready_targets", "")
            ).strip(),
            "broad_screen_mapping_fix_retry_policy_templates_ready": bool(
                str(bsmfrpts.get("status", "")).strip() == "wetlab_mapping_fix_retry_policy_templates_ready"
            ),
            "broad_screen_mapping_fix_retry_template_target_count": int(
                bsmfrpts.get("template_target_count", 0) or 0
            ),
            "broad_screen_mapping_fix_retry_ready_target_count": int(
                bsmfrpts.get("ready_target_count", 0) or 0
            ),
            "broad_screen_mapping_fix_retry_focus_target_id": str(
                bsmfrpts.get("focus_target_id", "")
            ).strip(),
            "broad_screen_mapping_fix_retry_focus_template_label": str(
                bsmfrpts.get("focus_template_label", "")
            ).strip(),
            "broad_screen_mapping_fix_retry_focus_selected_command_kind": str(
                bsmfrpts.get("focus_selected_command_kind", "")
            ).strip(),
            "broad_screen_mapping_fix_retry_next_required_step": str(
                bsmfrpts.get("next_required_step", "")
            ).strip(),
            "broad_screen_hard_target_rescue_lane_ready": bool(
                str(bshrls.get("status", "")).strip() == "wetlab_hard_target_rescue_lane_ready"
            ),
            "broad_screen_hard_target_rescue_lane_target_id": str(bshrls.get("target_id", "")).strip(),
            "broad_screen_hard_target_rescue_lane_shard_id": str(bshrls.get("shard_id", "")).strip(),
            "broad_screen_hard_target_rescue_lane_stage1_ok": bool(bshrls.get("stage1_ok", False)),
            "broad_screen_hard_target_rescue_lane_stage6_fail": bool(bshrls.get("stage6_fail", False)),
            "broad_screen_hard_target_rescue_lane_auto_hold_streak": int(bshrls.get("auto_hold_streak", 0) or 0),
            "broad_screen_hard_target_rescue_lane_selected_command_kind": str(
                bshrls.get("selected_command_kind", "")
            ).strip(),
            "broad_screen_hard_target_rescue_lane_lane_label": str(bshrls.get("lane_label", "")).strip(),
            "broad_screen_hard_target_rescue_lane_next_required_step": str(
                bshrls.get("next_required_step", "")
            ).strip(),
            "broad_screen_rescue_anchor_artifacts_ready": bool(
                str(bsresas.get("status", "")).strip() == "wetlab_rescue_anchor_artifacts_ready"
            ),
            "broad_screen_rescue_anchor_target_id": str(bsresas.get("target_id", "")).strip(),
            "broad_screen_rescue_anchor_artifact_count": int(bsresas.get("anchor_artifact_count", 0) or 0),
            "broad_screen_rescue_anchor_rescue_only": bool(bsresas.get("rescue_only", False)),
            "broad_screen_rescue_anchor_native_anchor_artifact": str(
                bsresas.get("native_anchor_artifact", "")
            ).strip(),
            "broad_screen_rescue_anchor_pocket_anchor_artifact": str(
                bsresas.get("pocket_anchor_artifact", "")
            ).strip(),
            "broad_screen_rescue_anchor_next_required_step": str(
                bsresas.get("next_required_step", "")
            ).strip(),
            "broad_screen_rescue_three_bead_candidates_ready": bool(
                str(bsr3bs.get("status", "")).strip() == "wetlab_rescue_three_bead_candidates_ready"
            ),
            "broad_screen_rescue_three_bead_candidate_target_id": str(
                bsr3bs.get("target_id", "")
            ).strip(),
            "broad_screen_rescue_three_bead_candidate_count": int(
                bsr3bs.get("candidate_count", 0) or 0
            ),
            "broad_screen_rescue_three_bead_candidate_top_n": int(bsr3bs.get("top_n", 0) or 0),
            "broad_screen_rescue_three_bead_candidate_selected_command_kind": str(
                bsr3bs.get("selected_command_kind", "")
            ).strip(),
            "broad_screen_rescue_three_bead_candidate_selected_threshold_A": float(
                bsr3bs.get("selected_threshold_A", 0.0) or 0.0
            ),
            "broad_screen_rescue_three_bead_candidate_next_required_step": str(
                bsr3bs.get("next_required_step", "")
            ).strip(),
            "broad_screen_kinase_retry_policy_templates_ready": bool(
                str(bskrts.get("status", "")).strip() == "wetlab_kinase_retry_policy_templates_ready"
            ),
            "broad_screen_kinase_retry_template_target_count": int(
                bskrts.get("template_target_count", 0) or 0
            ),
            "broad_screen_kinase_retry_empirical_validated_target_count": int(
                bskrts.get("empirical_validated_target_count", 0) or 0
            ),
            "broad_screen_kinase_retry_gate45_only_target_count": int(
                bskrts.get("gate45_only_target_count", 0) or 0
            ),
            "broad_screen_kinase_retry_guarded_gate55_candidate_target_count": int(
                bskrts.get("guarded_gate55_candidate_target_count", 0) or 0
            ),
            "broad_screen_kinase_retry_focus_target_id": str(bskrts.get("focus_target_id", "")).strip(),
            "broad_screen_kinase_retry_focus_template_label": str(
                bskrts.get("focus_template_label", "")
            ).strip(),
            "broad_screen_kinase_retry_focus_selected_command_kind": str(
                bskrts.get("focus_selected_command_kind", "")
            ).strip(),
            "broad_screen_kinase_retry_next_required_step": str(
                bskrts.get("next_required_step", "")
            ).strip(),
            "broad_screen_target_retry_policy_templates_ready": bool(
                str(bstrpts.get("status", "")).strip() == "wetlab_target_retry_policy_templates_ready"
            ),
            "broad_screen_target_retry_template_target_count": int(
                bstrpts.get("template_target_count", 0) or 0
            ),
            "broad_screen_target_retry_empirical_validated_target_count": int(
                bstrpts.get("empirical_validated_target_count", 0) or 0
            ),
            "broad_screen_target_retry_non_kinase_template_target_count": int(
                bstrpts.get("non_kinase_template_target_count", 0) or 0
            ),
            "broad_screen_target_retry_non_kinase_empirical_validated_target_count": int(
                bstrpts.get("non_kinase_empirical_validated_target_count", 0) or 0
            ),
            "broad_screen_target_retry_guarded_gate55_candidate_target_count": int(
                bstrpts.get("guarded_gate55_candidate_target_count", 0) or 0
            ),
            "broad_screen_target_retry_guarded_gate51_candidate_target_count": int(
                bstrpts.get("guarded_gate51_candidate_target_count", 0) or 0
            ),
            "broad_screen_target_retry_focus_target_id": str(bstrpts.get("focus_target_id", "")).strip(),
            "broad_screen_target_retry_focus_template_label": str(
                bstrpts.get("focus_template_label", "")
            ).strip(),
            "broad_screen_target_retry_focus_selected_command_kind": str(
                bstrpts.get("focus_selected_command_kind", "")
            ).strip(),
            "broad_screen_target_retry_focus_selected_threshold_A": float(
                bstrpts.get("focus_selected_threshold_A", 0.0) or 0.0
            ),
            "broad_screen_target_retry_next_required_step": str(
                bstrpts.get("next_required_step", "")
            ).strip(),
            "broad_screen_target_retry_policy_templates_artifact": "runs/wetlab_target_retry_policy_templates_current.md",
            "broad_screen_mapping_fix_retry_policy_templates_artifact": "runs/wetlab_mapping_fix_retry_policy_templates_current.md",
            "broad_screen_dpre1_branch_review_surface_artifact": "runs/wetlab_dpre1_branch_review_surface_current.md",
            "broad_screen_hard_target_rescue_lane_artifact": "runs/wetlab_hard_target_rescue_lane_current.md",
            "broad_screen_rescue_anchor_artifacts_artifact": "runs/wetlab_rescue_anchor_artifacts_current.md",
            "broad_screen_rescue_three_bead_candidates_artifact": "runs/wetlab_rescue_three_bead_candidates_current.md",
            "broad_screen_recommended_execution_lane": str(
                bsls.get("recommended_execution_lane", bsqs.get("library_lane", ""))
            ).strip(),
            "broad_screen_library_size": int(
                bsls.get("broad_lane_target_size", 0)
                or bsqs.get("library_size", 0)
                or bsbs.get("library_size", 0)
                or 0
            ),
            "broad_screen_ingested_compound_count": int(
                bscus.get("deduped_compound_count", 0)
                or bseqs.get("ingested_compound_count", 0)
                or 0
            ),
            "broad_screen_coverage_gap_to_target_size": int(
                bscus.get("coverage_gap_to_target_size", 0)
                or bseqs.get("coverage_gap_to_target_size", 0)
                or 0
            ),
            "broad_screen_override_target_count": int(bsrafs.get("override_target_count", 0) or 0),
            "broad_screen_override_row_count": int(bsrafs.get("override_row_count", 0) or 0),
            "broad_screen_full_bulk_ready_target_count": int(bstrs.get("full_bulk_ready_target_count", 0) or 0),
            "broad_screen_partial_actual_target_count": int(bstrs.get("partial_actual_target_count", 0) or 0),
            "broad_screen_stable_target_count": int(
                bssts.get("stable_high_confidence_target_count", 0) or 0
            ) + int(bssts.get("stable_provisional_target_count", 0) or 0),
            "broad_screen_antitarget_ready_now_row_count": int(bsats.get("ready_now_row_count", 0) or 0),
            "broad_screen_antitarget_running_row_count": int(bsaeqs.get("running_row_count", 0) or 0),
            "broad_screen_antitarget_first_actionable_primary_target_id": str(
                bsaeqs.get("first_actionable_primary_target_id", "")
            ).strip(),
            "broad_screen_antitarget_first_actionable_anti_target_id": str(
                bsaeqs.get("first_actionable_anti_target_id", "")
            ).strip(),
            "broad_screen_next_target_id": str(bsnxs.get("next_target_id", "")).strip(),
            "broad_screen_target_count": int(bsqs.get("target_count", 0) or 0),
            "broad_screen_shard_count_per_target": int(bsqs.get("shard_count_per_target", 0) or 0),
            "broad_screen_total_queue_rows": int(bsqs.get("total_queue_rows", 0) or 0),
            "broad_screen_execution_ready_now_row_count": int(bseqs.get("ready_now_row_count", 0) or 0),
            "broad_screen_execution_running_row_count": int(bseqs.get("running_row_count", 0) or 0),
            "broad_screen_execution_resolved_row_count": int(bseqs.get("resolved_row_count", 0) or 0),
            "broad_screen_first_actionable_target_id": str(bseqs.get("first_actionable_target_id", "")).strip(),
            "broad_screen_first_actionable_shard_id": str(bseqs.get("first_actionable_shard_id", "")).strip(),
            "broad_screen_first_actionable_queue_status": str(bseqs.get("first_actionable_queue_status", "")).strip(),
            "priority3_transition_artifact_ready_count": sum(
                1
                for ready in (
                    str(mps.get("status", "")).strip() == "sarscov2_mpro_run_status_ready",
                    str(crrs.get("status", "")).strip() == "caix_result_review_ready",
                    str(trrs.get("status", "")).strip() == "tcruzi_pde_result_review_ready",
                )
                if ready
            ),
            "priority3_ready_now_target_count": int(pqs.get("ready_now_target_count", 0) or 0),
            "priority3_running_target_count": int(pqs.get("running_target_count", 0) or 0),
            "priority3_resolved_target_count": int(pqs.get("resolved_target_count", 0) or 0),
            "next3_ready_now_target_count": int(nxqs.get("ready_now_target_count", 0) or 0),
            "next3_running_target_count": int(nxqs.get("running_target_count", 0) or 0),
            "next3_resolved_target_count": int(nxqs.get("resolved_target_count", 0) or 0),
            "final2_ready_now_target_count": int(f2qs.get("ready_now_target_count", 0) or 0),
            "final2_running_target_count": int(f2qs.get("running_target_count", 0) or 0),
            "final2_resolved_target_count": int(f2qs.get("resolved_target_count", 0) or 0),
            "wave2_ready_now_target_count": int(w2qs.get("ready_now_target_count", 0) or 0),
            "wave2_running_target_count": int(w2qs.get("running_target_count", 0) or 0),
            "wave2_resolved_target_count": int(w2qs.get("resolved_target_count", 0) or 0),
            "master_ready_now_target_count": int(mqs2.get("ready_now_target_count", 0) or 0),
            "master_blocked_on_previous_review_count": int(mqs2.get("blocked_on_previous_review_count", 0) or 0),
            "master_blocked_on_target_content_count": int(mqs2.get("blocked_on_target_content_count", 0) or 0),
            "master_first_actionable_target": str(mqs2.get("first_actionable_target", "")).strip(),
            "master_first_actionable_chain": str(mqs2.get("first_actionable_chain", "")).strip(),
            "campaign_terminal_state": str(mtrs.get("campaign_terminal_state", "")).strip(),
            "ready_to_send_track_count": int(
                mtrs.get("ready_to_send_track_count", 0)
                or oebs.get("ready_to_send_target_count", 0)
                or oebs.get("ready_to_send_count", 0)
                or 0
            ),
            "outbound_first_priority_target": str(
                oebs.get("first_priority_target", "")
                or oebs.get("top_priority_lead_targets", "")
                or oebs.get("top_priority_track_id", "")
            ).strip(),
            "outbound_follow_on_target_count": int(
                oebs.get("follow_on_target_count", 0)
                or max(int(oebs.get("priority_track_count", 0) or 0) - int(oebs.get("ready_to_send_count", 0) or 0), 0)
            ),
            "final_campaign_top_outbound_targets": str(
                fcss.get("top_outbound_targets", "")
                or oebs.get("top_priority_lead_targets", "")
            ).strip(),
            "first_dispatch_track_id": str(psrs.get("first_dispatch_track_id", "")).strip(),
            "first_dispatch_lead_targets": str(psrs.get("first_dispatch_lead_targets", "")).strip(),
            "overall_data_quality_band": str(dqas.get("overall_data_quality_band", "")).strip(),
            "partner_outreach_readiness": str(dqas.get("partner_outreach_readiness", "")).strip(),
            "therapeutic_claim_readiness": str(dqas.get("therapeutic_claim_readiness", "")).strip(),
            "master_wave2_release_gate_status": master_wave2_release_gate_status,
            "master_wave2_release_blocked": master_wave2_release_blocked,
            "master_wave2_ready": master_wave2_ready,
            "master_wave2_queue_status": master_wave2_queue_status,
            "active_stack_level": master_active_stack_level,
            "active_target_id": master_active_target_id,
            "active_target_queue_status": master_active_target_queue_status,
            "active_target_execution_state": master_active_target_execution_state,
            "stack_gate_states": master_stack_gate_states,
            "lbdhodh_blockers": master_lbdhodh_blockers,
            "stk17b_final2_queue_status": str(f2qs.get("stk17b_queue_status", "")).strip(),
            "lbdhodh_final2_queue_status": str(f2qs.get("lbdhodh_queue_status", "")).strip(),
            "lbdhodh_upstream_gate_open": bool(f2cs.get("next3_final_gate_open", False)),
            "lbdhodh_content_ready": bool(f2cs.get("lbdhodh_content_ready", False)),
            "cruzain_next3_queue_status": str(nxqs.get("cruzain_queue_status", "")).strip(),
            "plpro_next3_queue_status": str(nxqs.get("plpro_queue_status", "")).strip(),
            "alk2_next3_queue_status": str(nxqs.get("alk2_queue_status", "")).strip(),
            "mpro_execution_state": str(mps.get("execution_state", "")).strip(),
            "mpro_run_record_detected": bool(mps.get("run_record_detected", False)),
            "caix_review_state": str(crrs.get("caix_review_state", "")).strip(),
            "caix_run_record_detected": bool(crrs.get("caix_run_record_detected", False)),
            "caix_successor_gate_state": str(crrs.get("successor_gate_state", "")).strip(),
            "tcruzi_result_review_gate_status": str(trrs.get("result_review_gate_status", "")).strip(),
            "tcruzi_run_record_detected": bool(trrrs) or bool(trrs.get("tcruzi_run_record_detected", False)),
            "tcruzi_execution_state": str(trrrs.get("execution_state", trrs.get("tcruzi_execution_state", ""))).strip(),
            "tcruzi_run_record_queue_status": str(trrrs.get("queue_status_now", "")).strip(),
            "tcruzi_wave2_release_gate_status": str(trrs.get("wave2_release_gate_status", "")).strip(),
            "tcruzi_wave2_release_blocked": bool(trrs.get("wave2_release_blocked", True)),
            "wave2_first_target": str(w2qs.get("first_target", "")).strip(),
            "wave2_queue_target_count": int(w2qs.get("queue_target_count", 0) or 0),
            "wave2_missing_target_specific_packet_count": int(w2qs.get("missing_target_specific_packet_count", 0) or 0),
            "wave1_packet_queue_ready": bool(qs.get("status") == "wetlab_wave1_packet_queue_ready"),
            "one_page_brief_starters_ready": bool(ws.get("status") == "wetlab_wave1_one_page_briefs_ready"),
            "target_brief_index_ready": bool(bis.get("status") == "wetlab_wave1_target_brief_packets_ready"),
            "brief_fill_queue_ready": bool(fs.get("status") == "wetlab_wave1_brief_fill_queue_ready"),
            "first_contact_bundle_ready": bool(cs2.get("status") == "wetlab_first_contact_brief_bundle_ready"),
            "priority3_repurposing_fill_ready": bool(p3s.get("status") == "wetlab_priority3_repurposing_fill_map_ready"),
            "priority3_novelty_fill_ready": bool(n3s.get("status") == "wetlab_priority3_novelty_fill_map_ready"),
            "next3_repurposing_fill_ready": bool(nxs.get("status") == "wetlab_next3_repurposing_fill_map_ready"),
            "next3_novelty_fill_ready": bool(nns.get("status") == "wetlab_next3_novelty_fill_map_ready"),
            "mpro_vendor_cost_check_ready": bool(mvs.get("status") == "wetlab_mpro_vendor_cost_check_ready"),
            "first_contact_export_bundle_ready": bool(exs.get("status") == "wetlab_partner_first_contact_export_bundle_ready"),
            "cleanup_manifest_ready": bool(cms.get("status") in {"runs_cleanup_manifest_ready", "runs_cleanup_batch2_manifest_ready"}),
            "open_first": "runs/wetlab_partner_target_portfolio_current.md",
            "open_second": "runs/wetlab_wave1_campaign_blueprint_current.md",
            "open_third": "runs/wetlab_wave1_target_brief_matrix_current.md",
            "open_fourth": "runs/wetlab_validation_companion_panels_current.md",
            "open_fifth": "runs/wetlab_partner_outreach_tracks_current.md",
            "open_sixth": "runs/wetlab_wave1_rail_packet_index_current.md",
            "open_seventh": "runs/wetlab_one_page_brief_schema_current.md",
            "open_eighth": "runs/wetlab_domain_generation_schema_current.md",
            "open_ninth": "runs/wetlab_partner_export_schema_current.md",
            "open_tenth": "runs/wetlab_priority3_target_render_split_current.md",
            "open_eleventh": "runs/sarscov2_mpro_render_suite_current.md",
            "open_twelfth": "runs/caix_render_suite_current.md",
            "open_thirteenth": "runs/tcruzi_pde_render_suite_current.md",
            "open_fourteenth": "runs/wetlab_prep_artifact_lane_current.md",
            "open_fifteenth": "runs/wetlab_priority3_protein_run_queue_current.md",
            "open_sixteenth": "runs/sarscov2_mpro_launch_packet_current.md",
            "open_seventeenth": "runs/caix_launch_packet_current.md",
            "open_eighteenth": "runs/tcruzi_pde_launch_packet_current.md",
            "open_nineteenth": "runs/wetlab_wave1_packet_queue_current.md",
            "open_twentieth": "runs/wetlab_wave1_one_page_briefs_current.md",
            "open_twentyfirst": "runs/wetlab_wave1_target_brief_index_current.md",
            "open_twentisecond": "runs/wetlab_wave1_brief_fill_queue_current.md",
            "open_twentythird": "runs/wetlab_first_contact_brief_bundle_current.md",
            "open_twentyfourth": "runs/wetlab_priority3_repurposing_fill_map_current.md",
            "open_twentyfifth": "runs/wetlab_priority3_novelty_fill_map_current.md",
            "open_twentysixth": "runs/wetlab_mpro_vendor_cost_check_current.md",
            "open_twentyseventh": "runs/wetlab_next3_repurposing_fill_map_current.md",
            "open_twentyeighth": "runs/wetlab_next3_novelty_fill_map_current.md",
            "open_twentyninth": "runs/wetlab_partner_first_contact_export_bundle_current.md",
            "open_thirtieth": "runs/runs_cleanup_batch2_manifest_current.md",
            "open_thirtyfirst": "runs/sarscov2_mpro_run_status_current.md",
            "open_thirtysecond": "runs/caix_result_review_current.md",
            "open_thirtythird": "runs/tcruzi_pde_result_review_current.md",
            "open_thirtyfourth": "runs/sarscov2_mpro_run_record_current.md",
            "open_thirtyfifth": "runs/caix_run_record_current.md",
            "open_thirtysixth": "runs/tcruzi_pde_run_record_current.md",
            "open_thirtyseventh": "runs/wetlab_priority3_runtime_runbook_current.md",
            "open_thirtyeighth": "runs/wetlab_priority3_runtime_event_current.md",
            "open_thirtyninth": "runs/wetlab_next3_protein_run_queue_current.md",
            "open_fortieth": "runs/wetlab_next3_chain_stack_current.md",
            "open_fortyfirst": "runs/wetlab_next3_runtime_runbook_current.md",
            "open_fortysecond": "runs/wetlab_next3_runtime_event_current.md",
            "open_fortythird": "runs/wetlab_next3_execution_console_current.md",
            "open_fortyfourth": "runs/wetlab_final2_protein_run_queue_current.md",
            "open_fortyfifth": "runs/wetlab_final2_chain_stack_current.md",
            "open_fortysixth": "runs/wetlab_final2_runtime_runbook_current.md",
            "open_fortyseventh": "runs/wetlab_final2_runtime_event_current.md",
            "open_fortyeighth": "runs/wetlab_final2_execution_console_current.md",
            "open_fortyninth": "runs/wetlab_master_execution_queue_current.md",
            "open_fiftieth": "runs/wetlab_master_runtime_runbook_current.md",
            "open_fiftyfirst": "runs/wetlab_master_execution_console_current.md",
            "open_fiftysecond": "runs/wetlab_wave2_protein_run_queue_current.md",
            "open_fiftythird": "runs/wetlab_wave2_chain_stack_current.md",
            "open_fiftyfourth": "runs/wetlab_wave2_runtime_runbook_current.md",
            "open_fiftyfifth": "runs/wetlab_wave2_runtime_event_current.md",
            "open_fiftysixth": "runs/wetlab_wave2_execution_console_current.md",
            "open_fiftyseventh": "runs/wetlab_master_terminal_review_current.md",
            "open_fiftyeighth": "runs/wetlab_outbound_execution_priority_board_current.md",
            "open_fiftyninth": "runs/wetlab_final_campaign_summary_current.md",
            "open_sixtieth": "runs/wetlab_partner_send_round_current.md",
            "open_sixtyfirst": "runs/wetlab_master_handoff_dashboard_current.md",
            "open_sixtysecond": "runs/wetlab_data_quality_assessment_current.md",
            "open_sixtythird": "runs/wetlab_broad_screen_library_spec_current.md",
            "open_sixtyfourth": "runs/wetlab_broad_screen_queue_current.md",
            "open_sixtyfifth": "runs/wetlab_broad_screen_bridge_current.md",
            "open_sixtysixth": "runs/wetlab_broad_screen_compound_universe_current.md",
            "open_sixtyseventh": "runs/wetlab_broad_screen_execution_queue_current.md",
            "open_sixtyeighth": "runs/wetlab_broad_screen_runtime_runbook_current.md",
            "open_sixtyninth": "runs/wetlab_broad_screen_repurposing_autofill_current.md",
            "open_seventieth": "runs/wetlab_broad_screen_bulk_result_source_schema_current.md",
            "open_seventyfirst": "runs/wetlab_broad_screen_bulk_result_row_examples_current.md",
            "open_seventysecond": "runs/wetlab_broad_screen_target_rerank_current.md",
            "open_seventythird": "runs/wetlab_broad_screen_throughput_bridge_current.md",
            "open_seventyfourth": "runs/wetlab_retry_handoff_summary_current.md",
            "open_seventyfifth": "runs/wetlab_stk17b_manual_retry_lane_current.md",
            "open_seventysixth": "runs/wetlab_stk17b_exploratory_retry_lane_current.md",
            "open_seventyseventh": "runs/wetlab_stk17b_exploratory_followup_lane_current.md",
            "open_seventyseventh_b": "runs/wetlab_stk17b_followup_review_surface_current.md",
            "open_seventyeighth": "runs/wetlab_plpro_manual_retry_lane_current.md",
            "open_seventyninth": "runs/wetlab_mapping_fix_retry_support_current.md",
            "open_eightieth": "runs/wetlab_stage1_mapping_fix_lanes_current.md",
            "open_eightyfirst_mapping_fix_templates": "runs/wetlab_mapping_fix_retry_policy_templates_current.md",
            "open_eightyfirst": "runs/wetlab_kinase_retry_policy_templates_current.md",
            "open_eightysecond_target_retry": "runs/wetlab_target_retry_policy_templates_current.md",
            "open_eightyfifth": "runs/wetlab_dengue_ns2b_ns3_protease_stage6_tuning_surface_current.md",
            "open_eightysixth": "runs/wetlab_dengue_ns2b_ns3_protease_exploratory_retry_lane_current.md",
            "open_eightysecond": "runs/wetlab_lbdhodh_stage6_tuning_surface_current.md",
            "open_eightythird": "runs/wetlab_lbdhodh_exploratory_retry_lane_current.md",
            "open_eightyfourth": "runs/wetlab_lbdhodh_gate51_validation_review_surface_current.md",
            "open_eightyfifth_pde_top4": "runs/wetlab_tcruzi_pde_promoted_top4_review_packet_current.md",
            "open_eightysixth_pde_branch": "runs/wetlab_tcruzi_pde_rescue_only_branch_summary_current.md",
            "next_required_step": (
                selected_allatom_next_required_step
                if selected_allatom_next_required_step
                else str(bsrhs.get("selected_krs1_branch_review_next_required_step", "")).strip()
                if str(bsrhs.get("selected_krs1_branch_review_next_required_step", "")).strip()
                else str(bdr1.get("next_required_step", "")).strip()
                if str(bdr1.get("status", "")).strip() == "wetlab_dpre1_branch_review_surface_ready"
                and str(bdr1.get("next_required_step", "")).strip()
                else str(bsrhs.get("selected_rescue_branch_next_required_step", "")).strip()
                if str(bsrhs.get("selected_rescue_branch_next_required_step", "")).strip()
                else str(bsrhs.get("selected_rescue_review_next_required_step", "")).strip()
                if str(bsrhs.get("selected_rescue_review_next_required_step", "")).strip()
                else dengue_stage6_next_required_step
                if dengue_stage6_next_required_step
                else
                rescue_next_required_step
                if rescue_next_required_step
                else str(bslvrs.get("next_required_step", "")).strip()
                if bool(bslvrs.get("gate51_validated", False)) and str(bslvrs.get("next_required_step", "")).strip()
                else str(bstrpts.get("next_required_step", "")).strip()
                if bool(bstrpts.get("status", "")).strip() == "wetlab_target_retry_policy_templates_ready"
                and str(bstrpts.get("next_required_step", "")).strip()
                else _stk17b_followup_review_next_step(broad_screen_stk17b_followup_review_surface)
                if (
                    (
                        (
                            (
                                str(bsrhs.get("selected_manual_retry_target_id", "")).strip()
                                or str(bsrhs.get("selected_manual_retry_lane_label", "")).strip()
                            )
                            and (
                                (
                                    str(bsrhs.get("selected_manual_retry_target_id", "")).strip()
                                    or str(bsrhs.get("manual_retry_focus_target_id", "")).strip()
                                )
                                == "STK17B (DRAK2)"
                            )
                            and str(bsrhs.get("selected_manual_retry_lane_label", "")).strip()
                            == "exploratory_gate4.5_followup"
                        )
                        or (
                            not str(bsrhs.get("selected_manual_retry_target_id", "")).strip()
                            and not str(bsrhs.get("selected_manual_retry_lane_label", "")).strip()
                            and (
                                bool(bssefls.get("ready_for_manual_retry", False))
                                or (
                                    str(bssefls.get("followup_lane_label", "") or bssefls.get("lane_label", "")).strip()
                                    == "exploratory_gate4.5_followup"
                                    and str(bssefls.get("status", "")).strip().startswith(
                                        "wetlab_stk17b_exploratory_followup_lane_"
                                    )
                                )
                            )
                        )
                    )
                    and _stk17b_followup_review_next_step(broad_screen_stk17b_followup_review_surface)
                )
                else
                _manual_retry_next_step(
                    broad_screen_retry_handoff_summary or {},
                    broad_screen_stk17b_exploratory_followup_lane or {},
                    broad_screen_stk17b_manual_retry_lane or {},
                    broad_screen_stk17b_exploratory_retry_lane or {},
                    broad_screen_plpro_manual_retry_lane or {},
                    broad_screen_lbdhodh_exploratory_retry_lane or {},
                    str(bssefls.get("next_required_step", "")).strip()
                    or str(bsserls.get("next_required_step", "")).strip()
                    or str(bssmls.get("next_required_step", "")).strip()
                    or str(bspmls.get("next_required_step", "")).strip(),
                )
                if bool(
                    bssefls.get("ready_for_manual_retry", False)
                    or (
                        str(bssefls.get("followup_lane_label", "") or bssefls.get("lane_label", "")).strip() == "exploratory_gate4.5_followup"
                        and str(bssefls.get("status", "")).strip().startswith("wetlab_stk17b_exploratory_followup_lane_")
                    )
                    or
                    bsserls.get("ready_for_manual_retry", False)
                    or bssmls.get("ready_for_manual_retry", False)
                    or bspmls.get("ready_for_manual_retry", False)
                    or (
                        str(bsldrs.get("status", "")).strip().startswith("wetlab_lbdhodh_exploratory_retry_lane_")
                        and str(bsldrs.get("queue_status", "")).strip() == "running"
                    )
                    or bsldrs.get("ready_for_manual_retry", False)
                )
                else
                rescue_next_required_step
                if rescue_next_required_step
                else
                str(bsmfrs.get("next_required_step", "")).strip()
                if int(bsmfrs.get("ready_target_count", 0) or 0) > 0
                else
                f"Continue the active broad-procurement shard for {bseqs.get('first_actionable_target_id', '')} {bseqs.get('first_actionable_shard_id', '')}, then rerun autofill-driven repurposing packet refresh."
                if int(bseqs.get("running_row_count", 0) or 0) > 0
                else
                f"Dispatch {bseqs.get('first_actionable_target_id', '')} shard {bseqs.get('first_actionable_shard_id', '')} through the broad-screen runtime runner, then rerun autofill-driven repurposing packet refresh."
                if int(bseqs.get("ready_now_row_count", 0) or 0) > 0
                else
                "Launch the broad_procurement_100k target-by-shard screen, then bridge bulk results into the existing top-3 repurposing plus top-3 novelty packet layer."
                if str(bseqs.get("status", "")).strip() == "wetlab_broad_screen_execution_queue_ready"
                else str(mqs2.get("next_required_step", "")).strip()
                or "Use the prep/artifact lane and serialized priority-three protein run queue with live run-record-backed transition artifacts first. Once the final priority3 review resolves, continue into the next3 chain through Cruzain -> PLpro -> ALK2, then finish the Wave 1 tail through STK17B -> Leishmania braziliensis DHODH while keeping LbDHODH blocked until compound fill is real."
            ),
        }
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Partnering Stack",
        "",
        f"- status: `{s['status']}`",
        f"- portfolio_target_count: `{s['portfolio_target_count']}`",
        f"- wave1_target_count: `{s['wave1_target_count']}`",
        f"- brief_matrix_count: `{s['brief_matrix_count']}`",
        f"- companion_panel_count: `{s['companion_panel_count']}`",
        f"- outreach_track_count: `{s['outreach_track_count']}`",
        f"- rail_packet_index_ready: `{s['rail_packet_index_ready']}`",
        f"- brief_schema_ready: `{s['brief_schema_ready']}`",
        f"- domain_generation_schema_ready: `{s['domain_generation_schema_ready']}`",
        f"- partner_export_schema_ready: `{s['partner_export_schema_ready']}`",
        f"- priority3_render_split_ready: `{s['priority3_render_split_ready']}`",
        f"- sarscov2_mpro_render_suite_ready: `{s['sarscov2_mpro_render_suite_ready']}`",
        f"- caix_render_suite_ready: `{s['caix_render_suite_ready']}`",
        f"- tcruzi_pde_render_suite_ready: `{s['tcruzi_pde_render_suite_ready']}`",
        f"- priority3_target_overlay_ready_count: `{s['priority3_target_overlay_ready_count']}`",
        f"- prep_artifact_lane_ready: `{s['prep_artifact_lane_ready']}`",
        f"- priority3_run_queue_ready: `{s['priority3_run_queue_ready']}`",
        f"- mpro_launch_packet_ready: `{s['mpro_launch_packet_ready']}`",
        f"- caix_launch_packet_ready: `{s['caix_launch_packet_ready']}`",
        f"- tcruzi_pde_launch_packet_ready: `{s['tcruzi_pde_launch_packet_ready']}`",
        f"- priority3_launch_packet_ready_count: `{s['priority3_launch_packet_ready_count']}`",
        f"- mpro_run_record_ready: `{s['mpro_run_record_ready']}`",
        f"- caix_run_record_ready: `{s['caix_run_record_ready']}`",
        f"- tcruzi_pde_run_record_ready: `{s['tcruzi_pde_run_record_ready']}`",
        f"- priority3_run_record_ready_count: `{s['priority3_run_record_ready_count']}`",
        f"- mpro_run_status_ready: `{s['mpro_run_status_ready']}`",
        f"- caix_result_review_ready: `{s['caix_result_review_ready']}`",
        f"- tcruzi_pde_result_review_ready: `{s['tcruzi_pde_result_review_ready']}`",
        f"- priority3_runtime_event_ready: `{s['priority3_runtime_event_ready']}`",
        f"- priority3_runtime_runbook_ready: `{s['priority3_runtime_runbook_ready']}`",
        f"- next3_run_queue_ready: `{s['next3_run_queue_ready']}`",
        f"- next3_chain_stack_ready: `{s['next3_chain_stack_ready']}`",
        f"- next3_runtime_event_ready: `{s['next3_runtime_event_ready']}`",
        f"- next3_runtime_runbook_ready: `{s['next3_runtime_runbook_ready']}`",
        f"- next3_execution_console_ready: `{s['next3_execution_console_ready']}`",
        f"- final2_run_queue_ready: `{s['final2_run_queue_ready']}`",
        f"- final2_chain_stack_ready: `{s['final2_chain_stack_ready']}`",
        f"- final2_runtime_event_ready: `{s['final2_runtime_event_ready']}`",
        f"- final2_runtime_runbook_ready: `{s['final2_runtime_runbook_ready']}`",
        f"- final2_execution_console_ready: `{s['final2_execution_console_ready']}`",
        f"- wave2_run_queue_ready: `{s['wave2_run_queue_ready']}`",
        f"- wave2_chain_stack_ready: `{s['wave2_chain_stack_ready']}`",
        f"- wave2_runtime_event_ready: `{s['wave2_runtime_event_ready']}`",
        f"- wave2_runtime_runbook_ready: `{s['wave2_runtime_runbook_ready']}`",
        f"- wave2_execution_console_ready: `{s['wave2_execution_console_ready']}`",
        f"- master_queue_ready: `{s['master_queue_ready']}`",
        f"- master_runtime_runbook_ready: `{s['master_runtime_runbook_ready']}`",
        f"- master_execution_console_ready: `{s['master_execution_console_ready']}`",
        f"- master_terminal_review_ready: `{s['master_terminal_review_ready']}`",
        f"- outbound_execution_priority_board_ready: `{s['outbound_execution_priority_board_ready']}`",
        f"- final_campaign_summary_ready: `{s['final_campaign_summary_ready']}`",
        f"- partner_send_round_ready: `{s['partner_send_round_ready']}`",
        f"- master_handoff_dashboard_ready: `{s['master_handoff_dashboard_ready']}`",
        f"- data_quality_assessment_ready: `{s['data_quality_assessment_ready']}`",
        f"- broad_screen_library_spec_ready: `{s['broad_screen_library_spec_ready']}`",
        f"- broad_screen_queue_ready: `{s['broad_screen_queue_ready']}`",
        f"- broad_screen_bridge_ready: `{s['broad_screen_bridge_ready']}`",
        f"- broad_screen_compound_universe_ready: `{s['broad_screen_compound_universe_ready']}`",
        f"- broad_screen_bulk_results_ready: `{s['broad_screen_bulk_results_ready']}`",
        f"- broad_screen_repurposing_autofill_ready: `{s['broad_screen_repurposing_autofill_ready']}`",
        f"- broad_screen_execution_queue_ready: `{s['broad_screen_execution_queue_ready']}`",
        f"- broad_screen_runtime_runbook_ready: `{s['broad_screen_runtime_runbook_ready']}`",
        f"- broad_screen_bulk_result_source_schema_ready: `{s['broad_screen_bulk_result_source_schema_ready']}`",
        f"- broad_screen_bulk_result_row_examples_ready: `{s['broad_screen_bulk_result_row_examples_ready']}`",
        f"- broad_screen_target_rerank_ready: `{s['broad_screen_target_rerank_ready']}`",
        f"- broad_screen_stability_score_ready: `{s['broad_screen_stability_score_ready']}`",
        f"- broad_screen_antitarget_queue_ready: `{s['broad_screen_antitarget_queue_ready']}`",
        f"- broad_screen_antitarget_execution_queue_ready: `{s['broad_screen_antitarget_execution_queue_ready']}`",
        f"- broad_screen_primary_watch_state_ready: `{s['broad_screen_primary_watch_state_ready']}`",
        f"- broad_screen_primary_watch_ready: `{s['broad_screen_primary_watch_ready']}`",
        f"- broad_screen_primary_watch_next_required_step: `{s['broad_screen_primary_watch_next_required_step']}`",
        f"- broad_screen_primary_watch_loop_pid: `{s['broad_screen_primary_watch_loop_pid']}`",
        f"- broad_screen_primary_watch_loop_attached: `{s['broad_screen_primary_watch_loop_attached']}`",
        f"- broad_screen_primary_watch_liveness: `{s['broad_screen_primary_watch_liveness']}`",
        f"- broad_screen_primary_watch_fallback_mode: `{s['broad_screen_primary_watch_fallback_mode']}`",
        f"- broad_screen_antitarget_watch_state_ready: `{s['broad_screen_antitarget_watch_state_ready']}`",
        f"- broad_screen_antitarget_watch_ready: `{s['broad_screen_antitarget_watch_ready']}`",
        f"- broad_screen_antitarget_watch_next_required_step: `{s['broad_screen_antitarget_watch_next_required_step']}`",
        f"- broad_screen_antitarget_watch_loop_pid: `{s['broad_screen_antitarget_watch_loop_pid']}`",
        f"- broad_screen_antitarget_watch_loop_attached: `{s['broad_screen_antitarget_watch_loop_attached']}`",
        f"- broad_screen_antitarget_watch_liveness: `{s['broad_screen_antitarget_watch_liveness']}`",
        f"- broad_screen_antitarget_watch_fallback_mode: `{s['broad_screen_antitarget_watch_fallback_mode']}`",
        f"- broad_screen_actual_append_ready: `{s['broad_screen_actual_append_ready']}`",
        f"- broad_screen_append_batch_pending_entry_count: `{s['broad_screen_append_batch_pending_entry_count']}`",
        f"- broad_screen_next_target_extension_ready: `{s['broad_screen_next_target_extension_ready']}`",
        f"- broad_screen_throughput_bridge_ready: `{s['broad_screen_throughput_bridge_ready']}`",
        f"- broad_screen_throughput_target_id: `{s['broad_screen_throughput_target_id']}`",
        f"- broad_screen_throughput_shard_id: `{s['broad_screen_throughput_shard_id']}`",
        f"- broad_screen_throughput_execute_ready: `{s['broad_screen_throughput_execute_ready']}`",
        f"- broad_screen_primary_retry_preset_ready: `{s['broad_screen_primary_retry_preset_ready']}`",
        f"- broad_screen_primary_retry_guard_blocked_target_count: `{s['broad_screen_primary_retry_guard_blocked_target_count']}`",
        f"- broad_screen_primary_hold_guard_ready: `{s['broad_screen_primary_hold_guard_ready']}`",
        f"- broad_screen_primary_hold_guard_triggered_target_count: `{s['broad_screen_primary_hold_guard_triggered_target_count']}`",
        f"- broad_screen_current_results_index_ready: `{s['broad_screen_current_results_index_ready']}`",
        f"- broad_screen_current_results_group_count: `{s['broad_screen_current_results_group_count']}`",
        f"- broad_screen_monitor_semantics_ready: `{s['broad_screen_monitor_semantics_ready']}`",
        f"- broad_screen_monitor_guard_active: `{s['broad_screen_monitor_guard_active']}`",
        f"- broad_screen_retry_handoff_summary_ready: `{s['broad_screen_retry_handoff_summary_ready']}`",
        f"- broad_screen_retry_handoff_manual_retry_decision_count: `{s['broad_screen_retry_handoff_manual_retry_decision_count']}`",
        f"- broad_screen_retry_handoff_focus_target_id: `{s['broad_screen_retry_handoff_focus_target_id']}`",
        f"- broad_screen_dpre1_branch_review_ready: `{s['broad_screen_dpre1_branch_review_ready']}`",
        f"- broad_screen_dpre1_branch_review_target_id: `{s['broad_screen_dpre1_branch_review_target_id']}`",
        f"- broad_screen_dpre1_branch_review_branch_label: `{s['broad_screen_dpre1_branch_review_branch_label']}`",
        f"- broad_screen_dpre1_branch_review_source_priority: `{s['broad_screen_dpre1_branch_review_source_priority']}`",
        f"- broad_screen_dpre1_branch_review_stage6_tuning_recommended_threshold_A: `{s['broad_screen_dpre1_branch_review_stage6_tuning_recommended_threshold_A']}`",
        f"- broad_screen_dpre1_branch_review_exploratory_retry_lane_label: `{s['broad_screen_dpre1_branch_review_exploratory_retry_lane_label']}`",
        f"- broad_screen_dpre1_branch_review_successor_target: `{s['broad_screen_dpre1_branch_review_successor_target']}`",
        f"- broad_screen_lbdhodh_stage6_tuning_surface_ready: `{s['broad_screen_lbdhodh_stage6_tuning_surface_ready']}`",
        f"- broad_screen_lbdhodh_stage6_recommended_threshold_A: `{s['broad_screen_lbdhodh_stage6_recommended_threshold_A']}`",
        f"- broad_screen_lbdhodh_stage6_immediately_runnable_command_kind: `{s['broad_screen_lbdhodh_stage6_immediately_runnable_command_kind']}`",
        f"- broad_screen_lbdhodh_gate51_validation_review_surface_ready: `{s['broad_screen_lbdhodh_gate51_validation_review_surface_ready']}`",
        f"- broad_screen_lbdhodh_gate51_validated: `{s['broad_screen_lbdhodh_gate51_validated']}`",
        f"- broad_screen_lbdhodh_gate51_validation_decision: `{s['broad_screen_lbdhodh_gate51_validation_decision']}`",
        f"- broad_screen_lbdhodh_retry_lane_ready: `{s['broad_screen_lbdhodh_retry_lane_ready']}`",
        f"- broad_screen_lbdhodh_retry_ready_for_manual_retry: `{s['broad_screen_lbdhodh_retry_ready_for_manual_retry']}`",
        f"- broad_screen_lbdhodh_retry_target_id: `{s['broad_screen_lbdhodh_retry_target_id']}`",
        f"- broad_screen_lbdhodh_retry_shard_id: `{s['broad_screen_lbdhodh_retry_shard_id']}`",
        f"- broad_screen_lbdhodh_retry_selected_command_kind: `{s['broad_screen_lbdhodh_retry_selected_command_kind']}`",
        f"- broad_screen_lbdhodh_retry_lane_label: `{s['broad_screen_lbdhodh_retry_lane_label']}`",
        f"- broad_screen_stk17b_exploratory_retry_lane_ready: `{s['broad_screen_stk17b_exploratory_retry_lane_ready']}`",
        f"- broad_screen_stk17b_exploratory_retry_ready_for_manual_retry: `{s['broad_screen_stk17b_exploratory_retry_ready_for_manual_retry']}`",
        f"- broad_screen_stk17b_exploratory_retry_target_id: `{s['broad_screen_stk17b_exploratory_retry_target_id']}`",
        f"- broad_screen_stk17b_exploratory_retry_shard_id: `{s['broad_screen_stk17b_exploratory_retry_shard_id']}`",
        f"- broad_screen_stk17b_exploratory_retry_selected_command_kind: `{s['broad_screen_stk17b_exploratory_retry_selected_command_kind']}`",
        f"- broad_screen_stk17b_exploratory_retry_selected_threshold_A: `{s['broad_screen_stk17b_exploratory_retry_selected_threshold_A']}`",
        f"- broad_screen_stk17b_exploratory_followup_lane_label: `{s['broad_screen_stk17b_exploratory_followup_lane_label']}`",
        f"- broad_screen_stk17b_exploratory_followup_freeze_state: `{s['broad_screen_stk17b_exploratory_followup_freeze_state']}`",
        f"- broad_screen_stk17b_exploratory_followup_freeze_note: `{s['broad_screen_stk17b_exploratory_followup_freeze_note']}`",
        f"- broad_screen_stk17b_exploratory_followup_followup_shard_ids: `{s['broad_screen_stk17b_exploratory_followup_followup_shard_ids']}`",
        f"- broad_screen_stk17b_exploratory_freeze_state: `{s['broad_screen_stk17b_exploratory_freeze_state']}`",
        f"- broad_screen_stk17b_exploratory_freeze_target_id: `{s['broad_screen_stk17b_exploratory_freeze_target_id']}`",
        f"- broad_screen_stk17b_exploratory_freeze_hold_streak: `{s['broad_screen_stk17b_exploratory_freeze_hold_streak']}`",
        f"- broad_screen_stk17b_exploratory_freeze_hold_limit: `{s['broad_screen_stk17b_exploratory_freeze_hold_limit']}`",
        f"- broad_screen_stk17b_exploratory_freeze_note: `{s['broad_screen_stk17b_exploratory_freeze_note']}`",
        f"- broad_screen_stk17b_exploratory_freeze_next_required_step: `{s['broad_screen_stk17b_exploratory_freeze_next_required_step']}`",
        f"- broad_screen_stk17b_manual_retry_lane_ready: `{s['broad_screen_stk17b_manual_retry_lane_ready']}`",
        f"- broad_screen_plpro_manual_retry_lane_ready: `{s['broad_screen_plpro_manual_retry_lane_ready']}`",
        f"- broad_screen_plpro_manual_retry_ready_for_manual_retry: `{s['broad_screen_plpro_manual_retry_ready_for_manual_retry']}`",
        f"- broad_screen_plpro_manual_retry_target_id: `{s['broad_screen_plpro_manual_retry_target_id']}`",
        f"- broad_screen_plpro_manual_retry_shard_id: `{s['broad_screen_plpro_manual_retry_shard_id']}`",
        f"- broad_screen_plpro_manual_retry_selected_command_kind: `{s['broad_screen_plpro_manual_retry_selected_command_kind']}`",
        f"- broad_screen_mapping_fix_retry_support_ready: `{s['broad_screen_mapping_fix_retry_support_ready']}`",
        f"- broad_screen_mapping_fix_retry_ready_target_count: `{s['broad_screen_mapping_fix_retry_ready_target_count']}`",
        f"- broad_screen_mapping_fix_retry_ready_targets: `{s['broad_screen_mapping_fix_retry_ready_targets']}`",
        f"- broad_screen_stage1_mapping_fix_lanes_ready: `{s['broad_screen_stage1_mapping_fix_lanes_ready']}`",
        f"- broad_screen_stage1_mapping_fix_ready_target_count: `{s['broad_screen_stage1_mapping_fix_ready_target_count']}`",
        f"- broad_screen_stage1_mapping_fix_ready_targets: `{s['broad_screen_stage1_mapping_fix_ready_targets']}`",
        f"- broad_screen_kinase_retry_policy_templates_ready: `{s['broad_screen_kinase_retry_policy_templates_ready']}`",
        f"- broad_screen_kinase_retry_template_target_count: `{s['broad_screen_kinase_retry_template_target_count']}`",
        f"- broad_screen_kinase_retry_empirical_validated_target_count: `{s['broad_screen_kinase_retry_empirical_validated_target_count']}`",
        f"- broad_screen_kinase_retry_gate45_only_target_count: `{s['broad_screen_kinase_retry_gate45_only_target_count']}`",
        f"- broad_screen_kinase_retry_guarded_gate55_candidate_target_count: `{s['broad_screen_kinase_retry_guarded_gate55_candidate_target_count']}`",
        f"- broad_screen_kinase_retry_focus_target_id: `{s['broad_screen_kinase_retry_focus_target_id']}`",
        f"- broad_screen_kinase_retry_focus_template_label: `{s['broad_screen_kinase_retry_focus_template_label']}`",
        f"- broad_screen_kinase_retry_focus_selected_command_kind: `{s['broad_screen_kinase_retry_focus_selected_command_kind']}`",
        f"- broad_screen_kinase_retry_next_required_step: `{s['broad_screen_kinase_retry_next_required_step']}`",
        f"- broad_screen_target_retry_policy_templates_ready: `{s['broad_screen_target_retry_policy_templates_ready']}`",
        f"- broad_screen_target_retry_template_target_count: `{s['broad_screen_target_retry_template_target_count']}`",
        f"- broad_screen_target_retry_empirical_validated_target_count: `{s['broad_screen_target_retry_empirical_validated_target_count']}`",
        f"- broad_screen_target_retry_non_kinase_template_target_count: `{s['broad_screen_target_retry_non_kinase_template_target_count']}`",
        f"- broad_screen_target_retry_non_kinase_empirical_validated_target_count: `{s['broad_screen_target_retry_non_kinase_empirical_validated_target_count']}`",
        f"- broad_screen_target_retry_guarded_gate55_candidate_target_count: `{s['broad_screen_target_retry_guarded_gate55_candidate_target_count']}`",
        f"- broad_screen_target_retry_guarded_gate51_candidate_target_count: `{s['broad_screen_target_retry_guarded_gate51_candidate_target_count']}`",
        f"- broad_screen_target_retry_focus_target_id: `{s['broad_screen_target_retry_focus_target_id']}`",
        f"- broad_screen_target_retry_focus_template_label: `{s['broad_screen_target_retry_focus_template_label']}`",
        f"- broad_screen_target_retry_focus_selected_command_kind: `{s['broad_screen_target_retry_focus_selected_command_kind']}`",
        f"- broad_screen_target_retry_focus_selected_threshold_A: `{s['broad_screen_target_retry_focus_selected_threshold_A']}`",
        f"- broad_screen_target_retry_next_required_step: `{s['broad_screen_target_retry_next_required_step']}`",
        f"- broad_screen_target_retry_policy_templates_artifact: `{s['broad_screen_target_retry_policy_templates_artifact']}`",
        f"- broad_screen_hard_target_rescue_lane_ready: `{s['broad_screen_hard_target_rescue_lane_ready']}`",
        f"- broad_screen_hard_target_rescue_lane_target_id: `{s['broad_screen_hard_target_rescue_lane_target_id']}`",
        f"- broad_screen_hard_target_rescue_lane_shard_id: `{s['broad_screen_hard_target_rescue_lane_shard_id']}`",
        f"- broad_screen_hard_target_rescue_lane_auto_hold_streak: `{s['broad_screen_hard_target_rescue_lane_auto_hold_streak']}`",
        f"- broad_screen_hard_target_rescue_lane_selected_command_kind: `{s['broad_screen_hard_target_rescue_lane_selected_command_kind']}`",
        f"- broad_screen_hard_target_rescue_lane_lane_label: `{s['broad_screen_hard_target_rescue_lane_lane_label']}`",
        f"- broad_screen_hard_target_rescue_lane_next_required_step: `{s['broad_screen_hard_target_rescue_lane_next_required_step']}`",
        f"- broad_screen_rescue_anchor_artifacts_ready: `{s['broad_screen_rescue_anchor_artifacts_ready']}`",
        f"- broad_screen_rescue_anchor_target_id: `{s['broad_screen_rescue_anchor_target_id']}`",
        f"- broad_screen_rescue_anchor_artifact_count: `{s['broad_screen_rescue_anchor_artifact_count']}`",
        f"- broad_screen_rescue_anchor_rescue_only: `{s['broad_screen_rescue_anchor_rescue_only']}`",
        f"- broad_screen_rescue_anchor_native_anchor_artifact: `{s['broad_screen_rescue_anchor_native_anchor_artifact']}`",
        f"- broad_screen_rescue_anchor_pocket_anchor_artifact: `{s['broad_screen_rescue_anchor_pocket_anchor_artifact']}`",
        f"- broad_screen_rescue_anchor_next_required_step: `{s['broad_screen_rescue_anchor_next_required_step']}`",
        f"- broad_screen_rescue_three_bead_candidates_ready: `{s['broad_screen_rescue_three_bead_candidates_ready']}`",
        f"- broad_screen_rescue_three_bead_candidate_target_id: `{s['broad_screen_rescue_three_bead_candidate_target_id']}`",
        f"- broad_screen_rescue_three_bead_candidate_count: `{s['broad_screen_rescue_three_bead_candidate_count']}`",
        f"- broad_screen_rescue_three_bead_candidate_top_n: `{s['broad_screen_rescue_three_bead_candidate_top_n']}`",
        f"- broad_screen_rescue_three_bead_candidate_selected_command_kind: `{s['broad_screen_rescue_three_bead_candidate_selected_command_kind']}`",
        f"- broad_screen_rescue_three_bead_candidate_selected_threshold_A: `{s['broad_screen_rescue_three_bead_candidate_selected_threshold_A']}`",
        f"- broad_screen_rescue_three_bead_candidate_next_required_step: `{s['broad_screen_rescue_three_bead_candidate_next_required_step']}`",
        f"- broad_screen_tcruzi_pde_promoted_top4_review_packet_ready: `{s['broad_screen_tcruzi_pde_promoted_top4_review_packet_ready']}`",
        f"- broad_screen_tcruzi_pde_promoted_top4_packet_ready_for_operator_review: `{s['broad_screen_tcruzi_pde_promoted_top4_packet_ready_for_operator_review']}`",
        f"- broad_screen_tcruzi_pde_promoted_top4_wetlab_final_gate_pass: `{s['broad_screen_tcruzi_pde_promoted_top4_wetlab_final_gate_pass']}`",
        f"- broad_screen_tcruzi_pde_promoted_top4_claim_gate_available: `{s['broad_screen_tcruzi_pde_promoted_top4_claim_gate_available']}`",
        f"- broad_screen_tcruzi_pde_promoted_top4_claim_ready_for_allatom: `{s['broad_screen_tcruzi_pde_promoted_top4_claim_ready_for_allatom']}`",
        f"- broad_screen_tcruzi_pde_rescue_only_branch_summary_ready: `{s['broad_screen_tcruzi_pde_rescue_only_branch_summary_ready']}`",
        f"- broad_screen_tcruzi_pde_rescue_only_branch_review_packet_ready_for_operator_review: `{s['broad_screen_tcruzi_pde_rescue_only_branch_review_packet_ready_for_operator_review']}`",
        f"- broad_screen_tcruzi_pde_rescue_only_branch_review_packet_final_gate_pass: `{s['broad_screen_tcruzi_pde_rescue_only_branch_review_packet_final_gate_pass']}`",
        f"- broad_screen_tcruzi_pde_rescue_only_branch_review_packet_claim_gate_available: `{s['broad_screen_tcruzi_pde_rescue_only_branch_review_packet_claim_gate_available']}`",
        f"- broad_screen_tcruzi_pde_rescue_only_branch_review_packet_claim_ready_for_allatom: `{s['broad_screen_tcruzi_pde_rescue_only_branch_review_packet_claim_ready_for_allatom']}`",
        f"- broad_screen_tcruzi_pde_rescue_only_branch_ready_for_final_wetlab: `{s['broad_screen_tcruzi_pde_rescue_only_branch_ready_for_final_wetlab']}`",
        f"- broad_screen_tcruzi_pde_rescue_operator_packet_ready_for_operator_review: `{s['broad_screen_tcruzi_pde_rescue_operator_packet_ready_for_operator_review']}`",
        f"- broad_screen_tcruzi_pde_rescue_operator_packet_final_gate_pass: `{s['broad_screen_tcruzi_pde_rescue_operator_packet_final_gate_pass']}`",
        f"- broad_screen_tcruzi_pde_rescue_operator_packet_claim_gate_available: `{s['broad_screen_tcruzi_pde_rescue_operator_packet_claim_gate_available']}`",
        f"- broad_screen_tcruzi_pde_rescue_operator_packet_claim_ready_for_allatom: `{s['broad_screen_tcruzi_pde_rescue_operator_packet_claim_ready_for_allatom']}`",
        f"- selected_rescue_branch_ready_for_final_wetlab: `{s['selected_rescue_branch_ready_for_final_wetlab']}`",
        f"- selected_rescue_branch_operator_packet_ready: `{s['selected_rescue_branch_operator_packet_ready']}`",
        f"- selected_rescue_branch_operator_packet_ready_for_operator_review: `{s['selected_rescue_branch_operator_packet_ready_for_operator_review']}`",
        f"- selected_rescue_branch_operator_packet_final_gate_pass: `{s['selected_rescue_branch_operator_packet_final_gate_pass']}`",
        f"- selected_rescue_branch_operator_packet_claim_gate_available: `{s['selected_rescue_branch_operator_packet_claim_gate_available']}`",
        f"- selected_rescue_branch_operator_packet_claim_ready_for_allatom: `{s['selected_rescue_branch_operator_packet_claim_ready_for_allatom']}`",
        f"- selected_rescue_branch_operator_packet_scope: `{s['selected_rescue_branch_operator_packet_scope']}`",
        f"- selected_allatom_focus_available: `{s['selected_allatom_focus_available']}`",
        f"- selected_allatom_operator_review_ready_reported: `{s['selected_allatom_operator_review_ready_reported']}`",
        f"- selected_allatom_operator_review_ready: `{s['selected_allatom_operator_review_ready']}`",
        f"- selected_allatom_wetlab_gate_reported: `{s['selected_allatom_wetlab_gate_reported']}`",
        f"- selected_allatom_wetlab_gate_pass: `{s['selected_allatom_wetlab_gate_pass']}`",
        f"- selected_allatom_final_gate_reported: `{s['selected_allatom_final_gate_reported']}`",
        f"- selected_allatom_final_gate_pass: `{s['selected_allatom_final_gate_pass']}`",
        f"- selected_allatom_final_wetlab_ready: `{s['selected_allatom_final_wetlab_ready']}`",
        f"- selected_allatom_claim_gate_available_reported: `{s['selected_allatom_claim_gate_available_reported']}`",
        f"- selected_allatom_claim_gate_available: `{s['selected_allatom_claim_gate_available']}`",
        f"- selected_allatom_claim_ready_for_allatom_reported: `{s['selected_allatom_claim_ready_for_allatom_reported']}`",
        f"- selected_allatom_claim_ready_for_allatom: `{s['selected_allatom_claim_ready_for_allatom']}`",
        f"- selected_allatom_readiness_semantics: `{s['selected_allatom_readiness_semantics']}`",
        f"- selected_allatom_raw_claim_requirement_mode: `{s['selected_allatom_raw_claim_requirement_mode']}`",
        f"- selected_allatom_raw_claim_requirement_provenance: `{s['selected_allatom_raw_claim_requirement_provenance']}`",
        f"- selected_allatom_raw_claim_required_for_final_wetlab: `{s['selected_allatom_raw_claim_required_for_final_wetlab']}`",
        f"- selected_allatom_raw_claim_required_for_commercial_readiness: `{s['selected_allatom_raw_claim_required_for_commercial_readiness']}`",
        f"- selected_allatom_raw_claim_requirement_reason: `{s['selected_allatom_raw_claim_requirement_reason']}`",
        f"- selected_allatom_effective_actionability_status: `{s['selected_allatom_effective_actionability_status']}`",
        f"- selected_allatom_effective_actionability_claim_requirement_mode: `{s['selected_allatom_effective_actionability_claim_requirement_mode']}`",
        f"- selected_allatom_effective_actionability_claim_requirement_status: `{s['selected_allatom_effective_actionability_claim_requirement_status']}`",
        f"- selected_allatom_effective_actionability_claim_requirement_reason: `{s['selected_allatom_effective_actionability_claim_requirement_reason']}`",
        f"- selected_allatom_effective_actionability_next_expensive_lane: `{s['selected_allatom_effective_actionability_next_expensive_lane']}`",
        f"- selected_allatom_effective_actionability_next_expensive_lane_reason: `{s['selected_allatom_effective_actionability_next_expensive_lane_reason']}`",
        f"- selected_allatom_effective_actionability_required_calculations_text: `{s['selected_allatom_effective_actionability_required_calculations_text']}`",
        f"- selected_allatom_effective_actionability_action_list_text: `{s['selected_allatom_effective_actionability_action_list_text']}`",
        f"- selected_allatom_effective_blocking_order: `{s['selected_allatom_effective_blocking_order']}`",
        f"- selected_allatom_effective_primary_blocking_domain: `{s['selected_allatom_effective_primary_blocking_domain']}`",
        f"- selected_allatom_action_recipe_codes: `{', '.join(s['selected_allatom_action_recipe_codes'])}`",
        f"- selected_allatom_action_recipe_rollup_text: `{s['selected_allatom_action_recipe_rollup_text']}`",
        f"- selected_allatom_visual_bundle_ready: `{s['selected_allatom_visual_bundle_ready']}`",
        f"- selected_allatom_visual_human_summary: `{s['selected_allatom_visual_human_summary']}`",
        f"- selected_allatom_visual_primary_figure_path: `{s['selected_allatom_visual_primary_figure_path']}`",
        f"- selected_allatom_visual_primary_movie_script_path: `{s['selected_allatom_visual_primary_movie_script_path']}`",
        f"- selected_allatom_visual_primary_movie_mp4_path: `{s['selected_allatom_visual_primary_movie_mp4_path']}`",
        f"- selected_allatom_focus_label: `{s['selected_allatom_focus_label']}`",
        f"- selected_allatom_gate_rollup: `{s['selected_allatom_gate_rollup']}`",
        f"- selected_allatom_gate_detail_rollup: `{s['selected_allatom_gate_detail_rollup']}`",
        f"- selected_allatom_commercial_schema_version: `{s['selected_allatom_commercial_schema_version']}`",
        f"- selected_allatom_commercial_reported: `{s['selected_allatom_commercial_reported']}`",
        f"- selected_allatom_commercial_hard_gate_reported: `{s['selected_allatom_commercial_hard_gate_reported']}`",
        f"- selected_allatom_commercial_hard_gate_pass_v1: `{s['selected_allatom_commercial_hard_gate_pass_v1']}`",
        f"- selected_allatom_commercial_overall_score_v1: `{s['selected_allatom_commercial_overall_score_v1']}`",
        f"- selected_allatom_commercial_risk_bucket_v1: `{s['selected_allatom_commercial_risk_bucket_v1']}`",
        f"- selected_allatom_commercial_decision_class_v1: `{s['selected_allatom_commercial_decision_class_v1']}`",
        f"- selected_allatom_commercial_primary_upgrade_actions_v1: `{', '.join(s['selected_allatom_commercial_primary_upgrade_actions_v1'])}`",
        f"- selected_allatom_commercial_rollup: `{s['selected_allatom_commercial_rollup']}`",
        f"- selected_allatom_commercial_detail_rollup: `{s['selected_allatom_commercial_detail_rollup']}`",
        f"- selected_allatom_commercial_summary: `{s['selected_allatom_commercial_summary']}`",
        f"- selected_allatom_commercial_schema_version_v2: `{s['selected_allatom_commercial_schema_version_v2']}`",
        f"- selected_allatom_commercial_provenance_mode_v2: `{s['selected_allatom_commercial_provenance_mode_v2']}`",
        f"- selected_allatom_commercial_hard_gate_pass_v2: `{s['selected_allatom_commercial_hard_gate_pass_v2']}`",
        f"- selected_allatom_commercial_soft_score_v2: `{s['selected_allatom_commercial_soft_score_v2']}`",
        f"- selected_allatom_commercial_confidence_score_v2: `{s['selected_allatom_commercial_confidence_score_v2']}`",
        f"- selected_allatom_commercial_overall_score_v2: `{s['selected_allatom_commercial_overall_score_v2']}`",
        f"- selected_allatom_commercial_risk_bucket_v2: `{s['selected_allatom_commercial_risk_bucket_v2']}`",
        f"- selected_allatom_commercial_decision_class_v2: `{s['selected_allatom_commercial_decision_class_v2']}`",
        f"- selected_allatom_commercial_primary_upgrade_actions_v2: `{', '.join(s['selected_allatom_commercial_primary_upgrade_actions_v2'])}`",
        f"- selected_allatom_commercial_human_summary_v2: `{s['selected_allatom_commercial_human_summary_v2']}`",
        f"- selected_allatom_translation_gate_version: `{s['selected_allatom_translation_gate_version']}`",
        f"- selected_allatom_translation_gate_focus_status: `{s['selected_allatom_translation_gate_focus_status']}`",
        f"- selected_allatom_translation_gate_focus_score: `{s['selected_allatom_translation_gate_focus_score']}`",
        f"- selected_allatom_translation_gate_focus_reason: `{s['selected_allatom_translation_gate_focus_reason']}`",
        f"- selected_allatom_translation_provenance_mode: `{s['selected_allatom_translation_provenance_mode']}`",
        f"- selected_allatom_focus_shortlist_tier: `{s['selected_allatom_focus_shortlist_tier']}`",
        f"- selected_allatom_recommended_next_expensive_lane: `{s['selected_allatom_recommended_next_expensive_lane']}`",
        f"- selected_allatom_recommended_next_expensive_lane_reason: `{s['selected_allatom_recommended_next_expensive_lane_reason']}`",
        f"- selected_allatom_hybrid_policy: `{s['selected_allatom_hybrid_policy']}`",
        f"- selected_allatom_commercial_summary_v2: `{s['selected_allatom_commercial_summary_v2']}`",
        f"- selected_allatom_translation_summary: `{s['selected_allatom_translation_summary']}`",
        f"- selected_allatom_visual_bundle_ready: `{s['selected_allatom_visual_bundle_ready']}`",
        f"- selected_allatom_visual_availability_rollup: `{s['selected_allatom_visual_availability_rollup']}`",
        f"- selected_allatom_visual_media_ready_rollup: `{s['selected_allatom_visual_media_ready_rollup']}`",
        f"- selected_allatom_visual_human_summary: `{s['selected_allatom_visual_human_summary']}`",
        f"- selected_allatom_human_summary: `{s['selected_allatom_human_summary']}`",
        f"- broad_screen_recommended_execution_lane: `{s['broad_screen_recommended_execution_lane']}`",
        f"- broad_screen_library_size: `{s['broad_screen_library_size']}`",
        f"- broad_screen_ingested_compound_count: `{s['broad_screen_ingested_compound_count']}`",
        f"- broad_screen_coverage_gap_to_target_size: `{s['broad_screen_coverage_gap_to_target_size']}`",
        f"- broad_screen_override_target_count: `{s['broad_screen_override_target_count']}`",
        f"- broad_screen_override_row_count: `{s['broad_screen_override_row_count']}`",
        f"- broad_screen_full_bulk_ready_target_count: `{s['broad_screen_full_bulk_ready_target_count']}`",
        f"- broad_screen_partial_actual_target_count: `{s['broad_screen_partial_actual_target_count']}`",
        f"- broad_screen_stable_target_count: `{s['broad_screen_stable_target_count']}`",
        f"- broad_screen_antitarget_ready_now_row_count: `{s['broad_screen_antitarget_ready_now_row_count']}`",
        f"- broad_screen_antitarget_running_row_count: `{s['broad_screen_antitarget_running_row_count']}`",
        f"- broad_screen_antitarget_first_actionable_primary_target_id: `{s['broad_screen_antitarget_first_actionable_primary_target_id']}`",
        f"- broad_screen_antitarget_first_actionable_anti_target_id: `{s['broad_screen_antitarget_first_actionable_anti_target_id']}`",
        f"- broad_screen_next_target_id: `{s['broad_screen_next_target_id']}`",
        f"- broad_screen_target_count: `{s['broad_screen_target_count']}`",
        f"- broad_screen_shard_count_per_target: `{s['broad_screen_shard_count_per_target']}`",
        f"- broad_screen_total_queue_rows: `{s['broad_screen_total_queue_rows']}`",
        f"- broad_screen_execution_ready_now_row_count: `{s['broad_screen_execution_ready_now_row_count']}`",
        f"- broad_screen_execution_running_row_count: `{s['broad_screen_execution_running_row_count']}`",
        f"- broad_screen_execution_resolved_row_count: `{s['broad_screen_execution_resolved_row_count']}`",
        f"- broad_screen_first_actionable_target_id: `{s['broad_screen_first_actionable_target_id']}`",
        f"- broad_screen_first_actionable_shard_id: `{s['broad_screen_first_actionable_shard_id']}`",
        f"- broad_screen_first_actionable_queue_status: `{s['broad_screen_first_actionable_queue_status']}`",
        f"- priority3_transition_artifact_ready_count: `{s['priority3_transition_artifact_ready_count']}`",
        f"- priority3_ready_now_target_count: `{s['priority3_ready_now_target_count']}`",
        f"- priority3_running_target_count: `{s['priority3_running_target_count']}`",
        f"- priority3_resolved_target_count: `{s['priority3_resolved_target_count']}`",
        f"- next3_ready_now_target_count: `{s['next3_ready_now_target_count']}`",
        f"- next3_running_target_count: `{s['next3_running_target_count']}`",
        f"- next3_resolved_target_count: `{s['next3_resolved_target_count']}`",
        f"- final2_ready_now_target_count: `{s['final2_ready_now_target_count']}`",
        f"- final2_running_target_count: `{s['final2_running_target_count']}`",
        f"- final2_resolved_target_count: `{s['final2_resolved_target_count']}`",
        f"- wave2_ready_now_target_count: `{s['wave2_ready_now_target_count']}`",
        f"- wave2_running_target_count: `{s['wave2_running_target_count']}`",
        f"- wave2_resolved_target_count: `{s['wave2_resolved_target_count']}`",
        f"- master_ready_now_target_count: `{s['master_ready_now_target_count']}`",
        f"- master_blocked_on_previous_review_count: `{s['master_blocked_on_previous_review_count']}`",
        f"- master_blocked_on_target_content_count: `{s['master_blocked_on_target_content_count']}`",
        f"- master_first_actionable_target: `{s['master_first_actionable_target']}`",
        f"- master_first_actionable_chain: `{s['master_first_actionable_chain']}`",
        f"- campaign_terminal_state: `{s['campaign_terminal_state']}`",
        f"- ready_to_send_track_count: `{s['ready_to_send_track_count']}`",
        f"- outbound_first_priority_target: `{s['outbound_first_priority_target']}`",
        f"- outbound_follow_on_target_count: `{s['outbound_follow_on_target_count']}`",
        f"- final_campaign_top_outbound_targets: `{s['final_campaign_top_outbound_targets']}`",
        f"- first_dispatch_track_id: `{s['first_dispatch_track_id']}`",
        f"- first_dispatch_lead_targets: `{s['first_dispatch_lead_targets']}`",
        f"- overall_data_quality_band: `{s['overall_data_quality_band']}`",
        f"- partner_outreach_readiness: `{s['partner_outreach_readiness']}`",
        f"- therapeutic_claim_readiness: `{s['therapeutic_claim_readiness']}`",
        f"- master_wave2_release_gate_status: `{s['master_wave2_release_gate_status']}`",
        f"- master_wave2_release_blocked: `{s['master_wave2_release_blocked']}`",
        f"- master_wave2_ready: `{s['master_wave2_ready']}`",
        f"- master_wave2_queue_status: `{s['master_wave2_queue_status']}`",
        f"- active_stack_level: `{s['active_stack_level']}`",
        f"- active_target_id: `{s['active_target_id']}`",
        f"- active_target_queue_status: `{s['active_target_queue_status']}`",
        f"- active_target_execution_state: `{s['active_target_execution_state']}`",
        f"- stack_gate_states: `{s['stack_gate_states']}`",
        f"- lbdhodh_blockers: `{s['lbdhodh_blockers']}`",
        f"- stk17b_final2_queue_status: `{s['stk17b_final2_queue_status']}`",
        f"- lbdhodh_final2_queue_status: `{s['lbdhodh_final2_queue_status']}`",
        f"- lbdhodh_upstream_gate_open: `{s['lbdhodh_upstream_gate_open']}`",
        f"- lbdhodh_content_ready: `{s['lbdhodh_content_ready']}`",
        f"- cruzain_next3_queue_status: `{s['cruzain_next3_queue_status']}`",
        f"- plpro_next3_queue_status: `{s['plpro_next3_queue_status']}`",
        f"- alk2_next3_queue_status: `{s['alk2_next3_queue_status']}`",
        f"- mpro_execution_state: `{s['mpro_execution_state']}`",
        f"- mpro_run_record_detected: `{s['mpro_run_record_detected']}`",
        f"- caix_review_state: `{s['caix_review_state']}`",
        f"- caix_run_record_detected: `{s['caix_run_record_detected']}`",
        f"- caix_successor_gate_state: `{s['caix_successor_gate_state']}`",
        f"- tcruzi_result_review_gate_status: `{s['tcruzi_result_review_gate_status']}`",
        f"- tcruzi_run_record_detected: `{s['tcruzi_run_record_detected']}`",
        f"- tcruzi_execution_state: `{s['tcruzi_execution_state']}`",
        f"- tcruzi_run_record_queue_status: `{s['tcruzi_run_record_queue_status']}`",
        f"- tcruzi_wave2_release_gate_status: `{s['tcruzi_wave2_release_gate_status']}`",
        f"- tcruzi_wave2_release_blocked: `{s['tcruzi_wave2_release_blocked']}`",
        f"- wave2_first_target: `{s['wave2_first_target']}`",
        f"- wave2_queue_target_count: `{s['wave2_queue_target_count']}`",
        f"- wave2_missing_target_specific_packet_count: `{s['wave2_missing_target_specific_packet_count']}`",
        f"- wave1_packet_queue_ready: `{s['wave1_packet_queue_ready']}`",
        f"- one_page_brief_starters_ready: `{s['one_page_brief_starters_ready']}`",
        f"- target_brief_index_ready: `{s['target_brief_index_ready']}`",
        f"- brief_fill_queue_ready: `{s['brief_fill_queue_ready']}`",
        f"- first_contact_bundle_ready: `{s['first_contact_bundle_ready']}`",
        f"- priority3_repurposing_fill_ready: `{s['priority3_repurposing_fill_ready']}`",
        f"- priority3_novelty_fill_ready: `{s['priority3_novelty_fill_ready']}`",
        f"- next3_repurposing_fill_ready: `{s['next3_repurposing_fill_ready']}`",
        f"- next3_novelty_fill_ready: `{s['next3_novelty_fill_ready']}`",
        f"- mpro_vendor_cost_check_ready: `{s['mpro_vendor_cost_check_ready']}`",
        f"- first_contact_export_bundle_ready: `{s['first_contact_export_bundle_ready']}`",
        f"- cleanup_manifest_ready: `{s['cleanup_manifest_ready']}`",
        "",
        "## Open Order",
        "",
        f"1. `{s['open_first']}`",
        f"2. `{s['open_second']}`",
        f"3. `{s['open_third']}`",
        f"4. `{s['open_fourth']}`",
        f"5. `{s['open_fifth']}`",
        f"6. `{s['open_sixth']}`",
        f"7. `{s['open_seventh']}`",
        f"8. `{s['open_eighth']}`",
        f"9. `{s['open_ninth']}`",
        f"10. `{s['open_tenth']}`",
        f"11. `{s['open_eleventh']}`",
        f"12. `{s['open_twelfth']}`",
        f"13. `{s['open_thirteenth']}`",
        f"14. `{s['open_fourteenth']}`",
        f"15. `{s['open_fifteenth']}`",
        f"16. `{s['open_sixteenth']}`",
        f"17. `{s['open_seventeenth']}`",
        f"18. `{s['open_eighteenth']}`",
        f"19. `{s['open_nineteenth']}`",
        f"20. `{s['open_twentieth']}`",
        f"21. `{s['open_twentyfirst']}`",
        f"22. `{s['open_twentisecond']}`",
        f"23. `{s['open_twentythird']}`",
        f"24. `{s['open_twentyfourth']}`",
        f"25. `{s['open_twentyfifth']}`",
        f"26. `{s['open_twentysixth']}`",
        f"27. `{s['open_twentyseventh']}`",
        f"28. `{s['open_twentyeighth']}`",
        f"29. `{s['open_twentyninth']}`",
        f"30. `{s['open_thirtieth']}`",
        f"31. `{s['open_thirtyfirst']}`",
        f"32. `{s['open_thirtysecond']}`",
        f"33. `{s['open_thirtythird']}`",
        f"34. `{s['open_thirtyfourth']}`",
        f"35. `{s['open_thirtyfifth']}`",
        f"36. `{s['open_thirtysixth']}`",
        f"37. `{s['open_thirtyseventh']}`",
        f"38. `{s['open_thirtyeighth']}`",
        f"39. `{s['open_thirtyninth']}`",
        f"40. `{s['open_fortieth']}`",
        f"41. `{s['open_fortyfirst']}`",
        f"42. `{s['open_fortysecond']}`",
        f"43. `{s['open_fortythird']}`",
        f"44. `{s['open_fortyfourth']}`",
        f"45. `{s['open_fortyfifth']}`",
        f"46. `{s['open_fortysixth']}`",
        f"47. `{s['open_fortyseventh']}`",
        f"48. `{s['open_fortyeighth']}`",
        f"49. `{s['open_fortyninth']}`",
        f"50. `{s['open_fiftieth']}`",
        f"51. `{s['open_fiftyfirst']}`",
        f"52. `{s['open_fiftysecond']}`",
        f"53. `{s['open_fiftythird']}`",
        f"54. `{s['open_fiftyfourth']}`",
        f"55. `{s['open_fiftyfifth']}`",
        f"56. `{s['open_fiftysixth']}`",
        f"57. `{s['open_fiftyseventh']}`",
        f"58. `{s['open_fiftyeighth']}`",
        f"59. `{s['open_fiftyninth']}`",
        f"60. `{s['open_sixtieth']}`",
        f"61. `{s['open_sixtyfirst']}`",
        f"62. `{s['open_sixtysecond']}`",
        f"63. `{s['open_sixtythird']}`",
        f"64. `{s['open_sixtyfourth']}`",
        f"65. `{s['open_sixtyfifth']}`",
        f"66. `{s['open_sixtysixth']}`",
        f"67. `{s['open_sixtyseventh']}`",
        f"68. `{s['open_sixtyeighth']}`",
        f"69. `{s['open_sixtyninth']}`",
        f"70. `{s['open_seventieth']}`",
        f"71. `{s['open_seventyfirst']}`",
        f"72. `{s['open_seventysecond']}`",
        f"73. `{s['open_seventythird']}`",
        f"74. `{s['open_seventyfourth']}`",
        f"75. `{s['open_eightysecond_target_retry']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the wet-lab partnering stack index.")
    parser.add_argument("--portfolio-json", default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument("--blueprint-json", default=DEFAULT_BLUEPRINT_JSON)
    parser.add_argument("--brief-matrix-json", default=DEFAULT_BRIEF_MATRIX_JSON)
    parser.add_argument("--companion-json", default=DEFAULT_COMPANION_JSON)
    parser.add_argument("--outreach-json", default=DEFAULT_OUTREACH_JSON)
    parser.add_argument("--rail-packet-index-json", default=DEFAULT_RAIL_PACKET_INDEX_JSON)
    parser.add_argument("--schema-json", default=DEFAULT_SCHEMA_JSON)
    parser.add_argument("--domain-generation-schema-json", default=DEFAULT_DOMAIN_GENERATION_SCHEMA_JSON)
    parser.add_argument("--partner-export-schema-json", default=DEFAULT_PARTNER_EXPORT_SCHEMA_JSON)
    parser.add_argument("--priority3-render-split-json", default=DEFAULT_PRIORITY3_RENDER_SPLIT_JSON)
    parser.add_argument("--mpro-render-suite-json", default=DEFAULT_MPRO_RENDER_SUITE_JSON)
    parser.add_argument("--caix-render-suite-json", default=DEFAULT_CAIX_RENDER_SUITE_JSON)
    parser.add_argument("--tcruzi-pde-render-suite-json", default=DEFAULT_TCRUZI_PDE_RENDER_SUITE_JSON)
    parser.add_argument("--prep-artifact-lane-json", default=DEFAULT_PREP_ARTIFACT_LANE_JSON)
    parser.add_argument("--priority3-run-queue-json", default=DEFAULT_PRIORITY3_RUN_QUEUE_JSON)
    parser.add_argument("--mpro-launch-packet-json", default=DEFAULT_MPRO_LAUNCH_PACKET_JSON)
    parser.add_argument("--caix-launch-packet-json", default=DEFAULT_CAIX_LAUNCH_PACKET_JSON)
    parser.add_argument("--tcruzi-pde-launch-packet-json", default=DEFAULT_TCRUZI_PDE_LAUNCH_PACKET_JSON)
    parser.add_argument("--mpro-run-record-json", default=DEFAULT_MPRO_RUN_RECORD_JSON)
    parser.add_argument("--caix-run-record-json", default=DEFAULT_CAIX_RUN_RECORD_JSON)
    parser.add_argument("--tcruzi-pde-run-record-json", default=DEFAULT_TCRUZI_PDE_RUN_RECORD_JSON)
    parser.add_argument("--mpro-run-status-json", default=DEFAULT_MPRO_RUN_STATUS_JSON)
    parser.add_argument("--caix-result-review-json", default=DEFAULT_CAIX_RESULT_REVIEW_JSON)
    parser.add_argument("--tcruzi-pde-result-review-json", default=DEFAULT_TCRUZI_PDE_RESULT_REVIEW_JSON)
    parser.add_argument("--priority3-runtime-event-json", default=DEFAULT_PRIORITY3_RUNTIME_EVENT_JSON)
    parser.add_argument("--priority3-runtime-runbook-json", default=DEFAULT_PRIORITY3_RUNTIME_RUNBOOK_JSON)
    parser.add_argument("--next3-run-queue-json", default=DEFAULT_NEXT3_RUN_QUEUE_JSON)
    parser.add_argument("--next3-chain-stack-json", default=DEFAULT_NEXT3_CHAIN_STACK_JSON)
    parser.add_argument("--next3-runtime-event-json", default=DEFAULT_NEXT3_RUNTIME_EVENT_JSON)
    parser.add_argument("--next3-runtime-runbook-json", default=DEFAULT_NEXT3_RUNTIME_RUNBOOK_JSON)
    parser.add_argument("--next3-execution-console-json", default=DEFAULT_NEXT3_EXECUTION_CONSOLE_JSON)
    parser.add_argument("--final2-run-queue-json", default=DEFAULT_FINAL2_RUN_QUEUE_JSON)
    parser.add_argument("--final2-chain-stack-json", default=DEFAULT_FINAL2_CHAIN_STACK_JSON)
    parser.add_argument("--final2-runtime-event-json", default=DEFAULT_FINAL2_RUNTIME_EVENT_JSON)
    parser.add_argument("--final2-runtime-runbook-json", default=DEFAULT_FINAL2_RUNTIME_RUNBOOK_JSON)
    parser.add_argument("--final2-execution-console-json", default=DEFAULT_FINAL2_EXECUTION_CONSOLE_JSON)
    parser.add_argument("--wave2-run-queue-json", default=DEFAULT_WAVE2_RUN_QUEUE_JSON)
    parser.add_argument("--wave2-chain-stack-json", default=DEFAULT_WAVE2_CHAIN_STACK_JSON)
    parser.add_argument("--wave2-runtime-event-json", default=DEFAULT_WAVE2_RUNTIME_EVENT_JSON)
    parser.add_argument("--wave2-runtime-runbook-json", default=DEFAULT_WAVE2_RUNTIME_RUNBOOK_JSON)
    parser.add_argument("--wave2-execution-console-json", default=DEFAULT_WAVE2_EXECUTION_CONSOLE_JSON)
    parser.add_argument("--master-queue-json", default=DEFAULT_MASTER_QUEUE_JSON)
    parser.add_argument("--master-runtime-runbook-json", default=DEFAULT_MASTER_RUNTIME_RUNBOOK_JSON)
    parser.add_argument("--master-execution-console-json", default=DEFAULT_MASTER_EXECUTION_CONSOLE_JSON)
    parser.add_argument("--master-terminal-review-json", default=DEFAULT_MASTER_TERMINAL_REVIEW_JSON)
    parser.add_argument("--outbound-execution-priority-board-json", default=DEFAULT_OUTBOUND_EXECUTION_PRIORITY_BOARD_JSON)
    parser.add_argument("--final-campaign-summary-json", default=DEFAULT_FINAL_CAMPAIGN_SUMMARY_JSON)
    parser.add_argument("--partner-send-round-json", default=DEFAULT_PARTNER_SEND_ROUND_JSON)
    parser.add_argument("--master-handoff-dashboard-json", default=DEFAULT_MASTER_HANDOFF_DASHBOARD_JSON)
    parser.add_argument("--data-quality-assessment-json", default=DEFAULT_DATA_QUALITY_ASSESSMENT_JSON)
    parser.add_argument("--broad-screen-library-spec-json", default=DEFAULT_BROAD_SCREEN_LIBRARY_SPEC_JSON)
    parser.add_argument("--broad-screen-queue-json", default=DEFAULT_BROAD_SCREEN_QUEUE_JSON)
    parser.add_argument("--broad-screen-bridge-json", default=DEFAULT_BROAD_SCREEN_BRIDGE_JSON)
    parser.add_argument("--broad-screen-compound-universe-json", default=DEFAULT_BROAD_SCREEN_COMPOUND_UNIVERSE_JSON)
    parser.add_argument("--broad-screen-bulk-results-json", default=DEFAULT_BROAD_SCREEN_BULK_RESULTS_JSON)
    parser.add_argument("--broad-screen-repurposing-autofill-json", default=DEFAULT_BROAD_SCREEN_REPURPOSING_AUTOFILL_JSON)
    parser.add_argument("--broad-screen-execution-queue-json", default=DEFAULT_BROAD_SCREEN_EXECUTION_QUEUE_JSON)
    parser.add_argument("--broad-screen-runtime-runbook-json", default=DEFAULT_BROAD_SCREEN_RUNTIME_RUNBOOK_JSON)
    parser.add_argument("--broad-screen-bulk-result-source-schema-json", default=DEFAULT_BROAD_SCREEN_BULK_RESULT_SOURCE_SCHEMA_JSON)
    parser.add_argument("--broad-screen-bulk-result-row-examples-json", default=DEFAULT_BROAD_SCREEN_BULK_RESULT_ROW_EXAMPLES_JSON)
    parser.add_argument("--broad-screen-target-rerank-json", default=DEFAULT_BROAD_SCREEN_TARGET_RERANK_JSON)
    parser.add_argument("--broad-screen-stability-score-json", default=DEFAULT_BROAD_SCREEN_STABILITY_SCORE_JSON)
    parser.add_argument("--broad-screen-antitarget-queue-json", default=DEFAULT_BROAD_SCREEN_ANTITARGET_QUEUE_JSON)
    parser.add_argument("--broad-screen-antitarget-execution-queue-json", default=DEFAULT_BROAD_SCREEN_ANTITARGET_EXECUTION_QUEUE_JSON)
    parser.add_argument("--broad-screen-primary-watch-state-json", default=DEFAULT_BROAD_SCREEN_PRIMARY_WATCH_STATE_JSON)
    parser.add_argument("--broad-screen-primary-watch-json", default=DEFAULT_BROAD_SCREEN_PRIMARY_WATCH_JSON)
    parser.add_argument("--broad-screen-antitarget-watch-state-json", default=DEFAULT_BROAD_SCREEN_ANTITARGET_WATCH_STATE_JSON)
    parser.add_argument("--broad-screen-antitarget-watch-json", default=DEFAULT_BROAD_SCREEN_ANTITARGET_WATCH_JSON)
    parser.add_argument("--broad-screen-actual-append-json", default=DEFAULT_BROAD_SCREEN_ACTUAL_APPEND_JSON)
    parser.add_argument("--broad-screen-next-target-extension-json", default=DEFAULT_BROAD_SCREEN_NEXT_TARGET_EXTENSION_JSON)
    parser.add_argument("--broad-screen-throughput-bridge-json", default=DEFAULT_BROAD_SCREEN_THROUGHPUT_BRIDGE_JSON)
    parser.add_argument("--broad-screen-primary-retry-preset-json", default=DEFAULT_BROAD_SCREEN_PRIMARY_RETRY_PRESET_JSON)
    parser.add_argument("--broad-screen-primary-hold-guard-json", default=DEFAULT_BROAD_SCREEN_PRIMARY_HOLD_GUARD_JSON)
    parser.add_argument("--broad-screen-current-results-index-json", default=DEFAULT_BROAD_SCREEN_CURRENT_RESULTS_INDEX_JSON)
    parser.add_argument("--broad-screen-monitor-semantics-json", default=DEFAULT_BROAD_SCREEN_MONITOR_SEMANTICS_JSON)
    parser.add_argument("--broad-screen-retry-handoff-summary-json", default=DEFAULT_BROAD_SCREEN_RETRY_HANDOFF_SUMMARY_JSON)
    parser.add_argument("--broad-screen-selected-allatom-visual-bundle-json", default=DEFAULT_BROAD_SCREEN_SELECTED_ALLATOM_VISUAL_BUNDLE_JSON)
    parser.add_argument("--broad-screen-dpre1-branch-review-surface-json", default=DEFAULT_BROAD_SCREEN_DPRE1_BRANCH_REVIEW_SURFACE_JSON)
    parser.add_argument("--broad-screen-stk17b-manual-retry-lane-json", default=DEFAULT_BROAD_SCREEN_STK17B_MANUAL_RETRY_LANE_JSON)
    parser.add_argument("--broad-screen-stk17b-exploratory-retry-lane-json", default=DEFAULT_BROAD_SCREEN_STK17B_EXPLORATORY_RETRY_LANE_JSON)
    parser.add_argument("--broad-screen-stk17b-exploratory-followup-lane-json", default=DEFAULT_BROAD_SCREEN_STK17B_EXPLORATORY_FOLLOWUP_LANE_JSON)
    parser.add_argument("--broad-screen-stk17b-followup-review-surface-json", default=DEFAULT_BROAD_SCREEN_STK17B_FOLLOWUP_REVIEW_SURFACE_JSON)
    parser.add_argument("--broad-screen-plpro-manual-retry-lane-json", default=DEFAULT_BROAD_SCREEN_PLPRO_MANUAL_RETRY_LANE_JSON)
    parser.add_argument("--broad-screen-mapping-fix-retry-support-json", default=DEFAULT_BROAD_SCREEN_MAPPING_FIX_RETRY_SUPPORT_JSON)
    parser.add_argument("--broad-screen-stage1-mapping-fix-lanes-json", default=DEFAULT_BROAD_SCREEN_STAGE1_MAPPING_FIX_LANES_JSON)
    parser.add_argument("--broad-screen-mapping-fix-retry-policy-templates-json", default=DEFAULT_BROAD_SCREEN_MAPPING_FIX_RETRY_POLICY_TEMPLATES_JSON)
    parser.add_argument("--broad-screen-hard-target-rescue-lane-json", default=DEFAULT_BROAD_SCREEN_HARD_TARGET_RESCUE_LANE_JSON)
    parser.add_argument("--broad-screen-rescue-anchor-artifacts-json", default=DEFAULT_BROAD_SCREEN_RESCUE_ANCHOR_ARTIFACTS_JSON)
    parser.add_argument("--broad-screen-rescue-three-bead-candidates-json", default=DEFAULT_BROAD_SCREEN_RESCUE_THREE_BEAD_CANDIDATES_JSON)
    parser.add_argument("--broad-screen-tcruzi-pde-promoted-top4-review-packet-json", default=DEFAULT_BROAD_SCREEN_TCRUZI_PDE_PROMOTED_TOP4_REVIEW_PACKET_JSON)
    parser.add_argument("--broad-screen-tcruzi-pde-rescue-only-branch-summary-json", default=DEFAULT_BROAD_SCREEN_TCRUZI_PDE_RESCUE_ONLY_BRANCH_SUMMARY_JSON)
    parser.add_argument("--broad-screen-kinase-retry-policy-templates-json", default=DEFAULT_BROAD_SCREEN_KINASE_RETRY_POLICY_TEMPLATES_JSON)
    parser.add_argument("--broad-screen-target-retry-policy-templates-json", default=DEFAULT_BROAD_SCREEN_TARGET_RETRY_POLICY_TEMPLATES_JSON)
    parser.add_argument("--broad-screen-dengue-stage6-tuning-surface-json", default=DEFAULT_BROAD_SCREEN_DENGUE_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--broad-screen-dengue-exploratory-retry-lane-json", default=DEFAULT_BROAD_SCREEN_DENGUE_EXPLORATORY_RETRY_LANE_JSON)
    parser.add_argument("--broad-screen-lbdhodh-stage6-tuning-surface-json", default=DEFAULT_BROAD_SCREEN_LBDHODH_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--broad-screen-lbdhodh-exploratory-retry-lane-json", default=DEFAULT_BROAD_SCREEN_LBDHODH_EXPLORATORY_RETRY_LANE_JSON)
    parser.add_argument("--broad-screen-lbdhodh-gate51-validation-review-surface-json", default=DEFAULT_BROAD_SCREEN_LBDHODH_GATE51_VALIDATION_REVIEW_SURFACE_JSON)
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    parser.add_argument("--one-page-briefs-json", default=DEFAULT_ONE_PAGE_BRIEFS_JSON)
    parser.add_argument("--brief-index-json", default=DEFAULT_BRIEF_INDEX_JSON)
    parser.add_argument("--fill-queue-json", default=DEFAULT_FILL_QUEUE_JSON)
    parser.add_argument("--first-contact-json", default=DEFAULT_FIRST_CONTACT_JSON)
    parser.add_argument("--priority3-fill-map-json", default=DEFAULT_PRIORITY3_FILL_MAP_JSON)
    parser.add_argument("--priority3-novelty-fill-map-json", default=DEFAULT_PRIORITY3_NOVELTY_FILL_MAP_JSON)
    parser.add_argument("--next3-fill-map-json", default=DEFAULT_NEXT3_FILL_MAP_JSON)
    parser.add_argument("--next3-novelty-fill-map-json", default=DEFAULT_NEXT3_NOVELTY_FILL_MAP_JSON)
    parser.add_argument("--mpro-vendor-cost-check-json", default=DEFAULT_MPRO_VENDOR_COST_CHECK_JSON)
    parser.add_argument("--first-contact-export-json", default=DEFAULT_FIRST_CONTACT_EXPORT_JSON)
    parser.add_argument("--cleanup-manifest-json", default=DEFAULT_CLEANUP_MANIFEST_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.portfolio_json),
        _load_json(args.blueprint_json),
        _load_json(args.brief_matrix_json),
        _load_json(args.companion_json),
        _load_json(args.outreach_json),
        _load_json(args.rail_packet_index_json),
        _load_json(args.schema_json),
        _load_json(args.queue_json),
        _load_json(args.one_page_briefs_json),
        _load_json(args.brief_index_json),
        _load_json(args.fill_queue_json),
        _load_json(args.first_contact_json),
        _load_json(args.priority3_fill_map_json),
        _load_json(args.priority3_novelty_fill_map_json),
        _maybe_load_json(args.next3_fill_map_json),
        _maybe_load_json(args.next3_novelty_fill_map_json),
        _load_json(args.mpro_vendor_cost_check_json),
        _maybe_load_json(args.first_contact_export_json),
        _maybe_load_json(args.cleanup_manifest_json),
        _maybe_load_json(args.domain_generation_schema_json),
        _maybe_load_json(args.partner_export_schema_json),
        _maybe_load_json(args.priority3_render_split_json),
        _maybe_load_json(args.mpro_render_suite_json),
        _maybe_load_json(args.caix_render_suite_json),
        _maybe_load_json(args.tcruzi_pde_render_suite_json),
        _maybe_load_json(args.prep_artifact_lane_json),
        _maybe_load_json(args.priority3_run_queue_json),
        _maybe_load_json(args.mpro_launch_packet_json),
        _maybe_load_json(args.caix_launch_packet_json),
        _maybe_load_json(args.tcruzi_pde_launch_packet_json),
        _maybe_load_json(args.mpro_run_record_json),
        _maybe_load_json(args.caix_run_record_json),
        _maybe_load_json(args.tcruzi_pde_run_record_json),
        _maybe_load_json(args.mpro_run_status_json),
        _maybe_load_json(args.caix_result_review_json),
        _maybe_load_json(args.tcruzi_pde_result_review_json),
        _maybe_load_json(args.priority3_runtime_event_json),
        _maybe_load_json(args.priority3_runtime_runbook_json),
        _maybe_load_json(args.next3_run_queue_json),
        _maybe_load_json(args.next3_chain_stack_json),
        _maybe_load_json(args.next3_runtime_event_json),
        _maybe_load_json(args.next3_runtime_runbook_json),
        _maybe_load_json(args.next3_execution_console_json),
        _maybe_load_json(args.final2_run_queue_json),
        _maybe_load_json(args.final2_chain_stack_json),
        _maybe_load_json(args.final2_runtime_event_json),
        _maybe_load_json(args.final2_runtime_runbook_json),
        _maybe_load_json(args.final2_execution_console_json),
        _maybe_load_json(args.wave2_run_queue_json),
        _maybe_load_json(args.wave2_chain_stack_json),
        _maybe_load_json(args.wave2_runtime_event_json),
        _maybe_load_json(args.wave2_runtime_runbook_json),
        _maybe_load_json(args.wave2_execution_console_json),
        _maybe_load_json(args.master_queue_json),
        _maybe_load_json(args.master_runtime_runbook_json),
        _maybe_load_json(args.master_execution_console_json),
        _maybe_load_json(args.master_terminal_review_json),
        _maybe_load_json(args.outbound_execution_priority_board_json),
        _maybe_load_json(args.final_campaign_summary_json),
        _maybe_load_json(args.partner_send_round_json),
        _maybe_load_json(args.master_handoff_dashboard_json),
        _maybe_load_json(args.data_quality_assessment_json),
        _maybe_load_json(args.broad_screen_library_spec_json),
        _maybe_load_json(args.broad_screen_queue_json),
        _maybe_load_json(args.broad_screen_bridge_json),
        _maybe_load_json(args.broad_screen_compound_universe_json),
        _maybe_load_json(args.broad_screen_bulk_results_json),
        _maybe_load_json(args.broad_screen_repurposing_autofill_json),
        _maybe_load_json(args.broad_screen_execution_queue_json),
        _maybe_load_json(args.broad_screen_runtime_runbook_json),
        _maybe_load_json(args.broad_screen_bulk_result_source_schema_json),
        _maybe_load_json(args.broad_screen_bulk_result_row_examples_json),
        _maybe_load_json(args.broad_screen_target_rerank_json),
        _maybe_load_json(args.broad_screen_stability_score_json),
        _maybe_load_json(args.broad_screen_antitarget_queue_json),
        _maybe_load_json(args.broad_screen_antitarget_execution_queue_json),
        _maybe_load_json(args.broad_screen_primary_watch_state_json) or _maybe_load_json(LEGACY_BROAD_SCREEN_PRIMARY_WATCH_STATE_JSON),
        _maybe_load_json(args.broad_screen_primary_watch_json) or _maybe_load_json(LEGACY_BROAD_SCREEN_PRIMARY_WATCH_JSON),
        _maybe_load_json(args.broad_screen_antitarget_watch_state_json),
        _maybe_load_json(args.broad_screen_antitarget_watch_json),
        _maybe_load_json(args.broad_screen_actual_append_json),
        _maybe_load_json(args.broad_screen_next_target_extension_json),
        _maybe_load_json(args.broad_screen_throughput_bridge_json),
        _maybe_load_json(args.broad_screen_primary_retry_preset_json),
        _maybe_load_json(args.broad_screen_primary_hold_guard_json),
        _maybe_load_json(args.broad_screen_current_results_index_json),
        _maybe_load_json(args.broad_screen_monitor_semantics_json),
        _maybe_load_json(args.broad_screen_retry_handoff_summary_json),
        _maybe_load_json(args.broad_screen_dpre1_branch_review_surface_json),
        _maybe_load_json(args.broad_screen_stk17b_manual_retry_lane_json),
        _maybe_load_json(args.broad_screen_stk17b_exploratory_retry_lane_json),
        _maybe_load_json(args.broad_screen_stk17b_exploratory_followup_lane_json),
        _maybe_load_json(args.broad_screen_stk17b_followup_review_surface_json),
        _maybe_load_json(args.broad_screen_plpro_manual_retry_lane_json),
        _maybe_load_json(args.broad_screen_mapping_fix_retry_support_json),
        _maybe_load_json(args.broad_screen_stage1_mapping_fix_lanes_json),
        _maybe_load_json(args.broad_screen_mapping_fix_retry_policy_templates_json),
        _maybe_load_json(args.broad_screen_hard_target_rescue_lane_json),
        _maybe_load_json(args.broad_screen_rescue_anchor_artifacts_json),
        _maybe_load_json(args.broad_screen_rescue_three_bead_candidates_json),
        _maybe_load_json(args.broad_screen_tcruzi_pde_promoted_top4_review_packet_json),
        _maybe_load_json(args.broad_screen_tcruzi_pde_rescue_only_branch_summary_json),
        _maybe_load_json(args.broad_screen_kinase_retry_policy_templates_json),
        _maybe_load_json(args.broad_screen_target_retry_policy_templates_json),
        _maybe_load_json(args.broad_screen_dengue_stage6_tuning_surface_json),
        _maybe_load_json(args.broad_screen_dengue_exploratory_retry_lane_json),
        _maybe_load_json(args.broad_screen_lbdhodh_stage6_tuning_surface_json),
        _maybe_load_json(args.broad_screen_lbdhodh_exploratory_retry_lane_json),
        _maybe_load_json(args.broad_screen_lbdhodh_gate51_validation_review_surface_json),
        _maybe_load_json(args.broad_screen_selected_allatom_visual_bundle_json),
    )
    out_json = _resolve_output(args.out_json)
    out_md = _resolve_output(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
