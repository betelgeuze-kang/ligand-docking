#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from tools.wetlab_allatom_refinement_utils import _rank_rows_by_active_score, _selection_ranking_score_value
from tools.wetlab_broad_screen_watch_utils import slug
from tools.wetlab_pose_validation_utils import build_pose_validation_fields, summarize_pose_validation_rows
from tools.wetlab_target_render_utils import load_json, write_artifact

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESCUE_LANE_JSON = "runs/wetlab_hard_target_rescue_lane_current.json"
DEFAULT_STAGE6_FAILURE_SURFACE_JSON = "runs/wetlab_primary_stage6_failure_surface_current.json"
DEFAULT_RETRY_POLICY_TEMPLATES_JSON = "runs/wetlab_target_retry_policy_templates_current.json"
DEFAULT_OUT_MD = "runs/wetlab_rescue_three_bead_candidates_current.md"
DEFAULT_TOP_N = 32
TRANSLATION_GATE_VERSION = "three_bead_to_allatom_translation_v2"
STRONGER_PHYSICS_SHORTLIST_VERSION = "stronger_physics_shortlist_v2"
RESCUE_POSE_PRESERVATION_RMSD_MAX = 2.40
RESCUE_BACKMAPPING_CONSISTENCY_MIN = 0.58
RESCUE_STRONG_POSE_PRESERVATION_RMSD_MAX = 1.80
RESCUE_STRONG_BACKMAPPING_CONSISTENCY_MIN = 0.72


def _text(value: Any) -> str:
    return "" if value in {None, ""} else str(value).strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {None, ""}:
            return default
        return float(value)
    except Exception:
        return default


def _safe_optional_float(value: Any) -> float | None:
    try:
        if value in {None, ""}:
            return None
        return float(value)
    except Exception:
        return None


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _score_lower_better(value: Any, *, good: float, bad: float) -> float | None:
    if value in {None, ""}:
        return None
    try:
        numeric = float(value)
    except Exception:
        return None
    if numeric <= good:
        return 1.0
    if numeric >= bad:
        return 0.0
    if bad <= good:
        return 0.0
    return _clamp((bad - numeric) / (bad - good))


def _score_higher_better(value: Any, *, good: float, bad: float) -> float | None:
    if value in {None, ""}:
        return None
    try:
        numeric = float(value)
    except Exception:
        return None
    if numeric >= good:
        return 1.0
    if numeric <= bad:
        return 0.0
    if good <= bad:
        return 0.0
    return _clamp((numeric - bad) / (good - bad))


def _sorted_unique(values: list[str]) -> list[str]:
    return sorted({value for value in values if _text(value)})


def _translation_band_bucket(review_band: Any, mean_min_distance_A: Any) -> str:
    band = _text(review_band).lower()
    if "strict" in band:
        return "strict"
    if "near" in band:
        return "near"
    distance = _safe_float(mean_min_distance_A, float("nan"))
    if distance == distance:
        if distance <= 2.5:
            return "strict"
        if distance <= 3.0:
            return "near"
    return "other"


def annotate_translation_gate_row(
    row: dict[str, Any],
    *,
    review_band: Any = "",
    distance_key: str = "mean_min_distance_A",
    energy_key: str = "binding_energy_proxy",
    stability_key: str = "stability_score",
    contact_key: str = "contact_fraction",
    frames_key: str = "trajectory_frames",
    pose_rmsd_key: str = "pose_preservation_rmsd_A",
    backmapping_key: str = "backmapping_consistency_score",
    local_min_survival_key: str = "local_minimization_survival_fraction",
    replicate_pass_fraction_key: str = "replicate_pass_fraction",
) -> dict[str, Any]:
    annotated = dict(row or {})
    distance = _safe_float(annotated.get(distance_key), float("nan"))
    energy = _safe_float(annotated.get(energy_key), float("nan"))
    stability = _safe_float(annotated.get(stability_key), float("nan"))
    contact = _safe_float(annotated.get(contact_key), float("nan"))
    frames = _safe_float(annotated.get(frames_key), float("nan"))
    pose_rmsd = _safe_optional_float(annotated.get(pose_rmsd_key))
    backmapping_consistency = _safe_optional_float(annotated.get(backmapping_key))
    local_min_survival = _safe_optional_float(annotated.get(local_min_survival_key))
    replicate_pass_fraction = _safe_optional_float(annotated.get(replicate_pass_fraction_key))
    band_bucket = _translation_band_bucket(review_band, annotated.get(distance_key))
    annotated.update(
        build_pose_validation_fields(
            pose_preservation_rmsd_A=pose_rmsd,
            backmapping_consistency_score=backmapping_consistency,
            pose_preservation_rmsd_A_max=RESCUE_POSE_PRESERVATION_RMSD_MAX,
            backmapping_consistency_score_min=RESCUE_BACKMAPPING_CONSISTENCY_MIN,
            strong_pose_preservation_rmsd_A_max=RESCUE_STRONG_POSE_PRESERVATION_RMSD_MAX,
            strong_backmapping_consistency_score_min=RESCUE_STRONG_BACKMAPPING_CONSISTENCY_MIN,
        )
    )

    distance_score = _score_lower_better(distance, good=2.5, bad=3.5)
    energy_score = _score_lower_better(energy, good=-0.8, bad=-0.35)
    stability_score = _score_higher_better(stability, good=0.6, bad=0.25)
    contact_score = _score_higher_better(contact, good=0.7, bad=0.35)
    support_score = _score_higher_better(frames, good=220.0, bad=120.0)
    pose_rmsd_score = _score_lower_better(pose_rmsd, good=1.8, bad=3.0)
    backmapping_score = _score_higher_better(backmapping_consistency, good=0.78, bad=0.45)
    local_min_score = _score_higher_better(local_min_survival, good=0.78, bad=0.45)
    replicate_score = _score_higher_better(replicate_pass_fraction, good=0.75, bad=0.40)

    required_weights = [
        (distance_score, 0.36),
        (energy_score, 0.18),
        (stability_score, 0.14),
    ]
    optional_weights = [
        (contact_score, 0.08),
        (support_score, 0.06),
        (pose_rmsd_score, 0.08),
        (backmapping_score, 0.05),
        (local_min_score, 0.03),
        (replicate_score, 0.02),
    ]
    weighted_sum = 0.0
    weight_total = 0.0
    for score, weight in [*required_weights, *optional_weights]:
        if score is None:
            continue
        weighted_sum += score * weight
        weight_total += weight
    translation_score = round(100.0 * (weighted_sum / weight_total), 1) if weight_total else 0.0

    failed_checks: list[str] = []
    warning_checks: list[str] = []
    passed_checks: list[str] = []
    hard_failed_checks: list[str] = []
    soft_warning_checks: list[str] = []
    action_codes: list[str] = []
    blocker_codes: list[str] = []

    if distance == distance:
        if distance <= 3.10:
            passed_checks.append("distance_within_translation_near_band")
        else:
            failed_checks.append("distance_above_translation_near_band")
            hard_failed_checks.append("distance_above_translation_near_band")
            blocker_codes.append("translation_geometry_outside_near_band")
            action_codes.append("tighten_pose_geometry_under_translation_band")
    else:
        failed_checks.append("missing_mean_min_distance_A")
        hard_failed_checks.append("missing_mean_min_distance_A")
        blocker_codes.append("missing_translation_distance")
        action_codes.append("capture_translation_distance_signal")
    if energy == energy:
        if energy <= -0.55:
            passed_checks.append("binding_energy_proxy_supports_translation")
        else:
            failed_checks.append("binding_energy_proxy_too_weak_for_translation")
            hard_failed_checks.append("binding_energy_proxy_too_weak_for_translation")
            blocker_codes.append("translation_energy_too_weak")
            action_codes.append("strengthen_three_bead_binding_energy")
    else:
        failed_checks.append("missing_binding_energy_proxy")
        hard_failed_checks.append("missing_binding_energy_proxy")
        blocker_codes.append("missing_translation_energy")
        action_codes.append("capture_translation_energy_signal")
    if stability == stability:
        if stability >= 0.32:
            passed_checks.append("stability_supports_translation")
        else:
            failed_checks.append("stability_too_low_for_translation")
            hard_failed_checks.append("stability_too_low_for_translation")
            blocker_codes.append("translation_stability_too_low")
            action_codes.append("raise_three_bead_stability")
    else:
        failed_checks.append("missing_stability_score")
        hard_failed_checks.append("missing_stability_score")
        blocker_codes.append("missing_translation_stability")
        action_codes.append("capture_translation_stability_signal")

    if contact == contact:
        if contact >= 0.45:
            passed_checks.append("contact_fraction_supportive")
        else:
            warning_checks.append("contact_fraction_below_support_target")
            soft_warning_checks.append("contact_fraction_below_support_target")
            action_codes.append("increase_contact_occupancy")
    else:
        warning_checks.append("contact_fraction_not_observed")
        soft_warning_checks.append("contact_fraction_not_observed")
        action_codes.append("measure_contact_occupancy")
    if frames == frames:
        if frames >= 120:
            passed_checks.append("trajectory_support_present")
        else:
            warning_checks.append("trajectory_support_sparse")
            soft_warning_checks.append("trajectory_support_sparse")
            action_codes.append("increase_trajectory_support")
    else:
        warning_checks.append("trajectory_frames_not_observed")
        soft_warning_checks.append("trajectory_frames_not_observed")
        action_codes.append("increase_trajectory_support")

    if pose_rmsd is None:
        warning_checks.append("pose_preservation_rmsd_not_observed")
        soft_warning_checks.append("pose_preservation_rmsd_not_observed")
        action_codes.append("measure_pose_preservation_rmsd")
    elif pose_rmsd <= 2.4:
        passed_checks.append("pose_preservation_rmsd_supports_translation")
        if pose_rmsd <= 1.8:
            passed_checks.append("pose_preservation_rmsd_strong")
    else:
        failed_checks.append("pose_preservation_rmsd_too_high")
        hard_failed_checks.append("pose_preservation_rmsd_too_high")
        blocker_codes.append("pose_preservation_breaks_translation")
        action_codes.append("repair_pose_preservation_geometry")

    if backmapping_consistency is None:
        warning_checks.append("backmapping_consistency_not_observed")
        soft_warning_checks.append("backmapping_consistency_not_observed")
        action_codes.append("measure_backmapping_consistency")
    elif backmapping_consistency >= 0.58:
        passed_checks.append("backmapping_consistency_supports_translation")
        if backmapping_consistency >= 0.72:
            passed_checks.append("backmapping_consistency_strong")
    else:
        failed_checks.append("backmapping_consistency_too_low")
        hard_failed_checks.append("backmapping_consistency_too_low")
        blocker_codes.append("backmapping_consistency_breaks_translation")
        action_codes.append("repair_backmapping_consistency")

    if local_min_survival is None:
        warning_checks.append("local_minimization_survival_not_observed")
        soft_warning_checks.append("local_minimization_survival_not_observed")
        action_codes.append("measure_local_minimization_survival")
    elif local_min_survival >= 0.55:
        passed_checks.append("local_minimization_survival_supports_translation")
        if local_min_survival >= 0.72:
            passed_checks.append("local_minimization_survival_strong")
    else:
        failed_checks.append("local_minimization_survival_too_low")
        hard_failed_checks.append("local_minimization_survival_too_low")
        blocker_codes.append("local_minimization_breaks_translation")
        action_codes.append("stabilize_local_minimization_survival")

    if replicate_pass_fraction is None:
        warning_checks.append("replicate_pass_fraction_not_observed")
        soft_warning_checks.append("replicate_pass_fraction_not_observed")
        action_codes.append("collect_replicate_translation_support")
    elif replicate_pass_fraction >= 0.50:
        passed_checks.append("replicate_pass_fraction_supports_translation")
        if replicate_pass_fraction >= 0.70:
            passed_checks.append("replicate_pass_fraction_strong")
    else:
        failed_checks.append("replicate_pass_fraction_too_low")
        hard_failed_checks.append("replicate_pass_fraction_too_low")
        blocker_codes.append("replicate_consensus_breaks_translation")
        action_codes.append("increase_replicate_pass_fraction")

    required_pass_count = sum(
        1
        for check in (
            "distance_within_translation_near_band",
            "binding_energy_proxy_supports_translation",
            "stability_supports_translation",
        )
        if check in passed_checks
    )
    structural_failed_checks = [
        check
        for check in hard_failed_checks
        if check
        not in {
            "distance_above_translation_near_band",
            "missing_mean_min_distance_A",
            "binding_energy_proxy_too_weak_for_translation",
            "missing_binding_energy_proxy",
            "stability_too_low_for_translation",
            "missing_stability_score",
        }
    ]
    hard_fail = bool(
        hard_failed_checks
        and any(
            key in hard_failed_checks
            for key in (
                "distance_above_translation_near_band",
                "missing_mean_min_distance_A",
                "binding_energy_proxy_too_weak_for_translation",
                "missing_binding_energy_proxy",
                "stability_too_low_for_translation",
                "missing_stability_score",
            )
        )
    )

    if hard_fail:
        translation_hard_status = "fail"
    elif structural_failed_checks:
        translation_hard_status = "repairable_fail"
    else:
        translation_hard_status = "pass"

    if translation_score >= 82.0:
        translation_soft_status = "strong"
    elif translation_score >= 64.0:
        translation_soft_status = "watch"
    else:
        translation_soft_status = "weak"

    if (not hard_fail) and (not structural_failed_checks) and required_pass_count == 3 and translation_score >= 72.0:
        translation_status = "pass"
        translation_reason = "3-bead geometry, energy, and survival signals are coherent enough for direct all-atom translation."
    elif required_pass_count >= 2 and distance == distance and distance <= 3.35 and translation_score >= 50.0:
        translation_status = "borderline"
        if structural_failed_checks:
            translation_reason = "Translation remains repairable, but advanced translation signals already show geometry or survival loss."
        else:
            translation_reason = "Translation is plausible but missing or soft support suggests one more repair-or-validate step before expensive all-atom escalation."
    else:
        translation_status = "fail"
        translation_reason = "3-bead evidence is too weak for direct all-atom translation without repair."

    explicit_water_ready = (
        translation_status == "pass"
        and band_bucket == "strict"
        and translation_score >= 82.0
        and pose_rmsd is not None
        and pose_rmsd <= 1.8
        and backmapping_consistency is not None
        and backmapping_consistency >= 0.72
        and local_min_survival is not None
        and local_min_survival >= 0.72
        and replicate_pass_fraction is not None
        and replicate_pass_fraction >= 0.70
    )
    seed_md_ready = (
        translation_status == "pass"
        and translation_score >= 64.0
        and translation_hard_status == "pass"
    )
    repair_lane_ready = (
        translation_status == "borderline"
        and translation_score >= 50.0
        and bool(
            {"pose_preservation_breaks_translation", "backmapping_consistency_breaks_translation", "local_minimization_breaks_translation"}
            & set(blocker_codes)
        )
    )

    if explicit_water_ready:
        shortlist_tier = "tier1_gold"
        recommended_lane = "ensemble_explicit_water_mmgbsa"
        recommended_lane_priority = 1
        recommended_lane_reason = "Strict-band rescue already satisfies translation v2 hard checks and replicate-aware geometry support."
        recommended_lane_entry_status = "open"
        recommended_lane_gate = "strict_high_confidence_translation_v2"
        recommended_lane_action = "run_ensemble_explicit_water_mmgbsa"
    elif seed_md_ready:
        shortlist_tier = "tier2_silver"
        recommended_lane = "seed_replicated_short_md_consensus"
        recommended_lane_priority = 2
        recommended_lane_reason = "Translation passes the hard gate, but replicate-aware validation should precede explicit-water spend."
        recommended_lane_entry_status = "open"
        recommended_lane_gate = "translation_v2_validate_with_short_md"
        recommended_lane_action = "run_seed_replicated_short_md_consensus"
    elif repair_lane_ready:
        shortlist_tier = "tier3_bronze"
        recommended_lane = "pose_repair_then_explicit_water_minimization"
        recommended_lane_priority = 3
        recommended_lane_reason = "Repairable translation failures point to pose-preservation or minimization repair before stronger-physics ranking."
        recommended_lane_entry_status = "repair_then_reopen"
        recommended_lane_gate = "repair_translation_geometry_before_expensive_lane"
        recommended_lane_action = "run_pose_repair_then_explicit_water_minimization"
    else:
        shortlist_tier = "defer"
        recommended_lane = "defer_expensive_lane"
        recommended_lane_priority = 0
        recommended_lane_reason = "Do not spend stronger-physics budget until the translation hard gate or survival support improves."
        recommended_lane_entry_status = "closed"
        recommended_lane_gate = "translation_v2_blocked"
        recommended_lane_action = "defer_expensive_lane"

    if translation_status != "pass" or band_bucket != "strict":
        action_codes.append("tighten_pose_geometry_under_strict_gate")
    if translation_status == "fail":
        blocker_codes.append("translation_gate_v2_not_ready")
    elif translation_status == "borderline":
        blocker_codes.append("translation_gate_v2_requires_repair_or_validation")

    action_codes = _sorted_unique(action_codes)
    blocker_codes = _sorted_unique(blocker_codes)
    hard_failed_checks = _sorted_unique(hard_failed_checks)
    soft_warning_checks = _sorted_unique(soft_warning_checks)
    failed_checks = _sorted_unique(failed_checks)
    warning_checks = _sorted_unique(warning_checks)
    passed_checks = _sorted_unique(passed_checks)

    annotated.update(
        {
            "translation_gate_version": TRANSLATION_GATE_VERSION,
            "translation_gate_band_bucket": band_bucket,
            "translation_gate_score": translation_score,
            "translation_gate_soft_score": translation_score,
            "translation_gate_status": translation_status,
            "translation_gate_hard_status": translation_hard_status,
            "translation_gate_soft_status": translation_soft_status,
            "translation_gate_pass": translation_status == "pass",
            "translation_gate_required_check_count": 3,
            "translation_gate_required_pass_count": required_pass_count,
            "translation_gate_optional_check_count": 6,
            "translation_gate_optional_pass_count": sum(
                1
                for check in (
                    "contact_fraction_supportive",
                    "trajectory_support_present",
                    "pose_preservation_rmsd_supports_translation",
                    "backmapping_consistency_supports_translation",
                    "local_minimization_survival_supports_translation",
                    "replicate_pass_fraction_supports_translation",
                )
                if check in passed_checks
            ),
            "translation_gate_hard_check_count": 3 + sum(
                1 for value in (pose_rmsd, backmapping_consistency, local_min_survival, replicate_pass_fraction) if value is not None
            ),
            "translation_gate_hard_pass_count": required_pass_count + sum(
                1
                for check in (
                    "pose_preservation_rmsd_supports_translation",
                    "backmapping_consistency_supports_translation",
                    "local_minimization_survival_supports_translation",
                    "replicate_pass_fraction_supports_translation",
                )
                if check in passed_checks
            ),
            "translation_gate_hard_failed_checks": hard_failed_checks,
            "translation_gate_soft_warning_checks": soft_warning_checks,
            "translation_gate_failed_checks": failed_checks,
            "translation_gate_warning_checks": warning_checks,
            "translation_gate_passed_checks": passed_checks,
            "translation_gate_requires_pose_tightening": translation_status != "pass" or band_bucket != "strict",
            "translation_gate_reason": translation_reason,
            "translation_gate_action_codes": action_codes,
            "translation_gate_blocker_codes": blocker_codes,
            "stronger_physics_shortlist_version": STRONGER_PHYSICS_SHORTLIST_VERSION,
            "shortlist_tier": shortlist_tier,
            "shortlist_promising": shortlist_tier != "defer",
            "recommended_next_expensive_lane": recommended_lane,
            "recommended_next_expensive_lane_priority": recommended_lane_priority,
            "recommended_next_expensive_lane_reason": recommended_lane_reason,
            "recommended_next_expensive_lane_entry_status": recommended_lane_entry_status,
            "recommended_next_expensive_lane_gate": recommended_lane_gate,
            "recommended_next_expensive_lane_action": recommended_lane_action,
            "recommended_next_expensive_lane_blocker_codes": blocker_codes,
            "recommended_next_expensive_lane_action_codes": action_codes,
        }
    )
    return annotated


def summarize_translation_gate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pass_count = sum(1 for row in rows if _text(row.get("translation_gate_status")) == "pass")
    borderline_count = sum(1 for row in rows if _text(row.get("translation_gate_status")) == "borderline")
    fail_count = sum(1 for row in rows if _text(row.get("translation_gate_status")) == "fail")
    hard_pass_count = sum(1 for row in rows if _text(row.get("translation_gate_hard_status")) == "pass")
    hard_repairable_fail_count = sum(1 for row in rows if _text(row.get("translation_gate_hard_status")) == "repairable_fail")
    hard_fail_count = sum(1 for row in rows if _text(row.get("translation_gate_hard_status")) == "fail")
    promising_count = sum(1 for row in rows if bool(row.get("shortlist_promising", False)))
    tier1_count = sum(1 for row in rows if _text(row.get("shortlist_tier")) == "tier1_gold")
    tier2_count = sum(1 for row in rows if _text(row.get("shortlist_tier")) == "tier2_silver")
    tier3_count = sum(1 for row in rows if _text(row.get("shortlist_tier")) == "tier3_bronze")
    defer_count = sum(1 for row in rows if _text(row.get("shortlist_tier")) == "defer")
    focus = rows[0] if rows else {}
    lane_counts: dict[str, int] = {}
    lane_entry_counts: dict[str, int] = {}
    action_counts: dict[str, int] = {}
    blocker_counts: dict[str, int] = {}
    for row in rows:
        lane = _text(row.get("recommended_next_expensive_lane"))
        if lane:
            lane_counts[lane] = lane_counts.get(lane, 0) + 1
        lane_entry_status = _text(row.get("recommended_next_expensive_lane_entry_status"))
        if lane_entry_status:
            lane_entry_counts[lane_entry_status] = lane_entry_counts.get(lane_entry_status, 0) + 1
        for code in list(row.get("translation_gate_action_codes", []) or []):
            action_counts[_text(code)] = action_counts.get(_text(code), 0) + 1
        for code in list(row.get("translation_gate_blocker_codes", []) or []):
            blocker_counts[_text(code)] = blocker_counts.get(_text(code), 0) + 1
    recommended_lane_counts = [
        {"recommended_next_expensive_lane": lane, "candidate_count": count}
        for lane, count in sorted(lane_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    lane_entry_status_counts = [
        {"recommended_next_expensive_lane_entry_status": status, "candidate_count": count}
        for status, count in sorted(lane_entry_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    translation_gate_action_counts = [
        {"translation_gate_action_code": code, "candidate_count": count}
        for code, count in sorted(action_counts.items(), key=lambda item: (-item[1], item[0]))
        if code
    ]
    translation_gate_blocker_counts = [
        {"translation_gate_blocker_code": code, "candidate_count": count}
        for code, count in sorted(blocker_counts.items(), key=lambda item: (-item[1], item[0]))
        if code
    ]
    return {
        "translation_gate_version": TRANSLATION_GATE_VERSION,
        "translation_gate_pass_count": pass_count,
        "translation_gate_borderline_count": borderline_count,
        "translation_gate_fail_count": fail_count,
        "translation_gate_hard_pass_count": hard_pass_count,
        "translation_gate_hard_repairable_fail_count": hard_repairable_fail_count,
        "translation_gate_hard_fail_count": hard_fail_count,
        "translation_gate_focus_status": _text(focus.get("translation_gate_status")),
        "translation_gate_focus_score": focus.get("translation_gate_score"),
        "translation_gate_focus_reason": _text(focus.get("translation_gate_reason")),
        "translation_gate_focus_hard_status": _text(focus.get("translation_gate_hard_status")),
        "translation_gate_focus_soft_status": _text(focus.get("translation_gate_soft_status")),
        "translation_gate_focus_hard_failed_checks": list(focus.get("translation_gate_hard_failed_checks", []) or []),
        "translation_gate_focus_failed_checks": list(focus.get("translation_gate_failed_checks", []) or []),
        "translation_gate_focus_warning_checks": list(focus.get("translation_gate_warning_checks", []) or []),
        "translation_gate_focus_soft_warning_checks": list(focus.get("translation_gate_soft_warning_checks", []) or []),
        "translation_gate_focus_action_codes": list(focus.get("translation_gate_action_codes", []) or []),
        "translation_gate_focus_blocker_codes": list(focus.get("translation_gate_blocker_codes", []) or []),
        "stronger_physics_shortlist_version": STRONGER_PHYSICS_SHORTLIST_VERSION,
        "shortlist_promising_count": promising_count,
        "shortlist_tier1_gold_count": tier1_count,
        "shortlist_tier2_silver_count": tier2_count,
        "shortlist_tier3_bronze_count": tier3_count,
        "shortlist_defer_count": defer_count,
        "focus_shortlist_tier": _text(focus.get("shortlist_tier")),
        "focus_recommended_next_expensive_lane": _text(focus.get("recommended_next_expensive_lane")),
        "focus_recommended_next_expensive_lane_reason": _text(focus.get("recommended_next_expensive_lane_reason")),
        "focus_recommended_next_expensive_lane_entry_status": _text(
            focus.get("recommended_next_expensive_lane_entry_status")
        ),
        "focus_recommended_next_expensive_lane_gate": _text(focus.get("recommended_next_expensive_lane_gate")),
        "focus_recommended_next_expensive_lane_action": _text(focus.get("recommended_next_expensive_lane_action")),
        "focus_recommended_next_expensive_lane_action_codes": list(
            focus.get("recommended_next_expensive_lane_action_codes", []) or []
        ),
        "focus_recommended_next_expensive_lane_blocker_codes": list(
            focus.get("recommended_next_expensive_lane_blocker_codes", []) or []
        ),
        "recommended_next_expensive_lane_counts": recommended_lane_counts,
        "recommended_next_expensive_lane_entry_status_counts": lane_entry_status_counts,
        "translation_gate_action_counts": translation_gate_action_counts,
        "translation_gate_blocker_counts": translation_gate_blocker_counts,
    }


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    if (not str(path).strip()) or (not path.exists()) or path.is_dir():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _resolve_stage3_scores_csv(summary_json: str, summary_payload: dict[str, Any]) -> Path:
    artifacts = dict(summary_payload.get("artifacts", {}) or {})
    text = _text(artifacts.get("stage3_scores_csv"))
    if text:
        return Path(text)
    artifact_dir = Path(summary_json).parent
    for candidate in [
        artifact_dir / "throughput_run_stage3_scores.csv",
        artifact_dir / "throughput_run_gate45_stage3_scores.csv",
        artifact_dir / "throughput_run_gate51_stage3_scores.csv",
        artifact_dir / "throughput_run_gate55_stage3_scores.csv",
    ]:
        if candidate.exists():
            return candidate
    return Path("/__missing_stage3_scores_csv__")


def _summary_payload(summary_json: str) -> dict[str, Any]:
    path = Path(summary_json)
    if (not str(path).strip()) or (not path.exists()) or path.is_dir():
        return {}
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _resolve_rescue_lane_payload(
    rescue_lane_payload: dict[str, Any],
    *,
    rescue_lane_json: str = DEFAULT_RESCUE_LANE_JSON,
    stage6_failure_surface_json: str = DEFAULT_STAGE6_FAILURE_SURFACE_JSON,
    retry_policy_templates_json: str = DEFAULT_RETRY_POLICY_TEMPLATES_JSON,
) -> dict[str, Any]:
    if rescue_lane_payload.get("rows", []) or []:
        return rescue_lane_payload
    lane_payload = load_json(rescue_lane_json)
    if lane_payload.get("rows", []) or []:
        return lane_payload
    from tools import build_wetlab_hard_target_rescue_lane as rescue_lane_mod

    return rescue_lane_mod.build_payload(
        load_json(stage6_failure_surface_json),
        load_json(retry_policy_templates_json),
    )


def build_payload(
    rescue_lane_payload: dict[str, Any],
    *,
    top_n: int = DEFAULT_TOP_N,
) -> dict[str, Any]:
    candidate_rows = [
        dict(row or {})
        for row in rescue_lane_payload.get("rows", []) or []
        if bool((row or {}).get("top_n_three_bead_recommended", False) or (row or {}).get("three_bead_recommended", False))
    ]
    out_rows: list[dict[str, Any]] = []
    for candidate in candidate_rows:
        target_id = _text(candidate.get("target_id"))
        shard_id = _text(candidate.get("shard_id"))
        target_slug = _text(candidate.get("target_slug")) or slug(target_id)
        summary_payload = _summary_payload(_text(candidate.get("summary_json")))
        stage3_scores_csv = _resolve_stage3_scores_csv(_text(candidate.get("summary_json")), summary_payload)
        rows = _read_csv_rows(stage3_scores_csv)
        ranked, ranking_meta = _rank_rows_by_active_score(
            rows,
            score_sources=(candidate, summary_payload),
        )
        selection_score_col = _text(ranking_meta.get("score_col")) or "binding_energy_proxy"
        candidate_top_n = max(1, int(candidate.get("top_n_three_bead_count", candidate.get("three_bead_top_n", top_n)) or top_n))
        for idx, row in enumerate(ranked[:candidate_top_n], start=1):
            selection_score_value = _selection_ranking_score_value(row, selection_score_col)
            annotated_row = annotate_translation_gate_row(
                {
                    "row_kind": "three_bead_rescue_candidate",
                    "target_id": target_id,
                    "target_slug": target_slug,
                    "shard_id": shard_id,
                    "priority_rank": idx,
                    "ligand_id": _text(row.get("ligand_id")),
                    "binding_energy_proxy": _safe_float(row.get("binding_energy_proxy")),
                    "stability_score": _safe_float(row.get("stability_score")),
                    "mean_min_distance_A": _safe_float(row.get("mean_min_distance_A")),
                    "contact_fraction": _safe_optional_float(row.get("contact_fraction")),
                    "trajectory_frames": _safe_optional_float(row.get("trajectory_frames")),
                    "pose_preservation_rmsd_A": _safe_optional_float(row.get("pose_preservation_rmsd_A")),
                    "backmapping_consistency_score": _safe_optional_float(row.get("backmapping_consistency_score")),
                    "local_minimization_survival_fraction": _safe_optional_float(
                        row.get("local_minimization_survival_fraction")
                    ),
                    "replicate_pass_fraction": _safe_optional_float(row.get("replicate_pass_fraction")),
                    "selection_score_col": selection_score_col,
                    "selection_score_value": selection_score_value,
                    "selection_score_source": _text(ranking_meta.get("score_source")),
                    "three_bead_rescue_reason": "hard_target_stage6_fail_above_5A",
                    "top_n_requested": candidate_top_n,
                },
                review_band=row.get("rescue_review_band"),
            )
            out_rows.append(annotated_row)

    focus = out_rows[0] if out_rows else {}
    ranking_score_cols_used = sorted({_text(row.get("selection_score_col")) for row in out_rows if _text(row.get("selection_score_col"))})
    translation_summary = summarize_translation_gate_rows(out_rows)
    pose_validation_summary = summarize_pose_validation_rows(out_rows)
    return {
        "summary": {
            "status": "wetlab_rescue_three_bead_candidates_ready",
            "candidate_target_count": len({_text(row.get('target_id')) for row in out_rows if _text(row.get('target_id'))}),
            "candidate_row_count": len(out_rows),
            "candidate_count": len(out_rows),
            "top_n_per_target": int(top_n),
            "top_n": int(top_n),
            "focus_target_id": _text(focus.get("target_id")),
            "focus_shard_id": _text(focus.get("shard_id")),
            "focus_ligand_id": _text(focus.get("ligand_id")),
            "target_id": _text(focus.get("target_id")),
            "shard_id": _text(focus.get("shard_id")),
            "ligand_id": _text(focus.get("ligand_id")),
            "selected_command_kind": "three_bead_rescue_local_refine",
            "selected_threshold_A": 2.5,
            "selection_score_col": _text(focus.get("selection_score_col")),
            "selection_score_source": _text(focus.get("selection_score_source")),
            "selection_score_direction": "ascending",
            "focus_selection_score_value": focus.get("selection_score_value"),
            "selection_score_cols_used": ranking_score_cols_used,
            **translation_summary,
            **pose_validation_summary,
            "next_required_step": (
                (
                    f"Reserve top-{int(top_n)} 3-bead rescue for {_text(focus.get('target_id'))} {_text(focus.get('shard_id'))}, "
                    f"then promote the focus ligand to `{_text(focus.get('recommended_next_expensive_lane'))}` if pseudo-all-atom translation stays stable."
                )
                if focus
                else "No >5A hard-target rescue candidate is currently queued for 3-bead escalation."
            ),
        },
        "structured": {
            "rescue_lane_artifact": "runs/wetlab_hard_target_rescue_lane_current.md",
        },
        "rows": out_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build top-N 3-bead rescue candidates from hard-target rescue lane focus rows.")
    parser.add_argument("--rescue-lane-json", default=DEFAULT_RESCUE_LANE_JSON)
    parser.add_argument("--stage6-failure-surface-json", default=DEFAULT_STAGE6_FAILURE_SURFACE_JSON)
    parser.add_argument("--retry-policy-templates-json", default=DEFAULT_RETRY_POLICY_TEMPLATES_JSON)
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _resolve_rescue_lane_payload(
            load_json(args.rescue_lane_json),
            rescue_lane_json=args.rescue_lane_json,
            stage6_failure_surface_json=args.stage6_failure_surface_json,
            retry_policy_templates_json=args.retry_policy_templates_json,
        ),
        top_n=max(1, int(args.top_n)),
    )
    write_artifact(args.out_md, "Wet-Lab Rescue Three-Bead Candidates", payload)


if __name__ == "__main__":
    main()
