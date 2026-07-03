#!/usr/bin/env python3
"""Build the GPCR hard-decoy claim-unlock audit.

This read-only packet separates metric closure evidence from broad GPCR/router
promotion. It can mark Phase 3 hard-decoy metric evidence ready only when the
claim-locked official suite is green before the claim lock, the pre-registered
runner replay clears the hard-decoy gates, and an independent repeat clears its
guarded ranking thresholds. It never promotes claims or mutates external state.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

from tools.gpcr_replay.build_gpcr_active_scorer_promotion_decision_packet import (
    scorecard_metric_ready_under_claim_lock,
)

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OFFICIAL_SUITE_JSON = "runs/gpcr_hard_decoy_suite_current.json"
DEFAULT_PREREGISTERED_REPLAY_JSON = "runs/gpcr_hard_decoy_adora2a_preregistered_replay_current.json"
DEFAULT_INDEPENDENT_REPEAT_JSON = "runs/gpcr_a1_independent_repeat_packet_current.json"
DEFAULT_ACCURACY_SCORECARD_JSON = "runs/accuracy_parity_scorecard_current.json"
DEFAULT_BROAD_SCOPE_READINESS_JSON = "runs/gpcr_broad_claim_scope_readiness_current.json"
DEFAULT_ACTIVE_SCORER_DECISION_JSON = "runs/gpcr_active_scorer_promotion_decision_packet_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_hard_decoy_claim_unlock_audit_current.json"
DEFAULT_OUT_MD = "runs/gpcr_hard_decoy_claim_unlock_audit_current.md"

PACKET_TYPE = "gpcr_hard_decoy_claim_unlock_audit"
SCHEMA_VERSION = "gpcr_hard_decoy_claim_unlock_audit_v1"

CI_LOW_MIN = 0.45
TOP20_MIN = 0.20
REQUIRED_ACTUAL_CLOSURE_TARGET_IDS = ("DRD2", "HTR2A", "OPRM1")
ROOT_CAUSE_DECOY_CLASSES = ("over_anchored", "same_signature", "multipolar")

CLAIM_BOUNDARY = (
    "GPCR hard-decoy claim-unlock audit only. It reads local evidence artifacts and records whether "
    "the claim-locked hard-decoy diagnostic has enough independent metric evidence for Phase 3 metric "
    "closure review. It does not promote broad GPCR, router, platform, or active-scorer claims; run "
    "formal broad-claim review and scorer/router promotion gates separately."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _display(path_like: str | Path) -> str:
    path = Path(path_like)
    if path.is_absolute():
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)
    return str(path)


def _read_json(path_like: str | Path) -> tuple[dict[str, Any], str]:
    path = _resolve(path_like)
    if not path.exists():
        return {}, f"missing:{_display(path)}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, f"unreadable:{_display(path)}"
    return (payload, _display(path)) if isinstance(payload, dict) else ({}, f"invalid:{_display(path)}")


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _gate_row(
    *,
    gate_id: str,
    ready: bool,
    observed: Any,
    threshold: Any,
    blocker: str,
    evidence: str,
) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "status": "ready" if ready else "blocked",
        "observed": observed,
        "threshold": threshold,
        "blocker": "" if ready else blocker,
        "evidence": evidence,
    }


def _promotion_blocker_lane(blocker: str) -> str:
    text = str(blocker)
    if text.startswith("active_scorer:") or "active_scorer" in text or "residual_registry" in text:
        return "active_scorer"
    if "target_heldout" in text:
        return "target_heldout_review"
    if text.startswith("broad_scope:") or "broad_claim" in text or "broad_scope" in text:
        return "broad_scope_review"
    if "scorer_router" in text or "router" in text:
        return "scorer_router_promotion"
    return "gpcr_promotion_review"


def _promotion_blocker_action(blocker: str) -> str:
    text = str(blocker)
    detail = text.split(":", 1)[1] if ":" in text else text
    if detail == "formal_broad_claim_review_not_approved":
        return "Complete and approve the GPCR broad-claim review receipt."
    if detail == "scorer_router_promotion_gate_not_approved":
        return "Approve the scorer/router promotion gate after metric evidence review."
    if detail == "scorer_router_promotion_gate_not_ready":
        return "Refresh scorer/router promotion readiness until the gate is ready."
    if detail == "target_heldout_broad_scope_review_not_approved":
        return "Approve target-heldout broad-scope review before any broad GPCR claim."
    if detail == "active_scorer_apply_not_allowed":
        return "Keep active scorer apply disabled until guarded promotion gates pass."
    if detail == "operational_gate_refresh_not_complete":
        return "Refresh the operational active-scorer gate and rerun the promotion decision packet."
    if detail == "phase_a_claim_closure_not_ready":
        return "Close Phase A claim evidence before active scorer promotion."
    if detail == "residual_registry_production_promotion_not_allowed":
        return "Complete the guarded residual registry promotion operator receipt."
    return "Resolve this GPCR promotion blocker before broad claim unlock."


def _promotion_work_order_rows(
    promotion_blockers: list[str],
    *,
    broad_scope_evidence: str,
    active_scorer_evidence: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for blocker in promotion_blockers:
        lane = _promotion_blocker_lane(blocker)
        source_artifact = active_scorer_evidence if lane == "active_scorer" else broad_scope_evidence
        rows.append(
            {
                "lane_id": lane,
                "blocker": blocker,
                "required_action": _promotion_blocker_action(blocker),
                "source_artifact": source_artifact,
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
                "claim_boundary": CLAIM_BOUNDARY,
            }
        )
    return rows


def _metric_ready(ci_low: float | None, top20: float | None, decoys: float | None, anchor_ready: bool) -> bool:
    return (
        ci_low is not None
        and ci_low >= CI_LOW_MIN
        and top20 is not None
        and top20 >= TOP20_MIN
        and decoys == 0
        and anchor_ready
    )


def _int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number


def _target_by_id(targets: list[Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for target in targets:
        if not isinstance(target, dict):
            continue
        target_id = str(target.get("target_id") or "").strip()
        if target_id:
            rows[target_id] = target
    return rows


def _nonempty_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _decoy_class_clear(target: dict[str, Any], decoy_class: str) -> bool:
    counts = target.get("decoy_class_counts")
    if not isinstance(counts, dict):
        return False
    return _int(counts.get(decoy_class)) == 0


def _actual_closure_target_rows(
    *,
    official_targets: list[Any],
    replay_target_rows: dict[str, Any],
    required_target_ids: tuple[str, ...] = REQUIRED_ACTUAL_CLOSURE_TARGET_IDS,
) -> list[dict[str, Any]]:
    official_by_id = _target_by_id(official_targets)
    rows: list[dict[str, Any]] = []
    for target_id in required_target_ids:
        official = official_by_id.get(target_id, {})
        replay = replay_target_rows.get(target_id)
        replay_row = replay if isinstance(replay, dict) else {}
        ranking_pr_auc = _float(official.get("ranking_pr_auc"))
        ci_low = _float(official.get("ranking_pr_auc_ci_low"))
        top20 = _float(official.get("top20_hit_rate"))
        decoys = _int(official.get("decoys_above_positive_count"))
        anchor_margin = _float(official.get("anchor_margin_a"))
        blockers = [str(item) for item in _nonempty_list(official.get("blockers"))]
        root_causes = [str(item) for item in _nonempty_list(official.get("root_cause_tags"))]
        decoy_class_counts = official.get("decoy_class_counts")
        if not isinstance(decoy_class_counts, dict):
            decoy_class_counts = {}
        actual_values_populated = all(
            value is not None for value in (ranking_pr_auc, ci_low, top20, decoys, anchor_margin)
        )
        positive_not_out_anchored = anchor_margin is not None and anchor_margin >= 0.0
        closure_ready = (
            actual_values_populated
            and ci_low is not None
            and ci_low >= CI_LOW_MIN
            and top20 is not None
            and top20 >= TOP20_MIN
            and decoys == 0
            and positive_not_out_anchored
            and official.get("gate_status") == "green"
            and official.get("claim_safe") is True
            and not blockers
        )
        rows.append(
            {
                "target_id": target_id,
                "status": "ready" if closure_ready else "blocked",
                "actual_values_populated": actual_values_populated,
                "closure_ready": closure_ready,
                "gate_status": official.get("gate_status", "missing"),
                "claim_safe_before_broad_lock": official.get("claim_safe") is True,
                "ranking_pr_auc": ranking_pr_auc,
                "ranking_pr_auc_ci_low": ci_low,
                "ranking_pr_auc_ci_low_min": CI_LOW_MIN,
                "top20_hit_rate": top20,
                "top20_hit_rate_min": TOP20_MIN,
                "decoys_above_positive_count": decoys,
                "decoys_above_positive_count_max": 0,
                "positive_target_rank": _int(official.get("positive_target_rank")),
                "positive_anchor_distance_a": _float(official.get("positive_anchor_distance_a")),
                "top_decoy_anchor_distance_a": _float(official.get("top_decoy_anchor_distance_a")),
                "anchor_margin_a": anchor_margin,
                "positive_not_out_anchored_by_top_decoy": positive_not_out_anchored,
                "positive_ligand_id": str(replay_row.get("positive_ligand_id") or ""),
                "top_decoy_ligand_id": str(replay_row.get("top_decoy_ligand_id") or ""),
                "retained_target_row_count": _int(official.get("retained_target_row_count")),
                "retained_positive_count": _int(official.get("retained_positive_count")),
                "top_decoy_retained_count": _int(official.get("top_decoy_retained_count")),
                "decoy_class_counts": decoy_class_counts,
                "over_anchored_decoy_count": _int(decoy_class_counts.get("over_anchored")),
                "same_signature_decoy_count": _int(decoy_class_counts.get("same_signature")),
                "multipolar_decoy_count": _int(decoy_class_counts.get("multipolar")),
                "root_cause_tags": root_causes,
                "blockers": blockers,
                "claim_promotion_allowed": False,
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_boundary": CLAIM_BOUNDARY,
            }
        )
    return rows


def _actual_closure_requirement_rows(
    target_rows: list[dict[str, Any]],
    *,
    effective_metrics: dict[str, Any],
    official_diagnostic_green: bool,
    preregistered_replay_ready: bool,
    repeat_metric_ready: bool,
    broad_promotion_remains_locked: bool,
) -> list[dict[str, Any]]:
    target_by_id = {str(row.get("target_id")): row for row in target_rows}
    required_present = all(target_by_id.get(target_id, {}).get("actual_values_populated") for target_id in REQUIRED_ACTUAL_CLOSURE_TARGET_IDS)
    all_targets_ready = all(target_by_id.get(target_id, {}).get("closure_ready") is True for target_id in REQUIRED_ACTUAL_CLOSURE_TARGET_IDS)
    target_ci_values = [
        _float(row.get("ranking_pr_auc_ci_low")) for row in target_rows if _float(row.get("ranking_pr_auc_ci_low")) is not None
    ]
    target_top20_values = [
        _float(row.get("top20_hit_rate")) for row in target_rows if _float(row.get("top20_hit_rate")) is not None
    ]
    target_decoy_total = sum(_int(row.get("decoys_above_positive_count")) or 0 for row in target_rows)
    anchor_ready = all(row.get("positive_not_out_anchored_by_top_decoy") is True for row in target_rows)
    root_cause_clear = {
        decoy_class: all(_decoy_class_clear(row, decoy_class) for row in target_rows)
        for decoy_class in ROOT_CAUSE_DECOY_CLASSES
    }
    aggregate_ci = _float(effective_metrics.get("ranking_pr_auc_ci_low"))
    aggregate_top20 = _float(effective_metrics.get("top20_hit_rate"))
    aggregate_decoys = _int(effective_metrics.get("decoys_above_positive_count"))
    rows = [
        {
            "requirement_id": "drd2_htr2a_oprm1_actual_rows_populated",
            "status": "ready" if required_present else "blocked",
            "observed": sorted(target_by_id),
            "threshold": list(REQUIRED_ACTUAL_CLOSURE_TARGET_IDS),
            "blocker": "" if required_present else "required_gpcr_actual_target_rows_missing_or_incomplete",
            "claim_promotion_allowed": False,
        },
        {
            "requirement_id": "ranking_pr_auc_ci_low_ge_0p45",
            "status": "ready"
            if aggregate_ci is not None
            and aggregate_ci >= CI_LOW_MIN
            and target_ci_values
            and min(target_ci_values) >= CI_LOW_MIN
            else "blocked",
            "observed": {"effective": aggregate_ci, "target_min": min(target_ci_values) if target_ci_values else None},
            "threshold": CI_LOW_MIN,
            "blocker": "gpcr_hard_decoy_ranking_pr_auc_ci_low_below_gate",
            "claim_promotion_allowed": False,
        },
        {
            "requirement_id": "top20_hit_rate_ge_0p20",
            "status": "ready"
            if aggregate_top20 is not None
            and aggregate_top20 >= TOP20_MIN
            and target_top20_values
            and min(target_top20_values) >= TOP20_MIN
            else "blocked",
            "observed": {"effective": aggregate_top20, "target_min": min(target_top20_values) if target_top20_values else None},
            "threshold": TOP20_MIN,
            "blocker": "gpcr_hard_decoy_top20_hit_rate_below_gate",
            "claim_promotion_allowed": False,
        },
        {
            "requirement_id": "decoys_above_positive_count_eq_0",
            "status": "ready" if aggregate_decoys == 0 and target_decoy_total == 0 else "blocked",
            "observed": {"effective": aggregate_decoys, "target_total": target_decoy_total},
            "threshold": 0,
            "blocker": "gpcr_hard_decoy_decoys_above_positive_present",
            "claim_promotion_allowed": False,
        },
        {
            "requirement_id": "positive_not_out_anchored_by_top_decoys",
            "status": "ready" if anchor_ready else "blocked",
            "observed": [row.get("anchor_margin_a") for row in target_rows],
            "threshold": "all target anchor margins >= 0.0",
            "blocker": "gpcr_hard_decoy_positive_out_anchored_by_top_decoy",
            "claim_promotion_allowed": False,
        },
        {
            "requirement_id": "over_anchored_decoy_response_clear",
            "status": "ready" if root_cause_clear["over_anchored"] else "blocked",
            "observed": [row.get("over_anchored_decoy_count") for row in target_rows],
            "threshold": "all required target over_anchored decoy counts == 0",
            "blocker": "gpcr_hard_decoy_over_anchored_decoys_present",
            "claim_promotion_allowed": False,
        },
        {
            "requirement_id": "same_signature_decoy_response_clear",
            "status": "ready" if root_cause_clear["same_signature"] else "blocked",
            "observed": [row.get("same_signature_decoy_count") for row in target_rows],
            "threshold": "all required target same_signature decoy counts == 0",
            "blocker": "gpcr_hard_decoy_same_signature_decoys_present",
            "claim_promotion_allowed": False,
        },
        {
            "requirement_id": "multipolar_decoy_response_clear",
            "status": "ready" if root_cause_clear["multipolar"] else "blocked",
            "observed": [row.get("multipolar_decoy_count") for row in target_rows],
            "threshold": "all required target multipolar decoy counts == 0",
            "blocker": "gpcr_hard_decoy_multipolar_decoys_present",
            "claim_promotion_allowed": False,
        },
        {
            "requirement_id": "hard_decoy_suite_repeat_evidence_ready",
            "status": "ready"
            if official_diagnostic_green and preregistered_replay_ready and repeat_metric_ready and all_targets_ready
            else "blocked",
            "observed": {
                "official_diagnostic_green": official_diagnostic_green,
                "preregistered_replay_ready": preregistered_replay_ready,
                "independent_repeat_ready": repeat_metric_ready,
                "all_required_targets_ready": all_targets_ready,
            },
            "threshold": "official suite, pre-registered replay, independent repeat, and target rows ready",
            "blocker": "gpcr_hard_decoy_repeat_evidence_not_ready",
            "claim_promotion_allowed": False,
        },
        {
            "requirement_id": "broad_gpcr_claim_locked_until_ledger_approval",
            "status": "ready" if broad_promotion_remains_locked else "blocked",
            "observed": {
                "broad_promotion_remains_locked": broad_promotion_remains_locked,
                "claim_promotion_allowed": False,
            },
            "threshold": "broad claim remains locked until ledger/operator approval",
            "blocker": "broad_gpcr_claim_not_locked_for_ledger_review",
            "claim_promotion_allowed": False,
        },
    ]
    for row in rows:
        if row["status"] == "ready":
            row["blocker"] = ""
        row["execution_enabled"] = False
        row["external_state_mutated"] = False
        row["claim_boundary"] = CLAIM_BOUNDARY
    return rows


def build_gpcr_hard_decoy_claim_unlock_audit(
    *,
    official_suite_json: str | Path = DEFAULT_OFFICIAL_SUITE_JSON,
    preregistered_replay_json: str | Path = DEFAULT_PREREGISTERED_REPLAY_JSON,
    independent_repeat_json: str | Path = DEFAULT_INDEPENDENT_REPEAT_JSON,
    accuracy_scorecard_json: str | Path = DEFAULT_ACCURACY_SCORECARD_JSON,
    broad_scope_readiness_json: str | Path = DEFAULT_BROAD_SCOPE_READINESS_JSON,
    active_scorer_decision_json: str | Path = DEFAULT_ACTIVE_SCORER_DECISION_JSON,
) -> dict[str, Any]:
    official, official_evidence = _read_json(official_suite_json)
    preregistered, preregistered_evidence = _read_json(preregistered_replay_json)
    independent_repeat, independent_repeat_evidence = _read_json(independent_repeat_json)
    scorecard, scorecard_evidence = _read_json(accuracy_scorecard_json)
    broad_scope, broad_scope_evidence = _read_json(broad_scope_readiness_json)
    active_scorer, active_scorer_evidence = _read_json(active_scorer_decision_json)

    official_summary = _summary(official)
    repeat_summary = _summary(independent_repeat)
    broad_summary = _summary(broad_scope)
    active_summary = _summary(active_scorer)
    scorecard_readiness = scorecard_metric_ready_under_claim_lock(scorecard)

    official_required_targets = [str(item) for item in _list(official_summary.get("required_target_ids"))]
    official_green_targets = [str(item) for item in _list(official_summary.get("green_target_ids"))]
    official_blocked_targets = [str(item) for item in _list(official_summary.get("blocked_target_ids"))]
    official_missing_targets = [str(item) for item in _list(official_summary.get("missing_required_target_ids"))]
    official_diagnostic_green = (
        official_summary.get("claim_locked") is True
        and official_summary.get("diagnostic_status_before_claim_lock") == "gpcr_hard_decoy_family_ready"
        and official_summary.get("diagnostic_family_claim_safe_before_claim_lock") is True
        and not official_blocked_targets
        and not official_missing_targets
        and set(official_required_targets).issubset(set(official_green_targets))
    )

    preregistered_metrics = _dict(preregistered.get("runner_replay_target_heldout"))
    preregistered_ci = _float(preregistered_metrics.get("ranking_pr_auc_ci_low"))
    preregistered_top20 = _float(preregistered_metrics.get("top20_hit_rate"))
    preregistered_decoys = _float(preregistered_metrics.get("target_decoys_above_positive_total"))
    preregistered_anchor_ready = preregistered_metrics.get("all_required_targets_anchor_margin_nonnegative") is True
    preregistered_decoy_clear = (
        preregistered_metrics.get("all_required_targets_decoy_clear") is True and preregistered_decoys == 0
    )
    preregistered_metric_ready = _metric_ready(
        preregistered_ci,
        preregistered_top20,
        preregistered_decoys,
        preregistered_anchor_ready and preregistered_decoy_clear,
    )
    preregistered_replay_ready = (
        preregistered.get("status") == "gpcr_hard_decoy_adora2a_preregistered_replay_gate_pass_claim_locked"
        and preregistered.get("pre_registered_runner_replay_complete") is True
        and preregistered.get("runner_replay_closure_gate_pass") is True
        and (
            preregistered.get("score_matches_probe") is True
            or preregistered.get("runner_replay_matches_probe_score") is True
        )
        and preregistered.get("claim_promotion_allowed") is False
        and preregistered.get("canonical_runner_shadow_only_active_locked") is True
        and preregistered_metric_ready
    )

    repeat_ci = _float(repeat_summary.get("ranking_pr_auc_ci_low"))
    repeat_top20 = _float(repeat_summary.get("ranking_top20_hit_rate"))
    repeat_metric_ready = (
        repeat_summary.get("status") == "independent_repeat_passed_claim_locked"
        and repeat_summary.get("independent_repeat_completed") is True
        and repeat_summary.get("independent_repeat_result_passed") is True
        and repeat_summary.get("claim_promotion_allowed") is False
        and repeat_ci is not None
        and repeat_ci >= CI_LOW_MIN
        and repeat_top20 is not None
        and repeat_top20 >= TOP20_MIN
    )
    scorecard_metric_ready = bool(scorecard_readiness.get("metric_ready"))
    hard_decoy_metric_ready = bool(
        official_diagnostic_green
        and preregistered_replay_ready
        and repeat_metric_ready
        and scorecard_metric_ready
    )

    effective_ci_values = [value for value in (preregistered_ci, repeat_ci) if value is not None]
    effective_top20_values = [value for value in (preregistered_top20, repeat_top20) if value is not None]
    effective_metrics = {
        "ranking_pr_auc_ci_low": min(effective_ci_values) if effective_ci_values else None,
        "top20_hit_rate": min(effective_top20_values) if effective_top20_values else None,
        "decoys_above_positive_count": None if preregistered_decoys is None else int(preregistered_decoys),
        "anchor_margin_nonnegative": preregistered_anchor_ready,
        "source": "claim_locked_official_suite_plus_preregistered_replay_plus_independent_repeat",
    }

    metric_blockers: list[str] = []
    if not official_diagnostic_green:
        metric_blockers.append("official_suite_not_diagnostic_green_claim_locked")
    if not preregistered_replay_ready:
        metric_blockers.append("preregistered_runner_replay_not_ready")
    if not repeat_metric_ready:
        metric_blockers.append("independent_repeat_metric_evidence_not_passed")
    if not scorecard_metric_ready:
        metric_blockers.append("accuracy_parity_metric_not_ready")

    broad_blockers = [str(item) for item in _list(broad_summary.get("blockers"))]
    active_blockers = [str(item) for item in _list(active_summary.get("blockers"))]
    promotion_blockers: list[str] = []
    if broad_summary.get("target_heldout_broad_scope_review_approved") is not True:
        promotion_blockers.append("target_heldout_broad_scope_review_not_approved")
    if broad_summary.get("scorer_router_promotion_gate_ready") is not True:
        promotion_blockers.append("scorer_router_promotion_gate_not_ready")
    if active_summary.get("active_scorer_apply_allowed") is not True:
        promotion_blockers.append("active_scorer_apply_not_allowed")
    promotion_blockers.extend(f"broad_scope:{item}" for item in broad_blockers)
    promotion_blockers.extend(f"active_scorer:{item}" for item in active_blockers)
    promotion_blockers = sorted(set(promotion_blockers))
    promotion_work_order_rows = _promotion_work_order_rows(
        promotion_blockers,
        broad_scope_evidence=broad_scope_evidence,
        active_scorer_evidence=active_scorer_evidence,
    )
    replay_target_rows = preregistered_metrics.get("target_rows")
    replay_target_rows = replay_target_rows if isinstance(replay_target_rows, dict) else {}
    actual_closure_target_rows = _actual_closure_target_rows(
        official_targets=_list(official.get("targets")),
        replay_target_rows=replay_target_rows,
    )
    actual_closure_requirement_rows = _actual_closure_requirement_rows(
        actual_closure_target_rows,
        effective_metrics=effective_metrics,
        official_diagnostic_green=official_diagnostic_green,
        preregistered_replay_ready=preregistered_replay_ready,
        repeat_metric_ready=repeat_metric_ready,
        broad_promotion_remains_locked=bool(promotion_blockers),
    )
    actual_closure_ready_target_ids = [
        str(row["target_id"]) for row in actual_closure_target_rows if row.get("closure_ready") is True
    ]
    actual_closure_missing_target_ids = [
        target_id
        for target_id in REQUIRED_ACTUAL_CLOSURE_TARGET_IDS
        if not any(
            row.get("target_id") == target_id and row.get("actual_values_populated") is True
            for row in actual_closure_target_rows
        )
    ]
    actual_closure_blockers = sorted(
        str(row["blocker"])
        for row in actual_closure_requirement_rows
        if row.get("status") != "ready" and row.get("blocker")
    )
    actual_closure_metric_blockers = sorted(
        str(row["blocker"])
        for row in actual_closure_requirement_rows
        if row.get("requirement_id") != "broad_gpcr_claim_locked_until_ledger_approval"
        and row.get("status") != "ready"
        and row.get("blocker")
    )
    actual_closure_metrics_ready = not actual_closure_metric_blockers
    actual_closure_ready = actual_closure_metrics_ready and bool(promotion_blockers)
    if actual_closure_metric_blockers:
        metric_blockers.append("actual_closure_target_rows_not_ready")
    hard_decoy_metric_ready = bool(hard_decoy_metric_ready and actual_closure_metrics_ready)

    rows = [
        _gate_row(
            gate_id="official_suite_diagnostic_green_claim_locked",
            ready=official_diagnostic_green,
            observed=official_summary.get("status", "missing"),
            threshold="claim_locked diagnostic family-ready with all required targets green",
            blocker="official_suite_not_diagnostic_green_claim_locked",
            evidence=official_evidence,
        ),
        _gate_row(
            gate_id="preregistered_runner_replay_gate",
            ready=preregistered_replay_ready,
            observed=preregistered.get("status", "missing"),
            threshold="pre-registered replay complete, score-match, hard-decoy gates pass, claim locked",
            blocker="preregistered_runner_replay_not_ready",
            evidence=preregistered_evidence,
        ),
        _gate_row(
            gate_id="hard_decoy_ranking_pr_auc_ci_low",
            ready=preregistered_ci is not None and preregistered_ci >= CI_LOW_MIN,
            observed="" if preregistered_ci is None else preregistered_ci,
            threshold=CI_LOW_MIN,
            blocker="hard_decoy_ranking_pr_auc_ci_low_below_gate",
            evidence=preregistered_evidence,
        ),
        _gate_row(
            gate_id="hard_decoy_top20_hit_rate",
            ready=preregistered_top20 is not None and preregistered_top20 >= TOP20_MIN,
            observed="" if preregistered_top20 is None else preregistered_top20,
            threshold=TOP20_MIN,
            blocker="hard_decoy_top20_hit_rate_below_gate",
            evidence=preregistered_evidence,
        ),
        _gate_row(
            gate_id="hard_decoy_decoys_above_positive_count",
            ready=preregistered_decoys == 0 and preregistered_decoy_clear,
            observed="" if preregistered_decoys is None else int(preregistered_decoys),
            threshold=0,
            blocker="hard_decoy_decoys_above_positive_present",
            evidence=preregistered_evidence,
        ),
        _gate_row(
            gate_id="hard_decoy_anchor_margin",
            ready=preregistered_anchor_ready,
            observed=preregistered_anchor_ready,
            threshold="all required targets nonnegative",
            blocker="hard_decoy_positive_out_anchored_by_top_decoy",
            evidence=preregistered_evidence,
        ),
        _gate_row(
            gate_id="independent_repeat_metric_passed",
            ready=repeat_metric_ready,
            observed=repeat_summary.get("status", "missing"),
            threshold="independent repeat completed and passed guarded ranking thresholds",
            blocker="independent_repeat_metric_evidence_not_passed",
            evidence=independent_repeat_evidence,
        ),
        _gate_row(
            gate_id="accuracy_parity_metric_ready_under_claim_lock",
            ready=scorecard_metric_ready,
            observed=scorecard_readiness.get("status", "missing"),
            threshold="metric-ready restricted pass or green scorecard",
            blocker="accuracy_parity_metric_not_ready",
            evidence=scorecard_evidence,
        ),
    ]

    if hard_decoy_metric_ready:
        status = "gpcr_hard_decoy_claim_unlock_metric_evidence_ready_promotion_locked"
        next_required_step = (
            "Phase 3 hard-decoy metric evidence is ready for operator review, but broad/router/scorer promotion "
            "remains locked. Fill the broad-claim review receipt and scorer/router promotion gates before any "
            "claim promotion."
        )
    else:
        status = "blocked_gpcr_hard_decoy_claim_unlock_audit"
        next_required_step = "Resolve metric blockers before treating the claim-locked hard-decoy suite as Phase 3 ready."

    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "phase3_exit_metric_conditions_ready": hard_decoy_metric_ready,
        "hard_decoy_metric_claim_unlock_ready": hard_decoy_metric_ready,
        "operator_claim_review_ready": hard_decoy_metric_ready,
        "broad_promotion_remains_locked": bool(promotion_blockers),
        "claim_promotion_allowed": False,
        "router_claim_allowed": False,
        "platform_claim_allowed": False,
        "official_suite_diagnostic_green_claim_locked": official_diagnostic_green,
        "official_suite_status": official_summary.get("status", "missing"),
        "official_claim_lock_reason": official_summary.get("claim_lock_reason", ""),
        "preregistered_replay_status": preregistered.get("status", "missing"),
        "preregistered_replay_complete": preregistered.get("pre_registered_runner_replay_complete") is True,
        "preregistered_replay_gate_pass": preregistered.get("runner_replay_closure_gate_pass") is True,
        "preregistered_replay_score_matches_probe": (
            preregistered.get("score_matches_probe") is True
            or preregistered.get("runner_replay_matches_probe_score") is True
        ),
        "preregistered_ranking_pr_auc_ci_low": preregistered_ci,
        "preregistered_top20_hit_rate": preregistered_top20,
        "preregistered_decoys_above_positive_count": (
            None if preregistered_decoys is None else int(preregistered_decoys)
        ),
        "preregistered_anchor_margin_nonnegative": preregistered_anchor_ready,
        "independent_repeat_status": repeat_summary.get("status", "missing"),
        "independent_repeat_completed": repeat_summary.get("independent_repeat_completed") is True,
        "independent_repeat_result_passed": repeat_summary.get("independent_repeat_result_passed") is True,
        "independent_repeat_ready_to_launch": repeat_summary.get("independent_repeat_ready") is True,
        "independent_repeat_ranking_pr_auc_ci_low": repeat_ci,
        "independent_repeat_top20_hit_rate": repeat_top20,
        "accuracy_parity_metric_ready": scorecard_metric_ready,
        "accuracy_parity_metric_blockers": scorecard_readiness.get("metric_blockers", []),
        "accuracy_parity_claim_scope_lock_only": bool(scorecard_readiness.get("claim_scope_lock_only")),
        "effective_phase3_metrics": effective_metrics,
        "gpcr_hard_decoy_actual_closure_metrics_ready": actual_closure_metrics_ready,
        "gpcr_hard_decoy_actual_closure_ready": actual_closure_ready,
        "actual_closure_required_target_ids": list(REQUIRED_ACTUAL_CLOSURE_TARGET_IDS),
        "actual_closure_target_row_count": len(actual_closure_target_rows),
        "actual_closure_ready_target_ids": actual_closure_ready_target_ids,
        "actual_closure_missing_target_ids": actual_closure_missing_target_ids,
        "actual_closure_requirement_ready_count": sum(
            1 for row in actual_closure_requirement_rows if row.get("status") == "ready"
        ),
        "actual_closure_requirement_blocked_count": sum(
            1 for row in actual_closure_requirement_rows if row.get("status") != "ready"
        ),
        "actual_closure_blocker_count": len(actual_closure_blockers),
        "actual_closure_blockers": actual_closure_blockers,
        "actual_closure_metric_blocker_count": len(actual_closure_metric_blockers),
        "actual_closure_metric_blockers": actual_closure_metric_blockers,
        "broad_gpcr_claim_locked_until_ledger_approval": bool(promotion_blockers),
        "metric_blocker_count": len(metric_blockers),
        "metric_blockers": sorted(metric_blockers),
        "promotion_blocker_count": len(promotion_blockers),
        "promotion_blockers": promotion_blockers,
        "promotion_work_order_ready": not promotion_work_order_rows,
        "promotion_work_order_row_count": len(promotion_work_order_rows),
        "promotion_work_order_lane_count": len(
            {row["lane_id"] for row in promotion_work_order_rows}
        ),
        "promotion_work_order_primary_lane_id": (
            promotion_work_order_rows[0]["lane_id"] if promotion_work_order_rows else ""
        ),
        "promotion_work_order_primary_blocker": (
            promotion_work_order_rows[0]["blocker"] if promotion_work_order_rows else ""
        ),
        "broad_scope_readiness_status": broad_summary.get("status", "missing"),
        "active_scorer_decision_status": active_summary.get("status", "missing"),
        "next_required_step": next_required_step,
    }

    return {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "summary": summary,
        "rows": rows,
        "actual_closure_target_rows": actual_closure_target_rows,
        "actual_closure_requirement_rows": actual_closure_requirement_rows,
        "promotion_work_order_rows": promotion_work_order_rows,
        "evidence": {
            "official_suite_json": official_evidence,
            "preregistered_replay_json": preregistered_evidence,
            "independent_repeat_json": independent_repeat_evidence,
            "accuracy_scorecard_json": scorecard_evidence,
            "broad_scope_readiness_json": broad_scope_evidence,
            "active_scorer_decision_json": active_scorer_evidence,
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    metric_blockers = summary.get("metric_blockers") if isinstance(summary.get("metric_blockers"), list) else []
    promotion_blockers = (
        summary.get("promotion_blockers") if isinstance(summary.get("promotion_blockers"), list) else []
    )
    lines = [
        "# GPCR Hard-Decoy Claim-Unlock Audit",
        "",
        f"- status: `{summary['status']}`",
        f"- phase3_exit_metric_conditions_ready: `{str(summary['phase3_exit_metric_conditions_ready']).lower()}`",
        f"- hard_decoy_metric_claim_unlock_ready: `{str(summary['hard_decoy_metric_claim_unlock_ready']).lower()}`",
        f"- broad_promotion_remains_locked: `{str(summary['broad_promotion_remains_locked']).lower()}`",
        f"- claim_promotion_allowed: `{str(summary['claim_promotion_allowed']).lower()}`",
        f"- preregistered_ranking_pr_auc_ci_low: `{summary['preregistered_ranking_pr_auc_ci_low']}`",
        f"- preregistered_top20_hit_rate: `{summary['preregistered_top20_hit_rate']}`",
        f"- preregistered_decoys_above_positive_count: `{summary['preregistered_decoys_above_positive_count']}`",
        f"- independent_repeat_ranking_pr_auc_ci_low: `{summary['independent_repeat_ranking_pr_auc_ci_low']}`",
        f"- independent_repeat_top20_hit_rate: `{summary['independent_repeat_top20_hit_rate']}`",
        f"- gpcr_hard_decoy_actual_closure_ready: `{str(summary['gpcr_hard_decoy_actual_closure_ready']).lower()}`",
        f"- actual_closure_ready_target_ids: `{', '.join(summary['actual_closure_ready_target_ids']) or '(none)'}`",
        f"- actual_closure_blockers: `{', '.join(summary['actual_closure_blockers']) or '(none)'}`",
        f"- metric_blockers: `{', '.join(metric_blockers) or '(none)'}`",
        f"- promotion_blockers: `{', '.join(promotion_blockers) or '(none)'}`",
        f"- promotion_work_order_row_count: `{summary['promotion_work_order_row_count']}`",
        "",
        "## Gates",
        "",
        "| gate | status | observed | threshold | blocker |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| `{gate}` | `{status}` | `{observed}` | `{threshold}` | {blocker} |".format(
                gate=row["gate_id"],
                status=row["status"],
                observed=row["observed"],
                threshold=row["threshold"],
                blocker=row["blocker"] or "(none)",
            )
        )
    lines.extend(
        [
            "",
            "## Actual Closure Targets",
            "",
            "| target | status | CI-low | top20 | decoys_above | anchor_margin | not_out_anchored | blockers |",
            "| --- | --- | --: | --: | --: | --: | --- | --- |",
        ]
    )
    for row in payload.get("actual_closure_target_rows", []):
        blockers = row.get("blockers") if isinstance(row.get("blockers"), list) else []
        lines.append(
            "| `{target}` | `{status}` | `{ci}` | `{top20}` | `{decoys}` | `{anchor}` | `{anchor_ready}` | {blockers} |".format(
                target=row.get("target_id", ""),
                status=row.get("status", ""),
                ci=row.get("ranking_pr_auc_ci_low"),
                top20=row.get("top20_hit_rate"),
                decoys=row.get("decoys_above_positive_count"),
                anchor=row.get("anchor_margin_a"),
                anchor_ready=str(row.get("positive_not_out_anchored_by_top_decoy")).lower(),
                blockers=", ".join(str(item) for item in blockers) or "(none)",
            )
        )
    lines.extend(
        [
            "",
            "## Actual Closure Checklist",
            "",
            "| requirement | status | observed | threshold | blocker |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload.get("actual_closure_requirement_rows", []):
        lines.append(
            "| `{requirement}` | `{status}` | `{observed}` | `{threshold}` | {blocker} |".format(
                requirement=row.get("requirement_id", ""),
                status=row.get("status", ""),
                observed=row.get("observed"),
                threshold=row.get("threshold"),
                blocker=row.get("blocker") or "(none)",
            )
        )
    lines.extend(
        [
            "",
            "## Promotion Work Order",
            "",
            "| lane | blocker | action | source |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in payload.get("promotion_work_order_rows", []):
        lines.append(
            f"| `{row['lane_id']}` | `{row['blocker']}` | {row['required_action']} | "
            f"`{row['source_artifact']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def write_outputs(payload: dict[str, Any], *, out_json: str | Path, out_md: str | Path) -> None:
    json_path = _resolve(out_json)
    md_path = _resolve(out_md)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-suite-json", default=DEFAULT_OFFICIAL_SUITE_JSON)
    parser.add_argument("--preregistered-replay-json", default=DEFAULT_PREREGISTERED_REPLAY_JSON)
    parser.add_argument("--independent-repeat-json", default=DEFAULT_INDEPENDENT_REPEAT_JSON)
    parser.add_argument("--accuracy-scorecard-json", default=DEFAULT_ACCURACY_SCORECARD_JSON)
    parser.add_argument("--broad-scope-readiness-json", default=DEFAULT_BROAD_SCOPE_READINESS_JSON)
    parser.add_argument("--active-scorer-decision-json", default=DEFAULT_ACTIVE_SCORER_DECISION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_gpcr_hard_decoy_claim_unlock_audit(
        official_suite_json=args.official_suite_json,
        preregistered_replay_json=args.preregistered_replay_json,
        independent_repeat_json=args.independent_repeat_json,
        accuracy_scorecard_json=args.accuracy_scorecard_json,
        broad_scope_readiness_json=args.broad_scope_readiness_json,
        active_scorer_decision_json=args.active_scorer_decision_json,
    )
    write_outputs(payload, out_json=args.out_json, out_md=args.out_md)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
