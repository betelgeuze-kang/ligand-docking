#!/usr/bin/env python3
from __future__ import annotations

import re
from typing import Any


def _text(*values: Any, default: str = "") -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return default


def _safe_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in {"", None}:
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "ready", "pass", "passed", "satisfied"}:
        return True
    if text in {"0", "false", "f", "no", "n", "fail", "failed", "blocked"}:
        return False
    return None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {"", None}:
            return default
        return float(value)
    except Exception:
        return default


def _normalize_string_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple, set)):
        items = [str(item or "").strip() for item in value]
    else:
        items = [str(value).strip()]
    return [item for item in items if item]


def _pick_value(
    summaries: list[tuple[str, dict[str, Any]]],
    *keys: str,
) -> tuple[Any, str]:
    for source_label, summary in summaries:
        if not summary:
            continue
        for key in keys:
            if key not in summary:
                continue
            value = summary.get(key)
            if value is None or value == "":
                continue
            if isinstance(value, (list, tuple, set)) and not list(value):
                continue
            return value, f"{source_label}.{key}"
    return None, ""


def _pick_bool(
    summaries: list[tuple[str, dict[str, Any]]],
    *keys: str,
) -> tuple[bool | None, str]:
    value, source = _pick_value(summaries, *keys)
    return _safe_bool(value), source


def _pick_list(
    summaries: list[tuple[str, dict[str, Any]]],
    *keys: str,
) -> tuple[list[str], str]:
    value, source = _pick_value(summaries, *keys)
    return _normalize_string_list(value), source


def _joined(*values: Any, sep: str = " | ", default: str = "") -> str:
    parts = [str(value or "").strip() for value in values if str(value or "").strip()]
    return sep.join(parts) if parts else default


def _metric_value_text(value: Any) -> str:
    if value in {"", None}:
        return "missing"
    if isinstance(value, bool):
        return str(value).lower()
    try:
        numeric = float(value)
    except Exception:
        return _text(value)
    if numeric.is_integer():
        return f"{numeric:.0f}"
    if abs(numeric) >= 10:
        return f"{numeric:.2f}"
    return f"{numeric:.3f}"


def _metric_action(metric_name: str) -> tuple[str, str]:
    metric = _text(metric_name)
    if metric == "replicate_count":
        return "increase_replicate_coverage", "expand_replicate_sampling"
    if metric == "replicate_pass_fraction":
        return "raise_replicate_pass_fraction", "recompute_replicate_pass_fraction"
    if metric == "median_mean_min_distance_A":
        return "tighten_replicate_median_geometry", "recompute_median_mean_min_distance_A"
    if metric == "mean_min_distance_iqr_A":
        return "reduce_replicate_distance_dispersion", "recompute_mean_min_distance_iqr_A"
    if metric == "median_contact_fraction":
        return "raise_replicate_contact_occupancy", "recompute_median_contact_fraction"
    if metric == "pose_cluster_dominance":
        return "stabilize_dominant_pose_cluster", "recompute_pose_cluster_dominance"
    if metric == "pose_preservation_rmsd_A":
        return "improve_pose_preservation_rmsd", "recompute_pose_preservation_rmsd_A"
    if metric == "backmapping_consistency_score":
        return "stabilize_backmapping_consistency", "recompute_backmapping_consistency_score"
    if metric == "local_minimization_survival_fraction":
        return "improve_local_minimization_survival", "recompute_local_minimization_survival_fraction"
    if metric == "mean_min_distance_A":
        return "tighten_pose_geometry_under_strict_gate", "recompute_mean_min_distance_A"
    if metric == "binding_energy_proxy":
        return "strengthen_binding_energy_proxy", "recompute_binding_energy_proxy"
    if metric == "stability_score":
        return "raise_trajectory_stability", "recompute_stability_score"
    if metric == "contact_fraction":
        return "raise_contact_occupancy", "recompute_contact_fraction"
    if metric == "binding_energy_mmpbsa_std":
        return "reduce_mmpbsa_uncertainty", "recompute_binding_energy_mmpbsa_std"
    if metric == "trajectory_frames":
        return "increase_trajectory_support", "extend_trajectory_frames"
    return (f"review_{metric}" if metric else "review_metric", f"recompute_{metric}" if metric else "recompute_metric")


def _metric_threshold_text(metric_name: str, thresholds: dict[str, Any]) -> str:
    metric = _text(metric_name)
    if metric == "replicate_count":
        return _metric_value_text(thresholds.get("replicate_count_min"))
    if metric == "replicate_pass_fraction":
        return _metric_value_text(thresholds.get("replicate_pass_fraction_min"))
    if metric in {"median_mean_min_distance_A", "mean_min_distance_A"}:
        return _metric_value_text(
            thresholds.get("selected_threshold_A") or thresholds.get("strict_threshold_A")
        )
    if metric == "mean_min_distance_iqr_A":
        return _metric_value_text(thresholds.get("mean_min_distance_iqr_A_max"))
    if metric == "median_contact_fraction":
        return _metric_value_text(thresholds.get("median_contact_fraction_min"))
    if metric == "pose_cluster_dominance":
        return _metric_value_text(thresholds.get("pose_cluster_dominance_min"))
    if metric == "pose_preservation_rmsd_A":
        return _metric_value_text(thresholds.get("pose_preservation_rmsd_A_max"))
    if metric == "backmapping_consistency_score":
        return _metric_value_text(thresholds.get("backmapping_consistency_score_min"))
    if metric == "local_minimization_survival_fraction":
        return _metric_value_text(thresholds.get("local_minimization_survival_fraction_min"))
    if metric == "binding_energy_proxy":
        return _metric_value_text(thresholds.get("binding_energy_proxy_max_kcal_mol"))
    if metric == "stability_score":
        return _metric_value_text(thresholds.get("stability_score_min"))
    if metric == "contact_fraction":
        return _metric_value_text(thresholds.get("contact_fraction_min"))
    if metric == "binding_energy_mmpbsa_std":
        return _metric_value_text(thresholds.get("binding_energy_mmpbsa_std_max"))
    if metric == "trajectory_frames":
        return _metric_value_text(thresholds.get("trajectory_frames_min"))
    return "missing"


def _review_metric_matches_selected_focus(
    *,
    review: dict[str, Any],
    selected_target_id: str,
    selected_surface_label: str,
) -> bool:
    review_target_id = _text(
        review.get("target_id"),
        review.get("selected_allatom_target_id"),
    )
    review_surface_label = _text(
        review.get("surface_label"),
        review.get("selected_allatom_surface_label"),
    )
    target_matches = not review_target_id or review_target_id == selected_target_id
    surface_matches = not review_surface_label or review_surface_label == selected_surface_label
    return bool(target_matches and surface_matches)


def _infer_translation_fields_from_texts(*texts: Any) -> dict[str, str]:
    combined = " ".join(str(text or "").strip() for text in texts if str(text or "").strip())
    lowered = combined.lower()
    if not lowered:
        return {}
    resolved: dict[str, str] = {}
    patterns = {
        "translation_gate_focus_status": [
            r"translation_gate=([a-z_]+)",
            r"translation gate focus is ([a-z_]+)",
            r"translation gate is ([a-z_]+)",
        ],
        "focus_shortlist_tier": [
            r"shortlist_tier=([a-z_]+)",
            r"shortlist tier is ([a-z_]+)",
        ],
        "recommended_next_expensive_lane": [
            r"recommended_next_expensive_lane=([a-z_]+)",
            r"recommended next lane is ([a-z_]+)",
            r"next expensive lane is ([a-z_]+)",
        ],
    }
    for field_name, field_patterns in patterns.items():
        for pattern in field_patterns:
            match = re.search(pattern, lowered)
            if match:
                resolved[field_name] = match.group(1)
                break
    return resolved


def resolve_selected_allatom_canonical(
    *,
    review_packet_summary: dict[str, Any] | None = None,
    retry_handoff_summary: dict[str, Any] | None = None,
    current_results_index_summary: dict[str, Any] | None = None,
    monitor_semantics_summary: dict[str, Any] | None = None,
    master_handoff_dashboard_summary: dict[str, Any] | None = None,
    final_campaign_summary: dict[str, Any] | None = None,
    partnering_stack_summary: dict[str, Any] | None = None,
    next_required_step: str = "",
    allow_translation_fallback: bool = True,
) -> dict[str, Any]:
    """
    Canonical selected-allatom resolver contract.

    The implementation is expected to normalize a single selected-allatom view
    across downstream surfaces and return a dict with, at minimum, these keys:

    - commercial_schema_version_v2
    - commercial_overall_score_v2
    - commercial_risk_bucket_v2
    - commercial_decision_class_v2
    - commercial_primary_upgrade_actions_v2
    - translation_gate_version
    - translation_gate_focus_status
    - translation_gate_focus_score
    - translation_gate_focus_reason
    - focus_shortlist_tier
    - recommended_next_expensive_lane
    - recommended_next_expensive_lane_reason
    - raw_claim_requirement_mode
    - raw_claim_requirement_provenance
    - raw_claim_required_for_final_wetlab
    - raw_claim_required_for_commercial_readiness
    - raw_claim_requirement_reason
    - effective_actionability_status
    - effective_actionability_claim_requirement_mode
    - effective_actionability_claim_requirement_status
    - effective_actionability_claim_requirement_reason
    - effective_actionability_next_expensive_lane
    - effective_actionability_next_expensive_lane_reason
    - effective_actionability_required_calculations
    - effective_actionability_action_list
    - effective_blocking_order
    - effective_primary_blocking_domain
    - action_recipe_codes
    - action_recipe_rows
    - translation_provenance_mode
    - commercial_provenance_mode_v2
    - hybrid_policy
    """
    review = dict(review_packet_summary or {})
    retry = dict(retry_handoff_summary or {})
    current = dict(current_results_index_summary or {})
    monitor = dict(monitor_semantics_summary or {})
    dashboard = dict(master_handoff_dashboard_summary or {})
    final = dict(final_campaign_summary or {})
    partnering = dict(partnering_stack_summary or {})

    summaries = [
        ("current_results_index", current),
        ("monitor_semantics", monitor),
        ("master_handoff_dashboard", dashboard),
        ("final_campaign_summary", final),
        ("partnering_stack", partnering),
        ("retry_handoff_summary", retry),
        ("review_packet_summary", review),
    ]
    selected_target_id = _text(
        retry.get("selected_allatom_target_id"),
        current.get("selected_allatom_target_id"),
        monitor.get("selected_allatom_target_id"),
        review.get("target_id"),
    )
    selected_surface_label = _text(
        retry.get("selected_allatom_surface_label"),
        current.get("selected_allatom_surface_label"),
        monitor.get("selected_allatom_surface_label"),
        review.get("surface_label"),
    )
    focus_available = bool(
        _text(
            selected_target_id,
            selected_surface_label,
        )
    )

    translation_fallback = _infer_translation_fields_from_texts(
        next_required_step,
        retry.get("selected_allatom_next_required_step"),
        retry.get("selected_allatom_actionability_human_summary"),
        retry.get("selected_allatom_actionability_brief_summary"),
        review.get("next_required_step"),
        review.get("selected_allatom_human_summary"),
        review.get("selected_allatom_translation_human_summary"),
        current.get("selected_allatom_next_required_step"),
        current.get("selected_allatom_human_summary"),
        monitor.get("selected_allatom_next_required_step"),
        monitor.get("selected_allatom_human_summary"),
    )

    commercial_schema_version_v2, commercial_schema_source_v2 = _pick_value(
        summaries,
        "selected_allatom_commercial_schema_version_v2",
        "commercial_schema_version_v2",
    )
    commercial_hard_gate_pass_v2_raw, commercial_hard_gate_source_v2 = _pick_value(
        summaries,
        "selected_allatom_commercial_hard_gate_pass_v2",
        "commercial_hard_gate_pass_v2",
    )
    commercial_soft_score_v2, commercial_soft_source_v2 = _pick_value(
        summaries,
        "selected_allatom_commercial_soft_score_v2",
        "commercial_soft_score_v2",
    )
    commercial_confidence_score_v2, commercial_confidence_source_v2 = _pick_value(
        summaries,
        "selected_allatom_commercial_confidence_score_v2",
        "commercial_confidence_score_v2",
    )
    commercial_overall_score_v2, commercial_overall_source_v2 = _pick_value(
        summaries,
        "selected_allatom_commercial_overall_score_v2",
        "commercial_overall_score_v2",
    )
    commercial_risk_bucket_v2, commercial_risk_source_v2 = _pick_value(
        summaries,
        "selected_allatom_commercial_risk_bucket_v2",
        "commercial_risk_bucket_v2",
    )
    commercial_decision_class_v2, commercial_decision_source_v2 = _pick_value(
        summaries,
        "selected_allatom_commercial_decision_class_v2",
        "commercial_decision_class_v2",
    )
    commercial_actions_v2, _ = _pick_list(
        summaries,
        "selected_allatom_commercial_primary_upgrade_actions_v2",
        "commercial_primary_upgrade_actions_v2",
    )
    commercial_human_summary_v2, _ = _pick_value(
        summaries,
        "selected_allatom_commercial_human_summary_v2",
        "commercial_human_summary_v2",
    )
    legacy_commercial_schema_version, legacy_commercial_schema_source = _pick_value(
        summaries,
        "selected_allatom_commercial_schema_version",
        "commercial_schema_version",
    )
    legacy_commercial_hard_gate_pass, legacy_commercial_hard_gate_source = _pick_value(
        summaries,
        "selected_allatom_commercial_hard_gate_pass",
        "commercial_hard_gate_pass",
        "selected_allatom_commercial_hard_gate_pass_v1",
        "commercial_hard_gate_pass_v1",
    )
    legacy_commercial_soft_score, legacy_commercial_soft_source = _pick_value(
        summaries,
        "selected_allatom_commercial_soft_score_v1",
        "commercial_soft_score_v1",
    )
    legacy_commercial_confidence_score, legacy_commercial_confidence_source = _pick_value(
        summaries,
        "selected_allatom_commercial_confidence_score_v1",
        "commercial_confidence_score_v1",
    )
    legacy_commercial_overall_score, legacy_commercial_overall_source = _pick_value(
        summaries,
        "selected_allatom_commercial_overall_score_v1",
        "commercial_overall_score_v1",
    )
    legacy_commercial_risk_bucket, legacy_commercial_risk_source = _pick_value(
        summaries,
        "selected_allatom_commercial_risk_bucket_v1",
        "commercial_risk_bucket_v1",
    )
    legacy_commercial_decision_class, legacy_commercial_decision_source = _pick_value(
        summaries,
        "selected_allatom_commercial_decision_class_v1",
        "commercial_decision_class_v1",
    )
    legacy_commercial_actions, legacy_commercial_actions_source = _pick_value(
        summaries,
        "selected_allatom_commercial_primary_upgrade_actions_v1",
        "commercial_primary_upgrade_actions_v1",
    )
    legacy_commercial_actions = _normalize_string_list(legacy_commercial_actions)
    hard_failed_metrics, _ = _pick_list(
        summaries,
        "selected_allatom_commercial_hard_gate_failed_metrics_v2",
        "commercial_hard_gate_failed_metrics_v2",
    )
    hard_missing_metrics, _ = _pick_list(
        summaries,
        "selected_allatom_commercial_hard_gate_missing_metrics_v2",
        "commercial_hard_gate_missing_metrics_v2",
    )
    thresholds_raw, _ = _pick_value(
        summaries,
        "selected_allatom_commercial_score_thresholds_v2",
        "commercial_score_thresholds_v2",
    )
    thresholds = dict(thresholds_raw or {})
    selected_threshold_value, _ = _pick_value(
        summaries,
        "selected_allatom_selected_threshold_A",
        "selected_threshold_A",
        "strict_threshold_A",
    )
    if selected_threshold_value not in {"", None} and "selected_threshold_A" not in thresholds:
        thresholds["selected_threshold_A"] = _safe_float(selected_threshold_value, 0.0)
    if selected_threshold_value not in {"", None} and "strict_threshold_A" not in thresholds:
        thresholds["strict_threshold_A"] = _safe_float(selected_threshold_value, 0.0)

    legacy_schema_lower = _text(legacy_commercial_schema_version).lower()
    legacy_carries_v2 = "v2" in legacy_schema_lower
    if legacy_carries_v2:
        if not _text(commercial_schema_version_v2):
            commercial_schema_version_v2 = legacy_commercial_schema_version
            commercial_schema_source_v2 = legacy_commercial_schema_source
        if commercial_hard_gate_pass_v2_raw in {"", None}:
            commercial_hard_gate_pass_v2_raw = legacy_commercial_hard_gate_pass
            commercial_hard_gate_source_v2 = legacy_commercial_hard_gate_source
        if commercial_soft_score_v2 in {"", None}:
            commercial_soft_score_v2 = legacy_commercial_soft_score
            commercial_soft_source_v2 = legacy_commercial_soft_source
        if commercial_confidence_score_v2 in {"", None}:
            commercial_confidence_score_v2 = legacy_commercial_confidence_score
            commercial_confidence_source_v2 = legacy_commercial_confidence_source
        if commercial_overall_score_v2 in {"", None}:
            commercial_overall_score_v2 = legacy_commercial_overall_score
            commercial_overall_source_v2 = legacy_commercial_overall_source
        if commercial_risk_bucket_v2 in {"", None}:
            commercial_risk_bucket_v2 = legacy_commercial_risk_bucket
            commercial_risk_source_v2 = legacy_commercial_risk_source
        if commercial_decision_class_v2 in {"", None}:
            commercial_decision_class_v2 = legacy_commercial_decision_class
            commercial_decision_source_v2 = legacy_commercial_decision_source
        if not commercial_actions_v2 and legacy_commercial_actions:
            commercial_actions_v2 = list(legacy_commercial_actions)

    translation_gate_version, _ = _pick_value(
        summaries,
        "selected_allatom_translation_gate_version",
        "allatom_family_focus_translation_gate_version",
        "translation_gate_version",
    )
    translation_gate_focus_status, _ = _pick_value(
        summaries,
        "selected_allatom_translation_gate_focus_status",
        "selected_allatom_translation_gate_status",
        "allatom_family_focus_translation_gate_focus_status",
        "allatom_family_focus_translation_gate_status",
        "translation_gate_focus_status",
    )
    translation_gate_focus_score, _ = _pick_value(
        summaries,
        "selected_allatom_translation_gate_focus_score",
        "selected_allatom_translation_gate_score",
        "allatom_family_focus_translation_gate_focus_score",
        "allatom_family_focus_translation_gate_score",
        "translation_gate_focus_score",
    )
    translation_gate_focus_reason, _ = _pick_value(
        summaries,
        "selected_allatom_translation_gate_focus_reason",
        "selected_allatom_translation_gate_reason",
        "allatom_family_focus_translation_gate_focus_reason",
        "allatom_family_focus_translation_gate_reason",
        "translation_gate_focus_reason",
    )
    focus_shortlist_tier, _ = _pick_value(
        summaries,
        "selected_allatom_focus_shortlist_tier",
        "allatom_family_focus_shortlist_tier",
        "focus_shortlist_tier",
        "shortlist_tier",
    )
    recommended_next_expensive_lane, _ = _pick_value(
        summaries,
        "selected_allatom_recommended_next_expensive_lane",
        "allatom_family_focus_recommended_next_expensive_lane",
        "recommended_next_expensive_lane",
    )
    recommended_next_expensive_lane_reason, _ = _pick_value(
        summaries,
        "selected_allatom_recommended_next_expensive_lane_reason",
        "allatom_family_focus_recommended_next_expensive_lane_reason",
        "recommended_next_expensive_lane_reason",
    )
    stronger_physics_shortlist_version, _ = _pick_value(
        summaries,
        "selected_allatom_stronger_physics_shortlist_version",
        "allatom_family_focus_stronger_physics_shortlist_version",
        "stronger_physics_shortlist_version",
    )
    translation_failed_checks, _ = _pick_list(
        summaries,
        "translation_gate_focus_failed_checks",
        "selected_allatom_translation_gate_focus_failed_checks",
    )
    translation_warning_checks, _ = _pick_list(
        summaries,
        "translation_gate_focus_warning_checks",
        "selected_allatom_translation_gate_focus_warning_checks",
    )
    translation_action_codes, _ = _pick_list(
        summaries,
        "translation_gate_action_codes",
        "selected_allatom_translation_gate_action_codes",
    )
    translation_blocker_codes, _ = _pick_list(
        summaries,
        "translation_gate_blocker_codes",
        "selected_allatom_translation_gate_blocker_codes",
    )
    lane_action_codes, _ = _pick_list(
        summaries,
        "recommended_next_expensive_lane_action_codes",
        "selected_allatom_recommended_next_expensive_lane_action_codes",
    )
    lane_blocker_codes, _ = _pick_list(
        summaries,
        "recommended_next_expensive_lane_blocker_codes",
        "selected_allatom_recommended_next_expensive_lane_blocker_codes",
    )

    translation_provenance_mode = "source_driven"
    if allow_translation_fallback:
        if not _text(translation_gate_focus_status) and translation_fallback.get("translation_gate_focus_status"):
            translation_gate_focus_status = translation_fallback["translation_gate_focus_status"]
            translation_provenance_mode = "inferred_from_partial_upstream"
        if not _text(focus_shortlist_tier) and translation_fallback.get("focus_shortlist_tier"):
            focus_shortlist_tier = translation_fallback["focus_shortlist_tier"]
            translation_provenance_mode = "inferred_from_partial_upstream"
        if not _text(recommended_next_expensive_lane) and translation_fallback.get("recommended_next_expensive_lane"):
            recommended_next_expensive_lane = translation_fallback["recommended_next_expensive_lane"]
            translation_provenance_mode = "inferred_from_partial_upstream"

    operator_review_ready, _ = _pick_bool(
        summaries,
        "selected_allatom_packet_ready_for_operator_review",
        "selected_allatom_operator_review_ready",
        "packet_ready_for_operator_review",
    )
    final_gate_pass, _ = _pick_bool(
        summaries,
        "selected_allatom_wetlab_final_gate_pass",
        "selected_allatom_final_gate_pass",
        "wetlab_final_gate_pass",
        "final_gate_pass",
    )
    claim_gate_available, _ = _pick_bool(
        summaries,
        "selected_allatom_claim_gate_available",
        "claim_gate_available",
    )
    claim_ready_for_allatom, _ = _pick_bool(
        summaries,
        "selected_allatom_claim_ready_for_allatom",
        "claim_ready_for_allatom",
    )

    raw_claim_requirement_mode, _ = _pick_value(
        summaries,
        "selected_allatom_raw_claim_requirement_mode",
        "claim_gate_requirement_mode",
        "selected_allatom_claim_requirement_mode",
    )
    raw_claim_required_for_final_wetlab, raw_claim_required_for_final_source = _pick_bool(
        summaries,
        "selected_allatom_raw_claim_required_for_final_wetlab",
        "selected_allatom_claim_required_for_final_wetlab",
        "claim_gate_required_for_final_wetlab",
    )
    raw_claim_required_for_commercial_readiness, raw_claim_required_for_commercial_source = _pick_bool(
        summaries,
        "selected_allatom_raw_claim_required_for_commercial_readiness",
        "selected_allatom_claim_required_for_commercial_readiness",
        "claim_gate_required_for_commercial_readiness",
    )
    raw_claim_requirement_reason, _ = _pick_value(
        summaries,
        "selected_allatom_raw_claim_requirement_reason",
        "selected_allatom_claim_requirement_reason",
        "claim_gate_requirement_reason",
        "claim_gate_status_reason",
    )
    raw_claim_requirement_provenance, _ = _pick_value(
        summaries,
        "selected_allatom_claim_requirement_provenance",
        "claim_gate_requirement_provenance",
    )
    raw_claim_requirement_actions, _ = _pick_list(
        summaries,
        "selected_allatom_claim_requirement_actions",
        "claim_gate_requirement_actions",
    )

    raw_claim_required_for_final_wetlab = bool(raw_claim_required_for_final_wetlab)
    raw_claim_required_for_commercial_readiness = bool(
        raw_claim_required_for_commercial_readiness
    )
    if not _text(raw_claim_requirement_mode):
        if raw_claim_required_for_final_wetlab or raw_claim_required_for_commercial_readiness:
            raw_claim_requirement_mode = "semi_hard"
            raw_claim_requirement_provenance = _text(
                raw_claim_requirement_provenance,
                "inferred_from_claim_required_flags",
            )
        elif claim_gate_available:
            raw_claim_requirement_mode = "semi_hard"
            raw_claim_requirement_provenance = _text(
                raw_claim_requirement_provenance,
                "inferred_from_claim_gate_availability",
            )
        elif focus_available:
            raw_claim_requirement_mode = "semi_hard"
            raw_claim_requirement_provenance = _text(
                raw_claim_requirement_provenance,
                "inferred_from_selected_focus_missing_claim_contract",
            )
        else:
            raw_claim_requirement_mode = "not_applicable"
            raw_claim_requirement_provenance = _text(
                raw_claim_requirement_provenance,
                "not_reported",
            )
    if not _text(raw_claim_requirement_reason):
        if raw_claim_requirement_mode == "semi_hard" and claim_ready_for_allatom:
            raw_claim_requirement_reason = "claim/equivalence gate is required and already satisfied."
        elif raw_claim_requirement_mode == "semi_hard":
            raw_claim_requirement_reason = "claim/equivalence evidence is required before final release."
        else:
            raw_claim_requirement_reason = "claim/equivalence gate is not applicable."
    if raw_claim_requirement_mode == "semi_hard":
        if not raw_claim_required_for_final_wetlab and not _text(raw_claim_required_for_final_source):
            raw_claim_required_for_final_wetlab = True
        if (
            not raw_claim_required_for_commercial_readiness
            and not _text(raw_claim_required_for_commercial_source)
        ):
            raw_claim_required_for_commercial_readiness = True

    commercial_hard_gate_pass_v2 = bool(_safe_bool(commercial_hard_gate_pass_v2_raw))
    commercial_provenance_mode_v2 = (
        "source_driven"
        if any(
            (
                _text(commercial_schema_version_v2),
                commercial_schema_source_v2,
                commercial_hard_gate_source_v2,
                commercial_overall_source_v2,
                commercial_risk_source_v2,
                commercial_decision_source_v2,
            )
        )
        else "not_reported"
    )
    translation_status = _text(translation_gate_focus_status).lower()
    best_mean_min_distance_A, best_mean_min_distance_source = _pick_value(
        summaries,
        "selected_allatom_best_mean_min_distance_A",
        "best_mean_min_distance_A",
    )
    review_best_mean_min_distance_A, review_best_mean_min_distance_source = _pick_value(
        [("review_packet_summary", review)],
        "best_mean_min_distance_A",
        "selected_allatom_best_mean_min_distance_A",
    )
    if (
        review_best_mean_min_distance_A not in {"", None}
        and _review_metric_matches_selected_focus(
            review=review,
            selected_target_id=selected_target_id,
            selected_surface_label=selected_surface_label,
        )
    ):
        best_mean_min_distance_A = review_best_mean_min_distance_A
        best_mean_min_distance_source = review_best_mean_min_distance_source
    best_mean_min_distance_A = _safe_float(best_mean_min_distance_A, 0.0)
    selected_threshold_A = _safe_float(thresholds.get("selected_threshold_A"), 0.0)
    if (
        translation_status in {"fail", "blocked"}
        and not hard_failed_metrics
        and best_mean_min_distance_A > 0.0
        and selected_threshold_A > 0.0
        and best_mean_min_distance_A > selected_threshold_A
    ):
        hard_failed_metrics = ["mean_min_distance_A"]
    translation_hard_blocked = bool(
        translation_status in {"fail", "blocked"} or hard_failed_metrics or hard_missing_metrics
    )
    commercial_hard_gate_blocked = bool(
        (_text(commercial_schema_version_v2) or commercial_hard_gate_source_v2)
        and not commercial_hard_gate_pass_v2
    )
    hard_block_present = bool(translation_hard_blocked or commercial_hard_gate_blocked)

    effective_claim_requirement_mode = (
        raw_claim_requirement_mode
        if raw_claim_requirement_mode == "semi_hard" and not hard_block_present
        else "not_applicable"
    )
    effective_claim_requirement_status = (
        "satisfied"
        if effective_claim_requirement_mode == "semi_hard" and claim_ready_for_allatom
        else "blocked"
        if effective_claim_requirement_mode == "semi_hard"
        else "not_applicable"
    )
    effective_claim_requirement_reason = (
        "claim/equivalence gate is satisfied"
        if effective_claim_requirement_mode == "semi_hard" and claim_ready_for_allatom
        else "claim/equivalence gate is semi-hard and blocked"
        if effective_claim_requirement_mode == "semi_hard"
        else "claim/equivalence gate is deprioritized until the hard block clears"
        if raw_claim_requirement_mode == "semi_hard" and hard_block_present
        else "claim/equivalence gate is not applicable"
    )

    if final_gate_pass:
        effective_actionability_status = "ready"
    elif hard_block_present:
        effective_actionability_status = "hard_blocked"
    elif effective_claim_requirement_mode == "semi_hard" and not claim_ready_for_allatom:
        effective_actionability_status = "semi_hard_blocked"
    elif _text(recommended_next_expensive_lane, focus_shortlist_tier, translation_gate_focus_reason):
        effective_actionability_status = "soft_guided"
    else:
        effective_actionability_status = "blocked" if operator_review_ready else "not_reported"

    effective_primary_blocking_domain = ""
    if translation_hard_blocked and commercial_hard_gate_blocked:
        effective_primary_blocking_domain = "translation_commercial_hard_gate"
    elif translation_hard_blocked:
        effective_primary_blocking_domain = "translation"
    elif commercial_hard_gate_blocked:
        effective_primary_blocking_domain = "commercial"
    elif effective_claim_requirement_mode == "semi_hard" and not claim_ready_for_allatom:
        effective_primary_blocking_domain = "claim_equivalence"
    elif _text(recommended_next_expensive_lane, focus_shortlist_tier):
        effective_primary_blocking_domain = "soft_guidance"

    effective_blocking_order = "not_reported"
    if final_gate_pass:
        effective_blocking_order = "clear"
    elif hard_block_present:
        effective_blocking_order = (
            "hard_block_first"
            if raw_claim_requirement_mode == "semi_hard"
            else "hard_block_only"
        )
    elif effective_claim_requirement_mode == "semi_hard" and not claim_ready_for_allatom:
        effective_blocking_order = "claim_block_first"
    elif _text(recommended_next_expensive_lane, focus_shortlist_tier):
        effective_blocking_order = "soft_guidance_only"

    metric_values = {
        "replicate_count": review.get("commercial_replicate_count_v2"),
        "replicate_pass_fraction": review.get("commercial_replicate_pass_fraction_v2"),
        "median_mean_min_distance_A": review.get("commercial_median_mean_min_distance_A_v2"),
        "mean_min_distance_iqr_A": review.get("commercial_mean_min_distance_iqr_A_v2"),
        "median_contact_fraction": review.get("commercial_median_contact_fraction_v2"),
        "pose_cluster_dominance": review.get("commercial_pose_cluster_dominance_v2"),
        "pose_preservation_rmsd_A": review.get("commercial_pose_preservation_rmsd_A_v2"),
        "backmapping_consistency_score": review.get("commercial_backmapping_consistency_score_v2"),
        "local_minimization_survival_fraction": review.get("commercial_local_minimization_survival_fraction_v2"),
        "mean_min_distance_A": best_mean_min_distance_A or review.get("best_mean_min_distance_A"),
        "binding_energy_proxy": review.get("commercial_binding_energy_proxy_v2"),
        "stability_score": review.get("commercial_stability_score_v2"),
        "contact_fraction": review.get("commercial_contact_fraction_v2"),
        "binding_energy_mmpbsa_std": review.get("commercial_binding_energy_mmpbsa_std_v2"),
        "trajectory_frames": review.get("commercial_trajectory_frames_v2"),
    }

    action_recipe_rows: list[dict[str, Any]] = []
    action_recipe_codes: list[str] = []
    required_calculations: list[str] = []
    block_reason_codes: list[str] = []
    soft_guidance_reasons: list[str] = []

    if translation_status:
        soft_guidance_reasons.append(f"translation_gate_focus:{translation_status}")
    if _text(focus_shortlist_tier):
        soft_guidance_reasons.append(f"shortlist_tier:{focus_shortlist_tier}")
    if _text(recommended_next_expensive_lane):
        soft_guidance_reasons.append(f"next_expensive_lane:{recommended_next_expensive_lane}")

    for metric_name in list(dict.fromkeys(hard_failed_metrics + hard_missing_metrics)):
        operation_action, calculation_action = _metric_action(metric_name)
        threshold_text = _metric_threshold_text(metric_name, thresholds)
        value_text = _metric_value_text(metric_values.get(metric_name))
        action_status = "missing" if metric_name in hard_missing_metrics else "failed"
        action_recipe_rows.append(
            {
                "severity": "hard",
                "category": "translation_commercial_hard_gate",
                "action": operation_action,
                "calc_action": calculation_action,
                "status": action_status,
                "metric": metric_name,
                "value": value_text,
                "threshold": threshold_text,
                "code": calculation_action,
                "reason": f"{metric_name}={value_text}" + (
                    f" threshold={threshold_text}"
                    if threshold_text and threshold_text != "missing"
                    else ""
                ),
            }
        )
        action_recipe_codes.append(calculation_action)
        required_calculations.append(calculation_action)
        block_reason_codes.append(
            f"{'translation_v2_missing_metric' if action_status == 'missing' else 'translation_v2_hard_metric'}:{metric_name}"
        )

    for check in translation_failed_checks:
        code = f"translation_focus_failed:{check}"
        if code not in action_recipe_codes:
            action_recipe_codes.append(code)
        if code not in block_reason_codes:
            block_reason_codes.append(code)

    for check in translation_warning_checks:
        code = f"translation_focus_warning:{check}"
        if code not in soft_guidance_reasons:
            soft_guidance_reasons.append(code)

    if commercial_hard_gate_blocked:
        block_reason_codes.append("commercial_hard_gate_failed")

    if raw_claim_requirement_mode == "semi_hard":
        claim_actions = raw_claim_requirement_actions or [
            _text(review.get("claim_gate_primary_action"), default="produce_claim_equivalence_packet"),
            "resolve_claim_equivalence_gate",
        ]
        claim_actions = [action for action in claim_actions if action]
        for action_code in claim_actions:
            action_recipe_rows.append(
                {
                    "severity": "semi_hard",
                    "category": "claim_equivalence",
                    "action": action_code,
                    "status": "satisfied" if claim_ready_for_allatom else "required",
                    "code": action_code,
                    "reason": raw_claim_requirement_reason,
                }
            )
            action_recipe_codes.append(action_code)
            if not claim_ready_for_allatom:
                required_calculations.append(action_code)

    if _text(recommended_next_expensive_lane):
        lane_action = (
            "defer_expensive_lane"
            if recommended_next_expensive_lane == "defer_expensive_lane"
            else "enter_expensive_lane"
        )
        action_recipe_rows.append(
            {
                "severity": "soft",
                "category": "next_expensive_lane",
                "action": lane_action,
                "status": "deferred" if lane_action == "defer_expensive_lane" else "queued",
                "code": recommended_next_expensive_lane,
                "lane": recommended_next_expensive_lane,
                "reason": _text(recommended_next_expensive_lane_reason, translation_gate_focus_reason),
            }
        )
        action_recipe_codes.append(recommended_next_expensive_lane)

    for code in translation_action_codes + translation_blocker_codes + lane_action_codes + lane_blocker_codes:
        if code not in action_recipe_codes:
            action_recipe_codes.append(code)

    action_recipe_codes = list(dict.fromkeys(action_recipe_codes))
    required_calculations = list(dict.fromkeys(required_calculations))
    block_reason_codes = list(dict.fromkeys(block_reason_codes))
    soft_guidance_reasons = list(dict.fromkeys(soft_guidance_reasons))

    hard_block_reason_text = ", ".join(
        part
        for part in [
            "translation/commercial hard gate failed" if commercial_hard_gate_blocked else "",
            "translation gate failed" if translation_status in {"fail", "blocked"} else "",
            "failed metrics: " + ", ".join(hard_failed_metrics) if hard_failed_metrics else "",
            "missing metrics: " + ", ".join(hard_missing_metrics) if hard_missing_metrics else "",
        ]
        if part
    )
    effective_block_reason = _text(
        hard_block_reason_text,
        raw_claim_requirement_reason
        if effective_claim_requirement_mode == "semi_hard" and not claim_ready_for_allatom
        else "",
    )
    effective_brief_summary = _joined(
        effective_actionability_status.replace("_", " "),
        (
            f"claim {effective_claim_requirement_mode}:{effective_claim_requirement_status}"
            if effective_claim_requirement_mode
            else ""
        ),
        f"lane {recommended_next_expensive_lane}" if _text(recommended_next_expensive_lane) else "",
    )
    effective_human_summary = _joined(
        (
            f"{effective_actionability_status.replace('_', ' ')}: {effective_block_reason}"
            if effective_block_reason
            else effective_actionability_status.replace("_", " ")
        ),
        (
            f"required calculations: {', '.join(required_calculations)}"
            if required_calculations
            else ""
        ),
        (
            f"soft guidance: {', '.join(soft_guidance_reasons)}"
            if soft_guidance_reasons
            else ""
        ),
        (
            f"claim requirement: {effective_claim_requirement_reason}"
            if raw_claim_requirement_mode == "semi_hard"
            else ""
        ),
        (
            f"next expensive lane: {recommended_next_expensive_lane}"
            if _text(recommended_next_expensive_lane)
            else ""
        ),
    )

    raw_claim = {
        "requirement_mode": _text(raw_claim_requirement_mode, default="not_applicable"),
        "requirement_provenance": _text(
            raw_claim_requirement_provenance,
            raw_claim_required_for_final_source,
            raw_claim_required_for_commercial_source,
            "not_reported",
        ),
        "required_for_final_wetlab": raw_claim_required_for_final_wetlab,
        "required_for_commercial_readiness": raw_claim_required_for_commercial_readiness,
        "requirement_reason": _text(raw_claim_requirement_reason),
        "requirement_actions": list(dict.fromkeys(raw_claim_requirement_actions)),
    }
    effective_actionability = {
        "status": effective_actionability_status,
        "blocked": effective_actionability_status != "ready",
        "brief_summary": effective_brief_summary,
        "human_summary": effective_human_summary,
        "block_reason": effective_block_reason,
        "block_reason_codes": block_reason_codes,
        "soft_guidance_reasons": soft_guidance_reasons,
        "required_calculations": required_calculations,
        "required_calculations_text": ", ".join(required_calculations),
        "action_list": action_recipe_rows,
        "action_list_text": " | ".join(
            f"{row['severity']}:{row['action']}[{row['status']}]"
            + (f" lane={row['lane']}" if row.get("lane") else "")
            for row in action_recipe_rows
        ),
        "claim_requirement_mode": effective_claim_requirement_mode,
        "claim_requirement_status": effective_claim_requirement_status,
        "claim_requirement_reason": effective_claim_requirement_reason,
        "next_expensive_lane": _text(recommended_next_expensive_lane),
        "next_expensive_lane_reason": _text(
            recommended_next_expensive_lane_reason,
            translation_gate_focus_reason,
        ),
        "translation_gate_v2_failed_metrics": hard_failed_metrics,
        "translation_gate_v2_missing_metrics": hard_missing_metrics,
        "translation_gate_v2_thresholds": thresholds,
    }

    commercial = {
        "reported_v2": bool(
            _text(commercial_schema_version_v2)
            or commercial_overall_source_v2
            or commercial_risk_source_v2
            or commercial_decision_source_v2
            or commercial_actions_v2
        ),
        "schema_version_v2": _text(commercial_schema_version_v2),
        "hard_gate_reported_v2": bool(
            commercial_hard_gate_source_v2 or _text(commercial_schema_version_v2)
        ),
        "hard_gate_pass_v2": commercial_hard_gate_pass_v2,
        "soft_score_v2": _safe_float(commercial_soft_score_v2, 0.0),
        "confidence_score_v2": _safe_float(commercial_confidence_score_v2, 0.0),
        "overall_score_v2": _safe_float(commercial_overall_score_v2, 0.0),
        "risk_bucket_v2": _text(commercial_risk_bucket_v2),
        "decision_class_v2": _text(commercial_decision_class_v2),
        "primary_upgrade_actions_v2": commercial_actions_v2,
        "primary_upgrade_actions_text_v2": " | ".join(commercial_actions_v2),
        "human_summary_v2": _text(commercial_human_summary_v2),
    }
    translation = {
        "version": _text(translation_gate_version),
        "focus_status": _text(translation_gate_focus_status),
        "focus_score": _safe_float(translation_gate_focus_score, 0.0),
        "focus_reason": _text(translation_gate_focus_reason),
        "stronger_physics_shortlist_version": _text(stronger_physics_shortlist_version),
        "focus_shortlist_tier": _text(focus_shortlist_tier),
        "recommended_next_expensive_lane": _text(recommended_next_expensive_lane),
        "recommended_next_expensive_lane_reason": _text(recommended_next_expensive_lane_reason),
    }

    return {
        "commercial_schema_version_v2": commercial["schema_version_v2"],
        "commercial_soft_score_v2": commercial["soft_score_v2"],
        "commercial_confidence_score_v2": commercial["confidence_score_v2"],
        "commercial_overall_score_v2": commercial["overall_score_v2"],
        "commercial_risk_bucket_v2": commercial["risk_bucket_v2"],
        "commercial_decision_class_v2": commercial["decision_class_v2"],
        "commercial_hard_gate_pass_v2": commercial["hard_gate_pass_v2"],
        "commercial_primary_upgrade_actions_v2": commercial["primary_upgrade_actions_v2"],
        "commercial_human_summary_v2": commercial["human_summary_v2"],
        "translation_gate_version": translation["version"],
        "translation_gate_focus_status": translation["focus_status"],
        "translation_gate_focus_score": translation["focus_score"],
        "translation_gate_focus_reason": translation["focus_reason"],
        "focus_shortlist_tier": translation["focus_shortlist_tier"],
        "recommended_next_expensive_lane": translation["recommended_next_expensive_lane"],
        "recommended_next_expensive_lane_reason": translation["recommended_next_expensive_lane_reason"],
        "best_mean_min_distance_A": best_mean_min_distance_A,
        "best_mean_min_distance_source": best_mean_min_distance_source,
        "raw_claim_requirement_mode": raw_claim["requirement_mode"],
        "raw_claim_requirement_provenance": raw_claim["requirement_provenance"],
        "raw_claim_required_for_final_wetlab": raw_claim["required_for_final_wetlab"],
        "raw_claim_required_for_commercial_readiness": raw_claim[
            "required_for_commercial_readiness"
        ],
        "raw_claim_requirement_reason": raw_claim["requirement_reason"],
        "effective_actionability_status": effective_actionability["status"],
        "effective_actionability_claim_requirement_mode": effective_actionability[
            "claim_requirement_mode"
        ],
        "effective_actionability_claim_requirement_status": effective_actionability[
            "claim_requirement_status"
        ],
        "effective_actionability_claim_requirement_reason": effective_actionability[
            "claim_requirement_reason"
        ],
        "effective_actionability_next_expensive_lane": effective_actionability[
            "next_expensive_lane"
        ],
        "effective_actionability_next_expensive_lane_reason": effective_actionability[
            "next_expensive_lane_reason"
        ],
        "effective_actionability_required_calculations": effective_actionability[
            "required_calculations"
        ],
        "effective_actionability_action_list": effective_actionability["action_list"],
        "effective_blocking_order": effective_blocking_order,
        "effective_primary_blocking_domain": effective_primary_blocking_domain,
        "action_recipe_codes": action_recipe_codes,
        "action_recipe_rows": action_recipe_rows,
        "translation_provenance_mode": translation_provenance_mode,
        "commercial_provenance_mode_v2": commercial_provenance_mode_v2,
        "hybrid_policy": "canonical_selected_allatom_source_driven_with_translation_text_fallback",
        "commercial": commercial,
        "translation": translation,
        "raw_claim": raw_claim,
        "effective_actionability": effective_actionability,
    }
