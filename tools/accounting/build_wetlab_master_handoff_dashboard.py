#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Any

try:
    from tools.wetlab.wetlab_selected_allatom_canonical import (
        resolve_selected_allatom_canonical,
        selected_allatom_green_next_required_step,
    )
except ModuleNotFoundError:
    def resolve_selected_allatom_canonical(**_: Any) -> dict[str, Any]:
        raise NotImplementedError("selected_allatom canonical resolver is not available")

    def selected_allatom_green_next_required_step(
        *,
        wetlab_gate_pass: bool,
        final_gate_pass: bool,
        claim_ready_for_allatom: bool,
        translation_gate_focus_status: Any = "",
        recommended_next_expensive_lane: Any = "",
        fallback_next_required_step: Any = "",
    ) -> str:
        return str(fallback_next_required_step or "").strip()
from tools.wetlab.wetlab_selected_allatom_visual import (
    resolve_selected_allatom_visual_bundle,
    selected_allatom_visual_surface_fields,
)

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FINAL_CAMPAIGN_SUMMARY_JSON = "runs/wetlab_final_campaign_summary_current.json"
DEFAULT_MASTER_TERMINAL_REVIEW_JSON = "runs/wetlab_master_terminal_review_current.json"
DEFAULT_OUTBOUND_BOARD_JSON = "runs/wetlab_outbound_execution_priority_board_current.json"
DEFAULT_SEND_ROUND_JSON = "runs/wetlab_partner_send_round_current.json"
DEFAULT_EXPORT_BUNDLE_JSON = "runs/wetlab_partner_first_contact_export_bundle_current.json"
DEFAULT_BROAD_SCREEN_QUEUE_JSON = "runs/wetlab_broad_screen_queue_current.json"
DEFAULT_BROAD_SCREEN_BRIDGE_JSON = "runs/wetlab_broad_screen_bridge_current.json"
DEFAULT_BROAD_SCREEN_COMPOUND_UNIVERSE_JSON = "runs/wetlab_broad_screen_compound_universe_current.json"
DEFAULT_BROAD_SCREEN_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_BROAD_SCREEN_REPURPOSING_AUTOFILL_JSON = "runs/wetlab_broad_screen_repurposing_autofill_current.json"
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
DEFAULT_BROAD_SCREEN_THROUGHPUT_BRIDGE_JSON = "runs/wetlab_broad_screen_throughput_bridge_current.json"
DEFAULT_BROAD_SCREEN_PRIMARY_RETRY_PRESET_JSON = "runs/wetlab_primary_retry_preset_surface_current.json"
DEFAULT_BROAD_SCREEN_PRIMARY_HOLD_GUARD_JSON = "runs/wetlab_primary_hold_guard_surface_current.json"
DEFAULT_BROAD_SCREEN_CURRENT_RESULTS_INDEX_JSON = "runs/wetlab_current_results_index_current.json"
DEFAULT_BROAD_SCREEN_MONITOR_SEMANTICS_JSON = "runs/wetlab_monitor_semantics_current.json"
DEFAULT_BROAD_SCREEN_RETRY_HANDOFF_SUMMARY_JSON = "runs/wetlab_retry_handoff_summary_current.json"
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
DEFAULT_BROAD_SCREEN_KINASE_RETRY_POLICY_TEMPLATES_JSON = "runs/wetlab_kinase_retry_policy_templates_current.json"
DEFAULT_BROAD_SCREEN_TARGET_RETRY_POLICY_TEMPLATES_JSON = "runs/wetlab_target_retry_policy_templates_current.json"
DEFAULT_BROAD_SCREEN_DENGUE_STAGE6_TUNING_SURFACE_JSON = "runs/wetlab_dengue_ns2b_ns3_protease_stage6_tuning_surface_current.json"
DEFAULT_BROAD_SCREEN_DENGUE_EXPLORATORY_RETRY_LANE_JSON = "runs/wetlab_dengue_ns2b_ns3_protease_exploratory_retry_lane_current.json"
DEFAULT_BROAD_SCREEN_LBDHODH_STAGE6_TUNING_SURFACE_JSON = "runs/wetlab_lbdhodh_stage6_tuning_surface_current.json"
DEFAULT_BROAD_SCREEN_LBDHODH_EXPLORATORY_RETRY_LANE_JSON = "runs/wetlab_lbdhodh_exploratory_retry_lane_current.json"
DEFAULT_BROAD_SCREEN_LBDHODH_GATE51_VALIDATION_REVIEW_SURFACE_JSON = "runs/wetlab_lbdhodh_gate51_validation_review_surface_current.json"
DEFAULT_BROAD_SCREEN_TCRUZI_PDE_PROMOTED_TOP4_REVIEW_PACKET_JSON = "runs/wetlab_tcruzi_pde_promoted_top4_review_packet_current.json"
DEFAULT_BROAD_SCREEN_TCRUZI_PDE_RESCUE_ONLY_BRANCH_SUMMARY_JSON = "runs/wetlab_tcruzi_pde_rescue_only_branch_summary_current.json"
DEFAULT_BROAD_SCREEN_SELECTED_ALLATOM_VISUAL_BUNDLE_JSON = "runs/selected_allatom_visual_bundle_current.json"
DEFAULT_OUT_MD = "runs/wetlab_master_handoff_dashboard_current.md"
SEMI_HARD_CLAIM_TARGETS = {
    "T. cruzi PDE",
    "T. cruzi KRS1",
    "Leishmania braziliensis DHODH",
    "DprE1",
    "Dengue NS2B-NS3 protease",
}


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except Exception:
        return default


def _joined(*values: Any, sep: str = " | ", default: str = "") -> str:
    parts = [str(value or "").strip() for value in values if str(value or "").strip()]
    return sep.join(parts) if parts else default


def _selected_allatom_inferred_next_expensive_lane(*texts: Any) -> str:
    combined = " ".join(
        str(text or "").strip().lower() for text in texts if str(text or "").strip()
    )
    if not combined:
        return ""
    if "defer_expensive_lane" in combined or "defer expensive lane" in combined:
        return "defer_expensive_lane"
    if "enter_expensive_lane" in combined or "enter expensive lane" in combined:
        return "enter_expensive_lane"
    return ""


def _infer_selected_allatom_translation_shortlist_fallback(*texts: Any) -> dict[str, Any]:
    joined = " ".join(str(text or "").strip() for text in texts if str(text or "").strip())
    if not joined:
        return {
            "reported": False,
            "translation_gate_focus_status": "",
            "focus_shortlist_tier": "",
            "recommended_next_expensive_lane": "",
            "recommended_next_expensive_lane_reason": "",
        }
    translation_match = re.search(
        r"translation_gate=([A-Za-z0-9_]+)|translation gate focus is ([A-Za-z0-9_]+)",
        joined,
        re.IGNORECASE,
    )
    shortlist_match = re.search(
        r"shortlist_tier=([A-Za-z0-9_]+)|shortlist tier is ([A-Za-z0-9_]+)",
        joined,
        re.IGNORECASE,
    )
    lane_match = re.search(
        r"recommended_next_expensive_lane=([A-Za-z0-9_]+)|recommended next lane is ([A-Za-z0-9_]+)",
        joined,
        re.IGNORECASE,
    )
    reported = bool(translation_match or shortlist_match or lane_match)
    return {
        "reported": reported,
        "translation_gate_focus_status": (
            translation_match.group(1) or translation_match.group(2)
            if translation_match
            else ""
        ),
        "focus_shortlist_tier": (
            shortlist_match.group(1) or shortlist_match.group(2)
            if shortlist_match
            else ""
        ),
        "recommended_next_expensive_lane": (
            lane_match.group(1) or lane_match.group(2)
            if lane_match
            else ""
        ),
        "recommended_next_expensive_lane_reason": joined if reported else "",
    }


def _infer_raw_claim_requirement_mode(target_id: str, explicit_mode: str, claim_gate_reported: bool) -> str:
    mode = str(explicit_mode or "").strip()
    if mode:
        return mode
    if str(target_id or "").strip() in SEMI_HARD_CLAIM_TARGETS:
        return "semi_hard"
    return "not_applicable" if claim_gate_reported else ""


def _canonical_value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _overlay_canonical_values(base: dict[str, Any], overlay: dict[str, Any] | None) -> dict[str, Any]:
    resolved = dict(base)
    for key, value in (overlay or {}).items():
        if _canonical_value_present(value):
            resolved[key] = value
    return resolved


def _selected_allatom_effective_blocking_order(
    *,
    effective_status: str,
    raw_claim_requirement_mode: str,
    effective_claim_requirement_mode: str,
) -> str:
    if effective_status == "hard_blocked":
        if raw_claim_requirement_mode == "semi_hard" and effective_claim_requirement_mode == "not_applicable":
            return "hard_block_first"
        return "hard_block_only"
    if effective_status == "semi_hard_blocked":
        return "semi_hard_claim_first"
    if effective_status == "soft_guided":
        return "soft_guidance_only"
    if effective_status == "ready":
        return "clear"
    if effective_status:
        return "reported_without_order"
    return "not_reported"


def _selected_allatom_effective_primary_blocking_domain(
    *,
    effective_status: str,
    translation_status: str,
    commercial_hard_gate_reported: bool,
    commercial_hard_gate_pass: bool,
    effective_claim_requirement_mode: str,
) -> str:
    if effective_status == "hard_blocked":
        if commercial_hard_gate_reported and not commercial_hard_gate_pass:
            return "commercial_hard_gate"
        if translation_status in {"fail", "blocked"}:
            return "translation_gate_v2"
        return "hard_gate"
    if effective_status == "semi_hard_blocked" and effective_claim_requirement_mode == "semi_hard":
        return "claim_equivalence_gate"
    if effective_status == "soft_guided":
        return "stronger_physics_lane_deferred"
    if effective_status == "ready":
        return "not_blocked"
    return "not_reported"


def _selected_allatom_action_recipe(
    *,
    translation_status: str,
    translation_failed_checks: list[str],
    translation_warning_checks: list[str],
    raw_claim_requirement_mode: str,
    raw_claim_requirement_reason: str,
    raw_claim_requirement_actions: list[str],
    claim_ready_for_allatom: bool,
    recommended_next_expensive_lane: str,
    recommended_next_expensive_lane_reason: str,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    def add_row(code: str, priority: str, blocking_domain: str, next_calculation: str, reason: str) -> None:
        if not code:
            return
        if any(str(row.get("code", "")).strip() == code for row in rows):
            return
        rows.append(
            {
                "code": code,
                "priority": priority,
                "blocking_domain": blocking_domain,
                "next_calculation": next_calculation,
                "reason": reason,
            }
        )

    failed = set(_coerce_text_list(translation_failed_checks))
    warnings = set(_coerce_text_list(translation_warning_checks))

    if translation_status in {"fail", "blocked"} or "distance_above_translation_near_band" in failed:
        add_row(
            "recompute_mean_min_distance_A",
            "hard",
            "translation_gate_v2",
            "re-minimize the pose and rerun short replicated MD before any stronger-physics escalation",
            "Translation hard gate is failing on geometry, so mean-min-distance needs repair under a stricter local relaxation path.",
        )
        add_row(
            "run_short_replicated_md",
            "hard",
            "translation_gate_v2",
            "launch short replicated MD on the repaired pose and re-score survival support",
            "Short replicated MD is the fastest way to confirm whether the repaired geometry survives beyond a single frame.",
        )
    if "binding_energy_proxy_too_weak_for_translation" in failed:
        add_row(
            "strengthen_three_bead_binding_energy",
            "hard",
            "translation_gate_v2",
            "refresh the 3-bead ranking after geometry repair and binding-energy proxy recomputation",
            "Translation is still too weak energetically to justify explicit-water escalation.",
        )
    warning_actions = {
        "pose_preservation_rmsd_not_observed": (
            "measure_pose_preservation_rmsd",
            "quantify pose-preservation RMSD across the repaired backmapped trajectory",
        ),
        "backmapping_consistency_not_observed": (
            "measure_backmapping_consistency",
            "compute backmapping consistency on the repaired all-atom reconstruction",
        ),
        "local_minimization_survival_not_observed": (
            "measure_local_minimization_survival",
            "measure local-minimization survival fraction after pose repair",
        ),
        "replicate_pass_fraction_not_observed": (
            "collect_replicate_translation_support",
            "collect replicate-pass support after the repaired short-MD pass",
        ),
    }
    for warning, (code, next_calculation) in warning_actions.items():
        if warning in warnings:
            add_row(
                code,
                "soft",
                "translation_support",
                next_calculation,
                "Support metrics are still unobserved, so the translation lane should be instrumented before escalating physics spend.",
            )
    if raw_claim_requirement_mode == "semi_hard" and not claim_ready_for_allatom:
        for action in raw_claim_requirement_actions or ["produce_claim_equivalence_packet", "resolve_claim_equivalence_gate"]:
            action = str(action or "").strip()
            if not action:
                continue
            add_row(
                action,
                "semi_hard",
                "claim_equivalence_gate",
                "produce the claim/equivalence artifact and attach it to the selected all-atom focus",
                raw_claim_requirement_reason
                or "This target uses semi-hard claim/equivalence semantics before final wetlab advancement.",
            )
    lane_calculation = {
        "defer_expensive_lane": "hold explicit-water rescoring and seed-replicated short MD until the translation hard gate passes",
        "enter_expensive_lane": "open the stronger-physics lane with explicit-water rescoring and seed-replicated short MD",
    }.get(recommended_next_expensive_lane, "")
    if recommended_next_expensive_lane:
        add_row(
            recommended_next_expensive_lane,
            "soft",
            "stronger_physics_lane",
            lane_calculation or "follow the recommended stronger-physics lane policy for this focus",
            recommended_next_expensive_lane_reason
            or "The stronger-physics lane recommendation is being surfaced for operator triage.",
        )
    return {
        "action_recipe_codes": [str(row.get("code", "")).strip() for row in rows if str(row.get("code", "")).strip()],
        "action_recipe_rows": rows,
        "action_recipe_rollup_text": " | ".join(
            f"{row['priority']}:{row['code']} -> {row['next_calculation']}" for row in rows
        ),
    }


def _resolve_selected_allatom_canonical_with_fallback(
    *,
    fallback: dict[str, Any],
    review_packet_summary: dict[str, Any] | None = None,
    retry_handoff_summary: dict[str, Any] | None = None,
    current_results_index_summary: dict[str, Any] | None = None,
    monitor_semantics_summary: dict[str, Any] | None = None,
    master_handoff_dashboard_summary: dict[str, Any] | None = None,
    final_campaign_summary: dict[str, Any] | None = None,
    partnering_stack_summary: dict[str, Any] | None = None,
    next_required_step: str = "",
) -> dict[str, Any]:
    try:
        resolved = resolve_selected_allatom_canonical(
            review_packet_summary=review_packet_summary,
            retry_handoff_summary=retry_handoff_summary,
            current_results_index_summary=current_results_index_summary,
            monitor_semantics_summary=monitor_semantics_summary,
            master_handoff_dashboard_summary=master_handoff_dashboard_summary,
            final_campaign_summary=final_campaign_summary,
            partnering_stack_summary=partnering_stack_summary,
            next_required_step=next_required_step,
        )
        resolver_used = isinstance(resolved, dict) and bool(resolved)
    except NotImplementedError:
        resolved = {}
        resolver_used = False
    merged = _overlay_canonical_values(fallback, resolved if isinstance(resolved, dict) else {})
    merged["__canonical_resolver_used__"] = resolver_used
    return merged


def _has_value(summary: dict[str, Any], key: str) -> bool:
    if key not in summary:
        return False
    value = summary.get(key)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y", "ready", "pass"}:
        return True
    if text in {"0", "false", "no", "n", "not_ready", "fail"}:
        return False
    return bool(value)


def _resolve_bool(*values: Any, default: bool = False) -> bool:
    for value in values:
        if value in {"", None}:
            continue
        return _coerce_bool(value)
    return default


def _resolve_optional_bool(summary: dict[str, Any], *keys: str) -> tuple[bool, bool]:
    for key in keys:
        if _has_value(summary, key):
            return True, _coerce_bool(summary.get(key))
    return False, False


def _resolve_explicit_bool_from_sources(
    specs: list[tuple[dict[str, Any], tuple[str, ...], tuple[str, ...]]],
) -> tuple[bool, bool]:
    for summary, reported_keys, value_keys in specs:
        if not summary:
            continue
        for reported_key in reported_keys:
            if _has_value(summary, reported_key):
                if not _coerce_bool(summary.get(reported_key)):
                    return False, False
                for value_key in value_keys:
                    if _has_value(summary, value_key):
                        return True, _coerce_bool(summary.get(value_key))
                return True, False
        reported, value = _resolve_optional_bool(summary, *value_keys)
        if reported:
            return reported, value
    return False, False


def _resolve_first_value(specs: list[tuple[dict[str, Any], str]]) -> Any:
    for summary, key in specs:
        if summary and _has_value(summary, key):
            return summary.get(key)
    return None


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _coerce_text_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        items = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            items = []
        elif ";" in text:
            items = text.split(";")
        elif "," in text:
            items = text.split(",")
        else:
            items = [text]
    elif value in {"", None}:
        items = []
    else:
        items = [value]
    resolved: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if text:
            resolved.append(text)
    return resolved


def _artifact_json_path(path_like: str) -> str:
    text = str(path_like or "").strip()
    if not text:
        return ""
    path = Path(text)
    if path.suffix.lower() == ".md":
        path = path.with_suffix(".json")
    if not path.is_absolute():
        path = ROOT / path
    return str(path)


def _load_artifact_summary(path_like: str) -> dict[str, Any]:
    artifact_json_path = _artifact_json_path(path_like)
    if not artifact_json_path:
        return {}
    return _summary(maybe_load_json(artifact_json_path))


def _selected_allatom_review_packet_path(surface_label: str) -> str:
    label = str(surface_label or "").strip()
    if not label:
        return ""
    if label.endswith(".json"):
        path = Path(label)
    elif label.startswith("wetlab_"):
        path = Path("runs") / f"{label}_current.json"
    else:
        path = Path("runs") / f"wetlab_{label}_current.json"
    if not path.is_absolute():
        path = ROOT / path
    return str(path)


def _selected_allatom_review_packet_summary(surface_label: str) -> dict[str, Any]:
    path = _selected_allatom_review_packet_path(surface_label)
    return _summary(maybe_load_json(path)) if path else {}


def _reported_state(reported: bool, value: bool, *, ready_label: str, not_ready_label: str) -> str:
    if not reported:
        return "not_reported"
    return ready_label if value else not_ready_label


def _claim_state(
    claim_gate_reported: bool,
    claim_gate_available: bool,
    claim_ready_reported: bool,
    claim_ready_for_allatom: bool,
) -> str:
    if not claim_gate_reported and not claim_ready_reported:
        return "not_reported"
    if claim_gate_reported and not claim_gate_available:
        return "unavailable"
    if claim_ready_reported:
        return "ready" if claim_ready_for_allatom else "blocked"
    return "available"


def _readiness_signal(
    *,
    target_id: str = "",
    shard_id: str = "",
    surface_label: str = "",
    focus_available: bool | None = None,
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
) -> str:
    parts: list[str] = []
    if target_id:
        parts.append(target_id)
    if shard_id:
        parts.append(shard_id)
    if surface_label:
        parts.append(surface_label)
    if focus_available is not None:
        parts.append("focus=selected" if focus_available else "focus=not_selected")
    parts.append(
        "op_review="
        + _reported_state(
            operator_review_reported,
            operator_review_ready,
            ready_label="ready",
            not_ready_label="not_ready",
        )
    )
    parts.append(
        "wetlab_gate="
        + _reported_state(
            wetlab_gate_reported,
            wetlab_gate_pass,
            ready_label="pass",
            not_ready_label="fail",
        )
    )
    parts.append(
        "final_gate="
        + _reported_state(
            final_gate_reported,
            final_gate_pass,
            ready_label="pass",
            not_ready_label="fail",
        )
    )
    parts.append(
        "claim="
        + _claim_state(
            claim_gate_reported,
            claim_gate_available,
            claim_ready_reported,
            claim_ready_for_allatom,
        )
    )
    return " | ".join(part for part in parts if part)


def _human_gate_fragment(
    *,
    label: str,
    reported: bool,
    value: bool,
    positive: str,
    negative: str,
) -> str:
    if not reported:
        return f"{label} not reported"
    return f"{label} {positive if value else negative}"


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


def _commercial_schema_label(schema_version: str) -> str:
    text = str(schema_version or "").strip()
    if text == "wetlab_commercial_grade_v1":
        return "commercial grade v1"
    if text == "wetlab_commercial_grade_v2":
        return "commercial grade v2"
    if not text:
        return "commercial grade v1"
    return text.replace("_", " ")


def _selected_allatom_commercial_signal(
    *,
    commercial_reported: bool,
    schema_version: str,
    hard_gate_reported: bool,
    hard_gate_pass: bool,
    soft_score: float,
    confidence_score: float,
    overall_score: float,
    risk_bucket: str,
    decision_class: str,
    primary_upgrade_actions: list[str],
) -> str:
    if not commercial_reported:
        return ""
    parts: list[str] = []
    if overall_score > 0:
        parts.append(f"overall {overall_score:.1f}")
    if soft_score > 0:
        parts.append(f"soft {soft_score:.1f}")
    if confidence_score > 0:
        parts.append(f"confidence {confidence_score:.1f}")
    if hard_gate_reported:
        parts.append(f"hard gate {'passed' if hard_gate_pass else 'failed'}")
    if risk_bucket:
        parts.append(f"risk {risk_bucket}")
    if decision_class:
        parts.append(f"decision {decision_class}")
    summary = f"{_commercial_schema_label(schema_version).capitalize()}: "
    summary += ", ".join(parts) if parts else "reported."
    if primary_upgrade_actions:
        summary += f"; upgrade actions {', '.join(primary_upgrade_actions)}"
    if not summary.endswith("."):
        summary += "."
    return summary


def _selected_allatom_translation_signal(
    *,
    translation_reported: bool,
    translation_status: str,
    translation_score_reported: bool,
    translation_score: float,
    translation_reason: str,
    shortlist_tier: str,
    recommended_next_expensive_lane: str,
    recommended_next_expensive_lane_reason: str,
) -> str:
    if not translation_reported:
        return ""
    parts: list[str] = []
    if translation_status:
        parts.append(f"status {translation_status}")
    if translation_score_reported:
        parts.append(f"score {translation_score:.1f}")
    if shortlist_tier:
        parts.append(f"shortlist {shortlist_tier}")
    if recommended_next_expensive_lane:
        parts.append(f"lane {recommended_next_expensive_lane}")
    summary = "Translation/shortlist: "
    summary += ", ".join(parts) if parts else "reported."
    reason = _text(recommended_next_expensive_lane_reason, translation_reason)
    if reason:
        summary += f"; {reason}"
    if not summary.endswith("."):
        summary += "."
    return summary


def _selected_allatom_actionability_fallback(
    *,
    final_gate_pass: bool,
    operator_review_ready: bool,
    commercial_hard_gate_blocked: bool,
    claim_gate_available: bool,
    claim_ready_for_allatom: bool,
    translation_status: str,
    translation_reason: str,
    shortlist_tier: str,
    next_expensive_lane: str,
    next_expensive_lane_reason: str,
    next_required_step: str,
) -> dict[str, Any]:
    inferred_next_expensive_lane = _text(
        next_expensive_lane,
        _selected_allatom_inferred_next_expensive_lane(
            shortlist_tier,
            translation_status,
            next_expensive_lane_reason,
            next_required_step,
        ),
    )
    hard_block_present = bool(
        commercial_hard_gate_blocked
        or _text(translation_status).lower() in {"fail", "blocked"}
    )
    claim_requirement_mode = "semi_hard" if claim_gate_available else "not_applicable"
    claim_requirement_status = (
        "satisfied"
        if claim_requirement_mode == "semi_hard" and claim_ready_for_allatom
        else "blocked"
        if claim_requirement_mode == "semi_hard"
        else "not_applicable"
    )
    claim_requirement_reason = (
        "claim/equivalence gate is satisfied"
        if claim_requirement_mode == "semi_hard" and claim_ready_for_allatom
        else "claim/equivalence gate is semi-hard and blocked"
        if claim_requirement_mode == "semi_hard"
        else "claim/equivalence gate is not applicable"
    )
    status = "ready"
    if not final_gate_pass:
        if hard_block_present:
            status = "hard_blocked"
        elif claim_requirement_mode == "semi_hard" and not claim_ready_for_allatom:
            status = "semi_hard_blocked"
        elif inferred_next_expensive_lane or shortlist_tier:
            status = "soft_guided"
        else:
            status = "blocked"
    required_calculations: list[str] = []
    action_list: list[dict[str, Any]] = []
    if _text(translation_status).lower() in {"fail", "blocked"}:
        required_calculations.append("recompute_mean_min_distance_A")
    if claim_requirement_mode == "semi_hard":
        action_list.append(
            {
                "severity": "semi_hard",
                "category": "claim_equivalence",
                "action": "resolve_claim_equivalence_gate",
                "status": "satisfied" if claim_ready_for_allatom else "required",
                "claim_requirement_mode": "semi_hard",
                "reason": claim_requirement_reason,
            }
        )
        if not claim_ready_for_allatom:
            required_calculations.append("resolve_claim_equivalence_gate")
    if inferred_next_expensive_lane:
        action_list.append(
            {
                "severity": "soft",
                "category": "next_expensive_lane",
                "action": "defer_expensive_lane" if inferred_next_expensive_lane == "defer_expensive_lane" else "enter_expensive_lane",
                "status": "deferred" if inferred_next_expensive_lane == "defer_expensive_lane" else "queued",
                "lane": inferred_next_expensive_lane,
                "reason": next_expensive_lane_reason,
            }
        )
    human_summary = _joined(
        f"{status.replace('_', ' ')}: {claim_requirement_reason}" if claim_requirement_mode == "semi_hard" and not claim_ready_for_allatom else status.replace("_", " "),
        f"required calculations: {', '.join(required_calculations)}" if required_calculations else "",
        f"soft guidance: {translation_reason}" if translation_reason else "",
        f"next expensive lane: {inferred_next_expensive_lane}" if inferred_next_expensive_lane else "",
    )
    brief_summary = _joined(
        f"{status.replace('_', ' ')}" if status else "",
        f"claim {claim_requirement_mode}:{claim_requirement_status}" if claim_requirement_mode == "semi_hard" else "",
        f"lane {inferred_next_expensive_lane}" if inferred_next_expensive_lane else "",
    )
    action_list_text = " | ".join(
        f"{item['severity']}:{item['action']}[{item['status']}]" + (f" lane={item['lane']}" if item.get("lane") else "")
        for item in action_list
    )
    return {
        "status": status,
        "blocked": bool(status != "ready"),
        "block_reason": claim_requirement_reason if claim_requirement_mode == "semi_hard" and not claim_ready_for_allatom else (
            "commercial hard gate failed" if commercial_hard_gate_blocked else ""
        ),
        "block_reason_codes": ["claim_equivalence_gate_semi_hard"] if claim_requirement_mode == "semi_hard" and not claim_ready_for_allatom else (["commercial_hard_gate_failed"] if commercial_hard_gate_blocked else []),
        "soft_guidance_reasons": [f"translation_gate_focus:{translation_status}"] if translation_status else [],
        "required_calculations": required_calculations,
        "required_calculations_text": ", ".join(required_calculations),
        "action_list": action_list,
        "action_list_text": action_list_text,
        "claim_requirement_mode": claim_requirement_mode,
        "claim_requirement_status": claim_requirement_status,
        "claim_requirement_reason": claim_requirement_reason,
        "next_expensive_lane": inferred_next_expensive_lane,
        "next_expensive_lane_reason": next_expensive_lane_reason,
        "translation_gate_v2_failed_metrics": [],
        "translation_gate_v2_missing_metrics": [],
        "translation_gate_v2_thresholds": {},
        "human_summary": human_summary,
        "brief_summary": brief_summary,
    }


def _selected_allatom_human_signal(
    *,
    target_id: str,
    surface_label: str,
    focus_available: bool,
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
    packet_scope: str,
    selected_command_kind: str,
    selected_threshold_A: float,
    best_compound_name: str,
    best_compound_name_human_readable: str,
    best_compound_name_resolution: str,
    best_mean_min_distance_A: float,
    promoted_candidate_count: int,
    under_2p5_candidate_count: int,
    near_candidate_count: int,
) -> str:
    canonical_signal = _readiness_signal(
        target_id=target_id,
        surface_label=surface_label,
        focus_available=focus_available,
        operator_review_reported=operator_review_reported,
        operator_review_ready=operator_review_ready,
        wetlab_gate_reported=wetlab_gate_reported,
        wetlab_gate_pass=wetlab_gate_pass,
        final_gate_reported=final_gate_reported,
        final_gate_pass=final_gate_pass,
        claim_gate_reported=claim_gate_reported,
        claim_gate_available=claim_gate_available,
        claim_ready_reported=claim_ready_reported,
        claim_ready_for_allatom=claim_ready_for_allatom,
    )
    focus_label = "Selected all-atom focus"
    if target_id:
        focus_label += f" for {target_id}"
    if surface_label:
        focus_label += f" on {surface_label}"
    focus_phrase = (
        f"{focus_label} is attached"
        if focus_available
        else f"{focus_label} is not attached"
    )
    claim_phrase = {
        "not_reported": "claim state not reported",
        "unavailable": "claim gate unavailable",
        "available": "claim gate available but readiness not reported",
        "blocked": "claim blocked for all-atom",
        "ready": "claim ready for all-atom",
    }[
        _claim_state(
            claim_gate_reported,
            claim_gate_available,
            claim_ready_reported,
            claim_ready_for_allatom,
        )
    ]
    summary_parts = [
        focus_phrase,
        _human_gate_fragment(
            label="operator review",
            reported=operator_review_reported,
            value=operator_review_ready,
            positive="ready",
            negative="not ready",
        ),
        _human_gate_fragment(
            label="wetlab gate",
            reported=wetlab_gate_reported,
            value=wetlab_gate_pass,
            positive="passed",
            negative="failed",
        ),
        _human_gate_fragment(
            label="final gate",
            reported=final_gate_reported,
            value=final_gate_pass,
            positive="passed",
            negative="failed",
        ),
        claim_phrase,
    ]
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
    if selected_threshold_A > 0:
        detail_parts.append(f"selected threshold {selected_threshold_A:.1f}A")
    if packet_scope:
        detail_parts.append(f"scope {packet_scope}")
    if selected_command_kind:
        detail_parts.append(f"mode {selected_command_kind}")
    human_signal = "; ".join(part for part in summary_parts if part) + "."
    if detail_parts:
        human_signal += " Details: " + "; ".join(detail_parts) + "."
    if canonical_signal:
        human_signal += f" [{canonical_signal}]"
    return human_signal


def _pid_snapshot(path_like: str) -> dict[str, Any]:
    path = Path(path_like)
    if not path.is_absolute():
        path = ROOT / path
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


def _primary_watch_ready(summary: dict[str, Any]) -> bool:
    status = str(summary.get("status", "")).strip()
    return status in {
        "wetlab_broad_screen_primary_watcher_ready",
        "wetlab_broad_screen_primary_watch_state_ready",
        "wetlab_broad_screen_primary_watch_action_ready",
    }


def _primary_watch_decision(*summaries: dict[str, Any]) -> str:
    for summary in summaries:
        for key in ("watcher_decision", "compute_state", "active_progress_status", "active_queue_status"):
            text = str(summary.get(key, "")).strip()
            if text:
                return text
    return ""


def _primary_watch_action(*summaries: dict[str, Any]) -> str:
    for summary in summaries:
        text = str(summary.get("action_taken", "")).strip()
        if text:
            return text
        if "actions_taken_count" in summary:
            try:
                count = int(summary.get("actions_taken_count", 0) or 0)
            except Exception:
                count = 0
            return "noop" if count == 0 else f"actions_taken={count}"
    return ""


def _manual_retry_next_step_from_lane(lane_payload: dict[str, Any], fallback: str = "") -> str:
    summary = _summary(lane_payload)
    lane_label = str(summary.get("followup_lane_label", "") or summary.get("lane_label", "")).strip()
    status = str(summary.get("status", "")).strip()
    selectable = bool(summary.get("ready_for_manual_retry", False)) or (
        lane_label == "exploratory_gate4.5_followup" and status.startswith("wetlab_stk17b_exploratory_followup_lane_")
    )
    if not selectable:
        return fallback
    explicit_next_step = str(summary.get("next_required_step", "")).strip()
    if explicit_next_step:
        return explicit_next_step
    target_id = str(summary.get("target_id", "")).strip()
    shard_id = str(summary.get("shard_id", "")).strip()
    selected_kind = str(summary.get("selected_command_kind", "")).strip()
    followup_shards = str(summary.get("followup_shard_ids", "")).strip()
    target_label = target_id or "manual retry"
    if "followup" in lane_label:
        return (
            f"Run the {target_label} exploratory gate4.5 follow-up runner for {shard_id}; keep auto-start hard-frozen."
            if shard_id
            else f"Run the {target_label} exploratory gate4.5 follow-up runner; keep auto-start hard-frozen."
        )
    if "gate45" in selected_kind:
        return (
            f"Run the {target_label} exploratory gate4.5 manual retry runner for {shard_id}; keep auto-start blocked until the guarded retry either lands a clean summary or is held again."
            if shard_id
            else f"Run the {target_label} exploratory gate4.5 manual retry runner; keep auto-start blocked until the guarded retry either lands a clean summary or is held again."
        )
    if "gate55" in selected_kind:
        return (
            f"Run the {target_label} tuned gate55 manual retry runner for {shard_id}; keep auto-start blocked until the guarded retry either lands a clean summary or is held again."
            if shard_id
            else f"Run the {target_label} tuned gate55 manual retry runner; keep auto-start blocked until the guarded retry either lands a clean summary or is held again."
        )
    return (
        f"Run the {target_label} manual retry runner for {shard_id}; keep auto-start blocked until the guarded retry either lands a clean summary or is held again."
        if shard_id
        else f"Run the {target_label} manual retry runner; keep auto-start blocked until the guarded retry either lands a clean summary or is held again."
    )


def _manual_retry_next_step(
    retry_handoff_summary: dict[str, Any],
    broad_screen_stk17b_manual_retry_lane: dict[str, Any],
    broad_screen_stk17b_exploratory_retry_lane: dict[str, Any],
    broad_screen_stk17b_exploratory_followup_lane: dict[str, Any],
    broad_screen_plpro_manual_retry_lane: dict[str, Any],
    broad_screen_lbdhodh_exploratory_retry_lane: dict[str, Any],
    fallback: str = "",
) -> str:
    retry_summary = _summary(retry_handoff_summary)
    selected_lane_label = str(retry_summary.get("selected_manual_retry_lane_label", "")).strip()
    selected_target = str(retry_summary.get("selected_manual_retry_target_id", "")).strip()
    selected_shard = str(retry_summary.get("selected_manual_retry_shard_id", "")).strip()
    selected_kind = str(retry_summary.get("selected_manual_retry_selected_command_kind", "")).strip()
    for lane_payload in (
        broad_screen_stk17b_exploratory_followup_lane,
        broad_screen_stk17b_exploratory_retry_lane,
        broad_screen_stk17b_manual_retry_lane,
        broad_screen_plpro_manual_retry_lane,
        broad_screen_lbdhodh_exploratory_retry_lane,
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
        lane_step = _manual_retry_next_step_from_lane(lane_payload)
        if lane_step:
            return lane_step
    return _manual_retry_next_step_from_lane(
        broad_screen_stk17b_exploratory_followup_lane,
        _manual_retry_next_step_from_lane(
        broad_screen_stk17b_exploratory_retry_lane,
        _manual_retry_next_step_from_lane(
            broad_screen_stk17b_manual_retry_lane,
            _manual_retry_next_step_from_lane(broad_screen_plpro_manual_retry_lane, fallback),
        ),
        )
    )


def _rescue_next_required_step(
    hard_target_rescue_lane: dict[str, Any] | None,
    rescue_anchor_artifacts: dict[str, Any] | None,
    rescue_three_bead_candidates: dict[str, Any] | None,
) -> str:
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


def _stk17b_followup_review_next_step(review_surface_summary: dict[str, Any]) -> str:
    if str(review_surface_summary.get("target_id", "")).strip() != "STK17B (DRAK2)":
        return ""
    if not str(review_surface_summary.get("decision", "")).strip():
        return ""
    return str(review_surface_summary.get("next_required_step", "")).strip()


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
        queue_target_id if queue_priority else lane.get("target_id", tuning.get("target_id", "Dengue NS2B-NS3 protease"))
    ).strip()
    threshold = float(tuning.get("recommended_observed_threshold_A", 0.0) or 0.0)
    command_kind = str(lane.get("selected_command_kind", tuning.get("immediately_runnable_command_kind", ""))).strip()
    lane_label = str(lane.get("lane_label", "")).strip()
    shard_id = str(queue_shard_id if queue_priority else lane.get("shard_id", "") or tuning.get("next_retry_shard_id", "")).strip()
    next_required_step = str(
        queue_next_required_step if queue_priority else lane.get("next_required_step", tuning.get("next_required_step", ""))
    ).strip()
    if not next_required_step:
        next_required_step = (
            "Promote Dengue NS2B-NS3 protease stage6 tuned retry, keep the default lane closed, and reserve any future Dengue reopen for an explicit new review."
        )
    return {
        "status": str(queue_status if queue_priority else lane.get("status", tuning.get("status", ""))).strip() or (
            "wetlab_dengue_ns2b_ns3_protease_exploratory_retry_lane_ready"
            if lane_ready
            else "wetlab_dengue_ns2b_ns3_protease_stage6_tuning_surface_ready"
        ),
        "target_id": target_id,
        "source_priority": "execution_queue" if queue_priority else "exploratory_lane" if lane_ready else "tuning_surface",
        "tuning_ready": tuning_ready,
        "recommended_threshold_A": threshold,
        "immediately_runnable_command_kind": str(tuning.get("immediately_runnable_command_kind", "")).strip(),
        "retry_lane_ready": lane_ready,
        "ready_for_manual_retry": bool(lane.get("ready_for_manual_retry", False)),
        "shard_id": shard_id,
        "selected_command_kind": command_kind,
        "lane_label": lane_label or "dengue_stage6_tuned_retry",
        "next_required_step": next_required_step,
        "focus_target_id": target_id,
        "focus_template_label": lane_label or "dengue_stage6_tuned_retry",
        "focus_selected_command_kind": command_kind,
        "focus_selected_threshold_A": threshold,
    }


def _lane_shard_display(summary: dict[str, Any]) -> str:
    lane_label = str(summary.get("followup_lane_label", "") or summary.get("lane_label", "")).strip()
    if lane_label == "exploratory_gate4.5_followup":
        return str(summary.get("shard_id", "")).strip() or str(summary.get("followup_shard_ids", "")).strip()
    return str(summary.get("shard_id", "")).strip()


def _exploratory_freeze_snapshot(
    exploratory_summary: dict[str, Any],
    exploratory_followup_summary: dict[str, Any],
    *primary_watch_summaries: dict[str, Any],
) -> dict[str, Any]:
    if str(exploratory_followup_summary.get("hard_freeze_state", "")).strip():
        followup_shards_text = str(exploratory_followup_summary.get("followup_shard_ids", "")).strip()
        followup_shard_count = len([part for part in followup_shards_text.split(";") if str(part).strip()])
        hold_streak = int(
            exploratory_followup_summary.get("guard_hold_streak", 0)
            or exploratory_followup_summary.get("hold_streak", 0)
            or followup_shard_count
            or 0
        )
        hold_limit = int(
            exploratory_followup_summary.get("guard_limit", 0)
            or exploratory_followup_summary.get("hold_limit", 0)
            or followup_shard_count
            or 0
        )
        return {
            "state": str(exploratory_followup_summary.get("hard_freeze_state", "")).strip(),
            "target_id": str(exploratory_followup_summary.get("target_id", "")).strip(),
            "hold_streak": hold_streak,
            "hold_limit": hold_limit,
            "freeze_note": str(exploratory_followup_summary.get("freeze_note", "")).strip(),
            "next_required_step": str(exploratory_followup_summary.get("next_required_step", "")).strip(),
        }
    target_id = str(exploratory_summary.get("target_id", "")).strip()
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
    final_campaign_summary: dict[str, Any],
    master_terminal_review: dict[str, Any],
    outbound_board: dict[str, Any],
    send_round: dict[str, Any],
    export_bundle: dict[str, Any],
    broad_screen_queue: dict[str, Any],
    broad_screen_bridge: dict[str, Any],
    broad_screen_compound_universe: dict[str, Any] | None = None,
    broad_screen_execution_queue: dict[str, Any] | None = None,
    broad_screen_repurposing_autofill: dict[str, Any] | None = None,
    broad_screen_target_rerank: dict[str, Any] | None = None,
    broad_screen_stability_score: dict[str, Any] | None = None,
    broad_screen_antitarget_queue: dict[str, Any] | None = None,
    broad_screen_antitarget_execution_queue: dict[str, Any] | None = None,
    broad_screen_primary_watch_state: dict[str, Any] | None = None,
    broad_screen_primary_watch: dict[str, Any] | None = None,
    broad_screen_antitarget_watch_state: dict[str, Any] | None = None,
    broad_screen_antitarget_watch: dict[str, Any] | None = None,
    broad_screen_actual_append: dict[str, Any] | None = None,
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
    broad_screen_kinase_retry_policy_templates: dict[str, Any] | None = None,
    broad_screen_target_retry_policy_templates: dict[str, Any] | None = None,
    broad_screen_dengue_stage6_tuning_surface: dict[str, Any] | None = None,
    broad_screen_dengue_exploratory_retry_lane: dict[str, Any] | None = None,
    broad_screen_lbdhodh_stage6_tuning_surface: dict[str, Any] | None = None,
    broad_screen_lbdhodh_exploratory_retry_lane: dict[str, Any] | None = None,
    broad_screen_lbdhodh_gate51_validation_review_surface: dict[str, Any] | None = None,
    broad_screen_tcruzi_pde_promoted_top4_review_packet: dict[str, Any] | None = None,
    broad_screen_tcruzi_pde_rescue_only_branch_summary: dict[str, Any] | None = None,
    broad_screen_selected_allatom_visual_bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fcs = _summary(final_campaign_summary)
    mtrs = _summary(master_terminal_review)
    obs = _summary(outbound_board)
    srs = _summary(send_round)
    ebs = _summary(export_bundle)
    bsqs = _summary(broad_screen_queue)
    bsbs = _summary(broad_screen_bridge)
    bscus = _summary(broad_screen_compound_universe)
    bseqs = _summary(broad_screen_execution_queue)
    bsras = _summary(broad_screen_repurposing_autofill)
    bstrs = _summary(broad_screen_target_rerank)
    bssts = _summary(broad_screen_stability_score)
    bsats = _summary(broad_screen_antitarget_queue)
    bsaeqs = _summary(broad_screen_antitarget_execution_queue)
    bspwss = _summary(broad_screen_primary_watch_state)
    bspws = _summary(broad_screen_primary_watch)
    bsawss = _summary(broad_screen_antitarget_watch_state)
    bsaws = _summary(broad_screen_antitarget_watch)
    bspwlp = _pid_snapshot(DEFAULT_BROAD_SCREEN_PRIMARY_WATCH_LOOP_PID)
    bsawlp = _pid_snapshot(DEFAULT_BROAD_SCREEN_ANTITARGET_WATCHER_LOOP_PID)
    bsaas = _summary(broad_screen_actual_append)
    bstbs = _summary(broad_screen_throughput_bridge)
    bsrps = _summary(broad_screen_primary_retry_preset)
    bshgs = _summary(broad_screen_primary_hold_guard)
    bcris = _summary(broad_screen_current_results_index)
    bsmss = _summary(broad_screen_monitor_semantics)
    bsrhs = _summary(broad_screen_retry_handoff_summary)
    bdr1 = _summary(broad_screen_dpre1_branch_review_surface)
    bssmls = _summary(broad_screen_stk17b_manual_retry_lane)
    bsserls = _summary(broad_screen_stk17b_exploratory_retry_lane)
    bssefls = _summary(broad_screen_stk17b_exploratory_followup_lane)
    bssfrs = _summary(broad_screen_stk17b_followup_review_surface)
    bspmls = _summary(broad_screen_plpro_manual_retry_lane)
    bsmfrs = _summary(broad_screen_mapping_fix_retry_support)
    bssmfl = _summary(broad_screen_stage1_mapping_fix_lanes)
    bsmfrpts = _summary(broad_screen_mapping_fix_retry_policy_templates)
    bshrls = _summary(broad_screen_hard_target_rescue_lane)
    bresas = _summary(broad_screen_rescue_anchor_artifacts)
    bsr3bs = _summary(broad_screen_rescue_three_bead_candidates)
    bskrts = _summary(broad_screen_kinase_retry_policy_templates)
    bstrpts = _summary(broad_screen_target_retry_policy_templates)
    bdgts = _summary(broad_screen_dengue_stage6_tuning_surface)
    bdgrs = _summary(broad_screen_dengue_exploratory_retry_lane)
    bslts = _summary(broad_screen_lbdhodh_stage6_tuning_surface)
    bsldrs = _summary(broad_screen_lbdhodh_exploratory_retry_lane)
    bslvrs = _summary(broad_screen_lbdhodh_gate51_validation_review_surface)
    bstprp = _summary(broad_screen_tcruzi_pde_promoted_top4_review_packet)
    bstrob = _summary(broad_screen_tcruzi_pde_rescue_only_branch_summary)
    selected_allatom_visual = resolve_selected_allatom_visual_bundle(
        broad_screen_selected_allatom_visual_bundle
    )
    selected_allatom_visual_fields = selected_allatom_visual_surface_fields(
        selected_allatom_visual
    )
    promoted_top4_operator_review_ready = bool(
        bstprp.get("packet_ready_for_operator_review", bstprp.get("packet_ready", False))
    )
    promoted_top4_wetlab_gate_reported, promoted_top4_wetlab_gate_pass = _resolve_optional_bool(
        bstprp,
        "wetlab_gate_pass",
    )
    promoted_top4_final_gate_reported, promoted_top4_final_gate_pass = _resolve_optional_bool(
        bstprp,
        "wetlab_final_gate_pass",
        "final_gate_pass",
    )
    promoted_top4_claim_gate_reported, promoted_top4_claim_gate_available = _resolve_optional_bool(
        bstprp,
        "claim_gate_available",
    )
    promoted_top4_claim_ready_reported, promoted_top4_claim_ready = _resolve_optional_bool(
        bstprp,
        "claim_ready_for_allatom",
    )
    promoted_top4_readiness_semantics = (
        "operator_review_and_final_gate"
        if promoted_top4_final_gate_reported
        else "operator_review_only_legacy_packet_ready"
    )
    rescue_branch_review_operator_ready = bool(
        bstrob.get(
            "review_packet_operator_review_ready",
            bstrob.get(
                "packet_ready_for_operator_review",
                bstrob.get("review_packet_ready", bstrob.get("promoted_top4_packet_ready", False)),
            ),
        )
    )
    rescue_branch_review_wetlab_gate_reported, rescue_branch_review_wetlab_gate_pass = _resolve_optional_bool(
        bstrob,
        "review_packet_wetlab_gate_pass",
        "promoted_top4_packet_wetlab_gate_pass",
        "wetlab_gate_pass",
    )
    rescue_branch_review_final_gate_reported, rescue_branch_review_final_gate_pass = _resolve_optional_bool(
        bstrob,
        "review_packet_final_gate_pass",
        "promoted_top4_packet_final_gate_pass",
        "wetlab_final_gate_pass",
    )
    rescue_branch_operator_packet_ready = bool(
        bstrob.get("operator_packet_operator_review_ready", bstrob.get("operator_packet_ready", False))
    )
    rescue_branch_operator_wetlab_gate_reported, rescue_branch_operator_wetlab_gate_pass = _resolve_optional_bool(
        bstrob,
        "operator_packet_wetlab_gate_pass",
    )
    rescue_branch_operator_final_gate_reported, rescue_branch_operator_final_gate_pass = _resolve_optional_bool(
        bstrob,
        "operator_packet_final_gate_pass",
    )
    rescue_branch_claim_gate_reported, rescue_branch_claim_gate_available = _resolve_optional_bool(
        bstrob,
        "operator_packet_claim_gate_available",
        "review_packet_claim_gate_available",
        "claim_gate_available",
    )
    rescue_branch_claim_ready_reported, rescue_branch_claim_ready = _resolve_optional_bool(
        bstrob,
        "operator_packet_claim_ready_for_allatom",
        "review_packet_claim_ready_for_allatom",
        "claim_ready_for_allatom",
    )
    rescue_branch_wetlab_gate_reported = (
        rescue_branch_operator_wetlab_gate_reported or rescue_branch_review_wetlab_gate_reported
    )
    rescue_branch_wetlab_gate_pass = (
        rescue_branch_operator_wetlab_gate_pass
        if rescue_branch_operator_wetlab_gate_reported
        else rescue_branch_review_wetlab_gate_pass
    )
    rescue_branch_final_gate_reported = (
        rescue_branch_operator_final_gate_reported or rescue_branch_review_final_gate_reported
    )
    rescue_branch_final_gate_pass = (
        rescue_branch_operator_final_gate_pass
        if rescue_branch_operator_final_gate_reported
        else rescue_branch_review_final_gate_pass
    )
    rescue_branch_operator_review_ready = rescue_branch_operator_packet_ready or rescue_branch_review_operator_ready
    rescue_branch_readiness_semantics = (
        "operator_review_and_final_gate"
        if rescue_branch_final_gate_reported
        else "operator_review_only_legacy_review_packet"
    )
    selected_allatom_target_id = _text(
        bsrhs.get("selected_allatom_target_id", ""),
        bcris.get("selected_allatom_target_id", ""),
    )
    selected_allatom_surface_label = _text(
        bsrhs.get("selected_allatom_surface_label", ""),
        bcris.get("selected_allatom_surface_label", ""),
    )
    selected_allatom_focus_available = bool(_text(selected_allatom_target_id, selected_allatom_surface_label))
    selected_allatom_focus_artifact = _text(
        bcris.get("selected_allatom_focus_artifact", ""),
        "runs/wetlab_retry_handoff_summary_current.md" if selected_allatom_focus_available else "",
    )
    selected_allatom_focus_status = _text(
        bcris.get("selected_allatom_focus_status", ""),
        bsrhs.get("status", ""),
    )
    selected_allatom_focus_summary = _load_artifact_summary(selected_allatom_focus_artifact)
    selected_allatom_review_packet_summary = _selected_allatom_review_packet_summary(
        selected_allatom_surface_label
    )
    selected_allatom_focus_summary = _overlay_canonical_values(
        selected_allatom_focus_summary,
        selected_allatom_review_packet_summary,
    )
    selected_allatom_operator_review_reported, selected_allatom_operator_review_ready = _resolve_explicit_bool_from_sources(
        [
            (
                selected_allatom_focus_summary,
                (),
                (
                    "packet_ready_for_operator_review",
                    "selected_allatom_packet_ready_for_operator_review",
                    "selected_allatom_operator_review_ready",
                    "packet_ready",
                ),
            ),
            (
                bsrhs,
                (),
                (
                    "selected_allatom_packet_ready_for_operator_review",
                    "selected_allatom_operator_review_ready",
                    "selected_allatom_packet_ready",
                ),
            ),
            (
                bcris,
                ("selected_allatom_operator_review_ready_reported",),
                ("selected_allatom_operator_review_ready",),
            ),
        ]
    )
    selected_allatom_wetlab_gate_reported, selected_allatom_wetlab_gate_pass = _resolve_explicit_bool_from_sources(
        [
            (
                selected_allatom_focus_summary,
                (),
                ("wetlab_gate_pass", "selected_allatom_wetlab_gate_pass", "selected_allatom_gate_pass"),
            ),
            (
                bcris,
                ("selected_allatom_wetlab_gate_reported",),
                ("selected_allatom_wetlab_gate_pass",),
            ),
            (
                bsrhs,
                (),
                ("selected_allatom_wetlab_gate_pass", "selected_allatom_gate_pass"),
            ),
        ]
    )
    selected_allatom_final_gate_reported, selected_allatom_final_gate_pass = _resolve_explicit_bool_from_sources(
        [
            (
                selected_allatom_focus_summary,
                (),
                (
                    "wetlab_final_gate_pass",
                    "final_gate_pass",
                    "selected_allatom_wetlab_final_gate_pass",
                    "selected_allatom_final_gate_pass",
                ),
            ),
            (
                bsrhs,
                (),
                ("selected_allatom_wetlab_final_gate_pass", "selected_allatom_final_gate_pass"),
            ),
            (
                bcris,
                ("selected_allatom_final_gate_reported",),
                ("selected_allatom_final_gate_pass",),
            ),
        ]
    )
    selected_allatom_claim_gate_reported, selected_allatom_claim_gate_available = _resolve_explicit_bool_from_sources(
        [
            (
                selected_allatom_focus_summary,
                (),
                ("claim_gate_available", "selected_allatom_claim_gate_available"),
            ),
            (
                bcris,
                ("selected_allatom_claim_gate_available_reported",),
                ("selected_allatom_claim_gate_available",),
            ),
            (
                bsrhs,
                (),
                ("selected_allatom_claim_gate_available",),
            ),
        ]
    )
    selected_allatom_claim_ready_reported, selected_allatom_claim_ready = _resolve_explicit_bool_from_sources(
        [
            (
                selected_allatom_focus_summary,
                (),
                ("claim_ready_for_allatom", "selected_allatom_claim_ready_for_allatom"),
            ),
            (
                bcris,
                ("selected_allatom_claim_ready_for_allatom_reported",),
                ("selected_allatom_claim_ready_for_allatom",),
            ),
            (
                bsrhs,
                (),
                ("selected_allatom_claim_ready_for_allatom",),
            ),
        ]
    )
    selected_allatom_readiness_semantics = _normalize_selected_allatom_semantics(
        _text(
            bcris.get("selected_allatom_readiness_semantics", ""),
            bsrhs.get("selected_allatom_readiness_semantics", ""),
        ),
        focus_available=selected_allatom_focus_available,
        final_gate_reported=selected_allatom_final_gate_reported,
    )
    selected_allatom_claim_gate_source = _text(
        fcs.get("selected_allatom_claim_gate_source", ""),
        bcris.get("selected_allatom_claim_gate_source", ""),
        bsrhs.get("selected_allatom_claim_gate_source", ""),
        selected_allatom_focus_summary.get("claim_gate_source", ""),
    )
    selected_allatom_claim_ready_source = _text(
        fcs.get("selected_allatom_claim_ready_source", ""),
        bcris.get("selected_allatom_claim_ready_source", ""),
        bsrhs.get("selected_allatom_claim_ready_source", ""),
        selected_allatom_focus_summary.get("claim_ready_source", ""),
    )
    selected_allatom_commercial_hard_gate_raw = _resolve_first_value(
        [
            (fcs, "selected_allatom_commercial_hard_gate_pass_v1"),
            (bcris, "selected_allatom_commercial_hard_gate_pass_v1"),
            (bsrhs, "selected_allatom_commercial_hard_gate_pass_v1"),
            (selected_allatom_focus_summary, "commercial_hard_gate_pass_v1"),
        ]
    )
    selected_allatom_commercial_hard_gate_reported = selected_allatom_commercial_hard_gate_raw is not None
    selected_allatom_commercial_hard_gate_pass = (
        _coerce_bool(selected_allatom_commercial_hard_gate_raw)
        if selected_allatom_commercial_hard_gate_reported
        else False
    )
    selected_allatom_commercial_soft_score_v1 = _coerce_float(
        _resolve_first_value(
            [
                (fcs, "selected_allatom_commercial_soft_score_v1"),
                (bcris, "selected_allatom_commercial_soft_score_v1"),
                (bsrhs, "selected_allatom_commercial_soft_score_v1"),
                (selected_allatom_focus_summary, "commercial_soft_score_v1"),
            ]
        ),
        0.0,
    )
    selected_allatom_commercial_confidence_score_v1 = _coerce_float(
        _resolve_first_value(
            [
                (fcs, "selected_allatom_commercial_confidence_score_v1"),
                (bcris, "selected_allatom_commercial_confidence_score_v1"),
                (bsrhs, "selected_allatom_commercial_confidence_score_v1"),
                (selected_allatom_focus_summary, "commercial_confidence_score_v1"),
            ]
        ),
        0.0,
    )
    selected_allatom_commercial_overall_score_v1 = _coerce_float(
        _resolve_first_value(
            [
                (fcs, "selected_allatom_commercial_overall_score_v1"),
                (bcris, "selected_allatom_commercial_overall_score_v1"),
                (bsrhs, "selected_allatom_commercial_overall_score_v1"),
                (selected_allatom_focus_summary, "commercial_overall_score_v1"),
            ]
        ),
        0.0,
    )
    selected_allatom_commercial_risk_bucket_v1 = _text(
        fcs.get("selected_allatom_commercial_risk_bucket_v1", ""),
        bcris.get("selected_allatom_commercial_risk_bucket_v1", ""),
        bsrhs.get("selected_allatom_commercial_risk_bucket_v1", ""),
        selected_allatom_focus_summary.get("commercial_risk_bucket_v1", ""),
    )
    selected_allatom_commercial_decision_class_v1 = _text(
        fcs.get("selected_allatom_commercial_decision_class_v1", ""),
        bcris.get("selected_allatom_commercial_decision_class_v1", ""),
        bsrhs.get("selected_allatom_commercial_decision_class_v1", ""),
        selected_allatom_focus_summary.get("commercial_decision_class_v1", ""),
    )
    selected_allatom_commercial_primary_upgrade_actions_v1 = _coerce_text_list(
        _resolve_first_value(
            [
                (fcs, "selected_allatom_commercial_primary_upgrade_actions_v1"),
                (bcris, "selected_allatom_commercial_primary_upgrade_actions_v1"),
                (bsrhs, "selected_allatom_commercial_primary_upgrade_actions_v1"),
                (selected_allatom_focus_summary, "commercial_primary_upgrade_actions_v1"),
            ]
        )
    )
    selected_allatom_commercial_schema_version = _text(
        fcs.get("selected_allatom_commercial_schema_version", ""),
        bcris.get("selected_allatom_commercial_schema_version", ""),
        bsrhs.get("selected_allatom_commercial_schema_version", ""),
        selected_allatom_focus_summary.get("commercial_schema_version_v1", ""),
        selected_allatom_focus_summary.get("commercial_schema_version", ""),
    )
    selected_allatom_commercial_reported = bool(
        selected_allatom_commercial_schema_version
        or selected_allatom_commercial_hard_gate_reported
        or selected_allatom_commercial_overall_score_v1 > 0
        or selected_allatom_commercial_soft_score_v1 > 0
        or selected_allatom_commercial_confidence_score_v1 > 0
        or selected_allatom_commercial_risk_bucket_v1
        or selected_allatom_commercial_decision_class_v1
        or selected_allatom_commercial_primary_upgrade_actions_v1
    )
    selected_allatom_commercial_human_signal = _selected_allatom_commercial_signal(
        commercial_reported=selected_allatom_commercial_reported,
        schema_version=selected_allatom_commercial_schema_version,
        hard_gate_reported=selected_allatom_commercial_hard_gate_reported,
        hard_gate_pass=selected_allatom_commercial_hard_gate_pass,
        soft_score=selected_allatom_commercial_soft_score_v1,
        confidence_score=selected_allatom_commercial_confidence_score_v1,
        overall_score=selected_allatom_commercial_overall_score_v1,
        risk_bucket=selected_allatom_commercial_risk_bucket_v1,
        decision_class=selected_allatom_commercial_decision_class_v1,
        primary_upgrade_actions=selected_allatom_commercial_primary_upgrade_actions_v1,
    )
    selected_allatom_commercial_hard_gate_raw_v2 = _resolve_first_value(
        [
            (fcs, "selected_allatom_commercial_hard_gate_pass_v2"),
            (bcris, "selected_allatom_commercial_hard_gate_pass_v2"),
            (bsrhs, "selected_allatom_commercial_hard_gate_pass_v2"),
            (selected_allatom_focus_summary, "commercial_hard_gate_pass_v2"),
        ]
    )
    selected_allatom_commercial_hard_gate_reported_v2 = selected_allatom_commercial_hard_gate_raw_v2 is not None
    selected_allatom_commercial_hard_gate_pass_v2 = (
        _coerce_bool(selected_allatom_commercial_hard_gate_raw_v2)
        if selected_allatom_commercial_hard_gate_reported_v2
        else False
    )
    selected_allatom_commercial_soft_score_v2 = _coerce_float(
        _resolve_first_value(
            [
                (fcs, "selected_allatom_commercial_soft_score_v2"),
                (bcris, "selected_allatom_commercial_soft_score_v2"),
                (bsrhs, "selected_allatom_commercial_soft_score_v2"),
                (selected_allatom_focus_summary, "commercial_soft_score_v2"),
            ]
        ),
        0.0,
    )
    selected_allatom_commercial_confidence_score_v2 = _coerce_float(
        _resolve_first_value(
            [
                (fcs, "selected_allatom_commercial_confidence_score_v2"),
                (bcris, "selected_allatom_commercial_confidence_score_v2"),
                (bsrhs, "selected_allatom_commercial_confidence_score_v2"),
                (selected_allatom_focus_summary, "commercial_confidence_score_v2"),
            ]
        ),
        0.0,
    )
    selected_allatom_commercial_overall_score_v2 = _coerce_float(
        _resolve_first_value(
            [
                (fcs, "selected_allatom_commercial_overall_score_v2"),
                (bcris, "selected_allatom_commercial_overall_score_v2"),
                (bsrhs, "selected_allatom_commercial_overall_score_v2"),
                (selected_allatom_focus_summary, "commercial_overall_score_v2"),
            ]
        ),
        0.0,
    )
    selected_allatom_commercial_risk_bucket_v2 = _text(
        fcs.get("selected_allatom_commercial_risk_bucket_v2", ""),
        bcris.get("selected_allatom_commercial_risk_bucket_v2", ""),
        bsrhs.get("selected_allatom_commercial_risk_bucket_v2", ""),
        selected_allatom_focus_summary.get("commercial_risk_bucket_v2", ""),
    )
    selected_allatom_commercial_decision_class_v2 = _text(
        fcs.get("selected_allatom_commercial_decision_class_v2", ""),
        bcris.get("selected_allatom_commercial_decision_class_v2", ""),
        bsrhs.get("selected_allatom_commercial_decision_class_v2", ""),
        selected_allatom_focus_summary.get("commercial_decision_class_v2", ""),
    )
    selected_allatom_commercial_primary_upgrade_actions_v2 = _coerce_text_list(
        _resolve_first_value(
            [
                (fcs, "selected_allatom_commercial_primary_upgrade_actions_v2"),
                (bcris, "selected_allatom_commercial_primary_upgrade_actions_v2"),
                (bsrhs, "selected_allatom_commercial_primary_upgrade_actions_v2"),
                (selected_allatom_focus_summary, "commercial_primary_upgrade_actions_v2"),
            ]
        )
    )
    selected_allatom_commercial_schema_version_v2 = _text(
        fcs.get("selected_allatom_commercial_schema_version_v2", ""),
        bcris.get("selected_allatom_commercial_schema_version_v2", ""),
        bsrhs.get("selected_allatom_commercial_schema_version_v2", ""),
        selected_allatom_focus_summary.get("commercial_schema_version_v2", ""),
    )
    selected_allatom_commercial_human_summary_v2 = _text(
        fcs.get("selected_allatom_commercial_human_summary_v2", ""),
        bcris.get("selected_allatom_commercial_human_summary_v2", ""),
        bsrhs.get("selected_allatom_commercial_human_summary_v2", ""),
        selected_allatom_focus_summary.get("commercial_human_summary_v2", ""),
    )
    selected_allatom_commercial_reported_v2 = bool(
        selected_allatom_commercial_schema_version_v2
        or selected_allatom_commercial_hard_gate_reported_v2
        or selected_allatom_commercial_overall_score_v2 > 0
        or selected_allatom_commercial_soft_score_v2 > 0
        or selected_allatom_commercial_confidence_score_v2 > 0
        or selected_allatom_commercial_risk_bucket_v2
        or selected_allatom_commercial_decision_class_v2
        or selected_allatom_commercial_primary_upgrade_actions_v2
        or selected_allatom_commercial_human_summary_v2
    )
    selected_allatom_commercial_human_signal_v2 = _text(
        selected_allatom_commercial_human_summary_v2,
        _selected_allatom_commercial_signal(
            commercial_reported=selected_allatom_commercial_reported_v2,
            schema_version=selected_allatom_commercial_schema_version_v2,
            hard_gate_reported=selected_allatom_commercial_hard_gate_reported_v2,
            hard_gate_pass=selected_allatom_commercial_hard_gate_pass_v2,
            soft_score=selected_allatom_commercial_soft_score_v2,
            confidence_score=selected_allatom_commercial_confidence_score_v2,
            overall_score=selected_allatom_commercial_overall_score_v2,
            risk_bucket=selected_allatom_commercial_risk_bucket_v2,
            decision_class=selected_allatom_commercial_decision_class_v2,
            primary_upgrade_actions=selected_allatom_commercial_primary_upgrade_actions_v2,
        ),
    )
    selected_allatom_translation_gate_status = _text(
        fcs.get("selected_allatom_translation_gate_status", ""),
        bcris.get("selected_allatom_translation_gate_status", ""),
        bsrhs.get("selected_allatom_translation_gate_status", ""),
        selected_allatom_focus_summary.get("translation_gate_focus_status", ""),
    )
    selected_allatom_translation_gate_score_raw = _resolve_first_value(
        [
            (fcs, "selected_allatom_translation_gate_score"),
            (bcris, "selected_allatom_translation_gate_score"),
            (bsrhs, "selected_allatom_translation_gate_score"),
            (selected_allatom_focus_summary, "translation_gate_focus_score"),
        ]
    )
    selected_allatom_translation_gate_score_reported = selected_allatom_translation_gate_score_raw is not None
    selected_allatom_translation_gate_score = _coerce_float(
        selected_allatom_translation_gate_score_raw,
        0.0,
    )
    selected_allatom_translation_gate_reason = _text(
        fcs.get("selected_allatom_translation_gate_reason", ""),
        bcris.get("selected_allatom_translation_gate_reason", ""),
        bsrhs.get("selected_allatom_translation_gate_reason", ""),
        selected_allatom_focus_summary.get("translation_gate_focus_reason", ""),
    )
    selected_allatom_focus_shortlist_tier = _text(
        fcs.get("selected_allatom_focus_shortlist_tier", ""),
        bcris.get("selected_allatom_focus_shortlist_tier", ""),
        bsrhs.get("selected_allatom_focus_shortlist_tier", ""),
        selected_allatom_focus_summary.get("focus_shortlist_tier", ""),
    )
    selected_allatom_recommended_next_expensive_lane = _text(
        fcs.get("selected_allatom_recommended_next_expensive_lane", ""),
        bcris.get("selected_allatom_recommended_next_expensive_lane", ""),
        bsrhs.get("selected_allatom_recommended_next_expensive_lane", ""),
        selected_allatom_focus_summary.get("recommended_next_expensive_lane", ""),
    )
    selected_allatom_recommended_next_expensive_lane_reason = _text(
        fcs.get("selected_allatom_recommended_next_expensive_lane_reason", ""),
        bcris.get("selected_allatom_recommended_next_expensive_lane_reason", ""),
        bsrhs.get("selected_allatom_recommended_next_expensive_lane_reason", ""),
        selected_allatom_focus_summary.get("recommended_next_expensive_lane_reason", ""),
    )
    if not (
        selected_allatom_translation_gate_status
        and selected_allatom_focus_shortlist_tier
        and selected_allatom_recommended_next_expensive_lane
    ):
        translation_fallback = _infer_selected_allatom_translation_shortlist_fallback(
            bcris.get("selected_allatom_next_required_step", ""),
            fcs.get("selected_allatom_next_required_step", ""),
            bsrhs.get("selected_allatom_next_required_step", ""),
            selected_allatom_focus_summary.get("selected_allatom_next_required_step", ""),
            selected_allatom_focus_summary.get("next_required_step", ""),
        )
        if translation_fallback.get("reported", False):
            selected_allatom_translation_gate_status = _text(
                selected_allatom_translation_gate_status,
                translation_fallback.get("translation_gate_focus_status", ""),
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
    selected_allatom_translation_reported = bool(
        selected_allatom_translation_gate_status
        or selected_allatom_translation_gate_score_reported
        or selected_allatom_translation_gate_reason
        or selected_allatom_focus_shortlist_tier
        or selected_allatom_recommended_next_expensive_lane
        or selected_allatom_recommended_next_expensive_lane_reason
    )
    selected_allatom_translation_human_signal = _selected_allatom_translation_signal(
        translation_reported=selected_allatom_translation_reported,
        translation_status=selected_allatom_translation_gate_status,
        translation_score_reported=selected_allatom_translation_gate_score_reported,
        translation_score=selected_allatom_translation_gate_score,
        translation_reason=selected_allatom_translation_gate_reason,
        shortlist_tier=selected_allatom_focus_shortlist_tier,
        recommended_next_expensive_lane=selected_allatom_recommended_next_expensive_lane,
        recommended_next_expensive_lane_reason=selected_allatom_recommended_next_expensive_lane_reason,
    )
    selected_allatom_actionability_human_summary = _text(
        bcris.get("selected_allatom_actionability_human_summary", ""),
        fcs.get("selected_allatom_actionability_human_summary", ""),
        bsrhs.get("selected_allatom_actionability_human_summary", ""),
        selected_allatom_focus_summary.get("selected_allatom_actionability_human_summary", ""),
    )
    selected_allatom_actionability_brief_summary = _text(
        bcris.get("selected_allatom_actionability_brief_summary", ""),
        fcs.get("selected_allatom_actionability_brief_summary", ""),
        bsrhs.get("selected_allatom_actionability_brief_summary", ""),
        selected_allatom_focus_summary.get("selected_allatom_actionability_brief_summary", ""),
    )
    selected_allatom_actionability_status = _text(
        bcris.get("selected_allatom_actionability_status", ""),
        fcs.get("selected_allatom_actionability_status", ""),
        bsrhs.get("selected_allatom_actionability_status", ""),
        selected_allatom_focus_summary.get("selected_allatom_actionability_status", ""),
    )
    selected_allatom_actionability_block_reason = _text(
        bcris.get("selected_allatom_actionability_block_reason", ""),
        fcs.get("selected_allatom_actionability_block_reason", ""),
        bsrhs.get("selected_allatom_actionability_block_reason", ""),
        selected_allatom_focus_summary.get("selected_allatom_actionability_block_reason", ""),
    )
    selected_allatom_actionability_required_calculations_text = _text(
        bcris.get("selected_allatom_actionability_required_calculations_text", ""),
        fcs.get("selected_allatom_actionability_required_calculations_text", ""),
        bsrhs.get("selected_allatom_actionability_required_calculations_text", ""),
        selected_allatom_focus_summary.get("selected_allatom_actionability_required_calculations_text", ""),
    )
    selected_allatom_actionability_action_list_text = _text(
        bcris.get("selected_allatom_actionability_action_list_text", ""),
        fcs.get("selected_allatom_actionability_action_list_text", ""),
        bsrhs.get("selected_allatom_actionability_action_list_text", ""),
        selected_allatom_focus_summary.get("selected_allatom_actionability_action_list_text", ""),
    )
    selected_allatom_actionability_claim_requirement_mode = _text(
        bcris.get("selected_allatom_actionability_claim_requirement_mode", ""),
        fcs.get("selected_allatom_actionability_claim_requirement_mode", ""),
        bsrhs.get("selected_allatom_actionability_claim_requirement_mode", ""),
        selected_allatom_focus_summary.get("selected_allatom_actionability_claim_requirement_mode", ""),
    )
    selected_allatom_actionability_claim_requirement_status = _text(
        bcris.get("selected_allatom_actionability_claim_requirement_status", ""),
        fcs.get("selected_allatom_actionability_claim_requirement_status", ""),
        bsrhs.get("selected_allatom_actionability_claim_requirement_status", ""),
        selected_allatom_focus_summary.get("selected_allatom_actionability_claim_requirement_status", ""),
    )
    selected_allatom_actionability_next_expensive_lane = _text(
        bcris.get("selected_allatom_actionability_next_expensive_lane", ""),
        fcs.get("selected_allatom_actionability_next_expensive_lane", ""),
        bsrhs.get("selected_allatom_actionability_next_expensive_lane", ""),
        selected_allatom_focus_summary.get("selected_allatom_actionability_next_expensive_lane", ""),
    )
    selected_allatom_actionability_next_expensive_lane_reason = _text(
        bcris.get("selected_allatom_actionability_next_expensive_lane_reason", ""),
        fcs.get("selected_allatom_actionability_next_expensive_lane_reason", ""),
        bsrhs.get("selected_allatom_actionability_next_expensive_lane_reason", ""),
        selected_allatom_focus_summary.get("selected_allatom_actionability_next_expensive_lane_reason", ""),
    )
    if not (
        selected_allatom_actionability_status
        or selected_allatom_actionability_human_summary
        or selected_allatom_actionability_brief_summary
        or selected_allatom_actionability_block_reason
        or selected_allatom_actionability_required_calculations_text
        or selected_allatom_actionability_action_list_text
        or selected_allatom_actionability_claim_requirement_mode
        or selected_allatom_actionability_next_expensive_lane
    ):
        selected_allatom_actionability_fallback = _selected_allatom_actionability_fallback(
            final_gate_pass=selected_allatom_final_gate_pass,
            operator_review_ready=selected_allatom_operator_review_ready,
            commercial_hard_gate_blocked=bool(
                (selected_allatom_commercial_reported and not selected_allatom_commercial_hard_gate_pass)
                or (selected_allatom_commercial_reported_v2 and not selected_allatom_commercial_hard_gate_pass_v2)
            ),
            claim_gate_available=selected_allatom_claim_gate_available,
            claim_ready_for_allatom=selected_allatom_claim_ready,
            translation_status=selected_allatom_translation_gate_status,
            translation_reason=selected_allatom_translation_gate_reason,
            shortlist_tier=selected_allatom_focus_shortlist_tier,
            next_expensive_lane=selected_allatom_recommended_next_expensive_lane,
            next_expensive_lane_reason=selected_allatom_recommended_next_expensive_lane_reason,
            next_required_step=_text(
                str(bcris.get("selected_allatom_next_required_step", "")).strip(),
                str(bsrhs.get("selected_allatom_next_required_step", "")).strip(),
                selected_allatom_focus_summary.get("next_required_step", ""),
            ),
        )
        selected_allatom_actionability_status = _text(
            selected_allatom_actionability_status,
            selected_allatom_actionability_fallback.get("status"),
        )
        selected_allatom_actionability_brief_summary = _text(
            selected_allatom_actionability_brief_summary,
            selected_allatom_actionability_fallback.get("brief_summary"),
        )
        selected_allatom_actionability_human_summary = _text(
            selected_allatom_actionability_human_summary,
            selected_allatom_actionability_fallback.get("human_summary"),
        )
        selected_allatom_actionability_block_reason = _text(
            selected_allatom_actionability_block_reason,
            selected_allatom_actionability_fallback.get("block_reason"),
        )
        selected_allatom_actionability_required_calculations_text = _text(
            selected_allatom_actionability_required_calculations_text,
            selected_allatom_actionability_fallback.get("required_calculations_text"),
        )
        selected_allatom_actionability_action_list_text = _text(
            selected_allatom_actionability_action_list_text,
            selected_allatom_actionability_fallback.get("action_list_text"),
        )
        selected_allatom_actionability_claim_requirement_mode = _text(
            selected_allatom_actionability_claim_requirement_mode,
            selected_allatom_actionability_fallback.get("claim_requirement_mode"),
        )
        selected_allatom_actionability_claim_requirement_status = _text(
            selected_allatom_actionability_claim_requirement_status,
            selected_allatom_actionability_fallback.get("claim_requirement_status"),
        )
        selected_allatom_actionability_next_expensive_lane = _text(
            selected_allatom_actionability_next_expensive_lane,
            selected_allatom_actionability_fallback.get("next_expensive_lane"),
        )
        selected_allatom_actionability_next_expensive_lane_reason = _text(
            selected_allatom_actionability_next_expensive_lane_reason,
            selected_allatom_actionability_fallback.get("next_expensive_lane_reason"),
        )
    selected_allatom_next_required_step = _text(
        str(bcris.get("selected_allatom_next_required_step", "")).strip(),
        str(bsrhs.get("selected_allatom_next_required_step", "")).strip(),
        selected_allatom_focus_summary.get("next_required_step", ""),
    )
    selected_allatom_next_required_step = selected_allatom_green_next_required_step(
        wetlab_gate_pass=selected_allatom_wetlab_gate_pass,
        final_gate_pass=selected_allatom_final_gate_pass,
        claim_ready_for_allatom=selected_allatom_claim_ready,
        translation_gate_focus_status=selected_allatom_translation_gate_status,
        recommended_next_expensive_lane=selected_allatom_recommended_next_expensive_lane,
        fallback_next_required_step=selected_allatom_next_required_step,
    )
    selected_allatom_actionability_next_expensive_lane = _text(
        selected_allatom_actionability_next_expensive_lane,
        _selected_allatom_inferred_next_expensive_lane(
            selected_allatom_focus_shortlist_tier,
            selected_allatom_translation_gate_status,
            selected_allatom_actionability_next_expensive_lane_reason,
            selected_allatom_next_required_step,
        ),
    )
    selected_allatom_actionability_next_expensive_lane_reason = _text(
        selected_allatom_actionability_next_expensive_lane_reason,
        selected_allatom_recommended_next_expensive_lane_reason,
        selected_allatom_next_required_step,
    )
    selected_allatom_raw_claim_requirement_mode = _infer_raw_claim_requirement_mode(
        selected_allatom_target_id,
        _text(
        selected_allatom_focus_summary.get("selected_allatom_raw_claim_requirement_mode", ""),
        selected_allatom_focus_summary.get("claim_gate_requirement_mode", ""),
        bcris.get("selected_allatom_raw_claim_requirement_mode", ""),
        bcris.get("selected_allatom_claim_requirement_mode", ""),
        fcs.get("selected_allatom_raw_claim_requirement_mode", ""),
        fcs.get("selected_allatom_claim_requirement_mode", ""),
        bsrhs.get("selected_allatom_raw_claim_requirement_mode", ""),
        bsrhs.get("selected_allatom_claim_requirement_mode", ""),
        ),
        selected_allatom_claim_gate_reported,
    )
    selected_allatom_raw_claim_requirement_provenance = _text(
        selected_allatom_focus_summary.get("selected_allatom_raw_claim_requirement_provenance", ""),
        selected_allatom_focus_summary.get("claim_gate_requirement_provenance", ""),
        bcris.get("selected_allatom_raw_claim_requirement_provenance", ""),
        bcris.get("selected_allatom_claim_requirement_provenance", ""),
        fcs.get("selected_allatom_raw_claim_requirement_provenance", ""),
        fcs.get("selected_allatom_claim_requirement_provenance", ""),
        bsrhs.get("selected_allatom_raw_claim_requirement_provenance", ""),
        bsrhs.get("selected_allatom_claim_requirement_provenance", ""),
        "target_group_default" if selected_allatom_raw_claim_requirement_mode == "semi_hard" else "",
        "inferred_from_claim_gate_availability" if selected_allatom_claim_gate_reported else "",
    )
    selected_allatom_raw_claim_required_for_final_wetlab = _resolve_bool(
        selected_allatom_focus_summary.get("selected_allatom_raw_claim_required_for_final_wetlab"),
        selected_allatom_focus_summary.get("claim_gate_required_for_final_wetlab"),
        bcris.get("selected_allatom_raw_claim_required_for_final_wetlab"),
        bcris.get("selected_allatom_claim_required_for_final_wetlab"),
        fcs.get("selected_allatom_raw_claim_required_for_final_wetlab"),
        fcs.get("selected_allatom_claim_required_for_final_wetlab"),
        bsrhs.get("selected_allatom_raw_claim_required_for_final_wetlab"),
        bsrhs.get("selected_allatom_claim_required_for_final_wetlab"),
        default=selected_allatom_raw_claim_requirement_mode == "semi_hard",
    )
    selected_allatom_raw_claim_required_for_commercial_readiness = _resolve_bool(
        selected_allatom_focus_summary.get("selected_allatom_raw_claim_required_for_commercial_readiness"),
        selected_allatom_focus_summary.get("claim_gate_required_for_commercial_readiness"),
        bcris.get("selected_allatom_raw_claim_required_for_commercial_readiness"),
        bcris.get("selected_allatom_claim_required_for_commercial_readiness"),
        fcs.get("selected_allatom_raw_claim_required_for_commercial_readiness"),
        fcs.get("selected_allatom_claim_required_for_commercial_readiness"),
        bsrhs.get("selected_allatom_raw_claim_required_for_commercial_readiness"),
        bsrhs.get("selected_allatom_claim_required_for_commercial_readiness"),
        default=selected_allatom_raw_claim_requirement_mode == "semi_hard",
    )
    selected_allatom_raw_claim_requirement_reason = _text(
        selected_allatom_focus_summary.get("selected_allatom_raw_claim_requirement_reason", ""),
        selected_allatom_focus_summary.get("claim_gate_requirement_reason", ""),
        bcris.get("selected_allatom_raw_claim_requirement_reason", ""),
        bcris.get("selected_allatom_claim_requirement_reason", ""),
        fcs.get("selected_allatom_raw_claim_requirement_reason", ""),
        fcs.get("selected_allatom_claim_requirement_reason", ""),
        bsrhs.get("selected_allatom_raw_claim_requirement_reason", ""),
        bsrhs.get("selected_allatom_claim_requirement_reason", ""),
        (
            f"{selected_allatom_target_id} is in the neglected_disease_priority_v1 target group, so final wetlab advancement expects claim/equivalence evidence before release."
            if selected_allatom_raw_claim_requirement_mode == "semi_hard"
            else ""
        ),
    )
    selected_allatom_raw_claim_requirement_actions = _coerce_text_list(
        selected_allatom_focus_summary.get(
            "selected_allatom_raw_claim_requirement_actions",
            selected_allatom_focus_summary.get("claim_gate_requirement_actions", []),
        )
    ) or _coerce_text_list(
        bcris.get("selected_allatom_raw_claim_requirement_actions", "")
        or bcris.get("selected_allatom_claim_requirement_actions", "")
        or fcs.get("selected_allatom_raw_claim_requirement_actions", "")
        or fcs.get("selected_allatom_claim_requirement_actions", "")
        or bsrhs.get("selected_allatom_raw_claim_requirement_actions", "")
        or bsrhs.get("selected_allatom_claim_requirement_actions", "")
    )
    selected_allatom_effective_actionability_status = _text(
        selected_allatom_actionability_status,
        bcris.get("selected_allatom_effective_actionability_status", ""),
        fcs.get("selected_allatom_effective_actionability_status", ""),
        bsrhs.get("selected_allatom_effective_actionability_status", ""),
    )
    selected_allatom_effective_actionability_claim_requirement_mode = _text(
        bcris.get("selected_allatom_effective_actionability_claim_requirement_mode", ""),
        fcs.get("selected_allatom_effective_actionability_claim_requirement_mode", ""),
        bsrhs.get("selected_allatom_effective_actionability_claim_requirement_mode", ""),
        selected_allatom_actionability_claim_requirement_mode,
    )
    selected_allatom_effective_actionability_claim_requirement_status = _text(
        bcris.get("selected_allatom_effective_actionability_claim_requirement_status", ""),
        fcs.get("selected_allatom_effective_actionability_claim_requirement_status", ""),
        bsrhs.get("selected_allatom_effective_actionability_claim_requirement_status", ""),
        selected_allatom_actionability_claim_requirement_status,
    )
    selected_allatom_effective_actionability_claim_requirement_reason = _text(
        bcris.get("selected_allatom_effective_actionability_claim_requirement_reason", ""),
        fcs.get("selected_allatom_effective_actionability_claim_requirement_reason", ""),
        bsrhs.get("selected_allatom_effective_actionability_claim_requirement_reason", ""),
        selected_allatom_actionability_block_reason,
        selected_allatom_actionability_human_summary,
    )
    selected_allatom_effective_blocking_order = _selected_allatom_effective_blocking_order(
        effective_status=selected_allatom_effective_actionability_status,
        raw_claim_requirement_mode=selected_allatom_raw_claim_requirement_mode,
        effective_claim_requirement_mode=selected_allatom_effective_actionability_claim_requirement_mode,
    )
    selected_allatom_effective_primary_blocking_domain = _selected_allatom_effective_primary_blocking_domain(
        effective_status=selected_allatom_effective_actionability_status,
        translation_status=selected_allatom_translation_gate_status,
        commercial_hard_gate_reported=bool(
            selected_allatom_commercial_hard_gate_reported or selected_allatom_commercial_hard_gate_reported_v2
        ),
        commercial_hard_gate_pass=bool(
            (selected_allatom_commercial_hard_gate_pass_v2 if selected_allatom_commercial_hard_gate_reported_v2 else True)
            and (selected_allatom_commercial_hard_gate_pass if selected_allatom_commercial_hard_gate_reported else True)
        ),
        effective_claim_requirement_mode=selected_allatom_effective_actionability_claim_requirement_mode,
    )
    selected_allatom_action_recipe = _selected_allatom_action_recipe(
        translation_status=selected_allatom_translation_gate_status,
        translation_failed_checks=_coerce_text_list(
            selected_allatom_focus_summary.get("translation_gate_focus_failed_checks", [])
        ),
        translation_warning_checks=_coerce_text_list(
            selected_allatom_focus_summary.get("translation_gate_focus_warning_checks", [])
        ),
        raw_claim_requirement_mode=selected_allatom_raw_claim_requirement_mode,
        raw_claim_requirement_reason=selected_allatom_raw_claim_requirement_reason,
        raw_claim_requirement_actions=selected_allatom_raw_claim_requirement_actions,
        claim_ready_for_allatom=selected_allatom_claim_ready,
        recommended_next_expensive_lane=selected_allatom_actionability_next_expensive_lane,
        recommended_next_expensive_lane_reason=selected_allatom_actionability_next_expensive_lane_reason,
    )
    selected_allatom_best_mean_min_distance_A = _coerce_float(
        _resolve_first_value(
            [
                (bsrhs, "selected_allatom_best_mean_min_distance_A"),
                (bcris, "selected_allatom_best_mean_min_distance_A"),
            ]
        ),
        0.0,
    )
    selected_allatom_metric_source = (
        "retry_handoff_summary.selected_allatom_best_mean_min_distance_A"
        if _has_value(bsrhs, "selected_allatom_best_mean_min_distance_A")
        else "current_results_index.selected_allatom_best_mean_min_distance_A"
        if _has_value(bcris, "selected_allatom_best_mean_min_distance_A")
        else ""
    )
    fallback_selected_allatom_canonical = {
        "commercial_schema_version_v2": selected_allatom_commercial_schema_version_v2,
        "commercial_overall_score_v2": selected_allatom_commercial_overall_score_v2,
        "commercial_risk_bucket_v2": selected_allatom_commercial_risk_bucket_v2,
        "commercial_decision_class_v2": selected_allatom_commercial_decision_class_v2,
        "commercial_primary_upgrade_actions_v2": list(selected_allatom_commercial_primary_upgrade_actions_v2),
        "translation_gate_version": selected_allatom_focus_summary.get("translation_gate_version", ""),
        "translation_gate_focus_status": selected_allatom_translation_gate_status,
        "translation_gate_focus_score": selected_allatom_translation_gate_score,
        "translation_gate_focus_reason": selected_allatom_translation_gate_reason,
        "focus_shortlist_tier": selected_allatom_focus_shortlist_tier,
        "recommended_next_expensive_lane": selected_allatom_recommended_next_expensive_lane,
        "recommended_next_expensive_lane_reason": selected_allatom_recommended_next_expensive_lane_reason,
        "best_mean_min_distance_A": selected_allatom_best_mean_min_distance_A,
        "best_mean_min_distance_source": selected_allatom_metric_source,
        "raw_claim_requirement_mode": selected_allatom_raw_claim_requirement_mode,
        "raw_claim_requirement_provenance": selected_allatom_raw_claim_requirement_provenance,
        "raw_claim_required_for_final_wetlab": selected_allatom_raw_claim_required_for_final_wetlab,
        "raw_claim_required_for_commercial_readiness": selected_allatom_raw_claim_required_for_commercial_readiness,
        "raw_claim_requirement_reason": selected_allatom_raw_claim_requirement_reason,
        "effective_actionability_status": selected_allatom_effective_actionability_status,
        "effective_actionability_claim_requirement_mode": selected_allatom_effective_actionability_claim_requirement_mode,
        "effective_actionability_claim_requirement_status": selected_allatom_effective_actionability_claim_requirement_status,
        "effective_actionability_claim_requirement_reason": selected_allatom_effective_actionability_claim_requirement_reason,
        "effective_actionability_next_expensive_lane": selected_allatom_actionability_next_expensive_lane,
        "effective_actionability_next_expensive_lane_reason": selected_allatom_actionability_next_expensive_lane_reason,
        "effective_actionability_required_calculations": _coerce_text_list(
            selected_allatom_actionability_required_calculations_text
        ),
        "effective_actionability_action_list": list(selected_allatom_action_recipe["action_recipe_rows"]),
        "effective_blocking_order": selected_allatom_effective_blocking_order,
        "effective_primary_blocking_domain": selected_allatom_effective_primary_blocking_domain,
        "action_recipe_codes": list(selected_allatom_action_recipe["action_recipe_codes"]),
        "action_recipe_rows": list(selected_allatom_action_recipe["action_recipe_rows"]),
        "translation_provenance_mode": _text(
            bcris.get("selected_allatom_translation_provenance_mode", ""),
            fcs.get("selected_allatom_translation_provenance_mode", ""),
            bsrhs.get("selected_allatom_translation_provenance_mode", ""),
        ),
        "commercial_provenance_mode_v2": _text(
            bcris.get("selected_allatom_commercial_provenance_mode_v2", ""),
            fcs.get("selected_allatom_commercial_provenance_mode_v2", ""),
            bsrhs.get("selected_allatom_commercial_provenance_mode_v2", ""),
        ),
        "hybrid_policy": _text(
            bcris.get("selected_allatom_hybrid_policy", ""),
            fcs.get("selected_allatom_hybrid_policy", ""),
            "canonical_scores_source_only__translation_shortlist_labeled_fallback",
        ),
    }
    selected_allatom_canonical = _resolve_selected_allatom_canonical_with_fallback(
        fallback=fallback_selected_allatom_canonical,
        review_packet_summary=selected_allatom_focus_summary,
        retry_handoff_summary=bsrhs,
        current_results_index_summary=bcris,
        monitor_semantics_summary=bsmss,
        final_campaign_summary=fcs,
        next_required_step=selected_allatom_next_required_step,
    )
    selected_allatom_canonical_resolver_used = bool(
        selected_allatom_canonical.get("__canonical_resolver_used__", False)
    )
    if selected_allatom_canonical_resolver_used:
        canonical_schema_v2 = selected_allatom_canonical.get("commercial_schema_version_v2")
        if _canonical_value_present(canonical_schema_v2):
            selected_allatom_commercial_schema_version_v2 = _text(canonical_schema_v2)
        canonical_hard_gate_v2 = selected_allatom_canonical.get("commercial_hard_gate_pass_v2")
        if _canonical_value_present(canonical_hard_gate_v2):
            selected_allatom_commercial_hard_gate_reported_v2 = True
            selected_allatom_commercial_hard_gate_pass_v2 = _coerce_bool(canonical_hard_gate_v2)
        canonical_soft_v2 = selected_allatom_canonical.get("commercial_soft_score_v2")
        if _canonical_value_present(canonical_soft_v2):
            selected_allatom_commercial_soft_score_v2 = _coerce_float(canonical_soft_v2, 0.0)
        canonical_confidence_v2 = selected_allatom_canonical.get("commercial_confidence_score_v2")
        if _canonical_value_present(canonical_confidence_v2):
            selected_allatom_commercial_confidence_score_v2 = _coerce_float(
                canonical_confidence_v2,
                0.0,
            )
        canonical_overall_v2 = selected_allatom_canonical.get("commercial_overall_score_v2")
        if _canonical_value_present(canonical_overall_v2):
            selected_allatom_commercial_overall_score_v2 = _coerce_float(canonical_overall_v2, 0.0)
        canonical_risk_v2 = selected_allatom_canonical.get("commercial_risk_bucket_v2")
        if _canonical_value_present(canonical_risk_v2):
            selected_allatom_commercial_risk_bucket_v2 = _text(canonical_risk_v2)
        canonical_decision_v2 = selected_allatom_canonical.get("commercial_decision_class_v2")
        if _canonical_value_present(canonical_decision_v2):
            selected_allatom_commercial_decision_class_v2 = _text(canonical_decision_v2)
        canonical_actions_v2 = selected_allatom_canonical.get("commercial_primary_upgrade_actions_v2")
        if _canonical_value_present(canonical_actions_v2):
            selected_allatom_commercial_primary_upgrade_actions_v2 = _coerce_text_list(
                canonical_actions_v2
            )
        canonical_human_v2 = selected_allatom_canonical.get("commercial_human_summary_v2")
        if _canonical_value_present(canonical_human_v2):
            selected_allatom_commercial_human_summary_v2 = _text(canonical_human_v2)
        selected_allatom_commercial_reported_v2 = bool(
            selected_allatom_commercial_schema_version_v2
            or selected_allatom_commercial_hard_gate_reported_v2
            or selected_allatom_commercial_overall_score_v2 > 0
            or selected_allatom_commercial_soft_score_v2 > 0
            or selected_allatom_commercial_confidence_score_v2 > 0
            or selected_allatom_commercial_risk_bucket_v2
            or selected_allatom_commercial_decision_class_v2
            or selected_allatom_commercial_primary_upgrade_actions_v2
            or selected_allatom_commercial_human_summary_v2
        )
        selected_allatom_commercial_human_signal_v2 = _text(
            selected_allatom_commercial_human_summary_v2,
            _selected_allatom_commercial_signal(
                commercial_reported=selected_allatom_commercial_reported_v2,
                schema_version=selected_allatom_commercial_schema_version_v2,
                hard_gate_reported=selected_allatom_commercial_hard_gate_reported_v2,
                hard_gate_pass=selected_allatom_commercial_hard_gate_pass_v2,
                soft_score=selected_allatom_commercial_soft_score_v2,
                confidence_score=selected_allatom_commercial_confidence_score_v2,
                overall_score=selected_allatom_commercial_overall_score_v2,
                risk_bucket=selected_allatom_commercial_risk_bucket_v2,
                decision_class=selected_allatom_commercial_decision_class_v2,
                primary_upgrade_actions=selected_allatom_commercial_primary_upgrade_actions_v2,
            ),
        )
    canonical_best_mean_min_distance_A = _coerce_float(
        selected_allatom_canonical.get("best_mean_min_distance_A"),
        0.0,
    )
    if canonical_best_mean_min_distance_A > 0.0:
        selected_allatom_best_mean_min_distance_A = canonical_best_mean_min_distance_A
        selected_allatom_metric_source = _text(
            selected_allatom_canonical.get("best_mean_min_distance_source", ""),
            selected_allatom_metric_source,
        )
    selected_allatom_promoted_candidate_count = _safe_int(
        _resolve_first_value(
            [
                (bcris, "selected_allatom_promoted_candidate_count"),
                (selected_allatom_focus_summary, "promoted_candidate_count"),
                (bsrhs, "selected_allatom_promoted_candidate_count"),
            ]
        )
    )
    selected_allatom_under_2p5_candidate_count = _safe_int(
        _resolve_first_value(
            [
                (bcris, "selected_allatom_under_2p5_candidate_count"),
                (selected_allatom_focus_summary, "under_2p5_candidate_count"),
                (bsrhs, "selected_allatom_under_2p5_candidate_count"),
            ]
        )
    )
    selected_allatom_near_candidate_count = _safe_int(
        _resolve_first_value(
            [
                (bcris, "selected_allatom_near_candidate_count"),
                (selected_allatom_focus_summary, "near_candidate_count"),
                (bsrhs, "selected_allatom_near_candidate_count"),
            ]
        )
    )
    selected_allatom_raw_claim_requirement_mode = _text(
        selected_allatom_canonical.get("raw_claim_requirement_mode", ""),
        selected_allatom_raw_claim_requirement_mode,
    )
    selected_allatom_raw_claim_requirement_provenance = _text(
        selected_allatom_canonical.get("raw_claim_requirement_provenance", ""),
        selected_allatom_raw_claim_requirement_provenance,
    )
    selected_allatom_raw_claim_required_for_final_wetlab = _resolve_bool(
        selected_allatom_canonical.get("raw_claim_required_for_final_wetlab"),
        selected_allatom_raw_claim_required_for_final_wetlab,
        default=False,
    )
    selected_allatom_raw_claim_required_for_commercial_readiness = _resolve_bool(
        selected_allatom_canonical.get("raw_claim_required_for_commercial_readiness"),
        selected_allatom_raw_claim_required_for_commercial_readiness,
        default=False,
    )
    if selected_allatom_raw_claim_requirement_mode == "semi_hard":
        selected_allatom_raw_claim_required_for_final_wetlab = True
        selected_allatom_raw_claim_required_for_commercial_readiness = True
    selected_allatom_raw_claim_requirement_reason = _text(
        selected_allatom_canonical.get("raw_claim_requirement_reason", ""),
        selected_allatom_raw_claim_requirement_reason,
    )
    selected_allatom_effective_actionability_status = _text(
        selected_allatom_canonical.get("effective_actionability_status", ""),
        selected_allatom_effective_actionability_status,
    )
    selected_allatom_effective_actionability_claim_requirement_mode = _text(
        selected_allatom_canonical.get("effective_actionability_claim_requirement_mode", ""),
        selected_allatom_effective_actionability_claim_requirement_mode,
    )
    selected_allatom_effective_actionability_claim_requirement_status = _text(
        selected_allatom_canonical.get("effective_actionability_claim_requirement_status", ""),
        selected_allatom_effective_actionability_claim_requirement_status,
    )
    selected_allatom_effective_actionability_claim_requirement_reason = _text(
        selected_allatom_canonical.get("effective_actionability_claim_requirement_reason", ""),
        selected_allatom_effective_actionability_claim_requirement_reason,
    )
    selected_allatom_effective_blocking_order = _text(
        selected_allatom_canonical.get("effective_blocking_order", ""),
        selected_allatom_effective_blocking_order,
    )
    selected_allatom_effective_primary_blocking_domain = _text(
        selected_allatom_canonical.get("effective_primary_blocking_domain", ""),
        selected_allatom_effective_primary_blocking_domain,
    )
    selected_allatom_action_recipe_codes = (
        _coerce_text_list(selected_allatom_canonical.get("action_recipe_codes"))
        if selected_allatom_canonical_resolver_used
        else list(selected_allatom_action_recipe["action_recipe_codes"])
    )
    selected_allatom_action_recipe_rows = (
        list(selected_allatom_canonical.get("action_recipe_rows", []) or [])
        if selected_allatom_canonical_resolver_used
        else list(selected_allatom_action_recipe["action_recipe_rows"])
    )
    selected_allatom_action_recipe_rollup_text = _text(
        selected_allatom_canonical.get("action_recipe_rollup_text", "")
        if selected_allatom_canonical_resolver_used
        else "",
        selected_allatom_action_recipe["action_recipe_rollup_text"],
    )
    selected_allatom_effective_required_calculations = _coerce_text_list(
        selected_allatom_canonical.get("effective_actionability_required_calculations", [])
    )
    if selected_allatom_canonical_resolver_used:
        selected_allatom_actionability_required_calculations_text = ", ".join(
            selected_allatom_effective_required_calculations
        )
    elif not selected_allatom_actionability_required_calculations_text and selected_allatom_effective_required_calculations:
        selected_allatom_actionability_required_calculations_text = ", ".join(
            selected_allatom_effective_required_calculations
        )
    selected_allatom_actionability_status = selected_allatom_effective_actionability_status
    selected_allatom_actionability_claim_requirement_mode = selected_allatom_effective_actionability_claim_requirement_mode
    selected_allatom_actionability_claim_requirement_status = selected_allatom_effective_actionability_claim_requirement_status
    selected_allatom_actionability_human_summary = _text(
        selected_allatom_actionability_human_summary,
        selected_allatom_action_recipe_rollup_text,
    )
    selected_allatom_actionability_display = _text(
        selected_allatom_actionability_human_summary,
        selected_allatom_actionability_brief_summary,
        f"lane {selected_allatom_actionability_next_expensive_lane}" if selected_allatom_actionability_next_expensive_lane else "",
    )
    selected_allatom_human_signal = _selected_allatom_human_signal(
        target_id=selected_allatom_target_id,
        surface_label=selected_allatom_surface_label,
        focus_available=selected_allatom_focus_available,
        operator_review_reported=selected_allatom_operator_review_reported,
        operator_review_ready=selected_allatom_operator_review_ready,
        wetlab_gate_reported=selected_allatom_wetlab_gate_reported,
        wetlab_gate_pass=selected_allatom_wetlab_gate_pass,
        final_gate_reported=selected_allatom_final_gate_reported,
        final_gate_pass=selected_allatom_final_gate_pass,
        claim_gate_reported=selected_allatom_claim_gate_reported,
        claim_gate_available=selected_allatom_claim_gate_available,
        claim_ready_reported=selected_allatom_claim_ready_reported,
        claim_ready_for_allatom=selected_allatom_claim_ready,
        packet_scope=str(
            bsrhs.get("selected_allatom_packet_scope", bcris.get("selected_allatom_packet_scope", ""))
        ).strip(),
        selected_command_kind=str(
            bsrhs.get("selected_allatom_selected_command_kind", bcris.get("selected_allatom_selected_command_kind", ""))
        ).strip(),
        selected_threshold_A=float(
            bsrhs.get("selected_allatom_selected_threshold_A", bcris.get("selected_allatom_selected_threshold_A", 0.0))
            or 0.0
        ),
        best_compound_name=str(
            bsrhs.get("selected_allatom_best_compound_name", bcris.get("selected_allatom_best_compound_name", ""))
        ).strip(),
        best_compound_name_human_readable=str(
            bsrhs.get(
                "selected_allatom_best_compound_name_human_readable",
                bcris.get("selected_allatom_best_compound_name_human_readable", ""),
            )
        ).strip(),
        best_compound_name_resolution=str(
            bsrhs.get(
                "selected_allatom_best_compound_name_resolution",
                bcris.get("selected_allatom_best_compound_name_resolution", "unresolved"),
            )
        ).strip(),
        best_mean_min_distance_A=selected_allatom_best_mean_min_distance_A,
        promoted_candidate_count=selected_allatom_promoted_candidate_count,
        under_2p5_candidate_count=selected_allatom_under_2p5_candidate_count,
        near_candidate_count=selected_allatom_near_candidate_count,
    )
    if selected_allatom_commercial_human_signal:
        selected_allatom_human_signal = f"{selected_allatom_human_signal} {selected_allatom_commercial_human_signal}"
    if selected_allatom_commercial_human_signal_v2:
        selected_allatom_human_signal = f"{selected_allatom_human_signal} {selected_allatom_commercial_human_signal_v2}"
    if selected_allatom_translation_human_signal:
        selected_allatom_human_signal = f"{selected_allatom_human_signal} {selected_allatom_translation_human_signal}"
    if selected_allatom_actionability_display:
        selected_allatom_human_signal = f"{selected_allatom_human_signal} Actionability: {selected_allatom_actionability_display}"
    selected_allatom_claim_actionability_split_summary = _joined(
        f"raw claim {selected_allatom_raw_claim_requirement_mode}"
        if selected_allatom_raw_claim_requirement_mode
        else "",
        "required for final wetlab" if selected_allatom_raw_claim_required_for_final_wetlab else "",
        "required for commercial readiness"
        if selected_allatom_raw_claim_required_for_commercial_readiness
        else "",
        f"effective actionability {selected_allatom_effective_actionability_status}"
        if selected_allatom_effective_actionability_status
        else "",
        f"effective claim {selected_allatom_effective_actionability_claim_requirement_mode}:{selected_allatom_effective_actionability_claim_requirement_status}"
        if selected_allatom_effective_actionability_claim_requirement_mode
        else "",
        f"blocking order {selected_allatom_effective_blocking_order}"
        if selected_allatom_effective_blocking_order
        else "",
        f"domain {selected_allatom_effective_primary_blocking_domain}"
        if selected_allatom_effective_primary_blocking_domain
        else "",
        f"recipe {selected_allatom_action_recipe_rollup_text}"
        if selected_allatom_action_recipe_rollup_text
        else "",
    )
    if selected_allatom_claim_actionability_split_summary:
        selected_allatom_human_signal = (
            f"{selected_allatom_human_signal} Split: {selected_allatom_claim_actionability_split_summary}"
        )
    selected_allatom_visual_summary = _text(
        selected_allatom_visual.get("human_summary"),
        selected_allatom_visual.get("availability_rollup"),
    )
    selected_allatom_visual_media_summary = _text(
        selected_allatom_visual.get("media_ready_rollup")
    )
    selected_allatom_next_required_step = _text(
        selected_allatom_next_required_step,
        str(bcris.get("selected_allatom_next_required_step", "")).strip(),
        str(bsrhs.get("selected_allatom_next_required_step", "")).strip(),
        selected_allatom_focus_summary.get("next_required_step", ""),
    )
    selected_allatom_next_required_step = selected_allatom_green_next_required_step(
        wetlab_gate_pass=selected_allatom_wetlab_gate_pass,
        final_gate_pass=selected_allatom_final_gate_pass,
        claim_ready_for_allatom=selected_allatom_claim_ready,
        translation_gate_focus_status=selected_allatom_translation_gate_status,
        recommended_next_expensive_lane=selected_allatom_recommended_next_expensive_lane,
        fallback_next_required_step=selected_allatom_next_required_step,
    )
    selected_allatom_next_required_step_sentence = selected_allatom_next_required_step.rstrip().rstrip(".")
    selected_allatom_row_summary = " ".join(
        part
        for part in [
            selected_allatom_human_signal,
            f"Visual: {selected_allatom_visual_summary}." if selected_allatom_visual_summary else "",
            f"Media: {selected_allatom_visual_media_summary}." if selected_allatom_visual_media_summary else "",
            f"Next: {selected_allatom_next_required_step_sentence}." if selected_allatom_next_required_step_sentence else "",
        ]
        if part
    ).strip()
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
        broad_screen_hard_target_rescue_lane,
        broad_screen_rescue_anchor_artifacts,
        broad_screen_rescue_three_bead_candidates,
    )
    exploratory_freeze = _exploratory_freeze_snapshot(bsserls, bssefls, bspws, bspwss)
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

    rows = [
        {
            "surface": "final_campaign_summary",
            "artifact": "runs/wetlab_final_campaign_summary_current.md",
            "status": str(fcs.get("status", "")).strip(),
            "key_signal": str(fcs.get("campaign_terminal_state", "")).strip(),
        },
        {
            "surface": "master_terminal_review",
            "artifact": "runs/wetlab_master_terminal_review_current.md",
            "status": str(mtrs.get("status", "")).strip(),
            "key_signal": str(mtrs.get("ready_to_send_tracks", "")).strip(),
        },
        {
            "surface": "outbound_execution_priority_board",
            "artifact": "runs/wetlab_outbound_execution_priority_board_current.md",
            "status": str(obs.get("status", "")).strip(),
            "key_signal": str(obs.get("top_priority_lead_targets", "")).strip(),
        },
        {
            "surface": "partner_send_round",
            "artifact": "runs/wetlab_partner_send_round_current.md",
            "status": str(srs.get("status", "")).strip(),
            "key_signal": str(srs.get("first_dispatch_track_id", "")).strip(),
        },
        {
            "surface": "partner_export_bundle",
            "artifact": "runs/wetlab_partner_first_contact_export_bundle_current.md",
            "status": str(ebs.get("status", "")).strip(),
            "key_signal": str(ebs.get("sender_name", "")).strip(),
        },
        {
            "surface": "broad_screen_queue",
            "artifact": "runs/wetlab_broad_screen_queue_current.md",
            "status": str(bsqs.get("status", "")).strip(),
            "key_signal": str(bsqs.get("total_queue_rows", "")).strip(),
        },
        {
            "surface": "broad_screen_compound_universe",
            "artifact": "runs/wetlab_broad_screen_compound_universe_current.md",
            "status": str(bscus.get("status", "")).strip(),
            "key_signal": str(bscus.get("deduped_compound_count", "")).strip(),
        },
        {
            "surface": "broad_screen_execution_queue",
            "artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
            "status": str(bseqs.get("status", "")).strip(),
            "key_signal": str(bseqs.get("first_actionable_target_id", "")).strip(),
        },
        {
            "surface": "broad_screen_repurposing_autofill",
            "artifact": "runs/wetlab_broad_screen_repurposing_autofill_current.md",
            "status": str(bsras.get("status", "")).strip(),
            "key_signal": str(bsras.get("override_target_count", "")).strip(),
        },
        {
            "surface": "broad_screen_stability_score",
            "artifact": "runs/wetlab_broad_screen_stability_score_current.md",
            "status": str(bssts.get("status", "")).strip(),
            "key_signal": str(
                int(bssts.get("stable_high_confidence_target_count", 0) or 0)
                + int(bssts.get("stable_provisional_target_count", 0) or 0)
            ),
        },
        {
            "surface": "broad_screen_antitarget_queue",
            "artifact": "runs/wetlab_broad_screen_antitarget_queue_current.md",
            "status": str(bsats.get("status", "")).strip(),
            "key_signal": str(bsats.get("ready_now_row_count", "")).strip(),
        },
        {
            "surface": "broad_screen_primary_watch_state",
            "artifact": "runs/wetlab_broad_screen_primary_watcher_current.md",
            "status": str(bspwss.get("status", "")).strip(),
            "key_signal": _primary_watch_decision(bspwss, bspws),
        },
        {
            "surface": "broad_screen_primary_watch",
            "artifact": "runs/wetlab_broad_screen_primary_watcher_current.md",
            "status": str(bspws.get("status", "")).strip(),
            "key_signal": _primary_watch_action(bspws, bspwss),
        },
        {
            "surface": "broad_screen_antitarget_watch_state",
            "artifact": "runs/wetlab_broad_screen_antitarget_watcher_state_current.md",
            "status": str(bsawss.get("status", "")).strip(),
            "key_signal": str(bsawss.get("watcher_decision", "")).strip(),
        },
        {
            "surface": "broad_screen_antitarget_watch",
            "artifact": "runs/wetlab_broad_screen_antitarget_watcher_current.md",
            "status": str(bsaws.get("status", "")).strip(),
            "key_signal": str(bsaws.get("last_action", "")).strip(),
        },
        {
            "surface": "broad_screen_actual_append",
            "artifact": "runs/wetlab_broad_screen_actual_append_current.md",
            "status": str(bsaas.get("status", "")).strip(),
            "key_signal": str(bsaas.get("incoming_row_count", "")).strip(),
        },
        {
            "surface": "broad_screen_throughput_bridge",
            "artifact": "runs/wetlab_broad_screen_throughput_bridge_current.md",
            "status": str(bstbs.get("status", "")).strip(),
            "key_signal": str(bstbs.get("target_id", "")).strip(),
        },
        {
            "surface": "broad_screen_primary_retry_preset",
            "artifact": "runs/wetlab_primary_retry_preset_surface_current.md",
            "status": str(bsrps.get("status", "")).strip(),
            "key_signal": str(bsrps.get("guard_blocked_target_count", "")).strip(),
        },
        {
            "surface": "broad_screen_primary_hold_guard",
            "artifact": "runs/wetlab_primary_hold_guard_surface_current.md",
            "status": str(bshgs.get("status", "")).strip(),
            "key_signal": str(bshgs.get("triggered_target_count", "")).strip(),
        },
        {
            "surface": "broad_screen_current_results_index",
            "artifact": "runs/wetlab_current_results_index_current.md",
            "status": str(bcris.get("status", "")).strip(),
            "key_signal": str(bcris.get("group_count", "")).strip(),
        },
        {
            "surface": "broad_screen_monitor_semantics",
            "artifact": "runs/wetlab_monitor_semantics_current.md",
            "status": str(bsmss.get("status", "")).strip(),
            "key_signal": str(bsmss.get("guard_blocked_target_id", "")).strip(),
        },
        {
            "surface": "broad_screen_retry_handoff_summary",
            "artifact": "runs/wetlab_retry_handoff_summary_current.md",
            "status": str(bsrhs.get("status", "")).strip(),
            "key_signal": str(bsrhs.get("manual_retry_focus_target_id", "")).strip(),
        },
        {
            "surface": "broad_screen_tcruzi_pde_promoted_top4_review_packet",
            "artifact": "runs/wetlab_tcruzi_pde_promoted_top4_review_packet_current.md",
            "status": str(bstprp.get("status", "")).strip(),
            "key_signal": _readiness_signal(
                target_id=str(bstprp.get("target_id", "")).strip(),
                shard_id=str(bstprp.get("shard_id", "")).strip(),
                surface_label=str(bstprp.get("packet_scope", "")).strip(),
                operator_review_reported=True,
                operator_review_ready=promoted_top4_operator_review_ready,
                wetlab_gate_reported=promoted_top4_wetlab_gate_reported,
                wetlab_gate_pass=promoted_top4_wetlab_gate_pass,
                final_gate_reported=promoted_top4_final_gate_reported,
                final_gate_pass=promoted_top4_final_gate_pass,
                claim_gate_reported=promoted_top4_claim_gate_reported,
                claim_gate_available=promoted_top4_claim_gate_available,
                claim_ready_reported=promoted_top4_claim_ready_reported,
                claim_ready_for_allatom=promoted_top4_claim_ready,
            ),
        },
        {
            "surface": "broad_screen_tcruzi_pde_rescue_only_branch_summary",
            "artifact": "runs/wetlab_tcruzi_pde_rescue_only_branch_summary_current.md",
            "status": str(bstrob.get("status", "")).strip(),
            "key_signal": _readiness_signal(
                target_id=str(bstrob.get("target_id", "")).strip(),
                shard_id=str(bstrob.get("shard_id", "")).strip(),
                surface_label=str(bstrob.get("branch_label", "")).strip(),
                operator_review_reported=True,
                operator_review_ready=rescue_branch_operator_review_ready,
                wetlab_gate_reported=rescue_branch_wetlab_gate_reported,
                wetlab_gate_pass=rescue_branch_wetlab_gate_pass,
                final_gate_reported=rescue_branch_final_gate_reported,
                final_gate_pass=rescue_branch_final_gate_pass,
                claim_gate_reported=rescue_branch_claim_gate_reported,
                claim_gate_available=rescue_branch_claim_gate_available,
                claim_ready_reported=rescue_branch_claim_ready_reported,
                claim_ready_for_allatom=rescue_branch_claim_ready,
            ),
        },
        {
            "surface": "broad_screen_selected_allatom_focus",
            "artifact": selected_allatom_focus_artifact,
            "status": selected_allatom_focus_status,
            "key_signal": selected_allatom_human_signal,
            "one_line_summary": _text(
                selected_allatom_row_summary,
                str(fcs.get("selected_allatom_human_summary", "")).strip(),
                selected_allatom_next_required_step,
            ),
        },
        {
            "surface": "broad_screen_selected_allatom_actionability",
            "artifact": selected_allatom_focus_artifact,
            "status": selected_allatom_actionability_status or "not_reported",
            "key_signal": selected_allatom_actionability_display or selected_allatom_actionability_status or "not_reported",
            "one_line_summary": _joined(
                selected_allatom_actionability_human_summary,
                f"block {selected_allatom_actionability_block_reason}" if selected_allatom_actionability_block_reason else "",
                f"required {selected_allatom_actionability_required_calculations_text}" if selected_allatom_actionability_required_calculations_text else "",
                f"lane {selected_allatom_actionability_next_expensive_lane}" if selected_allatom_actionability_next_expensive_lane else "",
                f"raw claim {selected_allatom_raw_claim_requirement_mode}" if selected_allatom_raw_claim_requirement_mode else "",
                f"claim {selected_allatom_actionability_claim_requirement_mode}:{selected_allatom_actionability_claim_requirement_status}" if selected_allatom_actionability_claim_requirement_mode else "",
                f"blocking order {selected_allatom_effective_blocking_order}" if selected_allatom_effective_blocking_order else "",
                f"domain {selected_allatom_effective_primary_blocking_domain}" if selected_allatom_effective_primary_blocking_domain else "",
                f"actions {selected_allatom_actionability_action_list_text}" if selected_allatom_actionability_action_list_text else "",
                f"recipe {selected_allatom_action_recipe_rollup_text}" if selected_allatom_action_recipe_rollup_text else "",
            ),
        },
        {
            "surface": "broad_screen_stk17b_exploratory_followup_lane",
            "artifact": "runs/wetlab_stk17b_exploratory_followup_lane_current.md",
            "status": str(bssefls.get("status", "")).strip(),
            "key_signal": " | ".join(
                part
                for part in [
                    str(bssefls.get("target_id", "")).strip(),
                    str(bssefls.get("shard_id", "")).strip(),
                    str(bssefls.get("selected_command_kind", "")).strip(),
                ]
                if part
            ),
        },
        {
            "surface": "broad_screen_stk17b_exploratory_retry_lane",
            "artifact": "runs/wetlab_stk17b_exploratory_retry_lane_current.md",
            "status": str(bsserls.get("status", "")).strip(),
            "key_signal": " | ".join(
                part
                for part in [
                    str(bsserls.get("target_id", "")).strip(),
                    str(bsserls.get("shard_id", "")).strip(),
                    str(bsserls.get("selected_command_kind", "")).strip(),
                ]
                if part
            ),
        },
        {
            "surface": "broad_screen_plpro_manual_retry_lane",
            "artifact": "runs/wetlab_plpro_manual_retry_lane_current.md",
            "status": str(bspmls.get("status", "")).strip(),
            "key_signal": " | ".join(
                part for part in [
                    str(bspmls.get("target_id", "")).strip(),
                    str(bspmls.get("shard_id", "")).strip(),
                    str(bspmls.get("selected_command_kind", "")).strip(),
                ] if part
            ),
        },
        {
            "surface": "broad_screen_mapping_fix_retry_support",
            "artifact": "runs/wetlab_mapping_fix_retry_support_current.md",
            "status": str(bsmfrs.get("status", "")).strip(),
            "key_signal": str(bsmfrs.get("ready_targets", "")).strip(),
        },
        {
            "surface": "broad_screen_stage1_mapping_fix_lanes",
            "artifact": "runs/wetlab_stage1_mapping_fix_lanes_current.md",
            "status": str(bssmfl.get("status", "")).strip(),
            "key_signal": str(bssmfl.get("ready_targets", "")).strip(),
        },
        {
            "surface": "broad_screen_mapping_fix_retry_policy_templates",
            "artifact": "runs/wetlab_mapping_fix_retry_policy_templates_current.md",
            "status": str(bsmfrpts.get("status", "")).strip(),
            "key_signal": " | ".join(
                part
                for part in [
                    str(bsmfrpts.get("focus_target_id", "")).strip(),
                    str(bsmfrpts.get("focus_template_label", "")).strip(),
                    str(bsmfrpts.get("focus_selected_command_kind", "")).strip(),
                ]
                if part
            ),
        },
        {
            "surface": "broad_screen_kinase_retry_policy_templates",
            "artifact": "runs/wetlab_kinase_retry_policy_templates_current.md",
            "status": str(bskrts.get("status", "")).strip(),
            "key_signal": " | ".join(
                part
                for part in [
                    str(bskrts.get("focus_target_id", "")).strip(),
                    str(bskrts.get("focus_template_label", "")).strip(),
                    str(bskrts.get("focus_selected_command_kind", "")).strip(),
                ]
                if part
            ),
        },
        {
            "surface": "broad_screen_target_retry_policy_templates",
            "artifact": "runs/wetlab_target_retry_policy_templates_current.md",
            "status": str(bstrpts.get("status", "")).strip(),
            "key_signal": " | ".join(
                part
                for part in [
                    str(bstrpts.get("focus_target_id", "")).strip(),
                    str(bstrpts.get("focus_template_label", "")).strip(),
                    str(bstrpts.get("focus_selected_command_kind", "")).strip(),
                ]
                if part
            ),
        },
        {
            "surface": "broad_screen_bridge",
            "artifact": "runs/wetlab_broad_screen_bridge_current.md",
            "status": str(bsbs.get("status", "")).strip(),
            "key_signal": str(bsbs.get("final_packet_shape", "")).strip(),
        },
    ]

    selected_allatom_effective_actionability = dict(
        selected_allatom_canonical.get("effective_actionability", {}) or {}
    )
    selected_allatom_actionability_block_reason_codes = _coerce_text_list(
        selected_allatom_effective_actionability.get("block_reason_codes")
        or selected_allatom_focus_summary.get("selected_allatom_actionability_block_reason_codes", [])
    )
    selected_allatom_actionability_soft_guidance_reasons = _coerce_text_list(
        selected_allatom_effective_actionability.get("soft_guidance_reasons")
        or selected_allatom_focus_summary.get("selected_allatom_actionability_soft_guidance_reasons", [])
    )
    selected_allatom_actionability_action_list = list(
        selected_allatom_effective_actionability.get("action_list")
        or selected_allatom_focus_summary.get("selected_allatom_actionability_action_list", [])
        or []
    )
    selected_allatom_actionability_translation_gate_v2_failed_metrics = _coerce_text_list(
        selected_allatom_effective_actionability.get("translation_gate_v2_failed_metrics")
        or selected_allatom_focus_summary.get("selected_allatom_actionability_translation_gate_v2_failed_metrics", [])
    )
    selected_allatom_actionability_translation_gate_v2_missing_metrics = _coerce_text_list(
        selected_allatom_effective_actionability.get("translation_gate_v2_missing_metrics")
        or selected_allatom_focus_summary.get("selected_allatom_actionability_translation_gate_v2_missing_metrics", [])
    )
    selected_allatom_actionability_translation_gate_v2_thresholds = dict(
        selected_allatom_effective_actionability.get("translation_gate_v2_thresholds")
        or selected_allatom_focus_summary.get("selected_allatom_actionability_translation_gate_v2_thresholds", {})
        or {}
    )
    selected_allatom_commercial_hard_gate_failed_metrics_v2 = _coerce_text_list(
        selected_allatom_focus_summary.get("selected_allatom_commercial_hard_gate_failed_metrics_v2")
        or selected_allatom_focus_summary.get("commercial_hard_gate_failed_metrics_v2")
        or selected_allatom_actionability_translation_gate_v2_failed_metrics
    )
    selected_allatom_commercial_hard_gate_missing_metrics_v2 = _coerce_text_list(
        selected_allatom_focus_summary.get("selected_allatom_commercial_hard_gate_missing_metrics_v2")
        or selected_allatom_focus_summary.get("commercial_hard_gate_missing_metrics_v2")
        or selected_allatom_actionability_translation_gate_v2_missing_metrics
    )
    selected_allatom_commercial_score_thresholds_v2 = dict(
        selected_allatom_focus_summary.get("selected_allatom_commercial_score_thresholds_v2")
        or selected_allatom_focus_summary.get("commercial_score_thresholds_v2")
        or selected_allatom_actionability_translation_gate_v2_thresholds
        or {}
    )

    return {
        "summary": {
            "status": "wetlab_master_handoff_dashboard_ready",
            "primary_surface_artifact": "runs/wetlab_final_campaign_summary_current.md",
            "campaign_terminal_state": str(fcs.get("campaign_terminal_state", "")).strip(),
            "ready_to_send_track_count": int(fcs.get("ready_to_send_track_count", 0) or 0),
            "broad_screen_total_queue_rows": int(bsqs.get("total_queue_rows", 0) or 0),
            "broad_screen_library_size": int(bsqs.get("library_size", bsbs.get("library_size", 0)) or 0),
            "broad_screen_ingested_compound_count": int(
                bscus.get("deduped_compound_count", 0)
                or bseqs.get("ingested_compound_count", 0)
                or 0
            ),
            "broad_screen_execution_ready_now_row_count": int(bseqs.get("ready_now_row_count", 0) or 0),
            "broad_screen_first_actionable_target_id": str(bseqs.get("first_actionable_target_id", "")).strip(),
            "broad_screen_first_actionable_shard_id": str(bseqs.get("first_actionable_shard_id", "")).strip(),
            "broad_screen_override_target_count": int(bsras.get("override_target_count", 0) or 0),
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
            "broad_screen_primary_watch_state_ready": bool(
                _primary_watch_ready(bspwss) or _primary_watch_ready(bspws)
            ),
            "broad_screen_primary_watch_ready": bool(
                _primary_watch_ready(bspws) or _primary_watch_ready(bspwss)
            ),
            "broad_screen_primary_watch_decision": _primary_watch_decision(bspwss, bspws),
            "broad_screen_primary_watch_last_action": _primary_watch_action(bspws, bspwss),
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
            "broad_screen_antitarget_watch_decision": str(bsawss.get("watcher_decision", "")).strip(),
            "broad_screen_antitarget_watch_last_action": str(bsaws.get("last_action", "")).strip(),
            "broad_screen_antitarget_watch_loop_pid": int(bsawlp.get("pid", 0) or 0),
            "broad_screen_antitarget_watch_loop_attached": antitarget_watch_loop_attached,
            "broad_screen_antitarget_watch_liveness": antitarget_watch_loop_liveness,
            "broad_screen_antitarget_watch_fallback_mode": antitarget_watch_loop_fallback_mode,
            "broad_screen_actual_append_ready": bool(
                str(bsaas.get("status", "")).strip().startswith("wetlab_broad_screen_actual_append_")
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
                bssefls.get("followup_lane_label", "") or bssefls.get("lane_label", "")
            ).strip(),
            "broad_screen_stk17b_exploratory_followup_followup_shard_ids": str(
                bssefls.get("followup_shard_ids", "")
            ).strip(),
            "broad_screen_stk17b_exploratory_followup_freeze_state": str(
                bssefls.get("hard_freeze_state", bssefls.get("freeze_state", ""))
            ).strip(),
            "broad_screen_stk17b_exploratory_followup_hard_freeze_state": str(
                bssefls.get("hard_freeze_state", "")
            ).strip(),
            "broad_screen_stk17b_exploratory_followup_freeze_note": str(
                bssefls.get("freeze_note", "")
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
                str(bstprp.get("status", "")).strip() == "wetlab_tcruzi_pde_promoted_top4_review_packet_ready"
            ),
            "broad_screen_tcruzi_pde_promoted_top4_target_id": str(bstprp.get("target_id", "")).strip(),
            "broad_screen_tcruzi_pde_promoted_top4_shard_id": str(bstprp.get("shard_id", "")).strip(),
            "broad_screen_tcruzi_pde_promoted_top4_packet_scope": str(bstprp.get("packet_scope", "")).strip(),
            "broad_screen_tcruzi_pde_promoted_top4_packet_ready": bool(bstprp.get("packet_ready", False)),
            "broad_screen_tcruzi_pde_promoted_top4_operator_review_ready": promoted_top4_operator_review_ready,
            "broad_screen_tcruzi_pde_promoted_top4_wetlab_gate_reported": promoted_top4_wetlab_gate_reported,
            "broad_screen_tcruzi_pde_promoted_top4_wetlab_gate_pass": promoted_top4_wetlab_gate_pass,
            "broad_screen_tcruzi_pde_promoted_top4_final_gate_reported": promoted_top4_final_gate_reported,
            "broad_screen_tcruzi_pde_promoted_top4_final_gate_pass": promoted_top4_final_gate_pass,
            "broad_screen_tcruzi_pde_promoted_top4_final_wetlab_ready": promoted_top4_final_gate_pass,
            "broad_screen_tcruzi_pde_promoted_top4_claim_gate_available_reported": promoted_top4_claim_gate_reported,
            "broad_screen_tcruzi_pde_promoted_top4_claim_gate_available": promoted_top4_claim_gate_available,
            "broad_screen_tcruzi_pde_promoted_top4_claim_ready_for_allatom_reported": promoted_top4_claim_ready_reported,
            "broad_screen_tcruzi_pde_promoted_top4_claim_ready_for_allatom": promoted_top4_claim_ready,
            "broad_screen_tcruzi_pde_promoted_top4_readiness_semantics": promoted_top4_readiness_semantics,
            "broad_screen_tcruzi_pde_promoted_top4_default_lane_reopen_allowed": bool(
                bstprp.get("default_lane_reopen_allowed", False)
            ),
            "broad_screen_tcruzi_pde_promoted_top4_branch_to_rescue_only": bool(
                bstprp.get("branch_to_rescue_only", False)
            ),
            "broad_screen_tcruzi_pde_promoted_top4_selected_command_kind": str(
                bstprp.get("selected_command_kind", "")
            ).strip(),
            "broad_screen_tcruzi_pde_promoted_top4_strict_threshold_A": float(
                bstprp.get("strict_threshold_A", 0.0) or 0.0
            ),
            "broad_screen_tcruzi_pde_promoted_top4_near_threshold_A": float(
                bstprp.get("near_threshold_A", 0.0) or 0.0
            ),
            "broad_screen_tcruzi_pde_promoted_top4_promoted_candidate_count": int(
                bstprp.get("promoted_candidate_count", 0) or 0
            ),
            "broad_screen_tcruzi_pde_promoted_top4_under_2p5_candidate_count": int(
                bstprp.get("under_2p5_candidate_count", 0) or 0
            ),
            "broad_screen_tcruzi_pde_promoted_top4_near_candidate_count": int(
                bstprp.get("near_candidate_count", 0) or 0
            ),
            "broad_screen_tcruzi_pde_promoted_top4_best_ligand_id": str(
                bstprp.get("best_ligand_id", "")
            ).strip(),
            "broad_screen_tcruzi_pde_promoted_top4_best_compound_name": str(
                bstprp.get("best_compound_name", bstprp.get("best_ligand_id", ""))
            ).strip(),
            "broad_screen_tcruzi_pde_promoted_top4_best_compound_name_human_readable": str(
                bstprp.get("best_compound_name_human_readable", "")
            ).strip(),
            "broad_screen_tcruzi_pde_promoted_top4_best_compound_name_resolution": str(
                bstprp.get("best_compound_name_resolution", "unresolved")
            ).strip(),
            "broad_screen_tcruzi_pde_promoted_top4_best_mean_min_distance_A": float(
                bstprp.get("best_mean_min_distance_A", 0.0) or 0.0
            ),
            "broad_screen_tcruzi_pde_promoted_top4_next_required_step": str(
                bstprp.get("next_required_step", "")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_only_branch_summary_ready": bool(
                str(bstrob.get("status", "")).strip() == "wetlab_tcruzi_pde_rescue_only_branch_summary_ready"
            ),
            "broad_screen_tcruzi_pde_rescue_only_branch_target_id": str(
                bstrob.get("target_id", "")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_only_branch_shard_id": str(
                bstrob.get("shard_id", "")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_only_branch_label": str(
                bstrob.get("branch_label", "")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_only_branch_state": str(
                bstrob.get("branch_state", "")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_only_branch_default_lane_reopen_allowed": bool(
                bstrob.get("default_lane_reopen_allowed", False)
            ),
            "broad_screen_tcruzi_pde_rescue_only_branch_branch_to_rescue_only": bool(
                bstrob.get("branch_to_rescue_only", False)
            ),
            "broad_screen_tcruzi_pde_rescue_only_branch_selected_command_kind": str(
                bstrob.get("selected_command_kind", "")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_only_branch_selected_threshold_A": float(
                bstrob.get("selected_threshold_A", 0.0) or 0.0
            ),
            "broad_screen_tcruzi_pde_rescue_only_branch_promoted_top4_packet_ready": bool(
                bstrob.get("promoted_top4_packet_ready", False)
            ),
            "broad_screen_tcruzi_pde_rescue_only_branch_operator_review_ready": rescue_branch_operator_review_ready,
            "broad_screen_tcruzi_pde_rescue_only_branch_wetlab_gate_reported": rescue_branch_wetlab_gate_reported,
            "broad_screen_tcruzi_pde_rescue_only_branch_wetlab_gate_pass": rescue_branch_wetlab_gate_pass,
            "broad_screen_tcruzi_pde_rescue_only_branch_final_gate_reported": rescue_branch_final_gate_reported,
            "broad_screen_tcruzi_pde_rescue_only_branch_final_gate_pass": rescue_branch_final_gate_pass,
            "broad_screen_tcruzi_pde_rescue_only_branch_final_wetlab_ready": rescue_branch_final_gate_pass,
            "broad_screen_tcruzi_pde_rescue_only_branch_claim_gate_available_reported": rescue_branch_claim_gate_reported,
            "broad_screen_tcruzi_pde_rescue_only_branch_claim_gate_available": rescue_branch_claim_gate_available,
            "broad_screen_tcruzi_pde_rescue_only_branch_claim_ready_for_allatom_reported": rescue_branch_claim_ready_reported,
            "broad_screen_tcruzi_pde_rescue_only_branch_claim_ready_for_allatom": rescue_branch_claim_ready,
            "broad_screen_tcruzi_pde_rescue_only_branch_review_packet_operator_review_ready": rescue_branch_review_operator_ready,
            "broad_screen_tcruzi_pde_rescue_only_branch_review_packet_wetlab_gate_reported": rescue_branch_review_wetlab_gate_reported,
            "broad_screen_tcruzi_pde_rescue_only_branch_review_packet_wetlab_gate_pass": rescue_branch_review_wetlab_gate_pass,
            "broad_screen_tcruzi_pde_rescue_only_branch_review_packet_final_gate_reported": rescue_branch_review_final_gate_reported,
            "broad_screen_tcruzi_pde_rescue_only_branch_review_packet_final_gate_pass": rescue_branch_review_final_gate_pass,
            "broad_screen_tcruzi_pde_rescue_only_branch_operator_packet_ready": rescue_branch_operator_packet_ready,
            "broad_screen_tcruzi_pde_rescue_only_branch_operator_packet_wetlab_gate_reported": rescue_branch_operator_wetlab_gate_reported,
            "broad_screen_tcruzi_pde_rescue_only_branch_operator_packet_wetlab_gate_pass": rescue_branch_operator_wetlab_gate_pass,
            "broad_screen_tcruzi_pde_rescue_only_branch_operator_packet_final_gate_reported": rescue_branch_operator_final_gate_reported,
            "broad_screen_tcruzi_pde_rescue_only_branch_operator_packet_final_gate_pass": rescue_branch_operator_final_gate_pass,
            "broad_screen_tcruzi_pde_rescue_only_branch_readiness_semantics": rescue_branch_readiness_semantics,
            "broad_screen_tcruzi_pde_rescue_only_branch_promoted_candidate_count": int(
                bstrob.get("promoted_candidate_count", 0) or 0
            ),
            "broad_screen_tcruzi_pde_rescue_only_branch_under_2p5_candidate_count": int(
                bstrob.get("under_2p5_candidate_count", 0) or 0
            ),
            "broad_screen_tcruzi_pde_rescue_only_branch_near_candidate_count": int(
                bstrob.get("near_candidate_count", 0) or 0
            ),
            "broad_screen_tcruzi_pde_rescue_only_branch_best_ligand_id": str(
                bstrob.get("best_ligand_id", "")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_only_branch_best_compound_name": str(
                bstrob.get("best_compound_name", bstrob.get("best_ligand_id", ""))
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_only_branch_best_compound_name_human_readable": str(
                bstrob.get("best_compound_name_human_readable", "")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_only_branch_best_compound_name_resolution": str(
                bstrob.get("best_compound_name_resolution", "unresolved")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_only_branch_best_mean_min_distance_A": float(
                bstrob.get("best_mean_min_distance_A", 0.0) or 0.0
            ),
            "broad_screen_tcruzi_pde_rescue_only_branch_runner_status": str(
                bstrob.get("runner_status", "")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_only_branch_three_bead_scoring_status": str(
                bstrob.get("three_bead_scoring_status", "")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_only_branch_execution_mode": str(
                bstrob.get("execution_mode", "")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_only_branch_next_required_step": str(
                bstrob.get("next_required_step", "")
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
                bcris.get("selected_rescue_branch_target_id", bsrhs.get("selected_rescue_branch_target_id", bstrob.get("target_id", bstprp.get("target_id", ""))))
            ).strip(),
            "selected_rescue_branch_surface_label": _text(
                bcris.get("selected_rescue_branch_surface_label"),
                bsrhs.get("selected_rescue_branch_surface_label"),
                "pde_rescue_only_branch"
                if str(bstrob.get("status", "")).strip() == "wetlab_tcruzi_pde_rescue_only_branch_summary_ready"
                else "",
            ),
            "selected_rescue_branch_selected_command_kind": str(
                bcris.get("selected_rescue_branch_selected_command_kind", bsrhs.get("selected_rescue_branch_selected_command_kind", bstrob.get("selected_command_kind", bstprp.get("selected_command_kind", ""))))
            ).strip(),
            "selected_rescue_branch_best_compound_name": str(
                bcris.get("selected_rescue_branch_best_compound_name", bsrhs.get("selected_rescue_branch_best_compound_name", bstrob.get("best_compound_name", bstprp.get("best_compound_name", bstprp.get("best_ligand_id", "")))))
            ).strip(),
            "selected_rescue_branch_best_compound_name_human_readable": str(
                bcris.get("selected_rescue_branch_best_compound_name_human_readable", bsrhs.get("selected_rescue_branch_best_compound_name_human_readable", bstrob.get("best_compound_name_human_readable", bstprp.get("best_compound_name_human_readable", ""))))
            ).strip(),
            "selected_rescue_branch_best_compound_name_resolution": str(
                bcris.get("selected_rescue_branch_best_compound_name_resolution", bsrhs.get("selected_rescue_branch_best_compound_name_resolution", bstrob.get("best_compound_name_resolution", bstprp.get("best_compound_name_resolution", "unresolved"))))
            ).strip(),
            "selected_rescue_branch_threshold_A": float(
                bcris.get("selected_rescue_branch_selected_threshold_A", bsrhs.get("selected_rescue_branch_selected_threshold_A", bstrob.get("selected_threshold_A", bstprp.get("strict_threshold_A", 0.0)))) or 0.0
            ),
            "selected_rescue_branch_operator_packet_ready": bool(
                bcris.get("selected_rescue_branch_operator_packet_ready", bsrhs.get("selected_rescue_branch_operator_packet_ready", False))
            ),
            "selected_rescue_branch_operator_packet_scope": str(
                bcris.get("selected_rescue_branch_operator_packet_scope", bsrhs.get("selected_rescue_branch_operator_packet_scope", ""))
            ).strip(),
            "broad_screen_rescue_only_branch_templates_ready": bool(
                bcris.get("rescue_only_branch_templates_ready", bsrhs.get("rescue_only_branch_templates_ready", False))
            ),
            "broad_screen_rescue_only_branch_template_target_count": int(
                bcris.get("rescue_only_branch_template_target_count", bsrhs.get("rescue_only_branch_template_target_count", 0)) or 0
            ),
            "broad_screen_rescue_only_branch_focus_target_id": str(
                bcris.get("rescue_only_branch_focus_target_id", bsrhs.get("rescue_only_branch_focus_target_id", ""))
            ).strip(),
            "broad_screen_rescue_only_branch_focus_template_label": str(
                bcris.get("rescue_only_branch_focus_template_label", bsrhs.get("rescue_only_branch_focus_template_label", ""))
            ).strip(),
            "broad_screen_rescue_only_branch_focus_surface_label": str(
                bcris.get("rescue_only_branch_focus_surface_label", bsrhs.get("rescue_only_branch_focus_surface_label", ""))
            ).strip(),
            "broad_screen_rescue_only_branch_focus_selected_command_kind": str(
                bcris.get("rescue_only_branch_focus_selected_command_kind", bsrhs.get("rescue_only_branch_focus_selected_command_kind", ""))
            ).strip(),
            "broad_screen_rescue_only_branch_focus_selected_threshold_A": float(
                bcris.get("rescue_only_branch_focus_selected_threshold_A", bsrhs.get("rescue_only_branch_focus_selected_threshold_A", 0.0)) or 0.0
            ),
            "selected_rescue_branch_next_required_step": _text(
                bcris.get("selected_rescue_branch_next_required_step"),
                bsrhs.get("selected_rescue_branch_next_required_step"),
                bstrob.get("next_required_step", bstprp.get("next_required_step", "")),
            ),
            "broad_screen_allatom_family_ready": bool(
                bsrhs.get("allatom_family_ready", bcris.get("allatom_family_ready", False))
            ),
            "broad_screen_allatom_family_target_count": int(
                bsrhs.get("allatom_family_target_count", bcris.get("allatom_family_target_count", 0)) or 0
            ),
            "broad_screen_allatom_family_surface_count": int(
                bsrhs.get("allatom_family_surface_count", bcris.get("allatom_family_surface_count", 0)) or 0
            ),
            "broad_screen_allatom_family_focus_target_id": str(
                bsrhs.get("allatom_family_focus_target_id", bcris.get("allatom_family_focus_target_id", ""))
            ).strip(),
            "broad_screen_allatom_family_focus_surface_label": str(
                bsrhs.get("allatom_family_focus_surface_label", bcris.get("allatom_family_focus_surface_label", ""))
            ).strip(),
            "selected_allatom_target_id": selected_allatom_target_id,
            "selected_allatom_surface_label": selected_allatom_surface_label,
            "selected_allatom_focus_artifact": selected_allatom_focus_artifact,
            "selected_allatom_focus_status": selected_allatom_focus_status,
            "selected_allatom_selected_command_kind": str(
                bsrhs.get("selected_allatom_selected_command_kind", bcris.get("selected_allatom_selected_command_kind", ""))
            ).strip(),
            "selected_allatom_selected_threshold_A": float(
                bsrhs.get("selected_allatom_selected_threshold_A", bcris.get("selected_allatom_selected_threshold_A", 0.0)) or 0.0
            ),
            "selected_allatom_packet_scope": str(
                bsrhs.get("selected_allatom_packet_scope", bcris.get("selected_allatom_packet_scope", ""))
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
            "selected_allatom_claim_ready_for_allatom": selected_allatom_claim_ready,
            "selected_allatom_readiness_semantics": selected_allatom_readiness_semantics,
            "selected_allatom_human_summary": selected_allatom_human_signal,
            "selected_allatom_actionability_status": selected_allatom_actionability_status,
            "selected_allatom_actionability_brief_summary": selected_allatom_actionability_brief_summary,
            "selected_allatom_actionability_human_summary": selected_allatom_actionability_human_summary,
            "selected_allatom_actionability_block_reason": selected_allatom_actionability_block_reason,
            "selected_allatom_actionability_required_calculations_text": selected_allatom_actionability_required_calculations_text,
            "selected_allatom_actionability_action_list_text": selected_allatom_actionability_action_list_text,
            "selected_allatom_actionability_claim_requirement_mode": selected_allatom_actionability_claim_requirement_mode,
            "selected_allatom_actionability_claim_requirement_status": selected_allatom_actionability_claim_requirement_status,
            "selected_allatom_actionability_next_expensive_lane": selected_allatom_actionability_next_expensive_lane,
            "selected_allatom_actionability_next_expensive_lane_reason": selected_allatom_actionability_next_expensive_lane_reason,
            "selected_allatom_commercial_grade_reported_v1": selected_allatom_commercial_reported,
            "selected_allatom_commercial_schema_version": selected_allatom_commercial_schema_version,
            "selected_allatom_commercial_hard_gate_pass_v1": selected_allatom_commercial_hard_gate_pass,
            "selected_allatom_commercial_hard_gate_reported_v1": selected_allatom_commercial_hard_gate_reported,
            "selected_allatom_commercial_soft_score_v1": selected_allatom_commercial_soft_score_v1,
            "selected_allatom_commercial_confidence_score_v1": selected_allatom_commercial_confidence_score_v1,
            "selected_allatom_commercial_overall_score_v1": selected_allatom_commercial_overall_score_v1,
            "selected_allatom_commercial_risk_bucket_v1": selected_allatom_commercial_risk_bucket_v1,
            "selected_allatom_commercial_decision_class_v1": selected_allatom_commercial_decision_class_v1,
            "selected_allatom_commercial_primary_upgrade_actions_v1": selected_allatom_commercial_primary_upgrade_actions_v1,
            "selected_allatom_commercial_human_summary_v1": selected_allatom_commercial_human_signal,
            "selected_allatom_commercial_grade_reported_v2": selected_allatom_commercial_reported_v2,
            "selected_allatom_commercial_schema_version_v2": selected_allatom_commercial_schema_version_v2,
            "selected_allatom_commercial_hard_gate_pass_v2": selected_allatom_commercial_hard_gate_pass_v2,
            "selected_allatom_commercial_hard_gate_reported_v2": selected_allatom_commercial_hard_gate_reported_v2,
            "selected_allatom_commercial_soft_score_v2": selected_allatom_commercial_soft_score_v2,
            "selected_allatom_commercial_confidence_score_v2": selected_allatom_commercial_confidence_score_v2,
            "selected_allatom_commercial_overall_score_v2": selected_allatom_commercial_overall_score_v2,
            "selected_allatom_commercial_risk_bucket_v2": selected_allatom_commercial_risk_bucket_v2,
            "selected_allatom_commercial_decision_class_v2": selected_allatom_commercial_decision_class_v2,
            "selected_allatom_commercial_primary_upgrade_actions_v2": selected_allatom_commercial_primary_upgrade_actions_v2,
            "selected_allatom_commercial_human_summary_v2": selected_allatom_commercial_human_signal_v2,
            "selected_allatom_translation_gate_status": selected_allatom_translation_gate_status,
            "selected_allatom_translation_gate_score": selected_allatom_translation_gate_score,
            "selected_allatom_translation_gate_reason": selected_allatom_translation_gate_reason,
            "selected_allatom_focus_shortlist_tier": selected_allatom_focus_shortlist_tier,
            "selected_allatom_recommended_next_expensive_lane": selected_allatom_recommended_next_expensive_lane,
            "selected_allatom_recommended_next_expensive_lane_reason": selected_allatom_recommended_next_expensive_lane_reason,
            "selected_allatom_translation_human_summary": selected_allatom_translation_human_signal,
            "selected_allatom_claim_gate_source": selected_allatom_claim_gate_source,
            "selected_allatom_claim_ready_source": selected_allatom_claim_ready_source,
            "selected_allatom_claim_gate_policy_version": _text(
                bcris.get("selected_allatom_claim_gate_policy_version", ""),
                fcs.get("selected_allatom_claim_gate_policy_version", ""),
                bsrhs.get("selected_allatom_claim_gate_policy_version", ""),
                selected_allatom_focus_summary.get("selected_allatom_claim_gate_policy_version", ""),
            ),
            "selected_allatom_claim_pass_core_gate": selected_allatom_focus_summary.get(
                "selected_allatom_claim_pass_core_gate",
                selected_allatom_focus_summary.get("pass_core_gate"),
            ),
            "selected_allatom_claim_core_failed_metrics": _coerce_text_list(
                selected_allatom_focus_summary.get(
                    "selected_allatom_claim_core_failed_metrics",
                    selected_allatom_focus_summary.get("core_failed_metrics", []),
                )
            ),
            "selected_allatom_claim_core_missing_metrics": _coerce_text_list(
                selected_allatom_focus_summary.get(
                    "selected_allatom_claim_core_missing_metrics",
                    selected_allatom_focus_summary.get("core_missing_metrics", []),
                )
            ),
            "selected_allatom_claim_failed_metrics": _coerce_text_list(
                selected_allatom_focus_summary.get(
                    "selected_allatom_claim_failed_metrics",
                    selected_allatom_focus_summary.get("claim_failed_metrics", []),
                )
            ),
            "selected_allatom_claim_missing_metrics": _coerce_text_list(
                selected_allatom_focus_summary.get(
                    "selected_allatom_claim_missing_metrics",
                    selected_allatom_focus_summary.get("claim_missing_metrics", []),
                )
            ),
            "selected_allatom_claim_requirement_mode": _text(
                selected_allatom_focus_summary.get("claim_gate_requirement_mode", ""),
                selected_allatom_focus_summary.get("selected_allatom_claim_requirement_mode", ""),
                bcris.get("selected_allatom_claim_requirement_mode", ""),
                fcs.get("selected_allatom_claim_requirement_mode", ""),
                bsrhs.get("selected_allatom_claim_requirement_mode", ""),
            ),
            "selected_allatom_claim_requirement_provenance": _text(
                selected_allatom_focus_summary.get("claim_gate_requirement_provenance", ""),
                selected_allatom_focus_summary.get("selected_allatom_claim_requirement_provenance", ""),
                bcris.get("selected_allatom_claim_requirement_provenance", ""),
                fcs.get("selected_allatom_claim_requirement_provenance", ""),
                bsrhs.get("selected_allatom_claim_requirement_provenance", ""),
                "inferred_from_claim_gate_availability",
            ),
            "selected_allatom_claim_required_for_final_wetlab": bool(
                selected_allatom_focus_summary.get(
                    "selected_allatom_claim_required_for_final_wetlab",
                    selected_allatom_focus_summary.get("claim_gate_required_for_final_wetlab", False),
                )
            ),
            "selected_allatom_claim_required_for_commercial_readiness": bool(
                selected_allatom_focus_summary.get(
                    "selected_allatom_claim_required_for_commercial_readiness",
                    selected_allatom_focus_summary.get("claim_gate_required_for_commercial_readiness", False),
                )
            ),
            "selected_allatom_claim_requirement_reason": _text(
                bcris.get("selected_allatom_claim_requirement_reason", ""),
                fcs.get("selected_allatom_claim_requirement_reason", ""),
                bsrhs.get("selected_allatom_claim_requirement_reason", ""),
                selected_allatom_focus_summary.get("selected_allatom_claim_requirement_reason", ""),
                selected_allatom_focus_summary.get("claim_gate_requirement_reason", ""),
            ),
            "selected_allatom_claim_requirement_actions": _coerce_text_list(
                selected_allatom_focus_summary.get(
                    "selected_allatom_claim_requirement_actions",
                    selected_allatom_focus_summary.get("claim_gate_requirement_actions", []),
                )
            ),
            "selected_allatom_raw_claim_requirement_mode": selected_allatom_raw_claim_requirement_mode,
            "selected_allatom_raw_claim_requirement_provenance": selected_allatom_raw_claim_requirement_provenance,
            "selected_allatom_raw_claim_required_for_final_wetlab": selected_allatom_raw_claim_required_for_final_wetlab,
            "selected_allatom_raw_claim_required_for_commercial_readiness": selected_allatom_raw_claim_required_for_commercial_readiness,
            "selected_allatom_raw_claim_requirement_reason": selected_allatom_raw_claim_requirement_reason,
            "selected_allatom_raw_claim_requirement_actions": list(
                selected_allatom_raw_claim_requirement_actions
            ),
            "selected_allatom_effective_actionability_status": selected_allatom_effective_actionability_status,
            "selected_allatom_effective_actionability_claim_requirement_mode": selected_allatom_effective_actionability_claim_requirement_mode,
            "selected_allatom_effective_actionability_claim_requirement_status": selected_allatom_effective_actionability_claim_requirement_status,
            "selected_allatom_effective_actionability_claim_requirement_reason": selected_allatom_effective_actionability_claim_requirement_reason,
            "selected_allatom_effective_blocking_order": selected_allatom_effective_blocking_order,
            "selected_allatom_effective_primary_blocking_domain": selected_allatom_effective_primary_blocking_domain,
            "selected_allatom_action_recipe_codes": list(selected_allatom_action_recipe_codes),
            "selected_allatom_action_recipe_rows": list(selected_allatom_action_recipe_rows),
            "selected_allatom_action_recipe_rollup_text": selected_allatom_action_recipe_rollup_text,
            "selected_allatom_claim_actionability_split_summary": selected_allatom_claim_actionability_split_summary,
            **selected_allatom_visual_fields,
            "selected_allatom_actionability_block_reason_codes": selected_allatom_actionability_block_reason_codes,
            "selected_allatom_actionability_soft_guidance_reasons": selected_allatom_actionability_soft_guidance_reasons,
            "selected_allatom_actionability_required_calculations": _coerce_text_list(
                selected_allatom_effective_required_calculations
                or selected_allatom_focus_summary.get("selected_allatom_actionability_required_calculations", [])
            ),
            "selected_allatom_actionability_action_list": selected_allatom_actionability_action_list,
            "selected_allatom_actionability_translation_gate_v2_failed_metrics": selected_allatom_actionability_translation_gate_v2_failed_metrics,
            "selected_allatom_actionability_translation_gate_v2_missing_metrics": selected_allatom_actionability_translation_gate_v2_missing_metrics,
            "selected_allatom_actionability_translation_gate_v2_thresholds": selected_allatom_actionability_translation_gate_v2_thresholds,
            "selected_allatom_commercial_hard_gate_failed_metrics_v2": selected_allatom_commercial_hard_gate_failed_metrics_v2,
            "selected_allatom_commercial_hard_gate_missing_metrics_v2": selected_allatom_commercial_hard_gate_missing_metrics_v2,
            "selected_allatom_commercial_score_thresholds_v2": selected_allatom_commercial_score_thresholds_v2,
            "selected_allatom_best_compound_name": str(
                bsrhs.get("selected_allatom_best_compound_name", bcris.get("selected_allatom_best_compound_name", ""))
            ).strip(),
            "selected_allatom_best_compound_name_human_readable": str(
                bsrhs.get(
                    "selected_allatom_best_compound_name_human_readable",
                    bcris.get("selected_allatom_best_compound_name_human_readable", ""),
                )
            ).strip(),
            "selected_allatom_best_compound_name_resolution": str(
                bsrhs.get(
                    "selected_allatom_best_compound_name_resolution",
                    bcris.get("selected_allatom_best_compound_name_resolution", "unresolved"),
                )
            ).strip(),
            "selected_allatom_best_mean_min_distance_A": selected_allatom_best_mean_min_distance_A,
            "selected_allatom_metric_source": selected_allatom_metric_source,
            "selected_allatom_promoted_candidate_count": selected_allatom_promoted_candidate_count,
            "selected_allatom_under_2p5_candidate_count": selected_allatom_under_2p5_candidate_count,
            "selected_allatom_near_candidate_count": selected_allatom_near_candidate_count,
            "selected_allatom_next_required_step": str(
                selected_allatom_next_required_step
            ).strip(),
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
            "broad_screen_stk17b_exploratory_freeze_state": str(exploratory_freeze.get("state", "")).strip(),
            "broad_screen_stk17b_exploratory_freeze_note": str(exploratory_freeze.get("freeze_note", "")).strip(),
            "broad_screen_stk17b_exploratory_freeze_target_id": str(
                exploratory_freeze.get("target_id", "")
            ).strip(),
            "broad_screen_stk17b_exploratory_freeze_hold_streak": int(
                exploratory_freeze.get("hold_streak", 0) or 0
            ),
            "broad_screen_stk17b_exploratory_freeze_hold_limit": int(
                exploratory_freeze.get("hold_limit", 0) or 0
            ),
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
            "broad_screen_mapping_fix_retry_policy_templates_artifact": "runs/wetlab_mapping_fix_retry_policy_templates_current.md",
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
                str(bresas.get("status", "")).strip() == "wetlab_rescue_anchor_artifacts_ready"
            ),
            "broad_screen_rescue_anchor_target_id": str(bresas.get("target_id", "")).strip(),
            "broad_screen_rescue_anchor_artifact_count": int(bresas.get("anchor_artifact_count", 0) or 0),
            "broad_screen_rescue_anchor_rescue_only": bool(bresas.get("rescue_only", False)),
            "broad_screen_rescue_anchor_native_anchor_artifact": str(
                bresas.get("native_anchor_artifact", "")
            ).strip(),
            "broad_screen_rescue_anchor_pocket_anchor_artifact": str(
                bresas.get("pocket_anchor_artifact", "")
            ).strip(),
            "broad_screen_rescue_anchor_next_required_step": str(
                bresas.get("next_required_step", "")
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
            "broad_screen_target_retry_focus_target_id": str(
                bstrpts.get("focus_target_id", "")
            ).strip(),
            "broad_screen_target_retry_focus_template_label": str(
                bstrpts.get("focus_template_label", "")
            ).strip(),
            "broad_screen_target_retry_focus_selected_command_kind": str(
                bstrpts.get("focus_selected_command_kind", "")
            ).strip(),
            "broad_screen_target_retry_focus_selected_threshold_A": float(
                bstrpts.get("focus_selected_threshold_A", 0.0) or 0.0
            ),
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
            "broad_screen_target_retry_next_required_step": str(
                bstrpts.get("next_required_step", "")
            ).strip(),
            "broad_screen_target_retry_policy_templates_artifact": "runs/wetlab_target_retry_policy_templates_current.md",
            "first_dispatch_track_id": str(srs.get("first_dispatch_track_id", "")).strip(),
            "first_dispatch_lead_targets": str(srs.get("first_dispatch_lead_targets", "")).strip(),
            "sender_name": str(ebs.get("sender_name", "")).strip(),
            "next_required_step": (
                selected_allatom_next_required_step
                if selected_allatom_next_required_step
                else str(bsrhs.get("selected_krs1_branch_review_next_required_step", "")).strip()
                if str(bsrhs.get("selected_krs1_branch_review_next_required_step", "")).strip()
                else str(bdr1.get("next_required_step", "")).strip()
                if str(bdr1.get("status", "")).strip() == "wetlab_dpre1_branch_review_surface_ready"
                and str(bdr1.get("next_required_step", "")).strip()
                else str(bstrob.get("next_required_step", "")).strip()
                if str(bstrob.get("next_required_step", "")).strip()
                else str(bstprp.get("next_required_step", "")).strip()
                if str(bstprp.get("next_required_step", "")).strip()
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
                if str(bstrpts.get("status", "")).strip() == "wetlab_target_retry_policy_templates_ready"
                and str(bstrpts.get("next_required_step", "")).strip()
                else _stk17b_followup_review_next_step(bssfrs)
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
                                or str(bssefls.get("status", "")).strip().startswith(
                                    "wetlab_stk17b_exploratory_followup_lane_"
                                )
                            )
                        )
                    )
                    and _stk17b_followup_review_next_step(bssfrs)
                )
                else
                _manual_retry_next_step(
                    broad_screen_retry_handoff_summary or {},
                    broad_screen_stk17b_manual_retry_lane,
                    broad_screen_stk17b_exploratory_retry_lane,
                    broad_screen_stk17b_exploratory_followup_lane,
                    broad_screen_plpro_manual_retry_lane,
                    broad_screen_lbdhodh_exploratory_retry_lane,
                    str(bssefls.get("next_required_step", "")).strip()
                    or
                    str(bsserls.get("next_required_step", "")).strip()
                    or str(bssmls.get("next_required_step", "")).strip()
                    or str(bspmls.get("next_required_step", "")).strip(),
                )
                if bool(bssefls.get("ready_for_manual_retry", False))
                or str(bssefls.get("status", "")).strip().startswith("wetlab_stk17b_exploratory_followup_lane_")
                or bool(bsserls.get("ready_for_manual_retry", False))
                or bool(bssmls.get("ready_for_manual_retry", False))
                or bool(bspmls.get("ready_for_manual_retry", False))
                or (
                    str(bsldrs.get("status", "")).strip().startswith("wetlab_lbdhodh_exploratory_retry_lane_")
                    and str(bsldrs.get("queue_status", "")).strip() == "running"
                )
                or bool(bsldrs.get("ready_for_manual_retry", False))
                else
                str(bssmfl.get("next_required_step", "")).strip()
                if int(bssmfl.get("ready_target_count", 0) or 0) > 0
                else
                str(bsmfrs.get("next_required_step", "")).strip()
                if int(bsmfrs.get("ready_target_count", 0) or 0) > 0
                else
                f"Continue the active broad-procurement shard for {bseqs.get('first_actionable_target_id', '')} {bseqs.get('first_actionable_shard_id', '')}, then refresh autofill before manual dispatch."
                if int(bseqs.get("running_row_count", 0) or 0) > 0
                else
                f"Dispatch {bseqs.get('first_actionable_target_id', '')} shard {bseqs.get('first_actionable_shard_id', '')}, then refresh autofill before manual dispatch."
                if int(bseqs.get("ready_now_row_count", 0) or 0) > 0
                else
                "Start from the final campaign summary, then launch the 100k broad-procurement queue and only after bulk reranking use the partner send round for manual dispatch."
                if str(bsqs.get("status", "")).strip() == "wetlab_broad_screen_queue_ready"
                else "Start from the final campaign summary, then use the partner send round in canonical order for manual dispatch."
            ),
        },
        "structured": {
            "final_campaign_summary_artifact": "runs/wetlab_final_campaign_summary_current.md",
            "master_terminal_review_artifact": "runs/wetlab_master_terminal_review_current.md",
            "outbound_priority_board_artifact": "runs/wetlab_outbound_execution_priority_board_current.md",
            "partner_send_round_artifact": "runs/wetlab_partner_send_round_current.md",
            "partner_export_bundle_artifact": "runs/wetlab_partner_first_contact_export_bundle_current.md",
            "broad_screen_queue_artifact": "runs/wetlab_broad_screen_queue_current.md",
            "broad_screen_bridge_artifact": "runs/wetlab_broad_screen_bridge_current.md",
            "broad_screen_compound_universe_artifact": "runs/wetlab_broad_screen_compound_universe_current.md",
            "broad_screen_execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
            "broad_screen_repurposing_autofill_artifact": "runs/wetlab_broad_screen_repurposing_autofill_current.md",
            "broad_screen_target_rerank_artifact": "runs/wetlab_broad_screen_target_rerank_current.md",
            "broad_screen_stability_score_artifact": "runs/wetlab_broad_screen_stability_score_current.md",
            "broad_screen_antitarget_queue_artifact": "runs/wetlab_broad_screen_antitarget_queue_current.md",
            "broad_screen_antitarget_execution_queue_artifact": "runs/wetlab_broad_screen_antitarget_execution_queue_current.md",
            "broad_screen_primary_watch_state_artifact": "runs/wetlab_broad_screen_primary_watcher_current.md",
            "broad_screen_primary_watch_artifact": "runs/wetlab_broad_screen_primary_watcher_current.md",
            "broad_screen_antitarget_watch_state_artifact": "runs/wetlab_broad_screen_antitarget_watcher_state_current.md",
            "broad_screen_antitarget_watch_artifact": "runs/wetlab_broad_screen_antitarget_watcher_current.md",
            "broad_screen_actual_append_artifact": "runs/wetlab_broad_screen_actual_append_current.md",
            "broad_screen_throughput_bridge_artifact": "runs/wetlab_broad_screen_throughput_bridge_current.md",
            "broad_screen_dpre1_branch_review_surface_artifact": "runs/wetlab_dpre1_branch_review_surface_current.md",
            "broad_screen_primary_retry_preset_artifact": "runs/wetlab_primary_retry_preset_surface_current.md",
            "broad_screen_primary_hold_guard_artifact": "runs/wetlab_primary_hold_guard_surface_current.md",
            "broad_screen_current_results_index_artifact": "runs/wetlab_current_results_index_current.md",
            "broad_screen_monitor_semantics_artifact": "runs/wetlab_monitor_semantics_current.md",
            "broad_screen_stk17b_exploratory_followup_lane_artifact": "runs/wetlab_stk17b_exploratory_followup_lane_current.md",
            "broad_screen_stk17b_followup_review_surface_artifact": "runs/wetlab_stk17b_followup_review_surface_current.md",
            "broad_screen_stk17b_exploratory_retry_lane_artifact": "runs/wetlab_stk17b_exploratory_retry_lane_current.md",
            "broad_screen_kinase_retry_policy_templates_artifact": "runs/wetlab_kinase_retry_policy_templates_current.md",
            "broad_screen_mapping_fix_retry_policy_templates_artifact": "runs/wetlab_mapping_fix_retry_policy_templates_current.md",
            "broad_screen_target_retry_policy_templates_artifact": "runs/wetlab_target_retry_policy_templates_current.md",
            "broad_screen_hard_target_rescue_lane_artifact": "runs/wetlab_hard_target_rescue_lane_current.md",
            "broad_screen_rescue_anchor_artifacts_artifact": "runs/wetlab_rescue_anchor_artifacts_current.md",
            "broad_screen_rescue_three_bead_candidates_artifact": "runs/wetlab_rescue_three_bead_candidates_current.md",
            "broad_screen_dengue_stage6_tuning_surface_artifact": "runs/wetlab_dengue_ns2b_ns3_protease_stage6_tuning_surface_current.md",
            "broad_screen_dengue_exploratory_retry_lane_artifact": "runs/wetlab_dengue_ns2b_ns3_protease_exploratory_retry_lane_current.md",
            "broad_screen_lbdhodh_stage6_tuning_surface_artifact": "runs/wetlab_lbdhodh_stage6_tuning_surface_current.md",
            "broad_screen_lbdhodh_exploratory_retry_lane_artifact": "runs/wetlab_lbdhodh_exploratory_retry_lane_current.md",
            "broad_screen_lbdhodh_gate51_validation_review_surface_artifact": "runs/wetlab_lbdhodh_gate51_validation_review_surface_current.md",
            "broad_screen_tcruzi_pde_promoted_top4_review_packet_artifact": "runs/wetlab_tcruzi_pde_promoted_top4_review_packet_current.md",
            "broad_screen_tcruzi_pde_rescue_only_branch_summary_artifact": "runs/wetlab_tcruzi_pde_rescue_only_branch_summary_current.md",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the wet-lab master handoff dashboard.")
    parser.add_argument("--final-campaign-summary-json", default=DEFAULT_FINAL_CAMPAIGN_SUMMARY_JSON)
    parser.add_argument("--master-terminal-review-json", default=DEFAULT_MASTER_TERMINAL_REVIEW_JSON)
    parser.add_argument("--outbound-board-json", default=DEFAULT_OUTBOUND_BOARD_JSON)
    parser.add_argument("--send-round-json", default=DEFAULT_SEND_ROUND_JSON)
    parser.add_argument("--export-bundle-json", default=DEFAULT_EXPORT_BUNDLE_JSON)
    parser.add_argument("--broad-screen-queue-json", default=DEFAULT_BROAD_SCREEN_QUEUE_JSON)
    parser.add_argument("--broad-screen-bridge-json", default=DEFAULT_BROAD_SCREEN_BRIDGE_JSON)
    parser.add_argument("--broad-screen-compound-universe-json", default=DEFAULT_BROAD_SCREEN_COMPOUND_UNIVERSE_JSON)
    parser.add_argument("--broad-screen-execution-queue-json", default=DEFAULT_BROAD_SCREEN_EXECUTION_QUEUE_JSON)
    parser.add_argument("--broad-screen-repurposing-autofill-json", default=DEFAULT_BROAD_SCREEN_REPURPOSING_AUTOFILL_JSON)
    parser.add_argument("--broad-screen-target-rerank-json", default=DEFAULT_BROAD_SCREEN_TARGET_RERANK_JSON)
    parser.add_argument("--broad-screen-stability-score-json", default=DEFAULT_BROAD_SCREEN_STABILITY_SCORE_JSON)
    parser.add_argument("--broad-screen-antitarget-queue-json", default=DEFAULT_BROAD_SCREEN_ANTITARGET_QUEUE_JSON)
    parser.add_argument("--broad-screen-antitarget-execution-queue-json", default=DEFAULT_BROAD_SCREEN_ANTITARGET_EXECUTION_QUEUE_JSON)
    parser.add_argument("--broad-screen-primary-watch-state-json", default=DEFAULT_BROAD_SCREEN_PRIMARY_WATCH_STATE_JSON)
    parser.add_argument("--broad-screen-primary-watch-json", default=DEFAULT_BROAD_SCREEN_PRIMARY_WATCH_JSON)
    parser.add_argument("--broad-screen-antitarget-watch-state-json", default=DEFAULT_BROAD_SCREEN_ANTITARGET_WATCH_STATE_JSON)
    parser.add_argument("--broad-screen-antitarget-watch-json", default=DEFAULT_BROAD_SCREEN_ANTITARGET_WATCH_JSON)
    parser.add_argument("--broad-screen-actual-append-json", default=DEFAULT_BROAD_SCREEN_ACTUAL_APPEND_JSON)
    parser.add_argument("--broad-screen-throughput-bridge-json", default=DEFAULT_BROAD_SCREEN_THROUGHPUT_BRIDGE_JSON)
    parser.add_argument("--broad-screen-primary-retry-preset-json", default=DEFAULT_BROAD_SCREEN_PRIMARY_RETRY_PRESET_JSON)
    parser.add_argument("--broad-screen-primary-hold-guard-json", default=DEFAULT_BROAD_SCREEN_PRIMARY_HOLD_GUARD_JSON)
    parser.add_argument("--broad-screen-current-results-index-json", default=DEFAULT_BROAD_SCREEN_CURRENT_RESULTS_INDEX_JSON)
    parser.add_argument("--broad-screen-monitor-semantics-json", default=DEFAULT_BROAD_SCREEN_MONITOR_SEMANTICS_JSON)
    parser.add_argument("--broad-screen-retry-handoff-summary-json", default=DEFAULT_BROAD_SCREEN_RETRY_HANDOFF_SUMMARY_JSON)
    parser.add_argument("--broad-screen-dpre1-branch-review-surface-json", default=DEFAULT_BROAD_SCREEN_DPRE1_BRANCH_REVIEW_SURFACE_JSON)
    parser.add_argument("--broad-screen-stk17b-manual-retry-lane-json", default=DEFAULT_BROAD_SCREEN_STK17B_MANUAL_RETRY_LANE_JSON)
    parser.add_argument("--broad-screen-stk17b-exploratory-retry-lane-json", default=DEFAULT_BROAD_SCREEN_STK17B_EXPLORATORY_RETRY_LANE_JSON)
    parser.add_argument("--broad-screen-stk17b-exploratory-followup-lane-json", default=DEFAULT_BROAD_SCREEN_STK17B_EXPLORATORY_FOLLOWUP_LANE_JSON)
    parser.add_argument("--broad-screen-stk17b-followup-review-surface-json", default=DEFAULT_BROAD_SCREEN_STK17B_FOLLOWUP_REVIEW_SURFACE_JSON)
    parser.add_argument("--broad-screen-plpro-manual-retry-lane-json", default=DEFAULT_BROAD_SCREEN_PLPRO_MANUAL_RETRY_LANE_JSON)
    parser.add_argument("--broad-screen-mapping-fix-retry-support-json", default=DEFAULT_BROAD_SCREEN_MAPPING_FIX_RETRY_SUPPORT_JSON)
    parser.add_argument("--broad-screen-stage1-mapping-fix-lanes-json", default=DEFAULT_BROAD_SCREEN_STAGE1_MAPPING_FIX_LANES_JSON)
    parser.add_argument("--broad-screen-mapping-fix-retry-policy-templates-json", default=DEFAULT_BROAD_SCREEN_MAPPING_FIX_RETRY_POLICY_TEMPLATES_JSON)
    parser.add_argument("--broad-screen-kinase-retry-policy-templates-json", default=DEFAULT_BROAD_SCREEN_KINASE_RETRY_POLICY_TEMPLATES_JSON)
    parser.add_argument("--broad-screen-target-retry-policy-templates-json", default=DEFAULT_BROAD_SCREEN_TARGET_RETRY_POLICY_TEMPLATES_JSON)
    parser.add_argument("--broad-screen-dengue-stage6-tuning-surface-json", default=DEFAULT_BROAD_SCREEN_DENGUE_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--broad-screen-dengue-exploratory-retry-lane-json", default=DEFAULT_BROAD_SCREEN_DENGUE_EXPLORATORY_RETRY_LANE_JSON)
    parser.add_argument("--broad-screen-lbdhodh-stage6-tuning-surface-json", default=DEFAULT_BROAD_SCREEN_LBDHODH_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--broad-screen-lbdhodh-exploratory-retry-lane-json", default=DEFAULT_BROAD_SCREEN_LBDHODH_EXPLORATORY_RETRY_LANE_JSON)
    parser.add_argument("--broad-screen-lbdhodh-gate51-validation-review-surface-json", default=DEFAULT_BROAD_SCREEN_LBDHODH_GATE51_VALIDATION_REVIEW_SURFACE_JSON)
    parser.add_argument("--broad-screen-tcruzi-pde-promoted-top4-review-packet-json", default=DEFAULT_BROAD_SCREEN_TCRUZI_PDE_PROMOTED_TOP4_REVIEW_PACKET_JSON)
    parser.add_argument("--broad-screen-tcruzi-pde-rescue-only-branch-summary-json", default=DEFAULT_BROAD_SCREEN_TCRUZI_PDE_RESCUE_ONLY_BRANCH_SUMMARY_JSON)
    parser.add_argument("--broad-screen-selected-allatom-visual-bundle-json", default=DEFAULT_BROAD_SCREEN_SELECTED_ALLATOM_VISUAL_BUNDLE_JSON)
    parser.add_argument("--broad-screen-hard-target-rescue-lane-json", default=DEFAULT_BROAD_SCREEN_HARD_TARGET_RESCUE_LANE_JSON)
    parser.add_argument("--broad-screen-rescue-anchor-artifacts-json", default=DEFAULT_BROAD_SCREEN_RESCUE_ANCHOR_ARTIFACTS_JSON)
    parser.add_argument("--broad-screen-rescue-three-bead-candidates-json", default=DEFAULT_BROAD_SCREEN_RESCUE_THREE_BEAD_CANDIDATES_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    payload = build_payload(
        load_json(args.final_campaign_summary_json),
        load_json(args.master_terminal_review_json),
        load_json(args.outbound_board_json),
        load_json(args.send_round_json),
        load_json(args.export_bundle_json),
        load_json(args.broad_screen_queue_json),
        load_json(args.broad_screen_bridge_json),
        load_json(args.broad_screen_compound_universe_json),
        load_json(args.broad_screen_execution_queue_json),
        load_json(args.broad_screen_repurposing_autofill_json),
        load_json(args.broad_screen_target_rerank_json),
        maybe_load_json(args.broad_screen_stability_score_json),
        maybe_load_json(args.broad_screen_antitarget_queue_json),
        maybe_load_json(args.broad_screen_antitarget_execution_queue_json),
        maybe_load_json(args.broad_screen_primary_watch_state_json) or maybe_load_json(LEGACY_BROAD_SCREEN_PRIMARY_WATCH_STATE_JSON),
        maybe_load_json(args.broad_screen_primary_watch_json) or maybe_load_json(LEGACY_BROAD_SCREEN_PRIMARY_WATCH_JSON),
        maybe_load_json(args.broad_screen_antitarget_watch_state_json),
        maybe_load_json(args.broad_screen_antitarget_watch_json),
        maybe_load_json(args.broad_screen_actual_append_json),
        maybe_load_json(args.broad_screen_throughput_bridge_json),
        maybe_load_json(args.broad_screen_primary_retry_preset_json),
        maybe_load_json(args.broad_screen_primary_hold_guard_json),
        maybe_load_json(args.broad_screen_current_results_index_json),
        maybe_load_json(args.broad_screen_monitor_semantics_json),
        maybe_load_json(args.broad_screen_retry_handoff_summary_json),
        maybe_load_json(args.broad_screen_dpre1_branch_review_surface_json),
        maybe_load_json(args.broad_screen_stk17b_manual_retry_lane_json),
        maybe_load_json(args.broad_screen_stk17b_exploratory_retry_lane_json),
        maybe_load_json(args.broad_screen_stk17b_exploratory_followup_lane_json),
        maybe_load_json(args.broad_screen_stk17b_followup_review_surface_json),
        maybe_load_json(args.broad_screen_plpro_manual_retry_lane_json),
        maybe_load_json(args.broad_screen_mapping_fix_retry_support_json),
        maybe_load_json(args.broad_screen_stage1_mapping_fix_lanes_json),
        maybe_load_json(args.broad_screen_mapping_fix_retry_policy_templates_json),
        maybe_load_json(args.broad_screen_hard_target_rescue_lane_json),
        maybe_load_json(args.broad_screen_rescue_anchor_artifacts_json),
        maybe_load_json(args.broad_screen_rescue_three_bead_candidates_json),
        maybe_load_json(args.broad_screen_kinase_retry_policy_templates_json),
        maybe_load_json(args.broad_screen_target_retry_policy_templates_json),
        maybe_load_json(args.broad_screen_dengue_stage6_tuning_surface_json),
        maybe_load_json(args.broad_screen_dengue_exploratory_retry_lane_json),
        maybe_load_json(args.broad_screen_lbdhodh_stage6_tuning_surface_json),
        maybe_load_json(args.broad_screen_lbdhodh_exploratory_retry_lane_json),
        maybe_load_json(args.broad_screen_lbdhodh_gate51_validation_review_surface_json),
        maybe_load_json(args.broad_screen_tcruzi_pde_promoted_top4_review_packet_json),
        maybe_load_json(args.broad_screen_tcruzi_pde_rescue_only_branch_summary_json),
        maybe_load_json(args.broad_screen_selected_allatom_visual_bundle_json),
    )
    write_artifact(args.out_md, "Wet-Lab Master Handoff Dashboard", payload)
