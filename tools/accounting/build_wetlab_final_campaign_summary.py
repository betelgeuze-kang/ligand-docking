#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from typing import Any

try:
    from tools.wetlab_selected_allatom_canonical import (
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
from tools.wetlab_selected_allatom_visual import (
    resolve_selected_allatom_visual_bundle,
    selected_allatom_visual_surface_fields,
)

from tools.wetlab.wetlab_pose_validation_utils import build_pose_validation_fields_from_summary
from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

DEFAULT_TERMINAL_REVIEW_JSON = "runs/wetlab_master_terminal_review_current.json"
DEFAULT_MASTER_QUEUE_JSON = "runs/wetlab_master_execution_queue_current.json"
DEFAULT_EXPORT_BUNDLE_JSON = "runs/wetlab_partner_first_contact_export_bundle_current.json"
DEFAULT_OUTBOUND_BOARD_JSON = "runs/wetlab_outbound_execution_priority_board_current.json"
DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_BLUEPRINT_JSON = "runs/wetlab_wave1_campaign_blueprint_current.json"
DEFAULT_BROAD_SCREEN_QUEUE_JSON = "runs/wetlab_broad_screen_queue_current.json"
DEFAULT_BROAD_SCREEN_BRIDGE_JSON = "runs/wetlab_broad_screen_bridge_current.json"
DEFAULT_BROAD_SCREEN_COMPOUND_UNIVERSE_JSON = "runs/wetlab_broad_screen_compound_universe_current.json"
DEFAULT_BROAD_SCREEN_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_BROAD_SCREEN_REPURPOSING_AUTOFILL_JSON = "runs/wetlab_broad_screen_repurposing_autofill_current.json"
DEFAULT_BROAD_SCREEN_TARGET_RERANK_JSON = "runs/wetlab_broad_screen_target_rerank_current.json"
DEFAULT_BROAD_SCREEN_STABILITY_SCORE_JSON = "runs/wetlab_broad_screen_stability_score_current.json"
DEFAULT_BROAD_SCREEN_ANTITARGET_QUEUE_JSON = "runs/wetlab_broad_screen_antitarget_queue_current.json"
DEFAULT_BROAD_SCREEN_ANTITARGET_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_antitarget_execution_queue_current.json"
DEFAULT_BROAD_SCREEN_ACTUAL_APPEND_JSON = "runs/wetlab_broad_screen_actual_append_current.json"
DEFAULT_BROAD_SCREEN_DENGUE_STAGE6_TUNING_SURFACE_JSON = "runs/wetlab_dengue_ns2b_ns3_protease_stage6_tuning_surface_current.json"
DEFAULT_BROAD_SCREEN_DENGUE_EXPLORATORY_RETRY_LANE_JSON = "runs/wetlab_dengue_ns2b_ns3_protease_exploratory_retry_lane_current.json"
DEFAULT_BROAD_SCREEN_LBDHODH_STAGE6_TUNING_SURFACE_JSON = "runs/wetlab_lbdhodh_stage6_tuning_surface_current.json"
DEFAULT_BROAD_SCREEN_LBDHODH_EXPLORATORY_RETRY_LANE_JSON = "runs/wetlab_lbdhodh_exploratory_retry_lane_current.json"
DEFAULT_BROAD_SCREEN_LBDHODH_GATE51_VALIDATION_REVIEW_SURFACE_JSON = "runs/wetlab_lbdhodh_gate51_validation_review_surface_current.json"
DEFAULT_BROAD_SCREEN_DPRE1_BRANCH_REVIEW_SURFACE_JSON = "runs/wetlab_dpre1_branch_review_surface_current.json"
DEFAULT_BROAD_SCREEN_RETRY_HANDOFF_SUMMARY_JSON = "runs/wetlab_retry_handoff_summary_current.json"
DEFAULT_BROAD_SCREEN_TCRUZI_KRS1_BRANCH_REVIEW_SURFACE_JSON = "runs/wetlab_tcruzi_krs1_branch_review_surface_current.json"
DEFAULT_BROAD_SCREEN_TCRUZI_KRS1_GUARDED_BRANCH_SUMMARY_JSON = "runs/wetlab_tcruzi_krs1_guarded_branch_summary_current.json"
DEFAULT_BROAD_SCREEN_TCRUZI_PDE_RESCUE_REVIEW_SURFACE_JSON = "runs/wetlab_tcruzi_pde_rescue_review_surface_current.json"
DEFAULT_BROAD_SCREEN_TCRUZI_PDE_PROMOTED_TOP4_REVIEW_PACKET_JSON = "runs/wetlab_tcruzi_pde_promoted_top4_review_packet_current.json"
DEFAULT_BROAD_SCREEN_TCRUZI_PDE_RESCUE_ONLY_BRANCH_SUMMARY_JSON = "runs/wetlab_tcruzi_pde_rescue_only_branch_summary_current.json"
DEFAULT_BROAD_SCREEN_TCRUZI_PDE_RESCUE_OPERATOR_PACKET_JSON = "runs/wetlab_tcruzi_pde_rescue_operator_packet_current.json"
DEFAULT_BROAD_SCREEN_RESCUE_ONLY_BRANCH_TEMPLATES_JSON = "runs/wetlab_rescue_only_branch_templates_current.json"
DEFAULT_BROAD_SCREEN_TARGET_RETRY_POLICY_TEMPLATES_JSON = "runs/wetlab_target_retry_policy_templates_current.json"
DEFAULT_BROAD_SCREEN_MAPPING_FIX_RETRY_POLICY_TEMPLATES_JSON = "runs/wetlab_mapping_fix_retry_policy_templates_current.json"
DEFAULT_BROAD_SCREEN_HARD_TARGET_RESCUE_LANE_JSON = "runs/wetlab_hard_target_rescue_lane_current.json"
DEFAULT_BROAD_SCREEN_RESCUE_ANCHOR_ARTIFACTS_JSON = "runs/wetlab_rescue_anchor_artifacts_current.json"
DEFAULT_BROAD_SCREEN_RESCUE_THREE_BEAD_CANDIDATES_JSON = "runs/wetlab_rescue_three_bead_candidates_current.json"
DEFAULT_BROAD_SCREEN_SELECTED_ALLATOM_VISUAL_BUNDLE_JSON = "runs/selected_allatom_visual_bundle_current.json"
DEFAULT_OUT_MD = "runs/wetlab_final_campaign_summary_current.md"
KRS1_TARGET_ID = "T. cruzi KRS1"
SEMI_HARD_CLAIM_TARGETS = {
    "T. cruzi PDE",
    "T. cruzi KRS1",
    "Leishmania braziliensis DHODH",
    "DprE1",
    "Dengue NS2B-NS3 protease",
}


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _text(*values: Any, default: str = "") -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return default


def _joined(*values: Any, sep: str = " | ", default: str = "") -> str:
    parts = [str(value or "").strip() for value in values if str(value or "").strip()]
    return sep.join(parts) if parts else default


def _safe_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in {"", None}:
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "ready", "pass", "passed"}:
        return True
    if text in {"0", "false", "f", "no", "n", "fail", "failed"}:
        return False
    return None


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


def _resolve_optional_bool(summary: dict[str, Any], *keys: str) -> tuple[bool, bool]:
    for key in keys:
        if _has_value(summary, key):
            return True, _resolve_bool(summary.get(key), default=False)
    return False, False


def _safe_float(value: Any) -> float | None:
    if value in {"", None}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _resolve_float(*values: Any, default: float = 0.0) -> float:
    for value in values:
        parsed = _safe_float(value)
        if parsed is not None:
            return parsed
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


def _selected_allatom_review_packet_path(surface_label: str) -> str:
    label = str(surface_label or "").strip()
    if not label:
        return ""
    if label.endswith(".json"):
        return label
    if label.startswith("wetlab_"):
        return f"runs/{label}_current.json"
    return f"runs/wetlab_{label}_current.json"


def _selected_allatom_review_packet_summary(surface_label: str) -> dict[str, Any]:
    path = _selected_allatom_review_packet_path(surface_label)
    payload = maybe_load_json(path) if path else None
    return _summary(payload)


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


def _infer_raw_claim_requirement_mode(target_id: str, explicit_mode: str, claim_gate_reported: bool) -> str:
    mode = str(explicit_mode or "").strip()
    if mode:
        return mode
    if str(target_id or "").strip() in SEMI_HARD_CLAIM_TARGETS:
        return "semi_hard"
    return "not_applicable" if claim_gate_reported else ""


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

    failed = set(str(item or "").strip() for item in translation_failed_checks if str(item or "").strip())
    warnings = set(str(item or "").strip() for item in translation_warning_checks if str(item or "").strip())

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
    codes = [str(row.get("code", "")).strip() for row in rows if str(row.get("code", "")).strip()]
    rollup_text = " | ".join(
        f"{row['priority']}:{row['code']} -> {row['next_calculation']}" for row in rows
    )
    return {
        "action_recipe_codes": codes,
        "action_recipe_rows": rows,
        "action_recipe_rollup_text": rollup_text,
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
    pose_validation_reported: bool,
    pose_validation_version: str,
    pose_validation_status: str,
    pose_validation_soft_status: str,
    pose_validation_score: float | None,
    pose_validation_pass: bool,
    pose_validation_pose_preservation_rmsd_A: float | None,
    pose_validation_backmapping_consistency_score: float | None,
    pose_validation_reason: str,
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
            "pose_validation_rollup": "pose validation not reported",
            "pose_validation_summary": "Pose-validation metrics are not yet reported for the selected all-atom focus.",
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
    if pose_validation_reported:
        pose_validation_rollup = f"pose validation {pose_validation_status or 'reported'}"
        pose_validation_detail_parts: list[str] = []
        if pose_validation_score is not None:
            pose_validation_detail_parts.append(f"score {pose_validation_score:.1f}")
        if pose_validation_soft_status:
            pose_validation_detail_parts.append(f"soft {pose_validation_soft_status}")
        if pose_validation_pose_preservation_rmsd_A is not None:
            pose_validation_detail_parts.append(
                f"pose RMSD {pose_validation_pose_preservation_rmsd_A:.3f}A"
            )
        if pose_validation_backmapping_consistency_score is not None:
            pose_validation_detail_parts.append(
                f"backmapping {pose_validation_backmapping_consistency_score:.3f}"
            )
        if pose_validation_detail_parts:
            pose_validation_rollup += " | " + " | ".join(pose_validation_detail_parts)
        pose_validation_sentence = (
            f"Pose validation ({pose_validation_version or 'schema unreported'}): "
            f"status {pose_validation_status or 'reported'}"
            + (f", score {pose_validation_score:.1f}" if pose_validation_score is not None else "")
            + (
                f", pose preservation RMSD {pose_validation_pose_preservation_rmsd_A:.3f}A"
                if pose_validation_pose_preservation_rmsd_A is not None
                else ""
            )
            + (
                f", backmapping consistency {pose_validation_backmapping_consistency_score:.3f}"
                if pose_validation_backmapping_consistency_score is not None
                else ""
            )
            + (
                ", gate passed"
                if pose_validation_pass
                else ", gate needs repair"
                if pose_validation_status == "fail"
                else ", gate remains watchful"
            )
            + (f", rationale {pose_validation_reason}" if pose_validation_reason else "")
            + "."
        )
    else:
        pose_validation_rollup = "pose validation not reported"
        pose_validation_sentence = "Pose-validation metrics are not yet reported for this focus."
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
        "pose_validation_rollup": pose_validation_rollup,
        "pose_validation_summary": pose_validation_sentence.strip(),
        "human_summary": (
            f"Selected all-atom focus {focus_label}: {review_rollup}, {final_gate_rollup}, {claim_rollup}. "
            f"{wetlab_gate_rollup}. Semantics: {semantics_rollup}."
            + (f" Details: {'; '.join(detail_parts)}." if detail_parts else "")
            + f" {commercial_sentence.strip()}"
            + f" {commercial_sentence_v2.strip()}"
            + f" {translation_sentence.strip()}"
            + f" {pose_validation_sentence.strip()}"
        ),
    }


def _stage6_retry_template_summary(target_retry_policy_templates: dict[str, Any] | None) -> dict[str, Any]:
    summary = _summary(target_retry_policy_templates)
    rows = [dict(row) for row in ((target_retry_policy_templates or {}).get("rows", []) or [])]
    stage6_rows = [
        row
        for row in rows
        if str(row.get("row_kind", "")).strip() == "target_retry_policy_template"
        and str(row.get("template_scope", "")).strip() == "guarded_stage6_tuning_candidate"
    ]
    if not summary or not stage6_rows:
        return {}
    gate45_rows = [row for row in stage6_rows if "gate45" in str(row.get("selected_command_kind", "")).strip()]
    gate51_rows = [row for row in stage6_rows if "gate51" in str(row.get("selected_command_kind", "")).strip()]
    focus_row = next(
        (row for row in stage6_rows if str(row.get("target_id", "")).strip() == "Dengue NS2B-NS3 protease"),
        next((row for row in stage6_rows if str(row.get("target_id", "")).strip() == "Cathepsin K"), stage6_rows[0]),
    )
    return {
        "status": summary.get("status", ""),
        "template_target_count": len(stage6_rows),
        "gate45_candidate_target_count": len(gate45_rows),
        "gate51_candidate_target_count": len(gate51_rows),
        "ready_targets": "; ".join(str(row.get("target_id", "")).strip() for row in stage6_rows if str(row.get("target_id", "")).strip()),
        "gate45_targets": "; ".join(str(row.get("target_id", "")).strip() for row in gate45_rows if str(row.get("target_id", "")).strip()),
        "gate51_targets": "; ".join(str(row.get("target_id", "")).strip() for row in gate51_rows if str(row.get("target_id", "")).strip()),
        "focus_target_id": str(focus_row.get("target_id", "")).strip(),
        "focus_template_label": str(focus_row.get("template_label", "")).strip(),
        "focus_selected_command_kind": str(focus_row.get("selected_command_kind", "")).strip(),
        "focus_selected_threshold_A": float(focus_row.get("selected_threshold_A", 0.0) or 0.0),
        "next_required_step": str(focus_row.get("next_required_step", "")).strip(),
        "policy_templates_artifact": "runs/wetlab_target_retry_policy_templates_current.md",
    }


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
        if _text(summary.get("status")) != status_name:
            continue
        explicit = _text(summary.get("next_required_step"))
        if explicit:
            return explicit
        target_id = _text(summary.get("target_id"))
        shard_id = _text(summary.get("shard_id"))
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


def _krs1_live_focus_target_id(retry_handoff_summary: dict[str, Any] | None) -> str:
    summary = _summary(retry_handoff_summary)
    for key in (
        "selected_manual_retry_target_id",
        "manual_retry_focus_target_id",
        "selected_rescue_review_target_id",
        "selected_validated_target_id",
        "selected_rescue_branch_target_id",
        "guard_blocked_target_id",
        "focused_target_id",
        "selected_target_id",
        "current_target_id",
        "active_target_id",
        "first_actionable_target_id",
    ):
        if _text(summary.get(key)) == KRS1_TARGET_ID:
            return KRS1_TARGET_ID
    return ""


def _retry_handoff_focus_target_id(
    retry_handoff_summary: dict[str, Any] | None,
    krs1_live_focus_target_id: str = "",
) -> str:
    if krs1_live_focus_target_id:
        return krs1_live_focus_target_id
    summary = _summary(retry_handoff_summary)
    return _text(
        summary.get("selected_rescue_review_target_id"),
        summary.get("selected_validated_target_id"),
        summary.get("selected_manual_retry_target_id"),
        summary.get("manual_retry_focus_target_id"),
        summary.get("selected_rescue_branch_target_id"),
        summary.get("guard_blocked_target_id"),
    )


def _tcruzi_krs1_guarded_branch_selection(
    krs1_live_focus_target_id: str,
    branch_review_surface: dict[str, Any] | None,
    guarded_branch_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    if krs1_live_focus_target_id != KRS1_TARGET_ID:
        return {}
    branch_review_s = _summary(branch_review_surface)
    if _text(branch_review_s.get("status")) != "wetlab_tcruzi_krs1_branch_review_surface_ready":
        return {}
    guarded_branch_s = _summary(guarded_branch_summary)
    branch_validated = bool(guarded_branch_s.get("branch_validated", False)) or "validated" in _text(
        guarded_branch_s.get("status")
    ) or "validated" in _text(guarded_branch_s.get("branch_state"))
    selected_surface_label = _text(
        guarded_branch_s.get("branch_label"),
        branch_review_s.get("branch_label"),
        "tcruzi_krs1_guarded_gate51_branch",
    )
    selected_branch_state = _text(
        guarded_branch_s.get("branch_state"),
        branch_review_s.get("branch_state"),
        "guarded_gate51_review_default_lane_closed",
    )
    selected_command_kind = _text(
        guarded_branch_s.get("selected_command_kind"),
        branch_review_s.get("exploratory_retry_selected_command_kind"),
        branch_review_s.get("stage6_tuning_immediately_runnable_command_kind"),
    )
    selected_threshold_A = float(
        guarded_branch_s.get(
            "selected_threshold_A",
            branch_review_s.get(
                "exploratory_retry_selected_threshold_A",
                branch_review_s.get("stage6_tuning_recommended_threshold_A", 0.0),
            ),
        )
        or 0.0
    )
    successor_target = _text(branch_review_s.get("successor_target"), "LRRK2")
    successor_gate_state = (
        "open_for_lrrk2_execution"
        if branch_validated
        else _text(branch_review_s.get("successor_gate_state"), "blocked_pending_tcruzi_krs1_guarded_review")
    )
    selected_next_required_step = _text(
        guarded_branch_s.get("next_required_step"),
        branch_review_s.get("next_required_step"),
        "Review T. cruzi KRS1 through the guarded gate5.1 branch, keep the default lane closed, and do not reopen auto-start until the gate5.1 exploratory retry is explicitly resolved.",
    )
    return {
        "broad_screen_tcruzi_krs1_branch_review_ready": True,
        "broad_screen_tcruzi_krs1_branch_review_target_id": _text(branch_review_s.get("target_id"), KRS1_TARGET_ID),
        "broad_screen_tcruzi_krs1_branch_review_branch_label": selected_surface_label,
        "broad_screen_tcruzi_krs1_branch_review_branch_state": selected_branch_state,
        "broad_screen_tcruzi_krs1_branch_review_source_priority": _text(
            branch_review_s.get("source_priority"),
            guarded_branch_s.get("source_priority"),
        ),
        "broad_screen_tcruzi_krs1_branch_review_decision_source_priority": _text(
            branch_review_s.get("decision_source_priority"),
            guarded_branch_s.get("decision_source_priority"),
        ),
        "broad_screen_tcruzi_krs1_branch_review_result_review_status": _text(
            guarded_branch_s.get("status"),
            branch_review_s.get("result_review_status"),
        ),
        "broad_screen_tcruzi_krs1_branch_review_result_summary_status": _text(
            guarded_branch_s.get("status"),
            branch_review_s.get("result_summary_status"),
        ),
        "broad_screen_tcruzi_krs1_branch_review_launch_packet_status": _text(branch_review_s.get("launch_packet_status")),
        "broad_screen_tcruzi_krs1_branch_review_stage6_tuning_surface_ready": bool(
            branch_review_s.get("stage6_tuning_surface_ready", False)
        ),
        "broad_screen_tcruzi_krs1_branch_review_stage6_tuning_source_priority": _text(
            branch_review_s.get("stage6_tuning_source_priority")
        ),
        "broad_screen_tcruzi_krs1_branch_review_stage6_tuning_recommended_threshold_A": float(
            branch_review_s.get("stage6_tuning_recommended_threshold_A", 0.0) or 0.0
        ),
        "broad_screen_tcruzi_krs1_branch_review_stage6_tuning_immediately_runnable_command_kind": _text(
            branch_review_s.get("stage6_tuning_immediately_runnable_command_kind")
        ),
        "broad_screen_tcruzi_krs1_branch_review_exploratory_retry_lane_ready": bool(
            branch_review_s.get("exploratory_retry_lane_ready", False)
        ),
        "broad_screen_tcruzi_krs1_branch_review_exploratory_source_priority": _text(
            branch_review_s.get("exploratory_source_priority")
        ),
        "broad_screen_tcruzi_krs1_branch_review_exploratory_retry_lane_label": _text(
            branch_review_s.get("exploratory_retry_lane_label")
        ),
        "broad_screen_tcruzi_krs1_branch_review_exploratory_retry_selected_command_kind": _text(
            branch_review_s.get("exploratory_retry_selected_command_kind"),
            selected_command_kind,
        ),
        "broad_screen_tcruzi_krs1_branch_review_exploratory_retry_selected_threshold_A": float(
            branch_review_s.get("exploratory_retry_selected_threshold_A", selected_threshold_A) or selected_threshold_A
        ),
        "broad_screen_tcruzi_krs1_branch_review_successor_target": successor_target,
        "broad_screen_tcruzi_krs1_branch_review_successor_gate_state": successor_gate_state,
        "broad_screen_tcruzi_krs1_branch_review_next_required_step": selected_next_required_step,
        "broad_screen_tcruzi_krs1_guarded_branch_summary_ready": bool(guarded_branch_s),
        "broad_screen_tcruzi_krs1_guarded_branch_summary_validated": branch_validated,
        "broad_screen_tcruzi_krs1_guarded_branch_summary_target_id": _text(
            guarded_branch_s.get("target_id"),
            branch_review_s.get("target_id"),
            KRS1_TARGET_ID,
        ),
        "broad_screen_tcruzi_krs1_guarded_branch_summary_branch_label": selected_surface_label,
        "broad_screen_tcruzi_krs1_guarded_branch_summary_branch_state": selected_branch_state,
        "broad_screen_tcruzi_krs1_guarded_branch_summary_selected_command_kind": selected_command_kind,
        "broad_screen_tcruzi_krs1_guarded_branch_summary_selected_threshold_A": selected_threshold_A,
        "broad_screen_tcruzi_krs1_guarded_branch_summary_next_required_step": selected_next_required_step,
        "selected_krs1_guarded_branch_review_target_id": KRS1_TARGET_ID,
        "selected_krs1_guarded_branch_review_surface_label": selected_surface_label,
        "selected_krs1_guarded_branch_review_branch_state": selected_branch_state,
        "selected_krs1_guarded_branch_review_selected_command_kind": selected_command_kind,
        "selected_krs1_guarded_branch_review_selected_threshold_A": selected_threshold_A,
        "selected_krs1_guarded_branch_review_successor_target": successor_target,
        "selected_krs1_guarded_branch_review_successor_gate_state": successor_gate_state,
        "selected_krs1_guarded_branch_review_next_required_step": selected_next_required_step,
    }


def build_payload(
    terminal_review: dict[str, Any],
    master_queue: dict[str, Any],
    export_bundle: dict[str, Any],
    outbound_board: dict[str, Any],
    portfolio: dict[str, Any],
    blueprint: dict[str, Any],
    broad_screen_queue: dict[str, Any],
    broad_screen_bridge: dict[str, Any],
    broad_screen_compound_universe: dict[str, Any] | None = None,
    broad_screen_execution_queue: dict[str, Any] | None = None,
    broad_screen_repurposing_autofill: dict[str, Any] | None = None,
    broad_screen_target_rerank: dict[str, Any] | None = None,
    broad_screen_stability_score: dict[str, Any] | None = None,
    broad_screen_antitarget_queue: dict[str, Any] | None = None,
    broad_screen_antitarget_execution_queue: dict[str, Any] | None = None,
    broad_screen_actual_append: dict[str, Any] | None = None,
    broad_screen_dengue_stage6_tuning_surface: dict[str, Any] | None = None,
    broad_screen_dengue_exploratory_retry_lane: dict[str, Any] | None = None,
    broad_screen_lbdhodh_stage6_tuning_surface: dict[str, Any] | None = None,
    broad_screen_lbdhodh_exploratory_retry_lane: dict[str, Any] | None = None,
    broad_screen_lbdhodh_gate51_validation_review_surface: dict[str, Any] | None = None,
    broad_screen_dpre1_branch_review_surface: dict[str, Any] | None = None,
    broad_screen_tcruzi_krs1_branch_review_surface: dict[str, Any] | None = None,
    broad_screen_tcruzi_pde_rescue_review_surface: dict[str, Any] | None = None,
    broad_screen_tcruzi_pde_promoted_top4_review_packet: dict[str, Any] | None = None,
    broad_screen_tcruzi_pde_rescue_only_branch_summary: dict[str, Any] | None = None,
    broad_screen_tcruzi_pde_rescue_operator_packet: dict[str, Any] | None = None,
    broad_screen_rescue_only_branch_templates: dict[str, Any] | None = None,
    broad_screen_target_retry_policy_templates: dict[str, Any] | None = None,
    broad_screen_mapping_fix_retry_policy_templates: dict[str, Any] | None = None,
    broad_screen_hard_target_rescue_lane: dict[str, Any] | None = None,
    broad_screen_rescue_anchor_artifacts: dict[str, Any] | None = None,
    broad_screen_rescue_three_bead_candidates: dict[str, Any] | None = None,
    broad_screen_retry_handoff_summary: dict[str, Any] | None = None,
    broad_screen_selected_allatom_visual_bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trs = _summary(terminal_review)
    mqs = _summary(master_queue)
    ebs = _summary(export_bundle)
    obs = _summary(outbound_board)
    ps = _summary(portfolio)
    bs = _summary(blueprint)
    bsqs = _summary(broad_screen_queue)
    bsbs = _summary(broad_screen_bridge)
    bscus = _summary(broad_screen_compound_universe)
    bseqs = _summary(broad_screen_execution_queue)
    bsrafs = _summary(broad_screen_repurposing_autofill)
    bstrs = _summary(broad_screen_target_rerank)
    bssts = _summary(broad_screen_stability_score)
    bsats = _summary(broad_screen_antitarget_queue)
    bsaeqs = _summary(broad_screen_antitarget_execution_queue)
    bsaas = _summary(broad_screen_actual_append)
    bdgts = _summary(broad_screen_dengue_stage6_tuning_surface)
    bdgrs = _summary(broad_screen_dengue_exploratory_retry_lane)
    bslts = _summary(broad_screen_lbdhodh_stage6_tuning_surface)
    bsldrs = _summary(broad_screen_lbdhodh_exploratory_retry_lane)
    bslvrs = _summary(broad_screen_lbdhodh_gate51_validation_review_surface)
    bdr1 = _summary(broad_screen_dpre1_branch_review_surface)
    bskrs1 = _summary(broad_screen_tcruzi_krs1_branch_review_surface)
    bstrrs = _summary(broad_screen_tcruzi_pde_rescue_review_surface)
    bstprp = _summary(broad_screen_tcruzi_pde_promoted_top4_review_packet)
    bstrob = _summary(broad_screen_tcruzi_pde_rescue_only_branch_summary)
    bstropp = _summary(broad_screen_tcruzi_pde_rescue_operator_packet)
    bsrbt = _summary(broad_screen_rescue_only_branch_templates)
    bstrpts = _summary(broad_screen_target_retry_policy_templates)
    bsmfrpts = _summary(broad_screen_mapping_fix_retry_policy_templates)
    bsstrpts = _stage6_retry_template_summary(broad_screen_target_retry_policy_templates)
    bshrls = _summary(broad_screen_hard_target_rescue_lane)
    bsresas = _summary(broad_screen_rescue_anchor_artifacts)
    bsr3bs = _summary(broad_screen_rescue_three_bead_candidates)
    bsrhs = _summary(broad_screen_retry_handoff_summary)
    selected_allatom_visual = resolve_selected_allatom_visual_bundle(
        broad_screen_selected_allatom_visual_bundle
    )
    selected_allatom_visual_fields = selected_allatom_visual_surface_fields(
        selected_allatom_visual
    )
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
    promoted_top4_ready_for_operator_review = _resolve_bool(
        bstprp.get("packet_ready_for_operator_review"),
        bstprp.get("packet_ready"),
        _text(bstprp.get("status")) == "wetlab_tcruzi_pde_promoted_top4_review_packet_ready",
        default=False,
    )
    promoted_top4_final_gate_pass = _resolve_bool(
        bstprp.get("wetlab_final_gate_pass"),
        bstprp.get("wetlab_gate_pass"),
        bstprp.get("packet_ready"),
        default=promoted_top4_ready_for_operator_review,
    )
    promoted_top4_claim_gate_available = _resolve_bool(
        bstprp.get("claim_gate_available"),
        default=False,
    )
    promoted_top4_claim_ready_for_allatom = _resolve_bool(
        bstprp.get("claim_ready_for_allatom"),
        default=False,
    )
    rescue_only_review_packet_ready_for_operator_review = _resolve_bool(
        bstrob.get("review_packet_ready_for_operator_review"),
        bstrob.get("packet_ready_for_operator_review"),
        bstrob.get("review_packet_ready"),
        bstrob.get("promoted_top4_packet_ready"),
        promoted_top4_ready_for_operator_review,
        default=promoted_top4_ready_for_operator_review,
    )
    rescue_only_review_packet_final_gate_pass = _resolve_bool(
        bstrob.get("review_packet_final_gate_pass"),
        bstrob.get("wetlab_final_gate_pass"),
        bstrob.get("review_packet_wetlab_gate_pass"),
        bstrob.get("wetlab_gate_pass"),
        bstrob.get("review_packet_ready"),
        bstrob.get("promoted_top4_packet_ready"),
        promoted_top4_final_gate_pass,
        default=promoted_top4_final_gate_pass,
    )
    rescue_only_review_packet_claim_gate_available = _resolve_bool(
        bstrob.get("review_packet_claim_gate_available"),
        bstrob.get("claim_gate_available"),
        promoted_top4_claim_gate_available,
        default=promoted_top4_claim_gate_available,
    )
    rescue_only_review_packet_claim_ready_for_allatom = _resolve_bool(
        bstrob.get("review_packet_claim_ready_for_allatom"),
        bstrob.get("claim_ready_for_allatom"),
        promoted_top4_claim_ready_for_allatom,
        default=promoted_top4_claim_ready_for_allatom,
    )
    rescue_only_branch_ready_for_final_wetlab = _resolve_bool(
        bstrob.get("branch_ready_for_final_wetlab"),
        bool(bstrob.get("branch_to_rescue_only", False)) and rescue_only_review_packet_final_gate_pass,
        default=bool(bstrob.get("branch_to_rescue_only", False)) and rescue_only_review_packet_final_gate_pass,
    )
    rescue_operator_packet_ready_for_operator_review = _resolve_bool(
        bstropp.get("packet_ready_for_operator_review"),
        bstropp.get("packet_ready"),
        _text(bstropp.get("status")) == "wetlab_tcruzi_pde_rescue_operator_packet_ready",
        default=False,
    )
    rescue_operator_packet_final_gate_pass = _resolve_bool(
        bstropp.get("wetlab_final_gate_pass"),
        bstropp.get("wetlab_gate_pass"),
        bstropp.get("packet_ready"),
        default=rescue_operator_packet_ready_for_operator_review,
    )
    rescue_operator_packet_claim_gate_available = _resolve_bool(
        bstropp.get("claim_gate_available"),
        default=False,
    )
    rescue_operator_packet_claim_ready_for_allatom = _resolve_bool(
        bstropp.get("claim_ready_for_allatom"),
        default=False,
    )
    rescue_operator_packet_partner_send_gate_pass = _resolve_bool(
        bstropp.get("partner_send_gate_pass"),
        rescue_operator_packet_final_gate_pass,
        default=rescue_operator_packet_final_gate_pass,
    )
    selected_allatom_focus_available = bool(
        _text(
            bsrhs.get("selected_allatom_target_id", ""),
            bsrhs.get("selected_allatom_surface_label", ""),
        )
    )
    (
        selected_allatom_operator_review_reported,
        selected_allatom_operator_review_ready,
    ) = _resolve_optional_bool(
        bsrhs,
        "selected_allatom_packet_ready_for_operator_review",
        "selected_allatom_operator_review_ready",
        "selected_allatom_packet_ready",
    )
    (
        selected_allatom_wetlab_gate_reported,
        selected_allatom_wetlab_gate_pass,
    ) = _resolve_optional_bool(
        bsrhs,
        "selected_allatom_wetlab_gate_pass",
        "selected_allatom_gate_pass",
    )
    (
        selected_allatom_final_gate_reported,
        selected_allatom_final_gate_pass,
    ) = _resolve_optional_bool(
        bsrhs,
        "selected_allatom_wetlab_final_gate_pass",
        "selected_allatom_final_gate_pass",
    )
    (
        selected_allatom_claim_gate_reported,
        selected_allatom_claim_gate_available,
    ) = _resolve_optional_bool(
        bsrhs,
        "selected_allatom_claim_gate_available",
    )
    (
        selected_allatom_claim_ready_reported,
        selected_allatom_claim_ready_for_allatom,
    ) = _resolve_optional_bool(
        bsrhs,
        "selected_allatom_claim_ready_for_allatom",
    )
    selected_allatom_target_id = str(bsrhs.get("selected_allatom_target_id", "")).strip()
    selected_allatom_surface_label = str(bsrhs.get("selected_allatom_surface_label", "")).strip()
    selected_allatom_selected_command_kind = str(bsrhs.get("selected_allatom_selected_command_kind", "")).strip()
    selected_allatom_selected_threshold_A = float(bsrhs.get("selected_allatom_selected_threshold_A", 0.0) or 0.0)
    selected_allatom_packet_scope = str(bsrhs.get("selected_allatom_packet_scope", "")).strip()
    selected_allatom_best_compound_name = str(bsrhs.get("selected_allatom_best_compound_name", "")).strip()
    selected_allatom_best_compound_name_human_readable = str(
        bsrhs.get("selected_allatom_best_compound_name_human_readable", "")
    ).strip()
    selected_allatom_best_compound_name_resolution = str(
        bsrhs.get("selected_allatom_best_compound_name_resolution", "unresolved")
    ).strip()
    selected_allatom_best_mean_min_distance_A = float(
        bsrhs.get("selected_allatom_best_mean_min_distance_A", 0.0) or 0.0
    )
    selected_allatom_metric_source = (
        "retry_handoff_summary.selected_allatom_best_mean_min_distance_A"
        if _has_value(bsrhs, "selected_allatom_best_mean_min_distance_A")
        else ""
    )
    selected_allatom_promoted_candidate_count = int(
        bsrhs.get("selected_allatom_promoted_candidate_count", 0) or 0
    )
    selected_allatom_under_2p5_candidate_count = int(
        bsrhs.get("selected_allatom_under_2p5_candidate_count", 0) or 0
    )
    selected_allatom_near_candidate_count = int(
        bsrhs.get("selected_allatom_near_candidate_count", 0) or 0
    )
    selected_allatom_next_required_step = str(bsrhs.get("selected_allatom_next_required_step", "")).strip()
    selected_allatom_review_packet_summary = _selected_allatom_review_packet_summary(selected_allatom_surface_label)
    if _has_value(selected_allatom_review_packet_summary, "promoted_candidate_count"):
        selected_allatom_promoted_candidate_count = _safe_int(
            selected_allatom_review_packet_summary.get("promoted_candidate_count"),
            selected_allatom_promoted_candidate_count,
        )
    if _has_value(selected_allatom_review_packet_summary, "under_2p5_candidate_count"):
        selected_allatom_under_2p5_candidate_count = _safe_int(
            selected_allatom_review_packet_summary.get("under_2p5_candidate_count"),
            selected_allatom_under_2p5_candidate_count,
        )
    if _has_value(selected_allatom_review_packet_summary, "near_candidate_count"):
        selected_allatom_near_candidate_count = _safe_int(
            selected_allatom_review_packet_summary.get("near_candidate_count"),
            selected_allatom_near_candidate_count,
        )
    if _has_value(selected_allatom_review_packet_summary, "wetlab_gate_pass"):
        selected_allatom_wetlab_gate_reported = True
        selected_allatom_wetlab_gate_pass = _resolve_bool(
            selected_allatom_review_packet_summary.get("wetlab_gate_pass"),
            default=selected_allatom_wetlab_gate_pass,
        )
    if _has_value(selected_allatom_review_packet_summary, "wetlab_final_gate_pass"):
        selected_allatom_final_gate_reported = True
        selected_allatom_final_gate_pass = _resolve_bool(
            selected_allatom_review_packet_summary.get("wetlab_final_gate_pass"),
            default=selected_allatom_final_gate_pass,
        )
    if _has_value(selected_allatom_review_packet_summary, "claim_gate_available"):
        selected_allatom_claim_gate_reported = True
        selected_allatom_claim_gate_available = _resolve_bool(
            selected_allatom_review_packet_summary.get("claim_gate_available"),
            default=selected_allatom_claim_gate_available,
        )
    if _has_value(selected_allatom_review_packet_summary, "claim_ready_for_allatom"):
        selected_allatom_claim_ready_reported = True
        selected_allatom_claim_ready_for_allatom = _resolve_bool(
            selected_allatom_review_packet_summary.get("claim_ready_for_allatom"),
            default=selected_allatom_claim_ready_for_allatom,
        )
    selected_allatom_pose_validation = build_pose_validation_fields_from_summary(
        selected_allatom_review_packet_summary
    )
    selected_allatom_pose_validation_reported = _resolve_bool(
        bsrhs.get("selected_allatom_pose_validation_reported"),
        selected_allatom_pose_validation.get("pose_validation_reported"),
        default=False,
    )
    selected_allatom_pose_validation_version = _text(
        bsrhs.get("selected_allatom_pose_validation_version", ""),
        selected_allatom_pose_validation.get("pose_validation_version", ""),
    )
    selected_allatom_pose_validation_source = _text(
        bsrhs.get("selected_allatom_pose_validation_source", ""),
        selected_allatom_surface_label if selected_allatom_pose_validation_reported else "",
    )
    selected_allatom_pose_validation_status = _text(
        bsrhs.get("selected_allatom_pose_validation_status", ""),
        selected_allatom_pose_validation.get("pose_validation_status", ""),
    )
    selected_allatom_pose_validation_soft_status = _text(
        bsrhs.get("selected_allatom_pose_validation_soft_status", ""),
        selected_allatom_pose_validation.get("pose_validation_soft_status", ""),
    )
    selected_allatom_pose_validation_score = _resolve_float(
        bsrhs.get("selected_allatom_pose_validation_score"),
        selected_allatom_pose_validation.get("pose_validation_score"),
        default=0.0,
    )
    selected_allatom_pose_validation_pass = _resolve_bool(
        bsrhs.get("selected_allatom_pose_validation_pass"),
        selected_allatom_pose_validation.get("pose_validation_pass"),
        default=False,
    )
    selected_allatom_pose_validation_pose_preservation_rmsd_A = _safe_float(
        bsrhs.get("selected_allatom_pose_validation_pose_preservation_rmsd_A")
        if _has_value(bsrhs, "selected_allatom_pose_validation_pose_preservation_rmsd_A")
        else selected_allatom_pose_validation.get("pose_validation_pose_preservation_rmsd_A")
    )
    selected_allatom_pose_validation_backmapping_consistency_score = _safe_float(
        bsrhs.get("selected_allatom_pose_validation_backmapping_consistency_score")
        if _has_value(bsrhs, "selected_allatom_pose_validation_backmapping_consistency_score")
        else selected_allatom_pose_validation.get("pose_validation_backmapping_consistency_score")
    )
    selected_allatom_pose_validation_thresholds = dict(
        bsrhs.get("selected_allatom_pose_validation_thresholds", "")
        if isinstance(bsrhs.get("selected_allatom_pose_validation_thresholds"), dict)
        else selected_allatom_pose_validation.get("pose_validation_thresholds", {})
        or {}
    )
    selected_allatom_pose_validation_failed_checks = (
        _safe_str_list(bsrhs.get("selected_allatom_pose_validation_failed_checks"))
        or _safe_str_list(selected_allatom_pose_validation.get("pose_validation_failed_checks"))
    )
    selected_allatom_pose_validation_missing_checks = (
        _safe_str_list(bsrhs.get("selected_allatom_pose_validation_missing_checks"))
        or _safe_str_list(selected_allatom_pose_validation.get("pose_validation_missing_checks"))
    )
    selected_allatom_pose_validation_passed_checks = (
        _safe_str_list(bsrhs.get("selected_allatom_pose_validation_passed_checks"))
        or _safe_str_list(selected_allatom_pose_validation.get("pose_validation_passed_checks"))
    )
    selected_allatom_pose_validation_action_codes = (
        _safe_str_list(bsrhs.get("selected_allatom_pose_validation_action_codes"))
        or _safe_str_list(selected_allatom_pose_validation.get("pose_validation_action_codes"))
    )
    selected_allatom_pose_validation_blocker_codes = (
        _safe_str_list(bsrhs.get("selected_allatom_pose_validation_blocker_codes"))
        or _safe_str_list(selected_allatom_pose_validation.get("pose_validation_blocker_codes"))
    )
    selected_allatom_pose_validation_reason = _text(
        bsrhs.get("selected_allatom_pose_validation_reason", ""),
        selected_allatom_pose_validation.get("pose_validation_reason", ""),
    )
    selected_allatom_commercial_schema_version = _text(
        selected_allatom_review_packet_summary.get("commercial_schema_version", ""),
        bsrhs.get("selected_allatom_commercial_schema_version", ""),
    )
    selected_allatom_commercial_reported = any(
        _has_value(summary, key)
        for summary, key in (
            (bsrhs, "selected_allatom_commercial_schema_version"),
            (bsrhs, "selected_allatom_commercial_overall_score_v1"),
            (bsrhs, "selected_allatom_commercial_risk_bucket_v1"),
            (bsrhs, "selected_allatom_commercial_decision_class_v1"),
            (selected_allatom_review_packet_summary, "commercial_schema_version"),
            (selected_allatom_review_packet_summary, "commercial_overall_score_v1"),
            (selected_allatom_review_packet_summary, "commercial_risk_bucket_v1"),
            (selected_allatom_review_packet_summary, "commercial_decision_class_v1"),
        )
    )
    selected_allatom_commercial_hard_gate_reported = any(
        _has_value(summary, key)
        for summary, key in (
            (bsrhs, "selected_allatom_commercial_hard_gate_pass_v1"),
            (selected_allatom_review_packet_summary, "commercial_hard_gate_pass_v1"),
        )
    )
    selected_allatom_commercial_hard_gate_pass_v1 = _resolve_bool(
        selected_allatom_review_packet_summary.get("commercial_hard_gate_pass_v1"),
        bsrhs.get("selected_allatom_commercial_hard_gate_pass_v1"),
        default=False,
    )
    selected_allatom_commercial_overall_score_v1 = _resolve_float(
        selected_allatom_review_packet_summary.get("commercial_overall_score_v1"),
        bsrhs.get("selected_allatom_commercial_overall_score_v1"),
        default=0.0,
    )
    selected_allatom_commercial_risk_bucket_v1 = _text(
        selected_allatom_review_packet_summary.get("commercial_risk_bucket_v1", ""),
        bsrhs.get("selected_allatom_commercial_risk_bucket_v1", ""),
    )
    selected_allatom_commercial_decision_class_v1 = _text(
        selected_allatom_review_packet_summary.get("commercial_decision_class_v1", ""),
        bsrhs.get("selected_allatom_commercial_decision_class_v1", ""),
    )
    selected_allatom_commercial_primary_upgrade_actions_v1 = (
        _safe_str_list(selected_allatom_review_packet_summary.get("commercial_primary_upgrade_actions_v1"))
        or _safe_str_list(bsrhs.get("selected_allatom_commercial_primary_upgrade_actions_v1"))
    )
    selected_allatom_commercial_schema_version_v2 = _text(
        selected_allatom_review_packet_summary.get("commercial_schema_version_v2", ""),
        bsrhs.get("selected_allatom_commercial_schema_version_v2", ""),
    )
    selected_allatom_commercial_reported_v2 = any(
        _has_value(summary, key)
        for summary, key in (
            (bsrhs, "selected_allatom_commercial_schema_version_v2"),
            (bsrhs, "selected_allatom_commercial_overall_score_v2"),
            (bsrhs, "selected_allatom_commercial_risk_bucket_v2"),
            (bsrhs, "selected_allatom_commercial_decision_class_v2"),
            (bsrhs, "selected_allatom_commercial_human_summary_v2"),
            (selected_allatom_review_packet_summary, "commercial_schema_version_v2"),
            (selected_allatom_review_packet_summary, "commercial_overall_score_v2"),
            (selected_allatom_review_packet_summary, "commercial_risk_bucket_v2"),
            (selected_allatom_review_packet_summary, "commercial_decision_class_v2"),
            (selected_allatom_review_packet_summary, "commercial_human_summary_v2"),
        )
    )
    selected_allatom_commercial_hard_gate_reported_v2 = any(
        _has_value(summary, key)
        for summary, key in (
            (bsrhs, "selected_allatom_commercial_hard_gate_pass_v2"),
            (selected_allatom_review_packet_summary, "commercial_hard_gate_pass_v2"),
        )
    )
    selected_allatom_commercial_hard_gate_pass_v2 = _resolve_bool(
        selected_allatom_review_packet_summary.get("commercial_hard_gate_pass_v2"),
        bsrhs.get("selected_allatom_commercial_hard_gate_pass_v2"),
        default=False,
    )
    selected_allatom_commercial_soft_score_v2 = _resolve_float(
        selected_allatom_review_packet_summary.get("commercial_soft_score_v2"),
        bsrhs.get("selected_allatom_commercial_soft_score_v2"),
        default=0.0,
    )
    selected_allatom_commercial_confidence_score_v2 = _resolve_float(
        selected_allatom_review_packet_summary.get("commercial_confidence_score_v2"),
        bsrhs.get("selected_allatom_commercial_confidence_score_v2"),
        default=0.0,
    )
    selected_allatom_commercial_overall_score_v2 = _resolve_float(
        selected_allatom_review_packet_summary.get("commercial_overall_score_v2"),
        bsrhs.get("selected_allatom_commercial_overall_score_v2"),
        default=0.0,
    )
    selected_allatom_commercial_risk_bucket_v2 = _text(
        selected_allatom_review_packet_summary.get("commercial_risk_bucket_v2", ""),
        bsrhs.get("selected_allatom_commercial_risk_bucket_v2", ""),
    )
    selected_allatom_commercial_decision_class_v2 = _text(
        selected_allatom_review_packet_summary.get("commercial_decision_class_v2", ""),
        bsrhs.get("selected_allatom_commercial_decision_class_v2", ""),
    )
    selected_allatom_commercial_primary_upgrade_actions_v2 = (
        _safe_str_list(selected_allatom_review_packet_summary.get("commercial_primary_upgrade_actions_v2"))
        or _safe_str_list(bsrhs.get("selected_allatom_commercial_primary_upgrade_actions_v2"))
    )
    selected_allatom_commercial_human_summary_v2 = _text(
        selected_allatom_review_packet_summary.get("commercial_human_summary_v2", ""),
        bsrhs.get("selected_allatom_commercial_human_summary_v2", ""),
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
            (selected_allatom_review_packet_summary, "translation_gate_version"),
            (selected_allatom_review_packet_summary, "translation_gate_focus_status"),
            (selected_allatom_review_packet_summary, "translation_gate_focus_score"),
            (selected_allatom_review_packet_summary, "translation_gate_focus_reason"),
            (selected_allatom_review_packet_summary, "focus_shortlist_tier"),
            (selected_allatom_review_packet_summary, "recommended_next_expensive_lane"),
            (selected_allatom_review_packet_summary, "recommended_next_expensive_lane_reason"),
        )
    )
    selected_allatom_translation_gate_version = _text(
        selected_allatom_review_packet_summary.get("translation_gate_version", ""),
        bsrhs.get("selected_allatom_translation_gate_version", ""),
    )
    selected_allatom_translation_gate_focus_status = _text(
        selected_allatom_review_packet_summary.get("translation_gate_focus_status", ""),
        bsrhs.get("selected_allatom_translation_gate_focus_status", ""),
    )
    selected_allatom_translation_gate_focus_score = _resolve_float(
        selected_allatom_review_packet_summary.get("translation_gate_focus_score"),
        bsrhs.get("selected_allatom_translation_gate_focus_score"),
        default=0.0,
    )
    selected_allatom_translation_gate_focus_reason = _text(
        selected_allatom_review_packet_summary.get("translation_gate_focus_reason", ""),
        bsrhs.get("selected_allatom_translation_gate_focus_reason", ""),
    )
    selected_allatom_focus_shortlist_tier = _text(
        selected_allatom_review_packet_summary.get("focus_shortlist_tier", ""),
        bsrhs.get("selected_allatom_focus_shortlist_tier", ""),
    )
    selected_allatom_recommended_next_expensive_lane = _text(
        selected_allatom_review_packet_summary.get("recommended_next_expensive_lane", ""),
        bsrhs.get("selected_allatom_recommended_next_expensive_lane", ""),
    )
    selected_allatom_recommended_next_expensive_lane_reason = _text(
        selected_allatom_review_packet_summary.get("recommended_next_expensive_lane_reason", ""),
        bsrhs.get("selected_allatom_recommended_next_expensive_lane_reason", ""),
    )
    selected_allatom_translation_provenance_mode = (
        "source_driven" if selected_allatom_translation_reported else "not_reported"
    )
    if not selected_allatom_translation_reported:
        translation_fallback = _infer_selected_allatom_translation_shortlist_fallback(
            selected_allatom_next_required_step,
            selected_allatom_review_packet_summary.get("next_required_step", ""),
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
    selected_allatom_raw_claim_requirement_mode = _infer_raw_claim_requirement_mode(
        selected_allatom_target_id,
        _text(
        bsrhs.get("selected_allatom_raw_claim_requirement_mode", ""),
        bsrhs.get("selected_allatom_claim_requirement_mode", ""),
        selected_allatom_review_packet_summary.get("claim_gate_requirement_mode", ""),
        selected_allatom_review_packet_summary.get("selected_allatom_claim_requirement_mode", ""),
        "semi_hard" if selected_allatom_claim_gate_reported and selected_allatom_claim_gate_available else "",
        ),
        selected_allatom_claim_gate_reported,
    )
    selected_allatom_raw_claim_requirement_provenance = _text(
        bsrhs.get("selected_allatom_raw_claim_requirement_provenance", ""),
        bsrhs.get("selected_allatom_claim_requirement_provenance", ""),
        selected_allatom_review_packet_summary.get("claim_gate_requirement_provenance", ""),
        selected_allatom_review_packet_summary.get("selected_allatom_claim_requirement_provenance", ""),
        "target_group_default" if selected_allatom_raw_claim_requirement_mode == "semi_hard" else "",
        "inferred_from_claim_gate_availability" if selected_allatom_raw_claim_requirement_mode else "",
    )
    selected_allatom_raw_claim_required_for_final_wetlab = _resolve_bool(
        bsrhs.get("selected_allatom_raw_claim_required_for_final_wetlab"),
        bsrhs.get("selected_allatom_claim_required_for_final_wetlab"),
        selected_allatom_review_packet_summary.get("claim_gate_required_for_final_wetlab"),
        selected_allatom_review_packet_summary.get("selected_allatom_claim_required_for_final_wetlab"),
        default=selected_allatom_raw_claim_requirement_mode == "semi_hard",
    )
    selected_allatom_raw_claim_required_for_commercial_readiness = _resolve_bool(
        bsrhs.get("selected_allatom_raw_claim_required_for_commercial_readiness"),
        bsrhs.get("selected_allatom_claim_required_for_commercial_readiness"),
        selected_allatom_review_packet_summary.get("claim_gate_required_for_commercial_readiness"),
        selected_allatom_review_packet_summary.get("selected_allatom_claim_required_for_commercial_readiness"),
        default=selected_allatom_raw_claim_requirement_mode == "semi_hard",
    )
    selected_allatom_raw_claim_requirement_reason = _text(
        bsrhs.get("selected_allatom_raw_claim_requirement_reason", ""),
        bsrhs.get("selected_allatom_claim_requirement_reason", ""),
        selected_allatom_review_packet_summary.get("claim_gate_requirement_reason", ""),
        selected_allatom_review_packet_summary.get("selected_allatom_claim_requirement_reason", ""),
        (
            f"{selected_allatom_target_id} is in the neglected_disease_priority_v1 target group, so final wetlab advancement expects claim/equivalence evidence before release."
            if selected_allatom_raw_claim_requirement_mode == "semi_hard"
            else ""
        ),
        "claim/equivalence gate is not reported for this selected all-atom focus"
        if selected_allatom_raw_claim_requirement_mode == "not_applicable"
        else "",
    )
    selected_allatom_raw_claim_requirement_actions = (
        _safe_str_list(bsrhs.get("selected_allatom_raw_claim_requirement_actions"))
        or _safe_str_list(bsrhs.get("selected_allatom_claim_requirement_actions"))
        or _safe_str_list(selected_allatom_review_packet_summary.get("claim_gate_requirement_actions"))
        or _safe_str_list(selected_allatom_review_packet_summary.get("selected_allatom_claim_requirement_actions"))
    )
    selected_allatom_effective_actionability_status = _text(
        bsrhs.get("selected_allatom_effective_actionability_status", ""),
        bsrhs.get("selected_allatom_actionability_status", ""),
    )
    selected_allatom_effective_actionability_claim_requirement_mode = _text(
        bsrhs.get("selected_allatom_effective_actionability_claim_requirement_mode", ""),
        bsrhs.get("selected_allatom_actionability_claim_requirement_mode", ""),
    )
    selected_allatom_effective_actionability_claim_requirement_status = _text(
        bsrhs.get("selected_allatom_effective_actionability_claim_requirement_status", ""),
        bsrhs.get("selected_allatom_actionability_claim_requirement_status", ""),
    )
    selected_allatom_effective_actionability_claim_requirement_reason = _text(
        bsrhs.get("selected_allatom_effective_actionability_claim_requirement_reason", ""),
        bsrhs.get("selected_allatom_actionability_claim_requirement_reason", ""),
    )
    commercial_hard_block_present = bool(
        (selected_allatom_commercial_hard_gate_reported and not selected_allatom_commercial_hard_gate_pass_v1)
        or (selected_allatom_commercial_hard_gate_reported_v2 and not selected_allatom_commercial_hard_gate_pass_v2)
        or selected_allatom_translation_gate_focus_status in {"fail", "blocked"}
    )
    if not selected_allatom_effective_actionability_status:
        if selected_allatom_final_gate_pass:
            selected_allatom_effective_actionability_status = "ready"
        elif commercial_hard_block_present:
            selected_allatom_effective_actionability_status = "hard_blocked"
        elif (
            selected_allatom_raw_claim_requirement_mode == "semi_hard"
            and not selected_allatom_claim_ready_for_allatom
        ):
            selected_allatom_effective_actionability_status = "semi_hard_blocked"
        elif selected_allatom_recommended_next_expensive_lane or selected_allatom_focus_shortlist_tier:
            selected_allatom_effective_actionability_status = "soft_guided"
        else:
            selected_allatom_effective_actionability_status = "blocked"
    if not selected_allatom_effective_actionability_claim_requirement_mode:
        if selected_allatom_effective_actionability_status == "semi_hard_blocked":
            selected_allatom_effective_actionability_claim_requirement_mode = (
                selected_allatom_raw_claim_requirement_mode or "semi_hard"
            )
        else:
            selected_allatom_effective_actionability_claim_requirement_mode = "not_applicable"
    if not selected_allatom_effective_actionability_claim_requirement_status:
        if selected_allatom_effective_actionability_claim_requirement_mode == "semi_hard":
            selected_allatom_effective_actionability_claim_requirement_status = (
                "satisfied" if selected_allatom_claim_ready_for_allatom else "blocked"
            )
        else:
            selected_allatom_effective_actionability_claim_requirement_status = "not_applicable"
    if not selected_allatom_effective_actionability_claim_requirement_reason:
        if selected_allatom_effective_actionability_claim_requirement_mode == "semi_hard":
            selected_allatom_effective_actionability_claim_requirement_reason = _text(
                selected_allatom_raw_claim_requirement_reason,
                "claim/equivalence gate remains the effective blocker for this focus",
            )
        elif selected_allatom_effective_actionability_status == "hard_blocked":
            selected_allatom_effective_actionability_claim_requirement_reason = (
                "hard gate blocks this focus before claim/equivalence becomes the effective blocker"
            )
        else:
            selected_allatom_effective_actionability_claim_requirement_reason = (
                "claim/equivalence gate is not the effective blocker right now"
            )
    selected_allatom_effective_blocking_order = _selected_allatom_effective_blocking_order(
        effective_status=selected_allatom_effective_actionability_status,
        raw_claim_requirement_mode=selected_allatom_raw_claim_requirement_mode,
        effective_claim_requirement_mode=selected_allatom_effective_actionability_claim_requirement_mode,
    )
    selected_allatom_effective_primary_blocking_domain = _selected_allatom_effective_primary_blocking_domain(
        effective_status=selected_allatom_effective_actionability_status,
        translation_status=selected_allatom_translation_gate_focus_status,
        commercial_hard_gate_reported=bool(
            selected_allatom_commercial_hard_gate_reported or selected_allatom_commercial_hard_gate_reported_v2
        ),
        commercial_hard_gate_pass=bool(
            (selected_allatom_commercial_hard_gate_pass_v2 if selected_allatom_commercial_hard_gate_reported_v2 else True)
            and (selected_allatom_commercial_hard_gate_pass_v1 if selected_allatom_commercial_hard_gate_reported else True)
        ),
        effective_claim_requirement_mode=selected_allatom_effective_actionability_claim_requirement_mode,
    )
    selected_allatom_action_recipe = _selected_allatom_action_recipe(
        translation_status=selected_allatom_translation_gate_focus_status,
        translation_failed_checks=_safe_str_list(
            selected_allatom_review_packet_summary.get("translation_gate_focus_failed_checks")
        ),
        translation_warning_checks=_safe_str_list(
            selected_allatom_review_packet_summary.get("translation_gate_focus_warning_checks")
        ),
        raw_claim_requirement_mode=selected_allatom_raw_claim_requirement_mode,
        raw_claim_requirement_reason=selected_allatom_raw_claim_requirement_reason,
        raw_claim_requirement_actions=selected_allatom_raw_claim_requirement_actions,
        claim_ready_for_allatom=selected_allatom_claim_ready_for_allatom,
        recommended_next_expensive_lane=selected_allatom_recommended_next_expensive_lane,
        recommended_next_expensive_lane_reason=selected_allatom_recommended_next_expensive_lane_reason,
    )
    fallback_selected_allatom_canonical = {
        "commercial_schema_version_v2": selected_allatom_commercial_schema_version_v2,
        "commercial_overall_score_v2": selected_allatom_commercial_overall_score_v2,
        "commercial_risk_bucket_v2": selected_allatom_commercial_risk_bucket_v2,
        "commercial_decision_class_v2": selected_allatom_commercial_decision_class_v2,
        "commercial_primary_upgrade_actions_v2": list(selected_allatom_commercial_primary_upgrade_actions_v2),
        "translation_gate_version": selected_allatom_translation_gate_version,
        "translation_gate_focus_status": selected_allatom_translation_gate_focus_status,
        "translation_gate_focus_score": selected_allatom_translation_gate_focus_score,
        "translation_gate_focus_reason": selected_allatom_translation_gate_focus_reason,
        "focus_shortlist_tier": selected_allatom_focus_shortlist_tier,
        "recommended_next_expensive_lane": selected_allatom_recommended_next_expensive_lane,
        "recommended_next_expensive_lane_reason": selected_allatom_recommended_next_expensive_lane_reason,
        "raw_claim_requirement_mode": selected_allatom_raw_claim_requirement_mode,
        "raw_claim_requirement_provenance": selected_allatom_raw_claim_requirement_provenance,
        "raw_claim_required_for_final_wetlab": selected_allatom_raw_claim_required_for_final_wetlab,
        "raw_claim_required_for_commercial_readiness": selected_allatom_raw_claim_required_for_commercial_readiness,
        "raw_claim_requirement_reason": selected_allatom_raw_claim_requirement_reason,
        "effective_actionability_status": selected_allatom_effective_actionability_status,
        "effective_actionability_claim_requirement_mode": selected_allatom_effective_actionability_claim_requirement_mode,
        "effective_actionability_claim_requirement_status": selected_allatom_effective_actionability_claim_requirement_status,
        "effective_actionability_claim_requirement_reason": selected_allatom_effective_actionability_claim_requirement_reason,
        "effective_actionability_next_expensive_lane": selected_allatom_recommended_next_expensive_lane,
        "effective_actionability_next_expensive_lane_reason": selected_allatom_recommended_next_expensive_lane_reason,
        "effective_actionability_required_calculations": [
            row["code"]
            for row in selected_allatom_action_recipe["action_recipe_rows"]
            if row.get("priority") == "hard"
        ],
        "effective_actionability_action_list": list(selected_allatom_action_recipe["action_recipe_rows"]),
        "effective_blocking_order": selected_allatom_effective_blocking_order,
        "effective_primary_blocking_domain": selected_allatom_effective_primary_blocking_domain,
        "action_recipe_codes": list(selected_allatom_action_recipe["action_recipe_codes"]),
        "action_recipe_rows": list(selected_allatom_action_recipe["action_recipe_rows"]),
        "translation_provenance_mode": selected_allatom_translation_provenance_mode,
        "commercial_provenance_mode_v2": selected_allatom_commercial_provenance_mode_v2,
        "hybrid_policy": "canonical_scores_source_only__translation_shortlist_labeled_fallback",
    }
    selected_allatom_canonical = _resolve_selected_allatom_canonical_with_fallback(
        fallback=fallback_selected_allatom_canonical,
        review_packet_summary=selected_allatom_review_packet_summary,
        retry_handoff_summary=bsrhs,
        final_campaign_summary={},
        next_required_step=selected_allatom_next_required_step,
    )
    selected_allatom_canonical_resolver_used = bool(
        selected_allatom_canonical.get("__canonical_resolver_used__", False)
    )
    selected_allatom_commercial_schema_version_v2 = _text(
        selected_allatom_canonical.get("commercial_schema_version_v2", ""),
        selected_allatom_commercial_schema_version_v2,
    )
    selected_allatom_commercial_overall_score_v2 = _resolve_float(
        selected_allatom_canonical.get("commercial_overall_score_v2"),
        selected_allatom_commercial_overall_score_v2,
        default=0.0,
    )
    selected_allatom_commercial_risk_bucket_v2 = _text(
        selected_allatom_canonical.get("commercial_risk_bucket_v2", ""),
        selected_allatom_commercial_risk_bucket_v2,
    )
    selected_allatom_commercial_decision_class_v2 = _text(
        selected_allatom_canonical.get("commercial_decision_class_v2", ""),
        selected_allatom_commercial_decision_class_v2,
    )
    selected_allatom_commercial_primary_upgrade_actions_v2 = (
        _safe_str_list(selected_allatom_canonical.get("commercial_primary_upgrade_actions_v2"))
        or selected_allatom_commercial_primary_upgrade_actions_v2
    )
    selected_allatom_translation_gate_version = _text(
        selected_allatom_canonical.get("translation_gate_version", ""),
        selected_allatom_translation_gate_version,
    )
    selected_allatom_translation_gate_focus_status = _text(
        selected_allatom_canonical.get("translation_gate_focus_status", ""),
        selected_allatom_translation_gate_focus_status,
    )
    selected_allatom_translation_gate_focus_score = _resolve_float(
        selected_allatom_canonical.get("translation_gate_focus_score"),
        selected_allatom_translation_gate_focus_score,
        default=0.0,
    )
    selected_allatom_translation_gate_focus_reason = _text(
        selected_allatom_canonical.get("translation_gate_focus_reason", ""),
        selected_allatom_translation_gate_focus_reason,
    )
    selected_allatom_focus_shortlist_tier = _text(
        selected_allatom_canonical.get("focus_shortlist_tier", ""),
        selected_allatom_focus_shortlist_tier,
    )
    selected_allatom_recommended_next_expensive_lane = _text(
        selected_allatom_canonical.get("recommended_next_expensive_lane", ""),
        selected_allatom_recommended_next_expensive_lane,
    )
    selected_allatom_recommended_next_expensive_lane_reason = _text(
        selected_allatom_canonical.get("recommended_next_expensive_lane_reason", ""),
        selected_allatom_recommended_next_expensive_lane_reason,
    )
    selected_allatom_translation_provenance_mode = _text(
        selected_allatom_canonical.get("translation_provenance_mode", ""),
        selected_allatom_translation_provenance_mode,
    )
    selected_allatom_commercial_provenance_mode_v2 = _text(
        selected_allatom_canonical.get("commercial_provenance_mode_v2", ""),
        selected_allatom_commercial_provenance_mode_v2,
    )
    if not (
        selected_allatom_commercial_schema_version_v2
        or selected_allatom_commercial_overall_score_v2 > 0
        or selected_allatom_commercial_risk_bucket_v2
        or selected_allatom_commercial_decision_class_v2
        or selected_allatom_commercial_primary_upgrade_actions_v2
    ):
        selected_allatom_commercial_provenance_mode_v2 = "not_reported"
    selected_allatom_hybrid_policy = _text(
        selected_allatom_canonical.get("hybrid_policy", ""),
        "canonical_scores_source_only__translation_shortlist_labeled_fallback",
    )
    selected_allatom_next_required_step = selected_allatom_green_next_required_step(
        wetlab_gate_pass=selected_allatom_wetlab_gate_pass,
        final_gate_pass=selected_allatom_final_gate_pass,
        claim_ready_for_allatom=selected_allatom_claim_ready_for_allatom,
        translation_gate_focus_status=selected_allatom_translation_gate_focus_status,
        recommended_next_expensive_lane=selected_allatom_recommended_next_expensive_lane,
        fallback_next_required_step=selected_allatom_next_required_step,
    )
    canonical_best_mean_min_distance_A = _safe_float(
        selected_allatom_canonical.get("best_mean_min_distance_A")
    )
    if canonical_best_mean_min_distance_A is not None and canonical_best_mean_min_distance_A > 0.0:
        selected_allatom_best_mean_min_distance_A = canonical_best_mean_min_distance_A
        selected_allatom_metric_source = _text(
            selected_allatom_canonical.get("best_mean_min_distance_source", ""),
            selected_allatom_metric_source,
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
        _safe_str_list(selected_allatom_canonical.get("action_recipe_codes"))
        if selected_allatom_canonical_resolver_used
        else list(selected_allatom_action_recipe["action_recipe_codes"])
    )
    selected_allatom_action_recipe_rows = (
        list(selected_allatom_canonical.get("action_recipe_rows", []) or [])
        if selected_allatom_canonical_resolver_used
        else list(selected_allatom_action_recipe["action_recipe_rows"])
    )
    selected_allatom_canonical_action_recipe_rollup_text = " | ".join(
        f"{row.get('priority')}:{row.get('code')} -> {row.get('next_calculation')}"
        for row in selected_allatom_action_recipe_rows
        if row.get("priority") and row.get("code") and row.get("next_calculation")
    )
    selected_allatom_preferred_canonical_rollup = (
        "recompute_binding_energy_proxy" in selected_allatom_action_recipe_codes
    )
    selected_allatom_action_recipe_rollup_text = _text(
        selected_allatom_canonical.get("action_recipe_rollup_text", "")
        if selected_allatom_canonical_resolver_used and selected_allatom_preferred_canonical_rollup
        else "",
        selected_allatom_canonical_action_recipe_rollup_text
        if selected_allatom_canonical_resolver_used and selected_allatom_preferred_canonical_rollup
        else "",
        selected_allatom_action_recipe["action_recipe_rollup_text"],
    )
    selected_allatom_effective_actionability_required_calculations = (
        _safe_str_list(selected_allatom_canonical.get("effective_actionability_required_calculations"))
        if selected_allatom_canonical_resolver_used
        else list(selected_allatom_action_recipe["effective_actionability_required_calculations"])
    )
    selected_allatom_effective_actionability_action_list = (
        list(selected_allatom_canonical.get("effective_actionability_action_list", []) or [])
        if selected_allatom_canonical_resolver_used
        else list(selected_allatom_action_recipe["effective_actionability_action_list"])
    )
    selected_allatom_effective_actionability_required_calculations_text = ", ".join(
        selected_allatom_effective_actionability_required_calculations
    )
    selected_allatom_effective_actionability_action_list_text = " | ".join(
        f"{row.get('severity', 'soft')}:{row.get('action', row.get('code', 'review_action'))}[{row.get('status', 'pending')}]"
        + (f" lane={row.get('lane')}" if row.get("lane") else "")
        for row in selected_allatom_effective_actionability_action_list
        if isinstance(row, dict) and (row.get("action") or row.get("code"))
    )
    selected_allatom_actionability_human_summary = _text(
        bsrhs.get("selected_allatom_actionability_human_summary", ""),
        _text(
            selected_allatom_canonical.get("effective_actionability_reason", ""),
            selected_allatom_effective_actionability_claim_requirement_reason,
            selected_allatom_action_recipe_rollup_text,
        ),
    )
    selected_allatom_readiness_semantics = _normalize_selected_allatom_semantics(
        bsrhs.get("selected_allatom_readiness_semantics"),
        focus_available=selected_allatom_focus_available,
        final_gate_reported=selected_allatom_final_gate_reported,
    )
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
        pose_validation_reported=selected_allatom_pose_validation_reported,
        pose_validation_version=selected_allatom_pose_validation_version,
        pose_validation_status=selected_allatom_pose_validation_status,
        pose_validation_soft_status=selected_allatom_pose_validation_soft_status,
        pose_validation_score=selected_allatom_pose_validation_score
        if selected_allatom_pose_validation_reported
        else None,
        pose_validation_pass=selected_allatom_pose_validation_pass,
        pose_validation_pose_preservation_rmsd_A=selected_allatom_pose_validation_pose_preservation_rmsd_A,
        pose_validation_backmapping_consistency_score=selected_allatom_pose_validation_backmapping_consistency_score,
        pose_validation_reason=selected_allatom_pose_validation_reason,
    )

    rows: list[dict[str, Any]] = []
    master_rows = master_queue.get("rows", []) or []
    chain_targets: dict[str, list[str]] = {}
    for row in master_rows:
        chain_id = str(row.get("chain_id", "")).strip()
        target_id = str(row.get("target_id", "")).strip()
        if chain_id and target_id:
            chain_targets.setdefault(chain_id, []).append(target_id)

    for row in terminal_review.get("rows", []) or []:
        chain_id = str(row.get("chain_id", "")).strip()
        rows.append(
            {
                "chain_id": chain_id,
                "chain_rank": int(row.get("chain_rank", 0) or 0),
                "targets": "; ".join(chain_targets.get(chain_id, [])),
                "queue_target_count": int(row.get("queue_target_count", 0) or 0),
                "resolved_target_count": int(row.get("resolved_target_count", 0) or 0),
                "all_rows_resolved": bool(row.get("all_rows_resolved", False)),
                "terminal_state": str(row.get("terminal_state", "")).strip(),
            }
        )

    rows.sort(key=lambda row: (row["chain_rank"], row["chain_id"]))

    top_outbound_targets = "; ".join(
        str(row.get("target_id", "")).strip() for row in (outbound_board.get("rows", []) or [])[:5] if str(row.get("target_id", "")).strip()
    )

    return {
        "summary": {
            "status": "wetlab_final_campaign_summary_ready",
            "campaign_terminal_state": str(trs.get("campaign_terminal_state", "pending")).strip(),
            "chain_count": int(trs.get("chain_count", 0) or 0),
            "serialized_target_count": int(mqs.get("queue_target_count", 0) or 0),
            "serialized_resolved_target_count": int(mqs.get("resolved_target_count", 0) or 0),
            "outbound_track_count": int(ebs.get("track_count", 0) or 0),
            "ready_to_send_track_count": int(ebs.get("ready_to_send_count", 0) or 0),
            "portfolio_target_count": int(
                ps.get("total_target_count", 0)
                or ps.get("target_count", 0)
                or ps.get("portfolio_target_count", 0)
                or 0
            ),
            "wave1_target_count": int(bs.get("wave1_target_count", 0) or 0),
            "outbound_priority_target_count": int(
                obs.get("target_count", 0)
                or obs.get("priority_track_count", 0)
                or 0
            ),
            "broad_screen_queue_ready": bool(str(bsqs.get("status", "")).strip() == "wetlab_broad_screen_queue_ready"),
            "broad_screen_bridge_ready": bool(str(bsbs.get("status", "")).strip() == "wetlab_broad_screen_bridge_ready"),
            "broad_screen_library_size": int(bsqs.get("library_size", bsbs.get("library_size", 0)) or 0),
            "broad_screen_target_count": int(bsqs.get("target_count", 0) or 0),
            "broad_screen_total_queue_rows": int(bsqs.get("total_queue_rows", 0) or 0),
            "broad_screen_final_packet_shape": str(bsbs.get("final_packet_shape", "")).strip(),
            "broad_screen_compound_universe_ready": bool(
                str(bscus.get("status", "")).strip() == "wetlab_broad_screen_compound_universe_ready"
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
            "broad_screen_execution_queue_ready": bool(
                str(bseqs.get("status", "")).strip() == "wetlab_broad_screen_execution_queue_ready"
            ),
            "broad_screen_execution_ready_now_row_count": int(bseqs.get("ready_now_row_count", 0) or 0),
            "broad_screen_first_actionable_target_id": str(bseqs.get("first_actionable_target_id", "")).strip(),
            "broad_screen_first_actionable_shard_id": str(bseqs.get("first_actionable_shard_id", "")).strip(),
            "broad_screen_repurposing_autofill_ready": bool(
                str(bsrafs.get("status", "")).strip() == "wetlab_broad_screen_repurposing_autofill_ready"
            ),
            "broad_screen_override_target_count": int(bsrafs.get("override_target_count", 0) or 0),
            "broad_screen_target_rerank_ready": bool(
                str(bstrs.get("status", "")).strip() == "wetlab_broad_screen_target_rerank_ready"
            ),
            "broad_screen_full_bulk_ready_target_count": int(bstrs.get("full_bulk_ready_target_count", 0) or 0),
            "broad_screen_partial_actual_target_count": int(bstrs.get("partial_actual_target_count", 0) or 0),
            "broad_screen_stability_score_ready": bool(
                str(bssts.get("status", "")).strip() == "wetlab_broad_screen_stability_score_ready"
            ),
            "broad_screen_stable_target_count": int(
                bssts.get("stable_high_confidence_target_count", 0) or 0
            ) + int(bssts.get("stable_provisional_target_count", 0) or 0),
            "broad_screen_antitarget_queue_ready": bool(
                str(bsats.get("status", "")).strip() == "wetlab_broad_screen_antitarget_queue_ready"
            ),
            "broad_screen_antitarget_ready_now_row_count": int(bsats.get("ready_now_row_count", 0) or 0),
            "broad_screen_antitarget_running_row_count": int(bsaeqs.get("running_row_count", 0) or 0),
            "broad_screen_antitarget_first_actionable_primary_target_id": str(
                bsaeqs.get("first_actionable_primary_target_id", "")
            ).strip(),
            "broad_screen_antitarget_first_actionable_anti_target_id": str(
                bsaeqs.get("first_actionable_anti_target_id", "")
            ).strip(),
            "broad_screen_actual_append_ready": bool(
                str(bsaas.get("status", "")).strip().startswith("wetlab_broad_screen_actual_append_")
            ),
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
            "broad_screen_lbdhodh_gate51_validation_validated_command_kind": str(
                bslvrs.get("validated_command_kind", "")
            ).strip(),
            "broad_screen_lbdhodh_gate51_validation_validated_threshold_A": float(
                bslvrs.get("validated_threshold_A", 0.0) or 0.0
            ),
            "broad_screen_lbdhodh_gate51_validation_next_required_step": str(
                bslvrs.get("next_required_step", "")
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
            "selected_validated_target_id": str(bslvrs.get("target_id", "")).strip() if bool(bslvrs.get("gate51_validated", False)) else "",
            "selected_validated_surface_label": "gate5.1_validation_review" if bool(bslvrs.get("gate51_validated", False)) else "",
            "selected_validated_selected_command_kind": str(bslvrs.get("validated_command_kind", "")).strip() if bool(bslvrs.get("gate51_validated", False)) else "",
            "selected_validated_threshold_A": float(bslvrs.get("validated_threshold_A", 0.0) or 0.0) if bool(bslvrs.get("gate51_validated", False)) else 0.0,
            "selected_validated_next_required_step": str(bslvrs.get("next_required_step", "")).strip() if bool(bslvrs.get("gate51_validated", False)) else "",
            "selected_krs1_branch_review_target_id": str(
                bskrs1.get("target_id", "")
            ).strip(),
            "selected_krs1_branch_review_branch_label": str(
                bskrs1.get("branch_label", "")
            ).strip(),
            "selected_krs1_branch_review_branch_state": str(
                bskrs1.get("branch_state", "")
            ).strip(),
            "selected_krs1_branch_review_selected_command_kind": str(
                bskrs1.get("exploratory_retry_selected_command_kind", "")
            ).strip(),
            "selected_krs1_branch_review_selected_threshold_A": float(
                bskrs1.get("exploratory_retry_selected_threshold_A", 0.0) or 0.0
            ),
            "selected_krs1_branch_review_next_required_step": str(
                bskrs1.get("next_required_step", "")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_review_surface_ready": bool(
                str(bstrrs.get("status", "")).strip() == "wetlab_tcruzi_pde_rescue_review_surface_ready"
            ),
            "broad_screen_tcruzi_pde_rescue_review_target_id": str(bstrrs.get("target_id", "")).strip(),
            "broad_screen_tcruzi_pde_rescue_review_decision": str(bstrrs.get("decision", "")).strip(),
            "broad_screen_tcruzi_pde_rescue_review_default_lane_reopen_allowed": bool(
                bstrrs.get("default_lane_reopen_allowed", False)
            ),
            "broad_screen_tcruzi_pde_rescue_review_branch_to_rescue_only": bool(
                bstrrs.get("branch_to_rescue_only", False)
            ),
            "broad_screen_tcruzi_pde_rescue_review_promoted_candidate_count": int(
                bstrrs.get("promoted_candidate_count", 0) or 0
            ),
            "broad_screen_tcruzi_pde_rescue_review_under_2p5_candidate_count": int(
                bstrrs.get("under_2p5_candidate_count", 0) or 0
            ),
            "broad_screen_tcruzi_pde_rescue_review_selected_command_kind": str(
                bstrrs.get("selected_command_kind", "")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_review_selected_threshold_A": float(
                bstrrs.get("selected_threshold_A", 0.0) or 0.0
            ),
            "broad_screen_tcruzi_pde_rescue_review_next_required_step": str(
                bstrrs.get("next_required_step", "")
            ).strip(),
            "broad_screen_tcruzi_pde_promoted_top4_review_packet_ready": bool(
                str(bstprp.get("status", "")).strip() == "wetlab_tcruzi_pde_promoted_top4_review_packet_ready"
            ),
            "broad_screen_tcruzi_pde_promoted_top4_target_id": str(bstprp.get("target_id", "")).strip(),
            "broad_screen_tcruzi_pde_promoted_top4_shard_id": str(bstprp.get("shard_id", "")).strip(),
            "broad_screen_tcruzi_pde_promoted_top4_packet_scope": str(bstprp.get("packet_scope", "")).strip(),
            "broad_screen_tcruzi_pde_promoted_top4_packet_ready": bool(bstprp.get("packet_ready", False)),
            "broad_screen_tcruzi_pde_promoted_top4_packet_ready_for_operator_review": promoted_top4_ready_for_operator_review,
            "broad_screen_tcruzi_pde_promoted_top4_wetlab_final_gate_pass": promoted_top4_final_gate_pass,
            "broad_screen_tcruzi_pde_promoted_top4_claim_gate_available": promoted_top4_claim_gate_available,
            "broad_screen_tcruzi_pde_promoted_top4_claim_ready_for_allatom": promoted_top4_claim_ready_for_allatom,
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
            "broad_screen_tcruzi_pde_rescue_only_branch_review_packet_ready_for_operator_review": rescue_only_review_packet_ready_for_operator_review,
            "broad_screen_tcruzi_pde_rescue_only_branch_review_packet_final_gate_pass": rescue_only_review_packet_final_gate_pass,
            "broad_screen_tcruzi_pde_rescue_only_branch_review_packet_claim_gate_available": rescue_only_review_packet_claim_gate_available,
            "broad_screen_tcruzi_pde_rescue_only_branch_review_packet_claim_ready_for_allatom": rescue_only_review_packet_claim_ready_for_allatom,
            "broad_screen_tcruzi_pde_rescue_only_branch_ready_for_final_wetlab": rescue_only_branch_ready_for_final_wetlab,
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
            "selected_rescue_review_target_id": str(bstrrs.get("target_id", "")).strip(),
            "selected_rescue_review_surface_label": "pde_rescue_review"
            if str(bstrrs.get("status", "")).strip() == "wetlab_tcruzi_pde_rescue_review_surface_ready"
            else "",
            "selected_rescue_review_selected_command_kind": str(bstrrs.get("selected_command_kind", "")).strip(),
            "selected_rescue_review_strict_threshold_A": float(bstrrs.get("strict_threshold_A", 0.0) or 0.0),
            "selected_rescue_review_near_threshold_A": float(bstrrs.get("near_threshold_A", 0.0) or 0.0),
            "selected_rescue_review_promoted_candidate_count": int(bstrrs.get("promoted_candidate_count", 0) or 0),
            "selected_rescue_review_under_2p5_candidate_count": int(bstrrs.get("under_2p5_candidate_count", 0) or 0),
            "selected_rescue_review_next_required_step": str(bstrrs.get("next_required_step", "")).strip(),
            "selected_rescue_review_best_compound_name": str(
                bstrrs.get("best_compound_name", bstrrs.get("best_ligand_id", ""))
            ).strip(),
            "selected_rescue_review_best_compound_name_human_readable": str(
                bstrrs.get("best_compound_name_human_readable", "")
            ).strip(),
            "selected_rescue_review_best_compound_name_resolution": str(
                bstrrs.get("best_compound_name_resolution", "unresolved")
            ).strip(),
            "selected_rescue_branch_target_id": str(
                bstrob.get("target_id", bstprp.get("target_id", ""))
            ).strip(),
            "selected_rescue_branch_surface_label": (
                "pde_rescue_only_branch"
                if str(bstrob.get("status", "")).strip() == "wetlab_tcruzi_pde_rescue_only_branch_summary_ready"
                else ""
            ),
            "selected_rescue_branch_selected_command_kind": str(
                bstrob.get("selected_command_kind", bstprp.get("selected_command_kind", ""))
            ).strip(),
            "selected_rescue_branch_threshold_A": float(
                bstrob.get("selected_threshold_A", bstprp.get("strict_threshold_A", 0.0)) or 0.0
            ),
            "selected_rescue_branch_best_compound_name": str(
                bstrob.get("best_compound_name", bstprp.get("best_compound_name", bstprp.get("best_ligand_id", "")))
            ).strip(),
            "selected_rescue_branch_best_compound_name_human_readable": str(
                bstrob.get("best_compound_name_human_readable", bstprp.get("best_compound_name_human_readable", ""))
            ).strip(),
            "selected_rescue_branch_best_compound_name_resolution": str(
                bstrob.get("best_compound_name_resolution", bstprp.get("best_compound_name_resolution", "unresolved"))
            ).strip(),
            "selected_rescue_branch_ready_for_final_wetlab": rescue_only_branch_ready_for_final_wetlab,
            "broad_screen_tcruzi_pde_rescue_operator_packet_ready": bool(
                _text(bstropp.get("status")) == "wetlab_tcruzi_pde_rescue_operator_packet_ready"
            ),
            "broad_screen_tcruzi_pde_rescue_operator_packet_target_id": str(
                bstropp.get("target_id", "")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_operator_packet_shard_id": str(
                bstropp.get("shard_id", "")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_operator_packet_scope": str(
                bstropp.get("packet_scope", "")
            ).strip(),
            "broad_screen_tcruzi_pde_rescue_operator_packet_ready_for_operator_review": rescue_operator_packet_ready_for_operator_review,
            "broad_screen_tcruzi_pde_rescue_operator_packet_final_gate_pass": rescue_operator_packet_final_gate_pass,
            "broad_screen_tcruzi_pde_rescue_operator_packet_claim_gate_available": rescue_operator_packet_claim_gate_available,
            "broad_screen_tcruzi_pde_rescue_operator_packet_claim_ready_for_allatom": rescue_operator_packet_claim_ready_for_allatom,
            "broad_screen_tcruzi_pde_rescue_operator_packet_partner_send_gate_pass": rescue_operator_packet_partner_send_gate_pass,
            "selected_rescue_branch_operator_packet_ready": bool(
                rescue_operator_packet_ready_for_operator_review
            ),
            "selected_rescue_branch_operator_packet_ready_for_operator_review": rescue_operator_packet_ready_for_operator_review,
            "selected_rescue_branch_operator_packet_final_gate_pass": rescue_operator_packet_final_gate_pass,
            "selected_rescue_branch_operator_packet_claim_gate_available": rescue_operator_packet_claim_gate_available,
            "selected_rescue_branch_operator_packet_claim_ready_for_allatom": rescue_operator_packet_claim_ready_for_allatom,
            "selected_rescue_branch_operator_packet_partner_send_gate_pass": rescue_operator_packet_partner_send_gate_pass,
            "selected_rescue_branch_operator_packet_scope": str(
                bstropp.get("packet_scope", "")
            ).strip(),
            "broad_screen_rescue_only_branch_templates_ready": bool(
                str(bsrbt.get("status", "")).strip() == "wetlab_rescue_only_branch_templates_ready"
            ),
            "broad_screen_rescue_only_branch_template_target_count": int(
                bsrbt.get("template_target_count", 0) or 0
            ),
            "broad_screen_rescue_only_branch_focus_target_id": str(
                bsrbt.get("focus_target_id", "")
            ).strip(),
            "broad_screen_rescue_only_branch_focus_template_label": str(
                bsrbt.get("focus_template_label", "")
            ).strip(),
            "broad_screen_rescue_only_branch_focus_surface_label": str(
                bsrbt.get("focus_surface_label", "")
            ).strip(),
            "broad_screen_rescue_only_branch_focus_selected_command_kind": str(
                bsrbt.get("focus_selected_command_kind", "")
            ).strip(),
            "broad_screen_rescue_only_branch_focus_selected_threshold_A": float(
                bsrbt.get("focus_selected_threshold_A", 0.0) or 0.0
            ),
            "selected_rescue_branch_next_required_step": str(
                bstrob.get("next_required_step", bstprp.get("next_required_step", ""))
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
            "selected_allatom_selected_command_kind": selected_allatom_selected_command_kind,
            "selected_allatom_selected_threshold_A": selected_allatom_selected_threshold_A,
            "selected_allatom_packet_scope": selected_allatom_packet_scope,
            "selected_allatom_focus_available": selected_allatom_focus_available,
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
            "selected_allatom_pose_validation_rollup": selected_allatom_rollups["pose_validation_rollup"],
            "selected_allatom_pose_validation_summary": selected_allatom_rollups["pose_validation_summary"],
            "selected_allatom_claim_actionability_split_summary": _joined(
                f"raw claim {selected_allatom_raw_claim_requirement_mode}"
                if selected_allatom_raw_claim_requirement_mode
                else "",
                "required for final wetlab"
                if selected_allatom_raw_claim_required_for_final_wetlab
                else "",
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
            ),
            "selected_allatom_human_summary": selected_allatom_rollups["human_summary"],
            "selected_allatom_commercial_schema_version": selected_allatom_commercial_schema_version,
            "selected_allatom_commercial_schema_version_v2": selected_allatom_commercial_schema_version_v2,
            "selected_allatom_commercial_provenance_mode_v2": selected_allatom_commercial_provenance_mode_v2,
            "selected_allatom_translation_provenance_mode": selected_allatom_translation_provenance_mode,
            "selected_allatom_hybrid_policy": selected_allatom_hybrid_policy,
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
            "selected_allatom_raw_claim_requirement_mode": selected_allatom_raw_claim_requirement_mode,
            "selected_allatom_raw_claim_requirement_provenance": selected_allatom_raw_claim_requirement_provenance,
            "selected_allatom_raw_claim_required_for_final_wetlab": selected_allatom_raw_claim_required_for_final_wetlab,
            "selected_allatom_raw_claim_required_for_commercial_readiness": selected_allatom_raw_claim_required_for_commercial_readiness,
            "selected_allatom_raw_claim_requirement_reason": selected_allatom_raw_claim_requirement_reason,
            "selected_allatom_raw_claim_requirement_actions": list(selected_allatom_raw_claim_requirement_actions),
            "selected_allatom_claim_requirement_mode": selected_allatom_raw_claim_requirement_mode,
            "selected_allatom_claim_requirement_provenance": selected_allatom_raw_claim_requirement_provenance,
            "selected_allatom_claim_required_for_final_wetlab": selected_allatom_raw_claim_required_for_final_wetlab,
            "selected_allatom_claim_required_for_commercial_readiness": selected_allatom_raw_claim_required_for_commercial_readiness,
            "selected_allatom_claim_requirement_reason": selected_allatom_raw_claim_requirement_reason,
            "selected_allatom_claim_requirement_actions": list(selected_allatom_raw_claim_requirement_actions),
            "selected_allatom_effective_actionability_status": selected_allatom_effective_actionability_status,
            "selected_allatom_effective_actionability_claim_requirement_mode": selected_allatom_effective_actionability_claim_requirement_mode,
            "selected_allatom_effective_actionability_claim_requirement_status": selected_allatom_effective_actionability_claim_requirement_status,
            "selected_allatom_effective_actionability_claim_requirement_reason": selected_allatom_effective_actionability_claim_requirement_reason,
            "selected_allatom_effective_actionability_required_calculations": list(
                selected_allatom_effective_actionability_required_calculations
            ),
            "selected_allatom_effective_actionability_required_calculations_text": selected_allatom_effective_actionability_required_calculations_text,
            "selected_allatom_effective_actionability_action_list": list(
                selected_allatom_effective_actionability_action_list
            ),
            "selected_allatom_effective_actionability_action_list_text": selected_allatom_effective_actionability_action_list_text,
            "selected_allatom_effective_blocking_order": selected_allatom_effective_blocking_order,
            "selected_allatom_effective_primary_blocking_domain": selected_allatom_effective_primary_blocking_domain,
            "selected_allatom_actionability_status": selected_allatom_effective_actionability_status,
            "selected_allatom_actionability_claim_requirement_mode": selected_allatom_effective_actionability_claim_requirement_mode,
            "selected_allatom_actionability_claim_requirement_status": selected_allatom_effective_actionability_claim_requirement_status,
            "selected_allatom_actionability_claim_requirement_reason": selected_allatom_effective_actionability_claim_requirement_reason,
            "selected_allatom_actionability_required_calculations": list(
                selected_allatom_effective_actionability_required_calculations
            ),
            "selected_allatom_actionability_required_calculations_text": selected_allatom_effective_actionability_required_calculations_text,
            "selected_allatom_actionability_action_list": list(
                selected_allatom_effective_actionability_action_list
            ),
            "selected_allatom_actionability_action_list_text": selected_allatom_effective_actionability_action_list_text,
            "selected_allatom_actionability_human_summary": selected_allatom_actionability_human_summary,
            "selected_allatom_action_recipe_codes": list(selected_allatom_action_recipe_codes),
            "selected_allatom_action_recipe_rows": list(selected_allatom_action_recipe_rows),
            "selected_allatom_action_recipe_rollup_text": selected_allatom_action_recipe_rollup_text,
            **selected_allatom_visual_fields,
            "selected_allatom_readiness_semantics": selected_allatom_readiness_semantics,
            "selected_allatom_best_compound_name": selected_allatom_best_compound_name,
            "selected_allatom_best_compound_name_human_readable": selected_allatom_best_compound_name_human_readable,
            "selected_allatom_best_compound_name_resolution": selected_allatom_best_compound_name_resolution,
            "selected_allatom_best_mean_min_distance_A": selected_allatom_best_mean_min_distance_A,
            "selected_allatom_metric_source": selected_allatom_metric_source,
            "selected_allatom_promoted_candidate_count": selected_allatom_promoted_candidate_count,
            "selected_allatom_under_2p5_candidate_count": selected_allatom_under_2p5_candidate_count,
            "selected_allatom_near_candidate_count": selected_allatom_near_candidate_count,
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
            "selected_allatom_pose_validation_reported": selected_allatom_pose_validation_reported,
            "selected_allatom_pose_validation_version": selected_allatom_pose_validation_version,
            "selected_allatom_pose_validation_source": selected_allatom_pose_validation_source,
            "selected_allatom_pose_validation_status": selected_allatom_pose_validation_status,
            "selected_allatom_pose_validation_soft_status": selected_allatom_pose_validation_soft_status,
            "selected_allatom_pose_validation_score": selected_allatom_pose_validation_score,
            "selected_allatom_pose_validation_pass": selected_allatom_pose_validation_pass,
            "selected_allatom_pose_validation_pose_preservation_rmsd_A": selected_allatom_pose_validation_pose_preservation_rmsd_A,
            "selected_allatom_pose_validation_backmapping_consistency_score": selected_allatom_pose_validation_backmapping_consistency_score,
            "selected_allatom_pose_validation_thresholds": dict(
                selected_allatom_pose_validation_thresholds
            ),
            "selected_allatom_pose_validation_failed_checks": list(
                selected_allatom_pose_validation_failed_checks
            ),
            "selected_allatom_pose_validation_missing_checks": list(
                selected_allatom_pose_validation_missing_checks
            ),
            "selected_allatom_pose_validation_passed_checks": list(
                selected_allatom_pose_validation_passed_checks
            ),
            "selected_allatom_pose_validation_action_codes": list(
                selected_allatom_pose_validation_action_codes
            ),
            "selected_allatom_pose_validation_blocker_codes": list(
                selected_allatom_pose_validation_blocker_codes
            ),
            "selected_allatom_pose_validation_reason": selected_allatom_pose_validation_reason,
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
            "broad_screen_target_retry_policy_templates_ready": bool(
                str(bstrpts.get("status", "")).strip() == "wetlab_target_retry_policy_templates_ready"
            ),
            "broad_screen_target_retry_template_target_count": int(bstrpts.get("template_target_count", 0) or 0),
            "broad_screen_target_retry_empirical_validated_target_count": int(
                bstrpts.get("empirical_validated_target_count", 0) or 0
            ),
            "broad_screen_target_retry_focus_target_id": str(bstrpts.get("focus_target_id", "")).strip(),
            "broad_screen_target_retry_focus_template_label": str(bstrpts.get("focus_template_label", "")).strip(),
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
            "broad_screen_stage6_retry_policy_templates_ready": bool(
                str(bsstrpts.get("status", "")).strip() == "wetlab_target_retry_policy_templates_ready"
            ),
            "broad_screen_stage6_retry_template_target_count": int(bsstrpts.get("template_target_count", 0) or 0),
            "broad_screen_stage6_retry_gate45_candidate_target_count": int(
                bsstrpts.get("gate45_candidate_target_count", 0) or 0
            ),
            "broad_screen_stage6_retry_gate51_candidate_target_count": int(
                bsstrpts.get("gate51_candidate_target_count", 0) or 0
            ),
            "broad_screen_stage6_retry_ready_targets": str(bsstrpts.get("ready_targets", "")).strip(),
            "broad_screen_stage6_retry_gate45_targets": str(bsstrpts.get("gate45_targets", "")).strip(),
            "broad_screen_stage6_retry_gate51_targets": str(bsstrpts.get("gate51_targets", "")).strip(),
            "broad_screen_stage6_retry_focus_target_id": str(bsstrpts.get("focus_target_id", "")).strip(),
            "broad_screen_stage6_retry_focus_template_label": str(bsstrpts.get("focus_template_label", "")).strip(),
            "broad_screen_stage6_retry_focus_selected_command_kind": str(
                bsstrpts.get("focus_selected_command_kind", "")
            ).strip(),
            "broad_screen_stage6_retry_focus_selected_threshold_A": float(
                bsstrpts.get("focus_selected_threshold_A", 0.0) or 0.0
            ),
            "broad_screen_stage6_retry_next_required_step": str(bsstrpts.get("next_required_step", "")).strip(),
            "broad_screen_stage6_retry_policy_templates_artifact": "runs/wetlab_target_retry_policy_templates_current.md",
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
            "top_outbound_targets": top_outbound_targets or str(obs.get("top_priority_lead_targets", "")).strip(),
            "next_required_step": (
                selected_allatom_next_required_step
                if selected_allatom_next_required_step
                else str(bskrs1.get("next_required_step", "")).strip()
                if bool(bskrs1.get("branch_validated", False)) and str(bskrs1.get("next_required_step", "")).strip()
                else str(bdr1.get("next_required_step", "")).strip()
                if str(bdr1.get("status", "")).strip() == "wetlab_dpre1_branch_review_surface_ready"
                and str(bdr1.get("next_required_step", "")).strip()
                else str(bstrob.get("next_required_step", "")).strip()
                if str(bstrob.get("next_required_step", "")).strip()
                else str(bstprp.get("next_required_step", "")).strip()
                if str(bstprp.get("next_required_step", "")).strip()
                else str(bstrrs.get("next_required_step", "")).strip()
                if str(bstrrs.get("next_required_step", "")).strip()
                else dengue_stage6_next_required_step
                if dengue_stage6_next_required_step
                else
                rescue_next_required_step
                if rescue_next_required_step
                else str(bslvrs.get("next_required_step", "")).strip()
                if bool(bslvrs.get("gate51_validated", False)) and str(bslvrs.get("next_required_step", "")).strip()
                else f"Continue the active broad-procurement shard for {bseqs.get('first_actionable_target_id', '')} {bseqs.get('first_actionable_shard_id', '')}, then regenerate autofill-driven repurposing packets."
                if int(bseqs.get("running_row_count", 0) or 0) > 0
                else
                f"Dispatch {bseqs.get('first_actionable_target_id', '')} shard {bseqs.get('first_actionable_shard_id', '')}, then regenerate autofill-driven repurposing packets."
                if int(bseqs.get("ready_now_row_count", 0) or 0) > 0
                else
                "Run the 100k broad-procurement target-by-shard screen first, then use the bridge to replace manual repurposing rows before partner dispatch."
                if str(bsqs.get("status", "")).strip() == "wetlab_broad_screen_queue_ready"
                else "Use the outbound execution priority board in canonical track order, starting with ready_to_send lead packets and then the follow-on execution packets."
            ),
        },
        "structured": {
            "terminal_review_artifact": "runs/wetlab_master_terminal_review_current.md",
            "outbound_priority_board_artifact": "runs/wetlab_outbound_execution_priority_board_current.md",
            "partner_export_bundle_artifact": "runs/wetlab_partner_first_contact_export_bundle_current.md",
            "campaign_blueprint_artifact": "runs/wetlab_wave1_campaign_blueprint_current.md",
            "broad_screen_queue_artifact": "runs/wetlab_broad_screen_queue_current.md",
            "broad_screen_bridge_artifact": "runs/wetlab_broad_screen_bridge_current.md",
            "broad_screen_compound_universe_artifact": "runs/wetlab_broad_screen_compound_universe_current.md",
            "broad_screen_execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
            "broad_screen_repurposing_autofill_artifact": "runs/wetlab_broad_screen_repurposing_autofill_current.md",
            "broad_screen_target_rerank_artifact": "runs/wetlab_broad_screen_target_rerank_current.md",
            "broad_screen_stability_score_artifact": "runs/wetlab_broad_screen_stability_score_current.md",
            "broad_screen_antitarget_queue_artifact": "runs/wetlab_broad_screen_antitarget_queue_current.md",
            "broad_screen_actual_append_artifact": "runs/wetlab_broad_screen_actual_append_current.md",
            "broad_screen_target_retry_policy_templates_artifact": "runs/wetlab_target_retry_policy_templates_current.md",
            "broad_screen_stage6_retry_policy_templates_artifact": "runs/wetlab_target_retry_policy_templates_current.md",
            "broad_screen_dpre1_branch_review_surface_artifact": "runs/wetlab_dpre1_branch_review_surface_current.md",
            "broad_screen_dengue_stage6_tuning_surface_artifact": "runs/wetlab_dengue_ns2b_ns3_protease_stage6_tuning_surface_current.md",
            "broad_screen_dengue_exploratory_retry_lane_artifact": "runs/wetlab_dengue_ns2b_ns3_protease_exploratory_retry_lane_current.md",
            "broad_screen_mapping_fix_retry_policy_templates_artifact": "runs/wetlab_mapping_fix_retry_policy_templates_current.md",
            "broad_screen_hard_target_rescue_lane_artifact": "runs/wetlab_hard_target_rescue_lane_current.md",
            "broad_screen_rescue_anchor_artifacts_artifact": "runs/wetlab_rescue_anchor_artifacts_current.md",
            "broad_screen_rescue_three_bead_candidates_artifact": "runs/wetlab_rescue_three_bead_candidates_current.md",
            "broad_screen_tcruzi_pde_rescue_review_surface_artifact": "runs/wetlab_tcruzi_pde_rescue_review_surface_current.md",
            "broad_screen_tcruzi_pde_promoted_top4_review_packet_artifact": "runs/wetlab_tcruzi_pde_promoted_top4_review_packet_current.md",
            "broad_screen_tcruzi_pde_rescue_only_branch_summary_artifact": "runs/wetlab_tcruzi_pde_rescue_only_branch_summary_current.md",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the wet-lab final campaign summary surface.")
    parser.add_argument("--terminal-review-json", default=DEFAULT_TERMINAL_REVIEW_JSON)
    parser.add_argument("--master-queue-json", default=DEFAULT_MASTER_QUEUE_JSON)
    parser.add_argument("--export-bundle-json", default=DEFAULT_EXPORT_BUNDLE_JSON)
    parser.add_argument("--outbound-board-json", default=DEFAULT_OUTBOUND_BOARD_JSON)
    parser.add_argument("--portfolio-json", default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument("--blueprint-json", default=DEFAULT_BLUEPRINT_JSON)
    parser.add_argument("--broad-screen-queue-json", default=DEFAULT_BROAD_SCREEN_QUEUE_JSON)
    parser.add_argument("--broad-screen-bridge-json", default=DEFAULT_BROAD_SCREEN_BRIDGE_JSON)
    parser.add_argument("--broad-screen-retry-handoff-summary-json", default=DEFAULT_BROAD_SCREEN_RETRY_HANDOFF_SUMMARY_JSON)
    parser.add_argument("--broad-screen-compound-universe-json", default=DEFAULT_BROAD_SCREEN_COMPOUND_UNIVERSE_JSON)
    parser.add_argument("--broad-screen-execution-queue-json", default=DEFAULT_BROAD_SCREEN_EXECUTION_QUEUE_JSON)
    parser.add_argument("--broad-screen-repurposing-autofill-json", default=DEFAULT_BROAD_SCREEN_REPURPOSING_AUTOFILL_JSON)
    parser.add_argument("--broad-screen-target-rerank-json", default=DEFAULT_BROAD_SCREEN_TARGET_RERANK_JSON)
    parser.add_argument("--broad-screen-stability-score-json", default=DEFAULT_BROAD_SCREEN_STABILITY_SCORE_JSON)
    parser.add_argument("--broad-screen-antitarget-queue-json", default=DEFAULT_BROAD_SCREEN_ANTITARGET_QUEUE_JSON)
    parser.add_argument("--broad-screen-antitarget-execution-queue-json", default=DEFAULT_BROAD_SCREEN_ANTITARGET_EXECUTION_QUEUE_JSON)
    parser.add_argument("--broad-screen-actual-append-json", default=DEFAULT_BROAD_SCREEN_ACTUAL_APPEND_JSON)
    parser.add_argument("--broad-screen-dengue-stage6-tuning-surface-json", default=DEFAULT_BROAD_SCREEN_DENGUE_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--broad-screen-dengue-exploratory-retry-lane-json", default=DEFAULT_BROAD_SCREEN_DENGUE_EXPLORATORY_RETRY_LANE_JSON)
    parser.add_argument("--broad-screen-lbdhodh-stage6-tuning-surface-json", default=DEFAULT_BROAD_SCREEN_LBDHODH_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--broad-screen-lbdhodh-exploratory-retry-lane-json", default=DEFAULT_BROAD_SCREEN_LBDHODH_EXPLORATORY_RETRY_LANE_JSON)
    parser.add_argument("--broad-screen-lbdhodh-gate51-validation-review-surface-json", default=DEFAULT_BROAD_SCREEN_LBDHODH_GATE51_VALIDATION_REVIEW_SURFACE_JSON)
    parser.add_argument("--broad-screen-dpre1-branch-review-surface-json", default=DEFAULT_BROAD_SCREEN_DPRE1_BRANCH_REVIEW_SURFACE_JSON)
    parser.add_argument("--broad-screen-tcruzi-krs1-branch-review-surface-json", default=DEFAULT_BROAD_SCREEN_TCRUZI_KRS1_BRANCH_REVIEW_SURFACE_JSON)
    parser.add_argument("--broad-screen-tcruzi-pde-rescue-review-surface-json", default=DEFAULT_BROAD_SCREEN_TCRUZI_PDE_RESCUE_REVIEW_SURFACE_JSON)
    parser.add_argument("--broad-screen-tcruzi-pde-promoted-top4-review-packet-json", default=DEFAULT_BROAD_SCREEN_TCRUZI_PDE_PROMOTED_TOP4_REVIEW_PACKET_JSON)
    parser.add_argument("--broad-screen-tcruzi-pde-rescue-only-branch-summary-json", default=DEFAULT_BROAD_SCREEN_TCRUZI_PDE_RESCUE_ONLY_BRANCH_SUMMARY_JSON)
    parser.add_argument("--broad-screen-tcruzi-pde-rescue-operator-packet-json", default=DEFAULT_BROAD_SCREEN_TCRUZI_PDE_RESCUE_OPERATOR_PACKET_JSON)
    parser.add_argument("--broad-screen-rescue-only-branch-templates-json", default=DEFAULT_BROAD_SCREEN_RESCUE_ONLY_BRANCH_TEMPLATES_JSON)
    parser.add_argument("--broad-screen-target-retry-policy-templates-json", default=DEFAULT_BROAD_SCREEN_TARGET_RETRY_POLICY_TEMPLATES_JSON)
    parser.add_argument("--broad-screen-mapping-fix-retry-policy-templates-json", default=DEFAULT_BROAD_SCREEN_MAPPING_FIX_RETRY_POLICY_TEMPLATES_JSON)
    parser.add_argument("--broad-screen-hard-target-rescue-lane-json", default=DEFAULT_BROAD_SCREEN_HARD_TARGET_RESCUE_LANE_JSON)
    parser.add_argument("--broad-screen-rescue-anchor-artifacts-json", default=DEFAULT_BROAD_SCREEN_RESCUE_ANCHOR_ARTIFACTS_JSON)
    parser.add_argument("--broad-screen-rescue-three-bead-candidates-json", default=DEFAULT_BROAD_SCREEN_RESCUE_THREE_BEAD_CANDIDATES_JSON)
    parser.add_argument("--broad-screen-selected-allatom-visual-bundle-json", default=DEFAULT_BROAD_SCREEN_SELECTED_ALLATOM_VISUAL_BUNDLE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    payload = build_payload(
        load_json(args.terminal_review_json),
        load_json(args.master_queue_json),
        load_json(args.export_bundle_json),
        load_json(args.outbound_board_json),
        load_json(args.portfolio_json),
        load_json(args.blueprint_json),
        load_json(args.broad_screen_queue_json),
        load_json(args.broad_screen_bridge_json),
        load_json(args.broad_screen_compound_universe_json),
        load_json(args.broad_screen_execution_queue_json),
        load_json(args.broad_screen_repurposing_autofill_json),
        load_json(args.broad_screen_target_rerank_json),
        maybe_load_json(args.broad_screen_stability_score_json),
        maybe_load_json(args.broad_screen_antitarget_queue_json),
        maybe_load_json(args.broad_screen_antitarget_execution_queue_json),
        maybe_load_json(args.broad_screen_actual_append_json),
        maybe_load_json(args.broad_screen_dengue_stage6_tuning_surface_json),
        maybe_load_json(args.broad_screen_dengue_exploratory_retry_lane_json),
        maybe_load_json(args.broad_screen_lbdhodh_stage6_tuning_surface_json),
        maybe_load_json(args.broad_screen_lbdhodh_exploratory_retry_lane_json),
        maybe_load_json(args.broad_screen_lbdhodh_gate51_validation_review_surface_json),
        maybe_load_json(args.broad_screen_dpre1_branch_review_surface_json),
        maybe_load_json(args.broad_screen_tcruzi_krs1_branch_review_surface_json),
        maybe_load_json(args.broad_screen_tcruzi_pde_rescue_review_surface_json),
        maybe_load_json(args.broad_screen_tcruzi_pde_promoted_top4_review_packet_json),
        maybe_load_json(args.broad_screen_tcruzi_pde_rescue_only_branch_summary_json),
        maybe_load_json(args.broad_screen_tcruzi_pde_rescue_operator_packet_json),
        maybe_load_json(args.broad_screen_rescue_only_branch_templates_json),
        maybe_load_json(args.broad_screen_target_retry_policy_templates_json),
        maybe_load_json(args.broad_screen_mapping_fix_retry_policy_templates_json),
        maybe_load_json(args.broad_screen_hard_target_rescue_lane_json),
        maybe_load_json(args.broad_screen_rescue_anchor_artifacts_json),
        maybe_load_json(args.broad_screen_rescue_three_bead_candidates_json),
        maybe_load_json(args.broad_screen_retry_handoff_summary_json),
        maybe_load_json(args.broad_screen_selected_allatom_visual_bundle_json),
    )
    write_artifact(args.out_md, "Wet-Lab Final Campaign Summary", payload)
